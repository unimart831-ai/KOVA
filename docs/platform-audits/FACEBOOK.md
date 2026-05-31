# Facebook Platform Audit — How SMBs Use It vs What Kova Delivers

> **Purpose:** Role-by-role audit of Facebook Page management for startups and small businesses, mapped to Kova capabilities, gaps, and build priorities.  
> **Last updated:** May 2026  
> **Code reference:** `apps/platforms/providers/instagram_facebook.py` (`FacebookProvider`)  
> **Related:** `docs/KOVA_PLATFORM_CAPABILITY_CHECKLIST.md` (capability matrix — some rows outdated; this doc is the SMB lens)

---

## Executive summary

**What a Facebook Page is for an SMB:** A free storefront + community hub — posts for reach, visuals for trust, Reels for discovery, Messenger for sales questions, reviews for credibility, and insights for “is this working?”

**Kova’s Facebook story today:** Strong on **feed posts** (text, photo, carousel), **Facebook-native copy strategy** (no links in body → first comment), **comment engagement**, and **post-level analytics**. Weaker on **Reels/Stories/video**, **Messenger inbox**, **Page setup UX** (Page picker, profile photo/cover), and **several production bugs** that undermine trust if not fixed.

**Honest value-for-money score (Facebook-only):** **6.5 / 10** for a typical Kenyan SMB doing 3–5 feed posts/week + replying to comments. **4 / 10** if they expect Reels-first or Messenger-as-CRM.

---

## How startups & small businesses actually use Facebook

Below is the **job-to-be-done** breakdown — not features, but roles a founder or one-person marketing hire performs on a Page.

### 1. Page foundation (setup & trust)

| Role / task | What the business does | Why it matters |
|-------------|------------------------|----------------|
| Create & verify Page | Business name, category, contact info | Discovery + legitimacy |
| Profile photo & cover | Logo, hero image, seasonal cover | First impression |
| About / description | What we do, hours, location, website | SEO + Messenger context |
| CTA button | “Shop now”, “Book now”, “Message us”, “WhatsApp” | Converts visitors |
| Page completeness | Phone, email, address, hours filled in | Meta ranks complete Pages higher |
| Reviews & recommendations | Respond to star ratings | Social proof for local SMBs |

### 2. Content planning & creation

| Role / task | What the business does | Why it matters |
|-------------|------------------------|----------------|
| Content calendar | Plan themes (promo, education, BTS, social proof) | Consistency |
| Copywriting | Captions that spark comments, not just broadcast | FB algorithm rewards conversation |
| **Graphic design** | Square/landscape images, quote cards, promos | Feed is visual |
| **Carousel / album** | Multi-image storytelling, before/after, steps | High engagement format |
| **Video & Reels** | Short vertical video, hooks in 3 sec | Highest organic reach on FB now |
| Stories | 24h promos, polls, “today only” | Urgency (declining vs Reels but still used) |
| Link strategy | Product/website links without killing reach | Links in body = 50–70% reach penalty |
| Hashtags | Light use on FB (unlike IG) | Minor signal |
| Events & offers | Launch events, discount posts | Local retail / services |

### 3. Publishing & scheduling

| Role / task | What the business does | Why it matters |
|-------------|------------------------|----------------|
| Post at optimal times | When audience is online | First-hour engagement tests the algorithm |
| Schedule ahead | Batch Sunday for the week | Founder time savings |
| Pin important post | Hours, promo, announcement | New visitors see key message |
| Cross-post from IG | Same Reel on FB | Efficiency (often lazy cross-post hurts) |

### 4. Community & sales (engagement)

| Role / task | What the business does | Why it matters |
|-------------|------------------------|----------------|
| Reply to comments | Questions, praise, complaints | Algorithm + customer trust |
| Hide / delete spam | Moderation | Page quality |
| **Messenger inbox** | Price questions, “do you deliver?” | Where African SMB sales actually happen |
| Mention monitoring | When customers tag the Page | Reputation |
| Reviews responses | Thank / resolve publicly | Local search + trust |

### 5. Measurement & improvement

| Role / task | What the business does | Why it matters |
|-------------|------------------------|----------------|
| Post performance | Reach, engagement, clicks | Double down on what works |
| Page growth | Followers, fan adds/removes | Health check |
| Best time / format | Reels vs photo vs text | Content DNA |
| Attribution | Did FB drive bookings/sales? | ROI proof |

### 6. Paid & shop (often manual today)

| Role / task | What the business does | Kova scope |
|-------------|------------------------|------------|
| Boost / Ads Manager | Paid reach | **Out of scope** (Meta Ads API separate) |
| Facebook Shop / catalog | Product tagging | **Not built** |
| Marketplace listings | Local sales | **Not built** |

---

## Kova coverage map — task by task

Legend: ✅ Works · 🔧 Partial / buggy · 🔲 Not built · ❌ API won’t allow · 👤 Manual in Kova UI

### Page foundation

| SMB task | Kova today | Notes |
|----------|------------|-------|
| Connect Facebook Page | ✅ | OAuth via Meta; requires **Facebook Page** (not personal profile) |
| Choose which Page to publish to | 🔧 | `selected_page_id` in metadata; **no UI picker** — defaults to first Page; “contact support” to switch |
| Audit Page completeness | 🔧 | Provider supports 10-field audit; **orchestration may use wrong page ID/token after OAuth** — needs fix |
| AI suggest profile improvements | ✅ | Profile Health + suggester (`profile_audit` app) |
| Apply text fields (about, hours, phone…) | ✅ | `update_profile` field-by-field |
| Update profile photo / cover | 🔲 | Provider notes separate endpoints; **not implemented** |
| Set Page CTA button | 🔲 | Graph API allows; **not implemented** |
| Respond to Page reviews | 🔲 | **Not implemented** |

### Content planning & creation

| SMB task | Kova today | Notes |
|----------|------------|-------|
| Weekly content ideas | ✅ | Research Agent, Strategist, Autopilot, Brief suggestions |
| Facebook-native caption | ✅ | Rich `PLATFORM_RULES["facebook"]` in Create Agent — hooks, “See more”, no URLs in body |
| Text-only post | ✅ | Full pipeline |
| Single image post | ✅ | AI image gen (1200×630 / square) + upload; direct bytes preferred |
| Carousel / album (2–10 images) | ✅ | Multi-photo feed post |
| Graphic design / templates | 🔧 | AI images + `graphics.py` templates; **no Canva-style editor** |
| Video post (feed) | 🔧 | `publish_video` exists on provider; **content tasks don’t call it** for FB |
| **Facebook Reels** | 🔲 | Create Agent can label `post_format=reel`; **no FB Reels publish path** |
| **Facebook Stories** | ✅ | `publish_story()` — photo via `photo_stories`, video via `video_stories` |
| Link in post without reach penalty | ✅ | **First-comment strategy** — link auto-posted as comment after publish |
| Product link in first comment | ✅ | `compose_first_comment()` + publish task |
| Hashtags (3–5) | ✅ | Prompt rules; appended in caption |
| Polls, events, offers | 🔲 | Graph API supports some; **not built** |
| Tag location / people / products | 🔲 | **Not built** |

### Publishing & scheduling

| SMB task | Kova today | Notes |
|----------|------------|-------|
| Schedule via Kova Calendar/Queue | ✅ | `scheduled_at` + Celery `check_and_publish_due_posts` every 5 min |
| Native FB scheduled publish API | 🔲 | Provider supports `scheduled_publish_time`; **Kova uses own scheduler, not FB native** |
| Drag reschedule on calendar | ✅ | `/content/calendar/` |
| Approve before publish | ✅ | Default — Studio `pending_approval` |
| Auto-approve + auto-schedule | ✅ | If `auto_approve_posts=True` (Pro+) |
| Pin post to top of Page | 🔲 | API supports; **not implemented** |
| Archive / delete post via Kova | 🔲 | **Not implemented** |

### Community & engagement

| SMB task | Kova today | Notes |
|----------|------------|-------|
| Fetch comments on published posts | ✅ | Engage Agent — last 14 days, Kova-published posts |
| AI draft comment replies | ✅ | Engage Agent + inbox UI |
| Manual send reply | ✅ | `engage/views.py` → `reply_to_comment` |
| Auto-send comment reply | 🔧 | Routing exists; **`ENGAGE_GRADUATED_AUTONOMY_ENABLED` off by default**; auto path may call wrong API method |
| Undo auto-sent comment | ✅ | `delete_comment` within window |
| Hide spam comment | 🔲 | API supports; **not implemented** |
| **Messenger DMs** | 🔲 | `get_messages` / `send_message` on provider; **not wired to Engage inbox** |
| @mentions monitoring | 🔲 | **Not implemented** for Facebook |
| Reviews / recommendations | 🔲 | **Not implemented** |

### Measurement

| SMB task | Kova today | Notes |
|----------|------------|-------|
| Post metrics (likes, comments, shares, reach) | ✅ | `get_post_metrics` + `PostMetric` model |
| Insights in Analytics / Brief | ✅ | Analyst Agent + Daily Brief |
| Page-level follower growth | 🔧 | `track_audience_growth` expects metadata keys **OAuth doesn’t set** — often broken |
| Revenue attribution from FB traffic | ✅ | UTM on links + Pixel + Conversion model |
| Content DNA (“what works on FB”) | ✅ | Analyst → feeds back into Create Agent |

---

## What Kova does well for Facebook (sell these)

1. **Feed posts that respect the algorithm** — no links in body; first-comment link strategy is implemented end-to-end (Create Agent → `first_comment` field → publish task).
2. **Platform-native copy** — Facebook-specific psychology, formatting, and min length in Create Agent (not generic cross-post).
3. **Photo + carousel + AI images** — sensible dimensions (1200×630, square); product carousels from Snap to Sell.
4. **Approve-in-5-minutes workflow** — Brief → Studio → Queue matches how SMBs actually work.
5. **Comment engagement loop** — fetch, draft, manual reply (Growth+ plan).
6. **Post performance feedback loop** — metrics → Analyst → smarter next posts.

---

## Gaps, bugs & priorities (Facebook)

### P0 — Breaks trust or core promise

| Issue | Impact | Fix direction |
|-------|--------|---------------|
| Profile audit uses wrong Page ID/token after OAuth | Profile Health lies or fails | Resolve `selected_page_id` + page token in `auditor._audit_kwargs_for` |
| FB Stories/Reels promised in Create Agent but don’t publish correctly | User approves “Reel”, gets feed photo or failure | Wire `publish_video` / Reels endpoint OR stop suggesting formats until ready |
| No Page picker UI | Multi-Page businesses publish to wrong Page | Settings UI like LinkedIn org picker |
| Auto-reply wrong API path | Broken auto-engage on comments | Use `reply_to_comment`, not `post_comment` on comment ID |

### P1 — Major value gap for SMBs

| Issue | Impact | Fix direction |
|-------|--------|---------------|
| Messenger not in Engage inbox | **#1 sales channel** for African SMBs missing | Fetch `get_messages`, unified inbox tab, human-approved send |
| Facebook Reels publish | Reels = primary organic reach | Implement Graph API Reels upload path |
| Feed video publish wired | Video posts fail silently | Route `post_format=video` → `publish_video` in `content/tasks.py` |
| Page photo / cover update | “Complete your Page” audit can’t fix visuals | `/{page-id}/picture` + cover endpoints |
| Page growth tracking broken | Brief can’t show follower trend | Align metadata with OAuth `pages[]` shape |

### P2 — Nice-to-have for value-for-money

| Issue | Impact |
|-------|--------|
| Pin post, hide comment, like comment | Moderation polish |
| Page CTA button management | Conversion optimization |
| Polls / events for local businesses | Retail, restaurants |
| Native FB scheduling API as option | Backup if Kova scheduler down |
| Reviews / recommendations inbox | Local services |
| Facebook Shop / product tags | E-commerce SMBs |

### P3 — Out of scope or API-blocked

| Item | Note |
|------|------|
| Meta Ads / Boost | Separate Ads API product |
| Go Live | Not available to third-party apps |
| Full Ads Manager | Not Kova’s core loop |
| Marketplace | Different product surface |

---

## The “Facebook Page for a startup” — ideal Kova journey

```text
WEEK 0 — Setup
  Connect Page → pick correct Page → Profile Health audit → apply hours/phone/about
  → set CTA (future) → connect Pixel / Kova Page link for attribution

WEEK 1 — Content rhythm
  Autopilot or Studio seeds → Create Agent (FB-native copy + image)
  → approve in Studio → Queue schedules → first-comment link auto-posts

DAILY — 5 minutes
  Daily Brief → approve 1–3 posts → Engage: reply to comments (Messenger when built)

WEEKLY — Learn
  Insights: which format won → Adapt Agent adjusts → more carousels / fewer link posts
```

**Today’s gap in that journey:** Page picker, Messenger, Reels/video, profile images, follower growth on Brief.

---

## Facebook content formats — design specs Kova uses

| Format | Dimensions / notes | Kova support |
|--------|-------------------|--------------|
| Feed image (landscape) | 1200 × 630 recommended | ✅ AI + upload |
| Feed image (square) | 1080 × 1080 | ✅ |
| Carousel | 2–10 images | ✅ publish |
| Feed video | MP4, various ratios | 🔧 provider only |
| Reels | 9:16, short | 🔲 |
| Stories | 9:16, 24h | 🔲 (broken) |
| Link preview post | URL in post | ❌ avoided by design — use first comment |

---

## Plan gates affecting Facebook

From `apps/billing/models.py` — Facebook is not singled out; limits are cross-platform:

| Feature | Starter | Growth | Pro |
|---------|---------|--------|-----|
| Connect FB (counts as social account) | 1 account | 3 | 10 |
| Posts/month (includes FB) | 15 | 60 | 150 |
| Engage (comments) | No | Yes | Yes |
| AI image generation | No | Yes | Yes |
| Auto-approve posts | No | No | Yes |

**Messaging for sales:** Growth unlocks comment engagement; Pro unlocks full agent autonomy options.

---

## Recommended build order (Facebook sprint)

**Sprint 1 — Trust fixes (1–2 weeks)**  
1. Page picker UI + fix audit token/ID  
2. Fix auto-reply API method  
3. Stop Create Agent suggesting FB Reels/Stories until publish works (or gate with “coming soon”)

**Sprint 2 — Video & Reels (2–3 weeks)**  
4. Wire feed video publish  
5. Facebook Reels endpoint  
6. Studio UI: format picker shows only what works per platform

**Sprint 3 — Messenger (2–3 weeks)**  
7. Messenger fetch → Engage inbox tab  
8. AI draft + manual send (same autonomy model as comments)  
9. Link to Leads when phone/name captured

**Sprint 4 — Page completeness (1 week)**  
10. Profile + cover photo upload  
11. Page CTA button  
12. Fix follower growth in Brief

---

## API & Meta App Review notes

- Production requires **Meta App Review** for Page publish, engagement, and Messenger scopes.
- Personal Facebook profiles **cannot** be used — Pages only (Kova warns on connect).
- Token refresh: long-lived user token + page tokens in `metadata.pages[]`; beat refreshes every 30 min.
- Error messages mapped in `apps/platforms/error_codes.py` (codes 190, 200, 10, etc.).

---

## Quick reference — key files

```
apps/platforms/providers/instagram_facebook.py   # FacebookProvider — Graph API
apps/content/tasks.py                            # publish_post_to_platform, metrics
apps/agents/create_agent.py                      # PLATFORM_RULES["facebook"]
apps/agents/engage_agent.py                      # Comment fetch + reply
apps/utils/first_comments.py                     # Link-in-first-comment
apps/profile_audit/                              # Page audit orchestration
apps/content/image_gen.py                        # Image dimensions
apps/platforms/views.py                          # OAuth connect flow
```

---

## Bottom line for founders

**Kova is a strong Facebook feed-posting + comment-engagement assistant today**, with unusually good attention to Facebook’s link penalty (first-comment strategy) and caption quality.

**It is not yet a full Facebook Page manager** — Reels, Messenger, Stories, visual Page setup, and multi-Page UX are the main gaps between “good scheduler with AI” and “replace the person running our Facebook.”

**Next platform audit:** Instagram (separate doc — shared Meta provider but different formats and Engage rules).

---

*Update this doc when Facebook provider or publish pipeline changes. Cross-check against `docs/system-maps/` Create → Schedule map.*
