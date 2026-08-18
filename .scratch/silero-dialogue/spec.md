# Spec: Silero quote dialogue pauses

## Goal

Around quoted speech, Silero inserts silence (no pitch/SSML) so dialogue feels separated from narration.

## Decisions (grilling)

- Silero-only; say keeps `[[slnc]]`/`[[pbas]]`
- Quotes: `«»` / `“”` / `"..."`; glyphs not spoken
- Config: `speech.dialogue.quote_before_ms` / `quote_after_ms` (280 / 180)
- No dash-dialogue, no speaker switch, no SSML
- Cues remain sentence-level
- Long quotes (>280 chars): strip glyphs, skip dialogue pauses (parity with say)

## Acceptance

- Unit: `split_quote_segments` + patterns load
- Short Silero smoke with `«…»`
