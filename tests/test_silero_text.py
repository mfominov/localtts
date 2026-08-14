#!/usr/bin/env python3
"""Helpers that keep Silero from crashing on junk fragments."""

from __future__ import annotations

import unittest

import pdf_to_audio as ltts


class SileroTextPrepTests(unittest.TestCase):
    def test_not_speakable_digits_and_punctuation(self) -> None:
        self.assertFalse(ltts.is_speakable_for_silero("1."))
        self.assertFalse(ltts.is_speakable_for_silero("9) 10."))
        self.assertFalse(ltts.is_speakable_for_silero("• · —"))
        self.assertFalse(ltts.is_speakable_for_silero("   "))

    def test_speakable_has_letters(self) -> None:
        self.assertTrue(ltts.is_speakable_for_silero("Важный абзац."))
        self.assertTrue(ltts.is_speakable_for_silero("Assume breach."))
        self.assertTrue(ltts.is_speakable_for_silero("• Human–Agent Experience."))

    def test_prepare_normalizes_bullets_and_dashes(self) -> None:
        cleaned = ltts.prepare_silero_text("• Human–Agent Experience.")
        self.assertNotIn("•", cleaned)
        self.assertNotIn("–", cleaned)
        self.assertIn("Human-Agent", cleaned)


if __name__ == "__main__":
    unittest.main()
