# Spec: NUM v1 — numbers / dates / % / currency / № for TTS

## Goal

Pre-synth Russian spoken forms for numbers so Silero does not misread digits, dates, percents, and money.

## Decisions (grilling)

- Pre-synth only (`prepare_tts_spoken_text`); UI/cues keep original digits
- Module: `normalize_numbers.py`
- Lib: `num2words` + thin wrappers
- Config: `normalize_numbers: true` in `patterns/default.yml`
- Order: §-digits → words → **pronounce:** → **NUM** (so `GPT-3.5` is not eaten as a decimal)
- In scope: integers (incl. `1 500`), decimals (`,`/`.`), `%` inflection, `№`, `₽$€`, dates `ДД.ММ.ГГГГ` / `ДД.ММ.ГГ`
- Also: comparisons `≥ ≤ >= <= ≠` before a number; years with prep `к/в/с/до/… 20XX году|года` (ordinal case)
- Also: genitive after `не менее/не более/более/менее/свыше/около/порядка/от/до` (`не менее 20%` → «двадцати процентов»)
- Also: hyphen ordinals `1-е` / `2-й` / `3-я` / `1-го` (num2words gender+case)
- Out of scope v1: ranges `10–20`, bare `<`/`>`, full prepositional government for every noun

## Acceptance

- Unit/golden cases from OpenSpec numbers section
- Short Silero smoke on a mixed sentence
