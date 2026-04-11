# KOVA Visual Optimization Roadmap

## 5-Platform Strategy: Instagram · Facebook · LinkedIn · TikTok · Twitter/X

> **Goal**: Make every post look like it was made by a professional social media manager, for $2-21/month, without the user doing any work.

---

## Table of Contents

1. [Platform Priority Analysis](#platform-priority-analysis)
2. [Current State Assessment](#current-state-assessment)
3. [AI Image Models Analysis](#ai-image-models-analysis)
4. [AI Video Analysis & Decision](#ai-video-analysis--decision)
5. [Sprint 0: Foundation](#sprint-0-foundation)
6. [Sprint 1: Instagram — The Visual King](#sprint-1-instagram--the-visual-king)
7. [Sprint 2: LinkedIn — The PDF Carousel Moat](#sprint-2-linkedin--the-pdf-carousel-moat)
8. [Sprint 3: Facebook — Engagement Optimization](#sprint-3-facebook--engagement-optimization)
9. [Sprint 4: TikTok — Making It Actually Useful](#sprint-4-tiktok--making-it-actually-useful)
10. [Sprint 5: Twitter/X — Thread Intelligence](#sprint-5-twitterx--thread-intelligence)
11. [Sprint 6: Cross-Platform Intelligence](#sprint-6-cross-platform-intelligence)
12. [Sprint 7: WhatsApp Product Pipeline — The Wholesaler Play](#sprint-7-whatsapp-product-pipeline--the-wholesaler-play)
13. [Execution Priority Matrix](#execution-priority-matrix)
14. [What NOT To Build](#what-not-to-build)
15. [Cost Projections](#cost-projections)

---

## Platform Priority Analysis

### Demand Matrix (By Business Segment)

| Platform | Service SMBs | Retail/E-comm | Professional | Creators | B2B | **Weighted Score** |
|----------|:---:|:---:|:---:|:---:|:---:|:---:|
| **Instagram** | Critical | Critical | Important | Critical | Nice-to-have | **96** |
| **Facebook** | Critical | Critical | Important | Important | Important | **92** |
| **LinkedIn** | Nice-to-have | Nice-to-have | Critical | Nice-to-have | Critical | **68** |
| **TikTok** | Important | Important | Nice-to-have | Critical | Irrelevant | **58** |
| **Twitter/X** | Nice-to-have | Nice-to-have | Important | Important | Important | **52** |
| YouTube | Irrelevant | Nice-to-have | Nice-to-have | Critical | Nice-to-have | 38 |
| Pinterest | Nice-to-have | Important | Irrelevant | Nice-to-have | Irrelevant | 28 |
| Threads | Irrelevant | Nice-to-have | Nice-to-have | Nice-to-have | Irrelevant | 18 |
| Bluesky | Irrelevant | Irrelevant | Nice-to-have | Nice-to-have | Irrelevant | 12 |

*Weighted: Critical=5, Important=3, Nice-to-have=1, Irrelevant=0. Multiplied by segment size weight.*

### Platform Tiers

| Tier | Platforms | Action |
|------|-----------|--------|
| **Tier 1: Optimize First** | Instagram + Facebook + LinkedIn | 95% of business social media needs |
| **Tier 2: Optimize Next** | TikTok + Twitter/X | High demand from specific segments |
| **Tier 3: Maintenance** | YouTube, Pinterest, Threads, Bluesky | Keep working, don't invest |

### Platform Visual Format Requirements

#### Instagram
| Format | Aspect Ratio | Size | Engagement Rank |
|--------|-------------|------|----------------|
| Carousels | 4:5 | 1080×1350 | #1 (highest) |
| Reels | 9:16 | 1080×1920, 15-90s | #2 (highest reach) |
| Stories | 9:16 | 1080×1920 | #3 |
| Single image | 4:5 | 1080×1350 | #4 |

> **Death trap**: Instagram suppresses low-quality images. Below 1080px = reduced reach.

#### Facebook
| Format | Aspect Ratio | Size | Engagement Rank |
|--------|-------------|------|----------------|
| Reels | 9:16 | 1080×1920 | #1 |
| Video | 16:9 or 1:1 | 1280×720+ | #2 |
| Carousels | 1:1 | 1080×1080, 2-10 | #3 |
| Single image | 1.91:1 or 1:1 | 1200×630 or 1200×1200 | #4 |

#### LinkedIn
| Format | Aspect Ratio | Size | Engagement Rank |
|--------|-------------|------|----------------|
| Document carousels (PDF) | Any | 1080×1350 per page | #1 (3x engagement) |
| Single image | 1.91:1 or 1:1 | 1200×627 or 1200×1200 | #2 |
| Video | 16:9 or 1:1 | Up to 10min | #3 |

#### TikTok
| Format | Aspect Ratio | Size | Notes |
|--------|-------------|------|-------|
| Video | 9:16 | 1080×1920 | Primary format |
| Photo Mode | 9:16 | 1080×1920, up to 35 images | **Growing fast — our opportunity** |

> **Key insight**: TikTok Photo Mode carousel is getting massive organic reach in 2025-2026. Kova can serve this NOW without video.

#### Twitter/X
| Format | Aspect Ratio | Size | Notes |
|--------|-------------|------|-------|
| Single image | 16:9 or 1:1 | 1200×675 or 1200×1200 | Up to 4 images |
| Thread | N/A | 3-7 tweets | Text-first with optional images |

---

## Current State Assessment

### What Kova Already Has

| System | What It Does | Cost |
|--------|-------------|------|
| **FLUX.1-schnell** (Together/HF/Pollinations) | AI photo generation, 3-provider fallback | $0.00-0.005/image |
| **Pillow Graphics Engine** | Quote cards, tip graphics, stat highlights, CTA banners | $0.00 (CPU only) |
| **Carousel Generator** | 2-10 slide carousels via Pillow | $0.00 |
| **Visual Strategy System** | LLM picks the right visual type per post (6 strategies) | Built into Create Agent |
| **Platform-aware sizing** | 9 platform-specific resolutions | Built in |
| **Media Queue auto-crop** | Crops user-uploaded images to platform aspect ratio | Built in |
| **Brand fields on profile** | `brand_colors`, `visual_style`, `brand_logo_url` | Exists in DB |

### Capability Matrix (Current)

| Capability | IG | FB | LI | TT | X |
|-----------|:--:|:--:|:--:|:--:|:--:|
| Text content generation | ✅ | ✅ | ✅ | ✅ | ✅ |
| Platform-specific content style | ✅ | ✅ | ✅ | ✅ | ✅ |
| AI photo generation | ✅ 1080×1080 | ✅ 1200×630 | ✅ 1200×627 | ✅ 1080×1920 | ✅ 1200×675 |
| Branded Pillow graphics | ✅ | ✅ | ✅ | ✅ | ✅ |
| Carousel publishing | ✅ 2-10 imgs | ✅ Multi-photo | ❌ No PDF docs | ✅ Photo Mode | ❌ N/A |
| Carousel generation | ⚠️ 1:1 only | ⚠️ OK | ⚠️ PNG only | ⚠️ No 9:16 | N/A |
| Reels/Video publishing | ✅ Provider ready | ✅ Provider ready | ✅ Provider ready | ✅ Provider ready | N/A |
| Reels/Video generation | ❌ None | ❌ None | N/A | ❌ None | N/A |
| Brand colors in graphics | ⚠️ Colors only | ⚠️ Colors only | ⚠️ Colors only | ⚠️ Colors only | ⚠️ Colors only |
| Logo on graphics | ❌ | ❌ | ❌ | ❌ | ❌ |
| AI prompt per platform | ❌ Same for all | ❌ | ❌ | ❌ | ❌ |
| Visual strategy persistence | ❌ | ❌ | ❌ | ❌ | ❌ |
| Visual performance learning | ❌ | ❌ | ❌ | ❌ | ❌ |
| Per-tier image quality | ❌ All FLUX-schnell | ❌ | ❌ | ❌ | ❌ |

### Critical Gaps

1. **No `visual_strategy` field on Post model** — can't learn what works
2. **No PDF export for carousels** — LinkedIn carousels are PDFs, not images
3. **LinkedIn Documents API missing** — can't post carousel-style PDFs
4. **No platform-specific AI image prompt engineering** — same prompt everywhere
5. **Logo never rendered on graphics** — `brand_logo_url` field exists but unused
6. **Instagram carousels at 1:1** — should be 4:5 for maximum engagement
7. **Text platforms default to NO visual** — missing engagement boost on Twitter/LinkedIn/Facebook
8. **No thread generation** — Twitter threads mentioned but not structured

---

## AI Image Models Analysis

### Current Provider Chain

| Priority | Provider | Model | Cost | Notes |
|----------|----------|-------|------|-------|
| 1 | Together.ai | FLUX.1-schnell | $0.003/img | Paid tier |
| 2 | HuggingFace | FLUX.1-schnell | FREE | Rate-limited |
| 3 | Pollinations.ai | Configurable | ~$0.005/img | Fallback |

### Available Upgrade Models

| Model | Cost/Image | Quality | Speed | Best For |
|-------|-----------|---------|-------|----------|
| FLUX.1-schnell (current) | $0.003 | Good | 1-2s | Bulk generation |
| FLUX.1-dev | $0.01 | Better | 5-10s | Higher quality |
| FLUX.1-pro 1.1 | $0.04 | Excellent | 5-10s | Premium tier |
| Recraft V3 | $0.04 | Excellent (design) | 5s | Design graphics |
| Ideogram 2 | $0.04-0.08 | Excellent (text) | 5s | Text-in-image |
| GPT-Image (GPT-4o) | $0.02-0.07 | Excellent | 10s | Text + image |

### Recommended Per-Tier Routing

| Tier | Model | Cost | Quality Boost |
|------|-------|------|--------------|
| Starter ($2) | FLUX.1-schnell | $0.003 | Baseline |
| Growth ($7) | FLUX.1-dev | $0.01 | Better detail & coherence |
| Pro ($14) | FLUX.1-pro | $0.04 | Near-professional |
| Agency ($21) | FLUX.1-pro | $0.04 | Same + higher volume |

---

## AI Video Analysis & Decision

### Available Video Models

| Model | Cost/5s Clip | Quality | API Status |
|-------|-------------|---------|-----------|
| Minimax (Hailuo) | $0.15-0.25 | Good | Public |
| Luma Dream Machine | $0.15 | Good | Public |
| Kling 1.6 | $0.25-0.50 | Very Good | Public |
| Runway Gen-3 Alpha | $0.25 | Excellent | Public |
| Sora (OpenAI) | $0.75+ | Best | Limited |

### Economic Reality (Why We Don't Build This Now)

If 30% of posts include AI video (5s clips):

| Tier | Videos/mo | Cost @ $0.15/clip | Revenue | Video as % Revenue |
|------|----------|-------------------|---------|-------------------|
| Starter ($2) | 5 | $0.75 | $2 | **37.5%** — destroys margin |
| Growth ($7) | 18 | $2.70 | $7 | **38.6%** — unsustainable |
| Pro ($14) | 45 | $6.75 | $14 | **48.2%** — losing money |
| Agency ($21) | 100 | $15.00 | $21 | **71.4%** — bankrupt |

### Decision: NO AI Video Generation (for now)

**Instead, build motion graphics (Phase V3 future):**
- Ken Burns effect (zoom/pan on image) — FFmpeg, $0 cost
- Text reveal animations — FFmpeg, $0 cost
- Slideshow videos (carousel → video with transitions) — FFmpeg, $0 cost
- 70% of high-performing "video" on social media is exactly this format

**AI video reserved for future Pro/Agency tier** with hard limits (5-15/month) when unit economics improve.

---

## Sprint 0: Foundation

**Effort: 3-4 days | Cost impact: $0 | Affects all 5 platforms**

### 0A. Persist `visual_strategy` on Post Model

Add to `apps/content/models.py`:

```python
visual_strategy = models.CharField(
    max_length=30,
    choices=[
        ("ai_photo", "AI Photo"),
        ("quote_card", "Quote Card"),
        ("tip_graphic", "Tip Graphic"),
        ("stat_highlight", "Stat Highlight"),
        ("cta_banner", "CTA Banner"),
        ("carousel", "Carousel"),
        ("pdf_carousel", "PDF Carousel"),
        ("story_graphic", "Story Graphic"),
        ("none", "No Visual"),
    ],
    default="none",
    blank=True,
)
visual_metadata = models.JSONField(
    default=dict,
    blank=True,
    help_text="Slides count, graphic type, template style, etc.",
)
```

**Why**: Can't learn what works if we don't track what we generated.

### 0B. Brand Kit Completion

**What exists**: `brand_colors` (list), `visual_style` (choice field with 10 options), `brand_logo_url` (URL).

**What's missing**:
- Logo is never rendered on graphics
- `visual_style` is never injected into AI image prompts

**Build**:
- `graphics.py` → add logo watermark (bottom-right, 60px, semi-transparent) on all Pillow graphics
- `media.py` → inject `visual_style` into AI image prompt as style prefix
- Onboarding: "Upload your logo and pick brand colors" (simple form)

### 0C. Platform-Specific AI Image Prompt Engineering

**Current**: Same `image_prompt` string goes to FLUX for every platform.

**Build**: Inject platform-specific suffixes before sending to AI:

```python
PLATFORM_PROMPT_SUFFIX = {
    "instagram": "vibrant, eye-catching, social media style, centered composition, high contrast",
    "facebook":  "warm, relatable, community feel, lifestyle photography style",
    "linkedin":  "professional, clean, corporate editorial, subtle tones, business context",
    "tiktok":    "bold, energetic, vertical composition, youth-oriented, trending aesthetic",
    "twitter":   "striking, minimal, high-impact single subject, editorial",
}
```

### 0D. Per-Tier Image Model Routing

Route by `profile.plan` in `generate_post_image()`:

```python
TIER_IMAGE_MODELS = {
    "starter": ("black-forest-labs/FLUX.1-schnell", 0.003),
    "growth":  ("black-forest-labs/FLUX.1-dev", 0.01),
    "pro":     ("black-forest-labs/FLUX.1-pro-1.1-ultra", 0.04),
    "agency":  ("black-forest-labs/FLUX.1-pro-1.1-ultra", 0.04),
}
```

---

## Sprint 1: Instagram — The Visual King

**Effort: 5-6 days | Cost impact: $0 (Pillow) | Highest ROI**

Instagram is the #1 platform where visuals determine reach. If we nail Instagram, users stay.

### 1A. Upgrade All Instagram Dimensions to 4:5

**Why**: Instagram feed shows 4:5 images larger than 1:1 — more screen real estate, higher engagement. Every professional social media manager uses 4:5.

**Changes across files**:

| File | Current | New |
|------|---------|-----|
| `graphics.py` CANVAS_SIZES | `"instagram": (1080, 1080)` | `"instagram": (1080, 1350)` |
| `media.py` PLATFORM_IMAGE_SIZES | `"instagram": (1080, 1080)` | `"instagram": (1080, 1350)` |
| `carousel.py` Instagram override | Forces 1080×1080 | Forces 1080×1350 |
| `image_utils.py` PLATFORM_CROPS | `"instagram": (1, 1)` | `"instagram": (4, 5)` |
| `image_utils.py` PLATFORM_MAX_SIZE | `"instagram": (1080, 1080)` | `"instagram": (1080, 1350)` |

### 1B. Carousel Template System

**Current**: Solid color gradient + text. Basic.

**Build 4 carousel templates** (selected based on `visual_style`):

| Template | Style | Best For |
|----------|-------|----------|
| **Clean** | Minimal, whitespace, light backgrounds | Professional services, coaches |
| **Bold** | High contrast, large text, vivid colors | Retail, fitness, food |
| **Educational** | Numbered steps, progress indicator dots | How-tos, tutorials |
| **Story** | Narrative arc, emotional color gradient | Personal brands, storytelling |

Structure per carousel:
1. **Hook slide** — bold statement, large text, branded colors
2. **Content slides** — alternating background shades, visual variety
3. **CTA slide** — "Save this post · Follow @brand for more"

### 1C. Instagram Visual Strategy Weighting

Add platform-specific weights to the Create Agent's visual strategy prompt:

```
Instagram preferred visual mix:
- carousel: 50% (highest engagement format)
- ai_photo: 25% (variety)
- quote_card: 15% (shareable)
- tip_graphic: 10% (saveable)
```

### 1D. Hashtag Strategy Engine

Build into Create Agent:
- Generate 15-20 hashtags per post: 5 high-volume + 5 medium + 5 niche + 5 brand-specific
- Store in `Post.metadata["hashtags"]`
- Append to caption on publish (after main content)
- Analyst Agent tracks which hashtags correlate with higher reach

### 1E. Story-Ready Graphics (9:16)

New visual strategy: `story_graphic`
- 1080×1920 canvas (Pillow-rendered, $0)
- Full-screen branded graphic with large text + CTA
- Publish via existing `_publish_story()` Instagram provider
- Same dimensions serve TikTok natively

---

## Sprint 2: LinkedIn — The PDF Carousel Moat

**Effort: 4-5 days | Cost impact: $0 | Biggest competitive differentiator**

LinkedIn PDF document carousels get **3x the engagement** of single images. No SMB AI tool generates these. This is a genuine moat with zero marginal cost.

### 2A. PDF Carousel Generator

Extend `carousel.py` — Pillow natively supports multi-image PDF export:

```python
def generate_pdf_carousel(post, slides, **kwargs) -> str:
    # 1. Generate slides as PIL Images (existing code)
    # 2. Convert to PDF
    images[0].save(pdf_path, "PDF", save_all=True, append_images=images[1:])
    # 3. Save as MediaAttachment with file_type="document"
```

**Dimensions**: 1080×1350 (4:5) — optimal for LinkedIn document rendering.

### 2B. LinkedIn Documents API Provider

Add `_upload_document()` to `linkedin.py`:

1. `POST /rest/documents?action=initializeUpload` → get upload URL
2. `PUT` binary PDF to upload URL
3. Include document URN in post payload with `content.media.id`

Same pattern as the existing Video API (initialize → upload → reference).

### 2C. Carousel Content Structure for LinkedIn

Add to Create Agent's LinkedIn prompt:

```
LinkedIn carousel structure:
1. Hook slide — "X things about Y that nobody talks about"
2. 3-7 content slides — one key insight per slide, large readable text
3. Evidence slide — a data point, stat, or quote that reinforces
4. CTA slide — "Agree? Share with your network" + author name/title
```

### 2D. Professional LinkedIn Templates

| Template | Look | Best For |
|----------|------|----------|
| **Thought Leader** | Dark background, clean white text, slide numbers | Consultants, executives |
| **Data-Driven** | Stats emphasis, accent color highlights, charts | Analysts, B2B |
| **Story Arc** | Problem → journey → solution → lesson → CTA | Founders, career changers |

---

## Sprint 3: Facebook — Engagement Optimization

**Effort: 3-4 days | Cost impact: $0**

Facebook is already well-served. These optimizations increase engagement rate.

### 3A. Link Preview Workaround

**Problem**: Facebook suppresses link posts vs native content. But businesses need to share links.

**Solution**: When content includes a URL:
1. Generate a branded image (quote card or stat graphic) from the content
2. Post as **photo + caption with link in text** instead of bare link
3. 2-3x more reach than a link preview card

Create Agent detects link-sharing intent → chooses visual strategy accordingly.

### 3B. Facebook Multi-Photo Carousel Optimization

- Create Agent generates 3-5 related images for Facebook carousel posts
- Each image: different angle on the same topic
- Structure: hook image → detail images → CTA image
- Uses existing Facebook multi-photo publishing (already implemented)

### 3C. Engagement-Optimized Formatting

Sharpen PLATFORM_GUIDES for Facebook:
- End every post with a **genuine open question** (not "agree?")
- Short paragraph breaks for mobile readability
- First line = hook (only first 3 lines visible before "See more")
- Strategic emoji use (1-2 max as paragraph separators, not walls)

### 3D. Event/Offer Graphics (Future)

- Detect "event" or "sale" keywords in content seeds
- Generate event-card style graphics (date, location, CTA)
- Extend existing CTA_BANNER with event-specific layout

---

## Sprint 4: TikTok — Making It Actually Useful

**Effort: 5-6 days | Cost impact: $0**

TikTok Photo Mode is the secret weapon — massive organic reach for educational carousel content.

### 4A. TikTok Photo Mode Carousel Optimization

**Current**: TikTok Photo Mode supported but carousels generate at wrong dimensions.

**Build TikTok-specific carousels at 1080×1920 (9:16 vertical)**:

| Template | Style | Notes |
|----------|-------|-------|
| **Full-Screen Text** | Bold text, vivid colors, one statement per slide | Highest engagement |
| **Swipe Tips** | Numbered, progress dots at top | Educational content |
| **Story Arc** | Narrative with emotional color gradient | Storytelling |

- Slide count: 5-10 (TikTok allows 35 but engagement drops after 10)
- Auto-add music option via TikTok API's `auto_add_music` parameter

### 4B. TikTok Visual Strategy Weighting

```
TikTok preferred visual mix:
- carousel/photo_mode: 60% (highest engagement on TikTok)
- ai_photo: 20% (single image posts)
- quote_card: 10%
- tip_graphic: 10%
```

### 4C. TikTok Caption Optimization

Sharpen Create Agent prompt:
- First 150 chars visible before "more" — **hook must be there**
- 3-5 targeted hashtags (not 20)
- CTA: "Follow for more [topic]" / "Save this" / "Part 2?"
- Tone: raw, authentic, educational — not corporate

### 4D. Motion Graphics Foundation (Phase V3 Prep)

Prepare infrastructure without building renderers:
- Add `motion_quote`, `slideshow_video` to visual strategy choices
- Add `video` file_type support in MediaAttachment
- Add FFmpeg/MoviePy to requirements
- When V3 ships → TikTok, Instagram Reels, Facebook Reels all unlock simultaneously

---

## Sprint 5: Twitter/X — Thread Intelligence

**Effort: 3-4 days | Cost impact: $0**

Twitter is Kova's strongest text platform. The gap is thread structure and visual enhancement.

### 5A. Smart Thread Generation

Create Agent generates structured threads:

```
thread_tweets: [
    "Hook tweet — strongest statement, stops the scroll",
    "Context/story — why this matters",
    "Key insight #1",
    "Key insight #2",
    "Key insight #3",
    "CTA — 'If this was helpful, repost the first tweet'"
]
```

- 3-7 tweets per thread
- Publish as threaded replies via existing Twitter provider
- First tweet = standalone hook (works even if people don't read the thread)

### 5B. Twitter Visual Enhancement

**Change**: Twitter should get visuals 40-50% of the time (currently defaults to `none`):

```
Twitter preferred visual mix:
- none: 50% (text-first platform)
- ai_photo: 25% (tweets with images get 150% more engagement)
- quote_card: 15% (shareable quote graphics)
- stat_highlight: 10% (data-driven posts)
```

### 5C. Twitter Image Dimension Optimization

| Content Type | Dimension | Ratio | Why |
|-------------|-----------|-------|-----|
| AI photos | 1200×675 | 16:9 | Looks photographic |
| Quote cards, stats | 1200×1200 | 1:1 | More vertical real estate on mobile |

### 5D. Twitter Engagement Patterns

Enhance Create Agent instructions:
- **Self-reply context**: Post main tweet, then reply with supporting detail
- **Quote-tweet format**: When repurposing from other platforms
- **Poll-style framing**: Two opposing viewpoints to drive replies

---

## Sprint 6: Cross-Platform Intelligence

**Effort: 4-5 days | Cost impact: $0 | After Sprints 1-5**

This is where Kova becomes a genuine BIOS — the system learns and optimizes.

### 6A. Visual Strategy Analytics

Using the `visual_strategy` field from Sprint 0:
- Track engagement per strategy per platform per user
- Analyst Agent reports: "Your Instagram carousels get 3.2x more saves than single images"
- Daily brief includes visual performance data

### 6B. Automatic Strategy Shifting

- If carousels outperform for a user → increase carousel ratio (50% → 70%)
- If quote cards underperform on LinkedIn → reduce and shift to PDF carousels
- Create Agent reads analytics and adjusts visual strategy weights dynamically

### 6C. Content Repurposing Intelligence

- LinkedIn PDF carousel insight → extract hook → Twitter quote card
- Instagram carousel → rework into TikTok Photo Mode (adjust dimensions + tone)
- One content idea → 5 platform-optimized outputs with platform-native visuals

---

## Sprint 7: WhatsApp Product Pipeline — The Wholesaler Play

**Effort: 6-8 days | Cost impact: $0 (Pillow + existing infra) | Unlocks 30,000+ Nairobi merchants**

### The Market Reality

In Nairobi — Gikomba, Eastleigh, Kamukunji, Luthuli, downtown — tens of thousands of wholesalers run their businesses through WhatsApp groups. Their daily grind:

1. Take 10-30 product photos (shoes, clothes, electronics, kitchen items)
2. Crop badly in WhatsApp, maybe add a price sticker
3. Write caption: "New arrival! Size 37-42. DM for wholesale price. Min 12 pieces"
4. Copy-paste to 5-20 WhatsApp groups, one by one
5. Get flooded with DMs: "Bei?" "Iko size 40?" "Delivery to Mombasa?" — same questions 200 times
6. Repeat daily, 3-4 sessions per day

### The Pain Points

| Pain | Severity | Frequency |
|------|----------|----------|---|
| Posting 30 photos one-by-one to 15 groups | Extreme | Daily |
| Writing product descriptions | High | Daily |
| Answering "bei gani?" 200 times | Extreme | All day |
| Bad product photos (poor lighting, clutter) | High | Every post |
| No catalog — customers only see group chat | High | Constant |
| No tracking (what sold vs didn't) | Medium | Weekly |
| Getting blocked/muted for over-posting | High | Regularly |
| No brand identity — looks like every other wholesaler | Medium | Always |

### The Critical Constraint

**WhatsApp Cloud API does NOT support group posting.** Meta deliberately blocks this. We cannot build "auto-post to 20 WhatsApp groups."

**But that's not the right solution anyway.** Spam-posting bots in groups → users get muted faster → groups die → everyone loses.

### The 10x Reframe

Instead of: *"Help them post to WhatsApp groups faster"*

Think: *"Turn 30 raw phone photos into a professional, branded multi-platform product campaign in 2 minutes — with WhatsApp groups as just ONE distribution channel"*

### 7A. Batch Product Photo Upload & Enhancement

Extend existing `apps/products/`:

- Multi-photo upload (10-30 images at once)
- Auto-crop, enhance brightness/contrast per image
- Optional background removal by tier:
  - **Starter**: Pillow contrast enhancement + branded price tag overlay ($0)
  - **Growth+**: `rembg` library (open source, CPU) → clean white/branded background ($0)
  - **Pro+**: AI product descriptions generated from image content (existing LLM)
- User confirms/edits, sets wholesale and retail prices
- Each photo saved as product with name, description, pricing, sizes

### 7B. Product Catalog Grid Image (The Killer Feature)

**A single Pillow-rendered image showing 4-8 products in a branded grid:**

```
┌──────────────────────────────────────┐
│    KAMAU SHOES — New Arrivals        │  ← Brand header (brand colors)
├──────────┬──────────┬────────────────┤
│  [Shoe]  │  [Shoe]  │    [Shoe]      │
│ KES 800  │ KES 950  │   KES 700      │
├──────────┼──────────┼────────────────┤
│  [Shoe]  │  [Shoe]  │    [Shoe]      │
│ KES 600  │ KES 850  │   KES 750      │
├──────────┴──────────┴────────────────┤
│  📱 0712 345 678                      │
│  🔗 kovaagent.com/l/kamau-shoes      │  ← Kova Link
└──────────────────────────────────────┘
```

**One image. Share to all 15 groups. Professional. Branded. Has prices. Has contact. Has catalog link.**

This is a new Pillow graphic type (`product_grid`) — uses the existing graphics engine. $0 cost.

Variants:
- **Grid 2×2** (4 products) — for WhatsApp/Instagram square
- **Grid 2×3** (6 products) — for Instagram 4:5
- **Grid 2×4** (8 products) — for TikTok/Stories 9:16
- **Single product showcase** — one product, large photo, specs, price

### 7C. WhatsApp-Optimized Content Generation

AI generates copy-paste-ready WhatsApp text from the product batch:

```
🆕 NEW ARRIVALS — Today Only!

👟 Leather Loafers
   Sizes: 38-44
   Wholesale: KES 800/pair (min 6)
   Retail: KES 1,200

👟 Canvas Sneakers
   Sizes: 36-43
   Wholesale: KES 450/pair (min 12)
   Retail: KES 750

📦 Delivery: Nairobi same-day, upcountry 2-3 days
📱 Order: 0712-345-678
🔗 Full catalog: kovaagent.com/l/kamau-shoes
```

- Formatted with emojis and line breaks that render well in WhatsApp
- Bilingual: Swahili/Sheng/English based on user preference
- Includes contact info and Kova Link for full catalog
- One tap to copy to clipboard → paste into WhatsApp groups

### 7D. WhatsApp Status Content Queue

WhatsApp Status is the **underrated weapon** — viewed more than IG Stories in Kenya, free, all contacts see it, 24-hour urgency.

Generate daily Status content pipeline:

| Time | Content Type | Format |
|------|-------------|--------|
| 6-8 AM | "New stock alert" — top products montage | 1080×1920 (9:16) |
| 12-1 PM | Individual product showcase | 1080×1920 |
| 6-9 PM | "Last pieces" urgency graphic | 1080×1920 |

- Uses same 9:16 Pillow templates as TikTok Photo Mode (shared engine)
- One-tap share via `whatsapp://send` deep link with pre-loaded media
- Reuses same Status dimensions for Instagram Stories cross-posting

### 7E. Product Catalog Link Page

Extend existing `apps/links/` link-in-bio system for wholesalers:

- **Product grid view** — customers browse all products with photos, prices, sizes
- **WhatsApp order button** — "Order via WhatsApp" opens chat with pre-filled message:
  `"Hi, I want to order [Product Name], size [X], quantity [Y]"`
- **Category filtering** — shoes, bags, electronics, etc.
- **Stock status** — available / low stock / sold out
- **Share button** — generates shareable link for groups
- **No login required** — customers browse anonymously

This turns the Kova Link page into a **mini e-commerce catalog** that the wholesaler shares once per group. Customers bookmark it. No more "bei gani?" for every item.

### 7F. Multi-Platform Output From One Product Batch

15 product photos uploaded → Kova generates everything:

| Platform | Output | Format |
|----------|--------|--------|
| **WhatsApp groups** | Catalog grid image + formatted text | 1:1 grid + copy-paste text |
| **WhatsApp Status** | Daily product showcases (3/day) | 9:16 vertical |
| **Instagram** | Product carousel (4:5 branded slides) | 1080×1350 carousel |
| **Facebook** | Multi-photo post with descriptions | 1200×1200 images |
| **TikTok** | Photo Mode slideshow (9:16 vertical) | 1080×1920, 5-10 slides |
| **Kova Link** | Full browsable catalog page | Responsive web |

**One upload session → all channels populated.**

### Target Market Size

| Segment | Nairobi Count | Avg Monthly Revenue | KES 299-999/mo Willingness |
|---------|--------------|--------------------|--------------------------|
| Clothes/shoe wholesalers (Gikomba, Eastleigh) | 15,000+ | KES 50K-500K | High |
| Electronics dealers (Luthuli, downtown) | 5,000+ | KES 100K-1M | High |
| Kitchen/home wholesalers (Kamukunji) | 3,000+ | KES 30K-300K | Medium |
| Beauty/cosmetics | 5,000+ | KES 20K-200K | High |
| Food suppliers (Wakulima, Marikiti) | 2,000+ | KES 50K-500K | Medium |
| Auto parts (Kirinyaga Road) | 2,000+ | KES 100K-1M | Medium |
| **Total Nairobi** | **30,000+** | | |

- Scale to Mombasa, Kisumu, Nakuru, Eldoret: **multiply by 3x** (90,000+)
- Scale to Dar es Salaam, Kampala, Kigali: **multiply by 5x** (150,000+)
- At KES 299/month average: **KES 9M/month revenue opportunity** from Nairobi alone

### The User Journey (A Gikomba Wholesaler)

**Day 1: Sign up**
1. Signs up for Kova Starter (KES 299/month)
2. Connects Instagram + Facebook
3. Creates Kova Link page (kovaagent.com/l/kamau-shoes)

**Day 2: First product batch**
1. Opens Kova, taps "Add Products"
2. Takes 15 photos of shoes
3. Kova enhances all photos, generates descriptions and prices
4. Kova creates: catalog grid image + IG carousel + FB post + WhatsApp text
5. Auto-posts to IG and FB
6. Shares catalog grid image + text to WhatsApp groups (manual share, content is ready)
7. Shares Kova Link in group description: "See all our products here"

**Week 1: Results**
- Instagram: Getting follows from Nairobi buyers
- Facebook: Orders through Messenger
- WhatsApp groups: People clicking catalog link → ordering via WhatsApp
- WhatsApp Status: Daily fresh content driving DMs

**Month 1: Upgrades to Growth (KES 999)**
- Adds LinkedIn (for B2B wholesale clients)
- Gets background removal on product photos
- AI generates daily product posts automatically from catalog

### What Makes This Uniquely Kova

| Competitor | What they do | What Kova does differently |
|-----------|-------------|---------------------------|
| **Canva** | User designs product posts manually | AI generates everything from raw photos automatically |
| **WATI/Respond.io** | WhatsApp message routing | AI-generated product content + multi-platform distribution |
| **Jumia/Jiji** | Marketplace listing | Kova keeps the wholesaler as the brand, not the marketplace |
| **Google Business** | Static business listing | Dynamic daily product catalog with AI descriptions |
| **WhatsApp Business app** | Manual catalog feature | Auto-enhanced photos, AI descriptions, multi-platform output |

**Nobody takes 15 raw phone photos and turns them into a branded multi-platform product campaign in 2 minutes.** That's the category.

### Integration With Visual Roadmap Sprints

| Visual Sprint | Product Pipeline Phase | Overlap |
|---|---|---|
| Sprint 0 (Foundation) | 7A (Batch upload) | Brand Kit benefits both |
| Sprint 1 (Instagram) | 7B (Catalog grid) | Pillow engine shared |
| Sprint 2 (LinkedIn) | 7C (WhatsApp text) | Independent — can parallel |
| Sprint 4 (TikTok) | 7D (Status queue) | Same 9:16 format as TikTok |
| Sprint 6 (Intelligence) | 7E (Catalog link) | Analytics shared |

**Recommendation**: Start 7B (catalog grid image) during Sprint 0 — it's a new Pillow graphic type, uses the same engine, and immediately serves the wholesaler segment.

---

## Execution Priority Matrix

| Sprint | Days | Cost | User Impact | Revenue Impact |
|--------|------|------|-------------|----------------|
| **Sprint 0** (Foundation) | 3-4 | $0 | Medium — better images everywhere | Enables everything |
| **Sprint 1** (Instagram) | 5-6 | $0 | **Highest** — #1 platform | Reduces churn |
| **Sprint 2** (LinkedIn) | 4-5 | $0 | **High** — unique feature, no competitor has it | Attracts B2B (highest ARPU) |
| **Sprint 3** (Facebook) | 3-4 | $0 | Medium — polish, not fix | Broad SMB satisfaction |
| **Sprint 4** (TikTok) | 5-6 | $0 | **High** — makes TikTok viable | Young business owners, creators |
| **Sprint 5** (Twitter) | 3-4 | $0 | Medium — threads are the win | Thought leaders, tech |
| **Sprint 6** (Intelligence) | 4-5 | $0 | **Highest long-term** — system gets smarter | Retention moat |
| **Sprint 7** (WhatsApp Product Pipeline) | 6-8 | $0 | **Highest for Kenya** — 30K+ merchants | New market segment |
| **TOTAL** | **33-42** | **$0** | | |

### Recommended Build Order

```
Sprint 0 (Foundation) → Sprint 2 (LinkedIn PDF) → Sprint 1 (Instagram) → Sprint 7 (WhatsApp Products) → Sprint 4 (TikTok) → Sprint 3 (Facebook) → Sprint 5 (Twitter) → Sprint 6 (Intelligence)
```

**Why LinkedIn before Instagram**: LinkedIn PDF carousels are 3-4 days, zero cost, highest engagement format, and no competitor does it. Ship the moat fast.

**Why WhatsApp Products before TikTok**: The wholesaler segment is a massive addressable market (30K+ in Nairobi alone) with high willingness to pay. The catalog grid image and batch upload use existing Pillow infrastructure. And it makes Kova immediately relevant to a segment that no AI social media tool currently serves.

---

## What NOT To Build

| Feature | Why Not |
|---------|---------|
| **Full Canva editor** | Users don't want to design. They want it done automatically. An editor adds complexity that makes users leave. |
| **AI video generation** | $0.15-0.50/video destroys margins at every tier. Motion graphics (FFmpeg) handles 70% of video needs at $0. |
| **Text-to-video from scratch** | Too expensive, unpredictable quality, platforms detect and suppress. |
| **Real-time video rendering** | Queue-based async is fine for scheduled posts. |
| **Platform-specific video editors** | No TikTok editor, no Reels editor. We generate, they publish. |
| **AI music generation** | Use curated royalty-free library. Music AI adds cost and legal risk. |
| **User-facing prompt editing** | Don't expose AI prompts. Visual strategy selection is enough. A salon owner doesn't want to "engineer prompts." |
| **YouTube optimization** | Without video generation, YouTube is a shell. Park until motion graphics (V3) ships. |
| **Threads/Bluesky investment** | Low business adoption. Keep providers alive, don't optimize. |

---

## Cost Projections

### Cost Per User Per Month (After All Sprints)

| Component | Starter ($2) | Growth ($7) | Pro ($14) | Agency ($21) |
|-----------|-------------|-------------|-----------|-------------|
| LLM text generation | $0.05 | $0.15 | $0.30 | $0.50 |
| AI images (per-tier model) | $0.05 | $0.30 | $1.60 | $3.00 |
| Pillow graphics (templates) | $0.00 | $0.00 | $0.00 | $0.00 |
| PDF carousels | $0.00 | $0.00 | $0.00 | $0.00 |
| Motion videos (future) | $0.00 | $0.00 | $0.00 | $0.00 |
| R2 storage | $0.00 | $0.01 | $0.02 | $0.05 |
| Product photo processing | $0.00 | $0.00 | $0.00 | $0.00 |
| Background removal (rembg) | — | $0.00 | $0.00 | $0.00 |
| **Total COGS** | **$0.10** | **$0.46** | **$1.92** | **$3.55** |
| **Gross Margin** | **95%** | **93%** | **86%** | **83%** |

### Key Takeaway

All 6 sprints cost **$0 in new API expenses**. Everything is Pillow graphics (free), prompt engineering (free), PDF export (free), and smarter routing. The only incremental cost is per-tier image model routing (Sprint 0D), offset by higher-tier pricing.

---

## The Category We're Creating

Every existing tool says "here's an editor, now design it yourself" (Canva) or "here's an AI image, hope it's good" (most AI tools).

**Kova's category: "Visuals that optimize themselves."**

The system generates the right format, for the right platform, in your brand style, learns what performs, and shifts strategy automatically. The user connects accounts, approves posts, and watches results.

A salon owner in Nakuru posts "New braiding styles" and gets:
- Instagram: 4:5 branded carousel (4 slides with product photos + branded frames)
- Facebook: engagement-optimized photo post with open question
- LinkedIn: PDF document carousel with professional template
- TikTok: 9:16 Photo Mode slideshow (bold text, swipe-through)
- Twitter: quote card graphic + threaded breakdown

A shoe wholesaler in Gikomba uploads 15 product photos and gets:
- WhatsApp: branded catalog grid image + formatted text ready to paste
- WhatsApp Status: 3 daily product showcases (9:16 vertical)
- Instagram: product carousel with prices and order CTA
- Facebook: multi-photo product post
- TikTok: Photo Mode product slideshow
- Kova Link: full browsable catalog with WhatsApp order buttons

All automatic. All branded. All platform-native. All for $2-21/month.

**That's a BIOS.**

---

*Document created: April 11, 2026*
*Status: Planning — Sprint 0 next*
