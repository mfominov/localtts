# Spec: File-extension split + PDLC pronounce batch

## Goal

Не резать предложения/клаузы на точке в именах файлов (`init.sh`, `NOTES.md`) и вмержить ear/ValueError pronounce-батч без опасных коротких ключей-обломков.

## Behavior

- `_dot_is_file_extension`: слева stem (alnum/`_-`), справа whitelist-расширение 2–5 `[a-z]`, затем не-буква/конец.
- Используется в `split_sentences` и `split_speech_clauses`.
- Pronounce: новые ключи из батча; не добавлять `md`/`sh`/`com`/`fs`/`io`/`file`/`name`/`read`/`init`/`NOTES`/`progress`.
- Вместо обломков: `init.sh`, `NOTES.md`, `progress.md`.

## Non-goals

Сироты скобок; не-резать `,` внутри `(…)`; dotted API вроде `tools.search`.
