**[Grafana] WARN — dus-ingest: readings stored per minute down 67% (prod)**

Firing since 2026-11-16 09:45 UTC · service: `sensor-ingest` (plant DUS) · escalation: integrations on-call

Process engineering reports gaps in the temperature charts for lines 1, 2 and
3 in Düsseldorf since this morning. The charts are not empty: every line still
gets some readings, just far fewer than the sensors send. The sensors and the
plant broker look healthy from the OT side. We rolled out ingest 2.4.0 this
morning; the worker scale-up in that release is needed for line 3 throughput.

The ingest service is in `ingest/` with its config in `config/`, its tests are
in `tests/`, and today's service log is in `logs/ingest.log`.
`tools/plant_sim/` runs a local broker and simulated sensors so you can run the
service end to end.

Find the root cause and fix it. When you are done, explain the cause in two or
three sentences.
