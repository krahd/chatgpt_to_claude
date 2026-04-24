"""Compatibility shim — the canonical implementation lives in src/chatgpt_to_claude_toolkit/migration_core.py."""
import sys
from pathlib import Path

_src = Path(__file__).resolve().parent / "src"
if str(_src) not in sys.path:
    sys.path.insert(0, str(_src))

from chatgpt_to_claude_toolkit.migration_core import *  # noqa: F401, F403, E402
