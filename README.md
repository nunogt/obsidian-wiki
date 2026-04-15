# obsidian-wiki

[![Ask DeepWiki](https://deepwiki.com/badge.svg)](https://deepwiki.com/Ar9av/obsidian-wiki)

A knowledge mgmt system inspired by [gist](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f) published by Andrej Karpathy about maintaining a personal knowledge base with LLMs : the "LLM Wiki" pattern.

Instead of asking an LLM the same questions over over (or doing RAG every time), you compile knowledge once into interconnected markdown files and keep them current. In this case Obsidian is the viewer and the LLM is the maintainer.

We took that and built a framework around it. The whole thing is a set of markdown skill files that any AI coding agent (Claude Code, Cursor, Windsurf, whatever you use) can read and execute. You point it at your Obsidian vault and tell it what to do.

> **This is a fork** of [Ar9av/obsidian-wiki](https://github.com/Ar9av/obsidian-wiki) carrying local patches for multi-vault deployments (CWD-based profile selection, in-vault sources, rebase-maintained upstream). For the single-user / single-vault onboarding experience, see the upstream README.

## Quick Start

### Install via Skills CLI

```bash
npx skills add Ar9av/obsidian-wiki
```

This installs all wiki skills into your current agent (Claude Code, Cursor, Codex, etc.). Then open your agent and say **"set up my wiki"**.

Browse the full skill list at [skills.sh/ar9av/obsidian-wiki](https://skills.sh/ar9av/obsidian-wiki).

### Install via git clone

```bash
git clone https://github.com/nunogt/obsidian-wiki.git
cd obsidian-wiki
```

That's it — in-repo agent symlinks (`.claude/skills/`, `.cursor/skills/`, `.agents/skills/`, `.windsurf/skills/`) are committed as relative paths so they work out of the box on any clone.

Create a `.env` pointing at your Obsidian vault:

```bash
cp .env.example .env
# Edit .env and set OBSIDIAN_VAULT_PATH=/absolute/path/to/your/vault
```

Open the project in your agent and say **"set up my wiki"**. That's it.

### Multi-vault deployment

For running multiple isolated vaults with concurrent Claude sessions, see [kb-system](https://github.com/nunogt/kb-system) — an infrastructure repo that adds CWD-based profile directories, per-vault in-vault sources (`$VAULT/_sources/`), and rebase-maintained fork upstream. The skills in this fork carry patches (`OBSIDIAN_INVAULT_SOURCES_DIR` exclusion across scanning skills, CWD-first config ordering) that enable that pattern without re-introducing the single-vault shared global state.

## Agent Compatibility

This framework works with **any AI coding agent** that can read files. Each agent has its own convention for discovering skills; this fork's in-repo symlinks under `.claude/skills/`, `.cursor/skills/`, `.agents/skills/`, and `.windsurf/skills/` are committed (as relative paths), so a fresh clone works immediately for those four:

| Agent                                                     | Bootstrap Files                     | Skills Directory                | Slash Commands                          |
| --------------------------------------------------------- | ---------------------------------- | ------------------------------- | --------------------------------------- |
| **[Claude Code](https://claude.ai/code)**                 | `CLAUDE.md`                        | `.claude/skills/`               | ✅ `/wiki-ingest`, `/wiki-status`, etc. |
| **[Cursor](https://cursor.com)**                          | `.cursor/rules/obsidian-wiki.mdc`  | `.cursor/skills/`               | ✅ `/wiki-ingest`, `/wiki-status`, etc. |
| **[Windsurf](https://windsurf.com)**                      | `.windsurf/rules/obsidian-wiki.md` | `.windsurf/skills/`             | ✅ via Cascade                          |
| **[Codex (OpenAI)](https://openai.com/codex)**            | `AGENTS.md`                        | `~/.codex/skills/` (manual symlink) | `/wiki...`                              |
| **[Antigravity (Google)](https://aistudio.google.com)**   | `GEMINI.md`                        | `~/.gemini/antigravity/skills/` (manual symlink) | `update wiki`                           |
| **[OpenClaw](https://openclaw.ai)**                       | `AGENTS.md`                        | `.agents/skills/` + `~/.agents/skills/` (manual symlink for the global path) | — (trigger by phrase)           |
| **[GitHub Copilot](https://github.com/features/copilot)** | `.github/copilot-instructions.md`  | —                               | —                                       |
| **[Kilocode](https://kilo.ai/)**                          | `AGENTS.md` (primary) or `CLAUDE.md` (compatibility)         | `.agents/skills/` + `.claude/skills/` | ✅ `/wiki-ingest`, `/wiki-status`, etc. |

**Manual global symlinks** (for Codex, Antigravity, OpenClaw global discovery):

```bash
ln -sfn "$(pwd)/.skills" ~/.codex/skills
ln -sfn "$(pwd)/.skills" ~/.gemini/antigravity/skills
ln -sfn "$(pwd)/.skills" ~/.agents/skills
```

Use these only if you want a single vault's skills globally routable from any project. Multi-vault deployments (kb-system) should NOT create these global paths — they'd route all sessions to one vault.

## How it works

Every ingest runs through four stages:

**1. Ingest** — The agent reads your source material directly. It handles whatever you throw at it: markdown files, PDFs (with page ranges), JSONL conversation exports, plain text logs, chat exports, meeting transcripts, and images (screenshots, whiteboard photos, diagrams — vision-capable model required). No preprocessing step, no pipeline to run. The agent reads the file the same way it reads code.

**2. Extract** — From the raw source, the agent pulls out concepts, entities, claims, relationships, and open questions. A conversation about debugging a React hook yields a "stale closure" pattern. A research paper yields the key idea and its caveats. A work log yields decisions and their rationale. Noise gets dropped, signal gets kept. Each page also gets a 1–2 sentence `summary:` in its frontmatter at write time — later queries use this to preview pages without opening them.

**3. Resolve** — New knowledge gets merged against what's already in the wiki. If a concept page exists, the agent updates it — merging new information, noting contradictions, strengthening cross-references. If it's genuinely new, a page gets created. Nothing is duplicated. Sources are tracked in frontmatter so every claim stays attributable.

**4. Schema** — The wiki schema isn't fixed upfront. It emerges from your sources and evolves as you add more. The agent maintains coherence: categories stay consistent, wikilinks point to real pages, the index reflects what's actually there. When you add a new domain (a new project, a new field of study), the schema expands to accommodate it without breaking what exists.

A `.manifest.json` tracks every source that's been ingested — path, timestamps, which wiki pages it produced. On the next ingest, the agent computes the delta and only processes what's new or changed.

## What we added on top of Karpathy's pattern

- **Delta tracking.** A manifest tracks every source file that's been ingested: path, timestamps, which wiki pages it produced. When you come back later, it computes the delta and only processes what's new or changed. You're not re-ingesting your entire document library every time.

- **Project-based organization.** Knowledge gets filed under projects when it's project-specific, globally when it's not. Both are cross-referenced with wikilinks. If you're working on 10 different codebases, each one gets its own space in the vault.

- **Archive and rebuild.** When the wiki drifts too far from your sources, you can archive the whole thing (timestamped snapshot, nothing lost) and rebuild from scratch. Or restore any previous archive.

- **Multi-agent ingest.** Documents, PDFs, Claude Code history (`~/.claude`), Codex sessions (`~/.codex/`), Windsurf data (`~/.windsurf`), ChatGPT exports, Slack logs, meeting transcripts, raw text. There are dedicated skills for both Claude history and Codex history, plus a catch-all ingest skill for arbitrary text exports.

- **Audit and lint.** Find orphaned pages, broken wikilinks, stale content, contradictions, missing frontmatter. See a dashboard of what's been ingested vs what's pending.

- **Automated cross-linking.** After ingesting new pages, the cross-linker scans the vault for unlinked mentions and weaves them into the knowledge graph with `[[wikilinks]]`. No more orphan pages.

- **Tag taxonomy.** A controlled vocabulary of canonical tags stored in `_meta/taxonomy.md`, with a skill that audits and normalizes tags across your entire vault.

- **Provenance tracking.** Every claim on a wiki page is tagged: extracted (default), `^[inferred]` (LLM synthesis), or `^[ambiguous]` (sources disagree). A `provenance:` block in the frontmatter summarizes the mix per page, and `wiki-lint` flags pages that drift into mostly speculation. You can always tell what your wiki actually knows from what it guessed.

- **Multimodal sources.** Screenshots, whiteboard photos, slide captures, and diagrams ingest the same way as text — the agent transcribes any visible text verbatim and tags interpreted content as inferred. Requires a vision-capable model.

- **Wiki insights.** Beyond delta tracking, `wiki-status` can analyze the shape of your vault itself: top hubs, bridge pages (nodes whose removal would partition the graph), tag cluster cohesion scores, scored surprising connections, a graph delta since last run, and suggested questions the wiki structure is uniquely positioned to answer. Output goes to `_insights.md`.

- **Graph export.** `wiki-export` turns the vault's wikilink graph into `graph.json` (queryable), `graph.graphml` (Gephi/yEd), `cypher.txt` (Neo4j), and a self-contained `graph.html` interactive browser visualization — no server required.

- **Tiered retrieval.** `wiki-query` reads titles, tags, and page summaries first and only opens page bodies when the cheap pass can't answer. Say "quick answer" or "just scan" to force index-only mode. Keeps query cost roughly flat as your vault grows from 20 pages to 2000.

- **QMD semantic search (optional).** [QMD](https://github.com/tobi/qmd) is a local MCP server that indexes your wiki and source documents for fast semantic search. When `QMD_WIKI_COLLECTION` is set in `.env`, `wiki-query` runs a lex+vec pass against the collection before falling back to Grep — enabling concept-level matches that exact-string search misses. When `QMD_PAPERS_COLLECTION` is set, `wiki-ingest` queries your indexed sources before writing a new page, surfacing related work, detecting contradictions, and deciding whether to create or merge. Without QMD, both skills fall back to Grep/Glob and remain fully functional.

- **`_raw/` staging directory.** Drop rough notes, clipboard pastes, or quick captures into `_raw/` inside your vault. The next `wiki-ingest` run promotes them to proper wiki pages and removes the originals. Configured via `OBSIDIAN_RAW_DIR` in `.env` (defaults to `_raw`).

- **In-vault sources (`OBSIDIAN_INVAULT_SOURCES_DIR`).** For multi-vault deployments, this fork adds an env var that six vault-scanning skills (`cross-linker`, `tag-taxonomy`, `wiki-export`, `wiki-lint`, `wiki-status`, `wiki-ingest`) honor — skipping a vault-relative path (typically `_sources/`) from their globs. Without this, in-vault source documents would be mistreated as wiki pages.

## Optional: QMD Semantic Search

By default, `wiki-ingest` and `wiki-query` use `Grep`/`Glob` for search — fully functional, no extra setup. If your vault grows large or you want concept-level matches across your sources, you can plug in [QMD](https://github.com/tobi/qmd): a local MCP server that runs lex+vec queries against indexed collections.

**Setup:**

1. Install QMD and add it to your MCP config (see the QMD repo for instructions).
2. Index your wiki and/or source documents:
   ```bash
   qmd index --name wiki /path/to/your/vault
   qmd index --name papers /path/to/your/sources
   ```
3. Set the collection names in your `.env`:
   ```env
   QMD_WIKI_COLLECTION=wiki      # used by wiki-query
   QMD_PAPERS_COLLECTION=papers  # used by wiki-ingest (source discovery)
   ```

**What changes with QMD enabled:**

- **`wiki-query`** runs a semantic pass (lex+vec) against your wiki collection before falling back to Grep. Finds conceptually related pages even when the exact terms don't match.
- **`wiki-ingest`** queries your papers collection before writing a new page — surfaces related sources, spots contradictions, and decides whether to create a new page or merge into an existing one.

Both skills degrade gracefully: if `QMD_WIKI_COLLECTION` / `QMD_PAPERS_COLLECTION` are not set, they skip the QMD step silently and use Grep instead.

### `_raw/` Staging Directory

`_raw/` is a staging area inside your vault for unprocessed captures — rough notes, clipboard pastes, quick voice-memo transcripts. Drop files there and the next `wiki-ingest` run will promote them to proper wiki pages and remove the originals.

The directory is created automatically by `wiki-setup`. The path is configurable via `OBSIDIAN_RAW_DIR` in `.env` (defaults to `_raw`).

---

## Skills

Everything lives in `.skills/`. Each skill is a markdown file the agent reads when triggered:

| Skill                   | What it does                                      | Slash Command            |
| ----------------------- | ------------------------------------------------- | ------------------------ |
| `wiki-setup`            | Initialize vault structure                        | `/wiki-setup`            |
| `wiki-ingest`           | Distill any source into wiki pages — documents, images, agent history (`~/.claude`, `~/.codex`), chat exports (ChatGPT, Slack, Discord), CSV/HTML, arbitrary text. Format dispatch in Step 1; references for per-format parsing. | `/wiki-ingest`           |
| `wiki-status`           | Show what's ingested, what's pending, the delta   | `/wiki-status`           |
| `wiki-rebuild`          | Archive, rebuild from scratch, or restore         | `/wiki-rebuild`          |
| `wiki-query`            | Answer questions from the wiki                    | `/wiki-query`            |
| `wiki-lint`             | Find broken links, orphans, contradictions        | `/wiki-lint`             |
| `cross-linker`          | Auto-discover and insert missing wikilinks        | `/cross-linker`          |
| `tag-taxonomy`          | Enforce consistent tag vocabulary across pages    | `/tag-taxonomy`          |
| `llm-wiki`              | The core pattern and architecture reference       | `/llm-wiki`              |
| `wiki-ar9av-update`     | Rebase our fork onto upstream + regen contexts (fork-specific) | `/wiki-ar9av-update` |
| `wiki-export`           | Export vault graph to JSON, GraphML, Neo4j, HTML  | `/wiki-export`           |
| `skill-creator`         | Create new skills                                 | `/skill-creator`         |

> **Note:** Slash commands (`/skill-name`) work in Claude Code, Cursor, and Windsurf. In other agents, just describe what you want and the agent will find the right skill.

### Recommended: Obsidian Skills by Kepano

We handle the knowledge management workflow — ingest, query, lint, rebuild. For Obsidian format mastery, we recommend installing [**kepano/obsidian-skills**](https://github.com/kepano/obsidian-skills) alongside this framework. These are optional but improve the quality of wiki output:

| Skill | What it adds |
|---|---|
| `obsidian-markdown` | Teaches the agent correct Obsidian-flavored syntax — wikilinks, callouts, embeds, properties |
| `obsidian-bases` | Create and edit `.base` files (database-like views of notes) |
| `json-canvas` | Create and edit `.canvas` files (visual mind maps, flowcharts) |
| `obsidian-cli` | Interact with a running Obsidian instance via CLI (search, create, manage notes) |
| `defuddle` | Extract clean markdown from web pages — less noise than raw fetch, saves tokens during ingest |

Both projects use the same [Agent Skills spec](https://agentskills.io/specification), so they coexist in the same `.skills/` directory with no conflicts.

**Install:**

```bash
npx skills add kepano/obsidian-skills
```

After installing, your agent will automatically pick up the new skills alongside the existing wiki skills.

## Project Structure

```
obsidian-wiki/
├── .skills/                          # ← Canonical skill definitions (source of truth)
│   ├── wiki-setup/SKILL.md
│   ├── wiki-ingest/SKILL.md          # unified ingest (5 prior skills consolidated)
│   │   └── references/               # per-format parsing: claude/codex/text/images/qmd
│   ├── wiki-status/SKILL.md
│   ├── wiki-rebuild/SKILL.md
│   ├── wiki-query/SKILL.md
│   ├── wiki-lint/SKILL.md
│   ├── cross-linker/SKILL.md
│   ├── tag-taxonomy/SKILL.md
│   ├── llm-wiki/SKILL.md
│   ├── wiki-ar9av-update/SKILL.md   # fork-specific — upstream-pull maintenance
│   ├── wiki-export/SKILL.md
│   └── skill-creator/SKILL.md
│
├── CLAUDE.md                         # Bootstrap → Claude Code / Kilocode
├── GEMINI.md                         # Bootstrap → Gemini / Antigravity
├── AGENTS.md                         # Bootstrap → Codex / OpenAI / Kilocode
├── .cursor/rules/obsidian-wiki.mdc   # Bootstrap → Cursor
├── .windsurf/rules/obsidian-wiki.md  # Bootstrap → Windsurf
├── .github/copilot-instructions.md   # Bootstrap → GitHub Copilot
│
├── .claude/skills/   → committed relative symlinks to .skills/*
├── .cursor/skills/   → committed relative symlinks to .skills/*
├── .windsurf/skills/ → committed relative symlinks to .skills/*
├── .agents/skills/   → committed relative symlinks to .skills/*
│
├── .env.example                      # Configuration template
├── README.md                         # You are here
└── SETUP.md                          # Detailed setup guide
```

## Contributing

This is early. The skills work but there's a lot of room to make them smarter — better cross-referencing, smarter deduplication, handling larger vaults, new ingest sources. If you've been thinking about this problem or have a workflow that could be a skill, PRs are welcome.

### Adding a new skill

1. Create a folder in `.skills/your-skill-name/`
2. Add a `SKILL.md` with YAML frontmatter (`name`, `description`) and markdown instructions
3. Create relative symlinks in each in-repo agent dir: `ln -sfn ../../.skills/your-skill-name .claude/skills/your-skill-name` (repeat for `.cursor/skills/`, `.agents/skills/`, `.windsurf/skills/`)
4. Commit the skill + symlinks
5. Test with your agent by saying something that matches the description

See `.skills/skill-creator/SKILL.md` for the full guide on writing effective skills.
