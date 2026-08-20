# Spec: Silero / TTS pronunciation fixes

## Goal

Readable speech for section refs and Latin brands without breaking player `§` display.

## Decisions (grilling)

- Extract: keep `§3.2` → `в разделе 3 точка 2` (Arabic digits); `§4.1–4.9` → `в разделах 4 точка 1 — 4 точка 9`; strip PSLC footers in patterns
- TTS-only: `см.` → `смотри в` (or `смотри` when `в` already follows, e.g. `см. в разделе`)
- Extract: `ai_spoken_as` / `ii_spoken_as` from patterns YAML (CLI flags removed)
- Pre-synth only: digits → Russian words; `pronounce:` token map from patterns YAML
- UI/cues/txt: still show `§N.M` / `§4.1–4.9` via `section_refs_for_display`; AI/ИИ restored for display
- Engines: say / piper / silero all get pre-synth
- Dictionary: IT tokens in `patterns/default.yml` (`pronounce:`), incl. R0–R5 / R0-R5, OpenTelemetry, Board, RAG, Governance, Policy-as-Code, guardrails, ITSM-стек/стэк, red teaming, service bulletin

## Out of scope

- Dual stored display/spoken fields
- Reverse word→digit mapping
- Huge external lexicon file
