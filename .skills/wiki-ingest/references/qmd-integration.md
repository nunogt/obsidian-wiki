# QMD integration (optional pre-extraction discovery)

**Skip this entire file unless `$QMD_PAPERS_COLLECTION` is set in `.env`.** If unset, `wiki-ingest` uses Grep against `index.md` for existing-page discovery in Step 3.

Called from `wiki-ingest/SKILL.md` Step 1 when `$QMD_PAPERS_COLLECTION` resolves.

## What it does

Before distilling a source, surface related papers already indexed in the corpus that could enrich the wiki page you're about to write.

## Invocation

```
mcp__qmd__query:
  collection: <QMD_PAPERS_COLLECTION>      # e.g. "papers"
  intent: <what this source is about>
  searches:
    - type: vec     # semantic — same topic, different vocabulary
      query: <topic or thesis of this source>
    - type: lex     # keyword — same methods, tools, authors
      query: <key terms, author names, method names>
```

## How to use the results

1. **Surface related papers** you may not have thought to link — add them as cross-references in the wiki page
2. **Identify recurring themes** across the corpus — if 3+ papers touch the same concept, that concept almost certainly warrants its own `concepts/` page
3. **Find contradictions** between this source and indexed papers — flag with `^[ambiguous]`
4. **Avoid duplicate pages** — if the corpus already covers this concept heavily, merge rather than create

## When not to run

- `QMD_PAPERS_COLLECTION` unset → skip entirely (guard at the top of Step 1)
- Source is clearly non-research (a conversation, a Slack log, an arbitrary data export) → the paper corpus is unlikely to help
- Source is already the first paper on its topic in the corpus → no prior art to surface
