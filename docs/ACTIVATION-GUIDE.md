# Activation guide — v3 harness integration + consolidated ingest

*Written 2026-04-15, post-validation. Companion to the four design proposals in this directory.*

Short answer to the question *"should I nuke kb-system?"* — **no.** Everything is already on disk. The remaining step is just a session restart so Claude Code picks up the new `settings.json`.

---

## 1. What's on disk right now (nothing to do)

| Location | State | Source |
|---|---|---|
| `kb-system/scripts/hooks/` (5 Python files) | ✅ committed + pushed | v3 Phase 2 (`b1d5a61`) + validation fixes (`fe01292`) |
| `kb-system/scripts/templates/claude-settings.json` | ✅ committed + pushed | v3 Phase 3 (`3d92b9c`) |
| `kb-system/scripts/kb-contexts-regenerate` (updated) | ✅ committed + pushed | v3 Phase 3 (`3d92b9c`) |
| `kb-system/contexts/wiki/.claude/settings.json` (symlink) | ✅ in place | run of `kb-contexts-regenerate` |
| `kb-system/contexts/personal/.claude/settings.json` (symlink) | ✅ in place | run of `kb-contexts-regenerate` |
| Fork: `AGENTS.md §Continuous Fold-Back Convention` | ✅ committed + pushed | v3 Phase 4 (`902cdf0`) |
| Fork: `wiki-ingest/SKILL.md §Mode: --drain-pending` | ✅ committed + pushed | v3 Phase 4 (`902cdf0`) |
| Fork: `wiki-query/SKILL.md Step 5c` | ✅ committed + pushed | v3 Phase 4 (`902cdf0`) |
| Fork: consolidated `/wiki-ingest` (5→1 skills) | ✅ committed + pushed | INGESTION-SIMPLIFICATION (`932dbd8`, `ef42a4b`, `1c276ea`) |
| Fork: VFA ranks 2, 2.5, 3 (divergence, auto-lint, two-output) | ✅ committed + pushed | VFA (`35f8abd`, `cf9c4c3`, `3b4230f`) |

**No nuke. No regeneration. No migration scripts.** The filesystem already reflects the target state.

---

## 2. Why a session restart is still needed

Claude Code reads `settings.json` at session start. The current session (the one you're reading this in, if you're in `contexts/wiki/`) was initiated **before** the v3 hooks existed — so the hooks aren't registered for this session's event loop.

`claude-code-docs` mentions a `ConfigChange` hook that fires on settings file changes during a session, which *suggests* settings may reload mid-session. But this isn't documented as guaranteed behavior for hook registration itself (vs. hooks that modify agent context), and no operator-facing docs instruct agents to rely on it. **Safest to assume: restart required.**

---

## 3. Activation procedure (recommended)

### Step 1 — exit this session

`Ctrl+D` or `/exit` from inside Claude Code. If in `screen`, leave the screen session intact.

### Step 2 — start a fresh session in `contexts/wiki/`

```bash
cd /mnt/host/shared/git/kb-system/contexts/wiki
claude --dangerously-skip-permissions
```

(Or with the fast-mode toggle; any invocation works.)

Behind the scenes, the new session:
- Reads `.env` from CWD → resolves `OBSIDIAN_VAULT_PATH=/mnt/host/shared/git/kb-wiki`
- Reads `.claude/settings.json` (symlink → `scripts/templates/claude-settings.json`) → registers 4 hooks
- Loads `AGENTS.md` (symlink → fork) → includes `§Continuous Fold-Back Convention` in system prompt
- Loads `.claude/skills/*` (symlinks → fork) → new `wiki-ingest` + `wiki-query` available

### Step 3 — validate hooks are live

In another terminal:

```bash
tail -F /mnt/host/shared/git/kb-wiki/_autosave.log
```

In the Claude Code session, run any command (e.g. `ls`). After the assistant finishes the turn, you should see a `[stop_append]` entry (or nothing if queue size < threshold and no error). Anything in the log confirms hooks fire.

Also:

```bash
wc -l /mnt/host/shared/git/kb-wiki/.pending-fold-back.jsonl
# Should show a small number (grows by 1 per turn)
```

### Step 4 — exercise the fold-back convention

Work on anything — research, planning, analysis. At a natural breakpoint, either:
- Wait for the agent to proactively suggest `/wiki-ingest --drain-pending` (per AGENTS.md convention)
- Or invoke it manually: type `/wiki-ingest --drain-pending`

Expected: the skill reads `.pending-fold-back.jsonl`, atomically renames it to a handoff file, clusters queue entries by topic, LLM-evaluates each cluster for wiki-worthiness, and ingests worthy clusters into the wiki. Log line in `kb-wiki/log.md`:

```
- [TIMESTAMP] DRAIN_PENDING clusters_evaluated=N clusters_ingested=M entries_processed=K
```

### Step 5 — (optional) trigger a compaction manually

```
/compact
```

Expected: `[postcompact]` entry in `_autosave.log` (compact_summary captured), then `[sessionstart_compact]` entry (reminder injected into agent context for next turn). Next turn the agent should consider draining.

### Step 6 — (optional) trigger the threshold backstop

Let queue grow past 200 (the default `FOLD_BACK_BLOCK_THRESHOLD`). Next Stop will block with a `decision: block + reason`. Agent is forced to continue, sees the reason, drains inline. After drain, queue is 0, next Stop clears normally. Loop guard (`stop_hook_active`) prevents infinite blocks.

---

## 4. kb-wiki as testbed — dogfooding the system

The kb-wiki vault holds our own LLM-wiki research + kb-system architecture docs. Using v3 on kb-wiki is **the perfect testbed** because:

1. Every session working on kb-system/kb-wiki itself produces wiki-worthy content (meta-system work = the exact use case we built this for)
2. The vault already has 53 wiki pages, so ingest-merge has plenty of targets to strengthen
3. Karpathy's quote fits: *"The wiki is the codebase; the LLM is the programmer; Obsidian is the IDE"* — and the system now maintains itself continuously

**Suggested first real run:** exit + restart, then re-ingest the three proposal docs and this activation guide via `/wiki-ingest` on the `docs/` dir. The hooks will also capture the ingest conversation in the queue. Before ending the session, drain to complete the loop.

---

## 5. Escape hatches (if things go wrong)

Disable fold-back in one vault:
```bash
touch /mnt/host/shared/git/kb-wiki/.fold-back-disabled
```

Disable via profile env:
```bash
# Append to kb-system/profiles/wiki.env:
LINT_SCHEDULE=off
```

Disable all hooks for a context:
```bash
rm kb-system/contexts/wiki/.claude/settings.json
# Note: next kb-contexts-regenerate will restore it. To persist, remove
# the symlink line from kb-contexts-regenerate, or move the template aside.
```

Raise the threshold-block ceiling (never force draining):
```bash
# Append to profile .env:
FOLD_BACK_BLOCK_THRESHOLD=999999
```

Quiet the nudge rate:
```bash
# Append to profile .env:
FOLD_BACK_NUDGE_EVERY=500
```

Rollback completely to pre-v3 state:
```bash
cd kb-system && git revert fe01292 3d92b9c b1d5a61 9953bc2
# Then run kb-contexts-regenerate to refresh symlinks
```

---

## 6. What I'd watch in the first week

- `_autosave.log` growth rate — should be roughly proportional to active sessions
- Queue file staying under ~200 entries most of the time (drain-pending happening naturally)
- `log.md` entries showing `DRAIN_PENDING clusters_ingested=<N>` with reasonable N (1-5 per drain)
- Wiki pages touched by drains feel right (check `kb-wiki/index.md` — new or updated entries should look connected to recent work)
- Zero loop-events in log (no `[stop_append] threshold-block suppressed (stop_hook_active=true)` lines, or very rare)
- No `[ERROR]` or `error:` lines in `_autosave.log`

If any of these go wrong, review the proposal's §10 Risks section.

---

## 7. Live validation evidence (2026-04-15, kb-wiki testbed)

All v3 architecture proven in a real session. See `HARNESS-INTEGRATION-PROPOSAL-v3.md §D` for full evidence. Headlines:

| Layer | Verified by | Result |
|---|---|---|
| Hook registration (`/hooks` introspection) | Built-in Claude Code command | 4 hooks configured, loaded from `contexts/wiki/.claude/settings.json` symlink |
| `Stop` hook capturing turns | `.pending-fold-back.jsonl` entry after turn-end | 1 entry per user-prompt-ending response (not per tool-call sub-event) |
| `PostCompact` hook | Queue got `type: "compact_summary"` entry after `/compact` | 19.5 KB model-distilled summary captured |
| `SessionStart matcher:"compact"` context injection | `attachment.type = "hook_additional_context"` in transcript | Reminder text delivered to agent |
| In-session agent reacting to reminder | Agent read queue + log + changed pages voluntarily | Fold-back convention self-actualizing |
| Drain rubric applied correctly | `DRAIN_PENDING clusters_ingested=0` when queue held already-covered content | Rubric rejects redundancy defensibly |
| Atomic handoff rename | `.pending-fold-back.jsonl` → `.pending-fold-back-<ts>.jsonl` | Concurrent-drain safety works |

**Thesis proven**: hooks inject context, in-session agent acts. No subprocesses. No out-of-band state.

**Known cosmetic issues**:
- *"1 entries"* instead of *"1 entry"* in nudge text (pluralization)

**Untested paths** (simulated-only, but logic validated in Phase 2 smoke tests):
- Stop `decision: block` at 200-entry threshold
- `UserPromptSubmit` nudge at 30-prompt sample rate

---

*End of activation guide.*
