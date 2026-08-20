PYTHON ?= /opt/homebrew/bin/python3.11
VENV ?= .venv
BIN := $(VENV)/bin
SCRIPT := pdf_to_audio.py
PRONOUNCE_CANDIDATES := pronounce_candidates.py
PLAYER_SRC := web/player.html
FAVICON_SRC := web/favicon.svg

PDF ?=
TEXT ?=
LOG ?=
MIN_COUNT ?= 2
OUT_DIR ?= output_audio
VOICE ?= Milena
ENGINE ?= say
PIPER_MODEL ?= models/ru_RU-irina-medium.onnx
SILERO_MODEL ?= v5_ru
SILERO_SPEAKER ?= xenia
SILERO_SAMPLE_RATE ?= 24000
MAX_CHARS ?= 5000
START_PAGE ?= 1
END_PAGE ?= 0
MODE ?= chunks
CHAPTER_PAGES ?= 0
CHAPTERS_FILE ?=
PATTERNS_FILE ?= patterns/default.yml
JOBS ?= 4
KEEP ?= 0
FORCE ?= 0
PORT ?= 8765
COVER ?=
COVER_PAGE ?= 1
BOOK_TITLE ?=
BOOK_AUTHOR ?=
BITRATE ?= 96k

PIPER_MODEL_URL ?= https://huggingface.co/rhasspy/piper-voices/resolve/main/ru/ru_RU/irina/medium/ru_RU-irina-medium.onnx
PIPER_CONFIG_URL ?= https://huggingface.co/rhasspy/piper-voices/resolve/main/ru/ru_RU/irina/medium/ru_RU-irina-medium.onnx.json

.PHONY: help venv install install-piper install-silero install-audiobook run run-chapters run-chapters-say run-chapters-piper run-chapters-silero play listen listen-say listen-piper listen-silero serve refresh-web export-audiobook draft-chapters pronounce-candidates voices clean clean-audio

help:
	@echo "Targets:"
	@echo "  make venv             - create virtual environment"
	@echo "  make install          - install project dependencies"
	@echo "  make install-piper    - install Piper + download Russian Irina voice"
	@echo "  make install-silero   - install Silero TTS + torch (downloads model on first run)"
	@echo "  make voices           - list available macOS voices"
	@echo "  make run PDF=/path    - convert PDF to audio (ENGINE=$(ENGINE))"
	@echo "  make run-chapters-say PDF=/path    - chapters via macOS say"
	@echo "  make run-chapters-piper PDF=/path  - chapters via Piper"
	@echo "  make run-chapters-silero PDF=/path - chapters via Silero"
	@echo "  make listen-say PDF=/path          - say chapters + open player"
	@echo "  make listen-piper PDF=/path        - Piper chapters + open player"
	@echo "  make listen-silero PDF=/path       - Silero chapters + open player"
	@echo "  make draft-chapters PDF=/path      - draft {pdf}.chapters.txt from outline/TOC"
	@echo "  make pronounce-candidates PDF=/path|TEXT=/path [LOG=log] - Latin/ValueError → ChatGPT pronounce YAML"
	@echo "  make serve            - only open browser player for existing OUT_DIR"
	@echo "  make play             - play OUT_DIR/playlist.m3u in VLC"
	@echo "  make refresh-web      - update player + section markers without re-TTS"
	@echo "  make export-audiobook - build OUT_DIR/audiobook.m4b (ffmpeg + cover)"
	@echo "  make install-audiobook - install pymupdf for PDF cover render"
	@echo "  make clean-audio      - remove generated audio in OUT_DIR"
	@echo "  make clean            - remove virtual environment"
	@echo ""
	@echo "Aliases: run-chapters -> run-chapters-say, listen -> listen-say"
	@echo "listen-* skips TTS if OUT_DIR already has audio (use FORCE=1 to rebuild)."
	@echo "KEEP=1 keeps old files during rebuild (default: clean OUT_DIR first)."
	@echo "Chapters: PDF bookmarks → existing {pdf}.chapters.txt → TOC draft → stop for review."
	@echo ""
	@echo "Run options:"
	@echo "  OUT_DIR=$(OUT_DIR) VOICE=$(VOICE) PIPER_MODEL=$(PIPER_MODEL)"
	@echo "  SILERO_MODEL=$(SILERO_MODEL) SILERO_SPEAKER=$(SILERO_SPEAKER)"
	@echo "  SILERO_SAMPLE_RATE=$(SILERO_SAMPLE_RATE)"
	@echo "  MAX_CHARS=$(MAX_CHARS) START_PAGE=$(START_PAGE) END_PAGE=$(END_PAGE)"
	@echo "  CHAPTER_PAGES=$(CHAPTER_PAGES) CHAPTERS_FILE=$(CHAPTERS_FILE) PATTERNS_FILE=$(PATTERNS_FILE)"
	@echo "  TEXT=$(TEXT) LOG=$(LOG) MIN_COUNT=$(MIN_COUNT)"
	@echo "  JOBS=$(JOBS) KEEP=$(KEEP) FORCE=$(FORCE) PORT=$(PORT)"
	@echo "  COVER=$(COVER) COVER_PAGE=$(COVER_PAGE) BOOK_TITLE=$(BOOK_TITLE) BOOK_AUTHOR=$(BOOK_AUTHOR) BITRATE=$(BITRATE)"

venv:
	@if [ -x "$(BIN)/python" ]; then \
		cur="$$($(BIN)/python -c 'import sys; print(f"{sys.version_info[0]}.{sys.version_info[1]}")')"; \
		want="$$($(PYTHON) -c 'import sys; print(f"{sys.version_info[0]}.{sys.version_info[1]}")')"; \
		if [ "$$cur" != "$$want" ]; then \
			echo "Recreating $(VENV): Python $$cur -> $$want"; \
			rm -rf "$(VENV)"; \
		fi; \
	fi
	$(PYTHON) -m venv $(VENV)
	$(BIN)/python -m pip install --upgrade pip

install: venv
	$(BIN)/python -m pip install -e .

install-piper: install
	@command -v brew >/dev/null 2>&1 && brew list espeak-ng >/dev/null 2>&1 || brew install espeak-ng
	$(BIN)/python -m pip install -e ".[piper]"
	@mkdir -p models
	@if [ ! -f "$(PIPER_MODEL)" ]; then \
		echo "Downloading Piper model..."; \
		curl -L "$(PIPER_MODEL_URL)" -o "$(PIPER_MODEL)"; \
	fi
	@if [ ! -f "$(PIPER_MODEL).json" ]; then \
		echo "Downloading Piper model config..."; \
		curl -L "$(PIPER_CONFIG_URL)" -o "$(PIPER_MODEL).json"; \
	fi
	@echo "Piper ready: $(PIPER_MODEL)"

install-silero: install
	$(BIN)/python -m pip install -e ".[silero]"
	@echo "Warming up Silero model $(SILERO_MODEL) (first download may take a while)..."
	$(BIN)/python -c "from silero import silero_tts; silero_tts(language='ru', speaker='$(SILERO_MODEL)'); print('Silero ready: $(SILERO_MODEL)')"

install-audiobook: install
	$(BIN)/python -m pip install -e ".[audiobook]"
	@echo "Audiobook cover render ready (pymupdf). ffmpeg still required: brew install ffmpeg"

voices:
	say -v "?"

run:
	@if [ -z "$(PDF)" ]; then \
		echo "Usage: make run PDF=/absolute/or/relative/path/to/file.pdf"; \
		exit 1; \
	fi
	$(BIN)/python $(SCRIPT) "$(PDF)" \
		--out-dir "$(OUT_DIR)" \
		--voice "$(VOICE)" \
		--engine "$(ENGINE)" \
		--piper-model "$(PIPER_MODEL)" \
		--silero-model "$(SILERO_MODEL)" \
		--silero-speaker "$(SILERO_SPEAKER)" \
		--silero-sample-rate "$(SILERO_SAMPLE_RATE)" \
		--mode "$(MODE)" \
		--max-chars "$(MAX_CHARS)" \
		--start-page "$(START_PAGE)" \
		--end-page "$(END_PAGE)" \
		--chapter-pages "$(CHAPTER_PAGES)" \
		--jobs "$(JOBS)" \
		$(if $(filter 1,$(KEEP)),--no-clean-out-dir,) \
		$(if $(CHAPTERS_FILE),--chapters-file "$(CHAPTERS_FILE)",) \
		--patterns-file "$(PATTERNS_FILE)"

run-chapters-say:
	$(MAKE) run-chapters ENGINE=say

run-chapters-piper:
	$(MAKE) run-chapters ENGINE=piper

run-chapters-silero:
	$(MAKE) run-chapters ENGINE=silero

run-chapters:
	@if [ -z "$(PDF)" ]; then \
		echo "Usage: make run-chapters-say|run-chapters-piper|run-chapters-silero|PDF=/path/to/file.pdf"; \
		exit 1; \
	fi
	$(MAKE) run \
		PDF="$(PDF)" \
		OUT_DIR="$(OUT_DIR)" \
		VOICE="$(VOICE)" \
		ENGINE="$(ENGINE)" \
		PIPER_MODEL="$(PIPER_MODEL)" \
		SILERO_MODEL="$(SILERO_MODEL)" \
		SILERO_SPEAKER="$(SILERO_SPEAKER)" \
		SILERO_SAMPLE_RATE="$(SILERO_SAMPLE_RATE)" \
		MAX_CHARS="$(MAX_CHARS)" \
		START_PAGE="$(START_PAGE)" \
		END_PAGE="$(END_PAGE)" \
		MODE=chapters \
		CHAPTER_PAGES="$(CHAPTER_PAGES)" \
		CHAPTERS_FILE="$(CHAPTERS_FILE)" \
		PATTERNS_FILE="$(PATTERNS_FILE)" \
		JOBS="$(JOBS)" \
		KEEP="$(KEEP)"

play:
	@if [ ! -f "$(OUT_DIR)/playlist.m3u" ]; then \
		echo "Playlist not found: $(OUT_DIR)/playlist.m3u"; \
		echo "Run make run or make run-chapters first."; \
		exit 1; \
	fi
	@if [ -d "/Applications/VLC.app" ]; then \
		open -a "VLC" "$(OUT_DIR)/playlist.m3u"; \
	elif command -v vlc >/dev/null 2>&1; then \
		vlc "$(OUT_DIR)/playlist.m3u"; \
	else \
		echo "VLC not found. Install VLC or set PATH for 'vlc' command."; \
		exit 1; \
	fi

listen-say:
	$(MAKE) listen ENGINE=say

listen-piper:
	$(MAKE) listen ENGINE=piper

listen-silero:
	$(MAKE) listen ENGINE=silero

listen:
	@if [ "$(FORCE)" != "1" ] && [ -f "$(OUT_DIR)/manifest.json" ]; then \
		echo "OUT_DIR=$(OUT_DIR) already has audio — opening player without rebuild."; \
		echo "To regenerate (cleans OUT_DIR first): FORCE=1 make PDF=..."; \
		$(MAKE) serve OUT_DIR="$(OUT_DIR)" PORT="$(PORT)"; \
	elif [ -z "$(PDF)" ]; then \
		echo "Usage: make listen-say|listen-piper|listen-silero PDF=/path/to/file.pdf"; \
		echo "       Chapters: bookmarks → {pdf}.chapters.txt → TOC draft (review) → CHAPTERS_FILE/CHAPTER_PAGES"; \
		echo "       FORCE=1 make PDF=...   # rebuild from scratch"; \
		echo "       make draft-chapters PDF=...         # overwrite sidecar from outline/TOC"; \
		echo "       make serve                          # open existing OUT_DIR only"; \
		exit 1; \
	else \
		$(MAKE) run-chapters \
			PDF="$(PDF)" \
			OUT_DIR="$(OUT_DIR)" \
			VOICE="$(VOICE)" \
			ENGINE="$(ENGINE)" \
			PIPER_MODEL="$(PIPER_MODEL)" \
			SILERO_MODEL="$(SILERO_MODEL)" \
			SILERO_SPEAKER="$(SILERO_SPEAKER)" \
			SILERO_SAMPLE_RATE="$(SILERO_SAMPLE_RATE)" \
			MAX_CHARS="$(MAX_CHARS)" \
			START_PAGE="$(START_PAGE)" \
			END_PAGE="$(END_PAGE)" \
			CHAPTER_PAGES="$(CHAPTER_PAGES)" \
			CHAPTERS_FILE="$(CHAPTERS_FILE)" \
			PATTERNS_FILE="$(PATTERNS_FILE)" \
			JOBS="$(JOBS)" \
			KEEP="$(KEEP)"; \
		$(MAKE) serve OUT_DIR="$(OUT_DIR)" PORT="$(PORT)"; \
	fi

serve:
	@if [ ! -f "$(OUT_DIR)/manifest.json" ]; then \
		echo "manifest.json not found in $(OUT_DIR)."; \
		echo "Run make listen PDF=... or make run-chapters first."; \
		exit 1; \
	fi
	@cp "$(PLAYER_SRC)" "$(OUT_DIR)/player.html"
	@cp "$(FAVICON_SRC)" "$(OUT_DIR)/favicon.svg"
	@echo "Open http://127.0.0.1:$(PORT)/player.html"
	@open "http://127.0.0.1:$(PORT)/player.html" || true
	@$(PYTHON) serve_player.py --directory "$(OUT_DIR)" --port "$(PORT)" --bind 127.0.0.1

draft-chapters:
	@if [ -z "$(PDF)" ]; then \
		echo "Usage: make draft-chapters PDF=/path/to/file.pdf"; \
		exit 1; \
	fi
	@if [ -x "$(BIN)/python" ]; then \
		PY="$(BIN)/python"; \
	else \
		PY="$(PYTHON)"; \
	fi; \
	$$PY $(SCRIPT) "$(PDF)" --draft-chapters \
		--start-page "$(START_PAGE)" \
		--end-page "$(END_PAGE)" \
		--patterns-file "$(PATTERNS_FILE)"

pronounce-candidates:
	@if [ -z "$(PDF)" ] && [ -z "$(TEXT)" ] && [ -z "$(LOG)" ]; then \
		echo "Usage: make pronounce-candidates PDF=/path/to/file.pdf"; \
		echo "   or: make pronounce-candidates TEXT=/path/to/pre-pronounce.txt"; \
		echo "   or: make pronounce-candidates LOG=./log [PDF=...|TEXT=...]"; \
		exit 1; \
	fi
	@if [ -n "$(PDF)" ] && [ -n "$(TEXT)" ]; then \
		echo "Use either PDF= or TEXT=, not both"; \
		exit 1; \
	fi
	@if [ -x "$(BIN)/python" ]; then \
		PY="$(BIN)/python"; \
	else \
		PY="$(PYTHON)"; \
	fi; \
	CMD="$$PY $(PRONOUNCE_CANDIDATES) --patterns-file \"$(PATTERNS_FILE)\" --min-count \"$(MIN_COUNT)\""; \
	if [ -n "$(PDF)" ]; then \
		CMD="$$CMD --pdf \"$(PDF)\" --start-page \"$(START_PAGE)\" --end-page \"$(END_PAGE)\""; \
	fi; \
	if [ -n "$(TEXT)" ]; then \
		CMD="$$CMD --text \"$(TEXT)\""; \
	fi; \
	if [ -n "$(LOG)" ]; then \
		CMD="$$CMD --from-log \"$(LOG)\""; \
	fi; \
	eval $$CMD

refresh-web:
	@if [ -x "$(BIN)/python" ]; then \
		$(BIN)/python $(SCRIPT) --refresh-web --out-dir "$(OUT_DIR)"; \
	else \
		$(PYTHON) $(SCRIPT) --refresh-web --out-dir "$(OUT_DIR)"; \
	fi

export-audiobook:
	@command -v ffmpeg >/dev/null 2>&1 || { \
		echo "ffmpeg not found. Install: brew install ffmpeg"; \
		exit 1; \
	}
	@if [ -z "$(COVER)" ] && [ -z "$(PDF)" ]; then \
		echo "Usage: make export-audiobook OUT_DIR=$(OUT_DIR) PDF=/path/to.pdf"; \
		echo "   or: make export-audiobook OUT_DIR=$(OUT_DIR) COVER=/path/to/cover.jpg"; \
		exit 1; \
	fi
	@if [ -x "$(BIN)/python" ]; then \
		PY="$(BIN)/python"; \
	else \
		PY="$(PYTHON)"; \
	fi; \
	$$PY $(SCRIPT) \
		$(if $(PDF),"$(PDF)",) \
		--export-audiobook --out-dir "$(OUT_DIR)" \
		$(if $(COVER),--cover "$(COVER)",) \
		--cover-page "$(COVER_PAGE)" \
		$(if $(BOOK_TITLE),--book-title "$(BOOK_TITLE)",) \
		$(if $(BOOK_AUTHOR),--book-author "$(BOOK_AUTHOR)",) \
		--bitrate "$(BITRATE)"

clean-audio:
	rm -f "$(OUT_DIR)"/*.aiff "$(OUT_DIR)"/*.wav "$(OUT_DIR)"/*.mp3 "$(OUT_DIR)"/*.m4a "$(OUT_DIR)"/*.m3u "$(OUT_DIR)"/*.txt "$(OUT_DIR)"/*.cues.json
	rm -f "$(OUT_DIR)/manifest.json" "$(OUT_DIR)/player.html" "$(OUT_DIR)/favicon.svg"

clean:
	rm -rf $(VENV)
