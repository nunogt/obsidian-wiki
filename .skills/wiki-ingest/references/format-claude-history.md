# Format: Claude Code history (`~/.claude/`)

Parsing guide for Claude Code session transcripts and memory files. Called from `wiki-ingest/SKILL.md` Step 1 when the source path is under `~/.claude/` (or `$CLAUDE_HISTORY_PATH`).

## Directory layout

```
~/.claude/
├── projects/
│   └── -<path-with-dashes>/            # project dir (slashes → dashes)
│       ├── <session-uuid>.jsonl        # conversation transcript
│       └── memory/                     # structured memory files
│           ├── MEMORY.md               # index of this project's memories
│           ├── user_*.md               # user-profile memories
│           ├── feedback_*.md           # workflow feedback
│           ├── project_*.md            # project context
│           └── reference_*.md          # external-resource pointers
├── sessions/<pid>.json                 # session metadata (rarely useful at ingest)
└── settings.json                       # user config (do NOT ingest)
```

To decode a project dir name: `-Users-foo-projects-my-app` → `/Users/foo/projects/my-app`. The canonical path is also present as `cwd` in each conversation line.

## Inventory in priority order

1. **Memory files** (`projects/*/memory/*.md`) — pre-distilled. Already wiki-friendly. Ingest first.
2. **Conversation JSONL** (`projects/*/*.jsonl`) — rich but noisy; topic-cluster aggressively.
3. **Session metadata** (`sessions/*.json`) — skip unless building a timeline.

Read `MEMORY.md` in each memory dir first to triage which individual memory files to open.

## Conversation JSONL — what to keep, what to skip

Each line is one event with a `type` field:

| `type` | Keep? |
|---|---|
| `user` | Yes — the user's prompt |
| `assistant` | Yes — but only `text` content blocks |
| `progress`, `file-history-snapshot` | Skip — internal plumbing |
| other | Skip unless obviously meaningful |

Assistant messages often have a `content` array:
```json
"content": [
  {"type": "thinking", "text": "..."},
  {"type": "text",     "text": "actual visible answer"},
  {"type": "tool_use", "name": "Read", "input": {...}}
]
```

**Extract only `text` blocks.** `thinking` is internal reasoning; `tool_use` is mechanical plumbing. Neither adds wiki-worthy knowledge.

Also skip subagent conversations (`subagents/` subdirs) unless the operator explicitly requests them.

## Memory file structure

Each has YAML frontmatter:
```markdown
---
name: ...
description: ...
type: user | feedback | project | reference
---
<body>
```

Mapping to wiki:

| Memory `type` | Routes to |
|---|---|
| `user` | Entity page about the user, or relevant concept pages |
| `feedback` | Skills pages (workflow patterns) |
| `project` | `entities/<project>` or `projects/<name>/<name>.md` |
| `reference` | References pages |

## Topic clustering rule

**Do NOT create one wiki page per conversation.** Group by topic across conversations:
- A session covering "auth debug + CI setup" → 2 topics, contributes to 2 different pages
- 3 sessions about "React performance" across weeks → merge into 1 topic page
- The project dir name is a natural first-level grouping

## Provenance guidance

- **Memory files:** mostly extracted — user wrote them deliberately. Treat as extracted unless stitching across files.
- **Conversation distillation:** heavily inferred. Most claims synthesize across many turns. Apply `^[inferred]` liberally.
- **Cross-session contradictions:** `^[ambiguous]`.
- Recompute `provenance:` frontmatter block per the llm-wiki schema.

## Manifest fields

Set `source_type`:
- `claude_conversation` for `projects/*/<uuid>.jsonl`
- `claude_memory` for `projects/*/memory/*.md`

Track `project` as the decoded directory name (e.g. `my-app`).

## Privacy

Claude session logs are less secret-prone than Codex but still can contain tokens in pasted snippets. Follow the shared trust boundary (see `llm-wiki/SKILL.md §Safety`): summarize, never paste raw tokens; redact anything resembling an API key.
