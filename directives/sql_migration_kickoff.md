# SQL migration — kickoff prompt (paste this into a NEW chat)

> Open a new chat in this project folder (`C:\Users\PV_Natthapat\Desktop\Calude ERP`)
> and paste everything below the line. It's written to stand alone — the new chat has no
> memory of the build chat, so the brief + CLAUDE.md carry the context.

---

You are starting a new work stream for the **PVWood ERP** project (FastAPI + SQLite, on-prem
Windows Server). Your job in this chat is to **plan migrating the ERP from embedded SQLite to a
PostgreSQL server database.**

First, read these two files in full before responding:
1. `directives/sql_migration_handoff.md` — the handoff brief from the build chat. It has the
   complete context: current architecture (FastAPI + raw-SQL SQLite/WAL, one-conn-per-request,
   NO migration framework — schema lives in `init_db()` with CREATE-IF-NOT-EXISTS + a
   `_migrations` ALTER list + self-healing blocks, and the owner runs `uvicorn --reload` against
   the LIVE `erp.db`), the full domain/data model, why we're migrating, the SQLite-isms that must
   be ported, and an "Open decisions" agenda.
2. `CLAUDE.md` — project conventions (versioning in `execution/version.py`, idempotent-migration
   rule, dev/deploy, roles).

**Target is PostgreSQL** (the owner's decision). Do NOT start writing migration code yet — this
chat is for *planning*.

Kick off the planning like this:
1. Confirm the target (PostgreSQL) and recommend an **access layer** — keep raw SQL via `psycopg`
   (least churn, port ~11k lines of dialect) vs. adopt SQLAlchemy Core / an ORM (more churn,
   better long-term). Give a clear recommendation with the trade-off.
2. Recommend the **migration framework** (Alembic) and how to bootstrap a baseline from the
   current `init_db()` schema.
3. Sketch the **data-migration + cutover** approach (one-time `erp.db` → Postgres export,
   freeze/backup, big-bang vs dual-write) and a **dev/staging DB** so we stop editing the live
   database.
4. Flag the SQLite-isms that will need the most work (AUTOINCREMENT, `datetime('now')`,
   `INSERT OR IGNORE/REPLACE`, PRAGMA/FK-rebuild self-heals, string dates, rowid).

Ask me any clarifying questions first, then propose a phased plan. Keep the owner's constraints in
mind: single-writer concurrency pain is the main driver, and the current --reload-on-live-DB
workflow must be replaced with something safe.
