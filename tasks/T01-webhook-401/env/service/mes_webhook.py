"""Receives work-order webhooks from the MES vendor (Forgeline MES) and stores them.

Runs as `python -m service.mes_webhook` from the env/ directory.
"""
import hashlib
import hmac
import json
import logging
import os
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

SECRET = os.environ.get("MES_WEBHOOK_SECRET", "dev-secret").encode()
TOLERANCE_S = int(os.environ.get("MES_WEBHOOK_TOLERANCE_S", "300"))

log = logging.getLogger("mes_webhook")

# Stand-in for the work_orders table.
RECEIVED = []


def expected_signature(timestamp, body):
    mac = hmac.new(SECRET, timestamp.encode() + b"." + body, hashlib.sha256)
    return "sha256=" + mac.hexdigest()


def parse_event(raw):
    event = json.loads(raw)
    if "event_id" not in event or "type" not in event:
        raise ValueError("missing event_id/type")
    return event


class Handler(BaseHTTPRequestHandler):
    def do_POST(self):
        if self.path != "/webhooks/mes":
            return self._reply(404, {"error": "not found"})

        raw = self.rfile.read(int(self.headers.get("Content-Length", 0)))
        try:
            event = parse_event(raw)
        except ValueError as exc:
            log.warning("bad payload: %s", exc)
            return self._reply(400, {"error": "bad payload"})

        ts = self.headers.get("X-MES-Timestamp", "")
        sig = self.headers.get("X-MES-Signature", "")
        try:
            skew = abs(time.time() - float(ts))
        except ValueError:
            return self._reply(401, {"error": "bad timestamp"})
        if skew > 1:
            log.warning("clock skew %.1fs plant=%s", skew, event.get("plant"))
        if skew > TOLERANCE_S:
            log.error("stale webhook event_id=%s skew=%.0fs", event["event_id"], skew)
            return self._reply(401, {"error": "stale"})

        # Normalise before verifying so whitespace differences from the vendor don't matter.
        canonical = json.dumps(event).encode()
        if not hmac.compare_digest(sig, expected_signature(ts, canonical)):
            log.error("signature mismatch event_id=%s plant=%s", event["event_id"], event.get("plant"))
            return self._reply(401, {"error": "bad signature"})

        RECEIVED.append(event)
        log.info("accepted event_id=%s type=%s plant=%s", event["event_id"], event["type"], event.get("plant"))
        return self._reply(202, {"status": "accepted"})

    def _reply(self, code, body):
        data = json.dumps(body).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *args):  # silence default access log
        pass


def serve(port=8081):
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    ThreadingHTTPServer(("127.0.0.1", port), Handler).serve_forever()


if __name__ == "__main__":
    serve(int(os.environ.get("PORT", "8081")))
