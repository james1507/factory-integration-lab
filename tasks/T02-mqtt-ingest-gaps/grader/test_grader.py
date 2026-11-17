"""Hidden grader for T02. Run with CANDIDATE_DIR=<path to candidate env/>.

Starts the task's own (pristine) broker simulator, runs the candidate ingest
service against it with the candidate's config, publishes readings for lines
1-3, forces one broker-side connection drop mid-run, then checks what landed
in the candidate's SQLite store.
"""
import configparser
import logging
import os
import pathlib
import sqlite3
import subprocess
import sys
import tempfile
import time
import unittest

TASK = pathlib.Path(__file__).resolve().parent.parent
CANDIDATE = pathlib.Path(os.environ.get("CANDIDATE_DIR", TASK / "env")).resolve()
sys.path.insert(0, str(TASK / "env" / "tools" / "plant_sim"))  # pristine broker, not the candidate's
from broker import Broker  # noqa: E402
from publisher import Publisher  # noqa: E402

PUBLISHER_ID = "plant-sim-sensors"
RATE = 100  # readings per second per line


class T02(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        logging.getLogger("broker").setLevel(logging.CRITICAL)
        cls.tmp = tempfile.mkdtemp(prefix="t02-grade-")
        cls.broker = Broker().start()

        cp = configparser.ConfigParser(inline_comment_prefixes=(";",))
        cp.read(CANDIDATE / "config" / "ingest.ini")
        cls.cfg_workers = cp.getint("ingest", "workers", fallback=1)
        cls.cfg_lines = cp.get("ingest", "lines", fallback="")
        cp["broker"]["port"] = str(cls.broker.port)
        cp["store"]["path"] = os.path.join(cls.tmp, "readings.db")
        ini = os.path.join(cls.tmp, "ingest.ini")
        with open(ini, "w") as f:
            cp.write(f)

        cls.proc = subprocess.Popen([sys.executable, "-m", "ingest.main", "--config", ini], cwd=str(CANDIDATE),
                                    stdout=subprocess.DEVNULL, stderr=open(os.path.join(cls.tmp, "ingest.log"), "w"))
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline and cls.broker.stats["connects"] < 3:
            time.sleep(0.05)
        time.sleep(0.5)

        cls.pub = Publisher(cls.broker.port, rate=RATE)
        cls.pub.start()
        time.sleep(3)
        cls.t_drop = time.monotonic()
        cls.broker.drop_all_connections(except_ids={PUBLISHER_ID})
        time.sleep(2)
        cls.pub.stop()
        time.sleep(1.5)  # let queued readings drain
        cls.proc.terminate()
        try:
            cls.proc.wait(5)
        except subprocess.TimeoutExpired:
            cls.proc.kill()
        cls.broker.stop()

        db = sqlite3.connect(os.path.join(cls.tmp, "readings.db"))
        cls.stored = set(db.execute("SELECT line, seq FROM readings"))
        cls.sent = [(line, seq) for line, seq, _ in cls.pub.sent]
        cls.window = [(line, seq) for line, seq, t in cls.pub.sent if cls.t_drop + 0.02 <= t <= cls.t_drop + 0.6]
        cls.ingest_ids = {c for c in cls.broker.connects if c != PUBLISHER_ID}

    def ratio(self, items):
        return sum(1 for x in items if x in self.stored) / max(1, len(items))

    def test_g1_all_readings_stored(self):
        self.assertGreaterEqual(self.ratio(self.sent), 0.99, "stored %d of %d" % (len(self.stored), len(self.sent)))

    def test_g2_no_session_takeovers(self):
        self.assertEqual(self.broker.stats["takeovers"], 0)

    def test_g3_no_loss_across_broker_connection_drop(self):
        self.assertGreaterEqual(self.ratio(self.window), 0.99,
                                "readings published right after the drop must be queued and delivered")

    def test_g4_three_workers_kept(self):
        self.assertEqual(self.cfg_workers, 3)
        self.assertEqual(self.cfg_lines.replace(" ", ""), "1,2,3")
        self.assertGreaterEqual(len(self.ingest_ids), 3, "expected one broker session per worker")

    def test_g5_reconnect_reuses_session(self):
        # 3 workers connect once, then once more after the forced drop.
        self.assertLessEqual(len(self.ingest_ids), 3, "client ids must be stable across reconnects: %s"
                             % sorted(self.ingest_ids))


if __name__ == "__main__":
    unittest.main()
