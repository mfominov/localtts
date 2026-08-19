# Spec: pronounce candidates (one-shot ChatGPT → YAML)

## Goal

Найти латинские токены, которых ещё нет в `pronounce:`, и подготовить copy-paste в ChatGPT для letter-style транскрипций. Runtime LLM нет.

## Decisions (grilling)

- Разовый офлайн: кандидаты → ChatGPT → ручной merge в `patterns/default.yml`
- Только `pronounce:` (не homographs / не фразы)
- Кандидаты: regex латиница, interesting (CAPS / CamelCase / цифры / `.-+`), частота ≥2, минус существующие ключи (casefold)
- Источник: PDF extract до pronounce/NUM, или TEXT до pronounce; не spoken `.txt` из OUT_DIR
- Скрипт только печатает; не патчит YAML; без overwrite существующих
- Ожидание: +10–25% комфорта на хвосте после review
- Успех: ≥15 новых ключей + уши на 1 главе

## Out of scope

- Runtime / API LLM
- Авто-apply в default.yml
- Homographs, `≥`, падежи годов
