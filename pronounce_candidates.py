#!/usr/bin/env python3
"""Extract Latin pronounce candidates for a one-shot ChatGPT → YAML workflow.

Does not call any LLM API. Prints a token list, empty pronounce: YAML skeleton,
and a fixed letter-style prompt. Human pastes into ChatGPT and merges into
patterns/default.yml manually (no overwrite of existing keys).
"""

from __future__ import annotations

import argparse
import re
import sys
from collections import Counter
from pathlib import Path

import yaml

import pdf_to_audio as ltts

# Latin token: letter start, then letters/digits/.-+
CANDIDATE_RE = re.compile(r"[A-Za-z][A-Za-z0-9.\-+]*")

# Title-Case bigrams: "Fast Follower", "ServiceNow" is single-token elsewhere.
TITLE_BIGRAM_RE = re.compile(
    r"\b([A-Z][a-z]+(?:-[A-Z][a-z]+)?(?:\s+[A-Z][a-z]+(?:-[A-Z][a-z]+)?){1,2})\b"
)

VALUEERROR_RE = re.compile(r"Silero skip \(ValueError\) in [^:]+: (.*)$")

DEFAULT_MIN_COUNT = 2
ALLCAPS_MIN_LEN = 2
ALLCAPS_MAX_LEN = 8

CHAT_PROMPT = """\
Ты помогаешь словарю произношения для русского TTS (Silero).

Правила:
- Только letter-style: как произнести по буквам/слогам по-русски (ROI→рои, GPT→джи пи ти).
- НЕ расшифровывай аббревиатуры полностью (не «return on investment»).
- Ответ — ТОЛЬКО YAML-фрагмент вида:

pronounce:
  TOKEN: "транскрипция"

- Пропускай сомнительные токены и имена людей, если они попали в список.
- Не предлагай ключи, которых нет в списке кандидатов ниже.
- Сохраняй написание ключа как в списке (регистр важен для читаемости YAML).

Кандидаты (токен × частота):
"""


def is_interesting_candidate(token: str) -> bool:
    """Keep brands/acronyms/versions; drop plain lowercase English glue."""
    if len(token) < 2:
        return False
    if " " in token:
        # Multi-word Title Case already filtered by collector.
        return all(part[:1].isupper() for part in token.split() if part)
    if any(ch.isdigit() for ch in token):
        return True
    if any(ch in ".-+" for ch in token):
        return True
    upper = sum(1 for ch in token if ch.isupper())
    if upper >= 2:
        return True
    # Title case / CamelCase (Dynatrace, DeepSeek)
    return token[0].isupper() and any(ch.islower() for ch in token[1:])


def is_allcaps_acronym(token: str) -> bool:
    """Short ALLCAPS like FAA/NTSB — keep even at frequency 1."""
    if " " in token or not (ALLCAPS_MIN_LEN <= len(token) <= ALLCAPS_MAX_LEN):
        return False
    if not token.isupper():
        return False
    letters = sum(1 for ch in token if ch.isalpha())
    return letters >= 2 and all(ch.isalnum() for ch in token)


def existing_pronounce_keys(pronounce: dict[str, str]) -> set[str]:
    return {key.casefold() for key in pronounce if key.strip()}


def collect_raw_matches(text: str) -> list[str]:
    tokens = CANDIDATE_RE.findall(text)
    phrases = TITLE_BIGRAM_RE.findall(text)
    return tokens + phrases


def effective_min_count(token: str, min_count: int, *, from_log: bool = False) -> int:
    """ALLCAPS acronyms and ValueError-log hits keep at frequency 1."""
    if from_log or is_allcaps_acronym(token):
        return 1
    return min_count


def rank_candidates(
    text: str,
    *,
    known_keys: set[str],
    min_count: int = DEFAULT_MIN_COUNT,
    extra_counts: Counter[str] | None = None,
) -> list[tuple[str, int]]:
    """Return (canonical_token, count) sorted by count desc, then token."""
    variants: dict[str, Counter[str]] = {}
    totals: Counter[str] = Counter()
    from_log_folded: set[str] = set()

    for match in collect_raw_matches(text):
        if not is_interesting_candidate(match):
            continue
        folded = match.casefold()
        if folded in known_keys:
            continue
        totals[folded] += 1
        variants.setdefault(folded, Counter())[match] += 1

    if extra_counts:
        for surface, count in extra_counts.items():
            if not surface.strip():
                continue
            folded = surface.casefold()
            if folded in known_keys:
                continue
            totals[folded] += count
            variants.setdefault(folded, Counter())[surface] += count
            from_log_folded.add(folded)

    ranked: list[tuple[str, int]] = []
    for folded, count in totals.items():
        surface = sorted(
            variants[folded].items(),
            key=lambda item: (item[1], sum(c.isupper() for c in item[0]), len(item[0])),
            reverse=True,
        )[0][0]
        need = effective_min_count(surface, min_count, from_log=folded in from_log_folded)
        if count < need:
            continue
        ranked.append((surface, count))

    ranked.sort(key=lambda item: (-item[1], item[0].casefold()))
    return ranked


def clean_valueerror_fragment(raw: str) -> str | None:
    """Normalize a Silero ValueError fragment into a pronounce key candidate."""
    s = raw.strip()
    if len(s) >= 2 and s[0] == "'" and s[-1] == "'":
        s = s[1:-1]
    s = s.strip()
    if not s or "//" in s or s.startswith("www."):
        return None
    if re.fullmatch(r"[A-Za-z]\.", s):
        return None
    if re.fullmatch(r"G\d{5,}", s):
        return None
    while s and s[-1] in ",.;:)/":
        s = s[:-1]
    s = s.strip().lstrip("(").strip()
    if "(" in s:
        s = s.split("(", 1)[0].strip()
    if len(s) < 2:
        return None
    # Domain crumbs / junk
    junk = {
        "forbes",
        "stanford",
        "google",
        "amazon",
        "pagerduty",
        "honeycomb",
        "elastic",
        "jsp?",
    }
    if s.casefold() in junk:
        return None
    if s.casefold().startswith("com/"):
        return None
    return s


def collect_valueerror_counts(log_text: str) -> Counter[str]:
    counts: Counter[str] = Counter()
    for line in log_text.splitlines():
        match = VALUEERROR_RE.search(line)
        if not match:
            continue
        key = clean_valueerror_fragment(match.group(1))
        if key:
            counts[key] += 1
    return counts


def format_yaml_skeleton(candidates: list[tuple[str, int]]) -> str:
    lines = ["pronounce:"]
    if not candidates:
        lines.append("  {}")
        return "\n".join(lines) + "\n"
    for token, _count in candidates:
        key = yaml.dump(token, allow_unicode=True).strip()
        # yaml.dump adds quotes when needed; for plain keys use as-is.
        if key.startswith("'") or key.startswith('"'):
            lines.append(f'  {key}: ""')
        else:
            lines.append(f'  {token}: ""')
    return "\n".join(lines) + "\n"


def format_report(candidates: list[tuple[str, int]]) -> str:
    parts: list[str] = []
    parts.append("=== pronounce candidates ===")
    if not candidates:
        parts.append("(пусто — ничего нового с заданным порогом)")
    else:
        for token, count in candidates:
            parts.append(f"  {count:4d}  {token}")
    parts.append("")
    parts.append("=== YAML skeleton (paste values after ChatGPT) ===")
    parts.append(format_yaml_skeleton(candidates).rstrip())
    parts.append("")
    parts.append("=== ChatGPT prompt ===")
    parts.append(CHAT_PROMPT.rstrip())
    for token, count in candidates:
        parts.append(f"- {token} × {count}")
    if not candidates:
        parts.append("(нет кандидатов)")
    parts.append("")
    parts.append(
        "Дальше: скопируй блок prompt → ChatGPT → вручную вмержи новые ключи "
        "в patterns/default.yml (существующие не перезаписывать)."
    )
    return "\n".join(parts) + "\n"


def load_text_from_pdf(
    pdf_path: Path,
    *,
    patterns_file: Path | None,
    start_page: int = 1,
    end_page: int = 0,
) -> str:
    """Extract cleaned page text before pronounce/NUM (pipeline extract layer)."""
    patterns = ltts.load_cleaning_patterns(patterns_file)
    reader = ltts.get_pdf_reader(pdf_path)
    total = len(reader.pages)
    start_idx, end_idx = ltts.resolve_page_range(total, start_page, end_page)
    pages = ltts.extract_pages_text(
        reader,
        start_idx,
        end_idx,
        strip_artifacts=True,
        stylize_quotes=True,
        patterns=patterns,
        speech_patterns=patterns,
    )
    return "\n".join(pages)


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Extract Latin pronounce candidates (freq≥N, ALLCAPS×1, optional "
            "ValueError log) minus existing keys; print ChatGPT prompt + YAML. "
            "No LLM API."
        )
    )
    src = parser.add_mutually_exclusive_group(required=False)
    src.add_argument("--pdf", type=Path, help="PDF: extract text before pronounce apply")
    src.add_argument(
        "--text",
        type=Path,
        help="UTF-8 text file before pronounce apply (not OUT_DIR spoken .txt)",
    )
    parser.add_argument(
        "--from-log",
        type=Path,
        help="Conversion log: also mine Silero skip (ValueError) fragments",
    )
    parser.add_argument(
        "--patterns-file",
        type=Path,
        default=ltts.DEFAULT_PATTERNS_FILE,
        help="Patterns YAML with existing pronounce: keys",
    )
    parser.add_argument(
        "--min-count",
        type=int,
        default=DEFAULT_MIN_COUNT,
        help=(
            f"Minimum occurrences for normal tokens (default {DEFAULT_MIN_COUNT}); "
            "ALLCAPS acronyms 2–8 chars keep at ×1"
        ),
    )
    parser.add_argument("--start-page", type=int, default=1)
    parser.add_argument("--end-page", type=int, default=0, help="0 = last page")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    if args.min_count < 1:
        print("--min-count must be >= 1", file=sys.stderr)
        return 2
    if args.pdf is None and args.text is None and args.from_log is None:
        print("Need --pdf, --text, and/or --from-log", file=sys.stderr)
        return 2

    patterns = ltts.load_cleaning_patterns(args.patterns_file)
    known = existing_pronounce_keys(patterns.pronounce)

    text = ""
    if args.pdf is not None:
        if not args.pdf.is_file():
            print(f"PDF not found: {args.pdf}", file=sys.stderr)
            return 2
        text = load_text_from_pdf(
            args.pdf,
            patterns_file=args.patterns_file,
            start_page=args.start_page,
            end_page=args.end_page,
        )
    elif args.text is not None:
        if not args.text.is_file():
            print(f"Text file not found: {args.text}", file=sys.stderr)
            return 2
        text = args.text.read_text(encoding="utf-8")

    extra: Counter[str] | None = None
    if args.from_log is not None:
        if not args.from_log.is_file():
            print(f"Log file not found: {args.from_log}", file=sys.stderr)
            return 2
        extra = collect_valueerror_counts(
            args.from_log.read_text(encoding="utf-8", errors="replace")
        )

    candidates = rank_candidates(
        text,
        known_keys=known,
        min_count=args.min_count,
        extra_counts=extra,
    )
    sys.stdout.write(format_report(candidates))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
