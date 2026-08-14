# Local PDF -> Speech (macOS)

Этот скрипт озвучивает PDF полностью локально, чтобы слушать документ во время работы.

## Почему не Whisper

`Whisper` делает обратное: **речь -> текст** (STT).
Для твоей задачи нужен TTS: **текст -> речь**.

В этом решении используется:
- `pypdf` для чтения PDF
- встроенный `say` в macOS для офлайн-озвучки

## Быстрый старт

Нужен **Python 3.11+** (Makefile по умолчанию: `/opt/homebrew/bin/python3.11`).

```bash
make install
# или вручную:
# /opt/homebrew/bin/python3.11 -m venv .venv && source .venv/bin/activate
# pip install -e .

.venv/bin/python pdf_to_audio.py /path/to/document.pdf --out-dir audio_book --voice Milena
```

Результат:
- `audio_book/part_0001.aiff`, `part_0002.aiff`, ...
- `audio_book/*.wav` (для браузера)
- `audio_book/playlist.m3u`
- `audio_book/manifest.json` + `player.html`

## Более живой голос (Piper)

`say`/Milena — быстро, но роботизированно. Для более естественного русского голоса:

```bash
make install-piper
make listen-piper PDF=./doc.pdf CHAPTERS_FILE=./chapters.txt
```

Отдельные targets:
- `make listen-say` / `make run-chapters-say` — macOS `say`
- `make listen-piper` / `make run-chapters-piper` — Piper Irina
- `make listen-silero` / `make run-chapters-silero` — Silero (Xenia и др.)

Это скачает модель `ru_RU-irina-medium` (~63 MB) и поставит `piper-tts` + `espeak-ng`.

## Silero TTS

Ещё один локальный нейро-голос (часто звучит естественнее Piper на русском). Нужны `torch` + `silero` (~сотни MB при первой установке):

```bash
make install-silero
make listen-silero PDF=./doc.pdf CHAPTERS_FILE=./chapters.txt
```

Голоса: `xenia` (по умолчанию), `aidar`, `baya`, `kseniya`, `eugene`.

```bash
FORCE=1 make listen-silero PDF=./doc.pdf CHAPTERS_FILE=./chapters.txt \
  SILERO_SPEAKER=aidar SILERO_SAMPLE_RATE=48000
```

Модель по умолчанию — `v5_ru` (латиница в тексте ок; для вопросов — `SILERO_MODEL=v5_5_ru`).
Не используйте `v5_2_ru` на документах с английскими словами — там падает обработка латиницы.

Silero синтезирует **по предложениям** и пишет измеренные cues (`timing: measured` в `manifest.json`) —
подсветка в плеере совпадает с реальной длиной фраз. Пауза между предложениями:
`SILERO_SENTENCE_GAP=0.25` (секунды). У `say` / Piper cues по-прежнему оценочные (`speech_weight`).


## Браузерный плеер (текст + аудио)

После генерации:

```bash
make listen-say PDF=./doc.pdf CHAPTERS_FILE=./chapters.txt
# или
make listen-piper PDF=./doc.pdf CHAPTERS_FILE=./chapters.txt
# или
make listen-silero PDF=./doc.pdf CHAPTERS_FILE=./chapters.txt
```

`make listen-say` / `make listen-piper` / `make listen-silero` сначала делают нарезку, затем открывают плеер.
Если в `OUT_DIR` уже есть `manifest.json`, повторный `listen-*` **не** пересобирает аудио (и не чистит файлы) — только открывает плеер.
Пересборка с нуля (сначала удалит wav/aiff в `OUT_DIR`):

```bash
FORCE=1 make listen-silero PDF=./doc.pdf CHAPTERS_FILE=./chapters.txt
```

Только открыть готовое:

```bash
make serve
```

Если аудио уже готово и нужна только раздача:

```bash
make serve OUT_DIR=output_audio
```

Откроется `http://127.0.0.1:8765/player.html`:
- список глав
- внутренние разделы (`2.1`, `2.2`…) под активной главой
- текст с подсветкой текущего предложения
- клик по разделу/предложению — переход в аудио
- автопереход к следующей главе

Синхронизация пока приблизительная (по длине предложений и реальной длительности трека).

Обновить плеер и разделы без повторной озвучки:

```bash
make refresh-web
```

## Экспорт аудиокниги (`.m4b`)

После `listen-*` / `run-chapters-*` можно собрать один файл с главами и обложкой для телефона:

```bash
brew install ffmpeg          # один раз
make install-audiobook       # pymupdf для обложки из PDF

make export-audiobook OUT_DIR=output_audio PDF=./doc.pdf \
  BOOK_TITLE="Моя книга" BOOK_AUTHOR="Автор" \
  COVER_PAGE=1 BITRATE=96k
```

Результат: `output_audio/audiobook.m4b` и `output_audio/cover.jpg`.

Своя обложка (PDF не нужен):

```bash
make export-audiobook OUT_DIR=output_audio COVER=./cover.jpg BOOK_TITLE="Моя книга"
```

## Навигация по главам

Можно генерировать по одному файлу на главу:

```bash
python3 pdf_to_audio.py ./doc.pdf --mode chapters --out-dir audio_book
```

Как работает:
- сначала берется PDF оглавление (bookmarks/outlines);
- если нужен сложный ручной сценарий, можно передать свой файл глав;
- если оглавления нет, можно сделать fallback по фиксированному числу страниц:

```bash
python3 pdf_to_audio.py ./doc.pdf --mode chapters --chapter-pages 20
```

### Кастомный список глав

Формат файла `chapters.txt`:

```text
# Название|start-end
Введение|1-12
Глава 1. Архитектура|13-47
Глава 2. Практика|48-89
Приложения|90-110
```

Запуск:

```bash
python3 pdf_to_audio.py ./doc.pdf --mode chapters --chapters-file ./chapters.txt
```

## Полезные команды

Показать доступные голоса:

```bash
say -v "?"
```

Озвучить только часть документа (например, страницы 10-80):

```bash
python3 pdf_to_audio.py ./doc.pdf --start-page 10 --end-page 80
```

Увеличить размер чанка (меньше файлов):

```bash
python3 pdf_to_audio.py ./doc.pdf --max-chars 8000
```

Через `Makefile`:

```bash
make run-chapters-say PDF=./doc.pdf
make run-chapters-say PDF=./doc.pdf CHAPTER_PAGES=20
make run-chapters-say PDF=./doc.pdf CHAPTERS_FILE=./chapters.txt
make run-chapters-piper PDF=./doc.pdf CHAPTERS_FILE=./chapters.txt
make run-chapters-silero PDF=./doc.pdf CHAPTERS_FILE=./chapters.txt
```

## Параллельная генерация

В Makefile дефолт `JOBS=4`. Переопределение:

```bash
make run-chapters-say PDF=./doc.pdf CHAPTERS_FILE=./chapters.txt JOBS=2
```

Или напрямую:

```bash
python3 pdf_to_audio.py ./doc.pdf --mode chapters --chapters-file ./chapters.txt --jobs 4
```

### Замеры (один и тот же PDF, 11 глав, `JOBS=4`)

Wall-clock до `Done in …` (macOS, прогресс `[done/N] +per-file elapsed`):

| Движок | Wall-clock | Комментарий |
|--------|------------|-------------|
| `say` (Milena) | **1m39s** | Главы реально параллелятся (порядок завершения скачет) |
| `silero` (v5_ru / xenia) | **2m12s** | Быстрый движок, но `_silero_lock` сериализует TTS — `JOBS>1` почти не ускоряет синтез (`+…` включает ожидание лока) |
| `piper` (irina-medium) | **11m34s** | Параллель по главам работает, сам движок заметно медленнее |

Вывод: дефолт `JOBS=4` полезен для **say** и **piper**; для **silero** скорость в основном от модели, не от числа воркеров (`_silero_lock`).

## Как убрать зачитывание номера страницы / TOC

По умолчанию скрипт чистит текст по `patterns/default.yml`:
- выкидывает строки колонтитулов/номеров страниц;
- подчищает «прилипшие» footer'ы после нормализации;
- пропускает страницы, похожие на оглавление (`skip_toc`).

Свой шаблон:

```bash
PATTERNS_FILE=./my-clean.yml make listen-silero PDF=./doc.pdf CHAPTERS_FILE=./chapters.txt
```

Отключить очистку полностью:

```bash
python3 pdf_to_audio.py ./doc.pdf --no-strip-page-artifacts
```

## Произношение AI / ИИ

Чтобы `AI` и `ИИ` не читались как отдельные буквы, добавлена замена перед TTS:
- `AI` -> `эй ай`
- `ИИ` -> `и и`

Можно переопределить:

```bash
python3 pdf_to_audio.py ./doc.pdf --ai-spoken-as "эй-ай" --ii-spoken-as "ай-ай"
```

Ссылки вида `§2.5.1` перед озвучкой превращаются в `в разделе 2 точка 5 точка 1`, чтобы не терялась первая цифра и не читалось как десятичное число.

Кавычки (`«...»`, `“...”`, а также артефакты PDF вроде `\...\`) убираются и оформляются как прямая речь для `say`: короткая пауза и лёгкий подъём тона.

## Примечания

- Pre-commit: `pip install pre-commit && pre-commit install`, затем `pre-commit run --all-files`.
- Если в PDF текст не выделяется (скан), сначала нужен OCR.
- Формат по умолчанию `aiff` (нативный для `say`).
- Для русских текстов на macOS обычно хорошо подходят голоса `Milena` или `Yuri` (зависит от установленных voices).
