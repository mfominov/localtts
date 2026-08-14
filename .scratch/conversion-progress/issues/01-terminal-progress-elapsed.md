# 01 — Terminal progress lines + Done in

Status: resolved

Type: task

## What

- Add `format_duration` / `format_job_progress_line` in `pdf_to_audio.py`
- Instrument `run_jobs` (serial + thread pool) with done counter, per-job timing, elapsed from `started_at`
- `main`: set `started_at` after `--refresh-web` early exit; pass into `run_jobs`; replace bare `Done.` with `Done in … (N files)`
- `tests/test_progress.py` for formatters

## Done when

Matches `.scratch/conversion-progress/spec.md` acceptance.

## Answer

Implemented in `pdf_to_audio.py`: `format_duration` / `format_job_progress_line`, `run_jobs` prints `[done/N] name  +…  elapsed …`, `main` ends with `Done in … (N files)`. Tests: `tests/test_progress.py` (pass).
