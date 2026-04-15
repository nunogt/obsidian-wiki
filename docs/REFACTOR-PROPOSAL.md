# Refactor proposal: flatten + concurrent-sessions (combined, reviewed)

*For your review. Supersedes `PROPOSAL-CONCURRENT-SESSIONS.md` — folds that
change in. Nothing executed. Revised after a deep code review — §4.5
enumerates what I verified and the three material findings that changed
the plan.*

---

## 1. What you asked for (reiterated precisely)

1. Flatten the nested `/mnt/host/shared/git/kb/` tree into sibling repos
   at `/mnt/host/shared/git/`
2. Rename directory names to match remote names (`kb-wiki`, `kb-personal`,
   `kb-system`, `ar9av-obsidian-wiki`)
3. Fold in the concurrent-sessions refactor at the same time (CWD-based
   profile selection, contexts dir, no `wiki-switch`/`wiki-run`)
4. Push everything, then clean-slate clone from remote as a reproduction
   test
5. Backup the current tree, verify, delete backup

**I'm adding two things** to this plan that I don't think you'll object
to but flag for review:

- **A pre-refactor push verification step** — so we never lose work to a
  failed push
- **A manifest-path cleanup pass** — `.manifest.json` in each vault
  contains absolute paths that become stale after the flatten (details §5)

---

## 2. Target layout

```
/mnt/host/shared/git/
├── ar9av-obsidian-wiki/    ← upstream clone (gh.com/Ar9av/obsidian-wiki)
├── kb-system/              ← infrastructure repo (gh.com/nunogt/kb-system)
│   ├── scripts/
│   │   ├── kb-vault-new
│   │   ├── kb-contexts-regenerate         (NEW — from concurrent-sessions proposal)
│   │   ├── wiki-ar9av-update
│   │   └── templates/
│   │       ├── profile.env
│   │       └── vault.gitignore
│   ├── profiles/
│   │   ├── wiki.env
│   │   └── personal.env
│   ├── research/
│   │   ├── karpathy-llm-wiki-research.md
│   │   ├── karpathy-llm-wiki-panel-review.md
│   │   ├── ar9av-self-hosted-architecture.md
│   │   ├── _review-rubric.md
│   │   └── BOOTSTRAP-LOG.md
│   ├── contexts/           (GITIGNORED — derived per-machine state)
│   │   ├── wiki/
│   │   └── personal/
│   ├── README.md
│   └── .gitignore
│
├── kb-wiki/                ← wiki vault (gh.com/nunogt/kb-wiki) — was vaults/wiki/
│   ├── .git/
│   ├── .obsidian/
│   ├── .manifest.json      (paths updated)
│   ├── concepts/ entities/ skills/ references/ synthesis/ journal/ projects/
│   ├── _archives/ _meta/ _raw/
│   ├── index.md  log.md
│   └── .gitignore
│
├── kb-personal/            ← personal vault (gh.com/nunogt/kb-personal) — was vaults/personal/
│   └── (same shape as kb-wiki/)
│
├── obsidian-git/           ← unrelated, your pre-existing clone
└── ... other projects ...  ← unrelated
```

**Key naming convention change:**
- **Remote name = local directory name**, no more mismatch
- `vaults/` prefix goes away; each vault is a sibling at the root
- The `kb-` prefix appears everywhere: repo, directory, profile name

### `contexts/` placement: inside `kb-system/`, not at root

Rationale: `contexts/` is **derived per-machine state**, owned by kb-system's
tooling (`kb-contexts-regenerate`). Keeping it inside kb-system means:
- One `.gitignore` entry covers it
- `kb-contexts-regenerate` lives next to the thing it regenerates
- Nothing at `/mnt/host/shared/git/` level is derived state

Paths inside context dirs use **absolute symlinks** (regenerated per
machine by the script), same pattern ar9av's `setup.sh` uses. Three-dot
relative symlinks would work too but are harder to read.

---

## 3. Path changes required

### In scripts

All four scripts currently hardcode `KB=/mnt/host/shared/git/kb`. Change to:

```bash
KB_SYSTEM=/mnt/host/shared/git/kb-system
GIT_ROOT=/mnt/host/shared/git
AR9AV=$GIT_ROOT/ar9av-obsidian-wiki
PROFILES=$KB_SYSTEM/profiles
CONTEXTS=$KB_SYSTEM/contexts
```

And use `$GIT_ROOT/kb-$name` for vault paths instead of
`$KB/vaults/$name`.

### In profile files

Before:
```
OBSIDIAN_VAULT_PATH=/mnt/host/shared/git/kb/vaults/wiki
OBSIDIAN_SOURCES_DIR=/mnt/host/shared/git/kb/research
```

After:
```
OBSIDIAN_VAULT_PATH=/mnt/host/shared/git/kb-wiki
OBSIDIAN_SOURCES_DIR=/mnt/host/shared/git/kb-system/research
```

### In documentation

`README.md`, `research/ar9av-self-hosted-architecture.md`, and several
places in `research/BOOTSTRAP-LOG.md` reference the old paths. They need
updating to the new convention.

### In `.gitignore`

Current `vaults/` entry becomes meaningless (no more `vaults/` dir in
kb-system). Replace with the `contexts/` ignore.

### In vault `.manifest.json` — the tricky one (**verified**)

Inspected `.manifest.json` structure. Top-level shape:

```
{version, created, stats, sources, projects}
```

The `sources` dict uses **absolute paths as keys**:

```
"/mnt/host/shared/git/kb/research/karpathy-llm-wiki-research.md": {
  "ingested_at", "size_bytes", "modified_at", "content_hash",
  "source_type", "project",
  "pages_created": ["entities/karpathy.md", ...],
  "pages_updated": [],
  "history": [{"ingested_at", "content_hash", "size_bytes", "note"}, ...]
}
```

**Verified clean** (don't need to touch):
- `pages_created` / `pages_updated` — vault-relative strings (`entities/karpathy.md`)
- `history` entries — no paths, only timestamps/hashes/notes
- `stats`, `projects` — no absolute paths

**Must update** (sed pass):
- Top-level `sources` dict keys only

```bash
sed -i 's|/mnt/host/shared/git/kb/research/|/mnt/host/shared/git/kb-system/research/|g' \
    /mnt/host/shared/git/kb-wiki/.manifest.json
python3 -m json.tool /mnt/host/shared/git/kb-wiki/.manifest.json > /dev/null  # validate
```

kb-personal's manifest tracks zero sources (empty vault). No-op.

### Page-frontmatter `sources:` fields — verified non-issue

Inspected example: `concepts/fold-back-loop.md` has
`sources: ["research/karpathy-llm-wiki-research.md", ...]`. These are
**vault-relative annotations** — labels, not resolvable file handles. No
ar9av skill reads them as file paths. Leave alone; they're purely
provenance metadata.

---

## 4.5 Deep code review — what I verified and three findings

Before finalizing this plan I audited every piece of state that could hold
a path reference or shared config. Summary of what I checked:

### Verified clean (no changes needed upstream)

- **ar9av `.skills/*/SKILL.md`** — grep across all 16 skills: zero
  references to `/mnt/host/shared/git/kb/`. Skills are parent-directory
  agnostic; they read relative `.env` or `~/.obsidian-wiki/config`, never
  anything coupling to our layout.
- **ar9av `setup.sh`** — uses `$SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"`
  to derive the ar9av path dynamically. Zero assumptions about parent
  directory.
- **Vault `.obsidian/*.json`** — contains UI settings; grep `/mnt`
  returns nothing. Clean.
- **Vault page-frontmatter `sources:` fields** — vault-relative labels,
  no file-resolution. No-op.

### Enumerated (need path updates, but straightforward)

- **4 scripts** (`wiki-switch`, `wiki-run`, `wiki-ar9av-update`,
  `kb-vault-new`) — each hardcodes `KB=/mnt/host/shared/git/kb`. Also
  `scripts/templates/profile.env` has an example path. All 5 need update
  or replacement.
- **2 profile files** (`profiles/wiki.env`, `profiles/personal.env`) —
  both have absolute paths.
- **Research docs with live path refs**:
  - `research/BOOTSTRAP-LOG.md` — 6 references (incl. `vaults/work/` from
    early-bootstrap era; historical, probably leave those, but update new
    references that appear post-rename)
  - `research/ar9av-self-hosted-architecture.md` — 1 reference (example
    only, in §2 constraints)
- **README.md** — 3 references to current path
- **`BOOTSTRAP-PROPOSAL.md`** — many references but this is historical
  scaffolding. Leave alone.
- **Each vault `.manifest.json`** — top-level `sources` dict keys only
  (see §3).

### Three material findings that change the plan

**Finding 1 — `~/.obsidian-wiki/config` must be DELETED, not kept as
default.**

`wiki-ingest/SKILL.md:18` and `wiki-query/SKILL.md:18` read
`~/.obsidian-wiki/config` as **preferred**, falling back to `.env` only
if it's missing. Keeping it alive (with any vault path) would route all
concurrent sessions through whatever profile it pointed at, regardless of
CWD context — defeating the entire refactor.

Phase 3 explicitly:
```bash
rm -f ~/.obsidian-wiki/config
rmdir ~/.obsidian-wiki 2>/dev/null || true
```

**Finding 2 — `wiki-update` is not recoverable under this architecture.**

`wiki-update/SKILL.md:16-19` reads `~/.obsidian-wiki/config` with **no
fallback**. Message on missing file: *"tell the user to run bash setup.sh
from their obsidian-wiki repo first"*.

Since we're deleting the global config (Finding 1), `wiki-update` is
permanently broken in the new architecture. Two paths:

- **Accept** (recommended). You confirmed you don't use it; it was
  designed for "sync any project into one wiki" single-profile setups.
  In a multi-vault world, `/wiki-ingest` with a specific source path is
  the correct primitive anyway.
- **Fork + maintain** a version of wiki-update that reads `.env` first.
  Rejected: ongoing upstream merge burden.

`kb-contexts-regenerate` still symlinks wiki-update into each context
(keeping the 16-skill set complete). If invoked, it will simply error
with the "run setup.sh" message — user knows not to invoke it.

**Finding 3 — `bash setup.sh` should NOT run in Phase 4 (reproduction).**

The draft plan had "after cloning ar9av upstream, `bash setup.sh`". I
wrote that reflexively from the current pattern. Under the new
architecture, setup.sh's four jobs are all obsolete or actively harmful:

| setup.sh job | New architecture |
|---|---|
| Create `.env` from `.env.example` | **Obsolete** — profile files live in `kb-system/profiles/` |
| Write `~/.obsidian-wiki/config` | **Harmful** — re-introduces the shared-state bottleneck (Finding 1) |
| Symlink ar9av's in-repo `.claude/skills/` etc. | **Obsolete** — we use `contexts/<name>/.claude/skills/` generated by `kb-contexts-regenerate` |
| Install global `~/.claude/skills/wiki-{update,query}` | **Harmful** — re-introduces global skill routing (Finding 1) |

**Phase 4 drops setup.sh entirely.** Reproduction uses only
`kb-contexts-regenerate`. Correspondingly, `wiki-ar9av-update` drops its
`bash setup.sh` step too.

---

## 5. Pre-refactor verification (part 1)

Before touching anything, confirm remote state is current:

```bash
# kb-system
cd /mnt/host/shared/git/kb
git status                         # clean?
git fetch && git log HEAD..@{u}    # any incoming we don't have?
git log @{u}..HEAD                  # any outgoing not pushed?

# each vault
for v in vaults/wiki vaults/personal; do
  cd /mnt/host/shared/git/kb/$v
  git status
  git fetch && git log HEAD..@{u}
  git log @{u}..HEAD
done
```

If any repo has unpushed commits or uncommitted state: push/commit first.
If remote has commits we don't: pull first. Only proceed when all three
repos are clean and current.

**Why:** if the refactor or clone-from-remote step fails for any reason,
we want to know the remote is the true state. Backup is a safety net, not
the authority.

---

## 5. Refactor sequence

Executed as one session; user waits for completion.

### Phase 0: verification (§4)

### Phase 1: prepare the new-architecture changes in the current kb-system

1. **Write the new scripts in-place** (still at `/mnt/host/shared/git/kb/scripts/`):
   - Delete `wiki-switch` and `wiki-run`
   - Add `kb-contexts-regenerate`
   - Rewrite `kb-vault-new` (update paths, drop `wiki-switch` call, add
     context generation)
   - Rewrite `wiki-ar9av-update` (update paths, add contexts-regen step)
2. **Update profile files** (`profiles/wiki.env`, `profiles/personal.env`)
   with new paths
3. **Update docs** (README, research/ar9av-self-hosted-architecture.md,
   research/BOOTSTRAP-LOG.md addendum) with new paths
4. **Update `.gitignore`** — replace `vaults/` with `contexts/`
5. **Commit** to kb-system with a clear message
6. **Push** — remote now has the new architecture

This kb-system commit is valid AT the new paths, not at the old paths
yet. That's fine — the scripts would fail if run right now, but we're
not running them. The next step moves everything to match.

### Phase 2: update vault manifests + push

For each vault:
1. `sed -i` `.manifest.json` to rewrite research path
2. Commit with message "chore: update manifest paths for kb-system flatten"
3. Push

Both vaults now on remote with updated manifests.

### Phase 3: backup + flatten

```bash
cp -a /mnt/host/shared/git/kb /tmp/kb-backup-$(date +%Y%m%d-%H%M%S)
```

`cp -a` preserves symlinks, permissions, timestamps. Backup is a complete
snapshot.

Then flatten:

```bash
cd /mnt/host/shared/git
mv kb/ar9av-obsidian-wiki ./ar9av-obsidian-wiki
mv kb/vaults/wiki        ./kb-wiki
mv kb/vaults/personal    ./kb-personal
mv kb                    ./kb-system         # the outer repo becomes kb-system
# kb-system now has: scripts/, profiles/, research/, README.md, .gitignore, .git/
# (no more vaults/ subdir; it's empty and will be cleaned up)
```

**Caveat:** step 4 renames `kb/` (the directory containing everything) to
`kb-system/`. The `vaults/` subdir inside it was moved out in steps 2-3,
so `kb-system/` should now contain only the kb-system content. Let's
verify with `ls kb-system/` showing no `vaults/` dir.

### Phase 4: clean-slate test (reproduce from remote)

Move the flattened layout aside, clone fresh:

```bash
mv /mnt/host/shared/git/ar9av-obsidian-wiki  /tmp/kb-verify-flat-ar9av
mv /mnt/host/shared/git/kb-system            /tmp/kb-verify-flat-kb-system
mv /mnt/host/shared/git/kb-wiki              /tmp/kb-verify-flat-kb-wiki
mv /mnt/host/shared/git/kb-personal          /tmp/kb-verify-flat-kb-personal
```

Clone fresh (**no `bash setup.sh` — Finding 3**):

```bash
cd /mnt/host/shared/git
git clone git@github.com:nunogt/kb-system.git
git clone https://github.com/Ar9av/obsidian-wiki.git ar9av-obsidian-wiki
git clone git@github.com:nunogt/kb-wiki.git
git clone git@github.com:nunogt/kb-personal.git
cd kb-system
scripts/kb-contexts-regenerate            # rebuild derived contexts/
# No ar9av setup.sh — it's obsolete in this architecture.
```

### Phase 5: verification tests

1. **Symlink resolution:**
   ```
   ls -la contexts/wiki/             # CLAUDE.md, AGENTS.md, GEMINI.md, .env, .claude/
   readlink contexts/wiki/.env       # should resolve to ../profiles/wiki.env (or absolute equivalent)
   cat contexts/wiki/.env            # follow the symlink → verify post-refactor paths
   ls contexts/wiki/.claude/skills/  # 16 skill symlinks, all resolving into ar9av-obsidian-wiki/.skills/
   ```

2. **Global state absence:**
   ```
   test -f ~/.obsidian-wiki/config && echo "FAIL: global config present" || echo "OK: deleted"
   test -L ~/.claude/skills/wiki-update && echo "FAIL: global wiki-update present" || echo "OK: gone"
   test -L ~/.claude/skills/wiki-query && echo "FAIL: global wiki-query present" || echo "OK: gone"
   ```

3. **Single-session smoke test (wiki):**
   ```
   cd /mnt/host/shared/git/kb-system/contexts/wiki
   claude --dangerously-skip-permissions
   > what's the vault path you're targeting?  # should answer /mnt/host/shared/git/kb-wiki
   > /wiki-query "what is the three-layer architecture?"  # should return answer with wikilinks
   ```

4. **Concurrent test:**
   - Terminal A: `cd contexts/wiki` → claude → `> lint the wiki` → verify target = `/kb-wiki`
   - Terminal B (simultaneously): `cd contexts/personal` → claude → `> /wiki-query "test"` → verify target = `/kb-personal`
   - Confirm no race: both complete cleanly, no "unexpected path" errors

5. **Expected failure (Finding 2):**
   ```
   > /wiki-update
   # EXPECTED: skill asks you to run bash setup.sh. This confirms the
   # architectural choice is in effect; don't "fix" this.
   ```

6. **Git history intact:**
   ```
   cd /mnt/host/shared/git/kb-wiki && git log --oneline   # all prior commits present
   cd /mnt/host/shared/git/kb-personal && git log --oneline
   ```

7. **`kb-vault-new` works end-to-end:**
   ```
   scripts/kb-vault-new kb-sandbox "test vault"
   # verify: profile, vault dir, github remote, context dir all created
   # then clean up:
   gh repo delete kb-sandbox --yes
   rm -rf ../kb-sandbox
   rm profiles/kb-sandbox.env
   rm -rf contexts/kb-sandbox
   ```

8. **`wiki-ar9av-update` smoke test:**
   ```
   scripts/wiki-ar9av-update
   # expect: "already current" (we're on same commit as Ar9av upstream)
   ```

### Phase 6: delete backup and verify-staging

If all tests pass:
```bash
rm -rf /tmp/kb-backup-*
rm -rf /tmp/kb-verify-flat-*
```

If any test fails: rollback (§6).

---

## 6. Rollback

If phase 4 or 5 fails:

```bash
# kill the clean clones
rm -rf /mnt/host/shared/git/ar9av-obsidian-wiki
rm -rf /mnt/host/shared/git/kb-system
rm -rf /mnt/host/shared/git/kb-wiki
rm -rf /mnt/host/shared/git/kb-personal

# restore the flattened-but-not-yet-wiped state from /tmp
mv /tmp/kb-verify-flat-ar9av      /mnt/host/shared/git/ar9av-obsidian-wiki
mv /tmp/kb-verify-flat-kb-system  /mnt/host/shared/git/kb-system
mv /tmp/kb-verify-flat-kb-wiki    /mnt/host/shared/git/kb-wiki
mv /tmp/kb-verify-flat-kb-personal /mnt/host/shared/git/kb-personal

# OR full-rollback to original /mnt/host/shared/git/kb layout:
rm -rf /mnt/host/shared/git/{ar9av-obsidian-wiki,kb-system,kb-wiki,kb-personal}
mv /tmp/kb-backup-<timestamp> /mnt/host/shared/git/kb
```

Two rollback paths:
- **Light** (phases 4/5 failed but phases 1-3 OK): restore from
  `/tmp/kb-verify-flat-*`
- **Heavy** (something bad happened during phases 1-3): restore from
  `/tmp/kb-backup-<timestamp>`

The remote state on GitHub also serves as ultimate authority — worst
case, `git clone` from remote recovers everything that was pushed.

---

## 7. Risk assessment

| Risk | Severity | Mitigation |
|---|---|---|
| Push fails mid-refactor | Low | Phase 0 verifies state upfront; abort if remote isn't clean |
| Clone from remote has bug we didn't catch | Low | Phase 4 verifies before we delete anything; backup still exists |
| Manifest sed produces malformed JSON | Low | `sed` on a known-format path string is safe; `python3 -m json.tool .manifest.json` verifies post-edit |
| Concurrent-sessions architecture doesn't actually work end-to-end | Medium | Phase 5 tests it specifically before cleanup |
| Scripts have a bug at new paths | Medium | Phase 5 runs them; easy to spot and fix |
| ar9av's `setup.sh` misbehaves on the flattened layout | Low-Medium | ar9av doesn't know or care about parent dir structure; its symlinks are created relative to itself |

**Biggest risk:** a subtle path reference in some skill or config I
haven't caught. Mitigation: the backup + verify-staging pattern makes
rollback a matter of `rm -rf` and `mv`.

---

## 8. What this gets us

**Cleanliness:**
- Flat repo siblings at `/mnt/host/shared/git/` — no nesting
- Directory names match GitHub remote names exactly
- `kb-` prefix identifies the family at a glance
- kb-system repo contains only system state; vaults are fully external

**Concurrency (from the folded-in proposal):**
- CWD-based profile selection
- Two concurrent Claude sessions, different vaults
- No `wiki-switch` / `wiki-run`
- `contexts/` per-machine derived state, regenerated by tooling

**Script surface:**
- 4 scripts (kb-vault-new, kb-contexts-regenerate, wiki-ar9av-update, templates/)
- All infrastructure; zero Claude wrappers

**Verified reproducibility:**
- Phase 4's fresh clone from remote PROVES the setup can be rebuilt on
  any machine from three `git clone` commands + `kb-contexts-regenerate`

---

## 9. Open questions before I execute

1. **Atomic OK?** — the refactor is ~30 minutes of non-interactive work.
   Is there anything you need to do in the current kb/ tree during that
   window? If so, do it now or tell me to pause before destructive steps.

2. **Contexts symlinks: absolute or relative?** — default absolute (regen
   per-machine, matches ar9av's pattern). Relative works but 3+ `../`
   levels are awkward. Confirm unless you prefer relative.

3. **`pages_created` / `pages_updated` audit** — verified (§3 & §4.5):
   these are vault-relative strings, not affected by the flatten. No
   audit needed. Resolved.

4. **Delete `~/.obsidian-wiki/config` and `~/.claude/skills/wiki-*`** —
   per Finding 1, these MUST go (not "optional"). Phase 3 handles this.

5. **`wiki-update` becoming non-functional** (Finding 2) — confirmed
   acceptable per your earlier statement that you don't use it. Documented
   in the refactor log addendum so future-you knows why it errors out.

6. **Commit message conventions** — `refactor(flatten): ...` for
   kb-system, `chore(paths): ...` for vault manifest updates,
   `docs: ...` for README / research doc path updates. Fine?

7. **BOOTSTRAP-PROPOSAL.md disposition** — it's 14 KB of historical
   content with many old paths. Options: (a) move to `research/` so it
   gets ingested as historical context next time, (b) leave at root as
   historical scaffolding (per earlier comment), (c) delete (history is
   also captured by BOOTSTRAP-LOG). Your preference?

---

## 10. Approval protocol

Reply with one of:

- **"approved all"** — execute phases 0–6 sequentially, writing
  `REFACTOR-LOG.md` as I go (to be folded into research/ at next
  ingest)
- **"approved but relative symlinks"** — same, relative-path symlinks in
  contexts/
- **"approved but skip concurrent-sessions"** — only do the flatten, keep
  `wiki-switch`/`wiki-run`. I'll need to carefully preserve those scripts
  through the path updates
- **"pause after phase 3"** — do the push + backup but don't clean-slate
  clone; wait for my OK before proceeding
- **"reject / rework"** — tell me what you want different

**Recommendation:** "**approved all**" with the default (absolute
symlinks). The biggest risk is subtle path bugs, and Phase 4's
reproduction test is specifically designed to catch them before cleanup.
Nothing irreversible until Phase 6 (`rm -rf /tmp/kb-backup-*`).

---

## 11. Superseded by this

- `PROPOSAL-CONCURRENT-SESSIONS.md` — folded in; that file will be
  deleted (or retained as historical reference) when this executes
- `BOOTSTRAP-PROPOSAL.md` — already historical; no change from this
  refactor

Post-refactor, `REFACTOR-LOG.md` captures this session's decisions and
becomes the newest entry in `research/`'s history stack.
