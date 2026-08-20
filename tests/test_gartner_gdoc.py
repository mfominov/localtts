#!/usr/bin/env python3
"""Gartner GDOC ID normalization for TTS."""

from __future__ import annotations

import unittest

import pdf_to_audio as ltts
from pronounce_candidates import is_interesting_candidate


class GartnerGdocNormalizeTests(unittest.TestCase):
    def test_standalone_gdoc_becomes_gartner(self) -> None:
        self.assertEqual(
            ltts.normalize_gartner_gdoc("G00842943 вводит понятие invisible effort"),
            "Gartner вводит понятие invisible effort",
        )

    def test_standalone_gdoc_in_parens_keeps_metadata(self) -> None:
        self.assertEqual(
            ltts.normalize_gartner_gdoc("(G00845936, февраль 2026, n=671 сценариев)"),
            "(Gartner, февраль 2026, n=671 сценариев)",
        )

    def test_gartner_plus_gdoc_in_parens(self) -> None:
        self.assertEqual(
            ltts.normalize_gartner_gdoc("9 сценариев (Gartner G00845936)"),
            "9 сценариев (Gartner)",
        )

    def test_gartner_paren_gdoc_drops_id_keeps_authors(self) -> None:
        self.assertEqual(
            ltts.normalize_gartner_gdoc(
                "Gartner (G00851662, Милинд Говекар, Шивица Матур, 8 июня 2026)"
            ),
            "Gartner (Милинд Говекар, Шивица Матур, 8 июня 2026)",
        )

    def test_stats_citation_keeps_n(self) -> None:
        self.assertEqual(
            ltts.normalize_gartner_gdoc("29% — не могут оценить (n=144, Gartner G00835923)"),
            "29% — не могут оценить (n=144, Gartner)",
        )

    def test_semantic_context_preserved(self) -> None:
        self.assertEqual(
            ltts.normalize_gartner_gdoc(
                "53 процентных пункта (статистически значимая разница, Gartner G00835923)"
            ),
            "53 процентных пункта (статистически значимая разница, Gartner)",
        )

    def test_no_duplicate_gartner(self) -> None:
        self.assertEqual(ltts.normalize_gartner_gdoc("Gartner G00835923"), "Gartner")
        self.assertNotIn("Gartner Gartner", ltts.normalize_gartner_gdoc("Gartner G00835923"))

    def test_gdoc_not_pronounce_candidate(self) -> None:
        self.assertFalse(is_interesting_candidate("G00845936"))
        self.assertTrue(is_interesting_candidate("Gartner"))


if __name__ == "__main__":
    unittest.main()
