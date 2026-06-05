# archive/

One-off scripts that already ran during development. **Do not re-run** unless
you understand what they do — many were destructive (table rebuilds, data
backfills). Kept here as an audit trail.

## migrations_legacy/
Schema migrations that were applied before the new `migrations/` runner was
introduced (see Section 6 of the deployment plan). Each file mutated the DB
once and was retired. The current `execution/database.py` `init_db()` is the
source of truth for schema today.

## debug/
Throwaway diagnostic scripts (table dumps, duplicate checks, log scrapes).
Useful as templates if you need to write a new diagnostic, but they reference
data shapes that may no longer match current schema.

## frontend_patches/
Python scripts that bulk-edited `frontend/index.html` during heavy refactors.
The edits they made are now part of `index.html` itself; the patch scripts
have no purpose in the running application.

## old_config/
- `agent.json` / `agent.yaml` — config from an earlier agent-based architecture
  that's no longer wired up. Kept in case any reference is needed.

If you need to truly remove a file from the repo, delete from `archive/` and
commit. If unsure, leave it here — disk cost is negligible.
