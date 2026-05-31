# WhatsApp Strategy & Implementation Audit

**Last updated:** May 31, 2026  
**Status:** Implemented (Sprints 5A–5E + integration layer)

---

## Summary

Kova uses the **Meta WhatsApp Cloud API** (`apps/platforms/providers/whatsapp.py`) with inbound events at `/whatsapp/webhook/`. Outbound messaging is centralized in **`apps/whatsapp/services.py`** so nurture, bookings, reviews, broadcasts, and commerce share one code path.

---

## What Was Fixed (P0–P1)

| Issue | Resolution |
|-------|------------|
| Missing `apps/whatsapp/services.py` | Added unified `send_text_message`, `send_template_message`, account resolution, logging |
| Inbox split (WA vs Engage) | Webhook calls `bridge_whatsapp_message_to_inbox()` |
| Hardcoded AI confidence (0.8/0.5) | `handle_incoming_message` uses `engage_routing.route_reply()` + `UserProfile.engage_autonomy_level` |
| Broadcast `variables=` bug | Uses `components` via `variables_to_components()` |
| Template draft-only UI | Submit to Meta + Sync from Meta on template list |
| M-Pesa commerce receipt | `send_commerce_payment_receipt()` on successful `mpesa_commerce_callback` |
| Onboarding drip enrollment | New conversations enroll in active `onboarding` sequences |
| Broadcast delivery metrics | Status webhooks update `delivered_count` / `read_count` via `broadcast_id` on messages |

---

## Architecture

```
Inbound:  Meta → webhook.py → Conversation + Message → bridge → Engage inbox
                                              ↓
                                    Celery: handle_incoming_message
                                              ↓
                              engage_routing (autonomy + confidence)
                                              ↓
                              services.send_text_message (24h window)

Outbound: nurture / bookings / reviews / broadcasts / commerce
              → services.send_* → WhatsAppProvider (Graph API)
```

---

## Configuration

| Setting | Purpose |
|---------|---------|
| `WHATSAPP_ACCESS_TOKEN` | Cloud API token (per-account tokens stored on `SocialAccount`) |
| `WHATSAPP_PHONE_NUMBER_ID` | Master number (owner brief commands) |
| `WHATSAPP_WABA_ID` | Template create/sync |
| `WHATSAPP_VERIFY_TOKEN` | Webhook verification |
| `WHATSAPP_APP_SECRET` | Signature verification |

Per-tenant: connect WhatsApp under **Settings → Platforms**; `metadata.phone_number_id` and `metadata.waba_id` required for webhooks and templates.

---

## Templates

1. Create draft (manual or AI) on **WhatsApp → Templates**
2. **Submit to Meta** — status becomes `submitted`
3. **Sync from Meta** — pulls `approved` / `rejected` / `paused`
4. Use approved templates in **Broadcasts** and drip **Sequences**

Variable format for broadcasts: `{"1": "value"}` or `["val1", "val2"]` or named dict (sorted keys → body parameters).

---

## Post-Deploy

```bash
python manage.py migrate
# Celery beat: whatsapp.process_sequence_steps, whatsapp.aggregate_daily_analytics
```

Ensure webhook URL is registered in Meta Developer Portal: `https://<site>/whatsapp/webhook/`

---

## Related Docs

- [WHATSAPP_SETUP_GUIDE.md](./WHATSAPP_SETUP_GUIDE.md)
- [WHATSAPP_TEMPLATES.md](./WHATSAPP_TEMPLATES.md)
- [REACH_LEAD_AUTOMATION_AUDIT.md](./REACH_LEAD_AUTOMATION_AUDIT.md) (walk-in → lead → WhatsApp nurture)
