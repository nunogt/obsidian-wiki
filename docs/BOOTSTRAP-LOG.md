# Bootstrap execution log

Started: 2026-04-14. Executing `BOOTSTRAP-PROPOSAL.md` phases 1–7.

Operator answers (from review):
- Claude Code installed and authenticated: **yes**
- Model: **Opus 4.6** (inherited from Claude Code default)
- Billing: **subscription**
- Permissions: **`--dangerously-skip-permissions`** baked into `wiki-run`
- Disposition of this file: **converted to log; moved to `research/` at end
  for next ingest**

---

## Phase 1 — Cleanup

*completed 2026-04-14*

```
rm -rf /mnt/host/shared/git/kb/nvk-llm-wiki
rm -rf /mnt/host/shared/git/kb/samuraigpt-llm-wiki-agent
```

Verified: only `ar9av-obsidian-wiki/` remains in the repo-clones slot.
Research docs, proposal, log untouched. ~3.5 MB reclaimed.

---

## Phase 2 — Preserve research docs

*completed 2026-04-14*

```
mkdir -p research
mv karpathy-llm-wiki-research.md
   karpathy-llm-wiki-panel-review.md
   ar9av-self-hosted-architecture.md
   _review-rubric.md
   research/
```

Preserved as `OBSIDIAN_SOURCES_DIR` target. Append-mode ingest will not
delete these.

---

## Phase 3 — Install wrapper scripts

*completed 2026-04-14*

Created `scripts/wiki-switch` and `scripts/wiki-run`; both `chmod +x`.
`wiki-run` passes `--dangerously-skip-permissions` to every `claude`
invocation per operator decision.

Did **not** create `/usr/local/bin/` symlinks (sudo not available in this
session). Invoke scripts by absolute path for now:
```
/mnt/host/shared/git/kb/scripts/wiki-run work <op>
```
Operator can `sudo ln -s ...` later if desired.

---

## Phase 4 — Configure ar9av work profile

*completed 2026-04-14*

- Wrote `ar9av-obsidian-wiki/.env.work` with
  `OBSIDIAN_VAULT_PATH=/mnt/host/shared/git/kb/vaults/work` and
  `OBSIDIAN_SOURCES_DIR=/mnt/host/shared/git/kb/research`
- `.env` is now a symlink → `.env.work` (already in upstream `.gitignore`)
- `bash setup.sh` ran cleanly. 16 skills installed. Global config at
  `~/.obsidian-wiki/config` points at the work vault. Global skills
  installed: `~/.claude/skills/wiki-update`, `~/.claude/skills/wiki-query`.
- No interactive prompt (setup.sh read the non-placeholder path from
  `.env.work` as designed).

---

## Phase 5 — Scaffold work vault

*completed 2026-04-14 (with note)*

```
mkdir -p vaults/work
cd vaults/work && git init -b main
wiki-run work setup   # runs claude --print "/wiki-setup"
```

Scaffolding completed cleanly — ar9av's `/wiki-setup` created:
- Category dirs: `concepts/`, `entities/`, `skills/`, `references/`,
  `synthesis/`, `journal/`, `projects/`
- System dirs: `_archives/`, `_raw/`, `_meta/` (with `taxonomy.md`),
  `.obsidian/` (with `app.json` and `appearance.json`)
- Special files: `index.md`, `log.md`, `.manifest.json`

**Note:** the `wiki-run` wrapper stalled on the tail output of
`claude --print`. The scaffolding completed; only the auto-commit was
delayed. Committed manually as `e6bdca8`. Implication for Phase 6:
long-running ingest should be dispatched in background, not foreground.

---

## Phase 6 — Bootstrap meta-wiki via ingest

*completed 2026-04-14; duration 18m22s on Opus 4.6*

Operator started a fresh Claude Code session at
`/mnt/host/shared/git/kb/ar9av-obsidian-wiki` with
`claude --dangerously-skip-permissions` and issued the ingest prompt.
The `wiki-ingest` skill loaded cleanly, read all four source docs from
`research/`, planned ~34 pages, executed writes, and committed the
`.manifest.json` + `index.md` + `log.md` updates.

**Output:** 34 pages total.

| Source | Pages |
|---|---:|
| `karpathy-llm-wiki-research.md` | 10 |
| `karpathy-llm-wiki-panel-review.md` | 13 |
| `ar9av-self-hosted-architecture.md` | 6 |
| `_review-rubric.md` | 5 |

**Breakdown:** 10 entities, 13 concepts, 5 skills, 4 references, 2
synthesis. All under the 15-per-source cap.

**Commit:** `160bcf3` in `vaults/work/`. Vault size: 745 KB.

**Quality spot checks:**
- `concepts/fold-back-loop.md` contains verbatim gist quotes for both
  pathways, a comparative table of the three panel projects, provenance
  fractions (0.7/0.3/0.0), proper frontmatter with `sources:` list.
- `entities/karpathy.md` cites exact gist ID, dates (2026-04-02 tweet,
  2026-04-04 gist), star/fork counts, embeds Karpathy's governing quotes.
- `skills/using-ar9av-self-hosted.md` mirrors the architecture doc with
  proper cross-links via [[wikilinks|aliased]] syntax.

---

## Phase 7 — Verify bootstrap

*completed 2026-04-14*

**index.md:** all 34 pages catalogued under correct category headings
with one-line summaries drawn from each page's `summary:` frontmatter.

**log.md:** five entries — one INIT, four INGEST — with ISO-8601
timestamps and correct page counts.

**Wikilink integrity (offline check, no LLM):**
- Total `[[target]]` references: 38
- Resolved: 34
- Broken: 4 — all stylistic (`[[slug]]`, `[[wikilinks]]`, `[[wikilink]]`,
  `[[panel-review]]` used as nouns rather than real page targets). Not
  data corruption; trivial first-lint-pass cleanup.

**Sanity-query deferred.** Would require another `claude --print`
invocation; deferred to the operator's own ar9av session post-switchover.

**Lint pass deferred.** Same reasoning; `wiki-run work lint` is the first
thing the operator should run in their ar9av session and will catch the
4 stylistic broken links above.

---

## Final notes

**State at handoff:**
- Work vault at `/mnt/host/shared/git/kb/vaults/work/`
- 2 commits: `e6bdca8` (scaffold), `160bcf3` (initial ingest)
- 34 pages compiled, properly interlinked, summary/provenance frontmatter present
- `research/` preserved; `.manifest.json` records SHA-256 for delta-skip
  on any re-ingest
- `wiki-switch work` is the active profile; global config points here

**Recommended first operations in operator's ar9av session:**
1. `wiki-run work lint` — fixes the 4 stylistic broken wikilinks; confirms
   cleanliness
2. `wiki-run work query "what are the two canonical fold-back pathways?"`
   — sanity check that query works end-to-end with the compiled wiki
3. Start using it: drop new sources into `research/` (or scp into
   `_raw/`) and run ingest again; the manifest's SHA-256 skip keeps
   re-ingest cheap.

**This log will be moved to `research/` as a source for the next
ingest**, per the operator's §5 answer — the bootstrap process becomes
part of the wiki's history, which is the meta-meta-wiki property.

**What was not set up:**
- Personal vault (deferred; pattern is identical, just swap scope)
- Laptop-side clone + Obsidian Git plugin (deferred; follow arch doc §6)
- Automation (cron/systemd lint) — explicit operator decision to skip
- `/usr/local/bin/` symlinks for scripts (sudo unavailable in this
  session; operator can add later)

---

## Addendum — ar9av maintenance protocol

*added 2026-04-14*

**The symlink divergence problem.** ar9av's `setup.sh` rewrites the
committed in-repo agent symlinks under `.claude/skills/`, `.cursor/skills/`,
`.agents/skills/`, `.windsurf/skills/` from the author's absolute paths
(`/Users/ar9av/…`) to this machine's absolute paths
(`/mnt/host/shared/git/kb/…`). Because git tracks symlinks as versioned
objects, `git status` shows 56+ files as permanently modified. Every
upstream pull carries conflict risk.

**The resolution.** Treat those agent-dir symlinks as **derived state** —
discard local rewrites before pulling, then let `setup.sh` regenerate
them. This is what `scripts/wiki-ar9av-update` automates:

1. `git fetch origin`
2. Preview incoming commits; warn on `.env.example` or `SKILL.md` changes
3. Confirm (y/N gate)
4. Tag rollback point (`pre-update-YYYYMMDD-HHMMSS`)
5. `git checkout -- .claude/skills .cursor/skills .agents/skills .windsurf/skills`
6. `git pull --ff-only`
7. `bash setup.sh` to regenerate symlinks
8. Diff `.env.example` against `.env.work` / `.env.personal`; report new
   keys that may need adopting
9. `wiki-switch show` as smoke test
10. Remind to run `wiki-lint` post-update (catches schema migrations via
    ar9av's "lint-is-the-migration" principle)

**Suggested cadence.** Weekly, or when a GitHub notification highlights a
meaningful upstream change. ar9av commits a few per week historically —
low burden.

**What pull updates vs. doesn't:**
- *Updated by pull:* `.skills/*/SKILL.md` (actual skill content),
  `AGENTS.md` (schema), `setup.sh`, `.env.example`
- *Not touched:* `.env.work` (untracked), `~/.obsidian-wiki/config`
  (outside repo), vaults at `vaults/*` (separate repos)

**Gotchas:**
- **Architecture doc citations** (`SKILL.md:18` etc.) rot on upstream
  refactors. Accept as snapshot references; refresh when upstream breaks
  them.
- **Breaking schema changes** (e.g., v0.2.0's `_project.md → WHY.md`
  migration) are auto-fixed by running `wiki-lint` post-update.

---

## Addendum — post-bootstrap restructuring

*added 2026-04-14*

After Phase 7, three structural refinements were applied based on operator
feedback. The log above still describes what was true at bootstrap time;
this addendum describes what changed after.

### Vault rename: `work` → `wiki`

Operator feedback: "work" mischaracterized the vault, whose content is
meta-knowledge about ar9av itself, not domain work content. Renamed to
`wiki` as the base reference vault. Future vaults (personal, project,
etc.) are separate.

Impact:
- `vaults/work/` → `vaults/wiki/` (renamed; git history preserved)
- `.env.work` → `.env.wiki` and moved to `kb/profiles/wiki.env`
- `~/.obsidian-wiki/config` regenerated via `wiki-switch wiki`

### Profile file relocation

Profile files moved from inside the ar9av clone to `kb/profiles/<scope>.env`.
The ar9av clone's `.env` is now a symlink to `../profiles/<active>.env`.
This decouples user-specific config from upstream ar9av, so profile
files are tracked by the kb-system repo (reproducible on new machines)
without requiring an ar9av fork.

### `wiki-switch` generalized

Previously hard-coded to `work|personal`. Now dispatches on any file
matching `profiles/*.env`. Adding a new vault is a three-step operation:
drop a profile file, `mkdir vaults/<name>`, `git init`. No script changes.

### Three-repo versioning

The layout is now tracked across three independent git repos:

- `github.com/<operator>/kb-system` (private) — scripts, profiles,
  research, docs. Outer `kb/` directory is a git repo with `.gitignore`
  excluding `ar9av-obsidian-wiki/` and `vaults/`.
- `github.com/<operator>/<vault>` (private, one per vault) — each vault's
  content history.
- `github.com/Ar9av/obsidian-wiki` (upstream) — ar9av itself, pulled via
  `wiki-ar9av-update`.

Rationale and reproduction instructions are in the updated
`ar9av-self-hosted-architecture.md` §9 ("Versioning strategy").

### Decision: no governance-layer semantics

Considered using the `wiki` vault as a "governance layer" that propagates
conventions to future vaults. Rejected: ar9av has no cross-vault
inheritance mechanism. Claude's conventions come from `.skills/*/SKILL.md`
and `AGENTS.md`, which already propagate to every vault automatically
via shared scripts and symlinks. The `wiki` vault is a reference and
learning resource about ar9av itself — not a mechanism. See
`ar9av-self-hosted-architecture.md` §14.

---

## Addendum 2 — remote naming + vault-creation automation

*added 2026-04-14*

Follow-on session after the post-bootstrap restructuring. Two changes
driven by operator observation that bare repo names (`wiki`, `personal`)
collide with other GitHub projects and are non-discoverable as
vault-family members in a repo listing.

### Remote naming convention: `kb-<scope>`

Vault remotes now follow `github.com/<you>/kb-<scope>` so they sit
alongside `kb-system` as a visible family. Local directory names stay
unprefixed (`vaults/<scope>`), since the prefix adds no value on-disk
where context is obvious.

Applied to the existing vaults:
- `github.com/nunogt/wiki` renamed to `github.com/nunogt/kb-wiki` via
  `gh repo rename` (GitHub redirects old URLs automatically). Local
  `origin` URL updated for `vaults/wiki/`.
- `github.com/nunogt/kb-personal` created fresh. Contains the scaffold
  produced by `/wiki-setup` in a separate Claude session, plus the
  canonical vault `.gitignore`. Commit `33f14ff` pushed on creation.

### `scripts/kb-vault-new` — one-shot vault creator

New convenience script collapsing the six-step manual vault-creation
sequence into a single invocation:

```
kb-vault-new <name> ["optional description"]
```

Steps performed in order:

1. Validates name format (lowercase, alphanumeric + dash/underscore)
2. Aborts cleanly if any of: `profiles/<name>.env`, `vaults/<name>/`,
   or `github.com/<you>/kb-<name>` already exist
3. Writes `profiles/<name>.env` from `scripts/templates/profile.env`
   with `{NAME}` substituted — defaults `OBSIDIAN_SOURCES_DIR` to empty
   (material enters via scp to `_raw/`)
4. Creates `vaults/<name>/` and runs `git init -b main`
5. Seeds the canonical `.gitignore` from
   `scripts/templates/vault.gitignore`, commits it
6. Creates `github.com/<you>/kb-<name>` as a private repo via
   `gh repo create --source=. --push` and wires `origin`
7. Activates the new profile via `wiki-switch <name>`
8. Prints next-step instructions for ar9av's `/wiki-setup` scaffold
   and the eventual `git push`

The script is read-only on the outer kb-system working tree and writes
only under its own paths. Idempotency via hard aborts, not by being
re-runnable.

### `scripts/templates/` — canonical templates

New directory holding templates used by `kb-vault-new`:

- `profile.env` — profile file template with `{NAME}` placeholder
- `vault.gitignore` — canonical per-user Obsidian state ignore set

Both are version-tracked by kb-system. Updating a template affects
*future* vaults (existing vaults would need manual sync to absorb
changes).

### Doc propagation

Updated to reflect the kb-<scope> convention and `kb-vault-new`:
- `README.md` §Layout, §Reproducing, §Creating a new vault
- `research/ar9av-self-hosted-architecture.md` §3 directory layout,
  §9 versioning strategy (naming convention paragraph), §12 setup
  checklist (uses kb-vault-new)
- `.gitignore` — naming-convention note

No changes to existing scripts (`wiki-switch`, `wiki-run`,
`wiki-ar9av-update`): none reference remote names, so the convention
shift is purely additive at the naming layer.

kb-system commit `bfeeb28` captures the feature + rename in one
revision.

---

## Addendum 3 — flatten refactor + concurrent sessions

*added 2026-04-14*

Third post-bootstrap restructuring. Two drivers:

1. Operator observed that profile switching (`wiki-switch`) introduced
   shared global state that prevented concurrent Claude sessions on
   different vaults — a blocker for their actual workflow.
2. The nested `/mnt/host/shared/git/kb/{ar9av-obsidian-wiki,vaults,...}`
   layout had grown into a messy tree with four nested git repos.

Both addressed in one refactor. Motivations and design captured in
`REFACTOR-PROPOSAL.md` (now in this `research/` directory); this
addendum summarises the outcome.

### Flat layout

All four repos are now siblings at `/mnt/host/shared/git/`:

```
/mnt/host/shared/git/
├── ar9av-obsidian-wiki/     (upstream, read-only)
├── kb-system/               (formerly /kb/ — infrastructure repo)
├── kb-wiki/                 (formerly /kb/vaults/wiki/)
├── kb-personal/             (formerly /kb/vaults/personal/)
└── ...other projects...
```

Directory name = remote name. No more nesting.

### CWD-based profile selection

`wiki-switch` and `wiki-run` deleted. Each profile gets a gitignored
context directory under `kb-system/contexts/<name>/` with symlinks to
upstream ar9av skills and its own `.env`. CWD selects the profile; two
terminals in two context dirs = two concurrent sessions.

### Global state retired

Three pieces of shared global state removed:
- `~/.obsidian-wiki/config` — deleted (would route concurrent sessions through one profile)
- `~/.claude/skills/wiki-update` — deleted (global install ambiguated targeting)
- `~/.claude/skills/wiki-query` — deleted (same)

### Script changes

| Script | Before | After |
|---|---|---|
| `wiki-switch` | exists | deleted |
| `wiki-run` | exists | deleted |
| `kb-contexts-regenerate` | — | new |
| `kb-vault-new` | exists | updated (absolute paths + context generation) |
| `wiki-ar9av-update` | exists | updated (drops `setup.sh`, adds contexts regen) |

Four scripts, all infrastructure; no wrappers around Claude.

### Known non-functional: `/wiki-update`

`wiki-update/SKILL.md:16-19` reads `~/.obsidian-wiki/config` with no
fallback. With global config deleted, the skill errors out with *"run
setup.sh"*. Accepted: the skill was designed for single-vault setups
and doesn't fit the concurrent-vault model. Use `/wiki-ingest` with an
explicit source path instead. `kb-contexts-regenerate` still symlinks
the skill for completeness; invoking it is a no-op error.

### Proposal docs moved to `research/`

`BOOTSTRAP-PROPOSAL.md`, `PROPOSAL-CONCURRENT-SESSIONS.md`, and
`REFACTOR-PROPOSAL.md` — all moved here as historical scaffolding. They
describe decisions that shaped the current layout. Next re-ingest folds
their content into the wiki as further history.

### Reproduction verified

Phase 4 of the refactor included a clean-slate clone from remote to
prove the setup is rebuildable on any machine. Four clones + one
`kb-contexts-regenerate` invocation produces the working state. No
`bash setup.sh` needed — ar9av's setup.sh is now obsolete.
