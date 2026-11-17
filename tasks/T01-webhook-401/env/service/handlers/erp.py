"""Sales-order and material events from the in-house ERP connector."""
import logging

from .. import signing
from ..store import STORE

log = logging.getLogger("erp_webhook")
REQUIRED = ("doc_id", "type")


def handle(req):
    data = req.data if isinstance(req.data, dict) else {}
    try:
        signing.verify_erp(req.headers, req.body)
    except signing.AuthError as exc:
        log.error("rejected doc_id=%s: %s", data.get("doc_id"), exc)
        return 401, {"error": str(exc)}

    missing = [f for f in REQUIRED if f not in data]
    if missing:
        return 400, {"error": "missing " + ",".join(missing)}

    new = STORE.add("erp", req.body, data)
    log.info("accepted doc_id=%s type=%s", data["doc_id"], data["type"])
    return 202, {"status": "accepted" if new else "duplicate"}
