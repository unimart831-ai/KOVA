# Photoroom Upgrade — Preflight Repair & Channel Exports

> **Status:** Phase A–D shipped  
> **Last updated:** May 2026  
> **Builds on:** `docs/VISUAL_ENHANCEMENT_SPEC.md`, `apps/products/photoroom_plus.py`

---

## 1. Problem

Today, Studio polish pack treats every upload the same: pick N square scene variants from the catalog and append a promo frame. PhotoRoom’s repair and resize capabilities exist in the catalog but are **not orchestrated**:

- Dark, blurry, or WhatsApp-compressed photos go straight to lifestyle scenes.
- Every output is `1080×1080` JPEG — reels and stories rely on local letterboxing.
- Credits are spent on decorative alternates before fixing the source.

**Goal:** One Snap upload becomes a **repaired master** plus **channel-ready assets** (feed square, story/reel 9:16, optional banner), within the same per-plan credit pool.

---

## 2. New pipeline (Phase A + B)

```
Upload
  → Vision analysis (+ photo_quality block)
  → Local quality metrics (brightness, blur, compression heuristics)
  → Preflight repair chain (0–2 credits, only when triggered)
  → Master image URL
  → Scene pack on master (remaining credits)
  → Channel exports from best hero (0–2 credits, Growth+)
  → Promo frame (free, local Pillow)
  → Carousels / reels / posts
```

### Credit budget (same monthly pool)

| Step | Max credits | When |
|------|-------------|------|
| Preflight repairs | 2 | Only if quality triggers fire |
| Scene pack | `plan_max − channel_slots − repairs_used` | Always (min 1 scene) |
| Channel exports | 2 | Growth+ only; story + banner |
| Promo frame | 0 | Always after Plus |

**Example (Growth, 5 credits, bad phone photo):**  
2 repairs (relight + upscale) + 2 channel (story + banner) + 1 scene = 5.

**Example (Growth, 5 credits, clean photo):**  
0 repairs + 2 channel + 3 scenes = 5.

---

## 3. Phase A — Photo Intelligence Preflight

### 3.1 Quality signals

**Vision JSON** (added to all offering-type vision prompts):

```json
"photo_quality": {
  "lighting": "good|dark|uneven",
  "sharpness": "sharp|soft|blurry",
  "has_distracting_text": false,
  "crop": "comfortable|tight|very_tight"
}
```

**Local metrics** (`photoroom_preflight.py`, no extra API cost):

| Metric | Trigger |
|--------|---------|
| Mean brightness | `< 85` → dark |
| Laplacian variance | `< 120` → blurry |
| File size + dimensions | `< 90 KB` at ≥800px → WhatsApp/compressed |
| Aspect ratio | `< 0.55` or `> 1.85` → awkward crop hint |

Merged report drives repair plan.

### 3.2 Repair order (first match wins, max 2 runs)

| Priority | Variant ID | Trigger |
|----------|------------|---------|
| 1 | `text_removal` | `has_distracting_text` or vision/local text hint |
| 2 | `relight` | dark or uneven lighting |
| 3 | `upscale` | blurry, soft, or compression heuristic |
| 4 | `uncrop` | very_tight / tight crop (Growth+) |

Each repair:

1. Consumes 1 visual credit.
2. Saves to `studio_polish/{product_id}/preflight_{variant_id}_*.jpg`.
3. Passes output URL as input to the next step.
4. Final URL becomes **master** for scene pack.

Repairs use existing Plus variant specs — no duplicate API wiring.

### 3.3 Settings

| Env | Default | Purpose |
|-----|---------|---------|
| `PHOTOROOM_PREFLIGHT_ENABLED` | `true` | Toggle preflight |
| `PHOTOROOM_PREFLIGHT_MAX_REPAIRS` | `2` | Cap repair credits per product |

### 3.4 Module

`apps/products/photoroom_preflight.py`

- `assess_photo_quality(image_source, analysis) → PhotoQualityReport`
- `build_repair_plan(report, plan_tier) → list[str]`  (variant ids)
- `run_preflight_repairs(source_url, product, analysis, brand_colors, budget) → PreflightResult`

---

## 4. Phase B — Channel-native exports

After scene pack produces at least one hero, export **format-specific** assets from the best hero (prefer `studio_white`, else first success).

| Variant ID | Output | Use |
|------------|--------|-----|
| `channel_story` | `1080×1920` | Instagram/TikTok Stories, reel source |
| `channel_banner` | `1920×1080` | Facebook cover, ads, landscape cards |

Implementation: Plus `expand.mode=ai.auto` + `outputSize` + studio cutout/shadow on hero source.

Portrait heroes may use `uncrop` path when aspect `< 0.75` (story only).

Saved as:

```
studio_polish/{product_id}/channel_story_*.jpg
studio_polish/{product_id}/channel_banner_*.jpg
```

Appended to `product.additional_images` after square scenes.

### 4.1 Reel integration

`create_product_reel_posts` / `compose_reel_video` prefer URLs containing `channel_story` when building reel image lists (9:16 native, less letterbox padding).

### 4.2 Settings

| Env | Default | Purpose |
|-----|---------|---------|
| `PHOTOROOM_CHANNEL_EXPORTS_ENABLED` | `true` | Toggle channel step |
| `PHOTOROOM_STORY_SIZE` | `1080x1920` | Story/reel export |
| `PHOTOROOM_BANNER_SIZE` | `1920x1080` | Banner export |

Channel exports require **Growth+** plan (same as `ai_contextual`).

---

## 5. Catalog additions

New entries in `PLUS_VARIANT_CATALOG`:

```python
"channel_story"   # expand/uncrop → PHOTOROOM_STORY_SIZE
"channel_banner"  # expand → PHOTOROOM_BANNER_SIZE
```

Not selected by `select_plus_variants()` — invoked explicitly post-hero.

---

## 6. API / UI changes

### Snap pipeline modal

Expand step detail examples:

- Running preflight: `Fixing lighting and sharpness before scene pack…`
- Channel step (sub-detail): `Exporting story and banner formats…`

### Admin Photoroom tab

Document preflight + channel variants and new env keys.

### AgentAction `output_data`

Preflight and channel runs record:

```json
{
  "variant": "preflight_relight",
  "phase": "preflight|scene|channel",
  "url": "..."
}
```

---

## 7. Key files

| File | Change |
|------|--------|
| `apps/products/photoroom_preflight.py` | **New** — quality + repair orchestration |
| `apps/products/photoroom_plus.py` | Channel variant specs + output size placeholders |
| `apps/products/photo_variations.py` | Wire preflight → scenes → channel in `_expand_studio_polish` |
| `apps/products/tasks.py` | Vision prompt `photo_quality` block |
| `apps/products/tasks.py` | Reel source prefers `channel_story` URLs |
| `config/settings/base.py` | New env settings |
| `tests/test_photoroom_preflight.py` | **New** |
| `tests/test_photoroom_plus.py` | Channel catalog coverage |

---

## 8. Future phases

| Phase | Feature | Status |
|-------|---------|--------|
| C | Slide-role orchestration (hero → lifestyle → proof → CTA) | **Shipped** |
| **Creative** | Bold AI backgrounds (splash, marble, neon, powder…) | **Shipped** |
| D | Seller brand template (locked shadow, padding, prompt seed) | **Shipped** |
| E | Edit-with-AI UI + Create Any Image promos | Planned |
| F | PhotoRoom batch API for catalog imports | Planned |

---

## 9. Phase C — Slide-role orchestration (shipped)

Scene variants are selected and **run in carousel story order**, not raw priority:

| Role | Product variants | Service | Digital |
|------|------------------|---------|---------|
| Hero | `studio_white`, `studio_brand` | `service_hero` | `digital_desk_hero` |
| Desire / context | `ai_lifestyle`, `ai_contextual` | `service_context` | `digital_device_mockup` |
| Proof / trust | Category: flat lay, ghost, virtual model… | `relight`, blur | `ai_lifestyle` |
| Standout | `studio_dark`, `outline` | — | — |

**Carousel safety:** `Product.carousel_image_urls` and `filter_carousel_urls()` exclude `channel_story`, `channel_banner`, and `preflight_*` assets. Promo frame (local CTA slide) still appended last.

**Setting:** `PHOTOROOM_SLIDE_ROLES_ENABLED` (default `true`).

**AgentAction `output_data`:** scene runs include `slide_role` (`hero`, `desire`, `proof`, `standout`, etc.).

---

## 10. Creative Scene Pack (shipped)

Bold PhotoRoom-style AI backgrounds — selected by **product category** and run in the **desire** carousel slot (before standard lifestyle).

| Variant ID | Look | Categories | Plan |
|------------|------|------------|------|
| `ai_creative_splash` | Water splash, droplets | food, beauty | Growth+ |
| `ai_creative_marble` | Luxury marble pedestal | beauty, jewelry, home | Growth+ |
| `ai_creative_botanical` | Tropical leaves, organic | beauty, food, home, apparel | Growth+ |
| `ai_creative_neon` | Cyberpunk neon glow | electronics, apparel | Growth+ |
| `ai_creative_powder` | Cosmetic powder burst | beauty, food | Pro+ |
| `ai_creative_podium` | Gradient podium reveal | all products | Growth+ |

Prompts include product name + vision `campaign_angle`. Tagged `slide_role: creative` in usage logs.

**Setting:** `PHOTOROOM_CREATIVE_SCENES_ENABLED` (default `true`).

---

## 11. Phase D — Seller brand template (shipped)

Every Plus call for a seller uses a **locked brand template** so their catalog looks cohesive.

| Setting | Source | Applied to |
|---------|--------|------------|
| `shadow.mode` | Industry (+ override) | All cutout studio variants |
| `padding` | Industry (+ override) | All studio variants |
| `background.seed` | Stable hash of `user_id` | All AI background variants |
| `outline.color` | Brand accent color | Outline variant |
| `background.color` | Brand primary | `studio_brand` only |
| Prompt suffix | `visual_style` + brand voice | AI / flat lay / model prompts |

**Industry defaults:**

- SaaS / media → `ai.floating` shadow, tighter padding  
- Finance / legal / real estate → `ai.hard` shadow, wider padding  
- Retail / beauty / food → `ai.soft` shadow  

**Profile overrides:** `UserProfile.photoroom_brand_template` JSON:

```json
{
  "shadow_mode": "ai.floating",
  "padding": "0.11",
  "ai_seed": 117879368,
  "outline_color": "FF5733",
  "style_suffix": "Warm Kenyan boutique aesthetic",
  "enabled": true
}
```

**Setting:** `PHOTOROOM_BRAND_TEMPLATE_ENABLED` (default `true`).

**Migration:** `accounts.0022_userprofile_photoroom_brand_template`

---

## 12. Testing

```bash
pytest tests/test_photoroom_preflight.py tests/test_photoroom_plus.py tests/test_photoroom_brand_template.py -q
```

Manual: Snap a dark/blurry phone photo → confirm `preflight_*` URLs then `channel_story_*` in `additional_images`; reel should use story asset.

---

## 13. Rollout

1. Deploy with `PHOTOROOM_PREFLIGHT_ENABLED=true`, `PHOTOROOM_CHANNEL_EXPORTS_ENABLED=true`.
2. Monitor credit usage in admin Photoroom tab.
3. Tune blur/brightness thresholds from production feedback.
