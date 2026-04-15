#!/usr/bin/env python3
"""UserPromptSubmit hook — sampled fold-back nudge via additionalContext.

Fires before each user prompt. Most invocations no-op. Every Nth
invocation (default N=30, configurable via FOLD_BACK_NUDGE_EVERY)
injects an additionalContext line reminding the agent that the queue
exists.

The nudge text references AGENTS.md §Continuous Fold-Back Convention.
"""

from __future__ import annotations

import json
import os
import sys

from _common import (
    detect_vault,
    lint_off,
    log,
    queue_size,
    read_payload,
    state_path,
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

    nudge_every = int(os.environ.get("FOLD_BACK_NUDGE_EVERY", "30"))
    sf = state_path(vault)

    state = {}
    if sf.exists():
        try:
            state = json.loads(sf.read_text())
        except Exception:
            state = {}

    n = int(state.get("prompt_count", 0)) + 1
    state["prompt_count"] = n
    try:
        sf.write_text(json.dumps(state))
    except Exception as e:
        log(vault, f"[prompt_nudge] state write error: {e}")

    if n % nudge_every != 0:
        return 0

    pending = queue_size(vault)
    if pending == 0:
        return 0

    msg = (
        f"[fold-back reminder] You're working in vault context with {pending} pending "
        f"entries in the fold-back queue. At a natural breakpoint, consider invoking "
        f"`/wiki-ingest --drain-pending` to evaluate and integrate wiki-worthy content. "
        f"See AGENTS.md §Continuous Fold-Back Convention."
    )
    log(vault, f"[prompt_nudge] injected nudge prompt_count={n} pending={pending}")
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "UserPromptSubmit",
            "additionalContext": msg,
        },
    }))

    return 0


if __name__ == "__main__":
    sys.exit(main())
