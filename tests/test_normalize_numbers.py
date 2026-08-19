#!/usr/bin/env python3
"""Golden tests for number / date / currency speech normalization."""

from __future__ import annotations

import unittest

import pdf_to_audio as ltts
from normalize_numbers import normalize_numbers_for_speech


class NormalizeNumbersTests(unittest.TestCase):
    def test_disabled_passthrough(self) -> None:
        self.assertEqual(normalize_numbers_for_speech("20%", enabled=False), "20%")

    def test_percent_inflection(self) -> None:
        cases = {
            "1%": "один процент",
            "2%": "два процента",
            "5%": "пять процентов",
            "21%": "двадцать один процент",
            "20%": "двадцать процентов",
        }
        for src, expected in cases.items():
            with self.subTest(src=src):
                self.assertEqual(normalize_numbers_for_speech(src), expected)

    def test_date(self) -> None:
        spoken = normalize_numbers_for_speech("с 01.01.2024 года")
        self.assertIn("первое января", spoken)
        self.assertIn("двадцать четвёртого года", spoken)
        self.assertNotIn("01.01.2024", spoken)

    def test_currency(self) -> None:
        self.assertIn("долларов США", normalize_numbers_for_speech("$100"))
        self.assertIn("сто", normalize_numbers_for_speech("$100"))
        rub = normalize_numbers_for_speech("₽1 500,50")
        self.assertIn("рубл", rub.casefold())
        self.assertIn("пятьсот", rub)
        self.assertIn("пятьдесят", rub)

    def test_numero(self) -> None:
        self.assertEqual(normalize_numbers_for_speech("акт №12"), "акт номер двенадцать")

    def test_integer_with_spaces(self) -> None:
        self.assertIn("тысяча", normalize_numbers_for_speech("всего 1 500 штук"))

    def test_does_not_break_letter_digit_tokens(self) -> None:
        self.assertEqual(normalize_numbers_for_speech("уровень R0"), "уровень R0")
        self.assertEqual(normalize_numbers_for_speech("R0-R5"), "R0-R5")

    def test_compare_ge_le(self) -> None:
        self.assertEqual(
            normalize_numbers_for_speech("порог ≥ 0,90"),
            "порог больше или равно ноль целых девять десятых",
        )
        self.assertEqual(
            normalize_numbers_for_speech("SLA <= 1,5"),
            "SLA меньше или равно одна целая пять десятых",
        )
        self.assertIn("больше или равно", normalize_numbers_for_speech("score >= 75"))

    def test_year_prep_case(self) -> None:
        k = normalize_numbers_for_speech("к 2028 году")
        self.assertEqual(k, "к две тысячи двадцать восьмому году")
        v = normalize_numbers_for_speech("в 2026 году")
        self.assertEqual(v, "в две тысячи двадцать шестом году")
        s = normalize_numbers_for_speech("с 2024 года")
        self.assertEqual(s, "с две тысячи двадцать четвёртого года")
        # Bare year still cardinal (no prep+год).
        self.assertIn("две тысячи", normalize_numbers_for_speech("год 2028"))

    def test_prepare_tts_order_section_then_pronounce_then_numbers(self) -> None:
        patterns = ltts.load_cleaning_patterns(ltts.DEFAULT_PATTERNS_FILE)
        text = "см. §3.2 и ROI 20% и GPT-3.5"
        spoken = ltts.prepare_tts_spoken_text(
            text,
            patterns.pronounce,
            normalize_numbers=patterns.normalize_numbers,
        )
        self.assertIn("три точка два", spoken)
        self.assertIn("рои", spoken.casefold())
        self.assertIn("двадцать процентов", spoken)
        self.assertIn("джи пи ти три точка пять", spoken.casefold())
        self.assertNotIn("20%", spoken)
        self.assertNotIn("§", spoken)
        # Must not turn §3.2 into a decimal fraction reading.
        self.assertNotIn("целых", spoken)


if __name__ == "__main__":
    unittest.main()
