#!/usr/bin/env python3
"""
Convert a PDF document to local audio files on macOS.

Uses:
- pypdf for text extraction
- built-in `say` command for offline TTS
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
from collections.abc import Sequence
from typing import Any


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Convert PDF into offline audio chunks using macOS `say`."
    )
    parser.add_argument(
        "pdf",
        type=pathlib.Path,
        nargs="?",
        default=None,
        help="Path to source PDF (not required with --refresh-web)",
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
        "--voice",
        default="Milena",
        help="macOS `say` voice name (default: Milena). Ignored for Piper.",
    )
    parser.add_argument(
        "--engine",
        choices=["say", "piper"],
        default="say",
        help="TTS engine: macOS say (default) or local Piper neural voice",
    )
    parser.add_argument(
        "--piper-model",
        type=pathlib.Path,
        default=pathlib.Path("models/ru_RU-irina-medium.onnx"),
        help="Path to Piper .onnx model (default: models/ru_RU-irina-medium.onnx)",
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
        "--no-strip-page-artifacts",
        action="store_true",
        help="Disable removal of likely page numbers/headers/footers",
    )
    parser.add_argument(
        "--ai-spoken-as",
        default="эй ай",
        help="How to pronounce `AI` (default: `эй ай`)",
    )
    parser.add_argument(
        "--ii-spoken-as",
        default="и и",
        help="How to pronounce `ИИ` (default: `и и`)",
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


def strip_page_artifacts(text: str) -> str:
    lines = [line.strip() for line in text.replace("\r", "\n").split("\n")]
    nonempty = [line for line in lines if line]
    if not nonempty:
        return ""

    page_number_only = re.compile(r"^\d{1,4}$")
    footer_with_dot = re.compile(
        r"^(?:AI-Disrupt\s+)?PDLC\s*[·•]\s.{1,140}(?:\s+\d{1,4})?$",
        re.IGNORECASE,
    )
    footer_with_pipe = re.compile(r"^.{3,80}\s[|]\s.{1,80}(?:\s+\d{1,4})?$")

    def looks_like_artifact(line: str) -> bool:
        if (
            page_number_only.match(line)
            or footer_with_dot.match(line)
            or footer_with_pipe.match(line)
        ):
            return True
        return bool(re.match(r"^(?:AI-Disrupt\s+)?PDLC\s*[·•]", line, re.IGNORECASE))

    # Drop footer/header lines wherever they appear (PDF extract order varies).
    filtered = [line for line in nonempty if not looks_like_artifact(line)]
    if filtered:
        nonempty = filtered

    # Edge cleanup for artifacts not caught above.
    while nonempty and looks_like_artifact(nonempty[0]):
        nonempty.pop(0)
    while nonempty and looks_like_artifact(nonempty[-1]):
        nonempty.pop()

    return "\n".join(nonempty)


def strip_inline_page_artifacts(text: str) -> str:
    # Footers often get glued to the last sentence on the same line.
    text = re.sub(
        r"\s*AI-Disrupt PDLC\s*[·•]\s*Целевое видение\s*(?:\d{1,4})?\s*",
        " ",
        text,
        flags=re.IGNORECASE,
    )
    text = re.sub(
        r"\s[\w\-]{2,40}\s+PDLC\s*[·•]\s*[^\d.]{3,80}\s*(?:\d{1,4})?\s*",
        " ",
        text,
        flags=re.IGNORECASE,
    )
    text = re.sub(
        r"\s[·•]\s[^\d.]{3,80}\s+\d{1,4}\s*$",
        "",
        text,
    )
    # Trailing orphan page number at end of page text.
    text = re.sub(r"\s+\d{1,4}\s*$", "", text)
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
    ai_spoken_as: str,
    ii_spoken_as: str,
    stylize_quotes: bool = True,
) -> list[str]:
    pages_text: list[str] = []
    for page_idx in range(start_idx, end_idx):
        text = reader.pages[page_idx].extract_text() or ""
        if strip_artifacts:
            text = strip_page_artifacts(text)
        text = apply_pronunciation_fixes(text, ai_spoken_as=ai_spoken_as, ii_spoken_as=ii_spoken_as)
        text = expand_section_references(text)
        normalized = normalize_text(text)
        if strip_artifacts:
            normalized = strip_inline_page_artifacts(normalized)
        if stylize_quotes:
            normalized = stylize_quoted_speech(normalized)
        pages_text.append(normalized)
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

        if "|" not in line or "-" not in line:
            raise RuntimeError(
                f"Invalid chapters file format at line {line_number}: expected `Title|start-end`"
            )

        title_part, pages_part = line.split("|", 1)
        start_part, end_part = pages_part.split("-", 1)

        title = title_part.strip()
        if not title:
            raise RuntimeError(f"Invalid empty chapter title at line {line_number}")

        try:
            start_page = int(start_part.strip())
            end_page_inclusive = int(end_part.strip())
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


def clean_output_dir(output_dir: pathlib.Path) -> int:
    patterns = ("*.aiff", "*.wav", "*.mp3", "*.m4a", "*.m3u", "manifest.json")
    removed = 0
    for pattern in patterns:
        for path in output_dir.glob(pattern):
            path.unlink()
            removed += 1
    return removed


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


def build_sentence_cues(text: str, duration: float) -> list[dict[str, Any]]:
    sentences = split_sentences(text)
    if not sentences:
        return [{"start": 0.0, "end": duration, "text": strip_speech_markup(text)}]

    weights = [max(len(sentence), 1) for sentence in sentences]
    total_weight = float(sum(weights))
    cues: list[dict[str, Any]] = []
    cursor = 0.0
    for idx, (sentence, weight) in enumerate(zip(sentences, weights, strict=False)):
        end = duration if idx == len(sentences) - 1 else cursor + duration * (weight / total_weight)
        cues.append(
            {
                "start": round(cursor, 3),
                "end": round(end, 3),
                "text": sentence,
            }
        )
        cursor = end
    return cues


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
        cues = build_sentence_cues(display_text, duration)
        chapters.append(
            {
                "title": title,
                "audio": wav_file.name,
                "duration": round(duration, 3),
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
        for cue in chapter.get("cues") or []:
            cue["text"] = section_refs_for_display(str(cue.get("text", "")))
    enrich_manifest_sections(manifest)
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


def synthesize_with_say(voice: str, text: str, output_file: pathlib.Path) -> None:
    text_file = output_file.with_suffix(".txt")
    text_file.write_text(text, encoding="utf-8")
    try:
        subprocess.run(
            ["say", "-v", voice, "-f", str(text_file), "-o", str(output_file)],
            check=True,
        )
    finally:
        text_file.unlink(missing_ok=True)


def synthesize_with_piper(model: pathlib.Path, text: str, output_file: pathlib.Path) -> None:
    if not model.exists():
        raise RuntimeError(f"Piper model not found: {model}. Run: make install-piper")
    config = pathlib.Path(str(model) + ".json")
    if not config.exists():
        raise RuntimeError(f"Piper model config not found: {config}")

    spoken = strip_speech_markup(text)
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


def synthesize_chunk(
    voice: str,
    text: str,
    output_file: pathlib.Path,
    engine: str = "say",
    piper_model: pathlib.Path | None = None,
) -> None:
    if engine == "piper":
        if piper_model is None:
            raise RuntimeError("Piper model path is required for engine=piper")
        synthesize_with_piper(piper_model, text, output_file)
        return
    synthesize_with_say(voice, text, output_file)


def synthesize_job(
    job: tuple[int, pathlib.Path, str],
    voice: str,
    engine: str,
    piper_model: pathlib.Path | None,
) -> tuple[int, pathlib.Path]:
    idx, output_file, text = job
    synthesize_chunk(
        voice,
        text,
        output_file,
        engine=engine,
        piper_model=piper_model,
    )
    return idx, output_file


def run_jobs(
    jobs: list[tuple[int, pathlib.Path, str]],
    voice: str,
    workers: int,
    engine: str = "say",
    piper_model: pathlib.Path | None = None,
) -> list[pathlib.Path]:
    if workers <= 1:
        result: list[pathlib.Path] = []
        for idx, output_file, text in jobs:
            synthesize_chunk(
                voice,
                text,
                output_file,
                engine=engine,
                piper_model=piper_model,
            )
            result.append(output_file)
            print(f"[{idx}/{len(jobs)}] {output_file.name}")
        return result

    completed: list[tuple[int, pathlib.Path]] = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
        futures = [executor.submit(synthesize_job, job, voice, engine, piper_model) for job in jobs]
        for future in concurrent.futures.as_completed(futures):
            idx, output_file = future.result()
            completed.append((idx, output_file))
            print(f"[{idx}/{len(jobs)}] {output_file.name}")

    completed.sort(key=lambda pair: pair[0])
    return [file for _, file in completed]


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

    if args.pdf is None:
        print("PDF path is required (or use --refresh-web).", file=sys.stderr)
        return 1

    if not args.pdf.exists():
        print(f"PDF file not found: {args.pdf}", file=sys.stderr)
        return 1
    if args.jobs < 1:
        print("`--jobs` must be >= 1.", file=sys.stderr)
        return 1

    args.out_dir.mkdir(parents=True, exist_ok=True)
    if args.clean_out_dir:
        removed = clean_output_dir(args.out_dir)
        if removed:
            print(f"Removed {removed} old audio/playlist file(s) from {args.out_dir}")

    reader = get_pdf_reader(args.pdf)
    total_pages = len(reader.pages)
    start_idx, end_idx = resolve_page_range(total_pages, args.start_page, args.end_page)
    pages_text = extract_pages_text(
        reader,
        start_idx,
        end_idx,
        strip_artifacts=not args.no_strip_page_artifacts,
        ai_spoken_as=args.ai_spoken_as,
        ii_spoken_as=args.ii_spoken_as,
        stylize_quotes=(args.engine == "say"),
    )

    audio_files: list[pathlib.Path] = []
    web_items: list[tuple[str, pathlib.Path, str]] = []
    engine_label = (
        f"piper:{args.piper_model.name}" if args.engine == "piper" else f"say:{args.voice}"
    )

    if args.mode == "chapters":
        chapter_ranges: list[tuple[str, int, int]] = []
        if args.chapters_file is not None:
            chapter_ranges = chapter_ranges_from_file(
                args.chapters_file, total_pages, start_idx, end_idx
            )
        if not chapter_ranges:
            chapter_ranges = chapter_ranges_from_outline(reader, start_idx, end_idx)
        if not chapter_ranges:
            chapter_ranges = chapter_ranges_by_fixed_size(start_idx, end_idx, args.chapter_pages)

        if not chapter_ranges:
            print(
                "No chapters found. Use --chapters-file, PDF outline, or --chapter-pages N.",
                file=sys.stderr,
            )
            return 1

        print(f"Generating {len(chapter_ranges)} chapter audio files with {engine_label}...")
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
            engine=args.engine,
            piper_model=args.piper_model,
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
            engine=args.engine,
            piper_model=args.piper_model,
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
    print("\nDone.")
    print(f"Audio chunks: {args.out_dir}")
    print(f"Playlist: {playlist}")
    print(f"Web player: {args.out_dir / 'player.html'}")
    print(f"Manifest: {manifest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
