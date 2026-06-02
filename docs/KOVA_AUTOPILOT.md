# KOVA Operations Autopilot

Operations Autopilot reduces manual follow-up while keeping **safe defaults: every toggle is off until you turn it on** in Settings.

Settings URL: `/accounts/settings/#settings-autopilot`

## Toggles

| Toggle | Default | What it does |
|--------|---------|--------------|
| **Auto-publish approved posts** | Off | When a post is `approved` and `scheduled_at` is due, publish without an extra click. Respects global/per-user publish pause, emergency pause, and content safety. |
| **Auto-enroll new leads** | Off | New leads (forms, walk-ins, WhatsApp, QR, commerce) enroll in matching active nurture sequences (including default Welcome). Manual **Enroll in nurture** still works. |
| **Auto-create leads from WhatsApp** | Off | First inbound message from a new number creates a hot lead stub. **Save as lead** in inbox unchanged. |
| **24h WhatsApp follow-up** | Off | Hourly job: if the customer wrote last and no outbound reply in 24h, send a short nudge within the 24h service window. Max **1 nudge per conversation per 7 days**. |
| **WhatsApp FAQ auto-replies** | Off | Keyword match (case-insensitive) against up to 5 owner-defined rules. Skips if you replied manually in the last 5 minutes. Max **3 auto-FAQ replies per conversation per day**. |

FAQ rules shape:

```json
[
  {"keywords": ["hours", "open"], "reply": "We are open Mon–Sat 8am–6pm."}
]
```

## Plan gates

- **Auto-publish** and **auto-enroll**: available on all plans (subject to existing leads limits and publish safety).
- **WhatsApp automations** (auto-create lead, 24h follow-up, FAQ): require **Biashara (Pro)** or **Agency** with `whatsapp_enabled` on the plan. Settings form validates on save.

Content Autopilot (weekly content plans) is separate — see `/content/autopilot/` and `autopilot_enabled` on the brand settings form.

## Celery tasks

| Task | Schedule | Module |
|------|----------|--------|
| `content.check_and_publish_due_posts` | Every 5 min | Gates dispatch on `autopilot_auto_publish_approved` |
| `whatsapp.send_followup_nudges` | Hourly | `apps/whatsapp/autopilot.py` |
| `leads.process_nurture_steps` | Every 30 min | Unchanged — runs enrolled sequences |

## Safety

- **Emergency pause** (`UserProfile.emergency_pause`) blocks FAQ replies and follow-up nudges; publish path already checks it.
- **auto_publish_paused** (per-user or global via `SystemSafetyConfig`) blocks auto-publish dispatch.
- Content safety runs at publish time in `publish_post` (unchanged).
- WA follow-up uses session messages only when the 24h window is open; otherwise skipped (no template spam).

## Migration

`accounts.0030_userprofile_operations_autopilot` — adds autopilot fields and renames `auto_create_wa_leads` → `autopilot_auto_create_wa_leads`.

## Deferred

- **Money board notifications** (“X need reply, Y hot leads”) — optional daily push/email; not implemented in this pass. Use Today wedge / inbox until added.

## Related docs

- [REACH lead automation audit](REACH_LEAD_AUTOMATION_AUDIT.md)
- [KOVA plans guide](KOVA_PLANS_GUIDE.md)
- [Content safety](CONTENT_SAFETY.md)
