# 01 — wire ruaccent into Silero spoken path

Category: enhancement
Status: ready-for-agent

## Brief

Implement `.scratch/silero-ruaccent/spec.md`: `ruaccent` in main deps, YAML on/off + model size, spoken order with `custom_dict` from `homographs:`.

## Gate

**Do not start coding** until maintainer says `go stress` (after pronounce work settles).

## Done when

- `ruaccent` in `pyproject.toml` dependencies; install docs in README
- `patterns/default.yml`: `silero.ruaccent: true`, model default `turbo3.1`
- Spoken pipeline: `§ → pronounce → NUM → ruaccent → homographs`
- `homographs` map also fed as `custom_dict`
- Only Silero engine path
- Unit + omograph fixtures; opt-out restores prior behavior
- Ear check on a real chapter; note wall-time delta (budget ≤ +30%)

## Comments

> Grilled 2026-08-20 (Q1–Q17). Shared understanding confirmed (Q17=B): spec now, code on `go stress`.
