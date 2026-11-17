"""Request body handling shared by every endpoint."""
import json

from . import config


class BadRequest(Exception):
    pass


class Request:
    def __init__(self, path, headers, body, data):
        self.path = path
        self.headers = headers
        self.body = body  # normalised JSON bytes
        self.data = data  # parsed JSON


def read_request(handler):
    length = int(handler.headers.get("Content-Length", 0))
    if length > config.MAX_BODY_BYTES:
        raise BadRequest("body too large")
    raw = handler.rfile.read(length)
    if not raw:
        return Request(handler.path, handler.headers, b"", None)
    try:
        data = json.loads(raw)
    except ValueError as exc:
        raise BadRequest("invalid JSON: %s" % exc)

    # Connectors send pretty-printed JSON with CRLFs (ERP) or compact JSON (MES).
    # Re-encode once so signature checks, dedup hashes and audit logs all see one form.
    body = json.dumps(data).encode()
    return Request(handler.path, handler.headers, body, data)
