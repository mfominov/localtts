# Spec: Silero sentence-level cues

## Goal

For `engine=silero`, sentence highlight in the web player must seek “into the ear”: cue `start`/`end` come from real per-sentence audio lengths, not `speech_weight` heuristics.

## Decisions (from grilling)

- Canonical listen path: Silero
- Mechanism: synthesize **per sentence**, concatenate, measure durations
- Gap: `SILERO_SENTENCE_GAP` / `--silero-sentence-gap`, default **0.25** s
- Cue text: timing from **spoken** sentences; UI text = `section_refs_for_display(spoken_sentence)`
- say / piper / f5tts: unchanged (estimated cues via `speech_weight`)
- Acceptance: ears on a real chapter (`FORCE=1 make listen-silero …` + seek); no fixture required

## Out of scope

- Auto-chapters / PDF text cleanup
- Whisper / forced alignment
- Sentence-synth for other engines

## Implementation notes

- Write sidecar `*.cues.json` next to each `.aiff` with `timing: "measured"`
- Manifest chapters carry `"timing": "measured"` so `refresh-web` and the player **do not** re-apply heuristic retime
- Sentences longer than `SILERO_MAX_CHARS` are sub-chunked for TTS but remain **one** cue
