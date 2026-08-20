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

    def test_split_spaced_dash_not_hyphen(self) -> None:
        self.assertEqual(
            ltts.split_speech_clauses("PSLC AI-Disrupt PSLC - архитектура"),
            ["PSLC AI-Disrupt PSLC—", "архитектура"],
        )
        self.assertEqual(
            ltts.split_speech_clauses("Часть 1 — точка ROI"),
            ["Часть 1—", "точка ROI"],
        )
        # In-token hyphen must stay one clause
        self.assertEqual(
            ltts.split_speech_clauses("AI-Disrupt и GenAI"),
            ["AI-Disrupt и GenAI"],
        )

    def test_part_heading_number_stays_with_title_clause(self) -> None:
        self.assertEqual(
            ltts.split_speech_clauses("Часть 2. Архитектурное ядро PSLC."),
            ["Часть 2. Архитектурное ядро PSLC."],
        )

    def test_dotted_section_number_stays_one_clause(self) -> None:
        self.assertEqual(
            ltts.split_speech_clauses("1.3 Стоимость ошибки."),
            ["1.3 Стоимость ошибки."],
        )
        self.assertEqual(
            ltts.split_speech_clauses("порог 0.90 на тестах."),
            ["порог 0.90 на тестах."],
        )
        clauses = ltts.split_speech_clauses("1.3 Стоимость ошибки.")
        self.assertNotIn("1.", clauses)

    def test_orphan_punct_glues_or_drops(self) -> None:
        self.assertEqual(ltts.split_speech_clauses(", дальше."), ["дальше."])
        self.assertEqual(ltts.split_speech_clauses("."), [])
        self.assertEqual(
            ltts.split_speech_clauses("да, , нет."),
            ["да,", "нет."],
        )
        self.assertEqual(
            ltts.split_speech_clauses("ссылка). , дальше."),
            ["ссылка).", "дальше."],
        )
        glued = ltts.split_speech_clauses("слово,")
        self.assertEqual(glued, ["слово,"])
        self.assertTrue(ltts.is_punct_only_clause(","))
        self.assertTrue(ltts.is_punct_only_clause("."))
        self.assertTrue(ltts.is_punct_only_clause(":"))
        self.assertFalse(ltts.is_punct_only_clause("1."))
        self.assertFalse(ltts.is_punct_only_clause("16%"))

    def test_quote_trailing_comma_not_own_clause(self) -> None:
        segments = ltts.split_quote_segments("«цитата», дальше.")
        clauses: list[str] = []
        for text, _is_quote in segments:
            clauses.extend(ltts.split_speech_clauses(text))
        self.assertNotIn(",", clauses)
        self.assertTrue(any("цитата" in part for part in clauses))
        self.assertTrue(any(part.startswith("дальше") for part in clauses))

    def test_list_markers_become_ordinal_clause(self) -> None:
        clauses = ltts.split_speech_clauses(ltts.expand_numbered_list_markers("1. пункт два."))
        self.assertTrue(any("первое" in c for c in clauses))
        self.assertNotIn("1.", clauses)

    def test_pause_ms_mapping(self) -> None:
        pauses = ltts.SpeechPauses()
        self.assertEqual(ltts.pause_ms_after_text("да,", pauses), 150)
        self.assertEqual(ltts.pause_ms_after_text("да.", pauses), 400)
        self.assertEqual(ltts.pause_ms_after_text("да?", pauses), 400)
        self.assertEqual(ltts.pause_ms_after_text("да!", pauses), 400)
        self.assertEqual(ltts.pause_ms_after_text("да;", pauses), 250)
        self.assertEqual(ltts.pause_ms_after_text("да:", pauses), 250)
        self.assertEqual(ltts.pause_ms_after_text("PSLC—", pauses), 400)
        self.assertEqual(ltts.pause_ms_after_text("без знака", pauses), 0)
        self.assertEqual(
            ltts.pause_ms_between_clauses(
                "процентных пункта",
                "(статистически значимая разница)",
                pauses,
            ),
            280,
        )
        self.assertEqual(
            ltts.pause_ms_between_clauses(
                "(статистически значимая разница)",
                "дальше текст",
                pauses,
            ),
            280,
        )
        self.assertEqual(ltts.pause_ms_after_text("(ссылка)", pauses), 280)
        self.assertLess(pauses.paren_ms, pauses.dash_ms)

    def test_split_before_and_after_parens(self) -> None:
        self.assertEqual(
            ltts.split_speech_clauses("пункта (статистически значимая разница) дальше."),
            ["пункта", "(статистически значимая разница)", "дальше."],
        )
        self.assertEqual(
            ltts.split_speech_clauses("пункта (статистически значимая разница)."),
            ["пункта", "(статистически значимая разница)."],
        )

    def test_percent_before_dash_speakable_after_tts(self) -> None:
        text = "16% — слабая, 8% — никакой, 29% — не могут оценить"
        spoken = ltts.prepare_tts_spoken_text(text)
        self.assertIn("шестнадцать процентов", spoken)
        self.assertIn("восемь процентов", spoken)
        self.assertIn("двадцать девять процентов", spoken)
        for clause in ltts.split_speech_clauses(spoken):
            self.assertTrue(ltts.is_speakable_for_silero(clause), clause)

    def test_patterns_load_speech_section(self) -> None:
        patterns = ltts.load_cleaning_patterns(ltts.DEFAULT_PATTERNS_FILE)
        self.assertEqual(patterns.silero_chunk_chars, 300)
        self.assertEqual(patterns.speech_pauses.period_ms, 400)
        self.assertEqual(patterns.speech_pauses.comma_ms, 150)
        self.assertEqual(patterns.speech_pauses.dash_ms, 400)
        self.assertEqual(patterns.speech_pauses.paren_ms, 280)

    def test_chunk_limit_default(self) -> None:
        self.assertEqual(ltts.DEFAULT_SILERO_CHUNK_CHARS, 300)
        self.assertEqual(ltts.SILERO_MAX_CHARS, 300)


if __name__ == "__main__":
    unittest.main()
