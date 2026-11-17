I've fixed it in `service/mes_webhook.py`, and Unicode events now get through.

**Root cause:** The service didn't check the signature against the body Forgeline actually sent. It parsed the JSON, re-encoded it with `json.dumps(event)`, and checked the signature against that copy. `json.dumps` turns every non-ASCII character into an escape code (`ü` becomes `\u00fc`) and can change the spacing, so the bytes no longer match what Forgeline signed. Any event with an accented or non-Latin operator name or note, like "Müller" or "Nguyễn", got a 401 and ended up in Forgeline's dead-letter queue. That's why only some work orders are stuck, at every plant, with VN-BD hit hardest.

**What I changed:**
- The signature is now checked against the raw request body, exactly as received, which is what the vendor docs require.
- The signature is checked before the body is parsed, so payloads that haven't been verified are never parsed or logged.
- Authentication is as strict as before: the HMAC-SHA256 check, the constant-time comparison and the 5-minute timestamp limit are unchanged.

**Evidence and testing:**
- All 732 of the 401s in the log are "signature mismatch", with none for stale timestamps. The many clock-skew warnings in the log are noise.
- After the fix, I ran the service locally and sent test events with `tools/send_test_event.py`. Events with operators "J. Becker", "Nguyễn Văn Đức" and "Müller" were all accepted (202). A request with a forged signature still got a 401.

**Follow-up:** After you deploy, replay Forgeline's dead-letter queue from their console so the stuck work orders catch up.