#!/usr/bin/env python3
"""Stop hook handler — per-turn append to fold-back queue.

Fires after every assistant turn. Always appends one JSON line marking
the turn for later evaluation by /wiki-ingest --drain-pending.

Threshold backstop: if the queue grows past LARGE_QUEUE_THRESHOLD
(default 200; configurable via FOLD_BACK_BLOCK_THRESHOLD env var),
returns decision: block + reason to force the agent to drain inline
before the turn ends.

No subprocess. No LLM call. ~5-30ms per invocation.
"""

from __future__ import annotations

import json
import os
import sys

from _common import (
    append_queue,
    detect_vault,
    lint_off,
    log,
    now_iso,
    queue_size,
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

    transcript = payload.get("transcript_path", "")
    last_msg = payload.get("last_assistant_message", "") or ""

    entry = {
        "type": "turn",
        "ts": now_iso(),
        "transcript_path": transcript,
        "last_assistant_preview": last_msg[:280],
        "session_id": payload.get("session_id", ""),
    }
    if not append_queue(vault, entry):
        return 0  # logged inside append_queue

    threshold = int(os.environ.get("FOLD_BACK_BLOCK_THRESHOLD", "200"))
    size = queue_size(vault)

    # Loop guard: if we already blocked once on this stop chain, don't block
    # again — Claude is already continuing because we said so. Per
    # claude-code-docs hooks.md Stop input: stop_hook_active is True when
    # "Claude Code is already continuing as a result of a stop hook."
    # Without this guard a stuck drain (queue stays above threshold) would
    # loop indefinitely.
    if payload.get("stop_hook_active") is True:
        if size >= threshold:
            log(vault, f"[stop_append] threshold-block suppressed (stop_hook_active=true) size={size}")
        return 0

    if size >= threshold:
        # Stop hook supports only top-level decision + reason per
        # claude-code-docs hooks.md:1534-1548. The `reason` field is
        # shown to Claude as the rationale for continuing — so we put
        # the actionable instruction there.
        reason = (
            f"Fold-back queue at {size} entries (threshold {threshold}). "
            f"Drain via /wiki-ingest --drain-pending now before stopping this turn. "
            f"See AGENTS.md §Continuous Fold-Back Convention."
        )
        log(vault, f"[stop_append] threshold-block size={size}")
        print(json.dumps({
            "decision": "block",
            "reason": reason,
        }))

    return 0


if __name__ == "__main__":
    sys.exit(main())
