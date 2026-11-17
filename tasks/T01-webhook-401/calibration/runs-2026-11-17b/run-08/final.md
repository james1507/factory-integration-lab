I fixed it in `service/mes_webhook.py`. Events with non-ASCII characters were being rejected with 401 because the service checked the signature against a re-built copy of the request body instead of the bytes Forgeline actually sent.

**Root cause:** Forgeline signs the exact UTF-8 body it sends. Our handler parsed that body and rebuilt it with `json.dumps(event)` before checking the HMAC (the signature). The rebuilt bytes differ from the sent ones: non-ASCII characters get escaped (`ł` becomes `\u0142`) and the spacing changes. So any event with a non-ASCII value, like the operator names `Łukasz Wójcik` or `Nguyễn Văn An`, failed with "signature mismatch" at every plant, and plain-ASCII events still worked. That explains why only some work orders are stuck.

**Evidence:** All 2,898 401s in the log are signature mismatches, spread across all five plants. There are no "stale" rejections; the clock-skew warnings are only 1–5 seconds against a 300-second limit, so they're unrelated noise. Running `tools/send_test_event.py` before the fix: `J. Becker` got 202, while both non-ASCII names got 401.

**Fix:** The HMAC is now checked against the raw request body, and the JSON is parsed only after the signature passes. The comparison is still constant-time, and the 300-second timestamp limit is unchanged. Nothing in the authentication was loosened.

**Verified locally:** ASCII and non-ASCII events now get 202. A wrong secret, a tampered body and a timestamp an hour old all still get 401. A correctly signed body that isn't valid JSON gets 400.

**Follow-up:** After this is deployed, ask Forgeline to redrive (resend) their dead-letter queue so the stuck work orders update. If they resend with the original timestamps instead of signing again, those events will fail the 300-second limit. In that case they need to sign again on redrive, rather than us raising the limit.