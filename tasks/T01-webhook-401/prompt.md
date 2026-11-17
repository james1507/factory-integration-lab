**[PagerDuty] HIGH — mes-webhook: 401 rate above 15% for 30m (prod)**

Triggered 2026-11-14 16:05 UTC · service: `integration-gateway` (route `/webhooks/mes`) · escalation: integrations on-call

Forgeline MES support emailed us: their outbound webhooks to us are being
rejected with `401`, and after 6 retries the events go to their dead-letter
queue. Production planning says some work orders are stuck in old states on
the dashboards. Not all of them, and not only at one plant.

The gateway code is in `service/`, its tests are in `tests/`, and the last
day of logs is in `logs/mes-webhook.log`. `tools/send_test_event.py` replays a
captured Forgeline delivery against a local gateway.

Find the root cause and fix it. Do not weaken webhook authentication. When
you are done, explain the cause in two or three sentences.
