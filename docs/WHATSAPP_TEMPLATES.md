# WhatsApp Template Catalog

> Templates Kova sends programmatically. Each must be **approved by Meta**
> before production traffic can use it. Until approval, the code soft-fails
> (logs and continues).

**Full setup walkthrough:** [`DAILY_BRIEF_WHATSAPP_SETUP.md`](./DAILY_BRIEF_WHATSAPP_SETUP.md)

## How to submit a template

1. Meta Business Suite → WhatsApp Manager → Message Templates → **Create Template**.
2. Category, language, body text, variables — match the rows below exactly.
3. Submit. Approval typically takes <1 hour for Utility, up to 24h for Marketing.
4. Once approved, set the matching `KOVA_*_TEMPLATE_NAME` env var.
5. Restart workers — templates are looked up at send time.

## Catalog

| Code name | Env var | Category | Variables | Body template |
|-----------|---------|----------|-----------|---------------|
| **Daily brief morning ping** | `KOVA_DAILY_BRIEF_TEMPLATE_NAME` | Utility | `{{1}}` first name, `{{2}}` summary snippet, `{{3}}` score line | "Good morning {{1}}! ☀️ {{2}} Score: {{3}} — Reply HELP for commands." |
| Onboarding completion ping | `KOVA_ONBOARDING_TEMPLATE_NAME` | Utility | `{{1}}` first name, `{{2}}` next step URL | "Karibu {{1}}! Your Kova agency is ready. Your daily brief and content plan are live. Open: {{2}}" |
| Booking confirmation (customer) | `booking_confirmed_customer` | Utility | `{{1}}` service, `{{2}}` date, `{{3}}` time, `{{4}}` business | "Karibu! Your {{1}} is confirmed for {{2}} at {{3}}. Save this WhatsApp number for changes. Asante! — {{4}}" |
| Booking notification (owner) | `booking_new_owner` | Utility | `{{1}}` customer, `{{2}}` phone, `{{3}}` service, `{{4}}` date, `{{5}}` time, `{{6}}` price, `{{7}}` source | "New booking: {{1}} ({{2}}) — {{3}} · {{4}} {{5}} · KES {{6}} · Source: {{7}}" |
| Review request (24h after conversion) | `review_request_customer` | Utility | `{{1}}` customer name, `{{2}}` business | "Hi {{1}}! Quick favour — could you share a few words about your experience with {{2}}? Even one line helps a lot. Asante! 🙏" |

## Reply-to-act (after daily brief ping)

Once the daily brief template is delivered, Pro users can reply within **24 hours** with plain text — no additional template required:

| Reply | Action |
|-------|--------|
| `HELP` | List commands |
| `SCORE` | Kova score |
| `BRIEF` | Today's headline + your move |
| `POSTS` | Pending approval list |
| `APPROVE` / `APPROVE ALL` / `APPROVE 2` | Schedule posts |
| `IDEA 1` / `IDEA 2` | Queue content idea as seed |

Handled by `apps/briefs/whatsapp_commands.py` on Kova's master WhatsApp number.

## Why this exists

Captures every WhatsApp template the codebase expects so you can submit them in one Meta Business Suite session rather than discovering missing templates one failed message at a time.
