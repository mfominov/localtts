# Spec: External stress via `ruaccent` (Silero)

## Goal

Массовая авторасстановка ударений (`+` перед гласной) через `ruaccent`, чтобы ухо реже ловило кривой stress, чем на одном Silero `put_accent`.

## Status

Implemented 2026-08-20 (`go stress`). Opt-out: `silero.ruaccent: false`.

## Decisions (grilling)

- Dep: `ruaccent` в **основных** dependencies (`pyproject.toml`), не optional extra
- Только **Silero** path; say / piper / f5 не видят `+`
- Default **on** для Silero; opt-out только YAML: `silero.ruaccent: false` (без CLI/Make)
- Модель: `silero.ruaccent_model` / `omograph_model_size` в YAML, default **`turbo3.1`**
- `use_dictionary: true` (фиксировано в v1; не флаг)
- Порядок spoken: `§ → pronounce → NUM → **ruaccent** → **homographs**`
- Ручные `homographs:` побеждают; те же пары передавать в `custom_dict` ruaccent
- Silero `put_accent` / `put_yo` остаются `true` (страховка вместе с pre-marked `+`)
- Load accentizer once per process; модели с HF при первом `load`, дальше кэш
- Chunk long unpunctuated clauses (~1200 chars) before `process_all`; on ONNX errors skip chunk + reload session (JOBS>1 must not crash the run)
- Patch ONNX `session.run` to inject zero `token_type_ids` (transformers 5+ omits them; ruaccent accent/stress models still require)
- Бюджет: до **+30%** wall time на главу (Mac CPU) — замерить на приёмке
- Старт кода: явная команда maintainer **`go stress`** (не число N глав)

## Out of scope

- Headers/footers / OCR garbage
- Speech IR, full ABBR, tables, LUFS
- Stress path для non-Silero
- Замена `homographs:` / отказ от Silero `put_accent`

## Acceptance

- Unit: flags из YAML; порядок пайплайна; `homographs` поверх `ruaccent`; `custom_dict` из map
- Фикстуры омографов (`замок` / `мука` / …) — ожидаемый `+`
- Уши: 1–2 реальных главы Silero лучше или не хуже baseline по ударениям
- Opt-out `silero.ruaccent: false` → поведение как до среза
- README: deps, YAML keys, первый download моделей

## Pipeline order (target)

```
§ → pronounce → NUM → ruaccent → homographs → Silero apply_tts(put_yo, put_accent)
```
