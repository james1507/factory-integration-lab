# Forgeline MES — Outbound webhooks (vendor docs excerpt, v3.2)

Forgeline sends one HTTP `POST` per event to your registered endpoint.

## Headers

| Header | Value |
|---|---|
| `Content-Type` | `application/json; charset=utf-8` |
| `X-MES-Timestamp` | Unix seconds when the request was signed |
| `X-MES-Signature` | `sha256=` + hex HMAC-SHA256 |

## Signature

The signed message is the timestamp, a literal `.`, then the request body
exactly as sent, as UTF-8 bytes:

```
HMAC_SHA256(secret, X-MES-Timestamp + "." + body)
```

Reject requests whose timestamp is more than 5 minutes from your clock.

## Body

UTF-8 JSON. Text fields such as `operator` and `notes` are free text entered
on the shop floor and may contain any Unicode characters.

```json
{"event_id": "evt_01H...", "type": "work_order.updated", "plant": "DE-DUS",
 "work_order": "WO-88213", "status": "in_progress", "operator": "J. Becker",
 "notes": ""}
```

## Retries

Non-2xx responses are retried 6 times with exponential backoff, then the
event is moved to the dead-letter queue in the Forgeline console.
