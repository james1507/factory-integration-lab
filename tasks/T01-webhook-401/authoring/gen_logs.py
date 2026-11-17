"""Generate env/logs/mes-webhook.log for T01. Not shipped to the agent.

Deterministic for a given --seed. Calibration knobs: --lines (log volume),
--noise (share of unrelated lines), --skew-herring (VN-BD clock skew warnings).

Usage: python authoring/gen_logs.py [--lines 3000] [--noise 0.35] [--seed 7]
"""
import argparse
import datetime as dt
import pathlib
import random

PLANTS = {
    # plant: operators (some have non-ASCII names; those events fail after 1.8.0)
    "US-CLE": ["M. Johnson", "R. Patel", "K. Smith"],
    "DE-DUS": ["J. Becker", "S. Müller", "A. Schäfer", "T. Wagner"],
    "VN-BD": ["Nguyễn Văn An", "Tran Minh", "Lê Thị Hoa", "Pham Quoc"],
    "PL-WRO": ["Łukasz Nowak", "P. Kowalski", "M. Zieliński"],
    "MX-MTY": ["J. García", "L. Torres", "A. Ramos"],
}
NOTES = ["", "", "", "spindle temp ok", "tool change", "chờ vật tư", "Werkzeugwechsel", "pausa café"]
TYPES = ["work_order.updated", "work_order.updated", "work_order.completed", "work_order.created"]
NOISE = [
    "INFO uvicorn.access 10.4.1.9 \"GET /healthz\" 200",
    "INFO db.pool checkout pool=work_orders size=10 in_use=%d",
    "WARNING db.pool slow checkout pool=work_orders waited=%dms",
    "INFO scheduler job=sync_shift_calendar status=ok",
    "WARNING urllib3.connectionpool Retrying (Retry(total=2)) after connection broken by 'ReadTimeoutError' /api/v2/shifts",
    "INFO metrics flush series=%d",
    "INFO erp_webhook accepted doc_id=SO-1%05d type=sales_order.updated",
    "INFO erp_webhook accepted doc_id=MAT-%d type=material.stock_changed",
    "INFO erp_webhook accepted doc_id=SO-1%05d type=sales_order.created",
]


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--lines", type=int, default=3000)
    p.add_argument("--noise", type=float, default=0.35)
    p.add_argument("--seed", type=int, default=7)
    p.add_argument("--no-skew-herring", dest="skew_herring", action="store_false")
    p.add_argument("--no-deploy-marker", dest="deploy_marker", action="store_false",
                   help="omit the restart/version lines at the deploy")
    args = p.parse_args()

    rnd = random.Random(args.seed)
    t = dt.datetime(2026, 11, 14, 6, 0, 0)
    deploy_at = args.lines // 3
    out = []

    def emit(msg):
        nonlocal t
        t += dt.timedelta(milliseconds=rnd.randint(3, 250))  # keep timestamps monotonic
        out.append("%s,%03d %s" % (t.strftime("%Y-%m-%d %H:%M:%S"), t.microsecond // 1000, msg))

    if args.deploy_marker:
        emit("INFO gateway listening on 127.0.0.1:8081 version=1.7.4")
    for i in range(args.lines):
        t += dt.timedelta(seconds=rnd.randint(1, 9))
        if i == deploy_at and args.deploy_marker:
            emit("INFO gateway shutting down (SIGTERM)")
            emit("INFO gateway listening on 127.0.0.1:8081 version=1.8.0")
            continue
        if i == deploy_at + 400 and args.skew_herring:
            emit("WARNING ops.ntp chrony on vn-bd-gw01 stepped clock by -3.8s")
            continue
        if rnd.random() < args.noise:
            line = rnd.choice(NOISE)
            emit(line % rnd.randint(1, 900) if "%d" in line else line)
            continue

        plant = rnd.choice(list(PLANTS))
        text = rnd.choice(PLANTS[plant]) + rnd.choice(NOTES)
        evt = "evt_%012x" % rnd.getrandbits(48)
        typ = rnd.choice(TYPES)
        skew = rnd.uniform(2.0, 4.5) if (plant == "VN-BD" and args.skew_herring) else rnd.uniform(0, 1.3)
        if skew > 1:
            emit("WARNING mes_webhook clock skew %.1fs plant=%s" % (skew, plant))
        if i > deploy_at and not text.isascii():
            emit("ERROR mes_webhook signature mismatch event_id=%s plant=%s" % (evt, plant))
        else:
            emit("INFO mes_webhook accepted event_id=%s type=%s plant=%s" % (evt, typ, plant))

    dest = pathlib.Path(__file__).resolve().parent.parent / "env" / "logs" / "mes-webhook.log"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text("\n".join(out) + "\n", encoding="utf-8")
    print("wrote %d lines to %s" % (len(out), dest))


if __name__ == "__main__":
    main()
