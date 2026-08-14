#!/usr/bin/env python3
"""Unit tests for audiobook export helpers (no ffmpeg encode)."""

from __future__ import annotations

import unittest
from pathlib import Path

import pdf_to_audio as ltts


class AudiobookExportHelpersTests(unittest.TestCase):
    def test_ffmetadata_escape(self) -> None:
        self.assertEqual(ltts.ffmetadata_escape("a=b;c#d"), r"a\=b\;c\#d")

    def test_build_ffmetadata_chapter_timeline(self) -> None:
        meta = ltts.build_ffmetadata(
            title="Book=One",
            artist="Author",
            chapters=[("Intro", 1.5), ("Chapter 1", 2.0)],
        )
        self.assertIn(";FFMETADATA1", meta)
        self.assertIn(r"title=Book\=One", meta)
        self.assertIn("artist=Author", meta)
        self.assertIn("[CHAPTER]", meta)
        self.assertIn("START=0", meta)
        self.assertIn("END=1500", meta)
        self.assertIn("START=1500", meta)
        self.assertIn("END=3500", meta)
        self.assertIn("title=Intro", meta)
        self.assertIn("title=Chapter 1", meta)

    def test_default_book_title(self) -> None:
        self.assertEqual(
            ltts.default_book_title(Path("/tmp/My Doc.pdf"), Path("output_audio")),
            "My Doc",
        )
        self.assertEqual(
            ltts.default_book_title(None, Path("/tmp/output_audio")),
            "output_audio",
        )

    def test_concat_demuxer_line_escapes_quotes(self) -> None:
        line = ltts.concat_demuxer_line(Path("/tmp/it's fine.wav"))
        self.assertTrue(line.startswith("file '"))
        self.assertIn(r"'\''", line)


if __name__ == "__main__":
    unittest.main()
