#!/usr/bin/env python3
"""Unit tests for TOC → chapters drafting helpers."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import pdf_to_audio as ltts


class TocChaptersTests(unittest.TestCase):
    def test_parse_toc_entry_line_leaders_and_trailing(self) -> None:
        self.assertEqual(
            ltts.parse_toc_entry_line("Глава 1. Архитектура .......... 12"),
            ("Глава 1. Архитектура", 12),
        )
        self.assertEqual(
            ltts.parse_toc_entry_line("Введение … 3"),
            ("Введение", 3),
        )
        self.assertEqual(
            ltts.parse_toc_entry_line("Приложения  стр. 90"),
            ("Приложения", 90),
        )
        self.assertEqual(
            ltts.parse_toc_entry_line("Часть 2  45"),
            ("Часть 2", 45),
        )
        self.assertIsNone(ltts.parse_toc_entry_line("Содержание"))
        self.assertIsNone(ltts.parse_toc_entry_line("12"))

    def test_parse_toc_entries_dedup_and_sort(self) -> None:
        text = "\n".join(
            [
                "Содержание",
                "Введение .......... 1",
                "Глава 1 .......... 10",
                "Глава 1 again ..... 10",
                "Глава 2 .......... 20",
            ]
        )
        entries = ltts.parse_toc_entries(text)
        self.assertEqual(
            entries,
            [
                ("Введение", 1),
                ("Глава 1", 10),
                ("Глава 2", 20),
            ],
        )

    def test_toc_entries_to_ranges(self) -> None:
        ranges = ltts.toc_entries_to_ranges(
            [("Intro", 1), ("Ch1", 5), ("Ch2", 10)],
            total_pages=12,
            start_idx=0,
            end_idx=12,
        )
        self.assertEqual(
            ranges,
            [
                ("Intro", 0, 4),
                ("Ch1", 4, 9),
                ("Ch2", 9, 12),
            ],
        )

    def test_write_and_roundtrip_chapters_file(self) -> None:
        ranges = [("Intro", 0, 4), ("Ch1", 4, 9)]
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "doc.chapters.txt"
            ltts.write_chapters_file(path, ranges)
            loaded = ltts.chapter_ranges_from_file(path, total_pages=9, start_idx=0, end_idx=9)
            self.assertEqual(loaded, ranges)

    def test_chapter_ranges_from_file_single_page(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "doc.chapters.txt"
            path.write_text(
                "\n".join(
                    [
                        "ЧАСТЬ 8|120-131",
                        "ЗАКЛЮЧЕНИЕ|132",
                        "ПРИЛОЖЕНИЕ А|134-136",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            loaded = ltts.chapter_ranges_from_file(path, total_pages=148, start_idx=0, end_idx=148)
            self.assertEqual(
                loaded,
                [
                    ("ЧАСТЬ 8", 119, 131),
                    ("ЗАКЛЮЧЕНИЕ", 131, 132),
                    ("ПРИЛОЖЕНИЕ А", 133, 136),
                ],
            )

    def test_default_chapters_sidecar_path(self) -> None:
        self.assertEqual(
            ltts.default_chapters_sidecar_path(Path("/tmp/book.pdf")),
            Path("/tmp/book.chapters.txt"),
        )

    def test_parse_toc_entry_line_rejects_years(self) -> None:
        self.assertIsNone(ltts.parse_toc_entry_line("Концепция · v1.25 · Июль 2026"))
        self.assertIsNone(ltts.parse_toc_entry_line("2.4 Сопровождение: горизонт 2030"))

    def test_parse_toc_entries_stacked_title_then_page(self) -> None:
        text = "\n".join(
            [
                "СОДЕРЖАНИЕ",
                "Оглавление",
                "6",
                "РЕЗЮМЕ ДЛЯ РУКОВОДСТВА",
                "6",
                "ЧАСТЬ 1. СОПРОВОЖДЕНИЕ",
                "10",
                "1.1 TCO портфеля",
                "11",
                "Footer · Концепция",
                "Footer · Концепция",
                "2",
                "Platform Team",
                "Footer · Концепция",
                "3",
                "34",
                "ЧАСТЬ 2. ЯДРО",
                "20",
            ]
        )
        entries = ltts.parse_toc_entries(text)
        self.assertEqual(
            entries,
            [
                ("РЕЗЮМЕ ДЛЯ РУКОВОДСТВА", 6),
                ("ЧАСТЬ 1. СОПРОВОЖДЕНИЕ", 10),
                ("1.1 TCO портфеля", 11),
                ("ЧАСТЬ 2. ЯДРО", 20),
                ("Platform Team", 34),
            ],
        )

    def test_parse_toc_entries_multiline_title_before_page(self) -> None:
        text = "\n".join(
            [
                "1.2 GenAI даёт 30–80% эффекта в зависимости от",
                "метрики и класса инцидента",
                "13",
                "1.3 Стоимость ошибки агента",
                "13",
            ]
        )
        entries = ltts.parse_toc_entries(text)
        self.assertEqual(
            entries,
            [
                (
                    "1.2 GenAI даёт 30–80% эффекта в зависимости от метрики и класса инцидента",
                    13,
                ),
            ],
        )

    def test_same_page_prefers_top_level_title(self) -> None:
        text = "\n".join(
            [
                "Что меняется для CIO",
                "10",
                "ЧАСТЬ 1. СОПРОВОЖДЕНИЕ — ТОЧКА ROI",
                "10",
                "1.1 Сопровождение поглощает TCO",
                "11",
                "ЧАСТЬ 2. АРХИТЕКТУРНОЕ ЯДРО",
                "20",
            ]
        )
        entries = ltts.parse_toc_entries(text)
        self.assertEqual(
            entries,
            [
                ("ЧАСТЬ 1. СОПРОВОЖДЕНИЕ — ТОЧКА ROI", 10),
                ("1.1 Сопровождение поглощает TCO", 11),
                ("ЧАСТЬ 2. АРХИТЕКТУРНОЕ ЯДРО", 20),
            ],
        )

    def test_select_chapter_toc_entries_keeps_top_level_only(self) -> None:
        selected = ltts.select_chapter_toc_entries(
            [
                ("РЕЗЮМЕ ДЛЯ РУКОВОДСТВА", 6),
                ("Петля надёжности", 7),
                ("ЧАСТЬ 1. СОПРОВОЖДЕНИЕ", 10),
                ("1.1 TCO", 11),
                ("ЧАСТЬ 8. РОССИЙСКИЙ КОНТЕКСТ", 120),
                ("ЗАКЛЮЧЕНИЕ", 132),
                ("ГЛОССАРИЙ", 137),
                ("Аббревиатуры и основные понятия", 138),
            ]
        )
        self.assertEqual(
            [title for title, _page in selected],
            [
                "РЕЗЮМЕ ДЛЯ РУКОВОДСТВА",
                "ЧАСТЬ 1. СОПРОВОЖДЕНИЕ",
                "ЧАСТЬ 8. РОССИЙСКИЙ КОНТЕКСТ",
                "ЗАКЛЮЧЕНИЕ",
                "ГЛОССАРИЙ",
            ],
        )


if __name__ == "__main__":
    unittest.main()
