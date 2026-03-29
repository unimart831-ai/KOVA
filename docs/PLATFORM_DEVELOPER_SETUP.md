# ============================================================================
# KOVA AGENT — PLATFORM DEVELOPER ACCOUNT SETUP
# ============================================================================
# One-time setup guide for the platform owner (you).
# This creates the OAuth "pipes" that let ALL your users connect platforms.
# Your clients never see any of this — they just click "Connect" and authorize.
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
# STEP 1: FACEBOOK + INSTAGRAM (same app)
# ============================================================================
# Priority: DO THIS FIRST — one app unlocks both Facebook AND Instagram.
# Time: ~15 minutes (+ up to 48 hours if identity verification is triggered)
# ============================================================================

## 1a. Create a Facebook Account for Kova Agent

1. Go to https://www.facebook.com/r.php
2. Sign up with your Kova business email
3. Use your real name (Facebook requires it, can get banned otherwise)
4. Verify email + phone number when prompted

## 1b. Create a Facebook Page

Required before you can create a developer app.

1. Log into the new Facebook account
2. Go to https://www.facebook.com/pages/create
3. Page name: Kova Agent
4. Category: Software or Technology
5. Add a profile picture (Kova logo) and cover image
6. Publish the page

## 1c. Create the Developer App

1. Go to https://developers.facebook.com/
2. Log in with the Kova Facebook account
3. Click "My Apps" → "Create App"
4. App type: Business
5. App name: Kova Agent
6. Contact email: your Kova business email
7. Business Account: skip if you don't have a Meta Business Suite account

## 1d. Get Your Credentials

1. Go to App Settings → Basic
2. Copy the App ID → this is FACEBOOK_APP_ID
3. Click "Show" next to App Secret → this is FACEBOOK_APP_SECRET

## 1e. Add Products

1. From the app dashboard, click "Add Product"
2. Add: Facebook Login for Business
3. Add: Instagram Graph API

## 1f. Configure OAuth Redirect URIs

Go to Facebook Login → Settings → Valid OAuth Redirect URIs. Add ALL of these:

  Production:
    https://kovaagent-production.up.railway.app/platforms/callback/facebook/
    https://kovaagent-production.up.railway.app/platforms/callback/instagram/

  Local development:
    http://localhost:8000/platforms/callback/facebook/
    http://localhost:8000/platforms/callback/instagram/

## 1g. App Roles (for testing in Development Mode)

While the app is in Development Mode, only listed testers can use OAuth.

1. Go to App Roles → Roles
2. Click "Add People"
3. Add yourself and any test users by Facebook account

## 1h. Required Permissions

These are auto-requested by Kova's OAuth flow. For App Review (later):
  - pages_show_list
  - pages_manage_posts
  - pages_read_engagement
  - instagram_basic (Instagram)
  - instagram_content_publish (Instagram)

Note: You do NOT need App Review to test with users in your tester list.

## 1i. Set Railway Environment Variables

  FACEBOOK_APP_ID=123456789012345
  FACEBOOK_APP_SECRET=abc123def456ghi789...

## 1j. Verify It Works

1. Go to https://kovaagent-production.up.railway.app/platforms/
2. Click "Connect" on Facebook
3. Should redirect to Facebook → authorize → redirect back → Connected!
4. Repeat for Instagram


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
# RAILWAY ENVIRONMENT VARIABLES — FULL REFERENCE
# ============================================================================

Add all of these in Railway Dashboard → Your Service → Variables:

  # Facebook + Instagram (same app)
  FACEBOOK_APP_ID=
  FACEBOOK_APP_SECRET=

  # X (Twitter)
  TWITTER_CLIENT_ID=
  TWITTER_CLIENT_SECRET=

  # LinkedIn
  LINKEDIN_CLIENT_ID=
  LINKEDIN_CLIENT_SECRET=

  # TikTok
  TIKTOK_CLIENT_KEY=
  TIKTOK_CLIENT_SECRET=

Railway auto-redeploys after saving variables (~2 minutes).
Platforms without credentials will show a grayed-out connect button.


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

  For local development, replace domain with: http://localhost:8000


# ============================================================================
# CREDENTIAL STORAGE CHECKLIST
# ============================================================================
# Store ALL of these in a password manager (Bitwarden, 1Password, etc.)
# NEVER commit credentials to git.
# ============================================================================

  ☐ Kova business email address + password
  ☐ Facebook account login (email + password)
  ☐ Facebook App ID + App Secret
  ☐ Twitter/X account login (email + password)
  ☐ Twitter Client ID + Client Secret
  ☐ LinkedIn account login (email + password)
  ☐ LinkedIn Client ID + Client Secret
  ☐ TikTok account login (email + password)
  ☐ TikTok Client Key + Client Secret
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
  "Unauthorized"                 | App in dev mode — add yourself as tester
  "Invalid scope"                | Platform hasn't approved required permissions
  "This app is in development"   | Facebook: add user as tester in App Roles
  Login works but no Page found  | Facebook: user must be admin of a FB Page
  Instagram not connecting       | Instagram account must be Business/Creator
                                 | type AND linked to a Facebook Page


# ============================================================================
# APP REVIEW (WHEN READY TO GO PUBLIC)
# ============================================================================
# While in Development Mode, only testers you add can use OAuth.
# For public access, submit each app for review.
# ============================================================================

## Facebook App Review
- Go to App Review → Permissions and Features
- Request each permission with screenshots + screencasts showing usage
- Facebook reviews typically take 1-5 business days
- Required for: any user who isn't a listed tester

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

Save App Review for when you have real users. For now, Development Mode
with your own test accounts is sufficient.
