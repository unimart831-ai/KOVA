# Media Provider Capability Audit

**Purpose:** Full capability scan of Photoroom, Bannerbear, and Remotion before campaign-factory development.  
**Principle:** Kova = marketing intelligence · Vendors = pixel/video execution.  
**Related:** [MEDIA_API_SETUP.md](./MEDIA_API_SETUP.md) · [KOVA_BUILD_CHECKLIST.md](./KOVA_BUILD_CHECKLIST.md)

Last updated: 2026-06-23

---

## Executive summary

| Provider | Kova role | Owns | Does NOT own |
|----------|-----------|------|--------------|
| **[Photoroom](https://www.photoroom.com/api)** | Image production infrastructure | Cutout, relight, scenes, apparel, food, 1→N image variants | Carousel story, reel strategy, CTAs |
| **[Bannerbear](https://www.bannerbear.com/product/image-generation-api/)** | Carousel slide renderer (optional) | Template-based branded slides from Kova JSON | Campaign logic, slide copy strategy |
| **FFmpeg** (in-house) | Reel assembler v1 | Ken Burns, xfade, music, text burn-in | — |
| **[Remotion](https://www.remotion.dev/docs/api)** | Reel assembler v2 (planned) | Programmatic React video, captions, motion typography | Image enhancement |
| **Fal/Kling** (existing) | Premium motion clip add-on | AI image-to-video | Default $10 plan reels |

```
Campaign (Kova Brain)
    │
    ├─ slide copy / hook / CTA / scene order  ← ALWAYS KOVA
    │
    ├─ Photoroom  → image assets (5/campaign cap)
    ├─ Bannerbear → carousel pixels (from Kova slide JSON)
    ├─ FFmpeg     → reel MP4 (default)
    └─ Remotion   → reel MP4 (v2 quality upgrade)
```

---

## 1. Photoroom

**Docs:** [photoroom.com/api](https://www.photoroom.com/api) · [docs.photoroom.com](https://docs.photoroom.com/)

### 1.1 API products (billing units)

| API | Plan | Endpoint | Billing note |
|-----|------|----------|--------------|
| **Remove Background** | Basic | `POST sdk.photoroom.com/v1/segment` | 1 Basic call |
| **Image Editing** | Plus | `POST image-api.photoroom.com/v2/edit` | **1 Plus call = 5 Basic calls** ([docs](https://docs.photoroom.com/)) |
| **Video / Animate** | Enterprise | `POST image-api.photoroom.com/v1/animate` | Separate video pricing |
| **Visual QA** | Enterprise | Analyze QA API | Audit + auto-fix at scale |

Auth: `x-api-key` header on every request. Sandbox: prefix key with `sandbox_` for free watermarked tests.

### 1.2 Full capability matrix (marketing site + docs)

| Capability | What it does | API / feature | Kova status | Kova module |
|------------|--------------|---------------|-------------|-------------|
| Background removal | Cutout, transparency | Basic + Plus | **Live** | `photoroom_basic.py`, Plus cutout |
| PhotoFix | Lighting, brightness, recolor | Plus `photofix` variant | **Live** | `photoroom_photofix.py`, `photoroom_plus.py` |
| Reposition / smart crop | Centering, padding, marketplace specs | Plus positioning params | **Live** | `photoroom_plus.py`, `PHOTOROOM_SMART_CROP_PADDING` |
| Product Beautifier | Restore detail, color, quality | Plus `beautify` | **Live** | `photoroom_plus.py` |
| AI Relight | Subject relighting | Plus `relight` | **Live** | `photoroom_plus.py` |
| AI Backgrounds | Scene generation | Plus `background.*` / AI scenes | **Live** | Scene packs in `photoroom_plus.py` |
| AI Shadows | Realistic shadows | Plus `shadow.*` | **Live** | `PHOTOROOM_DEFAULT_SHADOW` |
| AI Expand / Uncrop | Outpaint frame | Plus expand | **Live** | variant catalog |
| Edit With AI | Lifestyle staging, angles | Plus `editWithAI` | **Live** | `PHOTOROOM_EDIT_WITH_AI_*` |
| Flat Lay | Top-down editorial | Plus `flatLay` | **Live** | `flat_lay` variant |
| Ghost Mannequin | Apparel invisible mannequin | Plus `ghostMannequin` | **Live** | `ghost_mannequin` variant |
| Virtual Model | On-model apparel | Plus `virtualModel` | **Partial** | Gated `PHOTOROOM_VIRTUAL_MODEL_ENABLED=False` |
| Product Staging | Commerce scenes | Plus staging prompts | **Live** | `build_commerce_scene_prompt()` |
| Photo Composition | Multi-product hero | Composition API | **Live** | `photoroom_composition.py` |
| AI Text Removal | Remove text on product | Plus | **Live** | food/apparel variants |
| Channel exports | IG/Story/banner sizes | Plus export params | **Live** | `PHOTOROOM_CHANNEL_EXPORTS_*` |
| Marketplace export | Google Shopping white-bg | Plus | **Live** | `PHOTOROOM_MARKETPLACE_*` |
| **Image to Video** | 3–7s MP4 from 1 image | `v1/animate` | **Partial** | `photoroom_video.py` — off by default |
| **Analyze QA** | Crop/ratio/text/bg audit + fix | Enterprise Visual QA | **Not started** | — |
| Uncertainty score | Segmentation confidence | Response header | **Live** | `photoroom_api.py`, guard skips bad cutouts |

### 1.3 What Photoroom must NOT do in Kova

- **Carousels** — no hook/problem/solution/CTA story model
- **Reel strategy** — animate is a single-image wiggle, not multi-scene narrative
- **Platform copy** — no brand voice or conversion logic

Use Photoroom **Image to Video** only as:
- Optional single-hero commerce clip
- Fallback before FFmpeg when 1 polished product frame exists  
Never as the primary reel engine for campaign bundles.

### 1.4 Implementation pattern (current + target)

**Current flow (Snap):**

```
upload → preflight/PhotoFix → category detect → Plus variant pack (3–7 scenes)
      → save to R2 → MediaPlan on BusinessAsset
```

**Target flow (per Campaign):**

```python
# Kova orchestrator sends a CAMPAIGN BRIEF, not ad-hoc calls
brief = {
    "scenes": ["studio_white", "lifestyle_cafe", "promo_offer"],  # max 5
    "brand": resolve_brand_dna(user),
    "product_category": "fashion",
    "aspect_ratios": ["1:1", "9:16"],
}
urls = photoroom_execute_brief(hero_image_url, brief)  # wraps photo_variations + plus
```

**Key files to extend:**

| File | Change |
|------|--------|
| `apps/media/orchestrator.py` | Accept campaign brief; enforce 5-scene cap |
| `apps/products/photo_variations.py` | Entry from campaign, not only Snap |
| `apps/products/photoroom_plus.py` | Map `CampaignSceneSpec` → variant IDs |
| `apps/billing/visual_credits.py` | Debit per campaign, not unbounded Snap |

**Env (production minimum):**

```bash
PHOTOROOM_API_KEY=...
PHOTOROOM_SANDBOX=False
PHOTOROOM_BASIC_API_KEY=...          # optional cost routing
PHOTOROOM_VIDEO_ENABLED=False      # keep off on $10 plan
VISUAL_ENHANCE_ENABLED=True
```

**Cost guardrail (@ KES 1,300 / 30 campaigns):** ~5 Plus calls × 30 = 150 calls/user/mo → monitor pool `PHOTOROOM_MONTHLY_POOL`.

### 1.5 Photoroom gaps to implement

| Priority | Feature | Why |
|----------|---------|-----|
| P1 | Campaign-scoped brief API wrapper | Stop duplicate logic Snap vs Create |
| P2 | Visual QA (Enterprise) pre-publish | Aligns with QA engine — audit before show user |
| P3 | Virtual Model for fashion vertical | High conversion for boutiques |
| P4 | Video animate behind add-on flag | "Cinematic clip" upsell only |

---

## 2. Bannerbear

**Docs:** [Image API](https://www.bannerbear.com/product/image-generation-api/) · [Video API](https://www.bannerbear.com/product/video-generation-api/) · [Templates](https://www.bannerbear.com/templates/)

### 2.1 Products

| Product | API | Use in Kova |
|---------|-----|-------------|
| **Image Generation** | `POST /v2/images` | Carousel slides |
| **Multi Image** | Batch variants | A/B carousel sizes |
| **Video Generation** | `POST /v2/videos` | **Not integrated** — evaluate vs Remotion |
| **PDF Generation** | PDF API | Future: price lists, menus |
| **Template editor** | Dashboard | Design once → API modifications forever |

### 2.2 How Bannerbear works

1. Design template in editor — each layer = named object (`title`, `photo`, `cta`, …)
2. Kova POSTs modifications:

```javascript
// From Bannerbear docs — same pattern we use in Python
const image = await bb.create_image(TEMPLATE_ID, {
  modifications: [
    { name: "headline", text: "5 Mistakes Killing Your Sales" },
    { name: "photo", image: "https://cdn.../hero.jpg" },
  ]
});
```

3. Async poll or `sync: true` → `image_url`

**Kova implementation:** `apps/media/bannerbear_client.py` → `render_template()`, `build_product_carousel_slides()`

### 2.3 Kova status

| Capability | Status | Notes |
|------------|--------|-------|
| Product carousel (cover + features + CTA) | **Live** | Needs 3 template UIDs in env |
| Educational carousel (hook/problem/…) | **Not started** | Need new templates per funnel |
| Offer / FAQ carousels | **Not started** | Template library + slide JSON from Create Agent |
| Video API | **Not started** | Overlaps Remotion — pick one for v2 |
| Webhooks (image completed) | **Not started** | Could replace polling in Celery |
| Auto-resize long text | **Bannerbear native** | Use for Swahili/English long product names |

### 2.4 Implementation pattern (target)

**Kova owns the story JSON:**

```json
{
  "campaign_id": "...",
  "carousel_type": "educational",
  "slides": [
    {"role": "hook", "headline": "...", "subhead": "..."},
    {"role": "problem", "body": "..."},
    {"role": "solution", "body": "...", "image": "photoroom_url"},
    {"role": "proof", "stat": "87%", "caption": "..."},
    {"role": "cta", "cta": "Order on WhatsApp", "price": "KES 2,500"}
  ]
}
```

**Bannerbear renders pixels:**

```python
# apps/media/carousel_bridge.py (extend)
def render_carousel_from_spec(spec: CarouselSpec, dna: BrandDNA) -> list[str]:
    template_map = {
        "hook": settings.BANNERBEAR_TEMPLATES["carousel_hook"],
        "problem": settings.BANNERBEAR_TEMPLATES["carousel_body"],
        "cta": settings.BANNERBEAR_TEMPLATES["carousel_cta"],
    }
    urls = []
    for slide in spec.slides:
        tpl = template_map[slide["role"]]
        mods = dna.bannerbear_modifications(**slide)
        urls.append(render_template(tpl, mods))
    return urls
```

**Fallback:** `apps/agents/carousel.py` (Pillow) — always works, no API cost.

### 2.5 Templates to create (pre-development)

| Template UID env var | Slide role | Sizes |
|---------------------|------------|-------|
| `BANNERBEAR_TEMPLATE_COVER` | Hook / product cover | 1080×1080 |
| `BANNERBEAR_TEMPLATE_SLIDE` | Body / feature | 1080×1080 |
| `BANNERBEAR_TEMPLATE_CTA` | CTA + price | 1080×1080 |
| `BANNERBEAR_TEMPLATE_HOOK` | Educational hook | 1080×1080 (new) |
| `BANNERBEAR_TEMPLATE_BODY` | Problem/solution text | 1080×1080 (new) |
| `BANNERBEAR_TEMPLATE_STORY` | 1080×1920 story frame | (new) |

Start from [Template Library](https://www.bannerbear.com/templates/) — filter Instagram Post / Carousel / Story.

### 2.6 Bannerbear vs Pillow vs HTML renderer

| Approach | Pros | Cons | When |
|----------|------|------|------|
| **Bannerbear** | Fast, designer-friendly, proven API | Per-render cost, template maintenance | v1 carousels at scale |
| **Pillow (current fallback)** | Free, in-process | Limited typography/motion | Offline, Starter, API down |
| **HTML + Playwright** | Full brand control | Build + host renderer service | v2 if Bannerbear limits hit |

**Decision:** Bannerbear for v1 campaign carousels; keep Pillow fallback; defer HTML renderer.

### 2.7 Bannerbear Video API — use or skip?

[Video Generation API](https://www.bannerbear.com/product/video-generation-api/) generates short branded videos from templates (text + image modifications).

| | Bannerbear Video | Remotion | FFmpeg (current) |
|--|------------------|----------|------------------|
| Input | Template + mods | React composition + props | Images + plan |
| Text animation | Template-limited | Full (`@remotion/captions`) | Basic drawtext |
| Cost | Per video credit | Infra (CPU/RAM) | Free |
| Kova fit | Quick branded bumps | **Best for reel factory** | **Current default** |

**Decision:** Do **not** add Bannerbear Video now. Standardize reels on **FFmpeg → Remotion**; keep Photoroom animate as optional 1-frame clip.

---

## 3. Remotion

**Docs:** [API overview](https://www.remotion.dev/docs/api) · [Configuration](https://www.remotion.dev/docs/config) · [remotion.dev](https://www.remotion.dev/)

**Status in Kova:** Not integrated. Reels use `apps/content/video_compose.py` (FFmpeg).

### 3.1 What Remotion is

Programmatic video via **React components**:

- `useCurrentFrame()` + `interpolate()` for motion
- `<Composition>` defines width, height, fps, duration
- `npx remotion render` or **`@remotion/renderer` SSR** → MP4
- Optional: [`@remotion/cloudrun`](https://www.remotion.dev/docs/lambda) for serverless render (not on Lambda for custom FFmpeg overrides)

> Config file (`remotion.config.ts`) applies to CLI only — **not SSR APIs** ([docs](https://www.remotion.dev/docs/config)).

### 3.2 Relevant packages for Kova reel factory

| Package | Purpose |
|---------|---------|
| `@remotion/renderer` | Headless render from Django/Celery worker |
| `@remotion/captions` | Karaoke-style text overlays from reel director copy |
| `@remotion/media-utils` | Audio duration, metadata |
| `@remotion/transitions` | Scene transitions (fade, slide, wipe) |
| `@remotion/elevenlabs` | Optional VO (future) |
| `@remotion/cloudrun` / Lambda | Scale renders off Railway worker |

### 3.3 Remotion vs FFmpeg (current)

| Capability | FFmpeg (`video_compose.py`) | Remotion |
|------------|----------------------------|----------|
| Ken Burns / pan zoom | **Live** | Easy |
| Crossfade / xfade | **Live** (12 transitions) | `@remotion/transitions` |
| Hook text overlays | Basic PIL burn-in | Animated typography |
| Scene-synced captions | Limited | `@remotion/captions` |
| Brand components | Hard-coded | React + Tailwind + Brand DNA tokens |
| Railway deploy | FFmpeg in worker image | Node + Chromium bundle (~heavy) |
| Render time | Fast | Slower first bundle, cache helps |

### 3.4 Recommended integration architecture

**Phase 1 (now):** Keep FFmpeg — ship campaign factory on $10 plan.

**Phase 2 (Remotion):** Separate render package in monorepo:

```
kova_agent/
├── media_render/                 # NEW — Remotion project
│   ├── remotion.config.ts
│   ├── src/
│   │   ├── Root.tsx
│   │   ├── compositions/
│   │   │   ├── ProductReel.tsx      # story_arc recipe
│   │   │   ├── ServiceTransform.tsx # before/after
│   │   │   └── OfferFlash.tsx
│   │   └── lib/brand-tokens.ts      # from Campaign JSON
│   └── package.json
└── apps/content/
    └── remotion_bridge.py         # NEW — subprocess or HTTP to render service
```

**Input contract (from `reel_director.py`):**

```json
{
  "recipe": "story_arc",
  "fps": 30,
  "width": 1080,
  "height": 1920,
  "scenes": [
    {"role": "hook", "duration_sec": 2, "image": "https://...", "text": "New arrival 🔥"},
    {"role": "hero", "duration_sec": 3, "image": "https://..."},
    {"role": "cta", "duration_sec": 2, "text": "Shop now", "price": "KES 4,500"}
  ],
  "audio": "/static/audio/reel-beds/upbeat/sunrise-drive.mp3",
  "brand": {"primary": "#10B981", "font": "Plus Jakarta Sans"}
}
```

**Render invocation options:**

| Option | Pros | Cons |
|--------|------|------|
| **A. Subprocess** `npx remotion render` on Celery worker | Simple | Node+Chrome on Railway worker |
| **B. Sidecar service** | Isolated memory/CPU | Extra Railway service |
| **C. Remotion Cloud Run** | Scales | Cost + no custom FFmpeg override |

**Recommendation:** Start with **B** — `media-render` Railway service, HTTP POST `/render` with `ReelComposePlan` JSON, returns MP4 URL to R2.

### 3.5 Remotion config essentials

From [remotion.config.ts docs](https://www.remotion.dev/docs/config):

```ts
import { Config } from '@remotion/cli/config';

Config.setConcurrency(4);
Config.setCodec('h264');
Config.setCrf(18);                    // quality vs size
Config.overrideWidth(1080);
Config.overrideHeight(1920);
Config.setChromiumOpenGlRenderer('angle');
```

SSR render uses `@remotion/renderer` `renderMedia()` — config passed per render call, not from `remotion.config.ts`.

### 3.6 Licensing

Remotion requires a [company license](https://www.remotion.dev/docs/commercial) for teams >3 or revenue thresholds. Budget ~$100–500/mo when commercial license applies — still cheaper than unlimited Kling.

---

## 4. In-house: FFmpeg reel engine (current default)

**Module:** `apps/content/video_compose.py` + `apps/content/reel_director.py`

| Feature | Status |
|---------|--------|
| 1080×1920 H.264 | Live |
| Ken Burns zoom/pan | Live |
| xfade transitions (12 types) | Live |
| Music bed from `static/audio/reel-beds/` | Live |
| Safe zones (IG/TikTok UI) | Live |
| `compose_from_plan(ReelComposePlan)` | Live |
| Text overlays | Basic |

**Wiring:** `content.compose_reel_video` Celery task → director → FFmpeg (after Kling/Photoroom optional attempts).

**Keep as:** Default reel backend for KES 1,300 plan until Remotion service ships.

---

## 5. Fal / Kling (reference — not in scope of this audit)

Already integrated: `apps/media/fal_client.py`, `reel_bridge.py`.  
**Policy:** Premium add-on only — not part of base 30 campaigns economics.

---

## 6. Master implementation map

### By campaign output (v1 bundle)

| Output | Intelligence (Kova) | Execution (vendor) | Module |
|--------|---------------------|-------------------|--------|
| Image variants (≤5) | Scene brief from asset + Brand DNA | Photoroom Plus | `orchestrator`, `photo_variations` |
| Carousel (5–6 slides) | Slide JSON funnel | Bannerbear → Pillow fallback | `carousel_bridge`, `carousel.py` |
| Reel | `ReelComposePlan` | FFmpeg → Remotion v2 | `reel_director`, `video_compose` |
| Story frames | Story copy | Pillow or Bannerbear 9:16 template | TBD |
| Feed post image | Uses Photoroom hero | — | Create Agent |
| QA gate | `blueprint_quality_score` + future Visual QA | Photoroom Analyze QA (enterprise) | `blueprint_retry.py` |

### Pre-development checklist (providers)

#### Photoroom
- [ ] Production Plus API key on Railway (no sandbox)
- [ ] Confirm monthly pool vs 30 campaigns × 5 scenes × users
- [ ] Basic API key for white-bg routing (cost save)
- [ ] Keep `PHOTOROOM_VIDEO_ENABLED=False` on base plan
- [ ] Document which Plus variants are in default campaign pack per category

#### Bannerbear
- [ ] Create account + API key
- [ ] Design 6 templates (cover, slide, cta, hook, body, story)
- [ ] Set all `BANNERBEAR_TEMPLATE_*` env vars
- [ ] Test `build_product_carousel_slides()` with public R2 URLs
- [ ] Add educational carousel template map to `carousel_bridge.py`

#### Reels (FFmpeg now, Remotion later)
- [ ] Verify FFmpeg on Celery worker (`ffmpeg -version`)
- [ ] Audit reel bed music licensing
- [ ] Spike: `media_render/` Remotion package + one composition
- [ ] Decide render sidecar vs subprocess
- [ ] Commercial Remotion license when team revenue qualifies

#### Storage (blocker)
- [ ] R2 public URLs for all vendor inputs (Photoroom/Bannerbear need HTTPS)

---

## 7. Architecture decisions (locked)

| # | Decision |
|---|----------|
| 1 | Photoroom = **100% of image production** — no in-house cutout/scene models |
| 2 | Photoroom ≠ carousels ≠ reels (marketing structure always Kova) |
| 3 | Bannerbear = **carousel pixel renderer** v1; Pillow = fallback |
| 4 | FFmpeg = **default reel** on $10 plan |
| 5 | Remotion = **reel quality upgrade** v2 — not blocking campaign factory |
| 6 | Bannerbear Video = **skip** — overlap with Remotion, less control |
| 7 | Photoroom Video animate = **optional single-hero clip** only |
| 8 | Kling = **paid add-on** — never unlimited on base plan |
| 9 | Max **5 Photoroom scenes per campaign** — economics guardrail |
| 10 | All vendor calls go through `apps/media/orchestrator.py` — no stray API calls from views |

---

## 8. Suggested development order

1. **Orchestrator campaign brief** — single entry for Photoroom scene packs  
2. **CarouselSpec JSON** — Create Agent → Bannerbear bridge  
3. **Template setup** — Bannerbear editor (1 day design work)  
4. **FFmpeg reel** — wire `ReelComposePlan` to campaign approval card  
5. **Visual credits** — per-campaign debit aligned with KES 1,300 pricing  
6. **Remotion spike** — parallel track, swap when quality wins A/B test  

---

## 9. External links

| Provider | URL |
|----------|-----|
| Photoroom API | https://www.photoroom.com/api |
| Photoroom docs | https://docs.photoroom.com/ |
| Photoroom Image Editing (Plus) | https://docs.photoroom.com/image-editing-api-plus-plan/ |
| Photoroom Video API | https://docs.photoroom.com/video-api-enterprise-plan/overview |
| Bannerbear Image API | https://www.bannerbear.com/product/image-generation-api/ |
| Bannerbear Video API | https://www.bannerbear.com/product/video-generation-api/ |
| Bannerbear templates | https://www.bannerbear.com/templates/ |
| Remotion docs | https://www.remotion.dev/docs/api |
| Remotion config | https://www.remotion.dev/docs/config |

---

## 10. Kova file index (media stack)

```
apps/media/
  orchestrator.py          # Central brain → vendor routing
  asset_intelligence.py    # Format recommendations
  brand_dna.py             # Shared tokens → all APIs
  bannerbear_client.py     # Carousel render
  carousel_bridge.py       # Bannerbear ↔ local fallback
  reel_bridge.py           # Kling only
  router.py                # Plan gates (update for single $10 plan)
  content_types.py         # MediaPlan enums

apps/products/
  photoroom_plus.py        # Full Plus variant catalog
  photoroom_video.py       # v1/animate (optional)
  photo_variations.py      # Snap scene packs
  phororoom_*.py           # Feature modules

apps/content/
  reel_director.py         # Reel storyboard JSON
  video_compose.py         # FFmpeg assembly
  tasks.py                 # compose_reel_video

apps/agents/
  carousel.py              # Pillow carousel fallback
```

---

*Changelog: 2026-06-23 — Initial provider audit for pre-campaign-factory development.*
