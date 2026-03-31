# Kova Agent — WhatsApp Intelligence Roadmap
> "Own the Most Important Channel in Kenya"

**Last updated:** March 31, 2026
**Phase:** 5 (Post-Launch)
**Status:** Planning — Zero code implemented yet
**Depends on:** Phase 3 completion (Engage Agent, Orchestration)

---

## Table of Contents
1. [Why WhatsApp](#1-why-whatsapp)
2. [WhatsApp Cloud API — Capability Map](#2-whatsapp-cloud-api--capability-map)
3. [Current Kova Architecture Readiness](#3-current-kova-architecture-readiness)
4. [Strategic Capabilities — What Kova Leverages](#4-strategic-capabilities--what-kova-leverages)
5. [Build Sprints](#5-build-sprints)
6. [Data Models & Schema](#6-data-models--schema)
7. [WhatsApp Pricing & Costs](#7-whatsapp-pricing--costs)
8. [Competitive Moat Analysis](#8-competitive-moat-analysis)
9. [Risks & Mitigations](#9-risks--mitigations)
10. [Technical References](#10-technical-references)

---

## 1. Why WhatsApp

### The Kenya Market Reality
- **90%+ smartphone penetration** with WhatsApp installed
- **7.4M+ MSMEs** already running businesses through WhatsApp (informal commerce)
- WhatsApp Status is viewed **more than Instagram Stories** in Kenya
- WhatsApp is the **default communication channel** for customer service, sales, and marketing
- M-Pesa + WhatsApp = the actual commerce stack for most Kenyan businesses

### The Gap
Every existing WhatsApp business tool (WATI, Respond.io, Twilio, 360dialog) is a **message routing platform** — they help you send and receive messages but have zero intelligence about:
- **What** to say (no AI content generation)
- **When** to say it (no send-time optimization)
- **How** to say it (no brand voice training)
- **What's working** (no AI-driven analytics feedback loop)
- **What's trending** (no cultural/meme intelligence)

Kova fills this gap with **6 AI agents that understand the brand, the audience, and the Kenyan market**.

### The Uniqueness Test
> "If someone can say 'this is like WATI/Respond.io', we haven't innovated enough."

Kova's WhatsApp is NOT a customer support inbox. It's an **AI-native content + engagement engine** that happens to operate on WhatsApp. The agents ARE the product. WhatsApp is the channel.

---

## 2. WhatsApp Cloud API — Capability Map

The WhatsApp Cloud API (hosted by Meta, no on-prem server needed) provides these capabilities via Graph API:

### 2.1 Message Types

| Type | Description | API Support | Kova Use Case |
|------|-------------|-------------|---------------|
| **Text** | Plain text messages (up to 4096 chars) | ✅ Full | Customer replies, AI responses, content distribution |
| **Image** | JPEG/PNG (up to 5MB) | ✅ Full | AI-generated visuals (FLUX via HuggingFace), product photos |
| **Video** | MP4 (up to 16MB) | ✅ Full | Video content repurposed from TikTok/Reels |
| **Audio** | AAC, MP3, OGG (up to 16MB) | ✅ Full | Voice notes, audio content |
| **Document** | PDF, DOC, etc. (up to 100MB) | ✅ Full | Catalogs, invoices, reports |
| **Location** | GPS coordinates + label | ✅ Full | Store locations, event venues |
| **Contacts** | vCard format | ✅ Full | Sales handoffs, referrals |
| **Sticker** | WebP format (static/animated) | ✅ Full | Brand personality, engagement |
| **Reaction** | Emoji reaction to specific message | ✅ Full | Quick acknowledgments |

### 2.2 Interactive Messages

| Type | Description | Limits | Kova Use Case |
|------|-------------|--------|---------------|
| **Reply Buttons** | Quick-action buttons in message | Up to 3 buttons | Yes/No surveys, quick confirmations |
| **List Messages** | Expandable menu with sections | Up to 10 items, 10 sections | Product menus, service options, appointment slots |
| **CTA URL Buttons** | Drive traffic to external links | Up to 2 buttons | Website, landing pages, payment links |
| **Single Product** | Show one product from catalog | Requires catalog | Product recommendations |
| **Multi-Product** | Show multiple products in sections | Up to 30 products | Product browsing, catalog sharing |

### 2.3 Template Messages (Outbound Marketing)

Templates are the **only way** to start a conversation with a user outside the 24-hour messaging window. They must be pre-approved by Meta.

| Category | Purpose | Kova Use Case |
|----------|---------|---------------|
| **Marketing** | Promotions, product launches, re-engagement | AI-drafted campaigns, broadcast |
| **Utility** | Order updates, shipping, appointments | Automated notifications |
| **Authentication** | OTPs, account verification | User verification flows |

Template features:
- **Dynamic variables**: `{{1}}` for name, `{{2}}` for order number — personalization at scale
- **Header media**: Image, video, or document in template header
- **Quick reply buttons**: Up to 3 buttons
- **CTA buttons**: URL or phone number buttons
- **Multi-language**: Submit templates in multiple languages

### 2.4 WhatsApp Flows (Structured Conversations)

Interactive multi-screen forms that run **inside WhatsApp** — no external links needed:

- Text inputs, dropdowns, date pickers, radio buttons, checkboxes
- Multi-screen navigation with back/continue
- Built-in data validation
- Backend endpoint integration (Django webhook)
- Dynamic data from API (personalized screens)

**Pre-built use case templates from Meta:**
- Lead generation forms
- Personalized offers / product recommendations
- Insurance quotes / loan applications (pre-approved loans)
- Purchase intent collection
- Customer onboarding
- Appointment booking
- Surveys and feedback

### 2.5 Webhooks (Real-Time Events)

| Event | Payload | Kova Action |
|-------|---------|-------------|
| **Message received** | Text, media, location, contacts, interactive reply | Route to Engage Agent for AI response |
| **Message status** | sent → delivered → read → failed | Update analytics, retry on failure |
| **Button clicked** | Button ID + payload | Track engagement, trigger next step |
| **Flow completed** | Form submission data (JSON) | Process leads, update CRM, trigger drip |
| **Template status** | approved / rejected / paused | Alert user, suggest fixes |
| **Account alerts** | Policy violations, rate limit warnings | Proactive compliance alerts |

### 2.6 Commerce & Catalog

| Feature | Description | API Support |
|---------|-------------|-------------|
| **Product Catalog** | Upload product inventory (synced with Meta Commerce Manager) | ✅ Full |
| **Single Product Message** | Product with image, price, description, CTA | ✅ Full |
| **Multi-Product Message** | Up to 30 products in sections | ✅ Full |
| **Cart** | Users build carts within WhatsApp | ✅ Full |
| **Order management** | Order creation, updates, status tracking | ✅ Full |

### 2.7 Business Profile & Verification

| Feature | Description |
|---------|-------------|
| **Verified badge** | Green checkmark (requires Meta Business Verification) |
| **Business info** | Description, address, website, email, category |
| **Profile photo** | Brand logo/photo |
| **Operating hours** | When the business is available |

### 2.8 What the API Does NOT Support

| Feature | Status | Workaround |
|---------|--------|------------|
| **Status/Stories posting** | ❌ No API | One-tap deep link share (pre-loaded media) |
| **Group management** | ❌ No API | None — not a business use case |
| **Channels (full)** | ⚠️ Limited/Expanding | Future-ready architecture |
| **Voice/Video calls** | ❌ No API | None |
| **Message editing** | ❌ No API | Send correction message |
| **Message deletion** | ❌ No API | None |

---

## 3. Current Kova Architecture Readiness

### What's Already Built (and ready to extend)

| Component | File | Status | WhatsApp Readiness |
|-----------|------|--------|-------------------|
| **Platform choices** | `apps/platforms/models.py` | 5 platforms defined | Add `WHATSAPP = "whatsapp"` — 1 line + migration |
| **Provider base class** | `apps/platforms/providers/base.py` | Abstract interface | WhatsApp provider extends this |
| **Provider registry** | `apps/platforms/providers/registry.py` | Dynamic lookup | Register WhatsApp provider |
| **Engage app (DMs)** | `apps/engage/models.py` | `DM = "dm"` interaction type exists | WhatsApp messages route here |
| **AI image generation** | `apps/agents/media.py` | HuggingFace FLUX working | Generate WhatsApp-optimized visuals |
| **Create Agent** | `apps/agents/create_agent.py` | Content generation | Add WhatsApp message/template drafting |
| **Analyst Agent** | `apps/agents/analyst_agent.py` | Performance analysis | Add WhatsApp delivery/read rate analysis |
| **Adapt Agent** | `apps/agents/adapt_agent.py` | Send-time optimization | Optimize WhatsApp send times per contact |
| **Research Agent** | `apps/agents/research_agent.py` | Trend detection | Feed trends into WhatsApp content |
| **Scheduling system** | `apps/content/scheduling.py` | Conflict-aware scheduling | WhatsApp message scheduling |
| **Celery Beat** | `config/celery.py` | 5 periodic tasks running | Add WhatsApp webhook processing, broadcast tasks |
| **Webhook infrastructure** | — | Not built yet | Need: endpoint + verification + event routing |
| **Notification system** | `apps/notifications/` | In-app notifications | Extend for WhatsApp delivery alerts |

### What Needs Building

| Component | Effort | Description |
|-----------|--------|-------------|
| `apps/platforms/providers/whatsapp.py` | **Medium** | Cloud API provider (messaging, templates, media) |
| WhatsApp webhook endpoint | **Medium** | Verify + receive + route incoming events |
| Template management UI | **Medium** | Create, submit, track approval status |
| WhatsApp conversation model | **Medium** | Thread-based message storage |
| Interactive message builder | **High** | Visual builder for buttons, lists, flows |
| WhatsApp Flows integration | **High** | Flow JSON generation, endpoint handler |
| Catalog sync | **High** | Sync products with Meta Commerce Manager |
| Broadcast campaign system | **High** | Segmentation, scheduling, drip sequences |
| WhatsApp analytics dashboard | **Medium** | Delivery rates, read rates, response times |

---

## 4. Strategic Capabilities — What Kova Leverages

### 4.1 AI-Generated Template Messages (Create Agent)

**The problem:** Businesses spend hours crafting WhatsApp templates, submit them to Meta, get rejected, rewrite, resubmit. Cycle takes days.

**Kova's approach:**
- User describes campaign intent: "Promote our Friday chapati special to lunch regulars"
- Create Agent drafts template with proper variable slots: `Hi {{1}}, this Friday only: 2 chapatis + chai for KES 150. Order now 👇`
- AI validates against Meta's template policies BEFORE submission (language, formatting, prohibited content)
- Auto-suggests header media from AI image generation
- Analyst Agent tracks which template categories/formats get highest open + reply rates
- Feedback loop: performance data improves future template drafts

**Uniqueness:** No tool auto-generates Meta-policy-compliant templates with AI. Most businesses copy-paste from WhatsApp template galleries.

### 4.2 Conversational AI Auto-Reply (Engage Agent)

**The problem:** Kenyan MSMEs miss 60%+ of WhatsApp messages because they can't reply fast enough. Every unanswered message is a lost sale.

**Kova's approach:**
- AI auto-replies to incoming messages in the customer's language (Swahili, Sheng, English — auto-detected)
- Brand voice trained — doesn't sound like a generic chatbot
- Confidence-based routing:
  - **High confidence** (FAQ, greetings, product inquiries): AI replies immediately
  - **Medium confidence** (complaints, complex questions): AI drafts reply, flags for human review
  - **Low confidence** (sensitive topics, angry customers): Routes to human with full context summary
- Catalog integration: "Do you have red shoes?" → AI searches catalog → sends product card with price
- Context memory: Knows previous conversation history, doesn't ask repeated questions

**Uniqueness:** Language intelligence (Swahili/Sheng) + brand voice training. No WhatsApp tool does this for the Kenyan market.

### 4.3 Interactive Message Intelligence (Create Agent + Analyst Agent)

**The problem:** Most businesses send plain text on WhatsApp. Interactive messages (buttons, lists) get 3-5x higher engagement but are complex to build.

**Kova's approach:**
- Create Agent auto-generates interactive message structures from natural language briefs
- "Create a product menu for our lunch specials" → AI generates List Message JSON with sections, items, descriptions
- "Ask customers if they want delivery or pickup" → AI generates Reply Button message
- Analyst Agent tracks button click rates, list item selection rates
- Auto-optimize: swap button order based on click data, A/B test list item descriptions

**Uniqueness:** AI generates the interactive JSON structures. Competing tools require manual form-filling.

### 4.4 WhatsApp Flows Generation (Create Agent — 10x Opportunity)

**The problem:** WhatsApp Flows are incredibly powerful (interactive forms inside WhatsApp) but require writing Flow JSON — a complex spec that most businesses can't handle.

**Kova's approach:**
- Natural language → Flow JSON: "Create a lead capture form for my real estate business"
- AI generates multi-screen flow: contact info → property preferences → budget range → schedule viewing
- Pre-built Flow templates for Kenyan market verticals:
  - M-Pesa collection preference forms
  - Property viewing bookings
  - Loan/insurance applications
  - Restaurant ordering
  - Event RSVP
  - Customer feedback surveys
- Analyst Agent A/B tests Flow variants (which screen order converts best?)
- Flow completion data feeds back into Kova's analytics

**Uniqueness:** Nobody combines AI generation with WhatsApp Flows. This is category creation — "conversational form builder powered by AI."

### 4.5 Broadcast Campaign Intelligence (Adapt Agent + Analyst Agent)

**The problem:** WhatsApp broadcasts feel spammy when everyone gets the same message at the same time. Businesses get blocked and lose their number.

**Kova's approach:**
- **Smart segmentation**: AI segments contacts by behavior (purchase history, message frequency, response patterns)
- **Per-contact timing**: Adapt Agent sends each message at the optimal time for THAT contact (not batch blast)
- **Drip sequences**: Multi-message campaigns spaced over days/weeks (onboarding, re-engagement, cart abandonment)
- **Compliance guard**: AI checks templates against Meta policies before submission
- **Throttling**: Auto-throttle send rate to stay within Meta's quality rating thresholds
- **Feedback loop**: Analyst Agent tracks open rates, reply rates, block rates per segment → adjusts strategy

**Uniqueness:** Per-contact send-time optimization + AI compliance checking. No WhatsApp tool does intelligent timing per recipient.

### 4.6 AI Image Generation → WhatsApp (Media Pipeline)

**Already built:** `apps/agents/media.py` generates images via HuggingFace FLUX.

**WhatsApp extension:**
- Generate WhatsApp-optimized images (1080×1080 for messages, 1920×1080 for Status)
- Template header images auto-generated from campaign brief
- Product catalog images enhanced with AI (background removal, text overlay)
- Meme adaptation: Take trending meme format → insert brand context → WhatsApp-ready

### 4.7 Meme Intelligence Engine (Research Agent — THE MOAT)

**The problem:** Memes drive engagement on Kenyan WhatsApp but there's no tool to systematically find, score, and adapt them for brands.

**Kova's approach:**
- **Trend detection**: Monitor KOT (Kenyan Twitter), TikTok Kenya, Reddit r/Kenya, FB meme pages
- **Meme ranking**: Score by virality velocity, brand-safety, cultural relevance, humor type
- **Cultural intelligence**: Sheng references, political context (safe vs risky), local events (Mashujaa Day, KPL season)
- **Meme adaptation**: AI takes trending meme FORMAT and adapts to user's brand/product
  - Not reposting — REMIXING (original meme format + brand context = viral brand content)
- **Status queue**: Memes auto-queued for WhatsApp Status at Kenya peak times (6-8am, 12-1pm, 6-9pm)
- **Celery Beat task**: `discover-trending-memes` — runs every 2-4 hours

**Uniqueness:** AI-powered meme intelligence localized to Kenya. Nobody does this.

### 4.8 Status Content Studio

**The problem:** WhatsApp Status has no API for direct posting. But it's the most-viewed story format in Kenya.

**Kova's workaround:**
- **Status Content Queue**: AI curates content optimized for Status format (vertical, short, visual, punchy)
- **One-tap share**: Deep link to WhatsApp with pre-loaded media — user taps once to post
- **Smart scheduling**: AI learns when user's contacts are most active on Status
- **Mix optimization**: Don't post 3 promos in a row — AI mixes memes, quotes, BTS, offers
- **Cross-platform repurpose**: Take LinkedIn/IG/TikTok post → AI adapts for Status format
- **Status calendar**: 7-day visual planner

---

## 5. Build Sprints

### Sprint 5A: WhatsApp Provider + Conversational AI
**Goal:** WhatsApp connected. AI handles customer conversations 24/7.

| Task | Priority | Effort | Details |
|------|----------|--------|---------|
| Add `WHATSAPP` to `SocialAccount.Platform` | P0 | Low | 1 line + migration |
| Create `apps/platforms/providers/whatsapp.py` | P0 | Medium | Extends BaseProvider, Cloud API integration |
| OAuth flow via Meta Business credentials | P0 | Medium | Shared infra with FB/IG provider |
| Send messages (text, image, video, document) | P0 | Medium | Graph API `/messages` endpoint |
| Receive messages via webhook | P0 | Medium | Webhook verification + event routing |
| Template message registration + sending | P1 | Medium | Create, submit for approval, send |
| Interactive messages (buttons, lists, CTAs) | P1 | Medium | JSON structure generation |
| Business profile management | P2 | Low | Name, about, photo, address |
| Conversational AI auto-reply | P1 | Medium | Engage Agent + language detection |
| Language intelligence (Swahili/Sheng/English) | P1 | Medium | Auto-detect, respond in same language |
| Smart routing (AI → human handoff) | P1 | Medium | Confidence-based escalation |
| Catalog assistant | P2 | High | Product search → card responses |

### Sprint 5B: Meme Intelligence Engine
**Goal:** Users get auto-curated, brand-adapted memes from Kenyan trends.

| Task | Priority | Effort | Details |
|------|----------|--------|---------|
| Trend detection (KOT, TikTok KE, Reddit, FB) | P0 | High | Multi-source scraping + scoring |
| Meme ranking algorithm | P0 | Medium | Virality, brand-safety, cultural relevance |
| Cultural intelligence layer | P1 | High | Sheng, political context, local events |
| Meme adaptation (AI remix) | P0 | High | Take format → insert brand context |
| Meme queue with Kenya peak times | P1 | Low | 6-8am, 12-1pm, 6-9pm |
| Celery Beat: `discover-trending-memes` | P1 | Low | Every 2-4 hours |

### Sprint 5C: Status Content Studio
**Goal:** AI-powered Status content pipeline. User taps once to share.

| Task | Priority | Effort | Details |
|------|----------|--------|---------|
| Status content queue | P0 | Medium | AI-curated, format-optimized |
| One-tap share (deep link) | P0 | Low | WhatsApp deep link with pre-loaded media |
| Status templates (product, offer, testimonial, BTS, poll) | P1 | Medium | Pre-built formats |
| AI content generation (Status-optimized) | P1 | Medium | Short, visual, punchy, Kenyan tone |
| Smart scheduling | P2 | Low | Adapt Agent learns contact activity |
| Status calendar (7-day planner) | P2 | Medium | Visual UI with mix optimization |
| Cross-platform repurposing | P2 | Medium | LinkedIn/IG/TikTok → Status format |

### Sprint 5D: Broadcast Intelligence + Analytics
**Goal:** WhatsApp becomes a measurable growth channel.

| Task | Priority | Effort | Details |
|------|----------|--------|---------|
| Smart segmentation | P0 | High | AI segments by behavior/history |
| Campaign builder UI | P0 | High | Visual builder with personalization |
| Drip sequences | P1 | High | Multi-day automated sequences |
| Per-contact timing optimization | P1 | Medium | Adapt Agent per-recipient scheduling |
| Compliance guard | P1 | Medium | Auto-check Meta policies before submit |
| Message analytics dashboard | P0 | Medium | Delivery, read, response rates |
| Customer sentiment analysis | P2 | Medium | Trend sentiment over time |
| Revenue attribution | P2 | High | Link conversations to sales |

### Sprint 5E: WhatsApp Flows + Channels
**Goal:** Interactive forms in WhatsApp. Channel management. Future-ready.

| Task | Priority | Effort | Details |
|------|----------|--------|---------|
| WhatsApp Flows integration | P0 | High | Flow JSON generation + endpoint handler |
| AI Flow generation (NL → Flow JSON) | P1 | High | Natural language → multi-screen forms |
| Pre-built Flow templates (Kenya verticals) | P1 | Medium | M-Pesa, real estate, restaurant, events |
| Flow analytics (completion rates, drop-off) | P2 | Medium | A/B test Flow variants |
| Channel content curation | P2 | Medium | AI selects best content for channel |
| Cross-post from Kova to Channel | P2 | Medium | Adapt content from other platforms |
| Channel growth analytics | P3 | Low | Follower trends, reach, engagement |

---

## 6. Data Models & Schema

### New Models Needed

```
WhatsAppAccount (extends SocialAccount or separate)
├── phone_number_id          # Meta's phone number ID
├── waba_id                  # WhatsApp Business Account ID
├── business_profile         # JSONField (name, about, photo, address, hours)
├── quality_rating           # green/yellow/red (from Meta)
├── messaging_limit          # current tier (1K, 10K, 100K, unlimited)
└── catalog_id               # linked Commerce Manager catalog

WhatsAppConversation
├── social_account           # FK to SocialAccount
├── contact_phone            # customer's phone (hashed for privacy)
├── contact_name             # push name from WhatsApp
├── status                   # active / closed / escalated
├── language                 # detected: en / sw / sheng
├── last_message_at          # for 24-hour window tracking
├── ai_handling              # bool — is AI currently handling this?
├── sentiment_score          # running average from Analyst Agent
└── tags                     # JSONField — customer segments

WhatsAppMessage
├── conversation             # FK to WhatsAppConversation
├── direction                # inbound / outbound
├── message_type             # text / image / video / audio / document / interactive / template / flow
├── content                  # text content or media URL
├── interactive_data         # JSONField (buttons, lists, flow responses)
├── wamid                    # WhatsApp message ID (for status tracking)
├── status                   # sent / delivered / read / failed
├── status_updated_at        # last status change
├── is_ai_generated          # bool
├── confidence_score         # AI confidence when auto-replied
└── template                 # FK to WhatsAppTemplate (if template message)

WhatsAppTemplate
├── social_account           # FK to SocialAccount
├── name                     # template name (Meta requirement)
├── category                 # marketing / utility / authentication
├── language                 # en, sw, etc.
├── header_type              # none / text / image / video / document
├── body_text                # template body with {{variables}}
├── footer_text              # optional footer
├── buttons                  # JSONField (quick_reply or cta buttons)
├── status                   # draft / submitted / approved / rejected / paused
├── rejection_reason         # from Meta if rejected
├── performance_data         # JSONField (open_rate, reply_rate, block_rate)
└── created_by_ai            # bool — drafted by Create Agent?

WhatsAppBroadcast
├── social_account           # FK to SocialAccount
├── name                     # campaign name
├── template                 # FK to WhatsAppTemplate
├── segment                  # JSONField (targeting criteria)
├── scheduled_at             # when to start sending
├── status                   # draft / scheduled / sending / completed / paused
├── total_recipients         # count
├── delivered_count          # running count
├── read_count               # running count
├── replied_count            # running count
└── failed_count             # running count

WhatsAppFlow
├── social_account           # FK to SocialAccount
├── name                     # flow name
├── flow_id                  # Meta's Flow ID
├── flow_json                # JSONField — the Flow definition
├── status                   # draft / published / deprecated
├── category                 # lead_gen / survey / booking / commerce / custom
├── completions_count        # total completions
├── drop_off_screen          # which screen has highest drop-off
└── created_by_ai            # bool — generated by Create Agent?
```

### Existing Model Changes

```
SocialAccount.Platform:
    + WHATSAPP = "whatsapp", "WhatsApp"

Interaction (engage app):
    # Already has DM type — WhatsApp messages route here
    # Add: whatsapp_message FK (nullable) for linking

Post model:
    # Already supports WhatsApp via social_account FK
    # Add: template FK (nullable) for template-based posts
```

---

## 7. WhatsApp Pricing & Costs

### Meta's Conversation-Based Pricing (as of 2025)

WhatsApp charges per **conversation** (24-hour window), not per message.

| Conversation Type | Who Initiates | Cost (Kenya, USD) | Notes |
|---|---|---|---|
| **Marketing** | Business → User (template) | ~$0.0490 | Promotions, offers |
| **Utility** | Business → User (template) | ~$0.0200 | Order updates, confirmations |
| **Authentication** | Business → User (template) | ~$0.0154 | OTPs, verification |
| **Service** | User → Business | FREE (first 1,000/mo) | Customer-initiated conversations |

### Cost Implications for Kova's Billing Tiers

| Kova Plan | Monthly Price | WhatsApp Budget Allocation | Estimated Conversations |
|-----------|--------------|---------------------------|------------------------|
| Jipange (KES 99) | ~$0.70 | Not included | WhatsApp is Growth+ feature |
| Kazi (KES 500) | ~$3.50 | ~$1.00 | ~20 marketing + free service |
| Biashara (KES 1,500) | ~$10.50 | ~$3.00 | ~60 marketing + free service |
| Wakala (KES 3,500) | ~$24.50 | ~$8.00 | ~160 marketing + free service |

**Business model consideration:** WhatsApp conversations have a real marginal cost. Options:
1. **Include a base allocation** per plan tier (above)
2. **Pass-through pricing** — charge users per conversation at cost + margin
3. **Hybrid** — include base allocation, charge overage at markup

### Free Tier (1,000 Service Conversations/month)
User-initiated conversations are free for the first 1,000/month. This means Kova users can handle customer inquiries at zero WhatsApp cost — the AI auto-reply system is effectively free to run for small businesses.

---

## 8. Competitive Moat Analysis

### Kova vs. Existing WhatsApp Tools

| Capability | WATI | Respond.io | Twilio | 360dialog | **Kova** |
|---|---|---|---|---|---|
| Send/receive messages | ✅ | ✅ | ✅ | ✅ | ✅ |
| Template management | ✅ | ✅ | ✅ | ✅ | ✅ + **AI drafting** |
| Broadcast campaigns | ✅ | ✅ | ✅ | ✅ | ✅ + **AI segmentation + per-contact timing** |
| Chatbot auto-reply | Basic rules | Basic rules | None | Basic rules | **AI with brand voice + language detection** |
| Multi-platform (social + WhatsApp) | ❌ | Partial | ❌ | ❌ | **✅ 6 platforms + WhatsApp** |
| AI content generation | ❌ | ❌ | ❌ | ❌ | **✅ 6 agents** |
| Send-time optimization | ❌ | ❌ | ❌ | ❌ | **✅ Adapt Agent** |
| Performance analytics with AI insights | ❌ | Basic | ❌ | ❌ | **✅ Analyst Agent** |
| Swahili/Sheng intelligence | ❌ | ❌ | ❌ | ❌ | **✅ Language detection** |
| Meme intelligence (Kenya) | ❌ | ❌ | ❌ | ❌ | **✅ Research Agent** |
| WhatsApp Flows + AI generation | ❌ | ❌ | ❌ | ❌ | **✅ Create Agent** |
| AI image generation | ❌ | ❌ | ❌ | ❌ | **✅ HuggingFace FLUX** |
| Kenya market pricing | $49+/mo | $79+/mo | Pay-per-msg | €49+/mo | **KES 500 (~$3.50)** |

### The 3 Moats

1. **AI-native, not AI-bolted-on**: 6 specialized agents trained on brand voice, not generic chatbot rules
2. **Multi-platform unified**: Same AI manages Facebook + Instagram + Twitter + LinkedIn + TikTok + WhatsApp — competitors are WhatsApp-only
3. **Kenya-first pricing & intelligence**: KES pricing, Swahili/Sheng support, local meme intelligence, M-Pesa-aware commerce flows

---

## 9. Risks & Mitigations

| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| **Meta policy changes** | Template rejections, account bans | Medium | Compliance guard AI, policy monitoring, conservative templates |
| **WhatsApp quality rating drops** | Reduced messaging limits | Medium | Throttling, segment hygiene, opt-out handling, block rate monitoring |
| **24-hour window expiry** | Can't reply after 24h without template | High (by design) | Auto-prompt template follow-up before window closes |
| **Conversation costs spike** | Margin erosion | Medium | Per-conversation budgets, usage alerts, plan enforcement |
| **Status API never opens** | Status Studio limited to deep links | Medium | Deep link approach works, just less seamless |
| **Competition copies AI features** | Differentiation erodes | Low (short-term) | Move fast, go deep on Kenya market, build network effects |
| **WhatsApp Business API access** | Requires Meta Business Verification | Low | Already documented in setup guide, user onboarding handles this |
| **Swahili/Sheng LLM quality** | Poor auto-replies in local languages | Medium | Fine-tune prompts, human review for low-confidence, feedback loop |

---

## 10. Technical References

| Resource | URL | Notes |
|----------|-----|-------|
| WhatsApp Cloud API Docs | `developers.facebook.com/docs/whatsapp/cloud-api` | Main API reference |
| Message Types Reference | `developers.facebook.com/docs/whatsapp/cloud-api/reference/messages` | All message type schemas |
| Template Messages | `developers.facebook.com/docs/whatsapp/cloud-api/guides/send-message-templates` | Template creation + sending |
| Interactive Messages | `developers.facebook.com/docs/whatsapp/cloud-api/guides/send-messages#interactive-messages` | Buttons, lists, products |
| WhatsApp Flows | `developers.facebook.com/docs/whatsapp/flows` | Flow JSON spec + guides |
| Webhooks | `developers.facebook.com/docs/whatsapp/cloud-api/webhooks` | Event types + verification |
| Commerce / Catalogs | `developers.facebook.com/docs/whatsapp/cloud-api/guides/sell-products-and-services` | Product messages + catalog |
| Business Management API | `developers.facebook.com/docs/whatsapp/business-management-api` | Account, phone, template CRUD |
| Pricing | `developers.facebook.com/docs/whatsapp/pricing` | Conversation-based pricing |
| WhatsApp Business Policy | `business.whatsapp.com/policy` | What you can/can't do |
| Graph API Explorer | `developers.facebook.com/tools/explorer` | Test API calls |
| Flow Playground | `developers.facebook.com/docs/whatsapp/flows/playground` | Preview flows visually |

---

## Appendix: Implementation Checklist

When we start building, here's the file-level checklist:

```
□ apps/platforms/models.py          → Add WHATSAPP to Platform choices
□ apps/platforms/migrations/000X    → Migration for new choice
□ apps/platforms/providers/whatsapp.py → New provider (Cloud API)
□ apps/platforms/webhooks.py        → WhatsApp webhook handler
□ apps/engage/models.py             → WhatsApp conversation/message models
□ apps/engage/migrations/000X       → Migration for new models
□ apps/engage/views.py              → WhatsApp inbox views
□ apps/agents/create_agent.py       → Add template/interactive message generation
□ apps/agents/analyst_agent.py      → Add WhatsApp analytics
□ apps/agents/adapt_agent.py        → Add per-contact timing
□ config/settings/base.py           → WHATSAPP_* settings
□ config/urls.py                    → Webhook URL route
□ templates/platforms/whatsapp/     → WhatsApp-specific templates
□ templates/engage/whatsapp/        → Conversation UI templates
□ static/js/whatsapp.js             → Real-time message UI (WebSocket?)
```

---

*This document is the strategic and technical blueprint for Kova's WhatsApp integration. It should be updated as we progress through the build sprints.*
