#!/usr/bin/env python3
"""Unit tests for conversion progress formatters."""

from __future__ import annotations

import unittest

import pdf_to_audio as ltts


class ProgressFormatTests(unittest.TestCase):
    def test_format_duration_seconds_minutes_hours(self) -> None:
        self.assertEqual(ltts.format_duration(0), "0s")
        self.assertEqual(ltts.format_duration(12.4), "12s")
        self.assertEqual(ltts.format_duration(74), "1m14s")
        self.assertEqual(ltts.format_duration(134), "2m14s")
        self.assertEqual(ltts.format_duration(3725), "1h02m")

    def test_format_job_progress_line(self) -> None:
        line = ltts.format_job_progress_line(
            3,
            12,
            "chapter_003_demo.aiff",
            134.2,
            481.0,
        )
        self.assertEqual(
            line,
            "[3/12] chapter_003_demo.aiff  +2m14s  elapsed 8m01s",
        )


if __name__ == "__main__":
    unittest.main()
