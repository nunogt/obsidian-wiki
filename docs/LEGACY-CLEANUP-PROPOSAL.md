# Legacy-cleanup + script-consolidation proposal

*Drafted 2026-04-15. Deep assessment against current fork state + all 16 skills
+ 3 kb-system scripts. Nothing executed. Builds on the completed
FORK-MIGRATION-PROPOSAL (end-to-end proven via the kb-personal recreation test).*

---

## 0. Operator decisions — locked execution scope

*(This section will be filled in after operator approval. Until then, sections
1-11 describe the full deliberation space.)*

---

## 1. What this proposal addresses

Two related goals, both now achievable because the multi-vault architecture
has been proven end-to-end (kb-personal bootstrap test passed cleanly):

1. **Remove legacy footguns from the fork** — files and code paths that,
   if ever executed, would re-introduce the single-vault / shared-global-state
   assumptions our architecture is specifically designed to avoid.
2. **Consolidate helper scripts** — move operational logic into skills where
   possible, keeping only the scripts that must run outside a Claude session
   (bootstrap concerns).

Original requirements preserved across both changes:
- CWD-based profiles → concurrent sessions on different vaults
- Per-vault sources (`$VAULT/_sources/` with `OBSIDIAN_INVAULT_SOURCES_DIR`)
- Fork with surgical patches rebased on upstream pulls
- One-shot vault creation (`kb-vault-new`)
- Safe reproduction on a new machine

---

## 2. Deep assessment

### 2.1 What legacy footguns remain in the fork

Read end-to-end of `setup.sh` (179 lines), all 16 `.skills/*/SKILL.md`,
`AGENTS.md`, `README.md`, `SETUP.md`, `.env.example`.

#### `setup.sh` — four steps, three are harmful under our architecture

| Step | What it does | Impact on our architecture |
|---|---|---|
| Step 1 (lines 77-83) | Create `.env` from `.env.example` if missing | **Pointless** — we don't use fork-internal `.env`; we use `kb-system/profiles/*.env`. Harmless but advertises a pattern we don't follow. |
| Step 1b (lines 85-115) | Write `~/.obsidian-wiki/config` unconditionally | **CRITICAL footgun** — re-introduces the single shared global config state that CWD-based profiles specifically replace |
| Step 2 (lines 117-127) | Symlink in-repo agent dirs (`.claude/skills/`, `.cursor/skills/`, `.agents/skills/`, `.windsurf/skills/`) with relative paths | **Redundant** — Patch A committed these as relative symlinks to the fork's `main`. A fresh clone already has them. |
| Step 3 (lines 129-143) | Install `~/.claude/skills/wiki-update`, `wiki-query` | **CRITICAL footgun** — global skills route ALL Claude sessions on the machine to whichever vault the global config points at, breaking concurrent sessions |
| Steps 3b-3d (lines 148-150) | Install all skills globally into `~/.gemini/antigravity/skills/`, `~/.codex/skills/`, `~/.agents/skills/` | **Harmful** — propagates the same global-routing problem to every supported agent; creates broken symlinks if paths ever change |
| Step 4 (lines 155-178) | Print summary advertising `/wiki-update` and `/wiki-query` as primary onboarding | **Misleading** — directs users toward the single-vault model we've architecturally moved past |

**Conclusion:** 3 of the 4 functional jobs are harmful; the 4th (Step 2) is
redundant with what Patch A already committed. Nothing in setup.sh adds value
under our architecture.

#### Skills with single-vault-preferred config ordering

Three skills read `~/.obsidian-wiki/config` (global state); the other 13 read
only `.env` (local/CWD).

| Skill | Line | Current ordering | Problem |
|---|---|---|---|
| `wiki-ingest/SKILL.md` | :18 | Global preferred, `.env` fallback | If stale global config exists, silently overrides CWD routing |
| `wiki-query/SKILL.md` | :18 | Global preferred, `.env` fallback (conditional on "inside obsidian-wiki repo") | Same |
| `wiki-update/SKILL.md` | :16-19 | Global only, **no fallback**; errors "run setup.sh" if missing | Dead under our architecture; couldn't be saved without reintroducing global config |

Under current architecture, `~/.obsidian-wiki/config` doesn't exist, so
wiki-ingest and wiki-query fall through to `.env` (works). The footgun is
**combinatorial**: if anyone ever re-creates `~/.obsidian-wiki/config` (e.g.
by running `setup.sh`, the thing we want to delete), these skills silently
hijack routing.

**Defensive fix:** invert ordering to CWD-first. Belt-and-suspenders with
setup.sh removal.

#### `wiki-update` skill — fundamentally incompatible

Beyond the ordering issue, `wiki-update` reads global config with no fallback
and errors out telling users to run `setup.sh`. We've documented this skill
as dead in [[wiki-update-deprecation]] — the skill was designed for
single-vault ("from any project, sync into the wiki") and doesn't fit
multi-vault semantics. Retaining it in the fork:

- Ships a broken entry point — invoking `/wiki-update` produces a confusing
  error that tells users to re-introduce the global config
- Bloats every context's `.claude/skills/` with a dead symlink
- Encourages users to try to "fix it" by running `setup.sh`, undoing the
  architecture

**Clean fix:** delete `.skills/wiki-update/` from the fork. `kb-contexts-regenerate`
no longer symlinks it into contexts (it iterates over whatever's in `.skills/*/`).

### 2.2 What helper scripts are candidates for migration to skills

Three kb-system scripts total (325 lines combined). Evaluated each against
bootstrap vs runtime constraints.

| Script | Lines | Timing | Migrate? | Why / why not |
|---|---|---|---|---|
| `kb-contexts-regenerate` | 80 | Bootstrap (runs **before** any Claude context exists) | **No** | True bootstrap primitive — a skill would need an existing context to run in, which is exactly what this creates. Chicken-and-egg. |
| `kb-vault-new` | 137 | Bootstrap-adjacent (creates profile + local + remote + calls regen) | **No** (keep for now) | Can *technically* run as a skill from any existing context, but the bootstrap-friendly property (works even when no contexts exist yet, given at least one manually-written profile) is valuable. Low migration benefit. |
| `wiki-ar9av-update` | 108 | Runtime (contexts already exist; maintains the fork) | **Yes** | Pure runtime operation; no bootstrap constraint. Claude can do all git/Bash operations inside a skill. Benefits: version-tracked in fork, interactive commit-preview, architectural consistency with rest of ecosystem. |

**Net script reduction:** 325 → 217 lines (save ~108 by migrating
wiki-ar9av-update). Not a dramatic size win, but conceptually
cleaner — the kb-system scripts become exactly the bootstrap primitives and
nothing else; everything else is a skill in the fork.

### 2.3 Reference hunt — what gets touched by cleanup

Enumerated for impact assessment:

**Fork (`obsidian-wiki/`):**
- `setup.sh` — gut or delete
- `.skills/wiki-update/` — delete the directory
- `.skills/wiki-ingest/SKILL.md:18` — flip config ordering
- `.skills/wiki-query/SKILL.md:18` — flip config ordering (+ drop the "inside obsidian-wiki repo" conditional)
- `.skills/wiki-ar9av-update/SKILL.md` — new; migrated from kb-system script
- `README.md` — 10+ references to setup.sh + global-skills onboarding; substantial rewrite
- `AGENTS.md:62` — mentions "Two global skills handle this" — needs update (single-source-of-truth file symlinked as CLAUDE.md, GEMINI.md)

**kb-system/:**
- `scripts/wiki-ar9av-update` — delete (migrated to fork skill)
- `README.md:119` — update the "Upstream maintenance" snippet to describe the skill invocation
- `docs/` historical proposals (BOOTSTRAP-LOG, REFACTOR-LOG, FORK-MIGRATION-PROPOSAL) — leave alone (historical record)

**kb-wiki (operational pages that may need touch):**
- `skills/wiki-ar9av-update.md` — update to describe skill-not-script
- `skills/using-ar9av-self-hosted.md` — upstream maintenance section
- Historical reference pages — leave alone

---

## 3. Target end-state

```
/mnt/host/shared/git/
├── obsidian-wiki/              (our fork)
│   ├── setup.sh                ← REMOVED (or stub with deprecation notice)
│   ├── .skills/
│   │   ├── wiki-update/        ← REMOVED (dead under our architecture)
│   │   ├── wiki-ingest/SKILL.md    ← Patch F: CWD-first config ordering
│   │   ├── wiki-query/SKILL.md     ← Patch F: CWD-first config ordering
│   │   ├── wiki-ar9av-update/SKILL.md  ← NEW: migrated from kb-system script
│   │   └── ... (other skills unchanged)
│   ├── README.md               ← rewritten: no setup.sh narrative; describes fork deployment
│   └── AGENTS.md               ← tweaked: drop "global skills" language
├── kb-system/
│   ├── scripts/
│   │   ├── kb-vault-new              ← kept (bootstrap-friendly)
│   │   ├── kb-contexts-regenerate    ← kept (true bootstrap)
│   │   ├── wiki-ar9av-update         ← REMOVED
│   │   └── templates/
│   ├── profiles/
│   ├── contexts/
│   ├── docs/
│   └── README.md               ← updated: upstream maintenance section points at `/wiki-ar9av-update` skill
├── kb-wiki/
└── kb-personal/
```

Plus operator cleanup of machine-local vestigial state (broken pre-flatten
symlinks in `~/.gemini/antigravity/skills/`, `~/.codex/skills/`, `~/.agents/skills/`).

---

## 4. The four patches

Layered on top of the fork's current `main` (which already carries Patches A,
C, and the wiki-ingest consistency fix).

### Patch D — Retire `setup.sh`

**Goal:** eliminate the primary path by which harmful global state
(`~/.obsidian-wiki/config`, global skill installs) gets re-introduced.

**Option D1 — Delete `setup.sh` entirely.**
- Cleanest; no file to accidentally run
- Update `README.md` to remove all setup.sh references; describe multi-vault
  deployment via kb-system instead

**Option D2 — Gut setup.sh to a deprecation notice.**
- File still exists; running it prints an informational message and exits
  non-zero so automation doesn't silently accept it
- Preserves the path for anyone with scripts referencing `bash setup.sh`

**Recommendation: D1 (delete).** The fork is ours; the file's only residual
value is "compatibility with the old onboarding flow," which we've specifically
moved past. Deletion is surgical and unambiguous.

### Patch E — Remove `wiki-update` skill

**Goal:** stop shipping a broken entry point that tempts users to re-introduce
global config.

**Action:** `rm -rf .skills/wiki-update/` in the fork.

**Side effects:**
- `kb-contexts-regenerate` iterates over `.skills/*/`, so on next regen
  the stale `wiki-update` symlinks in existing contexts are pruned automatically
- Existing wiki pages ([[wiki-update-deprecation]]) stay as historical reference

**Caveat:** upstream still ships `wiki-update`. If we rebase on upstream pulls,
the deletion shows as "our patch deleted something upstream still has." Clean
rebase — no conflict unless upstream renames/deletes the dir differently.

### Patch F — CWD-first config ordering in `wiki-ingest` and `wiki-query`

**Goal:** defensive barrier against any stale `~/.obsidian-wiki/config`.
After this patch, a stale global config file cannot silently override
CWD-based routing.

**Patches:**

`wiki-ingest/SKILL.md:18` — before:
```
1. Read `~/.obsidian-wiki/config` (preferred) or `.env` (fallback) to get ...
```
After:
```
1. Read configuration in this order (first found wins — CWD takes precedence
   so multi-vault sessions always read their own context):
   a. `.env` in the current working directory — local config
   b. `~/.obsidian-wiki/config` — legacy global config fallback
   Pull `OBSIDIAN_VAULT_PATH` and `OBSIDIAN_SOURCES_DIR` from whichever
   resolves first.
```

`wiki-query/SKILL.md:18` — same inversion; drop the "if you're inside the
obsidian-wiki repo" conditional (CWD-first makes it universal).

**Backwards compatibility:** single-vault users running from outside any
`.env`-bearing directory still get the global config. Only users in a
CWD-`.env` directory see a different resolution — which is the whole point.

### Patch G — Migrate `wiki-ar9av-update` from script to skill

**Goal:** move fork-maintenance logic into the fork itself. Consistent with
the rest of the ecosystem (all user-facing operations are skills).

**Actions:**
1. Create `.skills/wiki-ar9av-update/SKILL.md` in the fork with skill-form
   equivalent of the script's 108-line flow
2. Delete `kb-system/scripts/wiki-ar9av-update`
3. `kb-contexts-regenerate` picks up the new skill automatically and symlinks
   it into every context
4. Users invoke via `/wiki-ar9av-update` from any context dir (or
   `claude --print --dangerously-skip-permissions "/wiki-ar9av-update"` for
   scripted use)

**Skill structure (sketch):**

```markdown
---
name: wiki-ar9av-update
description: Safely pull upstream Ar9av/obsidian-wiki into our fork via
  fetch-rebase-force-with-lease, then regenerate kb-system contexts.
---

# Upstream Maintenance for the Obsidian-Wiki Fork

[...]

## Before You Start
1. Read .env to get fork path (usually /mnt/host/shared/git/obsidian-wiki)
2. Verify upstream remote exists; if not, abort with instructions

## Steps
1. `git fetch upstream` in the fork
2. Preview: `git log main..upstream/main --oneline`
3. Check for risky changes (setup.sh, SKILL.md); warn if present
4. Confirm with user (y/N gate)
5. Tag rollback point: `pre-update-YYYYMMDD-HHMMSS`
6. `git checkout main && git rebase upstream/main` — halt on conflict
7. `git push --force-with-lease origin main`
8. Run `kb-system/scripts/kb-contexts-regenerate`
9. Remind user to run `/wiki-lint` in each vault context

## Rollback
If something broke:
- `cd $REPO && git rebase --abort` (if mid-rebase)
- `git reset --hard <rollback_tag>`
- `git push --force-with-lease origin main`
- `kb-system/scripts/kb-contexts-regenerate`
```

**UX trade-off:** users must `cd contexts/<any>` before invoking, vs the
script which ran from anywhere. Acceptable — multi-vault workflow assumes
everyone's already cd-ing into contexts anyway.

---

## 5. Migration phases

Six phases. Phases 1-4 are fork-side patches; Phase 5 is kb-system cleanup;
Phase 6 is operator cleanup + verification.

### Phase 0 — verify (read-only)

- Re-confirm fork state clean, 3 commits ahead of upstream
- Snapshot pre-cleanup state of all touched files
- Verify test plan (see §7) can be executed against a fresh kb-personal
  clone / re-creation

### Phase 1 — Patch D (retire setup.sh)

Branch: `feat/retire-setup-sh`
- `git rm setup.sh` in the fork
- Rewrite `README.md` to describe multi-vault deployment:
  - Remove all `setup.sh` references from §Quick-Start, §Agent-Compatibility, §Manual-setup
  - Replace with "clone the fork; clone kb-system; run `kb-contexts-regenerate`"
  - Remove "Using from other projects" section (the /wiki-update narrative)
- Commit: `chore: retire setup.sh; onboarding via kb-system contexts`

### Phase 2 — Patch E (remove `wiki-update` skill)

Branch: `feat/remove-wiki-update-skill`
- `git rm -r .skills/wiki-update`
- Update `AGENTS.md` to drop the "two global skills" paragraph; replace
  `wiki-update` row in the skill-routing table with a note pointing at
  `/wiki-ingest <path>`
- Update `README.md` skill table (remove wiki-update row)
- Commit: `feat: remove wiki-update skill; superseded by /wiki-ingest in multi-vault model`

### Phase 3 — Patch F (CWD-first config ordering)

Branch: `feat/cwd-first-config`
- Edit `wiki-ingest/SKILL.md:18` and `wiki-query/SKILL.md:18`
- Commit: `feat: CWD-first config ordering in wiki-ingest and wiki-query`

### Phase 4 — Patch G (migrate `wiki-ar9av-update` to skill)

Branch: `feat/wiki-ar9av-update-skill`
- Create `.skills/wiki-ar9av-update/SKILL.md` with full skill content
- Commit: `feat: migrate wiki-ar9av-update from kb-system script to fork skill`

### Phase 5 — kb-system cleanup

(Not a fork branch; kb-system repo directly)
- `git rm kb-system/scripts/wiki-ar9av-update`
- Update `README.md` §Upstream-maintenance to describe
  `/wiki-ar9av-update` skill invocation from any context
- Commit to kb-system: `refactor(scripts): migrate wiki-ar9av-update to fork skill`

### Phase 6 — operator cleanup + verification

**Machine cleanup (optional, cosmetic):**
```bash
rm -rf ~/.gemini/antigravity/skills  # broken symlinks from pre-flatten setup.sh
rm -rf ~/.codex/skills
rm -rf ~/.agents/skills
```

**Verification:** re-run the kb-personal recreation test (§7) against the
cleaned-up fork. Validates end-to-end that cleanup didn't break anything.

---

## 6. Patch application order rationale

D → E → F → G is the ordering we'll use. Rationale:

- **D first:** removing setup.sh makes the rest safer. Any residual "run
  setup.sh to fix" paths in skill prompts (we're patching those too, but
  belt-and-suspenders) no longer have an executable target.
- **E second:** wiki-update skill removal is unblocked by D (users can't be
  told to "run setup.sh" because it doesn't exist).
- **F third:** config-ordering patches are pure defensive moves. Order
  relative to D/E doesn't matter.
- **G last:** the new skill depends on kb-contexts-regenerate (a kb-system
  script) which we're keeping. Easiest to validate after the other patches
  have settled.

Each patch is its own branch → merge to main → push. Per-patch atomic
commits per defensive discipline from FORK-MIGRATION-PROPOSAL.

---

## 7. Verification plan

### 7.1 Fork-side sanity

After all 4 patches applied:

- `bash setup.sh` produces "command not found" (D1) or deprecation notice (D2)
- `/wiki-update` in any context produces graceful error / the skill dir is absent from `.claude/skills/` post-regen
- `/wiki-ingest` and `/wiki-query` work normally; placing a dummy
  `~/.obsidian-wiki/config` with a wrong path doesn't override CWD routing
  (Patch F test)
- `/wiki-ar9av-update` invocable from `contexts/wiki` or `contexts/personal`;
  does a no-op fetch-rebase when fork is current

### 7.2 End-to-end: re-run kb-personal recreation test

Cleanest test of cumulative correctness. Repeat the exact sequence from the
prior successful run:

1. `gh repo delete nunogt/kb-personal --yes`
2. `mv /mnt/host/shared/git/kb-personal /tmp/kb-personal-pre-cleanup-test-<ts>`
3. `rm kb-system/profiles/personal.env`
4. `rm -rf kb-system/contexts/personal`
5. `kb-system/scripts/kb-vault-new personal "personal notes vault"`
6. User: open new terminal, `cd contexts/personal`, `claude`, `/wiki-setup`

Expected signals (all previously observed):
- `/wiki-setup` recognizes our multi-vault architecture and skips global-config
  creation
- `/wiki-setup` recognizes `OBSIDIAN_INVAULT_SOURCES_DIR` option
- Standard scaffold produced; concurrent-session isolation preserved
- **Additional new signal:** no reference to `setup.sh` or `/wiki-update` in
  skill output (they're gone from the fork)

### 7.3 Upstream-maintenance round-trip

Before committing the migration to main:
- On a test branch of the fork, run the new `/wiki-ar9av-update` skill
- Confirm: fetch, preview, rebase (no-op today since we're current), push
  (would force-with-lease — or skip if no-op), regen contexts
- Compare behavior vs current script — functional parity

---

## 8. Risk + rollback

| Risk | Severity | Mitigation |
|---|---|---|
| Rebase conflicts on future upstream pulls (setup.sh, SKILL.md changes) | Medium | Our fork's patches grow to 7-8 commits; upstream changes to same files produce conflicts needing manual resolution. Already our pattern — Patch G's wiki-ar9av-update handles rebase interactively. |
| Deleted `wiki-update` skill breaks someone's automation | Low | No consumer we know of. Remaining contexts have stale symlinks pruned on next regen. |
| CWD-first ordering surfaces a case we haven't considered | Low | `.env`-reading is well-defined; existing 13 non-global-config skills already use CWD-only and work fine. The 3 patched skills just join the 13 in behavior. |
| Migrated skill fails on first real run (new code path in the fork) | Low-Medium | Verification §7.3 catches this before merge. Rollback: `git revert` on the branch; script still exists at this point (deleted in Phase 5, not Phase 4). |
| User has legacy `~/.obsidian-wiki/config` we don't know about | Very low | Patch F makes this harmless anyway; belt-and-suspenders. |
| setup.sh deletion hides "legacy" onboarding path for newcomers | Low | Our fork's README is rewritten to describe the correct onboarding. Anyone using the upstream directly uses Ar9av's README, not ours. |
| Phase 5 breaks kb-system docs | Low | Same commit updates README alongside script removal. |

### Rollback paths

- **Per-patch rollback**: each patch is its own branch → if broken, don't
  merge. If merged-and-broken, `git revert <commit>` on fork's main and
  force-with-lease push.
- **Script-removal rollback** (Phase 5): `git checkout HEAD~1 -- scripts/wiki-ar9av-update` restores the script from history.
- **wiki-update skill**: if ever needed back, `git checkout <pre-patch-tag> -- .skills/wiki-update/` restores it. Low probability — we've explicitly documented it as dead.

---

## 9. What this opens up

Once all 4 patches are in + Phase 5 done:

### The fork carries a minimal, coherent patch series

Before this proposal: 3 patches (relative symlinks, in-vault sources, and a
consistency fix).

After: 7 patches (add: retire setup.sh, remove wiki-update, CWD-first
ordering, wiki-ar9av-update skill).

All 7 are defensible single-purpose changes. Eventual upstream PR (if ever
desired) is a series of small reviewable commits rather than a monolithic
divergence.

### kb-system becomes 100% infrastructure

No wrapper scripts around Claude operations (`/wiki-ar9av-update` is a skill
now). The only scripts are bootstrap primitives (`kb-contexts-regenerate`,
`kb-vault-new`). Their roles are crisp: "create things that can't be created
via a Claude session because there's no session yet."

### The "everything is a skill" invariant nearly holds

After this proposal: 
- 17 skills in the fork (16 upstream - wiki-update + wiki-ar9av-update = 16; actually let me recount)
- Actually: upstream has 16 skills. We remove wiki-update (→15). We add wiki-ar9av-update (→16). Net: still 16.
- 2 bootstrap scripts (kb-contexts-regenerate + kb-vault-new) — the only non-skill operational primitives

### Newer users see the post-refactor architecture as the default

A fresh clone of the fork + kb-system (the "reproducibility" test) walks a
newcomer through the CWD-based architecture from the start. No setup.sh
narrative in README, no wiki-update carrot dangling, no global config
mentioned. The docs reflect the system.

---

## 10. Doc propagation post-cleanup

### Fork (`obsidian-wiki/`)

| File | Change |
|---|---|
| `setup.sh` | REMOVED |
| `.skills/wiki-update/` | REMOVED |
| `.skills/wiki-ingest/SKILL.md` | Patch F — CWD-first ordering |
| `.skills/wiki-query/SKILL.md` | Patch F — CWD-first ordering |
| `.skills/wiki-ar9av-update/SKILL.md` | NEW — migrated from kb-system script |
| `README.md` | Rewritten; no setup.sh narrative; no "global skills" paragraph; onboarding via kb-system |
| `AGENTS.md` | Drop "Two global skills handle this" paragraph; update skill-routing table |

### kb-system

| File | Change |
|---|---|
| `scripts/wiki-ar9av-update` | REMOVED |
| `README.md` | §Upstream-maintenance → describe `/wiki-ar9av-update` skill invocation |

### kb-wiki (operational pages)

Following the pattern from previous ingests — pages that currently describe
`scripts/wiki-ar9av-update` get updated on next `/wiki-ingest` of this
proposal:

| Page | Update |
|---|---|
| `skills/wiki-ar9av-update` | Now a fork skill, not a kb-system script |
| `skills/using-ar9av-self-hosted` | Upstream maintenance section |
| `entities/ar9av-obsidian-wiki` | Gap "No in-vault sources support" is patched; "absolute symlinks in setup.sh" gap becomes moot (setup.sh is gone) |

Historical pages (`refactor-log-doc`, `bootstrap-log-doc`, `fork-migration-proposal-doc`, etc.) are untouched — they describe what was true at write time.

**New pages created on re-ingest of this proposal:**
- `references/legacy-cleanup-proposal-doc` (per convention)
- Possibly: `concepts/config-resolution-order` (if the CWD-first pattern is
  interesting enough to deserve its own page; probably fold into existing
  `cwd-based-profiles` instead)

---

## 11. Approval protocol

Reply with one of:

- **"approved all"** — execute Phases 0-6 sequentially. After phase 6 + verification, commit kb-wiki page updates in a follow-up ingest.
- **"approved through phase 4"** — fork-side patches only; pause before
  removing the kb-system script (Phase 5). Lets you eyeball the migrated
  skill before committing to the removal.
- **"approved D+F only"** (the defensive-only slice) — drop the setup.sh
  footgun + flip config ordering; keep wiki-update skill as-is; don't
  migrate wiki-ar9av-update. Minimalist cleanup.
- **"reject / rework"** — explain what to change.

**Recommendation:** "**approved all**".

Rationale: the multi-vault architecture is proven end-to-end. Every
intermediate step was deliberately conservative to prove out the approach.
Now that it works, the residual footguns serve no purpose. Full cleanup
produces the coherent final shape; anything less leaves landmines for
future sessions.

Phases are per-patch atomic; rollback at any point is a single `git revert`.
Verification (§7) reuses the already-successful kb-personal recreation test,
catching any regressions before they persist.

---

## 12. Cross-references for next ingestion

When this proposal lands in the wiki:

**New concept candidates:**
- *(Optional)* `concepts/config-resolution-order` — explaining CWD-first and
  why single-global-config is the anti-pattern for multi-vault.

**New reference:**
- `references/legacy-cleanup-proposal-doc` — this file.

**Updates to existing pages:** see §10 above.

**No new synthesis page needed** — `multi-vault-architecture` already covers
the full composition; this proposal is a cleanup to match.

---

*End of proposal. Awaiting approval.*
