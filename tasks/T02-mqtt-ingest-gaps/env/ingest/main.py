"""Sensor ingest service: python3 -m ingest.main --config config/ingest.ini"""
import argparse
import logging
import signal
import threading
import time

from . import __version__
from .config import Settings
from .store import ReadingStore
from .worker import Worker

log = logging.getLogger("ingest")
STATS_EVERY_S = 10


def assign_lines(lines, workers):
    """Round-robin lines over workers: [1,2,3] over 2 workers -> [[1,3],[2]]."""
    return [lines[i::workers] for i in range(workers)]


def start(settings, stop_event):
    store = ReadingStore(settings.db_path)
    workers = [Worker(i, owned, settings, store, stop_event)
               for i, owned in enumerate(assign_lines(settings.lines, settings.workers)) if owned]
    for w in workers:
        w.start()
    return store, workers


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--config", default="config/ingest.ini")
    args = p.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    settings = Settings(args.config)

    stop = threading.Event()
    signal.signal(signal.SIGTERM, lambda *_: stop.set())
    log.info("ingest %s starting workers=%d lines=%s broker=%s:%d",
             __version__, settings.workers, settings.lines, settings.host, settings.port)
    store, _ = start(settings, stop)
    last = 0
    try:
        while not stop.wait(STATS_EVERY_S):
            n = store.count()
            log.info("stored=%d (+%.1f/s)", n, (n - last) / STATS_EVERY_S)
            last = n
    except KeyboardInterrupt:
        stop.set()


if __name__ == "__main__":
    main()
