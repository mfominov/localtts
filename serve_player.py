#!/usr/bin/env python3
"""Tiny static server for the LocalTTS browser player.

Supports HTTP Range requests so the browser can seek inside large WAV files.
Also suppresses BrokenPipe/ConnectionReset noise on aborted downloads.
"""

from __future__ import annotations

import argparse
import contextlib
import os
import re
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

RANGE_RE = re.compile(r"bytes=(\d*)-(\d*)")


class QuietHandler(SimpleHTTPRequestHandler):
    extensions_map = {
        **getattr(SimpleHTTPRequestHandler, "extensions_map", {}),
        ".wav": "audio/wav",
        ".m4a": "audio/mp4",
        ".mp3": "audio/mpeg",
        ".json": "application/json; charset=utf-8",
        ".html": "text/html; charset=utf-8",
        ".txt": "text/plain; charset=utf-8",
    }

    protocol_version = "HTTP/1.1"

    def do_GET(self) -> None:  # type: ignore[override]
        # Browsers often probe /favicon.ico even when an SVG icon is declared.
        if self.path.split("?", 1)[0] in {"/favicon.ico", "/favicon.ico/"}:
            svg_path = Path(self.translate_path("/favicon.svg"))
            if svg_path.is_file():
                self.path = "/favicon.svg"
            else:
                self.send_response(204)
                self.end_headers()
                return
        super().do_GET()

    def end_headers(self) -> None:  # type: ignore[override]
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Cache-Control", "no-cache")
        super().end_headers()

    def copyfile(self, source, outputfile):  # type: ignore[override]
        with contextlib.suppress(BrokenPipeError, ConnectionResetError):
            super().copyfile(source, outputfile)

    def log_message(self, format: str, *args) -> None:  # noqa: A003
        message = format % args
        if "Broken pipe" in message or "Connection reset" in message:
            return
        super().log_message(format, *args)

    def handle_one_request(self) -> None:  # type: ignore[override]
        with contextlib.suppress(BrokenPipeError, ConnectionResetError):
            super().handle_one_request()

    def finish(self) -> None:  # type: ignore[override]
        with contextlib.suppress(BrokenPipeError, ConnectionResetError):
            super().finish()

    def send_head(self):  # type: ignore[override]
        path = self.translate_path(self.path)
        if os.path.isdir(path):
            return super().send_head()
        if not os.path.isfile(path):
            self.send_error(404, "File not found")
            return None

        try:
            # Handler returns the file; BaseHTTPRequestHandler closes it after copy.
            file_obj = open(path, "rb")  # noqa: SIM115
        except OSError:
            self.send_error(404, "File not found")
            return None

        try:
            fs = os.fstat(file_obj.fileno())
            file_size = fs.st_size
            content_type = self.guess_type(path)
            range_header = self.headers.get("Range")

            if not range_header:
                self.send_response(200)
                self.send_header("Content-Type", content_type)
                self.send_header("Content-Length", str(file_size))
                self.send_header("Last-Modified", self.date_time_string(fs.st_mtime))
                self.end_headers()
                return file_obj

            match = RANGE_RE.fullmatch(range_header.strip())
            if not match:
                file_obj.close()
                self.send_error(400, "Invalid Range")
                return None

            start_s, end_s = match.groups()
            start = int(start_s) if start_s else 0
            end = int(end_s) if end_s else file_size - 1
            if start >= file_size or end >= file_size or start > end:
                file_obj.close()
                self.send_error(416, "Requested Range Not Satisfiable")
                return None

            length = end - start + 1
            file_obj.seek(start)
            self.send_response(206)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Range", f"bytes {start}-{end}/{file_size}")
            self.send_header("Content-Length", str(length))
            self.send_header("Last-Modified", self.date_time_string(fs.st_mtime))
            self.end_headers()

            # Wrap so copyfile only streams the requested slice.
            return _RangedReader(file_obj, length)
        except Exception:
            file_obj.close()
            raise


class _RangedReader:
    def __init__(self, file_obj, remaining: int) -> None:
        self._file = file_obj
        self._remaining = remaining

    def read(self, size: int = -1) -> bytes:
        if self._remaining <= 0:
            return b""
        size = self._remaining if size is None or size < 0 else min(size, self._remaining)
        data = self._file.read(size)
        self._remaining -= len(data)
        return data

    def close(self) -> None:
        self._file.close()


def main() -> int:
    parser = argparse.ArgumentParser(description="Serve LocalTTS player directory.")
    parser.add_argument("--directory", type=Path, required=True)
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--bind", default="127.0.0.1")
    args = parser.parse_args()

    directory = args.directory.resolve()
    if not directory.is_dir():
        raise SystemExit(f"Directory not found: {directory}")

    handler = partial(QuietHandler, directory=str(directory))
    server = ThreadingHTTPServer((args.bind, args.port), handler)
    print(f"Serving {directory}")
    print(f"Open http://{args.bind}:{args.port}/player.html")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
