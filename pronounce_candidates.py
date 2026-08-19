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

DEFAULT_MIN_COUNT = 2

CHAT_PROMPT = """\
Ты помогаешь словарю произношения для русского TTS (Silero).

Правила:
- Только letter-style: как произнести по буквам/слогам по-русски (ROI→рои, GPT→джи пи ти).
- НЕ расшифровывай аббревиатуры полностью (не «return on investment»).
- Ответ — ТОЛЬКО YAML-фрагмент вида:

pronounce:
  TOKEN: "транскрипция"

- Пропускай сомнительные токены.
- Не предлагай ключи, которых нет в списке кандидатов ниже.
- Сохраняй написание ключа как в списке (регистр важен для читаемости YAML).

Кандидаты (токен × частота):
"""


def is_interesting_candidate(token: str) -> bool:
    """Keep brands/acronyms/versions; drop plain lowercase English glue."""
    if len(token) < 2:
        return False
    if any(ch.isdigit() for ch in token):
        return True
    if any(ch in ".-+" for ch in token):
        return True
    upper = sum(1 for ch in token if ch.isupper())
    if upper >= 2:
        return True
    # Title case / CamelCase (Dynatrace, DeepSeek)
    return token[0].isupper() and any(ch.islower() for ch in token[1:])


def existing_pronounce_keys(pronounce: dict[str, str]) -> set[str]:
    return {key.casefold() for key in pronounce if key.strip()}


def collect_raw_matches(text: str) -> list[str]:
    return CANDIDATE_RE.findall(text)


def rank_candidates(
    text: str,
    *,
    known_keys: set[str],
    min_count: int = DEFAULT_MIN_COUNT,
) -> list[tuple[str, int]]:
    """Return (canonical_token, count) sorted by count desc, then token."""
    variants: dict[str, Counter[str]] = {}
    totals: Counter[str] = Counter()

    for match in collect_raw_matches(text):
        if not is_interesting_candidate(match):
            continue
        folded = match.casefold()
        if folded in known_keys:
            continue
        totals[folded] += 1
        variants.setdefault(folded, Counter())[match] += 1

    ranked: list[tuple[str, int]] = []
    for folded, count in totals.items():
        if count < min_count:
            continue
        # Prefer the most frequent surface form; ties → longer / more uppercase.
        surface = sorted(
            variants[folded].items(),
            key=lambda item: (item[1], sum(c.isupper() for c in item[0]), len(item[0])),
            reverse=True,
        )[0][0]
        ranked.append((surface, count))

    ranked.sort(key=lambda item: (-item[1], item[0].casefold()))
    return ranked


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
            "Extract Latin pronounce candidates (freq≥N, minus existing keys) "
            "and print ChatGPT prompt + YAML skeleton. No LLM API."
        )
    )
    src = parser.add_mutually_exclusive_group(required=True)
    src.add_argument("--pdf", type=Path, help="PDF: extract text before pronounce apply")
    src.add_argument(
        "--text",
        type=Path,
        help="UTF-8 text file before pronounce apply (not OUT_DIR spoken .txt)",
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
        help=f"Minimum occurrences (default {DEFAULT_MIN_COUNT})",
    )
    parser.add_argument("--start-page", type=int, default=1)
    parser.add_argument("--end-page", type=int, default=0, help="0 = last page")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    if args.min_count < 1:
        print("--min-count must be >= 1", file=sys.stderr)
        return 2

    patterns = ltts.load_cleaning_patterns(args.patterns_file)
    known = existing_pronounce_keys(patterns.pronounce)

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
    else:
        assert args.text is not None
        if not args.text.is_file():
            print(f"Text file not found: {args.text}", file=sys.stderr)
            return 2
        text = args.text.read_text(encoding="utf-8")

    candidates = rank_candidates(text, known_keys=known, min_count=args.min_count)
    sys.stdout.write(format_report(candidates))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
