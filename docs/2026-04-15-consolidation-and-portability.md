# 2026-04-15 — consolidation + portability execution log

*Narrative record of the day the kb-system repo disappeared. What began as a portability refactor (making the dev-VM layout work on a work laptop) ended as an architectural consolidation (folding kb-system entirely into the fork). This doc captures both refactors' execution history, the final two-repo state, and the work-laptop validation that proved the system portable.*

---

## 0. The architectural shift, at a glance

### Morning state (pre-today)

```
/mnt/host/shared/git/
├── obsidian-wiki/           ← the fork (engine)
│   └── .skills/             ← 12 agent-invoked skills
├── kb-system/               ← provisioning + harness + docs
│   ├── scripts/             ← kb-vault-new, kb-contexts-regenerate, hooks/, templates/
│   ├── profiles/            ← per-vault .env files
│   ├── contexts/            ← gitignored per-machine assembly (symlinks + materialized state)
│   └── docs/                ← all proposals, panels, activation guide
└── kb-<vault>/              ← plain data, tracked wiki content
```

Three repos. Contexts/ was the operator-facing CWD (`cd kb-system/contexts/ebury && claude`). Absolute paths hardcoded to `/mnt/host/shared/git/` throughout.

### Evening state (post-today)

```
~/git/                       ← operator's git root (derived per-machine)
├── obsidian-wiki/           ← fork = engine + provisioning + harness + docs
│   ├── .skills/             ← 12 skills (unchanged)
│   ├── scripts/             ← kb-vault-new, kb-vault-materialize, hooks/, templates/
│   └── docs/                ← all proposals + this log
└── kb-<vault>/              ← self-contained Claude Code workspace
    ├── .env.template        ← tracked, {GIT_ROOT}/{NAME} placeholders
    ├── .env                 ← gitignored, materialized
    ├── .claude/             ← gitignored, materialized
    ├── CLAUDE.md→...        ← gitignored symlink to fork
    └── concepts/, entities/, ...
```

Two repo categories. Operator-facing CWD = the vault itself (`cd kb-ebury && claude`). Paths derived from script location, so `/Users/nunogt/git` on macOS works identically to `/mnt/host/shared/git` on Linux.

---

## 1. Refactor 1 — PORTABILITY (KB_GIT_ROOT)

### 1.1 Motivation

Operator wanted to run the system on a work laptop with a different filesystem layout (`/Users/nunogt/git` vs `/mnt/host/shared/git`). Seven files had `/mnt/host/shared/git/` hardcoded:
- `scripts/kb-vault-new` and `scripts/kb-contexts-regenerate` — `GIT_ROOT` at top
- `scripts/templates/profile.env` and `scripts/templates/claude-settings.json` — paths in templates
- `profiles/wiki.env`, `profiles/personal.env`, `profiles/ebury.env` — absolute paths in profiles

### 1.2 Panel deliberation

PORTABILITY-PANEL convened: Fowler, Hightower, Kernighan, Hashimoto, Cantrill. Four meta-questions:

| Q | Decision | Vote |
|---|---|---|
| Q1 profile format | `{GIT_ROOT}` placeholders + regen substitution | 4-of-5 (Hashimoto dissents for overlay pattern) |
| Q2 `KB_GIT_ROOT` origin | Derive from script location + optional env-var override | Unanimous on derivation |
| Q3 contexts | Materialize real files at regen time (not symlinks) | Unanimous |
| Q4 hook command paths | Absolute paths via realpath at regen time | Unanimous |

Hashimoto argued for a Vagrant-style `profiles/<name>.local.env` overlay. Majority deferred with documented migration path if/when variance grew beyond one path.

### 1.3 Execution

Commit `81f98b6` on `kb-system@main`. 7 files touched, +122/-46 lines:

- `kb-contexts-regenerate` gained derivation + env override + materialization helpers
- `kb-vault-new` got the same derivation
- Templates got `{GIT_ROOT}` placeholders
- Committed profiles rewritten with `{GIT_ROOT}`
- Contexts materialization changed from symlinks to real files

### 1.4 Cosmetic fix

Initial template's `_comment` field self-referenced `{GIT_ROOT}` which got substituted away at materialization, producing the misleading `"/mnt/host/shared/git is a placeholder"`. Rewrote the comment to describe the materialized form, not the template itself. Minor, fixed before the refactor landed.

### 1.5 Work-laptop validation (early)

After this refactor, `cd kb-system/scripts && ./kb-contexts-regenerate` on any machine would derive the correct `KB_GIT_ROOT` and produce usable contexts/. This was proven locally but not yet on a second machine. That validation came post-consolidation (§3.6).

---

## 2. Refactor 2 — CONSOLIDATION (kb-system dissolved)

### 2.1 The operator's pivot

Mid-afternoon, after the PORTABILITY refactor shipped, the operator asked a sharper question: *"can't I just run from the kb-ebury path? Do I need to run it from the kb-system path?"*

The answer revealed a design tension: kb-system's `contexts/` directory was a legacy assembly-point, even after PORTABILITY made the paths work. The operator's natural mental model — "the vault is the project; cd into the project to work" — didn't fit the contexts/ indirection.

From that came a bigger claim: *"I think we probably don't need the kb-system at all; entire system provisioning self-contained in fork with scripts to instantiate self-contained kb-vaults that Claude Code can execute on directly."*

### 2.2 Panel deliberation

CONSOLIDATION-PANEL convened: Fowler, DHH, Kernighan, Hashimoto, Cantrill. Four questions:

| Q | Decision | Vote |
|---|---|---|
| Q1 scripts location | `obsidian-wiki/scripts/` + `scripts/hooks/` + `scripts/templates/` | Unanimous |
| Q2 vault layout | Materialize `.env` + `.claude/` + symlinks at vault root, gitignored | Unanimous |
| Q3 migration | In-place; the new materializer *is* the migration tool | Unanimous |
| Q4 kb-system fate | Archive after migrating docs to fork | 4-of-5 (DHH dissents: delete) |

DHH's lone dissent on Q4: *"If it's not in active use, why pay the cognitive overhead of remembering it exists? Move what's worth keeping to the fork; abandon the rest. The 'archive in case' instinct is how repos accumulate forever. Just delete."*

Operator picked DHH. Archive became delete.

### 2.3 Six-phase migration plan

| Phase | What |
|---|---|
| 1 | Copy `kb-system/scripts/` (kb-vault-new, hooks/, templates/) → `obsidian-wiki/scripts/` |
| 2 | Copy `kb-system/docs/` (16 design docs) → `obsidian-wiki/docs/` |
| 3 | Adapt materializer for vault-self-contained layout; rename `kb-contexts-regenerate` → `kb-vault-materialize` |
| 4 | Update vault.gitignore template + per-vault .gitignore for each existing vault |
| 5 | Generate `.env.template` in each existing vault from the corresponding kb-system profile |
| 6 | Run materialization on all 3 existing vaults |
| 7 | Commit fork + push |
| 8 | Commit per-vault .env.template + .gitignore + push (3 repos) |
| 9 | Delete kb-system from GitHub |
| 10 | Final verification |

Each phase reversible by `git revert` if something broke. Migration was additive until Phase 9 (only GitHub deletion is hard-to-reverse, and even that isn't truly lost because content migrated to fork).

### 2.4 Execution — fork commit

Commit `3e66ab8` on `obsidian-wiki@main`. Single commit, 26 files created, +8840 lines:

- 16 design docs moved to `docs/`
- 5 Python hook helpers moved to `scripts/hooks/`
- 3 templates (profile.env, claude-settings.json, vault.gitignore) moved to `scripts/templates/`
- 2 provisioning scripts: kb-vault-new + kb-vault-materialize (renamed from kb-contexts-regenerate)
- All with updated paths — scripts now derive `KB_GIT_ROOT` from `obsidian-wiki/scripts/<name>`'s location (3 dirnames up), templates now reference `{GIT_ROOT}/obsidian-wiki/scripts/hooks/...` (not `{GIT_ROOT}/kb-system/scripts/hooks/...`)

### 2.5 Execution — per-vault commits

| Vault | Commit | Change |
|---|---|---|
| kb-wiki | `897e5a0` | `.env.template` (tracked) + `.gitignore` updated |
| kb-personal | `04c75fa` | Same |
| kb-ebury | `d6e02c2` | Same |

Later (once the operator asked to align accumulated content):

| Vault | Commit | Change |
|---|---|---|
| kb-wiki | `ef2c8a6` | 13 pages created + 11 updated from earlier proposal ingest + lint fixes |
| kb-personal | `3f7e038` | Initial scaffolding (`.obsidian/`, `index.md`, `log.md`) |

### 2.6 Execution — kb-system deletion

```bash
gh repo delete nunogt/kb-system --yes
```

GitHub repo gone. Local dir `kb-system/` kept intact to avoid breaking the running session's CWD. Operator can `rm -rf` when convenient.

### 2.7 What moved where — net changes

**Added to fork** (`obsidian-wiki/`):
- `scripts/kb-vault-new` + `scripts/kb-vault-materialize` (renamed from `kb-contexts-regenerate`)
- `scripts/hooks/` (5 Python files: `_common.py` + 4 event handlers)
- `scripts/templates/` (3 files: profile.env, claude-settings.json, vault.gitignore — all with `{GIT_ROOT}` placeholders pointing at the fork)
- `docs/` (16 design docs)

**Added to each vault** (kb-wiki, kb-personal, kb-ebury):
- `.env.template` (tracked — committed form with `{GIT_ROOT}` and `{NAME}` placeholders)
- `.gitignore` extended with self-contained-workspace exclusions (`.env`, `.claude/`, `CLAUDE.md`, `AGENTS.md`, `GEMINI.md`)

**Gitignored per-machine** (not tracked; regenerated per machine):
- `.env` (substituted from .env.template)
- `.claude/settings.json` (substituted from fork's template)
- `.claude/skills/*` (symlinks to fork's `.skills/`)
- `CLAUDE.md`, `AGENTS.md`, `GEMINI.md` (symlinks to fork's AGENTS.md)

**Removed**:
- GitHub repo `nunogt/kb-system` (deleted)
- Local `kb-system/` (kept pending operator's manual `rm -rf`)
- The `contexts/<vault>/` indirection (no more assembly directory)

---

## 3. Work-laptop validation

### 3.1 The test

Fresh macOS machine, no kb-system anywhere. Operator ran:

```bash
cd ~/git
git clone git@github.com:nunogt/obsidian-wiki.git
git clone git@github.com:nunogt/kb-ebury.git
./obsidian-wiki/scripts/kb-vault-materialize kb-ebury
```

### 3.2 The output (verbatim)

```
kb-vault-materialize
  KB_GIT_ROOT = /Users/nunogt/git (derived from script location)
  fork        = /Users/nunogt/git/obsidian-wiki

▶ kb-ebury (vault name: ebury)
    profile template: vault-local .env.template
    ✓ materialized .env + .claude/settings.json + 3 instruction symlinks + 12 skill symlinks

done — 1 vault(s) materialized
```

### 3.3 What this proves

- **`KB_GIT_ROOT` derivation works cross-platform** — Linux `/mnt/host/shared/git` vs macOS `/Users/nunogt/git`, zero config
- **Vault-local `.env.template` takes precedence** over the fork's default template — per-vault customization preserved across machines
- **Materialization produces absolute macOS paths** in `.env` and `.claude/settings.json` — hook commands resolve to `/Users/nunogt/git/obsidian-wiki/scripts/hooks/stop_append.py` (which exists)
- **Zero ceremony** — clone fork + clone vault + run one script = ready-to-use workspace. No config file editing. No environment variable setup.

### 3.4 Fresh-clone verification

```bash
$ cat kb-ebury/.env | head -3
# Vault: ebury
# Self-contained — Claude Code runs from this vault directly.
# Materialized by obsidian-wiki/scripts/kb-vault-materialize.

$ cat kb-ebury/.claude/settings.json | grep command | head -1
  {"type": "command", "command": "python3 /Users/nunogt/git/obsidian-wiki/scripts/hooks/stop_append.py"}
```

macOS-absolute paths throughout. No dev-VM path leakage. No placeholder residue.

---

## 4. What didn't change

Explicitly preserved across both refactors:

- **v3 hook architecture** — same Stop + PostCompact + SessionStart:compact + UserPromptSubmit; same 5 Python helpers (only their location moved from `kb-system/scripts/hooks/` to `obsidian-wiki/scripts/hooks/`)
- **INGESTION-SIMPLIFICATION** — same unified `/wiki-ingest` skill; same `--drain-pending` mode
- **VFA ranks 2, 2.5, 3** — divergence-check, post-ingest auto-lint, two-output rule all unchanged
- **Fork's 12 skills** — same count, same behavior
- **Vault git history** — each vault's own commit history intact (new commits added; nothing rewritten)
- **Wiki content** — all tracked wiki pages unchanged except where intentionally updated by today's ingests
- **GitHub repos** — `obsidian-wiki`, `kb-wiki`, `kb-personal`, `kb-ebury` all retained (only `kb-system` deleted)

The day was a **topology change, not a feature change**. Every capability the system had survived.

---

## 5. Commits shipped today (both repos)

### On `nunogt/obsidian-wiki@main` (11 commits)

| Commit | Summary |
|---|---|
| `932dbd8` | INGESTION-SIMPLIFICATION Phase 1 — 5 format-specific reference docs |
| `ef42a4b` | Phase 2 — unified wiki-ingest/SKILL.md (242→134) + `§Safety` in llm-wiki |
| `1c276ea` | Phase 3 — removed 4 absorbed skill dirs |
| `35f8abd` | VFA rank 2 — divergence-check |
| `cf9c4c3` | VFA rank 2.5 — post-ingest auto-lint |
| `3b4230f` | VFA rank 3 — two-output rule in wiki-query |
| `fe01292` | v3 hooks validation fixes (loop guard + LINT_SCHEDULE) |
| `b1c09c7` | drain-pending cleanup guidance |
| `902cdf0` | `--drain-pending` mode + Continuous Fold-Back Convention |
| `3e66ab8` | **Consolidation — kb-system merged into fork** |
| (prior) | v3 hook architecture (landed earlier in the day) |

### On vault repos

- `nunogt/kb-wiki@main`: `897e5a0` (self-contained) + `ef2c8a6` (13 pages from proposal ingest)
- `nunogt/kb-personal@main`: `04c75fa` (self-contained) + `3f7e038` (scaffolding)
- `nunogt/kb-ebury@main`: `d6e02c2` (self-contained; earlier commits retained the operator's EBO phishing campaign ingest)

### On kb-system

**Deleted**. Had the day's PORTABILITY refactor (`81f98b6`), four-proposal docs (`02e9952`), `ACTIVATION-GUIDE` (`8af78ef`), `PORTABILITY-PANEL` (`4380674`), `CONSOLIDATION-PANEL` (`d22adfc`) — all migrated to fork's `docs/` before deletion.

---

## 6. Operator UX evolution

### Morning (3 repos, contexts/ indirection)

```bash
cd /mnt/host/shared/git/kb-system/contexts/wiki
claude --dangerously-skip-permissions
```

### Noon (portability shipped, same UX)

```bash
cd /mnt/host/shared/git/kb-system/contexts/wiki
claude --dangerously-skip-permissions
# (same commands, but KB_GIT_ROOT derives correctly across machines)
```

### Evening (consolidation shipped, vault-self-contained)

```bash
cd /mnt/host/shared/git/kb-wiki   # or any vault, any machine
claude --dangerously-skip-permissions
```

Three layers of indirection collapsed to one. The vault is the project; the project is its own home.

---

## 7. Lessons + design observations

### 7.1 Architecture can be a question of UX

PORTABILITY was about making paths work; CONSOLIDATION was about UX. The operator didn't ask for consolidation — they asked a UX question ("can't I just run from the vault?") that surfaced the architecture smell. The right answer wasn't "here's a shell alias" (which would have been tactically correct); it was "let me show you how much of kb-system is doing nothing useful anymore."

Once contexts/ had to be materialized (PORTABILITY) rather than being a simple symlink bundle, its existence as a separate dir stopped paying for itself.

### 7.2 The panel pattern works as a forcing function

Both refactors used 5-expert panels (PORTABILITY-PANEL, CONSOLIDATION-PANEL). In both cases:
- Real dissent surfaced (Hashimoto on overlay pattern, DHH on outright deletion)
- Consensus on everything else built confidence in the direction
- The dissents got documented — not erased — so future-you has a record of the trade-offs that got deferred

The pattern isn't theater. When Fowler/Hightower/Kernighan all agree on something, that alignment is informative. When one of them breaks rank, that's *also* informative.

### 7.3 Materialize, don't symlink

The PORTABILITY panel's unanimous verdict on Q3 was "materialize contexts as real files." The CONSOLIDATION panel inherited this assumption and applied it to vaults.

In both cases the alternative (symlinks pointing at canonical files) seemed cleaner but broke down on inspection:
- Symlinks store absolute paths, so they're machine-specific anyway
- Materialized files are greppable/inspectable; symlinks resolve out-of-sight
- For Claude Code specifically, `settings.json` must be a real file — no shell expansion at read time — so you end up materializing at least that one, and the consistency argument for materializing the rest is strong

### 7.4 DHH's instinct on Q4 was right

Archive vs delete. The majority wanted archive for "historical value." DHH said *"if it's not in active use, delete it."*

The operator's choice of DHH validated: proposal docs had already migrated to the fork's `docs/` before deletion. Nothing was lost. The git history on kb-system was still available for the ~20 min window between decision and deletion; after that, anyone wanting it can search the fork's docs.

The "archive in case" instinct is the kind of drift that accumulates repos forever. DHH's minimalist instinct, once the migration was complete, was correct.

### 7.5 Script-location derivation scales

The `KB_GIT_ROOT=$(dirname $(dirname $(dirname $(realpath "${BASH_SOURCE[0]}"))))` pattern works without config files, env vars, or operator setup on:
- The dev VM (Linux, `/mnt/host/shared/git/obsidian-wiki/scripts/...`)
- The work laptop (macOS, `/Users/nunogt/git/obsidian-wiki/scripts/...`)
- Any future machine that follows the `<git-root>/obsidian-wiki/scripts/<script>` convention

If someone ever needs an override (testing, alternate layouts), `export KB_GIT_ROOT=...` handles the edge case without polluting the default-path. Kernighan was right about minimalism here.

---

## 8. Open items for future work

- **Local `kb-system/` cleanup** — operator to `rm -rf /mnt/host/shared/git/kb-system` at their convenience (I left it to avoid breaking my session's CWD)
- **Wiki pages describing the old topology** — `concepts/cwd-based-profiles`, `concepts/contexts-directory`, `skills/kb-contexts-regenerate` now describe a superseded state. Next `/wiki-ingest` against this log will merge corrections into them.
- **Hashimoto's overlay-pattern migration** — still documented as a future option in PORTABILITY-PANEL §6.4 if machine-specific config grows beyond just `KB_GIT_ROOT` + vault paths
- **Second-machine setup** — operator's work laptop needs the same setup for kb-wiki + kb-personal if they want those vaults accessible there

---

## 9. Current system topology (for the record)

```
GitHub:
  nunogt/obsidian-wiki    ← fork (engine + provisioning + docs)
  nunogt/kb-wiki          ← meta-knowledge vault (operator's LLM-wiki research)
  nunogt/kb-personal      ← personal vault (empty-scaffolded)
  nunogt/kb-ebury         ← operator's Ebury work vault
  (nunogt/kb-system — DELETED)

Local (any machine):
  <git-root>/obsidian-wiki        ← cloned from origin
  <git-root>/kb-<vault>           ← one per vault
  (contexts/ directory — RETIRED, does not exist anywhere)

Operator workflow:
  cd <git-root>/kb-<vault>
  claude --dangerously-skip-permissions
  # v3 hooks fire from .claude/settings.json (gitignored, materialized)
  # AGENTS.md symlink (gitignored) resolves to fork's schema
  # skills/ symlinks (gitignored) resolve to fork's .skills/
```

The system is two-repo-category, materialize-per-machine, vault-as-workspace. Karpathy's LLM-Wiki pattern instantiated as cleanly as the operator's domain allowed.

---

*End of log. 2026-04-15 concluded with an architecture simpler than it began.*
