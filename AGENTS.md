# Obsidian Wiki — Agent Context

A **skill-based framework** for building and maintaining an Obsidian knowledge base. No scripts or dependencies — everything is markdown instructions that you execute directly.

## Configuration

Read config in this order (first found wins — CWD takes precedence so multi-vault sessions always read their own context):

1. **`.env`** in the current working directory — local config (CWD-based multi-vault setups; e.g. `kb-system/contexts/<name>/.env`)
2. **`~/.obsidian-wiki/config`** — legacy global config fallback (single-vault setups)

Both files set `OBSIDIAN_VAULT_PATH` (where the wiki lives). CWD-based deployments set `OBSIDIAN_INVAULT_SOURCES_DIR` in `.env` to enable per-vault in-vault sources; the global config supports only single-vault single-path routing.

## Vault Structure

```
$OBSIDIAN_VAULT_PATH/
├── index.md                # Master index — every page listed, always kept current
├── log.md                  # Chronological activity log (ingests, updates, lints)
├── .manifest.json          # Tracks every ingested source: path, timestamps, pages produced
├── _meta/
│   └── taxonomy.md         # Controlled tag vocabulary
├── _insights.md            # Graph analysis output (hubs, bridges, dead ends)
├── _raw/                   # Staging area — drop rough notes here, next ingest promotes them
├── concepts/               # Abstract ideas, patterns, mental models
├── entities/               # Concrete things — people, tools, libraries, companies
├── skills/                 # How-to knowledge, techniques, procedures
├── references/             # Factual lookups — specs, APIs, configs
├── synthesis/              # Cross-cutting analysis connecting multiple concepts
├── journal/                # Time-bound entries — daily logs, session notes
└── projects/
    └── <project-name>.md   # One page per project synced via wiki-update
```

Every wiki page has required frontmatter: `title`, `category`, `tags`, `sources`, `created`, `updated`. Pages connect via `[[wikilinks]]`.

## Skill Routing

Skills live in `.skills/<name>/SKILL.md`. Match the user's intent to the right skill:

| User says something like… | Skill |
|---|---|
| "set up my wiki" / "initialize" | `wiki-setup` |
| "/wiki-history-ingest claude" / "/wiki-history-ingest codex" / "$wiki-history-ingest claude|codex" | `wiki-history-ingest` |
| "ingest" / "add this to the wiki" / "process these docs" | `wiki-ingest` |
| "import my Claude history" / "mine my conversations" | `claude-history-ingest` |
| "import my Codex history" / "mine my Codex sessions" | `codex-history-ingest` |
| "process this export" / "ingest this data" / logs, transcripts | `data-ingest` |
| "what's the status" / "what's been ingested" / "show the delta" | `wiki-status` |
| "wiki insights" / "hubs" / "wiki structure" | `wiki-status` (insights mode) |
| "what do I know about X" / "find info on Y" / any question | `wiki-query` |
| "audit" / "lint" / "find broken links" / "wiki health" | `wiki-lint` |
| "rebuild" / "start over" / "archive" / "restore" | `wiki-rebuild` |
| "link my pages" / "cross-reference" / "connect my wiki" | `cross-linker` |
| "fix my tags" / "normalize tags" / "tag audit" | `tag-taxonomy` |
| "update wiki" / "sync to wiki" / "save this to my wiki" | `wiki-ingest` with an explicit source path (this fork has retired the old `wiki-update` skill) |
| "pull upstream ar9av" / "update the fork" / "rebase on upstream" | `wiki-ar9av-update` |
| "export wiki" / "export graph" / "graphml" / "neo4j" | `wiki-export` |
| "create a new skill" | `skill-creator` |

## Cross-Project Usage

This fork targets **multi-vault deployments** where each vault has its own context directory (`kb-system/contexts/<name>/`) containing per-profile symlinks. The current working directory of a Claude session selects the profile — there's no global config file routing every session to one vault.

### Writing to the wiki from another project

Open a Claude session in the target vault's context directory, then run `/wiki-ingest` with the project path as a source:

```bash
cd /mnt/host/shared/git/kb-system/contexts/<vault>
claude --dangerously-skip-permissions
> /wiki-ingest /path/to/project
```

The upstream `wiki-update` skill (which read a single global config file) has been retired in this fork — it was incompatible with the multi-vault model. See `concepts/wiki-update-deprecation` in the wiki-managed docs.

### Reading from the wiki

1. Read config in this order (first found wins): `.env` in CWD (multi-vault setups), then `~/.obsidian-wiki/config` (legacy single-vault fallback)
2. Scan titles, tags, and `summary:` frontmatter fields first (cheap pass)
3. Only open page bodies when the index pass can't answer
4. Return a synthesized answer with `[[wikilink]]` citations

## Visibility Tags (optional)

Pages can carry a `visibility/` tag to mark their intended reach. **This is entirely optional** — untagged pages behave exactly as they always have (visible everywhere). The system stays single-vault, single source of truth.

| Tag | Meaning |
|---|---|
| *(no tag)* | Same as `visibility/public` — visible in all modes |
| `visibility/public` | Explicitly public — visible in all modes |
| `visibility/internal` | Team-only — excluded when querying in filtered mode |
| `visibility/pii` | Sensitive data — excluded when querying in filtered mode |

**Filtered mode** is opt-in, triggered by phrases like "public only", "user-facing answer", "no internal content", or "as a user would see it" in a query. Default mode shows everything.

`visibility/` tags are **system tags** — they don't count toward the 5-tag limit and are listed separately from domain/type tags in the taxonomy.

See `wiki-query` and `wiki-export` skills for how the filter is applied.

## Core Principles

- **Compile, don't retrieve.** The wiki is pre-compiled knowledge. Update existing pages — don't append or duplicate.
- **Track everything.** Update `.manifest.json` after ingesting, `index.md` and `log.md` after any operation.
- **Connect with `[[wikilinks]]`.** Every page should link to related pages. This is what makes it a knowledge graph, not a folder of files.
- **Frontmatter is required.** Every wiki page needs: `title`, `category`, `tags`, `sources`, `created`, `updated`.
- **Single source of truth.** Visibility tags shape how content is surfaced — they don't duplicate or separate it.

## Architecture Reference

For the full pattern (three-layer architecture, page templates, project org), read `.skills/llm-wiki/SKILL.md`.
