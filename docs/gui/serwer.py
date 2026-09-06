"""Serve the GUI preview and its explicitly shared UI auditor on loopback only."""

from __future__ import annotations

import mimetypes
import pathlib
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import unquote

KATALOG = pathlib.Path(__file__).parent


class Serwer(BaseHTTPRequestHandler):
    """Read-only preview handler with a resolved filesystem boundary."""

    def log_message(self, *_args):
        """Keep the local preview quiet."""

    def do_GET(self):
        """Serve regular files in the preview root or the named shared auditor."""
        try:
            route = unquote(self.path.split("?", 1)[0])
            name = "index.html" if route == "/" else route.lstrip("/")
            root = KATALOG.resolve()
            if name == "audyt-ui.js":
                target = root.parent / "audyt-ui.js"
                allowed = not target.is_symlink()
            else:
                target = (root / name).resolve()
                allowed = target.is_relative_to(root)
            if not allowed or not target.is_file():
                self.send_response(404)
                self.end_headers()
                return
            content = target.read_bytes()
        except (OSError, ValueError, RuntimeError):
            self.send_response(404)
            self.end_headers()
            return
        content_type = mimetypes.guess_type(target.name)[0] or "application/octet-stream"
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Content-Length", str(len(content)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(content)


def main() -> None:
    """Start the local preview; importing this module never opens a socket."""
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8658
    print(f"GUI preview: http://localhost:{port}/")
    ThreadingHTTPServer(("127.0.0.1", port), Serwer).serve_forever()


if __name__ == "__main__":
    main()
