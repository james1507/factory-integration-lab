I found the cause and fixed it. All 9 tests pass, and a non-ASCII event replayed through `tools/send_test_event.py` now gets `202`. Before the fix the same event got `401 bad signature`.

**Root cause:** Forgeline signs the exact bytes it sends, but the gateway checked the MES signature against its own re-encoded copy of the body (`json.dumps(data)` in `service/middleware.py`). That re-encoding was written for the ERP connector, which really does sign that form, but it was applied to every route. When an event contains non-ASCII text, such as operator names like "Nguyễn Văn An" or "Müller", `json.dumps` turns those characters into `\u` escapes. The bytes no longer match what Forgeline signed, so only those events failed, at every plant. Events with plain ASCII text happened to come out byte-for-byte the same and kept passing.

**Fix:**
- `service/middleware.py`: the request now keeps the raw received bytes (`req.raw`) next to the re-encoded `req.body`.
- `service/handlers/mes.py`: the MES check now uses `req.raw`. Authentication is no weaker: it's still HMAC-SHA256 over the timestamp and the exact body, with a constant-time compare and the 300 s freshness check. ERP still verifies the re-encoded body as `docs/erp-connector.md` says, and deduplication still uses the re-encoded form.
- `service/signing.py`: the docstring now says the MES body must be the bytes as received.
- `tests/test_webhooks.py`: two new tests. One checks that MES events signed over the wire bytes are accepted, including UTF-8 text and compact JSON. The other checks that a body changed after signing is still rejected. The old MES tests missed the bug because their test event is ASCII-only.

**Notes:**
- The errors start suddenly at 15:36:54 UTC. The log doesn't show whether that was a gateway deploy or a change in what Forgeline sends, so check your recent deploys.
- The "clock skew" warnings for VN-BD and the chrony entry are unrelated; none of the failures were stale-timestamp rejections.
- About 2,850 events (event IDs are in the "signature mismatch" log lines) are sitting in Forgeline's dead-letter queue. Once this is deployed, ask Forgeline to redeliver them so the stuck work orders catch up. They're safe to replay: a fresh timestamp passes the freshness check, and deduplication drops anything already accepted.

**Summary of the cause:** The gateway re-encoded every webhook body with Python's `json.dumps` before checking the signature, a step meant only for the ERP connector. Forgeline signs the exact bytes it sends, so any MES event with non-ASCII text failed with `401`, and after 6 retries it went to their dead-letter queue. MES signatures are now checked against the raw request body.