I found the root cause, fixed it, and checked that webhook authentication is just as strict as before.

**Cause:** `service/middleware.py` parses every request body and re-encodes it with `json.dumps()` before handing it on. That was added for the ERP connector, which signs that re-encoded form. But Forgeline signs the exact bytes it sends, and `json.dumps` turns any non-ASCII character into an escape code (`ä` becomes `\u00e4`). So any MES event containing a name like "J. Bäcker", a Polish or Vietnamese note, or similar no longer matched its signature and got a 401. That's why only some work orders are stuck, mostly at PL-WRO, DE-DUS, VN-BD and MX-MTY and fewer at US-CLE. The clock-skew warnings and the VN-BD chrony step in the logs are unrelated.

**Fix:**
- `service/middleware.py`: the request now keeps the exact bytes received (`req.raw`) alongside the re-encoded body.
- `service/handlers/mes.py`: the Forgeline signature is now checked against those raw bytes. The ERP check is unchanged, and duplicate detection still uses the re-encoded body.
- The HMAC, the timestamp window and the constant-time comparison are all unchanged.

**Testing:** I added tests for non-ASCII bodies, compact JSON, and a body changed after signing (still rejected with a 401). All 10 tests pass. Replaying a captured event with "Bäcker" through `tools/send_test_event.py` gave 401 before the fix and 202 after.

**Follow-ups:**
- **Deploy and replay:** once the fix is deployed, ask Forgeline to replay their dead-letter queue from about 2026-11-14 15:36 UTC, when the 401s started. That will catch up the stuck work orders, and any events that were already accepted will be ignored as duplicates.
- **What changed at 15:36:** there's no git history here, so I couldn't confirm what changed then. It's most likely when the re-encoding went out, or when Forgeline started sending raw UTF-8 instead of escaped characters.