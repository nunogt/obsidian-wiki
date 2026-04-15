# Harness integration v2 — long-session-aware, Python-based, skill-driven assessment

> **⚠ SUPERSEDED 2026-04-15 by [HARNESS-INTEGRATION-PROPOSAL-v3.md](./HARNESS-INTEGRATION-PROPOSAL-v3.md).** v2 fixed v1's `SessionEnd` issue and rewrote in Python, but retained the subprocess pattern (`PreCompact` hook spawning `claude -p`). Operator flagged this as fragile and out-of-band. v3 eliminates the subprocess entirely — hooks queue + inject context, in-session agent drains.
>
> Preserved here for historical context.

---

*Drafted 2026-04-15. Supersedes v1 (`HARNESS-INTEGRATION-PROPOSAL.md`, already implemented as commit `40b7110`). Based on operator feedback flagging three issues with v1: (1) `SessionEnd` never fires for the operator's long-running `screen` sessions, (2) bash is less portable than Python, (3) the 10-turn triviality skip is a crude proxy that misses dense short sessions. Re-deep-dive of `/mnt/host/shared/git/claude-code-docs` produced the architecture below. Nothing executed — assessment + proposal for review.*

---

## 0. Executive summary

**v1's three flaws (operator-flagged):**

1. **`SessionEnd` is the wrong trigger** for sessions that live in `screen` for weeks at a time. The hook never fires; autosave never runs; the wiki never compounds.
2. **Bash is fine but Python is more portable** and easier to unit-test for the operator's preferences.
3. **`MIN_TURNS=10` is a crude proxy** for "wiki-worthy." A 3-turn session with a sharp prompt can produce more durable knowledge than 50 turns of trial-and-error.

**v2 addresses all three:**

1. **Trigger** — drop `SessionEnd`. Use a **mix of per-turn and lifecycle hooks** that fire continuously inside long sessions:
   - `Stop` (per assistant turn) — append turn marker to a queue
   - `PreCompact` + `PostCompact` (auto-fires when context fills, even in screen sessions) — drain the queue + capture compact summary
   - `UserPromptSubmit` (sampled 1-in-N, with `additionalContext` injection) — periodic nudge to Claude about fold-back convention
2. **Python** — replace the bash wrapper with 4 small Python helpers (~50 lines each) plus a shared `_common.py`. Standard library only; no extra deps beyond `python3` itself.
3. **Dynamic assessment** — the **hook is dumb (queue maintenance only); the skill is smart**. Refine `wiki-ingest` with a new `--drain-pending` mode that asks the LLM per-cluster "is this wiki-worthy?" and ingests only the yes-cases. Assessment lives in the skill prompt; agent does the evaluation in-context. No turn-count gates.

**Net change vs v1:**

| Aspect | v1 | v2 |
|---|---|---|
| Trigger | `SessionEnd` only | `Stop` + `PreCompact` + `PostCompact` + sampled `UserPromptSubmit` |
| Helper language | bash | Python 3 (stdlib only) |
| Helper count | 1 (`wiki-autosave-on-session-end`, ~80 lines) | 5 (4 hook handlers + 1 shared) |
| Triviality filter | turn count | LLM-evaluated per-cluster, in skill |
| Works for screen sessions | ❌ | ✓ |
| Re-entrancy guard | env var + autosave context dir | same |
| Lines of code (helper layer) | ~80 bash | ~250 Python (including doc-strings) |
| Lines of skill prompt added | 0 | ~40 (wiki-ingest `--drain-pending` mode + CLAUDE.md fold-back convention) |

**v1 → v2 migration path:** revert v1's commit, install v2 helpers + settings.json, regenerate contexts. Same overall topology (interactive vs autosave context dir paired by naming).

**Recommendation:** approve v2 (full); revert v1's commit; ship as 1-2 fork patches + 1-2 kb-system commits.

---

## 1. Operator's feedback, distilled

> *"I tend not to exit the session, I have claude sessions in `screen` that have been running for weeks in a row, and I suspect that's a common use-case."*

This invalidates v1's primary trigger. `SessionEnd` only fires on actual session termination — kill, exit, crash. Long-running `screen` sessions essentially never trigger it.

> *"I'd like to avoid bash if possible, as I find python more portable."*

Python 3.x is available on every modern Linux/macOS without a separate install, and is more portable for cross-machine deployment. Operator preference.

> *"We shouldn't assume sessions under 10 prompts are trivial as good prompting packs a lot of capabilities in it. My preference would be a dynamic assessment of the relevance of the prompt and whether they produce meaningful value that should be integrated in the wiki, dynamically, through small refinements of existings skills."*

Two distinct preferences:
- **No turn-count heuristic.** Replace with LLM evaluation.
- **Logic lives in skills, not infrastructure.** Hook scripts should be minimal; the skill prompt should do the assessment.

---

## 2. Hook capability re-analysis (long-session-aware)

Re-reviewed `/mnt/host/shared/git/claude-code-docs` for hooks that fire while a session stays alive. Findings (full details in §A):

### 2.1 Per-turn hooks (fire continuously in long sessions)

| Hook | Fires | Has `transcript_path`? | Can inject context? | Can spawn detached work? |
|---|---|---|---|---|
| **`Stop`** | After every assistant turn | ✓ (also `last_assistant_message`) | ❌ (only `decision`, `reason`) | ✓ (via `command` handler + `setsid`) |
| **`UserPromptSubmit`** | Before each user prompt | ✓ | ✓ (`additionalContext` field; 10K char cap) | ✓ |
| **`PreToolUse` / `PostToolUse`** | Before/after each tool call | ✓ | ✓ | ✓ |

**Verdict:** `Stop` is the canonical per-turn trigger. `UserPromptSubmit` is the canonical context-injection vector.

### 2.2 Lifecycle hooks that fire in long sessions

| Hook | Fires | Useful for fold-back? |
|---|---|---|
| **`PreCompact`** | Before context compaction (auto when full, or manual `/compact`) | **Yes — context is about to be lost** |
| **`PostCompact`** | After compaction completes; receives `compact_summary` | **Yes — summary is distilled gold** |
| `SessionStart` | Once at start | Marginal (could pre-load wiki context — separate concern) |
| `SessionEnd` | Never fires for screen sessions | **Don't rely on** |
| `TaskCompleted` | When a Task is marked complete | Niche (not generic "work done" signal) |

**Verdict:** `PreCompact` is the natural fold-back moment. The gist's *"shouldn't disappear into chat history"* literally happens at compaction — context that's about to be discarded is the highest-leverage capture moment.

### 2.3 Hook handler types

| Type | LLM eval? | Cost | Spawn background? | Default timeout |
|---|---|---|---|---|
| `command` | No (exit codes) | n/a | **Yes** (`async: true` or `setsid` in script body) | 600s |
| `prompt` | Yes (single Haiku call) | ~$0.001/call | No | 30s |
| `agent` | Yes (multi-turn subagent) | Higher | No | 60s |
| `http` | No | per-server | No | 30s |

For v2 we use **`command` type for all hooks** (Python scripts via shebang). LLM evaluation is performed by the skill, not the hook — so we don't need the `prompt` handler. The `command` type's `async: true` lets us schedule detached drain work without blocking Claude.

### 2.4 Throttling & state

**Not built-in.** Hook scripts manage their own state via files (e.g., `$VAULT/.autosave-state.json`). v2 uses a tiny shared state file: counter for `UserPromptSubmit` sampling, `last_drained_turn` for queue cleanup.

### 2.5 Python compatibility

Hook scripts run with arbitrary shebang. **Python is not officially documented but works** — `#!/usr/bin/env python3` followed by reading JSON from stdin is fine. Standard library covers everything we need.

### 2.6 Vault-context detection

**Not built-in.** Hook scripts must inspect `$PWD` for an `.env` file with `OBSIDIAN_VAULT_PATH`. v2's `_common.py` does this in 5 lines.

---

## 3. Proposed v2 architecture

### 3.1 The flow, in plain English

```
Long-running session starts in contexts/<vault>/ → Stop hook fires per turn

Per turn (Stop hook, ~5ms):
  Append { turn_idx, timestamp, last_assistant_message_preview, transcript_path }
  to $VAULT/.pending-fold-back.jsonl

Every ~30 user prompts (UserPromptSubmit hook, sampled):
  Inject additionalContext: "Reminder — pending fold-back queue has N entries.
  Consider /wiki-ingest --drain-pending at the next natural break."

Context fills → Claude Code triggers auto-compaction
  PreCompact hook fires:
    Schedule background `claude -p /wiki-ingest --drain-pending` in autosave context.
    Detached via setsid; doesn't block compaction.

  Compaction runs, generating compact_summary.

  PostCompact hook fires:
    Append { type: "compact_summary", summary: <text>, source_transcript: <path> }
    to the same queue. (Catches what would otherwise vanish.)

The background drain (running in autosave context, no hooks → no loop):
  Reads $VAULT/.pending-fold-back.jsonl
  /wiki-ingest --drain-pending mode logic:
    - Cluster queue entries by topic (LLM-driven, like normal ingest)
    - For each cluster, ask LLM: "Is this wiki-worthy?"
    - Yes → ingest into wiki (touches 10-15 pages per worthy cluster)
    - No → drop
    - Update queue: remove processed entries
  Logs to $VAULT/_autosave.log

Session continues in screen. Queue starts accumulating again.
```

**Key properties:**
- Works regardless of session lifetime (Stop fires per turn; PreCompact fires on auto-trigger)
- Operator never has to invoke anything explicitly — but CAN at any time via `/wiki-ingest --drain-pending`
- LLM assessment lives in the skill (per cluster), not the hook
- Compact summary is captured (would otherwise be lost on every context fill)
- Re-entrancy: autosave context has no hooks → cannot loop

### 3.2 File layout

```
kb-system/
├── scripts/
│   ├── hooks/                              # NEW — Python hook handlers
│   │   ├── _common.py                      # ~40 lines: load env, vault detect, queue paths
│   │   ├── stop_append_to_queue.py         # ~50 lines: append turn marker
│   │   ├── precompact_schedule_drain.py    # ~40 lines: spawn background drain
│   │   ├── postcompact_append_summary.py   # ~40 lines: capture compact_summary
│   │   └── user_prompt_submit_nudge.py     # ~50 lines: sampled additionalContext
│   ├── templates/
│   │   └── claude-settings.json            # UPDATED — references Python hooks
│   ├── kb-contexts-regenerate              # UNCHANGED structurally
│   └── wiki-autosave-on-session-end        # DELETED (v1 bash wrapper retired)

obsidian-wiki/.skills/wiki-ingest/SKILL.md  # UPDATED — adds §--drain-pending mode
obsidian-wiki/AGENTS.md                     # UPDATED — adds §Continuous fold-back convention
obsidian-wiki/.skills/wiki-query/SKILL.md   # UPDATED — Step 5b can append to queue
```

### 3.3 The four Python hook handlers

All share `_common.py`:

```python
# _common.py (sketch — ~40 lines)
"""Shared utilities for kb-system Claude Code hook handlers."""
import json, os, sys, pathlib, time

def read_payload():
    """Parse JSON hook payload from stdin. Returns dict or None on error."""
    try:
        return json.load(sys.stdin)
    except Exception:
        return None

def detect_vault(cwd):
    """Returns OBSIDIAN_VAULT_PATH if cwd is a vault context, else None.
    Reads cwd/.env and pulls the variable. Quiet on any error."""
    envfile = pathlib.Path(cwd) / ".env"
    if not envfile.is_file():
        return None
    for line in envfile.read_text().splitlines():
        line = line.strip()
        if line.startswith("OBSIDIAN_VAULT_PATH="):
            return line.split("=", 1)[1].strip().strip('"').strip("'")
    return None

def queue_path(vault):
    return pathlib.Path(vault) / ".pending-fold-back.jsonl"

def state_path(vault):
    return pathlib.Path(vault) / ".autosave-state.json"

def log(vault, msg):
    """Append timestamped log entry to vault's _autosave.log. Never raises."""
    try:
        with open(pathlib.Path(vault) / "_autosave.log", "a") as f:
            f.write(f"{time.strftime('%Y-%m-%dT%H:%M:%S%z')} {msg}\n")
    except Exception:
        pass

def is_reentrant():
    return os.environ.get("WIKI_AUTOSAVE_INVOCATION") == "1"
```

#### Handler 1: `stop_append_to_queue.py`

```python
#!/usr/bin/env python3
"""Stop hook handler — per-turn append to fold-back queue.

Fires after every assistant turn. Appends a single JSON line marking
the turn for later evaluation by /wiki-ingest --drain-pending.

Constant cost: ~5ms (Python startup + one fs append).
Never blocks Claude. Never invokes the LLM."""

import json, sys
from _common import read_payload, detect_vault, queue_path, log, is_reentrant

def main():
    if is_reentrant():
        return 0
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
        "ts": payload.get("hook_event_name") and __import__("time").strftime("%Y-%m-%dT%H:%M:%S%z"),
        "transcript_path": transcript,
        "last_assistant_preview": last_msg[:280],
        "session_id": payload.get("session_id", ""),
    }
    try:
        with open(queue_path(vault), "a") as f:
            f.write(json.dumps(entry) + "\n")
    except Exception as e:
        log(vault, f"[stop_append] error: {e}")
    return 0

if __name__ == "__main__":
    sys.exit(main())
```

#### Handler 2: `precompact_schedule_drain.py`

```python
#!/usr/bin/env python3
"""PreCompact hook handler — schedule background drain of fold-back queue.

Fires immediately before context compaction (auto or manual). This is the
natural moment to fold back: context is about to be lost.

Spawns a detached `claude -p /wiki-ingest --drain-pending` in the vault's
sibling autosave context (no hooks there → cannot loop).

Returns immediately; does not block compaction."""

import os, subprocess, sys, pathlib
from _common import read_payload, detect_vault, log, is_reentrant

MAX_DRAIN_SECONDS = 1500   # 25min

def main():
    if is_reentrant():
        return 0
    payload = read_payload()
    if not payload:
        return 0
    cwd = payload.get("cwd", "")
    vault = detect_vault(cwd)
    if not vault:
        return 0

    # Find sibling autosave context: contexts/<vault>/  →  contexts/<vault>-autosave/
    ctx_dir = pathlib.Path(cwd)
    autosave_dir = ctx_dir.parent / f"{ctx_dir.name}-autosave"
    if not autosave_dir.is_dir():
        log(vault, f"[precompact] missing autosave ctx at {autosave_dir} — run kb-contexts-regenerate")
        return 0

    log(vault, f"[precompact] scheduling drain trigger={payload.get('trigger', '?')}")

    # Detach completely; do not wait
    env = dict(os.environ, WIKI_AUTOSAVE_INVOCATION="1")
    try:
        subprocess.Popen(
            ["setsid", "timeout", str(MAX_DRAIN_SECONDS),
             "claude", "-p", "--dangerously-skip-permissions",
             "/wiki-ingest --drain-pending"],
            cwd=str(autosave_dir),
            env=env,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
    except FileNotFoundError as e:
        log(vault, f"[precompact] missing dep: {e}")
    except Exception as e:
        log(vault, f"[precompact] spawn error: {e}")
    return 0

if __name__ == "__main__":
    sys.exit(main())
```

#### Handler 3: `postcompact_append_summary.py`

```python
#!/usr/bin/env python3
"""PostCompact hook handler — append compact_summary to fold-back queue.

Fires after context compaction. The compact_summary field contains a
distilled summary of what was just compressed away — pure gold for
the wiki since it represents what the model itself thought worth
preserving.

Append-only. No LLM call. No spawn."""

import json, sys, time
from _common import read_payload, detect_vault, queue_path, log, is_reentrant

def main():
    if is_reentrant():
        return 0
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
        log(vault, f"[postcompact] queued compact_summary ({len(summary)} chars)")
    except Exception as e:
        log(vault, f"[postcompact] error: {e}")
    return 0

if __name__ == "__main__":
    sys.exit(main())
```

#### Handler 4: `user_prompt_submit_nudge.py`

```python
#!/usr/bin/env python3
"""UserPromptSubmit hook handler — sampled fold-back nudge via additionalContext.

Fires before each user prompt. Most invocations no-op. Every Nth
invocation (default N=30, configurable via FOLD_BACK_NUDGE_EVERY env)
injects an additionalContext line reminding the agent that there's a
pending queue to consider.

The nudge text references the convention documented in CLAUDE.md /
AGENTS.md §Continuous fold-back."""

import json, os, sys
from _common import read_payload, detect_vault, queue_path, state_path, log, is_reentrant

NUDGE_EVERY = int(os.environ.get("FOLD_BACK_NUDGE_EVERY", "30"))

def main():
    if is_reentrant():
        return 0
    payload = read_payload()
    if not payload:
        return 0
    vault = detect_vault(payload.get("cwd", ""))
    if not vault:
        return 0

    # Increment counter
    state_file = state_path(vault)
    try:
        state = json.loads(state_file.read_text()) if state_file.exists() else {}
    except Exception:
        state = {}
    n = state.get("prompt_count", 0) + 1
    state["prompt_count"] = n
    try:
        state_file.write_text(json.dumps(state))
    except Exception as e:
        log(vault, f"[ups_nudge] state write error: {e}")

    if n % NUDGE_EVERY != 0:
        return 0   # silent

    # Count pending queue size
    qp = queue_path(vault)
    pending = 0
    try:
        if qp.exists():
            pending = sum(1 for _ in qp.open())
    except Exception:
        pass

    if pending == 0:
        return 0

    nudge = (
        f"[fold-back reminder] You're working in vault context with {pending} pending "
        f"turns/summaries in the fold-back queue (`{qp}`). At a natural breakpoint, "
        f"consider invoking `/wiki-ingest --drain-pending` to evaluate and integrate "
        f"wiki-worthy content. See AGENTS.md §Continuous fold-back convention."
    )
    print(json.dumps({"hookSpecificOutput": {"additionalContext": nudge}}))
    return 0

if __name__ == "__main__":
    sys.exit(main())
```

### 3.4 Updated `claude-settings.json` template

```json
{
  "_comment": "Per-vault Claude Code settings. Symlinked into contexts/<vault>/.claude/settings.json by kb-contexts-regenerate. Configures hooks for HARNESS-INTEGRATION-PROPOSAL v2 (long-session-aware fold-back).",
  "hooks": {
    "Stop": [
      {
        "hooks": [
          {"type": "command", "command": "python3 /mnt/host/shared/git/kb-system/scripts/hooks/stop_append_to_queue.py"}
        ]
      }
    ],
    "PreCompact": [
      {
        "hooks": [
          {"type": "command", "command": "python3 /mnt/host/shared/git/kb-system/scripts/hooks/precompact_schedule_drain.py", "async": true, "asyncTimeout": 1800}
        ]
      }
    ],
    "PostCompact": [
      {
        "hooks": [
          {"type": "command", "command": "python3 /mnt/host/shared/git/kb-system/scripts/hooks/postcompact_append_summary.py"}
        ]
      }
    ],
    "UserPromptSubmit": [
      {
        "hooks": [
          {"type": "command", "command": "python3 /mnt/host/shared/git/kb-system/scripts/hooks/user_prompt_submit_nudge.py"}
        ]
      }
    ]
  }
}
```

### 3.5 Skill refinements (small, in-skill assessment)

#### A. `wiki-ingest/SKILL.md` — new section after Step 5

```markdown
## Mode: --drain-pending (long-session fold-back)

When invoked as `/wiki-ingest --drain-pending`, the source is the **fold-back queue**
at `$OBSIDIAN_VAULT_PATH/.pending-fold-back.jsonl` rather than a file path.

The queue is populated by hooks (Stop, PostCompact) during long-running sessions.
Each line is a JSON object with `type: "turn" | "compact_summary"`, a transcript
reference, and either a 280-char preview or a full distilled summary.

### Drain-pending procedure

1. Read the queue. If empty, log "no pending entries" and exit.
2. **Cluster** queue entries by topic. Use the previews and (for `turn` entries)
   read the relevant slices of `transcript_path` to get full context. Group
   thematically — same project, same problem space, same conceptual thread.
3. **For each cluster, evaluate wiki-worthiness in-context** (this is the
   dynamic assessment that replaces v1's turn-count gate):
   - *Wiki-worthy* if the cluster contains at least one of: a durable insight
     the operator might want to revisit, a non-obvious connection between
     concepts, a useful procedure that should be canonicalized, an entity
     worth tracking, an analysis whose conclusion outlives the session.
   - *Not wiki-worthy* if the cluster is purely operational (file edits, build
     output, debugging steps that didn't reach a generalisable conclusion),
     pure pleasantries, or already-covered ground (covered by an existing wiki
     page with no new angle).
   - **Default to ingest when in doubt.** A false positive produces a redundant
     wiki update; a false negative loses signal forever. The asymmetry favours
     ingestion.
4. For wiki-worthy clusters, ingest per the standard process (Steps 2-5 above).
   Use the originating `transcript_path` as the `sources:` reference. Set
   `source_type: "claude_conversation"` (or `"claude_compact"` for compact_summary
   entries). Apply provenance markers heavily — these are conversation
   distillations, mostly inferred.
5. **Prune the queue.** Remove processed entries (worthy or not) by rewriting
   the file with only entries that arrived after this drain started (use a
   timestamp cutoff or atomic swap).
6. Log the drain outcome to `log.md`:
   ```
   - [TIMESTAMP] DRAIN_PENDING clusters_evaluated=N clusters_ingested=M entries_processed=K
   ```

### When to invoke this mode

- Automatically on `PreCompact` hook (operator's hook config does this — no
  manual action needed)
- Manually at natural breakpoints (end of research thread, completed analysis,
  before extended idle)
- When the periodic UserPromptSubmit nudge surfaces queue size

### Skip if

- `LINT_SCHEDULE=off` in `.env` (operator opted out of automation)
- Queue file is empty
- Queue file doesn't exist (vault hasn't accumulated any turns)
```

#### B. `AGENTS.md` (and the symlinked CLAUDE.md / GEMINI.md) — new top-level section

```markdown
## Continuous Fold-Back Convention

When operating in a vault context (CWD = `kb-system/contexts/<vault>/`),
treat the conversation itself as a source. Hooks accumulate per-turn markers
and post-compaction summaries in `$OBSIDIAN_VAULT_PATH/.pending-fold-back.jsonl`.

**Your job as the agent:** at natural breakpoints (end of a research thread,
completed analysis, before extended idle), invoke `/wiki-ingest --drain-pending`
to evaluate the queue and ingest wiki-worthy content.

You don't have to wait for an explicit user request. Karpathy's gist:
*"You're in charge of sourcing, exploration, and asking the right questions.
The LLM does all the grunt work — the summarizing, cross-referencing, filing,
and bookkeeping that makes a knowledge base actually useful over time."*

Filing is grunt work. Do it proactively when content warrants.

The PreCompact hook does this automatically when context fills, but you should
also offer or run it after meaningful exchanges, especially if you notice:
- A multi-turn discussion that reached a durable conclusion
- A cross-reference to existing wiki pages that warrants strengthening
- A new entity, concept, or skill the wiki doesn't yet have

The skill's `--drain-pending` mode includes the dynamic LLM assessment of
wiki-worthiness; you don't need to pre-filter — just invoke when it feels right.

Operator can disable by setting `LINT_SCHEDULE=off` in the profile `.env`.
```

#### C. `wiki-query/SKILL.md` — extend Step 5b

Add to the existing two-output rule:

```markdown
**Append to fold-back queue.** If the query produced a synthesis or insight worth
preserving (especially Output 2 suggested updates the operator approved), also
append a marker to `$OBSIDIAN_VAULT_PATH/.pending-fold-back.jsonl`:

```json
{"type": "query_synthesis", "ts": "...", "query": "...", "answer_preview": "...",
 "suggested_updates": [...], "session_id": "..."}
```

This ensures query-driven insights compound the wiki even when no explicit
ingest follows. The `--drain-pending` mode will evaluate them on the next
drain cycle.
```

---

## 4. Comparison: v1 vs v2

| Aspect | v1 (current) | v2 (proposed) |
|---|---|---|
| Trigger for screen sessions | ❌ never fires | ✓ Stop fires per turn; PreCompact fires on auto-compact |
| Trigger for short interactive sessions | ✓ SessionEnd | ✓ Same per-turn + on-demand |
| Helper language | bash (~80 lines) | Python 3 (~250 lines across 5 files, stdlib only) |
| Triviality filter | turn count ≥ 10 | LLM evaluation per cluster, in skill |
| Captures compact_summary | ❌ | ✓ (often the most distilled signal in the session) |
| Operator nudge mechanism | none | sampled UserPromptSubmit injects context |
| State tracking | none | `$VAULT/.pending-fold-back.jsonl` + `.autosave-state.json` |
| Manual fold-back invocation | `/wiki-ingest <transcript-path>` | `/wiki-ingest --drain-pending` |
| Re-entrancy guard | env var + autosave context dir | same |
| Cost per turn | ~0 (no work) | ~5ms (one fs append, no LLM) |
| Cost per drain | LLM ingest of full transcript | LLM evaluation per cluster + ingest of worthy clusters |
| Lines added to fork skills | 0 | ~40 (wiki-ingest §--drain-pending; AGENTS.md §Continuous fold-back; wiki-query Step 5b extension) |
| Approval needed | n/a (already merged) | yes — proposal v2 |

---

## 5. Reconciliation with gist spirit

Same alignment as v1 (see HARNESS-INTEGRATION v1 §7), with two strengthenings:

| Gist principle | v2 mechanism |
|---|---|
| *"The LLM writes and maintains all of it"* | Stop hook captures continuously; drain-pending evaluates and ingests |
| *"You're in charge of sourcing, exploration, and asking the right questions"* | Operator just works; queue accumulates; drain happens on PreCompact or skill-suggested |
| *"The LLM does all the grunt work — summarising, cross-referencing, filing, bookkeeping"* | Per-turn append + per-compaction summary capture + per-cluster LLM eval |
| *"Good answers can be filed back into the wiki as new pages"* | Drain-pending evaluates per-cluster; worthy clusters become pages |
| *"Shouldn't disappear into chat history"* | Compact_summary capture is the explicit anti-disappearance mechanism |
| *"Compound just like ingested sources do"* | Same `/wiki-ingest` skill, format-claude-history dispatch + new --drain-pending mode |

**Strengthened over v1:**
- v1 captured only on session exit (rare for screen). v2 captures continuously + at every compaction.
- v1 had a fixed turn-count heuristic. v2 has skill-driven LLM evaluation, which is genuinely "the LLM doing the grunt work" rather than "the script doing arithmetic."

---

## 6. Risks and mitigations

| Risk | Severity | Mitigation |
|---|---|---|
| **Stop hook adds latency to every turn** | Low | Python startup + 1 fs append ≈ 5-30ms; invisible to interactive use |
| **Queue file grows unboundedly** | Medium | Drain-pending prunes processed entries. If drain never runs, file grows until disk full. Mitigation: nudge increases urgency as `pending > N`; PreCompact guarantees drain at least every compaction. |
| **PreCompact hook spawn fails silently** | Medium | Logs to `$VAULT/_autosave.log`; operator can `tail -f`. Manual `/wiki-ingest --drain-pending` always available. |
| **LLM evaluation false negatives** (drops worthy content) | Medium-High | Skill's "default to ingest when in doubt" rule; periodic operator review of `_autosave.log`. |
| **LLM evaluation false positives** (ingests noise) | Low | Existing wiki-lint catches orphans/missing-summary on noise pages. Ingest-merge tends to dilute noise into existing pages, not create lasting clutter. |
| **Multiple concurrent drains** (rare race) | Low | Atomic manifest write (already part of v2 ingest skill); two simultaneous drains both succeed, may produce minor double-merge. Acceptable. |
| **`additionalContext` injection annoys operator** | Low | Configurable `FOLD_BACK_NUDGE_EVERY` env var; default 30 prompts means roughly weekly nudge in active use. Set high to silence. |
| **Python not installed** | Very low | Standard on every modern OS; documented as a hard dep. |
| **Hooks fire in non-vault CWD** | Mitigated | `_common.detect_vault()` returns None for non-vault CWD; handlers exit immediately. |
| **`claude -p` flag changes upstream** | Low-Medium | Single subprocess invocation in one helper; easy to update. |
| **Compact_summary captures sensitive content** | Medium | Inherits content-trust boundary; the drain-pending skill applies privacy rules during ingest. Operator can add format-specific redaction in `format-claude-history.md` if needed. |

### Rollback paths

- v1 is at commit `40b7110`; v2 supersedes it. Roll back v2 = restore v1 + retire v2 hooks.
- Each hook handler is independent — disable any one by removing its block from `claude-settings.json` and re-running `kb-contexts-regenerate`.
- Disable all hooks per-vault: set `LINT_SCHEDULE=off` in `.env` (skill respects this).
- Disable all hooks system-wide: remove the `Stop` / `PreCompact` / `PostCompact` / `UserPromptSubmit` blocks from the template; regenerate.

---

## 7. Implementation plan — granular tasks with per-task SVCR

### Phase 0 — verification (read-only, no changes)

| Task | Description | SVCR |
|---|---|---|
| P0.1 | Confirm Python 3.x installed in operator's environment | SV: `python3 --version`. C: which version? Ensure stdlib `pathlib`, `subprocess`, `json` work. R: documented as min Python 3.8. |
| P0.2 | Confirm `setsid` and `timeout` available (used in PreCompact spawn) | SV: `which setsid timeout`. C: macOS doesn't ship `setsid` natively — fallback? R: Linux-only for now; macOS would need `gtimeout` from coreutils. Document. |
| P0.3 | Confirm `claude -p --dangerously-skip-permissions` flag works on operator's CLI | SV: test with simple `/wiki-status` invocation. C: same as v1 P0.1. R: confirmed previously. |
| P0.4 | Verify hook payload structure for Stop / PreCompact / PostCompact / UserPromptSubmit matches docs | SV: install minimal echo-payload hook on a test branch and trigger each. C: any field name drift? R: verify before Phase 2. |

### Phase 1 — revert v1 (kb-system branch: `feat/harness-integration-v2-revert-v1`)

| Task | Description | SVCR |
|---|---|---|
| P1.1 | Revert commit `40b7110` (v1 implementation) | SV: `git show 40b7110 | head` confirms scope. C: any other commit depends on it? `git log --oneline 40b7110..` — none. R: revert. |
| P1.2 | Re-run `kb-contexts-regenerate` to remove sibling -autosave dirs and settings.json symlinks | SV: `ls contexts/` shows only original profiles. C: fork still references settings? No — settings is kb-system-side. R: clean. |
| P1.3 | Commit revert | SV: `git status` clean. C: HARNESS-INTEGRATION-PROPOSAL.md (v1) still on disk? Yes — keep as historical reference. R: commit `revert: HARNESS-INTEGRATION v1 (superseded by v2)`. |

### Phase 2 — Python helpers (kb-system branch: `feat/harness-integration-v2-helpers`)

| Task | Description | SVCR |
|---|---|---|
| P2.1 | Create `scripts/hooks/_common.py` (~40 lines per §3.3) | SV: `python3 -c "import sys; sys.path.insert(0, 'scripts/hooks'); from _common import detect_vault; print(detect_vault('contexts/wiki'))"` returns vault path. C: handles missing .env gracefully? Yes (returns None). R: locked. |
| P2.2 | Create `scripts/hooks/stop_append_to_queue.py` (~50 lines) | SV: pipe a fake JSON payload to it; verify queue file gets one new line. C: re-entrancy guard works? Yes (checks env var). R: locked. |
| P2.3 | Create `scripts/hooks/precompact_schedule_drain.py` (~40 lines) | SV: pipe fake payload; verify subprocess.Popen called (use a stub). C: missing autosave context dir handled? Yes (logs + exits). R: locked. |
| P2.4 | Create `scripts/hooks/postcompact_append_summary.py` (~40 lines) | SV: pipe fake payload with compact_summary; verify queue gets entry. C: empty summary handled? Yes (returns 0). R: locked. |
| P2.5 | Create `scripts/hooks/user_prompt_submit_nudge.py` (~50 lines) | SV: pipe payload 30 times; verify only one nudge emitted. C: queue check works? Yes (counts lines). R: locked. |
| P2.6 | Test scripts pass `python3 -m py_compile` | SV: zero syntax errors. R: locked. |
| P2.7 | Commit Phase 2 | SV: 5 new files + correct mode bits. R: commit `feat(hooks): Python hook handlers for v2 fold-back queue`. |

### Phase 3 — settings template + regenerate (kb-system branch: `feat/harness-integration-v2-settings`)

| Task | Description | SVCR |
|---|---|---|
| P3.1 | Update `scripts/templates/claude-settings.json` per §3.4 | SV: valid JSON. C: paths absolute? Yes. R: locked. |
| P3.2 | Verify `kb-contexts-regenerate` still produces correct dirs (interactive: with settings.json; autosave: without) | SV: dry-run. C: any change needed to script logic? No — template path same. R: locked. |
| P3.3 | Run `kb-contexts-regenerate`; spot-check both vaults | SV: `ls contexts/wiki/.claude/` shows settings.json; `ls contexts/wiki-autosave/.claude/` does not. R: confirmed. |
| P3.4 | Commit Phase 3 | SV: template updated, regenerate unchanged. R: commit `feat(hooks): v2 settings.json template (Stop+PreCompact+PostCompact+UserPromptSubmit)`. |

### Phase 4 — skill refinements (fork branch: `feat/wiki-ingest-drain-pending`)

| Task | Description | SVCR |
|---|---|---|
| P4.1 | Add `## Mode: --drain-pending` section to `.skills/wiki-ingest/SKILL.md` per §3.5.A | SV: skill file syntactically valid (no broken markdown). C: dynamic-assessment language clear? Re-read for ambiguity. R: locked. |
| P4.2 | Add `## Continuous Fold-Back Convention` section to `AGENTS.md` per §3.5.B | SV: AGENTS.md still parses. C: positioned where future agents will see it? Top after intro. R: locked. |
| P4.3 | Extend `.skills/wiki-query/SKILL.md` Step 5b per §3.5.C | SV: skill structure intact. C: queue-append happens after the operator approves Output 2 updates (no silent appends)? Yes — instruct accordingly. R: locked. |
| P4.4 | Commit Phase 4 | SV: 3 files modified. R: commit `feat(wiki-ingest): --drain-pending mode + continuous fold-back convention`. |

### Phase 5 — push + deploy (no new commits)

| Task | Description | SVCR |
|---|---|---|
| P5.1 | Push fork main; push kb-system main | SV: `git push` clean. C: any open PR conflicts? No. R: pushed. |
| P5.2 | Re-run `kb-contexts-regenerate` (deploys v2 settings + skills) | SV: contexts updated. C: stale v1 wrapper script still present? Yes — orphan in /scripts; not referenced. Leave for Phase 6 cleanup. R: confirmed. |
| P5.3 | Operator runs a real screen session for ≥1 day; observes queue accumulation in `$VAULT/.pending-fold-back.jsonl` | SV (operator): file grows. C: any error in `_autosave.log`? Operator checks. R: depends on observation. |
| P5.4 | Operator triggers manual `/compact`; verify PreCompact hook fires + drain runs | SV (operator): autosave context shows new pages or "no worthy clusters" log entry. R: depends on observation. |

### Phase 6 — cleanup (after operator validation, kb-system branch: `feat/harness-integration-v2-cleanup`)

| Task | Description | SVCR |
|---|---|---|
| P6.1 | Delete orphan `scripts/wiki-autosave-on-session-end` (v1 bash wrapper) | SV: nothing references it. C: any docs cite it? Update. R: delete. |
| P6.2 | Delete `docs/HARNESS-INTEGRATION-PROPOSAL.md` (v1) — superseded by v2 | SV: archive instead via rename to `_archives/`? Or delete and rely on git history? R: rename `HARNESS-INTEGRATION-PROPOSAL.md` → `HARNESS-INTEGRATION-PROPOSAL-v1-superseded.md` and add a top-of-file pointer to v2. |
| P6.3 | Re-ingest the v2 proposal into kb-wiki | SV: new pages reflect v2 architecture. C: existing pages updated (concepts/fold-back-loop, synthesis/fold-back-gap-analysis, references/harness-integration-proposal-doc)? Operator decides. R: cycle through ingest. |
| P6.4 | Final commit | SV: `git status` clean. R: commit `chore: retire v1 bash wrapper; supersede v1 proposal doc`. |

---

## 8. Self-validate / critique / refine

### 8.1 Self-validate

**Does v2 address operator's three concerns?**
- ✓ Long-running screen sessions: Stop fires per turn; PreCompact fires on auto-compaction; UserPromptSubmit injects nudges. None require session exit.
- ✓ Python instead of bash: 5 helpers, all Python 3 stdlib only.
- ✓ Dynamic LLM assessment in skill: `--drain-pending` mode does per-cluster eval inside the skill prompt, not in the hook.

**Does v2 honour gist spirit?** §5 maps the same 6 principles as v1, with two strengthenings (continuous capture vs single-shot, LLM eval vs arithmetic).

**Does v2 preserve drift integrity?** Same as v1 (§5 there): conversations are immutable sources, so no source-side drift; lint #4 covers the synthesis-staleness case if it arises.

**Are the hook payloads documented correctly?** Stop, PreCompact, PostCompact, UserPromptSubmit fields all confirmed in §A. Re-verify in Phase 0.

### 8.2 Critique

1. **Python startup overhead per turn.** Every `Stop` fires a Python interpreter cold. ~50ms cold, ~10ms warm. For interactive use this is invisible (a 0.05s pause between assistant finish and user prompt is inside the perception threshold). For programmatic clients (e.g. SDK clients doing 1000s of turns/min) it matters more — but operator's use-case is interactive screen sessions. Acceptable.

2. **Queue grows unboundedly if drain never runs.** PreCompact guarantees a drain when context fills (which always happens in long sessions). Operator can also manually `/wiki-ingest --drain-pending`. UserPromptSubmit nudge surfaces queue size. Three independent drainage paths. Acceptable risk.

3. **Concurrent drain processes if compactions happen fast.** Two PreCompacts fire close together; both spawn drains; both read the same queue; both ingest overlapping content. Mitigation: drain skill should atomically rename `.pending-fold-back.jsonl` → `.pending-fold-back-<pid>.jsonl` at start, then process its own copy. Add to skill prompt.

4. **`additionalContext` from UserPromptSubmit might confuse Claude on Nth turn.** Claude reads "fold-back reminder" as if the user said it. Mitigation: prefix the injected text with `[system reminder]` and frame as guidance, not user request. Already done in §3.3 helper #4 (the nudge starts with `[fold-back reminder]`).

5. **LLM evaluation per cluster might over-ingest.** "Default to ingest when in doubt" creates a risk of bloat. Counter: existing wiki-lint catches orphans + missing-summary on weak pages; provenance markers will skew heavily inferred for marginal pages, surfacing them in lint check #7. Self-correcting.

6. **Compact summary capture might double-count.** If a turn is in the queue AND its compact_summary covers it, both get evaluated. Drain skill clusters by topic, so they merge into one cluster; LLM eval runs once. Not a duplication problem in practice.

7. **macOS portability.** v1's `setsid` is Linux-only. macOS needs different detachment. Mitigation: helper #2 detects `setsid` availability; falls back to `os.setsid()` Python call + `subprocess.Popen(start_new_session=True)`. Already in §3.3 (uses `start_new_session=True` which is portable); the `setsid` shell call should be removed. Refine in Phase 2.

8. **What happens if Claude Code's hook payload format changes upstream?** Helpers parse defensively (`.get(field, default)`). One missing field doesn't crash. Worst case: handler no-ops silently and logs.

9. **Test coverage.** Phase 2 tasks include manual fake-payload tests. No automated tests proposed; for personal-use kb-system this is acceptable. Operator can add pytest if needed later.

10. **The drain skill assesses every cluster with the LLM.** Cost: per drain ≈ K clusters × 1 Haiku eval + ingest of worthy ones. K is small (typically <10 per compaction). ~1-5 cents per drain. Minimal.

### 8.3 Refine — adjustments after §8.2

- **Crit #3 (concurrent drains):** Add explicit "atomic queue handoff" instruction to drain-pending mode in §3.5.A. Drain skill renames queue file at start, processes its private copy. Updated in §3.5.A above.
- **Crit #4 (additionalContext framing):** Confirm `[fold-back reminder]` prefix in §3.3 helper #4 — already done.
- **Crit #7 (macOS portability):** Replace `subprocess.Popen([...setsid timeout...])` with `Popen(args=[claude, ...], start_new_session=True, preexec_fn=os.setsid)` and use Python-level timeout via threading. Refined in §3.3 helper #2 (use `start_new_session=True`). Document Linux-first; macOS as Phase 7 if needed.
- **Crit #10 (drain cost):** Document expected per-drain cost in operator-facing section. Added to §6 risks.

---

## 9. Approval protocol

Reply with one of:

- **"approved v2 full"** — execute Phases 0-6 as described; revert v1's `40b7110`; ship v2 helpers + settings + skill refinements. **[recommended]**
- **"approved v2 minus nudge"** — same as v2 full except do not install the `UserPromptSubmit` nudge handler (no additionalContext injection). Operator relies on PreCompact + manual invocation only. Cleaner semantically; less prompting.
- **"approved v2 hooks-only, defer skill refinements"** — install hooks (capture works); defer the wiki-ingest `--drain-pending` mode + AGENTS.md convention to a follow-up. Operator can manually invoke `/wiki-ingest <queue-path>` for now.
- **"approved revert v1 only"** — revert v1, do not yet install v2; revisit later.
- **"defer"** — leave v1 in place; revisit when there's time.
- **"reject / discuss"** — what to change.

**Recommendation: "approved v2 full".**

Rationale:
1. v1's `SessionEnd` is genuinely broken for the operator's use-case (screen sessions).
2. Python helpers are easier to debug and modify; bash was a v1 expedient.
3. Dynamic LLM assessment in the skill (rather than turn-count in the hook) puts the intelligence where it belongs and removes the need to calibrate a heuristic.
4. PreCompact + PostCompact form a natural fold-back loop tied to context lifecycle, not session lifecycle — perfectly suited to the gist's *"shouldn't disappear into chat history"* framing.
5. Each phase is independently revertable; Phase 5 deployment surfaces real-world issues before Phase 6 cleanup.

---

## A. Appendix — Hook capability findings (full)

Verbatim summary from `claude-code-docs` re-review (long-session focus):

- **`Stop`** fires per-turn. Payload includes `session_id`, `transcript_path`, `cwd`, `last_assistant_message`, `stop_hook_active`. Can return `decision: block` + `reason`. **Cannot inject `additionalContext`** (only `decision`/`reason` fields).
- **`UserPromptSubmit`** fires before each user prompt. Payload includes `prompt`, `session_id`, `transcript_path`, `cwd`. Can return `additionalContext` (10K char cap), `decision: block` + `reason`, or plain stdout (shown to user).
- **`PreCompact`** fires before context compaction (matcher: `manual` or `auto`). Payload includes `transcript_path`, `cwd`, `trigger`, `custom_instructions`. Can block via exit code 2.
- **`PostCompact`** fires after compaction. Payload includes `compact_summary`, `transcript_path`, `cwd`, `trigger`. **No decision control** — observation only.
- **Auto-compaction** fires when context window fills — guaranteed in long sessions.
- **`async: true`** (command type only) lets handler return immediately; output appears next conversation turn. **`asyncRewake: true`** wakes Claude immediately on exit code 2.
- **No throttling/sampling built in** — script self-manages via state file.
- **No vault detection built in** — script reads `cwd/.env`.
- **Python via shebang** is undocumented but works.
- **Hooks cannot directly invoke skills** — must shell out to `claude -p` if they need skill execution.

---

*End of v2 proposal. Awaiting approval.*
