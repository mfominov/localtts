#!/usr/bin/env python3
"""Tests for pronounce candidate extraction (ChatGPT offline workflow)."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import pronounce_candidates as pc


class PronounceCandidatesTests(unittest.TestCase):
    def test_interesting_keeps_acronyms_and_versions(self) -> None:
        self.assertTrue(pc.is_interesting_candidate("MTTR"))
        self.assertTrue(pc.is_interesting_candidate("GPT-3.5"))
        self.assertTrue(pc.is_interesting_candidate("Dynatrace"))
        self.assertTrue(pc.is_interesting_candidate("R0-R5"))
        self.assertFalse(pc.is_interesting_candidate("the"))
        self.assertFalse(pc.is_interesting_candidate("and"))
        self.assertFalse(pc.is_interesting_candidate("a"))

    def test_rank_filters_known_and_min_count(self) -> None:
        text = "FooBrand FooBrand FooBrand BarTool BarTool OnceOnly ROI ROI ROI the the the the"
        ranked = pc.rank_candidates(
            text,
            known_keys={"roi"},
            min_count=2,
        )
        tokens = [t for t, _ in ranked]
        self.assertIn("FooBrand", tokens)
        self.assertIn("BarTool", tokens)
        self.assertNotIn("OnceOnly", tokens)
        self.assertNotIn("ROI", tokens)
        self.assertNotIn("the", tokens)
        foo_count = dict(ranked)["FooBrand"]
        self.assertEqual(foo_count, 3)

    def test_yaml_skeleton_and_prompt(self) -> None:
        candidates = [("FooBrand", 3), ("BarTool", 2)]
        yaml_text = pc.format_yaml_skeleton(candidates)
        self.assertIn("pronounce:", yaml_text)
        self.assertIn('FooBrand: ""', yaml_text)
        report = pc.format_report(candidates)
        self.assertIn("ChatGPT prompt", report)
        self.assertIn("letter-style", report)
        self.assertIn("FooBrand × 3", report)

    def test_cli_text_file(self) -> None:
        yaml_patterns = """
line_drop: []
inline_sub: []
pronounce:
  ROI: "рои"
skip_toc:
  enabled: false
"""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            patterns = root / "p.yml"
            patterns.write_text(yaml_patterns, encoding="utf-8")
            text_path = root / "chapter.txt"
            text_path.write_text(
                "NewAcme NewAcme and ROI ROI ROI filler NewAcme\n",
                encoding="utf-8",
            )
            code = pc.main(
                [
                    "--text",
                    str(text_path),
                    "--patterns-file",
                    str(patterns),
                    "--min-count",
                    "2",
                ]
            )
            self.assertEqual(code, 0)


if __name__ == "__main__":
    unittest.main()
