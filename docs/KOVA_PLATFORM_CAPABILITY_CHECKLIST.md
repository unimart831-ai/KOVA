# Kova Platform Capability Checklist
## Instagram · Facebook · TikTok · WhatsApp

> **Purpose:** Single source of truth for what users can do on each platform,
> what Kova currently supports, what is broken, what is not yet built, and what
> the platform API makes impossible. Use this doc to prioritise engineering
> sprints and communicate capability gaps to founders and investors.
>
> **Last updated:** 2026-06-02
> **Informed by:** Platform audit (`KOVA_CAPABILITIES_UPDATE_2026_05.md`),
> full provider code review, and Engage/WhatsApp model audit.

---

## Legend

| Symbol | Meaning |
|--------|---------|
| ✅ | Kova supports it — fully working |
| 🔧 | Infrastructure exists but broken or incomplete |
| 🔲 | Not yet built — platform API allows it |
| ❌ | Platform API does not allow third-party apps to do this |

---

## INSTAGRAM

### Content Creation & Drafting

| # | Capability | Status | Notes |
|---|---|---|---|
| 1 | AI-generate caption from a brief | ✅ | Create Agent |
| 2 | Platform-specific caption variant (IG-optimised) | 🔲 | Currently uses the same caption for all platforms |
| 3 | Draft and save post before scheduling | ✅ | `Post.status = draft` |
| 4 | Design single-image post | 🔲 | Can publish images; no in-app canvas/editor |
| 5 | Design carousel (2-10 slides) | 🔲 | Can publish carousels; no in-app slide designer |
| 6 | Upload Reel (vertical video) | ✅ | Via video URL |
| 7 | Generate Reel script / hook from brief | 🔲 | Create Agent writes captions only, not video scripts |
| 8 | Add music to Reels | ❌ | Meta does not expose music library to third-party apps |
| 9 | Add stickers, polls, questions to Stories | ❌ | No API for Story interactive elements |
| 10 | Add text overlays / captions to video | ❌ | Must be baked into the video file before upload |
| 11 | Generate AI image for post | 🔲 | `apps/media_queue` infrastructure exists; not wired to publishing |
| 12 | Auto-add first comment after publish | ✅ | `post_comment(**kwargs)` + publish task for FB/IG/LinkedIn |
| 13 | Add hashtags to post | ✅ | Via caption |
| 14 | AI-suggest hashtags based on content | 🔲 | `search_hashtag` exists but not wired to Create Agent |
| 15 | Tag products (Instagram Shopping) | 🔲 | API supports `product_tags` field — not implemented |
| 16 | Tag location | 🔲 | Not implemented |
| 17 | Tag other accounts | 🔲 | Not implemented |
| 18 | Collab post (two-account co-author) | ❌ | Not available in Content Publishing API |
| 19 | Add alt text to image | 🔲 | API supports `accessibility_caption` field — not implemented |

### Scheduling & Publishing

| # | Capability | Status | Notes |
|---|---|---|---|
| 20 | Schedule post for a future time | ✅ | Celery Beat + `Post.scheduled_at` |
| 21 | Drag-to-reschedule on calendar | ✅ | `/content/<id>/reschedule/` endpoint (P4.3) |
| 22 | Publish single image post | ✅ | |
| 23 | Publish carousel post | ✅ | |
| 24 | Publish Reel | 🔧 | Works but polls synchronously — times out for videos > 60 seconds |
| 25 | Publish Story (image) | ✅ | |
| 26 | Publish Story (video) | 🔧 | Same synchronous polling bug as Reels |
| 27 | Publish feed video (non-Reel) | 🔲 | Container API supports it — not wired |
| 28 | Go Live | ❌ | Not available in Content Publishing API |
| 29 | Create Story Highlights | ❌ | Not available in Graph API |
| 30 | Pin a post to profile | ❌ | Not available in Graph API |
| 31 | Archive a post | ❌ | Not available in Graph API |
| 32 | Cross-post TikTok video as IG Reel | 🔲 | High-value innovation — not built |

### Engagement — Comments

| # | Capability | Status | Notes |
|---|---|---|---|
| 33 | Fetch comments on posts | ✅ | |
| 34 | AI-generate reply suggestion | ✅ | Engage Agent |
| 35 | Auto-send reply (confidence ≥ 0.85) | ✅ | GRADUATED autonomy mode |
| 36 | Manually approve and send draft reply | ✅ | |
| 37 | Undo auto-sent reply (5-minute window) | ✅ | `EngageReply.can_undo()` |
| 38 | Delete a comment | ✅ | |
| 39 | Reply to a comment (threaded) | ✅ | `reply_to_comment` |
| 40 | Like a comment | ❌ | Not available in Graph API |
| 41 | Pin a comment | ❌ | Not available in Graph API |
| 42 | Hide a comment | 🔲 | API supports `is_hidden=true` — not implemented |
| 43 | Detect booking intent in comments | ✅ | `apps/agents/booking_intent.py` |
| 44 | Auto-append booking link to reply | ✅ | Engage Agent v2 |
| 45 | Track repeat engagers (Superfans) | ✅ | `Superfan` model |

### Engagement — Direct Messages

| # | Capability | Status | Notes |
|---|---|---|---|
| 46 | Fetch DM conversations | ✅ | |
| 47 | Read DM message content | ✅ | |
| 48 | Send DM reply | ✅ | `send_message` |
| 49 | AI-generate DM reply | ✅ | Engage Agent |
| 50 | Auto-send DM reply | ✅ | Confidence-gated |
| 51 | Send image in DM | 🔲 | API supports it — not implemented |
| 52 | React to a DM | ❌ | Not available in Graph API |
| 53 | Voice notes in DMs | ❌ | Not available in Graph API |
| 54 | IG Broadcast Channels | ❌ | Not available in Graph API |

### Analytics & Insights

| # | Capability | Status | Notes |
|---|---|---|---|
| 55 | Post metrics (likes, comments, shares, saves, reach, impressions) | ✅ | |
| 56 | Account-level insights (profile views, website clicks, follower count) | ✅ | |
| 57 | Story metrics (exits, taps forward/back, impressions) | 🔧 | Must fetch within 24h of Story publish — no enforced timing in Celery |
| 58 | Reel-specific metrics (plays, shares, saves) | 🔧 | Uses same endpoint as feed posts; some Reel metrics need a separate call |
| 59 | Audience demographics (age, gender, location, active times) | 🔲 | Not implemented |
| 60 | Best posting time recommendation | 🔲 | Not implemented |
| 61 | Plain-English performance insights | ✅ | `apps/analytics/plain_english.py` (P4.4) |
| 62 | Hashtag performance tracking | 🔲 | `search_hashtag` not wired back to Adapt Agent |
| 63 | Competitor account benchmarking | 🔲 | Phase 3 W10 — not built |
| 64 | Revenue attribution per post | ✅ | Pixel + Conversion model |

### Profile & Bio Management

| # | Capability | Status | Notes |
|---|---|---|---|
| 65 | Audit profile completeness | ✅ | 5-field weighted score: bio, website, name, picture, username |
| 66 | Update bio | ✅ | `update_profile` → Graph API |
| 67 | Update website link | ✅ | |
| 68 | Update profile picture | ❌ | Meta restricts this to the mobile app |
| 69 | Switch account type (Personal → Professional) | ❌ | Not available in Graph API |
| 70 | Manage Story Highlights | ❌ | Not available in Graph API |
| 71 | Multi-link bio page (Linktree-style) | 🔲 | `apps/links` app exists — not surfaced as IG bio link |

---

## FACEBOOK

### Content Creation & Drafting

| # | Capability | Status | Notes |
|---|---|---|---|
| 1 | AI-generate caption | ✅ | Create Agent |
| 2 | Platform-specific caption (FB-optimised, no hashtags) | 🔲 | Uses same caption across all platforms |
| 3 | Draft and save post | ✅ | |
| 4 | Write text-only post | ✅ | |
| 5 | Post single photo | ✅ | Direct file upload + URL fallback |
| 6 | Post multiple photos (album) | ✅ | Batch upload |
| 7 | Post video | ✅ | Via `file_url` |
| 8 | Post Facebook Reel | 🔲 | Different endpoint from feed video — not implemented |
| 9 | Post Facebook Story | 🔲 | Not implemented |
| 10 | Create a poll | 🔲 | Graph API supports poll posts — not implemented |
| 11 | Create an event | 🔲 | Graph API supports event creation — not implemented |
| 12 | Create a Facebook Offer (discount/coupon) | 🔲 | Not implemented |
| 13 | Tag products from catalog (Facebook Shop) | 🔲 | Not implemented |
| 14 | Tag location | 🔲 | Not implemented |
| 15 | Tag people or Pages | 🔲 | Not implemented |
| 16 | Go Live | ❌ | Not available for third-party apps via Content Publishing API |
| 17 | First comment with clickable link | ✅ | Link-in-first-comment wired in publish pipeline |

### Scheduling & Publishing

| # | Capability | Status | Notes |
|---|---|---|---|
| 18 | Schedule post for a future time | ✅ | `scheduled_publish_time` parameter |
| 19 | Drag-to-reschedule | ✅ | Same endpoint as Instagram |
| 20 | Pin a post to the top of the Page | 🔲 | Graph API supports `pinned=true` — not implemented |
| 21 | Archive / unpublish a post | 🔲 | Not implemented |
| 22 | Cross-post IG Reel to FB Reel | 🔲 | High-value innovation — not built |

### Engagement — Comments & Reactions

| # | Capability | Status | Notes |
|---|---|---|---|
| 23 | Fetch comments | ✅ | |
| 24 | Reply to comments | ✅ | |
| 25 | Delete comments | ✅ | |
| 26 | Auto-send first comment with clickable link | ✅ | First-comment strategy enforced for FB/IG/LinkedIn |
| 27 | Like a comment | 🔲 | `POST /{comment-id}/likes` with page token — not implemented |
| 28 | Hide a comment | 🔲 | `is_hidden=true` — not implemented |
| 29 | AI-generate reply | ✅ | Engage Agent |
| 30 | Auto-send reply | ✅ | Confidence-gated |
| 31 | Undo auto-reply | ✅ | `delete_comment` wired |
| 32 | React to a post as the Page | ❌ | Pages cannot react to posts via API |

### Engagement — Page Inbox (Messenger)

| # | Capability | Status | Notes |
|---|---|---|---|
| 33 | Fetch Messenger conversations | ✅ | `get_messages` |
| 34 | Read message content | ✅ | |
| 35 | Reply to Messenger message | 🔧 | Posts to `/me/messages` — must be `/{page_id}/messages`. Bug |
| 36 | AI-generate Messenger reply | ✅ | Engage Agent (broken by endpoint bug above) |
| 37 | Send image in Messenger | 🔲 | Not implemented |
| 38 | Set up away / out-of-hours auto-reply | 🔲 | Graph API supports it — not implemented |
| 39 | Quick reply shortcuts | 🔲 | Not implemented |

### Analytics & Insights

| # | Capability | Status | Notes |
|---|---|---|---|
| 40 | Post metrics (likes, comments, shares, impressions, reach, clicks) | ✅ | Fallback metric sets for different post types |
| 41 | Page-level insights (impressions, engaged users, fan adds/removes) | ✅ | `get_account_insights` |
| 42 | Audience demographics | 🔲 | Not implemented |
| 43 | Revenue attribution per post | ✅ | Pixel + Conversion model |

### Profile & Page Management

| # | Capability | Status | Notes |
|---|---|---|---|
| 44 | Audit Page completeness (10-field weighted score) | ✅ | Strongest audit in the system |
| 45 | Update about, description, phone, email, website, address, hours | ✅ | `update_profile` field-by-field |
| 46 | Update profile picture | 🔲 | Separate endpoint `/{page_id}/picture` — not implemented |
| 47 | Update cover photo | 🔲 | Separate endpoint — not implemented |
| 48 | Add / change Page CTA button | 🔲 | Not implemented |
| 49 | Manage Page team roles | 🔲 | Not implemented |
| 50 | Respond to Page reviews / recommendations | 🔲 | Not implemented |
| 51 | Manage Facebook Shop / product catalog | 🔲 | Not implemented |

---

## TIKTOK

### Content Creation & Drafting

| # | Capability | Status | Notes |
|---|---|---|---|
| 1 | AI-generate caption | ✅ | Create Agent |
| 2 | TikTok-optimised caption (≤ 150 chars, trending hashtags) | 🔲 | Same caption as other platforms |
| 3 | Generate TikTok video script / hook | 🔲 | Not built |
| 4 | Upload video (from URL) | ✅ | PULL_FROM_URL |
| 5 | Upload video (direct file, chunked) | ✅ | FILE_UPLOAD with 10 MB chunks |
| 6 | Upload photo carousel (up to 35 images) | ✅ | Photo post via Content Posting API |
| 7 | Add music from TikTok library | ❌ | Not available in Content Posting API |
| 8 | Add text overlays / effects | ❌ | Must be in the video file before upload |
| 9 | Add voiceover | ❌ | Must be in the video file before upload |
| 10 | Create Duet | ❌ | Not available in API |
| 11 | Create Stitch | ❌ | Not available in API |
| 12 | Set video cover / thumbnail | ✅ | `video_cover_timestamp_ms` parameter |
| 13 | Set Duet / Stitch / Comment permissions | ✅ | `disable_duet`, `disable_stitch`, `disable_comment` |
| 14 | Label post as AI-generated | ✅ | `is_aigc` parameter |
| 15 | Label as branded / partnership content | ✅ | `brand_content_toggle`, `brand_organic_toggle` |

### Scheduling & Publishing

| # | Capability | Status | Notes |
|---|---|---|---|
| 16 | Publish video immediately | ✅ | Posts `SELF_ONLY` until TikTok app audit passes — invisible to audience |
| 17 | Schedule post for a future time | 🔲 | TikTok API supports `scheduled=true` + `schedule_time` — not implemented |
| 18 | Check publish / processing status | ✅ | `check_publish_status` |
| 19 | Backfill post URL after processing completes | 🔲 | No Celery task polling status → `Post.url` stays empty forever |
| 20 | Publish to PUBLIC audience | 🔲 | Requires passing TikTok's app audit — currently `SELF_ONLY` |
| 21 | Go Live | ❌ | Not available in Content Posting API |

### Engagement

| # | Capability | Status | Notes |
|---|---|---|---|
| 22 | Read comments on videos | ❌ | TikTok does not provide comment API to third-party apps |
| 23 | Reply to comments | ❌ | Not available in API |
| 24 | Reply to comments with a video | ❌ | Not available in API |
| 25 | Like / pin comments | ❌ | Not available in API |
| 26 | Read DMs | ❌ | Not available in API |
| 27 | Reply to DMs | ❌ | Not available in API |
| 28 | Detect booking intent in comments | 🔲 | Cannot read comments; partial workaround via TikTok mention webhooks |
| 29 | Track Superfans (repeat engagers) | 🔲 | No comment data to build from |

### Analytics & Insights

| # | Capability | Status | Notes |
|---|---|---|---|
| 30 | Per-video metrics (views, likes, comments, shares) | ✅ | `get_post_metrics` |
| 31 | List recent videos with metrics | ✅ | `get_own_posts` |
| 32 | Account-level insights (followers, total likes, video count) | ✅ | Via `get_user_info` |
| 33 | Video retention rate / watch time | ❌ | Not in Display API |
| 34 | Traffic source breakdown (FYP, Following, Search, Profile) | ❌ | Not in Display API |
| 35 | Audience demographics (age, gender, location, active times) | ❌ | Not in Display API |
| 36 | Trending sounds / audio intelligence | 🔲 | No official API; discovery via content pattern analysis |
| 37 | Cross-platform engagement comparison | 🔧 | Distorted: TikTok `view_count` ≠ IG `impressions` — mapped incorrectly |
| 38 | Revenue from TikTok Series / LIVE gifts | ❌ | Not in API |

### Profile Management

| # | Capability | Status | Notes |
|---|---|---|---|
| 39 | Audit profile completeness | 🔲 | `audit_profile` not implemented for TikTok |
| 40 | Update bio / display name | ❌ | TikTok API does not support profile updates by third-party apps |
| 41 | Update profile picture | ❌ | Not available in API |
| 42 | Add bio link | ❌ | Must be done in the TikTok app directly |
| 43 | Manage playlists / collections | ❌ | Not in API |
| 44 | View Creator Info (privacy defaults, max video duration) | ✅ | `get_creator_info` |

---

## WHATSAPP

### Messaging — Outbound

| # | Capability | Status | Notes |
|---|---|---|---|
| 1 | Send text message (within 24h window) | ✅ | `send_text_message` |
| 2 | Send text with link preview | ✅ | `preview_url=True` |
| 3 | Send image with caption | ✅ | `send_image_message` |
| 4 | Send video message | 🔲 | API supports it — not implemented |
| 5 | Send document / PDF | 🔲 | API supports it — not implemented |
| 6 | Send audio file | 🔲 | API supports it — not implemented |
| 7 | Send voice note | 🔲 | API supports it — not implemented |
| 8 | Send location | 🔲 | API supports it — not implemented |
| 9 | Send contact card | 🔲 | API supports it — not implemented |
| 10 | Send sticker | 🔲 | API supports it — not implemented |
| 11 | Send template message (outside 24h window) | ✅ | `send_template_message` |
| 12 | Send interactive button message (max 3 buttons) | ✅ | `send_interactive_buttons` |
| 13 | Send interactive list message (sections + rows) | ✅ | `send_interactive_list` |
| 14 | Send product / catalog message (Commerce API) | 🔲 | Not implemented |
| 15 | Send order confirmation message | 🔲 | Not implemented |
| 16 | React to a message (emoji) | 🔲 | API supports it — not implemented |
| 17 | Quote-reply to a specific message | 🔲 | API supports it — not implemented |
| 18 | Mark message as read (blue ticks) | ✅ | `mark_as_read` |

### Messaging — Inbound & Auto-Reply

| # | Capability | Status | Notes |
|---|---|---|---|
| 19 | Receive inbound messages via webhook | ✅ | `apps/whatsapp/webhook.py` |
| 20 | Parse inbound message types (text, image, video, etc.) | ✅ | `WhatsAppMessage.MessageType` |
| 21 | 24-hour window tracking | ✅ | `WhatsAppConversation.window_expires_at` |
| 22 | Auto-open 24h window on inbound message | 🔧 | `open_window()` doesn't call `.save()` — window never persists to DB |
| 23 | AI-generate reply (confidence-gated) | ✅ | |
| 24 | Auto-send reply when confidence ≥ 0.8 | ✅ | |
| 25 | Booking intent detection in WA message | ✅ | `booking_intent.py` |
| 26 | WA-native booking via interactive list (slot picker) | 🔲 | `send_interactive_list` built; not wired to booking flow |
| 27 | Away message / out-of-hours auto-reply | 🔲 | Not implemented |
| 28 | Quick reply shortcuts | 🔲 | Not implemented |
| 29 | Escalate to human (AI hands off) | ✅ | `escalated_in_brief` flag |
| 30 | WhatsApp Flows (multi-step interactive forms) | 🔲 | Not implemented (advanced Meta API) |

### Broadcast & Campaigns

| # | Capability | Status | Notes |
|---|---|---|---|
| 31 | Create broadcast campaign | ✅ | `WhatsAppBroadcast` model |
| 32 | Select template for broadcast | ✅ | |
| 33 | Segment recipients by tags / activity | ✅ | `segment` JSONField |
| 34 | Send broadcast to recipient list | 🔧 | Sends synchronously in a loop — blocks worker; no retry on rate limit |
| 35 | Schedule broadcast for a future time | ✅ | `scheduled_at` field |
| 36 | Per-contact optimal send timing | 🔲 | `per_contact_timing` field exists — logic not built |
| 37 | Track broadcast delivery (sent / delivered / read) | ✅ | `WhatsAppBroadcast` counters |
| 38 | Track broadcast replies | ✅ | `replied_count` counter |
| 39 | Drip sequence (multi-step, multi-day) | ✅ | `BroadcastSequence` + `SequenceEnrollment` |
| 40 | Onboarding sequence trigger | ✅ | `SequenceType.ONBOARDING` |
| 41 | Re-engagement sequence | ✅ | `SequenceType.RE_ENGAGEMENT` |
| 42 | Post-purchase follow-up sequence | ✅ | `SequenceType.POST_PURCHASE` |
| 43 | Auto-enrol walk-in customers into sequence | 🔲 | Walk-ins not tagged as WA contacts |
| 44 | Segment by walk-in or booking source | 🔲 | Not built — high-value for Tier 1 SMEs |

### Templates

| # | Capability | Status | Notes |
|---|---|---|---|
| 45 | Create / draft a template | ✅ | `WhatsAppTemplate` model + `create_template` API call |
| 46 | Submit template to Meta for approval | ✅ | |
| 47 | Track template approval status | ✅ | `TemplateStatus` enum |
| 48 | View all templates and their status | ✅ | `get_templates` |
| 49 | AI-draft a template from natural language | 🔲 | `created_by_ai` flag exists — no Create Agent wiring |
| 50 | Validate template against Meta policies before submit | 🔲 | `ai_prompt_used` field exists — no validator built |
| 51 | View template performance (open rate, reply rate, block rate) | 🔲 | `performance_data` JSONField exists — nothing writes to it |

### Status (WhatsApp's 24h Stories equivalent)

| # | Capability | Status | Notes |
|---|---|---|---|
| 52 | AI-generate Status text | ✅ | `StatusContent` + `StatusTemplate` models |
| 53 | Schedule Status for a specific time | ✅ | `scheduled_for` field |
| 54 | Generate one-tap share URL | 🔧 | Produces a `wa.me` chat link — not a Status share. Wrong URL format |
| 55 | Repurpose IG / FB post as a Status | ✅ | `source_post` FK + `ai_adapted` flag |
| 56 | Post Status directly via API | ❌ | WhatsApp has no Status publishing API for businesses |
| 57 | View Status analytics (views, reactions) | ❌ | Not available in Cloud API |

### Channels (Broadcast-to-subscribers)

| # | Capability | Status | Notes |
|---|---|---|---|
| 58 | Create / manage a WhatsApp Channel | ✅ | `WhatsAppChannel` model |
| 59 | Auto-curate content from other platforms to Channel | ✅ | `auto_curate` + `curate_from_platforms` fields |
| 60 | AI-adapt content for Channel format | ✅ | `ai_adapted` on `ChannelPost` |
| 61 | Set max posts per day limit | ✅ | `max_posts_per_day` field |
| 62 | View Channel follower count | ✅ | `follower_count` field |
| 63 | Track Channel post reach and reactions | ✅ | `reach` + `reactions` on `ChannelPost` |

### Analytics

| # | Capability | Status | Notes |
|---|---|---|---|
| 64 | Daily analytics snapshot (conversations, messages, AI performance) | ✅ | `WhatsAppAnalytics` model |
| 65 | AI weekly digest of WA performance | ✅ | `WeeklyDigest` model |
| 66 | Average response time tracking | ✅ | `avg_response_time_seconds` |
| 67 | Sentiment tracking per conversation | ✅ | `sentiment_score` on `WhatsAppConversation` |
| 68 | Delivery rate / read rate | ✅ | Computed properties on `WhatsAppAnalytics` |
| 69 | Revenue attributed via WA conversations | ✅ | `revenue_attributed` on `WhatsAppAnalytics` |
| 70 | Real-time delivery status updates (sent → delivered → read) | 🔲 | Webhook receives updates; `WhatsAppAnalytics` not updated from them |

### Profile Management

| # | Capability | Status | Notes |
|---|---|---|---|
| 71 | Audit WA business profile (about, address, description, email, website, vertical) | 🔧 | Works but calls hardcoded `v18.0` endpoint — module uses `v21.0` |
| 72 | Update business profile | 🔲 | `PATCH /{phone-id}/whatsapp_business_profile` — not implemented |
| 73 | View phone number quality rating | ✅ | Stored in `metadata.quality_rating` at connect time |
| 74 | Alert when quality rating degrades | 🔲 | Not implemented |
| 75 | Manage multiple phone numbers under one WABA | 🔲 | Not implemented |

---

## Cross-Platform — Shared Capabilities

| # | Capability | Status | Notes |
|---|---|---|---|
| 1 | Publish same post to multiple platforms simultaneously | ✅ | Multi-account publishing pipeline |
| 2 | One caption for all platforms | ✅ | Works — but actively hurts performance on 3 of 4 platforms |
| 3 | Per-platform caption variants (IG / FB / TikTok / WA) | 🔲 | Most important missing Create Agent feature |
| 4 | Cross-post TikTok video → IG Reels | 🔲 | Not built |
| 5 | Cross-post IG Reel → FB Reel | 🔲 | Not built |
| 6 | Cross-post any post → WA Channel | ✅ | `ChannelPost.source_post` FK |
| 7 | Token expiry warning (7 days before) | 🔲 | Not built |
| 8 | Token expired alert in Daily Brief | 🔲 | Not built |
| 9 | Superfan detection (repeat engager across platforms) | ✅ | `Superfan` model — blind on TikTok (no comment API) |
| 10 | Revenue attribution across all 4 platforms | ✅ | Unified `total_revenue` in `get_revenue_summary` |
| 11 | Plain-English performance insights per platform | ✅ | `apps/analytics/plain_english.py` (P4.4) |
| 12 | Competitor benchmarking | 🔲 | Master Plan Phase 3 W10 — not built |
| 13 | Profile completeness score across all connected accounts | 🔧 | Built for FB + IG + WA; TikTok missing |
| 14 | AI-generated profile update suggestions | 🔲 | Audit exists — no "here's what to write for your bio" next step |

---

## Gap Summary by Platform

| Platform | ✅ Working | 🔧 Broken / Partial | 🔲 Not Yet Built | ❌ Not Possible via API |
|---|---|---|---|---|
| **Instagram** | 25 | 6 | 20 | 10 |
| **Facebook** | 18 | 4 | 22 | 5 |
| **TikTok** | 11 | 4 | 10 | 18 |
| **WhatsApp** | 30 | 5 | 22 | 4 |
| **Cross-platform** | 6 | 1 | 7 | — |

---

## The Five Highest-ROI Fixes (in order)

### Fix 1 — Instagram `post_comment` NameError — ✅ Fixed (Jun 2026)
**File:** `apps/platforms/providers/instagram_facebook.py`
**Was:** Missing `**kwargs` caused NameError on first-comment calls.
**Now:** `post_comment(..., **kwargs)`; publish task posts first comments for FB/IG/LinkedIn.

### Fix 2 — Instagram / Facebook broken post URLs
**Instagram:** Returns `https://www.instagram.com/p/{raw_graph_api_id}/` — this 404s.
**Facebook:** Returns `https://www.facebook.com/{post_id}` — wrong format.
**Fix:** After publish, call `GET /{media_id}?fields=permalink` (Instagram) and construct the correct permalink from page_id + post_id (Facebook).

### Fix 3 — Facebook Messenger `send_message` wrong endpoint
**File:** `apps/platforms/providers/instagram_facebook.py:638`
**Problem:** Posts to `/me/messages` — must be `/{page_id}/messages`.
**Fix:** Pass `page_id` into the request URL.

### Fix 4 — WhatsApp `audit_profile` hardcoded `v18.0`
**File:** `apps/platforms/providers/whatsapp.py:278`
**Problem:** Module constant is `WA_API_VERSION = "v21.0"` but the audit call hardcodes `v18.0`. Magic Fill runs on a deprecated API version.
**Fix:** Use `WA_API_BASE` constant.

### Fix 5 — WhatsApp `open_window()` doesn't persist
**File:** `apps/whatsapp/models.py:103`
**Problem:** `open_window()` sets fields in memory but never calls `self.save()`. The 24-hour window never actually opens in the DB. Free-form messaging falls back to templates prematurely.
**Fix:** Call `self.save(update_fields=["window_expires_at", "last_message_at"])` at end of method.

---

## The Three Builds That Close the Most Gaps

### Build 1 — Per-platform caption generator in the Create Agent
One change. All four platforms improve immediately.
- **Instagram:** 150-word max, 5-8 hashtags, emoji-heavy, ends with save-prompt
- **Facebook:** 40-80 words, no hashtags, conversational, question-ending
- **TikTok:** Under 150 chars, 3 trending hashtags, hook word first
- **WhatsApp broadcast:** Two sentences, personal tone, one clear CTA

### Build 2 — Async Reel / TikTok publish status polling
A single Celery Beat task that polls container status for IG Reels, IG Story videos, and TikTok videos. Solves the 60-second timeout failure on IG and the empty `Post.url` on TikTok. One task, three problems closed.

### Build 3 — WhatsApp interactive list → booking slot picker
`send_interactive_list` is fully built. The slot engine runs. Booking intent detection runs. The missing piece: 30 lines wiring them together. When a customer DMs "can I book?" the reply is a list — "Tap your slot: 10am · 2pm · 4pm." They reply. Booking created. No browser, no link, no data cost.

---

## Platform API Limits — What Kova Can Never Do

| Platform | Hard API Limits |
|---|---|
| **Instagram** | No music library access, no Story stickers/polls/questions, no Highlights management, no profile picture update, no pin/archive posts, no comment likes/pins, no Live |
| **Facebook** | Pages cannot react to posts, no third-party Live publishing |
| **TikTok** | No comment read/write, no DM access, no music from TikTok library, no text overlay/effects/voiceover, no Duet/Stitch, no Live, no profile updates — TikTok is the most closed platform by far |
| **WhatsApp** | No Status publishing API (Status is manual-only), no Status analytics, WhatsApp Pay limited to select markets |

---

*This document is the companion to `KOVA_PLATFORM_AUDIT_2026_05.md` and `KOVA_MASTER_PLAN.md`.
Update it whenever a capability ships or an API limit changes.*
