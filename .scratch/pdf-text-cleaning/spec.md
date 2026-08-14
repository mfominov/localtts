# Spec: PDF text cleaning via patterns YAML

## Goal

Less junk in TTS: headers/footers/page numbers and TOC-like pages, tunable without code changes.

## Decisions (grilling)

- Config: `patterns/default.yml` + optional `PATTERNS_FILE` / `--patterns-file`
- TOC: skip pages via heuristics (keywords + dotted leaders), thresholds in YAML (`skip_toc`)
- Scope: migrate `strip_page_artifacts` / `strip_inline_page_artifacts` regexes into YAML + TOC skip
- Dep: `pyyaml` in main dependencies
- Tests: `tests/test_cleaning.py` with inline fixtures (unittest)
- Out of scope: auto `chapters.txt`, LLM cleaning, deep OCR repair, pronunciation config

## Acceptance

- Fixture tests green
- Real chapter listen (Silero) shows fewer artifacts / no TOC dump
