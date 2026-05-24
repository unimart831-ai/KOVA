# Kova Visual Enhancement Spec (BIOS)

> **Status:** Plus plan (v2/edit) — quality-first, no local fallbacks  
> **Last updated:** May 2026  
> **Scope:** Photo enhancement for commerce + Studio outputs. **No AI video generation.** Not a Canva clone.

---

## 1. Product Position

Kova is a **Business Intelligence Operating System (BIOS)** with commerce — not a design tool.

Visuals are **one output** of the OS. The user **chooses** how each photo is treated:

| Mode | User intent | Kova action | API cost |
|------|-------------|-------------|----------|
| **Use as-is** | Photo is already professional | Platform crop, caption, schedule | $0 |
| **Studio polish** | Needs pro cutout + shadow + studio background | Photoroom Plus v2/edit | 1 visual credit |

**Unlimited on all plans ($0 COGS):**
- Carousels (Pillow / PDF)
- Motion reels (FFmpeg Ken Burns + music library)
- Use-as-is uploads
- Branded promo frame derived from Plus hero (local Pillow only)

**Metered (paid API):**
- Studio polish only → **visual credits**

**Quality policy:** We do **not** fall back to local rembg/quick polish when Plus fails or is unavailable. The original photo is kept and the user sees a clear notice.

---

## 2. User Control Principles

1. **Default recommendation, not default transformation** — Studio polish is the default when credits are available.
2. **Never auto-burn credits** on Snap launch unless user selected Studio polish.
3. **Badge on outputs** — `Original` | `Studio` in queue and product gallery.
4. **At cap** — Compact plan-limit banner; user can choose **Use as-is** (no degraded free polish).

---

## 3. API Stack

### Primary: Photoroom **Image Editing API** (Plus plan)

| API | Plan | Endpoint | Use |
|-----|------|----------|-----|
| Remove Background API | Basic ($100/5k) | `POST sdk.photoroom.com/v1/segment` | **Not used** |
| **Image Editing API** | **Plus ($500/5k)** | `GET/POST image-api.photoroom.com/v2/edit` | **Studio polish** |

**Endpoint:** `GET/POST https://image-api.photoroom.com/v2/edit`

Query / form params (we use POST with `imageFile` when URL is not public):

| Param | Example | Purpose |
|-------|---------|---------|
| `removeBackground` | `true` | Pro cutout |
| `background.color` | `FFFFFF` | Solid studio background (hex, no `#`) |
| `outputSize` | `1080x1080` | Exact square output |
| `padding` | `0.12` | Product breathing room |
| `shadow.mode` | `ai.soft` | AI soft shadow |
| `export.format` | `jpeg` | JPEG output |

Header: `x-api-key: PHOTOROOM_API_KEY`

**Sandbox (free, watermarked):** Prepend `sandbox_` to your API key, or use a key that already starts with `sandbox_`. Set `PHOTOROOM_SANDBOX=True` — we auto-prefix only when the key does not already start with `sandbox_`.

Env (see `.env.example`):

| Variable | Default | Purpose |
|----------|---------|---------|
| `PHOTOROOM_API_KEY` | — | Required for studio polish |
| `VISUAL_ENHANCE_ENABLED` | `True` | Master switch |
| `PHOTOROOM_SANDBOX` | `False` | Prepend `sandbox_` to key when true |
| `PHOTOROOM_MONTHLY_POOL` | `5000` | Platform pool size |
| `PHOTOROOM_POOL_RESERVE` | `500` | Headroom (usable = pool − reserve) |
| `PHOTOROOM_MONTHLY_COST_USD` | `500` | Admin cost dashboard |
| `PHOTOROOM_OUTPUT_SIZE` | `1080x1080` | Plus output dimensions |
| `PHOTOROOM_PADDING` | `0.12` | Padding around product |
| `PHOTOROOM_DEFAULT_SHADOW` | `ai.soft` | Shadow mode |

**Production (Railway / live):** Use your **live Plus** API key, set `PHOTOROOM_SANDBOX=False`, and run migrations:

```bash
python manage.py migrate products
```

### Free tier (always)

- **Pillow** promo frame from Plus hero (`photo_variations.py`)
- **FFmpeg** reels (`video_compose.py`)

### Not in scope

- Local rembg quick polish in production paths
- Kling / Runway / AI video generation
- Canva-style canvas editor

---

## 4. Plan Limits

| Plan | KES | Studio polish/mo | AI images (FLUX) | Carousels | Reels |
|------|-----|------------------|------------------|-----------|-------|
| Jipange / Starter | 499 | **15** | 0 | Unlimited | Unlimited |
| Kazi / Growth | 999 | **40** | 50 | Unlimited | Unlimited |
| Biashara / Pro | 1,999 | **80** | 100 | Unlimited | Unlimited |
| Wakala / Agency | — | **200** | 500 | Unlimited | Unlimited |

**1 visual credit = 1 Photoroom Plus API call** (~$0.10 at $500/5k pool).

Platform enforcement: when pool is exhausted, studio polish is **blocked** (original photo kept).

---

## 5. Credit Metering

Module: `apps/billing/visual_credits.py`

- `get_visual_credit_usage(user)` — per-user monthly quota + platform pool status
- `get_platform_photoroom_usage()` — platform-wide pool consumption
- `check_visual_credit_limit(user)` — blocks user quota OR platform pool
- `record_studio_polish(user, product_id, provider, output_data)`

AgentAction:
- `action_type`: `commerce.studio_polish` (legacy: `commerce.pro_scene`)
- `input_data.provider`: `photoroom_plus`

---

## 6. Pipeline (Studio polish)

```
User selects Studio polish on Snap to Sell
    → check_visual_credit_limit (user + platform pool)
    → pick_background_color_hex(product, brand palette)
    → POST image-api.photoroom.com/v2/edit (cutout + bg + shadow + 1080×1080)
    → Save hero JPEG to studio_polish/{product_id}/
    → record_studio_polish (1 credit)
    → Local Pillow: branded promo frame from hero (free)
    → Append URLs to product.additional_images
    → Carousels + reels from all images (free, local)
```

**1 credit → 2 images** (1 Plus hero + 1 local promo frame).

On failure (API error, missing key, at cap): **no fallback** — original photo unchanged, user notified.

---

## 7. UI Surfaces

| Surface | Modes | Notes |
|---------|-------|-------|
| **Snap to Sell** | as_is / studio_polish | Two radio cards; default studio when credits available |
| **Product detail → Expand Photo Set** | Uses product `visual_mode` | Plus studio polish |
| **Pricing page** | — | Studio polish count per plan |
| **Admin costs** | — | Photoroom pool meter |

DB field: `Product.visual_mode` — value `pro_scene`, label **Studio polish**. Legacy `quick_polish` rows migrate to `pro_scene`.

---

## 8. File Map

| File | Role |
|------|------|
| `apps/products/photoroom.py` | Photoroom Plus v2/edit client |
| `apps/products/photo_variations.py` | Mode routing + promo frame |
| `apps/billing/visual_credits.py` | Usage + enforcement |
| `apps/billing/models.py` | `visual_enhancements_per_month` in PLAN_LIMITS |
| `scripts/test_photoroom_sandbox.py` | Standalone Plus API smoke test |
| `config/settings/base.py` | Photoroom env vars |
| `docs/VISUAL_ENHANCEMENT_SPEC.md` | This document |

---

## 9. Testing

### 9.1 Prerequisites

1. Pull latest `main`.
2. Install deps (`pip install -r requirements.txt`).
3. Add to `kova_agent/.env`:

```env
PHOTOROOM_API_KEY=your_plus_key_here
VISUAL_ENHANCE_ENABLED=True
PHOTOROOM_SANDBOX=True
PHOTOROOM_MONTHLY_POOL=5000
PHOTOROOM_POOL_RESERVE=500
PHOTOROOM_MONTHLY_COST_USD=500
```

4. Run migrations:

```bash
cd kova_agent
python manage.py migrate products
```

5. Celery worker must be running for Snap to Sell / Expand Photo Set background jobs.

---

### 9.2 Level 1 — API smoke test (fastest)

```bash
cd kova_agent
python scripts/test_photoroom_sandbox.py
```

**Expected:**
- `POST https://image-api.photoroom.com/v2/edit`
- `OK — Plus sandbox test passed`
- Output: `tmp/photoroom_test/plus_sandbox_result.jpg` (1080×1080, watermark in sandbox)

---

### 9.3 Level 2 — Snap to Sell (full user flow)

1. Start web + worker + Redis.
2. Log in as a user on **Jipange** or higher.
3. Open **Snap to Sell** → upload photo → select **Studio polish**.
4. Launch campaign → wait for pipeline (~1–2 min).

**Verify:**
- Gallery shows Plus hero (`studio_polish/{product_id}/`) + optional promo frame.
- One `commerce.studio_polish` action with `provider=photoroom_plus`.
- Credit counter decrements by 1.

**Failure behavior:**
- `PHOTOROOM_API_KEY` unset → amber notice on Snap; launch with studio blocked or kept as-is.
- At cap → plan-limit banner; original photo only.

---

### 9.4 Production checklist (Railway)

1. Set `PHOTOROOM_API_KEY` (live Plus key), `PHOTOROOM_SANDBOX=False`, `PHOTOROOM_MONTHLY_COST_USD=500`.
2. Deploy and run `python manage.py migrate products`.
3. Confirm one live studio polish — URLs must contain `studio_polish/`, not `product_variations/white_studio`.
4. Monitor `/dashboard/costs/` — Photoroom Plus pool meter.

---

## 10. Success Metrics

- Studio polish completion rate > 95%
- Zero silent fallback to local rembg in production
- Platform pool utilization < 90% at steady state
