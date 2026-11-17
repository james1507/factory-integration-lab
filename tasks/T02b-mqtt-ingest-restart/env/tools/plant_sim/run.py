"""Run a local plant edge: broker on 127.0.0.1:1883 plus simulated sensors for lines 1-3.

Usage (from env/):  python3 tools/plant_sim/run.py [--port 1883] [--rate 20]

Then start the ingest service against it in another terminal:
    python3 -m ingest.main --config config/ingest.ini
"""
import argparse
import logging
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from broker import Broker  # noqa: E402
from publisher import Publisher  # noqa: E402


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--port", type=int, default=1883)
    p.add_argument("--rate", type=float, default=20.0, help="readings per second per line")
    args = p.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")

    broker = Broker(port=args.port).start()
    pub = Publisher(broker.port, rate=args.rate)
    pub.start()
    try:
        while True:
            time.sleep(10)
            logging.getLogger("plant_sim").info("published=%d connects=%d", broker.stats["published"],
                                                broker.stats["connects"])
    except KeyboardInterrupt:
        pub.stop()
        broker.stop()


if __name__ == "__main__":
    main()
