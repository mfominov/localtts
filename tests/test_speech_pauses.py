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
