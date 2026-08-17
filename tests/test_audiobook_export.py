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

    def test_parse_ffmpeg_progress_and_out_time(self) -> None:
        # Realistic ffmpeg -progress block: out_time_ms is microseconds (misnomer).
        fields = ltts.parse_ffmpeg_progress_fields(
            "\n".join(
                [
                    "out_time_ms=125000000",
                    "out_time_us=125000000",
                    "out_time=00:02:05.000000",
                    "progress=continue",
                ]
            )
        )
        self.assertEqual(fields["progress"], "continue")
        self.assertEqual(ltts.ffmpeg_out_time_seconds(fields), 125.0)

        # Prefer out_time_us over a wrong out_time_ms interpretation.
        us_only = ltts.parse_ffmpeg_progress_fields(
            "out_time_ms=125000000\nout_time_us=125000000\nprogress=continue"
        )
        self.assertEqual(ltts.ffmpeg_out_time_seconds(us_only), 125.0)

        # Ignore misnamed out_time_ms when us/out_time absent (would be 1000x off).
        ms_only = ltts.parse_ffmpeg_progress_fields("out_time_ms=125000000\nprogress=continue")
        self.assertIsNone(ltts.ffmpeg_out_time_seconds(ms_only))

        fields2 = ltts.parse_ffmpeg_progress_fields("out_time=01:02:03.5\nprogress=end")
        self.assertAlmostEqual(ltts.ffmpeg_out_time_seconds(fields2) or 0, 3723.5)

    def test_format_export_progress_lines(self) -> None:
        self.assertEqual(
            ltts.format_export_phase_line("cover", 1.2, 3.0),
            "cover  +1s  elapsed 3s",
        )
        self.assertEqual(
            ltts.format_export_encode_line(12.4, 200.0, 45.0),
            "encode 12%  out 3m20s  elapsed 45s",
        )

    def test_should_emit_encode_progress_throttle(self) -> None:
        self.assertTrue(
            ltts.should_emit_encode_progress(
                last_percent=None,
                last_emit_at=None,
                percent=0.0,
                now=0.0,
            )
        )
        self.assertFalse(
            ltts.should_emit_encode_progress(
                last_percent=10.0,
                last_emit_at=100.0,
                percent=12.0,
                now=101.0,
            )
        )
        self.assertTrue(
            ltts.should_emit_encode_progress(
                last_percent=10.0,
                last_emit_at=100.0,
                percent=15.0,
                now=101.0,
            )
        )
        self.assertTrue(
            ltts.should_emit_encode_progress(
                last_percent=10.0,
                last_emit_at=100.0,
                percent=11.0,
                now=102.0,
            )
        )


if __name__ == "__main__":
    unittest.main()
