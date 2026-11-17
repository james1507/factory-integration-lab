"""Ingest tests. Run from env/:  python3 -m unittest discover -s tests -v"""
import os
import pathlib
import sys
import tempfile
import threading
import time
import unittest

ENV = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ENV / "tools" / "plant_sim"))

from broker import Broker, topic_matches  # noqa: E402
from publisher import Publisher  # noqa: E402

from ingest.config import Settings  # noqa: E402
from ingest.main import assign_lines, start  # noqa: E402
from ingest.store import ReadingStore  # noqa: E402


def write_ini(tmp, port, workers=1, lines="1,2,3"):
    path = os.path.join(tmp, "ingest.ini")
    with open(path, "w") as f:
        f.write("[broker]\nport = %d\nkeepalive = 10\nclean_session = false\n"
                "[ingest]\nplant = dus\nlines = %s\nworkers = %d\n"
                "[store]\npath = %s\n[backoff]\ninitial = 0.2\nmax = 5\n"
                % (port, lines, workers, os.path.join(tmp, "r.db")))
    return path


class UnitTests(unittest.TestCase):
    def test_assign_lines_round_robin(self):
        self.assertEqual(assign_lines([1, 2, 3], 2), [[1, 3], [2]])
        self.assertEqual(assign_lines([1, 2, 3], 3), [[1], [2], [3]])

    def test_store_ignores_redelivery(self):
        s = ReadingStore(os.path.join(tempfile.mkdtemp(), "r.db"))
        r = {"line": 1, "seq": 7, "temp_c": 65.0, "ts": 0}
        self.assertTrue(s.insert(r))
        self.assertFalse(s.insert(r))
        self.assertEqual(s.count(), 1)

    def test_topic_filters(self):
        self.assertTrue(topic_matches("plant/+/line/1/temp", "plant/dus/line/1/temp"))
        self.assertTrue(topic_matches("plant/#", "plant/dus/line/1/temp"))
        self.assertFalse(topic_matches("plant/dus/line/1/temp", "plant/dus/line/2/temp"))


class EndToEnd(unittest.TestCase):
    def test_single_worker_stores_all_lines(self):
        broker = Broker().start()
        tmp = tempfile.mkdtemp()
        settings = Settings(write_ini(tmp, broker.port, workers=1))
        stop = threading.Event()
        store, _ = start(settings, stop)
        time.sleep(0.3)
        pub = Publisher(broker.port, rate=50)
        pub.start()
        time.sleep(1)
        pub.stop()
        time.sleep(0.5)
        stop.set()
        broker.stop()
        self.assertGreaterEqual(store.count(), len(pub.sent) * 0.99)


if __name__ == "__main__":
    unittest.main()
