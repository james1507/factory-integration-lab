I found and fixed the cause, and webhook authentication is just as strict as before.

**Root cause:** The shared request middleware (`service/middleware.py`) parses every incoming body and re-encodes it with `json.dumps()`, which changes the bytes. Non-ASCII characters become `\u` escapes (`ł` turns into `\u0142`), and compact JSON gets spaces added. That works for the ERP connector, which signs that re-encoded form, but Forgeline signs the exact bytes it sends. So any MES event with a name or note containing characters like `ł`, `ü`, `ñ` or Vietnamese diacritics failed the signature check. That's why only some work orders got stuck, at several plants; the log shows the mismatches starting around 15:36 UTC on 11-14.

**Fix:**
- `service/middleware.py`: the request now also keeps the exact bytes received (`req.raw`). The re-encoded `req.body` is unchanged, so ERP signature checks and duplicate detection work as before.
- `service/handlers/mes.py`: MES signatures are now checked against `req.raw`, not the re-encoded body. The secret, timestamp window and constant-time comparison are the same.
- `tests/test_webhooks.py`: I added tests for non-ASCII UTF-8 bodies and compact JSON, which must now be accepted, and for a tampered body, which must still get a 401.

**Verification:** All 10 tests pass. Before the fix, replaying an event with operator "Łukasz Wróbel" through `tools/send_test_event.py` returned `401 bad signature`; after it, the same event returns `202`.

**Next steps:** After deploying, ask Forgeline to replay their dead-letter queue from about 15:30 UTC on 11-14. That's how the stuck work orders get updated; if the DLQ holds retries of the same event, the gateway's duplicate check will drop the extras.