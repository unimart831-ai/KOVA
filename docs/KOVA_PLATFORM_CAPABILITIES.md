# Kova — Platform Capabilities Guide

> Everything Kova can do for your business across every social media platform.
> Last updated: April 14, 2026

---

## Platforms Supported

Kova connects to **9 social media platforms**:

| Platform | Account Type | Auth Method |
|----------|-------------|-------------|
| **Twitter (X)** | Personal / Business | OAuth 2.0 with PKCE |
| **LinkedIn** | Personal Profile + Company Pages | OAuth 2.0 |
| **Instagram** | Professional (Business/Creator) | Facebook Login |
| **Facebook** | Pages | Facebook Login |
| **TikTok** | Creator | OAuth 2.0 |
| **YouTube** | Channels | Google OAuth 2.0 |
| **Pinterest** | Business | OAuth 2.0 |
| **Bluesky** | Personal | App Password (AT Protocol) |
| **Threads** | Personal | Facebook Login |

You can connect **multiple accounts per platform** and manage them all from one dashboard.

---

## 1. Content Creation

### AI-Powered Writing

Kova's **Create Agent** writes platform-native content for every connected platform:

- **Platform-adapted copy** — The same idea becomes a punchy 280-char tweet, a storytelling LinkedIn post, a hook-first IG caption, and a trending TikTok description. Each version follows the rules of its platform.
- **Brand voice consistency** — Kova learns your tone (professional, witty, bold, educational, etc.) from your brand setup and from every edit you make. The more you use it, the more it sounds like you.
- **Hook-first structure** — Every post opens with a scroll-stopping hook. Kova uses proven frameworks (Problem → Agitate → Solve, Story → Lesson → CTA, Bold Claim → Evidence, etc.).
- **Hashtag strategy** — Platform-relevant hashtags are included automatically. Instagram gets 15-20. LinkedIn gets 3-5. Twitter gets 1-2. TikTok gets trending tags.
- **Call-to-action insertion** — Every post ends with a clear CTA tied to your business goals (drive traffic, generate leads, build authority, sell).

### Content Types Per Platform

| Content Type | Twitter | LinkedIn | Instagram | Facebook | TikTok | YouTube | Pinterest | Bluesky | Threads |
|-------------|---------|----------|-----------|----------|--------|---------|-----------|---------|---------|
| Text posts | ✅ | ✅ | ✅ | ✅ | ✅ | — | — | ✅ | ✅ |
| Single image | ✅ | ✅ | ✅ | ✅ | — | — | ✅ | ✅ | ✅ |
| Multi-image / Carousel | ✅ (4 max) | ✅ (9 max) | ✅ | ✅ | ✅ (35 max) | — | — | — | ✅ |
| Video | ✅ | ✅ | ✅ (Reels) | ✅ | ✅ | ✅ | — | — | — |
| Stories | — | — | ✅ | — | — | — | — | — | — |
| Threads / Thread chains | ✅ | — | — | — | — | — | — | — | ✅ |
| Articles with link preview | — | ✅ | — | — | — | — | — | — | — |
| Pins with destination link | — | — | — | — | — | — | ✅ | — | — |

### AI Image Generation

Kova generates custom images for your posts using AI:

- **Brand-aligned visuals** — Generated images match your brand colors, style, and industry.
- **Multiple styles** — Photography-style, illustration, infographic, quote cards, product shots.
- **Auto-attached** — Generated images are automatically attached to the right post before publishing.
- **Storage** — All generated media is stored in your media library for reuse.

### Content Repurposing

One idea becomes content for every platform:

1. You provide a topic, product, or content pillar.
2. Kova's **Strategist Agent** creates a seed idea.
3. The **Create Agent** generates platform-native versions for every connected account.
4. You review, edit, and approve — or batch-approve everything at once.

**Example:** You say "Launch our new product." Kova creates:
- A Twitter thread with a hook, features, and CTA
- A LinkedIn storytelling post with authority framing
- An Instagram carousel with key selling points
- A Facebook post with social proof angle
- A TikTok description optimized for discovery

### A/B Testing

Kova can create **content variants** to test what works:

- Generate 2-3 versions of the same post with different hooks, angles, or CTAs.
- Publish variants and let Kova auto-evaluate which performed better.
- Winning patterns feed back into future content generation.

---

## 2. Scheduling & Publishing

### Five Scheduling Modes

| Mode | What It Does |
|------|-------------|
| **Post Now** | Publishes immediately to the selected platform(s) |
| **Next Best Time** | Kova picks the optimal time based on your platform's peak engagement hours |
| **Smart Queue** | Auto-spaces posts based on your posting frequency — no overlaps, no flooding |
| **Quick Schedule** | Predefined options: 30 minutes, 1 hour, 3 hours, tomorrow morning, tomorrow evening |
| **Exact Time** | You pick the exact date and time |

### Platform Peak Hours (Kova's Smart Timing)

Kova knows when your audience is most active:

| Platform | Peak Windows (UTC) |
|----------|-------------------|
| Twitter | 8-10am, 12-2pm, 5-7pm |
| LinkedIn | 7-9am, 11am-1pm, 5-6pm |
| Instagram | 7-9am, 12-2pm, 7-9pm |
| TikTok | 12-3pm, 7-11pm |
| Facebook | 9-11am, 1-3pm, 6-8pm |

### Conflict Prevention

- **4-hour minimum gap** between posts on the same platform (prevents audience fatigue).
- **1-hour global gap** between any two posts (prevents notification flooding).
- If today's slots are full, Kova looks at the next 3-4 days automatically.

### Batch Operations

- **Batch approve** — Review all AI-generated posts and approve them in one click with a single scheduling intent.
- **Content calendar** — Visual calendar view of all scheduled, published, and draft posts across platforms.
- **Queue management** — Drag, reorder, reschedule, or cancel queued posts.

### Facebook Native Scheduling

For Facebook Pages, Kova uses Facebook's native `scheduled_publish_time` parameter, ensuring posts appear exactly as if scheduled from Facebook's own tools.

---

## 3. Engagement & Community Management

### Comment Monitoring

Kova automatically fetches comments on your published posts:

| Platform | Comment Fetching | Reply Capability |
|----------|-----------------|-----------------|
| Twitter | ✅ Mentions + replies | ✅ AI-suggested replies |
| LinkedIn | ✅ Post comments | ✅ AI-suggested replies |
| Instagram | ✅ Post comments | ✅ AI-suggested replies |
| Facebook | ✅ Post comments | ✅ AI-suggested replies |
| TikTok | ❌ (API restriction) | ❌ |
| YouTube | ✅ Basic comment threads | ✅ Basic replies |

### AI Reply Suggestions

When someone comments on your post, Kova:

1. **Analyzes sentiment** — Positive, negative, neutral, question, complaint.
2. **Generates a reply** — Matching your brand voice and the context of the conversation.
3. **Queues for your approval** — You review, edit if needed, then approve or discard.
4. **Learns from your edits** — Every time you modify a suggested reply, Kova refines its style to match yours better over time.

### Direct Messages

| Platform | Read DMs | Send DMs |
|----------|----------|----------|
| Facebook Pages | ✅ | ✅ |
| Instagram | ✅ | ✅ |
| Twitter | ❌ | ❌ |
| LinkedIn | ❌ | ❌ |
| TikTok | ❌ | ❌ |

### Reactions & Engagement Actions

| Action | Twitter | LinkedIn |
|--------|---------|----------|
| Like / React | ✅ | ✅ |
| Retweet / Share | ✅ | — |
| Unlike / Undo | ✅ | — |

### Superfan Detection

Kova automatically identifies your most engaged followers:

| Tier | Interactions | What It Means |
|------|-------------|--------------|
| **Rising** | 3-5 | Someone starting to engage regularly |
| **Loyal** | 6-15 | A consistent supporter |
| **Superfan** | 16+ | Your brand champion — prioritize this person |

Tracked across all platforms. Kova logs which platforms they engage on, their sentiment patterns, and generates engagement notes so you know who your VIPs are.

### Engagement Inbox

Unified inbox that shows all interactions (comments, mentions, DMs) across every platform in one place. Filter by:
- Platform
- Sentiment
- Status (new, replied, ignored, flagged)
- Superfan tier

---

## 4. Analytics & Reporting

### Post-Level Metrics

Kova auto-fetches metrics **1 hour after publishing** and continues tracking:

| Metric | Twitter | LinkedIn | Instagram | Facebook | TikTok | YouTube | Pinterest |
|--------|---------|----------|-----------|----------|--------|---------|-----------|
| Likes | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | — |
| Comments | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | — |
| Shares / Retweets | ✅ | ✅ | ✅ | ✅ | ✅ | — | — |
| Impressions | ✅ | — | ✅ | ✅ | ✅ | ✅ | ✅ |
| Reach | — | — | ✅ | ✅ | — | — | — |
| Saves | — | — | ✅ | — | — | — | ✅ |
| Clicks | — | — | ✅ | ✅ | — | — | ✅ |
| Views (video) | — | — | — | — | ✅ | ✅ | — |
| Engagement Rate | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |

### Account-Level Insights

| Insight | Facebook | Instagram | TikTok | YouTube |
|---------|----------|-----------|--------|---------|
| Follower count | ✅ | ✅ | ✅ | ✅ (subscribers) |
| Page impressions | ✅ | — | — | — |
| Page/account reach | ✅ | ✅ | — | — |
| Total video views | — | — | ✅ | ✅ |
| Audience growth tracking | ✅ | ✅ | ✅ | ✅ |

### Content DNA Analysis

This is unique to Kova. After every post, Kova extracts the **DNA** — the combination of factors that made it perform well or poorly:

- **Format** — Was it a carousel, text-only, video, thread?
- **Tone** — Professional, casual, bold, educational, humorous?
- **Topic** — Which content pillar did it hit?
- **Length** — Short-form vs. long-form?
- **Hook type** — Question, bold claim, story, statistic?
- **CTA type** — Link click, comment, share, save?

Over time, Kova builds a **performance DNA profile** for your brand — it knows which combinations work and skews future content toward your winning formula.

### Engagement Prediction

Before publishing, Kova predicts how a post will perform based on:
- Your historical DNA data
- Platform trends
- Content characteristics

After publishing, Kova compares predicted vs. actual engagement — and uses the gap to improve future predictions.

### Competitor Intelligence

Track up to N competitors across all platforms:

- **Handles tracked:** Twitter, Instagram, Facebook, LinkedIn, TikTok, YouTube, Threads
- **AI analysis** includes:
  - Content strategy (what they post, how often, what format)
  - Content patterns (themes, tone, frequency)
  - Strengths and weaknesses
  - Threat level rating (low / medium / high)
- **Weekly competitor reports** — Automated re-analysis to track changes over time.

### Weekly Performance Reports

Auto-generated and delivered via email every week:

- Top performing posts
- Engagement trends
- Audience growth
- Platform comparison
- Recommendations for next week

---

## 5. Strategy & Intelligence

### Daily Brief

Every morning, Kova delivers a **strategic briefing** that includes:

- **What happened** — Performance summary of recent posts across all platforms.
- **What's trending** — Relevant trends in your industry discovered via real-time web search.
- **What to do today** — Decisions that need your attention (approve posts, respond to comments, review flagged content).
- **Agent plan** — What Kova's AI agents are working on today.
- **Content opportunities** — Timely topics you should post about.

### Research Agent (Trend Discovery)

Kova's Research Agent runs every 12 hours:

1. **Real-time web search** (via Tavily) — Searches for trends in your industry, content pillars, and competitor activity.
2. **Trend analysis** — 5-8 trending topics with relevance scores and urgency ratings.
3. **Content opportunities** — 3-4 ready-to-use content angles with suggested platforms.
4. **Industry signals** — News, shifts, and conversations your audience cares about.

For new users (first 7 days), research runs at **priority speed** so your first brief is rich with insights.

### Strategist Agent (Content Planning)

The Strategist creates **seed content ideas** based on:

- Your research brief (trending topics, opportunities)
- Your content pillars and goals
- Your posting schedule and gaps
- Past performance data (what worked, what didn't)
- Competitor blind spots (topics they're missing)

Seeds are then expanded into full posts by the Create Agent.

### Brand Voice Learning

Kova's brand voice engine adapts from three sources:

1. **Initial setup** — Your tone attributes, industry, target audience, brand personality.
2. **Edit history** — Every time you edit an AI-generated post, Kova learns what you changed and why.
3. **Performance feedback** — Posts you rate highly (🔥) influence future content direction.

---

## 6. Safety & Control

### Content Safety Gate

Every post passes through a safety check before publishing:

- **Hard block** — Dangerous, hateful, or harmful content is blocked and sent back for editing. Never published.
- **Soft flag** — Risky content (potentially controversial, off-brand) is paused for your review with a risk score.

### Emergency Pause

One-click button to **halt all autonomous publishing** across every platform instantly. Use this if:

- Something goes wrong with your brand
- You need to pivot messaging immediately
- You want to review everything before it goes out

All scheduled posts hold in queue until you unpause.

### Post Deletion

| Platform | Delete Post |
|----------|------------|
| Twitter | ✅ |
| LinkedIn | ✅ |
| Instagram | ❌ (API limitation) |
| Facebook | ❌ (API limitation) |
| TikTok | ❌ (API limitation) |

### Token Security

- All social media tokens are **encrypted at rest** in the database.
- Automatic token refresh when they expire.
- **3-strike deactivation** — If a platform returns 3 permanent auth errors, Kova deactivates the connection and notifies you to reconnect.
- **Smart error classification** — Temporary errors (rate limits, server issues) don't count as strikes. Only real auth failures do.

---

## 7. Link Management

### Kova Links (Link-in-Bio)

Built-in link page tool — no need for Linktree or similar:

- Custom branded link page
- Add unlimited links with titles and icons
- Track clicks per link
- Use your Kova Links URL in your Instagram/TikTok bio

### UTM Tracking

Every URL in every post is automatically tagged with UTM parameters:

- `utm_source` = platform name (twitter, linkedin, instagram, etc.)
- `utm_medium` = social
- `utm_campaign` = campaign name (if assigned)

This means your Google Analytics automatically shows which platform and post drove traffic.

---

## 8. Team Collaboration

### Multi-User Access

- Invite team members to your brand workspace.
- Role-based permissions (admin, editor, viewer).
- Activity feed showing who did what.

### Multi-Brand Management

- Manage multiple brands from one account.
- Each brand has its own connected platforms, content, analytics, and settings.
- Switch between brands instantly.

---

## 9. Leads & CRM

### Lead Capture

Kova tracks leads generated from your social media activity:

- UTM-tagged link clicks
- Form submissions from Kova Links pages
- DM inquiries flagged as leads

### Lead Management

- View all leads in one dashboard
- Track source platform and post
- Status tracking (new, contacted, converted)

---

## 10. Email Notifications

### Automated Emails

| Email | When It's Sent |
|-------|---------------|
| Welcome email | On signup |
| Trial ending reminders | Day 7, 3, 1, and 0 before trial expires |
| Payment confirmation | After successful payment |
| Payment failed | After failed payment attempt |
| Weekly performance report | Every Monday |

All critical emails have **automatic retry** — if delivery fails, Kova retries up to 3 times with increasing delays.

---

## 11. Billing & Payments

### Payment Methods

| Method | Availability |
|--------|-------------|
| **Stripe** (Cards) | Global |
| **M-Pesa** (Mobile Money) | Kenya, Tanzania, and other supported markets |

### M-Pesa Features

- **STK Push** — Payment prompt sent directly to your phone.
- **Idempotency guard** — Double-taps within 2 minutes are blocked (no duplicate charges).
- **Status recovery** — If a payment succeeds but the callback fails, Kova polls M-Pesa to recover the payment automatically.

### Plan Enforcement

Kova enforces plan limits automatically:

- Post limits per month
- Platform connection limits
- API access (Pro and Enterprise only)
- Feature gating based on subscription tier

---

## 12. API Access

### REST API (Pro & Enterprise Plans)

Programmatic access to Kova's capabilities:

- Create and schedule posts
- Fetch analytics data
- Manage platforms
- Trigger agent actions

**Rate limiting** scales with your plan tier. All endpoints require authentication.

---

## Platform Capability Matrix — Quick Reference

| Capability | Twitter | LinkedIn | Instagram | Facebook | TikTok | YouTube | Pinterest | Bluesky | Threads |
|-----------|---------|----------|-----------|----------|--------|---------|-----------|---------|---------|
| Publish text | ✅ | ✅ | ✅ | ✅ | ✅ | — | — | ✅ | ✅ |
| Publish images | ✅ | ✅ | ✅ | ✅ | ✅ | — | ✅ | ✅ | ✅ |
| Publish video | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | — | — | — |
| Publish carousels | ✅ | ✅ | ✅ | ✅ | ✅ | — | — | — | ✅ |
| Stories / Reels | — | — | ✅ | — | — | — | — | — | — |
| Threads / chains | ✅ | — | — | — | — | — | — | — | ✅ |
| Smart scheduling | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Fetch comments | ✅ | ✅ | ✅ | ✅ | — | ✅ | — | — | — |
| AI reply to comments | ✅ | ✅ | ✅ | ✅ | — | ✅ | — | — | — |
| Read DMs | — | — | ✅ | ✅ | — | — | — | — | — |
| Send DMs | — | — | ✅ | ✅ | — | — | — | — | — |
| Like / React | ✅ | ✅ | — | — | — | — | — | — | — |
| Delete posts | ✅ | ✅ | — | — | — | — | — | — | — |
| Post metrics | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | — | ✅ |
| Account insights | — | — | ✅ | ✅ | ✅ | ✅ | — | — | — |
| Audience tracking | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | — | — | — |
| Superfan detection | ✅ | ✅ | ✅ | ✅ | — | — | — | — | — |
| Competitor tracking | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | — | — | ✅ |

---

## What Makes Kova Different

These capabilities don't exist in traditional social media management tools:

1. **Content DNA Analysis** — Kova doesn't just track likes. It correlates format + tone + topic + hook + CTA to find your winning formula.

2. **Reply Style Learning** — Every time you edit an AI-suggested reply, Kova learns. After 20-30 edits, it writes replies that sound like you.

3. **1 Idea → 9 Platforms** — One content seed becomes platform-native posts for every connected account. Not copy-paste — genuinely adapted.

4. **Daily Strategic Brief** — No other tool gives you a morning briefing with agent plans, performance insights, trending topics, and action items.

5. **Superfan Tiering** — Automatic identification of your most engaged followers across all platforms, so you know who to nurture.

6. **Engagement Prediction** — Kova predicts how a post will perform before you publish it, then learns from the gap between prediction and reality.

7. **Smart Error Handling** — Temporary platform outages don't break your workflow. Kova retries with exponential backoff and distinguishes real auth failures from temporary glitches.

8. **Emergency Pause** — One button stops everything. No other tool gives you this level of control over autonomous AI actions.

---

*This document reflects Kova's capabilities as of April 2026. Features are continuously being added and improved.*
