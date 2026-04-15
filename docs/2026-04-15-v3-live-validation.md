# 2026-04-15 — v3 harness-integration live validation

*First-day production use of the HARNESS-INTEGRATION v3 hook system against the kb-wiki vault. Design-time assumptions were validated (or corrected) against real Claude Code behavior. This doc is the evidence trail — what worked, what I misunderstood, what needed fixing, and what the final architecture looks like in actual execution.*

---

## 0. Validation summary

**Architectural thesis validated**: hooks maintain a queue and inject `additionalContext`; the in-session agent does the work. No subprocess spawning. No out-of-band state. No re-entrancy. The v3 subprocess-free design — specifically chosen over v2's `claude -p` spawn pattern after operator flagged that pattern as fragile — held up in live use.

**Two real bugs caught** (and fixed):
1. `stop_append.py` could infinite-loop if a stuck drain kept the queue above threshold. Fix: respect Claude Code's `stop_hook_active` payload field.
2. `LINT_SCHEDULE=off` escape hatch was inert — documented in multiple places but the helper only honored a sentinel file. Fix: `_common.lint_off()` now checks both mechanisms.

**One semantic misunderstanding corrected** (mine): I expected one queue entry per assistant event. Actual behavior: one queue entry per *logical user-prompt-ending response*, not per tool-call sub-event. A 16-minute single-turn ingest produces 1 queue entry, not 100.

**Cosmetic issue noted**: pluralization bug (`"1 entries"`). Deferred per operator decision ("leave it").

---

## 1. Session setup

### 1.1 Fork state pre-validation

Commit `3b4230f` on `nunogt/obsidian-wiki@main`:
- v3 hook architecture shipped (Stop + PostCompact + SessionStart:compact + UserPromptSubmit)
- INGESTION-SIMPLIFICATION v2 shipped (5 skills → 1)
- VFA ranks 2, 2.5, 3 shipped (divergence, auto-lint, two-output)
- Skill count: 12

### 1.2 kb-wiki state pre-validation

```
kb-system/contexts/wiki/.claude/settings.json
  → /mnt/host/shared/git/kb-system/scripts/templates/claude-settings.json
  (v3 template — 4 hooks configured)

kb-wiki/ contained 53 wiki pages (pre-ingest baseline)
```

### 1.3 Validation path

The operator ran:
1. `/wiki-ingest /mnt/host/shared/git/kb-system/docs` — big ingest of the day's proposal documents
2. `/wiki-ingest --drain-pending` — test of the drain-mode rubric
3. `/wiki-lint` — full 8-check audit
4. `/compact` — trigger compaction flow
5. `/wiki-ingest --drain-pending` — second drain (now on a richer queue)

Each step exercised different v3 components.

---

## 2. Observation 1 — Stop hook fires per logical turn, not per tool-call

### 2.1 My incorrect expectation

I assumed `Stop` fires after each assistant event. During the 16-minute ingest, I watched the session's JSONL grow to 112 assistant events and expected 112 queue entries. Instead: **zero**.

My initial panic: *"the hooks aren't firing!"*

### 2.2 The correct semantics

After the ingest completed and the operator ran `/hooks` (Claude Code's built-in hook-introspection command), the report showed **"4 hooks configured"** — registration was fine. The queue file appeared at exactly 10:17:35, matching the turn-ender timestamp, with exactly **1 entry**.

Counting real user prompts in the session's JSONL:

| Metric | Count |
|---|---|
| Real user prompts | 2 (`/wiki-ingest` + `/hooks`) |
| Tool-result sub-events (type: user) | 89 |
| Assistant sub-events (text + tool_use mixed) | 112 |
| **Stop hook firings** | **1** |

`/hooks` is a built-in UI that doesn't fire Stop. So 1 real user prompt ending cleanly → 1 Stop firing → 1 queue entry.

### 2.3 What I learned

Claude Code's `Stop` semantic is "claude finished responding to a user prompt." During a long ingest where claude makes many tool calls, those tool_use → tool_result cycles are all within one "response." Stop fires when the response *truly ends*.

This has implications:

- A session with many short Q&A turns will produce one queue entry per turn (expected)
- A session with one long ingest produces one queue entry covering the whole thing
- The `last_assistant_preview` field (280 chars of the final message) is a lossy seed; the full content is in the transcript referenced by `transcript_path`

### 2.4 Correction propagated

Updated HARNESS-INTEGRATION-PROPOSAL-v3 with D.1 section noting this correction. The architecture docs no longer imply per-event firing.

---

## 3. Observation 2 — Drain rubric correctly rejects "already-covered ground"

### 3.1 Test 1 — drain against a 1-entry queue

The queue held one entry: the ingest's own completion-summary turn ("Ingest complete. 6 new sources processed, 13 pages created..."). Running `/wiki-ingest --drain-pending`:

Agent's verdict: *"not wiki-worthy. The content is the summary of work already written into the wiki (all 13 pages, manifest, index, log updated). Re-ingesting produces redundancy — fits 'already-covered ground' in the rubric."*

Execution:
- Atomic handoff: `.pending-fold-back.jsonl` → `.pending-fold-back-1776248675.jsonl` ✓
- LLM evaluation per cluster: 1 cluster → not-wiki-worthy ✓
- Log entry: `DRAIN_PENDING clusters_evaluated=1 clusters_ingested=0 entries_processed=1` ✓
- Handoff cleanup: `rm` succeeded ✓

**Rubric working as designed.** The reject branch fired correctly. No "default to ingest when in doubt" override, because there was no doubt.

### 3.2 Test 2 — drain against a 3-entry queue (including 19.5KB compact_summary)

After `/compact` and `/wiki-lint`, queue had 3 entries:
1. Prior drain-complete turn
2. 19.5KB `compact_summary` of the entire 16-min ingest session
3. Lint-report turn

All 3 rejected as *"already-covered ground — one topical cluster (ingest+lint+drain session meta); compact_summary + 2 turns all recap work already captured in the preceding INGEST_BATCH and LINT log lines."*

Agent's reasoning held up on inspection: each queue entry was *describing* work whose artifacts (wiki pages, log entries) existed. Re-ingesting would produce redundant descriptions.

### 3.3 Open question from this observation

The 19.5KB compact_summary did contain *process-knowledge* (the validation narrative, debugging paths, realizations) that wasn't on the wiki. Strictly the rubric was defensible — the ARTIFACTS were on wiki — but the meta-narrative wasn't.

This suggests the rubric may be slightly conservative for meta-work sessions. A potential refinement: distinguish "artifact knowledge" from "process/narrative knowledge." Deferred to see whether the pattern reproduces with non-meta work.

---

## 4. Observation 3 — PostCompact + SessionStart:compact flow validated end-to-end

### 4.1 The test

Operator ran `/compact`. Expected:
1. PreCompact fires (we don't have one; skipped)
2. Compaction happens
3. PostCompact hook fires → captures `compact_summary`
4. SessionStart matcher:"compact" hook fires → injects `additionalContext`

### 4.2 What actually happened (trace from JSONL)

```
L268 [system]:     subtype: compact_boundary
L271 [user]:       <command-name>/compact</command-name>
L272 [user]:       <local-command-stdout>Compacted...
L278 [attachment]: invoked_skills — wiki-ingest re-loaded
L280 [attachment]: hook_success — hookName=SessionStart:compact
L281 [attachment]: hook_additional_context — content=[fold-back reminder]...
```

And `_autosave.log`:

```
2026-04-15T10:30:03+0000 [sessionstart_compact] reminder injected (queue=1)
2026-04-15T10:30:03+0000 [postcompact] queued summary (19537 chars) trigger=manual
```

Every step fired as designed. Queue grew from 1 to 2 entries (added `type: "compact_summary"` with 19537 chars of distilled session content).

### 4.3 The exact `additionalContext` Claude received

```
[fold-back reminder] Compaction just completed; the compact_summary
has been queued. Fold-back queue now has 1 entries pending evaluation.
Consider invoking `/wiki-ingest --drain-pending` to evaluate and
integrate wiki-worthy content. See AGENTS.md §Continuous Fold-Back
Convention. Drain at natural breakpoints; not strictly required
this turn.
```

(Note: "1 entries" — pluralization bug, operator opted to leave.)

### 4.4 Agent's self-actualization

Critically, Claude **acted on the injected context without the operator saying anything**. The trace shows the agent proactively read:

```
Read ../../../kb-wiki/.pending-fold-back.jsonl (2 lines)
Read ../../../kb-wiki/log.md (77 lines)
Read ../../../kb-wiki/concepts/post-ingest-auto-lint.md (69 lines)
Read ../../../kb-wiki/concepts/schema-citation-pattern.md (90 lines)
Read ../../../kb-wiki/index.md (97 lines)
```

This was the v3 architecture's core thesis in action: **hooks inject context; the in-session agent acts**. No subprocess drained the queue; the agent saw the reminder and opened the relevant files to orient itself.

### 4.5 Architectural implication

The v3 design's "LLM does the grunt work in-session" claim was the load-bearing thesis. This trace validates it. The `additionalContext` mechanism + AGENTS.md's Continuous Fold-Back Convention + the in-session agent's natural instinct to read relevant files combined to produce exactly the behavior the architecture anticipated.

---

## 5. Observation 4 — lint primitive catches real issues

### 5.1 The lint run

`/wiki-lint` against kb-wiki (now with 66 pages post-ingest):

```
LINT issues_found=69
  orphans=0
  broken_links=2-real + 6-pedagogical-inline-code
  stale=10-real-4-sources-changed
  contradictions=0
  prov_issues=5-frontmatter-overstates-inferred
  missing_summary=43-soft-over-200-chars
  fragmented_clusters=0
  fixed=2-broken-links
```

### 5.2 Pedagogical-context detection working

6 of the "broken wikilinks" were actually `[[wikilinks]]`, `[[wikilink]]`, `[[slug]]` — pedagogical mentions inside inline-code spans in the page bodies. The skill correctly identified them as documentation examples, not real references, and skipped them.

This is non-trivial judgment: naïve regex on `\[\[.*?\]\]` would have flagged all 8. The skill's rubric distinguished "wikilink in prose context" (real) from "wikilink inside code fence" (pedagogical). 2 real broken links auto-fixed; 6 false positives correctly ignored.

### 5.3 SHA-256 delta detection working

10 pages flagged as stale — all referencing 4 source docs whose hashes had changed after ingest (commit `8af78ef`, the proposals-update-with-execution-status edit). The manifest machinery correctly detected the source drift. The lint didn't re-ingest in this run (flagged for the operator's next pass).

### 5.4 Provenance drift check working

5 pages flagged with frontmatter-vs-recomputed drift > 0.20:
- `concepts/compile-not-retrieve`: stated 0.30 inferred, recomputed 0.05
- `concepts/harness-integration-pattern`: stated 0.30, recomputed 0.04
- `concepts/lint-primitive`: stated 0.25, recomputed 0.04
- `synthesis/llm-wiki-ecosystem-2026`: stated 0.25, recomputed 0.03
- `synthesis/multi-vault-architecture`: stated 0.50, recomputed 0.00

Pattern: ingest-time estimates were consistently too high relative to actual marker counts. Either the LLM over-defaults to ~0.30 for "synthesis-heavy" pages, or markers get stripped during subsequent edits. Both scenarios are exactly what this check is meant to catch.

### 5.5 Implications

- **VFA rank 2.5 (post-ingest auto-lint) works** for the subset of checks it runs at ingest time. The "two broken wikilinks caught and fixed" in the earlier ingest's completion message was exactly this mechanism firing.
- **Full wiki-lint adds value beyond the post-ingest subset** — the provenance drift, stale-content, and pedagogical-context distinction all emerge from the richer 8-check audit that doesn't run on every ingest.
- **The "missing_summary=43 soft" finding** is systemic — ~70% of pages have summaries over the 200-char guideline. Not a functional issue; cheap retrieval still works, just uses more tokens per hit. Worth a bulk summary-rewrite pass eventually.

---

## 6. Bugs caught post-deployment

### 6.1 MAJOR — infinite block loop in Stop hook

Source review revealed: if the queue stayed above threshold after a drain attempt, the flow would be:

```
Stop fires → size >= threshold → decision: block, reason: "drain now"
  → Claude continues → agent attempts drain → drain fails or queue still large
    → turn ends → Stop fires → size >= threshold → decision: block
      → Claude continues → ... (infinite loop)
```

Per claude-code-docs `hooks.md` Stop input: `stop_hook_active` is `True` when "Claude Code is already continuing as a result of a stop hook." Without respecting this field, nothing prevents the loop.

**Fix** in commit `fe01292`: `stop_append.py` now checks `stop_hook_active`. If true, suppresses the block (logs the suppression, doesn't re-block). The turn ends; the queue may still be large; operator can manually drain later.

Verified with simulated payload (test R2 in that commit's message).

### 6.2 MAJOR — `LINT_SCHEDULE=off` escape hatch was inert

AGENTS.md, HARNESS-INTEGRATION-PROPOSAL-v3, ACTIVATION-GUIDE all documented two escape hatches for disabling the hooks per-vault:
1. `touch $VAULT/.fold-back-disabled` (sentinel file)
2. `LINT_SCHEDULE=off` in profile `.env`

The `_common.lint_off()` helper only honored #1. #2 was documented but never checked.

**Fix** in commit `fe01292`: extracted `_read_env_var(cwd, var)` helper; `lint_off(cwd, vault)` now checks both. Verified with simulated payload (test R3).

### 6.3 MINOR — dead code + misleading docstring

`_common.lint_off()` had an unused `envfile = pathlib.Path(vault).parent` line and a docstring that referenced `LINT_SCHEDULE=off` in `.env` (the feature that didn't work). Both cleaned up in the same `fe01292` fix.

### 6.4 COSMETIC — pluralization

The injected reminders say "1 entries" when the queue size is 1. Trivial fix; operator decided to leave. Noted here for anyone refreshing the helpers later.

---

## 7. The `/hooks` built-in — a validation gift

### 7.1 What `/hooks` does

Claude Code ships a built-in `/hooks` command (documented at `claude-code-docs/docs/hooks.md:445`):

> Type `/hooks` in Claude Code to open a read-only browser for your configured hooks. The menu shows every hook event with a count of configured hooks, lets you drill into matchers, and shows the full details of each hook handler.

### 7.2 Its role in this validation

When I (incorrectly) panicked that "hooks aren't firing," the operator's `/hooks` command surfaced "4 hooks configured" — definitively resolving the registration question. If `/hooks` had shown 0, we'd have been chasing a different problem.

Every operator working with Claude Code hooks should know about `/hooks`. It's the single best diagnostic.

---

## 8. Drain handoff-file cleanup footgun

Observed bug in two successive drain runs: the agent writes `rm <handoff> && ls .pending-fold-back*` as a self-verification. After `rm` succeeds, the glob matches nothing, bash passes the literal pattern through to `ls`, `ls` fails with exit 2 ("No such file or directory"). Claude Code's Bash tool surfaces this as a red `Error:` in the transcript — benign but alarming.

**Fix** in commit `b1c09c7`: added paragraph to `wiki-ingest/SKILL.md §Mode: --drain-pending` step 7:

> *"Cleanup-verification guidance. rm's exit code is authoritative — if rm exits 0, the file is gone. Do not shell-verify with a glob like ls .pending-fold-back* afterwards: when the glob matches nothing, bash passes the literal unexpanded pattern to ls, which exits 2 with 'No such file or directory.' That's not a real error — just a well-known shell footgun — but it surfaces as a red Error: in the session transcript and looks alarming."*

---

## 9. Final validated state

Every component of HARNESS-INTEGRATION-PROPOSAL-v3 exercised in live use:

| Component | Evidence | Result |
|---|---|---|
| Hook registration from project `.claude/settings.json` symlink | `/hooks` showed 4 configured | ✓ |
| Stop fires per logical user-prompt-ending turn | 1 queue entry per 1 complete turn | ✓ (corrected expectation) |
| PostCompact captures `compact_summary` | 19.5 KB captured with `type: "compact_summary"` | ✓ |
| SessionStart matcher:"compact" injects `additionalContext` | `hook_additional_context` attachment in transcript | ✓ |
| In-session agent acts on reminder | Agent opened queue + log + pages voluntarily | ✓ |
| LLM-driven "wiki-worthy?" rubric | Both drains correctly rejected already-covered content | ✓ |
| Atomic handoff rename | `.pending-fold-back.jsonl` → `.pending-fold-back-<ts>.jsonl` | ✓ |
| `DRAIN_PENDING` log format | byte-for-byte match with spec | ✓ |
| No subprocess spawning | Zero `claude -p` invocations in any trace | ✓ |
| Threshold backstop (Stop decision:block) | Not exercised live (would require 200+ queue entries) | simulated ✓ |
| UserPromptSubmit sampled nudge | Not exercised live (would require 30+ prompts) | simulated ✓ |

All simulated paths verified via payload tests during Phase 2 of the original v3 rollout. Live validation covers the non-simulated paths.

---

## 10. What remains untested

For future real-world exercise:

- **Stop `decision: block` threshold fires** — needs a session accumulating 200+ queue entries without drain
- **UserPromptSubmit sampled nudge** — needs a session with 30+ user prompts AND a non-empty queue
- **Drain's "ingest-worthy" branch** — both drains so far rejected as already-covered. Need a case where meaningful *new* synthesis emerges in queue content that isn't mirrored on the wiki yet.
- **Query-synthesis queue append (wiki-query Step 5c)** — requires a substantive `/wiki-query` invocation
- **Concurrent drains** — unlikely in practice (single operator, single vault) but the atomic-handoff + race-safety was designed for it

None of these are blockers. The core loop works.

---

## 11. Practical observations for operator use

### 11.1 Queue size in practice

For a typical day's work:
- ~5-10 discrete user prompts producing real responses
- Plus occasional compactions (auto-triggered or manual)
- → queue grows ~5-15 entries per day
- 200-entry threshold reached in ~1-2 weeks without manual draining
- Auto-drain from SessionStart:compact reminders means threshold may never actually fire in normal use

### 11.2 What's worth draining

The first-drain experience suggests the rubric is *somewhat* conservative. For meta-work sessions (like today's — which produced wiki pages describing the work itself), the rubric may reject the compact_summary as "already covered" when actually only the artifacts are, not the narrative.

For straight work sessions (no meta-layer) — e.g. a normal Ebury incident investigation — drains will likely ingest more, since the session content won't already be mirrored on pages. TBD once that pattern is observed.

### 11.3 Operator mental model

Practically: the vault is a living Claude Code workspace. You work in it; hooks capture turn markers; periodically (or automatically, on compaction) you drain. The drain is not mandatory — skipping it costs nothing except foregone compounding.

The Continuous Fold-Back Convention lives in AGENTS.md so the in-session agent treats drain-at-breakpoints as a default behavior, not an explicit user ceremony.

---

## 12. Net impact

**Load-bearing architectural claim** of v3 — *hooks inject context, in-session agent acts* — validated end-to-end on 2026-04-15. The subprocess-free design is the production design.

**Operator experience** — one session of dogfooding caught two real bugs, corrected one mental-model error, and surfaced one cosmetic issue. Everything else worked as intended.

**Future confidence** — the v3 hook system is ready for continued real use. Untested paths (threshold backstop, user-prompt nudge, ingest-worthy drain branch) have simulated verification and will surface naturally in extended use.

---

*End of log. HARNESS-INTEGRATION-PROPOSAL-v3 architecture validated in production.*
