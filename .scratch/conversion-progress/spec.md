# Spec: Terminal conversion progress + elapsed

## Goal

While converting PDF→audio, the terminal shows per-file progress with wall-clock timing so long Silero/F5 runs are understandable without a web UI.

## Decisions (from grilling)

- Surface: **terminal only** (plain lines, always scrolled)
- Unit: completed **chapter/chunk output files** (`done/N`, not chapter idx)
- Metrics: **per-file duration** (`+…`) + **elapsed** from start of conversion `main`
- Engines: all via `run_jobs` (`say` / piper / silero / f5tts)
- Deps: **stdlib only** (`time`)
- Model load: no special line; cold start may inflate first file / early elapsed
- Errors: unchanged (fail the run); printed lines stay
- Finale: `Done in … (N files)` then existing path lines
- Tests: unit tests for duration/progress formatters (no TTS)
- Out of scope: web progress, ETA, sentence-level bar, tqdm/rich, README, soft-fail per file

## Example

```
[3/12] chapter_003_….aiff  +2m14s  elapsed 8m01s
…
Done in 12m03s (12 files)
```

## Acceptance

- Serial and `JOBS>1` both print `done/N` in completion order
- Durations use `12s` / `2m14s` / `1h02m`
- `tests/test_progress.py` passes without TTS models
