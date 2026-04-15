#!/usr/bin/env python3
"""SessionStart hook with matcher:"compact" — post-compaction reminder.

Per hooks-guide.md §263-285 this is the docs-recommended way to reinject
context after compaction. We use it to remind the agent that the
fold-back queue exists and that compaction just delivered a fresh
compact_summary into it.

Returns additionalContext so the agent reads it on the next turn.
Output suppressed entirely when the queue is empty.
"""

from __future__ import annotations

import json
import sys

from _common import detect_vault, lint_off, log, queue_size, read_payload


def main() -> int:
    payload = read_payload()
    if not payload:
        return 0

    vault = detect_vault(payload.get("cwd", ""))
    if not vault:
        return 0

    cwd = payload.get("cwd", "")
    if lint_off(cwd, vault):
        return 0

    size = queue_size(vault)
    if size == 0:
        return 0

    msg = (
        f"[fold-back reminder] Compaction just completed; the compact_summary has been "
        f"queued. Fold-back queue now has {size} entries pending evaluation. Consider "
        f"invoking `/wiki-ingest --drain-pending` to evaluate and integrate wiki-worthy "
        f"content. See AGENTS.md §Continuous Fold-Back Convention. Drain at natural "
        f"breakpoints; not strictly required this turn."
    )
    log(vault, f"[sessionstart_compact] reminder injected (queue={size})")
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "SessionStart",
            "additionalContext": msg,
        },
    }))

    return 0


if __name__ == "__main__":
    sys.exit(main())
