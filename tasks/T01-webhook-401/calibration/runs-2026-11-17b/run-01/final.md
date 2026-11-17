I fixed it in `service/mes_webhook.py`. Signed events with accented names in them now get through, and authentication is no stricter or looser than before.

**Root cause:** The handler didn't check the signature against the bytes Forgeline actually sent. It parsed the JSON, re-encoded it with `json.dumps` (which turns non-ASCII characters into `\uXXXX` escapes) and computed the HMAC over that. Forgeline signs the original UTF-8, so any event with a character like "ü", "Ł" or "ễ" in a field such as `operator` failed with `401 bad signature` and ended up in their dead-letter queue after the retries. That's why only some work orders are stuck and why it happens at every plant: all 2,898 rejections in the log are signature mismatches, spread across all five plants. The clock-skew warnings are a red herring: the largest skew is 4.5s, far inside the 300s tolerance.

**What I changed:**
- The HMAC is now computed over the raw request body, using the same constant-time comparison as before.
- The signature is checked before the JSON is parsed, so unauthenticated payloads are never parsed.
- The timestamp and freshness checks are unchanged.

**Tested locally:** I ran the service and sent events with `tools/send_test_event.py`. Events with the operators "J. Becker", "Łukasz Wójcik" and "Nguyễn Văn An" were all accepted (202). A forged signature was still rejected (401). I didn't run the old code against the non-ASCII names to show the failure directly.

**Still to do after deploying:** the events already in Forgeline's dead-letter queue were never stored. Ask Forgeline support to redeliver them, or the dashboards will keep showing those work orders in old states.