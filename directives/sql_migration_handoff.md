# PVWood ERP → server SQL database: migration kickoff & handoff

> Purpose: carry the context from the build chat into a **new chat** dedicated to planning the
> move from embedded SQLite to a full SQL server (PostgreSQL / MySQL / SQL Server). Read this +
> `CLAUDE.md` first, then start the planning. Nothing here is decided yet — the "Open decisions"
> section is the agenda for the new chat.
>
> **Owner is leaning toward PostgreSQL** (2026-07-01) — treat it as the working default target
> unless the new chat surfaces a reason to reconsider.
>
> **DECISION (2026-07-03): greenfield the Postgres version.** The SQL build is a *fresh, clean
> schema* — proper types/constraints/FKs and Alembic-versioned migrations from day one — NOT a
> mechanical port of the SQLite-isms. The existing SQLite ERP keeps being developed in parallel;
> at cutover we do a one-time **data** migration (`erp.db` rows → the new schema), not a code port.
> This decouples the two tracks: feature work continues on SQLite; the Postgres schema is designed
> right, then loaded with the live data.

## Current system (as-is)
- **Backend:** FastAPI (`execution/main.py`, ~4k lines) over **raw SQL on SQLite in WAL mode**
  (`execution/database.py`, ~11k lines). One `sqlite3` connection per request, 30 s busy-timeout,
  sync `def` handlers running in Starlette's threadpool. Config in `execution/config.py`
  (`DB_PATH` env selects the DB file).
- **Database:** a single file `erp.db` (gitignored). ~60–70 tables, all created in `init_db()`.
- **Schema management:** *no migration framework.* `init_db()` runs on **every startup** and:
  `CREATE TABLE IF NOT EXISTS …` for every table, a `_migrations` list of idempotent `ALTER TABLE
  … ADD COLUMN` (errors on already-applied are swallowed), plus **self-healing blocks** — e.g.
  rebuild-a-table-to-strip-a-dangling-FK (FK off + `legacy_alter_table`), one-off data folds
  (glue-mix blank-line stock → P01), and a `glue_mix`→`laminating` station-stock department move.
- **Dev workflow (important):** the owner runs `uvicorn --reload` against the **LIVE `erp.db`**, so
  saving a backend edit re-runs `init_db()` on real data immediately. Migrations must stay
  idempotent + self-healing; always test on a **copy** first (see `_bulkval_srv.db` / `_preview_test.db`
  pattern + `.claude/launch.json`). Port 8000 = live; use an alt port + copy DB for preview.
- **Frontend:** static SPA (`frontend/index.html` + ES-classic modules in `frontend/js/`), no build
  step. Not affected by the DB migration except where it relies on API shapes.
- **Versioning:** `execution/version.py` (VERSION + BUILD_DATE + CHANGELOG). Currently ~2.25.2.
- **Deploy:** on-prem Windows Server, NSSM service (`scripts/install_service.ps1`) + daily SQLite
  file backup (`scripts/install_backup_task.ps1`). `DEPLOY.md` is the runbook.
- **Roles:** MANAGERIAL, PRODUCTION_PLANNING, DEPARTMENT_LEADER, WAREHOUSE.

## Domain / data model (what the tables are)
Veneer / wood-panel factory (see `CLAUDE.md` + `directives/fc_station_department_model.md`).
- **Catalog:** `manufacturing_line`, `departments`, `line_flow`, `stations`. FC = "Feed Center"
  (material prep/QC/staging — NOT a production stage). Production flow now starts at
  **"Glue & Laminating"** (the old `glue_mix` station was merged into `laminating`).
- **Materials / stock:** `materials` (`current_stock`=WH, `fc_stock`=FC, `wlwh_stock`,
  `fc_unit_cost`, `unit_cost`/`price`, dims, species/grade/cut for veneers, board_type),
  `station_stock` + `station_stock_movements` (per department+line; glue components live under
  `laminating`), `material_lots` (FIFO, used by VCMX).
- **BOM:** `skus` (finished goods) + `bom_lines` (seq 1 board, 2/3 face/back veneer, 4/5 face/back
  glue) + `bom_groups` + `glue_recipes` (component kg columns + `material_links` JSON) +
  `packing_skus`/`packing_lines`. (Legacy `products`/`bom` tables were DROPPED.)
- **Orders:** `purchase_orders` (sales POs) + `po_lines` + `customers`; `production_orders`
  (+ `prod_order_veneer_alloc`); `batches` + `batch_movements` (WIP = active batches by
  `current_department`).
- **Production logs:** `glue_mix_log`, `laminating_log` (+ `face/back_glue_g_per_face`),
  `cold_press_log`, `hot_press_log`, `repair_log`, `sanding_log`, `grading_log`, `packing_log`;
  plus `glue_util_day` (daily glue mixed/applied/waste), `veneer_regrade_log`, `board_resize_log`.
- **FC:** `fc_transfer_requests`, the `materials.fc_stock` counter, `get_fc_movements`.
- **AI:** `execution/factory_assistant.py` (tool-using Claude agent; `fa_conversations`,
  `fa_knowledge`) + `execution/claude_ai.py`.
- **Rules to preserve:** stock mutations validate availability before deducting and raise
  `ValueError("Insufficient … stock")` → HTTP 400 (never silently clamp).

## Why migrate to a server RDBMS
- Real multi-user **concurrency** (SQLite is single-writer; the --reload-on-live-DB pattern is
  fragile; "database is locked" risk under load with the 30 s busy-timeout).
- Connection **pooling**, stronger typing/constraints, better backup/HA, room to scale.

## SQLite-isms that will need porting (audit these)
`AUTOINCREMENT`; dynamic typing / booleans-as-int; `datetime('now')`; `INSERT OR IGNORE` /
`INSERT OR REPLACE`; `PRAGMA foreign_keys=OFF` + `legacy_alter_table` rebuilds; `rowid`; string
dates (`DATE(col)=?`); `printf(...)`; case-insensitive `LIKE`; the "rebuild table to drop a FK"
self-heal (a real RDBMS has `ALTER TABLE DROP CONSTRAINT`). ~11k lines of raw `sqlite3` SQL in
`database.py` are the surface area.

## Open decisions (the agenda for the new chat)
1. **Target RDBMS** — **PostgreSQL is the owner's leaning default** (types, JSON/JSONB, concurrency,
   great Python support). Reconsider only if hosting/licensing/team-familiarity argues for SQL
   Server (on-prem Windows/MS stack) or MySQL/MariaDB. Decide where it runs + the backup strategy.
2. **Access layer** — keep raw SQL (`psycopg`) vs adopt SQLAlchemy Core / SQLModel / an ORM.
   Trade-off: least churn (raw SQL, port dialect) vs. long-term maintainability.
3. **Migration framework** — replace the ad-hoc `init_db` CREATE-IF-NOT-EXISTS + `_migrations`
   model with **Alembic** (versioned migrations). Bootstrap the baseline from the current schema.
4. **Connection model** — one-conn-per-request → a pool (`psycopg_pool` / SQLAlchemy engine);
   keep sync-in-threadpool or go async.
5. **Data migration** — one-time export `erp.db` → target (schema + data), preserving live data;
   cutover plan (big-bang vs dual-write); how to freeze/backup before cutover.
6. **Dev/staging** — stop editing the live DB; stand up a dev/staging database.
7. **Deploy** — Windows service topology with a DB server; new backup strategy (vs daily file copy).

## Suggested first moves (new chat)
1. Decide RDBMS (Q1) + access layer (Q2).
2. Inventory: dump the full schema from `init_db()`; grep every raw-SQL call site; catalog the
   SQLite-isms above.
3. Stand up Alembic with a baseline migration matching the current schema.
4. Write a one-shot `erp.db` → target data-export script; plan phased cutover; test on a copy.

## Pointers
- Architecture: `CLAUDE.md`; FC model: `directives/fc_station_department_model.md`.
- Memory (`~/.claude/projects/…/memory/`): `project_fc_is_feed_center`,
  `project_glue_laminating_merge`, `project_dev_server_reload_live_db`.
- This build chat's raw transcript (if the full history is needed):
  `C:\Users\PV_Natthapat\.claude\projects\C--Users-PV-Natthapat-Desktop-Calude-ERP\*.jsonl`.
