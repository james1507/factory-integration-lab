I fixed it in `service/mes_webhook.py`, and authentication is no stricter or looser than before.

**Cause:** Version 1.8.0, deployed at 07:24 UTC (the first signature failures are 10 seconds later), started re-encoding the JSON body with `json.dumps(event)` and then checking the signature against that. Forgeline signs the body exactly as it sends it, as UTF-8. `json.dumps` rewrites accented characters as escape codes (`ü` → `\u00fc`), so any event with non-ASCII text, such as an operator name like "Jürgen Müller" or "Nguyễn Văn Ánh", got a different signature and a `401`. That's why only some work orders got stuck, at every plant: it depends on who typed into the `operator` or `notes` field, not on location.

**Fix:** The handler now checks the signature against the raw request bytes, as Forgeline's docs require, and only reads the JSON after that check passes. Previously it read the JSON first, before checking the request was genuine. The 5-minute timestamp limit is unchanged.

**Verified** with `tools/send_test_event.py` against a local instance:
- **Before the fix:** "J. Becker" was accepted, but "Jürgen Müller" and "Nguyễn Văn Ánh" got `401`.
- **After the fix:** all of those, plus "Łukasz Żółć", are accepted (`202`).
- **Wrong secret:** still rejected with `401`.

**Still to do:**
- Deploy the fix.
- Replay the events in Forgeline's dead-letter queue from about 07:24 UTC on 2026-11-14 onward. That's 732 events, by the "signature mismatch" count in the log. Until they're replayed, the stuck work orders on the dashboards won't update.