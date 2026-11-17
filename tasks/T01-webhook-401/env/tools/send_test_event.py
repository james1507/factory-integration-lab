"""Replay a captured Forgeline MES webhook body against the local gateway, signed like Forgeline.

Usage: python3 tools/send_test_event.py [--file tools/samples/work_order_updated.json] [--port 8081]

The file is sent byte for byte, as captured from Forgeline's delivery log.
"""
import argparse
import hashlib
import hmac
import os
import pathlib
import time
import urllib.error
import urllib.request

HERE = pathlib.Path(__file__).resolve().parent


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--file", default=str(HERE / "samples" / "work_order_updated.json"))
    p.add_argument("--port", type=int, default=8081)
    args = p.parse_args()

    body = pathlib.Path(args.file).read_bytes().rstrip(b"\n")
    ts = str(int(time.time()))
    secret = os.environ.get("MES_WEBHOOK_SECRET", "dev-mes-secret").encode()
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
