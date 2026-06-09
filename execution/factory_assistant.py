"""
PVWood ERP — Factory Assistant

A read-only Claude-powered chat surface with three tools:
  1. query_database(sql)        — execute a SELECT against the live DB
  2. read_server_log(lines)     — tail the persistent server log
  3. export_to_excel(rows, sheet_name, filename)
                                 — write rows to xlsx, return download path

The agent runs Claude in a tool-use loop until it produces a final text-only
response. Every SQL query is validated against an allowlist (SELECT only,
single statement, no PRAGMA / ATTACH / vacuum etc.) so the assistant cannot
mutate the DB even if the model is confused.

Generated Excel files live in `backups/factory_assistant/` and are served
via the /api/factory-assistant/export/<filename> endpoint so users can
download them with one click from the chat UI.
"""

from __future__ import annotations
import os, re, json, sqlite3, datetime, uuid
from typing import Any

try:
    from config import ANTHROPIC_API_KEY, LOG_PATH, BACKUP_DIR, DB_PATH, make_anthropic_client
except ImportError:
    from execution.config import ANTHROPIC_API_KEY, LOG_PATH, BACKUP_DIR, DB_PATH, make_anthropic_client

# Memory layer (conversation history + operational knowledge).
try:
    from database import (fa_save_message, fa_get_recent_messages,
                          fa_search_knowledge, fa_add_knowledge)
except ImportError:
    from execution.database import (fa_save_message, fa_get_recent_messages,
                          fa_search_knowledge, fa_add_knowledge)

# make_anthropic_client() pins the public endpoint + x-api-key auth and
# strips host-injected ANTHROPIC_AUTH_TOKEN/BASE_URL/CUSTOM_HEADERS that
# otherwise hijack the SDK (see config.py for the full rationale).
try:
    _client = make_anthropic_client()
except Exception:
    _client = None

# Where generated xlsx files live. Served via the FastAPI endpoint.
EXPORT_DIR = os.path.join(BACKUP_DIR, "factory_assistant")
os.makedirs(EXPORT_DIR, exist_ok=True)

# Bound the heavy bits so a runaway request can't lock up the server.
MAX_SQL_ROWS    = 10_000
MAX_LOG_LINES   = 2_000
MAX_TOOL_LOOPS  = 12          # tool calls per chat turn — usually 1–3
MAX_OUTPUT_TKNS = 4096

# Block any keyword that mutates state, even when wrapped in a CTE.
_FORBIDDEN_SQL = re.compile(
    r"\b(?:insert|update|delete|drop|alter|create|attach|detach|"
    r"pragma|vacuum|reindex|replace)\b",
    re.IGNORECASE,
)

# Tool schema sent to Claude. Keep descriptions concrete — the better the
# model knows what each tool does, the fewer wasted turns.
TOOLS = [
    {
        "name": "query_database",
        "description": (
            "Execute a single read-only SQL query against the live PVWood "
            "ERP SQLite database and return matching rows as a list of "
            "objects. Only SELECT statements are allowed; INSERT/UPDATE/"
            "DELETE/DDL are rejected. The result is capped at "
            f"{MAX_SQL_ROWS} rows — apply LIMIT in your query for narrower "
            "questions. Tables include: materials, batches, prod_batches, "
            "purchase_orders, purchase_requests, consumable_request, "
            "manufacturing_line, departments, line_flow, glue_recipes, "
            "production_orders, bom_lines, skus, packing_skus, "
            "material_lots, station_stock, dept_activities, employees, "
            "users, login_log, fc_transfer_requests, scrap_log. Run "
            "`PRAGMA table_info(<name>)`-style discovery? No — use "
            "list_tables and describe_table tools instead."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "sql": {
                    "type": "string",
                    "description": "A single SELECT statement.",
                },
            },
            "required": ["sql"],
        },
    },
    {
        "name": "list_tables",
        "description": "List every table in the ERP database.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "describe_table",
        "description": "Return the column schema for one table (name + type + nullable + default + primary key flag).",
        "input_schema": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Table name."},
            },
            "required": ["name"],
        },
    },
    {
        "name": "read_server_log",
        "description": (
            "Return the last N lines from the persistent server log "
            "(uvicorn + FastAPI + project log streams). Use to investigate "
            f"errors, slow endpoints, or recent activity. N defaults to 200; max is {MAX_LOG_LINES}."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "lines": {
                    "type": "integer",
                    "description": "Number of trailing lines to return (1..2000).",
                },
            },
        },
    },
    {
        "name": "export_to_excel",
        "description": (
            "Write a list of row-objects to an .xlsx file and return its "
            "download path. Use this whenever the user asks for an "
            "analysis they want to keep, send, or open in Excel. The "
            "first row's keys become column headers. Returns the public "
            "download URL the UI can link to."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "rows": {
                    "type": "array",
                    "description": "Array of objects; each object is one row. Keys must be consistent across rows.",
                    "items": {"type": "object"},
                },
                "sheet_name": {
                    "type": "string",
                    "description": "Excel sheet name (defaults to 'Report').",
                },
                "filename": {
                    "type": "string",
                    "description": "Suggested basename without extension (e.g. 'low_stock_2026_q2'). A timestamp is appended automatically.",
                },
            },
            "required": ["rows"],
        },
    },
    {
        "name": "save_knowledge",
        "description": (
            "Record a DURABLE operational insight you derived from data so "
            "future conversations can use it — not a one-off number, but a "
            "reusable fact: a recurring NCG pattern on a line, a supplier's "
            "seasonal quality quirk, a material's behaviour, a line tendency. "
            "Use sparingly and only when you have evidence. Do NOT use it to "
            "answer the current question. The insight is stored with "
            "source='assistant_observed'. category MUST be one of: "
            "line_behaviour, supplier, seasonal, ncg_pattern, material, general."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "category": {
                    "type": "string",
                    "description": "One of: line_behaviour | supplier | seasonal | ncg_pattern | material | general.",
                },
                "title": {
                    "type": "string",
                    "description": "Short, specific title for the insight.",
                },
                "content": {
                    "type": "string",
                    "description": "The insight plus the evidence that supports it (e.g. the numbers you observed).",
                },
                "confidence": {
                    "type": "string",
                    "description": "low | medium | high — how strongly the data supports this. Defaults to medium.",
                },
            },
            "required": ["category", "title", "content"],
        },
    },
]


SYSTEM_PROMPT = """You are the Factory Assistant for PVWood ERP — but think
of yourself as a seasoned production manager, not a chatbot. You have 30+
years on wood-based panel lines: veneer slicing, plywood pressing, MDF, and
door-skin production. You came up through Southeast Asian and Chinese
joint-venture factories and you know the floor cold.

WHAT YOU KNOW IN YOUR BONES
- Glue mixing ratios, open/closed assembly times, press cycles (cold + hot),
  and moisture-content tolerances — and how each one shows up as a defect
  when it drifts.
- NCG (non-conforming goods) root-cause analysis. When you see NCG, your mind
  immediately runs the usual suspects: glue starvation, core gap / overlap,
  excess moisture, press temperature or dwell off-spec, veneer telegraphing,
  bleed-through. You name the likely cause, not just the count.
- Veneer grading: face vs back, species-specific defect tolerance (oak,
  birch, okoume, sapele, teak, etc.) and what a grade-mix shift means for
  yield and cost.
- Throughput Accounting and Theory of Constraints applied to panel lines.
  You think in terms of the constraint, not local efficiencies. You ask
  "where is the bottleneck and is this batch feeding or starving it?"
- Lean for batch manufacturing: WIP control, changeover loss, scrap as a
  symptom, flow over utilisation.
- Raw-material supplier management: logs, resins/hardeners, paper/overlay.
  You know suppliers slip on spec — short moisture, off-colour, late.
- Thai factory operating context: shift structures, labour patterns, and
  seasonal log supply (rainy-season moisture, dry-season availability).

HOW YOU WORK
- Data first, always. You never state a number you have not pulled from the
  database this turn. If you don't have it, you query for it before speaking.
- Plan an analysis: understand the question -> probe the schema with small
  queries -> run the real aggregation -> state the finding. Use LIMIT when
  sampling; don't scan blindly.
- Constructive by default. Every problem you flag comes with the next action
  and which ERP screen to do it on (e.g. "raise this on Material Shortfalls",
  "log it at the Glue Mixing station", "check the BOM -> Glue Formulas tab").
- Opinionated. If something looks wrong you say so, even unasked — "P02's NCG
  rate is double P01 this month, that's a warning sign, here's what I'd check
  first." You recognise patterns that match known panel-production failure
  modes and call them early.
- Efficiency-minded. You naturally frame answers around throughput, scrap /
  waste, and removing the constraint — not vanity metrics.
- You have a memory. When CONVERSATION HISTORY or OPERATIONAL KNOWLEDGE is
  provided below, use it — refer back to earlier findings, build on what
  you've already established, and apply recorded operational facts (supplier
  quirks, line behaviours, seasonal effects). When you derive a durable,
  reusable insight from data (not a one-off number), record it with the
  save_knowledge tool so future sessions benefit.

OUTPUT
- Currency is THB (฿), Thai-style number formatting in prose.
- Concise. Markdown tables for comparisons. State caveats honestly ("excludes
  WIP", "only batches with a logged completion timestamp").
- Tone: a respected senior colleague on the floor. Direct, clear, no
  hand-holding, no emojis, no filler.

WHAT YOU CANNOT DO
- Write or modify the database. You are read-only (SELECT only). The single
  exception is save_knowledge, which records an operational insight — it does
  not touch production data.
- Promise or perform actions ("I'll order it", "I'll reschedule that"). Only
  the manager can act. You recommend the action and name the screen.
- Fabricate filenames. If you export, use the URL the tool returns."""


def _run_tool(name: str, params: dict[str, Any]) -> Any:
    """Dispatch a tool call. Returns a JSON-serialisable result or raises."""
    if name == "query_database":
        return _tool_query(params.get("sql", ""))
    if name == "list_tables":
        return _tool_list_tables()
    if name == "describe_table":
        return _tool_describe(params.get("name", ""))
    if name == "read_server_log":
        return _tool_read_log(int(params.get("lines") or 200))
    if name == "export_to_excel":
        return _tool_export(
            rows=params.get("rows") or [],
            sheet_name=params.get("sheet_name") or "Report",
            filename=params.get("filename") or "fa_report",
        )
    if name == "save_knowledge":
        return _tool_save_knowledge(
            category=params.get("category") or "general",
            title=params.get("title") or "",
            content=params.get("content") or "",
            confidence=params.get("confidence") or "medium",
        )
    return {"error": f"Unknown tool: {name}"}


def _tool_save_knowledge(*, category: str, title: str, content: str,
                         confidence: str) -> dict:
    """Persist an assistant-observed operational insight. source is forced to
    'assistant_observed' — the agent can never masquerade as manager input."""
    try:
        return fa_add_knowledge(category=category, title=title, content=content,
                                source="assistant_observed", confidence=confidence)
    except ValueError as e:
        return {"error": str(e)}
    except Exception as e:
        return {"error": f"Could not save knowledge: {e}"}


def _open_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    # Defensive: even though the connection is read-only by usage, set the
    # query-only PRAGMA so any sneaky write attempt errors out.
    try: conn.execute("PRAGMA query_only = 1")
    except Exception: pass
    return conn


def _tool_query(sql: str) -> dict:
    sql = (sql or "").strip().rstrip(";")
    if not sql:
        return {"error": "Empty SQL."}
    if _FORBIDDEN_SQL.search(sql):
        return {"error": "Only SELECT statements are allowed."}
    if ";" in sql:
        return {"error": "Single statement only — remove the ';'."}
    if not re.match(r"^\s*(?:with|select)\b", sql, re.IGNORECASE):
        return {"error": "Query must start with SELECT or WITH."}
    conn = _open_conn()
    try:
        cur = conn.execute(sql)
        rows = cur.fetchmany(MAX_SQL_ROWS + 1)
        truncated = len(rows) > MAX_SQL_ROWS
        if truncated: rows = rows[:MAX_SQL_ROWS]
        return {
            "row_count": len(rows),
            "truncated": truncated,
            "rows": [dict(r) for r in rows],
        }
    except sqlite3.Error as e:
        return {"error": f"SQL error: {e}"}
    finally:
        conn.close()


def _tool_list_tables() -> dict:
    conn = _open_conn()
    try:
        rows = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' "
            "AND name NOT LIKE 'sqlite_%' ORDER BY name"
        ).fetchall()
        return {"tables": [r["name"] for r in rows]}
    finally:
        conn.close()


def _tool_describe(name: str) -> dict:
    name = (name or "").strip()
    if not re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", name):
        return {"error": "Invalid table name."}
    conn = _open_conn()
    try:
        cols = conn.execute(f"PRAGMA table_info({name})").fetchall()
        if not cols: return {"error": f"Table not found: {name}"}
        return {
            "table": name,
            "columns": [
                {
                    "name":    c["name"],
                    "type":    c["type"],
                    "notnull": bool(c["notnull"]),
                    "default": c["dflt_value"],
                    "pk":      bool(c["pk"]),
                } for c in cols
            ],
        }
    finally:
        conn.close()


def _tool_read_log(lines: int) -> dict:
    lines = max(1, min(int(lines or 200), MAX_LOG_LINES))
    if not os.path.exists(LOG_PATH):
        return {"error": "Server log not found.", "path": LOG_PATH}
    try:
        with open(LOG_PATH, "r", encoding="utf-8", errors="replace") as f:
            tail = f.readlines()[-lines:]
        return {"lines_returned": len(tail), "log": "".join(tail)}
    except OSError as e:
        return {"error": f"Could not read log: {e}"}


def _tool_export(*, rows: list, sheet_name: str, filename: str) -> dict:
    if not rows:
        return {"error": "Nothing to export — rows array is empty."}
    if len(rows) > MAX_SQL_ROWS:
        return {"error": f"Too many rows ({len(rows)}); limit is {MAX_SQL_ROWS}."}

    # Sanitise filename: alnum + dash + underscore only.
    safe = re.sub(r"[^A-Za-z0-9_\-]+", "_", filename or "fa_report").strip("_") or "fa_report"
    stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    fname = f"{safe}_{stamp}_{uuid.uuid4().hex[:6]}.xlsx"
    path  = os.path.join(EXPORT_DIR, fname)

    import openpyxl  # delayed import keeps cold start cheap
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = (sheet_name or "Report")[:31]   # Excel limit

    # Column order = first row's key order (Python preserves insertion order).
    headers = list(rows[0].keys())
    ws.append(headers)
    for r in rows:
        ws.append([r.get(h) for h in headers])

    # Auto-size columns to a reasonable width.
    for col_idx, h in enumerate(headers, start=1):
        col_letter = openpyxl.utils.get_column_letter(col_idx)
        max_len = max([len(str(h))] + [len(str(r.get(h, ""))) for r in rows[:200]])
        ws.column_dimensions[col_letter].width = min(60, max_len + 2)

    wb.save(path)
    return {
        "filename": fname,
        "download_url": f"/api/factory-assistant/export/{fname}",
        "row_count": len(rows),
        "sheet_name": ws.title,
    }


def _last_user_text(messages: list[dict]) -> str:
    """The most recent plain-string user message — i.e. the question being
    asked this turn (tool_result entries are lists, so they're skipped)."""
    for m in reversed(messages):
        if m.get("role") == "user" and isinstance(m.get("content"), str):
            return m["content"]
    return ""


def _build_memory_context(session_id: str, question: str) -> str:
    """Compose the [CONVERSATION HISTORY] + [OPERATIONAL KNOWLEDGE] block that
    gets appended to the system prompt. Pulls the last 20 messages for this
    session and up to 10 knowledge entries relevant to the question (which
    also bumps their last_referenced_at). Returns '' if there's nothing."""
    parts = []

    try:
        history = fa_get_recent_messages(session_id, 20) if session_id else []
    except Exception:
        history = []
    if history:
        lines = []
        for m in history:
            who = "User" if m.get("role") == "user" else "Assistant"
            lines.append(f"{who}: {m.get('content','')}")
        parts.append("[CONVERSATION HISTORY]\n" + "\n".join(lines))

    try:
        knowledge = fa_search_knowledge(question, 10, touch=True) if question else []
    except Exception:
        knowledge = []
    if knowledge:
        lines = []
        for k in knowledge:
            lines.append(f"{k.get('category','general')} | {k.get('title','')}: {k.get('content','')}")
        parts.append(
            "[OPERATIONAL KNOWLEDGE] (recorded facts — apply where relevant)\n"
            + "\n".join(lines))

    return ("\n\n" + "\n\n".join(parts)) if parts else ""


def chat(messages: list[dict], session_id: str = None, user_id: str = None) -> dict:
    """Run one conversation turn through Claude with tools + memory.

    `messages` is the chronological list of {"role","content"} entries the
    client has accumulated this browser session. `session_id` ties the turn
    to a persisted conversation (fa_conversations); `user_id` is the
    authenticated user. Returns:
        { "reply": str, "exports": [...], "tool_calls": int, "session_id": str }
    """
    if not _client:
        return {
            "reply": ("Factory Assistant is unavailable — set ANTHROPIC_API_KEY "
                      "in .env to enable. (Anthropic SDK not configured.)"),
            "exports": [], "tool_calls": 0, "session_id": session_id,
        }

    session_id = session_id or uuid.uuid4().hex
    question = _last_user_text(messages)

    # Persist the user's question, then enrich the system prompt with memory.
    if user_id:
        try: fa_save_message(session_id, user_id, "user", question)
        except Exception: pass
    system = SYSTEM_PROMPT + _build_memory_context(session_id, question)

    convo = list(messages)
    exports: list[dict] = []
    tool_calls = 0

    def _finalise(reply: str) -> dict:
        # Save the assistant's reply (with the tools it used) before returning.
        if user_id:
            try:
                fa_save_message(session_id, user_id, "assistant", reply,
                                tool_calls=tool_calls or None)
            except Exception:
                pass
        return {"reply": reply, "exports": exports,
                "tool_calls": tool_calls, "session_id": session_id}

    for _ in range(MAX_TOOL_LOOPS):
        resp = _client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=MAX_OUTPUT_TKNS,
            system=system,
            tools=TOOLS,
            messages=convo,
        )

        if resp.stop_reason == "end_turn":
            text = ""
            for block in resp.content:
                if getattr(block, "type", None) == "text":
                    text += block.text
            return _finalise(text or "(no reply)")

        if resp.stop_reason == "tool_use":
            convo.append({"role": "assistant", "content": resp.content})
            tool_results = []
            for block in resp.content:
                if getattr(block, "type", None) != "tool_use":
                    continue
                tool_calls += 1
                try:
                    result = _run_tool(block.name, block.input or {})
                except Exception as e:
                    result = {"error": f"Tool {block.name} raised: {e}"}
                if block.name == "export_to_excel" and isinstance(result, dict) and result.get("filename"):
                    exports.append(result)
                tool_results.append({
                    "type":        "tool_result",
                    "tool_use_id": block.id,
                    "content":     json.dumps(result, default=str),
                })
            convo.append({"role": "user", "content": tool_results})
            continue

        return _finalise(f"(stopped early: {resp.stop_reason})")

    return _finalise("(too many tool iterations — bailing out before exhausting the budget)")
