# Daily Brief WhatsApp — Complete Setup Guide

This guide walks you through setting up **morning brief pings** and **reply-to-act** for Kova Pro users. After setup, business owners receive a WhatsApp message each morning and can reply with short commands like `APPROVE` or `IDEA 1` without opening the app.

---

## What you are setting up

| Feature | Plan | How it works |
|---------|------|--------------|
| In-app daily brief | All plans | `/brief/` home page |
| Email digest | Growth+ | Rich HTML email at brief time |
| WhatsApp morning ping | Pro+ | Meta-approved template via Kova master number |
| Reply-to-act | Pro+ | Owner replies within 24h with commands |

**Architecture:**

```
Celery (brief time) → deliver_daily_brief()
  → Meta template ping to user.phone_number

User replies "APPROVE" → Meta webhook → Kova master phone_number_id
  → find user by phone → whatsapp_commands.py → approve post → text reply
```

---

## Prerequisites

Before you start, confirm you have:

1. **Meta Business Portfolio** with a verified business
2. **WhatsApp Business Account (WABA)** connected to your Meta app
3. **Kova production server** with a public HTTPS URL
4. **Pro plan users** with `phone_number` set in Settings (Kenyan format `0712345678`)
5. **Environment access** on Railway / your host to set env vars

Existing guide for the full WhatsApp Business connection (customer inbox): [`WHATSAPP_SETUP_GUIDE.md`](./WHATSAPP_SETUP_GUIDE.md)

---

## Step 1 — Meta Developer App

1. Go to [developers.facebook.com](https://developers.facebook.com) → your Kova app
2. Add product **WhatsApp** if not already added
3. Note these values from **WhatsApp → API Setup**:
   - **Phone number ID** → `WHATSAPP_PHONE_NUMBER_ID`
   - **WhatsApp Business Account ID** → `WHATSAPP_WABA_ID`
4. Create a **System User** in Business Settings with `whatsapp_business_messaging` permission
5. Generate a **permanent access token** → `WHATSAPP_ACCESS_TOKEN`

---

## Step 2 — Webhook (required for reply-to-act)

The webhook must receive messages sent **to your Kova master number** (not only user-connected business numbers).

1. In Meta Developer Console → WhatsApp → **Configuration**
2. **Callback URL:**
   ```
   https://YOUR-DOMAIN.com/whatsapp/webhook/
   ```
   Include the trailing slash.

3. **Verify token:** choose a random string → `WHATSAPP_VERIFY_TOKEN`
4. Subscribe to webhook field: **`messages`**
5. Set **App Secret** from Meta app settings → `WHATSAPP_APP_SECRET` (required in production)

**Verify it works:**

```bash
curl "https://YOUR-DOMAIN.com/whatsapp/webhook/?hub.mode=subscribe&hub.verify_token=YOUR_TOKEN&hub.challenge=test123"
# Should return: test123
```

---

## Step 3 — Create Meta message templates

Templates must be **approved by Meta** before production sends. Submit both in one session via [Meta Business Suite → WhatsApp Manager → Message templates](https://business.facebook.com/wa/manage/message-templates/).

### Template A — Daily brief morning ping

| Field | Value |
|-------|-------|
| **Name** | `kova_daily_brief` (or your choice — must match env var) |
| **Category** | Utility |
| **Language** | English |

**Body text (3 variables):**

```
Good morning {{1}}! ☀️

{{2}}

Score: {{3}}

Tap a button below to act.
```

| Variable | Content from Kova |
|----------|-------------------|
| `{{1}}` | User's first name |
| `{{2}}` | 2-line brief summary (max ~160 chars) |
| `{{3}}` | Score line e.g. `72/100 (+4)` |

**Buttons (add in template builder — max 3 for Utility):**

| Index | Type | Label | Value |
|-------|------|-------|-------|
| 0 | **Visit website** (URL) | `Open brief` | `https://YOUR-DOMAIN.com/brief?{{1}}` |
| 1 | **Quick reply** | `Approve` | (fixed — sends "Approve" when tapped) |
| 2 | **Quick reply** | `Score` | (fixed — sends "Score" when tapped) |

The URL variable `{{1}}` is filled at send time from `KOVA_DAILY_BRIEF_URL_SUFFIX` (default: `utm_source=whatsapp`).

After the user taps any button or replies, Kova sends **session quick-action buttons** (Approve / Posts / Score) with each response — no extra Meta approval needed.

### Template B — Onboarding completion (if not already live)

| Field | Value |
|-------|-------|
| **Name** | `kova_onboarding_ready` |
| **Category** | Utility |

**Body:**

```
Karibu {{1}}! Your Kova agency is ready. Your daily brief and content plan are live. Open: {{2}}
```

See full catalog: [`WHATSAPP_TEMPLATES.md`](./WHATSAPP_TEMPLATES.md)

---

## Step 4 — Environment variables

Add to Railway / `.env` / production settings:

```bash
# Master WhatsApp credentials (Kova platform number)
WHATSAPP_PHONE_NUMBER_ID=123456789012345
WHATSAPP_ACCESS_TOKEN=EAAxxxxx...
WHATSAPP_WABA_ID=123456789012345
WHATSAPP_VERIFY_TOKEN=your-random-verify-token
WHATSAPP_APP_SECRET=your-meta-app-secret

# Daily brief template (must match Meta-approved name exactly)
KOVA_DAILY_BRIEF_TEMPLATE_NAME=kova_daily_brief
KOVA_DAILY_BRIEF_TEMPLATE_LANG=en
# URL button variable for template: https://YOUR-DOMAIN/brief?{{1}}
KOVA_DAILY_BRIEF_URL_SUFFIX=utm_source=whatsapp
# Set KOVA_DAILY_BRIEF_URL_SUFFIX= (empty) if URL button has no variable

# Onboarding ping (optional)
KOVA_ONBOARDING_TEMPLATE_NAME=kova_onboarding_ready
KOVA_ONBOARDING_TEMPLATE_LANG=en

# Site URL (used in brief links)
SITE_URL=https://app.kovaagent.com
```

Restart **web**, **worker**, and **beat** processes after changing env vars.

---

## Step 5 — User-side setup (Pro customers)

Each Pro user must:

1. **Upgrade to Biashara (Pro)** — `whatsapp_brief` plan limit
2. Open **Settings → Account**
3. Set **phone number** (e.g. `0712345678`)
4. Enable **WhatsApp morning ping** toggle
5. Set **daily brief time** and **timezone**

Kova matches inbound WhatsApp replies by converting `0712345678` → `254712345678` and comparing to the webhook `from` field.

---

## Step 6 — Reply-to-act commands

After the morning template ping, the user has a **24-hour messaging window**. They can reply with plain text (no template needed for replies).

| Command | Action |
|---------|--------|
| `HELP` | List all commands |
| `SCORE` | Kova score + delta |
| `BRIEF` | Headline + your move today |
| `POSTS` | List pending approvals |
| `APPROVE` | Approve first pending post (next-best slot) |
| `APPROVE ALL` | Approve all pending posts |
| `APPROVE 2` | Approve post #2 in queue |
| `IDEA 1` | Queue content idea #1 from today's brief |

**Examples:**

```
User: APPROVE
Kova: Approved 1 post for instagram. "New collection drop this week…" — queued for publishing.

User: IDEA 2
Kova: Queued idea #2 for creation: "Behind-the-scenes reel at the shop…"
```

Commands are case-insensitive. Unknown text returns HELP.

---

## Step 7 — Verify end-to-end

### A. Test brief generation manually

```bash
python manage.py shell
```

```python
from django.contrib.auth import get_user_model
from apps.create.briefs.tasks import generate_daily_brief

user = User.objects.get(email="your-test@email.com")
user.phone_number = "0712345678"
user.brief_whatsapp_enabled = True
user.save()
generate_daily_brief(user)
```

Check logs for: `Daily brief WhatsApp sent to ...`

### B. Test reply-to-act

From the phone number saved on the user account, reply to the Kova WhatsApp number:

```
HELP
SCORE
APPROVE
```

Check **Admin Dashboard → WhatsApp → Daily Brief Delivery** for command logs.

### C. Check delivery metadata

In Django admin or shell, today's `DailyBrief` should have:

```json
"performance_summary": {
  "last_whatsapp_delivery": {
    "sent_at": "...",
    "to": "254712345678",
    "wamid": "...",
    "reply_commands": "HELP · SCORE · APPROVE · IDEA 1"
  }
}
```

---

## Admin dashboard monitoring

Staff can monitor at:

| URL | What you see |
|-----|--------------|
| `/admin-dashboard/whatsapp/` | WhatsApp overview + link to brief delivery |
| `/admin-dashboard/whatsapp/brief-delivery/` | Pings sent, command volume, full audit log |

Django admin also exposes `BriefWhatsAppLog` for support lookups.

---

## Troubleshooting

### Morning ping not sent

| Symptom | Fix |
|---------|-----|
| Log: `KOVA_DAILY_BRIEF_TEMPLATE_NAME not set` | Set env var; restart workers |
| Log: `master WhatsApp creds missing` | Set `WHATSAPP_PHONE_NUMBER_ID` + `WHATSAPP_ACCESS_TOKEN` |
| Log: `no valid phone` | User must set phone in Settings |
| Meta API error `132001` | Template name/language mismatch — check Meta approval |
| User on Growth plan | WhatsApp brief is Pro-only |

### Reply commands ignored

| Symptom | Fix |
|---------|-----|
| Webhook log: `No SocialAccount found for phone_number_id` | **Expected for master number** — ensure `WHATSAPP_PHONE_NUMBER_ID` matches webhook metadata |
| No response to HELP | User phone must match `User.phone_number` exactly (0712… format) |
| `plan_blocked` in logs | User needs Pro + `brief_whatsapp_enabled` |
| Reply after 24h without user initiating | Template ping opens window; if expired, user must message first |

### APPROVE fails

| Symptom | Fix |
|---------|-----|
| "posts may need images" | Instagram/TikTok posts require media — approve in app |
| "Nothing to approve" | No posts in `pending_approval` status |

---

## Security notes

- **`WHATSAPP_APP_SECRET`** — always set in production; validates webhook signatures
- **Owner-only routing** — reply-to-act only fires when inbound `from` matches a Kova user's stored phone
- **Plan gating** — Growth/Starter users get an upgrade message, not command execution
- **No customer cross-talk** — master number path is separate from user business inbox (`SocialAccount`)

---

## File reference (developers)

| File | Purpose |
|------|---------|
| `apps/briefs/delivery.py` | Email + WhatsApp + WebSocket orchestration |
| `apps/briefs/whatsapp_commands.py` | Reply-to-act parser + handlers |
| `apps/content/approval.py` | Programmatic post approval |
| `apps/briefs/actions.py` | Create ContentSeed from brief idea |
| `apps/whatsapp/webhook.py` | Master number routing |
| `apps/briefs/models.py` | `BriefWhatsAppLog` audit model |
| `templates/emails/daily_brief.html` | Rich email digest |
| `docs/WHATSAPP_TEMPLATES.md` | Template catalog for Meta submission |

---

## Checklist before go-live

- [ ] Meta templates **approved** (not just submitted)
- [ ] All env vars set and workers restarted
- [ ] Webhook verified (GET challenge returns challenge string)
- [ ] Test user on **Pro** with phone + WhatsApp toggle on
- [ ] Manual `generate_daily_brief()` sends template
- [ ] `HELP` reply returns command list within 5 seconds
- [ ] `APPROVE` approves a test pending post
- [ ] Admin dashboard shows command in brief delivery log

---

*Last updated: May 2026 — Kova Daily Brief multi-channel delivery*
