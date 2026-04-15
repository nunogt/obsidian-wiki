# Vision-fidelity assessment: Karpathy's LLM-Wiki gist vs our forked implementation

*Drafted 2026-04-15. Based on re-fetch of the original gist (gist.github.com/karpathy/442a6bf555914893e9891c11519de94f, 75 lines) + all 494 comments (286 substantive) + end-to-end audit of our fork and kb-system. **Revised 2026-04-15 post-wiki-cross-check** — three refinements incorporated (see §8.4). Nothing executed — this is an assessment + proposal for review.*

> **2026-04-15 ADDENDUM (rank 1 superseded):** [HARNESS-INTEGRATION-PROPOSAL-v3](./HARNESS-INTEGRATION-PROPOSAL-v3.md) reframes the save-back gap. Karpathy's literal phrasing — *"shouldn't disappear into chat history"* — describes auto-ingestion of session transcripts, not a build-time save flag. Claude Code hooks (Stop + PostCompact + SessionStart matcher `compact` + sampled UserPromptSubmit) close the gap with **zero new skill code** and **higher gist-fidelity** than the original rank 1 spec. **Rank 1 below is superseded by harness-hook autosave; preserved for historical context.** Ranks 2, 2.5, 3 remain valid.
>
> **✅ STATUS: Ranks 2, 2.5, 3 EXECUTED (2026-04-15).**
>
> Shipped in 3 fork commits:
> - `35f8abd` — rank 2: divergence-check (`## Counter-Arguments & Data Gaps`) in wiki-ingest for concept pages
> - `cf9c4c3` — rank 2.5: post-ingest auto-lint (cheap checks: orphans, broken links, missing frontmatter)
> - `3b4230f` — rank 3: two-output rule in wiki-query Step 5b (plus Step 5c appending synthesis to fold-back queue, added by v3)
>
> Rank 1 (original explicit /wiki-save-answer skill) not shipped — superseded by HARNESS-INTEGRATION-PROPOSAL-v3 which delivers save-back via hooks instead. Ranks 4-7 remain as future polish, deferred per original recommendation.
>
> **Live validation status (2026-04-15)**:
> - **Rank 2.5 (auto-lint)**: *partially validated*. The big ingest run reported *"Two broken wikilinks caught and fixed"* in its completion summary — strong evidence the auto-lint ran and caught real issues. Not yet inspected in log.md for a formal LINT line.
> - **Rank 2 (divergence-check)**: *unvalidated in live run*. The ingest created 7 new concept pages; if the skill prompt is being followed, each should have a `## Counter-Arguments & Data Gaps` section. Worth a spot-check.
> - **Rank 3 (two-output in wiki-query)**: *unvalidated*. No `/wiki-query` has been invoked in this session yet. Step 5c queue-append likewise untested.
> - **Rank 2.5 + 3 would both fire during a natural `/wiki-query <substantive question>` invocation**.

---

## 0. Executive summary

**Fidelity verdict:** we match or improve on most of Karpathy's stated vision. The one genuine, emphasized gap is the **query-answer save-back loop** — which Karpathy calls out specifically as *"the important insight"*. Our wiki-query skill has no save-back; neither does upstream ar9av. This is the highest-leverage alignment opportunity.

**Our deliberate additions** beyond the vision — multi-vault architecture, in-vault sources, provenance markers, content-trust boundary, visibility tags, retrieval primitives contract, fork-with-rebase maintenance — are justified by operator need and don't violate the spirit of the gist. Karpathy's gist explicitly says:

> *"The exact directory structure, the schema conventions, the page formats, the tooling — all of that will depend on your domain, your preferences, and your LLM of choice. Everything mentioned above is optional and modular."*

So additions aren't deviations. They're instantiations.

**Simplification opportunities** are modest — we've been disciplined. Two mild candidates: consolidating per-claim markers with page-level provenance fractions (minor redundancy); and documenting the three "raw-sources" locations under Karpathy's single umbrella term (docs clarity, not code change).

**Community critiques worth heeding:** truth-maintenance rigor (@laphilosophia), type-specific extraction templates (@bluewater8008), divergence checks (@localwolfpackai), two-output rule (@bluewater8008) — all actionable as small enhancements.

---

## 1. Karpathy's vision, distilled

### The core claim

RAG re-derives knowledge on every query. LLM-Wiki pre-compiles it into a persistent, compounding artifact. The cross-references, synthesis, and contradictions are done **once** and **kept current**. The wiki accumulates.

### The three layers (architectural)

1. **Raw sources** — "your curated collection of source documents... immutable — the LLM reads from them but never modifies them. This is your source of truth."
2. **The wiki** — "a directory of LLM-generated markdown files... The LLM owns this layer entirely."
3. **The schema** — "a document (e.g. CLAUDE.md for Claude Code or AGENTS.md for Codex) that tells the LLM how the wiki is structured."

### Three operations (process)

- **Ingest** — drop source, LLM reads, discusses, summarizes, updates index/entity/concept pages. "A single source might touch 10-15 wiki pages."
- **Query** — ask question, LLM searches, reads, synthesizes with citations. **"Good answers can be filed back into the wiki as new pages."**
- **Lint** — periodic health-check: contradictions, stale claims, orphans, missing concepts, cross-reference gaps.

### Two navigation files

- **index.md** — content-oriented catalog, organized by category.
- **log.md** — chronological, append-only. Parseable with `grep "^## \["` for timelines.

### Optional infrastructure

- **qmd** (CLI/MCP search over markdown, BM25+vector+rerank) — mentioned explicitly as the tool of choice when index-alone stops scaling.
- **Obsidian plugins**: Web Clipper, Dataview, Marp, Graph view.
- **Git repo** — "you get version history, branching, and collaboration for free."

### Why it works

> *"The tedious part of maintaining a knowledge base is not the reading or the thinking — it's the bookkeeping. Humans abandon wikis because the maintenance burden grows faster than the value. LLMs don't get bored, don't forget to update a cross-reference, and can touch 15 files in one pass."*

### The human/LLM division of labor

> *"You never (or rarely) write the wiki yourself — the LLM writes and maintains all of it. You're in charge of sourcing, exploration, and asking the right questions. The LLM does all the grunt work."*

> *"Obsidian is the IDE; the LLM is the programmer; the wiki is the codebase."*

### Explicitly described as abstract

The gist closes with: *"This document is intentionally abstract. It describes the idea, not a specific implementation. [...] The right way to use this is to share it with your LLM agent and work together to instantiate a version that fits your needs."*

So fidelity is measured against **principles**, not a specification.

---

## 2. Community themes from 494 comments

Filtered the 286 substantive comments for recurring patterns; most valuable signal grouped by theme.

### 2.1 Truth maintenance is the hard problem (@laphilosophia, @JaxVN, @bluewater8008 rule 6, @peas)

The emphatic community pushback on *"the LLM owns this layer entirely"*:

> *"The appealing part of the workflow is that the LLM updates summaries, cross-links pages, integrates new sources, and flags contradictions. But that is also exactly where models tend to fail quietly. Bad synthesis, weak generalization, stale claims surviving new evidence, page sprawl, and false consistency can accumulate without being obvious."* — @laphilosophia

**Proposed mitigations:**
- Separate facts, inferences, open questions explicitly
- Require source links for important claims
- Make ingest idempotent
- Have LLM propose diffs, not silently overwrite
- Lint for stale claims, unsupported claims, contradiction tracking, source loss
- Editor-not-writer constraint (@peas): *"every sentence must trace to something the user actually said. Gaps get `[TODO: ...]` markers, not hallucinated filler."*
- Structural provenance (@JaxVN): per-proposition source-file hash; check on read for staleness.

### 2.2 Progressive disclosure needs token budgets (@bluewater8008)

Four-level cost tiers:
- L0 (~200 tokens): project context, every session
- L1 (~1-2K): index, session start
- L2 (~2-5K): search results
- L3 (5-20K): full articles

Discipline: don't read full articles until index has been checked.

### 2.3 Classify before extract (@bluewater8008 rule 1, @dkushnikov)

> *"When ingesting sources, don't treat every document the same. Classify by type first (e.g., report vs. letter vs. transcript vs. declaration), then run type-specific extraction. A 50-page report needs different handling than a 2-page letter."*

Mnemon (dkushnikov) uses 7 source-type-specific templates: article, video, podcast, book, paper, idea, conversation.

### 2.4 Every task produces two outputs (@bluewater8008 rule 4)

> *"Whatever the user asked for — an analysis, a comparison, a set of questions — that's output one. Output two is updates to the relevant wiki articles. If you don't make this explicit in your schema, the LLM will do the work and let the knowledge evaporate into chat history."*

This is the same pattern Karpathy mentions (**"good answers can be filed back into the wiki as new pages"**) — but made a structural rule instead of a recommendation.

### 2.5 Cross-domain tagging from day one (@bluewater8008 rule 5)

> *"If there's any chance your knowledge spans multiple projects, cases, clients, or research areas — add a domain tag to your frontmatter now. Shared entities (people, organizations, concepts that appear in multiple domains) become the most valuable nodes in your graph. Retrofitting this is painful."*

### 2.6 Divergence checks / counter-arguments (@localwolfpackai)

> *"Every time the LLM updates a concept page, it must generate a hidden section called `## Counter-Arguments & Data Gaps`. If you ingest 5 articles praising a specific UI framework, the LLM should be tasked to search for the most sophisticated critique of that framework."*

Surfaces bias; forces anti-thesis generation.

### 2.7 Query-time compilation (@JaxVN)

> *"Compilation happens at query time, not just at ingest. When you ask a question, the system pulls what's already known, reads the provenance sources, and identifies the delta — what the sources say about your question that isn't already captured."*

Each query densifies the KB from a new angle instead of just consuming what ingest produced.

### 2.8 Voice-first / mobile capture (@peas)

> *"Most knowledge systems fail at capture, not synthesis. I record voice memos into Telegram while walking. Whisper transcribes, an LLM classifier tags and routes, a synthesizer updates interlinked KB nodes. No laptop needed."*

Plus the editor-not-writer constraint: *"LLM must be an editor, not a writer — every sentence must trace to something the user actually said."*

### 2.9 Two-tier LLM (local + remote, privacy)

> *"Privacy architecture is the missing piece for institutional use. Your pattern assumes cloud LLM throughout. In a research/HE context, some material can't leave the machine. I run Ollama/Qwen locally for sensitive work and Claude for everything else."* — Hogeschool Rotterdam researcher

### 2.10 Multi-model verification (@tomjwxf)

Route canonical questions to 4 frontier models (council-of-experts / adversarial synthesis), cryptographically sign the receipts.

High-ceremony; not for every deployment.

### 2.11 Skills as knowledge units (@tylernash01, @brijoobopanna)

> *"Many wiki pages are already acting like skills, just represented as knowledge artifacts. Systems like Skillnote formalize that idea by making them versioned, shareable, and continuously improvable."*

ar9av's SKILL.md files already partially instantiate this framing.

### 2.12 Structured data behind the markdown (@mpazik, @buremba)

> *"Instead of files that slowly become a database, start from structured data that renders as markdown. The index isn't a file the agent maintains by hand. It's a query. Always current."* — @mpazik (Binder)

> *"The main difference is that we use Postgresql instead of filesystem, that makes it a strongly typed database where the agent has SQL access to."* — @buremba (owletto)

---

## 3. Our implementation — what we actually have

### 3.1 Fork (10 commits ahead of upstream)

16 skills in `.skills/`:

| Skill | Role | Gist mapping |
|---|---|---|
| `wiki-setup` | Initialize vault | meta-infrastructure |
| `wiki-ingest` | Distill sources into pages | **Ingest** op |
| `claude-history-ingest`, `codex-history-ingest`, `wiki-history-ingest`, `data-ingest` | Source-type-specific ingest variants | **Ingest** variants |
| `wiki-status` | Delta + insights | meta-navigation |
| `wiki-rebuild` | Archive + restore | destructive reset |
| `wiki-query` | Answer questions from wiki | **Query** op (without save-back) |
| `wiki-lint` | 8-check health audit | **Lint** op |
| `cross-linker` | Auto-insert missing wikilinks | supports Lint |
| `tag-taxonomy` | Controlled tag vocabulary | convention enforcer |
| `wiki-export` | Graph export (JSON, GraphML, Neo4j, HTML) | visualization |
| `llm-wiki` | Schema reference | **The schema** |
| `skill-creator` | Meta — create new skills | extension mechanism |
| `wiki-ar9av-update` | Fork upstream maintenance | **fork-specific** (not in vision) |

Local fork patches:
- A: relative symlinks in setup.sh (now deleted)
- C: `OBSIDIAN_INVAULT_SOURCES_DIR` exclusion in 6 scanning skills
- D: retire setup.sh
- E: remove wiki-update skill
- F: CWD-first config ordering
- G: migrate wiki-ar9av-update to skill

### 3.2 kb-system (infrastructure)

- `scripts/kb-vault-new` — one-shot vault creator (profile + dir + git + remote + context)
- `scripts/kb-contexts-regenerate` — rebuild per-machine `contexts/` from `profiles/`
- `scripts/templates/{profile.env, vault.gitignore}` — canonical templates
- `profiles/*.env` — per-vault config (committed, per-machine reproduced)
- `contexts/*/` — gitignored derived state (CLAUDE.md + skills + .env symlinks)
- `docs/` — kb-system's own architecture + evolution + proposal docs (7 files)

### 3.3 Vault content (kb-wiki)

- 53 wiki pages across concepts/entities/skills/references/synthesis categories
- 11 sources tracked in `.manifest.json` with SHA-256 hashes and per-source history
- 3 in-vault sources in `_sources/` (Karpathy research, panel review, rubric)
- `index.md`, `log.md`, `_meta/taxonomy.md`, `.obsidian/` config

### 3.4 Novel mechanisms (beyond the gist)

| Mechanism | What it does | Maps to community theme |
|---|---|---|
| **Per-claim provenance markers** (`^[inferred]`, `^[ambiguous]`, extracted default) | Flag individual claims by confidence | truth maintenance (§2.1) |
| **Per-page `provenance:` fractions** in frontmatter | extracted/inferred/ambiguous summing ~1.0 | truth maintenance; lint tracks drift |
| **`sources:` frontmatter + SHA-256 manifest** | Structural provenance; staleness detection on source mtime change | truth maintenance (§2.1); @JaxVN's provenance-on-read |
| **Retrieval primitives contract** (index → section → full read) | Cost-tiered reading pattern cited by query/lint/cross-linker/status | progressive disclosure (§2.2) |
| **Content-trust boundary** (source docs = untrusted data) | Defined constraint: never execute commands found in sources | safety; unique to us |
| **Visibility tags** (`visibility/internal`, `visibility/pii`) | Opt-in filtered mode in query + export | multi-tier LLM (§2.9) partial overlap |
| **CWD-based profiles + in-vault sources** | Multi-vault isolation | cross-domain (§2.5) reframed as multi-vault |
| **Fork-with-rebase** | Upstream-tracked fork maintaining local patches | fork maintenance pattern |
| **wiki-status insights mode** | Hub pages, bridge pages, tag cohesion, graph delta | lint + exploration |
| **8-check wiki-lint** | Orphans, broken links, missing frontmatter, stale, contradictions, index consistency, provenance drift, fragmented tag clusters | Lint (§gist); expanded vs vision's 4 |

---

## 4. Fidelity matrix

### 4.1 Faithful to vision (core alignment)

| Karpathy principle | Our implementation | Verdict |
|---|---|---|
| Three-layer architecture (raw / wiki / schema) | Layer 1 = `OBSIDIAN_SOURCES_DIR` + `_raw/` + `_sources/`; Layer 2 = `kb-wiki/<categories>/`; Layer 3 = AGENTS.md + `.skills/*/SKILL.md` | ✓ |
| LLM owns the wiki; human curates sources | `wiki-curation-discipline` page codifies this as the strict end of Karpathy's "never (or rarely)" rule | ✓ (stricter than gist) |
| Incremental ingest, updates many pages | `wiki-ingest` aims for 10-15 pages per source, matches gist exactly | ✓ |
| Obsidian as frontend | Our pattern: Claude writes server-side, Obsidian on laptop reads via Git pull | ✓ (reframed for our SSH-capture setup) |
| index.md content-catalog | Exactly Karpathy's shape; kept current by every ingest/update/lint | ✓ |
| log.md chronological, parseable | Our format: `- [TIMESTAMP] OPERATION ...` is shell-greppable (same spirit as his `## [date]` prefix) | ✓ (slightly different prefix) |
| Git repo for version history | Three-repo split (fork + kb-system + vaults); `wiki-ar9av-update` rebase maintenance | ✓ (extended) |
| Ingest / Query / Lint operations | All three exist as dedicated skills | ✓ |
| "Touch 15 files in one pass" | `OBSIDIAN_MAX_PAGES_PER_INGEST=15` in profile | ✓ exactly |
| qmd optional search | `QMD_WIKI_COLLECTION` / `QMD_PAPERS_COLLECTION` env vars supported, Grep fallback | ✓ |

### 4.2 Deliberate improvements (additions that serve the vision)

| Addition | Why it improves on the vision |
|---|---|
| **Provenance system** (per-claim markers + page-level fractions + drift lint) | The gist acknowledges "noting where new data contradicts old claims" as a goal but doesn't specify how. Our 3-layer provenance system makes it machinery, not vibes. Closes the community's #1 critique (truth maintenance). |
| **Multi-vault via CWD-based profiles** | Gist assumes single-user single-vault. Multi-vault is our real-world need; solved without forking upstream's skill code (Patches C + F enable it). |
| **In-vault sources** (`_sources/`) | Gist doesn't specify WHERE raw sources live. Per-vault containment prevents cross-contamination when multiple vaults coexist. Patch C makes 6 scanning skills honor the exclusion. |
| **Content-trust boundary** | Not in gist. We treat source documents as untrusted data and explicitly forbid LLM from executing embedded instructions. Essential safety property. |
| **8-check wiki-lint** (vs vision's ~4) | Gist lists: contradictions, stale, orphans, missing concepts, missing cross-refs, data gaps. We have all these plus: broken wikilinks, missing frontmatter, missing summary, index consistency, provenance drift, fragmented tag clusters. Wider coverage. |
| **Retrieval primitives contract** | Gist says "works at moderate scale" with index-first. We have an explicit 3-tier cost model (index → section → full read) cited by every scanning skill — the community (§2.2) independently arrived at a 4-tier version. |
| **SHA-256 content-hash delta** | Gist implies delta ingestion but doesn't specify mechanism. We use hash, immune to filesystem timestamp noise. Community (@JaxVN) corroborates this as the right primitive. |
| **Fork-with-rebase maintenance** | Gist doesn't address "how do I keep the framework current." Our rebase pattern keeps the fork linear and submittable upstream. |
| **wiki-status insights mode** (hubs, bridges, cohesion) | Gist mentions lint but doesn't discuss graph topology analysis. We surface structural insights as a separate mode. |

### 4.3 Deliberate deviations

| Deviation | Rationale |
|---|---|
| Removed `/wiki-update` skill | Dead under CWD-based profiles (reads global config with no fallback); Patch B considered + rejected as legacy. Not a loss — `/wiki-ingest <path>` from a context dir is the correct replacement. |
| No `setup.sh` | Our deployment is kb-system-based; setup.sh's residual value was zero and it's an active footgun (writes global config). |
| Strict "no human edits to compiled pages" | Gist says "never (or rarely)"; we took the strict end. Not strictly a deviation — a choice at the end of Karpathy's allowed range. |
| Three raw-sources locations instead of one | `_raw/` staging (gist-compatible) + `_sources/` in-vault + external `OBSIDIAN_SOURCES_DIR` (comma-separated). Multi-vault containment driver. |

### 4.4 Gaps vs vision / community critique

| Gap | Severity | Source |
|---|---|---|
| **No query-answer save-back** — the gist's emphatic "important insight" | **HIGH** | Gist direct |
| **No divergence-check / counter-arguments section on concept pages** | Medium | @localwolfpackai |
| **No type-specific extraction templates** (we have category dirs, not per-type templates for article vs transcript vs report) | Medium | @bluewater8008, @dkushnikov |
| **No two-output rule** explicit in skill prompts (it's implicit in wiki-ingest but not wiki-query) | Medium | @bluewater8008 rule 4 |
| **No query-time compilation delta** (we compile only at ingest) | Low | @JaxVN |
| **No voice/mobile capture pipeline** | Low (out of scope per operator) | @peas |
| **No local-LLM fallback tier** for sensitive content | Low (out of scope per operator) | Hogeschool Rotterdam |
| **No multi-model adversarial verification** | Low (out of scope) | @tomjwxf |
| **No append-and-review note integration** | Low | @expectfun reference to Karpathy's earlier blog post |

---

## 5. Simplification opportunities

We've been disciplined. The places where genuine simplification exists:

### 5.1 Provenance redundancy (minor)

Per-claim markers (`^[inferred]`, `^[ambiguous]`) + page-level `provenance:` fractions overlap in purpose. The fractions are derived from counting markers; maintaining both is bookkeeping for the LLM.

**Option:** keep fractions only. Per-claim markers become optional hints during writing but the authoritative record is the frontmatter.

**Cost of current approach:** marginal — LLM does both in one pass during ingest. Lint computes one from the other.

**Recommendation:** leave as-is. The per-claim markers are useful when reading the page manually (you can see which sentences are hedged). Fractions are for programmatic lint. Different consumers; redundancy justified.

### 5.2 Three "raw sources" terms in docs

We have `_raw/`, `_sources/`, `OBSIDIAN_SOURCES_DIR` — three distinct mechanisms explained across multiple pages. A single reference page tying all three to Karpathy's "raw sources" umbrella with a clear matrix would reduce cognitive load.

**Recommendation:** expand `concepts/in-vault-sources` or create `concepts/ingest-mechanics` with a clear table (this session already produced such a table for the operator — upgrade it into a wiki page).

### 5.3 Skills count (nothing to cut)

16 skills all serve distinct purposes. No candidates for consolidation without capability loss. (`wiki-history-ingest` is a router skill — one could argue it's overhead, but the 3-line routing is lightweight and the trigger vocabulary expands discoverability.)

### 5.4 Scripts (already minimized)

Post-LEGACY-CLEANUP we're at 2 bootstrap scripts. `kb-contexts-regenerate` is the true bootstrap primitive; `kb-vault-new` is bootstrap-friendly (works without existing contexts). Migrating `kb-vault-new` to a skill was considered and rejected for the bootstrap-friendliness property.

---

## 6. Alignment opportunities (small, high-value)

### 6.1 Close the query-save-back gap — with full drift integrity (HIGH priority)

Karpathy emphasizes this as *"the important insight"*. We document it as a gap but don't implement it.

**Critical scoping refinement (from post-write wiki cross-check):** a bare *"save synthesis as a new page"* implementation scores **equivalent to absence** per the panel rubric, because silent drift contaminates future queries. Per [[drift-integrity]], a reliable save-back must ship **all three components**:

1. **Provenance captured on save** — populate `sources:` from the query's candidate page list, not `[]`
2. **Staleness detection on source change** — ingest-side hook marks dependent pages stale when any listed source is modified
3. **Lint coverage** — a rule like `staleness = synthesis.updated < max(sources.updated)` so stale pages don't silently re-rank with fresh ones

Partial implementation (1 without 2-3) is **worse than nothing** — users reasonably assume the wiki self-maintains, and the failure is silent.

**Blueprint: the 5-step plan already in our wiki.** `synthesis/fold-back-gap-analysis.md` §"What would close the gap" contains a concrete engineering plan (written during our own deliberation) that implements all three drift-integrity components:

1. **Save action** — when the user requests fold-back, write the synthesis page with `sources: [<page1>, <page2>, ...]` populated from the query's candidate set, not `[]`
2. **Manifest schema extension** — add a `derived_pages` field to source-page manifest entries (list of synthesis pages depending on this source)
3. **Ingest-side hook** — when re-ingesting a source whose hash has changed, mark every `derived_pages` entry stale
4. **Lint rule** — `staleness = synthesis.last_updated < max(sources[*].last_updated)` — reuses the existing lint #4 (Stale Content) machinery
5. **Query-side filter** — optionally exclude stale syntheses from the candidate set, or surface a warning when they're cited

Wiki's estimate: ~1-2 days for a competent agent-skill author.

**Implementation location:** new `.skills/wiki-save-answer/SKILL.md` in the fork (companion to `wiki-query`, not an extension — keeps separation of concerns clean). Plus small edits to `wiki-ingest/SKILL.md` (manifest schema + ingest-side hook) and `wiki-lint/SKILL.md` (new staleness rule as lint #4b or extension of #4).

**Why this matters operationally:** our wiki has 53 pages after multiple ingest cycles. How many good synthesis-worthy answers have been lost to session history across all our Claude Code usage? Likely many. This is the feedback loop that makes the KB compound from Q&A, not just from ingest. Plus: **we'd be the first in the ecosystem to ship it reliably** per the wiki's own analysis. *"Nobody has shipped it yet."*

### 6.2 Two-output rule for wiki-query (MEDIUM priority)

Even before we build a save skill, we could tighten `wiki-query`'s SKILL.md to explicitly state:

> *"Output 1: the synthesized answer. Output 2: suggest 1-3 updates to existing pages (new wikilinks, updated claims, new cross-refs) based on what the query surfaced. Offer to apply them."*

The community's "two outputs" rule (§2.4) makes this explicit. Even the base-level improvement of *suggesting* edits (without auto-applying) would produce compounding benefits over time.

### 6.3 Divergence check in wiki-ingest (MEDIUM priority)

@localwolfpackai's `## Counter-Arguments & Data Gaps` section. When `wiki-ingest` writes or updates a concept page, have it generate this section — even if empty — forcing the LLM to consider opposing views.

**Minimal implementation:** add a Step 5b to `wiki-ingest/SKILL.md`:

> *"For concept pages, generate a `## Counter-Arguments & Data Gaps` section identifying: (a) the strongest critique of the position described, (b) sources that might disagree, (c) questions the current sources don't answer. Empty section is better than no section — the prompt alone surfaces bias."*

Simple to add; high leverage for epistemic integrity (community theme §2.1).

### 6.4 Type-specific ingest templates (MEDIUM priority)

Currently our ingest is one-size-fits-all across markdown docs, PDFs, history JSONLs. Community wisdom (@bluewater8008, @dkushnikov) strongly suggests classify-first, extract-second.

**Proposal:** add a Step 1.5 to `wiki-ingest/SKILL.md`: *"Classify the source type (article / paper / meeting-transcript / project-doc / chat-export / reference-spec) and select an appropriate extraction template."* Each type gets 2-3 sentences of extraction guidance.

**Lower-effort alternative:** skip templates; just say "classify source type before extracting and tailor depth/focus accordingly." Gives the LLM room without prescribing 7 templates.

### 6.5 Editor-not-writer constraint (LOW-MEDIUM priority)

@peas's constraint: *"every sentence must trace to something the user actually said. Gaps get `[TODO: ...]` markers, not hallucinated filler."*

Our `content-trust boundary` says we never TRUST source content as instructions. It doesn't say we never INVENT content when sources are thin. Those are different constraints.

**Proposal:** tighten `wiki-ingest/SKILL.md` to instruct: *"Prefer `[TODO: need source]` markers over plausible-sounding filler when the source is silent on a topic the page needs to cover."*

### 6.5b Automated lint scheduling (MEDIUM priority — added post-wiki-cross-check)

The wiki's `concepts/lint-primitive.md` notes: *"Panel §4.2 flagged 'lint defined but not automated' as an ecosystem-wide gap. All three reviewed projects ship lint as on-demand only."* Our `LINT_SCHEDULE=weekly` env var is **config-only** — not wired to anything. Operator would need a user crontab or manual invocation.

**Proposal:** wire `LINT_SCHEDULE` to actual behavior. Options:

- **Post-ingest auto-lint:** after every `/wiki-ingest` successful completion, run a minimal lint pass (orphans + broken links + missing frontmatter — the cheap checks). Full 8-check lint on weekly schedule.
- **Git pre-commit hook** in the vault: run lint before every commit, block on hard failures.
- **Cron wrapper documentation:** stay as-is, but ship a reference `crontab` snippet in kb-system/docs/ so operators can paste-and-go.

**Effort:** ~1 day per the wiki.

**Value:** closes another ecosystem-wide gap the wiki flagged but the assessment overlooked.

Recommended sub-option: **post-ingest auto-lint for cheap checks** — the ingest is already a heavy write; adding a fast orphan/broken-link check as a post-step costs little and catches new problems while they're fresh. Weekly full lint via cron (operator opt-in) stays external.

### 6.6 Append-and-review journal integration (LOW priority)

Karpathy's earlier blog post (karpathy.bearblog.dev/the-append-and-review-note) describes a pattern where you append notes to a single running file and periodically review/reorganize. Our `log.md` is append-only but for operational events. Adding a `journal/daily-<date>.md` pattern — optional append target — would integrate the append-and-review concept with our wiki.

**Current state:** we have `journal/` as a category dir but nothing populates it. Low-effort to document the append-and-review pattern as a supported journal workflow.

### 6.7 What NOT to add

| Community suggestion | Why we shouldn't |
|---|---|
| Multi-model adversarial verification (@tomjwxf) | High ceremony; delivers value mostly at institutional scale. Our personal multi-vault use doesn't need 4-model consensus. |
| Structured data backing (SQLite) instead of markdown (@mpazik, @buremba) | Violates Karpathy's "wiki is a git repo of markdown" principle. Would sacrifice Obsidian compatibility, human readability, and git-based collaboration. |
| Cryptographic receipt chains (@tomjwxf) | Over-engineered for personal/team use. Fine as a separate product (Veritas Acta); not our fit. |
| Skills-as-reusable-knowledge-registry (@tylernash01, Skillnote) | Our skills already live in the fork's `.skills/`; upstream-promotable via normal git. Formalizing a registry layer adds infra without clear benefit at our scale. |
| Voice-first pipeline (@peas) | Out of scope per operator's SSH-capture model. Would require Telegram/Whisper integration that doesn't match our laptop-as-viewer architecture. |

---

## 7. Recommended action plan

Ranked by effort-to-value ratio. **Revised 2026-04-15** post-wiki-cross-check to add rank 2.5 (automated lint) and refine rank 1 framing.

| Rank | Action | Effort | Value | Locations affected |
|---|---|---|---|---|
| **1** | **Reliable query-answer save with full drift integrity** (3 components per drift-integrity doc; 5-step plan in fold-back-gap-analysis) | Medium (1-2 days per wiki) | **HIGH** — closes Karpathy's "important insight" + ecosystem-wide unsolved problem | Fork: new `.skills/wiki-save-answer/` + edits to `wiki-ingest/` (manifest schema + hook) + `wiki-lint/` (staleness rule); kb-wiki: updates to query-primitive, fold-back-loop, fold-back-gap-analysis |
| 2 | **Divergence check** (`## Counter-Arguments & Data Gaps`) in concept pages via wiki-ingest | Low | Medium-High | Fork: wiki-ingest/SKILL.md one-section addition |
| **2.5** | **Automated lint scheduling** — wire `LINT_SCHEDULE` to actual behavior (post-ingest auto-lint for cheap checks; operator cron for full lint) | Low (~1 day per wiki) | Medium — closes ecosystem-wide gap flagged by Panel §4.2 | Fork: wiki-ingest/SKILL.md post-step + optional wiki-lint/SKILL.md sub-mode; kb-system/docs/: reference crontab snippet |
| 3 | **Two-output rule** explicit in wiki-query | Low | Medium | Fork: wiki-query/SKILL.md one-step addition |
| 4 | **Type-classify step** in wiki-ingest (lightweight version) | Low | Medium | Fork: wiki-ingest/SKILL.md Step 1.5 addition |
| 5 | **Editor-not-writer constraint** in wiki-ingest | Low | Low-Medium | Fork: wiki-ingest/SKILL.md tightening |
| 6 | **Ingest-mechanics reference page** for our wiki | Low | Low (clarity) | kb-wiki: new concepts/ingest-mechanics page |
| 7 | **Append-and-review journal pattern** documentation | Low | Low | kb-wiki: new skills/append-and-review page |

Each of these would be a separate patch on the fork (ranks 1-5 + 2.5) or wiki ingest (ranks 6-7).

**Total patch series, if all approved:** 6 new fork patches (bringing fork to 16 ahead of upstream) + 2 wiki ingest cycles.

---

## 8. Self-validate / critique / refine

### 8.1 Self-validate: did I read the gist accurately?

Key claims I'm making:
- Karpathy emphasizes save-back as "the important insight" → **verified:** the gist contains the phrase *"The important insight: good answers can be filed back into the wiki as new pages."* ✓
- Gist describes 3 operations: ingest, query, lint → **verified:** §Operations has these exact three ✓
- Gist says "you never (or rarely) write the wiki yourself" → **verified:** direct quote in §The core idea ✓
- Gist describes abstract idea, not spec → **verified:** final §Note paragraph ✓
- Gist suggests qmd optional → **verified:** §Optional: CLI tools ✓
- Gist uses `grep "^## \["` for log parseability → **verified:** §Indexing and logging ✓

### 8.2 Critique: what might I have missed?

- **I didn't fetch Karpathy's replies** to comments — if he endorsed/rejected specific community proposals, that's signal I'm missing. Attempted but the gist API is 502'ing intermittently. Risk: low — most comments don't show replies anyway.
- **I didn't read all 286 substantive comments** (only the first ~50 in detail). Risk: medium — could miss another strong theme. Mitigation: grep-based sampling for critical/problem/pitfall/risk language caught the main epistemic-integrity thread.
- **I'm evaluating our system from inside it** — my understanding of our capabilities is deep but my fresh-eyes perspective is limited. A community observer might flag things I'm blind to. Risk: medium.
- **I didn't benchmark against other community implementations** (Hosuke's llmbase, VihariKanukollu's browzy, xoai's sage-wiki, etc.). Risk: low-medium — we know upstream ar9av scored 48/60 on the panel review; our fork strictly improves on that.

### 8.3 Refine: conclusions after self-critique

- The query-save-back gap is unambiguously Karpathy's #1 call-out. My HIGH priority rating holds.
- The truth-maintenance theme is the #1 community concern; our provenance system addresses it well but not completely (divergence check adds another layer).
- Everything else is polish. Our forked system is a faithful and thoughtful instantiation of the vision — we don't have a fundamental alignment problem to solve.
- Simplification opportunities are genuinely limited. Our complexity maps to real operator need (multi-vault). Gratuitous simplification would be a step backward.

### 8.4 Post-write refinement: wiki cross-check findings (2026-04-15)

After drafting §0-8.3 from session-knowledge audit, cross-referenced every major claim against the wiki itself (synthesis/fold-back-gap-analysis, concepts/fold-back-loop, concepts/query-primitive, concepts/drift-integrity, concepts/lint-primitive, concepts/provenance-markers, concepts/retrieval-primitives, concepts/content-trust-boundary, concepts/in-vault-sources, references/karpathy-llm-wiki-research-doc).

**Zero contradictions.** Wiki analysis is uniformly same-depth or deeper. Three refinements surfaced:

**Refinement 1 — rank 1 scoping.** The wiki's drift-integrity doc enforces a 3-component framework (provenance-on-save + staleness-on-change + lint-for-stale). A bare save-back scores *"equivalent to absence"* per the panel rubric. Rank 1 in this assessment is **now scoped to all 3 components**, not just step 1. Reflected in §6.1 above.

**Refinement 2 — rank 1 blueprint.** The wiki's fold-back-gap-analysis §"What would close the gap" already contains a concrete 5-step engineering plan (written during a prior ingest) that I should defer to instead of inventing a new design. Reflected in §6.1.

**Refinement 3 — added rank 2.5 (automated lint).** The wiki's lint-primitive doc flags *"lint defined but not automated"* as an ecosystem-wide gap (Panel §4.2). Original assessment missed this. Added as §6.5b and rank 2.5 in §7.

**Meta-observation.** This cross-check demonstrates the wiki working exactly as intended — three ingests of careful analysis produced deeper, more actionable conclusions than ad-hoc assessment. Ironic note: had rank 1 already been implemented (query-save-back with drift integrity), this assessment could have been filed back into the wiki and queried against in a subsequent session, compounding forward. That's the feedback loop we're proposing to close.

---

## 9. Summary verdict

**We faithfully implement Karpathy's LLM-Wiki vision, and meaningfully improve on it in four areas:**

1. Provenance machinery (addresses the community's #1 critique — truth maintenance)
2. Multi-vault isolation (beyond the gist's single-vault scope)
3. Content-trust boundary (explicit safety property the gist doesn't address)
4. Extended lint (8 checks vs gist's ~4)

**The one gap worth closing, emphatically:** query-answer save-back. The gist calls this out as *"the important insight"* and we've been on the wrong side of it since bootstrap.

**Low-cost polish wins:** divergence checks, two-output rule in query, lightweight type-classify, editor-not-writer constraint. Each is a sub-10-line addition to one SKILL.md.

**What to leave alone:** our complexity, our provenance system, our multi-vault architecture, our skills count, our script minimalism. Each is justified by real operator need, and the simplification candidates that exist (per-claim marker redundancy, "three raw sources" naming) are documentation-level, not code-level.

---

## 10. Approval protocol

*Revised post-wiki-cross-check to include rank 2.5.*

Reply with one of:

- **"approved ranks 1-5+2.5"** — execute all 6 fork patches as a single review cycle
- **"approved rank 1 only"** — just add query-save-back (with full drift integrity); pause on the others
- **"approved ranks 1+2.5"** — the two gap-closers flagged by both gist and wiki (save-back + automated lint)
- **"approved ranks 1-3+2.5"** — save-back + divergence + auto-lint + two-output (highest-value subset)
- **"reject / discuss"** — call out what to change about the analysis

**Recommendation (revised post-HARNESS-INTEGRATION):** "**approved ranks 2-3 + 2.5 (defer rank 1 in favor of HARNESS-INTEGRATION-PROPOSAL)**". The save-back gap is better closed by `SessionEnd` hook + auto-ingest than by a dedicated `/wiki-save-answer` skill — see HARNESS-INTEGRATION-PROPOSAL §1, §6, §7. Rank 2 closes the community's #1 epistemic-integrity critique. Rank 2.5 closes the ecosystem-wide automated-lint gap. Rank 3 tightens wiki-query per the community's two-output rule. Original rank 1 (explicit save skill) remains in scope only as an additive option later if operator finds a class of "focused syntheses" topic-clustering misses.

**Original recommendation, preserved for context:** "approved ranks 1-3 + 2.5" — rank 1 was framed as building a `/wiki-save-answer` skill with full drift integrity. Subsumed by harness hook.

Ranks 4-5 are nice-to-have but not essential; they can wait for operator experience to validate whether they're actually needed. Ranks 6-7 are kb-wiki housekeeping for next ingest cycles.

Each rank = one fork branch → test → merge → push. Same defensive discipline as FORK-MIGRATION and LEGACY-CLEANUP.

---

## 11. Cross-references for next ingestion

**New concepts:**
- `concepts/query-save-back-loop` — the pattern (after rank 1 implementation)
- `concepts/divergence-check` — the pattern (after rank 2 implementation)
- `concepts/ingest-mechanics` — rank 6 (folds together in-vault-sources + scp-push + sources-dir as a single reference)

**Updates to existing:**
- `concepts/fold-back-loop` — rank 1 would close the "ar9av ships only half the fold-back" caveat
- `concepts/wiki-curation-discipline` — editor-not-writer addition (rank 5)
- `synthesis/fold-back-gap-analysis` — fundamentally shifts if rank 1 lands

**New reference:**
- `references/vision-fidelity-assessment-doc` — this file

---

*End of assessment. Awaiting approval.*
