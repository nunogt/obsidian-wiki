# Proposal: concurrent-session refactor (refined)

*For your review. Nothing executed. Refined after operator feedback:
external wrappers for wiki operations are out of scope — all wiki commands
happen inside Claude sessions. Only git/vault-setup scripts remain.*

---

## 1. The problem, precisely

Two shared pieces of state couple every Claude session on this machine to
one profile at a time:

| Coupling | Reads it | Why it prevents concurrency |
|---|---|---|
| `~/.obsidian-wiki/config` | `wiki-update`, `wiki-query` (global installs), `wiki-ingest` (preferred) | Global file — any concurrent write by `wiki-switch` overwrites the value other sessions rely on. |
| `ar9av-obsidian-wiki/.env` (symlink to `profiles/<active>.env`) | all 10 "local" skills (`wiki-lint`, `wiki-rebuild`, `wiki-status`, `wiki-export`, `cross-linker`, `data-ingest`, `wiki-setup`, `*-history-ingest`, `tag-taxonomy`) | Same symlink seen by every Claude session launched from the ar9av repo. Switching profiles flips it underfoot. |

Source-level confirmation (grepped from `.skills/*/SKILL.md`):
- `wiki-update/SKILL.md:16-19` — reads only global config, no `.env` fallback
- `wiki-ingest/SKILL.md:18` — global config preferred, `.env` fallback
- `wiki-query/SKILL.md:18` — global config preferred, `.env` fallback
- 10 other skills — local `.env` only

Fixing either layer alone isn't enough; both need isolation.

### What "concurrent" means for your use case

**Terminal A running a long ingest/lint on the `wiki` vault while terminal B
queries or updates the `personal` vault, with no `wiki-switch` toggle and no
race.** Each session fully isolated end-to-end.

---

## 2. Design constraints

- Don't fork ar9av (upstream-tracking via `wiki-ar9av-update` is load-bearing)
- Don't break three-repo versioning or `kb-vault-new`
- Don't break Obsidian Git laptop sync
- Don't require re-ingesting existing vaults
- **Keep only infrastructure scripts (git/setup); all wiki operations happen
  inside Claude sessions** — no `wiki-run` / `wiki-switch` wrappers

---

## 3. Options considered

### A. Per-profile context directories (**recommended**)

Each profile has a dedicated directory Claude is launched from. The
directory contains symlinks to ar9av's upstream skills and a local `.env`
for the profile. CWD determines the profile; two terminals in two
directories = two concurrent profiles.

**Pros:** zero shared mutable state; no fork; CWD self-documenting; every
session sees fresh upstream skills via symlinks.
**Cons:** removes the current ability to invoke `/wiki-update` from any
project dir — you CD to the context first, then ask Claude to process
whatever you want. (You already indicated this is acceptable.)

### B. Per-session env var override
Set `OBSIDIAN_VAULT_PATH` in the shell; hope skills prefer env over file.
They don't — skill prompts read explicit filesystem paths. **Rejected** —
brittle, still doesn't fix `wiki-update`.

### C. Fork ar9av to prefer env vars
Cleanest UX but ongoing merge burden; abandons clean upstream tracking.
**Rejected** unless upstream accepts a PR (separate project).

### D. Per-session `HOME` override
Fixes the global config layer but leaves the 10 local-`.env` skills
colliding. Also breaks Claude's auth path unless you symlink it.
**Rejected** — partial fix only.

### E. Per-profile ar9av clones
Duplicate the clone per profile. Isolates `.env` but not global config;
doubles upstream-pull burden. **Rejected** — partial fix only.

### Scoring

| Option | Concurrency | No-fork | DX | Effort |
|---|---|---|---|---|
| **A. Context dirs** | ✓ | ✓ | Good | Low–Moderate |
| B. Env + prompt | ✗ | ✓ | Bad | Trivial |
| C. Fork | ✓ | ✗ | Best | High (ongoing) |
| D. HOME swap | Partial | ✓ | OK | Moderate |
| E. Per-profile clone | Partial | ✓ | OK | Moderate |

**Recommendation: A.**

---

## 4. Recommended design

### 4.1 Directory layout

```
/mnt/host/shared/git/kb/
├── ar9av-obsidian-wiki/         (upstream, unchanged)
├── contexts/                    (GITIGNORED — derived state, regenerated per machine)
│   ├── wiki/
│   │   ├── CLAUDE.md  -> ../../ar9av-obsidian-wiki/AGENTS.md
│   │   ├── AGENTS.md  -> ../../ar9av-obsidian-wiki/AGENTS.md
│   │   ├── GEMINI.md  -> ../../ar9av-obsidian-wiki/AGENTS.md
│   │   ├── .claude/skills/      (per-skill symlinks into ar9av/.skills/)
│   │   └── .env -> ../../profiles/wiki.env
│   └── personal/
│       └── (same shape, .env → ../../profiles/personal.env)
├── profiles/                    (tracked in kb-system — source of truth)
│   ├── wiki.env
│   └── personal.env
├── vaults/                      (each independent git repo, gitignored from kb-system)
│   ├── wiki/
│   └── personal/
└── scripts/
    ├── kb-vault-new             (updated: also creates the context dir)
    ├── kb-contexts-regenerate   (NEW: rebuild contexts/ from profiles/)
    ├── wiki-ar9av-update        (updated: regenerate contexts post-pull)
    └── templates/               (unchanged)
        ├── profile.env
        └── vault.gitignore
```

### 4.2 How you work with it

```bash
# Terminal 1 — wiki session
cd /mnt/host/shared/git/kb/contexts/wiki
claude --dangerously-skip-permissions
> /wiki-ingest
> lint the wiki and commit

# Terminal 2 — personal session (concurrent)
cd /mnt/host/shared/git/kb/contexts/personal
claude --dangerously-skip-permissions
> /wiki-query "what's on my mind?"
```

CWD picks the profile. No toggle. No shared state. Git commits via in-session
prompts ("commit the vault"), which Claude handles itself.

### 4.3 The global config and global skills are abolished

- `rm -rf ~/.obsidian-wiki/` — no longer needed, nothing reads it
- `rm ~/.claude/skills/wiki-update ~/.claude/skills/wiki-query` — bye
  global skills

The skills still exist in each context's `.claude/skills/` via the symlink
scheme, so they work — but only when CWD is a context directory, where the
local `.env` resolves unambiguously.

### 4.4 `wiki-switch` and `wiki-run` go away

Both become obsolete:

- **`wiki-switch`** — obsolete; CWD selects the profile. Deleted.
- **`wiki-run`** — obsolete per your stated preference; wiki operations happen
  inside Claude sessions, with Claude handling the commit itself via prompt
  ("ingest and commit", "lint and commit"). Deleted.

Scripts-directory diff:

| Script | Before | After |
|---|---|---|
| `wiki-switch` | exists | **deleted** |
| `wiki-run` | exists | **deleted** |
| `kb-vault-new` | exists | updated (also creates context) |
| `wiki-ar9av-update` | exists | updated (regens contexts post-pull) |
| `kb-contexts-regenerate` | — | **new** |
| `templates/profile.env` | exists | unchanged |
| `templates/vault.gitignore` | exists | unchanged |

Net count: still 4 files in `scripts/`, but the surface is cleaner — every
script does one thing, all infrastructure, none wrapping Claude invocations.

---

## 5. Script specifications

### 5.1 `kb-contexts-regenerate` (new)

```bash
#!/bin/bash
# kb-contexts-regenerate — rebuild contexts/ from profiles/
#
# Idempotent. Safe to run on a fresh clone, after wiki-ar9av-update,
# or any time contexts/ looks stale. Only reads profiles/*.env and the
# upstream ar9av clone; writes only under contexts/.

set -euo pipefail
KB=/mnt/host/shared/git/kb
AR9AV=$KB/ar9av-obsidian-wiki

for envfile in "$KB/profiles"/*.env; do
  [ -f "$envfile" ] || continue
  name=$(basename "$envfile" .env)
  ctx=$KB/contexts/$name

  mkdir -p "$ctx/.claude/skills"
  ln -sfn ../../ar9av-obsidian-wiki/AGENTS.md "$ctx/CLAUDE.md"
  ln -sfn ../../ar9av-obsidian-wiki/AGENTS.md "$ctx/AGENTS.md"
  ln -sfn ../../ar9av-obsidian-wiki/AGENTS.md "$ctx/GEMINI.md"
  ln -sfn "../../profiles/$name.env" "$ctx/.env"

  # Prune stale skill symlinks (skill removed from upstream)
  for link in "$ctx"/.claude/skills/*; do
    [ -L "$link" ] || continue
    skill=$(basename "$link")
    [ -d "$AR9AV/.skills/$skill" ] || rm -f "$link"
  done

  # Add/refresh symlinks for current upstream skills
  for skill in "$AR9AV"/.skills/*/; do
    s=$(basename "$skill")
    ln -sfn "../../../ar9av-obsidian-wiki/.skills/$s" \
            "$ctx/.claude/skills/$s"
  done
  echo "✓ context/$name"
done
```

### 5.2 `kb-vault-new` — add context creation

Current script already does profile + vault + remote. Extend it to call
`kb-contexts-regenerate` (or inline the equivalent snippet) after the
profile file is written. After the script finishes, `contexts/<name>/` is
ready; user launches `cd contexts/<name> && claude` for the `/wiki-setup`
scaffold step.

Remove the final `wiki-switch` call — obsolete.

### 5.3 `wiki-ar9av-update` — add post-pull context regen

After the existing pull + `bash setup.sh` step, call
`kb-contexts-regenerate`. Ensures new or renamed upstream skills appear in
existing contexts without a separate manual step.

---

## 6. Migration plan

Three phases, each atomic and reversible:

**Phase 1 — additive, concurrent-sessions available immediately:**

1. Create `contexts/wiki/` and `contexts/personal/` with symlinks via
   `kb-contexts-regenerate` (install the script first)
2. Add `contexts/` to kb-system's `.gitignore`
3. Test: `cd contexts/wiki && claude --dangerously-skip-permissions` →
   run `/wiki-query "test"` → verify correct vault; repeat for personal
4. Test concurrent: two terminals, two context dirs, two simultaneous ops

**Phase 2 — wire the infrastructure scripts:**

5. Update `kb-vault-new` to generate context dirs for new vaults
6. Update `wiki-ar9av-update` to regen contexts post-pull

**Phase 3 — remove legacy coupling:**

7. `rm ~/.claude/skills/wiki-update ~/.claude/skills/wiki-query`
8. `rm -rf ~/.obsidian-wiki/` (no longer needed)
9. `rm scripts/wiki-switch scripts/wiki-run`
10. Update `README.md` and `research/ar9av-self-hosted-architecture.md`
    to reflect the CWD-based pattern

No vault content changes. No re-ingest. Rollback is just
`rm -rf contexts/` + restore the two deleted scripts from git.

---

## 7. What you gain and lose

**Gain:**
- Concurrent Claude sessions on different vaults
- No `wiki-switch` toggle (and no race on `~/.obsidian-wiki/config`)
- CWD = profile indicator, self-documenting
- Every session sees fresh upstream skills via symlinks
- Simpler script surface (4 scripts, all infrastructure, no Claude wrappers)

**Lose:**
- Running `/wiki-update` / `/wiki-query` from arbitrary project
  directories — you CD into a context first (acceptable per your
  feedback)

**Don't lose:**
- ar9av upstream tracking
- Three-repo versioning
- `kb-vault-new` convenience
- Vault content, manifest history, laptop setup

---

## 8. Approval protocol

Reply with one of:

- **"approved all"** — execute phases 1–3 sequentially, write
  `SESSION-LOG.md` as I go (to be folded into `research/` at next ingest
  like BOOTSTRAP-LOG)
- **"phase 1 only"** — contexts exist alongside the old `wiki-switch`
  path; live with both for a week; re-evaluate before removing legacy. ←
  **my recommendation**
- **"reject"** — explain what you want instead

Phase 1 is **additive and non-destructive** — it creates `contexts/`
alongside the existing profile system without removing anything. You can
try concurrent sessions immediately via `cd contexts/<name>` and still use
`wiki-switch` + `wiki-run` for the old workflow. If after a week you
prefer the new pattern, proceed to phases 2–3. If not, a single
`rm -rf contexts/` reverts to today's state.
