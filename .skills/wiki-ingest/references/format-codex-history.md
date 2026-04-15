# Format: Codex CLI history (`~/.codex/`)

Parsing guide for Codex rollout transcripts and session index. Called from `wiki-ingest/SKILL.md` Step 1 when the source path is under `~/.codex/` (or `$CODEX_HISTORY_PATH`).

## Directory layout

```
~/.codex/
├── sessions/YYYY/MM/DD/rollout-<timestamp>-<id>.jsonl   # primary event streams
├── archived_sessions/                                    # archived rollouts
├── session_index.jsonl                                   # id/name/updated_at inventory
├── history.jsonl                                         # optional transcript history
├── config.toml                                           # user config (do NOT ingest)
└── state_*.sqlite / logs_*.sqlite                        # runtime DBs (do NOT ingest)
```

## Inventory in priority order

1. **`session_index.jsonl`** — best for building a dated inventory of sessions.
2. **`sessions/**/rollout-*.jsonl`** — rich event streams.
3. **`archived_sessions/`** — skip unless operator requests archived history.
4. **`history.jsonl`** — optional fallback.

## session_index.jsonl

One JSON object per line:
```json
{"id":"<thread-id>","thread_name":"<title>","updated_at":"<timestamp>"}
```

Use to: build canonical inventory, map rollout ids to thread titles, prioritise recent/active sessions.

## Rollout JSONL — envelope and extraction

Each line:
```json
{"timestamp":"...","type":"<envelope-type>","payload":{...}}
```

Envelope types:

| `type` | Meaning |
|---|---|
| `session_meta` | Run metadata (id, cwd, model, provider) — treat as metadata, not knowledge |
| `turn_context` | Turn-scoped context envelope |
| `event_msg` | Runtime events (task lifecycle, token accounting, tool-call markers) |
| `response_item` | Model response items (messages, tool calls, reasoning blocks) |

### Keep

- `response_item` with user/assistant message content
- Key `event_msg` milestones (`task_started`, `user_message`, `agent_message`, meaningful `mcp_tool_call_end`, `exec_command_end` that encode reusable decisions)

### Skip (noise filters)

- `token_count` and other telemetry
- Tool-plumbing events with no semantic content
- Repeated plan snapshots unless they add novel decisions
- Raw command output unless it contains reusable knowledge/patterns

## CRITICAL privacy filter

Codex rollout logs can include:
- Injected instruction layers (system/developer prompts)
- Tool inputs/outputs containing secrets
- Potential credentials in command output

Rules (load-bearing safety property — do not relax):
- **Never** paste verbatim system/developer prompts into wiki pages
- **Remove** API keys, tokens, passwords, credentials before distilling
- **Redact** private identifiers unless the operator has explicitly approved including them
- **Summarize instead of quoting** raw transcripts
- If in doubt, ask the operator before writing a page that contains Codex-derived content

This is stricter than the Claude-history privacy guidance because Codex session logs historically include sensitive data that Claude's do not.

## Topic clustering rule

Same as Claude history: do NOT create one wiki page per session. Group by stable topics across sessions. Use `cwd` from `session_meta` to infer project scope.

## Provenance guidance

- Heavily inferred (same as Claude conversations) — apply `^[inferred]` liberally
- `^[ambiguous]` for cross-session contradictions
- Recompute `provenance:` frontmatter block per the llm-wiki schema

## Manifest fields

Set `source_type`:
- `codex_rollout` for `sessions/**/rollout-*.jsonl`
- `codex_index` for `session_index.jsonl`
- `codex_history` for `history.jsonl`

Track `project` from inferred cwd when available.
