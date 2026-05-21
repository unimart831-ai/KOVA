# Kova System Audit & Flow Maps

**Last updated:** May 2026  
**In-app:** Settings → System Maps → `/help/system-maps/`  
**Print all:** `/help/system-maps/print/`

This document is the master audit. Each section has a matching printable flow diagram in the app.

---

## Founder's Cut Navigation (19 sidebar surfaces)

| Group | Sidebar item | URL | Automation |
|-------|-------------|-----|------------|
| — | Home | `/brief/` | Auto (15 min beat) |
| Create | Studio | `/content/studio/` | Partial — approve to publish |
| Create | Queue | `/content/queue/` | Partial — publish beat 5 min |
| Customers | Inbox | `/engage/` | Partial — PRO, 30 min beat |
| Customers | WhatsApp | `/whatsapp/` | Partial — PRO |
| Customers | Leads | `/leads/` | Partial — nurture 30 min |
| Customers | Email | `/emails/marketing/` | Partial — auto flag |
| Customers | Bookings | `/bookings/` | Manual setup |
| Business | Revenue | `/analytics/revenue/` | Webhooks auto |
| Business | Products | `/products/` | Partial — snap AI, daily promote |
| Business | Links | `/links/` | Manual |
| Business | Walk-ins | `/qr/` | Manual cashier |
| Business | Insights | `/analytics/` | Partial — metrics 6h |
| Business | Competitors | `/analytics/competitors/` | Partial — weekly |
| Settings | Profile, Platforms, Agents, Billing, Help | various | Mixed |

**Create sub-nav (when Studio active):** Campaigns (voice), Visual Publisher, Memes, Autopilot

---

## Daily Wall — Print These 3 First

### 1. Founder Daily Routine
Morning: **Brief → Studio → Queue**. Engage/WhatsApp/Leads only when Brief alerts you.

### 2. Create → Schedule (core operating model)
```
Hidden until autonomous:  Campaigns tab, Email Marketing, A/B Tests  →  Queue
Create — automated:       Voice Campaign, Studio, Autopilot         →  Queue
Schedule — passive:         Calendar (view), Queue (hub)             →  Publish beat
```
**Key insight:** Queue is the hub. Publishing is passive once approved.

### 3. Six-Agent Loop
Research + Strategist → **Create** → Publish → **Analyst** → **Adapt** → back to Create. Engage runs in parallel on interactions.

---

## Section Audits (summary)

### Home / Daily Brief
- Celery: `briefs.generate_all_daily_briefs` every 15 min
- Aggregates overnight agent work, calendar intel, profile alerts, pipeline
- `brief_action` creates seed only — user opens Studio to generate

### Studio & Queue
- Default path: `ContentSeed` → Create Agent → `pending_approval` → user approves → schedule → publish beat
- `auto_approve_posts=False` by default on all new users
- Smart auto-approve after 15+ posts at 80%+ approval rate

### Autopilot
- Weekly plan preview → user must approve → then generation runs
- `autopilot_enabled` required on profile

### Voice Campaigns vs Campaigns app
- Sidebar "Campaigns" = `/content/voice-campaign/`
- Hidden `/campaigns/` CRUD linked from voice flow

### Engage
- 30 min beat; auto-send blocked unless `ENGAGE_GRADUATED_AUTONOMY_ENABLED=True`

### Adapt Agent v2
- Profile learning gated by `ADAPT_AGENT_V2_ENABLED=False` (dry-run by default)

### Email Marketing
- Tenant `EmailSubscriber` (per user) vs blog `NewsletterSubscriber` (prospects) — two systems

### Partners
- Commission models exist; automated accrual on payment not fully wired in Celery yet

### Reviews
- `send_due_review_requests` task exists but not in Celery Beat schedule

---

## Hidden Surfaces (URL only)

| Path | Purpose |
|------|---------|
| `/campaigns/` | Campaign CRUD |
| `/content/ab-tests/` | A/B tests |
| `/calendar/preferences/` | Calendar Intel (holidays) |
| `/profile-health/` | Profile audits |
| `/analytics/pixel/` | Kova Pixel |
| `/reviews/` | Review requests |

---

## Celery Beat — What Runs Without You

| Interval | Tasks |
|----------|-------|
| 5 min | Publish due posts, media queues |
| 15 min | Daily briefs, scheduled email campaigns |
| 30 min | Engage, nurture, email sequences, OAuth refresh, WA broadcasts |
| 6–12 h | Research, strategy, adapt, metrics, memes |
| Daily | Stock alerts, auto-promote, holiday watcher, profile audits, lead scoring |
| Weekly | Autopilot plan, competitor analysis |

---

## All 22 System Maps

| # | Slug | Title |
|---|------|-------|
| 1 | `founder-daily-routine` | Founder Daily Routine |
| 2 | `create-to-schedule` | Create → Schedule |
| 3 | `six-agent-loop` | 6-Agent Intelligence Loop |
| 4 | `daily-brief` | Home / Daily Brief |
| 5 | `studio-approval` | Studio → Approve → Publish |
| 6 | `autopilot-week` | Autopilot Weekly Plan |
| 7 | `voice-campaigns` | Voice Campaigns & Campaigns App |
| 8 | `memes-visual-publisher` | Memes & Visual Publisher |
| 9 | `engage-inbox` | Engage Inbox |
| 10 | `whatsapp-customers` | WhatsApp |
| 11 | `leads-nurture` | Leads & Nurture |
| 12 | `email-marketing` | Email Marketing |
| 13 | `bookings-loop` | Bookings |
| 14 | `products-commerce` | Products & Snap to Sell |
| 15 | `revenue-attribution` | Revenue & Attribution |
| 16 | `links-kova-page` | Links & Kova Page |
| 17 | `insights-competitors` | Insights & Competitors |
| 18 | `onboarding-first-value` | Signup → Onboarding → First Value |
| 19 | `platforms-agents-settings` | Platforms, Agents & Settings |
| 20 | `billing-plan-gates` | Billing & Plan Gates |
| 21 | `hidden-surfaces` | Hidden Surfaces |
| 22 | `celery-beat-schedule` | Background Jobs |

Source of truth for diagrams: `apps/help/system_maps.py`

---

## Related docs

- `docs/KOVA_LIFECYCLE.md` — customer lifecycle
- `docs/NAVIGATION.md` — nav structure
- `docs/COFOUNDER_PLATFORM_AUDIT_2026_05.md` — platform audit
- `docs/specs/ADAPT_AGENT_V2_SPEC.md` — Adapt agent
- `docs/specs/ENGAGE_AGENT_V2_SPEC.md` — Engage agent
