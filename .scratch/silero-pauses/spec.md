# Spec: Silero speech pauses + chunk soft-limit

## Goal

Configurable Silero rhythm via silence after punctuation clauses and a ~300-char soft-limit.

## Decisions (grilling)

- `speech.pauses` + `speech.silero_chunk_chars` in `patterns/default.yml`
- OpenSpec defaults: period/exclam/question 400ms; comma 150; semicolon/colon 250; chunk 300
- Split clauses on `.!?,;:` keeping trailing mark; silence between clauses; inter-sentence pause outside cue
- Remove `--silero-sentence-gap` / `SILERO_SENTENCE_GAP` (YAML only)
- Do not change `--max-chars` default
- No SSML / Speech IR

## Acceptance

- Unit: clause split, pause mapping, patterns load
- Short Silero smoke with comma + period pauses
