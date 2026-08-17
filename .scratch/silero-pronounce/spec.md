# Spec: Silero / TTS pronunciation fixes

## Goal

Readable speech for section refs and Latin brands without breaking player `§` display.

## Decisions (grilling)

- Extract: keep `§3.2` → `в разделе 3 точка 2` (Arabic digits); strip PSLC footers in patterns
- Pre-synth only: digits → Russian words; `pronounce:` token map from patterns YAML
- UI/cues/txt: still show `§N.M` via `section_refs_for_display`
- Engines: say / piper / silero all get pre-synth
- Dictionary: ~40 IT tokens in `patterns/default.yml` (`pronounce:`)

## Out of scope

- Dual stored display/spoken fields
- Reverse word→digit mapping
- Huge external lexicon file
