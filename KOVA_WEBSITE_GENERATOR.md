# Kova Website Generator — A to Z Specification

**Status:** Planning / Pre-build
**Owner:** Iranzi Innocent (Founder), Claude (Technical Co-founder)
**Last Updated:** 2026-05-06
**Target ship:** Phase 1 MVP — 4 weeks from build start

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Strategic Positioning](#2-strategic-positioning)
3. [Vision & Product Principles](#3-vision--product-principles)
4. [User Stories](#4-user-stories)
5. [System Architecture](#5-system-architecture)
6. [Cloudflare Infrastructure](#6-cloudflare-infrastructure)
7. [Cost Model](#7-cost-model)
8. [Django Application Structure](#8-django-application-structure)
9. [Data Models](#9-data-models)
10. [Section Schema](#10-section-schema)
11. [Theme System](#11-theme-system)
12. [Generation Pipeline](#12-generation-pipeline)
13. [Deployment Pipeline](#13-deployment-pipeline)
14. [Domain Management](#14-domain-management)
15. [Update & Regeneration Flow](#15-update--regeneration-flow)
16. [The Cloudflare Worker](#16-the-cloudflare-worker)
17. [Cloudflare Setup Checklist](#17-cloudflare-setup-checklist)
18. [Environment Variables](#18-environment-variables)
19. [URL Routes & API Endpoints](#19-url-routes--api-endpoints)
20. [Integration with Other Kova Apps](#20-integration-with-other-kova-apps)
21. [User Interface & Editor Model](#21-user-interface--editor-model)
22. [Security Considerations](#22-security-considerations)
23. [SEO & Performance](#23-seo--performance)
24. [Analytics & Feedback Loop](#24-analytics--feedback-loop)
25. [Pricing & Plan Tiers](#25-pricing--plan-tiers)
26. [Implementation Roadmap](#26-implementation-roadmap)
27. [Failure Modes & Mitigations](#27-failure-modes--mitigations)
28. [Open Questions](#28-open-questions)
29. [Glossary](#29-glossary)

---

## 1. Executive Summary

The Kova Website Generator is an AI agent that creates and continuously maintains a complete business website for every Kova subscriber. It is **not** a website builder. There is no drag-and-drop editor, no visual canvas, no template chooser overwhelm.

When a user subscribes to Kova, an agent reads everything Kova already knows about them — brand voice, top-performing posts, product catalogue, social profiles, lead activity — and generates a multi-page website on a Kova subdomain within minutes. The user can later connect a custom domain.

The user maintains the site by typing intent in plain language: *"Update the headline to focus on our new same-day delivery service."* The agent regenerates the relevant section and redeploys the site.

The site lives on Cloudflare (R2 + Workers + KV + Custom Hostnames) so we have near-zero hosting cost per user and can scale to tens of thousands of sites without infrastructure changes.

This is the missing layer that turns Kova from a social media tool into a complete digital presence platform.

---

## 2. Strategic Positioning

### What we are NOT competing with

| Category | Examples | Why we don't compete |
|---|---|---|
| Website builders | Wix, Squarespace, Webflow | They sell a canvas. We sell an outcome. Different battlefield. |
| E-commerce platforms | Shopify, WooCommerce | We integrate with payments, but our core is presence not catalogue. |
| Headless CMS | Sanity, Contentful | We have no CMS. The DB is the CMS. |

### What we ARE competing with

- **"I don't have a website"** — the majority of small businesses in our target markets (East Africa, emerging markets, solopreneurs globally) don't have one because building and maintaining one is too much effort.
- **"My website is dead"** — businesses with abandoned WordPress/Wix sites that haven't been updated in 2+ years and embarrass them.
- **"My website is a single Linktree"** — creators using link-in-bio tools because building a real site felt impossible.

### Our unfair advantages

1. **We already know the brand voice.** No website tool on earth has `profile.brand_voice` already filled in by the user.
2. **We already have proven content.** 50+ posts with engagement data tells us what copy works.
3. **The closed loop:** Social → Website → Leads → Social. No website tool owns the social layer; no social tool owns the web layer. Kova owns both.
4. **The refresh engine:** Websites die because nobody updates them. Kova generates content daily anyway — we recycle the best into the website automatically.
5. **Local context:** We understand the user's market (e.g., Kigali, Nairobi). Generic builders don't.

### The category we are creating

**"Autonomous Digital Presence"** — your business's online home that runs itself. No competitor has named this category. We can.

---

## 3. Vision & Product Principles

### North star

> *Every Kova subscriber has a professional, current, conversion-ready website that reflects their voice and updates itself — without them ever opening a builder.*

### Product principles (non-negotiable)

1. **Zero learning curve.** If a user has to read documentation to update their site, we have failed.
2. **Always current.** The site must never look stale. Auto-refresh top sections monthly.
3. **One site per user (initially).** Don't let users build agencies on us. Phase 3 problem.
4. **Generated, not edited.** All changes go through the AI. No raw HTML editing. This protects design integrity.
5. **Mobile-first.** 80%+ of our target market browses on phones. Desktop is secondary.
6. **Fast.** Sub-1-second loads globally. Cloudflare gives us this for free.
7. **Owned by the user.** Custom domains are essential. We host, but they own the URL.
8. **No lock-in trap.** If they leave Kova, they can export their site as static HTML.

### What we deliberately don't build

- ❌ Drag-and-drop canvas
- ❌ Per-pixel style controls
- ❌ Custom CSS injection by user
- ❌ Multi-site management (Phase 3+)
- ❌ Membership/login systems on user sites
- ❌ Email hosting (CNAME/MX support only)
- ❌ Visual A/B testing tools (the agent handles variants)

---

## 4. User Stories

### Onboarding

- **US-1:** As a new subscriber who has just completed onboarding, I want my website to generate automatically so I see immediate value within minutes.
- **US-2:** As a new user, I want to see my generated site at a Kova subdomain (e.g., `mybrand.kova.app`) so I can share it without buying a domain first.
- **US-3:** As a new user, I want to preview the site before publishing so I can confirm it represents me.

### Editing

- **US-4:** As a user, I want to type "change my hero headline to X" and have the site update so I don't need to learn a builder.
- **US-5:** As a user, I want to regenerate a single section without rebuilding the whole site so I can iterate quickly.
- **US-6:** As a user, I want to choose between 2–3 visual themes so my site doesn't look identical to every other Kova site.

### Custom Domain

- **US-7:** As a user with my own domain, I want to point it to my Kova site with one CNAME record so my customers see my real brand URL.
- **US-8:** As a user, I want SSL to "just work" on my custom domain so I never have to think about certificates.
- **US-9:** As a user, I want clear DNS instructions and live status feedback so I know when my domain is ready.

### Maintenance

- **US-10:** As a user, I want my best-performing social posts to feature on my homepage automatically so my site always shows my best work.
- **US-11:** As a user, when my brand voice changes, I want my website copy to update accordingly so it stays consistent.
- **US-12:** As a user, I want my Daily Brief to show me website traffic and conversions so I know if it's working.

### Conversion

- **US-13:** As a user, I want website visitors to be captured as Leads so I can engage them through Kova.
- **US-14:** As a user, I want a contact form on my site that emails me and creates a Lead simultaneously.

### Trust & Recovery

- **US-15:** As a user, I want to see when my site was last updated so I know it's fresh.
- **US-16:** As a user, if generation fails, I want a clear error message and a one-click retry.
- **US-17:** As a user leaving Kova, I want to export my site as static HTML so I don't lose my work.

---

## 5. System Architecture

### High-level diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│                          USER'S BROWSER                              │
│                  visits mybrand.com or slug.kova.app                 │
└────────────────────────────────┬────────────────────────────────────┘
                                 │ HTTPS request
                                 ▼
┌─────────────────────────────────────────────────────────────────────┐
│                      CLOUDFLARE EDGE NETWORK                         │
│   ┌──────────────────────────────────────────────────────────┐     │
│   │              Worker (kova-sites-router)                   │     │
│   │  1. Read hostname                                         │     │
│   │  2. Look up site_id in KV                                │     │
│   │  3. Fetch HTML from R2                                   │     │
│   │  4. Return response with CDN cache headers               │     │
│   └─────────┬────────────────────────────┬───────────────────┘     │
│             │                            │                          │
│             ▼                            ▼                          │
│   ┌─────────────────┐         ┌──────────────────────────────┐    │
│   │  KV Namespace   │         │       R2 Bucket              │    │
│   │  SITE_MAP       │         │       kova-sites             │    │
│   │                 │         │                              │    │
│   │ slug.kova.app   │         │ sites/                       │    │
│   │   → user_abc    │         │   user_abc/                  │    │
│   │ mybrand.com     │         │     index.html               │    │
│   │   → user_abc    │         │     about.html               │    │
│   └─────────────────┘         │     services.html            │    │
│                               │     contact.html             │    │
│                               │     style.css                │    │
│                               │   user_xyz/...               │    │
│                               └──────────────────────────────┘    │
│                                                                    │
│   ┌──────────────────────────────────────────────────────────┐   │
│   │            Custom Hostnames (Cloudflare for SaaS)         │   │
│   │   Auto SSL provisioning for user-owned domains           │   │
│   └──────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────┘
                                 ▲
                                 │ Deployments via Cloudflare API
                                 │
┌─────────────────────────────────────────────────────────────────────┐
│                       KOVA DJANGO APP (Railway)                      │
│                                                                      │
│  ┌───────────────────────────────────────────────────────────┐     │
│  │   apps/websites/                                           │     │
│  │   ├── models.py        — KovaWebsite, WebsiteDomain       │     │
│  │   ├── generator.py     — Claude-powered section gen       │     │
│  │   ├── renderer.py      — Jinja2 → HTML files              │     │
│  │   ├── cloudflare.py    — CF API client (R2/KV/Hostnames) │     │
│  │   ├── tasks.py         — Celery: generate + deploy        │     │
│  │   ├── views.py         — Dashboard, preview, domains      │     │
│  │   └── templates/themes/ — Jinja2 site templates           │     │
│  └───────────────────────────────────────────────────────────┘     │
│                                                                      │
│  Reads from:  Profile.brand_voice, Post.published, ContentSeed,     │
│               SocialAccount, Product, Lead                          │
│                                                                      │
│  Triggers:    On onboarding complete, brand_voice change,           │
│               user request, monthly auto-refresh                    │
└─────────────────────────────────────────────────────────────────────┘
```

### Request flow (read path)

1. User browser hits `mybrand.com`
2. DNS (set up via CNAME by user) resolves to Cloudflare
3. Cloudflare Custom Hostnames terminates SSL with auto-provisioned cert
4. Worker route matches; Worker script executes
5. Worker reads hostname → looks up `mybrand.com` in KV → gets `user_abc`
6. Worker fetches `sites/user_abc/index.html` from R2
7. Worker returns response with `Cache-Control: public, max-age=3600`
8. Cloudflare CDN caches at edge for 1 hour
9. Subsequent requests served from edge cache (sub-50ms globally)

### Write flow (deployment path)

1. Trigger fires (onboarding done / user request / cron)
2. Celery task `generate_and_deploy_website(user_id)` queued
3. Generator pulls context (brand voice, top posts, products, etc.)
4. Claude API call → returns structured sections JSON
5. Sections saved to `KovaWebsite.sections` field
6. Renderer applies Jinja2 theme template → produces HTML files
7. CloudflareClient uploads files to R2 via S3-compatible API
8. CloudflareClient writes KV entry mapping domain → user_id
9. `KovaWebsite.is_published = True`, `last_deployed_at = now()`
10. User notified: "Your site is live at mybrand.kova.app"

---

## 6. Cloudflare Infrastructure

### 6.1 Cloudflare Workers

**Purpose:** The single request router for all Kova-hosted sites.

**Configuration:**
- One Worker named `kova-sites-router`
- Routes:
  - `*.kova.app/*` (wildcard for all default subdomains)
  - One route per custom hostname (auto-added when user connects domain)
- Bindings:
  - `SITES_BUCKET` — R2 bucket binding
  - `SITE_MAP` — KV namespace binding
- Memory: 128 MB (default)
- CPU: 10 ms / request typical, 50 ms limit on free tier

**Why one Worker for all sites:** Simpler deploys, single source of truth for routing logic, no per-site cold starts.

### 6.2 Cloudflare R2 (Object Storage)

**Purpose:** Stores all generated HTML/CSS/asset files for every user's website.

**Bucket structure:**
```
kova-sites/
├── sites/
│   ├── user_abc123/
│   │   ├── index.html
│   │   ├── about.html
│   │   ├── services.html
│   │   ├── contact.html
│   │   ├── thanks.html
│   │   ├── style.css
│   │   └── assets/
│   │       ├── logo.png
│   │       └── og-image.jpg
│   └── user_xyz456/
│       └── ...
└── _system/
    ├── 404.html       # fallback served when no site matches
    └── error.html
```

**Why R2 over S3:** Zero egress fees. With S3, every page load costs us money. With R2, only storage costs (which are negligible for HTML).

**Access:** S3-compatible API via boto3. Generate access keys in Cloudflare dashboard.

### 6.3 Cloudflare KV (Key-Value Store)

**Purpose:** Maps incoming hostnames to user/site IDs at the edge with sub-1ms latency.

**Namespace:** `SITE_MAP`

**Schema:**
```
KEY                          VALUE
─────────────────────────    ──────────────
mybrand.kova.app             user_abc123
mybrand.com                  user_abc123
www.mybrand.com              user_abc123
anothershop.kova.app         user_xyz456
```

**Why KV not the database:** Every page request hits the lookup. KV is replicated globally and reads in <1ms. A database call from the Worker would add 100–500ms.

### 6.4 Cloudflare for SaaS (Custom Hostnames)

**Purpose:** Allows arbitrary user-owned domains to be served by our Worker with auto-provisioned SSL.

**How it works:**
1. We POST to `/zones/{zone_id}/custom_hostnames` with `{ "hostname": "mybrand.com" }`
2. Cloudflare returns a hostname ID and DNS verification instructions
3. User adds CNAME record at their registrar
4. Cloudflare validates ownership and issues a free SSL cert via Let's Encrypt
5. Site is now accessible over HTTPS at the custom domain

**Cost:** $2/month for first 100 hostnames, then $0.10/hostname/month.

### 6.5 Cloudflare Web Analytics

**Purpose:** Privacy-first analytics for every site. Free.

**Integration:** Inject the analytics snippet into the generated HTML `<head>`. We aggregate per-site data via Cloudflare GraphQL Analytics API and surface in the Daily Brief.

---

## 7. Cost Model

### Per-service costs

| Service | Free tier | Paid pricing | Notes |
|---|---|---|---|
| Workers | 100K req/day | $5/mo for 10M req, then $0.30/M | Single Worker handles all users. |
| R2 storage | 10 GB | $0.015/GB/mo | A typical site is <500 KB. |
| R2 operations | 1M reads, 1M writes | $0.36/M reads, $4.50/M writes | Reads dominate; cache reduces them. |
| KV reads | 100K/day | $0.50/M | Cached at edge, real reads << total reqs. |
| KV writes | 1K/day | $5/M | Only on deploy/domain change. |
| Custom Hostnames | None on free | $2/mo + $0.10/hostname after 100 | Only for custom domains. |
| Web Analytics | Unlimited | Free | Privacy-first. |

### Total cost projection

| Active users | Custom domains | Workers | R2 | KV | Hostnames | **Total / mo** | **Per user** |
|---|---|---|---|---|---|---|---|
| 50 | 10 | $0 | $0 | $0 | $2 | **$2** | $0.04 |
| 200 | 50 | $0 | $0 | $0 | $2 | **$2** | $0.01 |
| 500 | 200 | $5 | $0.01 | $0 | $12 | **$17** | $0.034 |
| 1,000 | 500 | $5 | $0.02 | $0 | $42 | **$47** | $0.047 |
| 5,000 | 2,500 | $5 | $0.10 | $1 | $242 | **$248** | $0.05 |
| 20,000 | 10,000 | $30 | $0.50 | $5 | $992 | **$1,028** | $0.05 |

**Key insight:** Cost per user stays at ~$0.05/month even at 20K users. If we charge $20/month for the Growth plan that includes a website with custom domain, hosting margin is **99.75%**.

### Hidden costs to plan for

- **Claude API for generation:** ~$0.20–$0.50 per full site generation (one-time + monthly refresh). Not Cloudflare cost.
- **Domain bookkeeping:** If we eventually offer "buy a domain through Kova," we resell at registrar cost (~$12/yr) — that's a Phase 3+ revenue stream, not now.

---

## 8. Django Application Structure

### Directory layout

```
apps/websites/
├── __init__.py
├── apps.py
├── admin.py
├── urls.py
├── views.py
├── models.py
├── forms.py
├── signals.py
├── generator.py          # Claude-powered section generation
├── renderer.py           # Jinja2 template → HTML files
├── cloudflare.py         # Cloudflare API client
├── tasks.py              # Celery: generate_website, deploy_website, refresh_website
├── prompts.py            # System and section-specific prompts for Claude
├── schemas.py            # Pydantic schemas for sections JSON validation
├── themes/
│   ├── clean/
│   │   ├── theme.json    # Theme metadata (colors, fonts)
│   │   ├── base.html     # Jinja2 template
│   │   ├── _hero.html
│   │   ├── _about.html
│   │   ├── _services.html
│   │   ├── _testimonials.html
│   │   ├── _faq.html
│   │   ├── _contact.html
│   │   └── _footer.html
│   ├── bold/
│   │   └── ...
│   └── minimal/
│       └── ...
├── static_site/
│   ├── style.css         # Pre-compiled Tailwind for generated sites
│   └── icons/
├── tests/
│   ├── test_generator.py
│   ├── test_renderer.py
│   ├── test_cloudflare.py
│   └── test_tasks.py
└── migrations/
```

### Templates (Django app templates, not user site templates)

```
templates/websites/
├── dashboard.html        # User's website dashboard
├── preview.html          # iframe preview
├── editor.html           # Section-by-section "what would you change" editor
├── domain_setup.html     # Custom domain wizard
├── domain_status.html    # SSL provisioning status (HTMX-polled)
└── partials/
    ├── _section_card.html
    ├── _generation_status.html
    └── _domain_dns_instructions.html
```

---

## 9. Data Models

### 9.1 KovaWebsite

```python
class KovaWebsite(models.Model):
    """
    One website per user (Phase 1).
    Phase 3+ may relax to multi-site for agency users.
    """
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="website",
    )

    # Identity
    slug = models.SlugField(
        max_length=63,
        unique=True,
        help_text="Becomes {slug}.kova.app",
    )
    business_name = models.CharField(max_length=200)
    tagline = models.CharField(max_length=500, blank=True)

    # Generated content
    sections = models.JSONField(
        default=dict,
        help_text="See SectionSchema in schemas.py",
    )
    pages = models.JSONField(
        default=list,
        help_text="['index', 'about', 'services', 'contact']",
    )

    # Theme
    theme = models.CharField(
        max_length=50,
        default="clean",
        choices=[
            ("clean", "Clean"),
            ("bold", "Bold"),
            ("minimal", "Minimal"),
        ],
    )
    color_palette = models.JSONField(
        default=dict,
        help_text="{'primary': '#0F4C5C', 'accent': '#E36414', ...}",
    )

    # State
    GENERATION_STATUS = [
        ("pending", "Pending"),
        ("generating", "Generating"),
        ("rendering", "Rendering"),
        ("deploying", "Deploying"),
        ("live", "Live"),
        ("failed", "Failed"),
    ]
    generation_status = models.CharField(
        max_length=20,
        default="pending",
        choices=GENERATION_STATUS,
    )
    generation_error = models.TextField(blank=True)
    is_published = models.BooleanField(default=False)

    # Deployment tracking
    last_generated_at = models.DateTimeField(null=True, blank=True)
    last_deployed_at = models.DateTimeField(null=True, blank=True)
    deploy_count = models.PositiveIntegerField(default=0)

    # Auto-refresh
    auto_refresh_enabled = models.BooleanField(default=True)
    next_auto_refresh_at = models.DateTimeField(null=True, blank=True)

    # Analytics summary (cached, refreshed nightly)
    analytics_snapshot = models.JSONField(
        default=dict,
        help_text="{'views_7d': 245, 'visitors_7d': 89, 'conversions_7d': 3}",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Kova Website"

    @property
    def default_url(self) -> str:
        return f"https://{self.slug}.{settings.KOVA_SITES_DOMAIN}"

    @property
    def primary_url(self) -> str:
        domain = self.domains.filter(is_primary=True, is_active=True).first()
        return f"https://{domain.hostname}" if domain else self.default_url

    @property
    def all_hostnames(self) -> list[str]:
        return [f"{self.slug}.{settings.KOVA_SITES_DOMAIN}"] + [
            d.hostname for d in self.domains.filter(is_active=True)
        ]
```

### 9.2 WebsiteDomain

```python
class WebsiteDomain(models.Model):
    """
    A custom domain attached to a KovaWebsite.
    A user may have multiple (e.g., apex + www).
    """
    website = models.ForeignKey(
        KovaWebsite,
        on_delete=models.CASCADE,
        related_name="domains",
    )
    hostname = models.CharField(max_length=253, unique=True)

    # Cloudflare integration
    cf_custom_hostname_id = models.CharField(max_length=100, blank=True)
    cf_status = models.CharField(
        max_length=30,
        default="pending",
        choices=[
            ("pending", "Pending DNS validation"),
            ("active", "Active"),
            ("ssl_pending", "SSL provisioning"),
            ("failed", "Failed"),
            ("removed", "Removed"),
        ],
    )
    cf_validation_record = models.JSONField(default=dict)

    # User-facing
    is_primary = models.BooleanField(default=False)
    is_active = models.BooleanField(default=False)

    last_checked_at = models.DateTimeField(null=True, blank=True)
    activated_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["website"],
                condition=models.Q(is_primary=True),
                name="one_primary_domain_per_site",
            ),
        ]
```

### 9.3 WebsiteGenerationLog

```python
class WebsiteGenerationLog(models.Model):
    """
    Audit log of every generation/deploy. Useful for debugging and the user
    activity feed ("Site refreshed 2 hours ago — homepage updated").
    """
    website = models.ForeignKey(
        KovaWebsite,
        on_delete=models.CASCADE,
        related_name="generation_logs",
    )
    trigger = models.CharField(
        max_length=50,
        choices=[
            ("onboarding", "Initial generation after onboarding"),
            ("user_request", "User-requested update"),
            ("section_edit", "Single-section regeneration"),
            ("brand_voice_changed", "Brand voice changed"),
            ("auto_refresh", "Monthly auto-refresh"),
            ("theme_change", "Theme changed"),
            ("retry", "Manual retry after failure"),
        ],
    )
    sections_regenerated = models.JSONField(default=list)
    user_prompt = models.TextField(blank=True)

    duration_ms = models.PositiveIntegerField(null=True)
    tokens_used = models.PositiveIntegerField(default=0)
    cost_usd = models.DecimalField(max_digits=8, decimal_places=4, default=0)

    success = models.BooleanField(default=False)
    error = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
```

### 9.4 WebsiteContactSubmission

```python
class WebsiteContactSubmission(models.Model):
    """
    Form submissions from the contact form on the user's website.
    Each submission also creates a Lead via signals.
    """
    website = models.ForeignKey(
        KovaWebsite,
        on_delete=models.CASCADE,
        related_name="contact_submissions",
    )
    name = models.CharField(max_length=200)
    email = models.EmailField()
    phone = models.CharField(max_length=50, blank=True)
    message = models.TextField()

    # Tracking
    source_page = models.CharField(max_length=100, blank=True)
    referrer = models.URLField(blank=True)
    ip_address = models.GenericIPAddressField(null=True)
    user_agent = models.TextField(blank=True)

    lead = models.ForeignKey(
        "leads.Lead",
        null=True, blank=True,
        on_delete=models.SET_NULL,
    )

    is_spam = models.BooleanField(default=False)
    handled = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)
```

---

## 10. Section Schema

The `KovaWebsite.sections` JSONField stores all site content as structured data. Validated by Pydantic schemas in `schemas.py`.

### 10.1 Top-level structure

```json
{
  "schema_version": 1,
  "hero": { ... },
  "value_props": { ... },
  "about": { ... },
  "services": { ... },
  "testimonials": { ... },
  "faq": { ... },
  "cta_banner": { ... },
  "contact": { ... },
  "footer": { ... },
  "meta": {
    "title": "...",
    "description": "...",
    "og_image_url": "..."
  }
}
```

### 10.2 Section types

#### Hero (always present)

```json
{
  "headline": "Premium briquettes that burn longer.",
  "subheadline": "Eco-friendly fuel for Rwandan homes and businesses — delivered.",
  "primary_cta": {
    "label": "Order now",
    "url": "/contact/"
  },
  "secondary_cta": {
    "label": "Learn more",
    "url": "/about/"
  },
  "image_prompt": "A neat stack of dark briquettes on a clean kitchen surface, warm natural light",
  "image_url": "https://..."
}
```

#### Value props (always present)

```json
{
  "heading": "Why choose us",
  "items": [
    {
      "title": "Burns 40% longer",
      "description": "Tested against firewood at independent labs.",
      "icon": "flame"
    },
    {
      "title": "100% eco-friendly",
      "description": "Made from agricultural waste, no trees cut.",
      "icon": "leaf"
    },
    {
      "title": "Same-day delivery",
      "description": "Order before noon, get it the same day in Kigali.",
      "icon": "truck"
    }
  ]
}
```

#### About (always present)

```json
{
  "heading": "About us",
  "story": "Started in 2024 by Iranzi Innocent...",
  "highlight": "Over 5,000 households served across Kigali",
  "founder_quote": {
    "text": "We started this because firewood was destroying forests faster than we could plant.",
    "name": "Iranzi Innocent",
    "role": "Founder"
  }
}
```

#### Services / Products

```json
{
  "heading": "What we offer",
  "items": [
    {
      "name": "Standard briquette pack — 25kg",
      "description": "Perfect for home use, lasts 3–4 weeks for an average family.",
      "price": "5,000 RWF",
      "image_url": "https://...",
      "cta_label": "Order this",
      "cta_url": "/contact/?product=standard"
    }
  ]
}
```

#### Testimonials

```json
{
  "heading": "What people say",
  "items": [
    {
      "quote": "Lasts twice as long as charcoal and no smoke in my kitchen.",
      "name": "Marie U.",
      "role": "Customer in Kicukiro",
      "image_url": "..."
    }
  ]
}
```

#### FAQ

```json
{
  "heading": "Frequently asked questions",
  "items": [
    {
      "question": "How long does a 25kg pack last?",
      "answer": "A typical family of five uses one pack every 3–4 weeks for daily cooking."
    }
  ]
}
```

#### CTA banner

```json
{
  "headline": "Ready to switch?",
  "subheadline": "Order your first pack today and get free delivery in Kigali.",
  "cta": {
    "label": "Get started",
    "url": "/contact/"
  }
}
```

#### Contact

```json
{
  "heading": "Get in touch",
  "intro": "Have a question or want to place a bulk order? We respond within 2 hours.",
  "email": "iranzi297@gmail.com",
  "phone": "+250 7XX XXX XXX",
  "whatsapp": "+250 7XX XXX XXX",
  "address": "Kigali, Rwanda",
  "form_fields": ["name", "email", "phone", "message"],
  "social_links": {
    "linkedin": "https://...",
    "instagram": "https://..."
  }
}
```

#### Footer

```json
{
  "tagline": "Eco-friendly fuel for a cleaner Rwanda.",
  "copyright_year": 2026,
  "links": [
    {"label": "About", "url": "/about/"},
    {"label": "Services", "url": "/services/"},
    {"label": "Contact", "url": "/contact/"}
  ]
}
```

#### Meta (SEO)

```json
{
  "title": "Briquettes Co — Premium Eco Fuel in Kigali",
  "description": "Long-burning, eco-friendly briquettes delivered to your door in Kigali. Order online today.",
  "og_image_url": "https://...",
  "keywords": ["briquettes", "eco fuel", "Kigali", "Rwanda"]
}
```

### 10.3 Schema versioning

Every sections JSON has `schema_version`. When we evolve the schema (add a section type, rename a field), we bump the version and write a migration in `apps/websites/migrations_data/`. Old sites lazily upgrade on next regeneration.

---

## 11. Theme System

### 11.1 What a theme is

A theme is:
- A directory under `apps/websites/themes/{name}/`
- A `theme.json` describing its metadata
- A set of Jinja2 templates that consume the sections JSON
- A pre-compiled CSS file with theme-specific Tailwind utilities

Themes are **completely interchangeable** — switching theme should never lose content because all themes consume the same sections JSON.

### 11.2 Initial themes (Phase 1)

| Theme | Vibe | Best for |
|---|---|---|
| **Clean** | Modern, professional, blue/white | Service businesses, B2B, consultants |
| **Bold** | High contrast, large type, vivid color | Creators, restaurants, retail |
| **Minimal** | Typography-led, monochrome, lots of white space | Photographers, writers, premium brands |

### 11.3 Theme structure

```
themes/clean/
├── theme.json           # { "name": "Clean", "primary_color": "#0F4C5C", "fonts": [...] }
├── base.html            # Jinja2 layout (head, nav, footer)
├── index.html           # Homepage layout
├── about.html
├── services.html
├── contact.html
├── _hero.html           # Section partials
├── _value_props.html
├── _about.html
├── _services.html
├── _testimonials.html
├── _faq.html
├── _cta_banner.html
├── _contact_form.html
├── _footer.html
└── style.css            # Pre-compiled (no client-side Tailwind)
```

### 11.4 Theme selection

- On first generation, agent picks a theme based on the user's industry (heuristic; can be overridden)
- User can switch in the dashboard — triggers a redeploy with same sections JSON in new templates

---

## 12. Generation Pipeline

### 12.1 The generator agent

Located in `apps/websites/generator.py`. Uses Claude (Sonnet 4.6 default; Opus 4.7 for premium plans) via prompt caching.

### 12.2 Context gathering

```python
def gather_context(user) -> dict:
    return {
        "business_name": user.profile.business_name,
        "industry": user.profile.industry,
        "location": user.profile.city or user.profile.country,
        "brand_voice": user.profile.brand_voice,
        "tone_keywords": user.profile.tone_keywords,
        "target_audience": user.profile.target_audience,
        "products": list(user.products.values("name", "description", "price")),
        "top_posts": list(
            user.posts.filter(status="published")
            .order_by("-engagement_score")[:10]
            .values("content_text", "ai_angle")
        ),
        "social_accounts": {
            sa.platform: sa.profile_url for sa in user.social_accounts.filter(is_active=True)
        },
        "contact_info": {
            "email": user.email,
            "phone": user.profile.phone,
            "address": user.profile.address,
        },
    }
```

### 12.3 The generation prompt

System prompt (cached for prompt caching efficiency):

```
You are Kova's website generation agent. You generate professional, conversion-
focused website content for small business owners. You return STRICTLY VALID
JSON matching the provided schema. You write in the user's brand voice. You
NEVER fabricate testimonials, case studies, statistics, or client names. If
you don't have real testimonials, omit the testimonials section.

Voice rules:
- Write in second person where natural
- Match the user's tone exactly (formal/casual/playful as specified)
- Use concrete numbers when provided (delivery times, prices, etc.)
- Localize where relevant (currency, region, language)

Hard constraints:
- NEVER invent statistics ("trusted by 500 customers" unless we said so)
- NEVER invent testimonials
- NEVER promise capabilities not in the user context
- Avoid generic AI phrases ("In today's fast-paced world...", "elevate your...")
```

User prompt:

```
Generate a complete website for the following business. Return JSON matching
the WebsiteSections schema.

Business: {business_name}
Industry: {industry}
Location: {location}
Brand voice: {brand_voice}

Top-performing social posts (use these for tone calibration and to surface
proven angles in copy):
{top_posts}

Products / services:
{products}

Generate sections: hero, value_props, about, services, faq, cta_banner,
contact, footer, meta. Skip testimonials unless the user has provided real
ones. Use the products list to populate services. Make the CTA banner
specific (e.g., "Order before noon for same-day delivery") rather than
generic ("Get started today").
```

### 12.4 Structured output enforcement

Use Anthropic's tool use as a structured output mechanism. Define a `submit_website_sections` tool with the full sections schema and force the model to use it.

```python
def generate_sections(user) -> dict:
    context = gather_context(user)
    response = anthropic_client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=8000,
        system=[{"type": "text", "text": SYSTEM_PROMPT, "cache_control": {"type": "ephemeral"}}],
        tools=[SUBMIT_SECTIONS_TOOL],
        tool_choice={"type": "tool", "name": "submit_website_sections"},
        messages=[{"role": "user", "content": render_user_prompt(context)}],
    )
    sections = response.content[0].input
    SectionSchema.model_validate(sections)  # Pydantic validation
    return sections
```

### 12.5 Per-section regeneration

For "change my hero headline" requests, we don't regenerate the whole site. We send the existing sections + the user's intent and ask for only the changed section.

```python
def regenerate_section(user, section_name: str, user_intent: str) -> dict:
    current = user.website.sections
    response = anthropic_client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=2000,
        system=[{"type": "text", "text": SYSTEM_PROMPT, "cache_control": {"type": "ephemeral"}}],
        tools=[REGENERATE_SECTION_TOOL],
        tool_choice={"type": "tool", "name": "regenerate_section"},
        messages=[{
            "role": "user",
            "content": (
                f"Current {section_name} section:\n{json.dumps(current[section_name])}\n\n"
                f"User wants: {user_intent}\n\n"
                f"Brand voice: {user.profile.brand_voice}\n\n"
                f"Return the new section only."
            ),
        }],
    )
    return response.content[0].input
```

### 12.6 Content safety pass

After generation, run a quick safety check:
- No banned words list (configurable per market)
- No phone numbers other than the user's own (prevents prompt injection from posts)
- No URLs other than the user's own (same)

---

## 13. Deployment Pipeline

### 13.1 Renderer

Takes sections JSON + theme, produces HTML files.

```python
def render_site(website: KovaWebsite) -> dict[str, str]:
    """Returns {filename: html_content} ready for upload."""
    env = jinja2.Environment(
        loader=jinja2.FileSystemLoader(f"apps/websites/themes/{website.theme}"),
        autoescape=True,
    )
    files = {}
    for page in website.pages:
        template = env.get_template(f"{page}.html")
        files[f"{page}.html"] = template.render(
            sections=website.sections,
            site=website,
            user=website.user,
        )
    files["style.css"] = read_compiled_css(website.theme)
    return files
```

### 13.2 Cloudflare upload

```python
class CloudflareClient:
    def upload_site(self, user_id: str, files: dict[str, str]):
        for path, content in files.items():
            content_type = mimetypes.guess_type(path)[0] or "text/html"
            self.s3.put_object(
                Bucket=settings.CF_R2_BUCKET,
                Key=f"sites/{user_id}/{path}",
                Body=content.encode("utf-8"),
                ContentType=content_type,
                CacheControl="public, max-age=3600",
            )

    def register_domain(self, hostname: str, user_id: str):
        self._kv_put(hostname, user_id)
```

### 13.3 The Celery task

```python
@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def generate_and_deploy_website(self, website_id: int, trigger: str = "user_request"):
    website = KovaWebsite.objects.get(id=website_id)
    log = WebsiteGenerationLog.objects.create(website=website, trigger=trigger)
    started = time.time()

    try:
        website.generation_status = "generating"
        website.save(update_fields=["generation_status"])

        sections = generate_sections(website.user)
        website.sections = sections
        website.last_generated_at = timezone.now()

        website.generation_status = "rendering"
        website.save(update_fields=["sections", "last_generated_at", "generation_status"])
        files = render_site(website)

        website.generation_status = "deploying"
        website.save(update_fields=["generation_status"])
        cf = CloudflareClient()
        cf.upload_site(f"user_{website.user_id}", files)
        cf.register_domain(f"{website.slug}.{settings.KOVA_SITES_DOMAIN}", f"user_{website.user_id}")

        website.generation_status = "live"
        website.is_published = True
        website.last_deployed_at = timezone.now()
        website.deploy_count += 1
        website.save()

        log.success = True
        log.duration_ms = int((time.time() - started) * 1000)
        log.save()
    except Exception as exc:
        website.generation_status = "failed"
        website.generation_error = str(exc)[:500]
        website.save(update_fields=["generation_status", "generation_error"])
        log.success = False
        log.error = str(exc)
        log.save()
        raise self.retry(exc=exc)
```

### 13.4 Cache invalidation

When we redeploy, the Worker still serves from CDN cache for up to 1 hour unless we purge. We purge via Cloudflare API:

```python
def purge_cache(hostnames: list[str]):
    httpx.post(
        f"https://api.cloudflare.com/client/v4/zones/{settings.CF_ZONE_ID}/purge_cache",
        headers={"Authorization": f"Bearer {settings.CF_API_TOKEN}"},
        json={"hosts": hostnames},
    )
```

---

## 14. Domain Management

### 14.1 Default subdomain

Every website has `{slug}.{KOVA_SITES_DOMAIN}` (e.g., `mybrand.kova.app`).

- Slug is unique, derived from business name on first generation, user can change once
- Slug must match `^[a-z0-9][a-z0-9-]{1,61}[a-z0-9]$`
- Reserved slugs: `www`, `app`, `api`, `admin`, `mail`, `blog`, etc. (configurable list)
- Wildcard route on the Worker handles all `*.kova.app` traffic

### 14.2 Custom domain flow

```
USER ACTION                          SYSTEM ACTION                       USER FEEDBACK
───────────                          ─────────────                       ─────────────
Enters "mybrand.com" in dashboard
                                     POST /custom_hostnames
                                     CF returns hostname_id +
                                     validation record
                                                                         "Add this CNAME:
                                                                          mybrand.com → 
                                                                          sites.kova.app"
User adds CNAME at registrar
                                     Background poll every 60s:
                                     GET /custom_hostnames/{id}
                                     status: pending → ssl_pending
                                                                         "DNS detected,
                                                                          provisioning SSL..."
                                     status: ssl_pending → active
                                     Update KV: mybrand.com → user_id
                                     Set is_active=True, primary=True
                                                                         "Live at
                                                                          https://mybrand.com"
```

### 14.3 The DNS instructions UI

The instructions page must be foolproof. We show:
1. A copy-button for the exact CNAME value
2. A registrar-specific guide (GoDaddy / Namecheap / Cloudflare / Other)
3. Real-time status: "Waiting for DNS..." → "DNS detected" → "SSL provisioning" → "Live ✓"
4. Estimated time ("Usually 5–15 minutes")
5. A "Test connection" button that probes DNS manually

### 14.4 Apex vs. www

A user may want both `mybrand.com` and `www.mybrand.com` to work. We handle this by:
- Letting them add both as separate `WebsiteDomain` records
- Setting one as `is_primary=True` (canonical)
- The Worker emits a 301 redirect from non-primary → primary

### 14.5 Domain removal

User can disconnect a custom domain. We:
1. Delete the Custom Hostname via CF API
2. Remove KV entry
3. Soft-delete the `WebsiteDomain` record (set `is_active=False`)
4. The site remains live at `{slug}.kova.app`

---

## 15. Update & Regeneration Flow

### 15.1 Trigger sources

| Trigger | Frequency | Scope |
|---|---|---|
| Onboarding complete | Once | Full site |
| User intent prompt | On demand | Single section or full |
| Brand voice changed | On change | Full site (next deploy) |
| Theme changed | On demand | Full site (sections unchanged) |
| Top post promoted | On promote | Hero or testimonials section |
| Monthly auto-refresh | Cron | Hero + value props + CTA banner |
| Product added/edited | On change | Services section |
| Manual retry after failure | On demand | Full site |

### 15.2 The natural language editor

In the dashboard, the user sees their site as a list of sections (Hero, About, Services, ...). Beside each section is a "Refine" button. Clicking it opens a small textarea: *"What would you like changed?"*

The user types intent → we call `regenerate_section()` → diff is shown in preview → user accepts → site redeploys.

### 15.3 Auto-refresh

A nightly Celery beat task identifies sites where `next_auto_refresh_at <= now()` and `auto_refresh_enabled=True`. For each, it:
- Pulls the latest top posts
- Regenerates Hero subheadline + CTA banner only (low-risk sections)
- Logs the change in the activity feed: *"Kova refreshed your homepage with content from your top post this month"*

Default refresh cadence: monthly.

### 15.4 Diff preview

Before redeploying after a regeneration, show the user a side-by-side: old vs. new copy. They click "Publish" to deploy. This builds trust and prevents AI surprises.

For onboarding generation and auto-refresh, no diff preview — those are auto-published.

---

## 16. The Cloudflare Worker

### 16.1 Full Worker source

```javascript
// cloudflare-worker/src/index.js
// Single Worker that routes all Kova-hosted websites.

const KOVA_DOMAIN = "kova.app";          // configurable
const CACHE_TTL = 3600;                   // 1 hour edge cache
const SYSTEM_404 = "_system/404.html";

export default {
  async fetch(request, env, ctx) {
    const url = new URL(request.url);
    const hostname = url.hostname.toLowerCase();
    const pathname = url.pathname;

    // 1. Resolve hostname → user_id
    const userId = await env.SITE_MAP.get(hostname);
    if (!userId) {
      return systemNotFound(env);
    }

    // 2. Handle form POST (contact form)
    if (request.method === "POST" && pathname === "/_contact") {
      return handleContactForm(request, env, userId);
    }

    // 3. Resolve path → file in R2
    const filePath = resolveFilePath(pathname);
    const r2Key = `sites/${userId}${filePath}`;

    // 4. Fetch from R2 (with edge caching)
    const cache = caches.default;
    const cacheKey = new Request(url.toString(), request);
    let response = await cache.match(cacheKey);
    if (response) return response;

    const object = await env.SITES_BUCKET.get(r2Key);
    if (!object) {
      // Fallback: try index.html for SPA-style routing
      const fallback = await env.SITES_BUCKET.get(`sites/${userId}/index.html`);
      if (!fallback) return systemNotFound(env);
      response = htmlResponse(fallback.body);
    } else {
      response = new Response(object.body, {
        headers: {
          "Content-Type": contentTypeFor(filePath),
          "Cache-Control": `public, max-age=${CACHE_TTL}`,
          "X-Kova-Site": userId,
        },
      });
    }

    ctx.waitUntil(cache.put(cacheKey, response.clone()));
    return response;
  },
};

function resolveFilePath(pathname) {
  if (pathname === "/" || pathname === "") return "/index.html";
  if (pathname.endsWith("/")) return `${pathname}index.html`;
  if (!pathname.includes(".")) return `${pathname}.html`;
  return pathname;
}

function contentTypeFor(path) {
  if (path.endsWith(".html")) return "text/html; charset=utf-8";
  if (path.endsWith(".css")) return "text/css; charset=utf-8";
  if (path.endsWith(".js")) return "application/javascript; charset=utf-8";
  if (path.endsWith(".png")) return "image/png";
  if (path.endsWith(".jpg") || path.endsWith(".jpeg")) return "image/jpeg";
  if (path.endsWith(".webp")) return "image/webp";
  if (path.endsWith(".svg")) return "image/svg+xml";
  return "application/octet-stream";
}

function htmlResponse(body) {
  return new Response(body, {
    headers: {
      "Content-Type": "text/html; charset=utf-8",
      "Cache-Control": `public, max-age=${CACHE_TTL}`,
    },
  });
}

async function systemNotFound(env) {
  const fallback = await env.SITES_BUCKET.get(SYSTEM_404);
  if (fallback) {
    return new Response(fallback.body, {
      status: 404,
      headers: { "Content-Type": "text/html; charset=utf-8" },
    });
  }
  return new Response("Site not found", { status: 404 });
}

async function handleContactForm(request, env, userId) {
  const formData = await request.formData();
  // Forward to Kova's Django app for processing
  const resp = await fetch(`${env.KOVA_API_URL}/api/websites/contact-submit/`, {
    method: "POST",
    headers: {
      "Authorization": `Bearer ${env.KOVA_INTERNAL_TOKEN}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      user_id: userId,
      name: formData.get("name"),
      email: formData.get("email"),
      phone: formData.get("phone"),
      message: formData.get("message"),
      source_url: request.headers.get("Referer") || "",
    }),
  });

  if (!resp.ok) {
    return new Response("Submission failed", { status: 500 });
  }

  // Redirect to thank-you page
  return Response.redirect(`https://${new URL(request.url).hostname}/thanks/`, 303);
}
```

### 16.2 wrangler.toml

```toml
name = "kova-sites-router"
main = "src/index.js"
compatibility_date = "2026-04-01"

[[kv_namespaces]]
binding = "SITE_MAP"
id = "<NAMESPACE_ID_FROM_DASHBOARD>"

[[r2_buckets]]
binding = "SITES_BUCKET"
bucket_name = "kova-sites"

[vars]
KOVA_API_URL = "https://app.kova.app"

[vars.production]
KOVA_API_URL = "https://app.kova.app"

# Secrets set via `wrangler secret put`:
# KOVA_INTERNAL_TOKEN

[[routes]]
pattern = "*.kova.app/*"
zone_name = "kova.app"
```

---

## 17. Cloudflare Setup Checklist

One-time setup, performed once before Phase 1 build starts.

### 17.1 Cloudflare account

- [ ] Sign in to or create a Cloudflare account
- [ ] Add the apex domain (e.g., `kova.app`) — change nameservers at registrar
- [ ] Verify zone is active

### 17.2 Workers

- [ ] Enable Workers (free plan is fine to start)
- [ ] Create Worker named `kova-sites-router` (we'll deploy code via wrangler)
- [ ] Note the Worker subdomain (e.g., `kova-sites-router.your-account.workers.dev`)

### 17.3 R2

- [ ] Enable R2 (requires payment method but no charge until usage)
- [ ] Create bucket `kova-sites`
- [ ] Generate R2 access key + secret (for boto3 uploads from Django)
- [ ] Optional: enable public bucket access for assets, keep HTML private

### 17.4 KV

- [ ] Enable Workers KV
- [ ] Create namespace `SITE_MAP`
- [ ] Note the namespace ID

### 17.5 Wildcard subdomain

- [ ] Add DNS record: `*.kova.app` → CNAME → 100:: (proxied)
- [ ] Add Worker route: `*.kova.app/*` → `kova-sites-router`

### 17.6 Custom Hostnames (Cloudflare for SaaS)

- [ ] Enable Cloudflare for SaaS in dashboard
- [ ] Configure fallback origin (the Worker)
- [ ] Set Custom Hostname SSL method: `http` (HTTP-01 challenge)

### 17.7 API token

- [ ] Create API token with permissions:
  - Workers Scripts: Edit
  - Workers KV Storage: Edit
  - Workers R2 Storage: Edit
  - SSL and Certificates: Edit
  - Custom Hostnames: Edit
  - Cache Purge: Purge
  - Zone: Read
- [ ] Restrict to the Kova zone only
- [ ] Save token in 1Password / vault — copy to Railway env vars

### 17.8 Web Analytics

- [ ] Enable Web Analytics
- [ ] Create site token (we'll inject into generated HTML)

### 17.9 Wrangler CLI

- [ ] Install wrangler locally (`npm i -g wrangler`)
- [ ] `wrangler login` (authenticates against your CF account)
- [ ] `wrangler deploy` to ship the Worker

---

## 18. Environment Variables

Add to `config/settings/base.py` and Railway env:

```python
# Cloudflare account
CF_ACCOUNT_ID = env("CF_ACCOUNT_ID")
CF_API_TOKEN = env("CF_API_TOKEN")
CF_ZONE_ID = env("CF_ZONE_ID")

# R2
CF_R2_BUCKET = env("CF_R2_BUCKET", default="kova-sites")
CF_R2_ACCESS_KEY = env("CF_R2_ACCESS_KEY")
CF_R2_SECRET_KEY = env("CF_R2_SECRET_KEY")
CF_R2_ENDPOINT = env("CF_R2_ENDPOINT")  # https://{account_id}.r2.cloudflarestorage.com

# KV
CF_KV_NAMESPACE_ID = env("CF_KV_NAMESPACE_ID")

# Sites
KOVA_SITES_DOMAIN = env("KOVA_SITES_DOMAIN", default="kova.app")

# Worker → Django authentication for contact form posts
KOVA_INTERNAL_TOKEN = env("KOVA_INTERNAL_TOKEN")

# Web Analytics
CF_ANALYTICS_TOKEN = env("CF_ANALYTICS_TOKEN", default="")
```

---

## 19. URL Routes & API Endpoints

### 19.1 Django routes (`apps/websites/urls.py`)

```python
app_name = "websites"

urlpatterns = [
    # User-facing dashboard
    path("", views.website_dashboard, name="dashboard"),
    path("preview/", views.website_preview, name="preview"),
    path("generate/", views.trigger_generation, name="generate"),
    path("regenerate-section/", views.regenerate_section, name="regenerate_section"),
    path("change-theme/", views.change_theme, name="change_theme"),
    path("activity/", views.generation_activity, name="activity"),
    path("export/", views.export_static_html, name="export"),

    # Domain management
    path("domain/setup/", views.domain_setup, name="domain_setup"),
    path("domain/<int:domain_id>/status/", views.domain_status, name="domain_status"),
    path("domain/<int:domain_id>/remove/", views.domain_remove, name="domain_remove"),
    path("domain/<int:domain_id>/set-primary/", views.domain_set_primary, name="domain_set_primary"),

    # Internal API (called from Worker)
    path("api/contact-submit/", views.api_contact_submit, name="api_contact_submit"),
    path("api/health/", views.api_health, name="api_health"),
]
```

### 19.2 Mounted in main `config/urls.py`

```python
path("websites/", include("apps.websites.urls", namespace="websites")),
```

### 19.3 HTMX endpoints

- `POST /websites/regenerate-section/` — body: `{section: "hero", intent: "..."}`, returns updated section card partial
- `GET /websites/domain/{id}/status/` — returns SSL provisioning status partial (poll every 30s while pending)
- `POST /websites/generate/` — kicks off Celery task, returns "generating..." card

---

## 20. Integration with Other Kova Apps

### 20.1 Onboarding

After `accounts.views.onboarding_complete()`:
```python
KovaWebsite.objects.create(user=user, slug=generate_unique_slug(user))
generate_and_deploy_website.delay(website.id, trigger="onboarding")
```

### 20.2 Brand voice changes

Signal in `accounts/signals.py`:
```python
@receiver(pre_save, sender=Profile)
def detect_brand_voice_change(sender, instance, **kwargs):
    if not instance.pk: return
    old = Profile.objects.get(pk=instance.pk)
    if old.brand_voice != instance.brand_voice:
        if hasattr(instance.user, "website"):
            generate_and_deploy_website.delay(
                instance.user.website.id,
                trigger="brand_voice_changed",
            )
```

### 20.3 Content Studio

Add a "Promote to homepage" action on top-performing posts. Stores the post ID in `KovaWebsite.featured_post_ids` and triggers a hero/testimonials regeneration that uses the post copy.

### 20.4 Daily Brief

In `apps/briefs/tasks.py::_gather_brief_data()`, add:
```python
website = getattr(user, "website", None)
if website and website.is_published:
    data["website"] = {
        "url": website.primary_url,
        "views_7d": website.analytics_snapshot.get("views_7d", 0),
        "visitors_7d": website.analytics_snapshot.get("visitors_7d", 0),
        "conversions_7d": website.analytics_snapshot.get("conversions_7d", 0),
        "last_deployed_at": website.last_deployed_at,
    }
```

The brief LLM gets website signals as part of its context and can mention them: *"Your website got 245 visits this week, up 30% from last week."*

### 20.5 Leads

Signal: `WebsiteContactSubmission.post_save` creates a `Lead`:
```python
@receiver(post_save, sender=WebsiteContactSubmission)
def create_lead_from_submission(sender, instance, created, **kwargs):
    if not created or instance.is_spam: return
    lead = Lead.objects.create(
        user=instance.website.user,
        name=instance.name,
        email=instance.email,
        phone=instance.phone,
        source="website_contact_form",
        notes=instance.message,
    )
    instance.lead = lead
    instance.save(update_fields=["lead"])
```

### 20.6 Engage

Future: when a website visitor leaves a contact submission, the engagement agent can draft a follow-up email (Phase 2).

### 20.7 Billing

Plan gate in `views.website_dashboard`:
```python
if not user.subscription.plan.includes_website:
    return redirect("billing:pricing")
```

---

## 21. User Interface & Editor Model

### 21.1 Dashboard (`/websites/`)

Single-page dashboard showing:

**Top hero:**
- Site preview thumbnail (screenshot or iframe)
- Status badge: 🟢 Live / 🟡 Generating / 🔴 Failed
- Primary URL (custom domain if set, else slug.kova.app) — copy button
- "View live site" + "Preview in editor" buttons

**Domain section:**
- Default URL with copy button
- Custom domain (if connected) with status
- "Connect custom domain" CTA if none

**Sections list:**
- One row per section (Hero, About, Services, ...)
- Each row: section preview snippet + "Refine" button
- Click "Refine" → modal: "What would you change about this section?"

**Activity feed:**
- Last 10 generation logs
- "Site refreshed 2h ago — homepage updated"
- "Theme changed to Bold — 1 day ago"

**Theme switcher:**
- Three theme cards
- Click → modal: "Switch theme? Your content stays the same."

**Settings:**
- Auto-refresh toggle (default: on, monthly)
- Slug change (one-time)
- Export site (download .zip of HTML)
- Disable site

### 21.2 The "Refine section" modal

```
┌─────────────────────────────────────────────────┐
│  Refine: Hero                                    │
│                                                  │
│  Current:                                        │
│  ┌────────────────────────────────────────────┐ │
│  │ Headline: Premium briquettes that burn     │ │
│  │           longer.                           │ │
│  │ Sub: Eco-friendly fuel for Rwandan...      │ │
│  └────────────────────────────────────────────┘ │
│                                                  │
│  What would you like changed?                   │
│  ┌────────────────────────────────────────────┐ │
│  │ Make the headline focus on free same-day   │ │
│  │ delivery in Kigali instead.                │ │
│  └────────────────────────────────────────────┘ │
│                                                  │
│             [ Cancel ]   [ Refine with AI ]     │
└─────────────────────────────────────────────────┘
```

After AI returns:
```
┌─────────────────────────────────────────────────┐
│  Preview the change                              │
│                                                  │
│  Old: Premium briquettes that burn longer.      │
│  New: Free same-day briquette delivery in Kigali│
│                                                  │
│             [ Try again ]   [ Publish change ]   │
└─────────────────────────────────────────────────┘
```

### 21.3 Domain setup wizard

Step 1: enter domain
Step 2: copy CNAME instructions, choose registrar guide
Step 3: live status (HTMX-polled every 30s) — shows propagation, SSL, then "✓ Live"

---

## 22. Security Considerations

### 22.1 Threats

| Threat | Mitigation |
|---|---|
| User enters someone else's domain | Cloudflare Custom Hostname validates ownership via DNS before SSL issues. |
| Prompt injection from social posts → malicious site copy | Generation prompt strips URLs/phone numbers not matching user's known set; Pydantic validates schema; review queue for first-time generation in early phase. |
| User enters reserved Kova subdomain | Slug validation against blacklist. |
| Worker exposed to abuse (high request volume) | Cloudflare bot protection on Workers; per-IP rate limit on contact form. |
| Spam contact submissions | Honeypot field + Cloudflare Turnstile (free); spam classification on server. |
| Stolen R2 key uploads malicious files | R2 key scoped to bucket only; rotate quarterly; keys in env vars never in code. |
| User uploads malicious image to "image upload" feature | Phase 1 has no image uploads; AI generates images. Phase 2 adds image moderation. |
| User-controlled HTML in generated site | NEVER. All content is JSON, rendered server-side via Jinja2 with autoescape. No user-provided HTML accepted. |
| KV poisoning (someone overwrites a domain mapping) | KV writes only via authenticated Django app using API token; user can't write directly. |
| User exports site to escape Kova | This is fine. We promised it. Export is HTML+CSS only (no DB). |

### 22.2 Data privacy

- Contact form submissions are stored in our DB; user owns them
- Cloudflare Web Analytics is privacy-first (no cookies, no tracking) — GDPR/CCPA safe by default
- Custom domain SSL certs are shared (DV, free, public CT logs) — same as any SaaS
- No third-party trackers injected into user sites without consent

### 22.3 Rate limiting

- Generation: 10 generations/day/user (cost protection)
- Section regeneration: 50/day/user
- Contact form: 5 submissions/IP/hour, 50/site/hour

---

## 23. SEO & Performance

### 23.1 What we get free from Cloudflare

- Global CDN (sub-50ms TTFB worldwide)
- Brotli compression
- HTTP/3
- Auto SSL
- Image optimization (Polish)

### 23.2 What we add

- Pre-compiled, minified CSS (no client-side Tailwind)
- Image lazy-loading by default
- `<title>`, `<meta description>`, OG tags from sections.meta
- JSON-LD `LocalBusiness` schema generated from contact info
- `sitemap.xml` per site, generated on deploy
- `robots.txt` allowing crawl
- Canonical URLs (primary domain)

### 23.3 Performance targets

| Metric | Target |
|---|---|
| TTFB | < 100 ms globally |
| LCP | < 1.5 s |
| Page weight | < 200 KB |
| Lighthouse Performance | ≥ 95 |
| Lighthouse SEO | ≥ 95 |

### 23.4 Indexing

We submit each new custom domain to Google Search Console via Indexing API — Phase 2.

---

## 24. Analytics & Feedback Loop

### 24.1 What we measure

| Metric | Source | Used for |
|---|---|---|
| Page views (per site, per page) | CF Web Analytics | Daily Brief, dashboard |
| Unique visitors | CF Web Analytics | Daily Brief |
| Top referrers | CF Web Analytics | Suggesting where to share |
| Top pages | CF Web Analytics | Promoting performing pages on social |
| Contact form submissions | Our DB | Lead pipeline |
| Time on page | CF Web Analytics | Quality signal |
| Country breakdown | CF Web Analytics | Targeting insights |

### 24.2 Daily snapshot

Nightly Celery task `apps/websites/tasks.py::snapshot_analytics()`:
- Calls Cloudflare GraphQL Analytics API for each active site
- Stores 7-day rolling totals in `KovaWebsite.analytics_snapshot`
- Available immediately to Daily Brief generator

### 24.3 The feedback loop

```
        Social posts
             │
             ▼
    Top performers identified
             │
             ▼
    Promoted to website (hero, testimonials)
             │
             ▼
    Website traffic grows
             │
             ▼
    Contact form submissions
             │
             ▼
    Leads created
             │
             ▼
    Daily Brief surfaces leads + traffic
             │
             ▼
    User engages leads (Engage app)
             │
             ▼
    Engagement → more social posts
             │
             └──────── back to top
```

This is the moat. Every other social tool dead-ends at the post; every other website tool dead-ends at the page. Kova closes the loop.

---

## 25. Pricing & Plan Tiers

### 25.1 Tier mapping

| Plan | Website? | Custom domain? | Auto-refresh? | Themes | Pages |
|---|---|---|---|---|---|
| Free / Trial | Default subdomain only | ❌ | ❌ | 1 | Home only |
| Starter | ✅ | ❌ | Monthly | 3 | Home, About, Contact |
| Growth | ✅ | ✅ | Monthly + on-event | 3 | + Services |
| Scale | ✅ | ✅ + multiple | Weekly | All | + FAQ, blog (Phase 2) |
| Enterprise | ✅ | ✅ unlimited | Custom | All + custom | All |

### 25.2 Why include in Growth not extra-charge

Including the website in Growth (rather than as a $X/mo add-on) deepens lock-in. A user with their custom domain on Kova is far less likely to churn. This is a strategic loss-leader.

### 25.3 Future revenue streams

- Premium themes (designer collaborations) — $5–10/mo
- Buy-domain-through-Kova — markup over registrar cost
- E-commerce (Stripe checkout in pages) — % of GMV
- Blog auto-publishing from social → SEO add-on — $10/mo

---

## 26. Implementation Roadmap

### Phase 1 — MVP (4 weeks from build start)

**Week 1: Foundation**
- [ ] Cloudflare account setup (R2, Workers, KV, Custom Hostnames, API token)
- [ ] Deploy Worker skeleton via wrangler — confirm `*.kova.app` routes work with hardcoded HTML
- [ ] Create `apps/websites/` with models + migrations
- [ ] `CloudflareClient` class (R2 upload + KV write)
- [ ] End-to-end test: manually trigger upload of static HTML → confirm visible at `test.kova.app`

**Week 2: Generation**
- [ ] `gather_context()` + `generate_sections()` in `generator.py`
- [ ] Pydantic schemas for sections
- [ ] Build "Clean" theme (base + section partials + compiled CSS)
- [ ] Renderer: sections + theme → HTML files
- [ ] Celery task `generate_and_deploy_website` end-to-end
- [ ] Trigger from onboarding completion

**Week 3: User dashboard**
- [ ] Dashboard view (`/websites/`) with status, preview, sections list
- [ ] "Refine section" modal + HTMX endpoint
- [ ] Activity feed
- [ ] Theme switcher (build remaining 2 themes: Bold, Minimal)
- [ ] Diff preview before publishing single-section changes

**Week 4: Custom domains + polish**
- [ ] Custom Hostname creation via CF API
- [ ] DNS instructions UI with copy button + registrar guides
- [ ] Status polling (HTMX) until SSL active
- [ ] Worker contact form handler → Django endpoint → Lead creation
- [ ] Cloudflare Web Analytics injection
- [ ] Daily Brief integration (analytics snapshot)
- [ ] End-to-end test on real domain
- [ ] Deploy to Railway production
- [ ] Soft launch to 10 beta users

### Phase 2 — Growth features (months 2–3)

- [ ] Multiple pages with rich routing
- [ ] FAQ section
- [ ] Blog (auto-published from social)
- [ ] Image moderation for user uploads
- [ ] More themes (5 total)
- [ ] Per-section A/B variants chosen by AI based on conversion
- [ ] SEO submission to Google
- [ ] Sitemap auto-generation

### Phase 3 — Scale features (months 4–6)

- [ ] E-commerce (Stripe checkout, product pages with cart)
- [ ] Multi-site for agency users
- [ ] Custom CSS overrides via prompt ("make the buttons rounder")
- [ ] Programmatic image generation (custom hero images per page)
- [ ] Email forwarding for custom domains
- [ ] Multi-language sites

### Phase 4 — Platform features (post month 6)

- [ ] Theme marketplace (designers submit, revenue share)
- [ ] White-label for agency partners
- [ ] API access for third-party integrations

---

## 27. Failure Modes & Mitigations

| Failure | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Claude API outage during generation | Low | High (no site) | Retry with exponential backoff; fall back to Sonnet if Opus unavailable; show "generating" state to user. |
| R2 outage | Very low | High | Cloudflare's SLA is 99.99%; if down, sites are unreachable (acceptable for outage window). |
| KV stale after deploy | Medium | Low | Purge cache on every deploy; KV is eventually-consistent within seconds. |
| Custom domain SSL stuck pending | Medium | High (user frustrated) | Show clear status; offer "retry verification"; 24h timeout → contact support. |
| Generated copy hallucinates testimonials | Medium | Medium | System prompt forbids; testimonials only from explicit user input; manual review for first 100 sites. |
| User-provided slug collides with Kova reserved word | Low | Low | Validate against blacklist before save. |
| Contact form spam | High | Low | Cloudflare Turnstile + honeypot + rate limit. |
| Worker hits CPU limit | Low | Medium | Logic is minimal; pre-render everything; no compute in Worker beyond routing. |
| Cloudflare API rate limit | Low | Medium | 1200 req/5min on free; we're well under; queue and back off if hit. |
| Theme template bug breaks all sites | Low | Catastrophic | Theme tests in CI; canary deploy to one site before fleet rollout. |

---

## 28. Open Questions

These need decisions before/during build but not blocking the spec:

1. **What's our `KOVA_SITES_DOMAIN`?** `kova.app`? `kova.site`? `getkova.app`? Cheap to register; pick one in Week 1.
2. **Multi-language sites:** Phase 3 problem. East Africa is multilingual (English/French/Swahili/Kinyarwanda); detect from brand voice and offer language toggle?
3. **Image generation for hero:** Use existing Kova image agent? Or stock photos from Unsplash API? MVP probably stock; Phase 2 generated.
4. **Site deletion vs. soft-delete:** When user cancels subscription, what happens to their site? Grace period of 30 days then hard delete from R2? KV entry removed immediately?
5. **Sitemap submission:** Google Search Console API requires verification; can we automate verification via Cloudflare DNS TXT record?
6. **Email setup for custom domains:** Just MX/SPF/DMARC instructions? Or partner with a transactional email provider for a "yourname@yourbrand.com" feature?
7. **A/B testing:** Phase 2; how do we measure "winning" — by contact form conversions only, or also by engaged time?
8. **Site backups:** Do we keep old versions of sections JSON for "undo"? Yes, in `WebsiteGenerationLog.sections_snapshot`?
9. **Template-locked sites for compliance industries:** Healthcare/legal/financial pages have strict copy rules — phase later.
10. **What to charge if user wants more than one site?** Phase 3 problem; preview answer: $10/mo per additional site.

---

## 29. Glossary

- **R2:** Cloudflare's object storage, S3-compatible, with zero egress fees.
- **Worker:** Cloudflare's serverless edge compute — JavaScript that runs on every request near the user.
- **KV:** Cloudflare's key-value store, edge-replicated, sub-1ms reads.
- **Custom Hostname (Cloudflare for SaaS):** Feature allowing user-owned domains to be served by your Worker with auto-provisioned SSL.
- **CNAME:** DNS record type that aliases one domain to another.
- **DV (Domain Validation):** SSL cert type proving domain ownership only (vs. OV/EV which prove organization identity).
- **Sections JSON:** The structured representation of a user's website content; what Claude generates and what themes render.
- **Theme:** A set of Jinja2 templates + CSS that consume sections JSON to produce HTML. All themes are interchangeable.
- **Refresh:** A regeneration of one or more sections to keep the site current.
- **Slug:** The user's chosen subdomain prefix (e.g., `mybrand` → `mybrand.kova.app`).
- **Wrangler:** Cloudflare's CLI for deploying Workers.
- **Edge cache:** Cloudflare's CDN layer that caches Worker responses globally.
- **Closed loop:** The architectural property where social → website → leads → social — each step feeds the next, owned by Kova end-to-end.

---

## Appendix A: Sample Pydantic Schema

```python
# apps/websites/schemas.py
from pydantic import BaseModel, Field, HttpUrl
from typing import Optional, Literal

class CTA(BaseModel):
    label: str = Field(..., max_length=80)
    url: str = Field(..., max_length=500)

class HeroSection(BaseModel):
    headline: str = Field(..., max_length=120)
    subheadline: str = Field(..., max_length=300)
    primary_cta: CTA
    secondary_cta: Optional[CTA] = None
    image_prompt: Optional[str] = Field(None, max_length=300)
    image_url: Optional[HttpUrl] = None

class ValuePropItem(BaseModel):
    title: str = Field(..., max_length=80)
    description: str = Field(..., max_length=300)
    icon: Literal["flame", "leaf", "truck", "check", "star", "shield", "clock", "heart"]

class ValuePropsSection(BaseModel):
    heading: str = Field(..., max_length=120)
    items: list[ValuePropItem] = Field(..., min_length=2, max_length=6)

# ... continued for every section type ...

class WebsiteSections(BaseModel):
    schema_version: int = 1
    hero: HeroSection
    value_props: ValuePropsSection
    about: AboutSection
    services: Optional[ServicesSection] = None
    testimonials: Optional[TestimonialsSection] = None
    faq: Optional[FAQSection] = None
    cta_banner: CTABannerSection
    contact: ContactSection
    footer: FooterSection
    meta: MetaSection
```

---

## Appendix B: Sample wrangler deploy command

```bash
# Deploy the Worker (one-time + on every Worker code change)
cd cloudflare-worker
wrangler login
wrangler kv:namespace create SITE_MAP
# Copy the namespace ID into wrangler.toml
wrangler r2 bucket create kova-sites
wrangler secret put KOVA_INTERNAL_TOKEN
wrangler deploy
```

---

## Appendix C: Sample first-deploy smoke test

After Week 1 setup, before any Django integration:

```bash
# 1. Manually upload a test HTML to R2
aws s3 cp test.html \
  s3://kova-sites/sites/test_user/index.html \
  --endpoint-url https://<account_id>.r2.cloudflarestorage.com

# 2. Manually write a KV entry
wrangler kv:key put --namespace-id=<NS_ID> \
  "test.kova.app" "test_user"

# 3. Curl the Worker
curl https://test.kova.app

# Expected: returns the HTML uploaded in step 1
```

If this works, the entire serving infrastructure is proven and we just need to wire Django to it.

---

## Document maintenance

This document is the source of truth for the Website Generator. Updates:

- **Major changes** (schema version, plan tiers, architectural shifts): update this doc and bump the date in the header.
- **Minor changes** (a new section type, a new theme): update the relevant section.
- **Decisions on Open Questions:** move from Section 28 into the relevant prior section.
- **Implementation findings:** add as Appendix entries.

When in doubt, this doc wins over Slack and tickets.

---

*End of specification.*
