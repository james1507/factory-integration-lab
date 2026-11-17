"""Generate env/logs/ingest.log for T02. Not shipped to the agent.

Every line is one the ingest service can actually print. Before the 2.4.0
rollout one worker stores all readings; after it, three workers share one
client id and take each other's broker session over in a loop.

Usage: python3 authoring/gen_logs.py [--churn 2.0] [--seed 11]
"""
import argparse
import datetime as dt
import pathlib
import random

RATE_PER_LINE = 5.0  # production sensor rate, readings/s/line


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--churn", type=float, default=2.0, help="logged reconnect events per second after rollout")
    p.add_argument("--seed", type=int, default=11)
    args = p.parse_args()
    rnd = random.Random(args.seed)

    start = dt.datetime(2026, 11, 16, 8, 0, 0)
    rollout = dt.datetime(2026, 11, 16, 9, 40, 12)
    end = dt.datetime(2026, 11, 16, 10, 45, 0)
    host = "mqtt.dus.plant.local:8883"
    events = []

    def at(t, msg):
        events.append((t, msg))

    at(start, "INFO ingest ingest 2.3.2 starting workers=1 lines=[1, 2, 3] broker=%s" % host)
    at(start + dt.timedelta(milliseconds=180), "INFO ingest.worker worker=0 connected lines=[1, 2, 3] session_present=True")
    at(rollout, "INFO ingest ingest 2.4.0 starting workers=3 lines=[1, 2, 3] broker=%s" % host)

    # stats every 10 s
    stored, t = 18_220_431, start + dt.timedelta(seconds=10)
    while t < end:
        if t < rollout:
            rate = 3 * RATE_PER_LINE * rnd.uniform(0.98, 1.02)
        else:
            # only the worker currently holding the session stores, and only its own line
            rate = RATE_PER_LINE * rnd.uniform(0.75, 1.15)
        stored += int(rate * 10)
        at(t, "INFO ingest stored=%d (+%.1f/s)" % (stored, rate))
        t += dt.timedelta(seconds=10)

    # takeover loop: each new connection kicks the previous holder, which reconnects 0.2 s later
    t, holder = rollout + dt.timedelta(milliseconds=150), None
    for w in range(3):
        at(t, "INFO ingest.worker worker=%d connected lines=[%d] session_present=%s" % (w, w + 1, w > 0))
        if holder is not None:
            at(t, "WARNING ingest.worker worker=%d connection lost (connection closed by broker); "
                  "reconnecting in 0.2s" % holder)
        holder = w
        t += dt.timedelta(milliseconds=rnd.randint(20, 60))
    while t < end:
        w = rnd.choice([x for x in range(3) if x != holder])
        t += dt.timedelta(seconds=rnd.expovariate(args.churn))
        at(t, "INFO ingest.worker worker=%d connected lines=[%d] session_present=True" % (w, w + 1))
        at(t + dt.timedelta(milliseconds=1), "WARNING ingest.worker worker=%d connection lost "
                                             "(connection closed by broker); reconnecting in 0.2s" % holder)
        holder = w

    events.sort(key=lambda e: e[0])
    out = ["%s,%03d %s" % (t.strftime("%Y-%m-%d %H:%M:%S"), t.microsecond // 1000, m) for t, m in events]
    dest = pathlib.Path(__file__).resolve().parent.parent / "env" / "logs" / "ingest.log"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text("\n".join(out) + "\n")
    print("wrote %d lines to %s" % (len(out), dest))


if __name__ == "__main__":
    main()
