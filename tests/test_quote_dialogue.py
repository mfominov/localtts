#!/usr/bin/env python3
"""Silero quote dialogue segmentation."""

from __future__ import annotations

import unittest

import pdf_to_audio as ltts


class QuoteDialogueTests(unittest.TestCase):
    def test_split_guillemets(self) -> None:
        segs = ltts.split_quote_segments("Он сказал: «Добрый день.» и ушёл.")
        self.assertEqual(
            segs,
            [("Он сказал:", False), ("Добрый день.", True), ("и ушёл.", False)],
        )

    def test_split_curly_and_straight(self) -> None:
        self.assertEqual(
            ltts.split_quote_segments('Слово “да” и "нет".'),
            [("Слово", False), ("да", True), ("и", False), ("нет", True), (".", False)],
        )

    def test_no_quotes(self) -> None:
        self.assertEqual(ltts.split_quote_segments("Просто текст."), [("Просто текст.", False)])

    def test_patterns_load_dialogue(self) -> None:
        patterns = ltts.load_cleaning_patterns(ltts.DEFAULT_PATTERNS_FILE)
        self.assertEqual(patterns.speech_dialogue.quote_before_ms, 280)
        self.assertEqual(patterns.speech_dialogue.quote_after_ms, 180)


if __name__ == "__main__":
    unittest.main()
