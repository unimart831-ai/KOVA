# Social Login Setup Guide — Facebook & Google

This guide walks you through setting up Facebook and Google social login for Kova Agent. After completing these steps, users will see "Continue with Facebook" and "Continue with Google" buttons on the signup and login pages.

**Facebook sign-up additionally auto-connects the user's publishing accounts** (Facebook Page + Instagram Business) so they can start posting immediately without a second OAuth flow.

---

## Table of Contents

1. [Facebook Setup](#1-facebook-setup)
2. [Google Setup](#2-google-setup)
3. [Environment Variables Summary](#3-environment-variables-summary)
4. [Deploying & Testing](#4-deploying--testing)
5. [Troubleshooting](#5-troubleshooting)

---

## 1. Facebook Setup

### Step 1.1: Create or Select Your Meta App

1. Go to **[Meta for Developers](https://developers.facebook.com/apps/)**
2. If you already have a Meta App for Kova (you likely do since platform connect uses it), select it
3. If creating a new one: click **Create App** → choose **Business** type → give it a name like "Kova Agent"

### Step 1.2: Get Your App ID and Secret

1. In the Meta App Dashboard, go to **Settings** → **Basic**
2. Copy your **App ID** — this is `FACEBOOK_APP_ID`
3. Click **Show** next to App Secret and copy it — this is `FACEBOOK_APP_SECRET`

### Step 1.3: Add Facebook Login Product

1. In the left sidebar, click **Add Product**
2. Find **Facebook Login** and click **Set Up**
3. Choose **Web** as the platform

### Step 1.4: Configure OAuth Redirect URIs

1. Go to **Facebook Login** → **Settings** in the left sidebar
2. Under **Valid OAuth Redirect URIs**, add:
   ```
   https://your-domain.com/accounts/facebook/login/callback/
   ```
   Replace `your-domain.com` with your actual production domain (e.g., `app.kovaagent.com`).

3. **Important**: You may also need the platform connect callback if it's not already there:
   ```
   https://your-domain.com/platforms/callback/facebook/
   ```

4. Click **Save Changes**

### Step 1.5: Configure Permissions (App Review)

For the auto-connect feature to work, your Meta App needs these permissions approved:

| Permission | Purpose | Review Required? |
|-----------|---------|-----------------|
| `email` | Get user's email for account creation | No (default) |
| `public_profile` | Get user's name and avatar | No (default) |
| `pages_manage_metadata` | Read Page info | Yes |
| `pages_manage_posts` | Publish to Facebook Pages | Yes |
| `pages_read_engagement` | Read post insights | Yes |
| `instagram_content_publish` | Publish to Instagram | Yes |
| `instagram_manage_insights` | Read IG analytics | Yes |
| `instagram_manage_comments` | Manage IG comments | Yes |

**If using Facebook Login for Business (recommended):**
- Go to **Use Cases** → **Customize** your Login for Business configuration
- Add all the permissions above to the configuration
- Set `FB_LOGIN_CONFIG_ID` to the configuration ID

**If using standard Facebook Login:**
- Go to **App Review** → **Permissions and Features**
- Request approval for each permission listed above
- Provide descriptions and screencasts as Meta requires

### Step 1.6: Set App Mode to Live

1. In the top of your Meta App Dashboard, toggle the app from **Development** to **Live**
2. You'll need to complete any required checks (Privacy Policy URL, Data Deletion URL, etc.)

### Step 1.7: Set Environment Variables

Add these to your deployment environment (Railway, .env, etc.):

```bash
FACEBOOK_APP_ID=your_app_id_here
FACEBOOK_APP_SECRET=your_app_secret_here
```

Optional (for Login for Business):
```bash
FB_LOGIN_CONFIG_ID=your_config_id_here
```

---

## 2. Google Setup

### Step 2.1: Create a Google Cloud Project

1. Go to **[Google Cloud Console](https://console.cloud.google.com/)**
2. Click the project dropdown at the top → **New Project**
3. Name it "Kova Agent" (or select existing project)
4. Wait for it to create, then select it

### Step 2.2: Configure the OAuth Consent Screen

1. Go to **APIs & Services** → **OAuth consent screen**
2. Choose **External** user type → click **Create**
3. Fill in:
   - **App name**: Kova Agent
   - **User support email**: your support email
   - **App logo**: (optional) upload your logo
   - **App domain**: `https://your-domain.com`
   - **Authorized domains**: add `your-domain.com`
   - **Developer contact email**: your email
4. Click **Save and Continue**
5. On the **Scopes** page:
   - Click **Add or Remove Scopes**
   - Add: `email`, `profile` (or `openid`, `../auth/userinfo.email`, `../auth/userinfo.profile`)
   - Click **Update** → **Save and Continue**
6. On **Test Users** page (skip if publishing to production):
   - Add test emails if your app is in "Testing" mode
7. Click **Back to Dashboard**

### Step 2.3: Create OAuth 2.0 Credentials

1. Go to **APIs & Services** → **Credentials**
2. Click **+ Create Credentials** → **OAuth client ID**
3. Choose **Web application** as the application type
4. Give it a name: "Kova Agent Web"
5. Under **Authorized JavaScript origins**, add:
   ```
   https://your-domain.com
   ```
6. Under **Authorized redirect URIs**, add:
   ```
   https://your-domain.com/accounts/google/login/callback/
   ```
7. Click **Create**
8. A dialog appears with your **Client ID** and **Client Secret** — copy both

### Step 2.4: Publish the App (Optional but Recommended)

If your consent screen is in "Testing" mode:
- Only users you've manually added as test users can sign in
- To allow any Google user: go to **OAuth consent screen** → click **Publish App**
- Google may require a verification review for certain scopes (email/profile are non-sensitive, so usually no review needed)

### Step 2.5: Set Environment Variables

Add these to your deployment environment:

```bash
GOOGLE_OAUTH_CLIENT_ID=your_client_id.apps.googleusercontent.com
GOOGLE_OAUTH_CLIENT_SECRET=your_client_secret_here
```

---

## 3. Environment Variables Summary

| Variable | Source | Required? |
|----------|--------|-----------|
| `FACEBOOK_APP_ID` | Meta App Dashboard → Settings → Basic → App ID | For Facebook login |
| `FACEBOOK_APP_SECRET` | Meta App Dashboard → Settings → Basic → App Secret | For Facebook login |
| `FB_LOGIN_CONFIG_ID` | Meta App Dashboard → Use Cases → Login config ID | Optional |
| `GOOGLE_OAUTH_CLIENT_ID` | Google Cloud Console → Credentials → OAuth Client ID | For Google login |
| `GOOGLE_OAUTH_CLIENT_SECRET` | Google Cloud Console → Credentials → OAuth Client Secret | For Google login |

**Both are optional and env-gated.** If a pair isn't set, that button simply won't appear.

### Setting Variables on Railway

1. Go to your Railway project → select the service
2. Click **Variables** tab
3. Click **+ New Variable** for each:
   - `FACEBOOK_APP_ID` = `123456789012345`
   - `FACEBOOK_APP_SECRET` = `abc123def456...`
   - `GOOGLE_OAUTH_CLIENT_ID` = `xxxx.apps.googleusercontent.com`
   - `GOOGLE_OAUTH_CLIENT_SECRET` = `GOCSPX-xxxx...`
4. Railway will automatically redeploy

---

## 4. Deploying & Testing

### Test Facebook Login

1. Ensure `FACEBOOK_APP_ID` and `FACEBOOK_APP_SECRET` are set
2. Visit your signup page — you should see "Continue with Facebook"
3. Click the button — you'll be redirected to Facebook's consent screen
4. After granting permissions, you'll be redirected back to Kova
5. Check:
   - User is created (check admin `/admin/accounts/user/`)
   - User is redirected to onboarding
   - In the background, `platforms.SocialAccount` entries are created for Facebook Page and Instagram (if the user has a Page linked to an IG Business Account)
   - On the Magic Connect onboarding step, the user sees "Auto-connected from your sign-up" with their accounts listed

### Test Google Login

1. Ensure `GOOGLE_OAUTH_CLIENT_ID` and `GOOGLE_OAUTH_CLIENT_SECRET` are set
2. Visit your signup page — you should see "Continue with Google"
3. Click the button — Google consent screen appears
4. After granting, user is created and redirected to onboarding
5. No platform auto-connect happens (Google doesn't own Facebook/Instagram)

### Test with Both Disabled

1. Remove both pairs of variables
2. Signup page should show only the email/password form with no social buttons

---

## 5. Troubleshooting

### "App Not Setup" error from Facebook

- Your Meta App is likely still in **Development** mode
- Go to Meta App Dashboard → toggle to **Live**
- Make sure you've added a Privacy Policy URL and Data Deletion URL

### "Redirect URI mismatch" error

- Double check the callback URL is exactly:
  - Facebook: `https://your-domain.com/accounts/facebook/login/callback/`
  - Google: `https://your-domain.com/accounts/google/login/callback/`
- Trailing slash matters!
- Make sure you're using HTTPS (not HTTP)

### Facebook button appears but Google doesn't (or vice versa)

- Each button only appears if its env vars are set and non-empty
- Check Railway variables are actually deployed (not just saved)

### "NameError: name 'FACEBOOK_APP_ID' is not defined"

- This was a bug (now fixed). The variable definition was out of order in settings.
- If you see this, make sure you're on the latest commit.

### User signs up with Facebook but platforms aren't auto-connected

- The user must have a **Facebook Page** for the auto-connect to work
- Check Celery/app logs for "Facebook auto-connect" messages
- Common: user declined some permissions on the Facebook consent screen
- The auto-connect is non-blocking — if it fails, the user still signs up successfully and can manually connect later

### Google "Access blocked: This app's request is invalid"

- Your OAuth consent screen might not be published
- The redirect URI might not match exactly what's in Google Cloud Console
- Check that `https://your-domain.com` is in Authorized JavaScript origins

### "Social account already connected" or email conflicts

- If a user already exists with the same email, allauth will try to connect the social account to the existing user
- This is controlled by `SOCIALACCOUNT_EMAIL_AUTHENTICATION_AUTO_CONNECT = True` in settings
- Users cannot have two accounts with the same email

---

## Architecture Reference

```
User clicks "Continue with Facebook"
    │
    ▼
allauth redirects to Facebook OAuth
(with publishing scopes: pages_manage_posts, instagram_content_publish, etc.)
    │
    ▼
User grants permissions on Facebook
    │
    ▼
Facebook redirects back to /accounts/facebook/login/callback/
    │
    ▼
allauth creates User + SocialAccount + SocialToken
    │
    ▼
Signal: social_account_added fires
    │
    ▼
_auto_connect_facebook_platforms() runs:
  1. Exchanges token for long-lived (60-day) token
  2. Calls GET /me/accounts → fetches user's Pages
  3. Creates platforms.SocialAccount for Facebook (page type)
  4. For each Page, checks for instagram_business_account
  5. If found, creates platforms.SocialAccount for Instagram
    │
    ▼
User lands on onboarding → sees "Auto-connected from your sign-up"
    │
    ▼
User can immediately start creating and publishing content
```
