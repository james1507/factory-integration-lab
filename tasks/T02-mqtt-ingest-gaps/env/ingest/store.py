"""Readings table (SQLite). Re-delivered readings are ignored by (line, seq)."""
import os
import sqlite3
import threading


class ReadingStore:
    def __init__(self, path):
        if os.path.dirname(path):
            os.makedirs(os.path.dirname(path), exist_ok=True)
        self._db = sqlite3.connect(path, check_same_thread=False, isolation_level=None)
        self._db.execute("PRAGMA journal_mode=WAL")
        self._db.execute("PRAGMA synchronous=OFF")
        self._db.execute("CREATE TABLE IF NOT EXISTS readings ("
                         "line INTEGER, seq INTEGER, temp_c REAL, ts REAL, PRIMARY KEY (line, seq))")
        self._lock = threading.Lock()

    def insert(self, r):
        with self._lock:
            cur = self._db.execute("INSERT OR IGNORE INTO readings VALUES (?, ?, ?, ?)",
                                   (r["line"], r["seq"], r["temp_c"], r["ts"]))
            return cur.rowcount == 1

    def count(self, line=None):
        with self._lock:
            if line is None:
                return self._db.execute("SELECT COUNT(*) FROM readings").fetchone()[0]
            return self._db.execute("SELECT COUNT(*) FROM readings WHERE line = ?", (line,)).fetchone()[0]
