# Kova Visual Enhancement Spec (BIOS) — Photoroom Plus Full Pack

> **Status:** Plus pack + Phase A/B preflight & channel exports  
> **Last updated:** May 2026  
> **See also:** `docs/Photoroom upgrade.md`

---

## 1. What “Studio polish pack” does

One Snap to Sell launch (when **Studio polish pack** is selected) runs **multiple Photoroom Plus API calls** — one per scene variant — capped by plan and remaining credits.

| Plan | Credits/mo | Max scenes per product |
|------|------------|------------------------|
| Jipange / Starter | 30 | 3 |
| Kazi / Growth | 100 | 5 |
| Biashara / Pro | 200 | 7 |
| Wakala / Agency | 500 | 10 |

**1 credit = 1 Plus API call.** A free local promo frame is appended after Plus scenes (no credit).

---

## 2. Plus variants (catalog)

Module: `apps/products/photoroom_plus.py`

| Variant ID | Plus feature | When used |
|------------|--------------|-----------|
| `studio_white` | Cutout + white bg + shadow | Always (products) |
| `studio_brand` | Brand color studio | Always |
| `studio_dark` | Premium dark studio | Jewelry, electronics |
| `ai_lifestyle` | AI background (Studio model) | Always |
| `ai_lifestyle_alt` | Second AI scene | Always |
| `ai_contextual` | AI contextual scene | Growth+ |
| `ai_creative_splash` | Water splash hero | food, beauty (Growth+) |
| `ai_creative_marble` | Luxury marble | beauty, jewelry (Growth+) |
| `ai_creative_botanical` | Botanical fresh | beauty, food, home (Growth+) |
| `ai_creative_neon` | Neon tech glow | electronics, apparel (Growth+) |
| `ai_creative_powder` | Powder explosion | beauty, food (Pro+) |
| `ai_creative_podium` | Gradient podium | all (Growth+) |
| `relight` | `lighting.mode=ai.auto` | Growth+ |
| `beautify` | `beautify.mode=ai.auto` | Beauty, jewelry |
| `background_blur` | Depth blur | General, electronics |
| `text_removal` | Clean label clutter | Food, beauty (Pro+) |
| `outline` | Product outline | Pro+ |
| `flat_lay` | Flat lay generation | Food, beauty, home |
| `ghost_mannequin` | Apparel ghost mannequin | Fashion |
| `virtual_model` | Virtual model | Fashion (Growth+) |
| `upscale` | AI upscale | Pro+ |
| `expand` | AI expand canvas | Pro+ |
| `uncrop` | AI uncrop | Agency |
| `ai_touchup` | Edit with AI | Agency |
| `service_hero` / `service_context` | AI backgrounds | Services & digital |

Selection is automatic from product name, tags, vision analysis, offering type, and plan tier.

---

## 3. Pipeline

```
Snap → vision analysis → select_plus_variants(product, analysis)
    → for each variant (until credits or cap):
        POST/GET image-api.photoroom.com/v2/edit
        → save studio_polish/{product_id}/{variant_id}_*.jpg
        → record_studio_polish (1 credit)
    → free Pillow promo frame from first hero
    → carousels / reels / posts use all images
```

No rembg fallback. Partial success is allowed (some variants may fail; successes are kept).

---

## 4. Key files

| File | Role |
|------|------|
| `apps/products/photoroom_plus.py` | Full Plus catalog + selection + API |
| `apps/products/photoroom_brand_template.py` | Phase D seller-locked shadow, padding, seed |
| `apps/products/photoroom_preflight.py` | Phase A preflight repair chain |
| `apps/products/photoroom.py` | Shared helpers, messages, save |
| `apps/products/photo_variations.py` | Multi-variant pack orchestration |
| `apps/billing/models.py` | Credits + `plus_max_variants_per_product` |
| `tests/test_photoroom_plus.py` | Variant selection tests |

---

## 5. Env & testing

Same as before — `PHOTOROOM_API_KEY`, Plus plan, `PHOTOROOM_SANDBOX` for local.

```bash
python scripts/test_photoroom_sandbox.py   # single studio call smoke test
pytest tests/test_photoroom_plus.py -q     # variant selection
```

Production: verify multiple `studio_polish/{id}/` URLs with different variant suffixes after Snap.
