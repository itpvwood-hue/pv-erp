# Factory Assistant — Directive

## Goal
Give Managerial users a single conversational surface to interrogate the
live ERP — production, inventory, costs, forecasts — and produce shareable
Excel reports, without writing SQL or exporting by hand. Replaces the two
narrow AI placeholders (BOM Query, Capacity Planner) with one tool-using
agent that reads the real database. Since v2.19.0 the assistant also has a
**veteran production-manager persona** and **persistent memory**.

## Persona (v2.19.0)
The system prompt frames the assistant as a 30-year veteran of wood-based
panel manufacturing (veneer slicing, plywood pressing, MDF, door skins),
seasoned across Southeast Asian and Chinese JV factories. It knows in its
bones: glue ratios / press cycles / moisture tolerances and how each drifts
into a defect; NCG root-cause (glue starvation, core gap, moisture, press
temp/dwell, telegraphing, bleed-through); veneer grading by species; Theory
of Constraints + Lean for batch panel lines; raw-material supplier quirks;
and Thai-factory shift/seasonal-log context.

Personality encoded: direct and concise; data-first (never states a number
it hasn't queried); constructive (every flagged problem comes with the next
action + the ERP screen to use); opinionated (flags warning signs unasked);
efficiency-minded (frames answers in throughput / waste / constraint terms).
Tone: a respected senior colleague, not a chatbot. No emojis.

## Inputs
- A natural-language question (plus prior turns of the same conversation).
- The live SQLite database (read-only).
- The persistent server log (`logs/server.log`).
- **Memory**: the last 20 messages of the current session and relevant
  recorded operational facts (see "Memory" below) are injected into the
  system prompt each call.

## Tools / Scripts
- **Endpoints (all Managerial role):**
  - `POST /api/factory-assistant/chat`              — body `{messages, session_id}` → `{reply, exports[], tool_calls, session_id}`
  - `GET  /api/factory-assistant/export/{file}`     — download a generated xlsx
  - `POST /api/factory-assistant/knowledge`         — manager injects a fact (source `manager_input`)
  - `GET  /api/factory-assistant/knowledge`         — list all knowledge, recently-referenced first
- **Module:** `execution/factory_assistant.py` → `chat(messages, session_id, user_id)`
- **Memory helpers:** `execution/database.py` → `fa_save_message`, `fa_get_recent_messages`, `fa_search_knowledge`, `fa_add_knowledge`, `fa_list_knowledge`
- **System prompt:** `factory_assistant.py` → `SYSTEM_PROMPT` (constant; see "Evolving the behaviour" below)
- **Frontend:** `page-factory-assistant` (sidebar "Factory Assistant"), handlers in `frontend/js/portal_admin.js` (`faInit`, `faSend`, `faReset`, `faLoadKnowledge`, `faAddKnowledge`, per-session `_faSessionId`) — Managerial only.

## The six tools the agent can call
| Tool | Purpose | Guardrail |
|---|---|---|
| `query_database(sql)` | Run a single read-only SELECT | Rejects INSERT/UPDATE/DELETE/DDL/PRAGMA, multi-statements; connection forced to `PRAGMA query_only=1`; capped at 10 000 rows |
| `list_tables()` | Enumerate tables | — |
| `describe_table(name)` | Column schema for one table | name validated against `^[A-Za-z_][A-Za-z0-9_]*$` |
| `read_server_log(lines)` | Tail `logs/server.log` | max 2 000 lines |
| `export_to_excel(rows, sheet, file)` | Write rows to xlsx, return a download URL | filename sanitised + timestamped + uuid-suffixed; lands in `backups/factory_assistant/` |
| `save_knowledge(category, title, content, confidence)` | Record a durable operational insight derived from data | `source` forced to `assistant_observed` (the agent can't masquerade as manager input); `category` validated against the allowed set; does NOT touch production data |

The agent loops (max 12 tool calls per turn) until it produces a text-only
reply.

## Memory (v2.19.0)
Two tables, created idempotently in `init_db()`:

- **`fa_conversations`** (id, session_id, user_id, role, content, tool_calls,
  created_at; index on `session_id`) — every chat turn. The frontend mints a
  per-browser-session UUID (sessionStorage) and sends it with each call;
  "New chat" starts a fresh session.
- **`fa_knowledge`** (id, category, title, content, source, confidence,
  created_at, last_referenced_at; index on `category`) — durable operational
  facts. `source` is `assistant_observed` (via the `save_knowledge` tool) or
  `manager_input` (via the POST endpoint). `category` ∈ {line_behaviour,
  supplier, seasonal, ncg_pattern, material, general}; `confidence` ∈
  {low, medium, high}.

Per turn: the user message is saved → the system prompt is enriched with the
last 20 session messages (`[CONVERSATION HISTORY]`) and up to 10 knowledge
entries whose title/content keyword-match the question (`[OPERATIONAL
KNOWLEDGE]`, which bumps their `last_referenced_at`) → the assistant reply is
saved. The system prompt tells the assistant to apply recorded facts and to
record durable, reusable insights (not one-off numbers) via `save_knowledge`.

## Behaviour the system prompt enforces
- **Reason from data** — always query the DB before answering; never guess a number.
- **Plan analyses** — understand the question, probe the schema with small queries, run the final aggregation, then summarise (and export to Excel if worth keeping).
- **Use memory** — refer back to earlier findings; apply recorded operational facts; record durable new insights with `save_knowledge`.
- **Currency = THB (฿)**, Thai-style number formatting in prose.
- **Cannot mutate** production data (SELECT only); the lone write is
  `save_knowledge`, which records an insight and never touches production
  tables. **Cannot promise actions** — it suggests the action and names the
  screen to use.
- Concise, opinionated, constructive, factory-floor managerial tone. No emojis.

## Example questions
- "Top 10 fastest-moving materials this quarter with average daily consumption — export to Excel."
- "Which production lines had the most NCG batches last month? Group by line and reason."
- "Forecast next 30 days of glue consumption per recipe from the last 90 days of batches."
- "Materials at or near reorder point with their suppliers and open PRs."
- "Remember that P02 runs hotter than P01 on hot press." (→ records a `line_behaviour` insight it will apply later)

## Safety model
- Read-only on production data: the SQL guard + `query_only` PRAGMA mean a
  confused model still cannot write. The only persistence the agent can do is
  `save_knowledge` (an insight note, `source=assistant_observed`).
- Managerial-gated: every chat / export / knowledge endpoint requires
  `Role.MANAGERIAL`.
- Export download validates the filename against path-traversal and only
  serves files from `backups/factory_assistant/`.
- Needs `ANTHROPIC_API_KEY` in `.env`; without it the endpoint returns a
  friendly "unavailable" message and the rest of the ERP is unaffected. The
  SDK client is built by `config.make_anthropic_client()` (pins the public
  endpoint + x-api-key, strips host-injected `ANTHROPIC_*` proxy vars).

## Evolving the behaviour
The system prompt is the constant `SYSTEM_PROMPT` in
`execution/factory_assistant.py`. To change how the assistant reasons,
edit that constant and restart the service. (Like the older
`claude_ai.py` prompts, it is **not** loaded from this directive at
runtime — this file is the design record. If you want the prompt to be
editable without touching Python, we can wire `factory_assistant.py` to
read `directives/factory_assistant.md` § "Behaviour…" at startup; ask and
it's a small change.)

## Relationship to the older AI directives
- `bom_intelligence.md` and `capacity_planning.md` describe the BOM Query
  and Capacity Planner pages that the Factory Assistant **replaced** in
  v2.11.0. Their `claude_ai.py` functions and `/api/ai/bom-query` +
  `/api/ai/capacity-check` endpoints still exist but have no UI.
- `production_reports.md` is still live — it drives the daily/shift report
  generator on the Reports page (`/api/ai/daily-report`).
