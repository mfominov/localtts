# Spec: Heading speech + reader strip

## Goal

Подпункты (`1.3`) и части (`Часть 2.`) читаются целиком, без skip `'1.'` / `'2.'` и без «Часть Часть». В плеере заголовок не дублируется в теле абзаца.

## Decisions (grilling 2026-08-20)

- Extract: `collapse_allcaps_echo` — `ЧАСТЬ Часть` → `Часть`
- Extract: `detach_glued_section_headings` — точка между `1.3 Title` и следующим предложением (пауза)
- Extract: `detach_glued_part_headings` — то же для `Часть|Глава|Раздел|Приложение N. Title` + body
- Split: не резать предложение/клаузу на точке в `1.3` и на `Часть N.` перед заглавным title
- TTS-only: `1.3 Title` → `один точка три Title` (не десятичная NUM)
- TTS-only: `Часть 2.` → `Часть два.` (Silero не skip `'2.'`)
- Player: вырезать токены section/chapter title из cue; пустой heading-cue не рисовать (`sentence-heading-only`)
- Существующий аудиофайл без перегона не заговорит «два» — нужен Silero re-synth; UI-strip достаточно `refresh-web`

## Out of scope

- Нумерованные списки `1. 2. 3.` (по-прежнему not speakable)
- Римские `Часть II`
- Speed / hotkeys / localStorage (`.scratch/player-playback/`)

## Acceptance

- Unit: `tests/test_cleaning.py`, `tests/test_pronounce.py`, `tests/test_speech_pauses.py`
- Уши: после `FORCE=1 make listen-silero` «Часть два» и `1.3` без «целых/десятых»; в UI заголовок один раз
