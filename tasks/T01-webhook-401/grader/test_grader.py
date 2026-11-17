"""Hidden grader for T01. Run with CANDIDATE_DIR=<path to candidate env/>.

    CANDIDATE_DIR=env python3 -m unittest -v grader/test_grader.py
"""
import base64
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

MES_SECRET, ERP_SECRET = "grader-mes-7f3a", "grader-erp-91c2"
os.environ["MES_WEBHOOK_SECRET"] = MES_SECRET
os.environ["ERP_WEBHOOK_SECRET"] = ERP_SECRET
os.environ["WEBHOOK_TOLERANCE_S"] = "300"
sys.path.insert(0, os.path.abspath(os.environ.get("CANDIDATE_DIR", "env")))
app = importlib.import_module("service.app")
store = importlib.import_module("service.store")


def mes_event(**over):
    e = {"event_id": "evt_grader_" + uuid.uuid4().hex[:12], "type": "work_order.updated",
         "plant": "DE-DUS", "work_order": "WO-1", "status": "in_progress",
         "operator": "J. Becker", "notes": ""}
    e.update(over)
    return e


def mes_headers(body, ts=None, secret=MES_SECRET):
    ts = str(int(time.time())) if ts is None else ts
    sig = "sha256=" + hmac.new(secret.encode(), ts.encode() + b"." + body, hashlib.sha256).hexdigest()
    return {"X-MES-Timestamp": ts, "X-MES-Signature": sig}


def erp_request(payload, secret=ERP_SECRET):
    """Wire: pretty-printed, CRLF, UTF-8. Signature: over json.dumps(payload) + ts (docs/erp-connector.md)."""
    wire = json.dumps(payload, indent=2, ensure_ascii=False).replace("\n", "\r\n").encode()
    ts = str(int(time.time()))
    mac = hmac.new(secret.encode(), json.dumps(payload).encode() + ts.encode(), hashlib.sha256)
    return wire, {"X-ERP-Request-Time": ts, "X-ERP-Signature": base64.b64encode(mac.digest()).decode()}


class T01(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.srv = ThreadingHTTPServer(("127.0.0.1", 0), app.Handler)
        threading.Thread(target=cls.srv.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()

    def post(self, path, body, headers):
        c = http.client.HTTPConnection("127.0.0.1", self.srv.server_address[1], timeout=5)
        c.request("POST", path, body=body,
                  headers=dict(headers, **{"Content-Type": "application/json; charset=utf-8"}))
        return c.getresponse().status

    def vendor_body(self, e):
        return json.dumps(e, ensure_ascii=False).encode("utf-8")

    def test_a1_ascii_accepted(self):
        b = self.vendor_body(mes_event())
        self.assertEqual(self.post("/webhooks/mes", b, mes_headers(b)), 202)

    def test_a2_non_ascii_accepted_and_stored_intact(self):
        e = mes_event(operator="Nguyễn Văn An", notes="chờ vật tư")
        b = self.vendor_body(e)
        self.assertEqual(self.post("/webhooks/mes", b, mes_headers(b)), 202)
        stored = [r for r in store.STORE.events if r.get("event_id") == e["event_id"]]
        self.assertEqual(len(stored), 1)
        self.assertEqual(stored[0]["operator"], "Nguyễn Văn An")

    def test_a3_compact_json_accepted(self):
        b = json.dumps(mes_event(operator="S. Müller"), ensure_ascii=False, separators=(",", ":")).encode()
        self.assertEqual(self.post("/webhooks/mes", b, mes_headers(b)), 202)

    def test_a4_tampered_body_rejected(self):
        b = self.vendor_body(mes_event(status="in_progress"))
        h = mes_headers(b)
        self.assertEqual(self.post("/webhooks/mes", b.replace(b"in_progress", b"completed__"), h), 401)

    def test_a5_wrong_secret_rejected(self):
        b = self.vendor_body(mes_event())
        self.assertEqual(self.post("/webhooks/mes", b, mes_headers(b, secret="dev-mes-secret")), 401)

    def test_a6_stale_timestamp_rejected(self):
        b = self.vendor_body(mes_event())
        self.assertEqual(self.post("/webhooks/mes", b, mes_headers(b, ts=str(int(time.time()) - 400))), 401)

    def test_a7_missing_signature_rejected(self):
        b = self.vendor_body(mes_event())
        self.assertEqual(self.post("/webhooks/mes", b, {"X-MES-Timestamp": str(int(time.time()))}), 401)

    def test_a8_erp_non_ascii_pretty_printed_accepted(self):
        wire, h = erp_request({"doc_id": "SO-" + uuid.uuid4().hex[:6], "type": "sales_order.updated",
                               "customer": "Müller Antriebstechnik GmbH", "lines": 4})
        self.assertEqual(self.post("/webhooks/erp", wire, h), 202)

    def test_a9_erp_wrong_secret_rejected(self):
        wire, h = erp_request({"doc_id": "SO-1", "type": "sales_order.updated"}, secret="dev-erp-secret")
        self.assertEqual(self.post("/webhooks/erp", wire, h), 401)


if __name__ == "__main__":
    unittest.main()
