# Spec: export-audiobook progress + elapsed

## Goal

`make export-audiobook` shows phases, approximate book duration, live encode progress, and `Done in …` — same plain-line style as TTS conversion.

## Decisions (from grilling)

- Scope: export only (not listen pipeline)
- Format: plain lines (new lines for encode updates, not `\r`)
- Phases: start summary (`N chapters ~duration`) + `cover` + `prepare` + encode updates + `Done in`
- Encode: parse `ffmpeg -progress pipe:1`; emit about every 2s or +5%
- Time source: `out_time_us` (µs) or `out_time` (HH:MM:SS); **never** `out_time_ms` (misnamed µs)
- Stdlib only; reuse `format_duration`
- Unit tests for progress parse / format (no real encode)

## Example

```
Exporting 11 chapters (~2h15m audio) → audiobook.m4b…
cover  +1s  elapsed 1s
prepare  +0s  elapsed 1s
encode 12%  out 16m12s  elapsed 45s
…
Done in 4m12s
Audiobook: …/audiobook.m4b
Cover: …/cover.jpg
```
