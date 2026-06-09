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
    from config import ANTHROPIC_API_KEY, LOG_PATH, BACKUP_DIR, DB_PATH
except ImportError:
    from execution.config import ANTHROPIC_API_KEY, LOG_PATH, BACKUP_DIR, DB_PATH

try:
    import anthropic
    _client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY) if (
        ANTHROPIC_API_KEY and ANTHROPIC_API_KEY != "your_anthropic_api_key_here"
    ) else None
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
]


SYSTEM_PROMPT = """You are the Factory Assistant for PVWood ERP, a veneer
overlaying factory. You help managers analyse production data, spot
issues, and produce shareable Excel reports.

Behaviour:
- Reason from data. Always check the DB before answering — never guess
  a number.
- Prefer concrete queries over wide table scans. Use LIMIT when sampling.
- When the user asks for an analysis, plan it: (1) understand the
  question, (2) run small probing queries to confirm the schema, (3)
  run the final aggregation, (4) summarise findings + export to Excel
  if it's worth keeping.
- Currency is THB (฿). Use Thai-style number formatting in your prose.
- Be concise. Tables in markdown for comparisons. Surface caveats: 'this
  excludes WIP', 'only batches with a logged completion timestamp'.

What you CANNOT do:
- Write/modify the database. SELECT only.
- Promise actions ("I'll order it") — only managers can do that. Suggest
  the action instead and tell them which screen to use.
- Fabricate filenames. If you export, use the URL returned by the tool.

Tone: factory-floor managerial. No emojis. No fluff."""


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
    return {"error": f"Unknown tool: {name}"}


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


def chat(messages: list[dict]) -> dict:
    """Run one conversation turn through Claude with tools.

    `messages` is a full chronological list of {"role","content"} entries
    from the client. The role can be 'user' or 'assistant' (we never
    persist tool_use/tool_result entries server-side — they're re-derived
    each turn from the user's question and the live DB state, so the
    client only sees clean prose). Returns:
        {
          "reply":  "<final text response>",
          "exports": [{ "filename": "...", "download_url": "..." }],
          "tool_calls": int,         # for debug / cost tracking
        }
    """
    if not _client:
        return {
            "reply": ("Factory Assistant is unavailable — set ANTHROPIC_API_KEY "
                      "in .env to enable. (Anthropic SDK not configured.)"),
            "exports": [], "tool_calls": 0,
        }

    convo = list(messages)
    exports: list[dict] = []
    tool_calls = 0

    for _ in range(MAX_TOOL_LOOPS):
        resp = _client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=MAX_OUTPUT_TKNS,
            system=SYSTEM_PROMPT,
            tools=TOOLS,
            messages=convo,
        )

        # If the model is done (text-only stop), return its prose.
        if resp.stop_reason == "end_turn":
            text = ""
            for block in resp.content:
                if getattr(block, "type", None) == "text":
                    text += block.text
            return {
                "reply": text or "(no reply)",
                "exports": exports,
                "tool_calls": tool_calls,
            }

        # Otherwise it asked for tools. Run each one and feed results back.
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

        # Stop reason was something unexpected (max_tokens, stop_sequence, …).
        return {
            "reply": f"(stopped early: {resp.stop_reason})",
            "exports": exports,
            "tool_calls": tool_calls,
        }

    return {
        "reply": "(too many tool iterations — bailing out before exhausting the budget)",
        "exports": exports,
        "tool_calls": tool_calls,
    }
