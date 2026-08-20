# Spec: Ear pronounce batch (wiki / inference / …)

## Status

Implemented 2026-08-20 (срез 3) — seed merge; further LOG mining optional.

## Goal

Латинские фразы и токены, которые Silero пропускает или калечит (`wiki`, `inference`, `Configuration Items`, `nice-looking demo`, `Identify gaps`, `ИИ-driven Knowledge Management`, …), получить letter-style `pronounce:`.

## Decisions (grilling 2026-08-20)

- Источник: список из ушей + `make pronounce-candidates` / `LOG=`
- Workflow как раньше: ChatGPT → ручной merge в `patterns/default.yml` (без runtime LLM)
- Срез 3 после lists + currency-scale NUM
- OpenSpec не трогаем

## Seed tokens (from ear)

- wiki / wiki-система
- inference
- Configuration Items
- nice-looking demo
- ИИ-driven / Knowledge Management
- Identify gaps
- Recommend improvements / Draft articles / Tag / categorize (по мере появления в LOG)

## Acceptance

- Ключи в `patterns/default.yml`; unit smoke на фразах из seed
- Уши: фрагменты больше не ValueError/не «молча»
