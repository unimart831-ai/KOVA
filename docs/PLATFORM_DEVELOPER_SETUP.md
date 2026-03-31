# ============================================================================
# KOVA AGENT — PLATFORM DEVELOPER ACCOUNT SETUP
# ============================================================================
# One-time setup guide for the platform owner (you).
# This creates the OAuth "pipes" that let ALL your users connect platforms.
# Your clients never see any of this — they just click "Connect" and authorize.
#
# Last updated: April 2026 — 9 platforms (FB, IG, Twitter, LinkedIn, TikTok, YouTube, Pinterest, Threads, Bluesky)
# ============================================================================


# STEP 0: CREATE A KOVA BUSINESS EMAIL
# ============================================================================
# All developer accounts below will use this email.
# Keep it separate from your personal email.
# ============================================================================

Recommended: kovaagent.ai@gmail.com (or your-name@kovaagent.com)

Quick options:
  - Gmail: https://accounts.google.com/signup (free, instant)
  - Zoho Mail: https://www.zoho.com/mail/ (free tier, custom domain support)
  - Google Workspace: https://workspace.google.com/ ($6/mo, professional)

Save these credentials in a password manager (1Password, Bitwarden, etc.).


# ============================================================================
# STEP 1: FACEBOOK + INSTAGRAM + WHATSAPP (one Meta app)
# ============================================================================
# Priority: DO THIS FIRST — one Meta app unlocks Facebook Pages, Instagram,
#           and WhatsApp. Meta now uses a USE-CASE-BASED app creation flow.
# Time: ~20 minutes (+ up to 48 hours if identity verification is triggered)
# Docs: https://developers.facebook.com/docs/development
# ============================================================================

## 1a. Create a Facebook Account & Register as Meta Developer

1. Go to https://www.facebook.com/r.php
2. Sign up with your Kova business email
3. Use your real name (Facebook requires it, can get banned otherwise)
4. Verify email + phone number when prompted

Then register as a developer:

1. Go to https://developers.facebook.com/async/registration
   (or visit https://developers.facebook.com/ and click "Get Started")
2. Click Next to agree to Meta Platform Terms and Developer Policies
3. Verify your phone number and email (confirmation code sent to both)
4. Select your occupation (e.g., "Developer")

Docs: https://developers.facebook.com/docs/development/register

## 1b. Create a Facebook Page

Required before your app can manage Pages on behalf of users.

1. Log into the new Facebook account
2. Go to https://www.facebook.com/pages/create
3. Page name: Kova Agent
4. Category: Software or Technology
5. Add a profile picture (Kova logo) and cover image
6. Publish the page

## 1c. Create the Developer App (Use-Case-Based)

Meta no longer uses "App type" (Business, Consumer, etc.).
Apps are now created by selecting USE CASES that define what your app can do.

1. Go to https://developers.facebook.com/apps/creation/
2. Enter app details:
   - App name: Kova Agent
   - Contact email: your Kova business email
3. Click Next

4. Select these USE CASES (you need all three for Kova):

   ┌─────────────────────────────────────────────────────────────┐
   │ USE CASE                              │ WHAT IT UNLOCKS     │
   ├─────────────────────────────────────────────────────────────┤
   │ Manage everything on your Page        │ Facebook Pages API  │
   │ Manage messaging & content on IG      │ Instagram API       │
   │ Connect with customers through WA     │ WhatsApp Cloud API  │
   └─────────────────────────────────────────────────────────────┘

   Note: Some use cases are incompatible with each other — greyed-out ones
   can't be added. The three above are compatible.
   Note: Facebook Login for Business and Webhooks may be auto-added.
   Note: Use cases CANNOT be removed after creation — only new ones added.

5. Click Next

6. Connect a Business Portfolio (or create one):
   - Option A: Select an existing verified business portfolio
   - Option B: Select an unverified business portfolio
   - Option C: Create a business portfolio (enter your business info)
   - Option D: "I don't want to connect a business portfolio yet"
   Note: WhatsApp use case REQUIRES a business portfolio.

7. Click Next → Review requirements → Click "Go to dashboard"

Docs: https://developers.facebook.com/docs/development/create-an-app

## 1d. Customize Use Cases & Permissions

After creating the app, customize each use case from the App Dashboard.

Go to: App Dashboard → Use Cases → click "Customize" on each use case.

### For "Manage everything on your Page":
Required permissions (auto-added, can't remove):
  - business_management
  - pages_show_list
  - public_profile

Add these optional permissions (click "Add" for each):
  - pages_manage_posts          ← publish posts to Pages
  - pages_read_engagement       ← read likes, comments, shares
  - pages_read_user_content     ← read user posts on your Page
  - pages_manage_engagement     ← respond to comments
  - pages_manage_metadata       ← manage Page settings
  - read_insights               ← Page analytics

Docs: https://developers.facebook.com/docs/pages-api/

### For "Manage messaging & content on Instagram":
Required permissions (auto-added):
  - public_profile

Add these optional permissions:
  - instagram_basic                       ← read profile info
  - instagram_business_basic              ← business account data
  - instagram_content_publish             ← publish posts
  - instagram_business_content_publish    ← business content publishing
  - instagram_manage_comments             ← moderate comments
  - instagram_manage_insights             ← analytics
  - instagram_manage_messages             ← DMs (if needed)
  - pages_show_list                       ← required for FB-linked IG accounts
  - pages_read_engagement                 ← read Page engagement

Note: Instagram accounts must be Business or Creator type AND linked to a
Facebook Page for the Facebook Login flow. Alternatively, use Instagram Login
(Business Login for Instagram) which doesn't require a FB Page link.

Docs: https://developers.facebook.com/docs/instagram-platform/

### For "Connect with customers through WhatsApp":
Required permissions (auto-added):
  - whatsapp_business_messaging
  - whatsapp_business_management
  - public_profile

Optional:
  - business_management
  - whatsapp_business_manage_events

Note: WhatsApp requires a verified Business Portfolio. You'll set up a
WhatsApp Business Account and register a phone number in the App Dashboard.

Docs: https://developers.facebook.com/docs/whatsapp/cloud-api/get-started

## 1e. Get Your Credentials

1. Go to App Dashboard → App Settings → Basic
2. Copy the App ID → this is FACEBOOK_APP_ID
3. Click "Show" next to App Secret → this is FACEBOOK_APP_SECRET

These same credentials are used for Facebook Pages, Instagram, AND WhatsApp.

## 1f. Configure OAuth Redirect URIs

Go to App Dashboard → Use Cases → find the use case with Facebook Login for
Business → click "Customize" → find Facebook Login for Business → Settings.

Under "Valid OAuth Redirect URIs", add ALL of these:

  Production:
    https://kovaagent-production.up.railway.app/platforms/callback/facebook/
    https://kovaagent-production.up.railway.app/platforms/callback/instagram/

  Local development:
    http://localhost:8000/platforms/callback/facebook/
    http://localhost:8000/platforms/callback/instagram/

Important: URIs must match EXACTLY — including trailing slashes and protocol
(https vs http). Mismatches cause "Redirect URI mismatch" errors.

## 1g. App Roles (for testing in Development Mode)

While your app is in Development Mode, only people with a role on the app
(or on the connected business portfolio) can use OAuth.

1. Go to App Dashboard → App Roles → Roles
2. Click "Add People"
3. Add yourself and any test users by their Facebook account

You do NOT need App Review to test with users who have a role on your app.

## 1h. WhatsApp-Specific Setup (if using WhatsApp)

1. Go to App Dashboard → WhatsApp → Getting Started
2. You'll get a temporary test phone number and access token
3. To use your own number:
   - Register a phone number under your WhatsApp Business Account
   - The number must NOT be registered on WhatsApp consumer app
4. Set Railway env vars (see 1i below)

## 1i. Set Railway Environment Variables

  FACEBOOK_APP_ID=123456789012345
  FACEBOOK_APP_SECRET=abc123def456ghi789...

  # WhatsApp (optional — only if using WhatsApp use case)
  WHATSAPP_TOKEN=your_permanent_access_token
  WHATSAPP_PHONE_NUMBER_ID=your_phone_number_id

## 1j. Verify It Works

1. Start your dev server (or go to production URL)
2. Go to /platforms/ → Click "Connect" on Facebook
3. Should redirect to Facebook → authorize → redirect back → Connected!
4. Repeat for Instagram
5. For WhatsApp: test sending a message via the WhatsApp Getting Started panel

## 1k. App Review (When Ready for Public Launch)

While in Development Mode, only people with roles on your app can use OAuth.
For public access, submit each permission for App Review:

1. Go to App Dashboard → App Review → Permissions and Features
2. For each permission, provide:
   - Screenshots showing how your app uses the permission
   - A screencast (video walkthrough) demonstrating the user flow
   - A clear description of why your app needs the permission
3. Facebook reviews typically take 1-5 business days

You also need to maintain data access — Meta may require periodic recertification.
Docs: https://developers.facebook.com/docs/development/maintaining-data-access


# ============================================================================
# STEP 2: X (TWITTER)
# ============================================================================
# Priority: Second — fast setup, instant developer approval.
# Time: ~10 minutes
# ============================================================================

## 2a. Create a Twitter/X Account

1. Go to https://x.com/i/flow/signup
2. Sign up with your Kova business email
3. Pick a handle: @KovaAgent (or @KovaAgentAI, etc.)
4. Verify email + phone number

## 2b. Apply for Developer Access

1. Go to https://developer.x.com/
2. Sign in with the Kova X account
3. Sign up for developer access
4. Choose the Free tier (1,500 tweets/month — enough for testing)
5. Use case description (paste this):

   Kova Agent is an AI-powered social media management platform.
   We use the Twitter API to publish posts, read tweets, and track
   engagement metrics on behalf of our users who authorize access
   via OAuth 2.0 with PKCE. Users connect their own Twitter accounts
   and control what gets published through an approval workflow.

6. Accept terms

## 2c. Create a Project and App

1. In the developer portal, create a new Project
2. Project name: Kova Agent
3. Create an App inside the project
4. App name: Kova Agent

## 2d. Configure User Authentication

1. Go to App Settings → User authentication settings → Set up
2. App permissions: Read and Write
3. Type of app: Web App, Automated App or Bot
4. Callback URI / Redirect URL:
   https://kovaagent-production.up.railway.app/platforms/callback/twitter/
5. Website URL:
   https://kovaagent-production.up.railway.app

## 2e. Get Your Credentials

1. Go to Keys and tokens
2. Under OAuth 2.0 Client ID and Client Secret:
   - Copy Client ID → TWITTER_CLIENT_ID
   - Copy Client Secret → TWITTER_CLIENT_SECRET
3. Save these — the secret is only shown once!

## 2f. Set Railway Environment Variables

  TWITTER_CLIENT_ID=xxxxxxxxxxxxxxxxxxxxxxxx
  TWITTER_CLIENT_SECRET=xxxxxxxxxxxxxxxxxxxxxxxx

## 2g. Verify It Works

1. Go to Platforms page → Click "Connect" on X (Twitter)
2. Should redirect to Twitter auth → authorize → connected


# ============================================================================
# STEP 3: LINKEDIN
# ============================================================================
# Priority: Third — requires a Company Page to create an app.
# Time: ~15 minutes
# ============================================================================

## 3a. Create a LinkedIn Account

1. Go to https://www.linkedin.com/signup
2. Sign up with your Kova business email
3. Use your real name (LinkedIn enforces real identity)
4. Fill in basic profile details

## 3b. Create a Company Page

Required to create a LinkedIn developer app.

1. Go to https://www.linkedin.com/company/setup/new/
2. Company name: Kova Agent
3. Public URL: linkedin.com/company/kova-agent
4. Industry: Technology, Information and Media
5. Company size: 1-10
6. Type: Privately Held
7. Complete and publish the page

## 3c. Create the Developer App

1. Go to https://www.linkedin.com/developers/
2. Click "Create App"
3. App name: Kova Agent
4. LinkedIn Page: select the Kova Agent Company Page you just created
5. App logo: upload the Kova logo
6. Accept terms

## 3d. Get Your Credentials

1. Go to the Auth tab
2. Copy Client ID → LINKEDIN_CLIENT_ID
3. Copy Client Secret → LINKEDIN_CLIENT_SECRET

## 3e. Configure OAuth Redirect

Under Auth tab → OAuth 2.0 settings → Authorized redirect URLs:

  https://kovaagent-production.up.railway.app/platforms/callback/linkedin/

## 3f. Request API Products

Go to the Products tab and request:
  - Share on LinkedIn (for publishing posts)
  - Sign in with LinkedIn using OpenID Connect

These are usually approved instantly.

## 3g. Set Railway Environment Variables

  LINKEDIN_CLIENT_ID=xxxxxxxxxxxxxxxx
  LINKEDIN_CLIENT_SECRET=xxxxxxxxxxxxxxxx

## 3h. Verify It Works

1. Go to Platforms page → Click "Connect" on LinkedIn
2. Should redirect to LinkedIn auth → authorize → connected


# ============================================================================
# STEP 4: TIKTOK
# ============================================================================
# Priority: Fourth — slower approval process.
# Time: ~10 minutes to submit, approval can take days.
# ============================================================================

## 4a. Create a TikTok Account

1. Go to https://www.tiktok.com/signup
2. Sign up with your Kova business email
3. Set up a basic profile

## 4b. Register as a Developer

1. Go to https://developers.tiktok.com/
2. Sign in with the TikTok account
3. Register as a developer (accept terms)

## 4c. Create an App

1. Click "Manage apps" → "Connect an app"
2. Select: Configure for Web
3. App name: Kova Agent
4. Description: AI-powered social media management platform
5. Set Redirect URI:
   https://kovaagent-production.up.railway.app/platforms/callback/tiktok/

## 4d. Add Products

1. Add: Login Kit
2. Add: Content Posting API

## 4e. Get Your Credentials

1. Copy Client Key → TIKTOK_CLIENT_KEY
2. Copy Client Secret → TIKTOK_CLIENT_SECRET

## 4f. Set Railway Environment Variables

  TIKTOK_CLIENT_KEY=xxxxxxxxxxxxxxxx
  TIKTOK_CLIENT_SECRET=xxxxxxxxxxxxxxxx

## 4g. Verify It Works

1. Go to Platforms page → Click "Connect" on TikTok
2. Should redirect to TikTok auth → authorize → connected

Note: TikTok's developer review can take several business days.
You may need to submit your app for review before OAuth works.


# ============================================================================
# STEP 5: YOUTUBE
# ============================================================================
# Priority: Fifth — requires Google Cloud project + API enablement.
# Time: ~15 minutes
# Docs: https://developers.google.com/youtube/v3/getting-started
# ============================================================================

## 5a. Create a Google Cloud Project

If you already have a Google Cloud account (from any Google service), skip to step 2.

1. Go to https://console.cloud.google.com/
2. Sign in with the Kova business email (or create a Google account)
3. Click "Select a project" (top bar) → "New Project"
4. Project name: Kova Agent
5. Organization: leave as "No organization" (or select yours)
6. Click "Create"

## 5b. Enable the YouTube Data API v3

1. In Google Cloud Console, go to:
   APIs & Services → Library
   (or: https://console.cloud.google.com/apis/library)
2. Search for "YouTube Data API v3"
3. Click it → Click "Enable"

## 5c. Create OAuth 2.0 Credentials

1. Go to APIs & Services → Credentials
   (or: https://console.cloud.google.com/apis/credentials)
2. Click "Create Credentials" → "OAuth client ID"
3. If prompted, configure the OAuth consent screen first:
   - User type: External
   - App name: Kova Agent
   - User support email: your Kova business email
   - Developer contact: your Kova business email
   - Scopes: add `youtube.upload`, `youtube.readonly`, `youtube.force-ssl`
   - Save and continue (leave test users empty for now)
4. Back to Create Credentials → OAuth client ID:
   - Application type: Web application
   - Name: Kova Agent
   - Authorized redirect URIs:
     https://kovaagent-production.up.railway.app/platforms/callback/youtube/
   - Click "Create"

## 5d. Get Your Credentials

1. A dialog shows your Client ID and Client Secret
2. Copy Client ID → YOUTUBE_CLIENT_ID
3. Copy Client Secret → YOUTUBE_CLIENT_SECRET
4. Download the JSON file as backup (store in password manager)

## 5e. Set Railway Environment Variables

  YOUTUBE_CLIENT_ID=xxxxxxxxxxxxxxxx.apps.googleusercontent.com
  YOUTUBE_CLIENT_SECRET=GOCSPX-xxxxxxxxxxxxxxxx

## 5f. Verify It Works

1. Go to Platforms page → Click "Connect" on YouTube
2. Should redirect to Google OAuth → authorize → connected

Note: While in development mode, only test users you add in the
OAuth consent screen can authorize. To go public, submit for Google
verification (requires privacy policy URL + demo video).

## 5g. YouTube API Quotas

YouTube Data API v3 has a daily quota of 10,000 units.
  - Video upload: 1,600 units per upload
  - Read channel stats: 1 unit
  - That means ~6 video uploads/day on the free default quota
  - Request quota increase: https://console.cloud.google.com/apis/api/youtube.googleapis.com/quotas

For Kova's use case (scheduling uploads + reading metrics), the default
quota is sufficient for early users. Monitor in Google Cloud Console.


# ============================================================================
# STEP 6: PINTEREST
# ============================================================================
# Priority: Sixth — straightforward OAuth setup.
# Time: ~10 minutes
# Docs: https://developers.pinterest.com/docs/getting-started/set-up-app/
# ============================================================================

## 6a. Create a Pinterest Business Account

1. Go to https://www.pinterest.com/business/create/
   (or convert existing account: https://www.pinterest.com/business/convert/)
2. Sign up with Kova business email
3. Business name: Kova Agent
4. Website: https://kovaagent-production.up.railway.app
5. Select industry: Technology

## 6b. Register as a Pinterest Developer

1. Go to https://developers.pinterest.com/
2. Sign in with the Pinterest business account
3. Accept developer terms

## 6c. Create an App

1. Go to https://developers.pinterest.com/apps/
2. Click "Create app"
3. App name: Kova Agent
4. Description: AI-powered social media management platform that creates
   and publishes pins on behalf of users via OAuth 2.0
5. Website URL: https://kovaagent-production.up.railway.app

## 6d. Configure OAuth

1. In your app settings, go to "OAuth" section
2. Add Redirect URI:
   https://kovaagent-production.up.railway.app/platforms/callback/pinterest/

## 6e. Get Your Credentials

1. In app settings, find:
   - App ID → PINTEREST_APP_ID
   - App Secret → PINTEREST_APP_SECRET
2. Save these securely

## 6f. Set Railway Environment Variables

  PINTEREST_APP_ID=xxxxxxxxxxxxxxxx
  PINTEREST_APP_SECRET=xxxxxxxxxxxxxxxx

## 6g. Pinterest API Access Levels

Pinterest API v5 has access tiers:
  - Trial: limited rate limits, sandbox only
  - Standard: request at https://developers.pinterest.com/ → app → "Request access"
  - Requires: app description, use case, privacy policy URL

Request Standard access once you have real users. Trial is fine for testing.

## 6h. Verify It Works

1. Go to Platforms page → Click "Connect" on Pinterest
2. Should redirect to Pinterest auth → authorize → connected


# ============================================================================
# STEP 7: THREADS
# ============================================================================
# Priority: Seventh — uses the same Meta app from Step 1 (shared credentials).
# Time: ~5 minutes (if Meta app already exists)
# Docs: https://developers.facebook.com/docs/threads
# ============================================================================

## 7a. Prerequisites

Threads uses the Meta Graph API with its own OAuth flow and scopes.
It can use the SAME Meta App from Step 1, OR a separate "Threads App ID."

Requirements:
  - Meta Developer account (from Step 1)
  - Instagram account linked to Threads (user must have Threads profile)
  - Your Meta App from Step 1 (FACEBOOK_APP_ID / FACEBOOK_APP_SECRET)

## 7b. Add Threads Use Case to Your Meta App

1. Go to https://developers.facebook.com/apps/ → select your Kova app
2. In the left sidebar, find "Use Cases" or "Add Product"
3. Add the "Threads" product/use case
4. Required permissions (scopes):
   - threads_basic — Read Threads profile
   - threads_content_publish — Create and publish Threads posts
   - threads_manage_insights — Read Threads post metrics
   - threads_manage_replies — Read and manage replies
   - threads_read_replies — Read reply threads

## 7c. Configure OAuth Redirect

In App Settings or Threads product settings, add redirect URI:
  https://kovaagent-production.up.railway.app/platforms/callback/threads/

## 7d. Set Railway Environment Variables

Threads falls back to FACEBOOK_APP_ID if THREADS_APP_ID is not set.
You can use either approach:

  # Option A: Use same Meta app credentials (recommended — simpler)
  # No additional env vars needed — Threads provider falls back to
  # FACEBOOK_APP_ID and FACEBOOK_APP_SECRET automatically.

  # Option B: Separate Threads app (if you want isolation)
  THREADS_APP_ID=xxxxxxxxxxxxxxxx
  THREADS_APP_SECRET=xxxxxxxxxxxxxxxx

## 7e. Important Notes

  - Threads API has its own OAuth flow at https://threads.net/oauth/authorize
    (NOT the same as Facebook/Instagram OAuth)
  - Graph API base URL for Threads: https://graph.threads.net/v1.0
  - Users must have an active Threads profile (just having Instagram isn't enough)
  - Threads supports: text posts, image posts, carousel posts, replies
  - Character limit: 500 characters per post
  - Carousel: up to 20 images/videos per carousel
  - Reply chains: post as reply to another Threads post (useful for threads)

## 7f. Verify It Works

1. Go to Platforms page → Click "Connect" on Threads
2. Should redirect to Threads OAuth → authorize → connected
3. Test: create a post, select Threads as platform, publish


# ============================================================================
# STEP 8: BLUESKY
# ============================================================================
# Priority: Eighth — no app review needed. Simplest setup.
# Time: ~3 minutes
# Docs: https://docs.bsky.app/ (AT Protocol)
# ============================================================================

## 8a. How Bluesky Authentication Works

Bluesky is DIFFERENT from all other platforms:
  - Uses the AT Protocol (open, decentralized)
  - NO OAuth flow — uses App Passwords instead
  - NO developer account needed — no app review, no API keys
  - Each USER creates their own app password when connecting
  - Kova stores the handle + app password in SocialAccount credentials

This means: YOU (the platform owner) don't need to register anything.
Each Kova user connects their own Bluesky account using their handle +
an app password they generate from Bluesky settings.

## 8b. How Users Connect Bluesky in Kova

When a user clicks "Connect" on Bluesky, Kova shows a form (not an OAuth redirect):

1. User enters their Bluesky handle (e.g., `username.bsky.social`)
2. User creates an App Password in their Bluesky account:
   - Go to https://bsky.app/settings/app-passwords
   - Click "Add App Password"
   - Name it: "Kova Agent"
   - Copy the generated password
3. User pastes the app password into the Kova form
4. Kova validates by calling the AT Protocol auth endpoint
5. If valid → account connected, tokens stored

## 8c. No Environment Variables Needed

Bluesky requires NO platform-level credentials. Unlike other platforms
where you need a Client ID/Secret for your app, Bluesky authentication
is entirely user-level (handle + app password).

  # No Bluesky env vars needed!
  # Each user provides their own credentials via the connect form.

## 8d. AT Protocol Endpoints

Kova uses these AT Protocol endpoints:

  Endpoint                                    | Purpose
  --------------------------------------------|----------------------------------
  POST /xrpc/com.atproto.server.createSession | Authenticate (get access token)
  POST /xrpc/com.atproto.server.refreshSession| Refresh expired token
  POST /xrpc/com.atproto.repo.createRecord    | Create a post (text + images)
  POST /xrpc/com.atproto.repo.uploadBlob      | Upload image for post
  GET /xrpc/app.bsky.feed.getAuthorFeed       | Get user's posts (for metrics)
  GET /xrpc/app.bsky.actor.getProfile         | Get profile info

Default PDS (Personal Data Server): https://bsky.social
If a user uses a custom PDS, they enter their full handle.

## 8e. Bluesky Post Limits

  - Text: 300 characters per post (grapheme-based, not byte-based)
  - Images: up to 4 per post (JPEG/PNG, max 1MB each after upload)
  - Links: auto-detected, displayed as link cards
  - Mentions: @handle.bsky.social format
  - Hashtags: not natively supported yet (just plain text #tags)
  - No video upload via API (as of March 2026)

## 8f. Verify It Works

1. Create a Bluesky account at https://bsky.app/ (if testing)
2. Generate an app password at https://bsky.app/settings/app-passwords
3. Go to Platforms page → Click "Connect" on Bluesky
4. Enter handle + app password in the form
5. Should validate and connect immediately


# ============================================================================
# RAILWAY ENVIRONMENT VARIABLES — FULL REFERENCE
# ============================================================================

Add all of these in Railway Dashboard → Your Service → Variables:

  # Facebook + Instagram + WhatsApp (same Meta app)
  FACEBOOK_APP_ID=
  FACEBOOK_APP_SECRET=

  # WhatsApp (optional — only if using WhatsApp use case)
  WHATSAPP_TOKEN=
  WHATSAPP_PHONE_NUMBER_ID=

  # X (Twitter)
  TWITTER_CLIENT_ID=
  TWITTER_CLIENT_SECRET=

  # LinkedIn
  LINKEDIN_CLIENT_ID=
  LINKEDIN_CLIENT_SECRET=

  # TikTok
  TIKTOK_CLIENT_KEY=
  TIKTOK_CLIENT_SECRET=

  # YouTube (Google Cloud OAuth)
  YOUTUBE_CLIENT_ID=
  YOUTUBE_CLIENT_SECRET=

  # Pinterest
  PINTEREST_APP_ID=
  PINTEREST_APP_SECRET=

  # Threads (optional — falls back to FACEBOOK_APP_ID/SECRET)
  # THREADS_APP_ID=
  # THREADS_APP_SECRET=

  # Bluesky — NO env vars needed (user-level app passwords)

Railway auto-redeploys after saving variables (~2 minutes).
Platforms without credentials will show a grayed-out connect button.
Bluesky always shows as connectable (no server credentials needed).


# ============================================================================
# CALLBACK URL QUICK REFERENCE
# ============================================================================
# Register these in each platform's developer portal.
# ============================================================================

  Platform   | Production Callback URL
  -----------|-------------------------------------------------------------
  Facebook   | https://kovaagent-production.up.railway.app/platforms/callback/facebook/
  Instagram  | https://kovaagent-production.up.railway.app/platforms/callback/instagram/
  Twitter/X  | https://kovaagent-production.up.railway.app/platforms/callback/twitter/
  LinkedIn   | https://kovaagent-production.up.railway.app/platforms/callback/linkedin/
  TikTok     | https://kovaagent-production.up.railway.app/platforms/callback/tiktok/
  YouTube    | https://kovaagent-production.up.railway.app/platforms/callback/youtube/
  Pinterest  | https://kovaagent-production.up.railway.app/platforms/callback/pinterest/
  Threads    | https://kovaagent-production.up.railway.app/platforms/callback/threads/
  Bluesky    | N/A — uses app password form, no OAuth redirect

  For local development, replace domain with: http://localhost:8000


# ============================================================================
# CREDENTIAL STORAGE CHECKLIST
# ============================================================================
# Store ALL of these in a password manager (Bitwarden, 1Password, etc.)
# NEVER commit credentials to git.
# ============================================================================

  ☐ Kova business email address + password
  ☐ Facebook account login (email + password)
  ☐ Facebook App ID + App Secret (used for FB, IG, Threads, and WhatsApp)
  ☐ WhatsApp permanent access token + phone number ID (if using WhatsApp)
  ☐ Twitter/X account login (email + password)
  ☐ Twitter Client ID + Client Secret
  ☐ LinkedIn account login (email + password)
  ☐ LinkedIn Client ID + Client Secret
  ☐ TikTok account login (email + password)
  ☐ TikTok Client Key + Client Secret
  ☐ Google Cloud account login (email + password)
  ☐ YouTube Client ID + Client Secret (Google Cloud OAuth)
  ☐ Pinterest business account login (email + password)
  ☐ Pinterest App ID + App Secret
  ☐ Threads App ID + Secret (optional — can reuse Facebook App credentials)
  ☐ Bluesky — no platform credentials needed (users provide their own)
  ☐ Railway dashboard login
  ☐ GitHub repo access


# ============================================================================
# COMMON ERRORS & FIXES
# ============================================================================

  Error                          | Cause & Fix
  -------------------------------|-------------------------------------------
  "Invalid App ID"               | FACEBOOK_APP_ID not set or wrong in Railway
  "Redirect URI mismatch"        | Callback URL in dev portal doesn't exactly
                                 | match (check trailing slash, https vs http)
  "App not set up"               | Twitter: user auth not configured in app
  "Unauthorized"                 | App in dev mode — add yourself via App Roles
  "Invalid scope"                | Permission not added to the use case in
                                 | App Dashboard → Use Cases → Customize
  "This app is in development"   | Facebook: add user via App Roles → Roles
  Login works but no Page found  | Facebook: user must be admin of a FB Page
  Instagram not connecting       | Instagram account must be Business/Creator
                                 | type AND linked to a Facebook Page (for
                                 | FB Login flow). Or use Instagram Login.
  "Use case not found"           | Use case wasn't selected during app creation.
                                 | You can add compatible use cases later from
                                 | App Dashboard, but can't remove existing ones.
  "Business portfolio required"  | WhatsApp use case requires a connected
                                 | business portfolio. Go to App Settings →
                                 | Basic → connect one.
  Max 15 apps reached            | You can have developer/admin role on max 15
                                 | apps not connected to a verified business.
                                 | Connect a verified business portfolio to
                                 | existing apps, or remove unused ones.
  YouTube "quotaExceeded"         | Daily API quota exceeded. Default is 10,000
                                 | units/day. Request quota increase in Google
                                 | Cloud Console → APIs → YouTube Data API v3.
  YouTube "forbidden"             | YouTube Data API v3 not enabled in project,
                                 | or OAuth consent screen not configured.
  Pinterest "Insufficient scopes" | App needs Standard access tier. Apply at
                                 | developers.pinterest.com → Manage → Access.
  Pinterest 429 rate limit        | Trial tier: 10 calls/min. Standard: 1000/min.
                                 | Implement backoff or request Standard access.
  Threads "User not found"        | User hasn't set up a Threads profile yet.
                                 | They must create one at threads.net first.
  Threads token issues            | If reusing FB credentials, ensure Threads
                                 | scopes are added to the FB app use case.
  Bluesky "AuthenticationRequired"| App password is wrong or was revoked.
                                 | User must generate a new one at
                                 | bsky.app → Settings → App Passwords.
  Bluesky "InvalidToken"          | Session expired. Re-authenticate with
                                 | createSession endpoint. Sessions last ~2hrs.


# ============================================================================
# APP REVIEW (WHEN READY TO GO PUBLIC)
# ============================================================================
# While in Development Mode, only people with roles on your app (or on the
# connected business portfolio) can use OAuth.
# For public access, submit each app for review.
# ============================================================================

## Facebook / Instagram / WhatsApp App Review
- Go to App Dashboard → App Review → Permissions and Features
- Request each permission with screenshots + screencasts showing usage
- Facebook reviews typically take 1-5 business days
- Required for: any user who doesn't have a role on your app
- You must also maintain data access — Meta may require periodic recertification
  Docs: https://developers.facebook.com/docs/development/maintaining-data-access
- WhatsApp requires business verification before you can message non-test users

## Twitter App Review
- Free tier has limited access; apply for Basic ($100/mo) or Pro for higher limits
- Elevated access may require app review

## LinkedIn App Review
- Most products (Share on LinkedIn, Sign in) are auto-approved
- Some products require manual review

## TikTok App Review
- Login Kit + Content Posting require review
- Submit app description + demo video
- Review takes 3-7 business days typically

## YouTube App Review (Google OAuth Verification)
- Google requires OAuth consent screen verification for apps with >100 users
- Submit privacy policy URL, homepage URL, and authorized domains
- If requesting sensitive scopes (youtube.upload), prepare a demo video
- Verification can take 2-6 weeks (plan ahead)
- While unverified, a "This app isn't verified" warning appears for users

## Pinterest App Review
- Trial access gives 10 API calls/min (enough for development)
- Apply for Standard access when ready for production
- Go to developers.pinterest.com → Your App → Manage → Request Standard Access
- Provide app description and expected API usage
- Review typically takes 1-2 weeks

## Threads App Review
- Uses the same Meta app as Facebook/Instagram — same review process
- Ensure Threads-specific scopes are included in your permission requests
- If your FB/IG app is already approved, Threads permissions may be auto-approved

## Bluesky — No App Review Needed
- Bluesky uses the AT Protocol — fully open, no app review required
- Users authenticate with their own app passwords (generated in Bluesky settings)
- No rate limit concerns for normal usage patterns
- No platform credentials stored on your server

Save App Review for when you have real users. For now, Development Mode
with your own test accounts is sufficient.


# ============================================================================
# DEVELOPER RESOURCES
# ============================================================================
# Bookmark these — you'll reference them often.
# ============================================================================

## Meta (Facebook / Instagram / Threads / WhatsApp)

  Resource                        | URL
  --------------------------------|-------------------------------------------
  App Dashboard                   | https://developers.facebook.com/apps/
  Graph API Explorer              | https://developers.facebook.com/tools/explorer/
  Access Token Debugger           | https://developers.facebook.com/tools/debug/accesstoken/
  Permissions Reference           | https://developers.facebook.com/docs/permissions
  Graph API Reference             | https://developers.facebook.com/docs/graph-api/reference
  Pages API Docs                  | https://developers.facebook.com/docs/pages-api/
  Instagram Platform Docs         | https://developers.facebook.com/docs/instagram-platform/
  Threads API Docs                | https://developers.facebook.com/docs/threads/
  WhatsApp Cloud API Docs         | https://developers.facebook.com/docs/whatsapp/cloud-api/
  Platform Status                 | https://metastatus.com/
  Bug Reports                     | https://developers.facebook.com/support/bugs/

## Google (YouTube)

  Resource                        | URL
  --------------------------------|-------------------------------------------
  Google Cloud Console            | https://console.cloud.google.com/
  YouTube Data API v3 Docs        | https://developers.google.com/youtube/v3
  OAuth 2.0 Playground            | https://developers.google.com/oauthplayground/
  API Quota Calculator            | https://developers.google.com/youtube/v3/determine_quota_cost
  YouTube API Status              | https://status.cloud.google.com/

## Pinterest

  Resource                        | URL
  --------------------------------|-------------------------------------------
  Developer Portal                | https://developers.pinterest.com/
  API v5 Reference                | https://developers.pinterest.com/docs/api/v5/
  OAuth Guide                     | https://developers.pinterest.com/docs/getting-started/authentication/
  Rate Limits                     | https://developers.pinterest.com/docs/getting-started/rate-limits/

## Twitter / X

  Resource                        | URL
  --------------------------------|-------------------------------------------
  Developer Portal                | https://developer.x.com/
  API v2 Reference                | https://developer.x.com/en/docs/twitter-api
  OAuth 2.0 Guide                 | https://developer.x.com/en/docs/authentication/oauth-2-0

## LinkedIn

  Resource                        | URL
  --------------------------------|-------------------------------------------
  Developer Portal                | https://developer.linkedin.com/
  Marketing API Docs              | https://learn.microsoft.com/en-us/linkedin/marketing/
  OAuth Guide                     | https://learn.microsoft.com/en-us/linkedin/shared/authentication/authorization-code-flow

## TikTok

  Resource                        | URL
  --------------------------------|-------------------------------------------
  Developer Portal                | https://developers.tiktok.com/
  Content Posting API             | https://developers.tiktok.com/doc/content-posting-api-get-started
  Login Kit                       | https://developers.tiktok.com/doc/login-kit-web

## Bluesky (AT Protocol)

  Resource                        | URL
  --------------------------------|-------------------------------------------
  AT Protocol Docs                | https://atproto.com/
  Bluesky API Reference           | https://docs.bsky.app/
  Lexicon Reference               | https://atproto.com/specs/lexicon
  App Passwords                   | https://bsky.app/settings/app-passwords
