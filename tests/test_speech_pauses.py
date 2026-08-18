#!/usr/bin/env python3
"""Silero speech pauses and clause splitting."""

from __future__ import annotations

import unittest

import pdf_to_audio as ltts


class SpeechPausesTests(unittest.TestCase):
    def test_split_speech_clauses(self) -> None:
        self.assertEqual(
            ltts.split_speech_clauses("Привет, мир; ок: да. Нет!"),
            ["Привет,", "мир;", "ок:", "да.", "Нет!"],
        )

    def test_pause_ms_mapping(self) -> None:
        pauses = ltts.SpeechPauses()
        self.assertEqual(ltts.pause_ms_after_text("да,", pauses), 150)
        self.assertEqual(ltts.pause_ms_after_text("да.", pauses), 400)
        self.assertEqual(ltts.pause_ms_after_text("да?", pauses), 400)
        self.assertEqual(ltts.pause_ms_after_text("да!", pauses), 400)
        self.assertEqual(ltts.pause_ms_after_text("да;", pauses), 250)
        self.assertEqual(ltts.pause_ms_after_text("да:", pauses), 250)
        self.assertEqual(ltts.pause_ms_after_text("без знака", pauses), 0)

    def test_patterns_load_speech_section(self) -> None:
        patterns = ltts.load_cleaning_patterns(ltts.DEFAULT_PATTERNS_FILE)
        self.assertEqual(patterns.silero_chunk_chars, 300)
        self.assertEqual(patterns.speech_pauses.period_ms, 400)
        self.assertEqual(patterns.speech_pauses.comma_ms, 150)

    def test_chunk_limit_default(self) -> None:
        self.assertEqual(ltts.DEFAULT_SILERO_CHUNK_CHARS, 300)
        self.assertEqual(ltts.SILERO_MAX_CHARS, 300)


if __name__ == "__main__":
    unittest.main()
