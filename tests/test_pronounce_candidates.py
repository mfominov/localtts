#!/usr/bin/env python3
"""Tests for pronounce candidate extraction (ChatGPT offline workflow)."""

from __future__ import annotations

import tempfile
import unittest
from collections import Counter
from pathlib import Path

import pronounce_candidates as pc


class PronounceCandidatesTests(unittest.TestCase):
    def test_interesting_keeps_acronyms_and_versions(self) -> None:
        self.assertTrue(pc.is_interesting_candidate("MTTR"))
        self.assertTrue(pc.is_interesting_candidate("GPT-3.5"))
        self.assertTrue(pc.is_interesting_candidate("Dynatrace"))
        self.assertTrue(pc.is_interesting_candidate("R0-R5"))
        self.assertTrue(pc.is_interesting_candidate("Fast Follower"))
        self.assertFalse(pc.is_interesting_candidate("the"))
        self.assertFalse(pc.is_interesting_candidate("and"))
        self.assertFalse(pc.is_interesting_candidate("a"))

    def test_allcaps_acronym_kept_at_count_one(self) -> None:
        self.assertTrue(pc.is_allcaps_acronym("FAA"))
        self.assertTrue(pc.is_allcaps_acronym("NTSB"))
        self.assertFalse(pc.is_allcaps_acronym("Fast"))
        text = "Once FAA and once NTSB and FooBrand FooBrand"
        ranked = pc.rank_candidates(text, known_keys=set(), min_count=2)
        tokens = dict(ranked)
        self.assertEqual(tokens.get("FAA"), 1)
        self.assertEqual(tokens.get("NTSB"), 1)
        self.assertEqual(tokens.get("FooBrand"), 2)
        self.assertNotIn("Once", tokens)

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

    def test_title_bigram(self) -> None:
        text = "Fast Follower strategy and Fast Follower again"
        ranked = pc.rank_candidates(text, known_keys=set(), min_count=2)
        self.assertIn("Fast Follower", dict(ranked))

    def test_from_log_valueerror(self) -> None:
        log = (
            "Silero skip (ValueError) in chapter_002.aiff: 'ServiceNow,'\n"
            "Silero skip (ValueError) in chapter_002.aiff: 'context engineering'\n"
            "Silero skip (ValueError) in chapter_013.aiff: '//www.'\n"
            "Silero skip (not speakable) in chapter_001.aiff: '1.'\n"
        )
        counts = pc.collect_valueerror_counts(log)
        self.assertEqual(counts["ServiceNow"], 1)
        self.assertEqual(counts["context engineering"], 1)
        self.assertNotIn("//www.", counts)
        ranked = pc.rank_candidates("", known_keys=set(), min_count=2, extra_counts=counts)
        tokens = dict(ranked)
        self.assertEqual(tokens["ServiceNow"], 1)
        self.assertEqual(tokens["context engineering"], 1)

    def test_from_log_merged_with_min_one_via_extra_and_low_min(self) -> None:
        counts = Counter({"ServiceNow": 1, "Datadog": 1})
        ranked = pc.rank_candidates(
            "",
            known_keys={"datadog"},
            min_count=1,
            extra_counts=counts,
        )
        self.assertEqual(dict(ranked), {"ServiceNow": 1})

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
