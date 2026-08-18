"""Pre-synth number / date / percent / currency normalization for Russian TTS."""

from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation

_MONTHS_GENITIVE = (
    "",
    "января",
    "февраля",
    "марта",
    "апреля",
    "мая",
    "июня",
    "июля",
    "августа",
    "сентября",
    "октября",
    "ноября",
    "декабря",
)

# Parked replacements use markers that must not appear in source text.
_SLOT = "⟦N{0}⟧"

_DATE_RE = re.compile(
    r"(?<![A-Za-zА-Яа-яЁё0-9])"
    r"(?P<d>\d{1,2})[.](?P<m>\d{1,2})[.](?P<y>\d{2,4})"
    r"(?![A-Za-zА-Яа-яЁё0-9])"
)

_CURRENCY_PREFIX_RE = re.compile(
    r"(?<![A-Za-zА-Яа-яЁё0-9])"
    r"(?P<sym>[$€₽])\s*(?P<num>\d{1,3}(?:[ \u00a0]\d{3})*(?:[.,]\d+)?|\d+(?:[.,]\d+)?)"
    r"(?![A-Za-zА-Яа-яЁё0-9])"
)

_CURRENCY_SUFFIX_RE = re.compile(
    r"(?<![A-Za-zА-Яа-яЁё0-9])"
    r"(?P<num>\d{1,3}(?:[ \u00a0]\d{3})*(?:[.,]\d+)?|\d+(?:[.,]\d+)?)\s*(?P<sym>[$€₽])"
    r"(?![A-Za-zА-Яа-яЁё0-9])"
)

_PERCENT_RE = re.compile(
    r"(?<![A-Za-zА-Яа-яЁё0-9])"
    r"(?P<num>\d{1,3}(?:[ \u00a0]\d{3})*(?:[.,]\d+)?|\d+(?:[.,]\d+)?)\s*%"
    r"(?![A-Za-zА-Яа-яЁё0-9])"
)

_NUMERO_RE = re.compile(
    r"(?<![A-Za-zА-Яа-яЁё0-9])"
    r"№\s*(?P<num>\d{1,3}(?:[ \u00a0]\d{3})*|\d+)"
    r"(?![A-Za-zА-Яа-яЁё0-9])"
)

_DECIMAL_RE = re.compile(
    r"(?<![A-Za-zА-Яа-яЁё0-9.])"
    r"(?P<num>\d{1,3}(?:[ \u00a0]\d{3})*[.,]\d+|\d+[.,]\d+)"
    r"(?![A-Za-zА-Яа-яЁё0-9.])"
)

_INTEGER_RE = re.compile(
    r"(?<![A-Za-zА-Яа-яЁё0-9.])"
    r"(?P<num>\d{1,3}(?:[ \u00a0]\d{3})+|\d+)"
    r"(?![A-Za-zА-Яа-яЁё0-9.])"
)

_SYM_TO_CURRENCY = {"$": "USD", "€": "EUR", "₽": "RUB"}


def _num2words():
    try:
        from num2words import num2words
        from num2words.lang_RU import Num2Word_RU
    except ImportError as exc:
        raise RuntimeError(
            "num2words is required for number normalization. Install with: pip install -e ."
        ) from exc
    return num2words, Num2Word_RU()


def _parse_number_token(raw: str) -> Decimal:
    cleaned = raw.replace("\u00a0", " ").replace(" ", "")
    if "," in cleaned and "." in cleaned:
        # 1.500,50 → European
        cleaned = cleaned.replace(".", "").replace(",", ".")
    elif "," in cleaned:
        left, _, right = cleaned.partition(",")
        cleaned = (
            f"{left}.{right}" if right.isdigit() and len(right) <= 2 else cleaned.replace(",", "")
        )
    return Decimal(cleaned)


def _cardinal(value: int | Decimal) -> str:
    num2words, _ = _num2words()
    if isinstance(value, Decimal):
        if value == value.to_integral_value():
            return num2words(int(value), lang="ru")
        # Prefer "двадцать пять" style for money-like decimals via float words.
        return num2words(float(value), lang="ru")
    return num2words(int(value), lang="ru")


def _percent_noun(n: int) -> str:
    n_abs = abs(n) % 100
    n1 = n_abs % 10
    if 11 <= n_abs <= 14:
        return "процентов"
    if n1 == 1:
        return "процент"
    if n1 in (2, 3, 4):
        return "процента"
    return "процентов"


def _speak_percent(raw: str) -> str:
    amount = _parse_number_token(raw)
    if amount == amount.to_integral_value():
        n = int(amount)
        return f"{_cardinal(n)} {_percent_noun(n)}"
    return f"{_cardinal(amount)} процентов"


def _strip_zero_fraction(spoken: str) -> str:
    spoken = re.sub(r",\s*ноль\s+(?:центов|копеек)\b", "", spoken, flags=re.IGNORECASE)
    spoken = re.sub(r",\s*0+\s+(?:центов|копеек)\b", "", spoken, flags=re.IGNORECASE)
    return spoken.strip().rstrip(",").strip()


def _speak_currency(raw: str, symbol: str) -> str:
    _, converter = _num2words()
    code = _SYM_TO_CURRENCY[symbol]
    amount = _parse_number_token(raw)
    # Integer amounts must be float/Decimal — num2words treats bare int as cents.
    spoken = converter.to_currency(Decimal(amount), currency=code, cents=True)
    spoken = _strip_zero_fraction(spoken)
    if code == "USD" and "США" not in spoken.upper() and "доллар" in spoken.casefold():
        spoken = f"{spoken} США"
    return spoken


def _normalize_year(year: int) -> int:
    if year < 100:
        return 2000 + year if year < 70 else 1900 + year
    return year


def _speak_date(day: int, month: int, year: int) -> str | None:
    if not (1 <= day <= 31 and 1 <= month <= 12):
        return None
    year = _normalize_year(year)
    _, converter = _num2words()
    day_words = converter.to_ordinal(day, gender="n")
    month_words = _MONTHS_GENITIVE[month]
    year_words = converter.to_ordinal(year, case="g")
    return f"{day_words} {month_words} {year_words} года"


def _speak_numero(raw: str) -> str:
    amount = _parse_number_token(raw)
    return f"номер {_cardinal(int(amount))}"


def normalize_numbers_for_speech(text: str, enabled: bool = True) -> str:
    """Replace numbers/dates/%/currency/№ with Russian spoken forms."""
    if not enabled or not text:
        return text

    slots: list[str] = []

    def park(spoken: str) -> str:
        idx = len(slots)
        slots.append(spoken)
        return _SLOT.format(idx)

    def sub_date(match: re.Match[str]) -> str:
        spoken = _speak_date(int(match.group("d")), int(match.group("m")), int(match.group("y")))
        return park(spoken) if spoken else match.group(0)

    def sub_currency(match: re.Match[str]) -> str:
        try:
            return park(_speak_currency(match.group("num"), match.group("sym")))
        except (InvalidOperation, ValueError):
            return match.group(0)

    def sub_percent(match: re.Match[str]) -> str:
        try:
            return park(_speak_percent(match.group("num")))
        except (InvalidOperation, ValueError):
            return match.group(0)

    def sub_numero(match: re.Match[str]) -> str:
        try:
            return park(_speak_numero(match.group("num")))
        except (InvalidOperation, ValueError):
            return match.group(0)

    def sub_decimal(match: re.Match[str]) -> str:
        try:
            return park(_cardinal(_parse_number_token(match.group("num"))))
        except (InvalidOperation, ValueError):
            return match.group(0)

    def sub_integer(match: re.Match[str]) -> str:
        try:
            return park(_cardinal(int(_parse_number_token(match.group("num")))))
        except (InvalidOperation, ValueError):
            return match.group(0)

    result = text
    result = _DATE_RE.sub(sub_date, result)
    result = _CURRENCY_PREFIX_RE.sub(sub_currency, result)
    result = _CURRENCY_SUFFIX_RE.sub(sub_currency, result)
    result = _PERCENT_RE.sub(sub_percent, result)
    result = _NUMERO_RE.sub(sub_numero, result)
    result = _DECIMAL_RE.sub(sub_decimal, result)
    result = _INTEGER_RE.sub(sub_integer, result)

    for idx, spoken in enumerate(slots):
        result = result.replace(_SLOT.format(idx), spoken)
    return result
