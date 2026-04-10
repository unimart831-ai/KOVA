# ============================================================================
# KOVA AGENT — PLATFORM DEVELOPER ACCOUNT SETUP (COMPLETE GUIDE)
# ============================================================================
# One-time setup guide for the platform owner (you).
# This creates the OAuth "pipes" that let ALL your KOVA users connect platforms.
# Your clients never see any of this — they just click "Connect" and authorize.
#
# Last updated: June 2026 — 9 platforms
# Platforms: Facebook, Instagram, Twitter/X, LinkedIn, TikTok, YouTube,
#            Pinterest, Threads, Bluesky
#
# KOVA Capabilities per platform:
#   - Publish posts (text, images, video, carousels)
#   - Fetch engagement metrics (likes, comments, shares, impressions)
#   - Fetch and reply to comments
#   - Token refresh / session management
# ============================================================================


# ╔══════════════════════════════════════════════════════════════════════════╗
# ║  STEP 0: CREATE A KOVA BUSINESS EMAIL                                  ║
# ╚══════════════════════════════════════════════════════════════════════════╝
#
# All developer accounts below should use a SINGLE business email.
# Keep it separate from your personal email.
# ============================================================================

Recommended: kovaagents@gmail.com (or your-name@kovaagent.com)

Quick options:
  - Gmail: https://accounts.google.com/signup (free, instant)
  - Zoho Mail: https://www.zoho.com/mail/ (free tier, custom domain support)
  - Google Workspace: https://workspace.google.com/ ($6/mo, professional)

Save these credentials in a password manager (1Password, Bitwarden, etc.).


# ╔══════════════════════════════════════════════════════════════════════════╗
# ║  STEP 1: FACEBOOK + INSTAGRAM (One Meta App)                           ║
# ╚══════════════════════════════════════════════════════════════════════════╝
#
# Priority: DO THIS FIRST — one Meta app unlocks Facebook Pages AND Instagram.
# Meta now uses a USE-CASE-BASED app creation flow.
# Time: ~20 minutes (+ up to 48 hours if identity verification is triggered)
#
# Graph API version: v25.0 (latest as of June 2026)
# Docs: https://developers.facebook.com/docs/development
#
# KOVA uses:
#   - Publish to Facebook Pages (text, photos, videos)
#   - Publish to Instagram (single image, carousels, reels)
#   - Read Page/IG insights (reach, impressions, engagement)
#   - Fetch and reply to comments on both platforms
#   - Long-lived tokens (60-day validity, auto-refreshed)
# ============================================================================

## 1a. Create a Facebook Account & Register as Meta Developer

1. Go to https://www.facebook.com/r.php
2. Sign up with your Kova business email
3. Complete account setup — add a profile picture (Meta may flag faceless accounts)
4. Go to https://developers.facebook.com/
5. Click "Get Started" → follow the prompts to register as a developer
6. Verify your email and accept the Platform Terms

## 1b. Create a Meta App (Use-Case Flow)

1. Go to https://developers.facebook.com/apps/
2. Click "Create App"
3. Meta shows use cases — select the ones KOVA needs:

   USE CASES TO SELECT:
   ┌─────────────────────────────────────────────────────────┐
   │  ✅ Authenticate and request data from users with       │
   │     Facebook Login                                      │
   │  ✅ Access the pages API (for Facebook Page management)  │
   │  ✅ Access the Instagram API (for IG publishing/metrics) │
   └─────────────────────────────────────────────────────────┘

4. App name: "KOVA Agent" (or your preferred name)
5. App contact email: your Kova business email
6. Business portfolio: select yours, or create one at
   https://business.facebook.com/
7. Click "Create App"

## 1c. Configure Required Permissions

After app creation, go to: App Dashboard → Use Cases → Customize

For each use case, add these permissions:

FACEBOOK PAGES PERMISSIONS:
  - pages_manage_metadata   — Manage Page settings
  - pages_manage_posts      — Create, edit, delete Page posts
  - pages_read_engagement   — Read Page likes, comments, shares
  - pages_manage_engagement — Reply to comments, hide/delete comments
  - read_insights            — Read Page analytics (reach, impressions)

INSTAGRAM PERMISSIONS:
  - instagram_content_publish  — Publish photos, carousels, reels
  - instagram_manage_insights  — Read IG account analytics
  - instagram_manage_comments  — Read/reply to IG comments
  - instagram_manage_messages  — (Optional) IG DM access

FACEBOOK LOGIN PERMISSIONS:
  - email                    — User's email address
  - public_profile           — User's name and profile picture

Full scopes string KOVA sends (configured in instagram_facebook.py):
```
email,public_profile,pages_manage_metadata,pages_manage_posts,
pages_read_engagement,pages_manage_engagement,pages_messaging,
read_insights,instagram_content_publish,instagram_manage_insights,
instagram_manage_comments,instagram_manage_messages
```

## 1d. Configure Facebook Login for Business (config_id Approach)

Meta now uses "Login for Business" with a Login Configuration ID instead of
old-style scope-based login. This is MORE RELIABLE for app review.

1. Go to: App Dashboard → Facebook Login for Business
2. Click "Create Configuration"
3. Name it: "KOVA Platform Connect"
4. Under Login Flow → select the use-case permissions listed in 1c above
5. Save — you'll get a **Login Configuration ID** (numeric string)
6. Set this as your FACEBOOK_LOGIN_CONFIG_ID env var (see Step 1j)

If config_id is set, KOVA uses it for the OAuth flow automatically.
If not set, KOVA falls back to scope-based login (still works for development).

## 1e. Get Your App Credentials

1. Go to: App Dashboard → Settings → Basic
2. Copy:
   - **App ID** → this is your FACEBOOK_APP_ID
   - **App Secret** → click "Show" → this is your FACEBOOK_APP_SECRET
3. Under "App Domains" add: your production domain (e.g., kovaagent-production.up.railway.app)

## 1f. Set OAuth Redirect URIs

1. Go to: App Dashboard → Facebook Login for Business → Settings
   (or Facebook Login → Settings if using legacy)
2. Under "Valid OAuth Redirect URIs" add:
   - https://YOUR_DOMAIN/platforms/facebook/callback/
   - https://YOUR_DOMAIN/platforms/instagram/callback/
   - http://localhost:8000/platforms/facebook/callback/    (for local dev)
   - http://localhost:8000/platforms/instagram/callback/   (for local dev)
3. Save Changes

## 1g. Add Test Users & App Roles (Before App Review)

Until your app passes App Review, only people with app roles can use it.

1. Go to: App Dashboard → App Roles → Roles
2. Click "Add People" for each role:
   - **Admin**: your account (already added)
   - **Developer**: any co-developer accounts
   - **Tester**: any accounts you want to test with
3. Each person must ACCEPT the invitation from their Facebook account

For Instagram testing:
- The IG account must be a Professional account (Business or Creator)
- The IG account must be connected to a Facebook Page

## 1h. App Review (For Production / Public Use)

For public production use (non-test users), you need App Review:

1. Go to: App Dashboard → App Review → Permissions and Features
2. For each permission in 1c, click "Request"
3. You'll need to provide:
   - Platform Policy compliance checklist
   - A screen recording showing how your app uses each permission
   - A detailed description of the use case
4. Submit for review — typically takes 1-5 business days

IMPORTANT: Until App Review is approved, only users with app roles can connect.

## 1i. Token Lifecycle

- KOVA requests a short-lived token during OAuth → immediately exchanges it for
  a long-lived token (60-day validity)
- KOVA auto-refreshes long-lived tokens before expiry via `fb_exchange_token`
- User's Page Access Token is derived from the User token and is long-lived
- If a token expires, the user re-connects from KOVA's Platforms page

## 1j. Environment Variables (Railway / .env)

```
FACEBOOK_APP_ID=your_app_id_here
FACEBOOK_APP_SECRET=your_app_secret_here
FACEBOOK_LOGIN_CONFIG_ID=your_config_id_here    # From step 1d (optional but recommended)
```


# ╔══════════════════════════════════════════════════════════════════════════╗
# ║  STEP 2: TWITTER / X                                                   ║
# ╚══════════════════════════════════════════════════════════════════════════╝
#
# X API v2 now uses pay-per-usage pricing (credit-based).
# No more Free/Basic/Pro subscription tiers.
# Purchase credits, deducted per API request.
#
# Docs: https://docs.x.com/x-api/getting-started/about-x-api
# Auth: https://docs.x.com/resources/fundamentals/authentication/oauth-2-0
#
# KOVA uses:
#   - Post tweets (text, images up to 4, video)
#   - Post threads (multi-tweet chains)
#   - Read tweet metrics (likes, retweets, replies, impressions)
#   - Reply to mentions
#   - OAuth 2.0 with PKCE (refresh tokens, 2-hour access tokens)
# ============================================================================

## 2a. Create an X Developer Account

1. Go to https://console.x.com/ (formerly developer.twitter.com)
2. Sign in with your X account (create one at https://x.com if needed)
3. Complete the developer application:
   - Describe your use case: "Social media management platform that publishes
     posts, reads analytics, and manages engagement on behalf of authorized users"
   - Accept the Developer Agreement
4. Your account will be reviewed — usually approved within minutes to hours

## 2b. Purchase API Credits

X API v2 uses pay-per-usage pricing:
- No monthly subscriptions — you buy credits, deducted per request
- Same-resource requests within 24 hours are deduplicated (charged once)
- Monitor usage in the Developer Console

1. Go to: Console → Billing
2. Purchase credits (start with $5-10 for testing)

## 2c. Create a Project & App

1. In the Developer Console, go to Projects & Apps
2. Click "Create Project":
   - Project name: "KOVA Agent"
   - Use case: "Making a social media management tool"
3. Create an App within the project:
   - App name: "KOVA Agent App"

## 2d. Configure OAuth 2.0

1. Go to: Your App → Settings → User authentication settings → Edit
2. Enable **OAuth 2.0**
3. App type: **Web App** (this makes it a Confidential Client — MORE SECURE)
4. Callback URI / Redirect URL:
   - https://YOUR_DOMAIN/platforms/twitter/callback/
   - http://localhost:8000/platforms/twitter/callback/    (for local dev)
5. Website URL: https://YOUR_DOMAIN

## 2e. Get Your Credentials

1. Go to: Your App → Keys and Tokens
2. You need:
   - **Client ID** → TWITTER_CLIENT_ID
   - **Client Secret** → TWITTER_CLIENT_SECRET (only for Confidential Clients)
3. Also generate (for media upload via v1.1):
   - **API Key** → TWITTER_API_KEY
   - **API Key Secret** → TWITTER_API_SECRET

NOTE: KOVA uses OAuth 2.0 with PKCE for user auth, but media upload still
requires v1.1 endpoints which need API Key + Secret for signing.

## 2f. Required Scopes

KOVA requests these scopes during OAuth (configured in twitter.py):
```
tweet.read tweet.write users.read offline.access like.write like.read
```

Scope meanings:
- tweet.read     — Read tweets and timelines
- tweet.write    — Create tweets, retweets, replies
- users.read     — Read user profile info
- offline.access — Get refresh tokens (long-lived access)
- like.write     — Like/unlike tweets
- like.read      — Read liked tweets

Optional scopes you could add for future features:
- media.write     — Upload media
- follows.read    — Read follower/following lists
- follows.write   — Follow/unfollow users
- dm.read/write   — Direct messages
- bookmark.read/write — Bookmarks

## 2g. Token Lifecycle

- Access tokens expire after 2 hours
- KOVA auto-refreshes using the refresh token (offline.access scope)
- If refresh fails, user re-connects from KOVA's Platforms page

## 2h. Environment Variables

```
TWITTER_CLIENT_ID=your_client_id
TWITTER_CLIENT_SECRET=your_client_secret
TWITTER_API_KEY=your_api_key
TWITTER_API_SECRET=your_api_key_secret
```


# ╔══════════════════════════════════════════════════════════════════════════╗
# ║  STEP 3: LINKEDIN                                                      ║
# ╚══════════════════════════════════════════════════════════════════════════╝
#
# LinkedIn uses the Marketing Community Management API (Posts API).
# The old ugcPosts API has been deprecated — KOVA uses the new Posts API.
# API versioning: YYYYMM format (e.g., 202603)
# Docs: https://learn.microsoft.com/en-us/linkedin/marketing/
#
# KOVA uses:
#   - Publish posts (text, single image, multi-image up to 9, video, articles)
#   - Read post metrics (likes, comments, shares, impressions)
#   - Fetch and reply to comments
#   - Post as Person OR Organization (Company Page)
#   - OAuth 2.0 with refresh tokens
# ============================================================================

## 3a. Create a LinkedIn Company Page (Recommended)

A Company Page lets KOVA post on behalf of a brand, not just a personal profile.

1. Go to https://www.linkedin.com/company/setup/new/
2. Company name: "KOVA Agent" (or your brand)
3. Choose: Company (Small business)
4. Complete the page setup

## 3b. Create a LinkedIn Developer App

1. Go to https://www.linkedin.com/developers/apps/new
2. Fill in:
   - App name: "KOVA Agent"
   - LinkedIn Page: select your Company Page from 3a
   - App logo: upload your logo
   - Legal agreement: accept
3. Click "Create app"

## 3c. Request API Products

After creating the app, you need to add Products:

1. Go to: Your App → Products tab
2. Request access to:

   ┌─────────────────────────────────────────────────────────────────┐
   │  ✅ Share on LinkedIn                                           │
   │     → Grants: w_member_social (post as member)                  │
   │                                                                 │
   │  ✅ Sign In with LinkedIn using OpenID Connect                  │
   │     → Grants: openid, profile, email                            │
   │                                                                 │
   │  ✅ Advertising API (optional, for org posting)                  │
   │     → Grants: w_organization_social, r_organization_social      │
   │     → Lets KOVA post as your Company Page                       │
   └─────────────────────────────────────────────────────────────────┘

3. "Share on LinkedIn" is usually auto-approved
4. "Advertising API" requires a short application explaining your use case
   - Say: "Social media management tool that publishes branded content and
     reads engagement analytics for Company Pages on behalf of authorized admins"

## 3d. Verify Your Company Page

To post as an Organization, your LinkedIn developer app must be associated with
a verified Company Page, and the authenticated user must have one of these
Company Page roles:
- ADMINISTRATOR
- DIRECT_SPONSORED_CONTENT_POSTER
- CONTENT_ADMIN

## 3e. Configure OAuth 2.0

1. Go to: Your App → Auth tab
2. Under "OAuth 2.0 settings":
   - Redirect URLs:
     - https://YOUR_DOMAIN/platforms/linkedin/callback/
     - http://localhost:8000/platforms/linkedin/callback/
3. Note your:
   - **Client ID** → LINKEDIN_CLIENT_ID
   - **Client Secret** → LINKEDIN_CLIENT_SECRET

## 3f. Required Scopes

KOVA requests these scopes (configured in linkedin.py):

For personal posting:
```
openid profile w_member_social
```

For organization/Company Page posting:
```
openid profile w_member_social w_organization_social r_organization_social
```

Scope meanings:
- openid              — OpenID Connect (required for Sign In with LinkedIn)
- profile             — Read user's name, profile picture, headline
- w_member_social     — Post, comment, like as a member
- w_organization_social — Post, comment, like as an Organization
- r_organization_social — Read Organization posts, comments, likes

## 3g. LinkedIn API Versioning

LinkedIn APIs use versioned headers. KOVA sends:
```
Linkedin-Version: 202603
X-Restli-Protocol-Version: 2.0.0
```

## 3h. Content Types Supported

| Post Type    | Supported | Notes                                    |
|-------------|-----------|------------------------------------------|
| Text only   | ✅        | Simple commentary post                    |
| Single image| ✅        | Upload via Images API → Image URN         |
| Multi-image | ✅        | Up to 9 images via MultiImage API         |
| Video       | ✅        | Upload via Videos API (chunked upload)    |
| Article/Link| ✅        | Custom thumbnail, title, description      |
| Poll        | ✅        | Organic polls only                        |
| Carousel    | ❌        | Sponsored only — not available for organic|
| Document    | ✅        | PDF/slides via Documents API              |

## 3i. Token Lifecycle

- Access tokens expire after ~60 days
- KOVA uses refresh tokens to auto-renew
- LinkedIn refresh tokens are long-lived

## 3j. Environment Variables

```
LINKEDIN_CLIENT_ID=your_client_id
LINKEDIN_CLIENT_SECRET=your_client_secret
```


# ╔══════════════════════════════════════════════════════════════════════════╗
# ║  STEP 4: TIKTOK                                                        ║
# ╚══════════════════════════════════════════════════════════════════════════╝
#
# TikTok uses the Content Posting API for direct posting.
# Supports both video AND photo posting (photos are a newer addition).
# Docs: https://developers.tiktok.com/doc/content-posting-api-get-started/
#
# KOVA uses:
#   - Direct post videos (PULL_FROM_URL or FILE_UPLOAD with chunked upload)
#   - Direct post photos/carousels (up to 35 images via PULL_FROM_URL)
#   - Query creator info (privacy levels, interaction settings)
#   - Check publish status (async — polling via publish_id)
#   - OAuth 2.0 with refresh tokens
#
# IMPORTANT: Content from unaudited apps is restricted to PRIVATE visibility.
# You must pass TikTok's audit to post PUBLIC content.
# ============================================================================

## 4a. Create a TikTok Developer Account

1. Go to https://developers.tiktok.com/
2. Click "Log in" and sign in with your TikTok account
3. Fill out the developer registration form
4. Accept the Developer Terms of Service

## 4b. Create an App

1. Go to: Manage Apps → Create App (or "My Apps")
2. Fill in:
   - App name: "KOVA Agent"
   - Description: "Social media management platform for automated content publishing"
   - App icon: upload your logo
   - Category: Social Media Management

## 4c. Add Required Products

In your app dashboard, add these products:

1. **Login Kit** — for OAuth authentication
   - Scopes: user.info.basic
2. **Content Posting API** — for publishing content
   - Scopes: video.publish, video.list
   - ✅ Enable "Direct Post" configuration (CRITICAL — without this, content
     goes to user's inbox instead of posting directly)

To enable Direct Post:
1. Go to your app → Content Posting API settings
2. Toggle ON "Direct Post"
3. This allows KOVA to publish directly to a creator's profile

## 4d. Configure OAuth

1. Go to: Your App → Configuration
2. Add Redirect URIs:
   - https://YOUR_DOMAIN/platforms/tiktok/callback/
   - http://localhost:8000/platforms/tiktok/callback/
3. Note your:
   - **Client Key** → TIKTOK_CLIENT_KEY
   - **Client Secret** → TIKTOK_CLIENT_SECRET

## 4e. Required Scopes

KOVA requests (configured in tiktok.py):
```
user.info.basic,video.publish,video.list
```

Scope meanings:
- user.info.basic — Read user's display name, avatar, username
- video.publish   — Post videos and photos to user's TikTok
- video.list      — List user's published videos and check post status

## 4f. Domain/URL Verification (For PULL_FROM_URL)

If KOVA uploads media via URL (PULL_FROM_URL method), TikTok requires
domain verification:

1. Go to: Your App → Content Posting API → Domain Verification
2. Add your R2 public domain:
   - pub-e0b58c475fab4dfbb1e598be12846447.r2.dev (or your custom domain)
3. Verify via one of:
   - DNS TXT record
   - HTML file upload to root
   - Meta tag in <head>

## 4g. Submit App for Audit

CRITICAL: Unaudited apps post content as PRIVATE (only creator can see it).

1. Go to: Your App → Submit for Audit
2. Required materials:
   - Working demo URL or screen recording of your app
   - Proof of compliance with TikTok's Terms of Service
   - Description of how user content is managed
3. Submit at: https://developers.tiktok.com/application/content-posting-api
4. Audit review: typically 2-5 business days

## 4h. Privacy Level Options

When posting, KOVA can set these privacy levels:
- PUBLIC_TO_EVERYONE  — visible to everyone (requires audit-approved app)
- MUTUAL_FOLLOW_FRIENDS — only mutual followers
- FOLLOWER_OF_CREATOR — only followers
- SELF_ONLY — only the creator (private)

## 4i. Content Types Supported

| Post Type      | Method          | Notes                              |
|---------------|----------------|------------------------------------|
| Video (URL)   | PULL_FROM_URL  | Requires domain verification       |
| Video (upload)| FILE_UPLOAD    | Chunked upload (10 MB per chunk)   |
| Photo carousel| PULL_FROM_URL  | Up to 35 images, auto_add_music    |
| Text only     | ❌             | Not supported — media required      |

## 4j. Environment Variables

```
TIKTOK_CLIENT_KEY=your_client_key
TIKTOK_CLIENT_SECRET=your_client_secret
```


# ╔══════════════════════════════════════════════════════════════════════════╗
# ║  STEP 5: YOUTUBE                                                       ║
# ╚══════════════════════════════════════════════════════════════════════════╝
#
# YouTube uses the YouTube Data API v3 via Google Cloud Console.
# Default quota: 10,000 units/day (video upload = 100 units each).
# Docs: https://developers.google.com/youtube/v3/getting-started
#
# KOVA uses:
#   - Upload videos (resumable upload, supports Shorts)
#   - Read video metrics (views, likes, comments)
#   - Fetch and reply to comments
#   - OAuth 2.0 with refresh tokens (Google OAuth)
#
# NOTE: YouTube API does NOT support text-only posts or image posts.
#       All content must be video. For Shorts, video must be ≤60 seconds,
#       vertical (9:16), and titled with #Shorts.
# ============================================================================

## 5a. Create a Google Cloud Project

1. Go to https://console.cloud.google.com/
2. Click "Select a project" → "New Project"
3. Name: "KOVA Agent"
4. Organization: leave default or select yours
5. Click "Create"

## 5b. Enable YouTube Data API v3

1. Go to: APIs & Services → Library
2. Search for "YouTube Data API v3"
3. Click on it → click "Enable"

## 5c. Configure OAuth Consent Screen

1. Go to: APIs & Services → OAuth consent screen
2. User Type: "External" (so any Google account can authorize)
3. Fill in:
   - App name: "KOVA Agent"
   - User support email: your Kova email
   - App logo: upload your logo
   - Authorized domains: add YOUR_DOMAIN
   - Developer contact email: your Kova email
4. Scopes: add:
   - youtube.upload
   - youtube.readonly
   - youtube.force-ssl
5. Test users: add your Google/YouTube account email
6. Save and continue

## 5d. Create OAuth 2.0 Credentials

1. Go to: APIs & Services → Credentials
2. Click "Create Credentials" → "OAuth client ID"
3. Application type: "Web application"
4. Name: "KOVA Agent OAuth"
5. Authorized redirect URIs:
   - https://YOUR_DOMAIN/platforms/youtube/callback/
   - http://localhost:8000/platforms/youtube/callback/
6. Click "Create"
7. Copy:
   - **Client ID** → YOUTUBE_CLIENT_ID
   - **Client Secret** → YOUTUBE_CLIENT_SECRET

## 5e. Required Scopes

KOVA requests (configured in youtube.py):
```
https://www.googleapis.com/auth/youtube.upload
https://www.googleapis.com/auth/youtube.readonly
https://www.googleapis.com/auth/youtube.force-ssl
```

Scope meanings:
- youtube.upload    — Upload videos to the user's channel
- youtube.readonly  — Read channel info, video details, metrics
- youtube.force-ssl — Read/write comments (requires SSL)

## 5f. Quota Management

YouTube Data API has a daily quota of 10,000 units (default):

| Operation           | Cost (units) |
|---------------------|-------------|
| Read (list)         | 1           |
| Write (update)      | 50          |
| Search              | 100         |
| Video upload        | 100         |

With 10,000 units/day you can:
- Upload ~100 videos/day
- Read ~10,000 video details/day
- Or a mix of operations

If you need more, apply for quota extension:
https://support.google.com/youtube/contact/yt_api_form

## 5g. Consent Screen Verification (For Production)

While in "Testing" mode, only test users (up to 100) can authorize.
For production:

1. Go to: OAuth consent screen
2. Click "Publish App"
3. Google will review your app — requires:
   - Privacy policy URL
   - Terms of service URL
   - Demonstration of OAuth scope usage
4. Review takes 1-4 weeks for sensitive scopes (youtube.upload is sensitive)

## 5h. IMPORTANT: Service Account Limitation

YouTube Data API does NOT support service accounts for user data access.
You MUST use OAuth 2.0 with user consent. Service account requests will
return a `NoLinkedYouTubeAccount` error.

## 5i. Environment Variables

```
YOUTUBE_CLIENT_ID=your_client_id
YOUTUBE_CLIENT_SECRET=your_client_secret
```


# ╔══════════════════════════════════════════════════════════════════════════╗
# ║  STEP 6: PINTEREST                                                     ║
# ╚══════════════════════════════════════════════════════════════════════════╝
#
# Pinterest uses API v5 with an access tier system.
# Start with Trial access, then upgrade to Standard for production.
# Docs: https://developers.pinterest.com/docs/getting-started/set-up-app/
#
# KOVA uses:
#   - Create Pins (image required — no text-only posts)
#   - Read Pin analytics (impressions, saves, clicks — 30-day window)
#   - Read boards list (auto-selects first board if none specified)
#   - OAuth 2.0 with refresh tokens
#
# NOTE: Pinterest requires an IMAGE for every Pin. Text-only is not supported.
# ============================================================================

## 6a. Create a Pinterest Business Account

1. Go to https://www.pinterest.com/business/create/
   (or convert existing: https://help.pinterest.com/business/article/create-an-advertiser-account)
2. Sign up with your Kova business email
3. Complete business profile setup
4. Verify your email address

## 6b. Register as a Pinterest Developer

1. Go to https://developers.pinterest.com/
2. Click through to accept the Developer Terms of Service
3. Go to "My apps" → https://developers.pinterest.com/apps/

## 6c. Create an App

1. Click "Connect app" (or "Create app")
2. Fill in the application form:
   - App name: "KOVA Agent"
   - Description: "Social media management tool for Pinterest content publishing and analytics"
   - Website URL: https://YOUR_DOMAIN
3. Submit for Trial access review
4. Wait for approval email (reviewed each business day, usually 1-2 days)

## 6d. Access Tiers

Pinterest has an access tier system:

| Tier     | Rate Limit        | How to Get               |
|----------|-------------------|--------------------------|
| Trial    | 10 calls/min      | Auto after app approval  |
| Standard | 1000 calls/min    | Apply after building app |

To upgrade to Standard:
1. Go to: My apps → your app
2. Click "Apply for Standard access"
3. Provide:
   - Working demo or screenshot of integration
   - Description of how Pinterest API is used
4. Review: 1-5 business days

## 6e. Configure OAuth

1. Go to: My apps → your app → "Manage"
2. Navigate to the "Configure" tab
3. Add Redirect URIs:
   - https://YOUR_DOMAIN/platforms/pinterest/callback/
   - http://localhost:8000/platforms/pinterest/callback/
4. Note your:
   - **App ID** → PINTEREST_APP_ID
   - **App Secret** → PINTEREST_APP_SECRET

IMPORTANT: Redirect URIs must be an EXACT match (including trailing slashes).
Pinterest does not follow secondary redirects.

## 6f. Required Scopes

KOVA requests (configured in pinterest.py):
```
boards:read,boards:write,pins:read,pins:write,user_accounts:read
```

Scope meanings:
- boards:read        — Read user's boards
- boards:write       — Create/update boards
- pins:read          — Read pins and pin analytics
- pins:write         — Create/update/delete pins
- user_accounts:read — Read user profile info

## 6g. Quick Testing with Product Token

Pinterest offers a 24-hour test token for quick API testing (no OAuth needed):

1. Go to: My apps → your app
2. Look for "Generate token" or product token option
3. Use it to test API calls before setting up full OAuth

## 6h. Environment Variables

```
PINTEREST_APP_ID=your_app_id
PINTEREST_APP_SECRET=your_app_secret
```


# ╔══════════════════════════════════════════════════════════════════════════╗
# ║  STEP 7: THREADS (Meta App — Separate Credentials from FB/IG)          ║
# ╚══════════════════════════════════════════════════════════════════════════╝
#
# Threads API uses the Meta developer ecosystem but has its OWN OAuth flow
# and its OWN app credentials (separate from Facebook/Instagram).
#
# Docs: https://developers.facebook.com/docs/threads/get-started
#
# KOVA uses:
#   - Publish text posts, single images, carousels (up to 10 items)
#   - Read post insights (likes, replies, reposts, quotes, views)
#   - Fetch and reply to thread replies
#   - Long-lived tokens (60-day validity, refreshable)
#
# NOTE: Threads has its own OAuth flow at threads.net domain, separate
#       from Facebook/Instagram login flow.
# ============================================================================

## 7a. Add Threads Use Case to Your Meta App

You have two options:
A) Add the Threads use case to your existing KOVA Meta app (from Step 1)
B) Create a separate Meta app with the Threads use case

For option A (recommended):
1. Go to: https://developers.facebook.com/apps/YOUR_APP_ID/
2. Go to: Use Cases → Add Use Case
3. Select "Access the Threads API"

For option B:
1. Go to: https://developers.facebook.com/apps/
2. Create App → select "Threads" use case
3. Complete app setup

IMPORTANT: When you add the Threads use case, Meta generates a SEPARATE set of
credentials:
- A **Threads App ID** + **Threads App Secret** (USE THESE for Threads)
- These are DIFFERENT from your Facebook App ID/Secret!

## 7b. Get Threads Credentials

1. Go to: App Dashboard → Settings → Basic
2. Look for the **Threads App ID** and **Threads App Secret**
   (check the Threads-specific section — NOT the general app section)
3. Copy:
   - **Threads App ID** → THREADS_APP_ID
   - **Threads App Secret** → THREADS_APP_SECRET

## 7c. Configure Threads OAuth

Threads uses its own OAuth authorization endpoints (NOT Facebook's):

Authorization URL: https://threads.net/oauth/authorize
Token Exchange URL: https://graph.threads.net/oauth/access_token

1. Go to: App Dashboard → Threads API → Settings
2. Add Redirect URIs:
   - https://YOUR_DOMAIN/platforms/threads/callback/
   - http://localhost:8000/platforms/threads/callback/

## 7d. Required Scopes

KOVA requests (configured in threads.py):
```
threads_basic,threads_content_publish,threads_manage_insights,
threads_manage_replies,threads_read_replies
```

Scope meanings:
- threads_basic            — Required for ALL Threads endpoints (profile, media)
- threads_content_publish  — Create posts (text, images, carousels)
- threads_manage_insights  — Read post analytics (views, likes, replies)
- threads_manage_replies   — Reply to threads, hide/unhide replies
- threads_read_replies     — Read thread replies and conversation threads

## 7e. Add Threads Testers (Before App Review)

Threads has its own tester role system:

1. Go to: App Dashboard → App Roles → Roles
2. Click "Add People" → select "Threads Tester"
3. Enter the Threads username/profile of the tester
4. The tester must ACCEPT the invitation:
   - Go to: https://www.threads.net/settings/account
   - Find "Website permissions" section
   - Accept the pending invitation

## 7f. Token Lifecycle

- Threads tokens are separate from Facebook/Instagram tokens
- Short-lived token: 1 hour validity
- Long-lived token: 60 days (exchanged via `th_exchange_token`)
- Refresh: long-lived tokens can be refreshed via `th_refresh_token` grant
- PUBLIC profiles: tokens can be refreshed indefinitely
- PRIVATE profiles: tokens cannot be extended — user must re-authorize

## 7g. Publishing Flow

Threads publishing is a two-step process:
1. Create a media container (with content, type, and media URLs)
2. Wait for container status = FINISHED
3. Publish the container

KOVA handles this automatically. Container processing typically takes 1-5 seconds.

## 7h. App Review for Threads

Same process as Facebook App Review:
1. Go to: App Dashboard → App Review → Permissions
2. Request each Threads permission
3. Provide screen recordings and use case descriptions
4. Submit for review

## 7i. Environment Variables

```
THREADS_APP_ID=your_threads_app_id
THREADS_APP_SECRET=your_threads_app_secret
```

NOTE: These are DIFFERENT from your FACEBOOK_APP_ID/FACEBOOK_APP_SECRET!


# ╔══════════════════════════════════════════════════════════════════════════╗
# ║  STEP 8: BLUESKY (AT Protocol — No Developer Account Required)         ║
# ╚══════════════════════════════════════════════════════════════════════════╝
#
# Bluesky uses the AT Protocol — fundamentally different from other platforms.
# NO DEVELOPER ACCOUNT, NO APP REGISTRATION, NO OAUTH needed.
# Users connect via their Bluesky handle + an App Password.
#
# Docs: https://docs.bsky.app/docs/get-started
# AT Protocol spec: https://atproto.com/specs
#
# KOVA uses:
#   - Publish text posts (300 grapheme char limit)
#   - Publish posts with images (up to 4 images)
#   - Auto-parse rich text (URLs → links, @mentions, #hashtags → facets)
#   - Read post metrics (likes, replies, reposts, quotes)
#   - Fetch notification mentions
#   - AT Protocol session management (accessJwt/refreshJwt)
#
# NOTE: Bluesky now supports OAuth (2026), but KOVA currently uses the
#       simpler App Password approach. OAuth can be added later for
#       enhanced security in a multi-user context.
# ============================================================================

## 8a. No Developer Setup Required!

Key advantages of Bluesky's AT Protocol:
- ✅ No developer portal registration
- ✅ No app creation or review process
- ✅ No OAuth redirect URLs to configure
- ✅ No API keys, client IDs, or secrets needed
- ✅ Works immediately — no waiting for approval
- ✅ Fully decentralized — works with any AT Protocol PDS server
- ✅ Free, no API quotas or rate limit purchases

## 8b. Create a Bluesky Account (For Your Brand)

1. Go to https://bsky.app/
2. Click "Create Account"
3. Choose your handle: @yourbrand.bsky.social
4. Complete profile setup (avatar, display name, bio)

Custom domain handle (optional):
- You can set your handle to @yourdomain.com
- Verify via DNS TXT record: _atproto.yourdomain.com → did=did:plc:xxxxx
- This adds legitimacy to your brand

## 8c. Generate an App Password

App Passwords are separate from your login password and can be revoked
independently without affecting your main account.

1. Go to: https://bsky.app/settings/app-passwords
2. Click "Add App Password"
3. Name it: "KOVA Agent"
4. Copy the generated password (you'll only see it once!)
5. This is what the user enters when connecting Bluesky in KOVA

## 8d. How Users Connect in KOVA

When a KOVA user connects Bluesky:
1. They enter their Bluesky handle (e.g., user.bsky.social)
2. They enter their App Password (NOT their login password)
3. KOVA creates a session: `com.atproto.server.createSession`
4. KOVA stores: accessJwt (short-lived) + refreshJwt (long-lived)
5. accessJwt used for API calls; refreshed via `com.atproto.server.refreshSession`

## 8e. AT Protocol Key APIs

API base: https://bsky.social/xrpc/
(or user's custom PDS URL if they self-host)

| Method | Purpose |
|--------|---------|
| com.atproto.server.createSession  | Login with handle + app password |
| com.atproto.server.refreshSession | Refresh expired access token     |
| com.atproto.repo.createRecord     | Create a post (or any record)    |
| com.atproto.repo.uploadBlob       | Upload image/media blobs         |
| app.bsky.feed.getPostThread       | Get post with replies            |
| app.bsky.notification.listNotifications | Fetch mentions/replies   |

## 8f. Content Capabilities

| Feature        | Supported | Notes                                  |
|---------------|-----------|----------------------------------------|
| Text posts    | ✅        | Up to 300 graphemes                     |
| Images        | ✅        | Up to 4 images per post                 |
| Rich text     | ✅        | URLs, @mentions, #hashtags auto-linked  |
| Video         | ❌        | Not yet supported by KOVA               |
| Carousels     | ❌        | Not a native Bluesky concept            |

## 8g. Bluesky OAuth (Future Enhancement)

Bluesky now supports full OAuth 2.0 via the AT Protocol:
- Requires: PKCE + PAR (Pushed Authorization Requests) + DPoP
- Client metadata published as JSON at a public URL
- More complex but more secure for multi-user SaaS platforms

When KOVA is ready to upgrade:
1. Host client metadata at: https://YOUR_DOMAIN/oauth/client-metadata.json
2. Implement atproto OAuth flow (PKCE + PAR + DPoP)
3. Required scope: "atproto" (plus optional "transition:generic")

For now, App Passwords are perfectly adequate for KOVA.

## 8h. Environment Variables

No platform-level env vars needed. Each user provides:
- Handle (e.g., user.bsky.social)
- App Password (generated per-user from their Bluesky settings)

These are stored securely in the user's PlatformAccount record in KOVA.


# ╔══════════════════════════════════════════════════════════════════════════╗
# ║  ENVIRONMENT VARIABLES REFERENCE (All Platforms)                        ║
# ╚══════════════════════════════════════════════════════════════════════════╝
#
# Add these to your Railway service variables or local .env file.
# NEVER commit these to git — they should be in .gitignore.
# ============================================================================

```
# --- Facebook / Instagram (Meta) ---
FACEBOOK_APP_ID=
FACEBOOK_APP_SECRET=
FACEBOOK_LOGIN_CONFIG_ID=         # Optional: Login for Business config ID

# --- Twitter / X ---
TWITTER_CLIENT_ID=
TWITTER_CLIENT_SECRET=
TWITTER_API_KEY=                  # v1.1 API key (for media upload)
TWITTER_API_SECRET=               # v1.1 API secret (for media upload)

# --- LinkedIn ---
LINKEDIN_CLIENT_ID=
LINKEDIN_CLIENT_SECRET=

# --- TikTok ---
TIKTOK_CLIENT_KEY=
TIKTOK_CLIENT_SECRET=

# --- YouTube (Google Cloud) ---
YOUTUBE_CLIENT_ID=
YOUTUBE_CLIENT_SECRET=

# --- Pinterest ---
PINTEREST_APP_ID=
PINTEREST_APP_SECRET=

# --- Threads (Meta — DIFFERENT credentials from FB/IG!) ---
THREADS_APP_ID=
THREADS_APP_SECRET=

# --- Bluesky ---
# No platform-level vars — each user provides handle + app password
```


# ╔══════════════════════════════════════════════════════════════════════════╗
# ║  PLATFORM CAPABILITIES MATRIX                                          ║
# ╚══════════════════════════════════════════════════════════════════════════╝

| Platform   | Text | Image | Multi-Image | Video | Carousel | Metrics | Comments | Reply |
|------------|------|-------|-------------|-------|----------|---------|----------|-------|
| Facebook   | ✅   | ✅    | ✅          | ✅    | ❌       | ✅      | ✅       | ✅    |
| Instagram  | ❌   | ✅    | ✅          | ✅    | ✅       | ✅      | ✅       | ✅    |
| Twitter/X  | ✅   | ✅    | ✅ (up to 4)| ✅    | ❌       | ✅      | ✅       | ✅    |
| LinkedIn   | ✅   | ✅    | ✅ (up to 9)| ✅    | ❌*      | ✅      | ✅       | ✅    |
| TikTok     | ❌   | ✅    | ✅ (up to 35)| ✅   | ✅       | 🔄**   | ❌       | ❌    |
| YouTube    | ❌   | ❌    | ❌          | ✅    | ❌       | ✅      | ✅       | ✅    |
| Pinterest  | ❌   | ✅    | ❌          | ❌    | ❌       | ✅      | ❌       | ❌    |
| Threads    | ✅   | ✅    | ✅ (up to 10)| ❌   | ✅       | ✅      | ✅       | ❌    |
| Bluesky    | ✅   | ✅    | ✅ (up to 4)| ❌    | ❌       | ✅      | ✅       | ❌    |

Legend:
  ❌* LinkedIn carousels are sponsored-only (not available for organic posts)
  🔄** TikTok metrics use async polling via publish_id (status checks)

Auth method summary:
| Platform         | Auth Type                | Token Validity    | Auto-Refresh |
|-----------------|--------------------------|-------------------|--------------|
| Facebook/IG     | OAuth 2.0 + config_id    | 60 days           | ✅ Exchange   |
| Twitter/X       | OAuth 2.0 + PKCE         | 2 hours           | ✅ Refresh    |
| LinkedIn        | OAuth 2.0                | ~60 days          | ✅ Refresh    |
| TikTok          | OAuth 2.0                | Varies            | ✅ Refresh    |
| YouTube         | Google OAuth 2.0         | 1 hour            | ✅ Refresh    |
| Pinterest       | OAuth 2.0                | Varies            | ✅ Refresh    |
| Threads         | OAuth 2.0 (Meta)         | 60 days           | ✅ Exchange   |
| Bluesky         | AT Protocol (App PW)     | Minutes (JWT)     | ✅ Session    |


# ╔══════════════════════════════════════════════════════════════════════════╗
# ║  RECOMMENDED SETUP ORDER                                                ║
# ╚══════════════════════════════════════════════════════════════════════════╝

Priority order (based on user base, ROI, and ease of setup):

1. 🔵 Facebook + Instagram (Step 1) — Highest ROI, one app covers both
2. 🐦 Twitter/X (Step 2) — Fast setup, pay-per-use credits
3. 💼 LinkedIn (Step 3) — B2B essential, straightforward
4. 🌀 Threads (Step 7) — Uses same Meta ecosystem, growing fast
5. 🦋 Bluesky (Step 8) — Zero setup, works immediately
6. 📌 Pinterest (Step 6) — Niche but valuable for visual/e-commerce brands
7. 🎵 TikTok (Step 4) — Requires audit for public posts, but massive reach
8. 📺 YouTube (Step 5) — Video-only, Google Cloud + consent screen verification


# ╔══════════════════════════════════════════════════════════════════════════╗
# ║  TROUBLESHOOTING                                                        ║
# ╚══════════════════════════════════════════════════════════════════════════╝

## Token Expired / User Disconnected
- Check Railway logs for "token expired" or "401" errors
- User re-connects from KOVA's Platforms page (Settings → Platforms)
- FB/IG/Threads: 60-day tokens, KOVA auto-refreshes before expiry
- Twitter: 2-hour access tokens, refresh token auto-renews
- YouTube: 1-hour tokens, refresh token auto-renews

## "App Not Authorized" / Permission Denied
- Check that all required scopes are enabled in the platform developer console
- Meta: check that App Review is completed for each permission
- TikTok: check that the audit is approved for public posting
- YouTube: check that OAuth consent screen is published (not "Testing" mode)

## Redirect URI Mismatch
- Callback URL in developer app MUST exactly match what KOVA sends
- Check for trailing slashes: /callback/ ≠ /callback
- Check http vs https: production must use https
- Check domain: must match your Railway/production domain exactly

## Media Upload Failures
- Ensure R2/storage URLs are publicly accessible
- TikTok: domain must be verified for PULL_FROM_URL uploads
- Pinterest: image is REQUIRED — text-only pins fail
- YouTube: video is REQUIRED — text/image posts fail
- Bluesky: images capped at 4 per post, text at 300 graphemes

## Rate Limits
| Platform         | Key Limits                                     |
|-----------------|------------------------------------------------|
| Facebook/IG     | ~200 calls/user/hour (Graph API)               |
| Twitter/X       | Pay-per-usage (credit-based, no hard limit)    |
| LinkedIn        | ~100-300 calls/day for posting endpoints        |
| TikTok          | Varies — check app dashboard                   |
| YouTube         | 10,000 quota units/day (default)               |
| Pinterest       | 10/min (Trial) or 1000/min (Standard)          |
| Threads         | Same as Meta Graph API limits                  |
| Bluesky         | Generous — no hard purchase required            |

## Missing Environment Variables
- Platform shows "Configuration Error" → check Railway env vars
- Missing vars = KOVA can't initiate OAuth for that platform
- Bluesky exception: no platform-level env vars needed
- Use Railway dashboard → Variables tab to add/edit

## Common Mistakes
1. Using Facebook App ID/Secret for Threads (they're different!)
2. Forgetting to enable "Direct Post" on TikTok (content goes to inbox)
3. Not adding test users/roles before App Review approval
4. Using http:// redirect URI in production (must be https://)
5. LinkedIn: not requesting "Advertising API" product for org posting
6. YouTube: trying to use Service Account instead of OAuth 2.0
