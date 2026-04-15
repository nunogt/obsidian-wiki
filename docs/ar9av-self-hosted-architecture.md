# Self-hosted ar9av/obsidian-wiki — architecture and operations

Evergreen reference for self-hosting [ar9av/obsidian-wiki][ar9av] under
Karpathy's LLM Wiki pattern. Describes the *pattern* — concrete examples
use `wiki` (the base reference vault) and a generic `<scope>` placeholder
for additional vaults.

[ar9av]: https://github.com/Ar9av/obsidian-wiki

---

## 1. The governing principle

From Karpathy's gist, verbatim:

> You never (or rarely) write the wiki yourself — the LLM writes and
> maintains all of it. You're in charge of sourcing, exploration, and
> asking the right questions. […] Obsidian is the IDE; the LLM is the
> programmer; the wiki is the codebase.

And:

> The human's job is to curate sources, direct the analysis, ask good
> questions, and think about what it all means. The LLM's job is
> everything else.

This architecture takes the strict end of "never (or rarely)" as the
operating discipline: **no direct human writes to compiled wiki pages**.
The human's write surface is the raw-source layer (via scp) and direct
instructions to the agent. The wiki — entity pages, concept pages,
summaries, cross-references — is output maintained by Claude + ar9av. If
something needs changing on a page, you ask the agent to change it.

Supporting the git substrate choice, the gist notes:

> The wiki is just a git repo of markdown files. You get version history,
> branching, and collaboration for free.

---

## 2. Constraints assumed

| Constraint | Consequence |
|---|---|
| Siblings at a single git root (e.g. `/mnt/host/shared/git/`) | Flat layout; each vault + kb-system + upstream ar9av as peers |
| Laptop writes via scp, reads via git pull | One-way data flow; no SSHFS; no bidirectional sync |
| Single server user | Profile separation by path + config switch, not by Unix user |
| Wiki is LLM-authored; human curates sources | No laptop-side writes to compiled pages |

If any of these don't match your setup, adapt. The core design survives
all four variations cleanly; the specific scripts and paths would differ.

---

## 3. Directory layout

```
/path/to/kb/                                 ← kb-system repo root
├── ar9av-obsidian-wiki/                     ← upstream clone (ignored by kb-system)
│   ├── .env → ../profiles/<active>.env      ← symlink, flipped by wiki-switch
│   └── .skills/                             ← skills live here, shared across profiles
├── vaults/                                  ← each child is an independent git repo
│   ├── wiki/                                ← base reference vault
│   │   ├── .git/
│   │   ├── .obsidian/                       ← Obsidian vault config (committed)
│   │   ├── .manifest.json                   ← ar9av state (tracked sources + SHA-256)
│   │   ├── index.md   log.md
│   │   ├── _raw/                            ← scp target for captures
│   │   ├── _archives/   _meta/   projects/
│   │   └── concepts/ entities/ skills/ references/ synthesis/ journal/
│   └── <scope>/                             ← one dir per vault, same shape as wiki/
├── profiles/                                ← per-vault ar9av config files
│   ├── wiki.env
│   └── <scope>.env
├── research/                                ← source docs ingested by ar9av
│   └── ...
├── scripts/
│   ├── wiki-switch                          ← select active profile
│   ├── wiki-run                             ← run an ar9av op with atomic commit
│   ├── wiki-ar9av-update                    ← pull upstream ar9av safely
│   ├── kb-vault-new                         ← create a new vault (profile + dir + git + remote)
│   └── templates/
│       ├── profile.env                      ← template for new profiles
│       └── vault.gitignore                  ← canonical vault .gitignore
└── .gitignore                               ← excludes ar9av-obsidian-wiki/ and vaults/
```

**Permissions.** Standard user ownership with group `vm-users` (or
equivalent) and mode 2775 on shared directories. No per-scope Unix users.

**Why profiles live in `kb/profiles/`, not inside ar9av.** The ar9av
clone is upstream-tracked; you don't want to fork it just to hold local
config. Profiles versioned in kb-system are reproducible on another
machine via `git clone`.

**Why vaults are siblings of ar9av.** Each is an independent git repo
with its own history and its own remote. Siblings (not children) avoid
nested-repo ambiguity and submodule pain.

---

## 4. Profile files

One per vault, named `<scope>.env`, placed in `kb/profiles/`. Minimal
shape:

```
# Profile: wiki (base reference vault)
OBSIDIAN_VAULT_PATH=/path/to/kb/vaults/wiki
OBSIDIAN_SOURCES_DIR=/path/to/kb/research
OBSIDIAN_CATEGORIES=concepts,entities,skills,references,synthesis,journal
OBSIDIAN_RAW_DIR=_raw
OBSIDIAN_MAX_PAGES_PER_INGEST=15

# QMD semantic search — leave empty for Grep fallback
QMD_WIKI_COLLECTION=
QMD_PAPERS_COLLECTION=
```

`OBSIDIAN_SOURCES_DIR` for the `wiki` vault typically points at
`kb/research/` (the source docs that describe the ar9av pattern itself).
For a domain-specific vault (e.g., a project vault), point it wherever
your raw domain material lives — or leave it unset and use `_raw/`
exclusively.

The ar9av clone's `.env` is a symlink flipped by `wiki-switch`:

```
ar9av-obsidian-wiki/.env -> ../profiles/<active>.env
```

Add `.env` to the ar9av repo's `.gitignore` so profile switches never
stain its working tree. ar9av already does this upstream.

---

## 5. `wiki-switch` — profile selector

Two files change on switch: the `.env` symlink (for ar9av's local skills)
and `~/.obsidian-wiki/config` (for the global skills `wiki-update` and
`wiki-query`).

```bash
#!/bin/bash
set -euo pipefail
KB=/path/to/kb
AR9AV=$KB/ar9av-obsidian-wiki
PROFILES=$KB/profiles
GLOBAL=$HOME/.obsidian-wiki/config

case "${1:-}" in
  show|list) ... ;;
  "") echo "usage: wiki-switch {<profile>|show|list}" >&2; exit 1 ;;
  *)
    envfile="$PROFILES/$1.env"
    [ -f "$envfile" ] || { echo "no such profile: $1" >&2; exit 1; }
    vault=$(grep -E '^OBSIDIAN_VAULT_PATH=' "$envfile" | head -1 | cut -d= -f2- | sed 's/^"//;s/"$//')
    ln -sfn "../profiles/$1.env" "$AR9AV/.env"
    mkdir -p "$(dirname "$GLOBAL")"
    cat > "$GLOBAL" <<EOF
OBSIDIAN_VAULT_PATH="$vault"
OBSIDIAN_WIKI_REPO="$AR9AV"
EOF
    ;;
esac
```

**Generic by design.** Any profile under `profiles/*.env` is valid. To
add a new vault, drop a new profile file and run `wiki-switch <new>`.
Discoverability via `wiki-switch list`.

**Discipline.** Never run two Claude Code sessions against different
profiles concurrently. The global config is per-machine. One
`wiki-switch` sets the mode for everything that follows.

---

## 6. `wiki-run` — op wrapper with atomic commit

Every ar9av operation that writes to the vault should produce one git
commit. Shape:

```bash
#!/bin/bash
set -euo pipefail
scope="${1:?scope required}"; shift
op="${1:?op required}"; shift
KB=/path/to/kb
VAULT=$KB/vaults/$scope

"$KB/scripts/wiki-switch" "$scope" >/dev/null
cd "$KB/ar9av-obsidian-wiki"
claude --print --dangerously-skip-permissions "/wiki-$op $*"

cd "$VAULT"
[ -z "$(git status --porcelain)" ] && { echo "no changes"; exit 0; }
git add -A
git commit -m "ar9av: $op $(date -Iseconds)
scope=$scope
op=$op
args=$*"
```

Usage:
```
wiki-run wiki ingest
wiki-run wiki lint
wiki-run <scope> query "how did X handle Y?"
```

`wiki-switch` runs inside `wiki-run`, so scope is always explicit and
verified in every commit message.

**When the wrapper doesn't earn its keep.** Inside an interactive Claude
session, the profile is already active and Claude can commit itself. Just
prompt `"lint the wiki and commit"` or `"ingest everything in research/
and commit"`. Reserve the wrapper for scripted use and one-shot
invocations.

---

## 7. Day-to-day interaction

### 7.1 Raw captures — scp push

From a laptop, drop material into `_raw/`:

```bash
scp ~/notes.md    server:/path/to/kb/vaults/<scope>/_raw/
scp ~/paper.pdf   server:/path/to/kb/vaults/<scope>/_raw/
```

Or a one-shot wrapper on the laptop:

```bash
#!/bin/bash
# wiki-ingest-scp <scope> FILE...
scp -- "${@:2}" "server:/path/to/kb/vaults/$1/_raw/"
ssh server "wiki-run $1 ingest"
```

Usage: `wiki-ingest-scp wiki ~/notes.md`.

### 7.2 Driving the wiki — Claude Code on the server

```bash
$ ssh server
$ cd /path/to/kb/ar9av-obsidian-wiki
$ wiki-switch <scope>
$ claude --dangerously-skip-permissions
```

Inside the session, ar9av's skills are discoverable via slash commands
or plain-English triggers:

```
> /wiki-ingest
> /wiki-lint
> /wiki-query what do I know about X?
> /wiki-rebuild
> process the updated research/ directory and commit the result
```

Skill routing is defined in ar9av's `CLAUDE.md` (symlinked from
`AGENTS.md`). Triggers like "lint the wiki", "process my drafts",
"what do I know about X" all resolve to the right skill.

### 7.3 Reading the wiki — Obsidian on laptop

One-time per vault:
```bash
git clone git@github.com:<you>/<vault> ~/vaults/<vault>
```

Open in Obsidian: *File → Open vault → Open folder as vault*. Each vault
has its own `.obsidian/` committed to its git repo, so settings follow
the vault across machines.

Install the **Obsidian Git plugin** and configure **pull-only**:
- Enable pull on startup
- Enable pull every N minutes (5–10 recommended)
- **Disable** auto-commit
- **Disable** auto-push

Because the architecture forbids laptop-side writes to compiled pages, a
stray laptop-side `git commit` has no natural home. If you need to edit
a file manually during an SSH session, do it on the server and commit
there.

### 7.4 Curation levers

- **Add sources.** scp into `vaults/<scope>/_raw/` (or drop into
  `kb/research/` for the `wiki` profile), then trigger ingest.
- **Ask for changes.** In a Claude session: *"reorganize the entities
  directory to split tools from services"*, *"merge pages A and B and
  commit"*, *"flag pages in synthesis/ older than three months"*.
- **Call skills explicitly.** `/wiki-lint`, `/cross-linker`,
  `/wiki-rebuild`, `/wiki-status`.
- **Save a good answer as a wiki page.** The gist: *"good answers can be
  filed back into the wiki as new pages."* ar9av doesn't ship this as a
  flag; you bridge it by prompting: *"save the above synthesis as
  synthesis/<slug>.md with sources: populated from the pages you drew
  from, and provenance: with extracted/inferred fractions."* `wiki-run`
  commits the result. Because `sources:` is populated at save time,
  `wiki-lint` check #4 (Stale Content) will later flag it if any listed
  source changes.

You never hand-edit compiled pages. That's the discipline.

---

## 8. Automation (optional)

Lint-on-a-schedule closes the panel-review-flagged "lint not automated"
gap. Simplest wiring is a user crontab line per vault:

```
30 3 * * * /path/to/kb/scripts/wiki-run wiki lint >/dev/null 2>&1
```

Promote to systemd if you need structured logging or better timer
semantics; otherwise cron is fine. You can skip automation entirely and
run `wiki-run <scope> lint` manually when you want a health check — the
architecture doesn't depend on it.

---

## 9. Versioning strategy

Three independently-versioned git repositories match the natural privacy
and update topology:

```
github.com/<you>/kb-system       (private)  ← scripts, profiles, research, docs
github.com/<you>/kb-<scope>      (private)  ← each vault, one per scope (convention: kb- prefix)
github.com/Ar9av/obsidian-wiki   (public)   ← upstream, pulled via wiki-ar9av-update
```

**Naming convention.** Vault remotes are named `kb-<scope>` so they stay
identifiable alongside `kb-system` in a GitHub listing. Local directory
names drop the prefix (e.g., `vaults/wiki/` for remote `kb-wiki`).

**Clone independence.** `git clone <vault>` on a machine without access
to any other vault works cleanly. Work, personal, and shared vaults have
no filesystem or git-history entanglement.

**Update decoupling.** Upstream ar9av progress flows through
`wiki-ar9av-update`. kb-system changes are local commits. Vault content
changes are per-vault commits. Each cadence is independent.

**Privacy segmentation.** Vaults are private. kb-system is private unless
you deliberately share the pattern (it contains no secrets, just paths
and conventions). ar9av stays upstream.

### Why not a monorepo

Tried and rejected:

- **Submodules**: stale pointers, detached-HEAD hazards, two-step updates.
  Vault SHAs change on every ingest — submodule bumps would be constant.
- **Subtree-vendor ar9av**: loses clean upstream tracking; becomes a fork.
  `wiki-ar9av-update` becomes much harder.
- **One big monorepo**: mixes privacy levels. Every machine with the
  monorepo gets every vault. Wrong blast radius.

### What's deliberately not versioned

- `~/.obsidian-wiki/config` — derived by `wiki-switch`
- `~/.claude/skills/{wiki-update,wiki-query}` — created by `setup.sh`
- In-repo agent symlinks (`ar9av-obsidian-wiki/.claude/skills/*` etc.) —
  derived; `wiki-ar9av-update` regenerates across upstream pulls

All derived from running the reproduction steps below. No loss of state.

### Reproducing the full setup on a new machine

Four clones plus two commands:

```bash
mkdir -p /path/to/kb && cd $_
git clone git@github.com:<you>/kb-system .
git clone https://github.com/Ar9av/obsidian-wiki ar9av-obsidian-wiki
git clone git@github.com:<you>/kb-wiki vaults/wiki
# ...and any other vaults, each cloned as git@github.com:<you>/kb-<scope> vaults/<scope>
scripts/wiki-switch wiki
cd ar9av-obsidian-wiki && bash setup.sh
```

setup.sh regenerates agent-directory symlinks for the new machine's
absolute paths. Global config comes from wiki-switch. Done.

### Maintaining ar9av current

Every week or so (or on a GitHub notification):

```
scripts/wiki-ar9av-update
```

The script fetches, previews incoming commits, tags a rollback point,
discards the local symlink rewrites, pulls fast-forward, re-runs
`setup.sh`, and reports any new `.env.example` keys. After a real pull,
run `wiki-lint` on each vault to let ar9av's "lint-is-the-migration"
principle absorb any schema changes.

---

## 10. Day in the life

1. Morning on laptop. Obsidian open on active vault. Obsidian Git plugin
   pulled overnight; vault is fresh.
2. Read the wiki; explore graph view; notice an article referenced in a
   concept page you want to follow up.
3. Save the article locally as markdown; `wiki-ingest-scp <scope>
   ~/Downloads/article.md`. Single command: scp to `_raw/`, ssh
   triggers `wiki-run <scope> ingest`, ar9av compiles, commits.
4. Next Obsidian Git pull brings down the new pages. Graph refreshes.
5. Later: ssh to server, `claude` from the ar9av repo, ask *"walk through
   all pages that cite this article and update the cross-links"*. Exit
   Claude; commit if needed.
6. Periodic: `wiki-run <scope> lint` (or in-session *"lint the wiki and
   commit"*) surfaces drift, orphans, stale content, provenance issues.
   Laptop pulls the report next cycle.

---

## 11. What this architecture doesn't include

- **No bidirectional sync.** Laptop reads, server writes. Different
  design if you need laptop-side editing.
- **No query-answer fold-back primitive.** ar9av omits the `--save` flag
  (see panel review §6.3). Workaround via prompt in §7.4.
- **No encryption at rest.** Add LUKS/ZFS underneath if threat model
  requires.
- **No team usage.** One human per vault.
- **No automated dry-run.** Would require forking ar9av.

---

## 12. Setup checklist

One-time, server-side (assuming `gh` CLI authenticated):

- [ ] Clone kb-system: `git clone git@github.com:<you>/kb-system /path/to/kb`
  (or `git init` + `gh repo create --private` if starting fresh)
- [ ] Clone upstream ar9av: `git clone https://github.com/Ar9av/obsidian-wiki
  /path/to/kb/ar9av-obsidian-wiki`
- [ ] For each new vault: run `scripts/kb-vault-new <scope>` — it handles
  the profile file, vault dir, initial `.gitignore` commit, private GitHub
  remote (`kb-<scope>`), and profile activation in one shot
- [ ] For an existing vault from another machine:
  `git clone git@github.com:<you>/kb-<scope> vaults/<scope>` and ensure
  `profiles/<scope>.env` exists in kb-system
- [ ] `scripts/wiki-switch <scope>`
- [ ] `cd ar9av-obsidian-wiki && bash setup.sh` — installs skills
- [ ] For fresh vaults: `claude --dangerously-skip-permissions`, run
  `/wiki-setup` inside; commit scaffold in `vaults/<scope>/`; `git push`
- [ ] *(Optional)* add cron line per §8 for nightly lint

One-time, laptop-side per vault:

- [ ] `git clone git@github.com:<you>/<vault> ~/vaults/<vault>`
- [ ] Open in Obsidian
- [ ] Install Obsidian Git plugin; configure **pull-only** per §7.3
- [ ] *(Optional)* drop `wiki-ingest-scp` wrapper on laptop per §7.1

Daily use follows §10.

---

## 13. Design notes

**The symlink-indirection pattern** (`.env` → `../profiles/<scope>.env`)
keeps profile files out of the ar9av clone, so they're tracked by
kb-system and immune to upstream pulls.

**Generic `wiki-switch`** dispatches on any file matching
`profiles/*.env`. Adding a new vault requires no code changes — drop a
new profile file, run `wiki-switch <new>`, scaffold the vault.

**The three-repo split** matches three distinct update cadences (rapid
vault changes; occasional kb-system changes; infrequent ar9av upstream
pulls) and three distinct privacy zones.

**Derived state regeneration** is the price of not forking ar9av. Every
`wiki-ar9av-update` run re-creates agent-directory symlinks for the
local path. The script automates the discard-then-regenerate pattern
around pulls.

**Single-user model trade-off.** This design gives up the
blast-radius-cap a per-user model would provide. A profile-switch error
followed by a destructive op could touch the wrong vault. Mitigations:
`wiki-switch show` before risky ops; `wiki-run`'s commit messages
always log the scope; git rollback is one command.

---

## 14. Why there is no "governance vault"

A natural temptation is to use the `wiki` vault (which contains
meta-knowledge about ar9av itself) as a "governance layer" that
propagates conventions to other vaults. **This doesn't work
structurally** and shouldn't be attempted:

- ar9av has no cross-vault inheritance, no shared-concept mechanism, no
  template-vault feature.
- Claude doesn't read your vault content to decide how to behave — it
  reads `.skills/*/SKILL.md` and `CLAUDE.md`/`AGENTS.md`. Those are the
  actual governance layer, and they already propagate to every vault
  automatically via the shared `scripts/` and `~/.claude/skills/`.

The `wiki` vault is best understood as a **reference and learning
resource about the ar9av system itself** — valuable to the human when
they want to understand *why* a convention exists, but carrying no
mechanical authority over other vaults.

If you want shared *domain* concepts across vaults (people, frameworks,
shared projects), the honest path is to ingest those source docs into
each vault independently. Cross-vault linking isn't a feature ar9av
supports, and a governance-layer framing would only obscure that.
