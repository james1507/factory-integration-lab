"""Hidden grader for T01. Run with CANDIDATE_DIR=<path to candidate env/>.

    CANDIDATE_DIR=env python3 -m unittest -v grader/test_grader.py
"""
import hashlib
import hmac
import http.client
import importlib
import json
import os
import sys
import threading
import time
import unittest
import uuid
from http.server import ThreadingHTTPServer

SECRET = "grader-secret-7f3a"
os.environ["MES_WEBHOOK_SECRET"] = SECRET
os.environ["MES_WEBHOOK_TOLERANCE_S"] = "300"
sys.path.insert(0, os.path.abspath(os.environ.get("CANDIDATE_DIR", "env")))
app = importlib.import_module("service.mes_webhook")


def event(**over):
    e = {"event_id": "evt_grader_" + uuid.uuid4().hex[:12], "type": "work_order.updated",
         "plant": "DE-DUS", "work_order": "WO-1", "status": "in_progress",
         "operator": "J. Becker", "notes": ""}
    e.update(over)
    return e


def sign(body, ts=None, secret=SECRET):
    ts = str(int(time.time())) if ts is None else ts
    sig = "sha256=" + hmac.new(secret.encode(), ts.encode() + b"." + body, hashlib.sha256).hexdigest()
    return {"X-MES-Timestamp": ts, "X-MES-Signature": sig}


class T01(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.srv = ThreadingHTTPServer(("127.0.0.1", 0), app.Handler)
        threading.Thread(target=cls.srv.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()

    def post(self, body, headers):
        c = http.client.HTTPConnection("127.0.0.1", self.srv.server_address[1], timeout=5)
        c.request("POST", "/webhooks/mes", body=body,
                  headers=dict(headers, **{"Content-Type": "application/json; charset=utf-8"}))
        return c.getresponse().status

    def vendor_body(self, e):
        return json.dumps(e, ensure_ascii=False).encode("utf-8")

    def test_a1_ascii_accepted(self):
        b = self.vendor_body(event())
        self.assertEqual(self.post(b, sign(b)), 202)

    def test_a2_non_ascii_accepted_and_stored_intact(self):
        e = event(operator="Nguyễn Văn An", notes="chờ vật tư")
        b = self.vendor_body(e)
        self.assertEqual(self.post(b, sign(b)), 202)
        stored = [r for r in app.RECEIVED if r.get("event_id") == e["event_id"]]
        self.assertEqual(len(stored), 1)
        self.assertEqual(stored[0]["operator"], "Nguyễn Văn An")

    def test_a3_compact_json_accepted(self):
        b = json.dumps(event(operator="S. Müller"), ensure_ascii=False, separators=(",", ":")).encode()
        self.assertEqual(self.post(b, sign(b)), 202)

    def test_a4_tampered_body_rejected(self):
        b = self.vendor_body(event(status="in_progress"))
        h = sign(b)
        self.assertEqual(self.post(b.replace(b"in_progress", b"completed__"), h), 401)

    def test_a5_wrong_secret_rejected(self):
        b = self.vendor_body(event())
        self.assertEqual(self.post(b, sign(b, secret="dev-secret")), 401)

    def test_a6_stale_timestamp_rejected(self):
        b = self.vendor_body(event())
        self.assertEqual(self.post(b, sign(b, ts=str(int(time.time()) - 400))), 401)

    def test_a7_missing_signature_rejected(self):
        b = self.vendor_body(event())
        self.assertEqual(self.post(b, {"X-MES-Timestamp": str(int(time.time()))}), 401)


if __name__ == "__main__":
    unittest.main()
