"""One ingest worker: owns a subset of lines, keeps a broker session, writes readings."""
import logging
import threading
import time

from . import mqtt_client

log = logging.getLogger("ingest.worker")


class Worker(threading.Thread):
    def __init__(self, index, lines, settings, store, stop_event):
        super().__init__(name="worker-%d" % index, daemon=True)
        self.index = index
        self.lines = set(lines)
        self.s = settings
        self.store = store
        self.stop_event = stop_event
        self.client_id = mqtt_client.default_client_id(settings.client_prefix)
        self.client = None

    def topics(self):
        return ["plant/%s/line/%d/temp" % (self.s.plant, line) for line in sorted(self.lines)]

    def run(self):
        delay = self.s.backoff_initial
        while not self.stop_event.is_set():
            self.client = mqtt_client.BrokerClient(self.s.host, self.s.port, self.client_id,
                                                   self.s.keepalive, self.s.clean_session)
            try:
                present = self.client.connect()
                for t in self.topics():
                    self.client.subscribe(t)
                log.info("worker=%d connected lines=%s session_present=%s",
                         self.index, sorted(self.lines), present)
                delay = self.s.backoff_initial
                for _topic, reading in self.client.messages():
                    self.handle(reading)
                    if self.stop_event.is_set():
                        break
            except (OSError, ConnectionError, ValueError) as exc:
                if self.stop_event.is_set():
                    break
                log.warning("worker=%d connection lost (%s); reconnecting in %.1fs", self.index, exc, delay)
                time.sleep(delay)
                delay = min(delay * 2, self.s.backoff_max)
            finally:
                self.client.close()

    def handle(self, reading):
        if reading.get("line") not in self.lines:
            # Another worker owns this line; it will store the reading.
            log.debug("worker=%d skipping reading for line %s", self.index, reading.get("line"))
            return
        self.store.insert(reading)
