#!/usr/bin/env python3
"""TTS pre-synth pronunciation helpers."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import pdf_to_audio as ltts


class PronounceHelpersTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.patterns = ltts.load_cleaning_patterns(ltts.DEFAULT_PATTERNS_FILE)

    def test_section_digits_to_words(self) -> None:
        spoken = ltts.expand_section_references("см. §3.2 и §5.2")
        self.assertEqual(spoken, "см. в разделе 3 точка 2 и в разделе 5 точка 2")
        words = ltts.expand_section_ref_digits_to_words(spoken)
        self.assertEqual(
            words,
            "см. в разделе три точка два и в разделе пять точка два",
        )

    def test_prepare_tts_keeps_ui_path_with_arabic(self) -> None:
        extracted = ltts.expand_section_references("Шкала (§4.2) и команда (§3.4).")
        display = ltts.section_refs_for_display(extracted)
        self.assertIn("§4.2", display)
        self.assertIn("§3.4", display)
        tts = ltts.prepare_tts_spoken_text(extracted, self.patterns.pronounce)
        self.assertIn("четыре точка два", tts)
        self.assertIn("три точка четыре", tts)
        self.assertNotIn("4 точка", tts)

    def test_pronounce_brands(self) -> None:
        text = "AI-DISRUPT PSLC и PDLC дают ROI для CIO"
        # Extract-time AI fix first (as in pipeline).
        text = ltts.apply_pronunciation_fixes(text, "эй ай", "и и")
        spoken = ltts.prepare_tts_spoken_text(text, self.patterns.pronounce)
        self.assertIn("дисрапт", spoken.casefold())
        self.assertIn("пи эс эл си", spoken.casefold())
        self.assertIn("пи ди эл си", spoken.casefold())
        self.assertIn("эр оу ай", spoken.casefold())
        self.assertIn("си ай оу", spoken.casefold())

    def test_pslc_footer_inline_stripped(self) -> None:
        raw = (
            "Потолки отчитываются от единственного канона; любое "
            "AI-DISRUPT PSLC · Концепция 136 упоминание золотой зоны."
        )
        cleaned = ltts.strip_inline_page_artifacts(raw, self.patterns)
        self.assertNotIn("Концепция 136", cleaned)
        self.assertNotIn("AI-DISRUPT", cleaned)
        self.assertIn("канона", cleaned)
        self.assertIn("упоминание", cleaned)

    def test_pslc_footer_line_dropped(self) -> None:
        page = "\n".join(
            [
                "AI-DISRUPT PSLC · Концепция",
                "136",
                "Нормальный абзац про агентов.",
            ]
        )
        cleaned = ltts.strip_page_artifacts(page, self.patterns)
        self.assertNotIn("Концепция", cleaned)
        self.assertIn("Нормальный абзац про агентов.", cleaned)

    def test_ai_ii_spoken_from_patterns(self) -> None:
        self.assertEqual(self.patterns.ai_spoken_as, "эй ай")
        self.assertEqual(self.patterns.ii_spoken_as, "и и")
        text = ltts.apply_pronunciation_fixes(
            "AI и ИИ вместе",
            self.patterns.ai_spoken_as,
            self.patterns.ii_spoken_as,
        )
        self.assertIn("эй ай", text)
        self.assertIn("и и", text)
        self.assertEqual(ltts.section_refs_for_display(text), "AI и ИИ вместе")

    def test_custom_ai_ii_from_yaml(self) -> None:
        yaml_text = """
line_drop: []
inline_sub: []
ai_spoken_as: "эй-ай"
ii_spoken_as: "и-и"
pronounce: {}
skip_toc:
  enabled: false
"""
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "p.yml"
            path.write_text(yaml_text, encoding="utf-8")
            patterns = ltts.load_cleaning_patterns(path)
            self.assertEqual(patterns.ai_spoken_as, "эй-ай")
            self.assertEqual(patterns.ii_spoken_as, "и-и")

    def test_custom_pronounce_override(self) -> None:
        yaml_text = """
line_drop: []
inline_sub: []
pronounce:
  PSLC: "пэ эс эл цэ"
skip_toc:
  enabled: false
"""
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "p.yml"
            path.write_text(yaml_text, encoding="utf-8")
            patterns = ltts.load_cleaning_patterns(path)
            spoken = ltts.apply_pronounce_map("док PSLC готов", patterns.pronounce)
            self.assertIn("пэ эс эл цэ", spoken)


if __name__ == "__main__":
    unittest.main()
