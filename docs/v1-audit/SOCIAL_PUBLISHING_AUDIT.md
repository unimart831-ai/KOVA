# Social Publishing Audit

**Date:** July 2026

---

## Architecture Overview

Social publishing in Kova follows a provider pattern:

```
ContentSeed → Create Agent → Post (draft) → Approval → Publisher → Platform API
                                                  ↓
                                        Metrics Collection ← Platform API
```

All platforms implement a `BaseProvider` interface defined in `platforms/providers/base.py`.

---

## Platform Provider Inventory

### Facebook + Instagram

| Attribute | Value |
|-----------|-------|
| File | `platforms/providers/instagram_facebook.py` |
| API | Meta Graph API |
| Auth | OAuth 2.0 (long-lived page tokens via Facebook Login) |
| Status | **Production Ready** |

**Capabilities:**
- Text posts (Facebook Pages)
- Image posts (Facebook + Instagram)
- Carousel posts (Instagram)
- Reels/Video (Facebook + Instagram)
- Stories (Instagram)
- Comment fetching
- DM fetching (Messenger + Instagram Direct)
- Insights/metrics retrieval
- Webhook for real-time comments/DMs

**Assessment:** Most mature integration. Handles all content formats. Token refresh exists. Data deletion callback implemented. The primary publishing target for V1.

---

### TikTok

| Attribute | Value |
|-----------|-------|
| File | `platforms/providers/tiktok.py` |
| API | TikTok Content Posting API + Display API |
| Auth | OAuth 2.0 |
| Status | **Working Prototype** |

**Capabilities:**
- Video publishing (direct post)
- Photo publishing (direct post)
- Post status polling (TikTok's async publish model)
- Basic metrics retrieval

**Limitations:**
- TikTok's API requires app review for each publish scope
- Async publishing model requires status polling (`poll_tiktok_publish_status` task)
- Limited API access for metrics compared to Meta
- No carousel support yet (TikTok API limitation)

**Assessment:** Functional but depends on TikTok app approval status. The async publishing model is handled correctly via Celery polling. V1.1 candidate — needs validation of app approval.

---

### LinkedIn

| Attribute | Value |
|-----------|-------|
| File | `platforms/providers/linkedin.py` |
| API | LinkedIn REST API |
| Auth | OAuth 2.0 |
| Status | **Working Prototype** |

**Capabilities:**
- Text posts (personal profile + company pages)
- Image posts
- Video posts
- Comment fetching
- Reaction retrieval

**Limitations:**
- LinkedIn API has strict rate limits
- Video upload is multi-step (initialize → upload → publish)
- No stories/reels equivalent
- Metrics access requires Marketing Developer Platform approval

**Assessment:** Functional for basic publishing. Appropriate for B2B-focused businesses. V1.1 candidate — less critical for the typical African SME target.

---

### WhatsApp (as Publishing Channel)

| Attribute | Value |
|-----------|-------|
| File | `platforms/providers/whatsapp.py` |
| API | Meta WhatsApp Cloud API |
| Auth | System User token + Business verification |
| Status | **Production Ready** |

**Capabilities:**
- Template-based messages (broadcasts)
- WhatsApp Status content (image + text)
- WhatsApp Channels (broadcast-only)
- Interactive messages (buttons, lists)

**Assessment:** WhatsApp isn't traditional "social publishing" but is a content distribution channel. Status content and Channels enable broadcast reach. Production-ready.

---

### Twitter/X, YouTube, Pinterest, Threads, Bluesky

| Platform | Provider File | Status |
|----------|---------------|--------|
| Twitter/X | Not found | **Not Implemented** |
| YouTube | Not found | **Not Implemented** |
| Pinterest | Not found | **Not Implemented** |
| Threads | Not found | **Not Implemented** |
| Bluesky | Not found | **Not Implemented** |

The `SocialAccount` model has `platform` choices including twitter, youtube, pinterest, threads, and bluesky — but no provider implementations exist for these platforms. They are future placeholders in the data model.

---

## Publishing Pipeline

### Content Generation Flow

```
1. Strategist creates ContentSeed
2. Create Agent generates Post draft (per-platform)
3. Platform rewrite adapts copy (content/platform_rewrite.py)
4. Visual strategy selects media type (agents/visual_strategy.py)
5. Media generated (AI image / graphic / carousel)
6. Content safety check (content/safety.py)
7. Post enters approval queue OR auto-publishes
8. Celery task publishes at scheduled time
9. Metrics fetched after publication
```

### Key Task Files

| File | Key Tasks |
|------|-----------|
| `content/tasks.py` | `publish_post`, `check_and_publish_due_posts`, `generate_from_seed`, `fetch_post_metrics` |
| `platforms/tasks.py` | `refresh_expiring_tokens`, `warn_expiring_tokens`, `poll_tiktok_publish_status` |
| `content/renderers.py` | Platform-native output formatting before publish |

### Publishing Safety

| Component | Purpose | Status |
|-----------|---------|--------|
| Content safety (vision/text) | Blocks explicit content | Implemented |
| SystemSafetyConfig | Platform-wide publish kill switches | Implemented |
| Token health check | Validates tokens before publish | Implemented |
| Platform outage detection | Detects and messages about outages | Implemented |
| PostVersion tracking | Audit trail for post edits | Implemented |

---

## OAuth & Token Management

| Component | File | Status |
|-----------|------|--------|
| Facebook OAuth | `accounts/facebook_oauth.py` | Production |
| Platform OAuth flows | `platforms/views.py` | Production |
| Token refresh | `platforms/tasks.py` | Production |
| Token health diagnostics | `platforms/token_health.py` | Production |
| Expiry warnings | `platforms/tasks.py` | Production |
| Data deletion (Meta) | `platforms/facebook_data_deletion.py` | Production |

---

## Engagement (Post-Publish)

| Component | File | Status |
|-----------|------|--------|
| Comment/DM fetching | `engage/dm_inbox.py` | Production |
| AI auto-reply | `agents/engage_agent.py` | Production |
| Reply routing | `agents/engage_routing.py` | Production |
| Superfan detection | `engage/models.py` | Production |
| Messenger webhook | `engage/messenger_webhook.py` | Production |
| Lead escalation | `engage/lead_escalation.py` | Production |

---

## Platform Status Matrix

| Platform | OAuth | Publish Text | Publish Image | Publish Video | Metrics | Engagement | Status |
|----------|-------|-------------|--------------|--------------|---------|------------|--------|
| Facebook | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | **Production** |
| Instagram | ✓ | ✓ | ✓ | ✓ (Reels) | ✓ | ✓ | **Production** |
| TikTok | ✓ | — | ✓ (photo) | ✓ | Partial | — | **Prototype** |
| LinkedIn | ✓ | ✓ | ✓ | ✓ | Partial | Partial | **Prototype** |
| WhatsApp | ✓ | ✓ (template) | ✓ (status) | — | ✓ | ✓ | **Production** |
| Twitter/X | — | — | — | — | — | — | **Not Implemented** |
| YouTube | — | — | — | — | — | — | **Not Implemented** |
| Pinterest | — | — | — | — | — | — | **Not Implemented** |
| Threads | — | — | — | — | — | — | **Not Implemented** |
| Bluesky | — | — | — | — | — | — | **Not Implemented** |

---

## V1 Recommendations

### Must Ship (V1)

1. **Facebook + Instagram** — Core publishing platforms for African SMEs. Fully ready.
2. **WhatsApp Status/Channels** — Native to the WhatsApp-first vision.
3. **Token refresh + health monitoring** — Prevents silent publishing failures.
4. **Content safety gates** — Protects brand reputation.
5. **AI engagement (Engage Agent)** — Automated comment/DM management.

### Ship If Ready (V1 stretch)

6. **TikTok** — Growing rapidly in Africa but depends on app approval status.

### Defer (V1.1)

7. **LinkedIn** — B2B niche, not primary target.
8. **Advanced metrics/analytics** — Basic post metrics sufficient for V1.

### Defer (V2)

9. **Twitter/X, YouTube, Pinterest, Threads, Bluesky** — Remove platform choices from UI until implemented.

---

## Risks

| Risk | Impact | Mitigation |
|------|--------|------------|
| Meta token expiry | Publishing stops silently | Token health + expiry warnings exist |
| Meta API changes | Provider breaks | Isolated provider pattern limits blast radius |
| TikTok app rejection | Cannot publish | Make TikTok optional / V1.1 |
| Rate limits (any platform) | Throttled publishing | Queue-based publishing with backoff |
| Content safety false positive | Good content blocked | Admin override + incident review exist |

---

## Social Publishing Readiness Score

| Platform | Score |
|----------|-------|
| Facebook | 9/10 |
| Instagram | 9/10 |
| TikTok | 6/10 |
| LinkedIn | 6/10 |
| WhatsApp (as channel) | 8/10 |

**Overall Social Publishing Readiness: 8/10 for V1 scope (FB + IG + WA)**
