"""Load config/ingest.ini into a flat settings object."""
import configparser


class Settings:
    def __init__(self, path):
        cp = configparser.ConfigParser(inline_comment_prefixes=(";",))
        if not cp.read(path):
            raise FileNotFoundError(path)
        b, i = cp["broker"], cp["ingest"]
        self.host = b.get("host", "127.0.0.1")
        self.port = b.getint("port", 1883)
        self.client_prefix = b.get("client_prefix", "ingest")
        self.keepalive = b.getint("keepalive", 60)
        self.clean_session = b.getboolean("clean_session", False)
        self.plant = i.get("plant")
        self.lines = [int(x) for x in i.get("lines").split(",")]
        self.workers = i.getint("workers", 1)
        self.db_path = cp["store"].get("path")
        self.backoff_initial = cp["backoff"].getfloat("initial", 0.2)
        self.backoff_max = cp["backoff"].getfloat("max", 5.0)
