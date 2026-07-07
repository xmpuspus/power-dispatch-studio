#!/usr/bin/env python3
"""Static file server with HTTP Range support, for local dev.

power-dispatch-studio serves plain GeoJSON/JSON, but the Range handler is kept so any large
binary asset added later streams with 206 Partial Content instead of the stdlib
SimpleHTTPRequestHandler's whole-file 200. Production hosts support ranges
natively; this only matters for `python3 serve.py` during dev.

    python3 serve.py [port]    # default 8789, serves this directory
"""

import os
import re
import sys
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8789


class RangeHandler(SimpleHTTPRequestHandler):
    def do_GET(self):
        rng = self.headers.get("Range")
        path = self.translate_path(self.path)
        m = re.match(r"bytes=(\d+)-(\d*)", rng or "")
        if m and os.path.isfile(path):
            size = os.path.getsize(path)
            start = int(m.group(1))
            end = int(m.group(2)) if m.group(2) else size - 1
            end = min(end, size - 1)
            if start > end:
                self.send_error(416)
                return
            self.send_response(206)
            self.send_header("Content-Type", self.guess_type(path))
            self.send_header("Accept-Ranges", "bytes")
            self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
            self.send_header("Content-Length", str(end - start + 1))
            self.end_headers()
            with open(path, "rb") as f:
                f.seek(start)
                self.wfile.write(f.read(end - start + 1))
            return
        super().do_GET()


if __name__ == "__main__":
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    print(f"serving {os.getcwd()} on http://localhost:{PORT} (Range-capable)")
    ThreadingHTTPServer(("127.0.0.1", PORT), RangeHandler).serve_forever()
