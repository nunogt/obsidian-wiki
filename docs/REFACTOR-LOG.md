# Refactor execution log

*Executed 2026-04-14. Flatten + concurrent-sessions refactor described in
`research/REFACTOR-PROPOSAL.md`. This log moved to `research/` after
completion.*

Operator answers:
- Symlinks: **absolute** (regenerated per-machine)
- Proposal docs disposition: **all three to `research/`** as historical scaffolding
- Log cadence: **live at kb-system root during execution**, moves to `research/` at the end

---

## Phase 0 — verification

*completed*

All three repos clean and in sync with remote at start:

```
kb-system:   0 ahead / 0 behind  (2 untracked proposal docs → moved in Phase 1)
kb-wiki:     0 ahead / 0 behind
kb-personal: 0 ahead / 0 behind
```

---

## Phase 1 — stage path changes in kb-system

*completed — commit `acd1bd2` pushed*

**Scripts:**
- Deleted: `scripts/wiki-switch`, `scripts/wiki-run`
- Created: `scripts/kb-contexts-regenerate`
- Rewritten: `scripts/kb-vault-new` (flat paths + context generation)
- Rewritten: `scripts/wiki-ar9av-update` (drops `bash setup.sh`, calls `kb-contexts-regenerate`)
- Updated: `scripts/templates/profile.env`

**Profiles:**
- `profiles/wiki.env`, `profiles/personal.env` — vault paths updated to flat layout

**Docs:**
- `README.md` — rewritten for flat layout + CWD-based workflow
- `research/ar9av-self-hosted-architecture.md` — §2 example path updated
- `research/BOOTSTRAP-LOG.md` — Addendum 3 documents this refactor

**Proposal docs → `research/`:**
- `BOOTSTRAP-PROPOSAL.md`, `PROPOSAL-CONCURRENT-SESSIONS.md`, `REFACTOR-PROPOSAL.md`

**`.gitignore`:** Replaced `vaults/` with `contexts/`; added defensive ignores.

---

## Phase 2 — vault manifests

*completed — kb-wiki commit `8ea4db6` pushed; kb-personal no-op*

```
sed -i 's|/mnt/host/shared/git/kb/research/|/mnt/host/shared/git/kb-system/research/|g' \
    /mnt/host/shared/git/kb-wiki/.manifest.json
```

Source-dict keys migrated for all 5 tracked sources. JSON validity
verified (`python3 -m json.tool`). kb-personal has zero tracked sources
(empty vault); no-op.

---

## Phase 3 — backup + flatten

*completed*

**Backup:** `/tmp/kb-backup-<ts>/` — full `cp -a` snapshot of
`/mnt/host/shared/git/kb/` pre-move (cleaned in Phase 6).

**Moves:**
```
mv kb/ar9av-obsidian-wiki → /mnt/host/shared/git/ar9av-obsidian-wiki
mv kb/vaults/wiki         → /mnt/host/shared/git/kb-wiki
mv kb/vaults/personal     → /mnt/host/shared/git/kb-personal
rmdir kb/vaults
mv kb                     → /mnt/host/shared/git/kb-system
```

**Global state removed:**
- `rm -rf ~/.obsidian-wiki/`
- `rm ~/.claude/skills/wiki-update`
- `rm ~/.claude/skills/wiki-query`

**Note on harness placeholder:** the Claude Code harness primary working
directory was `/mnt/host/shared/git/kb/` which became invalid post-move;
created an empty placeholder at that path so subsequent shell operations
could still spawn. Post-session, safe to `rmdir /mnt/host/shared/git/kb/`.

---

## Phase 4 — clean-slate reproduction

*completed*

Moved flattened state aside to `/tmp/kb-verify-flat-<ts>/`, cloned all
four repos fresh from remote, regenerated contexts.

**Fresh clone heads (at time of Phase 4):**
- ar9av-obsidian-wiki: 61 commits @ `ce54dcb`
- kb-system: 6 commits @ `acd1bd2`
- kb-wiki: 9 commits @ `8ea4db6`
- kb-personal: 1 commit @ `33f14ff`

**`kb-contexts-regenerate` run:** 2 contexts regenerated, 16 skills each.

**No `bash setup.sh`** — confirmed obsolete under this architecture.

---

## Phase 5 — verification

*completed — all 7 checks pass*

1. ✓ Symlink resolution — CLAUDE.md / AGENTS.md / GEMINI.md / .env all resolve
2. ✓ Skills — 16 linked in each context, 0 broken
3. ✓ `.env` content readable via symlink (profile content correct)
4. ✓ Global state absent (`~/.obsidian-wiki`, global `wiki-update`, `wiki-query`)
5. ✓ Git history intact (kb-system 6 commits; kb-wiki 9; kb-personal 1)
6. ✓ Vault manifest paths updated to `/kb-system/research/*` post-sed
7. ✓ Vault `.gitignore` present in both vaults

Concurrent-session smoke test (runtime) deferred to operator's normal
workflow — launch claude in `kb-system/contexts/wiki` and
`kb-system/contexts/personal` simultaneously and confirm no race.

---

## Phase 6 — cleanup

*completed*

- `/tmp/kb-backup-<ts>/` — deleted (2.6 MB reclaimed)
- `/tmp/kb-verify-flat-<ts>/` — deleted (2.6 MB reclaimed)
- Harness placeholder at `/mnt/host/shared/git/kb/` — left in place for
  the remainder of the current Claude session; operator can
  `rmdir /mnt/host/shared/git/kb/` post-session

---

## Final layout

```
/mnt/host/shared/git/
├── ar9av-obsidian-wiki/   upstream (github.com/Ar9av/obsidian-wiki)
├── kb-system/             this repo (github.com/nunogt/kb-system)
│   └── contexts/          gitignored, derived per-machine
│       ├── wiki/          → CLAUDE.md + skills + .env symlinks
│       └── personal/
├── kb-wiki/               wiki vault (github.com/nunogt/kb-wiki)
└── kb-personal/           personal vault (github.com/nunogt/kb-personal)
```

## Usage post-refactor

```bash
# wiki session
cd /mnt/host/shared/git/kb-system/contexts/wiki
claude --dangerously-skip-permissions
> /wiki-ingest
> lint the wiki and commit

# concurrent personal session (different terminal)
cd /mnt/host/shared/git/kb-system/contexts/personal
claude --dangerously-skip-permissions
> /wiki-query "recent themes"

# create a new vault
/mnt/host/shared/git/kb-system/scripts/kb-vault-new <name>
cd /mnt/host/shared/git/kb-system/contexts/<name>
claude --dangerously-skip-permissions
> /wiki-setup

# pull upstream ar9av
/mnt/host/shared/git/kb-system/scripts/wiki-ar9av-update
```

No `wiki-switch`. No `wiki-run`. No `~/.obsidian-wiki/config`. Two
terminals in two context directories work concurrently on different
vaults.
