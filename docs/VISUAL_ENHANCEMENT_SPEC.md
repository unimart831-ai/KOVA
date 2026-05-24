# Kova Visual Enhancement Spec (BIOS)

> **Status:** Implemented (Photoroom Basic)  
> **Last updated:** May 2026  
> **Scope:** Photo enhancement for commerce + Studio outputs. **No AI video generation.** Not a Canva clone.

---

## 1. Product Position

Kova is a **Business Intelligence Operating System (BIOS)** with commerce — not a design tool.

Visuals are **one output** of the OS. The user **chooses** how each photo is treated:

| Mode | User intent | Kova action | API cost |
|------|-------------|-------------|----------|
| **Use as-is** | Photo is already professional | Platform crop, caption, schedule | $0 |
| **Quick polish** | Needs framing, not a reshoot | Local rembg + Pillow presets | $0 |
| **Studio polish** | Needs pro cutout + studio background | Photoroom Basic API | 1 visual credit |

**Unlimited on all plans ($0 COGS):**
- Carousels (Pillow / PDF)
- Motion reels (FFmpeg Ken Burns + music library)
- Use-as-is uploads
- Quick polish
- Local variants generated from one studio polish call

**Metered (paid API):**
- Studio polish only → **visual credits**

---

## 2. User Control Principles

1. **Default recommendation, not default transformation** — Vision may suggest studio polish when background is cluttered; user confirms.
2. **Never auto-burn credits** on Snap launch unless user selected Studio polish.
3. **Badge on outputs** — `Original` | `Polished` | `Studio` in queue and product gallery.
4. **At cap** — Compact plan-limit banner + offer Quick polish / as-is (same pattern as seed limits).

---

## 3. API Stack

### Primary: Photoroom **Remove Background API** (Basic plan)

Per [Photoroom's introduction](https://docs.photoroom.com/#how-do-i-integrate-the-api-into-my-project), there are **two separate APIs**:

| API | Plan | Endpoint | Use |
|-----|------|----------|-----|
| **Remove Background API** | **Basic** ($100/5k) | `POST https://sdk.photoroom.com/v1/segment` | Cutout + `bg_color` + `size` |
| Image Editing API | Plus ($500+/5k) | `GET/POST https://image-api.photoroom.com/v2/edit` | AI backgrounds, shadows, padding, outputSize |

**We use Basic only.** One Image Editing call counts as **5** Remove Background calls — using v2/edit would burn the pool 5× faster and require Plus pricing.

**Endpoint:** `POST https://sdk.photoroom.com/v1/segment`

Multipart form fields:
- `image_file` — required (Basic API does not accept GET + imageUrl)
- `bg_color` — hex with `#` (e.g. `#FFFFFF`) or color name
- `size` — `preview` | `medium` | `hd` | `full` (we use `hd` = 4MP)
- `format` — `jpg` | `png` | `webp`
- `crop` — `false` (keep full frame with colored background)

Header: `x-api-key: PHOTOROOM_API_KEY`

**1080×1080 output:** Basic has no `outputSize` — we resize locally with Pillow after the API call (free).

Env:
- `PHOTOROOM_API_KEY`
- `VISUAL_ENHANCE_ENABLED` (default true)
- `PHOTOROOM_MONTHLY_POOL` (default 5000)
- `PHOTOROOM_POOL_RESERVE` (default 500)
- `PHOTOROOM_MONTHLY_COST_USD` (default 100)

### Free tier (always)

- **rembg** + **Pillow** presets (`photo_variations.py`)
- **FFmpeg** reels (`video_compose.py`)

### Not in scope

- Photoroom Plus ($500+/mo AI backgrounds)
- Kling / Runway / AI video generation
- Canva-style canvas editor
- User-facing prompt engineering UI

---

## 4. Plan Limits

| Plan | KES | Studio polish/mo | AI images (FLUX) | Carousels | Reels |
|------|-----|------------------|------------------|-----------|-------|
| Jipange / Starter | 499 | **15** | 0 | Unlimited | Unlimited |
| Kazi / Growth | 999 | **40** | 50 | Unlimited | Unlimited |
| Biashara / Pro | 1,999 | **80** | 100 | Unlimited | Unlimited |
| Wakala / Agency | — | **200** | 500 | Unlimited | Unlimited |

**1 visual credit = 1 Photoroom API call** (one cutout + color background).

Platform enforcement: when pool is exhausted, studio polish falls back to quick polish for all users.

---

## 5. Credit Metering

Module: `apps/billing/visual_credits.py`

- `get_visual_credit_usage(user)` — per-user monthly quota + platform pool status
- `get_platform_photoroom_usage()` — platform-wide pool consumption
- `check_visual_credit_limit(user)` — blocks user quota OR platform pool
- `record_studio_polish(user, product_id, provider, output_data)`

AgentAction:
- `action_type`: `commerce.studio_polish` (legacy: `commerce.pro_scene`)
- `input_data.provider`: `photoroom`

---

## 6. Pipeline (Studio polish)

```
User selects Studio polish on Snap to Sell
    → check_visual_credit_limit (user + platform pool)
    → pick_background_color_hex(product, brand palette)
    → POST sdk.photoroom.com/v1/segment (bg_color + size=hd, 1 Basic credit)
    → Local Pillow: fit to 1080×1080 square
    → Save hero JPEG to studio_polish/{product_id}/
    → record_studio_polish (1 credit)
    → Local rembg + Pillow: white studio, dark premium, promo frame (free)
    → Append URLs to product.additional_images
    → Carousels + reels from all images (free, local)
```

**1 credit → 4+ images** (1 API hero + 3 local bonus variants).

---

## 7. UI Surfaces

| Surface | Modes | Notes |
|---------|-------|-------|
| **Snap to Sell** | as_is / quick_polish / studio_polish | Radio cards; credit counter |
| **Product detail → Expand photos** | quick_polish / studio_polish | Credit check on studio |
| **Pricing page** | — | Studio polish count per plan |
| **Admin costs** | — | Photoroom pool meter (used / 4500) |

DB field: `Product.visual_mode` — value `pro_scene` (legacy), label **Studio polish**.

---

## 8. File Map

| File | Role |
|------|------|
| `apps/products/photoroom.py` | Photoroom API client |
| `apps/products/photo_variations.py` | Mode routing + local presets |
| `apps/billing/visual_credits.py` | Usage + enforcement |
| `apps/billing/models.py` | `visual_enhancements_per_month` in PLAN_LIMITS |
| `apps/products/visual_enhance.py` | Legacy shim (deprecated) |
| `config/settings/base.py` | Photoroom env vars |
| `docs/VISUAL_ENHANCEMENT_SPEC.md` | This document |

---

## 9. Success Metrics

- Studio polish completion rate > 95%
- Fallback to quick polish < 5% (excluding user at cap)
- Platform pool utilization < 90% at steady state
- Gross margin on studio polish > 70% at target mix

---

## 10. Future (not now)

- Photoroom Plus for AI generative scenes (premium tier add-on)
- Vision-suggested default mode when background is cluttered
- Unlimited studio polish on Agency
