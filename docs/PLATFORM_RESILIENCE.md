# Kova Platform Resilience — Founder Decision Document

**Written:** 2026-05-20  
**Status:** Baseline implemented (Jun 2026) — token warnings, auto-refresh, publish errors surfaced  
**Owner:** Iranzi Innocent (Founder)  
**Purpose:** Define how Kova survives every third-party platform failure before going live with real users

### Implementation status (Jun 2026)

| Decision area | Status | Where |
|---|---|---|
| Token expiry warnings (7-day / 1-day / expired) | ✅ Shipped | `platforms.warn_expiring_tokens`, Platforms list banners, in-app notifications |
| Facebook/Instagram token auto-extension | ✅ Shipped | `platforms.refresh_expiring_tokens` (Celery Beat, every 30 min) |
| Publish failure → user-visible error | ✅ Shipped | `Post.publish_error`, failed status, in-app notification on publish fail |
| Stuck publishing recovery (Reels/Stories timeouts) | ✅ Shipped | `content.recover_stuck_publishing_posts` (12 min cutoff) |
| Rate-limit retry with backoff | 🔲 Partial | Basic retry in providers; full 3-strike reschedule UX not built |
| Platform outage hold + auto-resume | ✅ Shipped (Jun 2026) | `check_and_publish_due_posts` + `publish_post` hold when `is_outage`; auto-resume on success |
| Token expiry WebSocket toasts | ✅ Shipped (Jun 2026) | `warn_expiring_tokens` → `token_warning` WS event + notification |

---

## The Core Principle

Kova sits between users and platforms we don't control. When Meta has a bad day, users blame Kova. When a token silently expires, posts stop going out and nobody knows why. When LinkedIn changes an API endpoint, users wake up to failed posts.

**We cannot prevent third-party failures. We control how Kova responds to them.**

The goal is simple: **users never lose a post, never wonder what's happening, and can always recover without contacting support.**

Every failure mode below is evaluated against this principle.

---

## Failure Category 1 — OAuth Token Expiry & Revocation

### What Happens
OAuth tokens are time-limited credentials that allow Kova to post on a user's behalf. They expire on a schedule, or are instantly revoked when a user:
- Changes their Facebook/Instagram password
- Revokes Kova's access from within Meta Settings
- Deactivates their social account
- Their account gets suspended by the platform

When a token dies silently, every scheduled post for that platform fails. The user has no idea until they notice their profile hasn't been updated.

### Token Lifespan by Platform

| Platform | Token Type | Lifespan | Refresh Available? |
|---|---|---|---|
| Facebook | Long-lived user token | 60 days | No — must re-authenticate |
| Instagram | Shares Facebook token | 60 days | No — same flow |
| LinkedIn | Access token | 60 days | No — must re-authenticate |
| TikTok | Access token | 24 hours | Yes — 365-day refresh token |
| WhatsApp | System user token | Never expires | N/A — manual revocation only |

### The Risk
A user connects Facebook on Day 1. Posts are going great. Day 58 — the token is about to expire. If nothing prompts them to reconnect, Day 61 every post silently fails. The user has been paying Kova for 2 months and suddenly their social media stops. They cancel.

### Decision
**Implement a three-stage token health system:**

**Stage 1 — Warning (7 days before expiry):**
- Show a yellow warning banner on the platform card in `/platforms/`
- Send one email: "Your [Platform] connection expires in 7 days — reconnect to keep posts going"

**Stage 2 — Urgent (1 day before expiry):**
- Banner turns red
- Block the "Approve" button on any post destined for that platform — user cannot approve new posts until they reconnect
- Send a second email with the reconnect link

**Stage 3 — Expired:**
- Mark the social account as `token_expired` 
- All scheduled posts for that account are paused (not deleted)
- Large banner on Studio and Queue pages: "[Platform] disconnected — reconnect to resume your scheduled posts"
- Posts remain intact — nothing is lost

**For instant revocations (password change, manual revoke):**
- When a post publish attempt returns a 401 or OAuthError, immediately mark the account `token_expired`
- Notify user in-app and by email
- Pause all future posts for that account

**Token refresh where available:**
- TikTok: auto-refresh silently using the refresh token — user never sees this
- Facebook/LinkedIn: no refresh available, must prompt user

---

## Failure Category 2 — API Rate Limiting

### What Happens
Each platform has per-app and per-user API call limits. When Kova hits those limits, the platform returns a `429 Too Many Requests` error. If not handled, posts get dropped.

### Limits by Platform

| Platform | Limit Type | Limit | Scope |
|---|---|---|---|
| Facebook/Instagram | Calls per hour | 200 calls/hour | Per user token |
| LinkedIn | Calls per day | 500 calls/day | Per app per member |
| TikTok (sandbox) | Posts per day | 100 total | Per app globally |
| TikTok (production) | Posts per day | Negotiated | Per app globally |
| WhatsApp | Messages/day | Tier-based (starts at 1,000/day) | Per phone number |

### The Silver Lining
Facebook/Instagram rate limits are per user token, not per app. This means the limit scales naturally with users — each connected account has its own 200 calls/hour budget. This is good news for Kova's growth path.

LinkedIn and TikTok limits are per app, which means they become real constraints as Kova scales.

### Decision
**Implement retry with exponential backoff, never silently drop a post:**

- On first 429: wait 2 minutes, retry
- On second 429: wait 8 minutes, retry
- On third 429: wait 30 minutes, retry
- After three failures: mark post as `rate_limited`, notify user, let them manually reschedule

The post is **never deleted** on a rate limit failure. The user is told what happened and given a one-click reschedule option.

**For LinkedIn at scale (>500 users):**
- Implement a per-user daily call counter
- Prioritize publishing calls over analytics calls when approaching limits
- Defer analytics fetches to off-peak hours (3–6am local time)

**Monitoring:**
- Track rate limit hits in the analytics dashboard (admin view)
- Alert internally when any platform hits >50% of its limit in a 24-hour window
- This is an early warning that we need to optimize API call patterns before we hit the ceiling

---

## Failure Category 3 — Platform Outages

### What Happens
Meta goes down. It happened in October 2021 for 6 hours. LinkedIn has periodic degraded service windows. TikTok's API occasionally has silent failures where calls succeed (return 200) but posts never actually appear.

When a platform is down during a scheduled post window, the post simply doesn't go out.

### The Risk
A user has a perfectly crafted post scheduled for their peak time — Tuesday 9am. Meta is down from 8:45am to 10:15am. The post never publishes. If Kova doesn't retry, it's silently lost.

### Decision
**Implement a 4-hour outage hold window with automatic retry:**

- On any 5xx server error from a platform: mark post as `retrying`, not `failed`
- Retry every 30 minutes for up to 4 hours
- If the platform recovers within 4 hours: publish automatically, notify user with "Your post published at [time] — delayed due to a [Platform] outage"
- If 4 hours pass with no recovery: notify user, give them the option to reschedule or delete

**Display a platform status banner in Kova during detected outages:**
- Detected by: 3+ consecutive failures across different users on the same platform
- Banner: "[Platform] is experiencing issues. Your posts are being held and will publish automatically when [Platform] recovers."
- Remove banner once posts start succeeding again

**The 4-hour window is a business decision, not a technical one.** A post that's more than 4 hours late may be worse than not posting at all (time-sensitive content, breaking news angles). After 4 hours, the user decides — Kova doesn't decide for them.

---

## Failure Category 4 — Content Rejection (Platform Policy)

### What Happens
A post fails not because of Kova or platform downtime, but because the content violates platform policy. The platform returns an error but Kova shows "Post failed" with no explanation.

**Common causes:**
- Image fails Instagram's content moderation (even subtle violations)
- Caption too long by 1 character (platform limits sometimes change without notice)
- Using a banned hashtag (Instagram has a shadow-ban list)
- Facebook detects an "engagement bait" pattern (the word "comment below" triggers it)
- Instagram account not properly connected to a Facebook Page
- Wrong aspect ratio (portrait image in a format that requires square)
- Missing required fields for TikTok (title, privacy settings)
- WhatsApp template not approved

### The Risk
The user sees "Post failed" with no further information. They don't know if they should edit the post, reconnect the platform, or call support. This is a support ticket waiting to happen.

### Decision
**Build a platform error code translation layer:**

Every known platform error code gets a human-readable explanation and a suggested action. No raw API errors ever reach the user interface.

**Error message format (what users see):**
```
[Platform] rejected this post.
Reason: Instagram requires your account to be connected to a Facebook Page 
        to publish feed posts.
Fix it: Go to Instagram Settings → Account → Linked Accounts → Connect Facebook.
        Then come back and click "Retry".
```

**Implementation:** Create a central `error_translations.py` mapping known error codes to:
1. Plain English reason
2. Specific fix instructions for that error
3. Whether the post can be retried (some errors are permanent, some are fixable)

**For unknown errors:** Show the raw error code alongside: "This is an unusual error from [Platform]. If it keeps happening, contact support with error code [X]." Never show a blank failure.

---

## Failure Category 5 — Meta App Review Rejection or Suspension

### What Happens
This is the existential risk. Meta suspends your developer app — either for policy violations, inactivity, or a bad review decision. **Every single user's Facebook and Instagram connection stops working instantly.** All posts fail. All tokens are invalid.

This has happened to Buffer (2019), several Hootsuite integrations, and dozens of smaller players. It's not hypothetical.

### Why It Happens
- App policy violations (posting on behalf of users without explicit consent flows)
- Inactivity (Meta can restrict apps with low API call volume)
- Suspicious traffic patterns (too many connections in a short window)
- Failed app review (incorrect use case, missing privacy policy, bad demo video)
- Meta's fraud detection flagging the app

### Decision
**Four-layer protection strategy:**

**Layer 1 — Prevention (most important):**
- Every API call Kova makes is logged with: timestamp, user_id, platform, endpoint, purpose
- This creates an audit trail. If Meta audits us, we can prove every call was legitimate and user-initiated
- Never make API calls beyond what the user explicitly authorized in the OAuth flow
- Keep privacy policy and terms of service current and accurate
- Respond to any Meta platform support emails within 24 hours

**Layer 2 — Early detection:**
- Monitor the Meta API for `190` error codes (invalid/expired app token) across multiple users
- If 3+ users hit the same app-level error within 1 hour: alert internally immediately
- Don't wait for users to report it

**Layer 3 — Backup app:**
- Maintain a second Meta developer app, registered and configured but not actively used
- App credentials stored securely, disconnected from production
- If primary app is suspended: update `FACEBOOK_APP_ID` and `FACEBOOK_APP_SECRET` in Railway → redeploy → all users re-authenticate (painful but survivable in ~15 minutes)
- Document the switchover runbook so it can be executed under pressure

**Layer 4 — User communication:**
- If a Meta suspension occurs: email all affected users within 30 minutes explaining what happened, that their posts are safe, and what they need to do
- Never let users find out by noticing their profile hasn't been updated
- Template the email now so it doesn't need to be written in a crisis

---

## Failure Category 6 — Webhook Reliability

### What Happens
Meta and WhatsApp send webhooks to Kova for real-time events: incoming messages, comment notifications, mention alerts, post performance updates. If Kova's server takes more than 20 seconds to respond, Meta marks the webhook endpoint as failed and stops sending events. Kova loses real-time data.

### Decision
**Non-negotiable architecture rule: webhooks must return 200 within 1 second.**

- Webhook handler receives the payload → immediately returns `200 OK` → queues the payload for async processing
- Never do database writes, API calls, or any logic in the webhook handler itself
- This is already partially implemented but must be verified before launch

**Webhook health monitoring:**
- Log every webhook received with timestamp and type
- Alert internally if webhook volume drops to zero for more than 2 hours during business hours (may indicate Meta stopped sending)
- Periodically re-verify the webhook subscription (Meta requires re-verification after certain app changes)

---

## Failure Category 7 — App Credential Rotation

### What Happens
At some point, credentials need to be rotated: `FACEBOOK_APP_SECRET`, `LINKEDIN_CLIENT_SECRET`, etc. Done wrong, every user's connection breaks simultaneously.

### Decision
**Document the rotation runbook now, while the process is fresh:**

**Facebook App Secret rotation:**
1. Go to Meta Developer App → App Settings → Basic → Generate new App Secret
2. Do NOT delete the old secret yet
3. Add new secret to Railway as `FACEBOOK_APP_SECRET_NEW`
4. Deploy and test one connection (your own account)
5. If successful: rename `FACEBOOK_APP_SECRET_NEW` → `FACEBOOK_APP_SECRET`, remove old variable
6. Monitor for 30 minutes — watch for any 190 errors
7. If errors appear: roll back immediately (redeploy with old secret)

**LinkedIn Client Secret rotation:** Same pattern — test before cutting over.

**Rule:** Never rotate credentials on a Friday or before a weekend.

---

## Failure Category 8 — Silent Publishing Success (TikTok-Specific)

### What Happens
TikTok's API occasionally returns a 200 success response but the post never actually appears on the user's profile. The post is marked "Published" in Kova, the user thinks it's live, but nothing is there.

### Decision
**Implement a post-publish verification step for TikTok:**

- After a TikTok post publishes (200 response received): wait 2 minutes, then query the TikTok API to confirm the post exists
- If confirmed: mark as Published ✓
- If not found after 2 minutes: retry verification at 5 minutes, then 15 minutes
- If still not found at 15 minutes: mark as `verification_failed`, notify user that the post may not have published and they should check their TikTok profile directly

This is TikTok-specific because their API has a known delay between publish and the post appearing in their system.

---

## Implementation Plan

### Must-complete before first user goes live

| # | What | Why It Can't Wait |
|---|---|---|
| 1 | Token expiry detection + warning banners | First user connects, token expires in 60 days, posts fail — they cancel |
| 2 | Post failure notifications (in-app + email) | Silent failures are the #1 trust-killer |
| 3 | Error code translation layer | "Post failed" with no explanation generates support tickets |
| 4 | Retry with backoff on rate limits and 5xx errors | Posts should never be silently dropped |
| 5 | Webhook returns 200 immediately (async processing) | Meta stops sending webhooks to slow endpoints |
| 6 | Backup Meta app registered and switchover runbook documented | One suspension shouldn't end the product |

### Complete within first 30 days of live users

| # | What | Why It Can Wait |
|---|---|---|
| 7 | Platform outage detection banner | Rare enough that manual monitoring covers the first month |
| 8 | LinkedIn at-scale rate limit optimization | Won't hit LinkedIn limits until 500+ active users |
| 9 | TikTok post-publish verification | TikTok is lower priority than Facebook/Instagram/LinkedIn at launch |
| 10 | Credential rotation runbook | Document it, but unlikely to need it in month 1 |

### Before 1,000 users

| # | What |
|---|---|
| 11 | Per-platform API call analytics dashboard (admin view) |
| 12 | Automated outage detection (N consecutive cross-user failures = internal alert) |
| 13 | Rate limit headroom monitoring with alerting at 50% of ceiling |

---

## Platform-Specific Risk Ratings

| Platform | Suspension Risk | API Stability | Rate Limit Risk | Overall |
|---|---|---|---|---|
| Facebook | HIGH — strict app review, active enforcement | Medium — frequent v-number changes | LOW — per-user limits scale naturally | HIGH RISK |
| Instagram | HIGH — shares Facebook app, same risks | Medium | LOW | HIGH RISK |
| LinkedIn | LOW — less enforcement, more developer-friendly | High — stable API, rare breaking changes | MEDIUM — app-level limits | MEDIUM RISK |
| TikTok | MEDIUM — app review required, quota-based | LOW — API is immature, breaking changes common | HIGH — global app-level limits | HIGH RISK |
| WhatsApp | LOW — permanent system token | High — Meta-backed, stable | LOW — business tier limits | LOW RISK |

---

## The Non-Negotiable User Promise

Before any line of resilience code is written, this is the promise it's building toward:

> **A user's post will either publish successfully, or the user will know why it didn't, when it didn't, and exactly what to do about it — within 5 minutes of the failure occurring.**

Every implementation decision in this document is evaluated against this promise. If a solution lets Kova satisfy this promise, build it. If it doesn't, rethink it.

---

## Reference — Key Error Codes to Handle at Launch

### Facebook / Instagram
| Code | Meaning | User-Facing Message |
|---|---|---|
| 190 | Invalid/expired access token | Your Facebook connection has expired. Reconnect to resume posting. |
| 200 | Permissions error | Kova doesn't have permission to post to this Page. Reconnect and re-approve all permissions. |
| 100 | Invalid parameter (often image) | This post has an issue that Facebook couldn't accept. Edit the post and try again. |
| 368 | Temporarily blocked for policy | Facebook has temporarily restricted this account. Check your Facebook Page for any warnings. |
| 10 | App permissions | Kova's Facebook app needs additional permissions. Contact support. |
| 4 | App rate limit | Facebook's limit reached. Your post will retry automatically in 30 minutes. |
| 17 | User rate limit | Too many requests from this account. Your post will retry in 1 hour. |
| 32 | Page rate limit | Too many posts to this Page today. Your post will retry tomorrow. |
| 2500 | Instagram: not a business account | Instagram requires a Professional (Business or Creator) account to post via API. Switch your account type in Instagram Settings. |

### LinkedIn
| Code | Meaning | User-Facing Message |
|---|---|---|
| 401 | Unauthorized / token expired | Your LinkedIn connection has expired. Reconnect to resume posting. |
| 403 | Insufficient permissions | Kova doesn't have the right permissions for LinkedIn. Reconnect and approve all requested permissions. |
| 422 | Content policy violation | LinkedIn rejected this post's content. Edit the caption and try again. |
| 429 | Rate limit | LinkedIn's daily limit reached. Your post will retry tomorrow. |
| 500 | LinkedIn server error | LinkedIn is experiencing issues. Your post will retry automatically. |

### TikTok
| Code | Meaning | User-Facing Message |
|---|---|---|
| 10002 | Scope not authorized | Kova doesn't have permission to post videos. Reconnect TikTok and approve all permissions. |
| 10003 | Access token expired | Your TikTok connection has expired. Reconnect to resume posting. |
| 10004 | User not found | TikTok account not found. Reconnect your account. |
| 20001 | Video rejected | TikTok rejected this video. Check it doesn't violate TikTok's community guidelines. |

---

*This document is a living record of founder decisions. Update it when new failure modes are discovered or decisions change. Never implement a platform resilience feature that isn't documented here first.*
