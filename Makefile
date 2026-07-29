PYTHON ?= python3
VENV ?= .venv
BIN := $(VENV)/bin
SCRIPT := pdf_to_audio.py
PLAYER_SRC := web/player.html
FAVICON_SRC := web/favicon.svg

PDF ?=
OUT_DIR ?= output_audio
VOICE ?= Milena
ENGINE ?= say
PIPER_MODEL ?= models/ru_RU-irina-medium.onnx
MAX_CHARS ?= 5000
START_PAGE ?= 1
END_PAGE ?= 0
MODE ?= chunks
CHAPTER_PAGES ?= 0
CHAPTERS_FILE ?=
JOBS ?= 1
KEEP ?= 0
FORCE ?= 0
PORT ?= 8765

PIPER_MODEL_URL ?= https://huggingface.co/rhasspy/piper-voices/resolve/main/ru/ru_RU/irina/medium/ru_RU-irina-medium.onnx
PIPER_CONFIG_URL ?= https://huggingface.co/rhasspy/piper-voices/resolve/main/ru/ru_RU/irina/medium/ru_RU-irina-medium.onnx.json

.PHONY: help venv install install-piper run run-chapters run-chapters-say run-chapters-piper play listen listen-say listen-piper serve refresh-web voices clean clean-audio

help:
	@echo "Targets:"
	@echo "  make venv             - create virtual environment"
	@echo "  make install          - install project dependencies"
	@echo "  make install-piper    - install Piper + download Russian Irina voice"
	@echo "  make voices           - list available macOS voices"
	@echo "  make run PDF=/path    - convert PDF to audio (ENGINE=$(ENGINE))"
	@echo "  make run-chapters-say PDF=/path   - chapters via macOS say"
	@echo "  make run-chapters-piper PDF=/path - chapters via Piper"
	@echo "  make listen-say PDF=/path         - say chapters + open player"
	@echo "  make listen-piper PDF=/path       - Piper chapters + open player"
	@echo "  make serve            - only open browser player for existing OUT_DIR"
	@echo "  make play             - play OUT_DIR/playlist.m3u in VLC"
	@echo "  make refresh-web      - update player + section markers without re-TTS"
	@echo "  make clean-audio      - remove generated audio in OUT_DIR"
	@echo "  make clean            - remove virtual environment"
	@echo ""
	@echo "Aliases: run-chapters -> run-chapters-say, listen -> listen-say"
	@echo "listen-* skips TTS if OUT_DIR already has audio (use FORCE=1 to rebuild)."
	@echo "KEEP=1 keeps old files during rebuild (default: clean OUT_DIR first)."
	@echo ""
	@echo "Run options:"
	@echo "  OUT_DIR=$(OUT_DIR) VOICE=$(VOICE) PIPER_MODEL=$(PIPER_MODEL)"
	@echo "  MAX_CHARS=$(MAX_CHARS) START_PAGE=$(START_PAGE) END_PAGE=$(END_PAGE)"
	@echo "  CHAPTER_PAGES=$(CHAPTER_PAGES) CHAPTERS_FILE=$(CHAPTERS_FILE) JOBS=$(JOBS) KEEP=$(KEEP) FORCE=$(FORCE) PORT=$(PORT)"

venv:
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
		--mode "$(MODE)" \
		--max-chars "$(MAX_CHARS)" \
		--start-page "$(START_PAGE)" \
		--end-page "$(END_PAGE)" \
		--chapter-pages "$(CHAPTER_PAGES)" \
		--jobs "$(JOBS)" \
		$(if $(filter 1,$(KEEP)),--no-clean-out-dir,) \
		$(if $(CHAPTERS_FILE),--chapters-file "$(CHAPTERS_FILE)",)

run-chapters-say:
	$(MAKE) run-chapters ENGINE=say

run-chapters-piper:
	$(MAKE) run-chapters ENGINE=piper

run-chapters:
	@if [ -z "$(PDF)" ]; then \
		echo "Usage: make run-chapters-say|run-chapters-piper PDF=/path/to/file.pdf"; \
		exit 1; \
	fi
	$(MAKE) run \
		PDF="$(PDF)" \
		OUT_DIR="$(OUT_DIR)" \
		VOICE="$(VOICE)" \
		ENGINE="$(ENGINE)" \
		PIPER_MODEL="$(PIPER_MODEL)" \
		MAX_CHARS="$(MAX_CHARS)" \
		START_PAGE="$(START_PAGE)" \
		END_PAGE="$(END_PAGE)" \
		MODE=chapters \
		CHAPTER_PAGES="$(CHAPTER_PAGES)" \
		CHAPTERS_FILE="$(CHAPTERS_FILE)" \
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

listen:
	@if [ "$(FORCE)" != "1" ] && [ -f "$(OUT_DIR)/manifest.json" ]; then \
		echo "OUT_DIR=$(OUT_DIR) already has audio — opening player without rebuild."; \
		echo "To regenerate (cleans OUT_DIR first): FORCE=1 make listen-piper PDF=..."; \
		$(MAKE) serve OUT_DIR="$(OUT_DIR)" PORT="$(PORT)"; \
	elif [ -z "$(PDF)" ]; then \
		echo "Usage: make listen-say|listen-piper PDF=/path/to/file.pdf [CHAPTERS_FILE=chapters.txt JOBS=4 ...]"; \
		echo "       FORCE=1 make listen-piper PDF=...   # rebuild from scratch"; \
		echo "       make serve                          # open existing OUT_DIR only"; \
		exit 1; \
	else \
		$(MAKE) run-chapters \
			PDF="$(PDF)" \
			OUT_DIR="$(OUT_DIR)" \
			VOICE="$(VOICE)" \
			ENGINE="$(ENGINE)" \
			PIPER_MODEL="$(PIPER_MODEL)" \
			MAX_CHARS="$(MAX_CHARS)" \
			START_PAGE="$(START_PAGE)" \
			END_PAGE="$(END_PAGE)" \
			CHAPTER_PAGES="$(CHAPTER_PAGES)" \
			CHAPTERS_FILE="$(CHAPTERS_FILE)" \
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

refresh-web:
	@if [ -x "$(BIN)/python" ]; then \
		$(BIN)/python $(SCRIPT) --refresh-web --out-dir "$(OUT_DIR)"; \
	else \
		$(PYTHON) $(SCRIPT) --refresh-web --out-dir "$(OUT_DIR)"; \
	fi

clean-audio:
	rm -f "$(OUT_DIR)"/*.aiff "$(OUT_DIR)"/*.wav "$(OUT_DIR)"/*.mp3 "$(OUT_DIR)"/*.m4a "$(OUT_DIR)"/*.m3u "$(OUT_DIR)"/*.txt
	rm -f "$(OUT_DIR)/manifest.json" "$(OUT_DIR)/player.html" "$(OUT_DIR)/favicon.svg"

clean:
	rm -rf $(VENV)
