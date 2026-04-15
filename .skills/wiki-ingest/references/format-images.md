# Format: Images

Parsing guide for image sources — screenshots, whiteboard photos, diagrams, slide captures. Called from `wiki-ingest/SKILL.md` Step 1 when the source has an image extension (`.png`, `.jpg`, `.jpeg`, `.webp`, `.gif`).

**Requires a vision-capable model.** Models without vision support should skip image sources and report the skipped filenames to the operator so they can re-run.

## How to read

Use the Read tool directly — it renders the image into context. The extraction pass is interpretive; walk the image methodically:

1. **Transcribe** any visible text verbatim — UI labels, slide bullets, whiteboard handwriting, code snippets in screenshots. This is the **only extracted content** from an image.
2. **Describe structure** — for diagrams, list boxes/nodes and arrows/edges. For screenshots, name the app or context if recognisable.
3. **Extract concepts** — what is the image *about*? What ideas, entities, or relationships does it convey? Most of this is inferred.
4. **Note ambiguity** — handwriting you can't read, arrows whose direction is unclear, cropped content. Use `^[ambiguous]` and call it out.

## Provenance skew

Vision is interpretive by nature. Image-derived pages will skew heavily toward `^[inferred]`. That's expected — the provenance markers exist precisely to surface this. **Don't pretend an image's "meaning" was extracted when you really inferred it.**

## PDFs that are mostly images

For scanned docs or slide decks exported to PDF, use `Read pages: "N"` to pull specific pages and treat each page as an image source.

## Folders of related images

For a folder of screenshots from a single debugging session or topic, cluster by visible subject rather than per-file. Twenty screenshots of the same UI bug should produce **one** wiki page, not twenty.

Skip files with EXIF-only changes (re-saved with no visual diff) — the standard SHA-256 delta logic catches this.

## Manifest fields

- `source_type: image`
- `format:` record the original extension (`png`, `jpg`, `webp`, `gif`) if useful for filtering
