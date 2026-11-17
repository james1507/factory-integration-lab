I fixed it in `service/mes_webhook.py`. A local test with the vendor-style sender now returns `202` for operator names with accents, Vietnamese and Chinese characters, as well as plain ASCII. A request signed with the wrong secret still gets `401`.

**Root cause:** Version 1.8.0, deployed at 07:24 UTC, started checking the webhook signature against a re-encoded copy of the body (`json.dumps(event)`) instead of the exact bytes Forgeline signed. Python's default re-encoding turns non-ASCII characters into `\uXXXX` escapes, so any event whose free-text fields (`operator`, `notes`) had a character like "ü" or "ễ" failed the check. That's why only some work orders at every plant got stuck. The first mismatch is logged 11 seconds after the 1.8.0 startup, and the "clock skew ~1s" warnings in the log are noise, far below the 5-minute limit.

**Fix:** The service now checks the signature against the raw request bytes, before parsing the JSON. This is what the vendor docs specify, and it's stricter than before, not weaker. Rejected requests still return `401`, and the timestamp check is unchanged.

**What you still need to do:**
- **Replay the dead-letter queue.** About 730 events were rejected after the deploy, and the dashboards will stay stale until someone replays Forgeline's dead-letter queue from their console.
- **Know about two small changes:** the "clock skew", "stale" and "signature mismatch" log lines no longer show `event_id` or plant, because those come from a body we haven't verified yet. Also, a request with a bad signature and bad JSON now gets `401` instead of `400`.