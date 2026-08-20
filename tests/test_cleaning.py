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

    def test_stacked_toc_page_detected_by_page_only_ratio(self) -> None:
        # Title and page number on separate lines (no dotted leaders).
        toc = "\n".join(
            [
                "СОДЕРЖАНИЕ",
                "РЕЗЮМЕ",
                "6",
                "ЧАСТЬ 1",
                "10",
                "1.1 Раздел",
                "11",
                "1.2 Раздел",
                "13",
                "ЧАСТЬ 2",
                "20",
                "2.1 Раздел",
                "21",
            ]
        )
        self.assertTrue(ltts.is_toc_page(toc, self.patterns))

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

    def test_collapse_allcaps_chapter_echo(self) -> None:
        self.assertEqual(
            ltts.collapse_allcaps_echo("ЧАСТЬ Часть 2. Архитектурное ядро PSLC"),
            "Часть 2. Архитектурное ядро PSLC",
        )
        self.assertEqual(
            ltts.collapse_allcaps_echo("РЕЗЮМЕ Резюме для руководства"),
            "Резюме для руководства",
        )
        # Different words must stay.
        self.assertEqual(
            ltts.collapse_allcaps_echo("PSLC Часть 2"),
            "PSLC Часть 2",
        )

    def test_detach_glued_section_heading(self) -> None:
        glued = (
            "1.4 ИИ не сокращает затраты — он перестраивает их структуру "
            "Распространённая управленческая ошибка — ждать."
        )
        detached = ltts.detach_glued_section_headings(glued)
        self.assertIn("структуру.", detached)
        self.assertIn(". Распространённая", detached)
        sentences = ltts.split_sentences(detached)
        self.assertGreaterEqual(len(sentences), 2)
        self.assertTrue(sentences[0].startswith("1.4"))
        self.assertTrue(sentences[1].startswith("Распространённая"))
        self.assertEqual(ltts.pause_ms_after_text(sentences[0], ltts.SpeechPauses()), 400)

    def test_detach_heading_after_latin_token(self) -> None:
        glued = (
            "1.3 Стоимость ошибки агента в производстве – на порядок выше "
            "стоимости ошибки в IDE Ошибка агента в разработке стоит одну итерацию."
        )
        detached = ltts.detach_glued_section_headings(glued)
        self.assertIn("IDE.", detached)
        self.assertIn(". Ошибка агента", detached)

    def test_subsection_pipeline_does_not_orphan_one(self) -> None:
        raw = (
            "1.3 Стоимость ошибки агента в производстве – на порядок выше "
            "стоимости ошибки в IDE Ошибка агента в разработке стоит одну итерацию."
        )
        text = ltts.polish_extracted_text(ltts.normalize_text(raw))
        clauses: list[str] = []
        for sentence in ltts.split_sentences(text):
            clauses.extend(ltts.split_speech_clauses(sentence))
        self.assertNotIn("1.", clauses)
        self.assertTrue(any(part.startswith("1.3") for part in clauses))

    def test_punctuate_table_rows_keeps_row_periods(self) -> None:
        raw = "\n".join(
            [
                "Барьер    Доля    Механика",
                "Ограничения бюджета    50%    Бизнес-кейс отвергается",
                "Интеграция ИИ    48%    Legacy без API",
            ]
        )
        marked = ltts.punctuate_table_rows(raw)
        self.assertIn("Барьер | Доля | Механика.", marked)
        self.assertIn("Ограничения бюджета | 50% | Бизнес-кейс отвергается.", marked)
        spoken = ltts.prepare_tts_spoken_text(ltts.normalize_text(raw))
        self.assertIn("пятьдесят процентов", spoken)
        self.assertIn(",", spoken)
        self.assertNotIn("|", spoken)
        sentences = ltts.split_sentences(ltts.normalize_text(raw))
        self.assertGreaterEqual(len(sentences), 3)


if __name__ == "__main__":
    unittest.main()
