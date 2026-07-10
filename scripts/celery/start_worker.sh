#!/usr/bin/env bash
# Celery worker entrypoint for Azure App Service / local Docker.
# Serves a minimal /healthz on WEBSITES_PORT (default 8000) so App Service
# liveness probes succeed while the worker process drains Redis queues.
set -euo pipefail

PORT="${WEBSITES_PORT:-8000}"
QUEUES="${CELERY_QUEUES:-default,email,notifications,reports,cleanup}"
CONCURRENCY="${CELERY_CONCURRENCY:-2}"
APP="src.infrastructure.tasks.celery_app.celery_app"

python - <<PY &
from http.server import BaseHTTPRequestHandler, HTTPServer

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path.split("?", 1)[0] in ("/healthz", "/", "/readyz"):
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(b"ok")
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, *_args):
        return

HTTPServer(("0.0.0.0", int("${PORT}")), Handler).serve_forever()
PY
HEALTH_PID=$!

cleanup() {
  kill "${HEALTH_PID}" 2>/dev/null || true
}
trap cleanup EXIT

exec celery -A "${APP}" worker \
  --loglevel="${CELERY_LOG_LEVEL:-info}" \
  --queues="${QUEUES}" \
  --concurrency="${CONCURRENCY}" \
  --prefetch-multiplier=1
