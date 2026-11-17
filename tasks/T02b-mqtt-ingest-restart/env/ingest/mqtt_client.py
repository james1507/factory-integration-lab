"""Minimal client for the plant broker (see tools/plant_sim/README.md for the wire format)."""
import json
import os
import socket


def default_client_id(prefix):
    # One stable id per ingest process, so the broker keeps our session (and
    # queues readings) across reconnects when clean_session is false.
    return "%s-%s-%d" % (prefix, socket.gethostname(), os.getpid())


class BrokerClient:
    def __init__(self, host, port, client_id, keepalive=60, clean_session=False):
        self.addr = (host, port)
        self.client_id = client_id
        self.keepalive = keepalive
        self.clean_session = clean_session
        self._sock = None
        self._f = None

    def connect(self):
        """Open the connection and return session_present from the CONNACK."""
        self._sock = socket.create_connection(self.addr, timeout=5)
        self._sock.settimeout(self.keepalive)
        self._f = self._sock.makefile("rwb")
        self._send({"op": "connect", "client_id": self.client_id,
                    "clean_session": self.clean_session, "keepalive": self.keepalive})
        ack = self._read()
        if ack.get("op") != "connack":
            raise ConnectionError("expected connack, got %r" % ack)
        return ack["session_present"]

    def subscribe(self, topic):
        self._send({"op": "subscribe", "topic": topic})

    def messages(self):
        """Yield publish payloads until the connection ends."""
        while True:
            try:
                msg = self._read()
            except socket.timeout:
                self._send({"op": "ping"})
                continue
            if msg.get("op") == "publish":
                yield msg["topic"], msg["payload"]

    def close(self):
        if self._sock:
            try:
                self._send({"op": "disconnect"})
            except OSError:
                pass
            self._sock.close()

    def _send(self, obj):
        self._f.write((json.dumps(obj) + "\n").encode())
        self._f.flush()

    def _read(self):
        line = self._f.readline()
        if not line:
            raise ConnectionError("connection closed by broker")
        return json.loads(line)
