# 01 — export-audiobook m4b

Status: resolved

Type: task

## What

Implement `--export-audiobook` + `make export-audiobook` per `.scratch/export-audiobook/spec.md`.

## Done when

Spec acceptance met; formatter/timeline unit tests pass.

## Answer

`--export-audiobook` + `make export-audiobook`: ffmpeg m4b with chapter markers, pymupdf cover (or COVER=), bitrate default 96k. Optional extra `[audiobook]`. Tests: `tests/test_audiobook_export.py`.
