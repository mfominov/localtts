# 01 — wire ruaccent into Silero spoken path

Category: enhancement
Status: resolved

## Brief

Implement `.scratch/silero-ruaccent/spec.md`: `ruaccent` in main deps, YAML on/off + model size, spoken order with `custom_dict` from `homographs:`.

## Gate

Maintainer said `go stress` (2026-08-20).

## Done when

- `ruaccent` in `pyproject.toml` dependencies; install docs in README
- `patterns/default.yml`: `silero.ruaccent: true`, model default `turbo3.1`
- Spoken pipeline: `§ → pronounce → NUM → ruaccent → homographs`
- `homographs` map also fed as `custom_dict`
- Only Silero engine path
- Unit + omograph fixtures; opt-out restores prior behavior
- Ear check on a real chapter; note wall-time delta (budget ≤ +30%)

## Answer

Wired in `pdf_to_audio.py` (`apply_ruaccent`, YAML flags, Silero-only). Unit tests: `tests/test_silero_ruaccent.py` (mocked accentizer). Ear / wall-time left to maintainer listen.

## Comments

> Grilled 2026-08-20 (Q1–Q17). Shared understanding confirmed (Q17=B): spec now, code on `go stress`.
