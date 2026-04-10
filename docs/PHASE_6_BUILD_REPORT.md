# KOVA Agent — Phase 6 Complete Build Report

> **Date**: April 10, 2026
> **Phase**: 6 (Sprints 6A through 6H + Campaigns System)
> **Status**: All sprints complete, deployed, validated
> **Total New Django Apps**: 4 (leads, links, products, campaigns)
> **Total New Models**: 22
> **Total New Views**: 80+
> **Total New Templates**: 55+

---

## Table of Contents

1. [Phase 6 Overview — What Was Built and Why](#1-phase-6-overview)
2. [Sprint 6A — Lead Capture & CRM Pipeline](#2-sprint-6a--lead-capture--crm-pipeline)
3. [Sprint 6B — Kova Links & Smart CTAs](#3-sprint-6b--kova-links--smart-ctas)
4. [Sprint 6C — Email Marketing Engine](#4-sprint-6c--email-marketing-engine)
5. [Sprint 6D — Engagement Intelligence & Superfans](#5-sprint-6d--engagement-intelligence--superfans)
6. [Sprint 6E — Content Intelligence & A/B Testing](#6-sprint-6e--content-intelligence--ab-testing)
7. [Sprint 6F — Revenue Attribution & Competitor Intel](#7-sprint-6f--revenue-attribution--competitor-intel)
8. [Sprint 6G — Stock-Aware Product Intelligence](#8-sprint-6g--stock-aware-product-intelligence)
9. [Sprint 6H — Cross-Channel Campaigns](#9-sprint-6h--cross-channel-campaigns)
10. [Admin Dashboard Expansion](#10-admin-dashboard-expansion)
11. [Plan Limits Architecture](#11-plan-limits-architecture)
12. [Data Flow & System Connections](#12-data-flow--system-connections)
13. [What This Means for KOVA](#13-what-this-means-for-kova)

---

## 1. Phase 6 Overview

### The Problem Phase 6 Solved

Before Phase 6, KOVA could create content and publish it. That's it. Content went out, but there was no way to:
- Capture who interacted with it
- Track if it generated revenue
- Manage leads that came from social
- Run coordinated campaigns across channels
- Understand what products to promote
- Build landing pages for bio links
- Send marketing emails to captured audiences

Phase 6 transformed KOVA from a **content creation tool** into a **Business Intelligence Operating System (BIOS)** — a complete pipeline from content creation → audience capture → lead management → revenue attribution.

### The Build Sequence (Why This Order)

```
6A: Leads      → Capture the people who respond to your content
6B: Links      → Give them a place to land (link-in-bio + forms)
6C: Emails     → Nurture them with email marketing
6D: Engage     → Track social interactions + detect superfans
6E: Content    → A/B test and add CTAs to posts
6F: Revenue    → Attribute revenue back to specific content + competitors
6G: Products   → Make AI agents stock-aware for smarter content
6H: Campaigns  → Orchestrate everything into coordinated campaigns
```

Each sprint builds on the previous ones. Leads captured by forms (6B) flow into the CRM (6A), get nurtured by emails (6C), their interactions are tracked (6D), the content that brought them has CTAs (6E), revenue is attributed (6F), product stock influences what gets promoted (6G), and campaigns tie it all together (6H).

---

## 2. Sprint 6A — Lead Capture & CRM Pipeline

**App**: `apps/leads/`
**What it does**: Automatically captures and manages every potential customer that touches your brand.

### Models

#### Lead
The core contact record. Every person who interacts with your brand becomes a Lead.

| Field | Type | Purpose |
|-------|------|---------|
| `id` | UUID | Primary key |
| `user` | FK → User | Owner (multi-tenant) |
| `name` | CharField | Contact name |
| `email` | EmailField | Contact email |
| `phone` | CharField | Contact phone |
| `source_type` | TextChoices | How they found you |
| `source_platform` | CharField | Which platform (instagram, twitter, etc.) |
| `source_post` | FK → Post | Which specific post drove them (nullable) |
| `source_form` | FK → KovaForm | Which form they submitted (nullable) |
| `source_submission` | FK → FormSubmission | The actual form submission (nullable) |
| `status` | TextChoices | Pipeline stage |
| `priority` | TextChoices | HIGH / MEDIUM / LOW |
| `tags` | JSONField | Custom labels |
| `notes` | TextField | Freeform notes |
| `metadata` | JSONField | UTM data, referrer, device, etc. |
| `first_seen_at` | DateTimeField | When they first appeared |
| `last_activity_at` | DateTimeField | Most recent interaction |
| `converted_at` | DateTimeField | When they became a customer |

**Status pipeline**: `NEW` → `CONTACTED` → `QUALIFIED` → `CONVERTED` (or `LOST`)

**Source types**: `FORM_SUBMISSION`, `SOCIAL_DM`, `SOCIAL_COMMENT`, `MANUAL`, `IMPORT`, `API`

#### LeadActivity
Activity timeline for each lead — every touchpoint is recorded.

| Field | Type | Purpose |
|-------|------|---------|
| `lead` | FK → Lead | Which lead |
| `activity_type` | TextChoices | What happened |
| `description` | TextField | Human-readable description |
| `metadata` | JSONField | Extra data (email IDs, link clicked, etc.) |

**Activity types**: `FORM_SUBMITTED`, `EMAIL_SENT`, `EMAIL_OPENED`, `EMAIL_CLICKED`, `SOCIAL_INTERACTION`, `NOTE_ADDED`, `STATUS_CHANGED`, `PHONE_CALLED`, `WHATSAPP_SENT`, `TAG_ADDED`

### Views (9 views)

| View | URL | Purpose |
|------|-----|---------|
| `lead_list` | `/leads/` | Lead inbox with status/priority/source filters |
| `lead_create` | `/leads/create/` | Manually add a lead |
| `lead_detail` | `/leads/<uuid>/` | Full lead profile + activity timeline |
| `lead_edit` | `/leads/<uuid>/edit/` | Edit lead info |
| `lead_change_status` | `/leads/<uuid>/status/` | Move lead through pipeline |
| `lead_add_note` | `/leads/<uuid>/note/` | Add note to timeline |
| `lead_add_tag` | `/leads/<uuid>/tag/` | Tag a lead |
| `lead_remove_tag` | `/leads/<uuid>/tag/remove/` | Remove tag |
| `lead_analytics` | `/leads/analytics/` | Lead analytics dashboard |

### Templates (7 files)
- `lead_list.html` — Filterable lead inbox with status badges
- `lead_form.html` — Add/edit lead form
- `lead_detail.html` — Lead profile with activity timeline
- `lead_analytics.html` — Pipeline analytics
- Partials: `lead_tags.html`, `lead_status_badge.html`, `activity_timeline.html`

### Why It Matters
Without a lead system, social media is just broadcasting into the void. Sprint 6A gives every post a purpose — capture someone. Every form submission, every DM, every comment that shows intent becomes a trackable lead with a full history.

---

## 3. Sprint 6B — Kova Links & Smart CTAs

**App**: `apps/links/`
**What it does**: Bio-link landing pages with forms, click tracking, and lead capture — like Linktree, but connected to your entire KOVA pipeline.

### Models

#### KovaPage
A customizable landing page that lives at `/k/<slug>/`.

| Field | Type | Purpose |
|-------|------|---------|
| `id` | UUID | Primary key |
| `user` | FK → User | Owner |
| `title` | CharField | Page headline |
| `slug` | SlugField (unique) | URL slug: `/k/your-brand/` |
| `bio` | TextField | Short bio text |
| `avatar_url` | URLField | Profile image |
| `theme` | TextChoices | Visual theme |
| `custom_css` | TextField | Advanced styling |
| `background_color` | CharField | Hex color |
| `text_color` | CharField | Hex color |
| `accent_color` | CharField | Hex color |
| `seo_title` | CharField | SEO meta title |
| `seo_description` | TextField | SEO meta description |
| `og_image_url` | URLField | Social share image |
| `is_published` | BooleanField | Live or draft |
| `total_views` | IntegerField | View counter |

**Themes**: `MINIMAL`, `BOLD`, `GRADIENT`, `DARK`, `NEON`, `WARM`

#### KovaLink
Individual links on a page (URLs, social profiles, emails, phone numbers).

| Field | Type | Purpose |
|-------|------|---------|
| `page` | FK → KovaPage | Which page |
| `link_type` | TextChoices | URL / SOCIAL / EMAIL / PHONE / HEADER |
| `title` | CharField | Display label |
| `url` | URLField | Target URL |
| `icon` | CharField | Icon identifier |
| `thumbnail_url` | URLField | Optional thumbnail |
| `is_featured` | BooleanField | Highlight this link |
| `is_active` | BooleanField | Show/hide |
| `order` | IntegerField | Display position |
| `total_clicks` | IntegerField | Click counter |

#### LinkClick
Every click is tracked with UTM data, device, country, and referrer.

| Field | Type | Purpose |
|-------|------|---------|
| `link` | FK → KovaLink | Which link was clicked |
| `referrer` | URLField | Where they came from |
| `country` | CharField | ISO country code |
| `device_type` | CharField | Mobile / Desktop / Tablet |
| `utm_source` | CharField | UTM source parameter |
| `utm_medium` | CharField | UTM medium parameter |
| `utm_campaign` | CharField | UTM campaign parameter |
| `clicked_at` | DateTimeField | When they clicked |

#### KovaForm
Embeddable forms on Kova Pages (plan-gated: Growth+ only).

#### FormSubmission
Captured form responses that auto-create Leads in the CRM (Sprint 6A).

#### PageView
Analytics: tracks every visit to a Kova Page.

### Views (13 views)

| View | URL | Purpose |
|------|-----|---------|
| `page_list` | `/links/` | All your Kova Pages |
| `page_create` | `/links/create/` | Create new page (plan-gated) |
| `page_detail` | `/links/<uuid>/` | Page builder/editor |
| `page_edit` | `/links/<uuid>/edit/` | Update page config |
| `page_delete` | `/links/<uuid>/delete/` | Archive page |
| `link_add` | `/links/<uuid>/links/add/` | Add link to page |
| `link_edit` | `/links/<uuid>/links/<uuid>/edit/` | Edit link |
| `link_delete` | `/links/<uuid>/links/<uuid>/delete/` | Remove link |
| `form_add` | `/links/<uuid>/forms/add/` | Create form (Growth+) |
| `form_edit` | `/links/<uuid>/forms/<uuid>/edit/` | Edit form |
| `form_delete` | `/links/<uuid>/forms/<uuid>/delete/` | Remove form |
| `submissions_list` | `/links/submissions/` | View all form submissions |
| `submission_mark_read` | `/links/submissions/<uuid>/read/` | Mark submission read |

### Templates (8+ files)
- `page_list.html` — Dashboard of all Kova Pages
- `page_form.html`, `page_detail.html` — Page builder/editor
- `link_form.html` — Link add/edit
- `form_form.html` — Form builder
- `submissions_list.html` — Form responses
- `public_page.html` — The actual public page visitors see at `/k/<slug>/`
- Partials: `public_form.html`, `form_success.html`, `submission_row.html`

### The Pipeline Connection
```
Instagram Bio → Kova Page (/k/your-brand/) → Visitor clicks link or fills form
    → FormSubmission created → Lead auto-created in CRM (Sprint 6A)
    → LinkClick tracked with UTM → Attribution (Sprint 6F)
```

### Why It Matters
Every social platform gives you one link in your bio. Kova Pages turn that single link into a full landing page with multiple CTAs, forms, and click tracking — all connected to your lead pipeline and revenue attribution.

---

## 4. Sprint 6C — Email Marketing Engine

**App**: `apps/emails/` (marketing_views.py module)
**What it does**: Full email marketing — subscribers, lists, campaigns, sequences, analytics. Built on top of the existing transactional email system.

### Models

#### EmailSubscriber
People who've opted in to receive email marketing.

| Field | Type | Purpose |
|-------|------|---------|
| `user` | FK → User | Owner |
| `email` | EmailField | Subscriber email |
| `name` | CharField | Subscriber name |
| `source` | TextChoices | How they subscribed |
| `source_form` | FK → KovaForm | Which form (nullable) |
| `lead` | FK → Lead | Linked lead record (nullable) |
| `status` | TextChoices | ACTIVE / UNSUBSCRIBED / BOUNCED / COMPLAINED |
| `tags` | JSONField | Subscriber tags for segmentation |
| `engagement_score` | IntegerField | Calculated engagement level |
| `metadata` | JSONField | Extra data |
| `bounce_count` | IntegerField | Number of bounces |

**Sources**: `KOVA_FORM`, `MANUAL`, `IMPORT`, `SOCIAL_BIO`, `API`, `LEAD_SYNC`

#### EmailList
Groups of subscribers — manual lists or smart lists with auto-filter rules.

| Field | Type | Purpose |
|-------|------|---------|
| `user` | FK → User | Owner |
| `name` | CharField | List name |
| `description` | TextField | List purpose |
| `subscribers` | M2M → EmailSubscriber | Members |
| `filter_rules` | JSONField | Smart list filter criteria |
| `is_smart` | BooleanField | Auto-updating vs manual |
| `subscriber_count` | IntegerField | Cached count |

#### EmailCampaign
One-time or scheduled email blasts to a list.

| Field | Type | Purpose |
|-------|------|---------|
| `user` | FK → User | Owner |
| `name` | CharField | Internal name |
| `description` | TextField | Notes |
| `subject` | CharField | Email subject line |
| `html_body` | TextField | Email content (HTML) |
| `recipients_list` | FK → EmailList | Who receives it |
| `segments` | JSONField | Segment filters |
| `status` | TextChoices | DRAFT / SCHEDULED / SENDING / SENT / CANCELLED |
| `send_at` | DateTimeField | Scheduled send time |
| `sent_at` | DateTimeField | Actual send time |
| `stats` | JSONField | Engagement metrics (sent, opened, clicked, bounced) |

#### EmailSequence
Automated email drip sequences triggered by events.

| Field | Type | Purpose |
|-------|------|---------|
| `user` | FK → User | Owner |
| `name` | CharField | Sequence name |
| `emails` | JSONField | Ordered list of emails with delays |
| `trigger_type` | CharField | What starts the sequence |
| `status` | TextChoices | ACTIVE / PAUSED / DRAFT |

#### SequenceEnrollment
Tracks which subscribers are in which sequences and where they are in the drip.

### Views (12 views)

| View | URL | Purpose |
|------|-----|---------|
| `email_dashboard` | `/emails/marketing/` | Email marketing overview |
| `subscriber_list` | `/emails/subscribers/` | Subscriber list with filters |
| `subscriber_add` | `/emails/subscribers/add/` | Add subscriber (plan-gated) |
| `list_index` | `/emails/lists/` | All email lists |
| `list_create` | `/emails/lists/create/` | Create list (plan-gated) |
| `list_detail` | `/emails/lists/<uuid>/` | View list + members |
| `list_edit` | `/emails/lists/<uuid>/edit/` | Edit list |
| `campaign_list` | `/emails/campaigns/` | All campaigns |
| `campaign_create` | `/emails/campaigns/create/` | Create campaign (plan-gated) |
| `campaign_detail` | `/emails/campaigns/<uuid>/` | Campaign stats |
| `campaign_edit` | `/emails/campaigns/<uuid>/edit/` | Edit campaign |
| `sequence_list` | `/emails/sequences/` | Automation sequences |

### Templates (9+ files)
- `dashboard.html` — Email marketing overview
- `campaign_list.html`, `campaign_form.html`, `campaign_detail.html`
- `list_index.html`, `list_form.html`, `list_detail.html`
- `subscriber_list.html`, `subscriber_form.html`

### Pre-existing Transactional Email System
The emails app also includes the core transactional email system (built before Phase 6):
- **EmailLog** model — tracks all 25 email types with 8 statuses
- **EmailService** — sends via Resend API with template rendering
- **12 Celery tasks** — async email sending
- **20 HTML email templates** — welcome, verification, payment, team invites, daily brief, etc.
- **Resend webhooks** — `/emails/webhooks/resend/` tracks delivered/opened/clicked/bounced/spam

### Why It Matters
You capture leads from social → forms → CRM. But then what? Email marketing lets you nurture those leads automatically. A subscriber from your Kova link form can be enrolled in a welcome sequence, then targeted with campaigns based on their tags and engagement score.

---

## 5. Sprint 6D — Engagement Intelligence & Superfans

**App**: `apps/engage/`
**What it does**: Tracks every social interaction (comments, DMs, mentions), AI-suggests replies, and automatically detects your biggest fans.

### Models

#### Interaction
Every comment, reply, mention, or DM across all platforms.

| Field | Type | Purpose |
|-------|------|---------|
| `user` | FK → User | Owner |
| `social_account` | FK → SocialAccount | Which connected account |
| `platform` | CharField | Platform name |
| `post` | FK → Post | Which post (nullable) |
| `interaction_type` | TextChoices | COMMENT / REPLY / MENTION / DM |
| `status` | TextChoices | Pipeline stage |
| `author_name` | CharField | Who interacted |
| `author_username` | CharField | Their handle |
| `content` | TextField | What they said |
| `ai_suggested_reply` | TextField | AI's suggested response |
| `ai_reply_sent` | BooleanField | Whether AI reply was sent |
| `user_edited_reply` | BooleanField | Whether user edited AI's reply before sending |
| `sentiment` | CharField | positive / neutral / negative |

**Status pipeline**: `NEW` → `AI_REPLIED` / `USER_REPLIED` / `IGNORED` / `FLAGGED`

#### Superfan
Automatically detected from interaction patterns. People who interact repeatedly get promoted through tiers.

| Field | Type | Purpose |
|-------|------|---------|
| `user` | FK → User | Owner |
| `author_username` | CharField | The fan's handle |
| `author_name` | CharField | Display name |
| `platforms` | JSONField | Which platforms they interact on |
| `interaction_count` | IntegerField | Total interactions |
| `tier` | TextChoices | Fan tier level |
| `last_sentiment` | CharField | Most recent sentiment |
| `first_seen` | DateTimeField | First interaction |
| `last_interaction_at` | DateTimeField | Most recent interaction |
| `notes` | TextField | User's notes about this fan |

**Tier system** (auto-calculated):
- `RISING` — 3-5 interactions
- `LOYAL` — 6-15 interactions
- `SUPERFAN` — 16+ interactions

### Views (3 views)

| View | URL | Purpose |
|------|-----|---------|
| `engage_inbox` | `/engage/` | Main inbox: filter by status/sentiment/platform, top 10 superfans, 50 recent interactions |
| `trigger_engage` | `/engage/trigger/` | HTMX trigger for Engage Agent cycle |
| `send_reply` | `/engage/reply/<uuid>/` | Send AI-suggested reply (user can edit first) |

### Templates
- `inbox.html` — Engagement inbox with sentiment colors and superfan sidebar
- `_interaction_item.html` — Individual interaction card

### The Intelligence Loop
```
Fan comments on post → Interaction created → AI generates reply suggestion
    → User reviews/edits → Reply sent via platform API
    → Interaction count increments → Superfan tier auto-updates
    → Agent learns from user edits (which replies users change vs accept)
```

### Why It Matters
Social media is a conversation, not a broadcast. The Engage system ensures no comment goes unnoticed, AI handles the volume, and your most valuable fans are automatically identified and tracked. The `user_edited_reply` field creates a feedback loop — the AI learns your voice from your edits.

---

## 6. Sprint 6E — Content Intelligence & A/B Testing

**App**: `apps/content/` (extended)
**What it does**: Adds CTA capabilities to every post and introduces A/B testing for content optimization.

### Model Changes

#### Post — New CTA Fields

| Field | Type | Purpose |
|-------|------|---------|
| `cta_type` | TextChoices | Type of call-to-action |
| `cta_url` | URLField | Where the CTA links to |
| `cta_text` | CharField | Button/link text ("Shop Now", "Learn More") |

**CTA types**: `NONE`, `LINK`, `EMAIL`, `PHONE`, `SHOP` (links to product), `FORM`

#### Post — AI Intelligence Fields (earlier sprint, included here for completeness)

| Field | Type | Purpose |
|-------|------|---------|
| `ai_original_text` | TextField | What AI generated before user edits |
| `user_edited` | BooleanField | Whether user modified AI text |
| `edit_distance_ratio` | FloatField | How much the user changed (0-1) |
| `ai_angle` | CharField | Strategic angle for this platform |
| `ai_framework` | CharField | Content framework used (Hook→Value→CTA, PAS, etc.) |

### A/B Testing System

**How it works**: Create a variant of any post, let both run, compare performance.

| View | URL | Purpose |
|------|-----|---------|
| `create_ab_test` | `/studio/ab-test/create/` | Create variant of existing post |
| `ab_test_results` | `/studio/ab-tests/` | Compare variant performance |

### Templates
- `ab_tests/create.html` — Variant creation form
- `ab_tests/list.html` — Active A/B tests
- `ab_tests/detail.html` — Head-to-head comparison with metrics

### The CTA Connection
```
AI creates post → Post has CTA (cta_type=SHOP, cta_url=/products/123/) 
    → Published to Instagram → User clicks link in bio → Kova Page
    → Clicks product link → LinkClick tracked with UTM
    → Buys product → Conversion attributed to original post
```

### Why It Matters
Without CTAs, posts are just content. With CTAs, every post becomes a conversion opportunity. And A/B testing lets you scientifically determine which angles, frameworks, and CTAs actually work — then do more of what converts.

---

## 7. Sprint 6F — Revenue Attribution & Competitor Intel

**App**: `apps/analytics/` (extended)
**What it does**: Attributes real revenue to specific posts, platforms, and campaigns. Also: competitive intelligence.

### Revenue Attribution Models

#### Conversion
Every revenue event is tracked and attributed.

| Field | Type | Purpose |
|-------|------|---------|
| `user` | FK → User | Owner |
| `social_account` | FK → SocialAccount | Which platform |
| `post` | FK → Post | Which post drove it (nullable) |
| `product` | FK → Product | Which product (nullable) |
| `conversion_type` | TextChoices | SALE / LEAD / CLICK |
| `revenue` | DecimalField | Revenue amount |
| `event_name` | CharField | Custom event label |
| `metadata` | JSONField | UTM params, referrer, etc. |

#### ConversionJourney
Multi-touch attribution — tracks the full path from first touch to conversion.

### Revenue Dashboard Module (`apps/analytics/revenue.py`)

`get_revenue_summary(user, days=30)` returns:
- **Totals**: total_revenue, total_conversions, total_sales, total_leads, total_clicks
- **Breakdowns**: by platform, by content type, by CTA type, by product
- **Top posts**: ranked by revenue generated (top 10)
- **Daily trend**: 30-day revenue chart data
- **ROI calculation**: `(revenue - monthly_plan_cost) / monthly_plan_cost × 100`
- **Funnel metrics**: click → lead conversion rate, lead → sale conversion rate, click → sale rate

### Competitor Intelligence Models

#### Competitor
Track competitors across all platforms.

| Field | Type | Purpose |
|-------|------|---------|
| `user` | FK → User | Owner |
| `name` | CharField | Competitor name |
| `website` | URLField | Their website |
| `industry` | CharField | Industry/niche |
| Platform handles | CharFields | twitter, instagram, facebook, linkedin, tiktok, youtube, threads |
| `strengths` | JSONField | AI-identified strengths |
| `weaknesses` | JSONField | AI-identified weaknesses |
| `content_patterns` | JSONField | Posting frequency, types, timing |
| `threat_level` | CharField | HIGH / MEDIUM / LOW |

#### CompetitorAnalysis
AI-generated competitive analysis reports.

| Field | Type | Purpose |
|-------|------|---------|
| `competitor` | FK → Competitor | Which competitor |
| `analysis_type` | TextChoices | FULL / QUICK / COMPARISON |
| `summary` | TextField | Executive summary |
| `content_strategy` | JSONField | Their content patterns |
| `strengths` | TextField | What they do well |
| `weaknesses` | TextField | Where they fall short |
| `opportunities` | TextField | Gaps you can exploit |
| `threats` | TextField | What to watch out for |
| `actionable_insights` | TextField | What to do about it |

#### CompetitorInsight
Actionable intelligence derived from competitor analysis.

**Insight types**: `CONTENT_GAP`, `TREND_AHEAD`, `WEAKNESS`, `STRATEGY_SHIFT`, `VIRAL_CONTENT`, `OPPORTUNITY`

### Views (6 views)

| View | URL | Purpose |
|------|-----|---------|
| `revenue_dashboard` | `/analytics/revenue/` | Full revenue dashboard |
| `conversion_list` | `/analytics/conversions/` | All conversions |
| `competitor_tracking` | `/analytics/competitors/` | Add/manage competitors |
| `competitor_detail` | `/analytics/competitors/<uuid>/` | Competitor deep dive |
| `competitor_landscape` | `/analytics/landscape/` | Head-to-head comparison |
| `insights` | `/analytics/insights/` | Actionable intelligence feed |

### Templates (6+ files)
- `revenue.html` — Revenue dashboard with charts and breakdowns
- `competitors.html` — Competitor list + add form
- `competitor_detail.html` — Individual competitor analysis
- `competitor_landscape.html` — Multi-competitor comparison
- `insights.html` — Intelligence feed
- Partials: `_insight_card.html`, `_insight_acted.html`

### The Attribution Chain
```
Campaign UTM tag → Post.utm_campaign → User clicks → LinkClick → Conversion
    ↓
Revenue attributed to: specific post, specific platform, specific campaign,
                       specific product, specific CTA type
    ↓
ROI calculated per plan tier: (revenue - plan_cost) / plan_cost × 100
```

### Why It Matters
This is where KOVA proves its value. Most social media tools can show you likes and impressions. KOVA shows you actual revenue generated by each post, each platform, each campaign. When a customer asks "is Kova worth it?", the revenue dashboard answers with hard numbers.

---

## 8. Sprint 6G — Stock-Aware Product Intelligence

**App**: `apps/products/`
**What it does**: Product catalog with real-time stock awareness that feeds into AI agent decisions.

### Strategic Decision
We deliberately did NOT build inventory management (that's Zoho/TradeGecko territory). Instead, we built **Stock-Aware AI** — a product catalog that every AI agent can reference when making content decisions.

### Models

#### ProductCategory
Organize products into browsable categories.

| Field | Type | Purpose |
|-------|------|---------|
| `user` | FK → User | Owner |
| `name` | CharField | Category name |
| `description` | TextField | Category description |
| `position` | IntegerField | Display order |
| `is_active` | BooleanField | Show/hide |

#### Product
The core product record.

| Field | Type | Purpose |
|-------|------|---------|
| `user` | FK → User | Owner |
| `name` | CharField | Product name |
| `description` | TextField | Product description |
| `category` | FK → ProductCategory | Category (nullable) |
| `price` | DecimalField | Price |
| `currency` | CharField | Currency code (default: KES) |
| `price_range_min` | DecimalField | Min price (for variable pricing) |
| `price_range_max` | DecimalField | Max price |
| `image` | ImageField | Product photo |
| `stock_status` | TextChoices | Current stock state |
| `quantity` | IntegerField | Actual count |
| `low_stock_threshold` | IntegerField | Alert threshold |
| `is_featured` | BooleanField | Promote this product |
| `is_active` | BooleanField | Active in catalog |
| `tags` | JSONField | Product tags |

**Stock statuses**: `IN_STOCK`, `LOW_STOCK`, `OUT_OF_STOCK`, `MADE_TO_ORDER`, `UNLIMITED`

**Custom QuerySet methods**: `.in_stock()`, `.low_stock()`, `.out_of_stock()`, `.featured()`, `.promotable()` (in stock + active + not low)

**Auto-behavior**: `check_low_stock()` method auto-creates StockAlerts when quantity drops below threshold.

#### StockUpdate
Audit trail for every stock change.

| Field | Type | Purpose |
|-------|------|---------|
| `product` | FK → Product | Which product |
| `previous_status` | CharField | Status before change |
| `new_status` | CharField | Status after change |
| `previous_quantity` | IntegerField | Quantity before |
| `new_quantity` | IntegerField | Quantity after |
| `reason` | TextChoices | MANUAL / SALE / RESTOCK / ADJUSTMENT |
| `notes` | TextField | Change notes |

#### StockAlert
Automatic alerts for stock events.

| Field | Type | Purpose |
|-------|------|---------|
| `user` | FK → User | Owner |
| `product` | FK → Product | Affected product |
| `alert_type` | TextChoices | What happened |
| `message` | TextField | Human-readable alert |
| `is_read` | BooleanField | Seen by user |

**Alert types**: `LOW_STOCK`, `OUT_OF_STOCK`, `RESTOCKED`, `FEATURED_NO_CONTENT`, `OVERSTOCK_NO_PROMO`

### Views (9 views)

| View | URL | Purpose |
|------|-----|---------|
| `product_list` | `/products/` | Catalog with stock/category/featured filters |
| `product_add` | `/products/add/` | Add product (plan-gated: max_products) |
| `product_detail` | `/products/<uuid>/` | Product card + stock history + alerts |
| `product_edit` | `/products/<uuid>/edit/` | Edit product |
| `product_delete` | `/products/<uuid>/delete/` | Deactivate product |
| `product_update_stock` | `/products/<uuid>/stock/` | Update quantity/status with reason |
| `product_import` | `/products/import/` | CSV bulk import (Growth+ only) |
| `category_list` | `/products/categories/` | Manage categories |
| `category_add` | `/products/categories/add/` | Create category |

### Templates (8+ files)
- `product_list.html` — Catalog browser with stat cards (total/in stock/low/out/featured)
- `product_form.html` — Product add/edit with image upload
- `product_detail.html` — Product detail with stock update timeline and alerts
- `product_import.html` — CSV import (Growth+ plan gate)
- `category_list.html`, `category_form.html`
- Partials: `stock_badge.html` (color-coded stock status), `product_card.html`

### How AI Agents Use Product Data
Every AI agent now receives product context in their prompts:

| Agent | How They Use Products |
|-------|----------------------|
| **Create Agent** | Mentions in-stock products in posts. Avoids out-of-stock items. Prioritizes featured products. |
| **Engage Agent** | When someone asks "how much?", responds with catalog data (price, availability). |
| **Strategist** | Plans content calendar around stock levels. Suggests promos for overstocked items. |
| **Daily Brief** | Shows "Product Pulse" — stock alerts, featured items needing content, restock alerts. |

**Cost**: ~200-500 extra tokens per agent call ≈ <$0.01/user/month.

### Why It Matters
Most AI social media tools are blind to your actual products. KOVA knows what you sell, what's in stock, and what's running low. The Create Agent won't promote something you can't deliver. The Strategist will suggest pushing a product that's overstocked. That's intelligence, not just content generation.

---

## 9. Sprint 6H — Cross-Channel Campaigns

**App**: `apps/campaigns/`
**What it does**: Orchestrates content seeds, email campaigns, and UTM attribution into coordinated cross-channel campaigns with approval workflows.

### Why Campaigns Is the Keystone

Before campaigns, every piece of content existed independently:
- Content seeds generated posts for individual platforms
- Email campaigns sent newsletters separately
- UTM tracking was manual
- There was no coordination between social and email

Campaigns ties everything together into a single orchestrated effort.

### Models

#### Campaign
The central orchestration model.

| Field | Type | Purpose |
|-------|------|---------|
| `id` | UUID | Primary key |
| `user` | FK → User | Owner |
| `brand` | FK → Brand | Team brand (nullable) |
| `name` | CharField | Campaign name |
| `description` | TextField | Campaign brief |
| `objective` | TextChoices | What this campaign aims to achieve |
| `status` | TextChoices | Lifecycle stage |
| `start_date` | DateField | Campaign start |
| `end_date` | DateField | Campaign end |
| `target_platforms` | JSONField | Which platforms to target |
| `target_audience` | TextField | Audience description |
| `utm_campaign_tag` | SlugField | Auto-generated UTM tag |
| `tags` | JSONField | Custom tags |
| `content_seeds` | M2M → ContentSeed (through CampaignSeed) | Linked social content |
| `email_campaigns` | M2M → EmailCampaign (through CampaignEmail) | Linked email blasts |
| `metrics_snapshot` | JSONField | Cached performance data |

**Objectives**: `AWARENESS`, `ENGAGEMENT`, `TRAFFIC`, `LEADS`, `SALES`, `LAUNCH`

**Status flow**:
```
DRAFT → PENDING_APPROVAL → APPROVED → ACTIVE → PAUSED → COMPLETED
                                          ↓
                                      CANCELLED
```

**Properties**:
- `is_editable` — True only for DRAFT and PENDING_APPROVAL
- `duration_days` — Date range duration
- `days_remaining` — Days until end_date
- `total_posts` — Count of all posts from linked seeds
- `published_posts` — Count of published posts

**Auto-behavior**: `utm_campaign_tag` auto-generates from `name` on first save (e.g., "Summer Sale 2026" → `summer-sale-2026`).

#### CampaignSeed (Through Model)
Links a Campaign to ContentSeeds with role and ordering.

| Field | Type | Purpose |
|-------|------|---------|
| `campaign` | FK → Campaign | Parent campaign |
| `seed` | FK → ContentSeed | Linked content seed |
| `role` | TextChoices | PRIMARY / SUPPORTING / FOLLOW_UP |
| `sequence_order` | IntegerField | Order within campaign |

**Constraint**: unique_together = [campaign, seed]

#### CampaignEmail (Through Model)
Links a Campaign to EmailCampaigns with role and ordering.

| Field | Type | Purpose |
|-------|------|---------|
| `campaign` | FK → Campaign | Parent campaign |
| `email_campaign` | FK → EmailCampaign | Linked email campaign |
| `role` | TextChoices | ANNOUNCEMENT / FOLLOW_UP / REMINDER |
| `sequence_order` | IntegerField | Order within campaign |

**Constraint**: unique_together = [campaign, email_campaign]

#### CampaignNote
Activity log for campaign lifecycle.

| Field | Type | Purpose |
|-------|------|---------|
| `campaign` | FK → Campaign | Parent campaign |
| `user` | FK → User | Who made the note |
| `content` | TextField | What happened |
| `note_type` | TextChoices | COMMENT / STATUS_CHANGE / APPROVAL / CONTENT_ADDED |

### Views (11 views)

| View | URL | Purpose |
|------|-----|---------|
| `campaign_list` | `/campaigns/` | Browse campaigns with status/objective filters, quick stats |
| `campaign_create` | `/campaigns/create/` | Create campaign (plan-gated: max_campaigns) |
| `campaign_detail` | `/campaigns/<uuid>/` | Full campaign dashboard |
| `campaign_edit` | `/campaigns/<uuid>/edit/` | Edit (draft/pending only) |
| `campaign_status` | `/campaigns/<uuid>/status/` | Change status with validation |
| `campaign_delete` | `/campaigns/<uuid>/delete/` | Delete (draft/cancelled only) |
| `campaign_add_seed` | `/campaigns/<uuid>/add-seed/` | Link a content seed |
| `campaign_remove_seed` | `/campaigns/<uuid>/remove-seed/<uuid>/` | Unlink a content seed |
| `campaign_add_email` | `/campaigns/<uuid>/add-email/` | Link an email campaign |
| `campaign_remove_email` | `/campaigns/<uuid>/remove-email/<uuid>/` | Unlink an email campaign |
| `campaign_add_note` | `/campaigns/<uuid>/add-note/` | Add activity note |

### Campaign Detail Dashboard

The campaign detail view (`campaign_detail`) is the command center. It shows:

- **Status bar** with contextual action buttons (Submit for Approval / Approve / Launch / Pause / Complete)
- **6 performance metric cards**: Total Posts, Published, Scheduled, Conversions, Leads, Revenue
- **Email metrics** (if campaigns linked): Sent, Opened
- **Linked Content Seeds**: Each seed shows its role (Primary/Supporting/Follow-up), all posts from that seed with their status (published/scheduled/draft), and a remove button
- **Linked Email Campaigns**: Role, sent/opened stats, remove button
- **Available content and emails**: Dropdowns to link more seeds or email campaigns
- **Activity Timeline**: Status changes, approvals, notes with timestamps
- **Campaign Info Card**: Objective, platforms, date range, UTM tag, audience

### UTM Auto-Push

When a campaign status changes to `ACTIVE`, the `_apply_utm_to_posts()` helper automatically:
1. Finds all posts linked to the campaign (via CampaignSeed → ContentSeed → Post)
2. Pushes the campaign's `utm_campaign_tag` to each post's `utm_campaign` field
3. This means all conversions from those posts are automatically attributed back to the campaign

```python
def _apply_utm_to_posts(campaign):
    """Push campaign UTM tag to all linked posts."""
    seed_ids = CampaignSeed.objects.filter(campaign=campaign).values_list("seed_id", flat=True)
    Post.objects.filter(seed_id__in=seed_ids, utm_campaign="").update(
        utm_campaign=campaign.utm_campaign_tag
    )
```

### Templates (3 customer + 2 admin)

**Customer templates** (`templates/campaigns/`):
- `campaign_list.html` — Stat cards (total/active/draft/completed), filterable campaign grid with status badges, objective labels, content/email counts, date ranges
- `campaign_form.html` — Create/edit form with platform checkboxes synced to JSON field
- `campaign_detail.html` — Full campaign dashboard (described above)

**Admin templates** (`templates/admin_dashboard/campaigns/`):
- `overview.html` — Platform-wide: stat cards, objective breakdown, active campaigns, top users, recent activity
- `campaign_list.html` — Filterable/paginated table with UTM tags, status badges, content/email counts

### Why It Matters
Campaigns is the orchestration layer that turns individual tools into a coordinated system. Without it, you're using separate weapons. With it, you're running a coordinated operation — social posts and email blasts unified under one strategy, one UTM tag, one measurement framework.

---

## 10. Admin Dashboard Expansion

Phase 6 significantly expanded the admin dashboard with new sections for every new module.

### New Admin Dashboard Sections

| Section | Views File | Templates | URL Prefix |
|---------|-----------|-----------|------------|
| Campaigns | `views/campaigns.py` | `campaigns/overview.html`, `campaigns/campaign_list.html` | `/dashboard/campaigns/` |
| Products | `views/products.py` | `products/overview.html`, `products/list.html`, `products/stock_alerts.html`, `products/stock_updates.html` | `/dashboard/products/` |
| Revenue | `views/revenue.py` | `revenue/overview.html`, `revenue/conversions.html`, `revenue/shopify.html`, `revenue/journeys.html` | `/dashboard/revenue/` |
| Emails | `views/emails.py` | `emails/overview.html`, `emails/log.html`, `emails/detail.html` | `/dashboard/emails/` |
| Engage | `views/engage.py` | `engage/overview.html`, `engage/interactions.html`, `engage/superfans.html` | `/dashboard/engage/` |
| Billing | `views/billing.py` | `billing/` (12 templates) | `/dashboard/billing/` |

### Admin Sidebar Navigation

The admin sidebar (`templates/admin_dashboard/base.html`) now includes:

**Intelligence Section:**
- Analytics → `/dashboard/analytics/`
- Revenue → `/dashboard/revenue/`
- **Campaigns** → `/dashboard/campaigns/` *(NEW)*
- A/B Tests → `/dashboard/ab-tests/`
- Products → `/dashboard/products/`

**Communications Section:**
- Engagement → `/dashboard/engage/`
- Email System → `/dashboard/emails/`

### Admin Capabilities

Each admin section provides platform-wide visibility:

- **Campaigns Overview**: Total campaigns, status breakdown, objective distribution, active campaigns list, top users by campaign count, recent activity feed
- **Products Overview**: Total products, stock status distribution, low stock alerts, stock update history, users with products
- **Revenue Overview**: Total revenue, top users by revenue, conversion breakdown, daily trends
- **Engagement Overview**: Total interactions, sentiment breakdown, superfan leaderboard, interaction feed
- **Email Overview**: Total subscribers, campaign metrics, delivery rate, email log audit trail

---

## 11. Plan Limits Architecture

Every feature in Phase 6 is gated by plan limits. The `PLAN_LIMITS` dict in `apps/billing/models.py` controls access.

### Complete Plan Comparison

| Feature | Starter (KES 299) | Growth (KES 999) | Pro (KES 1,999) | Agency (KES 2,999) |
|---------|-------------------|-------------------|------------------|---------------------|
| **Social Accounts** | 1 | 3 | 10 | 25 |
| **Posts/month** | 15 | 60 | 150 | Unlimited |
| **Seeds/month** | 5 | 30 | 60 | Unlimited |
| **AI Agents** | Create, Analyst | +Research, Adapt | +Engage, Strategist | All 6 |
| **Daily Brief** | ✅ | ✅ | ✅ | ✅ |
| **Email Brief** | ❌ | ✅ | ✅ | ✅ |
| **Engagement Agent** | ❌ | ✅ | ✅ | ✅ |
| **Competitor Tracking** | ❌ | ✅ | ✅ | ✅ |
| **AI Images** | ❌ | 50/mo | 100/mo | Unlimited |
| **A/B Testing** | ❌ | ✅ | ✅ | ✅ |
| **Team Members** | 0 | 0 | 5 | 25 |
| **Kova Pages** | 1 | 3 | 10 | 50 |
| **Links per Page** | 5 | 20 | 100 | Unlimited |
| **Kova Forms** | ❌ | ✅ | ✅ | ✅ |
| **Leads** | 10 | 100 | Unlimited | Unlimited |
| **Email Subscribers** | 50 | 2,500 | 25,000 | Unlimited |
| **Email Lists** | 1 | 5 | Unlimited | Unlimited |
| **Email Campaigns/mo** | 2 | 10 | Unlimited | Unlimited |
| **Email Sequences** | 0 | 3 | Unlimited | Unlimited |
| **Products** | 5 | 30 | 100 | Unlimited |
| **Quantity Tracking** | ❌ | ✅ | ✅ | ✅ |
| **CSV Import** | ❌ | ✅ | ✅ | ✅ |
| **Shopify** | ❌ | ✅ | ✅ | ✅ |
| **M-Pesa Commerce** | ❌ | ✅ | ✅ | ✅ |
| **Multi-touch Attribution** | ❌ | ❌ | ✅ | ✅ |
| **Campaigns** | 2 | 5 | Unlimited | Unlimited |
| **Revenue Dashboard** | ✅ | ✅ | ✅ | ✅ |

### How Plan Gating Works

```python
# In any view that needs plan limits:
from apps.billing.models import get_plan_limits

limits = get_plan_limits(request.user.profile.plan)  # e.g., "starter"
max_products = limits.get("max_products", 5)

current_count = Product.objects.filter(user=request.user).count()
if current_count >= max_products:
    messages.warning(request, f"Your plan allows up to {max_products} products.")
    return redirect("billing:pricing")
```

Every `_create` view in Phase 6 follows this pattern — check plan limit → count existing → allow or redirect to upgrade.

---

## 12. Data Flow & System Connections

### The Complete KOVA Pipeline

```
┌─────────────────────────────────────────────────────────────────┐
│                        CAMPAIGN                                 │
│  (name, objective, UTM tag, date range, target platforms)       │
│  Links to: ContentSeeds + EmailCampaigns                        │
└──────────┬──────────────────────────────────┬───────────────────┘
           │                                  │
    ┌──────▼──────┐                    ┌──────▼──────┐
    │ ContentSeed │                    │EmailCampaign│
    │ (idea/brief)│                    │ (subject,   │
    └──────┬──────┘                    │  body, list)│
           │                           └──────┬──────┘
    ┌──────▼──────┐                           │
    │    Posts     │                    ┌──────▼──────┐
    │ (per-platform│                   │EmailSubscrib│
    │  + CTA)     │                    │   ers       │
    └──────┬──────┘                    └─────────────┘
           │
    ┌──────▼──────┐        ┌────────────┐
    │  Published  │───────▶│ Interaction│──▶ Superfan Detection
    │  to Social  │        │ (comments, │
    └──────┬──────┘        │  DMs, etc) │
           │               └────────────┘
    ┌──────▼──────┐
    │  Kova Page  │──▶ LinkClick ──▶ FormSubmission ──▶ Lead
    │  (bio link) │        │
    └─────────────┘        │
                    ┌──────▼──────┐
                    │ Conversion  │──▶ Revenue Attribution
                    │ (UTM-linked │    (by post, platform,
                    │  to campaign│     campaign, product)
                    │  + product) │
                    └─────────────┘
```

### Key Data Connections

| From | To | Connection |
|------|----|------------|
| Campaign → ContentSeed | Through `CampaignSeed` | M2M with role + order |
| Campaign → EmailCampaign | Through `CampaignEmail` | M2M with role + order |
| Campaign → Conversion | Via `utm_campaign_tag` | Auto-pushed to posts on activation |
| ContentSeed → Post | ForeignKey | One seed → multiple platform posts |
| Post → Interaction | ForeignKey | Comments/replies on a post |
| Interaction → Superfan | Via `author_username` count | Auto-tier promotion |
| KovaForm → FormSubmission | ForeignKey | Form responses |
| FormSubmission → Lead | Auto-created | Source tracked |
| Lead → EmailSubscriber | ForeignKey link | Cross-reference |
| Post → Conversion | ForeignKey | Revenue attribution |
| Product → Conversion | ForeignKey | Product revenue tracking |
| Product → StockAlert | ForeignKey | Auto-generated alerts |

---

## 13. What This Means for KOVA

### Before Phase 6
KOVA was a content creation and publishing tool with AI agents. Smart, but incomplete. It could create and post content, but couldn't answer:
- "Did that post make me money?"
- "Who are my most engaged followers?"  
- "How many leads did Instagram generate this month?"
- "Is this product in stock before I promote it?"
- "How is my email campaign performing?"

### After Phase 6
KOVA is a **Business Intelligence Operating System**. The full pipeline:

1. **KNOW** what to sell (Product Intelligence: stock status, featured items, categories)
2. **CREATE** strategic content (AI agents with product awareness, A/B testing, CTAs)
3. **PUBLISH** across platforms (6 platforms, campaign coordination, UTM tracking)
4. **CAPTURE** the audience (Kova Pages, forms, lead auto-creation)
5. **NURTURE** with email (subscribers, lists, campaigns, sequences)
6. **ENGAGE** conversations (AI replies, superfan detection, sentiment tracking)
7. **CONVERT** to revenue (conversion tracking, multi-touch attribution)
8. **MEASURE** everything (revenue dashboard, ROI calculation, competitor intel)
9. **ORCHESTRATE** it all (campaigns connecting social + email + attribution)

### The Competitive Moat
Every feature compounds the others. A competitor would need to replicate not just individual features, but the entire connected pipeline. The data that flows through this system — brand voice profiles, content performance, lead behavior, conversion patterns, product intelligence, superfan detection — creates a moat that deepens with every day a customer uses KOVA.

### Category Created
**"Stock-Aware Social Intelligence"** — No other platform combines AI content creation with live product catalog awareness and full-pipeline revenue attribution. Tools like Coursiv automate ad spend. Tools like Buffer schedule posts. KOVA builds intelligence that compounds over time.

---

## Appendix: Files Created in Phase 6

### New Django Apps
- `apps/leads/` — 8 files (models, views, urls, forms, admin, apps, __init__, migrations)
- `apps/links/` — 8 files
- `apps/products/` — 8 files
- `apps/campaigns/` — 8 files

### New Templates
- `templates/leads/` — 7 templates
- `templates/links/` — 8+ templates
- `templates/emails/` — 9+ marketing templates (on top of 20 transactional)
- `templates/engage/` — 2+ templates
- `templates/products/` — 8+ templates
- `templates/campaigns/` — 3 templates
- `templates/analytics/` — 6+ templates (revenue, competitors, insights)
- `templates/admin_dashboard/campaigns/` — 2 templates
- `templates/admin_dashboard/products/` — 4 templates
- `templates/admin_dashboard/revenue/` — 4 templates
- `templates/admin_dashboard/engage/` — 3 templates
- `templates/admin_dashboard/billing/` — 12 templates
- `templates/content/ab_tests/` — 3 templates

### Admin Dashboard Views
- `apps/admin_dashboard/views/campaigns.py` — 2 views
- `apps/admin_dashboard/views/products.py` — 4 views
- `apps/admin_dashboard/views/revenue.py` — 5 views
- `apps/admin_dashboard/views/emails.py` — 5 views
- `apps/admin_dashboard/views/engage.py` — 3 views
- `apps/admin_dashboard/views/billing.py` — 12 views

### Migrations
- `leads/0001_initial` — Lead, LeadActivity
- `links/0001_initial` — KovaPage, KovaLink, LinkClick, KovaForm, FormSubmission, PageView
- `emails/marketing` — EmailSubscriber, EmailList, EmailCampaign, EmailSequence, SequenceEnrollment
- `products/0001_initial` — ProductCategory, Product, StockUpdate, StockAlert
- `campaigns/0001_initial` — Campaign, CampaignSeed, CampaignEmail, CampaignNote
- `analytics/` — Conversion, ConversionJourney, Competitor, CompetitorAnalysis, CompetitorInsight
- `content/` — Post CTA fields, A/B test fields

---

*Phase 6 complete. KOVA is no longer a content tool — it's a BIOS.*
