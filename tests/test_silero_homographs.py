#!/usr/bin/env python3
"""Silero put_yo/put_accent config and homograph +stress overrides."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest import mock

import pdf_to_audio as ltts


class SileroHomographTests(unittest.TestCase):
    def test_patterns_load_silero_and_empty_homographs(self) -> None:
        patterns = ltts.load_cleaning_patterns(ltts.DEFAULT_PATTERNS_FILE)
        self.assertTrue(patterns.silero_put_yo)
        self.assertTrue(patterns.silero_put_accent)
        self.assertEqual(patterns.homographs, {})

    def test_homographs_after_pronounce(self) -> None:
        spoken = ltts.prepare_tts_spoken_text(
            "ROI и замок",
            {"ROI": "эр оу ай"},
            homographs={"замок": "зам+ок"},
        )
        self.assertIn("эр оу ай", spoken.casefold())
        self.assertIn("зам+ок", spoken)
        self.assertNotIn("замок", spoken.casefold().replace("зам+ок", ""))

    def test_without_homographs_keeps_surface(self) -> None:
        spoken = ltts.prepare_tts_spoken_text("старый замок", {})
        self.assertIn("замок", spoken)

    def test_custom_silero_flags_from_yaml(self) -> None:
        yaml_text = """
line_drop: []
inline_sub: []
silero:
  put_yo: false
  put_accent: false
homographs:
  мука: "м+ука"
skip_toc:
  enabled: false
"""
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "p.yml"
            path.write_text(yaml_text, encoding="utf-8")
            patterns = ltts.load_cleaning_patterns(path)
            self.assertFalse(patterns.silero_put_yo)
            self.assertFalse(patterns.silero_put_accent)
            self.assertEqual(patterns.homographs["мука"], "м+ука")

    def test_apply_tts_receives_put_flags(self) -> None:
        fake_audio = mock.Mock()
        fake_audio.__iter__ = lambda self: iter([])
        model = mock.Mock()
        # Return a tiny torch-like tensor via real torch if available.
        import torch

        model.apply_tts.return_value = torch.zeros(8)

        with (
            mock.patch.object(ltts, "load_silero_model", return_value=model),
            mock.patch.object(ltts, "write_wav_mono_f32"),
            mock.patch.object(ltts, "write_cues_sidecar"),
            mock.patch("subprocess.run"),
            tempfile.TemporaryDirectory() as tmp,
        ):
            out = Path(tmp) / "sample.aiff"
            ltts.synthesize_with_silero(
                "v5_ru",
                "xenia",
                24000,
                "Это замок на холме.",
                out,
                homographs={"замок": "зам+ок"},
                put_yo=False,
                put_accent=True,
            )
            kwargs = model.apply_tts.call_args.kwargs
            self.assertFalse(kwargs["put_yo"])
            self.assertTrue(kwargs["put_accent"])
            self.assertIn("зам+ок", kwargs["text"])


if __name__ == "__main__":
    unittest.main()
