"""Shared utilities for kb-system Claude Code hook handlers.

Used by stop_append, postcompact_append, sessionstart_compact_remind,
prompt_nudge. Standard library only — no third-party deps.

All functions are designed to fail silently. A misbehaving hook should
never disrupt the operator's session — at worst, log to the vault's
_autosave.log and exit 0.
"""

from __future__ import annotations

import json
import os
import pathlib
import sys
import time
from typing import Optional


def read_payload() -> Optional[dict]:
    """Parse JSON hook payload from stdin. Returns dict or None on error."""
    try:
        return json.load(sys.stdin)
    except Exception:
        return None


def _read_env_var(cwd: str, var_name: str) -> Optional[str]:
    """Pull a single var from cwd/.env. Returns None if missing/unparseable.

    Defensive: doesn't source the file (no shell), just regex-parses
    KEY=value lines. Skips comments and quoted/unquoted values.
    """
    if not cwd:
        return None
    envfile = pathlib.Path(cwd) / ".env"
    if not envfile.is_file():
        return None
    prefix = f"{var_name}="
    try:
        for raw in envfile.read_text().splitlines():
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            if line.startswith(prefix):
                value = line.split("=", 1)[1].strip().strip('"').strip("'")
                return value or None
    except Exception:
        return None
    return None


def detect_vault(cwd: str) -> Optional[str]:
    """Return OBSIDIAN_VAULT_PATH if cwd contains an .env defining it.

    This is the v3 vault-detection mechanism: a hook only acts on a
    Claude session whose cwd has an active vault profile. Sessions
    outside any vault context get an immediate no-op.
    """
    return _read_env_var(cwd, "OBSIDIAN_VAULT_PATH")


def queue_path(vault: str) -> pathlib.Path:
    return pathlib.Path(vault) / ".pending-fold-back.jsonl"


def state_path(vault: str) -> pathlib.Path:
    return pathlib.Path(vault) / ".autosave-state.json"


def queue_size(vault: str) -> int:
    """Count newline-terminated entries in the queue. 0 if missing."""
    qp = queue_path(vault)
    if not qp.exists():
        return 0
    try:
        with qp.open() as f:
            return sum(1 for _ in f)
    except Exception:
        return 0


def append_queue(vault: str, entry: dict) -> bool:
    """Append one JSON line to the queue. Returns True on success."""
    try:
        with open(queue_path(vault), "a") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        return True
    except Exception as e:
        log(vault, f"[append_queue] error: {e}")
        return False


def log(vault: str, msg: str) -> None:
    """Append a timestamped line to ${VAULT}/_autosave.log. Never raises."""
    try:
        with open(pathlib.Path(vault) / "_autosave.log", "a") as f:
            f.write(f"{time.strftime('%Y-%m-%dT%H:%M:%S%z')} {msg}\n")
    except Exception:
        pass


def now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S%z")


def lint_off(cwd: str, vault: str) -> bool:
    """Operator escape hatches. Returns True if hooks should be skipped.

    Two mechanisms (either suffices):
      1. `$VAULT/.fold-back-disabled` sentinel file exists (per-vault)
      2. `LINT_SCHEDULE=off` in `cwd/.env` (per-profile)
    """
    if (pathlib.Path(vault) / ".fold-back-disabled").exists():
        return True
    schedule = _read_env_var(cwd, "LINT_SCHEDULE")
    if schedule and schedule.lower() == "off":
        return True
    return False
