# WhatsApp-First Assessment

**Date:** July 2026

---

## Current WhatsApp Infrastructure

Kova has a **remarkably mature** WhatsApp implementation across 14 dedicated modules:

| Module | Purpose | Status |
|--------|---------|--------|
| `whatsapp/webhook.py` | Meta Cloud API inbound messages, status updates | Production |
| `whatsapp/services.py` | Unified outbound messaging, 24h window management | Production |
| `whatsapp/commerce.py` | Conversational commerce state machine | Production |
| `whatsapp/commerce_enhanced.py` | Enhanced cart, M-Pesa in-chat, post-purchase | Production |
| `whatsapp/autopilot.py` | FAQ auto-replies, follow-up nudges | Production |
| `whatsapp/draft_actions.py` | AI draft approval from web inbox | Production |
| `whatsapp/owner_onboarding.py` | WhatsApp-first onboarding flow | Production |
| `whatsapp/memory.py` | Per-customer memory for returning buyers | Production |
| `whatsapp/tasks.py` | Async message handling, broadcasts, sequences | Production |
| `briefs/whatsapp_commands.py` | Owner reply-to-act commands | Production |
| `briefs/whatsapp_buttons.py` | Interactive button definitions | Production |
| `content/campaign_whatsapp.py` | Campaign approval via WhatsApp | Production |
| `products/owner_snap_whatsapp.py` | Snap-to-Sell via master number | Production |
| `billing/whatsapp_access.py` | Plan gating for WhatsApp features | Production |

---

## Owner Commands (WhatsApp → Business Operations)

The owner can currently perform these operations via WhatsApp:

| Command | Action | Status |
|---------|--------|--------|
| `STANDUP` / `MORNING` | Full morning standup digest | Implemented |
| `BRIEF` | Today's headline + recommended action | Implemented |
| `SCORE` | Kova score + delta | Implemented |
| `APPROVE` | Approve next pending post | Implemented |
| `APPROVE ALL` | Approve all pending posts | Implemented |
| `APPROVE CAMPAIGN` | Approve full campaign package | Implemented |
| `REJECT` | Reject next pending post | Implemented |
| `REJECT ALL` | Reject all pending posts | Implemented |
| `POSTS` | Pending approval count | Implemented |
| `LEADS` | Hot leads + need reply summary | Implemented |
| `MONEY` | Revenue + leads this week | Implemented |
| `BOOK` | Booking page link + services | Implemented |
| `SNAP` (+ photo) | Create product from photo | Implemented |
| `CAMPAIGNS` | Campaigns ready to approve | Implemented |
| `OPPORTUNITIES` | Growth moves Kova spotted | Implemented |
| `SHARE` | Campaign + shop links for Status | Implemented |
| `REPLIES` | AI reply drafts waiting for approval | Implemented |
| `APPROVE REPLY` | Send latest AI draft | Implemented |
| `REJECT REPLY` | Discard latest AI draft | Implemented |
| `HELP` | List all commands | Implemented |

---

## Customer-Facing WhatsApp Features

| Feature | Description | Status |
|---------|-------------|--------|
| Commerce State Machine | Browse → Product Detail → Book/Pay flow | Implemented |
| Keyword Triggers | "menu", "products", "buy", "book" etc. in English + Swahili | Implemented |
| M-Pesa In-Chat | STK Push initiated from WhatsApp conversation | Implemented |
| FAQ Autopilot | Auto-answer common questions when owner is away | Implemented |
| Follow-up Nudges | 24h reminder for unanswered conversations | Implemented |
| Customer Memory | Remember returning buyers, preferences, purchase history | Implemented |
| AI Auto-Reply | LLM-powered contextual responses | Implemented |
| Interactive Buttons | Structured reply options for browsing/booking | Implemented |
| WhatsApp Templates | Pre-approved broadcast messages | Implemented |
| Broadcast Sequences | Multi-step drip campaigns | Implemented |
| WhatsApp Status | Content publishing to Status | Implemented |
| WhatsApp Channels | Broadcast-only channels | Implemented |

---

## Workflows That Currently Assume Web Interaction

These workflows require the business owner to open the web platform. Each should be assessed for WhatsApp-first conversion:

### HIGH PRIORITY — Should Be WhatsApp-Native in V1

| Workflow | Current Interface | WhatsApp Alternative | Effort |
|----------|------------------|---------------------|--------|
| **Add a product** | Web form (`product_form.html`) | Already partially done via Snap-to-Sell. Enhance to accept text descriptions too. | Low |
| **Update prices** | Web form edit | Owner sends "price [product] [amount]" | Medium |
| **View daily report** | Web brief page | Already delivered as Daily Brief. Ensure completeness. | Done |
| **Respond to customers** | Web WhatsApp inbox | WhatsApp auto-forwarding of customer messages to owner's number | Medium |
| **Approve content** | Web approval UI | Already done via APPROVE command | Done |
| **View revenue** | Web analytics page | Already done via MONEY command | Done |
| **Check leads** | Web leads page | Already done via LEADS command | Done |
| **Publish a post** | Web content studio | Already possible via Snap (photo → content). Add "post [text]" command. | Medium |

### MEDIUM PRIORITY — Should Be WhatsApp-Native in V1.1

| Workflow | Current Interface | WhatsApp Alternative | Effort |
|----------|------------------|---------------------|--------|
| **Schedule content** | Web calendar drag-drop | "Schedule [post] for [time]" command | High |
| **View analytics** | Web insights page | Expand BRIEF with performance metrics | Medium |
| **Manage booking availability** | Web form | "Available [days/times]" command | Medium |
| **Update business info** | Web settings page | "Update [field] to [value]" conversational | Medium |
| **Create a campaign** | Web campaign form | "Campaign for [product/event]" → AI generates | High |
| **Add product category** | Web form | "Category [name]" command | Low |
| **Set up FAQ answers** | Web settings | "When asked about [X], reply [Y]" | Medium |

### LOW PRIORITY — Web Appropriate (Configuration)

| Workflow | Current Interface | Justification for Staying Web |
|----------|------------------|-------------------------------|
| Connect social accounts | OAuth flow | Requires browser redirects for OAuth |
| Manage team members | Web team settings | Infrequent, complex permissions |
| Configure billing/plan | Web billing page | Security-sensitive, infrequent |
| Set brand voice/DNA | Web Business Brain page | One-time deep configuration |
| Connect WhatsApp number | Web setup flow | One-time technical setup |
| View detailed analytics charts | Web analytics | Data-dense visualization |
| Manage email templates | Web editor | Rich formatting needs |
| Configure automation rules | Web settings | Complex logic configuration |

---

## Gap Analysis: What's Missing for True WhatsApp-First

### Critical Gaps (Must Fix for V1)

1. **No conversational onboarding fallback.** `owner_onboarding.py` exists but the primary onboarding flow is still web-based (3 screens + Business Brain). Should have a WhatsApp-first onboarding path where the web is optional.

2. **Customer message forwarding.** When a customer messages the business WhatsApp, the owner currently needs to check the web inbox OR hope the AI handles it. Need: immediate WhatsApp notification to owner's personal number with quick-reply options.

3. **Product creation beyond photos.** Snap-to-Sell handles photos well, but text-based product creation ("Add product: African print dress, KES 2500, available in S/M/L") isn't implemented.

4. **Price updates via WhatsApp.** No command exists to update product pricing conversationally.

5. **Stock status updates.** No "out of stock [product]" or "back in stock [product]" command.

### Important Gaps (V1.1)

6. **Report delivery improvements.** Weekly/monthly reports should be richer WhatsApp messages with key metrics, not just the daily brief.

7. **Campaign creation flow.** Currently campaigns require web interaction. An AI-guided WhatsApp flow ("I want to promote my new product") would be powerful.

8. **Bulk operations.** Updating multiple products, approving multiple items — need batch command patterns.

9. **Voice note to action.** The voice transcription exists (`content/voice.py`) but isn't wired to WhatsApp voice notes for creating content or products.

---

## Architecture Support Assessment

### What Supports WhatsApp-First Well

- **Conversation context storage** (`conversation.context` JSON) enables stateful multi-turn flows
- **Commerce state machine** provides a proven pattern for complex WhatsApp interactions
- **Owner command dispatch** is extensible — adding new commands is straightforward
- **Interactive buttons/lists** provide structured input beyond free text
- **Customer memory** enables personalized returning-buyer experiences
- **Template lifecycle management** handles Meta's approval flow
- **24h window awareness** correctly manages free-form vs. template-only messaging

### What Needs Improvement

- **No unified command router.** Owner commands are in `briefs/whatsapp_commands.py` but commerce is in `whatsapp/commerce.py` — need a single dispatch layer.
- **Web inbox duplicates WhatsApp.** The web-based conversation view (`whatsapp/views.py`) suggests the web is still expected as a reading interface.
- **Broadcast management is web-only.** Creating and managing broadcast lists/sequences requires the web UI.
- **No WhatsApp-native analytics.** Beyond MONEY and SCORE commands, detailed performance data isn't available conversationally.

---

## Recommendations for V1

1. **Implement "customer alert" forwarding** — when important messages arrive (purchase intent, complaints, new leads), forward a summary to the owner's WhatsApp with action buttons.

2. **Add product management commands** — `PRICE [product] [amount]`, `STOCK [product] [status]`, `ADD [description]`.

3. **Make the web WhatsApp inbox secondary** — it exists for history/search, not as the primary reading interface.

4. **Unify the command dispatch layer** — single entry point that routes to commerce, briefs, products, or AI based on intent.

5. **Wire voice notes to content/product creation** — transcribe → classify intent → create.

---

## WhatsApp Readiness Score

| Dimension | Score | Notes |
|-----------|-------|-------|
| Customer commerce flow | 9/10 | Browse, order, pay — complete |
| Owner daily operations | 8/10 | Brief, approve, score, leads — strong |
| Product management | 5/10 | Snap works; text/price/stock commands missing |
| Content creation | 7/10 | Snap + approve; need "post [text]" and voice |
| Reporting | 7/10 | Daily brief good; weekly/monthly via WhatsApp needed |
| Configuration | 3/10 | Appropriately web-based (OAuth, settings) |
| Onboarding | 4/10 | `owner_onboarding.py` exists but web-primary |

**Overall WhatsApp-First Readiness: 7/10**

The infrastructure is mature. The gaps are primarily about expanding the command vocabulary and ensuring the owner never *needs* to open the web to perform daily operations.
