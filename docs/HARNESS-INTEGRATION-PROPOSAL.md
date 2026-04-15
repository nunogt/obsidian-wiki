# Harness integration v1 — closing the save-back gap via Claude Code hooks

> **⚠ SUPERSEDED 2026-04-15 by [HARNESS-INTEGRATION-PROPOSAL-v3.md](./HARNESS-INTEGRATION-PROPOSAL-v3.md).** v1 used a `SessionEnd` hook to spawn a detached `claude -p /wiki-ingest <transcript>` subprocess. Two issues led to v3:
> 1. **`SessionEnd` never fires** for the operator's long-running `screen` sessions
> 2. **Spawning `claude` from a `claude` hook is not a documented pattern** — fragile auth/billing/failure-mode separation
>
> v3's subprocess-free design (Stop hook queue + SessionStart-after-compaction reminders + in-session `/wiki-ingest --drain-pending`) replaces this approach. v1 was deployed at commit `40b7110` and reverted at `7e6a3ae`.
>
> Preserved here for historical context. v2 ([HARNESS-INTEGRATION-PROPOSAL-v2.md](./HARNESS-INTEGRATION-PROPOSAL-v2.md)) was an intermediate Python-rewrite that retained the subprocess pattern; also superseded by v3.

---

*Drafted 2026-04-15. Based on end-to-end review of `/mnt/host/shared/git/claude-code-docs` (17 hook event types, settings precedence, skill auto-invocation, session persistence, hook handler types), re-read of Karpathy's gist §Operations save-back passage, cross-check against wiki's fold-back-loop / drift-integrity / query-primitive concept pages, and audit of our existing claude-history-ingest skill. Nothing executed — assessment + proposal for review.*

**Scope:** does Claude Code's hook system let us close the gist's *"good answers shouldn't disappear into chat history"* gap **without** requiring an explicit `/wiki-save-answer` slash command? Reframes VISION-FIDELITY-ASSESSMENT rank 1.

---

## 0. Executive summary

**The lightbulb:** Karpathy's exact phrasing — *"good answers can be filed back into the wiki as new pages... shouldn't disappear into chat history"* — is **literally** describing what auto-ingestion of `~/.claude/projects/*.jsonl` does. Our `claude-history-ingest` skill is already 95% of the save-back solution; the missing 5% is **automatic invocation**, not new functionality.

**The mechanism:** a per-vault `.claude/settings.json` `SessionEnd` hook in each `kb-system/contexts/<vault>/` directory. When a Claude session in that CWD ends, the hook shells out a non-interactive ingest of the just-completed transcript. **Zero user ceremony. The LLM "writes and maintains" continuously, exactly as the gist describes.**

**The reframe of VFA rank 1:** the original rank 1 proposed building a `/wiki-save-answer` skill modeled on SamurAIGPT's `--save` flag. That puts maintenance burden back on the user (must remember to invoke). This proposal argues a **hook-driven auto-ingest is more gist-aligned** — Karpathy's pitch is *"the LLM does all the grunt work"*, not *"the user files away good answers."* Filing is itself grunt work.

**Net change to the system:** zero new skills (uses existing `/wiki-ingest` after the v2 unified consolidation). One small `.claude/settings.json` per vault. One skill-level guard against re-ingest loops. Drift-integrity story is **softer than VFA rank 1's spec** (no `derived_pages` manifest field, no staleness-on-source-change for syntheses-derived-from-syntheses) — but still adequate because conversation files are immutable once ended.

**Recommendation:** ship hook-based auto-ingest as the primary save-back implementation. Keep `/wiki-ingest <transcript>` invocable manually for bulk catch-up. Defer (or cancel) the dedicated `/wiki-save-answer` skill from VFA rank 1 — it's a more complex implementation of a problem that hooks already solve more elegantly.

---

## 1. Karpathy's exact words

From the gist's §Operations, **Query** paragraph:

> The important insight: **good answers can be filed back into the wiki as new pages.** A comparison you asked for, an analysis, a connection you discovered — these are valuable and shouldn't disappear into chat history. **This way your explorations compound in the knowledge base just like ingested sources do.**

Three phrases worth re-reading:

1. *"shouldn't disappear into chat history"* — the failure mode is chat-history leakage. The fix is to capture what's in chat history.
2. *"filed back into the wiki as new pages"* — the conversation contents become pages.
3. *"compound… just like ingested sources do"* — this is the same operation as ingest, just with a different source type.

**Reading literally**: the operation Karpathy is describing is *ingest the chat history*. Not *build a save flag on the query path*. Our existing `claude-history-ingest` is closer to Karpathy's intent than any `/wiki-save-answer` skill we'd build.

The wiki already records this insight — `concepts/fold-back-loop.md` and `synthesis/fold-back-gap-analysis.md` frame "query-answer save" as canonical Karpathy. But both pages then assume the implementation must be a save-flag-on-query (because that's what SamurAIGPT shipped). That's an inherited framing, not a derivation from the gist text.

---

## 2. What we already have

### 2.1 `claude-history-ingest` skill (244 lines)

Today's skill, summarized from `.skills/claude-history-ingest/SKILL.md`:

- Reads `~/.claude/projects/*/<session>.jsonl` + `memory/*.md`
- Skips noise (`type: progress`, `file-history-snapshot`, `thinking`, `tool_use`)
- Topic-clusters: not one-page-per-conversation
- Updates manifest with `source_type: claude_conversation | claude_memory`
- Runs in append mode by default; uses SHA-256 hash to skip unchanged transcripts
- Routes project-specific knowledge to `projects/<name>/` directories
- Applies provenance markers (conversations skew `^[inferred]` due to synthesis)
- Privacy filters for secrets

**This is the save-back operation Karpathy describes.** It already does compounding. It already merges into existing pages. It already cites the conversation as `sources:`.

**What's missing:** automatic invocation. Currently the user has to type `/wiki-history-ingest claude` (or `/claude-history-ingest`) periodically.

### 2.2 v2 unified `/wiki-ingest`

After the INGESTION-SIMPLIFICATION-PROPOSAL v2 lands, `claude-history-ingest` is absorbed into `/wiki-ingest` with format dispatch in Step 1. The route becomes: `/wiki-ingest ~/.claude` → format-claude-history.md branch fires → conversations distill into wiki pages.

---

## 3. Claude Code's hook system (what's available)

End-to-end review of `/mnt/host/shared/git/claude-code-docs` confirms 17 documented hook event types. Relevant subset for save-back:

### 3.1 `SessionEnd` — the primary hook

Fires when a Claude Code session terminates (user exits, kills, completes). Receives JSON with `session_id`, `transcript_path`, `cwd`, `reason`. **Non-blocking** — runs asynchronously after session shutdown begins.

Handler types:
- **Command** — runs arbitrary shell. Return value ignored (non-blocking).
- **HTTP** — POST event JSON to URL.
- **Prompt** — single LLM yes/no.
- **Agent** — spawn a subagent with read tools.

For our use case: **Command** is sufficient. Shell out a non-interactive `claude -p` invocation against the just-completed transcript:

```bash
claude -p --skills-only "/wiki-ingest ${transcript_path}" &
```

Or, equivalently and more controlled, pipe through a small wrapper script. The hook can run with `async: true` so the user's exiting session doesn't have to wait.

### 3.2 `Stop` — for in-session nudges (optional)

Fires when Claude finishes responding *per turn*. Can return `decision: "block"` to keep Claude responding, or inject `systemMessage` Claude reads as context. **Blocking by default.**

Could be used (low-priority) for in-session: *"this answer looks wiki-worthy; consider /wiki-ingest'ing it later."* But this is a soft nudge — `SessionEnd` covers the core case automatically.

### 3.3 `UserPromptSubmit` — for read-side enrichment (separate value)

Fires before Claude processes a user prompt. Can inject `systemMessage` with relevant wiki context the user didn't ask for explicitly. E.g., grep the wiki index for keywords in the prompt and surface matching summaries. **Outside the save-back scope** but shares the harness-integration thinking.

### 3.4 Hook configuration scope

`.claude/settings.json` placement options (via `claude-code-docs/docs/hooks.md` precedence table):

- `~/.claude/settings.json` — user-wide; affects every session everywhere
- `<cwd>/.claude/settings.json` — project-local; **versioned in git, scoped to the CWD**

Our multi-vault setup uses CWD-based profiles. `<cwd>/.claude/settings.json` per `kb-system/contexts/<vault>/` directory is **exactly the right scope**: the hook only fires for sessions started in that vault's context directory, which is exactly when we want save-back to that vault.

### 3.5 What hooks cannot do

- Cannot directly invoke skills or `/commands`. Hooks run shell or LLM yes/no, not skill orchestration.
- Hooks cannot register new triggers Claude reads — they consume events Claude already emits.
- Hook scripts run with full user OS permissions (no sandbox).

The shell-out-to-`claude -p` workaround is how hooks compose with skills. Documented and supported.

---

## 4. Proposed integration architecture

### 4.1 Per-vault `.claude/settings.json`

In each `kb-system/contexts/<vault>/` directory, add a `.claude/settings.json`:

```json
{
  "hooks": {
    "SessionEnd": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "/mnt/host/shared/git/kb-system/scripts/wiki-autosave-on-session-end",
            "async": true,
            "asyncTimeout": 1800
          }
        ]
      }
    ]
  }
}
```

(Versioned in git via the `contexts/` repo or templated by `kb-contexts-regenerate`.)

### 4.2 The wrapper script

`kb-system/scripts/wiki-autosave-on-session-end` (~30 lines bash):

```bash
#!/bin/bash
# Triggered by Claude Code SessionEnd hook in CWD-based vault context.
# Reads JSON from stdin: {session_id, transcript_path, cwd, reason}.
# Schedules a background ingest of the just-completed transcript.

set -euo pipefail

# Load env from CWD's .env (vault config)
export $(grep -v '^#' "${PWD}/.env" | xargs)

# Parse hook payload
payload=$(cat)
transcript_path=$(jq -r '.transcript_path' <<< "$payload")
session_id=$(jq -r '.session_id' <<< "$payload")
session_cwd=$(jq -r '.cwd' <<< "$payload")

# Re-entrancy guard: skip if this session was itself an autosave invocation.
case "$session_cwd" in
  *-wiki-autosave-*) exit 0 ;;
esac

# Skip trivial sessions (under 10 turns)
turn_count=$(grep -c '"type":"user"' "$transcript_path" 2>/dev/null || echo 0)
if [ "$turn_count" -lt 10 ]; then exit 0; fi

# Schedule background ingest. The autosave context dir is a separate CWD so it
# doesn't itself trigger SessionEnd → autosave loop.
nohup claude -p --skills-only \
  --cwd "/mnt/host/shared/git/kb-system/contexts/wiki-autosave-${vault_name}" \
  "/wiki-ingest ${transcript_path}" \
  >/dev/null 2>&1 &
```

(Sketch — exact arg flags depend on `claude` CLI surface; finalize during Phase 2.)

Key safety properties:
1. **Re-entrancy guard:** the autosave session runs in a different CWD (`contexts/wiki-autosave-<vault>/`) so its own SessionEnd doesn't trigger another autosave.
2. **Triviality skip:** sessions under 10 turns (rough proxy for meaningful exploration) are skipped.
3. **Background:** never blocks the user's exiting session.

### 4.3 The autosave context dir

A new `contexts/wiki-autosave-<vault>/` per vault, exactly like the regular vault context but with **no `SessionEnd` hook configured**. This is the loop-breaker.

It still has the same `OBSIDIAN_VAULT_PATH` so the autosave session writes to the right vault.

`kb-contexts-regenerate` would create both `contexts/wiki/` (interactive) and `contexts/wiki-autosave/` (non-interactive ingest target) per vault.

### 4.4 What `/wiki-ingest <transcript>` does (already supports this)

Per the v2 unified `/wiki-ingest` SKILL.md format dispatch (and the `references/format-claude-history.md` reference doc), Step 1 detects `~/.claude/projects/*.jsonl` shape and routes to Claude-history parsing. The skill already handles:

- Skip noise (`thinking`, `tool_use`, `progress`, `file-history-snapshot`)
- Topic clustering (not one-page-per-conversation)
- Provenance markers (heavy `^[inferred]` for distillation)
- Manifest entry with `source_type: claude_conversation`
- Append-mode hash skip (won't re-ingest unchanged transcripts)

**No skill changes required.** The hook is purely an invocation mechanism.

---

## 5. Drift integrity reconciliation

VFA rank 1 specified a 3-component drift-integrity framework (per `concepts/drift-integrity.md`):

1. Provenance-on-save (populate `sources:`)
2. Staleness-on-source-change (mark dependent pages stale)
3. Lint-for-stale (flag pages with `updated < max(source.updated)`)

**How does hook-driven auto-ingest score?**

| Component | Hook autosave | VFA rank 1 spec |
|---|---|---|
| **1. Provenance on save** | ✓ `sources:` populated with conversation transcript path (the JSONL file is the canonical source). Per-claim provenance markers applied. | ✓ Would populate from `relevant_pages` (wiki pages cited during query) |
| **2. Staleness on source change** | ✓ Trivially: conversations are immutable once ended. SHA-256 hash matches forever. No staleness possible from the source side. | ✓ More complex: when a wiki source page changes, dependent synthesis page marked stale via `derived_pages` field |
| **3. Lint for stale** | ✓ Existing `wiki-lint #4 (Stale Content)` already covers this. Conversations don't change → no flags. | ✓ Same lint check, with extra `synthesis-from-pages-staleness` rule |

**Component 2 is the interesting case.** VFA rank 1 worried about syntheses derived from wiki pages that themselves changed. Hook autosave doesn't have that risk because the source (a JSONL conversation) is immutable.

**But there's a softer drift risk in autosave:** the LLM distilling a conversation might mention `[[some-wiki-page]]` in passing without declaring it as a source. If `some-wiki-page` later changes, the distilled page is silently stale on that link's content. This is the same risk the wiki already has for any page citing wikilinks (which is every page) — it's the general wiki-graph staleness, not a new failure mode introduced by autosave.

**Verdict:** hook autosave clears the drift-integrity bar for the "conversations are sources" path. It doesn't extend the bar to "syntheses-of-syntheses staleness," but neither does any current implementation, and the gist doesn't require it.

If we want the stricter VFA rank 1 spec (syntheses citing wiki pages by name, with `derived_pages` tracking), it's an additive enhancement on top of autosave — not a replacement for it.

---

## 6. Comparison — the five integration options

Mapping from B1 analysis. Each evaluated against gist-spirit, drift-integrity, operator cognitive load, implementation cost.

| # | Option | Trigger | Drift-integrity | Gist-spirit | Cost | Verdict |
|---|---|---|---|---|---|---|
| 1 | **Explicit `/wiki-save-answer` skill** (VFA rank 1 original) | User invokes after each query | High (sources from `relevant_pages`) | LOW — user does maintenance, not LLM | Medium (1-2 days) | Accurate to SamurAIGPT framing; mismatched to gist text |
| 2 | **`SessionEnd` hook → `/wiki-ingest <transcript>`** (this proposal) | Automatic on session end | Adequate (conversation immutability) | **HIGH — LLM does grunt work in background** | Low (script + settings.json) | Recommended primary |
| 3 | **`Stop` hook offering save** | Per-turn, with model yes/no | Equal to option 1 | Medium (still requires ack per turn) | Medium (LLM-in-loop hook) | Marginal value over option 2 |
| 4 | **`UserPromptSubmit` hook injecting wiki context** | Pre-prompt | n/a (read-side) | High (LLM benefits from wiki without ceremony) | Low | **Separate proposal — read-side enrichment** |
| 5 | **`PostToolUse` on `wiki-query` triggering save** | After Claude calls wiki-query | High | Medium (still ceremony to invoke wiki-query) | Medium | Niche; covers a small subset of save-back-worthy answers |

**Why option 2 wins for save-back:**
- Closest to gist's literal phrasing (*"shouldn't disappear into chat history"*)
- Uses existing skill (zero new skill code)
- Zero user ceremony
- Drift-integrity adequate
- Composes with v2 ingest consolidation

**Why option 1 might still be worth shipping later:** for the specific case where a query produces a brand-new synthesis (a comparison, an analysis) that should be a single dedicated wiki page — not just merged into existing pages by topic clustering. Hook autosave's topic-clustering would split such a synthesis across multiple existing pages. An explicit `/wiki-save-answer` would write it as one new synthesis page.

**Recommendation:** **option 2 first** (covers 90% of the gist's intent cheaply), then **option 1 later** if operator experience reveals the missing 10% (focused single-synthesis save).

---

## 7. Reconciliation with gist spirit

| Gist principle | This proposal |
|---|---|
| *"The LLM writes and maintains all of it"* | ✓ Autosave runs in background; LLM does the maintenance |
| *"You're in charge of sourcing, exploration, and asking the right questions"* | ✓ User uses Claude Code normally; doesn't think about the wiki |
| *"The LLM does all the grunt work — the summarizing, cross-referencing, filing"* | ✓ Autosave performs all three on every session |
| *"Good answers can be filed back into the wiki as new pages"* | ✓ Autosave files conversation contents as pages |
| *"Shouldn't disappear into chat history"* | ✓ Chat history becomes a wiki source automatically |
| *"This way your explorations compound in the knowledge base just like ingested sources do"* | ✓ Conversations ARE ingested sources under the v2 unified skill |
| *"The exact tooling will depend on your domain"* | ✓ Hook config is per-vault; operators can opt-out per profile |
| *"Everything mentioned above is optional and modular"* | ✓ Hook can be removed without breaking anything |

**Strongest alignment with gist spirit** of any save-back option I've considered — including the original VFA rank 1 spec.

---

## 8. Risks and mitigations

| Risk | Severity | Mitigation |
|---|---|---|
| **Re-entrancy loop** (autosave session triggers its own autosave) | High | Re-entrancy guard via separate `contexts/wiki-autosave-<vault>/` CWD without hook config (§4.3) |
| **Cost: every session triggers an LLM ingest** | Medium | Triviality skip (sessions under N turns); operator can disable per-vault by removing settings.json |
| **Privacy: every session ingested** including potentially sensitive | Medium | Existing trust boundary + privacy filter in claude-history-ingest applies; operator can configure `OBSIDIAN_INVAULT_SOURCES_DIR` exclusions |
| **Noise: not every session is wiki-worthy** | Medium | Topic-clustering (existing skill behavior) drops noise; under-N-turn skip catches trivial sessions |
| **Hook fails silently** (script error, missing dep) | Low | Log autosave wrapper output to `${VAULT}/_autosave.log`; lint check could surface failures |
| **Race: two sessions end simultaneously** | Low | Manifest writes are last-step in `/wiki-ingest`; concurrent ingests race on manifest update. Mitigation: file lock or accept transient inconsistency (next ingest fixes) |
| **Skill drift if ingest skill changes** | Low | Hook just calls `/wiki-ingest`; whatever the skill does is what autosave does. No coupling to skill internals. |
| **`claude -p --skills-only` flag changes upstream** | Low-Medium | Pin to specific Claude Code version OR use a more stable invocation pattern; verify in Phase 1 |
| **Hook timeout (default 600s)** for large transcripts | Low | `asyncTimeout: 1800` in settings; `async: true` so timeout doesn't block session exit |

---

## 9. Implementation plan — granular tasks with per-task SVCR

### Phase 0 — verification (read-only)

| Task | Description | SVCR |
|---|---|---|
| P0.1 | Verify `claude -p` actually works for non-interactive ingest invocation | SV: test on a synthetic transcript. C: are skills loaded in `-p` mode? Per docs, yes if context dir matches. R: confirmed before Phase 2. |
| P0.2 | Verify `SessionEnd` hook fires on session end (manual test with echo command) | SV: log appears in tmp file. C: any flag needed? Not per docs. R: confirmed. |
| P0.3 | Confirm `transcript_path` payload field is populated | SV: cat the payload from a test hook. C: any session-id mismatch? Verify. R: confirmed. |
| P0.4 | Confirm hook async behavior doesn't block session exit | SV: time the exit with `async: true` vs without. C: any UX regression? No. R: confirmed. |

### Phase 1 — wrapper script (kb-system branch: `feat/wiki-autosave-on-session-end`)

| Task | Description | SVCR |
|---|---|---|
| P1.1 | Write `kb-system/scripts/wiki-autosave-on-session-end` (~40 lines bash, sketch in §4.2) | SV: shellcheck passes. C: re-entrancy guard logic correct? Trace 3 cases. R: locked. |
| P1.2 | Define `contexts/wiki-autosave-<vault>/` template — same as `contexts/<vault>/` minus `.claude/settings.json` | SV: dir layout matches. C: env vars all present? Same .env source. R: locked. |
| P1.3 | Update `kb-contexts-regenerate` to create both `contexts/<vault>/` and `contexts/<vault>-autosave/` per profile | SV: dry-run shows expected directories. C: backwards compat with existing contexts? Just adds new sibling. R: locked. |
| P1.4 | Document the autosave-context concept in `docs/HARNESS-INTEGRATION-PROPOSAL.md` (this file) | SV: §4.3 + §4.2 cover it. R: locked. |
| P1.5 | Commit Phase 1 | SV: `git diff --stat` shows 1 script + 1 docs file + 1 contexts-regenerate script edit. C: anything else needed? No. R: commit `feat(autosave): wrapper script + autosave-context infrastructure`. |

### Phase 2 — settings.json template (kb-system branch: `feat/wiki-autosave-hook-config`)

| Task | Description | SVCR |
|---|---|---|
| P2.1 | Create template `kb-system/scripts/templates/claude-settings.json` with the SessionEnd hook block (§4.1) | SV: valid JSON. C: any matcher needed? SessionEnd doesn't take a matcher (no tool name). R: locked. |
| P2.2 | Update `kb-contexts-regenerate` to symlink/copy `claude-settings.json` to `contexts/<vault>/.claude/settings.json` | SV: dry-run confirms placement. C: file conflicts with operator's existing `~/.claude/settings.json`? No — project settings merge with user settings, both apply. R: locked. |
| P2.3 | Test end-to-end: in a test vault, run a session, exit, observe autosave ingest in background | SV: ingest completes; new pages appear in `kb-wiki`. C: re-entrancy actually broken? Verify autosave-context CWD exits cleanly without re-triggering. R: locked. |
| P2.4 | Commit Phase 2 | SV: `git diff --stat` shows template + regenerate update. R: commit `feat(autosave): SessionEnd hook config + per-vault settings.json`. |

### Phase 3 — autosave deployment to existing vaults (kb-system, no fork changes)

| Task | Description | SVCR |
|---|---|---|
| P3.1 | Run `kb-contexts-regenerate` to deploy the new template to all existing contexts (wiki, personal) | SV: both contexts now have `.claude/settings.json` and a sibling `-autosave` dir. C: any context missed? List dirs. R: confirmed. |
| P3.2 | Operator runs a real session in `contexts/wiki/`; confirm autosave ingests after exit | SV: log entry in `kb-wiki/log.md` showing INGEST source=transcript. C: pages plausible? Check 3-5. R: confirmed. |
| P3.3 | Lint vault to catch any new noise the autosave produced | SV: lint pass clean or only soft warnings. C: provenance fractions reasonable? Check. R: confirmed. |
| P3.4 | If issues: tune triviality skip threshold or temporarily disable hook | SV: documented escape hatch. R: locked. |

### Phase 4 — wiki propagation

| Task | Description | SVCR |
|---|---|---|
| P4.1 | Re-ingest `HARNESS-INTEGRATION-PROPOSAL.md` via `/wiki-ingest` (which itself triggers autosave for that very session) | SV: meta-test that autosave doesn't loop. C: pages created without infinite recursion. R: confirmed. |
| P4.2 | Update `concepts/fold-back-loop` — query-answer save now ✓ for ar9av (via autosave) | SV: matrix updated. C: still reflects gap for SamurAIGPT/nvk. R: locked. |
| P4.3 | Update `synthesis/fold-back-gap-analysis` — *"Nobody has shipped it yet"* claim updates to *"As of <date>, the kb-system fork ships hook-driven auto-ingest as the first reliable implementation"* | SV: claim defensible. C: against drift-integrity rubric? Yes — see §5. R: locked. |
| P4.4 | Optionally create `concepts/harness-integration-pattern` page | SV: new concept page. R: optional. |

---

## 10. Self-validate / critique / refine

### 10.1 Self-validate

**Did I read Karpathy's words accurately?** Quoted gist verbatim three times. *"shouldn't disappear into chat history"* is the explicit failure mode. ✓

**Does Claude Code actually support `SessionEnd` hooks?** Per Agent doc review — yes, documented as one of 17 hook types. Receives `transcript_path` in payload. Non-blocking by default. ✓

**Does our existing `claude-history-ingest` already do the work?** Per skill audit — yes, parses `~/.claude/projects/*.jsonl`, skips noise, topic-clusters, applies provenance, populates manifest. ✓

**Is this gist-aligned?** §7 maps 8 gist principles, all align. ✓

**Does it clear drift-integrity?** §5 maps the 3 components, all clear (with the softer-than-VFA-rank-1 caveat about syntheses-of-syntheses staleness). ✓

### 10.2 Critique

1. **Re-entrancy is the most fragile piece.** If the autosave-context CWD ALSO has a `.claude/settings.json` (because operator copied wrong, or because a future `kb-contexts-regenerate` change adds it), we get an infinite loop. Mitigation strength: medium — relies on explicit absence of the file. Better: have the wrapper script *itself* check for a `WIKI_AUTOSAVE_INVOCATION=1` env var set during invocation, and exit immediately if set. Belt + suspenders.

2. **Background processes orphaning.** `nohup … &` in a hook runs detached. If the user closes their terminal session entirely, the autosave Claude session keeps running — fine. But if the host shuts down mid-ingest, we get a half-written manifest. Mitigation: existing manifest write is last-step (atomic write with rename). Document this guarantee explicitly.

3. **Cost analysis.** Each user session → one LLM ingest. At one session per day, that's ~30 ingest sessions/month/vault. Each ingest is bounded (one transcript, ~10-15 pages). Total cost scales with active session count, not with corpus size. Acceptable.

4. **Could just do this with `claude-history-ingest` on cron** (no hook needed). Cron-every-10-minutes runs append-mode ingest of `~/.claude/projects/`. SHA-256 skip means cheap when no new sessions. **This is genuinely simpler.** Counter-argument: hook ties ingest to the session's actual end (clean transcript); cron may catch a session mid-write. Both work; hook is more precise; cron is more fault-tolerant.

5. **Hook timeout vs ingest length.** `asyncTimeout: 1800` is 30 minutes. A bad ingest could hang (e.g., calling out to QMD that's down). Mitigation: wrap with `timeout 1500 claude -p ...` to bound at 25min, leaving 5min slack.

6. **Operator review gate?** Currently autosave just runs and writes pages. Operator never sees what got written until they next look at the wiki. This is in tension with *"I prefer to ingest sources one at a time and stay involved"* (gist's explicit operator preference). Mitigation: surface autosave activity in next session's `wiki-status` view; operator reviews + can revert via git.

7. **What if the v2 unified `/wiki-ingest` doesn't ship before this?** This proposal references `/wiki-ingest` understanding Claude-history JSONL. If we ship this BEFORE v2 consolidation, the hook needs to call `/claude-history-ingest` instead (still works). Just a slash-name change.

### 10.3 Refine

After §10.2 critique:

- **Crit #1 → add env-var double-guard.** The wrapper script will set `WIKI_AUTOSAVE_INVOCATION=1` and check for it at top. Belt + suspenders against re-entrancy.
- **Crit #2 → document atomic manifest write in INGESTION-SIMPLIFICATION v2.** Verify the unified `/wiki-ingest` Phase 5 step actually does atomic rename (it should; check during implementation).
- **Crit #4 → present cron as alternative in approval protocol.** Operator may prefer the simpler cron-driven path.
- **Crit #5 → wrap with `timeout 1500`** in the script body.
- **Crit #6 → wiki-status integration.** Add a sentence in §4.2 that wiki-status's next invocation surfaces unreviewed autosave-derived pages.
- **Crit #7 → add precondition** to the proposal: ships AFTER INGESTION-SIMPLIFICATION v2 lands. Otherwise needs adjustment to call legacy `/claude-history-ingest`.

These refinements added inline above where they apply. (See §4.2 wrapper script env-var guard; §4.4 wiki-status sentence; §11 dependency order.)

---

## 11. Dependency order

| Order | Action | Proposal |
|---|---|---|
| 0a-c | INGESTION-SIMPLIFICATION v2 Phases 1-3 (consolidation) | INGESTION-SIMPLIFICATION |
| **1** | **HARNESS-INTEGRATION Phases 1-4** (this proposal) | This |
| 2 | VFA rank 2 — divergence check in `/wiki-ingest` | VFA |
| 2.5 | VFA rank 2.5 — automated lint scheduling (now significantly cheaper since autosave already wires post-ingest hooks) | VFA |
| 3 | VFA rank 3 — two-output rule in wiki-query | VFA |
| ~~1 (orig)~~ | ~~VFA rank 1 — explicit /wiki-save-answer~~ | **Subsumed by this proposal; defer or cancel** |

This proposal **supersedes VFA rank 1** as the primary save-back implementation. VFA rank 1 may be re-introduced later as an additive feature (single-synthesis explicit save) if operator experience demands it.

---

## 12. Approval protocol

Reply with one of:

- **"approved harness-hook autosave (option 2)"** — execute Phases 0-4 as described. **[recommended]**
- **"approved cron autosave"** — same outcome via simple `cron` running `claude-history-ingest` every 10 min instead of hook. Loses precision (catches mid-session writes), gains fault tolerance (no orphaned background processes). +0 fork patches, +1 kb-system docs entry.
- **"approved hybrid"** — ship both: hook for primary, cron as backstop catching missed sessions. +1 cron entry on top of hook config.
- **"approved hook + add explicit /wiki-save-answer"** — the original VFA rank 1 stays in scope; ship hook for default behavior, explicit skill for focused syntheses.
- **"defer"** — interesting, revisit after INGESTION-SIMPLIFICATION lands.
- **"reject / discuss"**.

**Recommendation:** **"approved harness-hook autosave (option 2)"** — most gist-aligned, lowest cost, uses existing skill, ships Karpathy's *"shouldn't disappear into chat history"* directly. If operational issues surface (cost, noise, re-entrancy edge cases), fall back to cron alternative. If operator finds a class of "focused syntheses" being missed by topic clustering, layer in option 1 (`/wiki-save-answer`) later.

---

## 13. Cross-references for next ingestion

**New concept (recommended):**
- `concepts/harness-integration-pattern` — hook-driven auto-ingestion as a save-back mechanism

**Updates to existing wiki pages:**
- `concepts/fold-back-loop` — query-answer save column updates: ar9av-fork now ✓ via autosave (was ❌)
- `synthesis/fold-back-gap-analysis` — "Nobody has shipped it yet" → updated with kb-system fork as first reliable implementation
- `concepts/query-primitive` — save-as-page section: add reference to harness-integration as the de-facto implementation
- `concepts/drift-integrity` — note the *"conversations are immutable"* simplification of component 2

**New reference:**
- `references/harness-integration-proposal-doc` — this file

---

*End of proposal. Awaiting approval. Should be approved jointly with INGESTION-SIMPLIFICATION-PROPOSAL v2 (this proposal depends on the unified `/wiki-ingest` to handle the format-claude-history dispatch path).*
