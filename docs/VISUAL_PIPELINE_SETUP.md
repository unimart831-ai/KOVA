# Visual Intelligence Pipeline — Setup & Configuration Guide

> **What this covers:** Everything added in the Visual Intelligence Pipeline (R1–R9) that needs manual setup, configuration, or awareness. Follow this step by step before/after deploying.

---

## Table of Contents

1. [Cloudflare R2 Media Storage (CRITICAL)](#1-cloudflare-r2-media-storage)
2. [Environment Variables Reference](#2-environment-variables-reference)
3. [Visual Brand Fields (Not Yet in UI)](#3-visual-brand-fields-gap)
4. [AI Image Limits per Plan](#4-ai-image-limits-per-plan)
5. [Media-Required Platforms](#5-media-required-platforms)
6. [Visual Content Types](#6-visual-content-types)
7. [How the Visual Strategy System Works](#7-how-the-visual-strategy-system-works)
8. [Testing Checklist](#8-testing-checklist)

---

## 1. Cloudflare R2 Media Storage

### Why This Is Critical

Railway uses an **ephemeral filesystem** — every time you deploy, redeploy, or the server restarts, all files on disk are **deleted permanently**. That means every AI-generated image, every uploaded photo, every carousel slide saved to `/media/` disappears.

Cloudflare R2 is an S3-compatible object storage service with **free egress** (no bandwidth fees when platforms download images). We configured Kova to use it automatically in production when the right environment variables are set.

### Step-by-Step: Create the R2 Bucket

1. **Log in to Cloudflare Dashboard**
   - Go to [dash.cloudflare.com](https://dash.cloudflare.com)
   - Sign up if you don't have an account (free tier includes 10GB R2 storage)

2. **Create an R2 Bucket**
   - In the left sidebar, click **R2 Object Storage**
   - Click **Create Bucket**
   - Bucket name: `kova-media` (or whatever you prefer — this becomes your `AWS_STORAGE_BUCKET_NAME`)
   - Location hint: Choose the region closest to your Railway deployment (e.g., `ENAM` for US East, `WEUR` for Europe, `APAC` for Asia)
   - Click **Create Bucket**

3. **Set Bucket to Public Access**
   - Open your new bucket → **Settings** tab
   - Under **Public Access**, click **Allow Access**
   - This makes media files accessible via URL (required for social platforms to download images)
   - Note the **Public bucket URL** — looks like: `https://pub-xxxxxxxxxxxx.r2.dev`

4. **Create an API Token**
   - Go back to **R2 Overview** (not inside a bucket)
   - Click **Manage R2 API Tokens** on the right sidebar
   - Click **Create API Token**
   - Token name: `kova-production`
   - Permissions: **Object Read & Write**
   - Specify bucket: Select `kova-media` (don't give access to all buckets)
   - TTL: No expiration (or set a reminder to rotate)
   - Click **Create API Token**
   - **COPY THESE IMMEDIATELY** (shown only once):
     - **Access Key ID** → This is your `AWS_S3_ACCESS_KEY_ID`
     - **Secret Access Key** → This is your `AWS_S3_SECRET_ACCESS_KEY`

5. **Get Your Account ID**
   - In the Cloudflare dashboard URL or on the R2 overview page, find your **Account ID**
   - Your endpoint URL is: `https://<ACCOUNT_ID>.r2.cloudflarestorage.com`

### Step-by-Step: Configure Railway

1. **Open your Railway project** → Click on the Kova service

2. **Go to Variables tab** and add these environment variables:

   | Variable | Value | Example |
   |----------|-------|---------|
   | `AWS_STORAGE_BUCKET_NAME` | Your bucket name | `kova-media` |
   | `AWS_S3_ENDPOINT_URL` | `https://<ACCOUNT_ID>.r2.cloudflarestorage.com` | `https://a1b2c3d4e5.r2.cloudflarestorage.com` |
   | `AWS_S3_ACCESS_KEY_ID` | The Access Key from step 4 | `abc123def456...` |
   | `AWS_S3_SECRET_ACCESS_KEY` | The Secret Key from step 4 | `xyz789...` |
   | `AWS_S3_CUSTOM_DOMAIN` | *(Optional)* Your R2 public URL | `pub-xxxxxxxxxxxx.r2.dev` |

3. **Redeploy** — Railway will restart, and Django will now use R2 for all media files.

### How It Works in Code

- **When `AWS_STORAGE_BUCKET_NAME` is set** → Django's default file storage switches to `S3Boto3Storage`. Every `ImageField.save()`, `FileField.save()`, and `default_storage.save()` call writes directly to R2.
- **When it's NOT set** → Falls back to local filesystem (fine for development).
- **File location:** `config/settings/production.py` lines 51–79.

### Optional: Custom Domain for Media URLs

If you want media URLs to look like `https://media.kova.co.ke/avatars/photo.jpg` instead of the R2 default URL:

1. In Cloudflare DNS, add a CNAME: `media.kova.co.ke` → your R2 public bucket URL
2. Set `AWS_S3_CUSTOM_DOMAIN=media.kova.co.ke` in Railway variables
3. Kova will automatically use `https://media.kova.co.ke/` as the media URL prefix

### What Gets Stored in R2

| Content | How It Gets There |
|---------|-------------------|
| AI-generated images (FLUX.1) | `media.py` → `generate_post_image()` downloads from provider, saves via Django storage |
| Branded graphics (quote cards, tip graphics, etc.) | `graphics.py` → Pillow renders image in memory, saves to storage |
| Carousel slides | `carousel.py` → Each slide rendered by Pillow, saved as `MediaAttachment` |
| User-uploaded media | `views.py` → `upload_media()` saves uploaded file |
| Profile avatars | User uploads in settings/onboarding |

---

## 2. Environment Variables Reference

All new env vars introduced by the visual pipeline (add to Railway):

| Variable | Required? | Purpose |
|----------|-----------|---------|
| `AWS_STORAGE_BUCKET_NAME` | **Yes** (production) | R2 bucket name — triggers cloud storage |
| `AWS_S3_ENDPOINT_URL` | **Yes** (production) | R2 endpoint `https://<id>.r2.cloudflarestorage.com` |
| `AWS_S3_ACCESS_KEY_ID` | **Yes** (production) | R2 API token access key |
| `AWS_S3_SECRET_ACCESS_KEY` | **Yes** (production) | R2 API token secret key |
| `AWS_S3_CUSTOM_DOMAIN` | No | Custom domain for media URLs |

> **No other new env vars were added.** The visual system (graphics engine, carousels, visual strategy) runs entirely on existing infrastructure (Pillow for rendering, existing image providers for AI photos).

---

## 3. Visual Brand Fields (Gap — Not Yet in UI)

Three new fields were added to `UserProfile` that power brand-consistent visuals:

| Field | Type | Purpose |
|-------|------|---------|
| `brand_colors` | JSON list of hex codes | Used by graphics engine and carousel for backgrounds, accents, text colors |
| `visual_style` | Choice field (10 options) | Guides AI image prompts and graphic rendering |
| `brand_logo_url` | URL | Public URL to brand logo *(reserved for future overlay use)* |

### The Gap

These fields exist on the model and are consumed by the AI (Create Agent reads them for image prompts, graphics engine reads them for color palettes), **but they are NOT yet exposed in any form or template.** This means:

- Users **cannot** set their brand colors or visual style through the UI yet
- The system falls back to defaults (dark navy + coral accent + white text, `auto` style)
- This is functional but not personalized until we add these fields to the UI

### Visual Style Options

| Value | Display Name | What It Tells the AI |
|-------|-------------|---------------------|
| `photography` | Photography / Real Photos | Generate realistic photo-style images |
| `illustration` | Illustrations / Drawn Art | Illustrated, hand-drawn aesthetic |
| `flat_design` | Flat Design / Minimal | Clean, flat, minimalist graphics |
| `3d_render` | 3D Renders | Three-dimensional rendered scenes |
| `collage` | Collage / Mixed Media | Mixed media, layered compositions |
| `abstract` | Abstract / Artistic | Abstract, artistic visuals |
| `corporate` | Corporate / Clean | Professional, business-appropriate |
| `vibrant` | Vibrant / Colorful | Bold, saturated, energetic colors |
| `dark_moody` | Dark / Moody | Dark backgrounds, dramatic lighting |
| `auto` | Let AI Decide *(default)* | AI picks based on content and platform |

### Temporary Workaround

Until the UI is built, you can set these via Django Admin:
1. Go to `/admin/accounts/userprofile/`
2. Find the user's profile
3. Set `brand_colors` to something like: `["#FF5733", "#1A1A2E", "#FFFFFF"]`
4. Set `visual_style` to one of the values above
5. Save — all future content will use these brand settings

---

## 4. AI Image Limits per Plan

Every plan now includes AI image generation. Limits are enforced per calendar month:

| Plan | Monthly Price | AI Images / Month | What Happens at Limit |
|------|--------------|-------------------|----------------------|
| **Starter** (Jipange) | KES 99 / $1 | **5** | Posts are created without images — text only |
| **Growth** (Kazi) | KES 500 / $5 | **50** | Same — graceful degradation |
| **Pro** (Biashara) | KES 1,500 / $15 | **Unlimited** | No limit |
| **Agency** (Wakala) | KES 3,500 / $29 | **Unlimited** | No limit |

### How Enforcement Works

- In `create_agent.py`, before generating any visual, the system counts posts with `media_status="generated"` for the current month
- If count ≥ plan limit → skips image generation, creates text-only post
- The post still gets created — only the visual is skipped
- Manual uploads are **never** counted against the limit (users can always upload their own images)

### Why Starter Gets 5 Free Images

Our image providers (FLUX.1-schnell via HuggingFace, Together.ai, Pollinations) are free-tier or nearly free. Giving Starter users 5 images/month costs us essentially nothing but makes the cheapest plan feel complete. It removes the "this product is crippled" feeling.

---

## 5. Media-Required Platforms

Three platforms **require** media — a text-only post will fail at the API level:

| Platform | Why |
|----------|-----|
| **Instagram** | API requires at least one image or video for every post |
| **TikTok** | Photo or video required — no text-only posting API |
| **Pinterest** | Every Pin must have an image |

### What the Guards Do

There are **two layers** of protection:

1. **Approval Guard** (`views.py → approve_post()`):
   - When a user clicks "Approve" on a post for Instagram/TikTok/Pinterest that has no media
   - System blocks approval and shows a warning: *"This post needs media for [platform]. Upload an image or generate one first."*
   - User must upload media or generate an image before approving

2. **Publish Safety Net** (`tasks.py → publish_post()`):
   - Even if a post somehow gets approved without media, the Celery publish task checks again
   - If media is missing, the post is marked as failed and the user gets a notification
   - This prevents silent failures where a post "publishes" but the platform rejects it

### Media Status Tracking

Every post now has a `media_status` field that tracks the full lifecycle:

```
none → pending → generated (AI made it)
                → uploaded  (user uploaded)
                → failed    (all AI providers failed)
```

Users see the status on their post cards. If a post has `failed` status, the warning tells them to upload manually.

---

## 6. Visual Content Types

Kova now generates **four types** of visual content (beyond AI photos):

### AI Photos (existing — enhanced)
- Generated by FLUX.1-schnell via 3 providers (HuggingFace, Together.ai, Pollinations)
- Now brand-aware: prompts include brand colors and visual style
- Explicit instruction: "NEVER include text/words/letters in the image"

### Branded Graphics (NEW — `graphics.py`)

Pillow-rendered images with brand colors, no external API needed:

| Type | Best For | What It Looks Like |
|------|----------|-------------------|
| **Quote Card** | Inspirational quotes, bold statements, testimonials | Large text centered on gradient background with opening quote mark |
| **Tip Graphic** | "5 tips for...", how-to lists, actionable advice | Numbered items with circle indicators, title at top, divider |
| **Stat Highlight** | "87% of...", achievements, data points | Big number in center, label below, context text, accent bars |
| **CTA Banner** | Promotions, event invites, product launches | Headline + subtext + rounded call-to-action button |

All graphics automatically use the user's `brand_colors` (or elegant defaults if none set).

### Carousels (NEW — `carousel.py`)

Multi-slide swipeable content (Instagram and Threads native format):

- **Title Slide:** Hook text + subtitle + "Swipe →" indicator
- **Content Slides:** Numbered slides (2–10) with individual content
- **Closing Slide:** CTA text + brand name
- Canvas: 1080×1080 square for Instagram/Threads
- Each slide saved as a separate `MediaAttachment`

### Content DNA Enhancement

The Analyst Agent now tracks visual performance data:
- `has_image` — whether the analyzed post had an image
- `image_source` — `ai_generated`, `uploaded`, or `none`
- `image_type` — `photo`, `illustration`, `graphic`, `meme`, `infographic`, `carousel`, `none`

This means over time, Kova learns which visual types perform best for each brand.

---

## 7. How the Visual Strategy System Works

This is the brain that decides WHAT type of visual to create for each post.

### The Flow

```
User creates ContentSeed
        ↓
Create Agent generates post content
        ↓
LLM returns visual_strategy JSON:
{
    "strategy": "tip_graphic",
    "tips": ["Tip 1...", "Tip 2...", "Tip 3..."],
    "title": "3 Marketing Tips"
}
        ↓
Check: Is user within monthly image limit?
        ↓  YES                    ↓  NO
apply_visual_strategy()     Skip — text-only post
        ↓
Dispatch based on strategy:
┌─────────────────────────────────────────────┐
│ "ai_photo"     → generate_post_image()      │
│ "quote_card"   → generate_branded_graphic() │
│ "tip_graphic"  → generate_branded_graphic() │
│ "stat_highlight"→ generate_branded_graphic() │
│ "cta_banner"   → generate_branded_graphic() │
│ "carousel"     → generate_carousel()        │
└─────────────────────────────────────────────┘
        ↓
MediaAttachment(s) created
Post.media_status = "generated"
```

### Fallback: Inference

If the LLM doesn't return a `visual_strategy` object (backward compatibility), the system infers the best type from the post content:

| Content Pattern | Inferred Type |
|----------------|---------------|
| Numbered list ("1.", "2.", "3.") | `tip_graphic` |
| Big numbers with % or stats language | `stat_highlight` |
| Quoted text or testimonial patterns | `quote_card` |
| CTA words ("sign up", "join", "register") | `cta_banner` |
| Long content on Instagram/Threads | `carousel` |
| Everything else | `ai_photo` |

---

## 8. Testing Checklist

### Before First Production Deploy

- [ ] **R2 bucket created** on Cloudflare with public access enabled
- [ ] **API token created** with Object Read & Write on your bucket
- [ ] **4 env vars set** on Railway: `AWS_STORAGE_BUCKET_NAME`, `AWS_S3_ENDPOINT_URL`, `AWS_S3_ACCESS_KEY_ID`, `AWS_S3_SECRET_ACCESS_KEY`
- [ ] **Deploy to Railway** and confirm no errors in build logs
- [ ] **Test media upload**: Upload an avatar or post image → verify it appears at the R2 URL (not a local `/media/` path)

### Functional Tests

- [ ] **Create a post for Instagram** without media → Try to approve → Should see warning blocking approval
- [ ] **Create a post for Twitter** without media → Approve → Should succeed (Twitter doesn't require media)
- [ ] **Trigger AI image generation** → Check that `post.media_status` becomes `"generated"` and the image URL points to R2
- [ ] **Upload media manually** → Check that `post.media_status` becomes `"uploaded"`
- [ ] **Set brand colors via admin** on a user profile → Generate a graphic → Verify the colors match
- [ ] **Generate a carousel** for an Instagram post with 5+ slides → Verify all slides appear as MediaAttachments

### Plan Limit Test

- [ ] Create a Starter user with 5 generated images this month → Create another post → Verify no image is generated (text-only)
- [ ] Upgrade to Growth → Verify image generation works again

---

## Quick Reference: Files Changed

| File | What Changed |
|------|-------------|
| `config/settings/production.py` | R2/S3 cloud storage configuration |
| `apps/content/models.py` | `media_status` field, `MEDIA_REQUIRED_PLATFORMS`, `has_media`/`needs_media`/`media_warning` properties |
| `apps/agents/media.py` | Sets `media_status` on success/failure |
| `apps/content/views.py` | Approval guard + upload status tracking |
| `apps/content/tasks.py` | Publish safety net for media-required platforms |
| `apps/agents/analyst_agent.py` | Visual attributes in Content DNA extraction |
| `apps/accounts/models.py` | `brand_colors`, `visual_style`, `brand_logo_url` fields |
| `apps/agents/create_agent.py` | Brand-aware prompts, visual strategy wiring, plan limit enforcement |
| `apps/billing/models.py` | `ai_images_per_month` limits, Starter plan enabled |
| `apps/agents/graphics.py` | **NEW** — Branded graphics engine (4 types) |
| `apps/agents/carousel.py` | **NEW** — Carousel slide generator |
| `apps/agents/visual_strategy.py` | **NEW** — Visual type selection + dispatching |

---

## What's NOT Done Yet (Future Work)

1. **UI for visual brand fields** — `brand_colors`, `visual_style`, and `brand_logo_url` need to be added to the onboarding form and settings page so users can set them without going into Django Admin
2. **Logo overlay on graphics** — `brand_logo_url` is stored but not yet rendered onto graphics/carousels
3. **Visual performance dashboard** — Content DNA now tracks visual data, but there's no analytics view showing "your carousels get 3x more engagement than photos"
4. **Premium image model option** — R10 was deferred: allow Pro/Agency users to use higher-quality paid image models (DALL-E, Midjourney API) for premium visuals
