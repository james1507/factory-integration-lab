"""Work-order events from Forgeline MES."""
import logging

from .. import signing
from ..store import STORE

log = logging.getLogger("mes_webhook")
REQUIRED = ("event_id", "type", "work_order")


def handle(req):
    data = req.data if isinstance(req.data, dict) else {}
    try:
        skew = signing.verify_mes(req.headers, req.body)
    except signing.AuthError as exc:
        if str(exc) == "bad signature":
            log.error("signature mismatch event_id=%s plant=%s", data.get("event_id"), data.get("plant"))
        else:
            log.error("rejected event_id=%s: %s", data.get("event_id"), exc)
        return 401, {"error": str(exc)}
    if skew > 1:
        log.warning("clock skew %.1fs plant=%s", skew, data.get("plant"))

    missing = [f for f in REQUIRED if f not in data]
    if missing:
        return 400, {"error": "missing " + ",".join(missing)}

    new = STORE.add("mes", req.body, data)
    log.info("accepted event_id=%s type=%s plant=%s", data["event_id"], data["type"], data.get("plant"))
    return 202, {"status": "accepted" if new else "duplicate"}
