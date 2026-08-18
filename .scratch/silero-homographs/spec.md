# Spec: Silero RU flags + homograph overrides

## Goal

Expose Silero `put_yo` / `put_accent` in patterns and allow optional `+stress` homograph overrides for ear fixes.

## Decisions (grilling)

- v5_ru already defaults put_yo/put_accent to True — wire explicitly for config/docs
- `silero:` section in `patterns/default.yml`
- `homographs:` map surface → Silero form with `+` before stressed vowel (empty by default)
- Order: § → pronounce → NUM → homographs
- Homographs/+ markers only on Silero path (say/piper never see `+`)
- Pre-synth only; UI/cues unchanged
- No external ruaccent in this slice
- Queue after this: pauses/chunk → dialogue

## Acceptance

- Unit: load flags, homograph map, apply_tts kwargs
- Short Silero smoke with a homograph override
