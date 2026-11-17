"""Hidden grader for T02b. Run with CANDIDATE_DIR=<path to candidate env/>.

Starts the task's own (pristine) broker simulator, runs the candidate ingest
service against it with the candidate's config, publishes readings for lines
1-3, forces one broker-side connection drop mid-run, then restarts the
candidate process (a rolling deploy), and checks what landed in the
candidate's SQLite store.
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


RESTART_GAP_S = 0.3  # time between the old process exiting and the new one starting


class T02b(unittest.TestCase):
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

        log = open(os.path.join(cls.tmp, "ingest.log"), "w")

        def launch():
            before = cls.broker.stats["connects"]
            proc = subprocess.Popen([sys.executable, "-m", "ingest.main", "--config", ini], cwd=str(CANDIDATE),
                                    stdout=subprocess.DEVNULL, stderr=log)
            deadline = time.monotonic() + 5
            while time.monotonic() < deadline and cls.broker.stats["connects"] < before + 3:
                time.sleep(0.01)
            return proc

        def shutdown(proc):
            proc.terminate()
            try:
                proc.wait(5)
            except subprocess.TimeoutExpired:
                proc.kill()

        cls.proc = launch()
        time.sleep(0.5)

        cls.pub = Publisher(cls.broker.port, rate=RATE)
        cls.pub.start()
        time.sleep(3)
        cls.t_drop = time.monotonic()
        cls.broker.drop_all_connections(except_ids={PUBLISHER_ID})
        time.sleep(2)

        # rolling deploy: stop the service, short gap, start it again
        cls.t_term = time.monotonic()
        shutdown(cls.proc)
        time.sleep(RESTART_GAP_S)
        cls.proc = launch()
        cls.t_up = time.monotonic()
        time.sleep(2)

        cls.pub.stop()
        time.sleep(1.5)  # let queued readings drain
        shutdown(cls.proc)
        cls.broker.stop()

        db = sqlite3.connect(os.path.join(cls.tmp, "readings.db"))
        cls.stored = set(db.execute("SELECT line, seq FROM readings"))
        cls.sent = [(line, seq) for line, seq, _ in cls.pub.sent]
        cls.window = [(line, seq) for line, seq, t in cls.pub.sent if cls.t_drop + 0.02 <= t <= cls.t_drop + 0.6]
        cls.restart_window = [(line, seq) for line, seq, t in cls.pub.sent if cls.t_term + 0.05 <= t <= cls.t_up]
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
        # 3 workers connect at start, after the forced drop and after the restart: still 3 ids.
        self.assertLessEqual(len(self.ingest_ids), 3, "client ids must be stable across reconnects and restarts: %s"
                             % sorted(self.ingest_ids))

    def test_g6_no_loss_across_process_restart(self):
        self.assertGreater(len(self.restart_window), 50)
        self.assertGreaterEqual(self.ratio(self.restart_window), 0.99,
                                "readings published while ingest restarts must be queued and delivered "
                                "(%d of %d stored)" % (sum(1 for x in self.restart_window if x in self.stored),
                                                       len(self.restart_window)))


if __name__ == "__main__":
    unittest.main()
