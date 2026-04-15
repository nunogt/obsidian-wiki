# kb-system consolidation — expert-panel deliberation

*Drafted 2026-04-15. Operator's vision: "We probably don't need kb-system at all; entire system provisioning should be self-contained in the fork, with scripts to instantiate self-contained kb-vaults that Claude Code can execute on directly." Panel of five: Fowler, DHH, Kernighan, Hashimoto, Cantrill. Question: is the operator's instinct right, and if so, what's the cleanest execution?*

---

## 0. The vision in one paragraph

Today the system is three repos — `obsidian-wiki` (engine), `kb-system` (provisioning + harness + docs), `kb-<vault>` (data). The operator wants it to be two — `obsidian-wiki` (engine + provisioning + harness) and `kb-<vault>` (data, self-contained). The `contexts/<vault>/` indirection that today sits between engine and vault dissolves: the vault becomes its own Claude Code workspace, with `.env` + `.claude/` + symlinked `CLAUDE.md` materialized directly into it. Operator workflow becomes: `cd kb-ebury && claude` — no second CWD, no contexts/, no kb-system to even know about.

This panel evaluates the consolidation. We assume the operator is moving forward; the panel's job is to validate the direction, surface risks, and pin down the cleanest execution.

---

## 1. The four questions

### Q1. Where do scripts/templates/hooks live in the consolidated layout?

- **(1a)** `obsidian-wiki/scripts/` (top-level, separate from `.skills/`) — terminal-invoked tools alongside skills
- **(1b)** `obsidian-wiki/.skills/wiki-vault-new/` etc. — model the provisioning tools as Claude skills
- **(1c)** Split: terminal scripts in `obsidian-wiki/scripts/`, hook helpers in `obsidian-wiki/scripts/hooks/`, templates in `obsidian-wiki/scripts/templates/`
- **(1d)** A new top-level `obsidian-wiki/bin/` for executables, separate from the skill system

### Q2. Self-contained vault layout

- **(2a)** Materialize directly into vault root: `kb-ebury/.env`, `kb-ebury/.claude/settings.json`, `kb-ebury/.claude/skills/` symlinks, `kb-ebury/CLAUDE.md` symlink — all gitignored
- **(2b)** Materialize into a `.kb/` subdir: `kb-ebury/.kb/.env`, `kb-ebury/.kb/.claude/...` — keeps the vault root cleaner but Claude Code wouldn't find `.claude/` automatically
- **(2c)** Materialize into vault root, but use `${CLAUDE_PROJECT_DIR}` for hook command paths (avoids per-machine settings.json materialization)

### Q3. Migration of existing vaults (kb-wiki, kb-personal, kb-ebury)

- **(3a)** Migrate in place — run new materialization script against existing vaults, gitignore the new files
- **(3b)** Re-clone fresh — backup current state, re-clone vaults, re-materialize
- **(3c)** Hybrid coexistence — keep contexts/ working alongside vault-self-contained, deprecate over time

### Q4. What happens to kb-system?

- **(4a)** Delete the repo entirely after migrating its contents to the fork
- **(4b)** Archive (rename + add ARCHIVED.md) but keep accessible for git history
- **(4c)** Repurpose as a meta-vault — `kb-system` becomes `kb-meta` or similar, holding system-design knowledge
- **(4d)** Empty the repo (move contents to fork; leave a README pointer)

---

## 2. Panel introductions

### Martin Fowler
*Patterns of Enterprise Application Architecture, Refactoring, NoSQL Distilled. ThoughtWorks Chief Scientist. Lens here: bounded contexts, module boundaries, when separation pays for itself vs when it doesn't.*

### David Heinemeier Hansson (DHH)
*Creator of Ruby on Rails. Author of "The Majestic Monolith." 37signals/Basecamp founder. Outspoken against gratuitous microservice/multi-repo splits. Lens here: when a single coherent codebase beats a federation of small ones.*

### Brian Kernighan
*Co-author of The C Programming Language and The Unix Programming Environment. Bell Labs Unix pioneer. Lens here: "do one thing well" applies to repos too — but so does "small, sharp tools that compose."*

### Mitchell Hashimoto
*Founder of HashiCorp. Built Vagrant, Packer, Terraform, Consul, Vault, Nomad — each its own product but designed to compose. Lens here: when does a tool deserve its own repo, and when does separation become friction?*

### Bryan Cantrill
*DTrace co-creator (Sun), Joyent CTO, Oxide CTO. Strong opinions on operational rigor and observability. Lens here: from an ops perspective, where do you want to look when something breaks?*

---

## 3. Position statements

### Q1 — Where do scripts/templates/hooks live?

**Fowler:** *"This is a bounded-context question. Skills are units of agent capability — discoverable and invoked by Claude during a session. Provisioning scripts are operational tooling — invoked by humans from the terminal to set up or maintain the system. They serve different consumers, even if they share concepts. **(1c) — split.** `scripts/` for terminal tools, `.skills/` for in-session capabilities, `scripts/hooks/` for the harness-invoked Python helpers. The fact that all three end up in `obsidian-wiki/` is correct; the internal organization should respect their distinct purposes."*

Position: **(1c)**.

**DHH:** *"You're worried about cluttering the repo. Don't be. A 12-script `scripts/` directory at the root of `obsidian-wiki/` is fine — it's how every Rails app I've ever shipped looks. **(1c).** The 'one big repo with sensibly organized subdirectories' is a perfectly good architecture. Any further split is theater."*

Position: **(1c)**.

**Kernighan:** *"Scripts go where scripts have always gone — `bin/` or `scripts/`. Don't overthink it. The Unix tradition is `bin/` for executables; Claude Code's tradition is `.skills/` for skills. **(1c) is the natural compromise.** Don't put provisioning into `.skills/` (that conflates Claude-invoked with human-invoked); don't invent a new `bin/` (the `scripts/` convention is already there from kb-system). Just move it."*

Position: **(1c)**.

**Hashimoto:** *"At HashiCorp we put each tool in its own repo because they had genuinely different release cadences, audiences, and team owners. Here you have one engine + provisioning bound to that engine. They release together; they're maintained by one person; they have one consumer (you). **(1c).** The skill/script split inside one repo respects how the agent vs human interact with each piece, without inventing artificial separation."*

Position: **(1c)**.

**Cantrill:** *"Operationally, when something breaks I want to find it. **(1c) wins on grep-ability** — `scripts/hooks/stop_append.py` is exactly where I'd look for the Stop hook. `(1b) `.skills/wiki-vault-new/` is misleading — when a hook fails I'd be hunting in `.skills/` for a thing that has nothing to do with skills. Don't do that."*

Position: **(1c)**.

**Q1 consensus**: **Unanimous (1c).** No dissent.

---

### Q2 — Self-contained vault layout

**Fowler:** *"`.kb/` subdir (2b) seems clever but breaks Claude Code's discovery — it looks for `.claude/` in CWD, walking up. If you put `.claude/` inside `.kb/`, Claude Code from `kb-ebury/` finds nothing. (2c) `${CLAUDE_PROJECT_DIR}` is appealing — it would let `settings.json` be machine-agnostic — but introduces an upstream dependency and a fragility surface (panel rejected this in PORTABILITY-PANEL §4). **(2a) — materialize at vault root, gitignore the lot.** It's the simplest thing that works."*

Position: **(2a)**.

**DHH:** *"Vaults already have `.obsidian/` at root. Adding `.claude/` and `.env` and a few symlinks is no different in spirit — Obsidian users already accept their vaults have config artifacts at the root. **(2a).** The .gitignore is one-time pain for permanent UX gain."*

Position: **(2a)**.

**Kernighan:** *"`.kb/` (2b) is hiding things the user shouldn't have to look for. `${CLAUDE_PROJECT_DIR}` (2c) is depending on someone else's runtime substitution — fragile. **(2a) is honest:** the files are there, in plain sight, gitignored. If anything goes wrong you can just look. That's the Unix way."*

Position: **(2a)**.

**Hashimoto:** *"Vagrant put everything at the project root — `Vagrantfile`, `.vagrant/`. People grumbled at first; they got over it. **(2a).** Same playbook here: dotfiles + `.claude/` directory at vault root, gitignored. Operators learn the convention once."*

Position: **(2a)**.

**Cantrill:** *"(2a) again wins on inspectability. `cat kb-ebury/.env`, `cat kb-ebury/.claude/settings.json` — done. No need to remember where the materialized state lives."*

Position: **(2a)**.

**Q2 consensus**: **Unanimous (2a).** No dissent.

---

### Q3 — Migration of existing vaults

**Fowler:** *"In-place migration (3a) is a one-shot operation. The new materialization script runs against existing vaults; .gitignore stops the new files from leaking into git; everything coexists. (3b) re-clone is overkill — you'd lose nothing by migrating in place. (3c) hybrid is a deferred decision masquerading as a strategy. **(3a).**"*

Position: **(3a)**.

**DHH:** *"You're not changing the vault content. You're adding gitignored config files. (3a) is the only sensible answer. (3c) hybrid is the kind of 'never finish migrating' trap I've watched companies live in for years. Cut over."*

Position: **(3a)**.

**Kernighan:** *"(3a). The new layout is additive to the vault; the old contexts/ directory just disappears. No data migration. No risk."*

Position: **(3a)**.

**Hashimoto:** *"(3a), with one caveat: write a migration script that does it, don't ask the operator to do it manually. `obsidian-wiki/scripts/kb-vault-migrate-to-self-contained` or similar. Make it idempotent. Run it against each vault."*

Position: **(3a) + scripted migration**.

**Cantrill:** *"(3a). The script Hashimoto wants is what we already need anyway — `kb-vault-materialize <vault-path>` is the new regen script, and it works on existing vaults the same way it works on fresh ones. Migration is just the first run of the new tool against an existing vault."*

Position: **(3a) — migration is just the first materialization**.

**Q3 consensus**: **Unanimous (3a).** Hashimoto and Cantrill add the (consistent) refinement that migration ≡ first run of the new materialization script.

---

### Q4 — What happens to kb-system?

**Fowler:** *"The repo has historical value (the proposal docs, the deliberations). It also has near-zero ongoing value once contents migrate. **(4b) archive.** Keep the git history accessible; rename to `kb-system-archive` or add a top-level ARCHIVED.md pointing to the fork. Don't delete (the proposal docs are referenced by wiki pages and by other operators who might find this approach useful)."*

Position: **(4b)**.

**DHH:** *"(4a) delete. If it's not in active use, why pay the cognitive overhead of remembering it exists? Move what's worth keeping to the fork; abandon the rest. The 'archive in case' instinct is how repos accumulate forever. **Just delete.**"*

Position: **(4a)**. Dissent.

**Kernighan:** *"(4b) archive. The historical record matters — these proposals show how the system evolved. A future reader (or future you) will thank you. Use git's `archive` tag plus a README pointing forward."*

Position: **(4b)**.

**Hashimoto:** *"(4c) repurpose as a meta-vault is intriguing but conflates two concerns — the kb-system repo *was* the provisioning system; making it a vault now is reusing the name for something fundamentally different. Confusing. **(4b) archive** is honest about what happened: kb-system became unnecessary, we kept the records."*

Position: **(4b)**.

**Cantrill:** *"(4b) — and put the proposal docs into the fork's `docs/` directory before archiving, so they're discoverable in the live repo. Don't make a future operator dig through an archived repo to find the design rationale. **(4b) with content migration.**"*

Position: **(4b) + migrate docs into fork**.

**Q4 consensus**: **(4b) archive, 4-of-5.** DHH dissents (delete). Cantrill adds the refinement that proposal docs should migrate to fork's `docs/` so they're discoverable, not just archived.

---

## 4. Where the panel disagrees

Only one substantive disagreement: **Q4**, where DHH alone argues for outright deletion of `kb-system` against the 4-of-5 majority for archive.

His argument: *"If you're not actively using it, it accrues only cognitive overhead. Just delete."*

The majority's response (synthesized from Fowler/Kernighan/Hashimoto/Cantrill): the proposal docs in `kb-system/docs/` are referenced from the wiki pages, document the design rationale, and might be useful to a future operator (or future you) reverse-engineering the system. Archiving with redirect costs nothing and preserves the record.

**Resolution**: archive (4b) with Cantrill's refinement that proposal docs migrate to fork's `docs/` so they're discoverable. DHH's position acknowledged but not adopted.

---

## 5. Synthesized recommendation

| Q | Decision | Vote |
|---|---|---|
| **Q1** | **(1c)** `obsidian-wiki/scripts/` + `obsidian-wiki/scripts/hooks/` + `obsidian-wiki/scripts/templates/` (existing `.skills/` unchanged) | Unanimous |
| **Q2** | **(2a)** Materialize `.env` + `.claude/` + `CLAUDE.md`/`AGENTS.md`/`GEMINI.md` symlinks at vault root, all gitignored | Unanimous |
| **Q3** | **(3a)** In-place migration; the new materialization script is the migration tool | Unanimous |
| **Q4** | **(4b)** Archive `kb-system` after migrating proposal docs to fork's `docs/`; rename to indicate archive status | 4-of-5 (DHH dissents for delete) |

---

## 6. Concrete migration plan

### 6.1 New layout (target state)

```
obsidian-wiki/                                ← engine + provisioning + harness
├── .skills/                                  (existing — agent-invoked skills)
│   ├── wiki-ingest/SKILL.md
│   ├── wiki-query/SKILL.md
│   └── ... (12 total)
├── scripts/                                  (NEW — terminal tools)
│   ├── kb-vault-new                          (was kb-system/scripts/kb-vault-new)
│   ├── kb-vault-materialize                  (was kb-system/scripts/kb-contexts-regenerate, renamed)
│   ├── wiki-ar9av-update                     (already a skill — moved entirely or kept as skill)
│   ├── hooks/                                (was kb-system/scripts/hooks/)
│   │   ├── _common.py
│   │   ├── stop_append.py
│   │   ├── postcompact_append.py
│   │   ├── sessionstart_compact_remind.py
│   │   └── prompt_nudge.py
│   └── templates/                            (was kb-system/scripts/templates/)
│       ├── claude-settings.json
│       ├── profile.env
│       └── vault.gitignore
├── docs/                                     (NEW — migrated from kb-system/docs/)
│   ├── HARNESS-INTEGRATION-PROPOSAL-v3.md
│   ├── INGESTION-SIMPLIFICATION-PROPOSAL.md
│   ├── VISION-FIDELITY-ASSESSMENT.md
│   ├── PORTABILITY-PANEL.md
│   ├── CONSOLIDATION-PANEL.md
│   ├── ACTIVATION-GUIDE.md
│   └── ... (others)
├── AGENTS.md
├── README.md
└── ... (existing top-level files)

kb-ebury/                                     ← self-contained vault
├── .env                                      (gitignored — materialized)
├── .claude/                                  (gitignored — entire dir)
│   ├── settings.json                         (materialized)
│   └── skills/                               (symlinks to fork .skills/)
├── CLAUDE.md → ../obsidian-wiki/AGENTS.md    (gitignored symlink)
├── AGENTS.md → ../obsidian-wiki/AGENTS.md    (gitignored symlink)
├── GEMINI.md → ../obsidian-wiki/AGENTS.md    (gitignored symlink)
├── .gitignore                                (tracked — knows about all the above)
├── concepts/                                 (tracked — wiki content)
├── entities/
└── ... (other vault content)
```

### 6.2 What "self-contained" means

Operator runs from anywhere on the laptop:
```bash
cd ~/code/kb-ebury
claude --dangerously-skip-permissions
```
Claude Code finds `.claude/settings.json` → registers v3 hooks. Reads `AGENTS.md` symlink → loads schema + Continuous Fold-Back Convention. Uses `.claude/skills/*` symlinks → all 12 skills available. Hooks fire and write to `kb-ebury/.pending-fold-back.jsonl` (already gitignored from earlier work).

### 6.3 Migration phases

**Phase 1 — Move scripts to fork.** Copy `kb-system/scripts/` (including `hooks/` and `templates/`) into `obsidian-wiki/scripts/`. Update derivation logic in scripts (script-location-derived `KB_GIT_ROOT` still works — the scripts now live in the fork, so the derivation walks up to GIT_ROOT one level less).

**Phase 2 — Move docs to fork.** Copy all `kb-system/docs/*.md` into `obsidian-wiki/docs/`. These docs reference each other; no internal-link breakage.

**Phase 3 — Rename + adapt the materialization script.** `kb-vault-new` and `kb-vault-materialize` (the renamed `kb-contexts-regenerate`):
- Materialize directly into vault dirs (not into a sibling `contexts/` dir)
- Update the canonical `vault.gitignore` template to ignore `.env`, `.claude/`, and the 3 instruction-symlinks
- Profiles concept retires — vault config is **just** the materialized `.env` in the vault. Each vault owns its config.

**Phase 4 — Migrate existing vaults.** Run `kb-vault-materialize <vault-path>` against `kb-wiki/`, `kb-personal/`, `kb-ebury/`. Each gets its own `.env`, `.claude/`, instruction symlinks. Update each vault's `.gitignore` with the new entries.

**Phase 5 — Verify.** `cd ~/code/kb-ebury && claude` — verify hooks fire, queue grows, drain works. Repeat for kb-wiki and kb-personal.

**Phase 6 — Archive kb-system.**
- Add top-level `ARCHIVED.md` to kb-system explaining the consolidation, pointing at fork
- Rename GitHub repo: `kb-system` → `kb-system-archive`
- Optional: tag a final commit `v-final-pre-consolidation`

### 6.4 Rollback strategy

Each phase is reversible:

| Phase | Rollback |
|---|---|
| 1-2 (move scripts/docs to fork) | `git revert` in fork |
| 3 (script rename + adaptation) | Revert fork commit; old kb-system scripts still work because they were copied not moved (kept as deprecated stubs that exec the fork versions) |
| 4 (migrate existing vaults) | Vault `.env`/`.claude/` are gitignored; `rm -rf` removes them; old `contexts/<v>/` still exists |
| 5 (verify) | n/a — read-only |
| 6 (archive kb-system) | Rename repo back; revert ARCHIVED.md commit |

The sequencing (1→2→3→4→5→6) ensures no irreversible step until verification passes.

### 6.5 Net file movements

Files MOVED (no content change):
- `kb-system/scripts/kb-vault-new` → `obsidian-wiki/scripts/kb-vault-new`
- `kb-system/scripts/kb-contexts-regenerate` → `obsidian-wiki/scripts/kb-vault-materialize` (renamed)
- `kb-system/scripts/hooks/*.py` → `obsidian-wiki/scripts/hooks/*.py`
- `kb-system/scripts/templates/*` → `obsidian-wiki/scripts/templates/*`
- `kb-system/docs/*.md` → `obsidian-wiki/docs/*.md`
- `kb-system/profiles/*.env` → distributed into respective vaults' `.env` (now machine-specific)

Files DELETED from kb-system at archive time:
- All migrated contents (`scripts/`, `docs/`, `profiles/`)
- `contexts/` (already gitignored; cleanup local only)

Files ADDED to fork:
- All migrated contents in their new locations
- `obsidian-wiki/docs/CONSOLIDATION-PANEL.md` (this doc)

Files MODIFIED in fork:
- `README.md` — explain provisioning + scripts/ structure
- `AGENTS.md` — note self-contained vault layout

---

## 7. Risks + mitigations

| Risk | Severity | Mitigation |
|---|---|---|
| **Live session in current `contexts/wiki/` breaks during migration** | Medium | Migration script doesn't touch the existing contexts/ until verified; old contexts/ keeps working as long as kb-system scripts haven't been removed |
| **Symlinks at vault root pollute the Obsidian graph view** | Low | Obsidian respects `.gitignore`-style hidden config; CLAUDE.md/AGENTS.md/GEMINI.md as gitignored symlinks won't appear as "wiki pages." Verify by inspection on first migration. |
| **Hook helpers break because they read `cwd` from payload, which is now the vault dir not contexts/** | Low | Hook scripts already read `OBSIDIAN_VAULT_PATH` from `.env`; new `.env` is in the same place (CWD). No code change needed. |
| **kb-system archive loses discoverability** | Low | Cantrill's refinement: docs migrate to fork's `docs/` BEFORE archive; nothing important stays only in archived repo |
| **Migration script bug corrupts a vault's tracked content** | High but bounded | Migration only adds gitignored files to vault root; never touches `concepts/`, `entities/`, etc. Verify with `git status` before and after — any non-`.gitignore` change is a bug, abort and rollback. |
| **Operator's mental model takes time to adjust** | Trivial | Two repos instead of three is genuinely simpler. README in fork covers the topology in one paragraph. |

---

## 8. Self-validate / critique / refine

### 8.1 Self-validate

- **Does the recommendation align with operator's stated vision?** Operator: *"entire system provisioning self-contained in fork with scripts to instantiate self-contained kb-vaults."* Recommendation: scripts in fork (Q1), self-contained vaults (Q2), scripted migration (Q3), archive kb-system (Q4). Direct match. ✓
- **Is the panel's composition appropriate?** Five voices spanning architecture (Fowler), pragmatism (DHH), Unix roots (Kernighan), multi-product systems (Hashimoto), ops (Cantrill). Balanced enough to surface real disagreement (Q4). ✓
- **Are the expert positions defensible per their actual public work?** Fowler's bounded-context lens, DHH's anti-fragmentation, Kernighan's "honest files," Hashimoto's HashiCorp-product split rationale, Cantrill's grep-ability concern — all consistent with their published views. ✓
- **Does the migration plan respect what's already shipped (v3 hooks, INGESTION-SIMPLIFICATION, VFA ranks)?** Yes — none of those are touched; this is a layout consolidation only. ✓

### 8.2 Critique

1. **Am I papering over the genuine cost of moving 7+ files across repo boundaries?** The git history for those files lives in kb-system. After migration to fork, future `git log` on (say) `obsidian-wiki/scripts/hooks/stop_append.py` won't show its kb-system history. Fix: either accept the loss (small) or use `git filter-repo` or `git mv` with history preservation (complex). Recommend acceptance — the historical context is captured in the proposal docs that migrate alongside.
2. **Is `obsidian-wiki/scripts/` likely to confuse upstream contributors?** ar9av/upstream doesn't have provisioning scripts. Our fork now ships them. If upstream pulls from us in a future hypothetical merge, they'd inherit the scripts. This is fine — they'd see the value. If they don't want them, they remove the dir.
3. **Have I considered keeping kb-system as a thin shim (4d empty-with-pointer)?** The panel rejected this implicitly in favor of (4b) archive. (4d) is functionally similar but creates a dead repo with a redirect — more confusing than an honest archive. Stick with (4b).
4. **Is migration actually as smooth as claimed?** The Phase-by-Phase plan has 6 steps. Each is reversible. The riskiest is Phase 4 (touching existing vault dirs). Mitigated by gitignored-only changes and `git status` verification. Acceptable risk.
5. **What about the operator's currently-running Claude session in `contexts/wiki/`?** They'd need to exit and restart from the new vault location post-migration. Same as the v3 activation flow — restart is the friction.
6. **Operator's workflow change**: today `cd kb-system/contexts/wiki && claude`; post-migration `cd kb-wiki && claude`. Net less typing, fewer dirs to remember. ✓

### 8.3 Refinement

- Add an explicit **deprecation period** to Phase 6: keep kb-system scripts as no-op wrappers that print *"this script has moved to obsidian-wiki/scripts/<name>; running it there"* and exec the fork version. Maintain for ~1 month, then remove.
- **Make `kb-vault-materialize` accept multiple paths** (`kb-vault-materialize ~/code/kb-*`) so the operator can re-materialize all vaults after a fork update with one command.
- Add a **README.md table** in the fork mapping old paths to new paths for anyone who has old shell history with `kb-system/...` paths.

---

## 9. Decision request

If the panel's synthesis matches your vision:

- ✅ **Approve "consolidate per panel"** — I execute Phases 1-6 as described
- Total work: ~1.5 hours including verification on the 3 existing vaults
- Hashimoto/Cantrill refinements: scripted migration (already in plan), proposal docs migrate to fork before archive (Phase 2 + Phase 6)

If you want to diverge:

- **(A) DHH wins** — outright delete kb-system instead of archive
- **(B) Keep contexts/ as a coexistence option** — both vault-self-contained AND contexts/ supported (panel rejected as deferred-decision-trap; revisit only if there's a use case I'm missing)
- **(C) Skip the script rename** — keep `kb-contexts-regenerate` name in the fork (purely cosmetic; rename was for clarity, not necessity)

---

## 10. Appendix — what doesn't change

For clarity, the following remain untouched by this consolidation:

- **v3 hook architecture** — same Stop/PostCompact/SessionStart:compact/UserPromptSubmit hooks; same Python helpers (just relocated)
- **INGESTION-SIMPLIFICATION** — unified `/wiki-ingest` skill is the same; `--drain-pending` mode same
- **VFA ranks 2/2.5/3** — divergence check, post-ingest auto-lint, two-output rule all unchanged
- **Vault content** — concepts/, entities/, references/, etc. untouched
- **Wiki linting + provenance machinery** — same
- **Fork's existing 12 skills** — same
- **GitHub repos** — kb-wiki, kb-personal, kb-ebury all stay (same names, same remotes, no force-pushes); only kb-system is renamed to indicate archive

This is a **layout consolidation, not a feature change**. Every capability the system has today survives. The change is *where* things live and *how* the operator enters the system.

---

*End of panel deliberation. Awaiting operator decision.*
