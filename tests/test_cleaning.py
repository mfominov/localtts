#!/usr/bin/env python3
"""Inline fixtures for PDF cleaning patterns."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import pdf_to_audio as ltts


class CleaningPatternsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.patterns = ltts.load_cleaning_patterns(ltts.DEFAULT_PATTERNS_FILE)

    def test_drop_page_number_and_pdlc_footer_lines(self) -> None:
        raw = "\n".join(
            [
                "10",
                "Важный абзац про продукт.",
                "AI-Disrupt PDLC · Целевое видение 12",
                "Ещё один абзац.",
            ]
        )
        cleaned = ltts.strip_page_artifacts(raw, self.patterns)
        self.assertIn("Важный абзац про продукт.", cleaned)
        self.assertIn("Ещё один абзац.", cleaned)
        self.assertNotIn("Целевое видение", cleaned)
        self.assertNotRegex(cleaned, r"(?m)^\d{1,4}$")

    def test_inline_footer_and_orphan_page_number(self) -> None:
        cleaned = ltts.strip_inline_page_artifacts(
            "Конец главы. AI-Disrupt PDLC · Целевое видение 42",
            self.patterns,
        )
        self.assertEqual(cleaned, "Конец главы.")
        cleaned2 = ltts.strip_inline_page_artifacts("Фраза целиком 15", self.patterns)
        self.assertEqual(cleaned2, "Фраза целиком")

    def test_toc_page_detected(self) -> None:
        toc = "\n".join(
            [
                "Содержание",
                "1. Введение ........................ 3",
                "2. Архитектура ..................... 12",
                "3. Риски ........................... 20",
                "4. План ............................ 28",
                "5. Приложение ...................... 40",
            ]
        )
        self.assertTrue(ltts.is_toc_page(toc, self.patterns))

    def test_normal_page_not_toc(self) -> None:
        page = "\n".join(
            [
                "2.1 Обзор",
                "В этом разделе описаны основные компоненты системы.",
                "Каждый компонент отвечает за свой контур ответственности.",
                "Дальше разбираем поток данных между сервисами.",
                "Отдельно отметим ограничения текущего MVP.",
            ]
        )
        self.assertFalse(ltts.is_toc_page(page, self.patterns))

    def test_custom_patterns_file_override(self) -> None:
        yaml_text = """
line_drop:
  - pattern: '^DROP-ME$'
inline_sub: []
skip_toc:
  enabled: false
"""
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "custom.yml"
            path.write_text(yaml_text, encoding="utf-8")
            patterns = ltts.load_cleaning_patterns(path)
            cleaned = ltts.strip_page_artifacts("keep\nDROP-ME\nok", patterns)
            self.assertEqual(cleaned, "keep\nok")
            toc_sample = "Содержание\n1 .... 2\n3 .... 4\n5 .... 6\n7 .... 8"
            self.assertFalse(ltts.is_toc_page(toc_sample, patterns))


if __name__ == "__main__":
    unittest.main()
