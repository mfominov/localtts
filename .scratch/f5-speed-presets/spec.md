# Spec: F5 speed defaults + presets

## Goal

Make `listen-f5tts` noticeably faster out of the box while keeping acceptable quality. Silero remains the daily driver; F5 stays a rare premium path.

## Decisions

- Default `F5_NFE_STEP=16` (was 32)
- Makefile `F5_PRESET=fast|balanced|quality` maps to nfe (and speed=1.0 for now):
  - `fast` → nfe 16 (default)
  - `balanced` → nfe 24
  - `quality` → nfe 32
- Explicit `F5_NFE_STEP` / `F5_SPEED` on the CLI still override the preset
- Acceptance: one real chapter wall-clock before/after + ears

## Out of scope

- Switching canon from Silero to F5
- Measured cues for F5
- Better ref-voice workflow
- JOBS>1 on MPS
