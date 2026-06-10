"""
PVWood ERP — central config loader.

All environment-driven configuration lives here. Other modules should import
constants from this file rather than calling os.getenv directly. This makes
deployment-time tuning a one-file edit and avoids the "where is this value
coming from?" hunt.

Loading order:
  1. .env file at the project root (via python-dotenv) — for local + on-prem.
  2. Real OS environment variables — take precedence (Windows Service uses
     these via NSSM or system env vars).
"""
import os
from typing import List
from dotenv import dotenv_values

# Project root = one directory above this file (the execution/ folder).
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))

# Load .env values manually so we can merge with the right precedence:
#   real OS env value (non-empty)  >  .env value  >  hardcoded default
# (The stock load_dotenv with override=False refuses to overwrite an EMPTY
# OS env var, which means an inherited blank value silently beats the .env.)
_env_file = dotenv_values(os.path.join(PROJECT_ROOT, '.env'))
for _k, _v in (_env_file or {}).items():
    if _v is None: continue
    if not os.environ.get(_k):   # empty OR missing → let .env win
        os.environ[_k] = _v


def _get_bool(key: str, default: bool = False) -> bool:
    v = os.getenv(key, '').strip().lower()
    if v in ('1', 'true', 'yes', 'on'):  return True
    if v in ('0', 'false', 'no', 'off'): return False
    return default


def _get_list(key: str, default: List[str]) -> List[str]:
    raw = os.getenv(key, '').strip()
    if not raw:
        return list(default)
    return [s.strip() for s in raw.split(',') if s.strip()]


# ── External secrets ─────────────────────────────────────────────
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "").strip()


def make_anthropic_client():
    """Build an Anthropic SDK client pinned to the public API with x-api-key
    auth, or return None if no usable key is configured.

    Why not just `anthropic.Anthropic(api_key=...)`? The SDK auto-reads
    ANTHROPIC_AUTH_TOKEN / ANTHROPIC_BASE_URL / ANTHROPIC_CUSTOM_HEADERS from
    the process environment. Some host environments (agent runners, proxy
    harnesses, CI) inject those — and an EMPTY ANTHROPIC_AUTH_TOKEN makes the
    SDK emit 'Authorization: Bearer ' which httpcore rejects as an illegal
    header (surfacing confusingly as APIConnectionError), while a stray
    ANTHROPIC_BASE_URL silently redirects calls off the real API. The ERP only
    ever authenticates with ANTHROPIC_API_KEY against the standard endpoint, so
    we strip the bogus empties and pin base_url. A normal production server has
    none of these vars set, so this is a harmless no-op there.
    """
    if not ANTHROPIC_API_KEY or ANTHROPIC_API_KEY == "your_anthropic_api_key_here":
        return None
    for _k in ("ANTHROPIC_AUTH_TOKEN", "ANTHROPIC_CUSTOM_HEADERS"):
        if os.environ.get(_k, None) == "":
            os.environ.pop(_k, None)
    try:
        import anthropic
    except Exception:
        return None
    return anthropic.Anthropic(api_key=ANTHROPIC_API_KEY,
                               base_url="https://api.anthropic.com")

# ── File paths (all overridable for non-standard deployments) ────
DB_PATH   = os.getenv("DB_PATH",
                      os.path.join(PROJECT_ROOT, 'erp.db'))
DOCS_DIR  = os.getenv("DOCS_DIR",
                      os.path.join(PROJECT_ROOT, 'docs_storage'))
LOG_DIR   = os.getenv("LOG_DIR",
                      os.path.join(PROJECT_ROOT, 'logs'))
LOG_PATH  = os.path.join(LOG_DIR, 'server.log')
BACKUP_DIR = os.getenv("BACKUP_DIR",
                       os.path.join(PROJECT_ROOT, 'backups'))
# Dedicated store for files the Factory Assistant generates (xlsx exports,
# etc.) — kept separate from DOCS_DIR (material PDFs) and BACKUP_DIR (DB
# snapshots) so it can be sized/cleaned/relocated independently.
FA_DIR    = os.getenv("FA_DIR",
                      os.path.join(PROJECT_ROOT, 'fa_storage'))

# ── Server ──────────────────────────────────────────────────────
HOST  = os.getenv("HOST", "0.0.0.0")          # bind to all interfaces for LAN
PORT  = int(os.getenv("PORT", "8000"))
DEBUG = _get_bool("DEBUG", default=False)

# ── CORS — default = localhost + 127.0.0.1 only (tight). Add LAN
# hosts via CORS_ORIGINS env var (comma-separated). Set to "*" to allow all
# (dev-only; NOT recommended in production).
CORS_ORIGINS = _get_list("CORS_ORIGINS", default=[
    "http://localhost:8000",
    "http://127.0.0.1:8000",
])


def summary() -> dict:
    """Diagnostic snapshot of effective config (no secrets) — exposed by the
    /api/admin/config endpoint for ops + debugging."""
    return {
        "project_root":     PROJECT_ROOT,
        "db_path":          DB_PATH,
        "docs_dir":         DOCS_DIR,
        "fa_dir":           FA_DIR,
        "log_dir":          LOG_DIR,
        "host":             HOST,
        "port":             PORT,
        "debug":            DEBUG,
        "cors_origins":     CORS_ORIGINS,
        "anthropic_key_set":bool(ANTHROPIC_API_KEY) and ANTHROPIC_API_KEY != "your_anthropic_api_key_here",
    }
