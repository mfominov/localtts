# 01 — Playback rate in the dock

Status: resolved

Type: task

Category: enhancement

## What

Implement `.scratch/player-playback/spec.md`: скорость в доке, persist, `[` `]`.

## Done when

Spec acceptance: контрол работает после `refresh-web`, rate не сбрасывается на новой главе.

## Answer

`05352c5` — `web/player.html`: `SPEED_RATES`, localStorage, pitch preserved, re-apply on `loadedmetadata`/`play`.

Также в этом коммите восстановлен `loadChapter` (регресс после HTML-таблиц в `ace6b9d`): без него плеер не переключал главы.
