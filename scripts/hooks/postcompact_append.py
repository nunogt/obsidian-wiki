#!/usr/bin/env python3
"""PostCompact hook handler — append compact_summary to queue.

PostCompact has no decision/context return surface (per hooks.md), so
this hook is purely observational. It captures the model-distilled
summary of what was just compacted away — often the highest-fidelity
distillation of the session so far.

Reinjection of "queue has N items" happens via the SessionStart hook
with matcher "compact" that fires next.
"""

from __future__ import annotations

import sys

from _common import (
    append_queue,
    detect_vault,
    lint_off,
    log,
    now_iso,
    read_payload,
)


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

    summary = payload.get("compact_summary", "")
    if not summary:
        return 0

    entry = {
        "type": "compact_summary",
        "ts": now_iso(),
        "transcript_path": payload.get("transcript_path", ""),
        "session_id": payload.get("session_id", ""),
        "trigger": payload.get("trigger", ""),
        "summary": summary,
    }
    if append_queue(vault, entry):
        log(vault, f"[postcompact] queued summary ({len(summary)} chars) trigger={entry['trigger']}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
