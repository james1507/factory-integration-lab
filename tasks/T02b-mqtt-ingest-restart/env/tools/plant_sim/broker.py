"""Plant edge broker simulator (MQTT-like), used for local reproduction and in CI.

Session semantics follow MQTT 3.1.1:
- A client id identifies a session. A CONNECT with a client id that is already
  connected takes the session over, and the older network connection is closed
  by the broker (MQTT-3.1.4-2).
- clean_session=false sessions keep their subscriptions, and queue matching
  messages while no connection is attached.
- Topic filters support "+" and "#".

Wire format: one JSON object per line, see README.md in this folder.
"""
import collections
import json
import logging
import socket
import socketserver
import threading

log = logging.getLogger("broker")


def topic_matches(flt, topic):
    f, t = flt.split("/"), topic.split("/")
    for i, part in enumerate(f):
        if part == "#":
            return True
        if i >= len(t) or (part != "+" and part != t[i]):
            return False
    return len(f) == len(t)


class Conn:
    def __init__(self, handler):
        self.handler = handler
        self.addr = "%s:%d" % handler.client_address
        self._wlock = threading.Lock()

    def send(self, obj):
        with self._wlock:
            self.handler.wfile.write((json.dumps(obj) + "\n").encode())
            self.handler.wfile.flush()

    def close(self):
        try:
            self.handler.connection.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass


class Session:
    def __init__(self, client_id, clean):
        self.client_id = client_id
        self.clean = clean
        self.subs = set()
        self.queue = collections.deque(maxlen=200000)
        self.conn = None


class Broker:
    def __init__(self, host="127.0.0.1", port=0):
        self.lock = threading.RLock()
        self.sessions = {}
        self.stats = collections.Counter()
        self.connects = []  # client ids, in CONNECT order
        self._mid = 0
        broker = self

        class Handler(socketserver.StreamRequestHandler):
            def handle(self):
                broker._serve(self)

        socketserver.ThreadingTCPServer.allow_reuse_address = True
        self.server = socketserver.ThreadingTCPServer((host, port), Handler)
        self.server.daemon_threads = True
        self.port = self.server.server_address[1]

    def start(self):
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        log.info("listening on 127.0.0.1:%d", self.port)
        return self

    def stop(self):
        self.server.shutdown()
        self.drop_all_connections()
        self.server.server_close()

    def drop_all_connections(self, except_ids=()):
        """Close client connections but keep sessions, like a load balancer failover."""
        with self.lock:
            for s in self.sessions.values():
                if s.conn and s.client_id not in except_ids:
                    old, s.conn = s.conn, None
                    old.close()
            self.stats["drops"] += 1

    def publish(self, topic, payload):
        with self.lock:
            self._mid += 1
            msg = {"op": "publish", "topic": topic, "payload": payload, "mid": self._mid}
            self.stats["published"] += 1
            for s in self.sessions.values():
                if not any(topic_matches(f, topic) for f in s.subs):
                    continue
                if s.conn:
                    try:
                        s.conn.send(msg)
                        continue
                    except OSError:
                        s.conn = None
                if not s.clean:
                    s.queue.append(msg)

    def _connect(self, conn, msg):
        cid, clean = msg["client_id"], bool(msg.get("clean_session", True))
        with self.lock:
            s = self.sessions.get(cid)
            if s and s.conn:
                log.warning("client_id=%s already connected from %s; taking over session for %s",
                            cid, s.conn.addr, conn.addr)
                self.stats["takeovers"] += 1
                old, s.conn = s.conn, None
                old.close()
            present = s is not None and not clean
            if s is None or clean:
                s = Session(cid, clean)
                self.sessions[cid] = s
            s.conn = conn
            self.connects.append(cid)
            self.stats["connects"] += 1
            conn.send({"op": "connack", "session_present": present})
            while s.queue:
                conn.send(s.queue.popleft())
        log.info("client_id=%s connected from %s session_present=%s", cid, conn.addr, present)
        return s

    def _serve(self, handler):
        conn, session = Conn(handler), None
        try:
            for line in handler.rfile:
                msg = json.loads(line)
                op = msg.get("op")
                if op == "connect":
                    session = self._connect(conn, msg)
                elif session is None:
                    break
                elif op == "subscribe":
                    with self.lock:
                        session.subs.add(msg["topic"])
                    conn.send({"op": "suback", "topic": msg["topic"]})
                elif op == "publish":
                    self.publish(msg["topic"], msg["payload"])
                elif op == "ping":
                    conn.send({"op": "pong"})
                elif op == "disconnect":
                    break
        except (OSError, ValueError):
            pass
        finally:
            with self.lock:
                if session and session.conn is conn:
                    session.conn = None
                    if session.clean:
                        self.sessions.pop(session.client_id, None)
            conn.close()
