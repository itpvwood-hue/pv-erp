# Factory Assistant — Directive

## Goal
Give Managerial users a single conversational surface to interrogate the
live ERP — production, inventory, costs, forecasts — and produce shareable
Excel reports, without writing SQL or exporting by hand. Replaces the two
narrow AI placeholders (BOM Query, Capacity Planner) with one tool-using
agent that reads the real database.

## Inputs
- A natural-language question (plus prior turns of the same conversation).
- The live SQLite database (read-only).
- The persistent server log (`logs/server.log`).

## Tools / Scripts
- **Endpoints:**
  - `POST /api/factory-assistant/chat`           (Managerial role)
  - `GET  /api/factory-assistant/export/{file}`  (Managerial role — download a generated xlsx)
- **Module:** `execution/factory_assistant.py` → `chat(messages)`
- **System prompt:** `factory_assistant.py` → `SYSTEM_PROMPT` (constant; see "Evolving the behaviour" below)
- **Frontend:** `page-factory-assistant` (sidebar "Factory Assistant"), handlers in `frontend/js/portal_planning.js` (`faInit`, `faSend`, `faReset`, …) — registered to Managerial only.

## The five tools the agent can call
| Tool | Purpose | Guardrail |
|---|---|---|
| `query_database(sql)` | Run a single read-only SELECT | Rejects INSERT/UPDATE/DELETE/DDL/PRAGMA, multi-statements; connection forced to `PRAGMA query_only=1`; capped at 10 000 rows |
| `list_tables()` | Enumerate tables | — |
| `describe_table(name)` | Column schema for one table | name validated against `^[A-Za-z_][A-Za-z0-9_]*$` |
| `read_server_log(lines)` | Tail `logs/server.log` | max 2 000 lines |
| `export_to_excel(rows, sheet, file)` | Write rows to xlsx, return a download URL | filename sanitised + timestamped + uuid-suffixed; lands in `backups/factory_assistant/` |

The agent loops (max 12 tool calls per turn) until it produces a text-only
reply. Returns `{ reply, exports[], tool_calls }`.

## Behaviour the system prompt enforces
- **Reason from data** — always query the DB before answering; never guess a number.
- **Plan analyses** — understand the question, probe the schema with small queries, run the final aggregation, then summarise (and export to Excel if worth keeping).
- **Currency = THB (฿)**, Thai-style number formatting in prose.
- **Cannot mutate** the database (SELECT only), **cannot promise actions** ("I'll order it") — it suggests the action and names the screen to use.
- Concise, factory-floor managerial tone. No emojis.

## Example questions
- "Top 10 fastest-moving materials this quarter with average daily consumption — export to Excel."
- "Which production lines had the most NCG batches last month? Group by line and reason."
- "Forecast next 30 days of glue consumption per recipe from the last 90 days of batches."
- "Materials at or near reorder point with their suppliers and open PRs."

## Safety model
- Read-only by construction: the SQL guard + `query_only` PRAGMA mean a
  confused model still cannot write.
- Managerial-gated: both endpoints require `Role.MANAGERIAL`.
- Export download validates the filename against path-traversal and only
  serves files from `backups/factory_assistant/`.
- Needs `ANTHROPIC_API_KEY` in `.env`; without it the endpoint returns a
  friendly "unavailable" message and the rest of the ERP is unaffected.

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
