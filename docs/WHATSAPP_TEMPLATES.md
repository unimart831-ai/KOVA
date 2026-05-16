# WhatsApp Template Catalog

> Templates Kova sends programmatically. Each must be **approved by
> Meta** before production traffic can use it. Until approval, the
> code soft-fails (logs and continues) — see `apps/whatsapp/services.py`
> and the catch blocks around every `send_template_message` call.

## How to submit a template

1. Meta Business Suite → WhatsApp Manager → Message Templates → **Create Template**.
2. Category, language, body text, variables — match the rows below exactly.
3. Submit. Approval typically takes <1 hour for transactional categories,
   up to 24h for marketing/utility.
4. Once approved, set the matching `KOVA_*_TEMPLATE_NAME` env var
   (the registered template name; Meta returns it on approval).
5. Restart workers — templates are looked up at send time, no migration needed.

## Catalog

| Code name | Env var | Category | Variables | Body template |
|-----------|---------|----------|-----------|---------------|
| Onboarding completion ping (P4.5) | `KOVA_ONBOARDING_TEMPLATE_NAME` | Utility | `{{1}}` = first name, `{{2}}` = next step URL | "Karibu {{1}}! Your Kova agency is ready. Your daily brief and content plan are live. Open: {{2}}" |
| Booking confirmation (customer) | `booking_confirmed_customer` | Utility | `{{1}}` service, `{{2}}` date, `{{3}}` time, `{{4}}` business | "Karibu! Your {{1}} is confirmed for {{2}} at {{3}}. Save this WhatsApp number for changes. Asante! — {{4}}" |
| Booking notification (owner) | `booking_new_owner` | Utility | `{{1}}` customer, `{{2}}` phone, `{{3}}` service, `{{4}}` date, `{{5}}` time, `{{6}}` price, `{{7}}` source | "New booking: {{1}} ({{2}}) — {{3}} · {{4}} {{5}} · KES {{6}} · Source: {{7}}" |
| Review request (24h after conversion) | `review_request_customer` | Utility | `{{1}}` customer name, `{{2}}` business | "Hi {{1}}! Quick favour — could you share a few words about your experience with {{2}}? Even one line helps a lot. Asante! 🙏" |

## Why this exists

P4.5 of the Master Plan flagged that the onboarding completion ping
"is currently no-op without [a template approval]." That stays true
until a template name is filled in at the row above. This catalog
captures every WhatsApp template the codebase expects so the founder
can submit them all in one Meta Business Suite session rather than
discovering them one missed message at a time.
