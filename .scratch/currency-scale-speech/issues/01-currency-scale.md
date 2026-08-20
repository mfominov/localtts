# 01 — currency + млрд/млн/тыс lossy speech

Category: enhancement
Status: resolved

## Brief

Implement `.scratch/currency-scale-speech/spec.md` in `normalize_numbers.py`.

## Done when

- `$1,04 млрд` → примерно + миллиард + доллар…; no raw `млрд`, no cents
- `$100` unchanged in spirit
- Unit tests in `tests/test_normalize_numbers.py`

## Answer

`_speak_scaled_amount` + regex before plain currency. `$1,04 млрд` → `примерно один миллиард долларов США`.

## Comments

> go на срез 2 (2026-08-20)
