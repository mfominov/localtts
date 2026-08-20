# Spec: Silero speech pauses + chunk soft-limit

## Goal

Configurable Silero rhythm via silence after punctuation clauses and a ~300-char soft-limit.

## Decisions (grilling)

- `speech.pauses` + `speech.silero_chunk_chars` in `patterns/default.yml`
- OpenSpec defaults: period/exclam/question 400ms; comma 150; semicolon/colon 250; chunk 300
- Split clauses on `.!?,;:` keeping trailing mark; silence between clauses; inter-sentence pause outside cue
- Spaced dash/тире (`title - subtitle`) → clause break + `dash_ms` (default 400); in-token hyphens (`AI-Disrupt`) untouched
- Opening `(` starts a new clause and `)` ends one; `paren_ms` (default 280, shorter than dash) before and after the parenthetical
- Orphan punct-only clause `[.!?,;:—–-]+` (`,` `.` `:` `;` `!` `?` тире): glue to the previous clause unless it already ends with punct; **drop** if it would be the first clause (after `»` / start). No ghost `,` clause, no skip-log. UI/cues keep punctuation. Lists `1.` / `%` / latin `(pods)` unchanged
- Silero: `prepare_tts_spoken_text` **before** clause split / speakable check, so `16% —` is not skipped as digits-only
- Table-like extract lines → `cell | cell.` rows; TTS speaks commas + period (row pause); player renders HTML table from `|`
- Remove `--silero-sentence-gap` / `SILERO_SENTENCE_GAP` (YAML only)
- Do not change `--max-chars` default
- No SSML / Speech IR

## Acceptance

- Unit: clause split, pause mapping, patterns load
- Short Silero smoke with comma + period pauses
