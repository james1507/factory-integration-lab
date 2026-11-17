I've fixed the 401s in `service/mes_webhook.py`: the service now checks the signature against the exact bytes Forgeline sends, and authentication is just as strict as before.

**Root cause:** The service didn't check the signature against the bytes Forgeline actually sent. It parsed the JSON, rebuilt it with `json.dumps(event)` and checked that rebuilt version. `json.dumps` turns non-ASCII characters into `\uXXXX` codes by default, so any event with an accented operator name (`Łukasz`, `Nguyễn`, `Müller`) or accented note no longer matched what Forgeline signed and got a 401. That's why only some work orders got stuck, and at every plant: all five show signature mismatches (2,898 in the log).

**What I changed:**
- The signature is now checked against the raw request body, byte for byte.
- That check now happens before the JSON is parsed, so unsigned input no longer reaches the parser.
- The HMAC-SHA256 check, the constant-time comparison and the 300s timestamp window are all unchanged.

**Clock skew is not the cause:** the "clock skew" warnings and the chrony clock correction on `vn-bd-gw01` are noise. The largest skew in the log is 4.5s against a 300s limit, and nothing was rejected as stale.

**Tests:** I ran the service locally on port 18931, since 8081 was already taken by another process.
- **Before the fix:** `tools/send_test_event.py` got 202 for "J. Becker" and 401 for "Łukasz Wójcik" and "Nguyễn Văn An".
- **After the fix:**
  - All of those names, plus "José Núñez", get 202.
  - A tampered body, a wrong secret and a stale timestamp all still get 401.

**Still to do:** the change has to be deployed to prod. After that, someone should ask Forgeline to replay their dead-letter queue, so the stuck work orders catch up on the dashboards.