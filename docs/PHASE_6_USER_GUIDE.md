# Phase 6 — Conversion Loop: User & Setup Guide

> **Phase 6 turns social media followers into leads, subscribers, and revenue.**
> It adds four interconnected systems: Kova Links, Smart CTAs, Lead Inbox, and Email Marketing.

---

## Table of Contents

1. [Architecture Overview](#1-architecture-overview)
2. [Sprint 6A — Kova Links](#2-sprint-6a--kova-links)
3. [Sprint 6B — Smart CTA System](#3-sprint-6b--smart-cta-system)
4. [Sprint 6C — Lead Inbox](#4-sprint-6c--lead-inbox)
5. [Sprint 6D — Email Marketing Engine](#5-sprint-6d--email-marketing-engine)
6. [How They Work Together (The Conversion Loop)](#6-how-they-work-together)
7. [Plan Limits by Tier](#7-plan-limits-by-tier)
8. [Admin Access](#8-admin-access)
9. [Sidebar Navigation](#9-sidebar-navigation)
10. [Troubleshooting](#10-troubleshooting)

---

## 1. Architecture Overview

```
Social Post (with CTA)
    │
    ▼
Kova Link Page  ──────►  Form Submission
    │                         │
    │                         ▼
    │                   Lead (auto-created)
    │                         │
    ▼                         ▼
Link Click Tracking      Email Subscriber (auto-synced)
    │                         │
    ▼                         ▼
UTM Attribution          Campaign / Sequence
```

**Data flow:** A post's CTA sends people to a Kova Link page → visitors fill a form → a Lead is auto-created → the lead becomes an Email Subscriber → you send campaigns or enroll them in drip sequences.

---

## 2. Sprint 6A — Kova Links

**What it is:** Your own link-in-bio / landing page builder. Each page lives at `yourdomain.com/k/your-slug/` — a public URL you put in your social media bios.

### Dashboard URL

```
/links/
```

### How to Set Up

#### Step 1 — Create a Kova Page

1. Go to **Conversion → Kova Links** in the sidebar
2. Click **"+ New Page"**
3. Fill in:
   - **Title** — The page heading visitors see (e.g. "Otieno Creative Studio")
   - **Slug** — The URL path (e.g. `otieno` → your page lives at `/k/otieno/`)
   - **Bio** — A short description shown below the title
   - **Theme** — Choose from: `minimal`, `bold`, `gradient`, `dark`, `neon`
   - **Primary/Secondary Color** — Hex codes for button styling
   - **SEO Title / SEO Description** — For Google/social previews
   - **Avatar** — Upload a profile image
4. Save → your page is live immediately

#### Step 2 — Add Links

1. Open your page from the list → click **"+ Add Link"**
2. Fill in:
   - **Title** — Button text (e.g. "Book a Consultation")
   - **URL** — Where the link goes
   - **Link Type** — `link` (standard), `social` (social profile), `video` (embedded), `music`, `download`
   - **Featured** — Toggle ON to highlight this link
   - **Order** — Controls the display position (lower = higher on page)
3. Links are auto-ordered. You can reorder by editing the order field.

#### Step 3 — Add Forms (Growth+ plan required)

1. On a page detail, click **"+ Add Form"**
2. Configure:
   - **Title** — Form heading (e.g. "Get my free guide")
   - **Form Type** — `email_capture`, `contact`, `booking`, `newsletter`, `feedback`
   - **Field toggles** — Enable/disable: name, phone, company, message fields
   - **Name/Phone/Company/Message required** — Set which fields are mandatory
   - **Button Text** — Customize the submit button
   - **Success Message** — What visitors see after submitting
   - **Notification Email** — Get notified when someone submits (optional)
3. Save → form appears at the bottom of your Kova page

#### Step 4 — View Submissions

- Go to **Kova Links → Submissions** (`/links/submissions/`)
- See all form submissions across all your pages
- Mark submissions as read

### Public Page Features

- **Click tracking** — Every link click is recorded with referrer, device type, browser, and UTM parameters
- **Page views** — Daily aggregated view counts
- **Responsive** — Works on mobile, tablet, desktop
- **Standalone HTML** — Public pages use Tailwind CDN (no auth layout)

### Key URLs

| Action | URL |
|--------|-----|
| List pages | `/links/` |
| Create page | `/links/create/` |
| View page | `/links/<page_id>/` |
| Public page | `/k/<slug>/` |
| All submissions | `/links/submissions/` |

---

## 3. Sprint 6B — Smart CTA System

**What it is:** Every post you create can have a call-to-action with UTM tracking baked in. Set your defaults once, and every post gets properly tracked links.

### How to Set Up

#### Step 1 — Configure Your Default CTA Settings

1. Go to `/accounts/settings/cta/` (or navigate: **Settings → CTA Defaults**)
2. Set your defaults:
   - **Default CTA Type** — What kind of CTA most posts should use: `link`, `phone`, `email`, `whatsapp`, `kova_link`
   - **Default CTA URL** — Your main landing page URL (e.g. your Kova Link page)
   - **CTA Phone** — Your business phone number
   - **CTA Email** — Your contact email
   - **CTA WhatsApp** — Your WhatsApp number
3. Save → these defaults pre-fill when you create new posts

#### Step 2 — Use CTAs in Posts

When editing a post (`/content/<post_id>/edit/`):

1. Scroll to the **Call-to-Action** section
2. Select a **CTA Type**:
   - **Link** → Shows URL field
   - **Phone** → Shows phone number
   - **Email** → Shows email address
   - **WhatsApp** → Shows WhatsApp number
   - **Kova Link** → Quick-fill buttons appear for each of your Kova pages
3. Set **CTA Text** — The call-to-action message (e.g. "Book now →", "DM for details")
4. **First Comment** — Text posted as the first comment (great for Instagram links)

#### Step 3 — UTM Tracking (auto or manual)

UTM fields auto-populate when you save a post:
- `utm_source` = platform name (e.g. `instagram`, `twitter`)
- `utm_medium` = `social`
- `utm_campaign` = post ID

You can override any UTM field manually. The **full tracked URL** (shown in the post detail) combines your CTA URL + all UTM params.

### How It Works Technically

- `Post.full_tracked_url` property — Builds the complete URL with `?utm_source=...&utm_medium=...&utm_campaign=...&utm_content=...` appended
- `Post.populate_utm()` method — Auto-fills UTM fields from the post's platform and ID
- CTA type uses Alpine.js conditional display — only relevant fields show based on your selection

---

## 4. Sprint 6C — Lead Inbox

**What it is:** Every person who interacts with your Kova pages becomes a lead. The Lead Inbox is your CRM — track status, add notes, tag and segment leads.

### Dashboard URL

```
/leads/
```

### How Leads Are Created

Leads are created **automatically** via two paths:

1. **Kova Form submissions** — When someone fills out a form on your Kova page, a signal fires that:
   - Creates a new Lead record (or updates existing if same email)
   - Sets `source_type` = `kova_form`
   - Links the lead to the form submission
   - Auto-calculates priority score
   - Logs a `form_submitted` activity on the lead's timeline

2. **Manual creation** — Go to `/leads/create/` and fill in lead details

### Lead Status Funnel

Every lead moves through these stages:

| Status | Meaning |
|--------|---------|
| **New** | Just arrived — hasn't been contacted yet |
| **Contacted** | You've reached out (email, DM, call) |
| **Qualified** | They're a real potential customer |
| **Converted** | They bought / signed up / became a client |
| **Lost** | Didn't convert — archived |

**To change status:** Open a lead → use the status dropdown → click "Update". An activity is logged on the timeline.

### Lead Priority

Priority is auto-calculated by `compute_priority()`:

| Priority | Criteria |
|----------|----------|
| **High** | Has email AND phone, or submitted via a form |
| **Medium** | Has email but no phone |
| **Low** | Missing contact info |

### Working with Leads

#### Tags
- On a lead detail page, type a tag name and click **"Add Tag"**
- Tags are stored as a JSON array — use them to segment (e.g. `vip`, `hot-lead`, `nairobi`)
- Remove tags with the × button next to each tag

#### Notes
- Add private notes on any lead from the detail page
- Each note is logged as an activity with timestamp

#### Activity Timeline
- Every action on a lead is recorded: status changes, notes added, tags changed, form submissions
- Timeline shows on the lead detail page in chronological order

### Filtering & Search

On the lead list page (`/leads/`):
- **Status filter** — Show only New, Contacted, Qualified, etc.
- **Priority filter** — High, Medium, Low
- **Source filter** — Kova Form, Social Bio, Manual, etc.
- **Search** — Search by name, email, phone, or notes content

### Lead Analytics

Go to `/leads/analytics/` to see:
- **Funnel metrics** — How many leads at each status stage
- **Source breakdown** — Where your leads come from
- **Priority distribution** — Health of your pipeline

### Key URLs

| Action | URL |
|--------|-----|
| Lead inbox | `/leads/` |
| Create lead | `/leads/create/` |
| Lead detail | `/leads/<lead_id>/` |
| Analytics | `/leads/analytics/` |

---

## 5. Sprint 6D — Email Marketing Engine

**What it is:** Send email campaigns, manage subscriber lists, and build automated drip sequences — all inside Kova. Built on top of the existing Resend email infrastructure.

### Dashboard URL

```
/emails/marketing/
```

### Core Concepts

| Concept | What It Is |
|---------|-----------|
| **Subscriber** | An email contact (auto-created from leads or forms, or added manually) |
| **List** | A group of subscribers — manual (you add people) or smart (auto-populates from rules) |
| **Campaign** | A one-time email send to a list (newsletter, announcement, promotion) |
| **Sequence** | An automated drip series triggered by an event (form submit, tag added, etc.) |
| **Enrollment** | A subscriber's progress through a sequence |

### Step 1 — Subscribers

**Where:** `/emails/subscribers/`

Subscribers come from 6 sources:
- `Kova Form` — Auto-synced from form submissions
- `Lead Sync` — Synced from your Lead Inbox
- `Manual Entry` — You add them by hand
- `CSV Import` — Bulk upload (future feature)
- `Social Bio` — From a social bio link click
- `API` — External integrations

**To add manually:**
1. Go to `/emails/subscribers/add/`
2. Enter name, email, and source
3. Save → subscriber is created with `active` status and engagement score of 50

**Subscriber health:**
- Each subscriber has an `engagement_score` (0-100)
- 70+ = green (engaged), 40-69 = amber (cooling off), <40 = red (at risk)
- `bounce_count` tracks delivery failures — 3+ bounces auto-marks as "Bounced"

### Step 2 — Lists

**Where:** `/emails/lists/`

Lists group subscribers for targeting campaigns.

**Manual lists:**
1. Go to `/emails/lists/create/`
2. Name your list (e.g. "Newsletter subscribers")
3. Leave "Smart" unchecked
4. Save → then add subscribers to it from the list detail page

**Smart lists:**
1. Create a list with "Smart" checked
2. Smart lists auto-populate based on `filter_rules` — a JSON config that filters by:
   - `tags` — Subscribers with specific tags
   - `source` — Only from a specific source (e.g. `kova_form`)
   - `min_engagement` — Only subscribers above a score threshold
3. Smart lists refresh automatically when queried

### Step 3 — Campaigns

**Where:** `/emails/campaigns/`

A campaign is a single email blast to a list.

**To create a campaign:**
1. Go to `/emails/campaigns/create/`
2. Fill in:
   - **Name** — Internal label (subscribers don't see this)
   - **Subject** — The email subject line
   - **Preview Text** — The snippet shown in inbox previews
   - **HTML Content** — Your email body (HTML supported)
   - **Text Content** — Plain text fallback
   - **From Name** — Sender display name
   - **Reply To** — Where replies go
   - **Target List** — Pick which list to send to
3. Save → campaign is created as a **Draft**

**Campaign lifecycle:** `Draft` → `Scheduled` → `Sending` → `Sent`

- Only Draft and Scheduled campaigns can be edited
- Campaign metrics track: total sent, opened, clicked, bounced, unsubscribed
- `open_rate` and `click_rate` are auto-calculated properties

**A/B Testing:**
- Set `variant_of` to link a campaign to a parent campaign
- Label variants A, B, C, etc.
- Compare metrics between variants on the campaign detail page

### Step 4 — Sequences

**Where:** `/emails/sequences/`

Sequences are automated email series triggered by events.

**Trigger types:**
| Trigger | When It Fires |
|---------|--------------|
| `Form Submission` | Someone submits a Kova Form |
| `Tag Added` | A tag is applied to a subscriber |
| `Subscriber Added` | A new subscriber joins a list |
| `Lead Status Change` | A lead's status changes in the Lead Inbox |
| `Manual` | You manually enroll a subscriber |

**Sequence steps:**
- Each step has: subject, HTML content, text content
- Steps have `delay_days` and `delay_hours` — how long to wait after the previous step
- Step 1 with delay 0 sends immediately on trigger
- Steps are ordered by `step_number`

**Enrollments:**
- When a trigger fires, a `SequenceEnrollment` is created
- Enrollment tracks: current step, status (active/completed/paused/cancelled), next send time
- One subscriber can only be enrolled once per sequence

### Key URLs

| Action | URL |
|--------|-----|
| Email dashboard | `/emails/marketing/` |
| Subscribers | `/emails/subscribers/` |
| Add subscriber | `/emails/subscribers/add/` |
| Lists | `/emails/lists/` |
| Create list | `/emails/lists/create/` |
| Campaigns | `/emails/campaigns/` |
| Create campaign | `/emails/campaigns/create/` |
| Sequences | `/emails/sequences/` |

---

## 6. How They Work Together

Here's the **full conversion loop** a Kova user operates:

### The Flow

```
1. CREATE CONTENT
   You write a post in Content → set CTA type to "Kova Link"
   → UTM tracking auto-populates

2. PUBLISH TO SOCIAL
   Post goes out to Instagram/Twitter/LinkedIn/etc.
   → CTA text tells followers to "click link in bio"

3. VISITOR LANDS ON KOVA PAGE
   They visit /k/your-slug/
   → Page view is recorded
   → They see your links, bio, and a form

4. VISITOR CLICKS OR SUBMITS
   a) Link click → tracked with referrer, device, UTM params
   b) Form submission → name, email, phone captured

5. LEAD AUTO-CREATED
   Form submission triggers a Django signal:
   → Lead created in your Lead Inbox
   → Priority auto-calculated
   → Activity logged

6. SUBSCRIBER AUTO-READY
   Lead email becomes an Email Subscriber
   → Ready for campaigns and sequences

7. NURTURE VIA EMAIL
   Send campaigns to your subscriber lists
   → Track opens, clicks, bounces
   → Run drip sequences for automated follow-up

8. TRACK & OPTIMIZE
   Use Lead Analytics + Campaign Metrics to see:
   → Which posts drive the most form submissions
   → Which CTAs convert best
   → Which email sequences close the most leads
```

### Connecting the Dots

| If you want to... | Do this... |
|-------------------|-----------|
| Get your Kova Link URL in a post | Edit post → CTA Type = "Kova Link" → click the quick-fill button for your page |
| See who submitted forms | Kova Links → Submissions, or Lead Inbox (auto-synced) |
| Email all your leads | Lead Inbox leads become Email Subscribers → create a List → send a Campaign |
| Auto-email new form submitters | Create a Sequence with trigger "Form Submission" → add steps → activate |
| Track which social platform brings leads | Check UTM source on leads + link clicks — set in the CTA system |

---

## 7. Plan Limits by Tier

| Feature | Starter (KES 299) | Growth (KES 999) | Pro (KES 1,999) | Agency (KES 2,999) |
|---------|-------------------|-------------------|------------------|---------------------|
| **Kova Pages** | 1 | 3 | 10 | 50 |
| **Links per Page** | 5 | 20 | 100 | Unlimited |
| **Kova Forms** | No | Yes | Yes | Yes |
| **Max Leads** | 10 (view only) | 100 | Unlimited | Unlimited |
| **Can Edit Leads** | No | Yes | Yes | Yes |
| **Email Subscribers** | 50 | 2,500 | 25,000 | Unlimited |
| **Email Lists** | 1 | 5 | Unlimited | Unlimited |
| **Campaigns / Month** | 2 | 10 | Unlimited | Unlimited |
| **Email Sequences** | 0 | 3 | Unlimited | Unlimited |

**Starter plan strategy:** Enough to prove value (1 page, 10 leads, 2 campaigns). Once they see results, they upgrade to Growth for forms + sequences.

---

## 8. Admin Access

All Sprint 6 models are registered in Django Admin (`/admin/`):

| Model | Admin Features |
|-------|---------------|
| `KovaPage` | List with user, title, slug, theme, is_published |
| `KovaLink` | List with page, title, link_type, is_featured |
| `KovaForm` | List with page, title, form_type |
| `FormSubmission` | List with form, name, email, is_read |
| `LinkClick` | List with link, referrer, device_type |
| `PageView` | List with page, date, view_count |
| `Lead` | List with name, email, status, priority + inline LeadActivity |
| `EmailSubscriber` | List with email, source, status, engagement_score |
| `EmailList` | List with name, subscriber_count, is_smart |
| `EmailCampaign` | List with name, subject, status, metrics |
| `EmailSequence` | List with name, trigger_type, is_active + inline steps |
| `SequenceEnrollment` | List with subscriber, sequence, step, status |

---

## 9. Sidebar Navigation

All Phase 6 features are in the **Conversion** section of the sidebar:

```
── Conversion ──────────────
   Kova Links      →  /links/
   Lead Inbox      →  /leads/
   Email Marketing →  /emails/marketing/
```

---

## 10. Troubleshooting

### "Page not found" for /leads/ or /emails/marketing/

Verify these are in `config/urls.py`:
```python
path("leads/", include("apps.leads.urls")),
path("emails/", include("apps.emails.urls")),
```

And in `config/settings/base.py` → `LOCAL_APPS`:
```python
"apps.leads",
```

### "No reverse match for 'leads:list'"

The URL name is `leads:list` (not `leads:lead_list`). Check your template references.

### Forms not showing on Kova page

Forms require **Growth plan or above**. Starter plan has `kova_forms: False`.

### Leads not auto-creating from form submissions

Check that `apps/leads/apps.py` has:
```python
def ready(self):
    import apps.leads.signals  # noqa: F401
```

This imports the `post_save` signal that listens for `FormSubmission` saves.

### Migrations not applied

Run:
```bash
python manage.py makemigrations leads emails
python manage.py migrate
```

### Email Marketing pages return 500

Make sure `apps/emails/marketing_views.py` exists and `apps/emails/urls.py` imports from it:
```python
from apps.emails import marketing_views, views
```

---

## Files Reference

### Sprint 6A (Kova Links)
- `apps/links/models.py` — KovaPage, KovaLink, LinkClick, KovaForm, FormSubmission, PageView
- `apps/links/views.py` — All CRUD + public page views
- `apps/links/urls.py` — Dashboard + submission routes
- `config/urls.py` — Public routes at `/k/<slug>/`
- `templates/links/` — 7 templates + 3 partials

### Sprint 6B (Smart CTA)
- `apps/content/models.py` — 8 CTA/UTM fields on Post model
- `apps/accounts/models.py` — 5 CTA default fields on UserProfile
- `apps/accounts/views.py` — `cta_settings_view`
- `templates/accounts/cta_settings.html`
- `templates/content/edit.html` — CTA section with Alpine.js

### Sprint 6C (Lead Inbox)
- `apps/leads/models.py` — Lead, LeadActivity
- `apps/leads/signals.py` — Auto-create leads from FormSubmission
- `apps/leads/views.py` — Inbox, detail, analytics, HTMX endpoints
- `apps/leads/urls.py` — 9 URL patterns
- `templates/leads/` — 4 templates + 3 partials

### Sprint 6D (Email Marketing)
- `apps/emails/models.py` — EmailSubscriber, EmailList, EmailCampaign, EmailSequence, EmailSequenceStep, SequenceEnrollment
- `apps/emails/marketing_views.py` — Dashboard, subscriber, list, campaign, sequence views
- `apps/emails/forms.py` — EmailSubscriberForm, EmailListForm, EmailCampaignForm
- `apps/emails/urls.py` — 15 URL patterns
- `templates/emails/` — 10 templates
