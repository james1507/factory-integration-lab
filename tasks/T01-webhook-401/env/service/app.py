"""Integration gateway: receives connector webhooks and serves work-order state.

Run from env/:  python3 -m service.app   (PORT defaults to 8081)
"""
import json
import logging
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from . import middleware
from .handlers import erp, mes
from .store import STORE

log = logging.getLogger("gateway")

ROUTES = {
    "/webhooks/mes": mes.handle,
    "/webhooks/erp": erp.handle,
}


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/healthz":
            return self._reply(200, {"status": "ok"})
        if self.path == "/api/work-orders":
            return self._reply(200, {"count": len(STORE.events), "events": STORE.events[-50:]})
        return self._reply(404, {"error": "not found"})

    def do_POST(self):
        route = ROUTES.get(self.path)
        if route is None:
            return self._reply(404, {"error": "not found"})
        try:
            req = middleware.read_request(self)
        except middleware.BadRequest as exc:
            log.warning("bad request path=%s: %s", self.path, exc)
            return self._reply(400, {"error": str(exc)})
        code, body = route(req)
        return self._reply(code, body)

    def _reply(self, code, body):
        data = json.dumps(body).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *args):  # access log is noise; handlers log what matters
        pass


def serve(port):
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    log.info("listening on 127.0.0.1:%d", port)
    ThreadingHTTPServer(("127.0.0.1", port), Handler).serve_forever()


if __name__ == "__main__":
    serve(int(os.environ.get("PORT", "8081")))
