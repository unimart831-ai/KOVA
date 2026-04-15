# WhatsApp Business Setup Guide — Kova Platform

> **Version**: 1.0 · **Last Updated**: April 16, 2026
> Covers: Platform setup (admin), user onboarding, AI auto-reply, templates, broadcasts, and webhook configuration.

---

## Table of Contents

**Part 1 — Platform Admin Setup**
1. [Prerequisites](#1-prerequisites)
2. [Meta Business Account Setup](#2-meta-business-account-setup)
3. [Create a Meta App](#3-create-a-meta-app)
4. [WhatsApp Business Platform Access](#4-whatsapp-business-platform-access)
5. [Generate a Permanent System User Token](#5-generate-a-permanent-system-user-token)
6. [Configure Environment Variables](#6-configure-environment-variables)
7. [Set Up the Webhook](#7-set-up-the-webhook)
8. [Verify the Setup](#8-verify-the-setup)
9. [Production Checklist](#9-production-checklist)

**Part 2 — User Guide**
10. [Connecting WhatsApp to Your Account](#10-connecting-whatsapp-to-your-account)
11. [The WhatsApp Inbox](#11-the-whatsapp-inbox)
12. [Conversations & Messaging](#12-conversations--messaging)
13. [AI Auto-Reply System](#13-ai-auto-reply-system)
14. [Understanding the 24-Hour Window](#14-understanding-the-24-hour-window)
15. [Message Templates](#15-message-templates)
16. [Broadcasts](#16-broadcasts)
17. [Admin Dashboard Controls](#17-admin-dashboard-controls)
18. [Troubleshooting](#18-troubleshooting)

---

# PART 1 — Platform Admin Setup

This section is for the **Kova platform administrator** (you) who configures the Meta Business integration at the infrastructure level.

---

## 1. Prerequisites

Before starting, confirm you have:

| Requirement | Details |
|---|---|
| **Meta Business Account** | A verified Meta Business account at [business.facebook.com](https://business.facebook.com) |
| **Business Verification** | Your Meta Business account must be **verified** (green checkmark). Unverified accounts are limited to 250 conversations/day |
| **A Phone Number** | A phone number that is NOT already registered with WhatsApp or WhatsApp Business app. You'll register it with the WhatsApp Business Platform |
| **Kova Deployed** | Kova must be deployed with HTTPS (Meta requires TLS for webhooks). Railway, Render, or any host with SSL works |
| **Celery Running** | The Celery worker must be active for AI auto-replies (`celery -A config worker -l info`) |
| **Redis Running** | Redis is required as the Celery broker |

---

## 2. Meta Business Account Setup

### 2.1 Create or Access Your Meta Business Account

1. Go to [business.facebook.com](https://business.facebook.com)
2. Click **Create Account** (or log into your existing one)
3. Fill in your business name, your name, and business email
4. Complete email verification

### 2.2 Verify Your Business

**Why**: Unverified businesses are limited to 250 conversations/day and can only message phone numbers you've added manually. Verified businesses get up to 100K+ conversations/day.

1. Go to **Business Settings** → **Security Center**
2. Click **Start Verification**
3. Provide:
   - Legal business name (must match official documents)
   - Business address
   - Business phone number
   - Business website
   - Tax ID or registration number
4. Upload one of: utility bill, business license, tax certificate, bank statement
5. Meta will send a verification code via phone or email — enter it to complete

> ⏱ Verification usually takes 1-3 business days. You can proceed with test setup while waiting.

---

## 3. Create a Meta App

1. Go to [developers.facebook.com/apps](https://developers.facebook.com/apps)
2. Click **Create App**
3. Select app type: **Business**
4. Fill in:
   - **App Name**: `Kova WhatsApp` (or your preferred name)
   - **App Contact Email**: your email
   - **Business Account**: select your verified business account
5. Click **Create App**

### 3.1 Add WhatsApp Product

1. In your new app's dashboard, find **Add Products to Your App**
2. Find **WhatsApp** and click **Set Up**
3. Select your Meta Business Account when prompted
4. You'll land on the **WhatsApp > Getting Started** page

### 3.2 Note Your App Secret

1. Go to **App Settings** → **Basic**
2. Copy the **App Secret** — you'll need this for webhook signature validation
3. Store it securely. **Never expose it in client-side code or git repos**

---

## 4. WhatsApp Business Platform Access

### 4.1 Register a Phone Number

On the **WhatsApp > Getting Started** page:

1. Under **Send and receive messages**, click **Add phone number**
2. Enter your business phone number (must not be on regular WhatsApp)
3. Choose verification method: **SMS** or **Voice call**
4. Enter the verification code
5. Once verified, your number appears with a **Phone Number ID** — copy this

### 4.2 Note Your WABA ID

1. Go to **WhatsApp > Getting Started**
2. Your **WhatsApp Business Account ID (WABA ID)** is shown at the top or under **Account** settings
3. Copy this value

> At this point you should have 3 values:
> - **Phone Number ID** (e.g., `123456789012345`)
> - **WABA ID** (e.g., `987654321098765`)
> - **App Secret** (e.g., `abc123def456...`)

---

## 5. Generate a Permanent System User Token

The WhatsApp Cloud API uses **permanent tokens** (not short-lived OAuth tokens). These are generated via System Users.

### 5.1 Create a System User

1. Go to [business.facebook.com/settings](https://business.facebook.com/settings)
2. Navigate to **Users** → **System Users**
3. Click **Add** → **Create System User**
4. Enter a name: `Kova WhatsApp Bot`
5. Set role: **Admin**
6. Click **Create System User**

### 5.2 Assign Assets

1. Select your new System User
2. Click **Add Assets**
3. Under **Apps**, find your `Kova WhatsApp` app
4. Toggle **Full Control** → **On**
5. Click **Save Changes**

### 5.3 Generate the Token

1. Click **Generate New Token**
2. Select your `Kova WhatsApp` app
3. **Token Expiration**: Select **Never** (permanent token)
4. Select these permissions:
   - ✅ `whatsapp_business_messaging` — Send/receive messages
   - ✅ `whatsapp_business_management` — Manage templates, phone numbers, settings
5. Click **Generate Token**
6. **COPY THE TOKEN IMMEDIATELY** — it's only shown once
7. Store it securely (password manager, encrypted secrets, etc.)

> ⚠️ **CRITICAL**: If you lose this token, you must generate a new one. The old one cannot be recovered.

---

## 6. Configure Environment Variables

Add these to your deployment environment (Railway dashboard, `.env` file, etc.):

```bash
# ── WhatsApp Business Configuration ─────────────────────────────────

# Your phone number ID from Meta (Step 4.1)
WHATSAPP_PHONE_NUMBER_ID=123456789012345

# The permanent System User token (Step 5.3)
WHATSAPP_ACCESS_TOKEN=EAAxxxxxxxxxxxxxxxxxxxxxxxx

# Your WhatsApp Business Account ID (Step 4.2)
WHATSAPP_WABA_ID=987654321098765

# Webhook verification token — set this to any random secure string
# You'll use the SAME value when configuring the webhook in Meta's dashboard
WHATSAPP_VERIFY_TOKEN=your-random-secret-string-here

# Your Meta App Secret (Step 3.2) — used to verify webhook signatures
WHATSAPP_APP_SECRET=abc123def456ghi789
```

### What Each Variable Does

| Variable | Required | Purpose |
|---|---|---|
| `WHATSAPP_PHONE_NUMBER_ID` | ✅ Yes | Identifies which phone number to use for the Cloud API |
| `WHATSAPP_ACCESS_TOKEN` | ✅ Yes | Global fallback token. Per-user tokens override this when connected |
| `WHATSAPP_WABA_ID` | ✅ Yes | Links to your WhatsApp Business Account for template management |
| `WHATSAPP_VERIFY_TOKEN` | ✅ Yes | Shared secret between Kova and Meta for webhook setup |
| `WHATSAPP_APP_SECRET` | ✅ Yes (prod) | HMAC-SHA256 signature verification for incoming webhooks. **Without this, anyone could fake webhook events** |

> ⚠️ **Security Note**: In development, if `WHATSAPP_APP_SECRET` is not set, Kova will skip signature verification and log a warning. **Never skip this in production** — it's your protection against spoofed webhooks.

### Generate a Secure Verify Token

```bash
# Linux/Mac
python -c "import secrets; print(secrets.token_urlsafe(32))"

# Or use any password generator — must be at least 16 characters
```

---

## 7. Set Up the Webhook

The webhook is how Meta delivers incoming messages and status updates to Kova in real-time.

### 7.1 Your Webhook URL

Your webhook URL is:

```
https://your-kova-domain.com/whatsapp/webhook/
```

For example:
- Railway: `https://kova-agent-production.up.railway.app/whatsapp/webhook/`
- Custom domain: `https://app.kova.ai/whatsapp/webhook/`

### 7.2 Configure in Meta Dashboard

1. Go to [developers.facebook.com/apps](https://developers.facebook.com/apps) → your app
2. Navigate to **WhatsApp** → **Configuration**
3. Under **Webhook**, click **Edit**
4. Enter:
   - **Callback URL**: `https://your-kova-domain.com/whatsapp/webhook/`
   - **Verify Token**: the exact value you set for `WHATSAPP_VERIFY_TOKEN`
5. Click **Verify and Save**

> If verification fails, check:
> - Is Kova running and accessible via HTTPS?
> - Is the verify token exactly the same in both places?
> - Is there a trailing slash? Kova expects `/whatsapp/webhook/` (with slash)

### 7.3 Subscribe to Webhook Fields

After verification succeeds, you need to subscribe to event types:

1. On the same **Configuration** page, find **Webhook fields**
2. Subscribe to (click **Subscribe** for each):
   - ✅ `messages` — Incoming messages, message status updates, errors
3. That's it — `messages` covers everything Kova needs

### 7.4 How the Webhook Works

```
Customer sends WhatsApp message
        ↓
Meta Cloud API receives it
        ↓
Meta POSTs to your webhook URL with:
  - Message content (text, image, etc.)
  - Sender's phone number (wa_id)
  - X-Hub-Signature-256 header (HMAC signature)
        ↓
Kova webhook handler:
  1. Verifies HMAC signature using APP_SECRET
  2. Finds the matching SocialAccount by phone_number_id
  3. Creates/updates conversation thread
  4. Saves message to database
  5. Marks message as read (blue checkmarks)
  6. If AI handling is ON → fires Celery task for auto-reply
        ↓
AI auto-reply task:
  1. Loads brand context + conversation history
  2. Detects language (English/Swahili/Sheng)
  3. Generates reply with confidence score
  4. High confidence (≥80%) → sends immediately
  5. Medium confidence (50-80%) → saves as draft for review
  6. Low confidence (<50%) → escalates to human
```

---

## 8. Verify the Setup

### 8.1 Django System Check

```bash
python manage.py check
# Should show: System check identified no issues
```

### 8.2 Test with Meta's Test Number

1. In Meta's **WhatsApp > Getting Started** page, there's a **Test** section
2. Add your personal phone number as a test recipient
3. Click **Send Message** — you should receive a test message on WhatsApp
4. Reply to that message — it should hit your webhook and appear in Kova's inbox

### 8.3 Check the Webhook is Receiving Events

```bash
# In your Kova logs, look for:
[WhatsApp Webhook] Processed inbound text from 254XXXXXXXXX

# If Celery is running, you should also see:
[whatsapp.handle_incoming_message] Processing message <uuid> for conversation <uuid>
```

### 8.4 Verify in Kova Admin Dashboard

1. Go to `/dashboard/whatsapp/`
2. You should see:
   - Active Conversations count increasing
   - Messages appearing in the 7-day chart
   - Recent conversations showing your test contact

---

## 9. Production Checklist

Before going live, verify every item:

- [ ] **Meta Business verified** — without this, you're limited to 250 conversations/day
- [ ] **`WHATSAPP_APP_SECRET` is set** — webhook signature verification is active
- [ ] **HTTPS only** — webhook URL uses TLS (Meta rejects HTTP)
- [ ] **Celery worker running** — `celery -A config worker -l info -Q default,whatsapp`
- [ ] **Redis running** — Celery broker is connected
- [ ] **Webhook subscribed to `messages`** — in Meta dashboard
- [ ] **Test message received** — send from a real phone, verify it appears in Kova
- [ ] **AI reply works** — verify auto-reply comes back within a few seconds
- [ ] **Error monitoring** — check Django logs for webhook errors
- [ ] **Phone number display name approved** — in Meta dashboard, set your business display name (shown to customers)
- [ ] **Privacy policy URL set** — required by Meta for business messaging
- [ ] **Message templates created** — needed for re-engaging customers after 24-hour window

---

# PART 2 — User Guide

This section is for **Kova users** (your clients/team members) who connect their WhatsApp Business account and use the messaging features.

---

## 10. Connecting WhatsApp to Your Account

### Step 1: Navigate to Platforms

1. Log into Kova
2. Go to **Platforms** in the sidebar (or visit `/platforms/`)
3. You'll see the platform grid — find the **WhatsApp** card (green icon)
4. Click **Connect**

### Step 2: Enter Your Access Token

You'll see a form with instructions. You need a **permanent System User token** from Meta Business Suite.

**How to get your token:**

1. Go to [Meta Business Suite](https://business.facebook.com/settings) → **Settings**
2. Navigate to **Users** → **System Users**
3. Create or select a System User with **Admin** role
4. Click **Generate New Token** for your WhatsApp app
5. Select permissions:
   - ✅ `whatsapp_business_messaging`
   - ✅ `whatsapp_business_management`
6. Set expiration to **Never**
7. Click **Generate Token** and copy it

### Step 3: Paste and Connect

1. Paste your token into the **Access Token** field
2. Click **Connect WhatsApp**
3. Kova will verify your token against Meta's API
4. If successful, you'll see a success message and your WhatsApp account on the Platforms page

### What Gets Connected

Once connected, your Platforms page shows your WhatsApp account with:
- ✅ Your business phone number
- ✅ Quality rating (from Meta)
- ✅ Capabilities: AI Auto-Reply, Templates, Broadcasts, Images, Interactive, Read Receipts

> **Note**: WhatsApp tokens don't expire. You can revoke access anytime from Meta Business Suite → System Users → your token → Revoke.

---

## 11. The WhatsApp Inbox

Navigate to **WhatsApp** in the sidebar (or visit `/whatsapp/`).

### Inbox Overview

Your inbox shows:

| Section | What It Shows |
|---|---|
| **Stats Bar** | Total conversations, active, escalated, AI handling, messages today, AI replies today |
| **Conversation List** | All conversations sorted by most recent message |

### Conversation Filters

Use the filter buttons at the top:

| Filter | Shows |
|---|---|
| **All** | Every conversation |
| **Active** | Conversations with ongoing messaging |
| **Escalated** | Conversations flagged for human attention (AI couldn't handle confidently) |
| **Closed** | Completed conversations |

### Language Filters

| Filter | Shows |
|---|---|
| **English** | Conversations detected as English |
| **Swahili** | Conversations in Swahili |
| **Sheng** | Conversations in Sheng (Nairobi urban slang) |

### What Each Conversation Row Shows

- **Avatar + Contact Name** — from WhatsApp profile (or phone number if no name)
- **Last Message Preview** — first 80 characters of the most recent message
- **Status Badges**:
  - 🟢 **Active** — conversation is live
  - 🟡 **Escalated** — needs your attention
  - 🟣 **AI** — AI is handling this conversation
  - 🔵 **Needs Human** — AI has escalated this to you
- **Language** — detected language tag
- **Window Status**:
  - ✅ **Window Open** — you can send free-form messages
  - ⏰ **Template Only** — 24-hour window expired, must use a template
- **Time** — how long since the last message

---

## 12. Conversations & Messaging

Click any conversation to open it.

### Conversation Header

At the top of each conversation:

| Element | Meaning |
|---|---|
| **Contact Name + Phone** | Who you're talking to |
| **AI Status Toggle** | Green = AI handling ON, Gray = OFF. Click to toggle |
| **Language Tag** | Detected conversation language |
| **Window Status** | Shows if 24-hour window is open or expired |

### Message Thread

Messages appear in a chat-style thread:

- **Left side (gray)** — Inbound messages from the customer
- **Right side (green)** — Your outbound messages
- **🤖 AI tag** — Messages generated by AI auto-reply
- **Delivery Status Icons**:
  - ✓ Sent
  - ✓✓ Delivered
  - ✓✓ (blue) Read
  - ⚠️ Failed

### Sending Messages

**When the 24-hour window is open:**
1. Type your message in the text box at the bottom
2. Press **Enter** to send (Shift+Enter for new line)
3. The message sends instantly via WhatsApp Cloud API

**When the window is expired:**
- The text input is replaced with a **"Send Template"** prompt
- You must use an approved template to re-open the conversation
- See [Message Templates](#15-message-templates) below

### Escalation Banner

If a conversation has been escalated by the AI, you'll see a yellow banner at the top explaining:
- **Why** the AI escalated (low confidence, complex query, etc.)
- **The draft reply** the AI would have sent (if any)
- You can review the draft, edit it, and send manually

### Pending AI Drafts

When the AI generates a reply with **medium confidence** (50-80%), it doesn't send automatically. Instead:
1. You'll see a "Pending AI Drafts" section
2. Each draft shows the AI-generated reply text
3. Click **Approve & Send** to send it as-is
4. Or type your own message and send that instead

---

## 13. AI Auto-Reply System

When AI handling is enabled (default for new conversations), here's how it works:

### The AI Reply Pipeline

```
Customer sends message
        ↓
Language detected (English / Swahili / Sheng)
        ↓
AI loads your brand context:
  - Business name, industry, voice & tone
  - Target audience, key offerings
  - Restrictions (what not to say/promise)
        ↓
AI reads last 20 messages for conversation context
        ↓
AI generates reply with confidence score (0-100%)
        ↓
Routing based on confidence:
```

| Confidence | What Happens | Your Action Needed? |
|---|---|---|
| **≥ 80%** (High) | Auto-sends immediately | No — fully automated |
| **50-80%** (Medium) | Saved as draft for your review | Yes — review and approve/edit |
| **< 50%** (Low) | Escalated to you, AI disabled for this conversation | Yes — take over manually |

### Controlling AI per Conversation

- **Toggle AI ON/OFF**: Click the AI status toggle in the conversation header
- When you turn AI **OFF**: You handle all messages manually
- When you turn AI **ON** for an escalated conversation: It resets to "Active" and AI resumes handling

### What the AI Knows About Your Brand

The AI uses your **Brand Profile** (set up in your account settings) to craft replies that match your voice:

- **Business Name** — used in greetings and sign-offs
- **Industry** — affects tone and terminology
- **Brand Voice** — e.g., "friendly and professional", "casual and witty"
- **Target Audience** — adjusts language complexity and references
- **Key Offerings** — products/services the AI can reference
- **Restrictions** — things the AI should never say or promise

> **Tip**: The better your brand profile, the better the AI replies. Take time to fill in detailed descriptions of your voice, offerings, and restrictions.

### Language Support

The AI detects and responds in three languages:

| Language | Detection | Example |
|---|---|---|
| **English** | Default | "Hello, I'd like to know about your products" |
| **Swahili** | Keywords: habari, karibu, asante, nataka, etc. | "Habari, nataka kujua bei ya bidhaa" |
| **Sheng** | Keywords: niaje, sema, mambo, poa, fiti, etc. | "Niaje, nashinda huku tu" |

The AI replies in the same language the customer uses.

---

## 14. Understanding the 24-Hour Window

WhatsApp enforces a **24-hour customer service window**. This is a Meta policy that applies to ALL businesses on the platform (not just Kova).

### How It Works

```
Customer messages you
        ↓
24-hour window OPENS ──────────────────────────┐
                                                │
  You can send ANY message:                     │
  - Free-form text                              │
  - Images, videos, documents                   │ 24 hours
  - Interactive buttons & lists                 │
  - AI auto-replies                             │
                                                │
24-hour window CLOSES ─────────────────────────┘
        ↓
After the window closes:
  - You can ONLY send approved templates
  - Templates re-open the window when the customer replies
```

### Key Rules

| Rule | Details |
|---|---|
| **Window opens** | When the customer sends you a message |
| **Window duration** | 24 hours from their last message |
| **Window extends** | Each new customer message resets the 24-hour timer |
| **After window closes** | Only approved templates can be sent |
| **Templates** | Pre-approved by Meta. Must follow their content policy |
| **Cost** | Messages within the window: cheaper. Template-initiated: slightly more expensive |

### What You See in Kova

- **"Window Open"** (green) — you can message freely
- **"Template Only"** (amber) — window expired, use a template
- Kova tracks window expiry automatically — you don't need to calculate anything

---

## 15. Message Templates

Templates are **pre-written message formats** that must be **approved by Meta** before you can use them. They're required for messaging customers outside the 24-hour window.

### Navigate to Templates

Go to **WhatsApp** → **Templates** (or visit `/whatsapp/templates/`)

### Creating a Template

You have two options:

#### Option A: AI-Generated Template (Recommended)

1. Click **Create Template**
2. Select **AI Generate** tab
3. Describe what you want in natural language:
   - Example: *"A friendly order confirmation that includes the order number and estimated delivery date"*
   - Example: *"A re-engagement message for customers who haven't ordered in 30 days, with a discount offer"*
4. Click **Generate**
5. The AI creates a Meta-compliant template with:
   - Proper name format (lowercase_underscores)
   - Category (marketing/utility)
   - Body with variable placeholders (`{{1}}`, `{{2}}`)
   - Footer
6. Review and save

#### Option B: Manual Template

1. Click **Create Template**
2. Select **Manual** tab
3. Fill in:
   - **Name**: lowercase letters and underscores only (e.g., `order_confirmation`)
   - **Category**: Marketing, Utility, or Authentication
   - **Body**: Your template text with variables like `{{1}}`, `{{2}}`
   - **Footer** (optional): Short text below the body
   - **Language**: en (English) by default
4. Click **Save**

### Template Variables

Use `{{1}}`, `{{2}}`, etc. for dynamic content:

```
Hi {{1}}, your order #{{2}} has been confirmed!
Expected delivery: {{3}}.

Thank you for shopping with us! 🛍️
```

When sending, you provide the actual values:
- `{{1}}` → "James"
- `{{2}}` → "KV-2026-0042"
- `{{3}}` → "April 18, 2026"

### Template Status Lifecycle

```
Draft → Submitted → Approved ✅
                  → Rejected ❌ (with reason)
                  → Paused ⏸️ (quality issues)
```

| Status | Meaning |
|---|---|
| **Draft** | Created in Kova, not yet sent to Meta |
| **Submitted** | Sent to Meta for review |
| **Approved** | Ready to use! Can be sent to customers |
| **Rejected** | Meta rejected it. Check the rejection reason and create a new one |
| **Paused** | Meta paused it due to quality issues (high block/report rate) |

### Template Categories

| Category | Use For | Meta Review Speed |
|---|---|---|
| **Utility** | Order confirmations, shipping updates, appointment reminders | Usually approved within minutes |
| **Marketing** | Promotions, offers, re-engagement, newsletters | Reviewed more carefully, may take hours |
| **Authentication** | OTP codes, login verification | Fastest approval |

### Tips for Getting Templates Approved

1. **Be clear and specific** — vague templates get rejected
2. **Don't be misleading** — template must match how it'll actually be used
3. **Include opt-out language** for marketing — e.g., "Reply STOP to unsubscribe"
4. **Avoid prohibited content** — no threatening language, no illegal products
5. **Use variables for dynamic content** — don't hardcode customer-specific info
6. **Keep it professional** — Meta reviews every template manually

---

## 16. Broadcasts

Broadcasts let you send a template message to multiple contacts at once — perfect for announcements, promotions, and re-engagement campaigns.

### Navigate to Broadcasts

Broadcasts are managed through the WhatsApp admin dashboard at `/dashboard/whatsapp/broadcasts/`.

### How Broadcasts Work

```
Create Broadcast
        ↓
Select an approved template
        ↓
Define your audience:
  - By tags (e.g., "vip", "new_customer")
  - By language (en, sw, sheng)
  - By last active (e.g., within 30 days)
        ↓
Set template variables (dynamic per recipient)
        ↓
Schedule or send immediately
        ↓
Kova sends the template to each recipient
        ↓
Track: sent → delivered → read → replied
```

### Broadcast Metrics

After sending, track performance:

| Metric | What It Tells You |
|---|---|
| **Sent** | Successfully queued for delivery |
| **Delivered** | Reached the customer's phone |
| **Read** | Customer opened the message |
| **Replied** | Customer responded (re-opens 24h window!) |
| **Failed** | Delivery failed (blocked, invalid number, etc.) |

### Smart Timing

Enable **Per-Contact Timing** to let Kova's Adapt Agent optimize send times for each recipient based on when they're most likely to read and respond.

---

## 17. Admin Dashboard Controls

As a Kova admin, you have full visibility and control over WhatsApp operations.

### Access

Navigate to **Admin Dashboard** → **WhatsApp** (in the sidebar under Communications) or visit `/dashboard/whatsapp/`.

### Overview Dashboard

| Section | What You See |
|---|---|
| **Stat Cards** | Active conversations, messages (7d), AI auto-replies, escalated count |
| **Delivery Stats** | Delivery rate %, read rate %, open windows, failed messages |
| **Templates Summary** | Total/approved/pending/rejected counts |
| **Broadcast Performance** | Total sent, delivered, read, replied across all broadcasts |
| **Message Volume Chart** | 7-day bar chart (inbound vs outbound) |
| **Recent Conversations** | Last 5 conversations with status, AI handling, window status |

### Sub-Pages

| Page | URL | What It Does |
|---|---|---|
| **Conversations** | `/dashboard/whatsapp/conversations/` | All conversations across all users. Search by name/phone, filter by status (active/closed/escalated) and handling type (AI/human). Shows message counts, window status |
| **Templates** | `/dashboard/whatsapp/templates/` | All templates across all users. Filter by approval status and category. Shows AI-created flag, owner, language |
| **Broadcasts** | `/dashboard/whatsapp/broadcasts/` | All broadcast campaigns. Shows template used, recipient count, delivery/read metrics, schedule date |

### Platform Management

The general **Platforms** page (`/dashboard/platforms/`) also shows WhatsApp accounts alongside other platforms — with active/inactive status, error count, and publishing stats.

---

## 18. Troubleshooting

### "Webhook verification failed"

| Cause | Fix |
|---|---|
| Wrong verify token | Ensure `WHATSAPP_VERIFY_TOKEN` in your env matches exactly what you entered in Meta's dashboard |
| No trailing slash | Your callback URL should end with `/whatsapp/webhook/` (with slash) |
| Kova not running | Make sure the Django server is up and accessible via HTTPS |
| SSL/TLS issue | Meta requires valid HTTPS. Self-signed certificates won't work |

### "Messages not arriving in Kova"

| Cause | Fix |
|---|---|
| Webhook not subscribed | In Meta dashboard → WhatsApp → Configuration → ensure `messages` field is subscribed |
| Wrong phone number | Check `WHATSAPP_PHONE_NUMBER_ID` matches the phone number receiving messages |
| App secret missing | If `WHATSAPP_APP_SECRET` is wrong (not missing), signatures will fail silently. Check Django logs for `Webhook signature mismatch` |
| No SocialAccount | The user must have connected WhatsApp in Kova (Step 10). The webhook matches by `phone_number_id` in account metadata |

### "AI not replying"

| Cause | Fix |
|---|---|
| Celery not running | Start it: `celery -A config worker -l info` |
| AI handling disabled | Check the conversation — is the AI toggle ON? |
| Reaction message | AI skips reaction messages (emoji reactions) by design |
| LLM error | Check Celery logs for errors from the AI generation. May be an API key or rate limit issue |
| Low confidence | If confidence is below 50%, AI escalates instead of replying. Check "Escalated" conversations |

### "Can't send messages — window expired"

This is normal WhatsApp behavior. After 24 hours since the customer's last message:
1. You must use an **approved template** to re-initiate
2. Go to Templates, select an approved one, and send it
3. When the customer replies, the window re-opens for 24 hours

### "Template rejected by Meta"

| Common Reason | Fix |
|---|---|
| "Scam or deceptive content" | Make the template more transparent about your business |
| "Missing variable" | Use `{{1}}` style variables for dynamic content |
| "Duplicate" | Template name must be unique per WABA. Change the name |
| "Incorrect category" | Marketing templates need opt-out. Utility templates must be transactional |
| "Sample content required" | Provide example values for each variable when submitting |

### "Connect WhatsApp failed"

| Cause | Fix |
|---|---|
| Invalid token | Regenerate the System User token in Meta Business Suite |
| Missing permissions | Token needs `whatsapp_business_messaging` AND `whatsapp_business_management` |
| Wrong phone number ID | Check `WHATSAPP_PHONE_NUMBER_ID` in your environment variables |
| Network error | Check if Meta's Graph API is reachable from your server |

### Checking Logs

```bash
# Django logs (webhook events)
grep "WhatsApp" your-django.log

# Celery logs (AI auto-reply)
grep "whatsapp" your-celery.log

# Look for specific errors
grep -i "error\|failed\|exception" your-celery.log | grep -i whatsapp
```

---

## Quick Reference Card

| What | Where |
|---|---|
| **Connect WhatsApp** | Platforms → WhatsApp → Connect |
| **View Inbox** | Sidebar → WhatsApp |
| **Open a Conversation** | WhatsApp Inbox → click any conversation |
| **Toggle AI** | Inside conversation → AI toggle in header |
| **Create Template** | WhatsApp → Templates → Create |
| **View Broadcasts** | Admin Dashboard → WhatsApp → Broadcasts |
| **Admin Overview** | Admin Dashboard → WhatsApp |
| **Webhook URL** | `https://your-domain.com/whatsapp/webhook/` |
| **Meta Dashboard** | [developers.facebook.com/apps](https://developers.facebook.com/apps) |
| **Meta Business Suite** | [business.facebook.com](https://business.facebook.com) |

---

## Environment Variables Summary

```bash
WHATSAPP_PHONE_NUMBER_ID=     # From Meta → WhatsApp → Getting Started
WHATSAPP_ACCESS_TOKEN=        # System User permanent token
WHATSAPP_WABA_ID=             # WhatsApp Business Account ID
WHATSAPP_VERIFY_TOKEN=        # Any secure random string (you create this)
WHATSAPP_APP_SECRET=          # From Meta → App Settings → Basic → App Secret
```

---

*Document generated for Kova Platform v1.0 · WhatsApp Business Cloud API v21.0*
