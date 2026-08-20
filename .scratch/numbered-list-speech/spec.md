# Spec: Numbered list markers → «первое / второе»

## Goal

Нумерованные списки `1. 2. 3.` не пропадают в Silero (`1.` был not speakable) и читаются как «первое», «второе», …

## Decisions (grilling 2026-08-20)

- Форма: средний род (`первое` / `второе` / …) через `num2words` ordinal `gender=n`
- Паттерн: `N.` + пробел + текст; **не** трогать `1.3` (нет пробела после первой точки → остаётся `expand_heading_section_numbers`)
- Срабатывает на маркерах списка в spoken-тексте; `split_sentences` / `split_speech_clauses` не режут по точке в `1. Title` (иначе сироты `'1.'` до expand)
- Порядок TTS: после heading/part expand, до pronounce/NUM
- Замена: `1. Identify` → `первое — Identify` (тире → пауза/клауза; `1.3` не матчится)
- OpenSpec backlog не двигаем; это ear-fix срез 1 из трёх

## Out of scope

- NUM `$1,04 млрд` (срез 2)
- pronounce-батч латиницы (срез 3)
- Римские номера

## Acceptance

- Unit: `1. foo` → содержит `первое`; `1.3 Title` по-прежнему `один точка три`
- `prepare` + clause split: нет orphan not-speakable `'1.'`
- Уши: список Identify gaps / Recommend… читает «первое… второе…»
