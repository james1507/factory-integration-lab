I found and fixed the root cause. All 10 tests pass, and the replay tool now gets `202` for an event that was getting `401` before.

**Cause:** `service/middleware.py` parses every webhook body and re-encodes it with `json.dumps(data)` before the signature is checked, and that function turns non-ASCII characters into `\uXXXX` escapes. Forgeline signs the exact UTF-8 bytes it sends, so any event containing a non-ASCII character fails the check, such as an operator named "Łukasz Wójcik" or a note like "Prüfung". That's why only some work orders are stuck, at every plant: it depends on the text in each event, not on where it came from. The logs show the mismatches starting on 2026-11-14 at about 15:36 UTC. I'm assuming that's when non-ASCII text started showing up in Forgeline's events; the logs don't say why.

**What I checked:**
- Replaying the captured sample with `tools/send_test_event.py` got `202`. The same sample with "Becker" changed to "Bäcker" got `401 bad signature`.
- The log has 2,851 signature mismatches across all five plants.
- The "clock skew" warnings, mostly from VN-BD after an NTP clock step, are a red herring. Those skews are a few seconds, well under the 300 s limit, and none of them led to a rejection.

**Fix:** authentication is not weakened. The HMAC is still required, still compared in constant time, and timestamps are still checked; the check now just runs over the bytes actually received.
- `service/middleware.py`: the request now also keeps the exact bytes received (`req.raw`). I added a comment explaining that the re-encoded body doesn't match what was sent.
- `service/handlers/mes.py`: the Forgeline signature is now checked against `req.raw`.
- The ERP endpoint still checks against the re-encoded body. Our own ERP connector signs that re-encoded form, as `docs/erp-connector.md` describes, so it was never affected.
- `tests/test_webhooks.py`: I added three tests. One sends an event with non-ASCII UTF-8 text, one sends compact JSON, and one changes a signed body before sending it, which must still get `401`.

**Follow-ups:**
- Once the fix is deployed, ask Forgeline to replay their dead-letter queue from about 15:30 UTC on 11-14 onward so the stuck work orders catch up. Duplicate detection will safely drop any events we already accepted.
- The existing tests missed this because they only sent ASCII text and signed the same re-encoded form the gateway produces. The new tests sign the real bytes on the wire.