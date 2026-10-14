# ATS integration (sketch)

Not built — a sketch of the smallest integration that would let a client's ATS (Workday,
Greenhouse, a custom system) consume this engine's results, written against what already exists
rather than invented from scratch.

## What already exists and is reusable as-is

`screening.record.final_record(state)` is already the deterministic, typed JSON this would
send — no new serialization to design:

```json
{"conversation_id": "…", "vacancy_id": "driver", "status": "qualified", "language": "es",
 "fields": {"full_name": "Laura Pérez", "has_driver_license": true, ...},
 "flags": [...], "disqualify_reason": null, "review_reasons": [], "summary": "…",
 "preference_score": 0.0}
```

An ATS needs exactly this shape: the fields, the outcome, the flags a recruiter should see,
and the recruiter-facing summary. Nothing about it was designed for internal use only.

## The integration: an outbound webhook on status change

Same pattern already proven for Twilio's inbound webhook, mirrored outbound:

1. **Trigger:** the worker's `_persist_turn` (`apps/messaging/services.py`) already knows the
   moment `state.status` leaves `in_progress` — that's the one place a status-change event
   would be raised from, not a new polling loop.
2. **Delivery:** a `POST` to a per-client, per-vacancy configured URL, body = `final_record(state)`
   plus `{"event": "status_changed", "vacancy_id": ..., "at": ...}`. Signed the way Twilio
   signs requests to us, just reversed — an HMAC-SHA1 (or SHA256) over the body with a shared
   secret, in an `X-Signature` header, so the ATS can verify it's really us. The same
   `RequestValidator`-style check already in `whatsapp.py` is the model to follow, just as the
   sender instead of the receiver.
3. **Retries:** at-least-once, exponential backoff, same shape as the existing `send_error`
   handling on outbound messages (`apps/messaging/services.py::_send`) — a failed delivery is
   recorded, never silently dropped, and never blocks the worker loop.
4. **Idempotency:** the ATS dedupes on `conversation_id` + `status`, the same pair that already
   uniquely identifies "this outcome," so a retried delivery is harmless to receive twice.

## What's new, specifically

- A `WebhookEndpoint` model (client, vacancy, URL, shared secret) — a few fields, one admin
  screen, no new architecture.
- A `send_webhook` step added to `_persist_turn`'s existing "after commit" phase (where
  `_send()` already lives for outbound messages) — same transaction-then-send discipline
  that's already the worker's core reliability property (D15), reused rather than reinvented.
- Delivery logging (`WebhookDelivery`: endpoint, payload, response code, attempt count) — the
  dashboard's existing event-timeline pattern, applied to a new kind of event.

## What's deliberately not in this sketch

- **A pull/polling API** as an alternative to the webhook — straightforward to add
  (`GET /api/conversations/?since=...&vacancy=...`, same `final_record` shape), but a client
  integrating an ATS almost always prefers push, so it's not worth building until a real
  client asks for pull specifically.
- **Field mapping per ATS** (their schema likely isn't `final_record`'s shape verbatim) — this
  is where most of the real integration effort would go, and it's inherently client-specific,
  so there's nothing general to design here ahead of a real client's actual ATS.
- **OAuth/API-key management for multiple clients** — the single-tenant `WebhookEndpoint` model
  above is enough for one client; a real multi-tenant version would need per-client auth and
  rate limiting, which is a bigger and genuinely separate piece of work, not a sketch-sized add.
