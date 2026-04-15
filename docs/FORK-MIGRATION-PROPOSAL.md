# Fork-migration + multi-vault proposal — kb-system on nunogt/obsidian-wiki fork

*Drafted 2026-04-14. Validated against current source via end-to-end audit
of all 16 ar9av skills + setup.sh + bootstrap files. Execution started 2026-04-15.*

---

## 0. Operator decisions — locked execution scope (2026-04-15)

After deliberation in §1-§11 below, the operator locked the following scope:

| Item | Decision | Rationale |
|---|---|---|
| Fork swap (Phases 0-4) | **Include** | Eliminates symlink-divergence dance, decouples from upstream maintenance timing |
| Patch A — relative symlinks | **Include** | Pure win; eliminates the discard-and-regen step in `wiki-ar9av-update` |
| Patch B — `.env` fallback in `wiki-update`/`wiki-query` | **Skip** | `wiki-update` is upstream legacy, superseded by our CWD-based model ([[wiki-update-deprecation]]); not worth maintaining a fork patch for a skill we don't use |
| Patch C — in-vault sources exclusion | **Include** | Required for proper multi-vault containment; verified via the sources reorg test bed |
| Sources reorg with proper split | **Include with split** | `kb-system/docs/` for kb-system's own evolution docs; `kb-wiki/_sources/` for external research only — clean separation of concerns |
| Phase 9 — file upstream PRs | **Skip entirely** | No interaction with upstream as part of this scope; fork stays self-contained |

The proposal body below preserves the full deliberation record. **Execution follows the locked scope above.** Where the body still describes Patch B or upstream PR steps, treat them as historical context for the deliberation — they will not be performed.

### Execution discipline

- **Tag a rollback point** before every destructive operation
- **`/tmp/` backups** before `mv` of any local clone or vault content
- **Each patch on its own branch** — tested → merged to fork `main` → pushed; no batching
- **Verify each phase** before proceeding; halt and report on any unexpected state
- **Patch C verification** uses the sources reorg as the test bed: scanning skills run against the actual `kb-wiki/_sources/` and must not touch any file there

---

## 1. What this proposal covers

This proposal combines three previously-separate threads into one coherent fork-migration plan:

1. **Switch local clone slot from upstream `Ar9av/obsidian-wiki` → fork `nunogt/obsidian-wiki`** (operator-owned).
2. **Apply three local patches to the fork** to fix architectural issues blocking multi-vault deployment:
   - **Patch A — relative symlinks** (`setup.sh`) — eliminates symlink-divergence dance
   - **Patch B — `.env` fallback** (`wiki-update`, `wiki-query`) — restores `/wiki-update` under CWD-based contexts
   - **Patch C — vault-scan source exclusion** (cross-linker, tag-taxonomy, wiki-export, wiki-lint, wiki-status, wiki-ingest) — lets sources live inside the vault without being mistreated as wiki pages
3. **Reorganize sources to live inside their respective vaults**, removing the cross-contamination risk that comes from sharing `OBSIDIAN_SOURCES_DIR` across vaults.

Once each patch is stable in our fork, file as upstream PRs in series.

Operator answers locked in:
- Directory **rename** (`ar9av-obsidian-wiki/` → `obsidian-wiki/`)
- **Rebase** semantics for `wiki-ar9av-update`
- Sources move **inside vaults**, not into sibling repos

---

## 2. End-to-end audit findings

### 2.1 ar9av is fundamentally designed for 1 user → 1 wiki

Verified via grep across `.skills/*/SKILL.md` + bootstrap files + `.env.example`:

| Evidence | Source | Implication |
|---|---|---|
| Definite-singular language ("the wiki") | `llm-wiki/SKILL.md:32, 263`, `wiki-update/SKILL.md:7, 17`, `AGENTS.md:62`, `README.md:319-345` | No notion of "active vault" or "target vault" |
| One global config file | `setup.sh:85-89` writes `~/.obsidian-wiki/config` with one `OBSIDIAN_VAULT_PATH` | Single machine-wide pointer |
| Global skills install once | `setup.sh:105-117` puts `~/.claude/skills/wiki-update`, `~/.claude/skills/wiki-query` | One install per machine, routes to one vault |
| `wiki-update` reads only global config, no fallback | `wiki-update/SKILL.md:16-19` | Cannot ask "which vault" — there's only ever one |
| Manifest keyed by absolute source paths | observed in our `.manifest.json` | Two vaults pointing at overlapping sources have independent manifests claiming ownership of the same files |
| Zero hits for `multi-vault\|multiple vault\|per-vault\|multi-wiki` | `grep -r` across entire repo | Not contemplated anywhere |
| Default `OBSIDIAN_SOURCES_DIR=~/Documents` | `wiki-setup/SKILL.md:24` | Assumes user has *one* document store feeding *one* wiki |

This is the Karpathy gist faithfully implemented: one user's personal knowledge base.

### 2.2 The "sources outside vault" rule has two intertwined reasons

`llm-wiki/SKILL.md:18-22` defines Layer 1 (Raw Sources) and Layer 2 (The Wiki) as conceptually distinct:

- **Architectural reason** (survives multi-vault): inputs ≠ outputs; different lifecycles, different roles. Compiled wiki pages are LLM-mutable; sources are immutable.
- **Implementational reason** (single-vault residue): with one vault, "sources outside vault" needs no further qualification — there's no other vault to confuse it with. With multiple vaults, sources need per-vault containment.

The architecture survives. The implementation breaks down. Patch C addresses the latter.

### 2.3 Vault-scanning skills — the patch surface for in-vault sources

End-to-end SKILL.md read confirmed exactly **6 skills** scan vault directories. Each has a different exclusion list, hardcoded in the SKILL.md prompt:

| Skill | Scan behavior | Today's excludes | If in-vault sources existed |
|---|---|---|---|
| **cross-linker** | Glob all `.md`, **READ + WRITE** (injects wikilinks) | `_archives/`, `.obsidian/` | **Critical** — would inject wikilinks into source markdowns |
| **tag-taxonomy** | Glob `**/*.md`, **READ + WRITE** (rewrites tags) | `_archives/`, `.obsidian/`, `_meta/` | **Critical** — would normalize tags inside source files |
| **wiki-export** | Glob all `.md`, **READ-ONLY** | `_archives/`, `_raw/`, `.obsidian/`, `index.md`, `log.md`, `_insights.md` | **High** — would emit source files as graph nodes |
| **wiki-lint** | Glob all `.md`, **READ-ONLY** | None explicit (uses index.md as inventory) | **Medium** — flags source files as orphans/missing-frontmatter |
| **wiki-status (insights)** | Glob all pages, **READ-ONLY**, builds wikilink graph | None explicit | **Medium** — skews hub/cohesion metrics with non-wiki content |
| **wiki-ingest** | Single `Glob` to check if a page exists by name | None explicit | **Low** — false-positive matches; non-destructive |

Three other skills also touch the vault but in safer ways:

- **wiki-rebuild** operates on category dirs only (uses `OBSIDIAN_CATEGORIES`); wouldn't touch sources unless they're in a category dir
- **wiki-query** scans frontmatter + reads pages — index.md is its inventory; sources outside index.md are invisible
- **wiki-setup, wiki-update, data-ingest, claude-history-ingest, codex-history-ingest, wiki-history-ingest, llm-wiki, skill-creator** don't scan vault contents in the destructive sense

### 2.4 The cross-contamination risk in multi-vault, concretely

```
~/Documents/research/                   ← one shared OBSIDIAN_SOURCES_DIR
├── q3-roadmap.pdf                      ← meant for kb-work
├── meditation-notes.md                 ← meant for kb-personal
└── llm-wiki-paper.pdf                  ← meant for kb-wiki
```

With both profiles' `OBSIDIAN_SOURCES_DIR=~/Documents/research/`:
- `/wiki-ingest` from any context dir distills **all three** files into that context's vault
- The work vault gets meditation notes; the personal vault gets the LLM-wiki paper
- No filter, no source-tagging, no manifest-routing rule

User-side workarounds (manual partition into per-vault subdirs) are brittle and easy to violate. The architecturally clean fix: **per-vault sources colocated with the vault**.

### 2.5 Verified clean — fork & local state

- **Fork parent confirmed** via `gh repo view nunogt/obsidian-wiki --json parent` → `Ar9av/obsidian-wiki`
- **Both clones at `ce54dcb`** (Merge PR #14) — fork synced with upstream
- **No uncommitted work** in either clone; no commits ahead/behind origin
- **kb-system live refs** to `ar9av-obsidian-wiki/`: 4 locations
  - `scripts/wiki-ar9av-update:16`
  - `scripts/kb-contexts-regenerate:20`
  - `README.md:17, 60`
  - `.gitignore:3, 12` (defensive — keep)
- **kb-wiki live refs**: 7 wiki pages (operational); rest are historical

---

## 3. Target end-state

```
/mnt/host/shared/git/
├── obsidian-wiki/              ← was ar9av-obsidian-wiki/ (now: nunogt fork)
│   ├── .git/
│   │   └── refs:
│   │       ├── origin   = git@github.com:nunogt/obsidian-wiki.git
│   │       └── upstream = https://github.com/Ar9av/obsidian-wiki.git
│   ├── setup.sh                ← Patch A: relative in-repo symlinks
│   ├── .skills/
│   │   ├── wiki-update/SKILL.md      ← Patch B: .env fallback
│   │   ├── wiki-query/SKILL.md       ← Patch B: .env fallback
│   │   ├── cross-linker/SKILL.md     ← Patch C: exclude in-vault sources
│   │   ├── tag-taxonomy/SKILL.md     ← Patch C
│   │   ├── wiki-export/SKILL.md      ← Patch C
│   │   ├── wiki-lint/SKILL.md        ← Patch C
│   │   ├── wiki-status/SKILL.md      ← Patch C (insights mode)
│   │   ├── wiki-ingest/SKILL.md      ← Patch C (page-existence check)
│   │   └── ... (others unchanged)
│   └── .env.example            ← Patch C: document `OBSIDIAN_INVAULT_SOURCES_DIR`
├── kb-system/                  ← INFRA ONLY
│   ├── scripts/
│   │   ├── kb-contexts-regenerate    ← path updated → obsidian-wiki/
│   │   └── wiki-ar9av-update         ← rewritten: rebase + force-push
│   ├── profiles/
│   │   ├── wiki.env                  ← OBSIDIAN_SOURCES_DIR + OBSIDIAN_INVAULT_SOURCES_DIR set
│   │   └── personal.env              ← per-vault sources path
│   └── docs/                         ← (future) kb-system's own docs
├── kb-wiki/                    ← the wiki vault
│   ├── _sources/               ← in-vault sources (Patch C unblocks this)
│   │   ├── karpathy-llm-wiki-research.md
│   │   ├── karpathy-llm-wiki-panel-review.md
│   │   ├── _review-rubric.md
│   │   ├── ar9av-self-hosted-architecture.md
│   │   ├── BOOTSTRAP-LOG.md
│   │   ├── REFACTOR-LOG.md
│   │   ├── REFACTOR-PROPOSAL.md
│   │   ├── PROPOSAL-CONCURRENT-SESSIONS.md
│   │   ├── BOOTSTRAP-PROPOSAL.md
│   │   └── FORK-MIGRATION-PROPOSAL.md
│   ├── concepts/, entities/, skills/, references/, synthesis/, ...
│   └── ...
├── kb-personal/                ← future
│   └── _sources/               ← per-vault sources, no shared dump
└── ...
```

Wiki profile post-migration:
```bash
OBSIDIAN_VAULT_PATH=/mnt/host/shared/git/kb-wiki
OBSIDIAN_SOURCES_DIR=/mnt/host/shared/git/kb-wiki/_sources
OBSIDIAN_INVAULT_SOURCES_DIR=_sources    # NEW: tells scanning skills to exclude this from vault scans
```

`kb-system/research/` is **dissolved** into the relevant vault's `_sources/`. The current contents (all about LLM-wiki / kb-system) move to `kb-wiki/_sources/`.

---

## 4. The three local patches (PRs A, B, C)

### Patch A — Relative symlinks in `setup.sh`

**Goal:** Eliminate the symlink-divergence problem (56+ "modified" files post-pull).

**Surgical scope:** modify only the in-repo agent-dir installs (`.claude/skills/`, `.cursor/skills/`, `.agents/skills/`, `.windsurf/skills/`). Global dirs in `~/` keep absolute symlinks (relative would resolve outside the repo).

**Patch shape** (full code in §6.1):
- Add `mode` parameter to `install_skills()` function (default `absolute` for backwards compat)
- In-repo loop call site (lines 99-101) passes `mode="relative"`
- When `mode=relative`, compute target via `realpath --relative-to="$target_dir" "${skill%/}"`

**Effect on kb-system:**
- `wiki-ar9av-update`'s discard step (`git checkout -- .claude/skills .cursor/skills .agents/skills .windsurf/skills`) becomes obsolete
- `bash setup.sh` is *not* unblocked for our use — it still writes harmful global state. Skip continues.

**Risk:** None for upstream merge appetite. Pure win for everyone.

### Patch B — `.env` fallback in `wiki-update` and `wiki-query`

**Goal:** Restore `/wiki-update` under [[cwd-based-profiles|CWD-based contexts]] without breaking single-vault setups.

**Current state:**
- `wiki-update/SKILL.md:16-19` reads `~/.obsidian-wiki/config` with **no fallback** → permanently broken under our refactor
- `wiki-query/SKILL.md:18` reads global config first, falls back to `.env` → already works under our refactor

**Patch shape** (full text in §6.2):
- `wiki-update/SKILL.md`: change Step 1 from "read global config" to "read global config OR `.env` from CWD" (preserves single-vault default)
- Update the "if missing" error to mention both paths

**Risk:** Low — additive, preserves existing single-vault behavior. Maintainer may accept easily.

### Patch C — In-vault sources exclusion mechanism

**Goal:** Allow `OBSIDIAN_SOURCES_DIR` to live under `OBSIDIAN_VAULT_PATH` without scanning skills mistreating source files as wiki pages.

**Mechanism design choice:**

Two API options considered:

| Option | API | Pros | Cons |
|---|---|---|---|
| **Auto-detect** | Inspect whether `OBSIDIAN_SOURCES_DIR` falls under `OBSIDIAN_VAULT_PATH`; if so, exclude that path from vault scans | Zero new config; works with existing `.env` | Subtle implicit behavior; harder to override if user wants explicit control |
| **Explicit config** (RECOMMENDED) | New `OBSIDIAN_INVAULT_SOURCES_DIR=<vault-relative-path>` env var; when set, scanning skills exclude it | Explicit, debuggable, opts-in safely; doesn't change behavior unless user sets it | One more config var |

**Recommendation: explicit config** — `OBSIDIAN_INVAULT_SOURCES_DIR=_sources` (vault-relative). Vault-scanning skills add this to their exclude list when set. Comma-separated for multi-source-dir vaults if needed.

**Affected skills (6 + 1):**

| Skill | Patch shape |
|---|---|
| `cross-linker/SKILL.md:27` | Add `$OBSIDIAN_INVAULT_SOURCES_DIR` to the exclude list in Step 1 (Build the Page Registry) |
| `tag-taxonomy/SKILL.md:59` | Add to exclude in Mode 1 Step 1 (Scan all pages) |
| `wiki-export/SKILL.md:35` | Add to exclude in Step 1 (Build the Node and Edge Lists) |
| `wiki-lint/SKILL.md:31, 152` | Add to exclude in checks 1 (Orphans) and 6 (Index Consistency) |
| `wiki-status/SKILL.md:188` | Add to exclude in Insights Mode "build the wikilink graph" |
| `wiki-ingest/SKILL.md:152` | Add to exclude in the Step 4 page-existence Glob |
| `wiki-setup/SKILL.md:39` | Optional: add `_sources/` to the standard mkdir set |

**Patch shape pattern** (applies to all 6 SKILL.md edits — see §6.3 for per-skill text):

> Glob all `.md` files in the vault, excluding `_archives/`, `.obsidian/`, `_meta/`, **and any path matching `$OBSIDIAN_INVAULT_SOURCES_DIR` (if set in `.env` — typically `_sources/`)**.

**Defensive defaults:** if `OBSIDIAN_INVAULT_SOURCES_DIR` is unset, behavior is unchanged. Single-vault users see no difference.

**Risk for upstream:** Medium. Multi-skill change. Maintainer may want to discuss the API (auto-detect vs explicit) before merging. File as **issue** before PR.

---

## 5. Migration phases

Eight phases. Phases 0-4 are clone swap + sanity check. Phases 5-8 layer the patches and reorg sources. Each phase is reversible; rollbacks documented in §7.

### Phase 0 — verify (read-only) ✅ done

- Both clones at `ce54dcb`
- Fork parent confirmed
- No uncommitted state
- Audit complete (this document)

### Phase 1 — wire upstream remote on the fork

```bash
cd /mnt/host/shared/git/obsidian-wiki
git remote add upstream https://github.com/Ar9av/obsidian-wiki.git
git fetch upstream
git rev-parse HEAD upstream/main          # both ce54dcb (no rebase needed)
```

### Phase 2 — swap the clones

```bash
mv /mnt/host/shared/git/ar9av-obsidian-wiki \
   /tmp/ar9av-pre-fork-swap-$(date +%Y%m%d-%H%M%S)
# Fork is already at /mnt/host/shared/git/obsidian-wiki/ — no second mv needed
```

### Phase 3 — update kb-system to the new path

```bash
# scripts/kb-contexts-regenerate
sed -i 's|AR9AV=$GIT_ROOT/ar9av-obsidian-wiki|AR9AV=$GIT_ROOT/obsidian-wiki|' \
    /mnt/host/shared/git/kb-system/scripts/kb-contexts-regenerate
sed -i 's|github.com/Ar9av/obsidian-wiki|github.com/nunogt/obsidian-wiki|' \
    /mnt/host/shared/git/kb-system/scripts/kb-contexts-regenerate

# scripts/wiki-ar9av-update — rewrite for fork+rebase semantics (§6.4)

# .gitignore — add obsidian-wiki/ alongside ar9av-obsidian-wiki/
# (manual one-line addition)

# README.md — update layout block + clone command

# Re-run regen so contexts symlinks point at the new path
/mnt/host/shared/git/kb-system/scripts/kb-contexts-regenerate
```

### Phase 4 — verify the swap (no patches yet)

```bash
ls -la /mnt/host/shared/git/kb-system/contexts/wiki/.claude/skills/wiki-ingest
# expect → /mnt/host/shared/git/obsidian-wiki/.skills/wiki-ingest

cd /mnt/host/shared/git/kb-system/contexts/wiki
claude --print --dangerously-skip-permissions \
  "list the wiki skills you can see" | head -20
# expect: 16 skills

cd /mnt/host/shared/git/kb-system && scripts/wiki-ar9av-update
# expect: "already current with upstream/main"
```

**Pause point.** If anything's wrong, rollback per §7. Otherwise proceed.

### Phase 5 — apply Patch A (relative symlinks)

```bash
cd /mnt/host/shared/git/obsidian-wiki
git checkout -b feat/relative-symlinks
# Apply patch from §6.1
bash setup.sh
git status                              # in-repo agent dirs CLEAN (the proof)
git commit -am "fix(setup): use relative symlinks for in-repo agent dirs"
git push -u origin feat/relative-symlinks
git checkout main && git merge --ff-only feat/relative-symlinks
git push origin main
```

### Phase 6 — apply Patch B (.env fallback) and Patch C (in-vault sources exclusion)

Two separate branches off main:

```bash
# Patch B
git checkout -b feat/env-fallback main
# Apply patch from §6.2
git commit -am "fix(wiki-update,wiki-query): fall back to .env when global config missing"
git push -u origin feat/env-fallback
git checkout main && git merge --ff-only feat/env-fallback
git push origin main

# Patch C
git checkout -b feat/in-vault-sources main
# Apply 6 SKILL.md edits + .env.example doc per §6.3
git commit -am "feat: support in-vault sources via OBSIDIAN_INVAULT_SOURCES_DIR"
git push -u origin feat/in-vault-sources
git checkout main && git merge --ff-only feat/in-vault-sources
git push origin main
```

After Phase 6, fork's `main` carries 3 commits ahead of upstream. `wiki-ar9av-update`'s rebase semantics (Phase 3) preserve them across upstream pulls.

### Phase 7 — sources reorg

> **Precondition: Patch C must be merged into the fork's `main` and `kb-contexts-regenerate` re-run before this phase.** Otherwise `_sources/` files would be mistreated as wiki pages by cross-linker / tag-taxonomy / wiki-export. Verify by running `claude --print "/wiki-lint"` from a context dir post-Patch-C and confirming `_sources/` doesn't appear in any orphan or missing-frontmatter complaint.

```bash
# Move research docs into the wiki vault
mkdir -p /mnt/host/shared/git/kb-wiki/_sources
mv /mnt/host/shared/git/kb-system/research/*.md \
   /mnt/host/shared/git/kb-wiki/_sources/
rmdir /mnt/host/shared/git/kb-system/research

# Update wiki profile
sed -i 's|OBSIDIAN_SOURCES_DIR=.*|OBSIDIAN_SOURCES_DIR=/mnt/host/shared/git/kb-wiki/_sources|' \
    /mnt/host/shared/git/kb-system/profiles/wiki.env
echo 'OBSIDIAN_INVAULT_SOURCES_DIR=_sources' >> \
    /mnt/host/shared/git/kb-system/profiles/wiki.env

# Update vault's manifest.json: rewrite source-dict keys from
# /mnt/host/shared/git/kb-system/research/ → /mnt/host/shared/git/kb-wiki/_sources/
sed -i 's|/mnt/host/shared/git/kb-system/research/|/mnt/host/shared/git/kb-wiki/_sources/|g' \
    /mnt/host/shared/git/kb-wiki/.manifest.json
python3 -m json.tool /mnt/host/shared/git/kb-wiki/.manifest.json > /dev/null  # validate

# Update kb-system .gitignore: remove research/, since it's gone
# (manual edit)
```

**Verification:**
- `cd kb-system/contexts/wiki && claude --print "/wiki-status"` should show all sources from new location, no surprises
- `claude --print "/wiki-lint"` should report 0 orphans (in-vault sources excluded by Patch C)
- `claude --print "/cross-linker"` should not touch any file in `_sources/`

### Phase 8 — commit kb-system changes

```bash
cd /mnt/host/shared/git/kb-system
git add scripts/ profiles/ .gitignore README.md
git rm -r research/    # already moved, just stage the deletion
git commit -m "refactor: migrate to fork + flat layout + in-vault sources"
git push

cd /mnt/host/shared/git/kb-wiki
git add _sources/ .manifest.json
git commit -m "chore: move ingested sources into vault"
git push
```

### Phase 9 (deferred) — file upstream PRs in series

Order: A → B → C. File each only after the previous is merged (or the maintainer has acknowledged intent).

- **PR A — relative symlinks**: file unconditionally. Pure win for all users.
- **PR B — `.env` fallback**: open issue first to gauge maintainer's view on multi-vault use case. PR if green.
- **PR C — in-vault sources exclusion**: open issue first; this is the bigger architectural change. Frame as "support multi-vault deployments via per-vault source containment." Maintainer may want to discuss API choice (auto-detect vs explicit).

Keep all three patches in our fork's `main` regardless of upstream merge timing. `wiki-ar9av-update`'s rebase keeps them on top of any upstream pulls.

---

## 6. Patch implementations

### 6.1 Patch A — `setup.sh` relative symlinks

```diff
--- a/setup.sh
+++ b/setup.sh
@@ -22,9 +22,12 @@ set -e
 SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
 SKILLS_DIR="$SCRIPT_DIR/.skills"

-# Symlink every skill in SKILLS_DIR into TARGET_DIR.
-# Skips real directories to avoid data loss; updates stale symlinks.
+# Symlink every skill in SKILLS_DIR into TARGET_DIR.
+# Skips real directories to avoid data loss; updates stale symlinks.
+# Mode "relative" (for in-repo agent dirs): writes a path relative to
+# TARGET_DIR — portable across machines, never shows as modified in git.
+# Mode "absolute" (default, for ~/ globals): writes the resolved abs path.
 install_skills() {
   local target_dir="$1"
   local label="$2"
+  local mode="${3:-absolute}"
   mkdir -p "$target_dir"
   for skill in "$SKILLS_DIR"/*/; do
     local skill_name link_path
@@ -36,7 +39,12 @@ install_skills() {
       echo "⚠️   $link_path is a real directory, skipping symlink"
       continue
     fi
-    ln -s "${skill%/}" "$link_path"
+    local target
+    if [ "$mode" = "relative" ]; then
+      target="$(realpath --relative-to="$target_dir" "${skill%/}")"
+    else
+      target="${skill%/}"
+    fi
+    ln -s "$target" "$link_path"
   done
   echo "✅  Installed global skills → $label"
 }
@@ -97,7 +105,7 @@ AGENT_DIRS=(
 )

 for agent_dir in "${AGENT_DIRS[@]}"; do
-  install_skills "$SCRIPT_DIR/$agent_dir" "$agent_dir/"
+  install_skills "$SCRIPT_DIR/$agent_dir" "$agent_dir/" "relative"
 done
```

The 122-124 global call sites are unchanged — they default to `absolute`.

**Self-validate:** Test by re-running `setup.sh` on the fork; confirm `git status` is clean (no modified symlinks). Confirm `ls -la .claude/skills/wiki-ingest` shows `→ ../../.skills/wiki-ingest`.

**Critique:** What if `realpath --relative-to` is missing on macOS without coreutils? Fallback: detect missing `realpath` and emit a clear error message. Or: implement the relative-path computation in pure bash (not necessary for our Linux deploy).

**Refine:** Add a portability check at script start: `command -v realpath >/dev/null || { echo "realpath required (install coreutils)" >&2; exit 1; }`. Acceptable cost for the new behavior.

### 6.2 Patch B — `wiki-update` and `wiki-query` env fallback

**`wiki-update/SKILL.md`** lines 16-19, before:
```markdown
1. Read `~/.obsidian-wiki/config` to get:
   - `OBSIDIAN_VAULT_PATH` — where the wiki lives
   - `OBSIDIAN_WIKI_REPO` — where the obsidian-wiki repo is cloned (for reading other skills if needed)
2. If `~/.obsidian-wiki/config` doesn't exist, tell the user to run `bash setup.sh` from their obsidian-wiki repo first.
```

After (CWD-first ordering — see Critique below):
```markdown
1. Read configuration in this order (first found wins — CWD takes precedence so multi-vault sessions always read their own context):
   a. `.env` in the current working directory — local config (CWD-based multi-vault setups)
   b. `~/.obsidian-wiki/config` — global config (single-vault fallback)
   Pull from whichever source: `OBSIDIAN_VAULT_PATH` (where the wiki lives) and `OBSIDIAN_WIKI_REPO` (where the obsidian-wiki repo is cloned, optional in CWD-based setups).
2. If neither source exists, tell the user: "Set `OBSIDIAN_VAULT_PATH` either via a `.env` file in the current directory (multi-vault) or via `bash setup.sh` (single-vault)."
```

**`wiki-query/SKILL.md`** line 18 — already has a fallback, but it's conditioned on being "inside the obsidian-wiki repo". Generalize and reorder to match `wiki-update`:

Before:
```markdown
1. Read `~/.obsidian-wiki/config` to get `OBSIDIAN_VAULT_PATH` (works from any project). Fall back to `.env` if you're inside the obsidian-wiki repo.
```

After:
```markdown
1. Read configuration: prefer `.env` in the current working directory (CWD-based multi-vault setups), fall back to `~/.obsidian-wiki/config` (single-vault). Pull `OBSIDIAN_VAULT_PATH` from whichever resolves first.
```

**Self-validate:** From a CWD-based context dir with both `.env` AND a global config present (e.g. legacy single-vault setup transitioning), both skills should resolve the CWD `.env` and ignore the global. Single-vault users without any `.env` in CWD still get the global config — backwards compatible.

**Critique (resolved during refinement):** The original draft had global-config-first ordering, which would have meant a stale global config silently overrides any CWD `.env` — exactly the multi-vault failure mode that motivated the CWD refactor in the first place. Reversed the order: **CWD first, global fallback**. This is the correct ordering because:
- Single-vault users (no `.env` in CWD) see no behavior change — global still resolves
- Multi-vault users in a context dir always get their context's `.env`, regardless of any leftover global config
- During migration from single-vault to multi-vault, the user can leave the global config alone and let CWD take over without any cleanup step

**Refine — done.** Patch text above reflects the reversed ordering. Open question for upstream PR: this ordering inversion is a *behavior change* for any user who currently has both a global config AND happens to have an unrelated `.env` in their CWD. Vanishingly rare in practice (`.env` files don't usually contain `OBSIDIAN_VAULT_PATH` outside this project), but worth a heads-up in the PR description.

### 6.3 Patch C — in-vault sources exclusion

**`.env.example`** addition:

```bash
# --- In-Vault Sources (optional) ---
#
# When OBSIDIAN_SOURCES_DIR points to a path under OBSIDIAN_VAULT_PATH,
# set this to the vault-relative path so vault-scanning skills (cross-linker,
# tag-taxonomy, wiki-export, wiki-lint, wiki-status, wiki-ingest) skip it.
# Without this, scanning skills will treat your source files as wiki pages.
#
# Example: vault at /home/me/vault/, sources at /home/me/vault/_sources/
#   OBSIDIAN_INVAULT_SOURCES_DIR=_sources
#
# Comma-separated for multiple in-vault source dirs.
OBSIDIAN_INVAULT_SOURCES_DIR=
```

**Per-skill SKILL.md edits** — pattern is the same across all 6 skills:

For each skill, the existing exclude clause looks like:
> Glob all `.md` files in the vault (excluding `_archives/`, `.obsidian/`).

Patch it to:
> Glob all `.md` files in the vault (excluding `_archives/`, `.obsidian/`, **and any path matching `$OBSIDIAN_INVAULT_SOURCES_DIR` from `.env` — typically `_sources/` for multi-vault setups**).

Specific line targets:
- `cross-linker/SKILL.md:27`
- `tag-taxonomy/SKILL.md:59`
- `wiki-export/SKILL.md:35`
- `wiki-lint/SKILL.md:31, 152` (two scan sites — orphan check + index check)
- `wiki-status/SKILL.md:188` (insights mode graph build)
- `wiki-ingest/SKILL.md:152` (page-existence Glob)

**`wiki-setup/SKILL.md:39`** — extend the standard mkdir set:
```bash
mkdir -p "$OBSIDIAN_VAULT_PATH"/{concepts,entities,skills,references,synthesis,journal,projects,_archives,_raw,_sources,.obsidian}
```

And add a §3 entry:
> - `_sources/` — In-vault source documents (when using multi-vault deployments). Set `OBSIDIAN_INVAULT_SOURCES_DIR=_sources` in `.env` and `OBSIDIAN_SOURCES_DIR=$VAULT_PATH/_sources`. Vault-scanning skills will skip this directory.

**Self-validate:** With `OBSIDIAN_INVAULT_SOURCES_DIR=_sources` set, run `/cross-linker` and verify it doesn't inject wikilinks into `_sources/*.md`. Run `/wiki-lint` and confirm no orphan complaints from `_sources/`. Run `/wiki-export` and confirm `_sources/` files don't appear as graph nodes.

**Critique:** What if a user has `OBSIDIAN_SOURCES_DIR=$VAULT/_sources` but forgets to set `OBSIDIAN_INVAULT_SOURCES_DIR`? They'd get the cross-contamination back. Could the skills detect the overlap automatically?

**Refine:** Add a soft auto-detect fallback in each scanning skill: *"If `OBSIDIAN_INVAULT_SOURCES_DIR` is unset but `OBSIDIAN_SOURCES_DIR` falls under `OBSIDIAN_VAULT_PATH`, treat the relative portion as an implicit exclude and warn the user to set `OBSIDIAN_INVAULT_SOURCES_DIR` explicitly."* Best of both worlds — explicit when present, defensive when forgotten.

### 6.4 `wiki-ar9av-update` rewrite for fork+rebase semantics

```bash
#!/bin/bash
# wiki-ar9av-update — pull upstream into the fork, rebase our patches, regenerate contexts.
set -euo pipefail

GIT_ROOT=/mnt/host/shared/git
REPO=$GIT_ROOT/obsidian-wiki
KB_SYSTEM=$GIT_ROOT/kb-system

[ -d "$REPO" ] || { echo "error: $REPO not found" >&2; exit 1; }
cd "$REPO"

echo "▶ fetching upstream..."
git fetch upstream

incoming=$(git log main..upstream/main --oneline 2>/dev/null || true)
if [ -z "$incoming" ]; then
  echo "✓ already current with upstream/main ($(git rev-parse --short upstream/main))"
  [ -x "$KB_SYSTEM/scripts/kb-contexts-regenerate" ] && "$KB_SYSTEM/scripts/kb-contexts-regenerate"
  exit 0
fi

echo ""
echo "▶ incoming upstream commits:"
echo "$incoming" | sed 's/^/    /'
echo ""

# Heads-up on changes that may affect our patches
if git diff main..upstream/main --name-only | grep -qE 'setup\.sh|SKILL\.md$'; then
  echo "  ⚠  setup.sh or SKILL.md files changed upstream. Our patches may need rebase conflict resolution."
fi

read -p "rebase our patches onto upstream/main and force-push fork? [y/N] " answer
[ "${answer:-N}" = "y" ] || [ "${answer:-N}" = "Y" ] || { echo aborted; exit 1; }

rollback_tag="pre-update-$(date +%Y%m%d-%H%M%S)"
git tag -f "$rollback_tag" main
echo "✓ rollback tag: $rollback_tag"

echo "▶ rebasing onto upstream/main..."
git checkout main
git rebase upstream/main || {
  echo "rebase conflict — fix in $REPO, then 'git rebase --continue'"
  echo "rollback: git rebase --abort && git reset --hard $rollback_tag"
  exit 1
}

git push --force-with-lease origin main

echo "▶ regenerating kb-system contexts..."
[ -x "$KB_SYSTEM/scripts/kb-contexts-regenerate" ] && "$KB_SYSTEM/scripts/kb-contexts-regenerate"

echo ""
echo "✓ update complete."
echo "  recommended next: run /wiki-lint inside each context dir."
echo "  rollback (if anything broke):"
echo "    cd $REPO && git reset --hard $rollback_tag && git push --force-with-lease origin main"
echo "    cd $KB_SYSTEM && scripts/kb-contexts-regenerate"
```

---

## 7. Risk + rollback

| Risk | Severity | Mitigation |
|---|---|---|
| Phase 2 mv loses upstream clone | Low | `/tmp/` backup; one `mv` to restore |
| `realpath --relative-to` not available on target | Low | Linux deploy has coreutils; pre-flight check in setup.sh patch |
| Patch B breaks existing wiki-update behavior for single-vault users | Low | "First found wins" preserves existing behavior when global config exists |
| Patch C overlap detection has false positives | Low | Soft warning, not a hard error; explicit config always wins |
| Rebase conflicts during `wiki-ar9av-update` | Low (rare) → Manual fix | Script halts cleanly; rollback tag printed |
| Force-push to fork main loses unpushed commits | Very low | `--force-with-lease`; we're the only consumer |
| Sources reorg orphans pages whose `sources:` field cites old paths | Low | Vault's `sources:` fields are vault-relative labels, not file handles. Verified in REFACTOR-PROPOSAL §3. |
| Manifest sed produces malformed JSON | Low | Pure path string sub; `python3 -m json.tool` validates |
| Upstream PR for Patch C rejected | Low impact | Local fork keeps working indefinitely; rebase preserves patches |
| In-vault sources break a skill we didn't audit | Medium | Phase 7 verification runs lint/cross-linker/export to catch |

### Rollback paths

**Light** (Phase 4-7 verification fails, patches OK):
```bash
mv /mnt/host/shared/git/obsidian-wiki /tmp/obsidian-wiki-aborted-$(date +%s)
mv /tmp/ar9av-pre-fork-swap-* /mnt/host/shared/git/ar9av-obsidian-wiki
git -C /mnt/host/shared/git/kb-system checkout -- scripts/ .gitignore README.md
scripts/kb-contexts-regenerate
```

**Patch rollback** (any patch broke something on the fork):
```bash
cd /mnt/host/shared/git/obsidian-wiki
git reset --hard <pre-patch-tag>
git push --force-with-lease origin main
```

**Sources reorg rollback**:
```bash
mv /mnt/host/shared/git/kb-wiki/_sources/* /mnt/host/shared/git/kb-system/research/
sed -i 's|/mnt/host/shared/git/kb-wiki/_sources/|/mnt/host/shared/git/kb-system/research/|g' \
    /mnt/host/shared/git/kb-wiki/.manifest.json
# Restore profiles/wiki.env from git
git -C /mnt/host/shared/git/kb-system checkout profiles/wiki.env
```

---

## 8. What this opens up

Once Phases 0-8 are in:

### Multi-vault deployments work cleanly

Each future vault (`kb-personal`, `kb-project-X`, ...) sets `OBSIDIAN_SOURCES_DIR=$VAULT_PATH/_sources` and `OBSIDIAN_INVAULT_SOURCES_DIR=_sources`. Sources travel with their vault; no shared dump in kb-system; no cross-contamination risk.

### `/wiki-update` returns to use

Patch B restores the cross-project sync skill. From any project: `cd /path/to/project && claude --print "/wiki-update"` writes to whichever vault's context dir is active (or, if invoked from a project dir without a context, whichever vault the global config points at).

### Symlink divergence dance is dead

Patch A removes the need for `git checkout -- .claude/skills` etc. in `wiki-ar9av-update`. Cleaner upstream pulls.

### kb-system shrinks back to pure infrastructure

After the sources reorg (Phase 7), `kb-system/` contains only scripts, profiles, contexts, and (eventually) its own docs. No source materials for any vault. Adding kb-personal doesn't add a single byte to kb-system.

### Upstream contribution path

Three submittable PRs ready when our fork has soaked. Even if upstream rejects them, we keep working. Even if upstream accepts them, the cost was low (small surgical changes, well-documented).

---

## 9. Doc propagation post-migration

### kb-system

| File | Change |
|---|---|
| `README.md` | Layout + clone command point at `obsidian-wiki/` |
| `scripts/wiki-ar9av-update` | Full rewrite per §6.4 |
| `scripts/kb-contexts-regenerate` | Path + URL refresh |
| `.gitignore` | Add `obsidian-wiki/`; keep `ar9av-obsidian-wiki/` defensively; remove `research/` |
| `profiles/wiki.env` | New `OBSIDIAN_SOURCES_DIR` + `OBSIDIAN_INVAULT_SOURCES_DIR` |
| `profiles/personal.env` | (Optional now) — same pattern when populated |
| `scripts/templates/profile.env` | Add `OBSIDIAN_INVAULT_SOURCES_DIR` to template |

### kb-wiki

| File | Change |
|---|---|
| `.manifest.json` | sed source paths from `kb-system/research/` → `kb-wiki/_sources/` |
| `_sources/*` | Receives all 9 doc files from kb-system/research/ |

### Wiki pages (post-ingest)

Each operational page that cites the old path or pre-fork scripts:

- [[refactor-log-doc]] — add Addendum 4 covering this fork+sources migration
- [[wiki-ar9av-update]] — rebase semantics; remove discard-symlinks step
- [[three-repo-versioning]] — note `obsidian-wiki/` is now the fork
- [[ar9av-obsidian-wiki]] entity — note we run a fork + which patches differ
- [[wiki-update-deprecation]] — note Patch B restores functionality
- [[skills/using-ar9av-self-hosted]] — flat-layout reproduction now uses fork
- [[skills/kb-contexts-regenerate]] — refreshed paths
- [[concepts/cwd-based-profiles]] · [[concepts/contexts-directory]] — refreshed paths

New pages worth creating (for next ingest):
- `concepts/in-vault-sources` — the architectural pattern + why it works
- `concepts/fork-with-upstream-rebase` — the maintenance pattern
- `references/fork-migration-proposal-doc` — this file
- `synthesis/multi-vault-architecture` — how all the pieces fit together (CWD contexts + per-vault sources + rebase fork)

---

## 10. Approval protocol

Reply with one of:

- **"approved all"** — execute Phases 0-8 sequentially, defer Phase 9 (upstream PRs) until each patch has soaked for ~1 week
- **"approved through phase 4"** — clone swap + sanity check; pause before any patches
- **"approved through phase 6"** — clone swap + all 3 patches on fork; pause before sources reorg
- **"approved through phase 7"** — full migration including sources reorg; pause before kb-system/kb-wiki commits
- **"reject / rework"** — explain what to change

**Recommendation:** "**approved through phase 6**". Phases 0-6 are the fork migration + patches; reversible at every step. Pausing before Phase 7 lets you eyeball the patched fork in normal use before touching source layout. Sources reorg is the only step that moves vault content; worth deliberating separately.

---

## 11. Cross-references for next ingestion

When this proposal lands in the wiki:

**New concept candidates:**
- `concepts/in-vault-sources` — multi-vault containment via colocated sources
- `concepts/fork-with-upstream-rebase` — maintaining a fork with patches via rebase semantics
- `concepts/vault-scan-skills` — the 6 skills that scan vault dirs and what they do

**New skill candidate:**
- `skills/applying-fork-patches` — the recipe for layering Patches A/B/C and rebasing on upstream pulls

**New reference:**
- `references/fork-migration-proposal-doc` — this file

**New synthesis:**
- `synthesis/multi-vault-architecture` — how CWD contexts + per-vault sources + fork-with-rebase compose into a coherent multi-vault deployment

**Updates to existing pages:** see §9 above.

---

*End of proposal. Audit complete; awaiting approval.*
