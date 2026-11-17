"""Gateway webhook tests. Run from env/:  python3 -m unittest discover -s tests -v"""
import base64
import hashlib
import hmac
import http.client
import json
import os
import threading
import time
import unittest
import uuid
from http.server import ThreadingHTTPServer

os.environ.setdefault("MES_WEBHOOK_SECRET", "test-mes")
os.environ.setdefault("ERP_WEBHOOK_SECRET", "test-erp")

from service import app  # noqa: E402

MES, ERP = os.environ["MES_WEBHOOK_SECRET"].encode(), os.environ["ERP_WEBHOOK_SECRET"].encode()


class GatewayTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.srv = ThreadingHTTPServer(("127.0.0.1", 0), app.Handler)
        threading.Thread(target=cls.srv.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()

    def request(self, method, path, body=None, headers=None):
        c = http.client.HTTPConnection("127.0.0.1", self.srv.server_address[1], timeout=5)
        c.request(method, path, body=body, headers=headers or {})
        r = c.getresponse()
        return r.status, json.loads(r.read() or b"{}")

    def mes_post(self, event, secret=MES):
        body = json.dumps(event).encode()
        ts = str(int(time.time()))
        sig = "sha256=" + hmac.new(secret, ts.encode() + b"." + body, hashlib.sha256).hexdigest()
        return self.request("POST", "/webhooks/mes", body, {"X-MES-Timestamp": ts, "X-MES-Signature": sig})

    def erp_post(self, payload, secret=ERP):
        wire = json.dumps(payload, indent=2, ensure_ascii=False).replace("\n", "\r\n").encode()
        ts = str(int(time.time()))
        mac = hmac.new(secret, json.dumps(payload).encode() + ts.encode(), hashlib.sha256)
        return self.request("POST", "/webhooks/erp", wire,
                            {"X-ERP-Request-Time": ts, "X-ERP-Signature": base64.b64encode(mac.digest()).decode()})

    def mes_event(self):
        return {"event_id": "evt_" + uuid.uuid4().hex[:12], "type": "work_order.updated",
                "plant": "US-CLE", "work_order": "WO-1", "operator": "R. Patel", "notes": ""}

    def test_healthz(self):
        self.assertEqual(self.request("GET", "/healthz")[0], 200)

    def test_mes_event_accepted(self):
        self.assertEqual(self.mes_post(self.mes_event()), (202, {"status": "accepted"}))

    def test_mes_retry_is_deduplicated(self):
        e = self.mes_event()
        self.mes_post(e)
        self.assertEqual(self.mes_post(e), (202, {"status": "duplicate"}))

    def test_mes_wrong_secret_rejected(self):
        self.assertEqual(self.mes_post(self.mes_event(), secret=b"nope")[0], 401)

    def test_mes_missing_fields_rejected(self):
        e = self.mes_event()
        del e["work_order"]
        self.assertEqual(self.mes_post(e)[0], 400)

    def test_erp_pretty_printed_accepted(self):
        payload = {"doc_id": "SO-" + uuid.uuid4().hex[:6], "type": "sales_order.updated",
                   "customer": "Müller Antriebstechnik GmbH", "lines": 4}
        self.assertEqual(self.erp_post(payload)[0], 202)

    def test_erp_wrong_secret_rejected(self):
        self.assertEqual(self.erp_post({"doc_id": "SO-1", "type": "x"}, secret=b"nope")[0], 401)


if __name__ == "__main__":
    unittest.main()
