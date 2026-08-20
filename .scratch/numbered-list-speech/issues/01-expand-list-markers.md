# 01 — expand numbered list markers

Category: enhancement
Status: resolved

## Brief

Implement `.scratch/numbered-list-speech/spec.md`: `N. text` → `первое. text` (neuter ordinal), without breaking `1.3` headings.

## Done when

- `expand_numbered_list_markers` in TTS path
- Tests for list vs `1.3`
- heading-speech out-of-scope line updated

## Answer

`expand_numbered_list_markers` in `prepare_tts_spoken_text` after part headings. Tests: `tests/test_numbered_list_speech.py`.

## Comments

> Grilled 2026-08-20; Q13=A — code slice 1 now.
