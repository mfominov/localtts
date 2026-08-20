# Spec: Normalize Gartner GDOC references for TTS

## Goal

GDOC IDs (`G########`) не озвучиваются; attribution остаётся словом **Gartner**, даты/авторы/`n=` сохраняются.

## Decisions

- Extract-time: `normalize_gartner_gdoc` после cleanup, до pronounce-candidates
- Order: `Gartner (GDOC, …)` → drop ID; `Gartner GDOC` → `Gartner`; remaining `GDOC` → `Gartner`
- Local punctuation cleanup only (`(,` `,,` `,)` etc.)
- Exclude `G\d{8}` from `pronounce_candidates`

## Acceptance

- Unit cases 1–7 from OpenSpec (see `tests/test_gartner_gdoc.py`)
- No `Gartner Gartner`; no GDOC in final extract/TTS text
