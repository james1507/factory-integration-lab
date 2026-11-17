# Plant edge simulator

A small broker with MQTT 3.1.1 session semantics and simulated line sensors,
so the ingest service can be run end to end on a laptop. The production plant
uses a managed MQTT broker; this simulator speaks a simpler wire format.

## Wire format

One JSON object per line over TCP.

| Direction | Message |
|---|---|
| client → broker | `{"op": "connect", "client_id": "...", "clean_session": false}` |
| broker → client | `{"op": "connack", "session_present": true}` |
| client → broker | `{"op": "subscribe", "topic": "plant/dus/line/1/temp"}` |
| broker → client | `{"op": "suback", "topic": "..."}` |
| broker → client | `{"op": "publish", "topic": "...", "payload": {...}, "mid": 42}` |
| client → broker | `{"op": "ping"}` → `{"op": "pong"}` |
| client → broker | `{"op": "disconnect"}` |

## Session rules

- A client id identifies a session. Connecting with a client id that is
  already connected takes the session over; the broker closes the older
  connection.
- With `clean_session: false` the session keeps its subscriptions and queues
  messages while no connection is attached. They are delivered on the next
  connect with the same client id.

## Run

```bash
python3 tools/plant_sim/run.py
```
