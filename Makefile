PYTHON ?= /opt/homebrew/bin/python3.11
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
SILERO_MODEL ?= v5_ru
SILERO_SPEAKER ?= xenia
SILERO_SAMPLE_RATE ?= 24000
SILERO_SENTENCE_GAP ?= 0.25
F5_MODEL ?= F5TTS_v1_Base
F5_CKPT ?= hf://Misha24-10/F5-TTS_RUSSIAN/F5TTS_v1_Base_v2/model_last_inference.safetensors
F5_VOCAB ?= hf://Misha24-10/F5-TTS_RUSSIAN/F5TTS_v1_Base/vocab.txt
F5_REF_AUDIO ?= models/f5_ref_ru.wav
F5_REF_TEXT ?=
F5_DEVICE ?=
F5_PRESET ?= fast
ifeq ($(F5_PRESET),quality)
_F5_NFE_DEFAULT := 32
else ifeq ($(F5_PRESET),balanced)
_F5_NFE_DEFAULT := 24
else
_F5_NFE_DEFAULT := 16
endif
F5_NFE_STEP ?= $(_F5_NFE_DEFAULT)
F5_SPEED ?= 1.0
MAX_CHARS ?= 5000
START_PAGE ?= 1
END_PAGE ?= 0
MODE ?= chunks
CHAPTER_PAGES ?= 0
CHAPTERS_FILE ?=
PATTERNS_FILE ?= patterns/default.yml
JOBS ?= 1
KEEP ?= 0
FORCE ?= 0
PORT ?= 8765

PIPER_MODEL_URL ?= https://huggingface.co/rhasspy/piper-voices/resolve/main/ru/ru_RU/irina/medium/ru_RU-irina-medium.onnx
PIPER_CONFIG_URL ?= https://huggingface.co/rhasspy/piper-voices/resolve/main/ru/ru_RU/irina/medium/ru_RU-irina-medium.onnx.json

F5_REF_SAMPLE_TEXT ?= Это образец голоса для клонирования. Модель будет говорить похожим тембром и интонацией.

.PHONY: help venv install install-piper install-silero install-f5tts run run-chapters run-chapters-say run-chapters-piper run-chapters-silero run-chapters-f5tts play listen listen-say listen-piper listen-silero listen-f5tts serve refresh-web voices clean clean-audio

help:
	@echo "Targets:"
	@echo "  make venv             - create virtual environment"
	@echo "  make install          - install project dependencies"
	@echo "  make install-piper    - install Piper + download Russian Irina voice"
	@echo "  make install-silero   - install Silero TTS + torch (downloads model on first run)"
	@echo "  make install-f5tts    - install F5-TTS + Russian ckpt + default ref voice"
	@echo "  make voices           - list available macOS voices"
	@echo "  make run PDF=/path    - convert PDF to audio (ENGINE=$(ENGINE))"
	@echo "  make run-chapters-say PDF=/path    - chapters via macOS say"
	@echo "  make run-chapters-piper PDF=/path  - chapters via Piper"
	@echo "  make run-chapters-silero PDF=/path - chapters via Silero"
	@echo "  make run-chapters-f5tts PDF=/path  - chapters via F5-TTS (needs ref audio)"
	@echo "  make listen-say PDF=/path          - say chapters + open player"
	@echo "  make listen-piper PDF=/path        - Piper chapters + open player"
	@echo "  make listen-silero PDF=/path       - Silero chapters + open player"
	@echo "  make listen-f5tts PDF=/path        - F5-TTS chapters + open player"
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
	@echo "  SILERO_MODEL=$(SILERO_MODEL) SILERO_SPEAKER=$(SILERO_SPEAKER)"
	@echo "  SILERO_SAMPLE_RATE=$(SILERO_SAMPLE_RATE) SILERO_SENTENCE_GAP=$(SILERO_SENTENCE_GAP)"
	@echo "  F5_REF_AUDIO=$(F5_REF_AUDIO) F5_PRESET=$(F5_PRESET) F5_NFE_STEP=$(F5_NFE_STEP) F5_SPEED=$(F5_SPEED)"
	@echo "  F5 presets: fast=16, balanced=24, quality=32 (override with F5_NFE_STEP=...)"
	@echo "  MAX_CHARS=$(MAX_CHARS) START_PAGE=$(START_PAGE) END_PAGE=$(END_PAGE)"
	@echo "  CHAPTER_PAGES=$(CHAPTER_PAGES) CHAPTERS_FILE=$(CHAPTERS_FILE) PATTERNS_FILE=$(PATTERNS_FILE)"
	@echo "  JOBS=$(JOBS) KEEP=$(KEEP) FORCE=$(FORCE) PORT=$(PORT)"

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

install-f5tts: install
	$(BIN)/python -m pip install -e ".[f5tts]"
	@mkdir -p models
	@if [ ! -f "$(F5_REF_AUDIO)" ]; then \
		echo "Creating default F5 reference voice via macOS say ($(VOICE))..."; \
		printf '%s\n' "$(F5_REF_SAMPLE_TEXT)" > "models/f5_ref_ru.txt"; \
		say -v "$(VOICE)" -f "models/f5_ref_ru.txt" -o "models/f5_ref_ru.aiff"; \
		afconvert -f WAVE -d LEI16 "models/f5_ref_ru.aiff" "$(F5_REF_AUDIO)"; \
		rm -f "models/f5_ref_ru.aiff"; \
	fi
	@echo "Warming up F5-TTS Russian checkpoint (first download ~1.3 GB)..."
	$(BIN)/python -c "from cached_path import cached_path; \
print(cached_path('$(F5_CKPT)')); \
print(cached_path('$(F5_VOCAB)')); \
print('F5-TTS ready')"
	@echo "Ref audio: $(F5_REF_AUDIO)"

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
		--silero-sentence-gap "$(SILERO_SENTENCE_GAP)" \
		--f5-model "$(F5_MODEL)" \
		--f5-ckpt "$(F5_CKPT)" \
		--f5-vocab "$(F5_VOCAB)" \
		--f5-ref-audio "$(F5_REF_AUDIO)" \
		$(if $(F5_REF_TEXT),--f5-ref-text "$(F5_REF_TEXT)",) \
		$(if $(F5_DEVICE),--f5-device "$(F5_DEVICE)",) \
		--f5-nfe-step "$(F5_NFE_STEP)" \
		--f5-speed "$(F5_SPEED)" \
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

run-chapters-f5tts:
	$(MAKE) run-chapters ENGINE=f5tts JOBS=1

run-chapters:
	@if [ -z "$(PDF)" ]; then \
		echo "Usage: make run-chapters-say|run-chapters-piper|run-chapters-silero|run-chapters-f5tts PDF=/path/to/file.pdf"; \
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
		SILERO_SENTENCE_GAP="$(SILERO_SENTENCE_GAP)" \
		F5_MODEL="$(F5_MODEL)" \
		F5_CKPT="$(F5_CKPT)" \
		F5_VOCAB="$(F5_VOCAB)" \
		F5_REF_AUDIO="$(F5_REF_AUDIO)" \
		F5_REF_TEXT="$(F5_REF_TEXT)" \
		F5_DEVICE="$(F5_DEVICE)" \
		F5_NFE_STEP="$(F5_NFE_STEP)" \
		F5_SPEED="$(F5_SPEED)" \
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

listen-f5tts:
	$(MAKE) listen ENGINE=f5tts JOBS=1

listen:
	@if [ "$(FORCE)" != "1" ] && [ -f "$(OUT_DIR)/manifest.json" ]; then \
		echo "OUT_DIR=$(OUT_DIR) already has audio — opening player without rebuild."; \
		echo "To regenerate (cleans OUT_DIR first): FORCE=1 make listen-f5tts PDF=..."; \
		$(MAKE) serve OUT_DIR="$(OUT_DIR)" PORT="$(PORT)"; \
	elif [ -z "$(PDF)" ]; then \
		echo "Usage: make listen-say|listen-piper|listen-silero|listen-f5tts PDF=/path/to/file.pdf [CHAPTERS_FILE=chapters.txt ...]"; \
		echo "       FORCE=1 make listen-f5tts PDF=...   # rebuild from scratch"; \
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
			SILERO_SENTENCE_GAP="$(SILERO_SENTENCE_GAP)" \
			F5_MODEL="$(F5_MODEL)" \
			F5_CKPT="$(F5_CKPT)" \
			F5_VOCAB="$(F5_VOCAB)" \
			F5_REF_AUDIO="$(F5_REF_AUDIO)" \
			F5_REF_TEXT="$(F5_REF_TEXT)" \
			F5_DEVICE="$(F5_DEVICE)" \
			F5_NFE_STEP="$(F5_NFE_STEP)" \
			F5_SPEED="$(F5_SPEED)" \
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

refresh-web:
	@if [ -x "$(BIN)/python" ]; then \
		$(BIN)/python $(SCRIPT) --refresh-web --out-dir "$(OUT_DIR)"; \
	else \
		$(PYTHON) $(SCRIPT) --refresh-web --out-dir "$(OUT_DIR)"; \
	fi

clean-audio:
	rm -f "$(OUT_DIR)"/*.aiff "$(OUT_DIR)"/*.wav "$(OUT_DIR)"/*.mp3 "$(OUT_DIR)"/*.m4a "$(OUT_DIR)"/*.m3u "$(OUT_DIR)"/*.txt "$(OUT_DIR)"/*.cues.json
	rm -f "$(OUT_DIR)/manifest.json" "$(OUT_DIR)/player.html" "$(OUT_DIR)/favicon.svg"

clean:
	rm -rf $(VENV)
