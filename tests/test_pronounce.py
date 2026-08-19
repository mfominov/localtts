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
        self.assertIn("рои", spoken.casefold())
        self.assertIn("си ай оу", spoken.casefold())

    def test_pronounce_ear_batch_brands(self) -> None:
        text = (
            "MTTR и runbooks, CSS-лидеров, GenAI и AIOps, "
            "GPT-3.5 Qwen3 DeepSeek-V4, Dynatrace Davis AI-RCA, "
            "DigitalOcean SquareOps L1 Forrester Komodor IDE IDC, "
            "Hype Cycle и IT service desk, LLM-powered Zero-means-All, "
            "ROI и data quality Confidence threshold."
        )
        spoken = ltts.prepare_tts_spoken_text(text, self.patterns.pronounce)
        low = spoken.casefold()
        self.assertIn("эм ти ти ар", low)
        self.assertIn("ранбукс", low)
        self.assertIn("си эс эс", low)
        self.assertIn("дженэй", low)
        self.assertIn("эй ай опс", low)
        self.assertIn("джи пи ти три точка пять", low)
        self.assertIn("квен три", low)
        self.assertIn("дипсик ви четыре", low)
        self.assertIn("дайнатрейс", low)
        self.assertIn("эй ай ар си эй", low)
        self.assertIn("диджитал оушн", low)
        self.assertIn("хайп сайкл", low)
        self.assertIn("ай ти сервис деск", low)
        self.assertIn("рои", low)
        self.assertIn("дэйта", low)
        self.assertIn("квалити", low)

    def test_pronounce_runtime_otel_rag_governance(self) -> None:
        text = (
            "Уровни runtime R0-R5 и отдельно R3. "
            "OpenTelemetry и Board KPI scorecard. "
            "поисковый слой (RAG). "
            "Governance Mesh и Policy-As-Code guardrails."
        )
        spoken = ltts.prepare_tts_spoken_text(text, self.patterns.pronounce)
        low = spoken.casefold()
        self.assertIn("рантайм", low)
        self.assertIn("эр ноль — эр пять", low)
        self.assertNotIn("r0-r5", low)
        self.assertIn("эр три", low)
        self.assertIn("опен телеметри", low)
        self.assertIn("борд", low)
        self.assertIn("кей пи ай", low)
        self.assertIn("скоркад", low)
        self.assertIn("раг", low)
        self.assertIn("гавернанс", low)
        self.assertIn("меш", low)
        self.assertIn("полиси эс код", low)
        self.assertIn("гардрейлс", low)

    def test_pronounce_chatgpt_batch(self) -> None:
        text = (
            "HITL и HOOTL, MCP A2A, CSAT MTTA MTTD, "
            "R3+ R4+ R3-R4, SaaS DORA ITOps ITIL, "
            "CMDB SLI C.O.R.E IT+OT SPVM"
        )
        spoken = ltts.prepare_tts_spoken_text(text, self.patterns.pronounce)
        low = spoken.casefold()
        self.assertIn("эйч ай ти эл", low)
        self.assertIn("эйч оу оу ти эл", low)
        self.assertIn("эм си пи", low)
        self.assertIn("эй ту эй", low)
        self.assertIn("си сат", low)
        self.assertIn("эм ти ти эй", low)
        self.assertIn("эр три плюс", low)
        self.assertIn("сас", low)
        self.assertIn("дора", low)
        self.assertIn("айтил", low)
        self.assertIn("си эм ди би", low)
        self.assertIn("си оу ар и", low)
        self.assertIn("ай ти плюс оу ти", low)
        self.assertIn("эс пи ви эм", low)

    def test_pronounce_chatgpt_batch2(self) -> None:
        text = "SDD ADLC OWASP SIEM SOAR SDLC, GPT-5.6 vLLM OpenSSF MITRE, R2+ L4+ AG-UI JSONL x402"
        spoken = ltts.prepare_tts_spoken_text(text, self.patterns.pronounce)
        low = spoken.casefold()
        self.assertIn("эс ди ди", low)
        self.assertIn("эй ди эл си", low)
        self.assertIn("оу васп", low)
        self.assertIn("сим", low)
        self.assertIn("соар", low)
        self.assertIn("эс ди эл си", low)
        self.assertIn("джи пи ти пять точка шесть", low)
        self.assertIn("ви эл эл эм", low)
        self.assertIn("оупен эс эс эф", low)
        self.assertIn("майтер", low)
        self.assertIn("эр два плюс", low)
        self.assertIn("эл четыре плюс", low)
        self.assertIn("эй джи ю ай", low)
        self.assertIn("джейсон эл", low)
        self.assertIn("икс четыре ноль два", low)

    def test_pronounce_chatgpt_batch3(self) -> None:
        text = "FAA NTSB ChatGPT PaaS CAPEX OPEX GCP IBM NPS PII Qwen3-14B R1-R2"
        spoken = ltts.prepare_tts_spoken_text(text, self.patterns.pronounce)
        low = spoken.casefold()
        self.assertIn("эф эй эй", low)
        self.assertIn("эн ти эс би", low)
        self.assertIn("чат джи пи ти", low)
        self.assertIn("пас", low)
        self.assertIn("капекс", low)
        self.assertIn("опекс", low)
        self.assertIn("джи си пи", low)
        self.assertIn("ай би эм", low)
        self.assertIn("эн пи эс", low)
        self.assertIn("пи ай ай", low)
        self.assertIn("квен три четырнадцать би", low)
        self.assertIn("эр один эр два", low)

    def test_pronounce_chatgpt_batch4(self) -> None:
        text = "GDPR GPT-4 MFA mTLS SBOM CVE CWE B2B P0 P95 S3 VLAN ZT M1.5"
        spoken = ltts.prepare_tts_spoken_text(text, self.patterns.pronounce)
        low = spoken.casefold()
        self.assertIn("джи ди пи ар", low)
        self.assertIn("джи пи ти четыре", low)
        self.assertIn("эм эф эй", low)
        self.assertIn("эм ти эл эс", low)
        self.assertIn("эс бом", low)
        self.assertIn("си ви и", low)
        self.assertIn("си дабл-ю и", low)
        self.assertIn("би ту би", low)
        self.assertIn("пи ноль", low)
        self.assertIn("пи девяносто пять", low)
        self.assertIn("эс три", low)
        self.assertIn("ви лан", low)
        self.assertIn("зи ти", low)
        self.assertIn("эм один точка пять", low)

    def test_pronounce_valueerror_batch(self) -> None:
        text = (
            "ServiceNow Datadog Terraform Anthropic Gemini FinOps "
            "context engineering prompt injection Autonomy Architect "
            "Yandex Cloud YandexGPT GigaChat Qwen"
        )
        spoken = ltts.prepare_tts_spoken_text(text, self.patterns.pronounce)
        low = spoken.casefold()
        self.assertIn("сервис нау", low)
        self.assertIn("дэйтадог", low)
        self.assertIn("терраформ", low)
        self.assertIn("антропик", low)
        self.assertIn("джемини", low)
        self.assertIn("финопс", low)
        self.assertIn("контекст инжиниринг", low)
        self.assertIn("промпт инджекшн", low)
        self.assertIn("отономи архитэкт", low)
        self.assertIn("яндекс клауд", low)
        self.assertIn("яндекс джи пи ти", low)
        self.assertIn("гигачат", low)
        self.assertIn("квен", low)

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
