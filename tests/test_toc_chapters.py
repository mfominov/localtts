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

    def test_default_chapters_sidecar_path(self) -> None:
        self.assertEqual(
            ltts.default_chapters_sidecar_path(Path("/tmp/book.pdf")),
            Path("/tmp/book.chapters.txt"),
        )


if __name__ == "__main__":
    unittest.main()
