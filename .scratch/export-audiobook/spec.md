# Spec: Export audiobook `.m4b` with cover

## Goal

After a chapters TTS run, produce one `{OUT_DIR}/audiobook.m4b` with chapter markers, embedded cover, and book tags — easy to AirDrop/copy to iPhone and Android.

## Decisions (from grilling)

- Devices: iPhone + Android
- Format: single `.m4b` (not folder of m4a)
- Cover: render PDF page via **pymupdf** (`--cover-page`, default 1); **`--cover FILE`** overrides (then PDF not required)
- PDF required when rendering from page
- Workflow: separate `make export-audiobook` (not inside listen)
- Tooling: **ffmpeg** required; Makefile checks + `brew install ffmpeg` hint
- Markers: one chapter per `manifest.json` chapter (not sections)
- Metadata: `--book-title` / `--book-author` with defaults from PDF stem / OUT_DIR
- Bitrate: `BITRATE` default **96k**
- Scope: chapters mode + existing `manifest.json` only
- Output: `{OUT_DIR}/audiobook.m4b` (+ write `cover.jpg` when rendered/copied)

## Acceptance

- `make export-audiobook OUT_DIR=… PDF=…` builds playable m4b with chapters + cover
- Without ffmpeg / without pymupdf (when needed): clear error
- Unit tests for ffmetadata / chapter timeline helpers (no ffmpeg encode in CI)
