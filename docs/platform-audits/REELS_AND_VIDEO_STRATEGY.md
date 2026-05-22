# Reels, Video & Visual Design — Strategy Brainstorm

> **Context:** Facebook (and IG/TikTok) Reels are the #1 organic reach format. Feed posts are Kova’s strength today; this doc decides **how** to close the Reels gap without breaking unit economics.  
> **Last updated:** May 2026  
> **Related:** `FACEBOOK.md`, `VISUAL_OPTIMIZATION_ROADMAP.md`, `apps/agents/graphics.py`, `apps/content/image_gen.py`

---

## The decision in one sentence

**Don’t build AI-generated video or a Canva clone. Build a Product → Motion Reel pipeline (FFmpeg + templates + licensed music) and wire it to Meta’s Reels publish API.**

---

## What Meta actually allows (constraints first)

| Capability | Facebook Reels API | Implication for Kova |
|------------|-------------------|----------------------|
| Upload Reels (9:16 video file) | ✅ Graph API | We must **produce an MP4**, not just an image |
| Add Meta’s trending music | ❌ Not via third-party API | Cannot replicate “use this trending sound” like the native app |
| Add stickers, polls, AR | ❌ | Out of scope |
| Music baked into uploaded file | ✅ If **we have rights** to the track | **Our library or user upload** |
| Publish feed video | ✅ `/{page-id}/videos` | Simpler path — wire existing `publish_video` first |
| Reels vs feed video | Different endpoints / fields | IG has `_publish_reels`; FB Reels need dedicated path (verify Graph v25 docs) |

**Music reality:** Trending audio is a native-app advantage. Kova’s answer is **curated royalty-free beds** + optional user upload — not Chart hits.

---

## How SMBs actually make Reels (jobs to be done)

| Job | What they do today | Tools they use |
|-----|-------------------|----------------|
| **Product showcase** | 3–5 product shots, price, “DM to order” | CapCut, Canva, phone camera |
| **Tip / education** | Bold hook text + 3 bullet points | Canva templates |
| **Before/after** | 2-image swipe or quick cut | CapCut |
| **Testimonial / quote** | Text on background + voice or music | Canva |
| **Behind-the-scenes** | Raw phone video + captions | CapCut auto-caption |
| **Promo / sale** | “50% off this week” motion graphic | Canva |

**Pattern:** 70%+ of high-performing SMB Reels are **motion graphics**, not cinematic AI video — slideshow + text + music + light Ken Burns.

This matches what we already decided in `VISUAL_OPTIMIZATION_ROADMAP.md` (Phase V3 motion, not AI video).

---

## Five approaches — scored for Kova

### A. Motion Reels from existing visuals (recommended core)

**How it works:**
1. Create Agent outputs **reel script** (hook line, 3–5 beats, CTA) — already partially in prompts
2. Visual layer picks strategy: `product_slideshow` | `tip_reel` | `quote_motion` | `carousel_to_video`
3. **FFmpeg compositor** (new `apps/content/video_compose.py`):
   - Input: images from FLUX / Pillow / product photos
   - Ken Burns pan/zoom per slide (2–4s each)
   - Text overlays (Pillow or drawtext) — hook in first 1.5s
   - Optional logo from `brand_logo_url`
   - Audio bed from licensed library
   - Output: 1080×1920 MP4, 15–45s, H.264
4. Publish via `FacebookProvider.publish_reels()` (to build) / IG `_publish_reels` (exists)

| Pros | Cons |
|------|------|
| ~$0 marginal cost per reel | Not “authentic creator” raw video |
| Reuses FLUX + Pillow + Products | FFmpeg ops on Railway (CPU, queue) |
| Matches African SMB workflow | Needs template design work |
| Scales to 1000s of users | |

**Score: 9/10** — best fit for Kova economics and existing stack.

---

### B. Product → Reel pipeline (recommended wedge)

**How it works:**
- User has products in catalog (photo from Snap to Sell)
- One-click or auto-promote: **“Make Reel for this product”**
- Template:  
  `Slide 1:` product hero + price  
  `Slide 2–3:` benefits (from product description / AI)  
  `Slide 4:` CTA “Comment ORDER” / first-comment link strategy  
- Music: upbeat default from library (category: retail / services)
- Caption: FB-native (Create Agent) + first comment for link

**Why this wedge:** Retail/e-commerce is huge in Kenya; `auto_promote_products` already creates seeds — extend to `post_format=reel` + video compose.

**Score: 9/10** — clear value, differentiated from Buffer/Hootsuite.

---

### C. User uploads video → Kova enhances

**How it works:**
- User uploads MP4 from phone (Visual Publisher pattern)
- Kova: auto-subtitles (Whisper), trim to 9:16, add intro card, add licensed music bed (ducking), suggest caption
- Publish as Reel

| Pros | Cons |
|------|------|
| Authentic BTS content | Users must shoot (friction) |
| Lower compute than AI video | Subtitle burn-in complexity |
| Good for services (salon, gym) | |

**Score: 7/10** — Phase 2 after motion templates; reuse media_queue upload UX.

---

### D. AI-generated video (Kling, Runway, Minimax)

**How it works:** Text/image → 5s AI clip → stitch into reel

| Pros | Cons |
|------|------|
| “Wow” factor | **37–71% of subscription revenue** at 30% adoption (see roadmap) |
| | Uncanny/product accuracy issues for SMBs |
| | Slow (10–30s generation) |

**Decision:** **Pro/Agency only, hard cap 5–10/month**, opt-in. Not the default Reels path.

**Score: 4/10** for default; **6/10** as premium upsell later.

---

### E. Canva integration vs Canva-style in-house

#### E1. Canva Connect API
- User designs in Canva → export → Kova schedules
- Or: Kova triggers Canva template with brand kit

| Pros | Cons |
|------|------|
| Professional templates day one | **Breaks “5-minute approve”** — user leaves Kova |
| | OAuth + billing + export polling |
| | Not autonomous — opposite of agent model |
| | Canva API limits autonomous generation |

**Score: 3/10** as core path — OK as **optional export** for power users.

#### E2. Canva-style in-house (template compositor)
- JSON-defined templates: layers (background, product_image, text_blocks, logo, price_badge)
- Render via Pillow (frames) → FFmpeg (motion)
- Industry packs: retail, salon, restaurant, coach

| Pros | Cons |
|------|------|
| Fully autonomous | 15–30 templates to feel “real” |
| Zero marginal API cost | Not as pretty as Canva at v1 |
| Brand colors + logo | Maintenance burden |
| Matches “AI team” positioning | |

**Score: 8/10** — this **is** the right “Canva” answer for Kova.

#### E3. Ideogram / Recraft for text-in-image slides
- Use for slides that need **price text baked in** (FLUX is bad at text)
- One frame per slide → FFmpeg slideshow

**Score: 7/10** — augment Pillow for promo slides with prices (Growth+ tier).

---

## Music strategy — three tiers

### Tier 1: Curated royalty-free library (ship first)

**Source options:**

| Source | Cost | Notes |
|--------|------|-------|
| **Pixabay / Mixkit / YouTube Audio Library** | Free | Verify commercial use + attribution rules |
| **Uppbeat** (free tier) | Free with attribution | Good for social |
| **Epidemic Sound / Artlist** | ~$15–50/mo platform license | Best quality; negotiate when scale warrants |
| **Commission 20–30 African beats** | One-time | Differentiator: afrobeats, gengetone beds — **on-brand for Kova** |

**Implementation:**
- Store 50–100 MP3s in S3: `static/audio/reel-beds/{mood}/{track}.mp3`
- Metadata: BPM, mood (upbeat, calm, urgent), duration, attribution_required
- Create Agent or template picker assigns mood from content type (sale → urgent, tip → calm)
- FFmpeg: `-i video -i audio -shortest` with fade in/out

**Do NOT:** Scrape Meta trending sounds — ToS violation and technically blocked.

### Tier 2: User-uploaded audio
- Settings → “Brand jingle” upload (like logo)
- Validate length, format, rights checkbox (“I own or licensed this”)

### Tier 3: Voiceover (no music)
- TTS hook (existing voice campaign / Whisper stack): “You won’t believe this deal…”
- Works for markets where music licensing is scary
- Lower engagement than music but zero licensing risk

**Recommendation:** Ship Tier 1 (30 tracks, 5 moods) + Tier 3 fallback. Tier 2 in v2.

---

## Image generation strategy (feeds Reels)

| Layer | Tool | Use in Reels |
|-------|------|--------------|
| **AI photo** | FLUX (current) | Backgrounds, lifestyle shots without text |
| **Text overlays** | Pillow `graphics.py` | Hook, price, CTA — reliable text |
| **Text-in-image** | Ideogram (future, Growth+) | Single promo frames with price |
| **Product photo** | User upload / Snap to Sell | Hero slide — always prefer real product |
| **Logo** | `brand_logo_url` on last slide | Trust |

**Not Canva:** Extend Pillow to **9:16** (`1080×1920`) templates — quote_motion, product_hero, tip_stack.

**Carousel → Reel:** Existing carousel slides → FFmpeg crossfade → automatic Reel variant (one seed, two formats).

---

## Recommended architecture

```text
ContentSeed
    │
    ▼
Create Agent ──► post_format=reel + reel_script JSON
    │              (hook, slides[{text, visual_strategy, duration}], cta)
    ▼
Visual Composer (new)
    ├─► Resolve assets: product.image | FLUX | Pillow frame
    ├─► Render frames (Pillow 9:16)
    ├─► FFmpeg: Ken Burns + transitions + audio bed
    └─► MediaAttachment (video/mp4)
    ▼
Studio preview (thumbnail + play inline)
    │
    ▼
Approve → Queue → publish_reels (FB) / _publish_reels (IG)
    │
    ▼
First comment (link) — same as feed
```

**Celery task:** `content.compose_reel_video(post_id)` — runs after images ready, before publish.

---

## Phased rollout

### Phase 0 — Honesty (1 week, no new video)
- Stop Create Agent assigning FB `post_format=reel` until compose exists
- UI badge: “Reels coming soon — we’ll notify you”
- Wire **feed video** publish for user-uploaded MP4 (quick win)

### Phase 1 — Motion Reels MVP (3–4 weeks)
- FFmpeg compositor + 5 templates (product, tip, quote, before/after, promo)
- 30-track music library (5 moods)
- Product → “Create Reel” from catalog
- IG Reels publish (wire existing provider)
- FB Reels publish (new provider method)
- Studio: inline video preview

### Phase 2 — Upload + enhance (2–3 weeks)
- Upload phone video → auto-caption + 9:16 crop + music bed
- Carousel → Reel auto-variant

### Phase 3 — Polish (ongoing)
- Logo on all frames
- Industry template packs (10 per vertical)
- Ideogram price frames (Growth+)
- Analyst learns which template + music mood performs

### Phase 4 — Premium (later)
- AI video clips (Pro, 5/month cap)
- Optional Canva export link (“Edit in Canva” opens pre-filled design — not in core loop)

---

## Facebook-specific Reels decisions

| Question | Recommendation |
|----------|----------------|
| Reels vs cross-post IG Reel? | **Generate once, publish to both** when both connected — same MP4, platform-specific caption |
| Caption on Reel? | Short hook + CTA; long story stays in **comments** or first comment |
| Link in Reel? | Same as feed: **first comment**, not on-screen URL |
| Length | 15–30s default (SMB attention); max 60s |
| Aspect | 9:16 only for Reels; don’t reuse 1:1 carousel without recompose |

---

## What NOT to build

| Idea | Why skip |
|------|----------|
| Full Canva clone | Years of work; wrong company |
| Meta trending sounds | API doesn’t allow |
| AI video as default | Unit economics |
| In-browser video editor | Scope creep; CapCut exists |
| Stock footage library | Licensing cost + not SMB-specific |

---

## Success metrics

| Metric | Target (90 days post Phase 1) |
|--------|-------------------------------|
| % Growth+ users publishing ≥1 Reel/week | 25% |
| Reel avg reach vs feed photo (same account) | Reel ≥ 1.5× |
| Time from product → published Reel | < 10 min (mostly automated) |
| Video compose failure rate | < 5% |
| Support tickets “Reel didn’t work” | ↓ vs today |

---

## Open questions for founder decision

1. **Music:** Start with free library + attribution, or budget Epidemic Sound from day one?
2. **African beats:** Worth commissioning 10 custom beds as a marketing differentiator?
3. **Reels in Starter plan?** Recommend: Growth+ only (compute + storage), or 2 Reels/mo on Starter
4. **User upload priority:** Phase 1 or Phase 2?
5. **Canva:** Any partnership interest, or stay fully in-house templates?

---

## Bottom line

**Reels for Kova = motion graphics + product photos + licensed music + FFmpeg — not AI video, not Canva.**

The winning wedge: **“Snap your product → Kova makes a Reel with music, text, and caption → you approve in Studio.”** That’s value for money no scheduler offers at KES 299/month.

Next step when ready to build: Phase 0 honesty fix + Phase 1 FFmpeg spike (one product template, one FB Reels publish end-to-end).
