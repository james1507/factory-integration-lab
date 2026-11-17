"""In-memory stand-in for the work_orders table."""
import hashlib
import threading


class WorkOrderStore:
    def __init__(self):
        self._lock = threading.Lock()
        self._seen = set()
        self.events = []

    def add(self, source, body, data):
        """Store an event once. Connectors retry, so dedup on the body hash."""
        key = hashlib.sha256(body).hexdigest()
        with self._lock:
            if key in self._seen:
                return False
            self._seen.add(key)
            self.events.append(dict(data, _source=source))
            return True


STORE = WorkOrderStore()
