# OpenSpec: PDF-to-Audio / Silero TTS Pipeline (reference)

## Status for localtts

**Cherry-pick only.** Full 14-stage / Speech IR architecture is **not** adopted wholesale.

### Adopted decisions (grilling 2026-08-18)

- Success metric: ear quality on real PDFs (not engineering purity).
- Keep letter-style `pronounce:` / `ai_spoken_as` (not OpenSpec full ABBR expansions).
- First slice: **NUM v1** — done (`normalize_numbers.py`).
- Next slice: **RU v1** — done (`.scratch/silero-homographs/spec.md`).
- Then: **pauses/chunk B** — done (`.scratch/silero-pauses/spec.md`); **C dialogue** — done (`.scratch/silero-dialogue/spec.md`).
- **Status (2026-08-18):** OpenSpec cherry-pick **paused**. Near-term = ear-driven `pronounce:` / `homographs:`.
- **Status (2026-08-20):** Next engineered slice after pronounce settles: **`ruaccent`** (grilled; spec `.scratch/silero-ruaccent/spec.md`). Code gated on maintainer `go stress`.
- **Preferred next after pronounce:** external stress resolver (`ruaccent`) — see silero-ruaccent spec.
- Near-term **non-goals:** Speech IR, OCR, LUFS/reverb, full SSML adapter, full ABBR expansions, pymupdf table finder.

### Backlog (from OpenSpec, unscheduled)

- External stress resolver (`ruaccent`) ← preferred next after pronounce (spec ready)
- Repeatability-based headers/footers
- OCR fallback + garbage filter
- `chapters.json` IR
- Table narration (first slice: row pauses + HTML in player; not pymupdf find_tables)
- Full abbreviation expansion + context tiers
- Dash-dialogue / speaker-switch for Silero (beyond quote silence)
- Speech IR + Silero Adapter
- Per-chunk retry + diagnostic event schema
- Loudness mastering
- Fixtures from OpenSpec §20

---

## Original OpenSpec (verbatim summary of intent)

Pipeline stages: PDF Extraction → Structure → Cleanup → Semantic Normalization → Abbreviation → Numbers/Dates/Symbols → Russian Pronunciation → Dialogue → Speech Markup → Chunking → Silero Adaptation → TTS → Audio Mastering → Assembly.

Key requirements retained as reference: PDF-001…003, STRUCT-001…002, NORM-001 (§ refs), TABLE-*, ABBR-*, NUM-*, RU-*, DIALOG-*, PAUSE-*, CHUNK-*, SILERO-*, TTS-*, AUDIO-*, Speech IR, diagnostics, acceptance, fixtures, P0/P1/P2 priority, Non-Goals §22.

Full pasted OpenSpec lived in the chat session that created this file; implementers should prefer the **Adopted decisions** above over copying the greenfield design into `pdf_to_audio.py`.
