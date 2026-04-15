# Format: Arbitrary text sources

Parsing guide for any text-shaped source that isn't a document, image, or known agent-history format. Called from `wiki-ingest/SKILL.md` Step 1 when the source is JSON, JSONL, CSV/TSV, HTML, or plain-text with turn-taking patterns.

## Identification table

| Format | How to spot | How to read |
|---|---|---|
| **JSON / JSONL** | `.json` / `.jsonl`; first char `{` or `[` | Read; look for `message`, `content`, `text` fields |
| **CSV / TSV** | `.csv` / `.tsv`; commas/tabs on line 2+ | Parse rows; identify columns from header or first rows |
| **HTML** | `.html`; starts with `<!DOCTYPE` or `<html` | Extract text content; ignore markup |
| **Chat log (generic)** | Turn markers like `[timestamp] user:`, `human:`/`ai:` | Extract the dialogue turns |
| **Plain text** | `.txt` or no extension | Read; check for structure (headers, bullets, quotes) |

If in doubt about format: **just Read the first 20 lines** and infer. The Read tool shows you what you're dealing with.

## Common chat-export shapes

### ChatGPT export (`conversations.json`)

```json
[
  {
    "title": "...",
    "mapping": {
      "<node-id>": {
        "message": {
          "role": "user | assistant",
          "content": {"parts": ["text..."]}
        }
      }
    }
  }
]
```

Walk the `mapping`; extract `content.parts` from messages with `role: user | assistant`.

### Slack export (per-channel directories)

```json
[
  {"user": "U123", "text": "message", "ts": "1234567890.123456"}
]
```

Resolve user IDs against the `users.json` file if present. Cluster by thread (`thread_ts`) when building pages.

### Discord export

Varies by exporter. Typically a JSON array of message objects with `author`, `content`, `timestamp`. Apply the same substance-focused extraction.

### Generic timestamped chat log

```
[2026-03-15 10:30] User: message
[2026-03-15 10:31] Bot: response
```

Simple regex for turn boundaries. Focus on substance, not ceremony.

## Extraction strategy (all chat formats)

Focus on **substance, not dialogue**:
- A 50-message debugging session → maybe 1 skills page about the fix
- A long brainstorming chat → maybe 3 concept pages
- Skip greetings, pleasantries, meta-conversation
- Skip repetitive back-and-forth with no new information
- Skip raw code dumps unless they illustrate a reusable pattern

## CSV / TSV handling

- Identify columns from the header row (or infer from first 3-5 rows)
- For tabular knowledge, each row often contributes to an entity page (e.g. `entities/<row-subject>.md`)
- For log-shaped CSVs (timestamp + message), treat like a chat log

## HTML handling

- Strip markup; preserve headings and links as structure
- Keep `[[wikilinks]]` derived from `<a href>` when the link target could become a wiki page
- Skip boilerplate (nav, footer, ads)

## Provenance guidance

- Distillation across multi-turn formats is heavily inferred — apply `^[inferred]` for synthesised patterns
- `^[ambiguous]` for speaker contradictions or unclear attribution
- Recompute `provenance:` frontmatter block per the llm-wiki schema

## Manifest fields

- `source_type: data` (default for arbitrary text)
- Record the detected format in a `format` sub-field if useful for later filtering

## When in doubt

Just Read the source. The Read tool will show you the structure. Adapt on the fly. Don't try to pre-handle every possible format — read the data, figure it out, write the pages.
