"""Send one signed test event the way Forgeline MES does.

Usage: python tools/send_test_event.py [operator] [--port 8081]
"""
import argparse
import hashlib
import hmac
import json
import os
import time
import urllib.error
import urllib.request
import uuid


def main():
    p = argparse.ArgumentParser()
    p.add_argument("operator", nargs="?", default="J. Becker")
    p.add_argument("--port", type=int, default=8081)
    args = p.parse_args()

    event = {
        "event_id": "evt_" + uuid.uuid4().hex[:12],
        "type": "work_order.updated",
        "plant": "DE-DUS",
        "work_order": "WO-88213",
        "status": "in_progress",
        "operator": args.operator,
        "notes": "",
    }
    body = json.dumps(event, ensure_ascii=False).encode("utf-8")
    ts = str(int(time.time()))
    secret = os.environ.get("MES_WEBHOOK_SECRET", "dev-secret").encode()
    sig = "sha256=" + hmac.new(secret, ts.encode() + b"." + body, hashlib.sha256).hexdigest()

    req = urllib.request.Request(
        "http://127.0.0.1:%d/webhooks/mes" % args.port,
        data=body,
        headers={"Content-Type": "application/json; charset=utf-8",
                 "X-MES-Timestamp": ts, "X-MES-Signature": sig},
    )
    try:
        with urllib.request.urlopen(req) as r:
            print(r.status, r.read().decode())
    except urllib.error.HTTPError as e:
        print(e.code, e.read().decode())


if __name__ == "__main__":
    main()
