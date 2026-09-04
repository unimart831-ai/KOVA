# Kova Platform Setup Guide — Meta, WhatsApp, TikTok & LinkedIn

> **Version**: 1.0 · **Last updated**: May 2026  
> **Audience**: Kova platform administrators (infrastructure + developer portal setup) 
> **Scope**: WhatsApp Cloud API, Facebook Pages, Instagram, TikTok, LinkedIn — verified against `config/settings/`, `.env.example`, and `apps/platforms/`

This is the **master setup guide** for connecting Kova to social platforms. It consolidates infrastructure steps that were previously split across multiple docs. For WhatsApp **user-facing** features (inbox, AI auto-reply, broadcasts), see [`WHATSAPP_SETUP_GUIDE.md`](./WHATSAPP_SETUP_GUIDE.md). For OAuth-only platform developer steps covering all 9 platforms, see [`PLATFORM_DEVELOPER_SETUP.md`](./PLATFORM_DEVELOPER_SETUP.md).

---

## Table of Contents

1. [Overview & prerequisites](#1-overview--prerequisites)
2. [Environment variables master table](#2-environment-variables-master-table)
3. [Meta (Facebook Developer App) — shared foundation](#3-meta-facebook-developer-app--shared-foundation)
4. [WhatsApp Cloud API (detailed)](#4-whatsapp-cloud-api-detailed)
5. [Facebook Pages & Messenger](#5-facebook-pages--messenger)
6. [Instagram (via Meta Graph API)](#6-instagram-via-meta-graph-api)
7. [TikTok for Business](#7-tiktok-for-business)
8. [LinkedIn Marketing / Community Management API](#8-linkedin-marketing--community-management-api)
9. [Connecting accounts inside Kova UI](#9-connecting-accounts-inside-kova-ui)
10. [Webhook verification checklist](#10-webhook-verification-checklist)
11. [App Review & permissions](#11-app-review--permissions)
12. [Security (tokens, secrets, rotation)](#12-security-tokens-secrets-rotation)
13. [FAQ per platform](#13-faq-per-platform)
14. [Appendix: Kova URL endpoints](#14-appendix-kova-url-endpoints)
15. [Production vs development checklists](#15-production-vs-development-checklists)

---

## 1. Overview & prerequisites

### What you are setting up

Kova uses **one Meta Developer App** for Facebook, Instagram, and WhatsApp (Cloud API + Embedded Signup). TikTok and LinkedIn each require **separate developer apps**. End users connect their own accounts from **Platforms** (`/platforms/`) — they never see your app secrets.

| Platform | Auth model | Kova provider file |
|----------|-----------|-------------------|
| WhatsApp | System User token **or** Embedded Signup OAuth | `apps/platforms/providers/whatsapp.py` |
| Facebook | OAuth 2.0 (Login for Business `config_id` or scopes) | `apps/platforms/providers/instagram_facebook.py` |
| Instagram | Same Meta app as Facebook (via linked Page) | `apps/platforms/providers/instagram_facebook.py` |
| TikTok | OAuth 2.0 (Login Kit + Content Posting API) | `apps/platforms/providers/tiktok.py` |
| LinkedIn | OAuth 2.0 (OpenID + Posts API) | `apps/platforms/providers/linkedin.py` |

### Infrastructure prerequisites

| Requirement | Why | Notes |
|-------------|-----|-------|
| **Public HTTPS domain** | Meta, TikTok, and LinkedIn reject HTTP callbacks in production | Set `SITE_URL=https://your-domain.com` (no trailing slash) |
| **Postgres + Redis** | OAuth state, Celery tasks, WhatsApp AI replies | `DATABASE_URL`, `REDIS_URL` |
| **Celery worker** | WhatsApp auto-reply, publishing, token refresh | `celery -A config worker -l info` |
| **Meta Business Portfolio** | WhatsApp, Business Verification, System Users | [business.facebook.com](https://business.facebook.com) |
| **Cloudflare R2 (recommended prod)** | Public HTTPS media URLs for Instagram/TikTok | `AWS_STORAGE_BUCKET_NAME`, `AWS_S3_*` — see `config/settings/production.py` |
| **`FIELD_ENCRYPTION_KEY` (production)** | Encrypts stored OAuth tokens | Required in production; separate from `SECRET_KEY` |

### Recommended setup order

1. **Core env** — `SITE_URL`, database, Redis, encryption key  
2. **Meta app** — unlocks Facebook, Instagram, WhatsApp  
3. **WhatsApp webhook** — inbound messages + delivery status  
4. **Facebook / Instagram OAuth** — publishing + engagement  
5. **LinkedIn app** — B2B posting  
6. **TikTok app** — video/photo posting (audit required for public posts)

### Related documentation

| Doc | Purpose |
|-----|---------|
| [`WHATSAPP_SETUP_GUIDE.md`](./WHATSAPP_SETUP_GUIDE.md) | WhatsApp admin + **user guide** (inbox, AI, templates, broadcasts) |
| [`KOVA_USER_GUIDE_WHATSAPP_REACH_EMAIL.md`](./KOVA_USER_GUIDE_WHATSAPP_REACH_EMAIL.md) | **End-user operator manual** — WhatsApp, REACH, and Email (day-to-day, non-admin) |
| [`WHATSAPP_TEMPLATES.md`](./WHATSAPP_TEMPLATES.md) | System template catalog + env vars |
| [`DAILY_BRIEF_WHATSAPP_SETUP.md`](./DAILY_BRIEF_WHATSAPP_SETUP.md) | Daily brief template + reply-to-act commands |
| [`PLATFORM_DEVELOPER_SETUP.md`](./PLATFORM_DEVELOPER_SETUP.md) | All 9 platforms (Twitter, YouTube, Pinterest, Threads, Bluesky) |
| [`social-login-setup.md`](./social-login-setup.md) | Facebook/Google **sign-up** buttons (uses same `FACEBOOK_APP_ID`) |
| [`LINKEDIN_PROFILE_SETUP.md`](./LINKEDIN_PROFILE_SETUP.md) | Founder LinkedIn profile (not API setup) |

---

## 2. Environment variables master table

Replace `{SITE_URL}` with your canonical base URL, e.g. `https://app.kovaagent.com`.

### Core (all environments)

| Variable | Required | Default | Purpose |
|----------|----------|---------|---------|
| `SITE_URL` | ✅ | `http://localhost:8000` | Canonical public URL; used in emails, media, OAuth context |
| `SECRET_KEY` | ✅ | insecure dev default | Django sessions; **must change in production** |
| `DEBUG` | ✅ | — | `False` in production |
| `ALLOWED_HOSTS` | ✅ | — | Comma-separated hostnames |
| `CSRF_TRUSTED_ORIGINS` | ✅ prod | — | e.g. `https://app.kovaagent.com` |
| `DATABASE_URL` | ✅ | local Postgres | Database connection |
| `REDIS_URL` | ✅ prod | — | Celery broker, cache, Channels (WebSockets) |

**Redis on Railway:** Use one `REDIS_URL` for Celery, Django cache, and Channels — do not split host/port for WebSockets. If Celery tasks succeed but `/ws/updates/` logs `Timeout reading from redis.railway.internal`, the Redis instance is reachable but **channels_redis** async clients hit the default 5s socket timeout; set `CHANNEL_REDIS_CONNECT_TIMEOUT` and `CHANNEL_REDIS_SOCKET_TIMEOUT` (default `15`) on the web service. Ensure the Redis plugin is not on a sleeping/free tier during production traffic. For TLS URLs (`rediss://`), pass the full URL; Channels config sets `ssl_cert_reqs=None` for managed Redis.
| `FIELD_ENCRYPTION_KEY` | ✅ prod | falls back to `SECRET_KEY` | Fernet key for OAuth token encryption |

### Meta — shared (Facebook + Instagram + WhatsApp Embedded Signup)

| Variable | Required | Purpose |
|----------|----------|---------|
| `FACEBOOK_APP_ID` | ✅ for Meta platforms | Meta App ID (`Settings → Basic`) |
| `FACEBOOK_APP_SECRET` | ✅ for Meta platforms | Meta App Secret |
| `FB_LOGIN_CONFIG_ID` | Optional (recommended) | Facebook Login for Business configuration ID — used for FB/IG OAuth when set |
| `FB_WA_CONFIG_ID` | Optional | WhatsApp Embedded Signup configuration ID — enables one-click WhatsApp connect in UI |

> **Note:** `PLATFORM_DEVELOPER_SETUP.md` references `FACEBOOK_LOGIN_CONFIG_ID`; the codebase uses **`FB_LOGIN_CONFIG_ID`** (see `config/settings/base.py`).

### WhatsApp Cloud API

| Variable | Required | Purpose |
|----------|----------|---------|
| `WHATSAPP_PHONE_NUMBER_ID` | ✅ platform-level | Master phone number ID (also used for daily-brief owner commands) |
| `WHATSAPP_ACCESS_TOKEN` | ✅ platform-level | System User permanent token (global fallback; per-user tokens override) |
| `WHATSAPP_WABA_ID` | ✅ platform-level | WhatsApp Business Account ID |
| `WHATSAPP_VERIFY_TOKEN` | ✅ | Shared secret for webhook GET verification — you choose this value |
| `WHATSAPP_APP_SECRET` | ✅ prod | HMAC webhook signature verification (`X-Hub-Signature-256`); typically same as `FACEBOOK_APP_SECRET` |

### WhatsApp system templates (optional)

| Variable | Required | Purpose |
|----------|----------|---------|
| `KOVA_ONBOARDING_TEMPLATE_NAME` | Optional | Template name for onboarding completion ping |
| `KOVA_ONBOARDING_TEMPLATE_LANG` | Optional | Default `en` |
| `KOVA_DAILY_BRIEF_TEMPLATE_NAME` | Optional | Pro+ daily brief WhatsApp ping |
| `KOVA_DAILY_BRIEF_TEMPLATE_LANG` | Optional | Default `en` |
| `KOVA_DAILY_BRIEF_URL_SUFFIX` | Optional | URL button variable suffix; default `utm_source=whatsapp` |

See [`WHATSAPP_TEMPLATES.md`](./WHATSAPP_TEMPLATES.md) for full template bodies.

### TikTok

| Variable | Required | Purpose |
|----------|----------|---------|
| `TIKTOK_CLIENT_KEY` | ✅ | App Client Key |
| `TIKTOK_CLIENT_SECRET` | ✅ | App Client Secret |
| `TIKTOK_RESEARCH_API_ENABLED` | Optional | Default `False`; Research API comment access is gated separately |

### LinkedIn

| Variable | Required | Purpose |
|----------|----------|---------|
| `LINKEDIN_CLIENT_ID` | ✅ | Developer app Client ID |
| `LINKEDIN_CLIENT_SECRET` | ✅ | Developer app Client Secret |
| `LINKEDIN_API_VERSION` | Optional | Default `202603` in provider (confirm in LinkedIn developer portal) |

### Media storage (production — required for IG/TikTok URL publishing)

| Variable | Required | Purpose |
|----------|----------|---------|
| `AWS_STORAGE_BUCKET_NAME` | ✅ prod | R2 bucket name |
| `AWS_S3_ENDPOINT_URL` | ✅ prod | R2 S3-compatible endpoint |
| `AWS_S3_ACCESS_KEY_ID` | ✅ prod | R2 access key |
| `AWS_S3_SECRET_ACCESS_KEY` | ✅ prod | R2 secret key |
| `AWS_S3_CUSTOM_DOMAIN` | Optional | Public CDN domain for media (verify with TikTok domain verification) |

### Social sign-up (optional — not platform connect)

| Variable | Purpose |
|----------|---------|
| `GOOGLE_OAUTH_CLIENT_ID` / `GOOGLE_OAUTH_CLIENT_SECRET` | Google sign-up button |

---

## 3. Meta (Facebook Developer App) — shared foundation

One Meta app powers Facebook Page publishing, Instagram publishing, WhatsApp Cloud API, and (optionally) Facebook social sign-up.

**Graph API versions in code:**
- Facebook / Instagram: **v25.0** (`instagram_facebook.py`)
- WhatsApp Cloud API: **v21.0** (`whatsapp.py`, Embedded Signup JS SDK)

Confirm current versions in your Meta App Dashboard if Meta has upgraded defaults.

### Step 3.1 — Create or select your Meta app

1. Go to [developers.facebook.com/apps](https://developers.facebook.com/apps)
2. **Create App** → type **Business** (or select your existing Kova app)
3. App name: e.g. `Kova Agent`
4. Link to your **Business Portfolio** at [business.facebook.com](https://business.facebook.com)

### Step 3.2 — Add use cases / products

In the App Dashboard, add these use cases (Meta's 2025+ flow):

| Use case | Enables |
|----------|---------|
| **Authenticate and request data from users with Facebook Login** | OAuth for FB/IG connect |
| **Access the Pages API** | Facebook Page publishing, insights, comments |
| **Access the Instagram API** | IG publishing, insights, comments, DMs |
| **WhatsApp** | Cloud API messaging + Embedded Signup |

### Step 3.3 — App Settings → Basic

1. Copy **App ID** → `FACEBOOK_APP_ID`
2. Copy **App Secret** → `FACEBOOK_APP_SECRET` (also use for `WHATSAPP_APP_SECRET`)
3. **App Domains**: add your domain without protocol, e.g. `app.kovaagent.com`
4. **Privacy Policy URL**: `{SITE_URL}/privacy/` (required for App Review and WhatsApp)
5. **Terms of Service URL**: `{SITE_URL}/terms/` (recommended)
6. **User data deletion** (Meta App Dashboard → Settings → Basic):
   - **Data Deletion Instructions URL**: `{SITE_URL}/legal/facebook-data-deletion/`  
     (alias: `{SITE_URL}/privacy/data-deletion/`)
   - **Data Deletion Callback URL** (optional but recommended): `{SITE_URL}/platforms/facebook/data-deletion/`  
     Meta POSTs `signed_request` here when a user removes the app; Kova clears Facebook/Instagram OAuth data and returns a status URL + `confirmation_code`.

**Production example** (`SITE_URL=https://kovaagents-production.up.railway.app`):

| Meta field | URL |
|------------|-----|
| Data Deletion Instructions URL | `https://kovaagents-production.up.railway.app/legal/facebook-data-deletion/` |
| Data Deletion Callback URL | `https://kovaagents-production.up.railway.app/platforms/facebook/data-deletion/` |

### Step 3.4 — Facebook Login for Business (recommended)

1. App Dashboard → **Facebook Login for Business** → **Create Configuration**
2. Name: `Kova Platform Connect`
3. Add permissions from [Section 11](#11-app-review--permissions) (FB + IG bundle)
4. Save → copy **Configuration ID** → `FB_LOGIN_CONFIG_ID`

When `FB_LOGIN_CONFIG_ID` is set, Kova sends `config_id` instead of `scope` in the OAuth URL (`instagram_facebook.py`). If unset, Kova falls back to classic scope-based login (works for Development mode testers).

**Separate configuration for WhatsApp Embedded Signup:**

1. Create another Login for Business configuration (or WhatsApp-specific config in WhatsApp product settings)
2. Include WhatsApp permissions: `whatsapp_business_management`, `whatsapp_business_messaging`
3. Copy Configuration ID → `FB_WA_CONFIG_ID`

Embedded Signup is only shown in the UI when **all three** are set: `FACEBOOK_APP_ID`, `FACEBOOK_APP_SECRET`, `FB_WA_CONFIG_ID` (`apps/platforms/views.py`).

### Step 3.5 — OAuth redirect URIs

Add **exact** URIs (trailing slash matters). Kova builds callbacks dynamically; register both production and local dev.

| Flow | Redirect URI |
|------|-------------|
| Facebook signup / login / platform connect | `{SITE_URL}/platforms/callback/facebook/` |
| Instagram platform connect | `{SITE_URL}/platforms/callback/instagram/` |
| Legacy django-allauth Facebook (optional) | `{SITE_URL}/accounts/facebook/login/callback/` |

**Production example** (`SITE_URL=https://kovaagents-production.up.railway.app`):

```
https://kovaagents-production.up.railway.app/platforms/callback/facebook/
https://kovaagents-production.up.railway.app/platforms/callback/instagram/
https://kovaagents-production.up.railway.app/accounts/facebook/login/callback/
```

**Local development:**

```
http://localhost:8000/platforms/callback/facebook/
http://localhost:8000/platforms/callback/instagram/
http://localhost:8000/accounts/facebook/login/callback/
```

> **Signup UX:** The signup page **Continue with Facebook** button uses platform OAuth (`/accounts/facebook/signup/` → `/platforms/callback/facebook/`), not the allauth intermediate page. Whitelist `/platforms/callback/facebook/` first — that fixes the Meta **URL Blocked** error on registration.

Configure under **Facebook Login for Business → Settings** (or **Facebook Login → Settings** for legacy).

### Step 3.6 — App roles (before App Review)

Until App Review passes, only users with app roles can authorize:

1. App Dashboard → **App Roles** → add **Admin**, **Developer**, or **Tester**
2. Each person must **accept the invitation** in their Facebook account
3. For Instagram testing: IG account must be **Professional** (Business/Creator) and **linked to a Facebook Page**

### Step 3.7 — Business Verification

Required for higher WhatsApp messaging limits and some advanced features.

1. [business.facebook.com/settings](https://business.facebook.com/settings) → **Security Center**
2. **Start Verification** — legal name, address, phone, website, documents
3. Timeline: typically 1–3 business days (can proceed with dev/test setup while waiting)

**Impact if unverified:**
- WhatsApp: lower conversation tier (e.g. 250 conversations/day cap for unverified businesses — confirm current tier in Meta Business Suite)
- Some permissions may remain in **Standard Access** only until verification completes

### Step 3.8 — Switch app to Live

1. App Dashboard → toggle **App Mode** from **Development** to **Live**
2. Only do this after App Review approves required permissions (or you accept tester-only access)

---

## 4. WhatsApp Cloud API (detailed)

WhatsApp is the most involved integration. Kova supports **two connection paths**:

| Path | Who sets it up | Best for |
|------|---------------|----------|
| **Platform admin** | You (env vars + webhook) | Master number, daily brief commands, platform defaults |
| **Embedded Signup** | Each Kova user (one click) | SaaS — users connect their own WABA |
| **Manual token** | Each Kova user (fallback form) | Users with existing System User tokens |

For user-facing WhatsApp features, see [`WHATSAPP_SETUP_GUIDE.md`](./WHATSAPP_SETUP_GUIDE.md).

### Step 4.1 — Add WhatsApp product to Meta app

1. App Dashboard → **Add Product** → **WhatsApp** → **Set Up**
2. Link your **WhatsApp Business Account (WABA)** to the app
3. Note your **WABA ID** (WhatsApp Manager or API Setup page)

### Step 4.2 — Register a phone number

1. WhatsApp → **API Setup** (or **Getting Started**)
2. **Add phone number** — must not be active on consumer WhatsApp or WhatsApp Business app on the same number
3. Verify via SMS or voice
4. Copy **Phone Number ID** after verification

You should now have:
- **Phone Number ID** (numeric)
- **WABA ID** (numeric)
- **App Secret** (from App Settings → Basic)

### Step 4.3 — System User & permanent access token

WhatsApp Cloud API uses **long-lived System User tokens**, not short OAuth tokens.

1. [business.facebook.com/settings](https://business.facebook.com/settings) → **Users** → **System Users**
2. **Add** → Create System User (e.g. `Kova WhatsApp Bot`) → role **Admin**
3. **Add Assets** → Apps → select your Meta app → **Full Control**
4. **Add Assets** → WhatsApp Accounts → select WABA → **Full Control**
5. **Generate New Token** → select your app → expiration **Never**
6. Permissions (minimum):
   - ✅ `whatsapp_business_messaging`
   - ✅ `whatsapp_business_management`
7. Copy token immediately → `WHATSAPP_ACCESS_TOKEN`

> ⚠️ Token is shown once. Store in your secrets manager / Railway env vars.

### Step 4.4 — Configure Kova environment variables

```bash
WHATSAPP_PHONE_NUMBER_ID=123456789012345
WHATSAPP_ACCESS_TOKEN=EAAxxxxxxxxxxxxxxxx
WHATSAPP_WABA_ID=987654321098765
WHATSAPP_VERIFY_TOKEN=<generate-a-random-string>
WHATSAPP_APP_SECRET=<same-as-FACEBOOK_APP_SECRET>
FB_WA_CONFIG_ID=<embedded-signup-config-id>   # optional but recommended
```

Generate a secure verify token:

```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

| Variable | If missing |
|----------|-----------|
| `WHATSAPP_VERIFY_TOKEN` | Webhook verification fails |
| `WHATSAPP_APP_SECRET` | Dev: signatures skipped with warning; **prod: spoofed webhooks possible** |
| `WHATSAPP_ACCESS_TOKEN` | Platform-level sends fail; users can still connect with per-account tokens |

### Step 4.5 — Webhook URL

**Callback URL (register in Meta):**

```
{SITE_URL}/whatsapp/webhook/
```

Example: `https://app.kovaagent.com/whatsapp/webhook/`

**Configure in Meta:**

1. App Dashboard → **WhatsApp** → **Configuration**
2. Webhook → **Edit**
3. **Callback URL**: `{SITE_URL}/whatsapp/webhook/`
4. **Verify token**: exact value of `WHATSAPP_VERIFY_TOKEN`
5. Click **Verify and Save**

**Subscribe to webhook fields:**

| Field | Subscribe? | Kova usage |
|-------|-----------|------------|
| `messages` | ✅ **Yes** | Inbound messages + delivery/read/failed statuses |

Kova's webhook handler (`apps/whatsapp/webhook.py`) processes `field: "messages"` only. Template status webhooks are not currently handled in code — sync templates via Kova UI **Sync from Meta** (`/whatsapp/templates/sync/`).

**How verification works (GET):**

Meta sends:
```
GET /whatsapp/webhook/?hub.mode=subscribe&hub.verify_token=...&hub.challenge=...
```
Kova compares `hub.verify_token` to `WHATSAPP_VERIFY_TOKEN` and returns `hub.challenge` as plain text.

**How events work (POST):**

Meta signs the body with HMAC-SHA256 using your app secret. Kova verifies `X-Hub-Signature-256` via `WhatsAppProvider.verify_webhook_signature()`.

### Step 4.6 — WhatsApp Embedded Signup (per-user connect)

When `FB_WA_CONFIG_ID` is configured, users see **Connect with WhatsApp** on `/platforms/connect/whatsapp/`:

1. Facebook JS SDK launches Embedded Signup (`config_id: FB_WA_CONFIG_ID`)
2. User authorizes → Kova receives `code` + optional `phone_number_id` / `waba_id` from `WA_EMBEDDED_SIGNUP` session event
3. POST to `{SITE_URL}/platforms/whatsapp/embedded-callback/`
4. Kova exchanges code, subscribes WABA to app, registers phone, stores `SocialAccount`

**Meta Embedded Signup checklist (confirm in your Meta console):**

- [ ] WhatsApp Embedded Signup enabled on the app
- [ ] `FB_WA_CONFIG_ID` matches the Embedded Signup Login configuration
- [ ] OAuth redirect includes your domain (Embedded Signup uses FB Login under the hood)
- [ ] Business owns the WABA being connected

**Fallback — manual connect:** Users paste System User token + Phone Number ID + WABA ID on the same page.

### Step 4.7 — Message templates

Templates are required for messaging **outside the 24-hour customer service window**.

**In Kova UI:**
- `/whatsapp/templates/` — create, AI-generate, submit to Meta
- `/whatsapp/templates/sync/` — pull approval status from Meta

**Platform-level templates** (automated system messages):

See [`WHATSAPP_TEMPLATES.md`](./WHATSAPP_TEMPLATES.md) for bodies and env vars.

**Template rules (Meta):**
- Names: lowercase, underscores only (`order_confirmation`)
- Categories: `UTILITY`, `MARKETING`, `AUTHENTICATION`
- Variables: `{{1}}`, `{{2}}`, … with sample values at submission
- Marketing templates need opt-out language

### Step 4.8 — Display name & business profile

1. WhatsApp Manager → your phone number → **Profile**
2. Set **Display name** (requires Meta approval)
3. Complete business profile (about, address, email, website) — Kova can audit via Magic Fill (`WhatsAppProvider.audit_profile`)

### Step 4.9 — Verify platform setup

```bash
python manage.py check
```

**Webhook test:**
1. Send a WhatsApp message to your business number from a personal phone
2. Check logs for: `WhatsApp webhook verified successfully` (on setup) and inbound message processing
3. Visit `/whatsapp/` — conversation should appear

**Celery (AI auto-reply):**
```bash
celery -A config worker -l info
```

### WhatsApp troubleshooting

| Symptom | Likely cause | Fix |
|---------|-------------|-----|
| Webhook verification failed | Token mismatch or Kova not reachable | Match `WHATSAPP_VERIFY_TOKEN`; ensure HTTPS; trailing slash on URL |
| Invalid signature (403) | Wrong `WHATSAPP_APP_SECRET` | Set to Meta App Secret; redeploy |
| Messages not in inbox | No matching `SocialAccount` | User must connect WhatsApp; webhook matches `metadata.phone_number_id` |
| Embedded Signup unavailable | Missing `FB_WA_CONFIG_ID` | Set all three: app ID, secret, WA config ID |
| Template send fails | Template not approved or wrong WABA | Check status in `/whatsapp/templates/` |
| AI not replying | Celery down or AI toggle off | Start worker; check conversation AI toggle |

Full troubleshooting: [`WHATSAPP_SETUP_GUIDE.md` §18](./WHATSAPP_SETUP_GUIDE.md#18-troubleshooting)

---

## 5. Facebook Pages & Messenger

### What Kova does with Facebook

From `FacebookProvider` (`instagram_facebook.py`):

- Publish text, photo, video, multi-photo, **Reels** to Pages
- Read post metrics and Page insights
- Read and reply to **comments**
- Read and send **Page Messenger** messages (`pages_messaging`)
- Profile audit + selective field updates

### Messenger webhooks (real-time DMs)

Kova registers a **Page webhook** for Messenger DMs at:

```
https://<your-domain>/engage/webhook/messenger/
```

| Setting | Purpose |
|---------|---------|
| `WHATSAPP_VERIFY_TOKEN` | **Reused** for GET webhook verification (same Meta app as WhatsApp) |
| `FACEBOOK_APP_SECRET` | POST signature validation (`X-Hub-Signature-256`); falls back to `WHATSAPP_APP_SECRET` |

In Meta Developer Portal → **Webhooks** → **Page** → subscribe to **`messages`**.

Polling via `run-engage-cycle` (every 30 min) remains as fallback when webhooks are not configured.

### Legacy note (pre–Phase 4)

Page comment fetching still uses polling via the Engage Agent Celery cycle. Only **Messenger DMs** are real-time via webhook.

### Step 5.1 — Permissions

Scopes requested by Kova (classic fallback — your Login for Business config should include equivalent permissions):

```
email, public_profile,
pages_manage_metadata, pages_manage_posts, pages_read_engagement,
pages_manage_engagement, pages_messaging, read_insights
```

| Permission | Purpose |
|------------|---------|
| `pages_manage_metadata` | List user's Pages |
| `pages_manage_posts` | Create/edit Page posts |
| `pages_read_engagement` | Read likes, comments, shares |
| `pages_manage_engagement` | Reply to comments |
| `pages_messaging` | Page Messenger inbox |
| `read_insights` | Page/post analytics |

### Step 5.2 — OAuth redirect

```
{SITE_URL}/platforms/callback/facebook/
```

### Step 5.3 — Page requirements

- User must be **admin** of at least one Facebook **Page** (not personal profile)
- Kova stores all managed Pages in account `metadata.pages`
- Default publish target: first Page (`selected_page_id`); multi-Page switching via support (no self-service picker yet — see `docs/platform-audits/FACEBOOK.md`)

### Step 5.4 — Token lifecycle

- Short-lived token → exchanged to **60-day** long-lived user token on connect
- Page access tokens derived from user token (long-lived while user token valid)
- Celery task `platforms.refresh_expiring_tokens` runs every **30 minutes**

### Facebook troubleshooting

| Symptom | Fix |
|---------|-----|
| "No Pages were found" | User needs Page admin role; grant `pages_manage_metadata` |
| Publish fails with localhost image URL | Media must be public HTTPS (R2); Kova blocks localhost URLs |
| Comments not fetched | App Review for `pages_read_engagement`; token refresh |
| Messenger not working | Requires `pages_messaging` approval; polling delay up to 30 min |

---

## 6. Instagram (via Meta Graph API)

Instagram uses the **same Meta app** and OAuth flow as Facebook.

### Step 6.1 — Prerequisites

1. Instagram account converted to **Professional** (Business or Creator)
2. IG account **linked to a Facebook Page** (Meta Business Suite → Settings → Linked accounts)
3. Same Meta app permissions as Section 5 + IG-specific:

```
instagram_content_publish, instagram_manage_insights,
instagram_manage_comments, instagram_manage_messages
```

> `instagram_basic` is **deprecated** in Graph API v21.0+ — not used by Kova.

### Step 6.2 — OAuth redirect

```
{SITE_URL}/platforms/callback/instagram/
```

Uses same `FB_LOGIN_CONFIG_ID` / scopes as Facebook.

### Step 6.3 — How connect works in Kova

On OAuth callback, Kova:
1. Lists user's Facebook Pages
2. Finds first Page with `instagram_business_account`
3. Stores IG Business ID, Page ID, and Page access token in `SocialAccount.metadata`

If no IG Business account is linked: error — *"No Instagram Business/Creator Account found linked to your Facebook Pages."*

### Step 6.4 — Publishing requirements

- All media URLs must be **public HTTPS** (Instagram rejects HTTP/localhost)
- Reels: MP4/MOV, H.264/AAC recommended, 9:16 aspect ratio
- Carousels: 2–10 images
- Container polling handled automatically (`_wait_for_ig_container`)

### Step 6.5 — Media storage

Production requires R2 (or equivalent) so generated images/videos have public URLs:

```bash
AWS_STORAGE_BUCKET_NAME=your-bucket
AWS_S3_ENDPOINT_URL=https://<accountid>.r2.cloudflarestorage.com
AWS_S3_ACCESS_KEY_ID=...
AWS_S3_SECRET_ACCESS_KEY=...
AWS_S3_CUSTOM_DOMAIN=pub-xxxxx.r2.dev   # optional CDN domain
```

### Instagram troubleshooting

| Symptom | Fix |
|---------|-----|
| Connect succeeds but no IG | Link IG Professional account to a Facebook Page |
| Publish: HTTPS error | Fix R2/public media URL configuration |
| Reel processing ERROR | Check video codec, size (<1GB), duration |
| Insights empty | Request `instagram_manage_insights` in App Review |

---

## 7. TikTok for Business

### Step 7.1 — Create developer account & app

1. [developers.tiktok.com](https://developers.tiktok.com/) → log in
2. **Manage Apps** → **Create App**
3. Name: `Kova Agent`; category: Social Media Management

### Step 7.2 — Add products

| Product | Required | Scopes |
|---------|----------|--------|
| **Login Kit** | ✅ | `user.info.basic` |
| **Content Posting API** | ✅ | `video.publish`, `video.list` |

**Critical:** Enable **Direct Post** in Content Posting API settings. Without it, content goes to the user's TikTok inbox instead of publishing directly.

Kova requests (hardcoded in `tiktok.py`):
```
user.info.basic,video.publish,video.list
```

### Step 7.3 — OAuth redirect URI

```
{SITE_URL}/platforms/tiktok/callback/
```

Local: `http://localhost:8000/platforms/tiktok/callback/`

Copy **Client Key** → `TIKTOK_CLIENT_KEY`, **Client Secret** → `TIKTOK_CLIENT_SECRET`.

### Step 7.4 — Domain verification (PULL_FROM_URL)

Kova publishes via **PULL_FROM_URL** — TikTok downloads media from your public URL.

1. App → Content Posting API → **Domain Verification**
2. Add your R2 public domain (`AWS_S3_CUSTOM_DOMAIN`) or confirm exact domain in TikTok console
3. Verify via DNS TXT, HTML file, or meta tag

### Step 7.5 — App audit (required for public posts)

**Unaudited apps post as `SELF_ONLY` (private)** — Kova defaults to `SELF_ONLY` privacy when unaudited (`tiktok.py`).

1. App → **Submit for Audit**
2. Provide demo URL (`{SITE_URL}`), screencast of connect + publish flow, privacy policy
3. Submit at [developers.tiktok.com/application/content-posting-api](https://developers.tiktok.com/application/content-posting-api)
4. After approval: posts can use `PUBLIC_TO_EVERYONE`

### Step 7.6 — Content limits

| Type | Supported | Notes |
|------|-----------|-------|
| Video (URL) | ✅ | `.mp4`, `.mov`, `.webm` |
| Video (upload) | ✅ | `FILE_UPLOAD` chunked — provider supports bytes upload |
| Photo carousel | ✅ | Up to 35 images via PULL_FROM_URL |
| Text only | ❌ | Media required |
| Comments read | ⚠️ | Research API only (`research.data.basic`) — gated; default off |
| Comment reply | ❌ | No public TikTok API |

Optional flag: `TIKTOK_RESEARCH_API_ENABLED=True` — still requires TikTok Research API approval.

### TikTok troubleshooting

| Symptom | Fix |
|---------|-----|
| Posts private only | Complete TikTok app audit |
| PULL_FROM_URL fails | Verify media domain in TikTok console |
| Redirect URI mismatch | Exact match including trailing slash |
| Content in inbox not feed | Enable **Direct Post** |
| `scope_not_authorized` | Add Content Posting API product + scopes |

---

## 8. LinkedIn Marketing / Community Management API

Kova uses the **REST Posts API** (not deprecated UGC API). API version header: `LinkedIn-Version: 202603` (override via `LINKEDIN_API_VERSION` if needed — confirm in LinkedIn developer portal).

### Step 8.1 — Create LinkedIn Company Page (recommended)

1. [linkedin.com/company/setup/new/](https://www.linkedin.com/company/setup/new/)
2. Complete company page — required to associate developer app

### Step 8.2 — Create developer app

1. [linkedin.com/developers/apps/new](https://www.linkedin.com/developers/apps/new)
2. App name: `Kova Agent`
3. Link to your Company Page
4. Accept legal agreement

### Step 8.3 — Request API products

| Product | Grants | Approval |
|---------|--------|----------|
| **Sign In with LinkedIn using OpenID Connect** | `openid`, `profile`, `email` | Usually automatic |
| **Share on LinkedIn** | `w_member_social` | Usually automatic |
| **Advertising API** (for org posting) | `w_organization_social`, `r_organization_social` | Application required |

For **Company Page posting**, request **Advertising API** and explain: *"Social media management tool that publishes branded content and reads engagement analytics for Company Pages on behalf of authorized admins."*

### Step 8.4 — OAuth redirect URLs

```
{SITE_URL}/platforms/linkedin/callback/
```

Local: `http://localhost:8000/platforms/linkedin/callback/`

### Step 8.5 — Scopes

**Personal posting** (default connect):
```
openid profile w_member_social
```

**Organization posting** (Company Page connect flow):
```
openid profile w_member_social w_organization_social r_organization_social
```

Org flow: user connects personal LinkedIn first, then **Connect Company Page** → `{SITE_URL}/platforms/linkedin/connect-page/` → select page at `/platforms/linkedin/select-page/`.

### Step 8.6 — Company Page admin role

Authenticated user must have one of:
- ADMINISTRATOR
- DIRECT_SPONSORED_CONTENT_POSTER
- CONTENT_ADMIN

on the target Company Page.

### Step 8.7 — Content types

| Type | Supported |
|------|-----------|
| Text | ✅ |
| Single image | ✅ |
| Multi-image (up to 9) | ✅ |
| Video | ✅ |
| Article/link | ✅ |
| Organic carousel | ❌ (sponsored only) |

Comment reading via `socialActions` may return **403** without LinkedIn Partner Program access — Kova degrades gracefully (`linkedin.py`).

### LinkedIn troubleshooting

| Symptom | Fix |
|---------|-----|
| Org scopes denied | Request Advertising API product |
| No Company Pages listed | User must be Page admin |
| Comments 403 | Partner-only API — expected without partner access |
| Token looks encrypted in logs | User should reconnect if `FIELD_ENCRYPTION_KEY` rotated |
| Publish fails >3000 chars | LinkedIn commentary limit |

---

## 9. Connecting accounts inside Kova UI

### User flow (all platforms)

1. Log in to Kova
2. Navigate to **Platforms** → `/platforms/`
3. Click **Connect** on the desired platform card
4. Complete OAuth (or WhatsApp Embedded Signup / manual form)
5. Account appears in connected list with capabilities

**Active platforms in UI** (`ACTIVE_PLATFORMS` in `views.py`): Facebook, Instagram, TikTok, LinkedIn, WhatsApp, Pinterest, Bluesky.

Twitter, YouTube, Threads show as **Coming soon** (providers exist; OAuth apps pending).

### Platform-specific connect paths

| Platform | Connect URL | Callback / endpoint |
|----------|------------|---------------------|
| Facebook | `/platforms/connect/facebook/` | `/platforms/callback/facebook/` |
| Instagram | `/platforms/connect/instagram/` | `/platforms/callback/instagram/` |
| TikTok | `/platforms/connect/tiktok/` | `/platforms/tiktok/callback/` |
| LinkedIn (personal) | `/platforms/connect/linkedin/` | `/platforms/linkedin/callback/` |
| LinkedIn (Company Page) | `/platforms/linkedin/connect-page/` | → callback → `/platforms/linkedin/select-page/` |
| WhatsApp (Embedded) | `/platforms/connect/whatsapp/` | `/platforms/whatsapp/embedded-callback/` |
| WhatsApp (manual) | `/platforms/connect/whatsapp/` (POST form) | — |
| Disconnect | POST `/platforms/disconnect/<uuid>/` | Soft-deactivate; preserves post history |

### Onboarding integration

If user has not completed onboarding, successful connect redirects to `/accounts/onboarding/?step=2`.

### Token refresh

Celery beat schedules:
- `platforms.refresh_expiring_tokens` — every 30 minutes
- `platforms.warn_expiring_tokens` — daily warnings at 7-day and 1-day expiry

Users can **reconnect** from Platforms if refresh fails.

---

## 10. Webhook verification checklist

### WhatsApp (implemented)

| Check | Endpoint | Method |
|-------|----------|--------|
| ✅ Verification challenge | `{SITE_URL}/whatsapp/webhook/` | GET |
| ✅ Signed events | `{SITE_URL}/whatsapp/webhook/` | POST |
| Subscribe field | `messages` | |
| Verify token env | `WHATSAPP_VERIFY_TOKEN` | |
| Signature secret | `WHATSAPP_APP_SECRET` | |

**Test GET manually:**
```
curl "{SITE_URL}/whatsapp/webhook/?hub.mode=subscribe&hub.verify_token=YOUR_TOKEN&hub.challenge=test123"
```
Expected: plain text response `test123`

### Facebook / Instagram Pages

| Check | Status in Kova |
|-------|---------------|
| Page feed webhooks | ❌ Not implemented — polling via Engage Agent |
| Messenger webhooks | ❌ Not implemented — polling via Engage Agent |

No Meta Page webhook URL to register in Kova today.

### TikTok / LinkedIn

No inbound webhooks — OAuth + REST API only.

---

## 11. App Review & permissions

### Meta — permissions matrix

| Permission | Platform | Standard vs Advanced | Kova feature |
|------------|----------|---------------------|--------------|
| `email`, `public_profile` | Login | Standard | Account identity |
| `pages_manage_metadata` | FB | Advanced | List Pages |
| `pages_manage_posts` | FB | Advanced | Publish posts, **Page Stories** |
| `pages_read_engagement` | FB | Advanced | Metrics, read comments |
| `pages_manage_engagement` | FB | Advanced | Reply to comments |
| `pages_messaging` | FB | Advanced | Messenger inbox |
| `read_insights` | FB | Advanced | Page insights |
| `instagram_content_publish` | IG | Advanced | Publish posts, Reels, **Stories** |
| `instagram_manage_insights` | IG | Advanced | IG analytics |
| `instagram_manage_comments` | IG | Advanced | Comment replies |
| `instagram_manage_messages` | IG | Advanced | IG DMs |
| `whatsapp_business_messaging` | WA | Advanced | Send/receive messages |
| `whatsapp_business_management` | WA | Advanced | Templates, phone management |

### Meta App Review — common questions & suggested answers

Prepare these before submitting. Adjust wording to match your actual UI.

| Meta question | Suggested answer |
|---------------|-----------------|
| **How will your app use `pages_manage_posts`?** | Authorized users connect their Facebook Page via OAuth. Kova publishes organic content (text, images, videos, Reels, **Page Stories**) they create or approve in our content studio. We do not post without user action or explicit autopilot approval settings. |
| **How will your app use `pages_read_engagement`?** | We fetch post-level metrics (reach, impressions, likes, comments) to show performance dashboards and train our Adapt content agent on what resonates with their audience. |
| **How will your app use `pages_manage_engagement`?** | Our Engage Agent drafts replies to Page comments; users review or enable graduated auto-reply. We reply as the Page, not as the user personally. |
| **How will your app use `pages_messaging`?** | We read Page Messenger conversations to display an unified inbox and send replies the business approves — for customer sales and support queries. |
| **How will your app use `instagram_content_publish`?** | Users connect their Instagram Professional account linked to their Page. Kova publishes images, carousels, Reels, and **Stories** they create or schedule in Kova. |
| **How will your app use `instagram_manage_comments`?** | We fetch comments on the user's posts and allow reply from Kova's Engage inbox — with optional AI-drafted responses under user control. |
| **How will your app use `instagram_manage_messages`?** | We display Instagram Direct messages in the unified Engage inbox and send replies authorized by the business. |
| **How will your app use WhatsApp permissions?** | Businesses connect their WhatsApp Business Account. Kova provides customer inbox, AI-assisted replies within the 24-hour window, approved template broadcasts, and order/booking notifications they configure. |
| **Do you store user data?** | Yes — encrypted OAuth tokens and message content necessary to provide the service. Privacy policy at `{SITE_URL}/privacy/`. |
| **Provide a screencast** | Record: login → Platforms → Connect Facebook → create post → publish → Engage comment reply. Separate clip for WhatsApp inbox if requesting WhatsApp permissions. |
| **Data deletion** | Instructions: `{SITE_URL}/legal/facebook-data-deletion/`. Automated callback: `{SITE_URL}/platforms/facebook/data-deletion/`. Users can also disconnect in Platforms or email support@kovaagent.com for full account deletion (privacy policy). |

**Business Verification** (separate from App Review): required for full WhatsApp tier — see Section 3.7.

### TikTok App Review

| Question | Answer |
|----------|--------|
| What does your app do? | Social media management for SMBs — users authorize TikTok to publish videos/photos they create in Kova. |
| How is content moderated? | Users preview and approve content before publish; we support TikTok's `is_aigc` labeling for AI-generated media. |
| Privacy policy URL | `{SITE_URL}/privacy/` |

### LinkedIn product access

| Product | Application text |
|---------|-----------------|
| Share on LinkedIn | Auto-approved for member posting |
| Advertising API | "OAuth-based social management tool; authorized Company Page admins publish organic posts and view engagement metrics. We do not run paid ad campaigns through this integration." |

---

## 12. Security (tokens, secrets, rotation)

### Token storage

- OAuth tokens stored in `SocialAccount` model, **Fernet-encrypted** (`apps/platforms/encryption.py`)
- Encryption key: `FIELD_ENCRYPTION_KEY` (production mandatory)
- WhatsApp per-user tokens stored same way after Embedded Signup or manual connect

### Secret handling

| Secret | Storage | Rotation |
|--------|---------|----------|
| `FACEBOOK_APP_SECRET` / `WHATSAPP_APP_SECRET` | Env vars only | Meta → Settings → Basic → Reset; update env; redeploy |
| `WHATSAPP_ACCESS_TOKEN` | Env + DB per account | Regenerate System User token in Business Suite |
| `WHATSAPP_VERIFY_TOKEN` | Env | Change env + Meta webhook config together |
| `TIKTOK_CLIENT_SECRET` | Env | TikTok developer portal → reset |
| `LINKEDIN_CLIENT_SECRET` | Env | LinkedIn app → Auth → regenerate |

**Never commit secrets to git.** `.env` is gitignored; use Railway/host env vars.

### App secret rotation procedure (Meta)

1. Generate new App Secret in Meta App Dashboard
2. Update `FACEBOOK_APP_SECRET` and `WHATSAPP_APP_SECRET` in deployment
3. Redeploy Kova
4. Webhook signature verification uses new secret immediately
5. Existing user tokens remain valid (no user action needed)

### FIELD_ENCRYPTION_KEY rotation

Rotating `FIELD_ENCRYPTION_KEY` **without** a migration path will make existing stored tokens unreadable. Users must **reconnect** affected platforms. Plan rotation during maintenance window.

### Production hardening (automatic)

`config/settings/production.py` enforces:
- `SECRET_KEY` not default
- `FIELD_ENCRYPTION_KEY` set
- `RESEND_API_KEY` set
- HTTPS (`SECURE_SSL_REDIRECT`, secure cookies)
- Token redaction in logs

---

## 13. FAQ per platform

### WhatsApp

**Q: One WABA for all Kova users or per customer?**  
A: SaaS model — each customer connects their own WABA via Embedded Signup or manual token. Platform env vars (`WHATSAPP_*`) are for the **master** number (daily brief owner commands, optional global fallback).

**Q: Can I use the same phone number in env and per-user connect?**  
A: The webhook routes master number (`WHATSAPP_PHONE_NUMBER_ID`) to brief commands; other numbers match `SocialAccount.metadata.phone_number_id`.

**Q: What Graph API version for WhatsApp?**  
A: v21.0 in code (`whatsapp.py`). Embedded Signup JS also uses v21.0.

**Q: Do I need a separate Meta app for WhatsApp?**  
A: No — add WhatsApp product to the same Business app.

### Facebook

**Q: Can users connect personal profiles?**  
A: Kova publishes to **Pages** only. Personal profile timelines are not supported.

**Q: Real-time comment notifications?**  
A: No — Engage Agent polls every ~30 minutes.

### Instagram

**Q: Why does Instagram use Facebook OAuth?**  
A: Instagram Graph API requires a Page-linked Professional account; Meta issues Page-scoped tokens.

**Q: Can I post text-only to Instagram?**  
A: No — Kova requires media (image, carousel, reel, or story). See [STORIES_PUBLISHING.md](./STORIES_PUBLISHING.md) for Story-specific setup.

### TikTok

**Q: Why are my posts private?**  
A: App not audited — complete TikTok Content Posting API audit.

**Q: Can Kova reply to TikTok comments?**  
A: No public write API. Research API read is optional and gated.

### LinkedIn

**Q: Personal vs Company Page posting?**  
A: Personal uses default connect. Company Page requires org OAuth flow + Page admin role.

**Q: Why can't Kova read comments?**  
A: `socialActions` may require LinkedIn Partner Program — 403 is handled gracefully.

---

## 14. Appendix: Kova URL endpoints

Replace `{SITE_URL}` with your deployment URL.

### OAuth & platform connect

| Path | Name | Method |
|------|------|--------|
| `/platforms/` | Platform list | GET |
| `/platforms/connect/<platform>/` | Start OAuth / WhatsApp connect | GET/POST |
| `/platforms/callback/facebook/` | Facebook OAuth callback (signup, login, connect) | GET |
| `/platforms/callback/instagram/` | Instagram OAuth callback | GET |
| `/platforms/tiktok/callback/` | TikTok OAuth callback | GET |
| `/platforms/linkedin/callback/` | LinkedIn OAuth callback | GET |
| `/platforms/whatsapp/embedded-callback/` | WhatsApp Embedded Signup | POST |
| `/platforms/linkedin/connect-page/` | LinkedIn org OAuth start | GET |
| `/platforms/linkedin/select-page/` | Select Company Page | GET/POST |
| `/platforms/disconnect/<uuid>/` | Disconnect account | POST |

Valid `<platform>` values for connect: `facebook`, `instagram`, `tiktok`, `linkedin`, `whatsapp`, `pinterest`, `bluesky`.

### WhatsApp

| Path | Purpose |
|------|---------|
| `{SITE_URL}/whatsapp/webhook/` | Meta webhook (GET verify + POST events) |
| `/whatsapp/` | Customer inbox |
| `/whatsapp/templates/` | Template management |
| `/whatsapp/broadcasts/` | Broadcast campaigns |
| `/dashboard/whatsapp/` | Admin WhatsApp overview |

### Social sign-up

| Path | Purpose |
|------|---------|
| `/accounts/facebook/signup/` | Facebook signup — starts platform OAuth (full page + IG scopes) |
| `/accounts/facebook/login/` | Facebook login — same OAuth flow for returning users |
| `/platforms/callback/facebook/` | Facebook OAuth callback (signup, login, and platform connect) |
| `/accounts/facebook/login/callback/` | Legacy allauth Facebook (optional) |
| `/accounts/google/login/callback/` | allauth Google sign-up |

### Legal (required by Meta/TikTok/LinkedIn review)

| Path | Purpose |
|------|---------|
| `{SITE_URL}/privacy/` | Privacy policy |
| `{SITE_URL}/terms/` | Terms of service |
| `{SITE_URL}/legal/facebook-data-deletion/` | Meta **Data Deletion Instructions URL** |
| `{SITE_URL}/privacy/data-deletion/` | Redirect to instructions (short alias) |
| `{SITE_URL}/legal/facebook-data-deletion/status/<code>/` | Deletion status page (from callback) |
| `{SITE_URL}/platforms/facebook/data-deletion/` | Meta **Data Deletion Callback URL** (POST `signed_request`) |

### Health

| Path | Purpose |
|------|---------|
| `{SITE_URL}/health/` | Deployment health check |

---

## 15. Production vs development checklists

### Development checklist

- [ ] `.env` copied from `.env.example` with local values
- [ ] `SITE_URL=http://localhost:8000`
- [ ] `DEBUG=True`
- [ ] Postgres + Redis running locally
- [ ] Meta app in **Development** mode; test users added as app roles
- [ ] OAuth redirect URIs include `http://localhost:8000/platforms/*/callback/`
- [ ] WhatsApp webhook: use ngrok or similar tunnel for HTTPS testing, **or** test sends only (webhook optional locally)
- [ ] `WHATSAPP_APP_SECRET` unset skips signature check (logged warning — dev only)
- [ ] Celery worker running for WhatsApp AI tests

### Production checklist

- [ ] `DJANGO_SETTINGS_MODULE=config.settings.production`
- [ ] `SECRET_KEY` — strong random value
- [ ] `FIELD_ENCRYPTION_KEY` — generated via Fernet, separate from SECRET_KEY
- [ ] `SITE_URL=https://your-domain.com` (matches public URL)
- [ ] `ALLOWED_HOSTS` + `CSRF_TRUSTED_ORIGINS` include production domain
- [ ] `RESEND_API_KEY` set (email verification mandatory)
- [ ] `SENTRY_DSN` set (recommended)
- [ ] R2 media storage configured (`AWS_*` vars)
- [ ] Meta app **Live** + App Review permissions approved
- [ ] Meta **Business Verification** complete (WhatsApp tiers)
- [ ] WhatsApp webhook verified; `messages` field subscribed
- [ ] `WHATSAPP_APP_SECRET` set (signature verification active)
- [ ] `FB_LOGIN_CONFIG_ID` set (recommended for FB/IG OAuth)
- [ ] `FB_WA_CONFIG_ID` set (Embedded Signup for users)
- [ ] TikTok app audited (public posting)
- [ ] TikTok media domain verified
- [ ] LinkedIn Advertising API approved (if Company Page posting needed)
- [ ] Celery worker + beat running (django-celery-beat tables via release migrate)
- [ ] Railway `releaseCommand` = `bash scripts/release.sh` (`migrate --noinput` before traffic)
- [ ] Redis connected (`REDIS_URL` on web + worker)
- [ ] Privacy policy live at `{SITE_URL}/privacy/`
- [ ] Meta data deletion URLs set (instructions + callback — Section 3.3)
- [ ] System WhatsApp templates approved (see `WHATSAPP_TEMPLATES.md`)
- [ ] Test end-to-end: connect → publish → engage reply for each platform

---

*Document verified against Kova codebase May 2026. When Meta/TikTok/LinkedIn console labels differ from this doc, treat the developer console as source of truth and update this file.*
