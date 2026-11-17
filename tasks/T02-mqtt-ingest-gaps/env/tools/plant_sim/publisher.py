"""Simulated line sensors: publish one temperature reading per line every 1/rate seconds."""
import json
import random
import socket
import threading
import time


class Publisher(threading.Thread):
    def __init__(self, port, lines=(1, 2, 3), rate=100.0, host="127.0.0.1", plant="dus"):
        super().__init__(daemon=True)
        self.addr, self.lines, self.rate, self.plant = (host, port), lines, rate, plant
        self.stop_event = threading.Event()
        self.sent = []  # (line, seq, monotonic time of publish)

    def run(self):
        sock = socket.create_connection(self.addr)
        f = sock.makefile("rwb")
        f.write(b'{"op": "connect", "client_id": "plant-sim-sensors", "clean_session": true}\n')
        f.flush()
        f.readline()  # connack
        rnd, seq = random.Random(1), 0
        nxt = time.monotonic()
        while not self.stop_event.is_set():
            seq += 1
            for line in self.lines:
                reading = {"line": line, "seq": seq, "temp_c": round(rnd.uniform(61, 74), 2), "ts": time.time()}
                topic = "plant/%s/line/%d/temp" % (self.plant, line)
                f.write((json.dumps({"op": "publish", "topic": topic, "payload": reading}) + "\n").encode())
                self.sent.append((line, seq, time.monotonic()))
            f.flush()
            nxt += 1.0 / self.rate
            time.sleep(max(0.0, nxt - time.monotonic()))
        f.write(b'{"op": "disconnect"}\n')
        f.flush()
        sock.close()

    def stop(self):
        self.stop_event.set()
        self.join(5)
