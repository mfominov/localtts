# OpenSpec: PDF-to-Audio / Silero TTS Pipeline (reference)

## Status for localtts

**Cherry-pick only.** Full 14-stage / Speech IR architecture is **not** adopted wholesale.

### Adopted decisions (grilling 2026-08-18)

- Success metric: ear quality on real PDFs (not engineering purity).
- Keep letter-style `pronounce:` / `ai_spoken_as` (not OpenSpec full ABBR expansions).
- First slice: **NUM v1** — numbers/dates/%/currency/№ → speech (`normalize_numbers.py`, pre-synth).
- Near-term **non-goals:** Speech IR, OCR, tables, LUFS/reverb, full SSML adapter.
- This file is a **backlog / reference**, not an implementation mandate.

### Backlog (from OpenSpec, unscheduled)

- OCR fallback + garbage filter
- Repeatability-based headers/footers
- `chapters.json` IR
- Table narration
- Full abbreviation expansion + context tiers
- ё / stress / `put_yo`/`put_accent`
- Dialogue prosody + configurable pauses
- Speech IR + Silero Adapter
- Per-chunk retry + diagnostic event schema
- Loudness mastering
- Fixtures from OpenSpec §20

---

## Original OpenSpec (verbatim summary of intent)

Pipeline stages: PDF Extraction → Structure → Cleanup → Semantic Normalization → Abbreviation → Numbers/Dates/Symbols → Russian Pronunciation → Dialogue → Speech Markup → Chunking → Silero Adaptation → TTS → Audio Mastering → Assembly.

Key requirements retained as reference: PDF-001…003, STRUCT-001…002, NORM-001 (§ refs), TABLE-*, ABBR-*, NUM-*, RU-*, DIALOG-*, PAUSE-*, CHUNK-*, SILERO-*, TTS-*, AUDIO-*, Speech IR, diagnostics, acceptance, fixtures, P0/P1/P2 priority, Non-Goals §22.

Full pasted OpenSpec lived in the chat session that created this file; implementers should prefer the **Adopted decisions** above over copying the greenfield design into `pdf_to_audio.py`.
