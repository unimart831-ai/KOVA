# Content System Audit

**Date:** July 2026

---

## Overview

The content system is Kova's engine for creating, managing, and publishing social media content. It spans from idea generation (seeds) through publishing to performance measurement.

---

## Content Pipeline Architecture

```
Research Agent → Strategist → ContentSeed → Create Agent → Post (draft)
                                                              ↓
                              Owner Approval ← WhatsApp Brief/Queue
                                   ↓
                            Platform Rewrite → Visual Strategy → Media Generation
                                                                      ↓
                                                              Content Safety Check
                                                                      ↓
                                                         Scheduled Publish (Celery)
                                                                      ↓
                                                         Platform API → Published
                                                                      ↓
                                                         Metrics Collection (24h+)
                                                                      ↓
                                                         Analyst Agent → Adapt Agent
```

---

## Component Inventory

### Content Generation

| Component | Location | Status | Description |
|-----------|----------|--------|-------------|
| ContentSeed model | `content/models.py` | **Ready** | Idea container with pillar, topic, angle, platform target |
| Create Agent | `agents/create_agent.py` | **Ready** | Generates platform-native posts from seeds |
| Platform rewrite | `content/platform_rewrite.py` | **Ready** | Adapts copy per platform norms |
| Visual strategy | `agents/visual_strategy.py` | **Ready** | Decides media type (AI photo, graphic, carousel, none) |
| AI image generation | `agents/media.py` | **Ready** | Together/Pollinations/FLUX image chain |
| Branded graphics | `agents/graphics.py` | **Ready** | Quote cards, tips, stats, CTAs via Pillow |
| Carousel generation | `agents/carousel.py` | **Ready** | Multi-slide structured content |
| Voice transcription | `content/voice.py` | **Ready** | Whisper (Groq/OpenAI) for voice memos |
| Renderers | `content/renderers.py` | **Ready** | Blueprint formatting before publish |
| Weekly content plan | `content/models.py` (WeeklyContentPlan) | **Ready** | AI autopilot weekly schedule |

### Media Library

| Component | Location | Status | Description |
|-----------|----------|--------|-------------|
| MediaAttachment model | `content/models.py` | **Ready** | File attachments on posts |
| Photoroom pipeline | `products/photoroom*.py` | **Ready** | Product image enhancement |
| Media orchestrator | `media/orchestrator.py` | **Ready** | Plans media production per post |
| Media factory | `media/media_factory.py` | **Ready** | Campaign-driven media production |
| Media router | `media/router.py` | **Ready** | Plan-tier gates + backend selection |
| Reel bridge | `media/reel_bridge.py` | **Partial** | Kling via Fal (experimental) |
| Carousel bridge | `media/carousel_bridge.py` | **Ready** | Bannerbear + local fallback |
| Asset intelligence | `media/asset_intelligence.py` | **Ready** | AI media recommendations per product |

### Templates & Scheduling

| Component | Location | Status | Description |
|-----------|----------|--------|-------------|
| Post model | `content/models.py` | **Ready** | Full lifecycle: draft → scheduled → published → archived |
| Post scheduling | `content/tasks.py` | **Ready** | `check_and_publish_due_posts` runs periodically |
| Content calendar | `content/calendar.html` | **Ready** | Visual calendar UI |
| Content queue | `content/queue.html` | **Ready** | Approval queue with actions |
| Optimal scheduling | Adapt Agent | **Ready** | AI-optimized posting times |
| Weekly content plan | `content/models.py` | **Ready** | Auto-generated weekly schedule |
| Calendar intel | `calendar_intel/` | **Ready** | Holiday/cultural moment awareness |

### Publishing

| Component | Location | Status | Description |
|-----------|----------|--------|-------------|
| Publish task | `content/tasks.py` (`publish_post`) | **Ready** | Core publish logic |
| Due post checker | `content/tasks.py` | **Ready** | Periodic check for scheduled posts |
| Facebook publisher | `platforms/providers/instagram_facebook.py` | **Ready** | Graph API integration |
| Instagram publisher | `platforms/providers/instagram_facebook.py` | **Ready** | Graph API integration |
| TikTok publisher | `platforms/providers/tiktok.py` | **Prototype** | Content Posting API |
| LinkedIn publisher | `platforms/providers/linkedin.py` | **Prototype** | REST API |
| WhatsApp Status | `whatsapp/models.py` (StatusContent) | **Ready** | Publish to WA Status |
| Content safety | `content/safety.py` | **Ready** | Pre-publish moderation |
| Safety kill switch | `content/models.py` (SystemSafetyConfig) | **Ready** | Platform-wide halt |

### Campaigns

| Component | Location | Status | Description |
|-----------|----------|--------|-------------|
| MarketingCampaign model | `content/models.py` | **Ready** | Campaign container with objective, commerce link |
| Campaign proposals | `content/campaign_proposals.html` | **Ready** | AI-generated campaign packages |
| Campaign WhatsApp approval | `content/campaign_whatsapp.py` | **Ready** | Approve full campaign via WhatsApp |
| Campaign page (public) | `content/public/campaign_page.html` | **Ready** | Public campaign landing page |
| VoiceBrief | `content/models.py` | **Ready** | Campaign voice-note brief |

### Drafts & Versions

| Component | Location | Status | Description |
|-----------|----------|--------|-------------|
| Post status workflow | `content/models.py` | **Ready** | draft → approved → scheduled → published |
| PostVersion | `content/models.py` | **Ready** | Edit history audit trail |
| Post edit UI | `content/edit.html` | **Ready** | Web-based post editing |
| Draft actions (WA) | `whatsapp/draft_actions.py` | **Ready** | Approve/reject from WhatsApp |

---

## Content Status Workflow

```
           ┌──────────┐
           │  SEED    │ (ContentSeed — idea)
           └────┬─────┘
                │ Generate (Create Agent)
                ▼
           ┌──────────┐
           │  DRAFT   │ (Post created, needs review)
           └────┬─────┘
                │ Approve (owner via WA or web)
                ▼
           ┌──────────┐
           │ APPROVED │ (Ready for scheduling)
           └────┬─────┘
                │ Schedule (auto or manual)
                ▼
           ┌──────────┐
           │SCHEDULED │ (Waiting for publish time)
           └────┬─────┘
                │ Publish (Celery task at due time)
                ▼
           ┌──────────┐
           │PUBLISHED │ (Live on platform)
           └────┬─────┘
                │ Metrics (24h+)
                ▼
           ┌──────────┐
           │ MEASURED │ (Performance data collected)
           └──────────┘
```

---

## Readiness Assessment

| Area | Score | Notes |
|------|-------|-------|
| Content generation (text) | 9/10 | Create Agent + platform rewrite + Business Brain grounding |
| Content generation (images) | 8/10 | AI generation + branded graphics + Photoroom |
| Media library management | 7/10 | MediaAttachment exists; no dedicated media library UI |
| Content scheduling | 9/10 | Auto-schedule + manual + weekly plans |
| Multi-platform publishing | 8/10 | FB + IG ready; TikTok/LinkedIn prototype |
| Content approval flow | 9/10 | WhatsApp + web approval; graduated autonomy |
| Campaign management | 8/10 | Campaigns + proposals + WhatsApp approval |
| Drafts & versioning | 8/10 | PostVersion tracking; edit UI exists |
| Content safety | 9/10 | Fail-closed moderation + kill switches |
| Performance tracking | 7/10 | Post metrics exist; feedback loop via Analyst |

**Overall Content System Readiness: 8.5/10**

---

## Recommendations for V1

1. **Content system is V1-ready.** The full pipeline from seed to publish to measurement works. No structural changes needed.

2. **Focus testing on quality.** The pipeline works mechanically — validate that AI-generated content is actually good enough for auto-publishing with owner trust.

3. **Simplify the web content studio.** The studio page has many features (suggestions, quality scorecard, status badges). For V1, focus on: queue (what needs approval) + calendar (what's scheduled) + list (published history).

4. **Defer video/reel generation.** The reel bridge (Fal/Kling) is experimental. Image content is sufficient for V1 launch. Video can come in V1.1.

5. **Defer A/B testing.** The ABTest model exists but the workflow is incomplete. Not needed for V1.

6. **Validate voice memo → content flow.** Transcription exists but the path from WhatsApp voice note → content seed is unclear. If wired up, it's powerful; if not, defer to V1.1.
