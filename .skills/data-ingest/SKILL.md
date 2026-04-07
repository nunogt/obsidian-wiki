---
name: data-ingest
description: >
  Ingest any raw text data, conversation logs, chat exports, or unstructured documents into the Obsidian wiki.
  Use this skill when the user wants to process data that isn't standard documents or Claude history —
  things like ChatGPT exports, Slack threads, Discord logs, meeting transcripts, journal entries, CSV data,
  browser bookmarks, email archives, or any raw text dump. Triggers on "ingest this data", "process these logs",
  "add this export to the wiki", "import my chat history from X". This is the catch-all for any text source
  not covered by the more specific ingest skills.
---

# Data Ingest — Universal Text Source Handler

You are ingesting arbitrary text data into an Obsidian wiki. The source could be anything — conversation exports, log files, transcripts, data dumps. Your job is to figure out the format, extract knowledge, and distill it into wiki pages.

## Before You Start

1. Read `.env` to get `OBSIDIAN_VAULT_PATH`
2. Read `.manifest.json` at the vault root — check if this source has been ingested before
3. Read `index.md` at the vault root to know what already exists

If the source path is already in `.manifest.json` and the file hasn't been modified since `ingested_at`, tell the user it's already been ingested. Ask if they want to re-ingest anyway.

## Step 1: Identify the Source Format

Read the file(s) the user points you at. Common formats you'll encounter:

| Format | How to identify | How to read |
|---|---|---|
| **JSON / JSONL** | `.json` / `.jsonl` extension, starts with `{` or `[` | Parse with Read tool, look for message/content fields |
| **Markdown** | `.md` extension | Read directly |
| **Plain text** | `.txt` extension or no extension | Read directly |
| **CSV / TSV** | `.csv` / `.tsv`, comma or tab separated | Parse rows, identify columns |
| **HTML** | `.html`, starts with `<` | Extract text content, ignore markup |
| **Chat export** | Varies — look for turn-taking patterns (user/assistant, human/ai, timestamps) | Extract the dialogue turns |

### Common Chat Export Formats

**ChatGPT export** (`conversations.json`):
```json
[{"title": "...", "mapping": {"node-id": {"message": {"role": "user", "content": {"parts": ["text"]}}}}}]
```

**Slack export** (directory of JSON files per channel):
```json
[{"user": "U123", "text": "message", "ts": "1234567890.123456"}]
```

**Generic chat log** (timestamped text):
```
[2024-03-15 10:30] User: message here
[2024-03-15 10:31] Bot: response here
```

Don't try to handle every format upfront — read the actual data, figure out the structure, and adapt.

## Step 2: Extract Knowledge

Regardless of format, extract the same things:

- **Topics** discussed — what subjects come up?
- **Decisions** made — what was concluded or decided?
- **Facts** learned — what concrete information is stated?
- **Procedures** described — how-to knowledge, workflows, steps
- **Entities** mentioned — people, tools, projects, organizations
- **Connections** — how do topics relate to each other and to existing wiki content?

### For conversation data specifically:

Focus on the **substance**, not the dialogue. A 50-message debugging session might yield one skills page about the fix. A long brainstorming chat might yield three concept pages.

Skip:
- Greetings, pleasantries, meta-conversation ("can you help me with...")
- Repetitive back-and-forth that doesn't add new information
- Raw code dumps (unless they illustrate a reusable pattern)

## Step 3: Cluster and Deduplicate

Before creating pages:
- Group extracted knowledge by topic (not by source file or conversation)
- Check existing wiki pages — does this knowledge belong on an existing page?
- Merge overlapping information from multiple sources
- Note contradictions between sources

## Step 4: Distill into Wiki Pages

Follow the `wiki-ingest` skill's process for creating/updating pages:

- Use correct category directories (`concepts/`, `entities/`, `skills/`, etc.)
- Add YAML frontmatter with title, category, tags, sources
- Use `[[wikilinks]]` to connect to existing pages
- Attribute claims to their source
- **Apply provenance markers** per the convention in `llm-wiki`. Conversation, log, and chat data tend to be high-inference — you're often reading between the turns to extract a coherent claim. Be liberal with `^[inferred]` for synthesized patterns and with `^[ambiguous]` when speakers contradict each other or you're unsure who's right. Write a `provenance:` frontmatter block on each new/updated page.

## Step 5: Update Manifest and Special Files

**`.manifest.json`** — Add an entry for each source file processed:
```json
{
  "ingested_at": "TIMESTAMP",
  "size_bytes": FILE_SIZE,
  "modified_at": FILE_MTIME,
  "source_type": "data",
  "project": "project-name-or-null",
  "pages_created": ["list/of/pages.md"],
  "pages_updated": ["list/of/pages.md"]
}
```

**`index.md`** and **`log.md`**:
```
- [TIMESTAMP] DATA_INGEST source="path/to/data" format=FORMAT pages_updated=X pages_created=Y
```

## Tips

- **When in doubt about format, just read it.** The Read tool will show you what you're dealing with.
- **Large files:** Read in chunks using offset/limit. Don't try to load a 10MB JSON in one go.
- **Multiple files:** Process them in order, building up wiki pages incrementally.
- **Binary files:** Skip them. This skill handles text only.
- **Encoding issues:** If you see garbled text, mention it to the user and move on.
