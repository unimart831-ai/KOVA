# ============================================================================
# KOVA AGENT — EMAIL SYSTEM GUIDE
# ============================================================================
# Complete reference for the transactional email system.
# Covers architecture, email types, templates, admin dashboard,
# adding new emails, and Resend webhook tracking.
#
# Last Updated: April 5, 2026
# ============================================================================


# TABLE OF CONTENTS
# ─────────────────
# 1. Architecture Overview
# 2. Email Provider (Resend)
# 3. Email Types & Templates
# 4. How Emails Are Sent (The Flow)
# 5. EmailLog Model (Audit Trail)
# 6. Celery Tasks (Async Sending)
# 7. EmailService API Reference
# 8. Wiring Points (Where Emails Trigger)
# 9. Admin Dashboard (Monitoring)
# 10. Resend Webhooks (Delivery Tracking)
# 11. Adding a New Email Type
# 12. Template Authoring Guide
# 13. Configuration & Environment Variables
# 14. Troubleshooting


# ============================================================================
# 1. ARCHITECTURE OVERVIEW
# ============================================================================

## How it works (high level)

```
User action (signup, payment, invite, etc.)
    ↓
Django signal / view / billing webhook
    ↓
Celery task queued (never blocks the HTTP request)
    ↓
EmailService._send()
    ↓
├── Creates EmailLog entry (status = "queued")
├── Renders HTML template (extends base_email.html)
├── Sends via Django EmailMultiAlternatives → Resend SMTP
├── Updates EmailLog (status = "sent", sent_at timestamp)
    ↓
Resend delivers the email
    ↓
Resend webhook fires (delivered / opened / clicked / bounced)
    ↓
apps/emails/views.py::resend_webhook updates EmailLog status
```

## Key design decisions

1. **Single interface**: Every email in the platform routes through `EmailService._send()`.
   No email is ever sent using raw `send_mail()` elsewhere.

2. **Always async**: Real email sending happens in Celery tasks, never in HTTP request handlers.
   This keeps page loads fast and handles transient SMTP failures with retries.

3. **Full audit trail**: Every email gets an `EmailLog` row with timestamps for each lifecycle
   stage (queued → sent → delivered → opened → clicked). Failures are logged with error messages.

4. **Template inheritance**: All email templates extend `base_email.html` for consistent branding
   (purple header, white body, gray footer). To change the look of all emails, edit one file.


# ============================================================================
# 2. EMAIL PROVIDER (RESEND)
# ============================================================================

## Why Resend
- Already integrated (was set up during Sprint 8 for Daily Brief emails)
- Simple SMTP relay — works with Django's built-in `EmailMultiAlternatives`
- $20/mo for 50K emails (plenty for our scale)
- Webhooks for delivery/open/click tracking
- Good deliverability + DKIM/SPF support

## Configuration

### Environment Variables (Railway)
```
RESEND_API_KEY=re_xxxxxxxxxxxx      # Resend API key (also used as SMTP password)
DEFAULT_FROM_EMAIL=Kova Agent <noreply@kovaagent.com>
```

### Django Settings

**Production** (`config/settings/production.py`):
```python
EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
EMAIL_HOST = "smtp.resend.com"
EMAIL_PORT = 465
EMAIL_USE_SSL = True
EMAIL_HOST_USER = "resend"
EMAIL_HOST_PASSWORD = env("RESEND_API_KEY")
```

**Development** (`config/settings/development.py`):
```python
EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
# Emails print to terminal — no Resend account needed for local dev
```


# ============================================================================
# 3. EMAIL TYPES & TEMPLATES
# ============================================================================

## Complete email type registry

19 email types, each mapped to a template and default subject line.

| Category       | Type                    | Template                          | Default Subject                                |
|----------------|-------------------------|-----------------------------------|------------------------------------------------|
| **Auth**       | `verification`          | `emails/verification.html`        | Verify your email — Kova Agent                 |
| **Auth**       | `password_reset`        | `emails/password_reset.html`      | Reset your password — Kova Agent               |
| **Auth**       | `password_changed`      | `emails/password_changed.html`    | Your password was changed — Kova Agent         |
| **Onboarding** | `welcome`               | `emails/welcome.html`             | Welcome to Kova Agent! 🎉                      |
| **Billing**    | `payment_confirmation`  | `emails/payment_confirmation.html`| Payment confirmed — Kova Agent                 |
| **Billing**    | `invoice`               | `emails/invoice.html`             | Your invoice from Kova Agent                   |
| **Billing**    | `receipt`               | `emails/receipt.html`             | Payment receipt — Kova Agent                   |
| **Billing**    | `payment_failed`        | `emails/payment_failed.html`      | Payment failed — action needed                 |
| **Billing**    | `payment_reminder`      | `emails/payment_reminder.html`    | Your subscription is expiring soon             |
| **Billing**    | `plan_changed`          | `emails/plan_changed.html`        | Your plan has been updated — Kova Agent        |
| **Billing**    | `subscription_canceled` | `emails/subscription_canceled.html`| Your subscription has been canceled            |
| **Billing**    | `trial_ending`          | `emails/trial_ending.html`        | Your trial ends soon — Kova Agent              |
| **Teams**      | `team_invitation`       | `emails/team_invitation.html`     | You've been invited to join a team             |
| **Reports**    | `weekly_report`         | `emails/weekly_report.html`       | Your weekly performance report                 |
| **Reports**    | `daily_brief`           | `emails/daily_brief.html`         | Your Daily Brief — Kova Agent                  |
| **Product**    | `feature_announcement`  | `emails/feature_announcement.html`| What's new in Kova Agent                       |
| **Marketing**  | `promotional`           | `emails/promotional.html`         | Special offer from Kova Agent                  |
| **System**     | `usage_warning`         | `emails/usage_warning.html`       | You're approaching your plan limits            |
| **System**     | `system`                | `emails/system.html`              | Important update from Kova Agent               |

## Template design

All templates extend `base_email.html` which provides:
- Responsive table layout (works in all email clients including Outlook)
- Purple branded header with customizable background color, title, subtitle, badge
- White content body area
- Gray footer with "Manage your plan" + "Email preferences" links + © year
- Blocks: `{% block header_bg %}`, `{% block header_title %}`, `{% block content %}`, `{% block cta %}`


# ============================================================================
# 4. HOW EMAILS ARE SENT (THE FLOW)
# ============================================================================

## Typical flow: User signs up

```
1. User submits registration form
2. django-allauth creates User instance
3. post_save signal fires (apps/accounts/signals.py)
4. Signal calls: send_welcome_email.delay(str(user.pk))
5. Celery worker picks up the task
6. Task loads user from DB, calls: email_service.send_welcome(user)
7. EmailService._send() runs:
   a. Looks up template: emails/welcome.html
   b. Creates EmailLog(status="queued")
   c. Renders HTML with user context
   d. Sends via SMTP to Resend
   e. Updates EmailLog(status="sent", sent_at=now)
8. Resend delivers email to user's inbox
9. Resend webhook fires → EmailLog updated to "delivered"
10. User opens email → Resend webhook fires → EmailLog updated to "opened"
```

## Typical flow: Payment fails

```
1. Stripe webhook fires: invoice.payment_failed
2. apps/billing/services.py::_handle_invoice_failed() runs
3. User's subscription_status set to "past_due"
4. Calls: send_payment_failed_email.delay(str(user.pk))
5. Celery task → email_service.send_payment_failed(user)
6. User gets red-header "ACTION NEEDED" email with update payment CTA
```


# ============================================================================
# 5. EMAILLOG MODEL (AUDIT TRAIL)
# ============================================================================

```python
# apps/emails/models.py

class EmailLog(models.Model):
    id             = UUIDField(primary_key=True)
    user           = ForeignKey(User, null=True, blank=True)      # Who received it
    to_email       = EmailField()                                  # Recipient address
    from_email     = EmailField()                                  # Sender address
    email_type     = CharField(choices=EmailType)                  # e.g. "welcome"
    subject        = CharField(max_length=500)                     # Subject line
    status         = CharField(choices=Status)                     # Lifecycle stage
    provider_message_id = CharField(blank=True)                    # Resend's message ID
    metadata       = JSONField(default=dict)                       # Extra data (amount, plan, etc.)

    # Timestamps — full lifecycle tracking
    created_at     = DateTimeField(auto_now_add=True)              # When queued
    sent_at        = DateTimeField(null=True)                      # When SMTP accepted
    delivered_at   = DateTimeField(null=True)                      # When inbox received
    opened_at      = DateTimeField(null=True)                      # When user opened
    clicked_at     = DateTimeField(null=True)                      # When user clicked a link
    failed_at      = DateTimeField(null=True)                      # When sending failed

    error_message  = TextField(blank=True)                         # Error details if failed
```

### Status lifecycle
```
queued → sent → delivered → opened → clicked
              ↘ failed
              ↘ bounced
              ↘ spam (complaint)
```


# ============================================================================
# 6. CELERY TASKS (ASYNC SENDING)
# ============================================================================

All tasks are in `apps/emails/tasks.py`.

### Generic task
```python
send_email_task.delay(
    email_type="receipt",
    to_email="user@example.com",
    user_id="uuid-string",        # Optional
    context={"amount": "500"},    # Template variables
    subject="Custom subject",      # Optional override
    metadata={"source": "stripe"}, # Optional extra data
)
```

### Named convenience tasks
| Task                                 | Arguments                                          | Triggered From                |
|--------------------------------------|----------------------------------------------------|-------------------------------|
| `send_welcome_email`                 | `user_id`                                          | accounts/signals.py           |
| `send_payment_confirmation_email`    | `user_id, plan, amount, provider`                  | billing/services.py, mpesa    |
| `send_payment_failed_email`          | `user_id`                                          | billing/services.py           |
| `send_plan_changed_email`            | `user_id, old_plan, new_plan`                      | billing/services.py           |
| `send_subscription_canceled_email`   | `user_id`                                          | billing/services.py           |
| `send_payment_reminder_email`        | `user_id, days_until_expiry`                       | billing/tasks.py              |
| `send_team_invitation_email`         | `to_email, team_name, inviter_name, invite_url`    | teams/views.py                |
| `send_weekly_report_email`           | `user_id`                                          | scheduled (Monday 8AM)        |
| `send_feature_announcement_email`    | `user_id, title, description, cta_url`             | admin dashboard broadcast     |
| `send_usage_warning_email`           | `user_id, resource, current, limit`                | (manual / future automation)  |
| `send_weekly_reports_all`            | (no args — scheduled task)                         | Celery Beat weekly            |

### Retry behavior
- All tasks: `max_retries=3`, `default_retry_delay=60` seconds
- Exponential backoff: 60s → 120s → 240s
- On final failure, EmailLog gets status=FAILED with error message


# ============================================================================
# 7. EMAILSERVICE API REFERENCE
# ============================================================================

Import:
```python
from apps.messaging.emails.services import email_service
```

### Core method
```python
email_service._send(
    email_type="welcome",           # Required — key from EMAIL_TEMPLATES
    to_email="user@example.com",    # Required — recipient
    context={"key": "value"},       # Optional — template variables
    user=user_instance,             # Optional — links EmailLog to user
    subject="Custom subject",       # Optional — overrides default
    metadata={"source": "admin"},   # Optional — stored in EmailLog.metadata
)
```

### Convenience methods
```python
# Auth
email_service.send_welcome(user)
email_service.send_password_changed(user)

# Billing
email_service.send_payment_confirmation(user, amount="500 KES", plan="Kazi", provider="mpesa")
email_service.send_payment_failed(user)
email_service.send_plan_changed(user, old_plan="Jipange", new_plan="Kazi")
email_service.send_subscription_canceled(user)
email_service.send_payment_reminder(user, days_until_expiry=3)
email_service.send_trial_ending(user, days_left=2)
email_service.send_invoice(user, amount="79", plan="Growth", invoice_date="2026-04-01")
email_service.send_receipt(user, amount="79", plan="Growth", receipt_number="INV-001")

# Teams
email_service.send_team_invitation(
    to_email="new@example.com",
    inviter_name="James",
    team_name="Acme Corp",
    invite_url="https://kovaagent.com/teams/invite/abc123",
)

# Reports
email_service.send_weekly_report(user, report_data={"posts_created": 12, "posts_published": 8})

# Product / Marketing
email_service.send_feature_announcement(user, "AI Video", "Generate video content from text seeds")
email_service.send_promotional(user, "50% Off Upgrade", "Limited time offer for Growth plan", "Upgrade Now", "/billing/")

# System
email_service.send_usage_warning(user, resource="Posts", current=45, limit=50)
```


# ============================================================================
# 8. WIRING POINTS (WHERE EMAILS TRIGGER)
# ============================================================================

Every email trigger in the codebase:

| File                             | Event                        | Email Type              |
|----------------------------------|------------------------------|-------------------------|
| `apps/accounts/signals.py`      | User created (post_save)     | `welcome`               |
| `apps/billing/services.py`      | Checkout completed (Stripe)  | `payment_confirmation`  |
| `apps/billing/services.py`      | Subscription updated         | `plan_changed`          |
| `apps/billing/services.py`      | Subscription deleted         | `subscription_canceled` |
| `apps/billing/services.py`      | Invoice paid (Stripe)        | `receipt`               |
| `apps/billing/services.py`      | Invoice failed (Stripe)      | `payment_failed`        |
| `apps/billing/tasks.py`         | M-Pesa subscription past due | `payment_reminder` (0d) |
| `apps/billing/tasks.py`         | M-Pesa expiring in ≤3 days   | `payment_reminder` (Xd) |
| `apps/billing/mpesa_services.py`| M-Pesa payment success       | `payment_confirmation`  |
| `apps/briefs/tasks.py`          | Daily brief generated        | `daily_brief`           |
| `apps/teams/views.py`           | Team invitation created      | `team_invitation`       |
| `apps/emails/tasks.py`          | Celery Beat (Monday 8AM)     | `weekly_report` (all)   |
| Admin dashboard                 | "Send test email" button     | `system` (test)         |
| Admin dashboard                 | "Send broadcast" form        | `feature_announcement`  |


# ============================================================================
# 9. ADMIN DASHBOARD (MONITORING)
# ============================================================================

Access: `/dashboard/emails/` (staff only)

### Overview page (`/dashboard/emails/`)
- **Stat cards**: Sent (7d), delivery rate, open rate, failed count
- **Volume chart**: 30-day bar chart of daily email volume (Chart.js)
- **Breakdown by type**: Which email types are sent most
- **Breakdown by status**: delivered vs sent vs failed vs bounced
- **Recent emails table**: Last 20 emails with clickable rows → detail view
- **Recent failures**: Red-bordered section showing failed/bounced emails with errors
- **Quick actions**:
  - "Send test email" — sends a system email to your own address (validates delivery works)
  - "Send broadcast" — compose a feature announcement to all active users

### Email log (`/dashboard/emails/log/`)
- Filterable by type, status, and search (email/subject)
- Shows last 100 emails with sent/delivered/opened timestamps
- Click any row to view full detail

### Email detail (`/dashboard/emails/<uuid>/`)
- Full metadata: to, from, user, type, subject
- Status badge with color coding
- Timeline: created → sent → delivered → opened → clicked (with timestamps)
- Error message display (if failed)
- Metadata JSON viewer


# ============================================================================
# 10. RESEND WEBHOOKS (DELIVERY TRACKING)
# ============================================================================

## Endpoint
`POST /emails/webhooks/resend/`

## How it works
1. Resend sends a POST request for delivery events
2. `apps/emails/views.py::resend_webhook` handles it
3. Looks up `EmailLog` by `provider_message_id`
4. Updates status + timestamp based on event type

## Supported events
| Resend Event     | EmailLog Status | Timestamp Updated |
|------------------|-----------------|-------------------|
| `email.delivered`| `delivered`     | `delivered_at`    |
| `email.opened`   | `opened`        | `opened_at`       |
| `email.clicked`  | `clicked`       | `clicked_at`      |
| `email.bounced`  | `bounced`       | `failed_at`       |
| `email.complained`| `spam`         | `failed_at`       |

## Setup in Resend dashboard
1. Go to Resend → webhooks
2. Add endpoint: `https://kovaagent.com/emails/webhooks/resend/`
3. Select events: delivered, opened, clicked, bounced, complained
4. Save — Resend will start posting events


# ============================================================================
# 11. ADDING A NEW EMAIL TYPE
# ============================================================================

Step-by-step process for adding a new email:

### Step 1: Add to EmailLog.EmailType
```python
# apps/emails/models.py — add choice to the relevant section
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
  Your email body here. Use inline styles (email clients ignore CSS classes).
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
    return self._send(
        "my_new_type", user.email, user=user,
        context={"custom_data": custom_data},
    )
```

### Step 5: Add Celery task (optional)
```python
# apps/emails/tasks.py
@shared_task(name="emails.send_my_new_type")
def send_my_new_type_email(user_id, custom_data):
    from apps.messaging.emails.services import email_service
    from django.contrib.auth import get_user_model
    user = get_user_model().objects.get(pk=user_id)
    email_service.send_my_new_type(user, custom_data)
```

### Step 6: Wire it in
```python
# In whatever view/signal/task triggers this email:
from apps.messaging.emails.tasks import send_my_new_type_email
send_my_new_type_email.delay(str(user.pk), "some data")
```

### Step 7: Make migration
```bash
python manage.py makemigrations emails
python manage.py migrate
```


# ============================================================================
# 12. TEMPLATE AUTHORING GUIDE
# ============================================================================

## Rules for email HTML

1. **Use inline styles only** — Email clients strip `<style>` tags. Every element needs
   `style="..."` attributes.

2. **Use tables for layout** — Flexbox/grid don't work in Outlook. `base_email.html` already
   handles this with a centered 600px table layout.

3. **Keep images hosted** — Reference images via absolute URLs, not relative paths.

4. **Test in multiple clients** — Outlook, Gmail, Apple Mail all render differently.
   Litmus or Email on Acid for testing.

## Available blocks in base_email.html

| Block              | Purpose                           | Default                  |
|--------------------|-----------------------------------|--------------------------|
| `title`            | `<title>` tag (preview text)      | "Kova Agent"             |
| `header_bg`        | Header background color           | `#7c3aed` (purple)       |
| `header_badge`     | Small badge in header             | (empty)                  |
| `header_title`     | Main header text                  | "Kova Agent"             |
| `header_subtitle`  | Smaller text under title          | (empty)                  |
| `content`          | Main body content                 | (empty)                  |
| `cta`              | Call-to-action button row         | (empty)                  |

## Context variables available in every template

These are injected by `EmailService._send()` automatically:

| Variable         | Description                        |
|------------------|------------------------------------|
| `site_url`       | Base URL (e.g. `https://kovaagent.com`) |
| `current_year`   | Current year (for © footer)        |
| `user`           | User instance (if provided)        |
| `first_name`     | User's first name or email prefix  |

## Color conventions

| Email category | Header color | Hex       |
|----------------|-------------|-----------|
| Default        | Purple      | `#7c3aed` |
| Success        | Green       | `#059669` |
| Error/Urgent   | Red         | `#dc2626` |
| Warning        | Amber       | `#d97706` |
| Info/Team      | Blue        | `#2563eb` |
| Canceled       | Gray        | `#6b7280` |


# ============================================================================
# 13. CONFIGURATION & ENVIRONMENT VARIABLES
# ============================================================================

| Variable               | Required | Default                              | Description                    |
|------------------------|----------|--------------------------------------|--------------------------------|
| `RESEND_API_KEY`       | Prod only| —                                    | Resend SMTP password           |
| `DEFAULT_FROM_EMAIL`   | Yes      | `Kova Agent <noreply@kovaagent.com>` | Sender address for all emails  |
| `SITE_URL`             | Yes      | `http://localhost:8000`              | Base URL (used in email links) |

## Files involved

```
apps/emails/
├── __init__.py
├── admin.py          # Django admin for EmailLog
├── apps.py           # AppConfig
├── models.py         # EmailLog model
├── services.py       # EmailService class + EMAIL_TEMPLATES registry
├── tasks.py          # Celery tasks for async sending
├── urls.py           # Resend webhook endpoint
├── views.py          # Webhook handler
└── migrations/
    └── 0001_initial.py

templates/emails/
├── base_email.html           # Master email layout
├── welcome.html              # Onboarding
├── verification.html         # Email verification
├── password_reset.html       # Password reset
├── password_changed.html     # Password change confirmation
├── payment_confirmation.html # Payment success
├── payment_failed.html       # Payment failure
├── plan_changed.html         # Plan upgrade/downgrade
├── subscription_canceled.html# Subscription canceled
├── payment_reminder.html     # Expiry reminder
├── trial_ending.html         # Trial expiring
├── invoice.html              # Invoice details
├── receipt.html              # Payment receipt
├── team_invitation.html      # Team invite
├── weekly_report.html        # Weekly performance
├── daily_brief.html          # Daily brief wrapper
├── feature_announcement.html # New feature
├── promotional.html          # Promo / marketing
├── usage_warning.html        # Plan limit warning
└── system.html               # Generic system notification

templates/admin_dashboard/emails/
├── overview.html             # Email dashboard (stats, chart, actions)
├── log.html                  # Filterable email log
└── detail.html               # Single email detail view
```


# ============================================================================
# 14. TROUBLESHOOTING
# ============================================================================

### Emails not sending in development
**Expected.** Development uses `console.EmailBackend` — emails print to terminal output.
Check your terminal/Celery worker output.

### Emails not sending in production
1. Check `RESEND_API_KEY` is set in Railway environment variables
2. Check Celery worker is running (`celery -A config worker -l info`)
3. Check EmailLog in admin: `/admin/emails/emaillog/` — look for status=FAILED rows
4. Check error_message on failed EmailLog entries

### Webhook events not updating EmailLog
1. Verify webhook URL in Resend dashboard: `https://kovaagent.com/emails/webhooks/resend/`
2. Check `provider_message_id` is being captured (needs Resend to return it in SMTP response)
3. CSRF: The webhook endpoint is `@csrf_exempt` — verify this decorator is present

### Template rendering errors
```bash
# Test all templates load correctly
python manage.py shell -c "
from django.template.loader import get_template
from apps.messaging.emails.services import EMAIL_TEMPLATES
for key, (path, _) in EMAIL_TEMPLATES.items():
    get_template(path)
    print(f'  ✓ {key}: {path}')
print('All templates OK')
"
```

### Admin dashboard shows no data
Normal on a fresh deployment. EmailLog entries are created when emails are sent.
Use the "Send test email" button on `/dashboard/emails/` to create your first entry.


# ============================================================================
# END OF EMAIL SYSTEM GUIDE
# ============================================================================
