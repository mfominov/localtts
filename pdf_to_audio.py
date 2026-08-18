#!/usr/bin/env python3
"""
Convert a PDF document to local audio files on macOS.

Uses:
- pypdf for text extraction
- built-in `say`, Piper, or Silero for offline TTS
"""

from __future__ import annotations

import argparse
import concurrent.futures
import json
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import warnings
import wave
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any

# Silero apply_tts is happier with shorter inputs; we stitch parts together.
SILERO_MAX_CHARS = 900
DEFAULT_SILERO_SENTENCE_GAP = 0.25
DEFAULT_PATTERNS_FILE = pathlib.Path(__file__).resolve().parent / "patterns" / "default.yml"
_silero_lock = threading.Lock()
_silero_models: dict[str, Any] = {}

_REGEX_FLAGS = {
    "IGNORECASE": re.IGNORECASE,
    "MULTILINE": re.MULTILINE,
    "DOTALL": re.DOTALL,
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Convert PDF into offline audio chunks using macOS `say`."
    )
    parser.add_argument(
        "pdf",
        type=pathlib.Path,
        nargs="?",
        default=None,
        help="Path to source PDF (required except --refresh-web / --export-audiobook+--cover)",
    )
    parser.add_argument(
        "--out-dir",
        type=pathlib.Path,
        default=pathlib.Path("output_audio"),
        help="Output directory for audio chunks (default: output_audio)",
    )
    parser.add_argument(
        "--refresh-web",
        action="store_true",
        help="Only refresh player.html and section markers in existing manifest.json",
    )
    parser.add_argument(
        "--export-audiobook",
        action="store_true",
        help="Build OUT_DIR/audiobook.m4b from existing chapters manifest (needs ffmpeg)",
    )
    parser.add_argument(
        "--draft-chapters",
        action="store_true",
        help="Draft {pdf_stem}.chapters.txt from PDF outline/TOC and exit (no TTS)",
    )
    parser.add_argument(
        "--cover",
        type=pathlib.Path,
        default=None,
        help="Cover image for --export-audiobook (skips PDF page render)",
    )
    parser.add_argument(
        "--cover-page",
        type=int,
        default=1,
        help="1-indexed PDF page to render as cover (default: 1)",
    )
    parser.add_argument(
        "--book-title",
        default="",
        help="Audiobook title metadata (default: PDF stem or OUT_DIR name)",
    )
    parser.add_argument(
        "--book-author",
        default="",
        help="Audiobook author/artist metadata (default: LocalTTS)",
    )
    parser.add_argument(
        "--bitrate",
        default="96k",
        help="AAC bitrate for --export-audiobook (default: 96k)",
    )
    parser.add_argument(
        "--voice",
        default="Milena",
        help="macOS `say` voice name (default: Milena). Ignored for Piper/Silero.",
    )
    parser.add_argument(
        "--engine",
        choices=["say", "piper", "silero"],
        default="say",
        help="TTS engine: macOS say (default), Piper, or Silero",
    )
    parser.add_argument(
        "--piper-model",
        type=pathlib.Path,
        default=pathlib.Path("models/ru_RU-irina-medium.onnx"),
        help="Path to Piper .onnx model (default: models/ru_RU-irina-medium.onnx)",
    )
    parser.add_argument(
        "--silero-model",
        default="v5_ru",
        help="Silero model id (default: v5_ru; also v5_5_ru, v4_ru, …)",
    )
    parser.add_argument(
        "--silero-speaker",
        default="xenia",
        help="Silero speaker: aidar, baya, kseniya, xenia, eugene (default: xenia)",
    )
    parser.add_argument(
        "--silero-sample-rate",
        type=int,
        choices=[8000, 24000, 48000],
        default=24000,
        help="Silero sample rate (default: 24000)",
    )
    parser.add_argument(
        "--silero-sentence-gap",
        type=float,
        default=DEFAULT_SILERO_SENTENCE_GAP,
        help=(
            "Silence between Silero sentences in seconds "
            f"(default: {DEFAULT_SILERO_SENTENCE_GAP}; enables measured cues)"
        ),
    )
    parser.add_argument(
        "--mode",
        choices=["chunks", "chapters"],
        default="chunks",
        help="Output mode: chunks or chapter files (default: chunks)",
    )
    parser.add_argument(
        "--max-chars",
        type=int,
        default=5000,
        help="Max chars per audio chunk (default: 5000)",
    )
    parser.add_argument(
        "--start-page",
        type=int,
        default=1,
        help="Start page number, 1-indexed (default: 1)",
    )
    parser.add_argument(
        "--end-page",
        type=int,
        default=0,
        help="End page number, 1-indexed and inclusive (default: 0 = until end)",
    )
    parser.add_argument(
        "--chapter-pages",
        type=int,
        default=0,
        help="Fallback pages per chapter when PDF has no outline (default: 0 = disabled)",
    )
    parser.add_argument(
        "--chapters-file",
        type=pathlib.Path,
        default=None,
        help="Custom chapter mapping file: one line `Title|start-end` (1-indexed, inclusive)",
    )
    parser.add_argument(
        "--patterns-file",
        type=pathlib.Path,
        default=DEFAULT_PATTERNS_FILE,
        help=f"YAML cleaning patterns (default: {DEFAULT_PATTERNS_FILE.name})",
    )
    parser.add_argument(
        "--no-strip-page-artifacts",
        action="store_true",
        help="Disable page cleaning and TOC page skip from patterns file",
    )
    parser.add_argument(
        "--jobs",
        type=int,
        default=1,
        help="Parallel TTS workers (default: 1)",
    )
    parser.set_defaults(clean_out_dir=True)
    parser.add_argument(
        "--no-clean-out-dir",
        action="store_false",
        dest="clean_out_dir",
        help=(
            "Keep existing audio files in OUT_DIR "
            "(default: remove *.aiff, *.wav, *.mp3, *.m3u before run)"
        ),
    )
    return parser.parse_args()


def normalize_text(text: str) -> str:
    text = text.replace("\r", "\n")
    text = re.sub(r"(\w)-\n(\w)", r"\1\2", text)
    text = text.replace("\n", " ")
    text = re.sub(r"\s+", " ", text)
    return text.strip()


@dataclass
class SkipTocConfig:
    enabled: bool = True
    min_lines: int = 5
    keywords: list[str] = field(default_factory=list)
    keyword_line_ratio: float = 0.12
    leader_pattern: str = r"\.{2,}\s*\d{1,4}\s*$"
    leader_line_ratio: float = 0.35
    page_only_pattern: str = r"^(?:стр\.?\s*)?\d{1,4}\s*$"
    page_only_line_ratio: float = 0.35


@dataclass
class CleaningPatterns:
    line_drop: list[re.Pattern[str]] = field(default_factory=list)
    inline_sub: list[tuple[re.Pattern[str], str]] = field(default_factory=list)
    skip_toc: SkipTocConfig = field(default_factory=SkipTocConfig)
    pronounce: dict[str, str] = field(default_factory=dict)
    ai_spoken_as: str = "эй ай"
    ii_spoken_as: str = "и и"
    normalize_numbers: bool = True
    silero_put_yo: bool = True
    silero_put_accent: bool = True
    homographs: dict[str, str] = field(default_factory=dict)


def _compile_regex_flags(flags: Any) -> int:
    value = 0
    for name in flags or []:
        key = str(name).upper()
        if key not in _REGEX_FLAGS:
            raise RuntimeError(f"Unknown regex flag in patterns file: {name}")
        value |= _REGEX_FLAGS[key]
    return value


def load_cleaning_patterns(path: pathlib.Path | None = None) -> CleaningPatterns:
    patterns_path = path or DEFAULT_PATTERNS_FILE
    if not patterns_path.exists():
        raise RuntimeError(f"Cleaning patterns file not found: {patterns_path}")
    try:
        import yaml
    except ImportError as exc:
        raise RuntimeError(
            "PyYAML is required for cleaning patterns. Install with: pip install -e ."
        ) from exc

    raw = yaml.safe_load(patterns_path.read_text(encoding="utf-8")) or {}
    if not isinstance(raw, dict):
        raise RuntimeError(f"Patterns file must be a mapping: {patterns_path}")

    line_drop: list[re.Pattern[str]] = []
    for item in raw.get("line_drop") or []:
        if not isinstance(item, dict) or not item.get("pattern"):
            raise RuntimeError(f"Invalid line_drop entry in {patterns_path}")
        line_drop.append(re.compile(str(item["pattern"]), _compile_regex_flags(item.get("flags"))))

    inline_sub: list[tuple[re.Pattern[str], str]] = []
    for item in raw.get("inline_sub") or []:
        if not isinstance(item, dict) or not item.get("pattern"):
            raise RuntimeError(f"Invalid inline_sub entry in {patterns_path}")
        inline_sub.append(
            (
                re.compile(str(item["pattern"]), _compile_regex_flags(item.get("flags"))),
                str(item.get("repl", "")),
            )
        )

    toc_raw = raw.get("skip_toc") or {}
    if toc_raw and not isinstance(toc_raw, dict):
        raise RuntimeError(f"Invalid skip_toc section in {patterns_path}")
    skip_toc = SkipTocConfig(
        enabled=bool(toc_raw.get("enabled", True)),
        min_lines=int(toc_raw.get("min_lines", 5)),
        keywords=[str(k) for k in (toc_raw.get("keywords") or [])],
        keyword_line_ratio=float(toc_raw.get("keyword_line_ratio", 0.12)),
        leader_pattern=str(toc_raw.get("leader_pattern", r"\.{2,}\s*\d{1,4}\s*$")),
        leader_line_ratio=float(toc_raw.get("leader_line_ratio", 0.35)),
        page_only_pattern=str(toc_raw.get("page_only_pattern", r"^(?:стр\.?\s*)?\d{1,4}\s*$")),
        page_only_line_ratio=float(toc_raw.get("page_only_line_ratio", 0.35)),
    )

    pronounce_raw = raw.get("pronounce") or {}
    if pronounce_raw and not isinstance(pronounce_raw, dict):
        raise RuntimeError(f"Invalid pronounce section in {patterns_path}")
    pronounce = {str(key): str(value) for key, value in pronounce_raw.items() if str(key).strip()}

    ai_spoken_as = str(raw.get("ai_spoken_as") or "эй ай").strip() or "эй ай"
    ii_spoken_as = str(raw.get("ii_spoken_as") or "и и").strip() or "и и"
    normalize_numbers = bool(raw.get("normalize_numbers", True))

    silero_raw = raw.get("silero") or {}
    if silero_raw and not isinstance(silero_raw, dict):
        raise RuntimeError(f"Invalid silero section in {patterns_path}")
    silero_put_yo = bool(silero_raw.get("put_yo", True))
    silero_put_accent = bool(silero_raw.get("put_accent", True))

    homographs_raw = raw.get("homographs") or {}
    if homographs_raw and not isinstance(homographs_raw, dict):
        raise RuntimeError(f"Invalid homographs section in {patterns_path}")
    homographs = {str(key): str(value) for key, value in homographs_raw.items() if str(key).strip()}

    return CleaningPatterns(
        line_drop=line_drop,
        inline_sub=inline_sub,
        skip_toc=skip_toc,
        pronounce=pronounce,
        ai_spoken_as=ai_spoken_as,
        ii_spoken_as=ii_spoken_as,
        normalize_numbers=normalize_numbers,
        silero_put_yo=silero_put_yo,
        silero_put_accent=silero_put_accent,
        homographs=homographs,
    )


def is_toc_page(text: str, patterns: CleaningPatterns) -> bool:
    cfg = patterns.skip_toc
    if not cfg.enabled:
        return False
    lines = [line.strip() for line in text.replace("\r", "\n").split("\n") if line.strip()]
    if len(lines) < cfg.min_lines:
        return False

    keywords = [k.casefold() for k in cfg.keywords if k.strip()]
    keyword_hits = 0
    if keywords:
        keyword_hits = sum(
            1 for line in lines if any(keyword in line.casefold() for keyword in keywords)
        )
    leader_re = re.compile(cfg.leader_pattern)
    leader_hits = sum(1 for line in lines if leader_re.search(line))
    page_only_re = re.compile(cfg.page_only_pattern, re.IGNORECASE)
    page_only_hits = sum(1 for line in lines if page_only_re.match(line))
    keyword_ratio = keyword_hits / float(len(lines))
    leader_ratio = leader_hits / float(len(lines))
    page_only_ratio = page_only_hits / float(len(lines))

    if leader_ratio >= cfg.leader_line_ratio:
        return True
    if page_only_ratio >= cfg.page_only_line_ratio:
        return True
    if keyword_ratio >= cfg.keyword_line_ratio:
        return True
    # Keyword header + moderate leaders (typical TOC)
    if keyword_hits >= 1 and leader_ratio >= max(cfg.leader_line_ratio * 0.45, 0.15):
        return True
    # Keyword header + stacked page column (title\\npage)
    return keyword_hits >= 1 and page_only_ratio >= max(cfg.page_only_line_ratio * 0.45, 0.15)


def strip_page_artifacts(text: str, patterns: CleaningPatterns | None = None) -> str:
    cfg = patterns or load_cleaning_patterns()
    lines = [line.strip() for line in text.replace("\r", "\n").split("\n")]
    nonempty = [line for line in lines if line]
    if not nonempty:
        return ""

    def looks_like_artifact(line: str) -> bool:
        return any(pattern.search(line) for pattern in cfg.line_drop)

    filtered = [line for line in nonempty if not looks_like_artifact(line)]
    if filtered:
        nonempty = filtered

    while nonempty and looks_like_artifact(nonempty[0]):
        nonempty.pop(0)
    while nonempty and looks_like_artifact(nonempty[-1]):
        nonempty.pop()

    return "\n".join(nonempty)


def strip_inline_page_artifacts(text: str, patterns: CleaningPatterns | None = None) -> str:
    cfg = patterns or load_cleaning_patterns()
    for pattern, repl in cfg.inline_sub:
        text = pattern.sub(repl, text)
    return re.sub(r"\s+", " ", text).strip()


def apply_pronunciation_fixes(text: str, ai_spoken_as: str, ii_spoken_as: str) -> str:
    # Replace standalone tokens with robust boundaries so forms like
    # `ИИ-помощник`, `ИИ —`, `AI/ML`, `AI.` are handled too.
    token_boundary = r"[A-Za-zА-Яа-яЁё0-9]"
    text = re.sub(
        rf"(?<!{token_boundary})AI(?!{token_boundary})",
        ai_spoken_as,
        text,
    )
    text = re.sub(
        rf"(?<!{token_boundary})ИИ(?!{token_boundary})",
        ii_spoken_as,
        text,
    )
    # `12+ мес`, `6 мес.`, `3-6 мес` -> "... месяцев"
    text = re.sub(
        r"(?<=\d)\s*\+?\s*мес\.?(?![A-Za-zА-Яа-яЁё0-9])",
        " месяцев",
        text,
        flags=re.IGNORECASE,
    )
    return text


SECTION_REFERENCE = re.compile(r"§\s*(\d+(?:\.\d+)*)")


def expand_section_references(text: str) -> str:
    def repl(match: re.Match[str]) -> str:
        parts = match.group(1).split(".")
        numbering = " точка ".join(parts)
        return f"в разделе {numbering}"

    return SECTION_REFERENCE.sub(repl, text)


SPOKEN_SECTION_REF = re.compile(
    r"в разделе\s+(\d+(?:\s+точка\s+\d+)+)",
    flags=re.IGNORECASE,
)

_SPOKEN_SECTION_DIGITS = re.compile(
    r"(в разделе\s+)(\d+(?:\s+точка\s+\d+)+)",
    flags=re.IGNORECASE,
)

_RU_ONES = (
    "ноль",
    "один",
    "два",
    "три",
    "четыре",
    "пять",
    "шесть",
    "семь",
    "восемь",
    "девять",
)
_RU_TEENS = (
    "десять",
    "одиннадцать",
    "двенадцать",
    "тринадцать",
    "четырнадцать",
    "пятнадцать",
    "шестнадцать",
    "семнадцать",
    "восемнадцать",
    "девятнадцать",
)
_RU_TENS = (
    "",
    "",
    "двадцать",
    "тридцать",
    "сорок",
    "пятьдесят",
    "шестьдесят",
    "семьдесят",
    "восемьдесят",
    "девяносто",
)
_RU_HUNDREDS = (
    "",
    "сто",
    "двести",
    "триста",
    "четыреста",
    "пятьсот",
    "шестьсот",
    "семьсот",
    "восемьсот",
    "девятьсот",
)


def int_to_ru_words(value: int) -> str:
    """Convert 0..999 to Russian words (for section numbers in TTS)."""
    if value < 0 or value > 999:
        return str(value)
    if value < 10:
        return _RU_ONES[value]
    if value < 20:
        return _RU_TEENS[value - 10]
    if value < 100:
        tens, ones = divmod(value, 10)
        if ones == 0:
            return _RU_TENS[tens]
        return f"{_RU_TENS[tens]} {_RU_ONES[ones]}"
    hundreds, rem = divmod(value, 100)
    if rem == 0:
        return _RU_HUNDREDS[hundreds]
    return f"{_RU_HUNDREDS[hundreds]} {int_to_ru_words(rem)}"


def expand_section_ref_digits_to_words(text: str) -> str:
    """Turn `в разделе 3 точка 2` into `в разделе три точка два` for TTS."""

    def repl(match: re.Match[str]) -> str:
        prefix = match.group(1)
        parts = re.split(r"\s+точка\s+", match.group(2), flags=re.IGNORECASE)
        words = [int_to_ru_words(int(part)) for part in parts]
        return prefix + " точка ".join(words)

    return _SPOKEN_SECTION_DIGITS.sub(repl, text)


def apply_pronounce_map(text: str, pronounce: dict[str, str] | None) -> str:
    """Replace whole tokens from patterns `pronounce:` map (longest first)."""
    if not pronounce:
        return text
    result = text
    for token, spoken in sorted(pronounce.items(), key=lambda item: len(item[0]), reverse=True):
        if not token.strip() or not spoken.strip():
            continue
        pattern = re.compile(
            rf"(?<![A-Za-zА-Яа-яЁё0-9]){re.escape(token)}(?![A-Za-zА-Яа-яЁё0-9])",
            flags=re.IGNORECASE,
        )
        result = pattern.sub(spoken, result)
    return result


def prepare_tts_spoken_text(
    text: str,
    pronounce: dict[str, str] | None = None,
    *,
    normalize_numbers: bool = True,
    homographs: dict[str, str] | None = None,
) -> str:
    """TTS-only transforms; do not use for UI/cues storage."""
    from normalize_numbers import normalize_numbers_for_speech

    spoken = expand_section_references(text)
    spoken = expand_section_ref_digits_to_words(spoken)
    spoken = normalize_numbers_for_speech(spoken, enabled=normalize_numbers)
    spoken = apply_pronounce_map(spoken, pronounce)
    # Homograph +stress markers are Silero-only; callers pass homographs only for silero.
    spoken = apply_pronounce_map(spoken, homographs)
    return spoken


def section_refs_for_display(text: str) -> str:
    """Keep spoken wording for TTS, but show §N.M / AI / ИИ in the reader UI."""

    def repl(match: re.Match[str]) -> str:
        numbers = re.findall(r"\d+", match.group(1))
        return f"§{'.'.join(numbers)}"

    text = SPOKEN_SECTION_REF.sub(repl, text)
    # Spoken "эй ай" / "эй-ай" back to AI, including identifiers like эй ай_saved_hours.
    text = re.sub(r"эй[\s\-–—]*ай", "AI", text, flags=re.IGNORECASE)
    text = _restore_ii_tokens(text)
    return text


def _restore_ii_tokens(text: str) -> str:
    # Hyphenated compounds first: "и и-агент" -> "ИИ-агент"
    text = re.sub(r"и\s+и(?=-)", "ИИ", text)
    boundary = r"[A-Za-zА-Яа-яЁё0-9-]"
    pattern = re.compile(rf"(?<!{boundary})и\s+и(?!{boundary})")
    # Replace rightmost matches so "и и и" becomes "и ИИ", not "ИИ и".
    while True:
        matches = []
        pos = 0
        while True:
            match = pattern.search(text, pos)
            if not match:
                break
            matches.append(match)
            pos = match.start() + 1
        if not matches:
            break
        match = matches[-1]
        text = text[: match.start()] + "ИИ" + text[match.end() :]
    return text


def stylize_quoted_speech(text: str) -> str:
    """
    Turn quotes into spoken dialogue cues for macOS `say`:
    short pause before quote, slight pitch up, pause after.
    Removes quote glyphs so they are not misread (e.g. as backslash).
    """

    def repl(match: re.Match[str]) -> str:
        inner = re.sub(r"\s+", " ", match.group(1)).strip()
        if not inner or len(inner) > 280:
            return f" {inner} "
        return f" [[slnc 280]] [[pbas +1]] {inner} [[pbas +0]] [[slnc 180]] "

    # Prefer paired guillemets / curly quotes first (safer than bare \).
    text = re.sub(r"«\s*(.+?)\s*»", repl, text, flags=re.DOTALL)
    text = re.sub(r"“\s*(.+?)\s*”", repl, text, flags=re.DOTALL)
    text = re.sub(r'"\s*([^"]{1,280})\s*"', repl, text)
    # Leftover quote-like backslashes from bad PDF extraction.
    text = re.sub(r"\\\s*([^\\]{1,280})\s*\\", repl, text)
    text = text.replace("«", " ").replace("»", " ")
    text = text.replace("“", " ").replace("”", " ")
    return re.sub(r"[ \t]{2,}", " ", text).strip()


def chunk_text(text: str, max_chars: int) -> list[str]:
    if len(text) <= max_chars:
        return [text]

    chunks: list[str] = []
    cursor = 0
    length = len(text)

    while cursor < length:
        end = min(cursor + max_chars, length)
        if end < length:
            dot = text.rfind(". ", cursor, end)
            comma = text.rfind(", ", cursor, end)
            split_at = max(dot, comma)
            if split_at > cursor + int(max_chars * 0.6):
                end = split_at + 1
        part = text[cursor:end].strip()
        if part:
            chunks.append(part)
        cursor = end
    return chunks


def get_pdf_reader(pdf_path: pathlib.Path):
    try:
        from pypdf import PdfReader
    except ImportError as exc:
        raise RuntimeError(
            "Dependency missing: pypdf. Install with: python3 -m pip install pypdf"
        ) from exc
    return PdfReader(str(pdf_path))


def resolve_page_range(total_pages: int, start_page: int, end_page: int) -> tuple[int, int]:
    start_idx = max(0, start_page - 1)
    end_idx = total_pages if end_page <= 0 else min(total_pages, end_page)

    if start_idx >= end_idx:
        raise RuntimeError(
            f"Invalid page range: start={start_page}, end={end_page}, total_pages={total_pages}"
        )
    return start_idx, end_idx


def extract_pages_text(
    reader: Any,
    start_idx: int,
    end_idx: int,
    strip_artifacts: bool,
    stylize_quotes: bool = True,
    patterns: CleaningPatterns | None = None,
    speech_patterns: CleaningPatterns | None = None,
) -> list[str]:
    cleaning = patterns
    if strip_artifacts and cleaning is None:
        cleaning = load_cleaning_patterns()
    speech = speech_patterns or cleaning or CleaningPatterns()

    pages_text: list[str] = []
    skipped_toc = 0
    for page_idx in range(start_idx, end_idx):
        text = reader.pages[page_idx].extract_text() or ""
        if strip_artifacts and cleaning is not None:
            if is_toc_page(text, cleaning):
                pages_text.append("")
                skipped_toc += 1
                continue
            text = strip_page_artifacts(text, cleaning)
        text = apply_pronunciation_fixes(
            text,
            ai_spoken_as=speech.ai_spoken_as,
            ii_spoken_as=speech.ii_spoken_as,
        )
        text = expand_section_references(text)
        normalized = normalize_text(text)
        if strip_artifacts and cleaning is not None:
            normalized = strip_inline_page_artifacts(normalized, cleaning)
        if stylize_quotes:
            normalized = stylize_quoted_speech(normalized)
        pages_text.append(normalized)
    if skipped_toc:
        print(f"Skipped {skipped_toc} TOC-like page(s) via cleaning patterns", flush=True)
    return pages_text


def sanitize_filename(value: str) -> str:
    cleaned = re.sub(r"[^\w\-. ]+", "", value, flags=re.UNICODE).strip()
    cleaned = re.sub(r"\s+", "_", cleaned)
    return cleaned[:80] or "chapter"


def flatten_outline(items: Sequence[Any], out: list[Any]) -> None:
    for item in items:
        if isinstance(item, list):
            flatten_outline(item, out)
        else:
            out.append(item)


def chapter_ranges_from_outline(
    reader: Any, start_idx: int, end_idx: int
) -> list[tuple[str, int, int]]:
    outline_items = []
    try:
        raw_outline = reader.outline or []
        flatten_outline(raw_outline, outline_items)
    except Exception:
        return []

    starts: list[tuple[str, int]] = []
    for item in outline_items:
        if not hasattr(item, "title"):
            continue
        try:
            page_number = int(reader.get_destination_page_number(item))
        except Exception:
            continue
        if page_number < start_idx or page_number >= end_idx:
            continue
        title = str(getattr(item, "title", "")).strip()
        if title:
            starts.append((title, page_number))

    # Deduplicate by page; keep the first title encountered for each page.
    dedup: list[tuple[str, int]] = []
    seen_pages = set()
    for title, page in sorted(starts, key=lambda x: x[1]):
        if page in seen_pages:
            continue
        seen_pages.add(page)
        dedup.append((title, page))

    if not dedup:
        return []

    ranges: list[tuple[str, int, int]] = []
    for idx, (title, start_page) in enumerate(dedup):
        end_page = dedup[idx + 1][1] if idx + 1 < len(dedup) else end_idx
        if start_page < end_page:
            ranges.append((title, start_page, end_page))
    return ranges


def chapter_ranges_by_fixed_size(
    start_idx: int, end_idx: int, chapter_pages: int
) -> list[tuple[str, int, int]]:
    if chapter_pages <= 0:
        return []
    ranges: list[tuple[str, int, int]] = []
    chapter_number = 1
    cursor = start_idx
    while cursor < end_idx:
        end_page = min(end_idx, cursor + chapter_pages)
        ranges.append((f"Chapter {chapter_number}", cursor, end_page))
        chapter_number += 1
        cursor = end_page
    return ranges


def chapter_ranges_from_file(
    chapters_file: pathlib.Path, total_pages: int, start_idx: int, end_idx: int
) -> list[tuple[str, int, int]]:
    if not chapters_file.exists():
        raise RuntimeError(f"Chapters file not found: {chapters_file}")

    ranges: list[tuple[str, int, int]] = []
    lines = chapters_file.read_text(encoding="utf-8").splitlines()
    for line_number, raw_line in enumerate(lines, start=1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue

        if "|" not in line:
            raise RuntimeError(
                f"Invalid chapters file format at line {line_number}: "
                "expected `Title|start-end` or `Title|page`"
            )

        title_part, pages_part = line.split("|", 1)
        title = title_part.strip()
        pages_part = pages_part.strip()
        if not title:
            raise RuntimeError(f"Invalid empty chapter title at line {line_number}")

        try:
            if "-" in pages_part:
                start_part, end_part = pages_part.split("-", 1)
                start_page = int(start_part.strip())
                end_page_inclusive = int(end_part.strip())
            else:
                # Single page: `ЗАКЛЮЧЕНИЕ|132`
                start_page = int(pages_part)
                end_page_inclusive = start_page
        except ValueError as exc:
            raise RuntimeError(
                f"Invalid page numbers at line {line_number}: `{pages_part}`"
            ) from exc

        if start_page < 1 or end_page_inclusive < start_page:
            raise RuntimeError(
                f"Invalid page range at line {line_number}: "
                f"start={start_page}, end={end_page_inclusive}"
            )
        if end_page_inclusive > total_pages:
            raise RuntimeError(
                f"Page out of bounds at line {line_number}: "
                f"end={end_page_inclusive}, total_pages={total_pages}"
            )

        start_zero = start_page - 1
        end_zero_exclusive = end_page_inclusive

        # Respect the selected global page window.
        clipped_start = max(start_zero, start_idx)
        clipped_end = min(end_zero_exclusive, end_idx)
        if clipped_start < clipped_end:
            ranges.append((title, clipped_start, clipped_end))

    if not ranges:
        return []

    ranges.sort(key=lambda item: item[1])
    for idx in range(1, len(ranges)):
        prev = ranges[idx - 1]
        current = ranges[idx]
        if current[1] < prev[2]:
            raise RuntimeError(f"Overlapping chapter ranges: `{prev[0]}` and `{current[0]}`")
    return ranges


def default_chapters_sidecar_path(pdf: pathlib.Path) -> pathlib.Path:
    """Path next to PDF: doc.pdf → doc.chapters.txt."""
    return pdf.with_name(f"{pdf.stem}.chapters.txt")


_TOC_LEADER_RE = re.compile(
    r"^(?P<title>.+?)\s*[\.·•…]{2,}\s*(?:стр\.?\s*)?(?P<page>\d{1,4})\s*$",
    re.IGNORECASE,
)
_TOC_TRAILING_PAGE_RE = re.compile(
    r"^(?P<title>.+?)\s+(?:стр\.?\s*)?(?P<page>\d{1,4})\s*$",
    re.IGNORECASE,
)
_TOC_PAGE_ONLY_RE = re.compile(r"^(?:стр\.?\s*)?(?P<page>\d{1,4})\s*$", re.IGNORECASE)
_TOC_HEADER_TITLES = frozenset(
    {
        "содержание",
        "оглавление",
        "список таблиц",
        "список рисунков",
        "table of contents",
        "contents",
    }
)
_TOP_LEVEL_TOC_RE = re.compile(
    r"^(?:ЧАСТЬ\s+\d+|РЕЗЮМЕ\b|ЗАКЛЮЧЕНИЕ\b|ПРИЛОЖЕНИЕ\b|ГЛОССАРИЙ\b)",
    re.IGNORECASE,
)


def normalize_toc_title(title: str) -> str:
    title = title.replace("…", " ")
    title = re.sub(r"[\.·•]{2,}", " ", title)
    title = re.sub(r"\s+", " ", title).strip(" .-–—\t")
    return title


def is_top_level_toc_title(title: str) -> bool:
    """True for major chapter headings (ЧАСТЬ / РЕЗЮМЕ / ALL CAPS), not 1.1 subsections."""
    text = normalize_toc_title(title)
    if not text or text.casefold() in _TOC_HEADER_TITLES:
        return False
    if re.match(r"^\d+\.\d+", text):
        return False
    if _TOP_LEVEL_TOC_RE.match(text):
        return True
    letters = [char for char in text if char.isalpha()]
    return len(letters) >= 4 and all(char.isupper() for char in letters)


def toc_entry_rank(title: str) -> int:
    return 2 if is_top_level_toc_title(title) else 1


def select_chapter_toc_entries(
    entries: Sequence[tuple[str, int]],
) -> list[tuple[str, int]]:
    """Keep major TOC headings for chapter splits; fall back if too few."""
    top = [(title, page) for title, page in entries if is_top_level_toc_title(title)]
    return top if len(top) >= 2 else list(entries)


def _upsert_toc_entry(
    by_page: dict[int, tuple[str, int]],
    title: str,
    page: int,
) -> None:
    rank = toc_entry_rank(title)
    previous = by_page.get(page)
    if previous is None or rank > previous[1]:
        by_page[page] = (title, rank)


def _is_toc_year_page(page: int) -> bool:
    """Years in titles (2026, 2030) must not become page numbers."""
    return 1900 <= page <= 2099


def parse_toc_entry_line(line: str) -> tuple[str, int] | None:
    """Parse one TOC line into (title, 1-based page) or None."""
    raw = re.sub(r"[ \t]+", " ", (line or "").strip())
    if not raw or raw.startswith("#"):
        return None
    match = _TOC_LEADER_RE.match(raw) or _TOC_TRAILING_PAGE_RE.match(raw)
    if match is None:
        return None
    title = normalize_toc_title(match.group("title"))
    page = int(match.group("page"))
    if page < 1 or _is_toc_year_page(page) or len(title) < 2:
        return None
    if re.fullmatch(r"\d+", title):
        return None
    # Avoid matching prose sentences that happen to end with a year-like number.
    if len(title) > 120:
        return None
    if title.casefold() in _TOC_HEADER_TITLES:
        return None
    return title, page


def parse_toc_page_only_line(line: str) -> int | None:
    match = _TOC_PAGE_ONLY_RE.match((line or "").strip())
    if match is None:
        return None
    page = int(match.group("page"))
    if page < 1 or _is_toc_year_page(page):
        return None
    return page


def parse_toc_entries(text: str) -> list[tuple[str, int]]:
    """Parse TOC text: same-line leaders, or stacked title(s) then page number(s)."""
    lines = [re.sub(r"[ \t]+", " ", line).strip() for line in (text or "").splitlines()]
    lines = [line for line in lines if line and not line.startswith("#")]
    counts: dict[str, int] = {}
    for line in lines:
        counts[line] = counts.get(line, 0) + 1
    # Repeated running headers/footers only — page numbers often repeat across entries.
    noise = {
        line
        for line, count in counts.items()
        if count >= 2 and parse_toc_page_only_line(line) is None
    }

    by_page: dict[int, tuple[str, int]] = {}
    idx = 0
    while idx < len(lines):
        line = lines[idx]
        if line in noise:
            idx += 1
            continue

        single = parse_toc_entry_line(line)
        if single is not None:
            title, page = single
            _upsert_toc_entry(by_page, title, page)
            idx += 1
            continue

        if parse_toc_page_only_line(line) is not None:
            idx += 1
            continue

        title_parts: list[str] = []
        while idx < len(lines):
            cur = lines[idx]
            if cur in noise:
                idx += 1
                continue
            if parse_toc_entry_line(cur) is not None:
                break
            page = parse_toc_page_only_line(cur)
            if page is not None:
                # Folio + TOC page on consecutive lines: take the last. Do not
                # skip noise here — that would glue the next section's folio.
                idx += 1
                while idx < len(lines):
                    nxt_page = parse_toc_page_only_line(lines[idx])
                    if nxt_page is None:
                        break
                    page = nxt_page
                    idx += 1
                title = normalize_toc_title(" ".join(title_parts))
                if (
                    title
                    and len(title) >= 2
                    and title.casefold() not in _TOC_HEADER_TITLES
                    and not re.fullmatch(r"\d+", title)
                ):
                    _upsert_toc_entry(by_page, title, page)
                title_parts = []
                break
            if cur.casefold() in _TOC_HEADER_TITLES and not title_parts:
                idx += 1
                continue
            title_parts.append(cur)
            idx += 1
        else:
            break
        if title_parts and idx >= len(lines):
            break

    return [(title, page) for page, (title, _rank) in sorted(by_page.items())]


def toc_entries_to_ranges(
    entries: Sequence[tuple[str, int]],
    *,
    total_pages: int,
    start_idx: int,
    end_idx: int,
) -> list[tuple[str, int, int]]:
    """Convert 1-based TOC starts to clipped half-open chapter ranges."""
    if not entries:
        return []
    starts: list[tuple[str, int]] = []
    for title, page_1based in entries:
        if page_1based < 1 or page_1based > total_pages:
            continue
        page0 = page_1based - 1
        if page0 < start_idx or page0 >= end_idx:
            continue
        starts.append((title, page0))
    if not starts:
        return []

    ranges: list[tuple[str, int, int]] = []
    for idx, (title, start_page) in enumerate(starts):
        end_page = starts[idx + 1][1] if idx + 1 < len(starts) else end_idx
        clipped_start = max(start_page, start_idx)
        clipped_end = min(end_page, end_idx)
        if clipped_start < clipped_end:
            ranges.append((title, clipped_start, clipped_end))
    return ranges


def collect_toc_text(
    reader: Any,
    *,
    start_idx: int,
    end_idx: int,
    patterns: CleaningPatterns,
    fallback_pages: int = 8,
) -> tuple[str, str]:
    """Return (text, source_label). Prefer is_toc_page pages; else first N pages."""
    toc_chunks: list[str] = []
    for page_idx in range(start_idx, end_idx):
        raw = reader.pages[page_idx].extract_text() or ""
        if is_toc_page(raw, patterns):
            toc_chunks.append(raw)
    if toc_chunks:
        return "\n".join(toc_chunks), "toc-pages"
    limit = min(end_idx, start_idx + max(1, fallback_pages))
    fallback = [reader.pages[page_idx].extract_text() or "" for page_idx in range(start_idx, limit)]
    return "\n".join(fallback), f"first-{limit - start_idx}-pages"


def write_chapters_file(
    path: pathlib.Path,
    ranges: Sequence[tuple[str, int, int]],
    *,
    header_note: str = "Auto-drafted chapters. Review before listen.",
) -> pathlib.Path:
    lines = [f"# {header_note}", "# Title|start-end"]
    for title, start0, end0 in ranges:
        # end0 is exclusive → inclusive 1-based end
        lines.append(f"{title}|{start0 + 1}-{end0}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def draft_chapter_ranges_from_toc(
    reader: Any,
    *,
    total_pages: int,
    start_idx: int,
    end_idx: int,
    patterns: CleaningPatterns,
) -> list[tuple[str, int, int]]:
    text, _source = collect_toc_text(
        reader,
        start_idx=start_idx,
        end_idx=end_idx,
        patterns=patterns,
    )
    entries = select_chapter_toc_entries(parse_toc_entries(text))
    return toc_entries_to_ranges(
        entries,
        total_pages=total_pages,
        start_idx=start_idx,
        end_idx=end_idx,
    )


def resolve_chapter_ranges(
    reader: Any,
    *,
    pdf: pathlib.Path,
    total_pages: int,
    start_idx: int,
    end_idx: int,
    chapters_file: pathlib.Path | None,
    chapter_pages: int,
    patterns: CleaningPatterns | None,
    draft_chapters: bool = False,
) -> tuple[list[tuple[str, int, int]], pathlib.Path | None, str]:
    """Resolve chapter ranges.

    Returns (ranges, sidecar_path_or_none, source_label).
    If TOC draft was written and TTS should stop, ranges is empty and
    source_label starts with ``drafted:``.
    """
    sidecar = default_chapters_sidecar_path(pdf)

    if draft_chapters:
        if patterns is None:
            raise RuntimeError("Cleaning patterns are required to draft chapters from TOC")
        outline = chapter_ranges_from_outline(reader, start_idx, end_idx)
        if outline:
            write_chapters_file(
                sidecar,
                outline,
                header_note="Drafted from PDF outline (bookmarks). Review before listen.",
            )
            return [], sidecar, f"drafted:outline:{sidecar}"
        ranges = draft_chapter_ranges_from_toc(
            reader,
            total_pages=total_pages,
            start_idx=start_idx,
            end_idx=end_idx,
            patterns=patterns,
        )
        if not ranges:
            raise RuntimeError(
                "Could not draft chapters from PDF outline or TOC text. "
                "Pass --chapters-file or --chapter-pages N."
            )
        write_chapters_file(sidecar, ranges)
        return [], sidecar, f"drafted:toc:{sidecar}"

    if chapters_file is not None:
        ranges = chapter_ranges_from_file(chapters_file, total_pages, start_idx, end_idx)
        if ranges:
            return ranges, None, f"file:{chapters_file}"

    outline = chapter_ranges_from_outline(reader, start_idx, end_idx)
    if outline:
        return outline, None, "outline"

    if sidecar.exists():
        ranges = chapter_ranges_from_file(sidecar, total_pages, start_idx, end_idx)
        if ranges:
            return ranges, sidecar, f"sidecar:{sidecar}"

    if chapter_pages > 0:
        ranges = chapter_ranges_by_fixed_size(start_idx, end_idx, chapter_pages)
        if ranges:
            return ranges, None, f"fixed:{chapter_pages}"

    if patterns is None:
        raise RuntimeError(
            "No chapters found (no outline/sidecar). "
            "Install cleaning patterns or pass --chapters-file / --chapter-pages N."
        )
    ranges = draft_chapter_ranges_from_toc(
        reader,
        total_pages=total_pages,
        start_idx=start_idx,
        end_idx=end_idx,
        patterns=patterns,
    )
    if not ranges:
        raise RuntimeError(
            "No chapters found. PDF has no bookmarks/usable TOC. "
            f"Create {sidecar.name} manually, or pass --chapters-file / --chapter-pages N."
        )
    write_chapters_file(sidecar, ranges)
    return [], sidecar, f"drafted:toc:{sidecar}"


def clean_output_dir(output_dir: pathlib.Path) -> int:
    patterns = ("*.aiff", "*.wav", "*.mp3", "*.m4a", "*.m3u", "*.cues.json", "manifest.json")
    removed = 0
    for pattern in patterns:
        for path in output_dir.glob(pattern):
            path.unlink()
            removed += 1
    return removed


def cues_sidecar_path(aiff_file: pathlib.Path) -> pathlib.Path:
    return aiff_file.with_suffix(".cues.json")


def write_cues_sidecar(
    aiff_file: pathlib.Path,
    cues: list[dict[str, Any]],
    *,
    timing: str = "measured",
) -> pathlib.Path:
    path = cues_sidecar_path(aiff_file)
    path.write_text(
        json.dumps({"timing": timing, "cues": cues}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return path


def load_cues_sidecar(aiff_file: pathlib.Path) -> tuple[str, list[dict[str, Any]]] | None:
    path = cues_sidecar_path(aiff_file)
    if not path.exists():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    cues = data.get("cues") or []
    if not isinstance(cues, list) or not cues:
        return None
    timing = str(data.get("timing") or "measured")
    return timing, cues


def strip_speech_markup(text: str) -> str:
    text = re.sub(r"\[\[.*?\]\]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def split_sentences(text: str) -> list[str]:
    text = strip_speech_markup(text)
    if not text:
        return []
    parts = re.split(r"(?<=[.!?…])\s+", text)
    return [part.strip() for part in parts if part.strip()]


def audio_duration_seconds(audio_file: pathlib.Path) -> float:
    result = subprocess.run(
        ["afinfo", str(audio_file)],
        check=True,
        capture_output=True,
        text=True,
    )
    match = re.search(r"estimated duration:\s*([0-9.]+)\s*sec", result.stdout)
    if not match:
        raise RuntimeError(f"Could not read duration for {audio_file}")
    return float(match.group(1))


def convert_aiff_to_wav(aiff_file: pathlib.Path) -> pathlib.Path:
    wav_file = aiff_file.with_suffix(".wav")
    if wav_file.exists() and wav_file.stat().st_size > 0:
        return wav_file
    subprocess.run(
        ["afconvert", "-f", "WAVE", "-d", "LEI16", str(aiff_file), str(wav_file)],
        check=True,
    )
    return wav_file


def speech_weight(text: str) -> float:
    """Estimate relative speaking time (not pure character count).

    Latin tokens, digits and abbreviations are slower for RU voices; punctuation
    adds pauses. Without this, highlight drifts ahead of Piper/say audio.
    """
    weight = 0.0
    for char in text:
        if "A" <= char <= "Z" or "a" <= char <= "z":
            weight += 1.65
        elif char.isalpha():
            weight += 1.0
        elif char.isdigit():
            weight += 1.85
        elif char in ".!?…":
            weight += 10.0
        elif char in ",;:—–":
            weight += 3.5
        elif char.isspace():
            weight += 0.12
        else:
            weight += 0.55

    weight += 5.0 * len(re.findall(r"\b[A-Z]{2,}\b", text))
    weight += 2.5 * len(re.findall(r"\d+(?:[.,]\d+)+", text))
    weight += 1.8 * len(re.findall(r"[/\\|]", text))
    return max(weight, 1.0)


def build_sentence_cues(text: str, duration: float) -> list[dict[str, Any]]:
    sentences = split_sentences(text)
    if not sentences:
        return [{"start": 0.0, "end": duration, "text": strip_speech_markup(text)}]

    return retime_cues(
        [{"text": sentence} for sentence in sentences],
        duration,
    )


def retime_cues(cues: list[dict[str, Any]], duration: float) -> list[dict[str, Any]]:
    if not cues:
        return []
    if duration <= 0:
        return [
            {
                "start": float(cue.get("start") or 0.0),
                "end": float(cue.get("end") or 0.0),
                "text": str(cue.get("text", "")),
            }
            for cue in cues
        ]

    weights = [speech_weight(str(cue.get("text", ""))) for cue in cues]
    total_weight = float(sum(weights)) or 1.0
    timed: list[dict[str, Any]] = []
    cursor = 0.0
    for idx, (cue, weight) in enumerate(zip(cues, weights, strict=False)):
        end = duration if idx == len(cues) - 1 else cursor + duration * (weight / total_weight)
        timed.append(
            {
                "start": round(cursor, 3),
                "end": round(end, 3),
                "text": str(cue.get("text", "")),
            }
        )
        cursor = end
    return timed


SECTION_AT_START = re.compile(
    r"^(?:[\[\(\«\"']*)(?P<num>\d+(?:\.\d+){1,3})\.?\s+(?P<title>[A-ZА-ЯЁA-Za-z].{0,160})"
)


def _short_section_title(number: str, title_tail: str) -> str:
    title_tail = re.sub(r"\s+", " ", title_tail).strip()
    title_tail = re.split(r"(?<=\w)[.!?…]\s+", title_tail, maxsplit=1)[0]
    title_tail = re.split(r"\s+[—–]\s+", title_tail, maxsplit=1)[0]
    title_tail = re.split(
        r"(?<=[а-яёa-z0-9\)])\s+(?=[А-ЯЁ][а-яё]{3,})",
        title_tail,
        maxsplit=1,
    )[0]
    title_tail = title_tail.strip(" .:;,—-")
    words = title_tail.split()
    if len(words) > 10:
        title_tail = " ".join(words[:10]) + "…"
    elif len(title_tail) > 72:
        cut = title_tail[:72]
        if " " in cut:
            cut = cut.rsplit(" ", 1)[0]
        title_tail = cut.rstrip(" .,;:") + "…"
    return f"{number} {title_tail}".strip()


def extract_sections_from_cues(cues: list[dict[str, Any]]) -> list[dict[str, Any]]:
    sections: list[dict[str, Any]] = []
    seen = set()
    for idx, cue in enumerate(cues):
        match = SECTION_AT_START.match(str(cue.get("text", "")).strip())
        if not match:
            continue
        number = match.group("num")
        if number in seen:
            continue
        seen.add(number)
        label = _short_section_title(number, match.group("title"))
        sections.append(
            {
                "id": number,
                "title": label,
                "start": float(cue.get("start", 0.0)),
                "cueIndex": idx,
            }
        )
    return sections


def enrich_manifest_sections(manifest: dict[str, Any]) -> dict[str, Any]:
    for chapter in manifest.get("chapters", []):
        cues = chapter.get("cues") or []
        chapter["sections"] = extract_sections_from_cues(cues)
    return manifest


def write_web_bundle(
    output_dir: pathlib.Path,
    items: list[tuple[str, pathlib.Path, str]],
) -> pathlib.Path:
    web_dir = pathlib.Path(__file__).resolve().parent / "web"
    player_src = web_dir / "player.html"
    if player_src.exists():
        shutil.copy2(player_src, output_dir / "player.html")
    favicon_src = web_dir / "favicon.svg"
    if favicon_src.exists():
        shutil.copy2(favicon_src, output_dir / "favicon.svg")

    chapters: list[dict[str, Any]] = []
    for title, aiff_file, spoken_text in items:
        wav_file = convert_aiff_to_wav(aiff_file)
        duration_source = wav_file if wav_file.exists() else aiff_file
        duration = audio_duration_seconds(duration_source)
        display_text = section_refs_for_display(strip_speech_markup(spoken_text))
        aiff_file.with_suffix(".txt").write_text(display_text + "\n", encoding="utf-8")
        sidecar = load_cues_sidecar(aiff_file)
        if sidecar is not None:
            timing, cues = sidecar
        else:
            timing = "estimated"
            cues = build_sentence_cues(display_text, duration)
        chapters.append(
            {
                "title": title,
                "audio": wav_file.name,
                "duration": round(duration, 3),
                "timing": timing,
                "cues": cues,
                "sections": extract_sections_from_cues(cues),
            }
        )

    manifest = {"chapters": chapters}
    manifest_path = output_dir / "manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return manifest_path


def refresh_web_manifest(output_dir: pathlib.Path) -> pathlib.Path:
    """Update player.html and recompute section markers from existing cues."""
    web_dir = pathlib.Path(__file__).resolve().parent / "web"
    player_src = web_dir / "player.html"
    if player_src.exists():
        shutil.copy2(player_src, output_dir / "player.html")
    favicon_src = web_dir / "favicon.svg"
    if favicon_src.exists():
        shutil.copy2(favicon_src, output_dir / "favicon.svg")

    manifest_path = output_dir / "manifest.json"
    if not manifest_path.exists():
        raise RuntimeError(f"manifest.json not found in {output_dir}")

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    for chapter in manifest.get("chapters", []):
        duration = float(chapter.get("duration") or 0.0)
        cues = chapter.get("cues") or []
        for cue in cues:
            cue["text"] = section_refs_for_display(str(cue.get("text", "")))
        # Measured cues already match real audio — do not re-apply heuristics.
        if str(chapter.get("timing") or "") != "measured":
            chapter["timing"] = "estimated"
            chapter["cues"] = retime_cues(cues, duration)
        else:
            chapter["cues"] = cues
        chapter["sections"] = extract_sections_from_cues(chapter["cues"])
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return manifest_path


def write_playlist(output_dir: pathlib.Path, audio_files: list[pathlib.Path]) -> pathlib.Path:
    playlist = output_dir / "playlist.m3u"
    lines = [file.name for file in audio_files]
    playlist.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return playlist


def resolve_piper_binary() -> str:
    # Prefer the venv that owns this interpreter. Do not resolve() the
    # executable first — on macOS .venv/bin/python is a symlink into
    # Homebrew Cellar, and piper lives next to the symlink, not the target.
    exe = pathlib.Path(sys.executable)
    candidates = [
        shutil.which("piper"),
        str(exe.parent / "piper"),
        str(exe.resolve().parent / "piper"),
    ]
    for candidate in candidates:
        if candidate and pathlib.Path(candidate).is_file():
            return candidate
    raise RuntimeError(
        "Piper binary not found. Install with: make install-piper (needs brew install espeak-ng)."
    )


def synthesize_with_say(
    voice: str,
    text: str,
    output_file: pathlib.Path,
    *,
    pronounce: dict[str, str] | None = None,
    normalize_numbers: bool = True,
) -> None:
    spoken = prepare_tts_spoken_text(text, pronounce, normalize_numbers=normalize_numbers)
    text_file = output_file.with_suffix(".txt")
    text_file.write_text(spoken, encoding="utf-8")
    try:
        subprocess.run(
            ["say", "-v", voice, "-f", str(text_file), "-o", str(output_file)],
            check=True,
        )
    finally:
        text_file.unlink(missing_ok=True)


def synthesize_with_piper(
    model: pathlib.Path,
    text: str,
    output_file: pathlib.Path,
    *,
    pronounce: dict[str, str] | None = None,
    normalize_numbers: bool = True,
) -> None:
    if not model.exists():
        raise RuntimeError(f"Piper model not found: {model}. Run: make install-piper")
    config = pathlib.Path(str(model) + ".json")
    if not config.exists():
        raise RuntimeError(f"Piper model config not found: {config}")

    spoken = prepare_tts_spoken_text(
        strip_speech_markup(text), pronounce, normalize_numbers=normalize_numbers
    )
    wav_file = output_file.with_suffix(".wav")
    piper_bin = resolve_piper_binary()
    process = subprocess.run(
        [piper_bin, "--model", str(model), "--output_file", str(wav_file)],
        input=spoken + "\n",
        text=True,
        capture_output=True,
        check=False,
    )
    if process.returncode != 0:
        detail = (process.stderr or process.stdout or "").strip()
        raise RuntimeError(f"Piper failed for {output_file.name}: {detail}")

    subprocess.run(
        ["afconvert", "-f", "AIFF", "-d", "BEI16", str(wav_file), str(output_file)],
        check=True,
    )


def load_silero_model(model_id: str) -> Any:
    with _silero_lock:
        cached = _silero_models.get(model_id)
        if cached is not None:
            return cached
        try:
            from silero import silero_tts
        except ImportError as exc:
            raise RuntimeError("Silero deps missing. Install with: make install-silero") from exc

        # Do not call model.to()/eval() — packaged Silero wrappers break on that.
        # Torch emits TypedStorage deprecation from package_importer during load.
        with warnings.catch_warnings():
            warnings.filterwarnings(
                "ignore",
                message=r".*TypedStorage is deprecated.*",
                category=UserWarning,
            )
            model, _example = silero_tts(language="ru", speaker=model_id)
        _silero_models[model_id] = model
        return model


def write_wav_mono_f32(path: pathlib.Path, audio: Any, sample_rate: int) -> None:
    import torch

    if not isinstance(audio, torch.Tensor):
        audio = torch.as_tensor(audio)
    pcm = audio.detach().cpu().float().reshape(-1).clamp(-1.0, 1.0)
    samples = (pcm * 32767.0).round().to(torch.int16).numpy().tobytes()
    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(sample_rate)
        wav.writeframes(samples)


_SILERO_LETTER = re.compile(r"[A-Za-zА-Яа-яЁё]")


def prepare_silero_text(text: str) -> str:
    """Normalize glyphs that often break Silero's text pipeline."""
    text = (
        text.replace("•", " ")
        .replace("·", " ")
        .replace("–", "-")
        .replace("—", "-")
        .replace("−", "-")
    )
    return re.sub(r"\s+", " ", text).strip()


def is_speakable_for_silero(text: str) -> bool:
    """Reject empty / digits-only / punctuation-only fragments Silero ValueError's on."""
    cleaned = prepare_silero_text(text)
    return bool(cleaned) and _SILERO_LETTER.search(cleaned) is not None


def synthesize_with_silero(
    model_id: str,
    speaker: str,
    sample_rate: int,
    text: str,
    output_file: pathlib.Path,
    sentence_gap: float = DEFAULT_SILERO_SENTENCE_GAP,
    *,
    pronounce: dict[str, str] | None = None,
    normalize_numbers: bool = True,
    homographs: dict[str, str] | None = None,
    put_yo: bool = True,
    put_accent: bool = True,
) -> list[dict[str, Any]]:
    import torch

    spoken = prepare_silero_text(strip_speech_markup(text))
    if not spoken:
        raise RuntimeError(f"Empty text for Silero synthesis: {output_file.name}")

    sentences = split_sentences(spoken)
    if not sentences:
        sentences = [spoken]

    model = load_silero_model(model_id)
    gap_samples = max(0, int(sample_rate * max(sentence_gap, 0.0)))
    gap = torch.zeros(gap_samples, dtype=torch.float32) if gap_samples > 0 else None

    pieces: list[Any] = []
    cues: list[dict[str, Any]] = []
    cursor_samples = 0
    skipped = 0

    with _silero_lock:
        for idx, sentence in enumerate(sentences):
            parts = chunk_text(sentence, max_chars=SILERO_MAX_CHARS)
            sentence_parts: list[Any] = []
            for part in parts:
                part = prepare_silero_text(part)
                if not is_speakable_for_silero(part):
                    skipped += 1
                    print(
                        f"Silero skip (not speakable) in {output_file.name}: {part!r}",
                        flush=True,
                    )
                    continue
                tts_part = prepare_tts_spoken_text(
                    part,
                    pronounce,
                    normalize_numbers=normalize_numbers,
                    homographs=homographs,
                )
                try:
                    audio = model.apply_tts(
                        text=tts_part,
                        speaker=speaker,
                        sample_rate=sample_rate,
                        put_yo=put_yo,
                        put_accent=put_accent,
                    )
                except ValueError:
                    skipped += 1
                    print(
                        f"Silero skip (ValueError) in {output_file.name}: {part!r}",
                        flush=True,
                    )
                    continue
                if audio is None:
                    skipped += 1
                    print(
                        f"Silero skip (empty audio) in {output_file.name}: {part!r}",
                        flush=True,
                    )
                    continue
                sentence_parts.append(torch.as_tensor(audio).detach().cpu().float().reshape(-1))
            if not sentence_parts:
                continue
            if len(sentence_parts) == 1:
                sentence_audio = sentence_parts[0]
            else:
                sentence_audio = torch.cat(sentence_parts)

            start = cursor_samples / float(sample_rate)
            cursor_samples += int(sentence_audio.numel())
            end = cursor_samples / float(sample_rate)
            pieces.append(sentence_audio)
            cues.append(
                {
                    "start": round(start, 3),
                    "end": round(end, 3),
                    "text": section_refs_for_display(sentence),
                }
            )

            if gap is not None and idx < len(sentences) - 1:
                pieces.append(gap)
                cursor_samples += gap_samples

    if not pieces:
        raise RuntimeError(
            f"Silero produced no audio for {output_file.name} (skipped_fragments={skipped})"
        )
    if skipped:
        print(
            f"Silero skipped {skipped} fragment(s) in {output_file.name}",
            flush=True,
        )

    joined = pieces[0] if len(pieces) == 1 else torch.cat(pieces)
    wav_file = output_file.with_suffix(".wav")
    write_wav_mono_f32(wav_file, joined, sample_rate)
    subprocess.run(
        ["afconvert", "-f", "AIFF", "-d", "BEI16", str(wav_file), str(output_file)],
        check=True,
    )
    write_cues_sidecar(output_file, cues, timing="measured")
    return cues


def synthesize_chunk(
    voice: str,
    text: str,
    output_file: pathlib.Path,
    engine: str = "say",
    piper_model: pathlib.Path | None = None,
    silero_model: str = "v5_ru",
    silero_speaker: str = "xenia",
    silero_sample_rate: int = 24000,
    silero_sentence_gap: float = DEFAULT_SILERO_SENTENCE_GAP,
    pronounce: dict[str, str] | None = None,
    normalize_numbers: bool = True,
    homographs: dict[str, str] | None = None,
    silero_put_yo: bool = True,
    silero_put_accent: bool = True,
) -> None:
    if engine == "piper":
        if piper_model is None:
            raise RuntimeError("Piper model path is required for engine=piper")
        synthesize_with_piper(
            piper_model,
            text,
            output_file,
            pronounce=pronounce,
            normalize_numbers=normalize_numbers,
        )
        return
    if engine == "silero":
        synthesize_with_silero(
            silero_model,
            silero_speaker,
            silero_sample_rate,
            text,
            output_file,
            sentence_gap=silero_sentence_gap,
            pronounce=pronounce,
            normalize_numbers=normalize_numbers,
            homographs=homographs,
            put_yo=silero_put_yo,
            put_accent=silero_put_accent,
        )
        return
    synthesize_with_say(
        voice, text, output_file, pronounce=pronounce, normalize_numbers=normalize_numbers
    )


def format_duration(seconds: float) -> str:
    """Format seconds as 12s / 2m14s / 1h02m (rounded to whole seconds)."""
    total = max(0, int(round(seconds)))
    hours, rem = divmod(total, 3600)
    minutes, secs = divmod(rem, 60)
    if hours:
        return f"{hours}h{minutes:02d}m"
    if minutes:
        return f"{minutes}m{secs:02d}s"
    return f"{secs}s"


def format_job_progress_line(
    done: int,
    total: int,
    name: str,
    job_seconds: float,
    elapsed_seconds: float,
) -> str:
    return (
        f"[{done}/{total}] {name}  "
        f"+{format_duration(job_seconds)}  "
        f"elapsed {format_duration(elapsed_seconds)}"
    )


def synthesize_job(
    job: tuple[int, pathlib.Path, str],
    voice: str,
    engine: str,
    piper_model: pathlib.Path | None,
    silero_model: str,
    silero_speaker: str,
    silero_sample_rate: int,
    silero_sentence_gap: float,
    pronounce: dict[str, str] | None = None,
    normalize_numbers: bool = True,
    homographs: dict[str, str] | None = None,
    silero_put_yo: bool = True,
    silero_put_accent: bool = True,
) -> tuple[int, pathlib.Path, float]:
    idx, output_file, text = job
    started = time.perf_counter()
    synthesize_chunk(
        voice,
        text,
        output_file,
        engine=engine,
        piper_model=piper_model,
        silero_model=silero_model,
        silero_speaker=silero_speaker,
        silero_sample_rate=silero_sample_rate,
        silero_sentence_gap=silero_sentence_gap,
        pronounce=pronounce,
        normalize_numbers=normalize_numbers,
        homographs=homographs,
        silero_put_yo=silero_put_yo,
        silero_put_accent=silero_put_accent,
    )
    return idx, output_file, time.perf_counter() - started


def run_jobs(
    jobs: list[tuple[int, pathlib.Path, str]],
    voice: str,
    workers: int,
    engine: str = "say",
    piper_model: pathlib.Path | None = None,
    silero_model: str = "v5_ru",
    silero_speaker: str = "xenia",
    silero_sample_rate: int = 24000,
    silero_sentence_gap: float = DEFAULT_SILERO_SENTENCE_GAP,
    started_at: float | None = None,
    pronounce: dict[str, str] | None = None,
    normalize_numbers: bool = True,
    homographs: dict[str, str] | None = None,
    silero_put_yo: bool = True,
    silero_put_accent: bool = True,
) -> list[pathlib.Path]:
    if started_at is None:
        started_at = time.perf_counter()
    total = len(jobs)
    common = dict(
        engine=engine,
        piper_model=piper_model,
        silero_model=silero_model,
        silero_speaker=silero_speaker,
        silero_sample_rate=silero_sample_rate,
        silero_sentence_gap=silero_sentence_gap,
        pronounce=pronounce,
        normalize_numbers=normalize_numbers,
        homographs=homographs,
        silero_put_yo=silero_put_yo,
        silero_put_accent=silero_put_accent,
    )
    if workers <= 1:
        result: list[pathlib.Path] = []
        for done, (_idx, output_file, text) in enumerate(jobs, start=1):
            job_started = time.perf_counter()
            synthesize_chunk(voice, text, output_file, **common)
            print(
                format_job_progress_line(
                    done,
                    total,
                    output_file.name,
                    time.perf_counter() - job_started,
                    time.perf_counter() - started_at,
                ),
                flush=True,
            )
            result.append(output_file)
        return result

    completed: list[tuple[int, pathlib.Path]] = []
    done = 0
    done_lock = threading.Lock()
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
        futures = [
            executor.submit(
                synthesize_job,
                job,
                voice,
                engine,
                piper_model,
                silero_model,
                silero_speaker,
                silero_sample_rate,
                silero_sentence_gap,
                pronounce,
                normalize_numbers,
                homographs,
                silero_put_yo,
                silero_put_accent,
            )
            for job in jobs
        ]
        for future in concurrent.futures.as_completed(futures):
            idx, output_file, job_seconds = future.result()
            completed.append((idx, output_file))
            with done_lock:
                done += 1
                done_now = done
            print(
                format_job_progress_line(
                    done_now,
                    total,
                    output_file.name,
                    job_seconds,
                    time.perf_counter() - started_at,
                ),
                flush=True,
            )

    completed.sort(key=lambda pair: pair[0])
    return [file for _, file in completed]


def require_ffmpeg() -> str:
    path = shutil.which("ffmpeg")
    if not path:
        raise RuntimeError("ffmpeg not found. Install: brew install ffmpeg")
    return path


def default_book_title(pdf: pathlib.Path | None, out_dir: pathlib.Path) -> str:
    if pdf is not None:
        stem = pdf.stem.strip()
        if stem:
            return stem
    name = out_dir.resolve().name.strip()
    return name or "Audiobook"


def ffmetadata_escape(value: str) -> str:
    return (
        value.replace("\\", "\\\\")
        .replace("=", "\\=")
        .replace(";", "\\;")
        .replace("#", "\\#")
        .replace("\n", " ")
    )


def build_ffmetadata(
    *,
    title: str,
    artist: str,
    chapters: Sequence[tuple[str, float]],
) -> str:
    """Build ffmetadata with chapter markers; durations in seconds."""
    lines = [
        ";FFMETADATA1",
        f"title={ffmetadata_escape(title)}",
        f"artist={ffmetadata_escape(artist)}",
        f"album={ffmetadata_escape(title)}",
    ]
    cursor_ms = 0
    for chapter_title, duration in chapters:
        start_ms = cursor_ms
        end_ms = cursor_ms + max(1, int(round(float(duration) * 1000)))
        lines.extend(
            [
                "[CHAPTER]",
                "TIMEBASE=1/1000",
                f"START={start_ms}",
                f"END={end_ms}",
                f"title={ffmetadata_escape(chapter_title)}",
            ]
        )
        cursor_ms = end_ms
    return "\n".join(lines) + "\n"


def concat_demuxer_line(path: pathlib.Path) -> str:
    resolved = path.resolve().as_posix().replace("'", r"'\''")
    return f"file '{resolved}'"


def resolve_chapter_audio_file(out_dir: pathlib.Path, chapter: dict[str, Any]) -> pathlib.Path:
    audio_name = str(chapter.get("audio") or "").strip()
    if not audio_name:
        raise RuntimeError(f"Chapter missing audio field: {chapter.get('title')!r}")
    wav = out_dir / audio_name
    if wav.exists() and wav.stat().st_size > 0:
        return wav
    aiff = wav.with_suffix(".aiff")
    if aiff.exists() and aiff.stat().st_size > 0:
        return convert_aiff_to_wav(aiff)
    raise RuntimeError(f"Chapter audio not found: {wav.name} (or {aiff.name})")


def render_pdf_cover(
    pdf: pathlib.Path,
    cover_page: int,
    dest: pathlib.Path,
) -> pathlib.Path:
    try:
        import pymupdf
    except ImportError as exc:
        raise RuntimeError(
            "pymupdf is required to render a cover from PDF. "
            "Install: make install-audiobook  (or pip install -e '.[audiobook]')"
        ) from exc
    if cover_page < 1:
        raise RuntimeError("--cover-page must be >= 1")
    doc = pymupdf.open(pdf)
    try:
        if cover_page > doc.page_count:
            raise RuntimeError(
                f"--cover-page {cover_page} out of range (PDF has {doc.page_count} page(s))"
            )
        page = doc.load_page(cover_page - 1)
        pix = page.get_pixmap(matrix=pymupdf.Matrix(2, 2), alpha=False)
        dest.parent.mkdir(parents=True, exist_ok=True)
        pix.save(str(dest))
    finally:
        doc.close()
    if not dest.exists() or dest.stat().st_size == 0:
        raise RuntimeError(f"Failed to render cover to {dest}")
    return dest


def prepare_audiobook_cover(
    *,
    out_dir: pathlib.Path,
    pdf: pathlib.Path | None,
    cover: pathlib.Path | None,
    cover_page: int,
) -> pathlib.Path:
    dest = out_dir / "cover.jpg"
    if cover is not None:
        if not cover.exists():
            raise RuntimeError(f"Cover image not found: {cover}")
        if cover.resolve() != dest.resolve():
            shutil.copy2(cover, dest)
        return dest
    if pdf is None:
        raise RuntimeError("PDF path is required to render a cover (or pass --cover / COVER=…).")
    if not pdf.exists():
        raise RuntimeError(f"PDF file not found: {pdf}")
    return render_pdf_cover(pdf, cover_page, dest)


def parse_ffmpeg_progress_fields(block: str) -> dict[str, str]:
    """Parse a ffmpeg `-progress` key=value block into a dict."""
    fields: dict[str, str] = {}
    for line in block.splitlines():
        line = line.strip()
        if not line or "=" not in line:
            continue
        key, value = line.split("=", 1)
        fields[key.strip()] = value.strip()
    return fields


def ffmpeg_out_time_seconds(fields: dict[str, str]) -> float | None:
    """Best-effort output time in seconds from a progress field dict.

    Prefer ``out_time_us`` (microseconds). Do **not** use ``out_time_ms``:
    despite the name, ffmpeg reports the same microsecond PTS there.
    Fall back to human-readable ``out_time`` (HH:MM:SS.fractions).
    """
    if "out_time_us" in fields:
        raw_us = fields["out_time_us"]
        if raw_us and raw_us != "N/A":
            try:
                return max(0.0, int(raw_us) / 1_000_000.0)
            except ValueError:
                pass
    raw = fields.get("out_time")
    if not raw or raw == "N/A":
        return None
    # HH:MM:SS.microseconds
    try:
        parts = raw.split(":")
        if len(parts) != 3:
            return None
        hours = int(parts[0])
        minutes = int(parts[1])
        seconds = float(parts[2])
        return max(0.0, hours * 3600 + minutes * 60 + seconds)
    except ValueError:
        return None


def format_export_phase_line(phase: str, phase_seconds: float, elapsed_seconds: float) -> str:
    return f"{phase}  +{format_duration(phase_seconds)}  elapsed {format_duration(elapsed_seconds)}"


def format_export_encode_line(
    percent: float,
    out_seconds: float,
    elapsed_seconds: float,
) -> str:
    pct = max(0, min(100, int(round(percent))))
    return (
        f"encode {pct}%  out {format_duration(out_seconds)}  "
        f"elapsed {format_duration(elapsed_seconds)}"
    )


def should_emit_encode_progress(
    *,
    last_percent: float | None,
    last_emit_at: float | None,
    percent: float,
    now: float,
    min_interval_sec: float = 2.0,
    min_percent_step: float = 5.0,
) -> bool:
    if last_percent is None or last_emit_at is None:
        return True
    if percent - last_percent >= min_percent_step:
        return True
    return now - last_emit_at >= min_interval_sec


def run_ffmpeg_encode_with_progress(
    cmd: list[str],
    *,
    total_audio_seconds: float,
    started_at: float,
) -> None:
    """Run ffmpeg with `-progress pipe:1`, printing throttled encode lines."""
    progress_cmd = [
        *cmd[:-1],
        "-nostats",
        "-loglevel",
        "error",
        "-progress",
        "pipe:1",
        cmd[-1],
    ]
    proc = subprocess.Popen(
        progress_cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    assert proc.stdout is not None
    assert proc.stderr is not None

    block_lines: list[str] = []
    last_percent: float | None = None
    last_emit_at: float | None = None
    last_out_seconds = 0.0

    def emit(percent: float, out_seconds: float, *, force: bool = False) -> None:
        nonlocal last_percent, last_emit_at, last_out_seconds
        now = time.perf_counter()
        if not force and not should_emit_encode_progress(
            last_percent=last_percent,
            last_emit_at=last_emit_at,
            percent=percent,
            now=now,
        ):
            return
        print(
            format_export_encode_line(percent, out_seconds, now - started_at),
            flush=True,
        )
        last_percent = percent
        last_emit_at = now
        last_out_seconds = out_seconds

    while True:
        line = proc.stdout.readline()
        if line == "" and proc.poll() is not None:
            break
        if line == "":
            continue
        block_lines.append(line.rstrip("\n"))
        if not line.startswith("progress="):
            continue
        fields = parse_ffmpeg_progress_fields("\n".join(block_lines))
        block_lines.clear()
        out_seconds = ffmpeg_out_time_seconds(fields)
        if out_seconds is None:
            continue
        if total_audio_seconds > 0:
            percent = min(100.0, (out_seconds / total_audio_seconds) * 100.0)
        else:
            percent = 0.0
        force = fields.get("progress") == "end"
        if force:
            percent = 100.0
        emit(percent, out_seconds, force=force)

    stderr_text = proc.stderr.read()
    code = proc.wait()
    if code != 0:
        detail = (stderr_text or "").strip()
        raise RuntimeError(
            "ffmpeg failed to build audiobook.m4b" + (f":\n{detail}" if detail else "")
        )
    if last_percent is None or last_percent < 100:
        emit(100.0, max(last_out_seconds, total_audio_seconds), force=True)


def export_audiobook(
    out_dir: pathlib.Path,
    *,
    pdf: pathlib.Path | None = None,
    cover: pathlib.Path | None = None,
    cover_page: int = 1,
    book_title: str = "",
    book_author: str = "",
    bitrate: str = "96k",
) -> pathlib.Path:
    started_at = time.perf_counter()
    ffmpeg = require_ffmpeg()
    manifest_path = out_dir / "manifest.json"
    if not manifest_path.exists():
        raise RuntimeError(f"manifest.json not found in {out_dir}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    chapters_raw = manifest.get("chapters") or []
    if not isinstance(chapters_raw, list) or not chapters_raw:
        raise RuntimeError("manifest.json has no chapters to export")

    audio_files: list[pathlib.Path] = []
    chapter_meta: list[tuple[str, float]] = []
    for chapter in chapters_raw:
        if not isinstance(chapter, dict):
            continue
        title = str(chapter.get("title") or "Chapter").strip() or "Chapter"
        duration = float(chapter.get("duration") or 0)
        audio_path = resolve_chapter_audio_file(out_dir, chapter)
        if duration <= 0:
            duration = audio_duration_seconds(audio_path)
        audio_files.append(audio_path)
        chapter_meta.append((title, duration))

    if not audio_files:
        raise RuntimeError("No chapter audio files found for export")

    total_audio_seconds = sum(duration for _, duration in chapter_meta)
    print(
        f"Exporting {len(audio_files)} chapters "
        f"(~{format_duration(total_audio_seconds)} audio) → audiobook.m4b…",
        flush=True,
    )

    title = (book_title or "").strip() or default_book_title(pdf, out_dir)
    artist = (book_author or "").strip() or "LocalTTS"

    cover_started = time.perf_counter()
    cover_path = prepare_audiobook_cover(
        out_dir=out_dir,
        pdf=pdf,
        cover=cover,
        cover_page=cover_page,
    )
    print(
        format_export_phase_line(
            "cover",
            time.perf_counter() - cover_started,
            time.perf_counter() - started_at,
        ),
        flush=True,
    )

    output_m4b = out_dir / "audiobook.m4b"

    with tempfile.TemporaryDirectory(prefix="localtts-m4b-") as tmp:
        prepare_started = time.perf_counter()
        tmp_dir = pathlib.Path(tmp)
        concat_path = tmp_dir / "concat.txt"
        meta_path = tmp_dir / "ffmetadata.txt"
        concat_path.write_text(
            "\n".join(concat_demuxer_line(path) for path in audio_files) + "\n",
            encoding="utf-8",
        )
        meta_path.write_text(
            build_ffmetadata(title=title, artist=artist, chapters=chapter_meta),
            encoding="utf-8",
        )
        print(
            format_export_phase_line(
                "prepare",
                time.perf_counter() - prepare_started,
                time.perf_counter() - started_at,
            ),
            flush=True,
        )
        cmd = [
            ffmpeg,
            "-y",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(concat_path),
            "-i",
            str(meta_path),
            "-i",
            str(cover_path),
            "-map",
            "0:a",
            "-map_metadata",
            "1",
            "-map",
            "2:v",
            "-c:a",
            "aac",
            "-b:a",
            bitrate,
            "-c:v",
            "mjpeg",
            "-disposition:v:0",
            "attached_pic",
            "-movflags",
            "+faststart",
            str(output_m4b),
        ]
        run_ffmpeg_encode_with_progress(
            cmd,
            total_audio_seconds=total_audio_seconds,
            started_at=started_at,
        )

    if not output_m4b.exists() or output_m4b.stat().st_size == 0:
        raise RuntimeError(f"audiobook.m4b was not created in {out_dir}")
    print(
        f"\nDone in {format_duration(time.perf_counter() - started_at)}",
        flush=True,
    )
    return output_m4b


def main() -> int:
    args = parse_args()

    if args.refresh_web:
        try:
            manifest = refresh_web_manifest(args.out_dir)
        except Exception as exc:
            print(str(exc), file=sys.stderr)
            return 1
        total_sections = sum(
            len(ch.get("sections") or [])
            for ch in json.loads(manifest.read_text(encoding="utf-8"))["chapters"]
        )
        print(f"Refreshed {manifest}")
        print(f"Sections found: {total_sections}")
        return 0

    if args.export_audiobook:
        try:
            m4b = export_audiobook(
                args.out_dir,
                pdf=args.pdf,
                cover=args.cover,
                cover_page=args.cover_page,
                book_title=args.book_title,
                book_author=args.book_author,
                bitrate=args.bitrate,
            )
        except Exception as exc:
            print(str(exc), file=sys.stderr)
            return 1
        print(f"Audiobook: {m4b}")
        print(f"Cover: {args.out_dir / 'cover.jpg'}")
        return 0

    if args.pdf is None:
        print("PDF path is required (or use --refresh-web / --export-audiobook).", file=sys.stderr)
        return 1
    if not args.pdf.exists():
        print(f"PDF file not found: {args.pdf}", file=sys.stderr)
        return 1

    if args.draft_chapters:
        try:
            cleaning_patterns = load_cleaning_patterns(args.patterns_file)
        except RuntimeError as exc:
            print(str(exc), file=sys.stderr)
            return 1
        reader = get_pdf_reader(args.pdf)
        total_pages = len(reader.pages)
        start_idx, end_idx = resolve_page_range(total_pages, args.start_page, args.end_page)
        try:
            _ranges, sidecar, source = resolve_chapter_ranges(
                reader,
                pdf=args.pdf,
                total_pages=total_pages,
                start_idx=start_idx,
                end_idx=end_idx,
                chapters_file=None,
                chapter_pages=0,
                patterns=cleaning_patterns,
                draft_chapters=True,
            )
        except Exception as exc:
            print(str(exc), file=sys.stderr)
            return 1
        assert sidecar is not None
        drafted = chapter_ranges_from_file(sidecar, total_pages, start_idx, end_idx)
        print(f"Drafted {sidecar} ({len(drafted)} chapters) [{source}]")
        print("Review the file, then re-run listen (sidecar is picked up automatically):")
        print(f"  make listen-silero PDF={args.pdf}")
        return 0

    started_at = time.perf_counter()

    if args.engine == "say" and not shutil.which("say"):
        print("`say` command was not found. This script supports macOS only.", file=sys.stderr)
        return 1
    if args.engine == "piper":
        try:
            resolve_piper_binary()
        except RuntimeError as exc:
            print(str(exc), file=sys.stderr)
            return 1
        if not args.piper_model.exists():
            print(
                f"Piper model not found: {args.piper_model}. Run: make install-piper",
                file=sys.stderr,
            )
            return 1
    if args.engine == "silero":
        try:
            load_silero_model(args.silero_model)
        except RuntimeError as exc:
            print(str(exc), file=sys.stderr)
            return 1
    if args.jobs < 1:
        print("`--jobs` must be >= 1.", file=sys.stderr)
        return 1
    if args.silero_sentence_gap < 0:
        print("`--silero-sentence-gap` must be >= 0.", file=sys.stderr)
        return 1

    cleaning_patterns: CleaningPatterns | None = None
    if not args.no_strip_page_artifacts:
        try:
            cleaning_patterns = load_cleaning_patterns(args.patterns_file)
        except RuntimeError as exc:
            print(str(exc), file=sys.stderr)
            return 1

    pronounce_map: dict[str, str] = {}
    normalize_numbers = True
    homographs_map: dict[str, str] = {}
    silero_put_yo = True
    silero_put_accent = True
    speech_patterns = CleaningPatterns()
    try:
        speech_patterns = cleaning_patterns or load_cleaning_patterns(args.patterns_file)
        pronounce_map = dict(speech_patterns.pronounce)
        normalize_numbers = speech_patterns.normalize_numbers
        homographs_map = dict(speech_patterns.homographs)
        silero_put_yo = speech_patterns.silero_put_yo
        silero_put_accent = speech_patterns.silero_put_accent
    except RuntimeError:
        pronounce_map = {}
        normalize_numbers = True
        homographs_map = {}
        silero_put_yo = True
        silero_put_accent = True

    reader = get_pdf_reader(args.pdf)
    total_pages = len(reader.pages)
    start_idx, end_idx = resolve_page_range(total_pages, args.start_page, args.end_page)

    chapter_ranges: list[tuple[str, int, int]] = []
    chapter_source = ""
    if args.mode == "chapters":
        resolve_patterns = cleaning_patterns
        if resolve_patterns is None:
            try:
                resolve_patterns = load_cleaning_patterns(args.patterns_file)
            except RuntimeError:
                resolve_patterns = None
        try:
            chapter_ranges, _sidecar, chapter_source = resolve_chapter_ranges(
                reader,
                pdf=args.pdf,
                total_pages=total_pages,
                start_idx=start_idx,
                end_idx=end_idx,
                chapters_file=args.chapters_file,
                chapter_pages=args.chapter_pages,
                patterns=resolve_patterns,
                draft_chapters=False,
            )
        except Exception as exc:
            print(str(exc), file=sys.stderr)
            return 1

        if not chapter_ranges and chapter_source.startswith("drafted:"):
            sidecar_path = default_chapters_sidecar_path(args.pdf)
            drafted = chapter_ranges_from_file(sidecar_path, total_pages, start_idx, end_idx)
            print(
                f"Drafted {sidecar_path} ({len(drafted)} chapters). "
                "Review the file, then re-run the same listen command "
                "(existing sidecar is used automatically).",
                flush=True,
            )
            return 0

        if not chapter_ranges:
            print(
                "No chapters found. Use --chapters-file, PDF outline, or --chapter-pages N.",
                file=sys.stderr,
            )
            return 1

    args.out_dir.mkdir(parents=True, exist_ok=True)
    if args.clean_out_dir:
        removed = clean_output_dir(args.out_dir)
        if removed:
            print(f"Removed {removed} old audio/playlist file(s) from {args.out_dir}")

    pages_text = extract_pages_text(
        reader,
        start_idx,
        end_idx,
        strip_artifacts=not args.no_strip_page_artifacts,
        stylize_quotes=(args.engine == "say"),
        patterns=cleaning_patterns,
        speech_patterns=speech_patterns,
    )

    audio_files: list[pathlib.Path] = []
    web_items: list[tuple[str, pathlib.Path, str]] = []
    if args.engine == "piper":
        engine_label = f"piper:{args.piper_model.name}"
    elif args.engine == "silero":
        engine_label = f"silero:{args.silero_model}/{args.silero_speaker}"
    else:
        engine_label = f"say:{args.voice}"

    job_kwargs = dict(
        engine=args.engine,
        piper_model=args.piper_model,
        silero_model=args.silero_model,
        silero_speaker=args.silero_speaker,
        silero_sample_rate=args.silero_sample_rate,
        silero_sentence_gap=args.silero_sentence_gap,
        pronounce=pronounce_map,
        normalize_numbers=normalize_numbers,
        # Homographs/+stress only for Silero; say/piper ignore unused kwargs via synthesize_chunk.
        homographs=homographs_map if args.engine == "silero" else None,
        silero_put_yo=silero_put_yo,
        silero_put_accent=silero_put_accent,
    )

    if args.mode == "chapters":
        print(
            f"Generating {len(chapter_ranges)} chapter audio files with {engine_label} "
            f"[{chapter_source}]...",
            flush=True,
        )
        chapter_jobs: list[tuple[int, pathlib.Path, str]] = []
        titles_by_idx: dict[int, str] = {}
        for idx, (title, chapter_start, chapter_end) in enumerate(chapter_ranges, start=1):
            chapter_text = " ".join(
                pages_text[chapter_start - start_idx : chapter_end - start_idx]
            ).strip()
            if not chapter_text:
                continue
            safe_title = sanitize_filename(title)
            out_file = args.out_dir / f"chapter_{idx:03d}_{safe_title}.aiff"
            chapter_jobs.append((idx, out_file, chapter_text))
            titles_by_idx[idx] = title
        audio_files = run_jobs(
            chapter_jobs,
            args.voice,
            args.jobs,
            started_at=started_at,
            **job_kwargs,
        )
        web_items = [(titles_by_idx[idx], out_file, text) for idx, out_file, text in chapter_jobs]
    else:
        full_text = " ".join(pages_text).strip()
        if not full_text:
            print("No extractable text found in selected PDF pages.", file=sys.stderr)
            return 1
        chunks = chunk_text(full_text, max_chars=args.max_chars)
        print(f"Generating {len(chunks)} audio chunks with {engine_label}...")
        chunk_jobs = [
            (idx, args.out_dir / f"part_{idx:04d}.aiff", chunk)
            for idx, chunk in enumerate(chunks, start=1)
        ]
        audio_files = run_jobs(
            chunk_jobs,
            args.voice,
            args.jobs,
            started_at=started_at,
            **job_kwargs,
        )
        web_items = [(f"Часть {idx}", out_file, text) for idx, out_file, text in chunk_jobs]

    if not audio_files:
        print(
            "No audio files were generated (possibly empty pages in selected range).",
            file=sys.stderr,
        )
        return 1

    playlist = write_playlist(args.out_dir, audio_files)
    print("Building browser player bundle (wav + manifest)...")
    manifest = write_web_bundle(args.out_dir, web_items)
    print(
        f"\nDone in {format_duration(time.perf_counter() - started_at)} ({len(audio_files)} files)"
    )
    print(f"Audio chunks: {args.out_dir}")
    print(f"Playlist: {playlist}")
    print(f"Web player: {args.out_dir / 'player.html'}")
    print(f"Manifest: {manifest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
