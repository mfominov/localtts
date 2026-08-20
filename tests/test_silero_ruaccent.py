#!/usr/bin/env python3
"""Silero ruaccent config and spoken-text order (homographs win)."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest import mock

import pdf_to_audio as ltts


class SileroRuaccentTests(unittest.TestCase):
    def test_default_patterns_enable_ruaccent(self) -> None:
        patterns = ltts.load_cleaning_patterns(ltts.DEFAULT_PATTERNS_FILE)
        self.assertTrue(patterns.silero_ruaccent)
        self.assertEqual(patterns.silero_ruaccent_model, "turbo3.1")

    def test_yaml_can_disable_ruaccent(self) -> None:
        yaml_text = """
line_drop: []
inline_sub: []
silero:
  put_yo: true
  put_accent: true
  ruaccent: false
  ruaccent_model: tiny2.1
homographs: {}
skip_toc:
  enabled: false
"""
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "p.yml"
            path.write_text(yaml_text, encoding="utf-8")
            patterns = ltts.load_cleaning_patterns(path)
            self.assertFalse(patterns.silero_ruaccent)
            self.assertEqual(patterns.silero_ruaccent_model, "tiny2.1")

    def test_ruaccent_runs_before_homographs(self) -> None:
        def fake_ruaccent(text: str, **_kwargs: object) -> str:
            return text.replace("замок", "з+амок")

        with mock.patch.object(ltts, "apply_ruaccent", side_effect=fake_ruaccent) as mocked:
            spoken = ltts.prepare_tts_spoken_text(
                "старый замок",
                {},
                ruaccent=True,
                ruaccent_model="turbo3.1",
                homographs={"замок": "зам+ок"},
            )
            mocked.assert_called_once()
            kwargs = mocked.call_args.kwargs
            self.assertEqual(kwargs.get("custom_dict"), {"замок": "зам+ок"})
            self.assertEqual(kwargs.get("model_size"), "turbo3.1")
            self.assertIn("зам+ок", spoken)
            self.assertNotIn("з+амок", spoken)

    def test_ruaccent_opt_out_skips_call(self) -> None:
        with mock.patch.object(ltts, "apply_ruaccent") as mocked:
            spoken = ltts.prepare_tts_spoken_text("старый замок", {}, ruaccent=False)
            mocked.assert_not_called()
            self.assertIn("замок", spoken)

    def test_chunk_long_text_for_ruaccent(self) -> None:
        parts = ltts._chunk_text_for_ruaccent("слово " * 500, max_chars=100)
        self.assertGreater(len(parts), 1)
        self.assertTrue(all(len(p) <= 100 or " " not in p for p in parts))

    def test_long_unpunctuated_ruaccent_does_not_crash(self) -> None:
        # ~2.5k+ chars without periods used to blow BERT (2048); chunking must keep it alive.
        text = "замок мука дверь окно стол книга " * 100
        out = ltts.apply_ruaccent(text)
        self.assertIsInstance(out, str)
        self.assertGreater(len(out), 100)

    def test_ruaccent_onnx_failure_falls_back(self) -> None:
        accentizer = mock.Mock()
        accentizer.process_all.side_effect = RuntimeError("onnx boom")

        with mock.patch.object(ltts, "_get_ruaccentizer", return_value=accentizer):
            # Reset any live singleton so reload stays on the mock.
            ltts._ruaccentizer = None
            ltts._ruaccentizer_key = None
            out = ltts.apply_ruaccent("короткий текст")
        self.assertEqual(out, "короткий текст")
        accentizer.process_all.assert_called()

        accentizer = mock.Mock()
        accentizer.process_all.return_value = "зам+ок"

        with mock.patch.object(ltts, "_get_ruaccentizer", return_value=accentizer) as get_acc:
            out = ltts.apply_ruaccent(
                "замок",
                model_size="turbo3.1",
                custom_dict={"замок": "зам+ок"},
            )
            get_acc.assert_called_once_with("turbo3.1", {"замок": "зам+ок"})
            accentizer.process_all.assert_called_once_with("замок")
            self.assertEqual(out, "зам+ок")


if __name__ == "__main__":
    unittest.main()
