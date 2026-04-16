# Kova Agent — Complete Email Documentation

> Last Updated: April 16, 2026

---

## Table of Contents

1. [Architecture Overview](#1-architecture-overview)
2. [Email Provider — Resend](#2-email-provider--resend)
3. [Resend Setup Guide](#3-resend-setup-guide)
4. [Environment Variables](#4-environment-variables)
5. [Django Settings by Environment](#5-django-settings-by-environment)
6. [Email Types & Templates](#6-email-types--templates)
7. [How Emails Are Sent](#7-how-emails-are-sent)
8. [EmailService API Reference](#8-emailservice-api-reference)
9. [Celery Tasks](#9-celery-tasks)
10. [Celery Beat Schedule](#10-celery-beat-schedule)
11. [Data Models](#11-data-models)
12. [Email Marketing Engine](#12-email-marketing-engine)
13. [Webhook System](#13-webhook-system)
14. [Email Verification (Signup)](#14-email-verification-signup)
15. [Unsubscribe System](#15-unsubscribe-system)
16. [Admin Dashboard](#16-admin-dashboard)
17. [URL Routes](#17-url-routes)
18. [Plan Limits](#18-plan-limits)
19. [Adding a New Email Type](#19-adding-a-new-email-type)
20. [Template Authoring Guide](#20-template-authoring-guide)
21. [Wiring Points](#21-wiring-points)
22. [Troubleshooting](#22-troubleshooting)

---

## 1. Architecture Overview

### High-Level Flow

```
User action (signup, payment, invite, etc.)
        ↓
Django signal / view / billing webhook
        ↓
Celery task queued (never blocks HTTP request)
        ↓
EmailService._send()
    ├── Creates EmailLog (status = "queued")
    ├── Renders HTML template (extends base_email.html)
    ├── Sets Message-ID header with log UUID
    ├── Sends via Django EmailMultiAlternatives → Resend SMTP
    └── Updates EmailLog (status = "sent")
        ↓
Resend delivers to recipient's inbox
        ↓
Resend webhook fires (delivered / opened / clicked / bounced / complained)
        ↓
resend_webhook view → updates EmailLog status + timestamps
        ↓
Bounce/complaint → auto-updates EmailSubscriber status
```

### Key Design Decisions

| Decision | Why |
|---|---|
| **Single interface** | Every email routes through `EmailService._send()`. No raw `send_mail()` calls anywhere. |
| **Always async** | Real sending happens in Celery tasks, never in HTTP handlers. Pages stay fast. |
| **Full audit trail** | Every email gets an `EmailLog` row tracking its entire lifecycle. |
| **Template inheritance** | All emails extend `base_email.html` — change branding in one place. |
| **Webhook correlation** | Custom `Message-ID` header embeds log UUID for reliable webhook matching. |
| **Auto-bounce handling** | 3 bounces auto-marks subscriber as bounced. Complaints mark immediately. |

### File Map

```
apps/emails/
├── models.py              # EmailLog, EmailSubscriber, EmailList, EmailCampaign, EmailSequence, SequenceEnrollment
├── services.py            # EmailService class (singleton: email_service)
├── tasks.py               # 18+ Celery tasks + campaign send + sequence processing
├── views.py               # Resend webhook handler + one-click unsubscribe
├── marketing_views.py     # Marketing dashboard, subscribers, lists, campaigns, sequences
├── forms.py               # EmailSubscriberForm, EmailListForm, EmailCampaignForm
├── urls.py                # All email URL routes
└── admin.py               # Django admin registration

templates/emails/
├── base_email.html        # Master email layout (purple header, white body, gray footer)
├── welcome.html           # Welcome email
├── verification.html      # Email verification
├── password_reset.html    # Password reset
├── payment_*.html         # Billing emails (6 templates)
├── team_invitation.html   # Team invite
├── weekly_report.html     # Performance report
├── daily_brief.html       # Daily brief
├── promotional.html       # Marketing campaigns
├── partner_*.html         # Partner program emails (6 templates)
└── system.html            # System notifications

config/settings/
├── base.py                # CELERY_BEAT_SCHEDULE, allauth config, email defaults
├── development.py         # Console backend, verification disabled
└── production.py          # Resend SMTP, verification mandatory
```

---

## 2. Email Provider — Resend

### Why Resend

- **Simple SMTP relay** — works with Django's built-in `EmailMultiAlternatives`, no custom SDK
- **Webhooks** — delivery, open, click, bounce, complaint tracking via Svix
- **Affordable** — Free tier: 3,000 emails/month. Paid: $20/month for 50K emails
- **Good deliverability** — built-in DKIM, SPF, DMARC support
- **Dashboard** — see every email sent, delivery status, open/click rates

### How It Connects

```
Django EmailMultiAlternatives
    ↓ SMTP (port 465, SSL)
smtp.resend.com
    ↓
EMAIL_HOST_USER = "resend"
EMAIL_HOST_PASSWORD = RESEND_API_KEY
```

Resend acts as an SMTP relay. Django sends via standard SMTP, Resend handles deliverability, tracking pixels, and webhooks. No proprietary SDK required.

---

## 3. Resend Setup Guide

### Step 1: Create Account

1. Go to [resend.com](https://resend.com) and sign up
2. Free tier gives 3,000 emails/month — enough to start

### Step 2: Add & Verify Domain

1. Resend dashboard → **Domains** → **Add Domain**
2. Enter your sending domain (e.g., `kovaagent.com` or `yourdomain.xyz`)
3. Resend provides **3 DNS records** to add at your domain registrar:

| Record Type | Name | Purpose |
|---|---|---|
| TXT | SPF | Authorizes Resend to send on your behalf |
| TXT | DKIM | Cryptographic email authentication |
| TXT | DMARC | Policy for failed authentication |

4. Add records in your DNS provider (Cloudflare, Namecheap, etc.)
5. Click **Verify** in Resend — takes 5-60 minutes (rarely up to 48 hours)

> **No custom domain yet?** Use `onboarding@resend.dev` as sender. Resend will only deliver to the email you signed up with — enough for testing the full flow.

> **Using Railway's default URL?** Your app URL (`*.up.railway.app`) and email sending domain don't need to match. Buy a cheap `.xyz` domain ($1/year) just for email DNS records. Your app can stay on Railway's URL.

### Step 3: Generate API Key

1. Resend dashboard → **API Keys** → **Create API Key**
2. Name: `kova-production`
3. Permission: **Sending access**
4. Copy the key (starts with `re_`) — only shown once

### Step 4: Set Up Webhook

1. Resend dashboard → **Webhooks** → **Add Webhook**
2. **Endpoint URL:** `https://your-domain.com/emails/webhooks/resend/`
3. **Select events:**
   - `email.sent`
   - `email.delivered`
   - `email.opened`
   - `email.clicked`
   - `email.bounced`
   - `email.complained`
4. After creating → copy the **Signing Secret** (starts with `whsec_`)

### Step 5: Set Environment Variables

Add these to your Railway project → **Variables** tab:

```
RESEND_API_KEY=re_your_key_here
RESEND_WEBHOOK_SECRET=whsec_your_secret_here
DEFAULT_FROM_EMAIL=Kova Agent <noreply@yourdomain.com>
SITE_URL=https://your-app-url.com
```

Then redeploy.

### Step 6: Verify

1. Sign up on your production site with a real email
2. You should receive a verification email
3. Check Resend dashboard → **Emails** tab for delivery status
4. Test webhook: Resend dashboard → **Webhooks** → **Send Test**

---

## 4. Environment Variables

| Variable | Required | Default | Description |
|---|---|---|---|
| `RESEND_API_KEY` | Yes (production) | `""` | Resend API key. Also used as SMTP password. |
| `RESEND_WEBHOOK_SECRET` | Yes (production) | `""` | Svix signing secret for webhook verification. Starts with `whsec_`. |
| `DEFAULT_FROM_EMAIL` | Yes | `Kova Agent <noreply@kovaagent.com>` | Sender address. Domain must match verified Resend domain. |
| `SITE_URL` | Yes | `http://localhost:8000` | Base URL for links in emails (unsubscribe, CTAs, etc.). |
| `EMAIL_BACKEND` | No | Console (dev) / SMTP (prod) | Django email backend. Auto-configured based on `RESEND_API_KEY`. |

---

## 5. Django Settings by Environment

### Development (`config/settings/development.py`)

```python
EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"  # prints to terminal
ACCOUNT_EMAIL_VERIFICATION = "none"                                # skip verification
CELERY_TASK_ALWAYS_EAGER = True                                    # tasks run synchronously
```

- Emails print to terminal as formatted HTML — no Resend account needed
- Email verification disabled so you can sign up instantly
- Celery tasks execute inline (no Redis/worker needed)

### Production (`config/settings/production.py`)

```python
# When RESEND_API_KEY is set:
EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
EMAIL_HOST = "smtp.resend.com"
EMAIL_PORT = 465
EMAIL_USE_SSL = True
EMAIL_HOST_USER = "resend"
EMAIL_HOST_PASSWORD = RESEND_API_KEY
ACCOUNT_EMAIL_VERIFICATION = "mandatory"

# When RESEND_API_KEY is NOT set:
EMAIL_BACKEND = "django.core.mail.backends.filebased.EmailBackend"
EMAIL_FILE_PATH = "/tmp/kova-emails"
ACCOUNT_EMAIL_VERIFICATION = "none"
```

- Real SMTP delivery through Resend when API key is configured
- Falls back to file-based backend if no key (emails saved to `/tmp/kova-emails`)
- Email verification mandatory only when Resend is properly configured

### Base Settings (`config/settings/base.py`)

```python
ACCOUNT_LOGIN_METHODS = {"email"}                       # email-only login
ACCOUNT_SIGNUP_FIELDS = ["email*", "password1*", "password2*"]
ACCOUNT_UNIQUE_EMAIL = True
ACCOUNT_EMAIL_VERIFICATION = "mandatory"                # base default
ACCOUNT_LOGIN_ON_EMAIL_CONFIRMATION = True              # auto-login after confirm
ACCOUNT_SIGNUP_REDIRECT_URL = "/accounts/onboarding/"   # post-signup destination
```

---

## 6. Email Types & Templates

### Complete Registry (27 email types)

| Category | Type Key | Template | Default Subject |
|---|---|---|---|
| **Auth** | `verification` | `emails/verification.html` | Verify your email — Kova Agent |
| **Auth** | `password_reset` | `emails/password_reset.html` | Reset your password — Kova Agent |
| **Auth** | `password_changed` | `emails/password_changed.html` | Your password was changed — Kova Agent |
| **Onboarding** | `welcome` | `emails/welcome.html` | Welcome to Kova Agent! 🎉 |
| **Billing** | `payment_confirmation` | `emails/payment_confirmation.html` | Payment confirmed — Kova Agent |
| **Billing** | `invoice` | `emails/invoice.html` | Your invoice from Kova Agent |
| **Billing** | `receipt` | `emails/receipt.html` | Payment receipt — Kova Agent |
| **Billing** | `payment_failed` | `emails/payment_failed.html` | Payment failed — action needed |
| **Billing** | `payment_reminder` | `emails/payment_reminder.html` | Your subscription is expiring soon |
| **Billing** | `plan_changed` | `emails/plan_changed.html` | Your plan has been updated — Kova Agent |
| **Billing** | `subscription_canceled` | `emails/subscription_canceled.html` | Your subscription has been canceled |
| **Billing** | `trial_ending` | `emails/trial_ending.html` | Your trial ends soon — Kova Agent |
| **Teams** | `team_invitation` | `emails/team_invitation.html` | You've been invited to join a team on Kova Agent |
| **Reports** | `weekly_report` | `emails/weekly_report.html` | Your weekly performance report — Kova Agent |
| **Reports** | `daily_brief` | `emails/daily_brief.html` | Your Daily Brief — Kova Agent |
| **Product** | `feature_announcement` | `emails/feature_announcement.html` | What's new in Kova Agent |
| **Marketing** | `promotional` | `emails/promotional.html` | Special offer from Kova Agent |
| **Partners** | `partner_app_received` | `emails/partner_app_received.html` | We received your Growth Partner application |
| **Partners** | `partner_app_approved` | `emails/partner_app_approved.html` | You're approved! Welcome to Growth Partners 🎉 |
| **Partners** | `partner_approved_noacc` | `emails/partner_approved_no_account.html` | You're approved! Create your account 🎉 |
| **Partners** | `partner_app_rejected` | `emails/partner_app_rejected.html` | Update on your Growth Partner application |
| **Partners** | `partner_new_referral` | `emails/partner_new_referral.html` | New referral! Someone signed up with your link 🔥 |
| **Partners** | `partner_milestone` | `emails/partner_milestone.html` | Milestone achieved! You've unlocked a bonus 🏆 |
| **System** | `usage_warning` | `emails/usage_warning.html` | You're approaching your plan limits |
| **System** | `system` | `emails/system.html` | Important update from Kova Agent |

### Template Design

All templates extend `base_email.html`:

- **Purple branded header** — customizable background color, title, subtitle, badge
- **White content body** — responsive table layout (works in Outlook)
- **Gray footer** — "Manage your plan" + "Email preferences" links + copyright year
- **Unsubscribe link** — auto-injected for marketing emails

Available template blocks:

| Block | Purpose | Default |
|---|---|---|
| `title` | `<title>` tag (email preview text) | "Kova Agent" |
| `header_bg` | Header background color | `#7c3aed` (purple) |
| `header_badge` | Small badge text in header | empty |
| `header_title` | Main header text | "Kova Agent" |
| `header_subtitle` | Smaller text under title | empty |
| `content` | Main email body | empty |
| `cta` | Call-to-action button row | empty |

### Context Variables (Auto-Injected)

Every template automatically receives:

```python
{
    "site_url": "https://kovaagent.com",       # from SITE_URL setting
    "current_year": 2026,                       # for footer copyright
    "user": <User instance>,                    # if user was provided
    "first_name": "John",                       # user.first_name or email prefix
    "unsubscribe_url": "https://...token...",   # if subscriber exists
}
```

---

## 7. How Emails Are Sent

### Example: User Signs Up

```
1. User submits registration form
2. django-allauth creates User instance
3. post_save signal fires (apps/accounts/signals.py)
4. Signal calls: send_welcome_email.delay(str(user.pk))
5. Celery worker picks up the task
6. Task loads user from DB
7. Calls: email_service.send_welcome(user)
8. EmailService._send() runs:
   a. Looks up template: emails/welcome.html
   b. Creates EmailLog (status="queued")
   c. Renders HTML with user context
   d. Sets Message-ID header: <log_uuid@domain>
   e. Adds List-Unsubscribe headers (if subscriber exists)
   f. Sends via SMTP to Resend
   g. Updates EmailLog (status="sent", sent_at=now)
9. Resend delivers to inbox
10. Webhook fires → EmailLog updated to "delivered"
11. User opens → webhook → EmailLog updated to "opened"
```

### Example: Payment Fails

```
1. Stripe webhook: invoice.payment_failed
2. apps/billing/services.py::_handle_invoice_failed()
3. Sets subscription_status = "past_due"
4. Calls: send_payment_failed_email.delay(str(user.pk))
5. Celery → email_service.send_payment_failed(user)
6. User receives red-header "ACTION NEEDED" email
```

### Example: Campaign Sent

```
1. User clicks "Send Campaign" on campaign detail page
2. campaign_send view validates: status, target_list, subscriber count, plan limits
3. Calls: send_campaign_task.delay(str(campaign.pk))
4. Task sets campaign.status = "sending"
5. Iterates all active subscribers on target list
6. For each subscriber:
   a. Creates EmailLog
   b. Builds email with campaign HTML content
   c. Sets Message-ID, List-Unsubscribe headers
   d. Sends via SMTP
7. Updates campaign: total_sent, status = "sent", sent_at
```

---

## 8. EmailService API Reference

### Import

```python
from apps.emails.services import email_service
```

### Core Method

```python
email_service._send(
    email_type="welcome",           # Required — key from EMAIL_TEMPLATES
    to_email="user@example.com",    # Required — recipient
    context={"key": "value"},       # Optional — template variables
    user=user_instance,             # Optional — links EmailLog to user
    subject="Custom subject",       # Optional — overrides default
    metadata={"source": "admin"},   # Optional — stored in EmailLog.metadata
)
# Returns: EmailLog instance
```

### Convenience Methods

**Authentication:**
```python
email_service.send_welcome(user)
email_service.send_password_changed(user)
```

**Billing:**
```python
email_service.send_payment_confirmation(user, amount="500 KES", plan="Growth", provider="stripe", receipt_number="")
email_service.send_payment_failed(user, plan=None)
email_service.send_plan_changed(user, old_plan="Starter", new_plan="Growth")
email_service.send_subscription_canceled(user)
email_service.send_payment_reminder(user, days_until_expiry=3)
email_service.send_trial_ending(user, days_left=2)
email_service.send_invoice(user, amount="79", plan="Growth", invoice_date="2026-04-01", invoice_number="")
email_service.send_receipt(user, amount="79", plan="Growth", receipt_number="INV-001", payment_method="")
```

**Teams:**
```python
email_service.send_team_invitation(
    to_email="new@example.com",
    inviter_name="James",
    team_name="Acme Corp",
    invite_url="https://kovaagent.com/teams/invite/abc123",
)
```

**Reports:**
```python
email_service.send_weekly_report(user, report_data={"posts_created": 12, "posts_published": 8})
```

**Product / Marketing:**
```python
email_service.send_feature_announcement(user, "AI Video", "Generate video from text", cta_url="/features/")
email_service.send_promotional(user, "50% Off", "Limited time offer", "Upgrade Now", "/billing/")
```

**Partners:**
```python
email_service.send_partner_application_received(to_email, full_name, user=None)
email_service.send_partner_application_approved(user, referral_code, dashboard_url="")
email_service.send_partner_approved_no_account(to_email, full_name)
email_service.send_partner_application_rejected(to_email, full_name, user=None, reason="")
email_service.send_partner_new_referral(partner_user, referred_email, total_referrals=0)
email_service.send_partner_milestone(partner_user, milestone_label, bonus_kes, extras="")
```

**System:**
```python
email_service.send_usage_warning(user, resource="Posts", current=45, limit=50)
```

---

## 9. Celery Tasks

All tasks are in `apps/emails/tasks.py`. Every task uses automatic retry with exponential backoff.

### Generic Task

```python
from apps.emails.tasks import send_email_task

send_email_task.delay(
    email_type="receipt",
    to_email="user@example.com",
    user_id="uuid-string",
    context={"amount": "500"},
    subject="Custom subject",
    metadata={"source": "stripe"},
)
```

### Named Convenience Tasks

| Task Name | Function | Arguments | Triggered From |
|---|---|---|---|
| `emails.send_welcome` | `send_welcome_email` | `user_id` | accounts/signals.py |
| `emails.send_payment_confirmation` | `send_payment_confirmation_email` | `user_id, amount, plan, provider, receipt_number` | billing/services.py |
| `emails.send_payment_failed` | `send_payment_failed_email` | `user_id, plan` | billing/services.py |
| `emails.send_plan_changed` | `send_plan_changed_email` | `user_id, old_plan, new_plan` | billing/services.py |
| `emails.send_subscription_canceled` | `send_subscription_canceled_email` | `user_id` | billing/services.py |
| `emails.send_payment_reminder` | `send_payment_reminder_email` | `user_id, days_until_expiry` | billing/tasks.py |
| `emails.send_team_invitation` | `send_team_invitation_email` | `to_email, inviter_name, team_name, invite_url` | teams/views.py |
| `emails.send_weekly_report` | `send_weekly_report_email` | `user_id, report_data` | Celery Beat |
| `emails.send_feature_announcement` | `send_feature_announcement_email` | `user_id, title, description, cta_url` | admin dashboard |
| `emails.send_usage_warning` | `send_usage_warning_email` | `user_id, resource, current, limit` | manual |
| `emails.send_partner_app_received` | `send_partner_app_received_email` | `to_email, full_name, user_id` | partners/views.py |
| `emails.send_partner_app_approved` | `send_partner_app_approved_email` | `user_id, referral_code` | admin dashboard |
| `emails.send_partner_approved_no_account` | `send_partner_app_approved_no_account_email` | `to_email, full_name` | admin dashboard |
| `emails.send_partner_app_rejected` | `send_partner_app_rejected_email` | `to_email, full_name, user_id, reason` | admin dashboard |
| `emails.send_partner_new_referral` | `send_partner_new_referral_email` | `partner_user_id, referred_email, total_referrals` | accounts/signals.py |
| `emails.send_partner_milestone` | `send_partner_milestone_email` | `partner_user_id, milestone_label, bonus_kes, extras` | partners logic |

### Campaign & Sequence Tasks

| Task Name | Function | Arguments | Triggered From |
|---|---|---|---|
| `emails.send_campaign` | `send_campaign_task` | `campaign_id` | campaign_send view (POST) |
| `emails.process_email_sequences` | `process_email_sequences` | (none) | Celery Beat (every 30 min) |
| `emails.check_trial_expiry_emails` | `check_trial_expiry_emails` | (none) | Celery Beat (daily) |
| `emails.send_weekly_reports_all` | `send_weekly_reports_all` | (none) | Celery Beat (weekly) |

### Retry Behavior

- Default: `max_retries=3`, `default_retry_delay=60` seconds
- Exponential backoff: 60s → 120s → 240s
- On final failure: `EmailLog.status = FAILED` with error message stored

---

## 10. Celery Beat Schedule

Email-related scheduled tasks in `CELERY_BEAT_SCHEDULE`:

| Beat Key | Task | Schedule | Purpose |
|---|---|---|---|
| `check-trial-expiry-emails` | `emails.check_trial_expiry_emails` | Daily | Send trial countdown emails at day 7, 3, 1, 0 |
| `send-weekly-reports` | `emails.send_weekly_reports_all` | Weekly | Performance summary to all active/trialing users |
| `process-email-sequences` | `emails.process_email_sequences` | Every 30 min | Advance drip sequence enrollments |

---

## 11. Data Models

### EmailLog

Audit trail for every email sent by the platform.

```
EmailLog
├── id                  UUID (primary key)
├── user                FK → User (nullable — for non-user emails like invites)
├── to_email            EmailField (indexed)
├── from_email          EmailField
├── email_type          CharField (27 choices)
├── subject             CharField(255)
├── status              CharField (queued → sent → delivered → opened → clicked | failed | bounced | spam)
├── provider_message_id CharField (Resend's message ID — for webhook correlation)
├── metadata            JSONField (extra context: plan, amount, campaign_id, etc.)
├── created_at          DateTimeField (auto)
├── sent_at             DateTimeField (nullable)
├── delivered_at        DateTimeField (nullable)
├── opened_at           DateTimeField (nullable)
├── clicked_at          DateTimeField (nullable)
├── failed_at           DateTimeField (nullable)
└── error_message       TextField (error details if failed)
```

**Status lifecycle:**
```
queued → sent → delivered → opened → clicked
              ↘ failed
              ↘ bounced
              ↘ spam (complaint)
```

### EmailSubscriber

Individual email subscribers belonging to a Kova user.

```
EmailSubscriber
├── id                  UUID
├── user                FK → User (the Kova user who owns this subscriber)
├── email               EmailField (indexed)
├── name                CharField(200)
├── source              CharField (kova_form / manual / import / social_bio / api / lead_sync)
├── source_form         FK → KovaForm (nullable)
├── lead                FK → Lead (nullable)
├── status              CharField (active / unsubscribed / bounced / complained)
├── tags                JSONField (list of tags)
├── engagement_score    FloatField (0-100)
├── metadata            JSONField
├── subscribed_at       DateTimeField (auto)
├── unsubscribed_at     DateTimeField (nullable)
├── bounce_count        PositiveSmallIntegerField (auto-bounced at 3)
└── unsubscribe_token   CharField(64, unique) — auto-generated on save
```

**Unique constraint:** `(user, email)` — one subscriber record per user-email pair.

**Bounce logic:** `record_bounce()` increments `bounce_count`. At 3 bounces → status becomes `bounced`.

### EmailList

Named subscription list or smart segment.

```
EmailList
├── id                  UUID
├── user                FK → User
├── name                CharField(200)
├── description         TextField
├── subscribers         M2M → EmailSubscriber
├── filter_rules        JSONField (smart list criteria: tags, source, engagement range)
├── is_smart            BooleanField (smart lists auto-populate from rules)
├── subscriber_count    PositiveIntegerField (cached)
├── created_at          DateTimeField
└── updated_at          DateTimeField
```

**Smart lists:** When `is_smart=True`, `get_active_subscribers()` builds a queryset from `filter_rules` instead of using the M2M. Supports filtering by tags, source, and minimum engagement score.

### EmailCampaign

A single email campaign (newsletter, announcement, promotion).

```
EmailCampaign
├── id                  UUID
├── user                FK → User
├── name                CharField(200) — internal name
├── subject             CharField(255)
├── preview_text        CharField(255)
├── html_content        TextField
├── text_content        TextField (plain text fallback)
├── from_name           CharField(200)
├── reply_to            EmailField
├── target_list         FK → EmailList (nullable)
├── status              CharField (draft → scheduled → sending → sent | cancelled)
├── scheduled_at        DateTimeField (nullable)
├── sent_at             DateTimeField (nullable)
├── total_sent          PositiveIntegerField
├── total_opened        PositiveIntegerField
├── total_clicked       PositiveIntegerField
├── total_bounced       PositiveIntegerField
├── total_unsubscribed  PositiveIntegerField
├── ai_generated        BooleanField
├── source_post         FK → Post (nullable) — if campaign was generated from a post
├── variant_of          FK → self (nullable) — A/B testing
├── variant_label       CharField(10) — "A", "B", "C"
├── created_at          DateTimeField
└── updated_at          DateTimeField
```

**Computed properties:** `open_rate` and `click_rate` (percentage based on `total_sent`).

### EmailSequence

Automated drip email sequence triggered by an event.

```
EmailSequence
├── id                  UUID
├── user                FK → User
├── name                CharField(200)
├── trigger_type        CharField (form_submission / tag_added / subscriber_added / lead_status_change / manual)
├── trigger_config      JSONField (form_id, tag_name, list_id, etc.)
├── is_active           BooleanField
├── created_at          DateTimeField
└── updated_at          DateTimeField
```

### EmailSequenceStep

A single step in an automated sequence.

```
EmailSequenceStep
├── id                  UUID
├── sequence            FK → EmailSequence
├── step_number         PositiveSmallIntegerField
├── delay_days          PositiveSmallIntegerField — days after previous step
├── delay_hours         PositiveSmallIntegerField — hours after previous step
├── subject             CharField(255)
├── html_content        TextField
├── text_content        TextField
└── ai_generated        BooleanField
```

**Unique constraint:** `(sequence, step_number)` — no duplicate step numbers.

### SequenceEnrollment

Tracks a subscriber's progress through a sequence.

```
SequenceEnrollment
├── id                  UUID
├── sequence            FK → EmailSequence
├── subscriber          FK → EmailSubscriber
├── current_step        PositiveSmallIntegerField (0-based start)
├── status              CharField (active / completed / paused / cancelled)
├── next_send_at        DateTimeField (nullable) — when to send the next step
├── enrolled_at         DateTimeField (auto)
└── completed_at        DateTimeField (nullable)
```

**Unique constraint:** `(sequence, subscriber)` — one enrollment per subscriber per sequence.

**Processing:** The `process_email_sequences` task runs every 30 minutes, finds enrollments where `next_send_at <= now`, sends the current step, and advances `current_step` + calculates the next `next_send_at` based on the next step's delay.

---

## 12. Email Marketing Engine

### Dashboard

**URL:** `/emails/marketing/`

Shows:
- Subscriber stats (total, active, unsubscribed)
- Campaign overview (draft, sent, sending)
- Sequence overview (active, total enrollments)
- Quick actions to create campaigns, lists, subscribers

### Subscribers

| URL | View | Purpose |
|---|---|---|
| `/emails/subscribers/` | `subscriber_list` | List all subscribers with status/search filters |
| `/emails/subscribers/add/` | `subscriber_add` | Add a subscriber manually |

### Lists

| URL | View | Purpose |
|---|---|---|
| `/emails/lists/` | `list_index` | All email lists |
| `/emails/lists/create/` | `list_create` | Create a new list |
| `/emails/lists/<id>/` | `list_detail` | List detail with subscribers |
| `/emails/lists/<id>/edit/` | `list_edit` | Edit list name/description/rules |

### Campaigns

| URL | View | Purpose |
|---|---|---|
| `/emails/campaigns/` | `campaign_list` | All campaigns |
| `/emails/campaigns/create/` | `campaign_create` | Create a new campaign |
| `/emails/campaigns/<id>/` | `campaign_detail` | Campaign detail with metrics + Send button |
| `/emails/campaigns/<id>/edit/` | `campaign_edit` | Edit draft/scheduled campaign |
| `/emails/campaigns/<id>/send/` | `campaign_send` | **POST** — queue campaign for sending |

**Campaign Send Flow:**
1. Only `draft` or `scheduled` campaigns can be sent
2. Must have a `target_list` with active subscribers
3. Checks plan limit (`email_campaigns_per_month`)
4. Queues `send_campaign_task` via Celery
5. Task iterates subscribers, sends each email, updates metrics

### Sequences

| URL | View | Purpose |
|---|---|---|
| `/emails/sequences/` | `sequence_list` | All sequences with step/enrollment counts |
| `/emails/sequences/<id>/` | `sequence_detail` | Sequence detail with steps and enrollments |

---

## 13. Webhook System

### Endpoint

`POST /emails/webhooks/resend/`

### Security

- **Signature verification** using Svix HMAC-SHA256
- Secret stored in `RESEND_WEBHOOK_SECRET` (starts with `whsec_`)
- If no secret configured: accepts with warning (dev mode)
- Rate limited: 60 requests/minute per IP

### Webhook Correlation (3-tier matching)

When Resend sends a webhook, the handler finds the matching `EmailLog` using:

1. **`provider_message_id`** — exact match on Resend's `email_id`
2. **Custom Message-ID header** — extracts log UUID from `<uuid@domain>` format in webhook headers
3. **Fallback** — matches by `to_email` + `sent` or `delivered` status + sent within last 48 hours

On first match, the handler backfills `provider_message_id` for future webhook correlation.

### Supported Events

| Resend Event | EmailLog Status | Timestamp Updated | Side Effects |
|---|---|---|---|
| `email.delivered` | `delivered` | `delivered_at` | — |
| `email.opened` | `opened` | `opened_at` (first open) | Won't downgrade from `clicked` |
| `email.clicked` | `clicked` | `clicked_at` (first click) | — |
| `email.bounced` | `bounced` | `failed_at` | Calls `subscriber.record_bounce()` → auto-bounced at 3 |
| `email.complained` | `spam` | — | Marks subscriber as `complained` |

---

## 14. Email Verification (Signup)

### How It Works

Kova uses **django-allauth** for authentication. Email verification is controlled by `ACCOUNT_EMAIL_VERIFICATION`.

| Environment | Setting | Behavior |
|---|---|---|
| **Development** | `"none"` | No verification — instant signup |
| **Production** (with Resend) | `"mandatory"` | Must verify email before login |
| **Production** (no Resend) | `"none"` | Falls back to no verification |

### Signup Flow (Production)

```
1. User submits signup form (email + password)
2. Allauth creates User (inactive session)
3. Allauth sends verification email via Resend SMTP
4. User sees "Check your email" page (verification_sent.html)
5. User clicks verification link
6. Lands on confirm page (email_confirm.html)
7. Clicks "Confirm email address"
8. ACCOUNT_LOGIN_ON_EMAIL_CONFIRMATION=True → auto-logged in
9. Redirected to /accounts/onboarding/
```

### Templates

- `templates/account/verification_sent.html` — "Check your email" page
- `templates/account/email_confirm.html` — Confirmation page with button
- Allauth's default email templates handle the actual verification email content

---

## 15. Unsubscribe System

### One-Click Unsubscribe (CAN-SPAM / GDPR Compliant)

**URL:** `/emails/unsubscribe/<token>/`

- Works with both **GET** (link in email) and **POST** (List-Unsubscribe header)
- No login required
- No confirmation page required
- Rate limited: 30/minute per IP
- CSRF exempt (must work from email clients)

### How It Works

1. Every `EmailSubscriber` gets a unique `unsubscribe_token` (auto-generated on save)
2. `EmailService._send()` generates an unsubscribe URL if a matching subscriber exists
3. The URL is injected into the template context as `{{ unsubscribe_url }}`
4. Two HTTP headers are added to every marketing email:
   - `List-Unsubscribe: <url>` — for email client "Unsubscribe" buttons (Gmail, Apple Mail)
   - `List-Unsubscribe-Post: List-Unsubscribe=One-Click` — RFC 8058 compliance

### What Happens on Unsubscribe

1. Token looked up → finds `EmailSubscriber`
2. Status set to `unsubscribed`
3. `unsubscribed_at` set to current time
4. Returns simple "You've been unsubscribed" response

---

## 16. Admin Dashboard

### Email Monitoring

**URL:** `/dashboard/emails/` (staff only)

**Overview page:**
- Stat cards: sent (7 days), delivery rate, open rate, failed count
- Volume chart: 30-day bar chart (Chart.js)
- Breakdown by type and status
- Recent emails table (last 20, clickable)
- Recent failures section
- Quick actions: "Send test email" + "Send broadcast"

**Email log:** `/dashboard/emails/log/`
- Filterable by type, status, and search
- Last 100 emails with timestamps

**Email detail:** `/dashboard/emails/<uuid>/`
- Full metadata, status badge
- Timeline: created → sent → delivered → opened → clicked
- Error message display, metadata JSON viewer

---

## 17. URL Routes

All routes are under `/emails/` (mounted in `config/urls.py`).

```
# Public (no login)
/emails/unsubscribe/<token>/              → one-click unsubscribe
/emails/webhooks/resend/                  → Resend webhook endpoint

# Marketing (login required)
/emails/marketing/                        → email marketing dashboard
/emails/subscribers/                      → subscriber list
/emails/subscribers/add/                  → add subscriber
/emails/lists/                            → all lists
/emails/lists/create/                     → create list
/emails/lists/<uuid>/                     → list detail
/emails/lists/<uuid>/edit/                → edit list
/emails/campaigns/                        → all campaigns
/emails/campaigns/create/                 → create campaign
/emails/campaigns/<uuid>/                 → campaign detail + send button
/emails/campaigns/<uuid>/edit/            → edit campaign
/emails/campaigns/<uuid>/send/            → send campaign (POST only)
/emails/sequences/                        → all sequences
/emails/sequences/<uuid>/                 → sequence detail
```

---

## 18. Plan Limits

| Feature | Starter | Growth | Pro | Agency |
|---|---|---|---|---|
| `email_subscribers` | 50 | 2,500 | 25,000 | Unlimited |
| `email_lists` | 1 | 5 | Unlimited | Unlimited |
| `email_campaigns_per_month` | 2 | 10 | Unlimited | Unlimited |
| `email_sequences` | 0 | 3 | Unlimited | Unlimited |

- Plan limits checked via `apps/billing/models.py::get_plan_limits(user)`
- Campaign send view enforces `email_campaigns_per_month` before queuing
- Subscriber/list/sequence limits enforced in respective create views

---

## 19. Adding a New Email Type

### Step 1: Add to EmailLog.EmailType choices

```python
# apps/emails/models.py
class EmailType(models.TextChoices):
    ...
    MY_NEW_TYPE = "my_new_type", "My New Email"
```

### Step 2: Create the template

```html
<!-- templates/emails/my_new_type.html -->
{% extends "emails/base_email.html" %}

{% block title %}My New Email{% endblock %}
{% block header_title %}Hello {{ first_name }}{% endblock %}

{% block content %}
<p style="margin:0;font-size:14px;line-height:1.7;color:#374151;">
  Your content here. Use inline styles (email clients ignore CSS classes).
</p>
{% endblock %}

{% block cta %}
<tr>
  <td align="center" style="padding:0 32px 28px;">
    <a href="{{ site_url }}/some-action/"
       style="display:inline-block;background-color:#7c3aed;color:#ffffff;
              text-decoration:none;font-size:14px;font-weight:600;
              padding:12px 32px;border-radius:8px;">
      Take Action
    </a>
  </td>
</tr>
{% endblock %}
```

### Step 3: Register in EMAIL_TEMPLATES

```python
# apps/emails/services.py — add to EMAIL_TEMPLATES dict
"my_new_type": ("emails/my_new_type.html", "Default Subject Line"),
```

### Step 4: Add convenience method (optional)

```python
# apps/emails/services.py — add to EmailService class
def send_my_new_type(self, user, custom_data):
    return self._send("my_new_type", user.email, user=user, context={"custom_data": custom_data})
```

### Step 5: Add Celery task (optional)

```python
# apps/emails/tasks.py
@shared_task(name="emails.send_my_new_type")
def send_my_new_type_email(user_id, custom_data):
    from apps.emails.services import email_service
    from django.contrib.auth import get_user_model
    user = get_user_model().objects.get(pk=user_id)
    email_service.send_my_new_type(user, custom_data)
```

### Step 6: Wire it in

```python
# Wherever this email triggers:
from apps.emails.tasks import send_my_new_type_email
send_my_new_type_email.delay(str(user.pk), "some data")
```

### Step 7: Migrate

```bash
python manage.py makemigrations emails
python manage.py migrate
```

---

## 20. Template Authoring Guide

### Rules for Email HTML

1. **Inline styles only** — email clients strip `<style>` tags
2. **Tables for layout** — flexbox/grid don't work in Outlook
3. **Absolute image URLs** — relative paths won't resolve
4. **600px max width** — standard for email rendering
5. **Test across clients** — Outlook, Gmail, Apple Mail all differ

### Example: Simple Announcement Email

```html
{% extends "emails/base_email.html" %}

{% block title %}{{ feature_title }}{% endblock %}
{% block header_bg %}#059669{% endblock %}
{% block header_badge %}NEW{% endblock %}
{% block header_title %}{{ feature_title }}{% endblock %}

{% block content %}
<tr>
  <td style="padding:24px 32px;">
    <p style="margin:0 0 16px;font-size:14px;line-height:1.7;color:#374151;">
      Hey {{ first_name }},
    </p>
    <p style="margin:0 0 16px;font-size:14px;line-height:1.7;color:#374151;">
      {{ feature_description }}
    </p>
  </td>
</tr>
{% endblock %}

{% block cta %}
<tr>
  <td align="center" style="padding:0 32px 28px;">
    <a href="{{ cta_url }}"
       style="display:inline-block;background-color:#7c3aed;color:#ffffff;
              text-decoration:none;font-size:14px;font-weight:600;
              padding:12px 32px;border-radius:8px;">
      Try it now →
    </a>
  </td>
</tr>
{% endblock %}
```

### Brand Colors

| Color | Hex | Usage |
|---|---|---|
| Purple (primary) | `#7c3aed` | Default header, CTA buttons |
| Green (success) | `#059669` | Payment confirmations, approvals |
| Red (danger) | `#dc2626` | Payment failures, urgent alerts |
| Amber (warning) | `#d97706` | Trial ending, usage warnings |
| Blue (info) | `#2563eb` | Feature announcements |

---

## 21. Wiring Points

Every place in the codebase that triggers an email:

| File | Event | Email Type |
|---|---|---|
| `apps/accounts/signals.py` | User created (post_save) | `welcome` |
| `apps/billing/services.py` | Stripe checkout completed | `payment_confirmation` |
| `apps/billing/services.py` | Subscription updated | `plan_changed` |
| `apps/billing/services.py` | Subscription deleted | `subscription_canceled` |
| `apps/billing/services.py` | Invoice paid (Stripe) | `receipt` |
| `apps/billing/services.py` | Invoice failed (Stripe) | `payment_failed` |
| `apps/billing/tasks.py` | M-Pesa subscription expiring | `payment_reminder` |
| `apps/billing/mpesa_services.py` | M-Pesa payment success | `payment_confirmation` |
| `apps/briefs/tasks.py` | Daily brief generated | `daily_brief` |
| `apps/teams/views.py` | Team invitation created | `team_invitation` |
| `apps/emails/tasks.py` | Celery Beat (daily) | `trial_ending` (day 7, 3, 1, 0) |
| `apps/emails/tasks.py` | Celery Beat (weekly) | `weekly_report` (all users) |
| `apps/emails/tasks.py` | Celery Beat (30 min) | Sequence step emails |
| `apps/emails/marketing_views.py` | "Send Campaign" button | Campaign emails via task |
| `apps/partners/views.py` | Partner application submitted | `partner_app_received` |
| `apps/partners/` (admin) | Application approved | `partner_app_approved` |
| `apps/partners/` (admin) | Application rejected | `partner_app_rejected` |
| `apps/accounts/signals.py` | Referral signup | `partner_new_referral` |
| Admin dashboard | "Send test email" button | `system` |
| Admin dashboard | "Send broadcast" form | `feature_announcement` |

---

## 22. Troubleshooting

| Problem | Likely Cause | Fix |
|---|---|---|
| Emails not sending in production | `RESEND_API_KEY` not set | Add to Railway env vars, redeploy |
| Emails go to `/tmp/kova-emails` | No Resend API key | Set `RESEND_API_KEY` in production |
| "Domain not verified" from Resend | DNS records not propagated | Wait up to 48 hours, re-verify in Resend dashboard |
| Verification email not arriving | Wrong `DEFAULT_FROM_EMAIL` domain | Must match your verified Resend domain |
| Emails land in spam | Missing DKIM/SPF/DMARC | Verify all 3 DNS records in Resend dashboard |
| Webhook returning 401 | `RESEND_WEBHOOK_SECRET` mismatch | Copy exact value from Resend dashboard |
| Webhook returning 400 | Malformed JSON payload | Check Resend webhook logs |
| "Webhook for unknown email_id" in logs | Normal for first webhooks | Handler uses 3-tier fallback; will auto-backfill `provider_message_id` |
| Campaign not sending | Campaign status not `draft`/`scheduled` | Check campaign status in admin |
| Campaign send button missing | Campaign already sent | Only draft/scheduled campaigns show the button |
| Sequence emails not advancing | `is_active=False` on sequence | Activate the sequence |
| Sequence emails not sending at all | `process-email-sequences` Beat task | Verify Celery Beat is running |
| Email verification disabled in production | `RESEND_API_KEY` not set | Set the key — verification auto-enables |
| `send_weekly_reports_all` not running | Celery Beat not started | Ensure `celery beat` process is running (Procfile `worker`) |
| Template not found error | Missing template file | Create in `templates/emails/` + register in `EMAIL_TEMPLATES` |
| Bounce count not incrementing | Webhook not matching subscriber | Check `EmailSubscriber` exists for that `user + email` |
| Unsubscribe link not in email | No `EmailSubscriber` record for recipient | Transactional emails (billing, etc.) don't have subscribers — expected |

### Useful Django Shell Commands

```python
# Check recent email logs
from apps.emails.models import EmailLog
EmailLog.objects.order_by('-created_at')[:10]

# Check failed emails
EmailLog.objects.filter(status='failed').order_by('-created_at')[:5]

# Check a subscriber's status
from apps.emails.models import EmailSubscriber
EmailSubscriber.objects.filter(email='user@example.com')

# Manually send a test email
from apps.emails.services import email_service
from apps.accounts.models import User
user = User.objects.get(email='your@email.com')
email_service.send_welcome(user)

# Check campaign status
from apps.emails.models import EmailCampaign
EmailCampaign.objects.filter(user=user)

# Check sequence enrollments
from apps.emails.models import SequenceEnrollment
SequenceEnrollment.objects.filter(status='active')
```

---

*This document covers the complete Kova Agent email system as of April 16, 2026.*
