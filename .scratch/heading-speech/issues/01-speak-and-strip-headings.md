# 01 — Speak subsection/part headings and strip UI echo

Status: resolved

Type: task

Category: bug

## What

Implement `.scratch/heading-speech/spec.md`: не orphan `'1.'`/`'2.'`, не дублировать ALLCAPS echo, не рисовать заголовок второй раз в `#text`.

## Done when

Spec acceptance: unit green; UI без дубля после `refresh-web`; TTS номера — после перегона главы.

## Answer

Shipped:

- `957cd9a` — `1.3` остаётся одной клаузой, `expand_heading_section_numbers`, `collapse_allcaps_echo`
- `6985c4b` — `Часть N.` не режет предложение; `expand_part_heading_numbers` (`Часть два.`)
- `05352c5` (часть) — token-strip section/chapter title в `web/player.html`; пустой cue скрыт

Тесты: `tests/test_cleaning.py`, `tests/test_pronounce.py`, `tests/test_speech_pauses.py`.
