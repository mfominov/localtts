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

# $1,04 млрд / 1,04 млрд $ — before plain currency so scale is not left raw.
_NUM_TOKEN = r"\d{1,3}(?:[ \u00a0]\d{3})*(?:[.,]\d+)?|\d+(?:[.,]\d+)?"
_SCALE_TOKEN = r"млрд|млн|тыс"

_CURRENCY_SCALE_PREFIX_RE = re.compile(
    rf"(?<![A-Za-zА-Яа-яЁё0-9])"
    rf"(?P<sym>[$€₽])\s*(?P<num>{_NUM_TOKEN})"
    rf"\s*(?P<scale>{_SCALE_TOKEN})\.?"
    rf"(?![A-Za-zА-Яа-яЁё0-9])",
    flags=re.IGNORECASE,
)

_CURRENCY_SCALE_SUFFIX_RE = re.compile(
    rf"(?<![A-Za-zА-Яа-яЁё0-9])"
    rf"(?P<num>{_NUM_TOKEN})"
    rf"\s*(?P<scale>{_SCALE_TOKEN})\.?\s*(?P<sym>[$€₽])"
    rf"(?![A-Za-zА-Яа-яЁё0-9])",
    flags=re.IGNORECASE,
)

_NUM_SCALE_RE = re.compile(
    rf"(?<![A-Za-zА-Яа-яЁё0-9])"
    rf"(?P<num>{_NUM_TOKEN})"
    rf"\s*(?P<scale>{_SCALE_TOKEN})\.?"
    rf"(?![A-Za-zА-Яа-яЁё0-9])",
    flags=re.IGNORECASE,
)

_PERCENT_RE = re.compile(
    r"(?<![A-Za-zА-Яа-яЁё0-9])"
    r"(?:(?P<pre>не\s+менее|не\s+более|более|менее|свыше|около|порядка|от|до)\s+)?"
    r"(?P<num>\d{1,3}(?:[ \u00a0]\d{3})*(?:[.,]\d+)?|\d+(?:[.,]\d+)?)\s*%"
    r"(?![A-Za-zА-Яа-яЁё0-9])"
)

# не менее 20 / свыше 5 — after percent so `20%` is not eaten twice.
_GENITIVE_NUM_RE = re.compile(
    r"(?<![A-Za-zА-Яа-яЁё0-9])"
    r"(?P<pre>не\s+менее|не\s+более|более|менее|свыше|около|порядка|от|до)\s+"
    r"(?P<num>\d{1,3}(?:[ \u00a0]\d{3})+|\d+)"
    r"(?![A-Za-zА-Яа-яЁё0-9.%]|-)"
)

# 1-е место / 2-й / 3-я — before bare integers so `1-е` is not `один-е`.
_ORDINAL_RE = re.compile(
    r"(?<![A-Za-zА-Яа-яЁё0-9.])"
    r"(?P<num>\d{1,3})"
    r"-"
    r"(?P<suf>его|ому|ыми|ый|ой|ое|ая|ых|ым|ую|ей|го|му|ми|х|й|е|я|м|ю)"
    r"(?![A-Za-zА-Яа-яЁё0-9])"
)

_NUMERO_RE = re.compile(
    r"(?<![A-Za-zА-Яа-яЁё0-9])"
    r"№\s*(?P<num>\d{1,3}(?:[ \u00a0]\d{3})*|\d+)"
    r"(?![A-Za-zА-Яа-яЁё0-9])"
)

# ≥ 0,90 / <=1.5 — before bare decimals/integers.
_COMPARE_RE = re.compile(
    r"(?<![A-Za-zА-Яа-яЁё0-9])"
    r"(?P<op>≥|≤|≠|>=|<=)"
    r"\s*"
    r"(?P<num>\d{1,3}(?:[ \u00a0]\d{3})*(?:[.,]\d+)?|\d+(?:[.,]\d+)?)"
    r"(?![A-Za-zА-Яа-яЁё0-9])"
)

# к 2028 году / в 2028 году / с 2024 года — before bare year integers.
_YEAR_PREP_RE = re.compile(
    r"(?<![A-Za-zА-Яа-яЁё0-9])"
    r"(?P<pre>ко|к|во|в|до|после|со|с|от)\s+"
    r"(?P<year>19\d{2}|20\d{2})\s+"
    r"(?P<noun>году|года|годом|год)"
    r"(?![A-Za-zА-Яа-яЁё0-9])",
    flags=re.IGNORECASE,
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

# After scale noun, currency is genitive plural («миллиард долларов США»).
_CURRENCY_AFTER_SCALE = {
    "USD": "долларов США",
    "EUR": "евро",
    "RUB": "рублей",
}

_SCALE_FORMS = {
    # (1, 2-4, 5+)
    "млрд": ("миллиард", "миллиарда", "миллиардов"),
    "млн": ("миллион", "миллиона", "миллионов"),
    "тыс": ("тысяча", "тысячи", "тысяч"),
}

_COMPARE_WORDS = {
    "≥": "больше или равно",
    ">=": "больше или равно",
    "≤": "меньше или равно",
    "<=": "меньше или равно",
    "≠": "не равно",
}

# Preposition → num2words ordinal case; spoken noun follows the case.
_YEAR_PREP_CASE = {
    "к": "d",
    "ко": "d",
    "в": "p",
    "во": "p",
    "до": "g",
    "после": "g",
    "с": "g",
    "со": "g",
    "от": "g",
}

_YEAR_CASE_NOUN = {
    "d": "году",
    "p": "году",
    "g": "года",
    "n": "год",
}

# Hyphen ordinal suffix → (gender, case, plural) for num2words RU.
_ORDINAL_SUFFIX = {
    "ый": ("m", "n", False),
    "ой": ("m", "n", False),
    "й": ("m", "n", False),
    "ое": ("n", "n", False),
    "е": ("n", "n", False),
    "ая": ("f", "n", False),
    "я": ("f", "n", False),
    "его": ("m", "g", False),
    "го": ("m", "g", False),
    "ому": ("m", "d", False),
    "му": ("m", "d", False),
    "ыми": ("m", "i", True),
    "ми": ("m", "i", True),
    "ых": ("m", "g", True),
    "х": ("m", "g", True),
    "ым": ("m", "p", False),
    "м": ("m", "p", False),
    "ую": ("f", "a", False),
    "ю": ("f", "a", False),
    "ей": ("f", "g", False),
}


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


def _cardinal(value: int | Decimal, case: str = "n") -> str:
    num2words, converter = _num2words()
    if isinstance(value, Decimal):
        if value == value.to_integral_value():
            return converter.to_cardinal(int(value), case=case)
        # Prefer "двадцать пять" style for money-like decimals via float words.
        return num2words(float(value), lang="ru")
    return converter.to_cardinal(int(value), case=case)


def _percent_noun(n: int, case: str = "n") -> str:
    n_abs = abs(n) % 100
    n1 = n_abs % 10
    if case == "g":
        if 11 <= n_abs <= 14:
            return "процентов"
        if n1 == 1:
            return "процента"
        return "процентов"
    if 11 <= n_abs <= 14:
        return "процентов"
    if n1 == 1:
        return "процент"
    if n1 in (2, 3, 4):
        return "процента"
    return "процентов"


def _speak_percent(raw: str, case: str = "n") -> str:
    amount = _parse_number_token(raw)
    if amount == amount.to_integral_value():
        n = int(amount)
        return f"{_cardinal(n, case=case)} {_percent_noun(n, case=case)}"
    return f"{_cardinal(amount)} процентов"


def _speak_ordinal(raw: str, suffix: str) -> str | None:
    spec = _ORDINAL_SUFFIX.get(suffix.casefold())
    if not spec:
        return None
    gender, case, plural = spec
    _, converter = _num2words()
    return converter.to_ordinal(int(raw), case=case, gender=gender, plural=plural)


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


def _lossy_scale_count(amount: Decimal) -> int:
    """Integer magnitude for «примерно N миллиард…» (drop fractional cents-of-a-billion)."""
    if amount < 0:
        amount = -amount
    n = int(amount)
    if n == 0 and amount > 0:
        return 1
    return n


def _scale_noun(n: int, scale: str) -> str:
    key = scale.casefold().rstrip(".")
    forms = _SCALE_FORMS[key]
    n_abs = abs(n) % 100
    n1 = n_abs % 10
    if 11 <= n_abs <= 14:
        return forms[2]
    if n1 == 1:
        return forms[0]
    if n1 in (2, 3, 4):
        return forms[1]
    return forms[2]


def _speak_scaled_amount(raw: str, scale: str, symbol: str | None = None) -> str:
    amount = _parse_number_token(raw)
    n = _lossy_scale_count(amount)
    spoken = f"примерно {_cardinal(n)} {_scale_noun(n, scale)}"
    if symbol:
        code = _SYM_TO_CURRENCY[symbol]
        spoken = f"{spoken} {_CURRENCY_AFTER_SCALE[code]}"
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


def _speak_compare(op: str, raw: str) -> str:
    words = _COMPARE_WORDS[op]
    return f"{words} {_cardinal(_parse_number_token(raw))}"


def _speak_year_prep(pre: str, year: int, _noun: str) -> str | None:
    case = _YEAR_PREP_CASE.get(pre.casefold())
    if not case:
        return None
    year = _normalize_year(year)
    if not (1900 <= year <= 2100):
        return None
    _, converter = _num2words()
    year_words = converter.to_ordinal(year, case=case)
    noun = _YEAR_CASE_NOUN[case]
    return f"{pre} {year_words} {noun}"


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

    def sub_currency_scale(match: re.Match[str]) -> str:
        try:
            return park(
                _speak_scaled_amount(
                    match.group("num"),
                    match.group("scale"),
                    match.group("sym"),
                )
            )
        except (InvalidOperation, ValueError, KeyError):
            return match.group(0)

    def sub_num_scale(match: re.Match[str]) -> str:
        try:
            return park(_speak_scaled_amount(match.group("num"), match.group("scale")))
        except (InvalidOperation, ValueError, KeyError):
            return match.group(0)

    def sub_percent(match: re.Match[str]) -> str:
        try:
            case = "g" if match.group("pre") else "n"
            spoken = _speak_percent(match.group("num"), case=case)
            prefix = match.group("pre")
            return park(f"{prefix} {spoken}" if prefix else spoken)
        except (InvalidOperation, ValueError):
            return match.group(0)

    def sub_genitive_num(match: re.Match[str]) -> str:
        try:
            spoken = _cardinal(int(_parse_number_token(match.group("num"))), case="g")
            return park(f"{match.group('pre')} {spoken}")
        except (InvalidOperation, ValueError):
            return match.group(0)

    def sub_ordinal(match: re.Match[str]) -> str:
        spoken = _speak_ordinal(match.group("num"), match.group("suf"))
        return park(spoken) if spoken else match.group(0)

    def sub_numero(match: re.Match[str]) -> str:
        try:
            return park(_speak_numero(match.group("num")))
        except (InvalidOperation, ValueError):
            return match.group(0)

    def sub_compare(match: re.Match[str]) -> str:
        try:
            return park(_speak_compare(match.group("op"), match.group("num")))
        except (InvalidOperation, ValueError, KeyError):
            return match.group(0)

    def sub_year_prep(match: re.Match[str]) -> str:
        spoken = _speak_year_prep(match.group("pre"), int(match.group("year")), match.group("noun"))
        return park(spoken) if spoken else match.group(0)

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
    result = _CURRENCY_SCALE_PREFIX_RE.sub(sub_currency_scale, result)
    result = _CURRENCY_SCALE_SUFFIX_RE.sub(sub_currency_scale, result)
    result = _CURRENCY_PREFIX_RE.sub(sub_currency, result)
    result = _CURRENCY_SUFFIX_RE.sub(sub_currency, result)
    result = _NUM_SCALE_RE.sub(sub_num_scale, result)
    result = _PERCENT_RE.sub(sub_percent, result)
    result = _NUMERO_RE.sub(sub_numero, result)
    result = _COMPARE_RE.sub(sub_compare, result)
    result = _YEAR_PREP_RE.sub(sub_year_prep, result)
    result = _GENITIVE_NUM_RE.sub(sub_genitive_num, result)
    result = _ORDINAL_RE.sub(sub_ordinal, result)
    result = _DECIMAL_RE.sub(sub_decimal, result)
    result = _INTEGER_RE.sub(sub_integer, result)

    for idx, spoken in enumerate(slots):
        result = result.replace(_SLOT.format(idx), spoken)
    return result
