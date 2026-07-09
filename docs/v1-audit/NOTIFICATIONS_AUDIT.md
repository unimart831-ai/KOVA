# Notifications Audit

**Date:** July 2026

---

## Overview

Kova has multiple notification channels serving different purposes. The WhatsApp-first vision means WhatsApp should be the PRIMARY notification channel for business owners.

---

## Notification Channels

### 1. WhatsApp Notifications (Primary)

| Component | Location | Status | Description |
|-----------|----------|--------|-------------|
| Daily Brief delivery | `briefs/tasks.py` | **Implemented** | Morning strategic brief via WhatsApp |
| Owner commands response | `briefs/whatsapp_commands.py` | **Implemented** | Replies to APPROVE, SCORE, LEADS, etc. |
| Campaign ready notification | `content/campaign_whatsapp.py` | **Implemented** | Campaign package ready for review |
| Snap-to-Sell confirmation | `products/owner_snap_whatsapp.py` | **Implemented** | Product created from photo |
| Customer follow-up nudge | `whatsapp/autopilot.py` | **Implemented** | 24h reminder for unanswered conversations |
| Brief WhatsApp log | `briefs/models.py` (BriefWhatsAppLog) | **Implemented** | Tracks brief delivery + owner reply |
| Stock alerts | `products/models.py` (StockAlert) | **Implemented** | Low stock notifications |
| AI draft ready | Via REPLIES command | **Implemented** | Engage agent drafts awaiting approval |

**Assessment:** Strong coverage of operational notifications via WhatsApp. The Daily Brief is the cornerstone — delivered every morning with key metrics, pending actions, and strategic recommendations.

---

### 2. In-App Notifications (Secondary)

| Component | Location | Status | Description |
|-----------|----------|--------|-------------|
| Notification model | `notifications/models.py` | **Implemented** | Generic notification with type, message, read status |
| NotificationPreference | `notifications/models.py` | **Implemented** | Per-type toggles |
| WebSocket consumer | `notifications/routing.py` | **Implemented** | Real-time push via `ws/updates/` |
| Bell icon + dropdown | `notifications/_bell.html`, `_dropdown.html` | **Implemented** | UI components |
| Notification list page | `notifications/list.html` | **Implemented** | Full history view |
| Preferences page | `notifications/preferences.html` | **Implemented** | User control over notification types |

**Assessment:** Standard in-app notification system. Appropriate as secondary channel for when users are on the web platform. WebSocket enables real-time delivery without polling.

---

### 3. Email Notifications

| Component | Location | Status | Description |
|-----------|----------|--------|-------------|
| Email service | `emails/services.py` | **Implemented** | Template registry for all email types |
| Welcome email | `emails/welcome.html` | **Implemented** | Post-signup |
| Daily brief email | `emails/daily_brief.html` | **Implemented** | Email version of brief |
| Weekly report | `emails/weekly_report.html` | **Implemented** | Weekly summary |
| Monthly report | `emails/monthly_report.html` | **Implemented** | Monthly summary |
| Billing emails | `emails/invoice.html`, `payment_failed.html`, etc. | **Implemented** | Payment lifecycle |
| Partner emails | `emails/partner_*.html` | **Implemented** | Partner program notifications |
| Trial ending | `emails/trial_ending.html` | **Implemented** | Subscription urgency |
| Usage warning | `emails/usage_warning.html` | **Implemented** | Approaching limits |

**Assessment:** Comprehensive email notification suite via Resend. Appropriate for transactional/billing notifications. For daily operations, WhatsApp should be primary.

---

### 4. Daily Brief System

| Component | Location | Status | Description |
|-----------|----------|--------|-------------|
| DailyBrief model | `briefs/models.py` | **Implemented** | Stores generated brief content + Kova Score |
| Brief generation task | `briefs/tasks.py` | **Implemented** | `generate_all_daily_briefs` — runs daily |
| Kova Score | `briefs/tasks.py` | **Implemented** | Composite business health score |
| Brief WhatsApp delivery | `briefs/tasks.py` | **Implemented** | Sends via WhatsApp to enabled users |
| Brief web page | `briefs/home.html` | **Implemented** | Web version with full detail |
| Morning standup | `briefs/_morning_standup.html` | **Implemented** | Digest format |
| Decision stream | `briefs/_decision_stream.html` | **Implemented** | Real-time activity feed |
| Money board | `briefs/_money_board.html` | **Implemented** | Revenue snapshot |
| Agent activity | `briefs/_agent_activity.html` | **Implemented** | What agents did today |
| Pending approvals | `briefs/_pending_approvals.html` | **Implemented** | Content awaiting action |
| Customer pulse | `briefs/_customer_pulse.html` | **Implemented** | Customer activity summary |

**Assessment:** The Daily Brief is the crown jewel of the notification system. It's the primary touchpoint — delivered via WhatsApp with a quick summary and action buttons. The web version provides depth when needed. Fully production-ready.

---

### 5. Scheduling & Reports

| Component | Location | Status | Description |
|-----------|----------|--------|-------------|
| Celery Beat scheduler | `docs/config/celery.py` | **Implemented** | Periodic task execution |
| Daily brief schedule | Beat config | **Implemented** | Morning generation + delivery |
| Weekly report task | `emails/tasks.py` | **Implemented** | Weekly email summary |
| Monthly report task | `emails/tasks.py` | **Implemented** | Monthly email summary |
| Money board digest | `briefs/tasks.py` | **Implemented** | Revenue digest delivery |
| Token refresh warnings | `platforms/tasks.py` | **Implemented** | Expiring OAuth token alerts |

---

### 6. Follow-up & Reminder System

| Component | Location | Status | Description |
|-----------|----------|--------|-------------|
| 24h follow-up nudge | `whatsapp/autopilot.py` | **Implemented** | Remind owner about unanswered customers |
| Lead nurture steps | `leads/tasks.py` | **Implemented** | Automated lead follow-up |
| Stale lead re-engagement | `leads/tasks.py` | **Implemented** | Re-activate cold leads |
| Broadcast sequences | `whatsapp/tasks.py` | **Implemented** | Multi-step WhatsApp drips |
| Trial ending reminder | `emails/tasks.py` | **Implemented** | Subscription urgency email |

---

## Notification Priority Hierarchy

For the WhatsApp-first vision, notifications should follow this priority:

```
1. WhatsApp (primary) — operational alerts, daily brief, approvals
2. In-app (secondary) — real-time when user is on web platform
3. Email (tertiary) — weekly/monthly reports, billing, legal
```

---

## Current Status vs. Vision

| Notification Type | WhatsApp | In-App | Email | Vision-Aligned? |
|-------------------|----------|--------|-------|-----------------|
| Daily Brief | ✓ | ✓ | ✓ | Yes — WhatsApp primary |
| Content ready for approval | ✓ | ✓ | — | Yes |
| Campaign ready | ✓ | — | — | Yes |
| New customer message | — | ✓ | — | **Gap** — should alert via WA |
| New lead captured | — | ✓ | — | **Gap** — should alert via WA |
| Payment received | — | — | ✓ | **Gap** — should alert via WA |
| Post published | — | ✓ | — | OK — low urgency |
| Token expiring | — | ✓ | ✓ | OK — configuration action needed |
| Weekly summary | — | — | ✓ | OK — email appropriate |
| Stock alert | ✓ | ✓ | — | Yes |

---

## Gaps for V1

### Critical

1. **No WhatsApp alert for new customer messages.** When a customer sends a message to the business WhatsApp and the AI handles it, the owner should get a summary notification (e.g., "3 new customer conversations today. 1 needs your attention.").

2. **No WhatsApp alert for payments received.** When a commerce payment completes, the owner should immediately know via WhatsApp.

### Important

3. **No WhatsApp alert for new leads.** When a lead is captured from the storefront or a form, the owner should be notified.

4. **No consolidated end-of-day summary.** Beyond the morning brief, an evening "here's what happened today" via WhatsApp would reinforce the WhatsApp-first experience.

---

## Recommendations

1. **Add "commerce payment received" WhatsApp notification** — immediate value signal to owner.

2. **Add "new lead" WhatsApp notification** — with quick-reply button to respond.

3. **Add daily "customer conversation summary"** — brief evening summary of customer interactions.

4. **Keep email for billing/legal only** — don't duplicate operational notifications to email.

5. **Keep in-app notifications as web-session supplement** — useful when owner is already on the platform.

---

## Notification System Readiness Score

| Channel | Score | Notes |
|---------|-------|-------|
| WhatsApp notifications | 7/10 | Strong base; needs commerce + lead alerts |
| Daily Brief | 9/10 | Excellent primary touchpoint |
| In-app (WebSocket) | 8/10 | Solid implementation |
| Email (transactional) | 9/10 | Comprehensive template suite |
| Follow-up/reminders | 7/10 | Exists for customers; needs owner reminders |
| Scheduling | 9/10 | Celery Beat handles all periodic tasks |

**Overall Notifications Readiness: 8/10**
