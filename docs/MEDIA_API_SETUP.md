# Media API Setup Guide

Complete reference for configuring **media orchestration**, **Photoroom**, **Fal.ai**, **Bannerbear**, **AI image providers**, and **cloud storage** in Kova.

**Related docs:**
- [VISUAL_PIPELINE_SETUP.md](VISUAL_PIPELINE_SETUP.md) — R2 storage, media-required platforms, visual strategy
- [VISUAL_ENHANCEMENT_SPEC.md](VISUAL_ENHANCEMENT_SPEC.md) — Photoroom Plus variant catalog
- [KOVA_PHOTOROOM_STRATEGY.md](KOVA_PHOTOROOM_STRATEGY.md) — Basic vs Plus routing, cost strategy
- [ONBOARDING_EXPERIENCE.md](ONBOARDING_EXPERIENCE.md) — User onboarding (separate from API setup)

---

## Table of contents

1. [Architecture overview](#1-architecture-overview)
2. [Quick start (minimum viable)](#2-quick-start-minimum-viable)
3. [Environment variables master list](#3-environment-variables-master-list)
4. [Photoroom](#4-photoroom)
5. [Media orchestration (apps/media)](#5-media-orchestration-appsmedia)
6. [Fal.ai (Kling + Flux)](#6-falai-kling--flux)
7. [Bannerbear (branded carousels)](#7-bannerbear-branded-carousels)
8. [AI image generation (FLUX)](#8-ai-image-generation-flux)
9. [Cloudflare R2 storage](#9-cloudflare-r2-storage)
10. [Plan tiers & feature gates](#10-plan-tiers--feature-gates)
11. [In-app URLs & admin links](#11-in-app-urls--admin-links)
12. [Verification & smoke tests](#12-verification--smoke-tests)
13. [Production vs development matrix](#13-production-vs-development-matrix)
14. [Troubleshooting](#14-troubleshooting)

---

## 1. Architecture overview

```
User uploads photo (Snap / Batch)
        │
        ▼
┌───────────────────────────────────────────────────────────┐
│  apps/media/orchestrator.py — MediaPlan per product       │
│  • enhancement: photoroom | flux_edit | none              │
│  • reel_backend: kling | photoroom | ffmpeg               │
│  • carousel_backend: bannerbear | local                   │
└───────────────────────────────────────────────────────────┘
        │
        ├── Photoroom Plus  → v2/edit (cutout, AI scenes, PhotoFix)
        ├── Photoroom Basic → v1/segment (white-bg cutouts only)
        ├── Photoroom Video → v1/animate (reels, optional)
        ├── Fal.ai          → Kling image-to-video, Flux edit
        ├── Bannerbear      → Branded carousel slides
        ├── Together/HF/Pollinations → AI post images (Create Agent)
        └── FFmpeg (local)  → Reel fallback (no API key)
```

**Brand DNA** (`apps/media/brand_dna.py`) feeds all pipelines: colors from Settings → Profile & Brand, visual style, industry, business model.

**Master switch:** `MEDIA_ORCHESTRATION_ENABLED` — when `False`, Fal/Bannerbear routing is disabled (Photoroom Snap polish still runs if `PHOTOROOM_API_KEY` is set).

---

## 2. Quick start (minimum viable)

### Local development (Snap polish works)

Add to `kova_agent/.env`:

```bash
# Required for Studio polish / Snap scenes
PHOTOROOM_API_KEY=your_key_here
PHOTOROOM_SANDBOX=True          # Free watermarked test calls
VISUAL_ENHANCE_ENABLED=True

# Orchestration on (default) — Fal/Bannerbear optional
MEDIA_ORCHESTRATION_ENABLED=True
```

Run smoke test:

```bash
cd kova_agent
python scripts/test_photoroom_sandbox.py
```

### Production (recommended stack)

| Priority | Service | Why |
|----------|---------|-----|
| **P0** | Cloudflare R2 | Railway disk is ephemeral — images vanish on redeploy |
| **P0** | Photoroom Plus API key | Core commerce visual pipeline |
| **P1** | Together.ai or HF token | AI images for social posts |
| **P2** | Bannerbear | Branded product carousels (Growth+) |
| **P2** | Fal.ai | Kling reels + Flux edits (Pro+) |

---

## 3. Environment variables master list

All variables live in `config/settings/base.py`. Copy from `.env.example`.

### Master switches

| Variable | Default | Purpose |
|----------|---------|---------|
| `MEDIA_ORCHESTRATION_ENABLED` | `True` | Enables Fal + Bannerbear routing in `apps/media` |
| `VISUAL_ENHANCE_ENABLED` | `True` | Enables Photoroom Studio polish globally |
| `AI_IMAGE_GENERATION_ENABLED` | `True` | Enables FLUX post images in Create Agent |
| `PHOTO_VARIATIONS_ENABLED` | `True` | Local + Photoroom photo expansion in Snap |

### Photoroom — credentials

| Variable | Required | Purpose |
|----------|----------|---------|
| `PHOTOROOM_API_KEY` | **Yes** (for polish) | Plus plan key — `x-api-key` header |
| `PHOTOROOM_BASIC_API_KEY` | No | Basic plan key for cutout-only routing (cheaper) |
| `PHOTOROOM_SANDBOX` | No | `True` → prepends `sandbox_` to key (free test calls) |

### Photoroom — pool & cost tracking

| Variable | Default | Purpose |
|----------|---------|---------|
| `PHOTOROOM_MONTHLY_POOL` | `5000` | Platform-wide monthly Plus call budget |
| `PHOTOROOM_POOL_RESERVE` | `500` | Reserved headroom before blocking users |
| `PHOTOROOM_MONTHLY_COST_USD` | `500.0` | Cost ceiling for admin dashboards |

### Photoroom — output defaults

| Variable | Default | Purpose |
|----------|---------|---------|
| `PHOTOROOM_OUTPUT_SIZE` | `1080x1080` | Square product output |
| `PHOTOROOM_STORY_SIZE` | `1080x1920` | Story format |
| `PHOTOROOM_BANNER_SIZE` | `1920x1080` | Wide banner |
| `PHOTOROOM_MARKETPLACE_SIZE` | `1000x1000` | Google Shopping export |
| `PHOTOROOM_PADDING` | `0.06` | Subject padding in frame |
| `PHOTOROOM_MARKETPLACE_PADDING` | `0.075` | Marketplace white-bg padding |
| `PHOTOROOM_DEFAULT_SHADOW` | `ai.preset-soft` | Default shadow mode |
| `PHOTOROOM_SCALING` | `fill` | `fit` or `fill` |
| `PHOTOROOM_SMART_CROP_PADDING` | `10%` | Smart crop padding |
| `PHOTOROOM_RELIGHT_PRODUCT_MODE` | `ai.preserve-hue-and-saturation` | Color-safe relight for products |

### Photoroom — feature flags

| Variable | Default | Purpose |
|----------|---------|---------|
| `PHOTOROOM_PHOTOFIX_ENABLED` | `True` | Auto-repair bad phone photos on upload |
| `PHOTOROOM_PHOTOFIX_ALWAYS` | `False` | Run PhotoFix on every upload |
| `PHOTOROOM_COMPOSITION_ENABLED` | `True` | Multi-product composition hero (batch) |
| `PHOTOROOM_PREFLIGHT_ENABLED` | `True` | Pre-upload quality checks |
| `PHOTOROOM_PREFLIGHT_MAX_REPAIRS` | `2` | Max repair attempts |
| `PHOTOROOM_CHANNEL_EXPORTS_ENABLED` | `True` | Channel-specific export sizes |
| `PHOTOROOM_MARKETPLACE_EXPORT_ENABLED` | `True` | Google Shopping PNG/JPEG |
| `PHOTOROOM_MARKET_DAY_ENABLED` | `True` | Batch Snap “market day” preset |
| `PHOTOROOM_CREATIVE_SCENES_ENABLED` | `True` | Grounded AI lifestyle scenes |
| `PHOTOROOM_BRAND_TEMPLATE_ENABLED` | `True` | User brand kit in scenes |
| `PHOTOROOM_EDIT_WITH_AI_ENABLED` | `True` | Edit With AI staging |
| `PHOTOROOM_EDIT_WITH_AI_MAX_PER_PACK` | `2` | Cap per Snap pack |
| `PHOTOROOM_SLIDE_ROLES_ENABLED` | `True` | Role-based reel slides |
| `PHOTOROOM_VARIANT_LAYOUTS_ENABLED` | `True` | Layout variants |
| `PHOTOROOM_BASIC_ROUTING_ENABLED` | `True` | Route white-bg cutouts to Basic API |
| `PHOTOROOM_REVIEW_ALTERATIONS` | `True` | Apparel review gate |
| `PHOTOROOM_AI_SHADOWS_MODEL_ENABLED` | `True` | New shadow model header |
| `PHOTOROOM_VIRTUAL_MODEL_ENABLED` | `False` | Virtual model (fashion) — off by default |
| `PHOTOROOM_VIDEO_ENABLED` | `False` | Live video API (costly) |
| `PHOTOROOM_REEL_USE_VIDEO_API` | `True` | Try Photoroom animate in sandbox reels |
| `PHOTOROOM_UNCERTAINTY_PROBE_ENABLED` | `True` | Read `x-uncertainty-score` header |
| `PHOTOROOM_UNCERTAINTY_HIGH_THRESHOLD` | `0.6` | Skip fragile variants above this score |
| `PHOTOROOM_SANDBOX_DAILY_LIMIT` | `100` | Sandbox daily cap |
| `PHOTOROOM_SANDBOX_MONTHLY_LIMIT` | `1000` | Sandbox monthly cap |
| `PHOTOROOM_MIN_SCENE_VARIANTS` | `3` | Minimum scenes per Snap |
| `PHOTOROOM_MIN_AI_SCENES` | `2` | Minimum AI backgrounds |
| `PHOTOROOM_MAX_AI_SCENES` | `3` | Maximum AI backgrounds |
| `PHOTOROOM_EXPAND_MAX_WORKERS` | `2` | Parallel Plus API workers |
| `PHOTOROOM_DEFAULT_BLUR_MODE` | `bokeh` | `bokeh` or `gaussian` |
| `PHOTOROOM_DEFAULT_BLUR_RADIUS` | `0.01` | Blur strength |

### Fal.ai

| Variable | Default | Purpose |
|----------|---------|---------|
| `FAL_API_KEY` | — | **Preferred** API key |
| `FAL_KEY` | — | Legacy alias (either works) |
| `FAL_KLING_MODEL` | `fal-ai/kling-video/v2.1/master/image-to-video` | Reel video model |
| `FAL_FLUX_EDIT_MODEL` | `fal-ai/flux-pro/kontext` | Creative image edit |

### Bannerbear

| Variable | Purpose |
|----------|---------|
| `BANNERBEAR_API_KEY` | API bearer token |
| `BANNERBEAR_TEMPLATE_COVER` | Template UID — carousel cover slide |
| `BANNERBEAR_TEMPLATE_SLIDE` | Template UID — feature slides |
| `BANNERBEAR_TEMPLATE_CTA` | Template UID — CTA slide |

### AI image providers (Create Agent — not Snap)

| Variable | Purpose |
|----------|---------|
| `TOGETHER_API_KEY` | [Together.ai](https://api.together.xyz) — FLUX.1-schnell ~$0.003/image |
| `TOGETHER_IMAGE_MODEL` | Default `black-forest-labs/FLUX.1-schnell` |
| `HF_TOKEN` | [HuggingFace](https://huggingface.co/settings/tokens) — free tier |
| `POLLINATIONS_API_KEY` | [Pollinations.ai](https://pollinations.ai) — free tier |
| `AI_IMAGE_MODEL` | Pollinations model: `flux`, `gptimage`, `zimage` |

### Reel director

| Variable | Default | Purpose |
|----------|---------|---------|
| `REEL_DIRECTOR_ENABLED` | `True` | Recipe-based reel composition |
| `REEL_MAX_SLIDES` | `5` | Max slides per reel |

### Cloud storage (production)

| Variable | Purpose |
|----------|---------|
| `AWS_STORAGE_BUCKET_NAME` | R2 bucket name |
| `AWS_S3_ENDPOINT_URL` | `https://<ACCOUNT_ID>.r2.cloudflarestorage.com` |
| `AWS_S3_ACCESS_KEY_ID` | R2 access key |
| `AWS_S3_SECRET_ACCESS_KEY` | R2 secret |
| `AWS_S3_CUSTOM_DOMAIN` | Optional public CDN domain |

---

## 4. Photoroom

### Official documentation

| API | Endpoint | Docs |
|-----|----------|------|
| **Plus** (v2/edit) | `https://image-api.photoroom.com/v2/edit` | [Image Editing API Plus](https://docs.photoroom.com/image-editing-api-plus-plan/) |
| **Basic** (segment) | `https://sdk.photoroom.com/v1/segment` | [Remove Background Basic](https://docs.photoroom.com/remove-background-api-basic-plan/) |
| **Video** (animate) | `https://image-api.photoroom.com/v1/animate` | [Video API](https://docs.photoroom.com/video-api-enterprise-plan/overview) |

### How to get API keys

1. Sign up at [Photoroom](https://www.photoroom.com/api)
2. Subscribe to **Image Editing API Plus** (required for Snap studio scenes)
3. Optional: subscribe to **Basic** plan for cheaper white-bg cutouts → `PHOTOROOM_BASIC_API_KEY`
4. Copy API key → `PHOTOROOM_API_KEY` in `.env` or Railway variables

### Sandbox mode (development)

```bash
PHOTOROOM_SANDBOX=True
```

Kova automatically prefixes your key with `sandbox_` when calling the API. Sandbox calls are free but watermarked. Limits enforced via `PHOTOROOM_SANDBOX_DAILY_LIMIT` / `MONTHLY_LIMIT`.

### Authentication

All Photoroom calls use:

```
Header: x-api-key: <your_key>
```

Plus requests: multipart `imageFile` + query/body params (see `apps/products/photoroom_plus.py`).

### Code map

| Module | Role |
|--------|------|
| `apps/products/photoroom.py` | Plus enable check, API key headers, studio polish save |
| `apps/products/photoroom_plus.py` | Full variant catalog, v2/edit calls |
| `apps/products/photoroom_basic.py` | Basic v1/segment routing |
| `apps/products/photoroom_api.py` | Uncertainty score, sandbox quotas |
| `apps/products/photoroom_video.py` | v1/animate for reels |
| `apps/products/photoroom_photofix.py` | PhotoFix on upload |
| `apps/products/photoroom_guard.py` | Cutout safety / fragile categories |
| `apps/products/photoroom_brand_template.py` | Brand kit → scene params |
| `apps/products/photo_variations.py` | Snap pipeline orchestration |

### User-facing brand settings

Photoroom brand kit is configured in **Settings → Profile & Brand** (`templates/accounts/settings.html`):

- Studio background color
- Shadow mode
- Padding
- Brand template enable/disable

Stored on `UserProfile` → consumed by `resolve_brand_dna()` in `apps/media/brand_dna.py`.

---

## 5. Media orchestration (apps/media)

### Package structure

| File | Purpose |
|------|---------|
| `orchestrator.py` | `plan_media_for_product()`, Flux enhancement hook |
| `asset_intelligence.py` | Recommends `MediaPlan` from product + images |
| `router.py` | Picks reel/carousel/enhancement backend by plan tier |
| `content_types.py` | `MediaPlan`, `ReelBackend`, `CarouselBackend` enums |
| `brand_dna.py` | Unified brand colors/voice for all APIs |
| `fal_client.py` | Kling + Flux Fal.ai client |
| `bannerbear_client.py` | Carousel slide rendering |
| `carousel_bridge.py` | Wires Bannerbear into product carousels |
| `reel_bridge.py` | Wires Kling/Photoroom into reel posts |
| `tasks.py` | Celery async media jobs |
| `context_processors.py` | Exposes `media_caps` to templates |

### Template context (`media_caps`)

Available in all authenticated templates via `media_capabilities` context processor:

```django
{% if media_caps.photoroom_enabled %}…{% endif %}
{% if media_caps.kling_reels %}…{% endif %}
{% if media_caps.bannerbear_carousels %}…{% endif %}
{{ media_caps.flux_edits_per_month }}
{{ media_caps.orchestration_enabled }}
```

### MediaPlan metadata

Stored on `BusinessAsset.metadata.media_plan` after Snap:

```json
{
  "formats": ["carousel", "reel", "single_post"],
  "enhancement": "photoroom",
  "reel_backend": "ffmpeg",
  "carousel_backend": "local",
  "scene_pack": "auto",
  "kling_prompt": "",
  "flux_edit_prompt": "",
  "rationale": "3 images, fashion product — carousel + reel"
}
```

---

## 6. Fal.ai (Kling + Flux)

### Sign up

1. Create account at [fal.ai](https://fal.ai)
2. Go to **Dashboard → API Keys**
3. Copy key → `FAL_API_KEY` in environment

`FAL_KEY` is accepted as a legacy alias.

### API base URL

```
https://queue.fal.run/<model_id>
```

Implemented in `apps/media/fal_client.py`.

### Models (configurable)

| Use | Default model | Env override |
|-----|---------------|--------------|
| Image-to-video reels | `fal-ai/kling-video/v2.1/master/image-to-video` | `FAL_KLING_MODEL` |
| Creative image edit | `fal-ai/flux-pro/kontext` | `FAL_FLUX_EDIT_MODEL` |

### When Fal is used

| Feature | Plan gate | Fallback |
|---------|-----------|----------|
| Kling reels | `kling_reels_enabled` (Pro+) | FFmpeg slideshow |
| Flux edit | `fal_flux_edits_per_month` > 0 | Photoroom only |

`fal_enabled()` returns `False` if `MEDIA_ORCHESTRATION_ENABLED=False` or no API key.

### Billing note

Fal charges per generation. Monitor usage in [fal.ai dashboard](https://fal.ai/dashboard). Kling is significantly more expensive than FFmpeg reels — gate remains Pro+ only.

---

## 7. Bannerbear (branded carousels)

### Sign up

1. Create account at [bannerbear.com](https://www.bannerbear.com)
2. **Settings → API Key** → `BANNERBEAR_API_KEY`
3. Create three templates in the Bannerbear editor:
   - **Cover** — product name, hero image, price
   - **Slide** — feature bullet + image
   - **CTA** — order/WhatsApp call-to-action

### Template setup

Templates must expose modification layers matching `BrandDNA.bannerbear_modifications()`:

| Layer name | Typical use |
|------------|-------------|
| `title` | Product or feature name |
| `subtitle` | Description or brand name |
| `price` | Display price |
| `image` | Product photo URL (must be public HTTPS) |
| `cta` | Button text |

Copy each template UID:

```bash
BANNERBEAR_TEMPLATE_COVER=abc123...
BANNERBEAR_TEMPLATE_SLIDE=def456...
BANNERBEAR_TEMPLATE_CTA=ghi789...
```

Mapped in settings as `BANNERBEAR_TEMPLATES` dict.

### API

```
POST https://api.bannerbear.com/v2/images
Authorization: Bearer <BANNERBEAR_API_KEY>
```

See `apps/media/bannerbear_client.py`.

### Plan gate

`bannerbear_carousels_enabled` — **Growth+** only. Starter uses local Pillow carousels.

---

## 8. AI image generation (FLUX)

Used by the **Create Agent** for social post images (not Snap product polish).

### Provider priority (automatic fallback)

1. **HuggingFace** — `HF_TOKEN` (free, rate-limited)
2. **Together.ai** — `TOGETHER_API_KEY` (paid, reliable)
3. **Pollinations** — `POLLINATIONS_API_KEY` (free tier)

At least one key recommended for Growth+ plans with `ai_image_generation=True`.

### Limits per plan

| Plan | `ai_images_per_month` | `visual_enhancements_per_month` (Photoroom credits) |
|------|----------------------|-----------------------------------------------------|
| Starter | 0 | 8 |
| Growth | 50 | 30 |
| Pro | 100 | 100 |
| Agency | 200 | 150 |

`visual_enhancements_per_month` = Photoroom Plus calls (1 credit = 1 API call per scene variant).

---

## 9. Cloudflare R2 storage

**Required in production.** Without R2, polished images and generated media are lost on every Railway redeploy.

Full step-by-step: [VISUAL_PIPELINE_SETUP.md §1](VISUAL_PIPELINE_SETUP.md#1-cloudflare-r2-media-storage)

Quick checklist:

- [ ] Create bucket `kova-media` with public access
- [ ] Create API token (Object Read & Write)
- [ ] Set 4 env vars on Railway
- [ ] Optional: `AWS_S3_CUSTOM_DOMAIN` for branded media URLs

---

## 10. Plan tiers & feature gates

| Feature | Starter | Growth | Pro | Agency |
|---------|---------|--------|-----|--------|
| Photoroom credits/mo | 8 | 30 | 100 | 150 |
| Max scenes per Snap | 3 | 5 | 7 | 10 |
| AI images/mo | 0 | 50 | 100 | 200 |
| Bannerbear carousels | No | Yes | Yes | Yes |
| Kling reels (Fal) | No | No | Yes | Yes |
| Flux edits/mo | 0 | 10 | 30 | 100 |

Enforced in:
- `apps/billing/models.py` → `PLAN_LIMITS`
- `apps/media/router.py` → `plan_allows()`
- `apps/billing/visual_credits.py` → per-user Photoroom credits

---

## 11. In-app URLs & admin links

### User-facing

| URL | Purpose |
|-----|---------|
| `/products/snap/` | Snap to Sell — triggers Photoroom polish |
| `/products/snap/batch/` | Batch Snap (market day) |
| `/products/<id>/snap-status/` | HTMX pipeline status poll |
| `/content/studio/` | Review generated posts + media |
| `/accounts/settings/` | Brand kit (Photoroom colors, shadow) |
| `/billing/pricing/` | Plan limits for media features |

### Staff admin

| URL | Purpose |
|-----|---------|
| `/admin-dashboard/commerce/photoroom/` | Photoroom config, pool usage, API param reference |
| `/admin-dashboard/costs/` | Visual API cost breakdown |

### External service dashboards

| Service | Dashboard |
|---------|-----------|
| Photoroom | [photoroom.com/api](https://www.photoroom.com/api) |
| Fal.ai | [fal.ai/dashboard](https://fal.ai/dashboard) |
| Bannerbear | [app.bannerbear.com](https://app.bannerbear.com) |
| Together | [api.together.xyz](https://api.together.xyz) |
| Cloudflare R2 | [dash.cloudflare.com](https://dash.cloudflare.com) → R2 |

---

## 12. Verification & smoke tests

### Photoroom sandbox

```bash
cd kova_agent
# Ensure PHOTOROOM_API_KEY and PHOTOROOM_SANDBOX=True in .env
python scripts/test_photoroom_sandbox.py
```

Expected: `plus_sandbox_result.jpg` written to `tmp/photoroom_test/`.

### Django check

```bash
python manage.py check
```

### Manual Snap test

1. Log in as a user on Growth+ plan (or trial with credits)
2. Go to `/products/snap/`
3. Upload a product photo with **Studio polish pack** enabled
4. Confirm variants appear (studio white, AI lifestyle, etc.)
5. Check image URLs point to R2 in production (not `/media/` local path)

### Fal test (Pro+ user)

1. Set `FAL_API_KEY`
2. Ensure user plan has `kling_reels_enabled=True`
3. Create a reel post from a polished product image
4. Check Celery logs for `Fal submit` / `kling` prefix in saved video path

### Bannerbear test (Growth+)

1. Set `BANNERBEAR_API_KEY` + all three template UIDs
2. Snap a product with 2+ images
3. Generate carousel — slides should use Bannerbear URLs when configured

---

## 13. Production vs development matrix

| Setting | Development | Production |
|---------|---------------|------------|
| `PHOTOROOM_SANDBOX` | `True` | `False` |
| `PHOTOROOM_VIDEO_ENABLED` | `False` | `True` only if budget allows |
| `AWS_STORAGE_BUCKET_NAME` | Empty (local disk OK) | **Required** |
| `FAL_API_KEY` | Optional | Set if offering Kling reels |
| `BANNERBEAR_API_KEY` | Optional | Set for branded carousels |
| `MEDIA_ORCHESTRATION_ENABLED` | `True` | `True` |
| `DEBUG` | `True` | `False` |

### Recommended production `.env` block

```bash
# ─── MEDIA STORAGE (P0) ───
AWS_STORAGE_BUCKET_NAME=kova-media
AWS_S3_ENDPOINT_URL=https://YOUR_ACCOUNT_ID.r2.cloudflarestorage.com
AWS_S3_ACCESS_KEY_ID=
AWS_S3_SECRET_ACCESS_KEY=
AWS_S3_CUSTOM_DOMAIN=pub-xxxxx.r2.dev

# ─── PHOTOROOM (P0) ───
PHOTOROOM_API_KEY=
PHOTOROOM_SANDBOX=False
VISUAL_ENHANCE_ENABLED=True
PHOTOROOM_BASIC_API_KEY=
PHOTOROOM_BASIC_ROUTING_ENABLED=True

# ─── AI IMAGES (P1) ───
TOGETHER_API_KEY=
HF_TOKEN=

# ─── ORCHESTRATION (P2) ───
MEDIA_ORCHESTRATION_ENABLED=True
FAL_API_KEY=
BANNERBEAR_API_KEY=
BANNERBEAR_TEMPLATE_COVER=
BANNERBEAR_TEMPLATE_SLIDE=
BANNERBEAR_TEMPLATE_CTA=
```

---

## 14. Troubleshooting

| Symptom | Likely cause | Fix |
|---------|--------------|-----|
| "Photoroom is not configured" | Missing `PHOTOROOM_API_KEY` | Add key; set `VISUAL_ENHANCE_ENABLED=True` |
| Studio polish returns original only | Sandbox limit hit or pool exhausted | Check admin Photoroom dashboard; raise pool or wait for reset |
| Images disappear after deploy | No R2 configured | Set R2 env vars (see §9) |
| Reels are slideshow only | No `FAL_API_KEY` or Starter/Growth plan | Add Fal key; upgrade to Pro for Kling |
| "Video generation failed" | `PHOTOROOM_VIDEO_ENABLED=False` | Enable video flag or rely on FFmpeg fallback |
| Bannerbear slides empty | Missing template UIDs | Set all three `BANNERBEAR_TEMPLATE_*` vars |
| Carousel uses local slides not Bannerbear | Growth plan required + key set | Check `bannerbear_carousels_enabled` in plan |
| `ModuleNotFoundError: apps.media` | `.gitignore` ignored `apps/media/` | Ensure `.gitignore` uses `/media/` not `media/` |
| High uncertainty / skipped variants | Bad segmentation on jewelry/reflective goods | Expected — guard uses safe fallback (`photoroom_guard.py`) |
| Fal timeout | Queue poll exceeded 180s | Retry; check fal.ai status; reduce concurrent jobs |

### Logs to watch

```bash
# Celery worker
grep -E "Photoroom|Fal|Bannerbear|studio_polish" <celery_log>

# Django
grep -E "photoroom|fal_enabled|bannerbear" <app_log>
```

---

## File index

```
kova_agent/
├── .env.example                          # Copy-paste template
├── config/settings/base.py               # All MEDIA_* / PHOTOROOM_* defaults
├── apps/media/                           # Orchestration package
├── apps/products/photoroom*.py           # Photoroom integration
├── apps/billing/models.py                # PLAN_LIMITS media gates
├── apps/billing/visual_credits.py        # Per-user polish credits
├── scripts/test_photoroom_sandbox.py     # API smoke test
└── docs/
    ├── MEDIA_API_SETUP.md                # This file
    ├── VISUAL_PIPELINE_SETUP.md          # R2 + visual strategy
    ├── VISUAL_ENHANCEMENT_SPEC.md        # Plus variant catalog
    └── KOVA_PHOTOROOM_STRATEGY.md        # Basic vs Plus economics
```

---

*Last updated: June 2026*
