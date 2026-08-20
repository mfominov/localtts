#!/usr/bin/env python3
"""Numbered list markers → neuter ordinals for Silero."""

from __future__ import annotations

import unittest

import pdf_to_audio as ltts


class NumberedListSpeechTests(unittest.TestCase):
    def test_list_marker_becomes_neuter_ordinal(self) -> None:
        spoken = ltts.prepare_tts_spoken_text(
            "1. Identify gaps Нахождение пробелов",
            {},
            normalize_numbers=False,
            ruaccent=False,
        )
        self.assertIn("первое", spoken)
        self.assertIn("Identify", spoken)
        self.assertNotRegex(spoken, r"(?<!\d)1\.(?=\s)")
        self.assertRegex(spoken, r"первое\s*—")

    def test_second_list_marker(self) -> None:
        spoken = ltts.prepare_tts_spoken_text(
            "2. Recommend improvements Диагностика",
            {},
            normalize_numbers=False,
            ruaccent=False,
        )
        self.assertIn("второе", spoken)
        self.assertRegex(spoken, r"второе\s*—")

    def test_section_heading_still_dot_words(self) -> None:
        spoken = ltts.prepare_tts_spoken_text(
            "1.3 Стоимость ошибки.",
            {},
            normalize_numbers=False,
            ruaccent=False,
        )
        self.assertIn("один точка три", spoken)
        self.assertNotIn("первое", spoken)

    def test_list_clause_is_speakable(self) -> None:
        spoken = ltts.prepare_tts_spoken_text(
            "1. пункт два.",
            {},
            normalize_numbers=False,
            ruaccent=False,
        )
        clauses = ltts.split_speech_clauses(spoken)
        self.assertTrue(any("первое" in c for c in clauses))
        self.assertNotIn("1.", clauses)
        for part in clauses:
            cleaned = ltts.prepare_silero_text(part)
            if cleaned:
                self.assertTrue(
                    ltts.is_speakable_for_silero(cleaned) or ltts.is_punct_only_clause(cleaned),
                    msg=repr(part),
                )


if __name__ == "__main__":
    unittest.main()
