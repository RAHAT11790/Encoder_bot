"""
Hugging Face Spaces (Docker SDK) expects the container to be listening on
a port (7860 by default) -- it uses that to decide whether the Space
"started" successfully. This bot is a Telegram bot with no web UI of its
own, so this just runs a tiny background HTTP server that responds with a
simple status page, purely to satisfy that requirement. It has nothing to
do with the bot's actual functionality.
"""

import os
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer


class _HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/plain")
        self.end_headers()
        self.wfile.write(b"VideoEncoder bot is running.")

    def log_message(self, format, *args):
        pass  # keep this out of the bot's own logs


def start_health_server():
    port = int(os.environ.get("PORT", 7860))
    server = HTTPServer(("0.0.0.0", port), _HealthHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server
