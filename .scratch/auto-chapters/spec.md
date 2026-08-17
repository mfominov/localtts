# Spec: Auto chapters without mandatory chapters.txt

## Goal

`listen-*` works without hand-written `chapters.txt` when PDF has bookmarks; otherwise auto-draft `{pdf_stem}.chapters.txt` from TOC text for review, then listen.

## Decisions (from grilling)

Resolution order (chapters mode):
1. Explicit `--chapters-file` / `CHAPTERS_FILE`
2. PDF outline (bookmarks)
3. Existing `{pdf_stem}.chapters.txt` beside the PDF (reuse, do not overwrite on listen)
4. Explicit `--chapter-pages` / `CHAPTER_PAGES` > 0
5. Else: parse TOC (`is_toc_page` pages, else first N pages) → write draft sidecar → **stop** (no TTS)
6. Parse failure → clear error + hints

- `make draft-chapters` / `--draft-chapters`: always regenerate/overwrite sidecar
- Parser: dotted leaders + trailing page + stacked title/page lines; normalize dots / `стр.`; reject years as pages
- Draft chapters = **top-level TOC only** (`ЧАСТЬ N`, `РЕЗЮМЕ`, `ЗАКЛЮЧЕНИЕ`, `ПРИЛОЖЕНИЕ`, `ГЛОССАРИЙ`, ALL CAPS); subsections like `1.1` excluded
- Same PDF page: prefer top-level title over subsection when deduping
- `is_toc_page`: also high ratio of page-only lines (stacked TOC without leaders)
- Tests: inline TOC fixtures → ranges
- README: happy path without `CHAPTERS_FILE`

## Out of scope

- LLM
- Silent default `CHAPTER_PAGES=20`
- Removing manual `--chapters-file`
