"""
PVWood ERP - SQLite live backup script.

Run while the ERP service is live. Uses SQLite's online backup API which
copies the database page-by-page under the write lock — safe to run on a
busy database, no need to stop the server.

Defaults:
  src  = <project_root>/erp.db           (or DB_PATH env var)
  dest = <project_root>/backups/erp-YYYYMMDD-HHMMSS.db
  keep = 30 most recent snapshots; older files auto-deleted.

CLI:
  python scripts/backup_db.py                  # standard daily backup
  python scripts/backup_db.py --keep 90        # keep 90 days
  python scripts/backup_db.py --dest D:\\path  # backup to a non-default folder
  python scripts/backup_db.py --quiet          # no stdout on success (for cron)

Exit codes:
  0 = success
  1 = backup file empty or corrupted (basic integrity check failed)
  2 = source DB unreachable
  3 = destination not writable
"""
from __future__ import annotations
import argparse
import datetime
import os
import sqlite3
import sys
from pathlib import Path


def _project_root() -> Path:
    """The repo root = the directory above scripts/."""
    return Path(__file__).resolve().parent.parent


def _default_src() -> Path:
    # Honour DB_PATH if set, otherwise fall back to <root>/erp.db.
    env = os.environ.get('DB_PATH', '').strip()
    return Path(env) if env else _project_root() / 'erp.db'


def _default_dest_dir() -> Path:
    return _project_root() / 'backups'


def backup(src: Path, dest: Path, *, quiet: bool = False) -> None:
    """Copy `src` to `dest` using the online backup API.

    Raises SystemExit on error (so the scheduler sees a non-zero code).
    """
    if not src.exists():
        print(f'[ERROR] Source DB does not exist: {src}', file=sys.stderr)
        sys.exit(2)

    dest.parent.mkdir(parents=True, exist_ok=True)

    # Online backup. Open src in read-only mode via URI so we never
    # accidentally take a write lock on the live DB.
    src_uri = f'file:{src}?mode=ro'
    try:
        src_conn = sqlite3.connect(src_uri, uri=True)
    except sqlite3.OperationalError as e:
        print(f'[ERROR] Cannot open source DB ({src}): {e}', file=sys.stderr)
        sys.exit(2)

    try:
        # Open dest fresh. If a previous attempt left a partial file, we
        # overwrite it; sqlite3.backup handles the schema copy fully.
        if dest.exists():
            dest.unlink()
        dst_conn = sqlite3.connect(str(dest))
        try:
            src_conn.backup(dst_conn)
        finally:
            dst_conn.close()
    finally:
        src_conn.close()

    # Quick sanity: the copy should be a real SQLite file with at least
    # one table.
    try:
        verify = sqlite3.connect(str(dest))
        n_tables = verify.execute(
            "SELECT COUNT(*) FROM sqlite_master WHERE type='table'"
        ).fetchone()[0]
        verify.close()
    except sqlite3.Error as e:
        print(f'[ERROR] Backup integrity check failed: {e}', file=sys.stderr)
        dest.unlink(missing_ok=True)
        sys.exit(1)

    size_mb = dest.stat().st_size / (1024 * 1024)
    if not quiet:
        print(f'[OK] {dest.name}  ({size_mb:.1f} MB, {n_tables} tables)')


def prune_old(dest_dir: Path, *, keep: int, quiet: bool = False) -> None:
    """Keep the newest `keep` backup files (by mtime); delete the rest.

    Only files matching erp-*.db are considered — any ad-hoc copies the
    user left in the folder are ignored.
    """
    pattern = sorted(
        dest_dir.glob('erp-*.db'),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    to_delete = pattern[keep:]
    for old in to_delete:
        try:
            old.unlink()
            if not quiet:
                print(f'  - pruned {old.name}')
        except OSError as e:
            print(f'[WARN] Could not prune {old}: {e}', file=sys.stderr)


def main() -> None:
    ap = argparse.ArgumentParser(description='Live SQLite backup for PVWood ERP.')
    ap.add_argument('--src',  type=Path, default=_default_src(),
                    help='Source DB path. Default: <project>/erp.db (honours DB_PATH env).')
    ap.add_argument('--dest', type=Path, default=_default_dest_dir(),
                    help='Destination directory for snapshots. Default: <project>/backups.')
    ap.add_argument('--keep', type=int, default=30,
                    help='How many recent snapshots to keep. Default: 30.')
    ap.add_argument('--quiet', action='store_true',
                    help='Suppress stdout on success (for Task Scheduler).')
    args = ap.parse_args()

    if not args.dest.exists():
        try:
            args.dest.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            print(f'[ERROR] Cannot create destination directory {args.dest}: {e}', file=sys.stderr)
            sys.exit(3)

    stamp = datetime.datetime.now().strftime('%Y%m%d-%H%M%S')
    dest_file = args.dest / f'erp-{stamp}.db'

    backup(args.src, dest_file, quiet=args.quiet)
    prune_old(args.dest, keep=args.keep, quiet=args.quiet)


if __name__ == '__main__':
    main()
