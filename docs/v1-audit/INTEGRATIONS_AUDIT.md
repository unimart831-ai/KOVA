# Integrations Audit

**Date:** July 2026

---

## Integration Classification

Every external integration is classified as:
- **Production Ready** — tested, deployed, actively used in production
- **Working Prototype** — code complete, tested in sandbox, not yet production-validated
- **Stub** — code exists but incomplete or untested
- **Missing** — referenced in models/UI but no implementation
- **Deprecated** — superseded or abandoned

---

## Integration Inventory

### Messaging & Communication

#### Meta WhatsApp Cloud API

| Attribute | Detail |
|-----------|--------|
| Status | **Production Ready** |
| Files | `whatsapp/webhook.py`, `whatsapp/services.py`, `platforms/providers/whatsapp.py` |
| Capabilities | Send/receive messages, templates, interactive buttons/lists, status updates, media, webhook verification |
| Auth | System User token + Business verification |
| Webhook | `/whatsapp/webhook/` — inbound messages, delivery status, template events |
| Dependencies | Meta Business Manager, verified WhatsApp Business Account |

#### Resend (Email)

| Attribute | Detail |
|-----------|--------|
| Status | **Production Ready** |
| Files | `emails/services.py`, `emails/views.py` (webhook) |
| Capabilities | Transactional email, delivery tracking, bounce/complaint handling |
| Auth | API key |
| Webhook | `/emails/webhooks/resend/` — delivery events |
| Package | `resend` + `django-anymail` |

---

### Social Media Platforms

#### Meta Graph API (Facebook + Instagram)

| Attribute | Detail |
|-----------|--------|
| Status | **Production Ready** |
| Files | `platforms/providers/instagram_facebook.py`, `accounts/facebook_oauth.py`, `engage/messenger_webhook.py` |
| Capabilities | OAuth, publish (text/image/video/carousel/stories/reels), comments, DMs, insights, data deletion |
| Auth | OAuth 2.0 (long-lived page tokens) |
| Webhook | `/engage/webhook/messenger/` — Messenger DMs |
| Dependencies | Facebook App with Publishing permissions |

#### TikTok

| Attribute | Detail |
|-----------|--------|
| Status | **Working Prototype** |
| Files | `platforms/providers/tiktok.py`, `platforms/tasks.py` (poll_tiktok_publish_status) |
| Capabilities | OAuth, video/photo publish, async status polling, basic metrics |
| Auth | OAuth 2.0 |
| Limitation | Requires TikTok app review for content.publish scope; async publish model |

#### LinkedIn

| Attribute | Detail |
|-----------|--------|
| Status | **Working Prototype** |
| Files | `platforms/providers/linkedin.py` |
| Capabilities | OAuth, text/image/video posts, comments, reactions |
| Auth | OAuth 2.0 |
| Limitation | Rate limits; video upload is multi-step; metrics need Marketing Developer Platform approval |

#### Twitter/X

| Attribute | Detail |
|-----------|--------|
| Status | **Missing** |
| Evidence | `SocialAccount` model has `twitter` as a platform choice; no provider implementation |

#### YouTube

| Attribute | Detail |
|-----------|--------|
| Status | **Missing** |
| Evidence | `SocialAccount` model has `youtube` as a platform choice; no provider implementation |

#### Pinterest

| Attribute | Detail |
|-----------|--------|
| Status | **Missing** |
| Evidence | `SocialAccount` model has `pinterest` as a platform choice; no provider implementation |

#### Threads

| Attribute | Detail |
|-----------|--------|
| Status | **Missing** |
| Evidence | `SocialAccount` model has `threads` as a platform choice; no provider implementation |

#### Bluesky

| Attribute | Detail |
|-----------|--------|
| Status | **Missing** |
| Evidence | `SocialAccount` model has `bluesky` as a platform choice; no provider implementation |

---

### AI & Machine Learning

#### OpenAI

| Attribute | Detail |
|-----------|--------|
| Status | **Production Ready** |
| Files | `agents/llm.py` |
| Capabilities | GPT text generation, Whisper transcription, structured output |
| Auth | API key |
| Package | `langchain-openai` |

#### Anthropic (Claude)

| Attribute | Detail |
|-----------|--------|
| Status | **Production Ready** |
| Files | `agents/llm.py` |
| Capabilities | Claude text generation |
| Auth | API key |
| Package | `langchain-anthropic` |

#### OpenRouter

| Attribute | Detail |
|-----------|--------|
| Status | **Production Ready** |
| Files | `agents/llm.py`, `content/safety.py` |
| Capabilities | Multi-model routing, vision moderation |
| Auth | API key |

#### Tavily

| Attribute | Detail |
|-----------|--------|
| Status | **Production Ready** |
| Files | `agents/research_agent.py` |
| Capabilities | Web search for trend discovery |
| Auth | API key |
| Package | `tavily-python` |

#### Together AI

| Attribute | Detail |
|-----------|--------|
| Status | **Production Ready** |
| Files | `agents/media.py`, `content/image_gen.py` |
| Capabilities | FLUX image generation |
| Auth | API key |

#### Pollinations

| Attribute | Detail |
|-----------|--------|
| Status | **Production Ready** |
| Files | `agents/media.py`, `content/image_gen.py` |
| Capabilities | Image generation (fallback) |
| Auth | None (public API) |

#### HuggingFace

| Attribute | Detail |
|-----------|--------|
| Status | **Production Ready** |
| Files | `agents/media.py`, `content/image_gen.py` |
| Capabilities | FLUX image generation (fallback) |
| Auth | API key |

#### Groq

| Attribute | Detail |
|-----------|--------|
| Status | **Production Ready** |
| Files | `content/voice.py` |
| Capabilities | Fast Whisper transcription |
| Auth | API key |

---

### Image & Media Processing

#### Photoroom

| Attribute | Detail |
|-----------|--------|
| Status | **Production Ready** |
| Files | `products/photoroom*.py` (18 files) |
| Capabilities | Background removal, studio scenes, shadow, resize, virtual models, video, batch, brand templates, food presets |
| Auth | API key |
| Notes | Over-engineered with 18 files; core functionality is solid |

#### Fal.ai

| Attribute | Detail |
|-----------|--------|
| Status | **Working Prototype** |
| Files | `media/fal_client.py` |
| Capabilities | Flux image edit, Kling video generation |
| Auth | API key |
| Notes | Used for reel/video generation; experimental |

#### Bannerbear

| Attribute | Detail |
|-----------|--------|
| Status | **Working Prototype** |
| Files | `media/bannerbear_client.py`, `media/carousel_bridge.py` |
| Capabilities | Branded carousel slide generation from templates |
| Auth | API key |
| Notes | Falls back to local Pillow rendering if unavailable |

#### Remotion

| Attribute | Detail |
|-----------|--------|
| Status | **Stub** |
| Files | `media_render/` (TypeScript subproject), `media/remotion_bridge.py` |
| Capabilities | Programmatic video composition |
| Notes | Separate Node.js process; unclear if actively invoked from Python |

---

### Payments

#### M-Pesa (Safaricom Daraja API)

| Attribute | Detail |
|-----------|--------|
| Status | **Production Ready** |
| Files | `billing/mpesa.py`, `billing/mpesa_services.py` |
| Capabilities | STK Push (subscription + commerce), callback handling, status query, renewal |
| Auth | OAuth (consumer key/secret) |
| Webhook | `/billing/webhook/mpesa/` + `/analytics/webhooks/mpesa/commerce/` |

#### Stripe

| Attribute | Detail |
|-----------|--------|
| Status | **Production Ready** |
| Files | `billing/services.py`, `billing/views.py` |
| Capabilities | Customer management, checkout sessions, portal, subscription lifecycle |
| Auth | Secret key + webhook signing secret |
| Webhook | `/billing/webhook/stripe/` |
| Package | `stripe` |

---

### Storage & Infrastructure

#### Cloudflare R2

| Attribute | Detail |
|-----------|--------|
| Status | **Production Ready** |
| Files | `docs/config/settings/base.py` (storage config) |
| Capabilities | Media file storage (product images, generated content) |
| Auth | Access key + secret (S3-compatible) |
| Package | `boto3`, `django-storages` |

#### Sentry

| Attribute | Detail |
|-----------|--------|
| Status | **Production Ready** |
| Files | `docs/config/settings/production.py` |
| Capabilities | Error monitoring, performance tracing |
| Auth | DSN |
| Package | `sentry-sdk` |

#### Redis

| Attribute | Detail |
|-----------|--------|
| Status | **Production Ready** |
| Files | `docs/config/celery.py`, `docs/config/redis_channels.py` |
| Capabilities | Celery broker, Django Channels layer, caching |
| Auth | URL-based (Railway managed) |

---

### E-Commerce

#### Shopify

| Attribute | Detail |
|-----------|--------|
| Status | **Stub** |
| Files | `analytics/shopify_oauth.py`, `analytics/webhooks.py`, `analytics/models.py` (ShopifyStore) |
| Capabilities | OAuth install, order/product webhooks |
| Notes | OAuth flow exists but integration is untested and likely unused |

---

## Integration Dependency Map

```
CRITICAL (V1 breaks without these):
├── Meta WhatsApp Cloud API (messaging)
├── Meta Graph API (publishing)
├── OpenAI (content generation)
├── M-Pesa Daraja (payments)
├── Redis (task queue + WebSocket)
├── PostgreSQL (database)
└── Cloudflare R2 (media storage)

IMPORTANT (V1 degraded without these):
├── Anthropic (LLM fallback)
├── Together AI (image generation)
├── Photoroom (product images)
├── Tavily (research agent)
├── Resend (email)
├── Sentry (monitoring)
└── Stripe (international payments)

OPTIONAL (V1 works without these):
├── Pollinations (image fallback)
├── HuggingFace (image fallback)
├── Groq (fast transcription)
├── OpenRouter (moderation)
├── Fal.ai (video)
├── Bannerbear (carousels)
└── TikTok / LinkedIn APIs
```

---

## Recommendations

1. **Validate all CRITICAL integrations have fallback behavior.** If WhatsApp API is down, queue messages. If OpenAI is down, try Anthropic. If M-Pesa times out, retry.

2. **Remove platform choices for unimplemented providers.** Twitter, YouTube, Pinterest, Threads, Bluesky should not appear in any UI dropdown until providers exist.

3. **Consolidate image generation fallback chain.** Together → Pollinations → HuggingFace is already implemented; ensure it's tested.

4. **Verify Shopify integration status.** If unused, hide from UI. The model and OAuth code can remain dormant.

5. **Monitor API costs.** OpenAI, Anthropic, Photoroom, and Together all have usage-based pricing. Ensure token budgets and plan limits prevent cost overrun.

6. **Document API key requirements.** Create a clear checklist of all required environment variables with instructions for obtaining each key.
