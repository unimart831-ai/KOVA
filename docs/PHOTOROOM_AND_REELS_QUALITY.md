# Photoroom & Reels — Quality Guardrails

**Last updated:** June 2026  
**Related:** `KOVA_PHOTOROOM_STRATEGY.md`, `platform-audits/REELS_AND_VIDEO_STRATEGY.md`

---

## Problem statement

1. **Photoroom cutouts** sometimes erase thin products (rings, chains, earrings) or leave empty white frames — customers lose trust because the listing looks worse than their phone photo.
2. **Motion reels** felt amateur: too many AI slides, preflight junk in the timeline, white-on-white blur in 9:16, and pacing that didn’t match professional shop content.

---

## Photoroom — what we changed

### Safe hero (`studio_safe`)

When cutout confidence is low or the category is fragile (jewelry, beauty, watches, accessories), the pipeline prefers **`studio_safe`**:

- `removeBackground=false`
- Background bokeh blur on the original photo
- `lighting.mode=ai.preserve-hue-and-saturation` (no color drift)

No subject erasure — we polish the photo they took, not replace it.

### Category-aware uncertainty

| Category | Uncertainty threshold (high) |
|----------|------------------------------|
| Jewelry, beauty, watches, accessories | **0.42** (default) |
| Everything else | **0.60** (default) |

Configurable via `PHOTOROOM_FRAGILE_UNCERTAINTY_THRESHOLD` and `PHOTOROOM_UNCERTAINTY_HIGH_THRESHOLD`.

### Post-cutout validation

After every cutout variant (`studio_white`, `relight`, AI scenes, etc.):

1. Compare **subject fill ratio** (non-white pixels in center crop) before vs after.
2. If the product mass collapsed → **reject** and re-run **`studio_safe`** on the master image.
3. Toggle: `PHOTOROOM_CUTOUT_VALIDATION_ENABLED` (default `true`).

**Code:** `apps/products/photoroom_guard.py`, integrated in `photo_variations.py`.

### Jewelry-specific

- **Beautify disabled** for jewelry/watches (alters metal/skin tones).
- Hero order: `studio_safe` → `studio_white` when category is jewelry.
- High uncertainty: skip ghost mannequin, flat lay, virtual model (unchanged).

---

## Reels — what we changed

### Smarter slide selection (`reel_curation.py`)

| Rule | Before | After |
|------|--------|-------|
| Max slides | Up to 10 (`max_slides * 2`) | **5 max** |
| AI scenes per reel | Up to 3 | **2 max** |
| Excluded URLs | preflight, channel_banner | + sandbox, local_quick, photofix |
| Priority | Mixed | channel story → **studio_safe/white** → 1–2 AI → promo CTA |
| Single product | Could duplicate in carousel | **1 slide** = one strong hold |

### Professional 9:16 framing (`video_compose.py`)

White studio product shots (common after Photoroom) no longer get **blurred white backgrounds** in reels.

- Detect ≥55% near-white pixels → use **dark branded gradient** (`#0c1222` → `#1a2235`).
- Product stays in the hero safe zone; captions stay in lower third.

---

## Operator checklist

### When a Snap listing looks destroyed

1. Check **Photoroom admin** → uncertainty score on that product’s variants.
2. Re-snap with plain background, good lighting, product centered (reduces uncertainty).
3. For rings/jewelry: expect **`studio_safe`** hero automatically — share that URL on WhatsApp, not a failed `studio_white`.
4. **Photoroom watermarks** = sandbox key or expired credits — fix `PHOTOROOM_API_KEY` on Railway.

### When a reel looks amateur

1. Confirm product has **`studio_white`** or **`studio_safe`** in additional_images (not raw `product_images/` only).
2. Re-trigger reel: approve post in Studio or re-run Snap pipeline.
3. Ideal reel length: **3–5 slides**, 12–18 seconds total.

---

## Settings reference

| Setting | Default | Purpose |
|---------|---------|---------|
| `PHOTOROOM_CUTOUT_VALIDATION_ENABLED` | `true` | Pixel validation after cutout |
| `PHOTOROOM_FRAGILE_UNCERTAINTY_THRESHOLD` | `0.42` | Earlier safe mode for jewelry etc. |
| `PHOTOROOM_UNCERTAINTY_HIGH_THRESHOLD` | `0.60` | General cutout caution |
| `PHOTOROOM_UNCERTAINTY_PROBE_ENABLED` | `true` | Pre-flight cutout probe |
| `REEL_MAX_SLIDES` | `5` | Cap slides in reel director |

---

## Tests

```bash
pytest tests/test_photoroom_guard.py tests/test_photoroom_api.py -q
```

---

## Next improvements (backlog)

- [ ] Human review queue UI for high-uncertainty Snap outputs before publish
- [ ] Per-industry reel recipe tuning (food = faster cuts, jewelry = slower hero hold)
- [ ] Photoroom HD segmentation flag for fine metal edges
- [ ] A/B: Basic API cutout vs Plus for simple white-bg phone photos (cost)
