# 02 — Drop orphan punct clauses from Silero skip log

Status: resolved

Type: task

Category: bug

## What

Implement the orphan-punct decision in `.scratch/silero-pauses/spec.md`: голые `,` `.` `:` `;` `!` `?` / тире не слать в Silero и не писать `not speakable` в лог. Списки `1.` не трогать. Пунктуация в UI остаётся.

## Done when

`split_speech_clauses(", дальше.")` → `["дальше."]`; `1.` всё ещё отдельная клауза; unit green.

## Answer

`split_speech_clauses`: punct-only клеится к предыдущей клаузе (если та ещё без знака) или отбрасывается как leading. В `synthesize_with_silero` punct-only после `prepare_silero_text` — тихий `continue` без skip-log. Тесты: `tests/test_speech_pauses.py`.
