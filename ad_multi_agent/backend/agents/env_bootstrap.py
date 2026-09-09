"""Load env into os.environ before Google GenAI / ADK clients initialize."""

from __future__ import annotations

from pathlib import Path

from dotenv import load_dotenv

_BACKEND_ROOT = Path(__file__).resolve().parents[1]
_REPO_ROOT = _BACKEND_ROOT.parent

# Prefer backend/.env, then repo-level .env
load_dotenv(_BACKEND_ROOT / ".env", override=False)
load_dotenv(_REPO_ROOT / ".env", override=False)
