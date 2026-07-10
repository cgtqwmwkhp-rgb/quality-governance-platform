#!/usr/bin/env bash
# Celery beat entrypoint for Azure App Service / local Docker.
# Serves /healthz that is honest about the beat process (503 if beat PID dies).
set -euo pipefail

PORT="${WEBSITES_PORT:-8000}"
APP="src.infrastructure.tasks.celery_app.celery_app"
SCHEDULE_FILE="${CELERY_BEAT_SCHEDULE_FILE:-/tmp/celerybeat-schedule}"
PID_FILE="${CELERY_PID_FILE:-/tmp/celery-beat.pid}"

celery -A "${APP}" beat \
  --loglevel="${CELERY_LOG_LEVEL:-info}" \
  --schedule="${SCHEDULE_FILE}" &
CELERY_PID=$!
echo "${CELERY_PID}" > "${PID_FILE}"

python - <<PY &
import os
from http.server import BaseHTTPRequestHandler, HTTPServer

pid_file = "${PID_FILE}"
port = int("${PORT}")


def celery_alive() -> bool:
    try:
        with open(pid_file, encoding="utf-8") as fh:
            pid = int(fh.read().strip())
        os.kill(pid, 0)
        return True
    except (OSError, ValueError, FileNotFoundError):
        return False


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        path = self.path.split("?", 1)[0]
        if path not in ("/healthz", "/", "/readyz"):
            self.send_response(404)
            self.end_headers()
            return
        if celery_alive():
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"status":"ok","role":"beat","celery":"alive"}')
        else:
            self.send_response(503)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"status":"unhealthy","role":"beat","celery":"dead"}')

    def log_message(self, *_args):
        return


HTTPServer(("0.0.0.0", port), Handler).serve_forever()
PY
HEALTH_PID=$!

cleanup() {
  kill "${HEALTH_PID}" 2>/dev/null || true
  if kill -0 "${CELERY_PID}" 2>/dev/null; then
    kill -TERM "${CELERY_PID}" 2>/dev/null || true
    wait "${CELERY_PID}" 2>/dev/null || true
  fi
  rm -f "${PID_FILE}"
}
trap cleanup EXIT INT TERM

wait "${CELERY_PID}"
exit $?
