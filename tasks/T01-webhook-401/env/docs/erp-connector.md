# ERP connector → gateway webhooks (internal)

Owner: integrations team. The connector is our own Python service that tails
the ERP change feed and POSTs each change to `/webhooks/erp`.

## Wire format

Pretty-printed UTF-8 JSON, 2-space indent, CRLF line endings (the ERP export
library does this and we cannot turn it off).

## Signature

The connector does not sign the wire bytes. It signs the payload re-encoded
with Python's `json.dumps(payload)` defaults, followed by the timestamp:

```
X-ERP-Request-Time: <unix seconds>
X-ERP-Signature:    base64( HMAC_SHA256(secret, json.dumps(payload) + timestamp) )
```

The gateway therefore has to re-encode the parsed body the same way before it
verifies. This is done once in `service/middleware.py` for all routes.

## Example payload

```json
{
  "doc_id": "SO-104233",
  "type": "sales_order.updated",
  "customer": "Müller Antriebstechnik GmbH",
  "lines": 4
}
```
