# KOVA Photoroom Strategy

Cross-links: [Photoroom upgrade.md](Photoroom%20upgrade.md) · [VISUAL_ENHANCEMENT_SPEC.md](VISUAL_ENHANCEMENT_SPEC.md) · [PLAN_V2_SPEC.md](PLAN_V2_SPEC.md) · [KOVA_PLANS_GUIDE.md](KOVA_PLANS_GUIDE.md)

---

## Executive summary

Photoroom is KOVA's **revenue-adjacent visual engine**: it turns stall-phone photos into listing-ready, carousel-ready, reel-ready assets in Snap and Batch Snap. KOVA already implements a **mature Plus (v2/edit) integration** — preflight repair, brand templates, 30+ variant catalog, channel exports, uncertainty gating — but **does not use Basic API** for cost optimization, lacks **Google Shopping–specific exports**, and keeps **alteration-prone features** (virtual model, beautifier) gated or disabled.

**Strategic bet:** Double down on **consistent brand backgrounds + shadows + white-bg marketplace exports** for mitumba/retail and food vendors; add **market-day presets** for Batch Snap; route **simple cutouts to Basic API**; enable **human-in-the-loop review** for apparel AI before go-live.

---

## Part 1 — Photoroom API capability map

### Plans & billing

| Plan | Endpoint | Credit model |
|------|----------|--------------|
| **Basic** | `POST https://sdk.photoroom.com/v1/segment` | 1 credit per call |
| **Plus** | `POST/GET https://image-api.photoroom.com/v2/edit` | **1 Plus call = 5 Basic credits** |
| **Video (Enterprise)** | `POST https://image-api.photoroom.com/v1/animate` | Separate enterprise pricing |

Docs: [Introduction](https://docs.photoroom.com/) · [Image Editing Quickstart](https://docs.photoroom.com/image-editing-api-plus-plan/quickstart-guide) · [Remove Background (Basic)](https://docs.photoroom.com/remove-background-api-basic-plan/) · [OpenAPI Reference](https://docs.photoroom.com/getting-started/api-reference-openapi)

### Feature map

| Feature | Plus params (summary) | Alteration risk |
|---------|----------------------|-----------------|
| Background removal | `removeBackground=true` | Low |
| HD removal | HD mode (see [HD Background Removal](https://docs.photoroom.com/image-editing-api-plus-plan/hd-background-removal)) | Low |
| Static background | `background.color=HEX` | Low |
| AI Backgrounds | `background.prompt`, `background.seed`, `background.expandPrompt` | Low–medium |
| Background blur | `background.blur.mode`, `background.blur.radius` (no cutout) | Low |
| AI Shadows | `shadow.mode` (`ai.soft`, `ai.hard`, `ai.floating`, overrides) | Low |
| AI Relight | `lighting.mode` (`ai.auto`, `ai.preserve-hue-and-saturation`, `ai.optimize-portrait`) | Medium (color) |
| AI Expand / Uncrop | `expand.mode`, `uncrop.mode` | Medium (generates pixels) |
| Smart crop / positioning | `segmentation.prompt`, `padding*`, `scaling`, `outputSize`, alignments | Low |
| Flat Lay | `flatLay.mode`, `flatLay.prompt`, `flatLay.size` | Medium (apparel AI) |
| Ghost Mannequin | `ghostMannequin.mode`, `ghostMannequin.prompt` | Medium |
| Virtual Model | `virtualModel.*` presets | **High** |
| Product staging | Edit With AI / staging prompts | Medium–high |
| AI Beautifier | `beautify.mode` (`ai.auto`, `ai.food`, `ai.car`) | **High** |
| Edit With AI | `editWithAI.mode`, `editWithAI.prompt`, `editWithAI.seed` | **High** |
| Create Any Image | text-to-image on Plus | **High** |
| AI Text Removal | `textRemoval.mode` | Medium |
| AI Ironing | apparel wrinkle removal | Medium |
| AI Upscale | `upscale.mode` | Medium |
| Sandbox | `sandbox_` key prefix / sandbox mode | Free, watermarked |
| Metadata / DPI | `export.format`, `export.dpi`, PNG alpha | Configurable |
| Uncertainty | Response header `x-uncertainty-score` | Diagnostic |

### SMB use-case tutorials (Photoroom docs)

| Use case | Doc section | Typical param combo |
|----------|-------------|---------------------|
| Second-hand marketplaces | [Second-hand marketplaces](https://docs.photoroom.com/) | White bg + soft shadow + consistent padding |
| E-commerce brand consistency | [E-commerce brand guidelines](https://docs.photoroom.com/) | Locked bg color/seed, shadow mode, output size |
| Food delivery | [Food delivery brand guidelines](https://docs.photoroom.com/) | Branded surface, `beautify.mode=ai.food`, relight |
| Google Shopping compliance | [Google Shopping compliant images](https://docs.photoroom.com/) | Pure white (#FFFFFF), product ≥75% frame, no text |
| Clothing/apparel | [Clothing and apparel listings](https://docs.photoroom.com/) | Ghost mannequin, flat lay, virtual model + human QA |
| Selfie generator | [Selfie generator](https://docs.photoroom.com/) | Virtual model / portrait relight |

---

## Part 2 — KOVA current usage

### Endpoints called

| Endpoint | Used? | Module |
|----------|-------|--------|
| **Plus v2/edit** | ✅ Primary | `apps/products/photoroom_plus.py`, `photoroom.py` |
| **Basic v1/segment** | ❌ Not called (legacy comment in `visual_enhance.py` routes to Plus) | — |
| **Video v1/animate** | ⚠️ Partial | `apps/products/photoroom_video.py` (sandbox/default off) |

### Features enabled (params sent)

Core studio: `removeBackground`, `background.color`, `shadow.mode=ai.soft`, `padding`, `outputSize=1080x1080`, `scaling=fill`, `referenceBox=originalImage`, `export.format=jpeg`.

AI: `background.prompt` + `background.seed` + `pr-ai-background-model-version`, `background.expandPrompt=ai.auto`, `lighting.mode=ai.auto`, `beautify.mode` (category-mapped), `textRemoval.mode`, `flatLay.*`, `ghostMannequin.*`, `virtualModel.*`, `editWithAI.*`, `expand.mode` / `uncrop.mode`, `upscale.mode`, `background.blur.*`, `outline.*`, `segmentation.prompt=product`.

Brand: `UserProfile.photoroom_brand_template` → shadow/padding/seed/outline via `photoroom_brand_template.py`.

Safety: `x-uncertainty-score` probe; skips `ghost_mannequin`, `virtual_model`, `flat_lay` when score ≥ 0.6.

### UX integration points

| Surface | Flow | Source tag |
|---------|------|------------|
| **Snap to Sell** | Vision → expand task → scene pack | `commerce_source="snap"` |
| **Batch Snap / Market Day** | Per-item vision + polish + stall finalize | `commerce_source="batch_snap"` |
| **Product catalog** | Manual expand, studio polish | `"manual"` |
| **Carousels / posts** | Polished URLs in `additional_images`; slide-role ordering | `photoroom_plus.py` |
| **Reels** | Prefers `channel_story`; optional Photoroom animate | `content/tasks.py` |
| **Batch composition hero** | Multi-product grid + AI polish | `photoroom_composition.py` |
| **Virtual model** | Separate view, flag off | `photoroom_virtual_models.py` |
| **Admin** | Pool usage, variant catalog | `/dashboard/commerce/photoroom/` |

### Plan limits / metering

From `apps/billing/models.py` → `PLAN_LIMITS`:

| Tier | `visual_enhancements_per_month` | `plus_max_variants_per_product` |
|------|--------------------------------|--------------------------------|
| Starter | 8 | 3 |
| Growth | 30 | 5 |
| Pro | 100 | 7 |
| Agency | 150 | 10 |

Platform pool: `PHOTOROOM_MONTHLY_POOL=5000`, reserve 500; Growth throttled when pool >80% (`visual_credits.py`).

### Error handling & sandbox

- User-facing fallbacks: original photo kept (`studio_polish_failure_message`)
- API errors: variant skipped; minimal studio fallback; local quick polish
- Sandbox: key prefix `sandbox_`, daily 100 / monthly 1000 cache limits
- Partial success allowed; credits debited per successful API call

### Tests

| File | Coverage |
|------|----------|
| `tests/test_photoroom_api.py` | Uncertainty, sandbox quota, beautify modes |
| `tests/test_photoroom_plus.py` | Variant selection, commerce prompts, slide roles |
| `tests/test_photoroom_preflight.py` | Repair plan, quality triggers |
| `tests/test_photoroom_brand_template.py` | Brand template application |
| `tests/test_photoroom_commerce_features.py` | PhotoFix on snap/batch |
| `scripts/test_photoroom_sandbox.py` | Manual sandbox script |

---

## Part 3 — Capability matrix (Photoroom × KOVA)

| Photoroom feature | KOVA status | Notes |
|-------------------|-------------|-------|
| Background removal | **Used** | All studio variants |
| HD removal | **Not used** | Standard cutout only |
| Static background | **Used** | `studio_white`, `studio_brand`, `studio_dark` |
| AI Backgrounds | **Used** | Lifestyle + commerce scenes |
| Background blur | **Used** | `background_blur` variant |
| AI Shadows | **Used** | Default `ai.soft`; brand template overrides |
| AI Relight | **Used** | Preflight + `relight` variant |
| AI Expand / Uncrop | **Partial** | Channel exports + preflight; not user-selectable |
| Smart crop / positioning | **Used** | Preflight + layout styles |
| Flat Lay | **Partial** | Catalog + category boost; gated by uncertainty |
| Ghost Mannequin | **Partial** | Auto-selected for apparel; gated by uncertainty |
| Virtual Model | **Partial** | Code complete; **flag disabled** |
| Product staging | **Partial** | Via Edit With AI prompts |
| AI Beautifier / PhotoFix | **Used** | Preflight + `beautify` variant |
| Edit With AI | **Used** | `edit_ai_staging`, `edit_ai_angle` (Growth+) |
| Create Any Image | **Not used** | Planned Phase E |
| AI Text Removal | **Partial** | Preflight + Pro tier |
| AI Ironing | **Not used** | — |
| AI Upscale | **Used** | Preflight repair |
| Video animate | **Partial** | Sandbox only |
| Sandbox mode | **Used** | Dev + quota tracking |
| export.dpi / metadata | **Not used** | JPEG only, no DPI |
| Google Shopping preset | **Not used** | White studio exists but not compliance-tuned |
| Basic API routing | **Not used** | All calls are Plus-priced |
| Batch API | **Not used** | ThreadPoolExecutor locally |
| Human-in-the-loop QA | **Partial** | Uncertainty skip only; no review UI |

---

## Gap analysis — ranked opportunities

| Opportunity | Photoroom feature | KOVA integration | Tier | Effort | Value | Segment fit |
|-------------|-------------------|------------------|------|--------|-------|-------------|
| **1. Brand-locked listing pack** | Static bg + AI shadow + brand seed | Default Snap output = `studio_brand` hero first; enforce template | Plus | S | **Very high** | Mitumba, retail, salon product lines |
| **2. Google Shopping export** | White bg + padding + size | New `channel_marketplace` variant 1000×1000 PNG | Plus | S | **Very high** | E-commerce, marketplace vendors |
| **3. Market Day preset** | PhotoFix + brand bg + composition | Batch Snap stall template in `batch_snap_intelligence` | Plus | M | **Very high** | Market vendors, mitumba tables |
| **4. Food delivery branded bg** | AI bg + `ai.food` beautify | Restaurant category preset pack | Plus | M | **High** | Restaurants, caterers |
| **5. Apparel ghost mannequin pack** | Ghost mannequin + flat lay | Enable for fashion test users + review queue | Plus | M | **High** | Fashion/mitumba clothing |
| **6. Basic API cutout routing** | v1/segment | Route "white bg only" exports to Basic | Basic | M | **High** (margin) | All tiers at scale |
| **7. Human review for alteration features** | Virtual model, beautify, Edit With AI | Post-expand review step before publish | Plus | M | **High** (trust) | Apparel, agency |
| **8. Relight color-safe mode** | `ai.preserve-hue-and-saturation` | Product preflight relight | Plus | S | Medium | Electronics, cosmetics |
| **9. AI Ironing for apparel** | AI Ironing | Preflight for wrinkled garment snaps | Plus | S | Medium | Mitumba, boutique |
| **10. Video animate in prod** | v1/animate | Enable for Pro+ with credit cap | Enterprise | L | Medium | Reels-first sellers |

### Segment notes

- **Mitumba/retail:** Brand consistency + white-bg marketplace export + Batch Snap preset; avoid virtual model until QA.
- **Salon:** Service variants (`service_hero`, `service_context`) already strong; add before/after relight + blur.
- **Restaurant:** Food beautify + marble/table scenes; branded delivery-app-style backgrounds.
- **Marketplace vendor:** Google Shopping PNG + consistent square feed; M-Pesa shop link on promo frame (already local).
- **Agency:** Brand template per client, higher credit pools, virtual model with approval workflow.

---

## 90-day implementation roadmap

### Phase 1 — Days 0–30: "Look like a real shop"

- Make **brand studio hero default** in Snap (not optional alternate).
- Add **`channel_marketplace`** export: 1000×1000 white, 85% fill, PNG option.
- **Market Day preset** in Batch Snap: shared stall bg color + PhotoFix always + composition hero.
- Tune relight to **`ai.preserve-hue-and-saturation`** for product categories.
- Document operator runbook in admin Photoroom tab.

### Phase 2 — Days 31–60: "Sell on more channels"

- **Restaurant / food preset pack** (3 locked AI surface prompts + food beautify).
- **Apparel pilot:** enable ghost mannequin for Pro+ with **review-before-publish** flag.
- **Basic API router** for cutout-only exports (internal cost dashboard).
- Enable **new shadow model** header (`pr-ai-shadows-model-version: 2026-04-15`) A/B on studio variants.
- Credit UX: show "X of Y polish credits" per Snap with scene breakdown.

### Phase 3 — Days 61–90: "Scale & agency"

- **Virtual model** GA behind human approval + African scene presets (`market_scene` already mapped).
- **Create Any Image** for promo/sale banners (Agency tier, 2/mo cap).
- Photoroom **batch API** evaluation for CSV catalog import.
- **Video animate** for Pro+ (separate credit bucket or 1 polish = 3 animate).
- AI Ironing in apparel preflight chain.

---

## API key / env / billing recommendations (Plan v2 aligned)

### Env vars (existing + proposed)

| Variable | Purpose |
|----------|---------|
| `PHOTOROOM_API_KEY` | Production Plus key |
| `PHOTOROOM_SANDBOX` | Dev watermarked calls |
| `PHOTOROOM_MONTHLY_POOL` / `PHOTOROOM_POOL_RESERVE` | Platform cap |
| `PHOTOROOM_MONTHLY_COST_USD` | Cost attribution (~$0.10/image at 5000 pool) |
| `PHOTOROOM_BRAND_TEMPLATE_ENABLED` | Locked seller styling |
| `PHOTOROOM_PREFLIGHT_ENABLED` | Repair-before-scenes |
| `PHOTOROOM_CHANNEL_EXPORTS_ENABLED` | Story/banner |
| **Proposed:** `PHOTOROOM_BASIC_API_KEY` | Separate Basic key for cutout-only |
| **Proposed:** `PHOTOROOM_MARKETPLACE_EXPORT_ENABLED` | Google Shopping preset |
| **Proposed:** `PHOTOROOM_REVIEW_ALTERATIONS` | Human QA gate |

### Billing model recommendations

1. Keep **1 KOVA credit = 1 Plus API call** (simple seller mental model).
2. Add **"marketplace export"** as 0 extra credits when bundled in scene pack (same API call, different params).
3. Introduce **Basic routing** internally: 5 Basic calls ≈ 1 Plus — do not expose Basic to sellers.
4. Separate **video credits** on Pro+ (e.g. 5 animate/mo) to avoid draining polish pool.
5. Fix audit finding L4: ensure **preflight + probe + channel** all debit correctly (already mostly implemented via per-call `record_studio_polish`).

---

## Photoroom doc links (quick index)

- [Introduction & plan comparison](https://docs.photoroom.com/)
- [Image Editing API (Plus)](https://docs.photoroom.com/image-editing-api-plus-plan/quickstart-guide)
- [Remove Background API (Basic)](https://docs.photoroom.com/remove-background-api-basic-plan/)
- [AI Shadows](https://docs.photoroom.com/image-editing-api-plus-plan/ai-shadows)
- [AI Relight](https://docs.photoroom.com/image-editing-api-plus-plan/ai-relight)
- [Flat Lay](https://docs.photoroom.com/image-editing-api-plus-plan/flat-lay)
- [Ghost Mannequin](https://docs.photoroom.com/image-editing-api-plus-plan/ghost-mannequin)
- [Virtual Model](https://docs.photoroom.com/image-editing-api-plus-plan/virtual-model)
- [Edit With AI](https://docs.photoroom.com/image-editing-api-plus-plan/edit-with-ai)
- [Sandbox Mode](https://docs.photoroom.com/image-editing-api-plus-plan/sandbox-mode)
- [HD Background Removal](https://docs.photoroom.com/image-editing-api-plus-plan/hd-background-removal)
- [Video API](https://docs.photoroom.com/video-api-enterprise-plan/overview)
- [OpenAPI Reference](https://docs.photoroom.com/getting-started/api-reference-openapi)

---

## Key codebase references

`apps/products/photoroom.py`:

```python
PHOTOROOM_EDIT_URL = "https://image-api.photoroom.com/v2/edit"
```

`apps/billing/visual_credits.py`:

```python
def record_studio_polish(user, *, product_id, provider: str = "photoroom_plus", output_data: dict | None = None) -> None:
    """Debit one studio polish credit per Photoroom API call."""
```

`apps/billing/models.py` (Starter tier excerpt):

```python
"visual_enhancements_per_month": 8,
"plus_max_variants_per_product": 3,
```
