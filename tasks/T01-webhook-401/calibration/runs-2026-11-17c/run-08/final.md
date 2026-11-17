I found and fixed the cause. All 10 tests pass (7 existing, 3 new), and replaying captured Forgeline events against a local gateway now returns 202 where it returned 401 before.

**Root cause:** `service/middleware.py` parses every incoming body and rewrites it with Python's default `json.dumps` before the signature check. That rewrite turns non-ASCII characters into `\uXXXX` codes and changes whitespace. Forgeline signs the exact bytes it sends, so the 401s hit only events that contain characters like `Ł` or `ü` (operator names, notes) or use different spacing. That's why only some work orders, at every plant, got stuck. The ERP connector signs that rewritten form, as `docs/erp-connector.md` describes, so ERP was unaffected and the shared step looked correct. The first signature mismatch is at 15:36 UTC on the 14th, about 150 per hour since then.

**Fix:**
- **`service/middleware.py`:** the request now also keeps the exact bytes received (`req.raw`) next to the rewritten body.
- **`service/handlers/mes.py`:** the MES signature check now runs on those raw bytes. ERP still checks the rewritten body, as its docs require.
- **Authentication:** it is no weaker. The HMAC and timestamp checks are unchanged, and any change to the body still fails. A new test sends a tampered body and confirms it gets a 401.
- **Duplicate detection:** it still uses the rewritten body, so retries are still caught. In the replay, a compact copy of the sample event came back as `duplicate`.
- **New tests in `tests/test_webhooks.py`:** a UTF-8 non-ASCII body is accepted, a compact-JSON body is accepted, and a tampered body is rejected.

**Red herrings:** the clock-skew warnings and the chrony clock step at the VN-BD plant aren't related. The skew is a few seconds against a 300-second limit, and those warnings appear throughout the log, well before the failures started.

**Follow-up:** after this is deployed, ask Forgeline to replay their dead-letter queue from 2026-11-14 15:36 UTC onward. The stuck work orders won't recover on their own.

**Cause in brief:** the gateway rewrites every webhook body into one standard JSON form before checking its signature. Forgeline MES signs the exact bytes it sends, so any event containing accented characters, like operator names, failed with 401 and ended up in Forgeline's dead-letter queue after 6 retries. MES signatures are now checked against the bytes as received, and ERP keeps the rewritten form it actually signs.