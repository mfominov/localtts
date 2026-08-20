# Spec: Player playback speed

## Goal

В доке веб-плеера можно менять скорость речи, не пересобирая TTS. Подсветка cue остаётся на `audio.currentTime` (media time).

## Decisions (grilling 2026-08-20)

- Срез отдельный от `.scratch/player-reader-typography/` (там speed/hotkeys/localStorage были out of scope)
- Ступени: `0.75 1 1.25 1.5 1.75 2`
- UI: − / значение / + рядом с transport; клик по значению → `1×`
- Клавиши `[` / `]` (без модификаторов, не в input)
- Persist: `localStorage` ключ `localtts-playback-rate`; пусто / невалидно → **1×** (не 0.75: `Number(null)===0`)
- `playbackRate` заново после `load()` / `play` (смена главы не сбрасывает)
- `preservesPitch` / `webkitPreservesPitch` = true
- Strip дубля заголовков — `.scratch/heading-speech/`, не этот spec

## Out of scope

- Произвольный slider, 0.5×, pitch-shift
- Bookmarks, остальные hotkeys
- Phone drawer

## Acceptance

- В доке виден контрол; скорость переживает reload и смену главы
- `make refresh-web` подхватывает `web/player.html`
