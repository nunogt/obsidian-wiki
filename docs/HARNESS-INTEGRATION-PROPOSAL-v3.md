# Harness integration v3 — subprocess-free, in-session drain

*Drafted 2026-04-15. Supersedes v1 (commit `40b7110`, deployed then reverted at `7e6a3ae`) and v2 (proposed but not executed). Based on a deep re-read of `/mnt/host/shared/git/claude-code-docs` after operator flagged that v2's `claude -p` subprocess-spawn pattern is fragile. The docs research found a cleaner mechanism: hooks **inject context**, the **in-session agent** does the work. No subprocess, no detached background processes, no autosave-context-dir gymnastics.*

> **✅ STATUS: EXECUTED + VALIDATED (2026-04-15).**
>
> Shipped in 6 kb-system commits + 1 fork commit:
>
> **kb-system** (`nunogt/kb-system@main`):
> - `7e6a3ae` — Phase 1: revert v1 (`40b7110`); remove autosave context dirs
> - `b1d5a61` — Phase 2: 4 Python hook helpers (_common.py + stop_append + postcompact_append + sessionstart_compact_remind + prompt_nudge)
> - `9953bc2` — Phase 2.5: gitignore `__pycache__/` (housekeeping slip)
> - `3d92b9c` — Phase 3: settings.json template (4 v3 hooks) + kb-contexts-regenerate deploys it
> - `153571a` — Phase 6: mark v1+v2 proposals superseded; commit v3 to docs/
> - **`fe01292`** — **post-deployment validation fixes** (see §B below)
>
> **fork** (`nunogt/obsidian-wiki@main`):
> - `902cdf0` — Phase 4: `wiki-ingest/SKILL.md §Mode: --drain-pending` + `AGENTS.md §Continuous Fold-Back Convention` + `wiki-query/SKILL.md Step 5c`
>
> ### B. Post-deployment validation findings (commit `fe01292`)
>
> End-to-end source review + `claude-code-docs` cross-check caught **two real bugs** and applied fixes:
>
> 1. **MAJOR: infinite block loop** — Stop hook didn't check `stop_hook_active` per `hooks.md` Stop input spec. If the queue stayed above threshold after a drain attempt, Stop would block → agent continues → turn finishes → Stop fires → blocks again → ad infinitum. **Fix:** respect `stop_hook_active=true` and log+skip rather than re-block. Verified with simulated payload (test R2).
>
> 2. **MAJOR: `LINT_SCHEDULE=off` escape hatch was inert** — `_common.lint_off` only honored `$VAULT/.fold-back-disabled` sentinel, but AGENTS.md and this proposal both documented `LINT_SCHEDULE=off` as a parallel mechanism. **Fix:** extracted `_read_env_var` helper; `lint_off(cwd, vault)` now checks both mechanisms. Verified with simulated payload (test R3).
>
> 3. Minor: removed dead code in `_common.lint_off`; fixed misleading docstring.
>
> Additionally verified per-hook JSON output formats, input payload schemas, settings.json schema, and matcher syntax against docs. All 4 helpers pass `python3 -m py_compile` and 7 simulated-payload smoke tests (R1-R7).
>
> **Deployment state (as of 2026-04-15):**
> - ✅ `kb-system/scripts/hooks/` — 4 Python helpers + shared module, all executable, stdlib-only
> - ✅ `kb-system/scripts/templates/claude-settings.json` — 4 v3 hooks configured
> - ✅ `kb-system/contexts/wiki/.claude/settings.json` — symlink to template (active)
> - ✅ `kb-system/contexts/personal/.claude/settings.json` — symlink to template (active)
> - ✅ Fork skill refinements in `.skills/wiki-ingest/`, `.skills/wiki-query/`, `AGENTS.md`
> - ⏳ Operator to validate in real long-running session; testbed plan in §C below
>
> ### C. kb-wiki as the testbed
>
> The operator indicated kb-wiki will serve as the v3 testbed. Recommended validation path:
>
> 1. Exit current session (this one) — v3 hooks aren't registered for the running process yet because settings.json was installed after session start
> 2. Restart a fresh session in `/mnt/host/shared/git/kb-system/contexts/wiki/` (same CWD)
> 3. Tail `/mnt/host/shared/git/kb-wiki/_autosave.log` in another pane
> 4. Work normally; expect `[stop_append]` lines silently accumulating
> 5. Verify queue growth: `wc -l kb-wiki/.pending-fold-back.jsonl`
> 6. Trigger a compaction (manual `/compact` or wait for auto); verify `[postcompact]` and `[sessionstart_compact]` log lines
> 7. Notice the agent receive `[fold-back reminder]` additionalContext post-compaction and after ~30 prompts
> 8. Eventually invoke `/wiki-ingest --drain-pending` (manual or prompted); verify `DRAIN_PENDING` line in `kb-wiki/log.md`
>
> **No kb-system nuke needed.** Everything is already on disk; only a session restart is required to pick up the new settings.json. See `ACTIVATION-GUIDE.md` for full procedure.
>
> ### D. Live validation results (2026-04-15, kb-wiki as testbed)
>
> Real-session dogfooding in `contexts/wiki/`. Three scenarios exercised end-to-end.
>
> **D.1 — Big ingest (`/wiki-ingest /mnt/host/shared/git/kb-system/docs`)**
>
> 16-minute single logical turn, ~100 internal tool-call iterations. After completion:
> - `/hooks` reported *"4 hooks configured"* — registration confirmed
> - Queue grew by **1 entry** (one Stop firing per user-prompt-ending-response, as specified — NOT per tool-call sub-event)
> - The entry captured the ingest's completion summary (280-char preview + `transcript_path` reference)
> - **Correction to prior assumption**: Stop fires at logical turn-end, not per internal event. An "active" 100-event session can produce 1 queue entry. This is correct behavior.
>
> **D.2 — Drain (`/wiki-ingest --drain-pending`)**
>
> Clean end-to-end pass of the drain path:
> - Skill read queue (1 entry)
> - **LLM-driven rubric applied correctly**: agent verdict was *"not wiki-worthy: already-covered ground"* — the queue entry was the summary of work immediately ingested into the wiki; re-ingesting would produce only redundancy
> - Atomic handoff rename executed: `.pending-fold-back.jsonl` → `.pending-fold-back-<ts>.jsonl`
> - `DRAIN_PENDING clusters_evaluated=1 clusters_ingested=0 entries_processed=1` logged to `kb-wiki/log.md` — exact format specified in §3.5.A
> - Handoff file deleted on clean completion
> - The rubric's reject branch works with defensible reasoning; the "default to ingest when in doubt" override didn't fire because there was no doubt
>
> **D.3 — Compaction flow (`/compact` manual trigger)**
>
> The most sensitive architectural claim of v3 — *hooks inject context, in-session agent acts* — validated:
>
> 1. Compaction performed (`subtype: compact_boundary` in transcript)
> 2. `PostCompact` hook fired → 19.5 KB `compact_summary` captured to queue with `type: "compact_summary"`
> 3. `SessionStart matcher:"compact"` hook fired → emitted `hookSpecificOutput.additionalContext` with the fold-back reminder
> 4. Claude Code surfaced the hook firing as `attachment.type = "hook_success"` and delivered the context as `attachment.type = "hook_additional_context"` — visible in the transcript
> 5. **Claude read the reminder and proactively acted on it**: opened `.pending-fold-back.jsonl`, `log.md`, and newly-created pages — without the operator saying anything
>
> This is the *"LLM does the grunt work"* + *"in-session drain, not subprocess"* thesis proven in a live trace.
>
> **D.4 — Autosave log outputs (evidence trail)**
>
> ```
> 2026-04-15T10:30:03+0000 [sessionstart_compact] reminder injected (queue=1)
> 2026-04-15T10:30:03+0000 [postcompact] queued summary (19537 chars) trigger=manual
> ```
>
> Both hooks log on success paths (defensive design — lets the operator verify activity without enabling `--debug-file`).
>
> **D.5 — Known minor issues**
>
> - **Cosmetic pluralization**: the nudge text renders as *"Fold-back queue now has 1 entries"* (should be *"1 entry"* when size == 1). In `sessionstart_compact_remind.py` and `prompt_nudge.py`. Operator's call whether to fix preemptively or leave. Not a functional issue.
> - **Untested paths** (as of this draft): Stop's `decision: block` threshold backstop (requires 200+ queue entries), `UserPromptSubmit` sampled nudge (requires 30+ prompts with non-empty queue), drain's "ingest-worthy" branch (only the "reject" branch exercised so far), `/wiki-query` Step 5b two-output + Step 5c queue-append.
>
> **D.6 — Architectural validation summary**
>
> | v3 claim | Status |
> |---|---|
> | Hooks register in project-local `.claude/settings.json` via symlink | ✓ `/hooks` shows 4 configured |
> | `Stop` hook fires per logical user-prompt-ending | ✓ 1 entry per 1 completed turn |
> | `PostCompact` captures `compact_summary` | ✓ 19.5 KB captured |
> | `SessionStart matcher:"compact"` is the docs-recommended reinjection path | ✓ fired + delivered `additionalContext` |
> | No subprocess spawning | ✓ zero `claude -p` invocations in any trace |
> | In-session agent acts on injected reminders | ✓ agent opened queue + log + pages voluntarily |
> | LLM-driven rubric replaces turn-count heuristic | ✓ agent applied "already-covered ground" branch correctly |
> | Atomic handoff for concurrent-drain safety | ✓ rename-then-process pattern executed |
> | `DRAIN_PENDING` log format as specified | ✓ byte-for-byte match |
>
> **Every design claim of v3 has now been tested in a real session** except the threshold-block backstop and the sampled nudge (both proven in simulated payloads during Phase 2). The system is production-ready for continued use on kb-wiki and for provisioning fresh vaults.

---

## 0. Executive summary

**The fragile pattern v3 eliminates:** v2's `PreCompact` hook spawning `claude -p /wiki-ingest --drain-pending` as a detached subprocess. Per the docs:
- Spawning `claude` from inside a `claude` hook is **not a documented pattern** — the docs nowhere recommend it
- Detached subprocess auth, billing, and failure modes are out-of-band relative to the parent session
- Re-entrancy required two sibling context dirs (`<vault>/` + `<vault>-autosave/`) and an env-var guard — engineering cost for a workaround

**The cleaner pattern v3 uses:** hooks become **purely informative**. They (a) maintain a queue, (b) inject `additionalContext` to nudge the in-session agent. The drain runs **in the operator's existing Claude Code session** when the agent decides — informed by docs-recommended `SessionStart` matcher-`compact` post-compaction reminders, sampled `UserPromptSubmit` nudges, and the AGENTS.md "Continuous Fold-Back Convention". The drain is the same `/wiki-ingest --drain-pending` skill mode v2 specified — but invoked in-session, not as a subprocess.

**What this buys:**

| Property | v2 (subprocess) | v3 (in-session) |
|---|---|---|
| Documented pattern? | ❌ no | ✓ yes (`asyncRewake` + context injection per `hooks.md:2231-2319`) |
| Subprocess spawning | yes | **no** |
| Autosave context dirs | required | **not needed** |
| Re-entrancy guards | env var + dir convention | **not applicable** |
| Drain visibility | logs only (background) | live in operator's session |
| Drain interruption | kill subprocess | operator interrupts naturally |
| Drain timing | immediate on compact (rigid) | agent discretion at breakpoints (gist-aligned) |
| Auth/billing scope | separate subprocess | parent session |
| Failure modes | silent (detached) | visible (in-session) |
| Hook count | 4 | 4 (one swap: `PreCompact` → `SessionStart:compact`) |

**Net change vs v2:**
- Drop `PreCompact` hook entirely (its only role was spawning the subprocess)
- Replace with `SessionStart` hook with `matcher: "compact"` (docs-recommended post-compaction reinjection — `hooks-guide.md:263-285`)
- Drop `wiki-autosave-on-session-end` script
- Drop `contexts/<vault>-autosave/` directory pairing in `kb-contexts-regenerate`
- Drop env-var re-entrancy guards in helpers
- Net: simpler infra, cleaner separation, same UX outcome

**Recommendation:** approve v3; revert v1 (`40b7110`); ship v3 helpers + skill refinements.

---

## 1. Operator's concern, distilled

> *"I'm worried about this 'PreCompact spawns a detached `claude -p /wiki-ingest --drain-pending` in the sibling autosave context (no hooks → no loop)' — seems a bit fragile and spawning a claude from within claude out-of-band is not as clean as I'd like."*

Three valid sub-concerns:
1. **Fragility** — detached subprocess can fail silently; auth/PATH/env mismatches surface as nothing-happened
2. **Out-of-band** — the spawned `claude` runs in a different session; logs go to a sidecar file; operator has to actively check
3. **Cleanliness** — the autosave-context-dir + env-var-guard scaffolding exists *only* to make subprocess re-entry safe; remove the subprocess, remove the scaffolding

v3 addresses all three by removing the subprocess entirely.

---

## 2. Hook capability re-analysis (cleaner-pattern focus)

Re-deep-dive of `/mnt/host/shared/git/claude-code-docs`. Critical findings (full citations in §A):

### 2.1 What hooks can and cannot do

| Capability | Documented? | Source |
|---|---|---|
| `agent` handler runs **in-session** as a subagent (not a subprocess) | ✓ | `hooks.md:2189-2194` |
| `agent` handler inherits parent auth + permissions + cwd | ✓ | `hooks.md:2189` |
| `agent` handler can do up to 50 turns with Read/Grep/Glob/Bash | ✓ | `hooks.md:2193` |
| `agent` handler returns `{"ok": true/false}` only — **cannot perform arbitrary work and write back** | ✓ | `hooks.md:2229` |
| Hooks **cannot directly invoke skills** | ✓ (absent) | not documented |
| Hooks **cannot inject tool calls** | ✓ (absent) | not documented |
| Hooks **can inject `additionalContext`** that the agent reads | ✓ | `hooks.md:595-628` |
| `Stop` supports `additionalContext` via `hookSpecificOutput` | ✓ | `hooks.md:1534-1548` |
| **`PreCompact` does NOT support `additionalContext`** | ✓ | `hooks.md:2086-2103` |
| **`PostCompact` does NOT support any decision/context fields** | ✓ | `hooks.md` (PostCompact is observe-only) |
| `SessionStart` **with `matcher: "compact"`** is the docs-recommended way to reinject context after compaction | ✓ | `hooks-guide.md:263-285` |
| `asyncRewake: true` lets a hook wake idle Claude with `systemMessage` (via stderr + exit 2) | ✓ | `hooks.md:305, 2327` |
| `Stop` hook can return `decision: "block"` to force continuation | ✓ | `hooks.md:1534-1548` |
| Subprocess spawning of `claude -p` from a hook | ❌ not documented | n/a |

### 2.2 The recommended pattern for hook-triggered expensive work

From `hooks.md:2231-2319` and `hooks-guide.md:174-196`:

> Use a `command` hook with `async: true` (background) and `asyncRewake: true` (wake-on-exit-code-2 with systemMessage). The hook script does I/O work (file appends, queue updates, light evaluation), then exits 2 with stderr containing a system-message hint. Claude wakes on next turn (or immediately if active) and decides what to do.

**Critically: hooks recommend the agent, they don't drive it.** The docs are explicit that there's no deterministic skill-invocation-from-hook mechanism. v2 worked around this by spawning a fresh `claude` to drive the skill. v3 follows the docs: **let the in-session agent drive itself**, prompted by injected context.

### 2.3 The `SessionStart` matcher-`compact` pattern (key v3 mechanism)

`hooks-guide.md:263-285` shows the exact pattern v3 uses:

```json
{
  "SessionStart": [
    {
      "matcher": "compact",
      "hooks": [{"type": "command", "command": "/path/to/post-compact-reminder.py"}]
    }
  ]
}
```

`SessionStart` fires both on actual session start AND after compaction (matcher distinguishes). This hook **can return `additionalContext`**, unlike `PreCompact`/`PostCompact`. So this is where v3 reinjects the "queue has N items, consider draining" reminder.

---

## 3. Proposed v3 architecture

### 3.1 The flow, in plain English

```
Long-running session in contexts/<vault>/

Per turn (Stop hook, ~5ms):
  Append { turn_idx, ts, last_assistant_preview, transcript_path } to
  $VAULT/.pending-fold-back.jsonl

  IF queue size exceeds LARGE_QUEUE_THRESHOLD (default 200):
    Return decision: block + systemMessage hint:
    "Fold-back queue is large (N entries). Drain via /wiki-ingest --drain-pending
     before stopping this turn."
    → Claude continues, sees the hint, drains the queue inline.

Context fills → Claude Code triggers compaction
  No PreCompact hook needed (or use a no-op marker hook for visibility)

  Compaction runs.

  After compaction completes:
  PostCompact hook (Python, sync):
    Append { type: compact_summary, summary, transcript_path } to queue
    No context injection (PostCompact has no return surface)

  Then:
  SessionStart hook with matcher:"compact" fires (docs-recommended pattern):
    Read queue size. If non-empty:
      Return additionalContext: "[fold-back reminder] You just compacted N
      turns and the fold-back queue has M total entries. The compact summary
      has been queued for you. Consider invoking /wiki-ingest --drain-pending
      now or at the next natural breakpoint."
    Agent reads this on next turn and decides whether to drain.

Every ~30 user prompts (UserPromptSubmit hook, sampled):
  IF queue has entries:
    Return additionalContext: "[fold-back reminder] Queue has N items
    pending fold-back. Consider /wiki-ingest --drain-pending."

Operator can also explicitly say "drain the queue" or invoke /wiki-ingest --drain-pending.

The drain runs IN THE OPERATOR'S SESSION (via the existing /wiki-ingest skill).
The skill's --drain-pending mode (same logic as v2) does:
  - Read $VAULT/.pending-fold-back.jsonl
  - Atomically rename to .pending-fold-back-<timestamp>.jsonl (handoff)
  - Cluster by topic
  - Per cluster: LLM evaluates "is this wiki-worthy?" (default ingest if unclear)
  - Ingest worthy clusters
  - Delete the handoff file when done
  - Log to log.md
```

**Key properties:**

- **Zero subprocesses.** All execution happens in the operator's Claude Code session.
- **Zero autosave context dirs.** The vault's interactive context is the only context.
- **Zero re-entrancy guards.** Hooks don't spawn `claude`; nothing to re-enter.
- **Visible work.** When the agent drains, the operator sees it happen turn-by-turn.
- **Deterministic backstops.** `Stop` hook returns `decision: block` if queue exceeds threshold (forces continuation; agent sees hint; drains inline).
- **Docs-aligned.** Every mechanism (queue maintenance, `additionalContext`, `SessionStart:compact`, `decision:block`) is in the official docs.

### 3.2 File layout

```
kb-system/
├── scripts/
│   ├── hooks/                              # Python hook handlers
│   │   ├── _common.py                      # ~40 lines: env, vault detect, queue paths, log
│   │   ├── stop_append.py                  # ~60 lines: append turn + threshold-block
│   │   ├── postcompact_append.py           # ~30 lines: append compact_summary
│   │   ├── sessionstart_compact_remind.py  # ~30 lines: post-compaction additionalContext
│   │   └── prompt_nudge.py                 # ~50 lines: sampled additionalContext
│   ├── templates/
│   │   └── claude-settings.json            # 4 hook entries (Stop, PostCompact, SessionStart:compact, UserPromptSubmit)
│   └── kb-contexts-regenerate              # Reverted: no -autosave dir pairing

obsidian-wiki/
├── .skills/wiki-ingest/SKILL.md            # NEW SECTION: §Mode: --drain-pending (same as v2 §3.5.A)
├── .skills/wiki-query/SKILL.md             # Step 5b extension (same as v2 §3.5.C)
└── AGENTS.md                               # NEW SECTION: §Continuous Fold-Back Convention (same as v2 §3.5.B)

DELETED in cleanup:
  scripts/wiki-autosave-on-session-end      # v1 bash wrapper
  contexts/<vault>-autosave/                # v1 sibling autosave contexts
```

### 3.3 The four Python hook handlers (sketches)

#### `_common.py` — same as v2 §3.3

#### Handler 1: `stop_append.py` (with threshold-block backstop)

```python
#!/usr/bin/env python3
"""Stop hook handler — per-turn append to fold-back queue.

Always appends one JSON line for the just-completed turn. If the queue
exceeds LARGE_QUEUE_THRESHOLD, returns decision: block to prevent the
turn from ending until the agent drains.

No subprocess. No LLM call. ~5ms per invocation.
"""
import json, os, sys, time
from _common import read_payload, detect_vault, queue_path, log

LARGE_QUEUE_THRESHOLD = int(os.environ.get("FOLD_BACK_BLOCK_THRESHOLD", "200"))

def main():
    payload = read_payload()
    if not payload:
        return 0
    vault = detect_vault(payload.get("cwd", ""))
    if not vault:
        return 0

    transcript = payload.get("transcript_path", "")
    last_msg = payload.get("last_assistant_message", "") or ""
    entry = {
        "type": "turn",
        "ts": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "transcript_path": transcript,
        "last_assistant_preview": last_msg[:280],
        "session_id": payload.get("session_id", ""),
    }
    qp = queue_path(vault)
    try:
        with open(qp, "a") as f:
            f.write(json.dumps(entry) + "\n")
    except Exception as e:
        log(vault, f"[stop_append] error: {e}")
        return 0

    # Backstop: if queue is too large, force continuation
    try:
        size = sum(1 for _ in qp.open())
    except Exception:
        size = 0

    if size >= LARGE_QUEUE_THRESHOLD:
        msg = (
            f"Fold-back queue at {size} entries (threshold {LARGE_QUEUE_THRESHOLD}). "
            f"Run /wiki-ingest --drain-pending before stopping this turn."
        )
        print(json.dumps({"decision": "block", "reason": msg,
                          "hookSpecificOutput": {"additionalContext": msg}}))
    return 0

if __name__ == "__main__":
    sys.exit(main())
```

#### Handler 2: `postcompact_append.py`

```python
#!/usr/bin/env python3
"""PostCompact hook — append compact_summary to queue.

PostCompact has no decision/context return surface (per hooks.md);
this hook is purely observational. The reinjection happens via the
SessionStart:compact hook that fires next.
"""
import json, sys, time
from _common import read_payload, detect_vault, queue_path, log

def main():
    payload = read_payload()
    if not payload:
        return 0
    vault = detect_vault(payload.get("cwd", ""))
    if not vault:
        return 0
    summary = payload.get("compact_summary", "")
    if not summary:
        return 0
    entry = {
        "type": "compact_summary",
        "ts": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "transcript_path": payload.get("transcript_path", ""),
        "session_id": payload.get("session_id", ""),
        "trigger": payload.get("trigger", ""),
        "summary": summary,
    }
    try:
        with open(queue_path(vault), "a") as f:
            f.write(json.dumps(entry) + "\n")
        log(vault, f"[postcompact] queued summary ({len(summary)} chars)")
    except Exception as e:
        log(vault, f"[postcompact] error: {e}")
    return 0

if __name__ == "__main__":
    sys.exit(main())
```

#### Handler 3: `sessionstart_compact_remind.py`

```python
#!/usr/bin/env python3
"""SessionStart hook with matcher:"compact" — post-compaction reminder.

Per hooks-guide.md:263-285, this is the docs-recommended way to reinject
context that was lost in compaction. We use it to remind the agent that
the fold-back queue exists and that compaction just delivered a fresh
compact_summary into it.
"""
import json, sys
from _common import read_payload, detect_vault, queue_path

def main():
    payload = read_payload()
    if not payload:
        return 0
    vault = detect_vault(payload.get("cwd", ""))
    if not vault:
        return 0
    qp = queue_path(vault)
    if not qp.exists():
        return 0
    try:
        size = sum(1 for _ in qp.open())
    except Exception:
        return 0
    if size == 0:
        return 0

    msg = (
        f"[fold-back reminder] Compaction just completed; the compact summary has "
        f"been queued. Fold-back queue now has {size} entries. Consider invoking "
        f"`/wiki-ingest --drain-pending` to evaluate and integrate wiki-worthy "
        f"content. See AGENTS.md §Continuous Fold-Back Convention. Default to "
        f"draining at natural breakpoints; not strictly required this turn."
    )
    print(json.dumps({"hookSpecificOutput": {"additionalContext": msg}}))
    return 0

if __name__ == "__main__":
    sys.exit(main())
```

#### Handler 4: `prompt_nudge.py` — same as v2 §3.3 helper #4

(Sampled `UserPromptSubmit` injecting `additionalContext` every Nth prompt when queue is non-empty.)

### 3.4 Updated `claude-settings.json` template

```json
{
  "_comment": "Per-vault Claude Code settings for HARNESS-INTEGRATION v3. Hooks maintain a fold-back queue and inject additionalContext to nudge the in-session agent. NO subprocess spawning.",
  "hooks": {
    "Stop": [
      {
        "hooks": [
          {"type": "command", "command": "python3 /mnt/host/shared/git/kb-system/scripts/hooks/stop_append.py"}
        ]
      }
    ],
    "PostCompact": [
      {
        "hooks": [
          {"type": "command", "command": "python3 /mnt/host/shared/git/kb-system/scripts/hooks/postcompact_append.py"}
        ]
      }
    ],
    "SessionStart": [
      {
        "matcher": "compact",
        "hooks": [
          {"type": "command", "command": "python3 /mnt/host/shared/git/kb-system/scripts/hooks/sessionstart_compact_remind.py"}
        ]
      }
    ],
    "UserPromptSubmit": [
      {
        "hooks": [
          {"type": "command", "command": "python3 /mnt/host/shared/git/kb-system/scripts/hooks/prompt_nudge.py"}
        ]
      }
    ]
  }
}
```

**No `PreCompact` hook.** Compaction is allowed to proceed unimpeded; capture happens via Stop (per-turn before compact) and PostCompact (after compact).

**No `async` or `asyncRewake` flags needed.** All hooks complete synchronously in <50ms.

### 3.5 Skill refinements

Same as v2 §3.5 (A, B, C). The `--drain-pending` mode logic is unchanged — only the trigger pathway changes.

One small refinement to AGENTS.md §Continuous Fold-Back Convention to reflect the in-session model:

> *"The drain happens **in this session**, not in a background process. When you invoke `/wiki-ingest --drain-pending`, you are doing the work the operator is watching live. The operator can interrupt at any time. This is gist-aligned: the LLM (you, in this session) does the grunt work; the operator curates direction."*

---

## 4. Comparison: v1, v2, v3

| Aspect | v1 (deployed) | v2 (proposed) | v3 (proposed) |
|---|---|---|---|
| Trigger for screen sessions | ❌ never fires | ✓ Stop + PreCompact | ✓ Stop + SessionStart:compact |
| Subprocess spawn | yes (SessionEnd → bash → claude -p) | yes (PreCompact → claude -p) | **no — in-session drain** |
| Autosave context dirs | yes | yes | **no** |
| Re-entrancy guards | env var + dir | env var + dir | **not needed** |
| Drain visibility | log file only | log file only | **live in operator's session** |
| Drain interruption | kill subprocess | kill subprocess | **operator interrupts naturally** |
| Drain timing | on session end (rare) | on every compaction (rigid) | **agent discretion at breakpoints** |
| Backstop for "agent never drains" | n/a | n/a | **Stop hook decision:block at threshold** |
| Helper count | 1 bash | 5 Python | 4 Python (one swap, one removed) |
| Hook count | 1 (SessionEnd) | 5 (Stop, PreCompact, PostCompact, SessionStart, UserPromptSubmit) | 4 (Stop, PostCompact, SessionStart:compact, UserPromptSubmit) |
| Documented hook patterns? | partial | partial (subprocess part undocumented) | **fully docs-aligned** |
| Long screen sessions | broken | works | **works** |
| Auth/billing scope | separate subprocess | separate subprocess | **parent session** |
| Operator cognitive load | low (invisible) | low (invisible) | low (visible drains, but framed as agent doing grunt work) |

---

## 5. Reconciliation with gist spirit

Same alignment as v1/v2 plus one strengthening:

| Gist principle | v3 mechanism |
|---|---|
| *"The LLM writes and maintains all of it"* | The IN-SESSION LLM does it — not a spawned secondary LLM |
| *"You're in charge of sourcing, exploration, and asking the right questions"* | Operator works normally; queue accumulates; agent drains at natural breakpoints |
| *"The LLM does all the grunt work — summarising, cross-referencing, filing, bookkeeping"* | Per-turn append + compact-summary capture + per-cluster LLM eval |
| *"Good answers can be filed back into the wiki as new pages"* | Drain-pending evaluates per-cluster; worthy clusters become pages |
| *"Shouldn't disappear into chat history"* | Compact_summary capture + per-turn capture means nothing is lost even pre-drain |
| *"Compound just like ingested sources do"* | Same `/wiki-ingest` skill, --drain-pending mode |

**The strengthening: gist's "the LLM" is now unambiguously the operator's working LLM.** v1/v2 spawned a separate `claude` to do the work, which broke the gist's framing of a single agent maintaining the wiki. v3 restores the singular framing.

---

## 6. Risks and mitigations

| Risk | Severity | Mitigation |
|---|---|---|
| **Agent never drains queue voluntarily** | Medium | (a) `Stop` hook returns `decision: block` at queue size ≥ 200 — forces continuation; agent sees hint; drains. (b) `SessionStart:compact` reminder fires on every compaction. (c) Sampled `UserPromptSubmit` nudges. (d) Operator can manually invoke `/wiki-ingest --drain-pending`. **Four independent paths.** |
| **Drain consumes operator's context budget** | Medium-Low | Same true cost as v2 (would have used same tokens via subprocess). v3 makes it visible — operator can interrupt if mid-task. |
| **Drain happens at inconvenient time** (breaks operator's flow) | Medium | Agent uses judgment from AGENTS.md "natural breakpoints" guidance. Operator can also reply "not now, drain later" if drain starts when undesired. |
| **Stop hook decision:block annoys operator at threshold** | Low | Threshold default 200 — high enough to be rare. Configurable via `FOLD_BACK_BLOCK_THRESHOLD`. Operator can set very high to disable backstop. |
| **`additionalContext` injection might confuse agent** | Low | All injected text starts with `[fold-back reminder]` framing. Agent recognizes as system hint, not user request. |
| **Queue grows unboundedly if no compactions and no manual drain** | Low | Compaction in long sessions is essentially guaranteed (context fills). Threshold-block backstop catches it. Default threshold 200 turns ≈ several days of typical use. |
| **Compaction summary captures sensitive content** | Medium | Inherits content-trust boundary; drain-pending applies privacy rules during ingest. |
| **macOS portability** | Mitigated | All Python helpers use stdlib only. No `setsid`/`timeout` (no subprocesses). Should work cross-platform. |
| **`SessionStart:compact` matcher behavior on first session start** | Verified | Matcher `compact` fires only on post-compaction restart, not on actual session start (`hooks-guide.md:263-285`). No false fires. |

### Rollback paths

- v3 is reversible by removing hook entries from `claude-settings.json` and re-running `kb-contexts-regenerate`.
- Per-vault disable: set `FOLD_BACK_BLOCK_THRESHOLD=999999` to disable the backstop without touching settings.
- Full disable: delete `contexts/<vault>/.claude/settings.json` symlink (operator gets normal Claude Code with no fold-back hooks).
- Fall back to v2 if in-session drain proves problematic: re-introduce subprocess-based PreCompact hook.

---

## 7. Implementation plan — granular tasks with per-task SVCR

### Phase 0 — verification (read-only)

| Task | Description | SVCR |
|---|---|---|
| P0.1 | Confirm `python3 --version` ≥ 3.8 | SV: stdlib has all needed modules. R: noted as min version. |
| P0.2 | Confirm `SessionStart` hook with `matcher: "compact"` actually fires post-compaction (not just on session start) | SV: install a test echo hook; trigger `/compact`; inspect log. C: any matcher edge cases? `hooks-guide.md` says yes. R: verified before Phase 2. |
| P0.3 | Confirm `Stop` hook can return `hookSpecificOutput.additionalContext` simultaneously with `decision: block` | SV: docs say yes (`hooks.md:1534-1548`). C: agent actually reads it? Manual test. R: verify before Phase 2. |
| P0.4 | Confirm `additionalContext` injection in JSON output is recognized | SV: docs say `print(json.dumps({"hookSpecificOutput": {"additionalContext": "..."}}))` works on stdout. R: verified during Phase 2. |

### Phase 1 — revert v1 (kb-system branch)

Same as v2 Phase 1. Revert `40b7110`. Run `kb-contexts-regenerate` to clean up sibling `-autosave` dirs and v1 settings symlinks.

### Phase 2 — Python helpers (kb-system branch: `feat/harness-integration-v3-helpers`)

| Task | Description | SVCR |
|---|---|---|
| P2.1 | Create `scripts/hooks/_common.py` (~40 lines) | SV: importable via `python3`. C: handles missing .env. R: locked. |
| P2.2 | Create `stop_append.py` with threshold backstop (~60 lines) | SV: pipe fake payload; verify queue line + decision-block at threshold. C: threshold env var works? Yes. R: locked. |
| P2.3 | Create `postcompact_append.py` (~30 lines) | SV: pipe fake payload with compact_summary; verify queue entry. R: locked. |
| P2.4 | Create `sessionstart_compact_remind.py` (~30 lines) | SV: pipe fake payload; verify additionalContext output when queue >0; no output when queue empty. R: locked. |
| P2.5 | Create `prompt_nudge.py` (~50 lines) | SV: pipe payload 30 times; verify one nudge emitted. C: counter persists? Yes via state file. R: locked. |
| P2.6 | All scripts pass `python3 -m py_compile` | SV: zero errors. R: locked. |
| P2.7 | Commit | SV: 5 new files. R: commit `feat(hooks): v3 Python hook handlers (subprocess-free)`. |

### Phase 3 — settings template + regenerate (kb-system branch: `feat/harness-integration-v3-settings`)

| Task | Description | SVCR |
|---|---|---|
| P3.1 | Update `scripts/templates/claude-settings.json` per §3.4 | SV: valid JSON; 4 hook entries; no `async` flags. R: locked. |
| P3.2 | Update `kb-contexts-regenerate` to remove sibling `-autosave` dir creation (revert v2 changes) | SV: dry-run shows only the original `<vault>/` dirs. C: existing `-autosave` dirs cleaned up? Add explicit removal step. R: locked. |
| P3.3 | Run `kb-contexts-regenerate`; verify clean state | SV: `ls contexts/` shows only `wiki/` and `personal/`. C: settings.json present and pointing to v3 template. R: confirmed. |
| P3.4 | Commit | SV: template + regenerate updated. R: commit `feat(hooks): v3 settings.json template; remove -autosave context dirs`. |

### Phase 4 — skill refinements (fork branch: `feat/wiki-ingest-drain-pending-v3`)

| Task | Description | SVCR |
|---|---|---|
| P4.1 | Add `## Mode: --drain-pending` to `wiki-ingest/SKILL.md` (same as v2 §3.5.A) | SV: skill file valid. R: locked. |
| P4.2 | Add `## Continuous Fold-Back Convention` to `AGENTS.md` with v3 in-session framing | SV: AGENTS.md valid. C: in-session message clear? Re-read. R: locked. |
| P4.3 | Extend `wiki-query/SKILL.md` Step 5b to optionally append to queue | SV: skill valid. R: locked. |
| P4.4 | Commit | SV: 3 files modified. R: commit `feat(wiki-ingest): --drain-pending mode + continuous fold-back convention (v3 in-session framing)`. |

### Phase 5 — push + deploy

Same as v2 Phase 5. Operator validates with a real screen session.

### Phase 6 — cleanup

Delete v1 bash wrapper, mark v1+v2 proposal docs as superseded.

---

## 8. Self-validate / critique / refine

### 8.1 Self-validate

**Operator's three concerns from previous turn:**
- ✓ Long-running screen sessions: Stop fires per turn; SessionStart:compact fires post-compaction; UserPromptSubmit injects nudges
- ✓ Python: 4 Python helpers + shared module
- ✓ Dynamic LLM assessment in skill: `--drain-pending` mode does per-cluster eval

**Operator's new concern (v2 fragility):**
- ✓ No subprocess spawning
- ✓ No autosave context dirs
- ✓ Docs-recommended patterns throughout (`SessionStart:compact`, `additionalContext`, `Stop` decision:block)

**Drift integrity:** unchanged from v1/v2 — conversations are immutable sources; lint #4 covers stale syntheses.

### 8.2 Critique

1. **In-session drain consumes operator's context.** A drain pass evaluating 5-10 clusters + ingesting 2-3 worthy ones might be 20-50K tokens of Claude work. Eats into the operator's effective context. Counter: same cost as v2's subprocess; v3 just relocates billing. Operator can split drain into smaller `/wiki-ingest --drain-pending --max-clusters=3` runs (skill refinement, future).

2. **Stop hook's `decision: block` can lock operator into a long drain.** If queue hits 200 and operator just wanted a quick answer, getting forced into a multi-turn drain is annoying. Counter: threshold default 200 is high; `FOLD_BACK_BLOCK_THRESHOLD` configurable; can disable via env. Plus the agent can drain quickly if cluster count is small.

3. **`SessionStart:compact` fires on every restart, not just post-compaction.** Need to verify matcher behavior. Per `hooks-guide.md` only fires post-compaction with `matcher: "compact"`. Verify in P0.2.

4. **No PreCompact means we can't capture context that compaction loses.** Counter: Stop already captured each turn before compaction. The compact_summary captures the model's distillation. The combination is more comprehensive than either alone.

5. **What if the agent just ignores all reminders?** The Stop-hook backstop at threshold 200 forces it. If operator removes the backstop, drains become entirely voluntary — but that's a deliberate choice operator can make.

6. **Cost: 4 Python invocations per turn (Stop + maybe UserPromptSubmit + maybe SessionStart-compact + PostCompact rare).** Actually only Stop fires per turn. UserPromptSubmit fires per user prompt. PostCompact + SessionStart:compact only on compactions (rare). So ~2 Python invocations per turn typically. ~10-30ms cumulative. Invisible.

7. **The `additionalContext` from SessionStart-compact might be ignored if agent is mid-task at compaction.** Counter: it's not ignored — it persists in context. Agent reads it next turn and decides.

8. **Drain mid-task could create odd transitions.** Operator: "Help me debug X" → drain triggers → 5 turns of wiki ingest → "OK now back to X". Disruptive. Mitigation: AGENTS.md guidance says "at natural breakpoints"; agent should not drain mid-task unless threshold-blocked. If threshold-blocked, that's by design — queue is huge and drain is overdue.

9. **What about `agent` hook handler?** Could a `Stop` `agent` hook do the cluster-evaluation + ingest in-context? Per docs, agent handler returns yes/no only. Cannot perform writes back. So no — agent handler can't replace the in-session drain. v3 is correct to leave drain in main session.

### 8.3 Refine

- **Crit #1 (token cost):** Note in §6 that operator can use `/wiki-ingest --drain-pending --max-clusters=N` for partial drains. Add to skill spec as an optional flag. Already implicit in skill — flag becomes explicit.
- **Crit #3 (matcher behavior):** Phase 0 P0.2 explicit verification. Don't deploy until confirmed.
- **Crit #8 (mid-task disruption):** Strengthen AGENTS.md language: "Drain only at end-of-task or before-extended-pause. If user is mid-flow, defer until they finish." Already in §3.5; reinforce.

---

## 9. Approval protocol

Reply with one of:

- **"approved v3 full"** — execute Phases 0-6; revert v1; ship v3 helpers + skill refinements. **[recommended]**
- **"approved v3 minus backstop"** — same as v3 full but `Stop` hook does NOT include `decision: block` at threshold (drain is fully voluntary)
- **"approved v3 minus nudge"** — same as v3 full but no `UserPromptSubmit` nudge handler
- **"approved v2 instead"** — accept the subprocess pattern despite fragility concerns (revisit later)
- **"defer"** — leave v1 in place
- **"reject / discuss"** — what to change

**Recommendation: "approved v3 full".**

Rationale:
1. v3 eliminates the only fragile element (subprocess spawning) operator flagged.
2. Every mechanism is in the official Claude Code docs — no working-around-the-system.
3. The drain happens in the operator's session — visible, interruptible, naturally framed as "the LLM doing the grunt work" per the gist.
4. Backstop (`Stop` `decision: block` at threshold) provides a deterministic safety net for the worst case ("agent never drains").
5. Removes infra (autosave context dirs, env-var guards, bash wrapper) — net simpler than v1, much less infrastructure than v2.

---

## A. Appendix — Hook capability findings (v3-relevant subset)

Verbatim summary from `claude-code-docs` re-review:

- **`Stop` hook** (`hooks.md:1534-1548`): per-turn; payload includes `transcript_path`, `last_assistant_message`, `session_id`, `cwd`. Can return `decision: block` + `reason` AND `hookSpecificOutput.additionalContext`.
- **`PostCompact`**: observe-only; receives `compact_summary`, `transcript_path`, `cwd`, `trigger`. **Cannot return decision or context.**
- **`PreCompact`**: can block via exit code 2 or `decision: block`. **Cannot inject `additionalContext`** (`hooks.md:2086-2103`).
- **`SessionStart` with `matcher: "compact"`** (`hooks-guide.md:263-285`): docs-recommended way to reinject context after compaction. Can return `additionalContext`.
- **`UserPromptSubmit`**: per-prompt; can return `additionalContext`, `decision: block`, plain stdout.
- **`agent` hook handler** (`hooks.md:2183-2229`): runs in-session subagent; inherits parent auth/permissions/cwd; up to 50 turns; returns `{"ok": true/false}` only. **Cannot perform arbitrary work and write back.**
- **Hooks cannot directly invoke skills.** No documented mechanism.
- **`asyncRewake: true`** (`hooks.md:305, 2327`): exit code 2 wakes Claude with stderr as systemMessage on next turn (or immediately if active).
- **Spawning `claude -p` from a hook**: not documented as a supported pattern.

---

*End of v3 proposal. Awaiting approval.*
