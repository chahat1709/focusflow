# ─────────────────────────────────────────────
#  FocusFlow — Configuration
#  Reads from .env file first, then environment variables.
#  If no credentials found, runs in local-only SQLite mode.
# ─────────────────────────────────────────────
import os

# ── Auto-load .env file (no external dependency needed) ──
_env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env')
if os.path.exists(_env_path):
    with open(_env_path, 'r') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, _, value = line.partition('=')
                os.environ.setdefault(key.strip(), value.strip())

HOST = os.environ.get("FOCUSFLOW_HOST", "127.0.0.1")
PORT = int(os.environ.get("FOCUSFLOW_PORT", "8888"))

SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_ANON_KEY = os.environ.get("SUPABASE_ANON_KEY", "")
