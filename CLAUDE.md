# PVWood ERP — Project Context

FastAPI + SQLite ERP for a veneer / wood-panel factory (PVWood). Single-page
app frontend, on-prem Windows Server deployment.

## Architecture

- **Backend:** FastAPI (`execution/main.py`) + raw-SQL SQLite in WAL mode
  (`execution/database.py`). One connection per request, 30 s busy-timeout.
  Route handlers are mostly sync `def` → run in Starlette's threadpool.
- **Config:** all env-driven config in `execution/config.py` (single source).
  `make_anthropic_client()` builds the Claude SDK client (pins the public
  endpoint + x-api-key; strips host-injected `ANTHROPIC_*` proxy vars).
- **Frontend:** `frontend/index.html` is a thin shell + login + page markup.
  Logic is split into ES-classic modules under `frontend/js/`, loaded per
  role after login (no bundler, no build step):
  - `i18n.js`, `core.js`, `nav.js`, `auth.js` — shared
  - `portal_warehouse.js`, `portal_planning.js`, `portal_accounting.js`,
    `portal_admin.js` — one per role, fetched on demand by `auth.js`'s
    `loadPortalsForRole()`. Each self-registers its pages via
    `Object.assign(PAGE_LOADERS, { … })`.
  - `frontend/css/styles.css` — extracted styles.
- **AI:** `execution/claude_ai.py` (legacy BOM/capacity/report prompts) and
  `execution/factory_assistant.py` (the Factory Assistant — tool-using agent
  with memory; Managerial only).

## Roles

`MANAGERIAL`, `PRODUCTION_PLANNING`, `DEPARTMENT_LEADER`, `WAREHOUSE`.
Backend constants: `class Role` in `main.py`. Frontend: `const ROLE`.
Page→role grants: `ROLE_PAGES` in `index.html`.

## Conventions

- **Versioning:** `execution/version.py` is the single source. Bump
  `VERSION` + `BUILD_DATE`, prepend a one-line `CHANGELOG` entry for every
  shipped change. The running process reads VERSION at import — **restart to
  see a new version** (the sidebar footer lagging = service not restarted).
- **Migrations:** there is no numbered-migration system. New tables are
  added as `CREATE TABLE IF NOT EXISTS` inside `init_db()` in `database.py`
  (idempotent, runs on every startup). Column adds go in the `_migrations`
  ALTER list in the same function.
- **Tests:** `python tests/test_audit.py` — 37 endpoint smoke tests. Keep it
  green. It needs the server running on `127.0.0.1:8000`.
- **Stock mutations** validate availability before deducting and raise
  `ValueError("Insufficient … stock: …")`, surfaced as HTTP 400. Don't
  silently clamp.
- **Lines / departments / stations** come from the DB catalog
  (`manufacturing_line`, `departments`, `line_flow`, `stations`), exposed at
  `/api/catalog/*`. Per-line departments require a line; centralised
  departments (packing, fg_receiving, fg_warehouse — `is_centralised=1`) are
  line-less.

## Factory Assistant (memory)

`execution/factory_assistant.py`. Six tools: `query_database` (SELECT-only,
`query_only` PRAGMA, 10k-row cap), `list_tables`, `describe_table`,
`read_server_log`, `export_to_excel`, `save_knowledge`. Max 12 tool calls /
turn. Persona = a 30-year veteran production manager (see `SYSTEM_PROMPT`).
Design doc: `directives/factory_assistant.md`.

**Memory tables** (created in `init_db()`):
- `fa_conversations` (id, session_id, user_id, role, content, tool_calls,
  created_at) — every chat turn, keyed by browser session. Index on
  `session_id`.
- `fa_knowledge` (id, category, title, content, source, confidence,
  created_at, last_referenced_at) — durable operational facts, either
  `assistant_observed` (via the `save_knowledge` tool) or `manager_input`
  (via the endpoint). Index on `category`.

Each turn: the user message is saved, the system prompt is enriched with the
last 20 session messages (`[CONVERSATION HISTORY]`) + up to 10 keyword-matched
knowledge entries (`[OPERATIONAL KNOWLEDGE]`, bumps `last_referenced_at`), and
the assistant reply is saved.

**Endpoints** (all Managerial):
- `POST /api/factory-assistant/chat` — `{messages, session_id}` → `{reply,
  exports[], tool_calls, session_id}`.
- `GET  /api/factory-assistant/export/{file}` — download a generated xlsx.
- `POST /api/factory-assistant/knowledge` — `{category, title, content,
  confidence}`, source forced to `manager_input`.
- `GET  /api/factory-assistant/knowledge` — all entries, recently-referenced
  first (powers the Knowledge Base panel).

Data-access helpers live in `database.py`: `fa_save_message`,
`fa_get_recent_messages`, `fa_search_knowledge`, `fa_add_knowledge`,
`fa_list_knowledge`.

## Run / deploy

- **Dev:** `start.bat` (installs deps, seeds DB on first run, runs uvicorn
  with `--reload`).
- **Server:** `scripts/install_service.ps1` (NSSM service, auto-start,
  crash-restart) + `scripts/install_backup_task.ps1` (daily SQLite backup).
  Full runbook: `DEPLOY.md`. Health probe: `GET /api/health`.
- Secrets (`.env`) and the database (`erp.db`) are gitignored — created on
  the server, never committed.
