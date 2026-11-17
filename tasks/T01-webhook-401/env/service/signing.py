"""Webhook authentication for each connector."""
import base64
import hashlib
import hmac
import time

from . import config


class AuthError(Exception):
    pass


def check_timestamp(ts_header):
    """Return the request age in seconds, or raise if it is too old."""
    try:
        ts = int(ts_header)
    except (TypeError, ValueError):
        raise AuthError("bad timestamp")
    skew = time.time() - ts
    if skew > config.TOLERANCE_S:
        raise AuthError("stale (skew=%ds)" % skew)
    return skew


def verify_mes(headers, body):
    """Forgeline MES: X-MES-Signature = "sha256=" + hex HMAC(secret, timestamp + "." + body)."""
    ts = headers.get("X-MES-Timestamp")
    skew = check_timestamp(ts)
    mac = hmac.new(config.MES_SECRET, ts.encode() + b"." + body, hashlib.sha256)
    if not hmac.compare_digest(headers.get("X-MES-Signature", ""), "sha256=" + mac.hexdigest()):
        raise AuthError("bad signature")
    return skew


def verify_erp(headers, body):
    """In-house ERP connector, see docs/erp-connector.md."""
    ts = headers.get("X-ERP-Request-Time")
    skew = check_timestamp(ts)
    mac = hmac.new(config.ERP_SECRET, body + ts.encode(), hashlib.sha256)
    if not hmac.compare_digest(headers.get("X-ERP-Signature", ""), base64.b64encode(mac.digest()).decode()):
        raise AuthError("bad signature")
    return skew
