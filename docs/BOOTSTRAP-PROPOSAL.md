# Bootstrap proposal — kb/ to production ar9av + meta-wiki

*For your review. Nothing below has been executed. Approve, edit, or reject
whole or in part.*

---

## 0. Current state (measured)

```
/mnt/host/shared/git/kb/
├── ar9av-obsidian-wiki/                 1.1 MB   61 commits   ← KEEP (engine)
├── nvk-llm-wiki/                        2.8 MB   84 commits   ← remove
├── samuraigpt-llm-wiki-agent/           701 KB   39 commits   ← remove
├── karpathy-llm-wiki-research.md        17 KB                  ← move to research/
├── karpathy-llm-wiki-panel-review.md    33 KB                  ← move to research/
├── ar9av-self-hosted-architecture.md    17 KB                  ← move to research/
├── _review-rubric.md                    5 KB                   ← move to research/
└── BOOTSTRAP-PROPOSAL.md                (this file — keep)
```

Disk reclaimed by cleanup: **~3.5 MB.** Not a meaningful saving; the reason to
cleanup is clarity, not space.

The kb directory itself is **not** a git repo. Its contents are tracked only
insofar as `ar9av-obsidian-wiki/` has its own internal git history.

---

## 1. Target end-state after bootstrap

```
/mnt/host/shared/git/kb/
├── ar9av-obsidian-wiki/                 ← the engine (unchanged)
│   ├── .env → .env.work                 ← symlink (new)
│   ├── .env.work                        ← profile template (new)
│   └── ...
├── research/                            ← preserved source docs (new)
│   ├── karpathy-llm-wiki-research.md
│   ├── karpathy-llm-wiki-panel-review.md
│   ├── ar9av-self-hosted-architecture.md
│   └── _review-rubric.md
├── vaults/
│   └── work/                            ← the work vault (new, git repo)
│       ├── .git/
│       ├── .obsidian/
│       ├── .manifest.json
│       ├── index.md
│       ├── log.md
│       ├── _raw/                        ← scp target; empty at bootstrap
│       ├── _archives/
│       ├── _meta/
│       ├── concepts/                    ← populated by ingest
│       ├── entities/                    ←   "
│       ├── skills/                      ←   "
│       ├── references/                  ←   "
│       ├── synthesis/                   ←   "
│       ├── journal/
│       └── projects/
├── scripts/                             ← wrapper scripts (new)
│   ├── wiki-switch
│   └── wiki-run
├── BOOTSTRAP-PROPOSAL.md                ← this file
└── BOOTSTRAP-LOG.md                     ← written during execution
```

No personal vault yet. Deferred to a later pass once the work rhythm
settles.

---

## 2. Phase 1 — Cleanup *(destructive; approve explicitly)*

Remove the two non-ar9av research clones.

```bash
cd /mnt/host/shared/git/kb
rm -rf nvk-llm-wiki samuraigpt-llm-wiki-agent
```

**Recoverability.** Both are public GitHub repos; re-clone with:
```
git clone https://github.com/nvk/llm-wiki
git clone https://github.com/SamurAIGPT/llm-wiki-agent
```
We have nothing locally that's not upstream. No local changes, no stash.

**Research-doc line references** in `karpathy-llm-wiki-panel-review.md`
occasionally cite paths like `nvk-llm-wiki/claude-plugin/...`. After cleanup,
those references become historical pointers; the line numbers still describe
upstream state. This is acceptable for a research archive.

**SVCR (self-check).** Confirmed via `git log` that neither clone has uncommitted
changes or stashes. The only local artifact would be anything we added, and
we added nothing — they're read-only research inputs.

---

## 3. Phase 2 — Preserve research as sources *(non-destructive)*

Move the four research docs into a `research/` subdirectory. They become the
persistent source set that ar9av ingests from. In ar9av's **append mode**,
ingest reads from `OBSIDIAN_SOURCES_DIR` **without deleting** the originals
(only raw mode, which reads from the vault's `_raw/` directory, deletes on
promotion — we won't use raw mode for bootstrap).

```bash
cd /mnt/host/shared/git/kb
mkdir -p research
mv karpathy-llm-wiki-research.md \
   karpathy-llm-wiki-panel-review.md \
   ar9av-self-hosted-architecture.md \
   _review-rubric.md \
   research/
```

Post-move the `research/` directory is the canonical location. ar9av's
`.manifest.json` will track each file's SHA-256 and record delta state, so
if you edit them later ar9av will re-ingest only what changed.

---

## 4. Phase 3 — Install wrapper scripts *(non-destructive)*

Create `/mnt/host/shared/git/kb/scripts/` with `wiki-switch` and `wiki-run`
exactly as specified in `research/ar9av-self-hosted-architecture.md` §5 and
§6. Then symlink to `/usr/local/bin/` so they're on PATH:

```bash
mkdir -p /mnt/host/shared/git/kb/scripts
# (drop the two scripts per arch doc §5, §6)
chmod +x /mnt/host/shared/git/kb/scripts/wiki-{switch,run}
sudo ln -s /mnt/host/shared/git/kb/scripts/wiki-switch /usr/local/bin/
sudo ln -s /mnt/host/shared/git/kb/scripts/wiki-run    /usr/local/bin/
```

**SVCR.** Both scripts were already written inline in the arch doc; nothing
new to design. The symlink into `/usr/local/bin/` requires sudo — flag for
your awareness.

---

## 5. Phase 4 — Configure ar9av for the work profile *(non-destructive)*

Create `.env.work` in the ar9av repo and symlink `.env` to point at it:

**`/mnt/host/shared/git/kb/ar9av-obsidian-wiki/.env.work`**
```
OBSIDIAN_VAULT_PATH=/mnt/host/shared/git/kb/vaults/work
OBSIDIAN_SOURCES_DIR=/mnt/host/shared/git/kb/research
OBSIDIAN_CATEGORIES=concepts,entities,skills,references,synthesis,journal
OBSIDIAN_RAW_DIR=_raw
OBSIDIAN_MAX_PAGES_PER_INGEST=15
```

```bash
cd /mnt/host/shared/git/kb/ar9av-obsidian-wiki
ln -s .env.work .env
echo '.env' >> .gitignore
```

Run setup.sh. It will:
- Write `~/.obsidian-wiki/config` pointing at the work vault
- Install global skills under `~/.claude/skills/wiki-update` and `~/.claude/skills/wiki-query`
- Regenerate the in-repo `.claude/skills/`, `.cursor/skills/`, etc. symlinks (currently broken — they point at `/Users/ar9av/…` from the author's Mac; setup.sh rewrites them to absolute paths under this repo)

```bash
bash setup.sh
```

When it prompts for the vault path, give it
`/mnt/host/shared/git/kb/vaults/work`.

**SVCR.** Confirmed via grepping `.skills/*/SKILL.md` that all local skills
resolve `.env` via the symlink. `setup.sh:53–80` skips prompting if `.env`
already has a non-placeholder path; since we wrote `.env.work` with a real
path, setup.sh will accept it silently.

**State written outside `/mnt/host/shared/git/kb/`:**
- `~/.obsidian-wiki/config` (small text file, single line)
- `~/.claude/skills/wiki-update/` (symlink)
- `~/.claude/skills/wiki-query/` (symlink)
- Also `~/.codex/skills/`, `~/.agents/skills/`, `~/.gemini/antigravity/skills/`
  (if those directories don't exist, setup.sh creates them as empty with
  symlinks; they're harmless)

---

## 6. Phase 5 — Scaffold the work vault *(creates files)*

The `vaults/work/` directory doesn't exist yet. We'll init it as a git repo
and use ar9av's `/wiki-setup` skill to scaffold the directory tree.

```bash
cd /mnt/host/shared/git/kb
mkdir -p vaults/work
cd vaults/work
git init -b main
# Obsidian recognizes .obsidian/ as the vault marker; ar9av's /wiki-setup creates it
```

Then from inside the ar9av repo, launch Claude and run the setup skill:

```bash
cd /mnt/host/shared/git/kb/ar9av-obsidian-wiki
wiki-switch work       # sanity — should already be active after §5
claude
```

Inside the Claude session:
```
> /wiki-setup
```

This runs ar9av's `wiki-setup` skill, which scaffolds:
- `concepts/`, `entities/`, `skills/`, `references/`, `synthesis/`, `journal/`,
  `projects/`, `_archives/`, `_raw/`, `.obsidian/`
- `index.md` (empty catalog, ready to be populated)
- `log.md` (empty activity log)
- `.manifest.json` (empty, waiting for first ingest)

Exit Claude. Back in shell:
```bash
cd /mnt/host/shared/git/kb/vaults/work
git add -A
git commit -m "scaffold: initial vault structure via /wiki-setup"
```

**SVCR.** Confirmed `wiki-setup/SKILL.md:39` creates all required directories.
If `/wiki-setup` prompts for preferences (categories, `.obsidian` config),
accept the defaults — those are already defined in `.env.work`.

---

## 7. Phase 6 — Bootstrap the meta-wiki *(creates the wiki content)*

This is the main event. ar9av reads the four research docs in
`research/` and compiles them into a wiki. Expected output:

- **Entity pages** for: Andrej Karpathy, Steph Ango, Martin Fowler, Kent Beck,
  Simon Willison, Bryan Cantrill, ar9av (the author), nvk, SamurAIGPT, Obsidian,
  Claude Code, Codex, Gemini CLI
- **Concept pages** for: LLM Wiki pattern, Three-layer architecture, Ingest
  (primitive), Query (primitive), Lint (primitive), Fold-back (ingest-merge vs
  query-answer-save), Drift integrity, Provenance markers, Retrieval Primitives
  table, Content-trust boundary, Compound-merge, Visibility tags, File-over-app,
  Vault separation, `.manifest.json` schema
- **Skill pages** (how-to) for: Setting up ar9av, Running wiki-switch, Running
  wiki-run, Writing drift-protected syntheses via prompt
- **Reference pages** (source summaries) for each of the four docs
- **Synthesis pages** for: Panel review methodology, Three-pass revision
  history (§6.1, §6.2, §6.3), Ecosystem unsolved problems

Estimated page count: **30–50 pages on first ingest**. README says ar9av aims
for 10–15 pages per source × 4 sources; realistic with some overlap.

### Run the ingest

```bash
cd /mnt/host/shared/git/kb
wiki-run work ingest
```

`wiki-run` does three things:
1. Calls `wiki-switch work` (belt-and-braces — already set)
2. Runs `claude --print "/wiki-ingest"` in the ar9av repo
3. After ingest completes, `git add -A && git commit` in the vault

The ingest is the expensive step. Claude will read each of the four research
docs, extract entities/concepts/skills, create or update pages, maintain
`[[wikilinks]]`, update `index.md`, append to `log.md`, and write
`.manifest.json`. Count on **10–30 minutes of wall-clock time** depending on
model and load, and a non-trivial token spend (probably $0.50–$2 of Sonnet
usage or equivalent in subscription quota).

**SVCR.** Confirmed via `wiki-ingest/SKILL.md:70` that append mode (the
default) reads `OBSIDIAN_SOURCES_DIR` without deleting. `.manifest.json`
tracks `pages_created` and `pages_updated` per source for delta runs.

### What to do if ingest partially fails

ar9av updates `log.md` incrementally. If Claude errors out mid-ingest:
- The pages already written are valid
- `git commit` (via `wiki-run`) captures partial progress
- Re-running `wiki-run work ingest` picks up where it left off (content-hash
  delta check skips already-ingested sources)

So failure is cheap. No need for pre-flight dry-run.

---

## 8. Phase 7 — Verify the bootstrap

### 8.1 Sanity queries

```bash
cd /mnt/host/shared/git/kb
wiki-run work query "what is the three-layer architecture?"
wiki-run work query "what are the two canonical fold-back pathways?"
wiki-run work query "how do I steer curation in this setup?"
```

Each should produce a synthesized answer with `[[wikilink]]` citations drawn
from the ingested pages. If answers cite the right pages and don't hallucinate,
the bootstrap worked.

### 8.2 Lint pass

```bash
wiki-run work lint
```

Look for:
- Orphan pages (should be few — the four source docs are densely interlinked)
- Broken wikilinks (should be zero)
- Provenance-drift flags (may flag the meta-wiki as inferred-heavy; expected)

### 8.3 Inspect the graph

From the laptop eventually (after you set up the laptop-side git clone), open
the work vault in Obsidian and flip to Graph view. The shape of the graph is
your first visceral read of whether the meta-wiki is coherent.

---

## 9. Rollback

If at any point you want to undo:

**Phase 1 (cleanup):** re-clone from GitHub. Takes seconds.

**Phases 2–6 (config + scaffold):** delete the created artifacts.
```bash
rm -rf /mnt/host/shared/git/kb/vaults
rm -rf /mnt/host/shared/git/kb/scripts
rm /mnt/host/shared/git/kb/ar9av-obsidian-wiki/.env \
   /mnt/host/shared/git/kb/ar9av-obsidian-wiki/.env.work
rm -rf ~/.obsidian-wiki/
rm ~/.claude/skills/wiki-update ~/.claude/skills/wiki-query 2>/dev/null
# Move research docs back to kb/ root:
mv /mnt/host/shared/git/kb/research/*.md /mnt/host/shared/git/kb/
rmdir /mnt/host/shared/git/kb/research
```

**Phase 7 (ingest):** the vault is a git repo, so
`cd vaults/work && git reset --hard HEAD~1` undoes the ingest commit;
`git reflog` gives you longer history if multiple ingests happened.

---

## 10. What this doesn't include

- **No personal vault.** Deferred. Pattern is identical: `mkdir vaults/personal`,
  `cp .env.work .env.personal` (swap paths), `wiki-switch personal && /wiki-setup`.
  Do it when the work vault rhythm is settled.
- **No automation.** No cron, no systemd. Run `wiki-run work lint` manually
  when you want a health check.
- **No laptop setup.** Once the work vault exists, you'll clone it on your
  laptop per the architecture doc §6.2. Defer to after bootstrap is verified.
- **No QMD semantic search.** `.env.work` leaves the QMD collection vars
  empty; ar9av falls back to grep. Adequate for 30–50 pages.

---

## 11. Open questions for you before I execute

1. **Claude Code credentials.** This setup assumes you have Claude Code
   installed on the server and authenticated. If not, you'll need to
   `claude login` as your user before the `wiki-run` calls will work.
2. **Which model.** ar9av's skills inherit whatever model your Claude Code
   defaults to. Sonnet is the sweet spot for ingest. Opus for quality,
   Haiku for speed. Confirm your default.
3. **Subscription vs API.** If you're on a Claude Pro/Max subscription,
   ingest is "free" against your quota. If it's API-billed, expect $0.50–$2
   for the initial bootstrap.
4. **Approval mode.** ar9av writes to the vault. If your Claude Code is in
   restrictive permission mode, every `Write` call will prompt. You may want
   to `--permission-mode acceptEdits` for the ingest run specifically.
5. **Do you want to keep `BOOTSTRAP-PROPOSAL.md` after execution?** I'd
   convert it to a `BOOTSTRAP-LOG.md` with timestamps of each phase as I
   execute. Confirms-or-rejects each step.

---

## 12. SVCR on this proposal

**Self-validate.** Walked through each phase against ar9av source:
- wiki-ingest append mode (default): reads `OBSIDIAN_SOURCES_DIR`, doesn't
  delete. ✓
- wiki-setup scaffolds vault structure. ✓
- wiki-lint catches broken links, orphans, provenance drift. ✓
- `setup.sh`'s re-prompt logic skips when `.env` has a real path. ✓
- Global skills install into `~/.claude/skills/`. ✓
- Content-hash delta makes re-ingest idempotent. ✓

**Critique.**
- *"30–50 pages on first ingest feels high."* — Possibly. `OBSIDIAN_MAX_PAGES_PER_INGEST=15`
  caps per-source; with four sources that's a theoretical max of 60, but in
  practice there's heavy overlap (entities cited across all four docs).
  Adjust the cap downward in `.env.work` if you want a smaller first pass.
- *"setup.sh installs global skills into other agents' directories
  (Codex, Gemini) even if you don't use them."* — Yes, harmless, but worth
  knowing. Easy to remove post-setup.
- *"What if `/wiki-setup` conflicts with the already-initialized git repo
  in `vaults/work/`?"* — It won't; wiki-setup creates files and directories,
  and `git init` doesn't fight with that. First commit captures everything.
- *"I assumed Claude Code is already installed."* — Flagged as open question
  #1.

**Refine.** Added §11 "Open questions for you before I execute" as a
forcing function for the prerequisites I couldn't verify from here. Moved
from implicit assumptions to explicit asks.

---

## 13. Approval protocol

Reply with one of:

- **"approved all"** — I execute phases 1–7 sequentially, writing a
  `BOOTSTRAP-LOG.md` as I go.
- **"approved except N"** — I skip phase N and proceed with the rest.
- **"stop at phase N"** — I execute through phase N and pause for review.
- **"edit X"** — call out what to change; I revise this proposal.
- **"reject"** — I delete this file and wait for a different plan.

Given the destructive nature of Phase 1 (rm -rf), I will not proceed
without explicit approval.
