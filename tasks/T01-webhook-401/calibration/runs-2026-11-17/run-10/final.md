I fixed it in `service/mes_webhook.py`. Signed test events now return 202, including operator names with Unicode characters such as "Jürgen Müller", "Nguyễn Văn Đức" and "Łukasz Wójcik". An event with a wrong signature still gets 401.

**Root cause:** Release 1.8.0, deployed at 07:24:54 UTC, started checking the signature against the event after parsing it and turning it back into text with `json.dumps(event)`, not against the body bytes Forgeline actually sent. Forgeline signs the exact body with Unicode characters left as they are. `json.dumps` writes them as escape codes (`ü` becomes `\u00fc`), so any event with a non-ASCII character in a field like `operator` or `notes` failed the check and was rejected with 401. That explains why only some work orders are stuck, at every plant: the log shows 0 signature mismatches before 1.8.0 and 732 after, spread across all five plants.

**Fix:**
- The signature is now checked against the raw body bytes, as the vendor docs require, and before the body is parsed.
- The timestamp check and its 5-minute limit are unchanged, and the signature comparison still runs in constant time, so authentication is not weakened.
- Logs about an event (like the clock-skew warning) are now written only after its signature has been verified.

**Follow-up:** Events that failed after 07:25 UTC on 2026-11-14 are in Forgeline's dead-letter queue. Once this fix is deployed, they need to be replayed from the Forgeline console so the stuck work orders update.