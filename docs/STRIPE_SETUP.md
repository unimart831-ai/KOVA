# Kova Agent — Stripe Billing Setup Guide
> Step-by-step guide to configure Stripe payments for Kova Agent

**Last updated:** March 31, 2026

---

## Table of Contents
1. [Overview — How Billing Works in Kova](#1-overview)
2. [Create a Stripe Account](#2-create-a-stripe-account)
3. [Get Your API Keys (Sandbox/Test Mode)](#3-get-your-api-keys)
4. [Create Products & Prices in Stripe Dashboard](#4-create-products--prices)
5. [Configure Customer Portal](#5-configure-customer-portal)
6. [Set Up Webhooks](#6-set-up-webhooks)
7. [Add Environment Variables](#7-add-environment-variables)
8. [Test the Integration Locally](#8-test-the-integration-locally)
9. [Go Live (Production)](#9-go-live-production)
10. [Railway Deployment](#10-railway-deployment)
11. [Troubleshooting](#11-troubleshooting)

---

## 1. Overview

### How Billing Works in Kova

Kova uses **Stripe Checkout** (hosted payment page) + **Stripe Customer Portal** (self-service billing management) + **Stripe Webhooks** (real-time event sync).

```
User clicks "Subscribe" on pricing page
    → Kova creates a Stripe Checkout Session (server-side)
    → User is redirected to Stripe's hosted payment page
    → User enters card details on Stripe (we never touch card data)
    → Stripe processes payment
    → Stripe redirects user back to Kova (success/cancel URL)
    → Stripe sends webhook events to Kova
    → Kova updates user's plan and subscription status
```

### Architecture (files you should know)

| File | Purpose |
|------|---------|
| `apps/billing/models.py` | `BillingEvent` audit model + `PLAN_LIMITS` config (4 tiers) |
| `apps/billing/services.py` | All Stripe API calls — checkout, portal, webhooks, sync |
| `apps/billing/views.py` | Django views — overview, pricing, checkout, portal, webhook endpoint |
| `apps/billing/urls.py` | URL routes: `/billing/`, `/billing/checkout/`, `/billing/webhook/stripe/` |
| `apps/billing/middleware.py` | `PlanEnforcementMiddleware` — blocks actions exceeding plan limits |
| `apps/accounts/models.py` | `UserProfile` fields: `stripe_customer_id`, `stripe_subscription_id`, `plan`, `subscription_status`, `trial_ends_at`, `current_period_end` |
| `config/settings/base.py` | Stripe env var references (`STRIPE_SECRET_KEY`, etc.) |

### Kova's 4 Plans

| Plan Tier (code) | Display Name | Price (KES/mo) | Price (USD/mo) | Trial |
|---|---|---|---|---|
| `starter` | Jipange / Starter | KES 299 | $2 | 14 days |
| `growth` | Kazi / Growth | KES 999 | $7 | 14 days |
| `pro` | Biashara / Pro | KES 1,999 | $14 | 14 days |
| `agency` | Wakala / Agency | KES 2,999 | $21 | 14 days |

---

## 2. Create a Stripe Account

### Step 2.1: Register

1. Go to **https://dashboard.stripe.com/register**
2. Enter your email, full name, and create a password
3. Verify your email address

### Step 2.2: Activate Your Account

To accept real payments later, you'll need to activate your account:

1. In the Dashboard, click **"Activate payments"** (top banner)
2. Fill in your business details:
   - **Business type**: Individual / Sole proprietor (or Company if registered)
   - **Country**: Kenya
   - **Business name**: Your registered business name
   - **Industry**: Software / SaaS
3. Add your bank account details for payouts (M-Pesa and bank transfer are supported in Kenya via Stripe)
4. Verify your identity (ID upload)

> **Note**: You can skip activation for now and use **Sandbox (Test Mode)** to develop. Activation is only needed when you're ready to accept real money.

### Step 2.3: Understand Test vs. Live Mode

| Mode | API Key Prefix | Purpose |
|------|---------------|---------|
| **Sandbox (Test)** | `pk_test_...`, `sk_test_...` | Development & testing. No real money moves. |
| **Live** | `pk_live_...`, `sk_live_...` | Production. Real charges on real cards. |

You toggle between modes using the **mode switch** in the top-right corner of the Stripe Dashboard.

---

## 3. Get Your API Keys

### Step 3.1: Access API Keys

1. Go to **https://dashboard.stripe.com/test/apikeys** (make sure you're in **Test mode**)
2. You'll see two keys:
   - **Publishable key**: Starts with `pk_test_...` — safe to use in client-side code
   - **Secret key**: Starts with `sk_test_...` — **server-side only, never expose publicly**

### Step 3.2: Reveal and Copy Your Secret Key

1. Click **"Reveal test key"** next to the Secret key row
2. Copy the full key (starts with `sk_test_`)
3. Save it somewhere safe — you'll add it to your `.env` file in Step 7

### Step 3.3: Copy Your Publishable Key

1. The publishable key (`pk_test_...`) is visible by default
2. Click it to copy

> **Security**: Never commit API keys to Git. Never put secret keys in client-side code. Always use environment variables.

---

## 4. Create Products & Prices

Kova needs 4 Products with 4 recurring Prices in Stripe. Each Price ID gets mapped to a plan tier in the code.

### Step 4.1: Create the Starter Product

1. Go to **https://dashboard.stripe.com/test/products** (Test mode)
2. Click **"+ Add product"**
3. Fill in:
   - **Name**: `Jipange / Starter`
   - **Description**: `1 social account, 15 posts/month, Create + Analyst agents, Daily Brief`
   - **Image**: (optional — upload your Kova logo)
4. Under **Price information**:
   - **Pricing model**: Standard pricing
   - **Price**: `99` (if using KES) or `1.00` (if using USD)
   - **Currency**: `KES` or `USD` (choose one — Stripe handles conversion if needed)
   - **Billing period**: `Monthly`
   - **Lookup key** (optional but recommended): `kova_starter_monthly`
5. Click **"Save product"**
6. After saving, click into the product → click the Price → **copy the Price ID**
   - It looks like: `price_1Abc123...`
   - **Save this** — you'll need it for `STRIPE_PRICE_STARTER` in Step 7

### Step 4.2: Create the Growth Product

Repeat the same process:

| Field | Value |
|-------|-------|
| Name | `Kazi / Growth` |
| Description | `3 social accounts, 50 posts/month, 4 agents, Email briefs, Engagement agent` |
| Price | `500` KES or `5.00` USD |
| Billing period | Monthly |
| Lookup key | `kova_growth_monthly` |

Copy the Price ID → save as `STRIPE_PRICE_GROWTH`

### Step 4.3: Create the Pro Product

| Field | Value |
|-------|-------|
| Name | `Biashara / Pro` |
| Description | `10 social accounts, Unlimited posts, All 6 agents, Auto-approve, Full analytics` |
| Price | `1500` KES or `15.00` USD |
| Billing period | Monthly |
| Lookup key | `kova_pro_monthly` |

Copy the Price ID → save as `STRIPE_PRICE_PRO`

### Step 4.4: Create the Agency Product

| Field | Value |
|-------|-------|
| Name | `Wakala / Agency` |
| Description | `25 social accounts, Unlimited posts, All agents, Priority support, White-label reports` |
| Price | `3500` KES or `29.00` USD |
| Billing period | Monthly |
| Lookup key | `kova_agency_monthly` |

Copy the Price ID → save as `STRIPE_PRICE_AGENCY`

### What You Should Have Now

After creating all 4 products, you should have **4 Price IDs**:

```
STRIPE_PRICE_STARTER = price_1Abc...  (KES 299 or $2/mo)
STRIPE_PRICE_GROWTH  = price_1Def...  (KES 999 or $7/mo)
STRIPE_PRICE_PRO     = price_1Ghi...  (KES 1999 or $14/mo)
STRIPE_PRICE_AGENCY  = price_1Jkl...  (KES 2999 or $21/mo)
```

---

## 5. Configure Customer Portal

The Customer Portal lets users manage their own subscription (upgrade, downgrade, cancel, update payment method) on a Stripe-hosted page. Kova redirects to it from the Billing Overview page.

### Step 5.1: Open Portal Settings

1. Go to **https://dashboard.stripe.com/test/settings/billing/portal**
2. (Or: Dashboard → Settings → Billing → Customer portal)

### Step 5.2: Configure Features

Enable the following:

| Feature | Setting | Why |
|---------|---------|-----|
| **Update payment method** | ✅ Enabled | Users can update their card |
| **Update subscriptions** | ✅ Enabled | Users can switch between plans |
| **Cancel subscriptions** | ✅ Enabled | Users can cancel (set to "Cancel at end of period" — not immediate) |
| **View invoice history** | ✅ Enabled | Users can download invoices/receipts |

### Step 5.3: Add Your Products to the Portal

Under **"Products"** in the portal settings:
1. Click **"+ Add product"** for each of the 4 products you created
2. Add all 4: Starter, Growth, Pro, Agency
3. This allows users to switch between plans in the portal

### Step 5.4: Set Cancellation Policy

Under **"Cancel subscriptions"**:
- Select **"At end of billing period"** (recommended)
- This means: when a user cancels, they keep access until the current period ends, then revert to starter

### Step 5.5: Customize Branding (Optional)

Under **"Branding"**:
- Upload your Kova logo
- Set accent color to match your brand (Kova's purple: `#7C3AED`)
- Add your business name

### Step 5.6: Set Return URL

Under **"Business information"**:
- **Default return URL**: `https://yourdomain.com/billing/` (or `http://127.0.0.1:8000/billing/` for local testing)

> **Note**: The code already handles the return URL dynamically in `services.py` → `create_portal_session()`, so this is just a fallback.

### Step 5.7: Save

Click **"Save changes"** at the bottom.

---

## 6. Set Up Webhooks

Webhooks are how Stripe tells Kova about payment events (successful checkout, subscription updated, payment failed, etc.). Without webhooks, Kova won't know when payments happen.

### How It Works in Kova

```
Stripe Event (e.g. invoice.paid)
    → POST to https://yourdomain.com/billing/webhook/stripe/
    → Django view: stripe_webhook() in billing/views.py
    → Verifies signature using STRIPE_WEBHOOK_SECRET
    → Routes to handler in billing/services.py
    → Updates UserProfile (plan, status, period_end)
    → Saves BillingEvent audit record
```

### Events Kova Handles

| Event | Handler | What It Does |
|-------|---------|--------------|
| `checkout.session.completed` | `_handle_checkout_completed` | User finished checkout → sync subscription to DB |
| `customer.subscription.updated` | `_handle_subscription_updated` | Plan change, renewal, trial end → sync subscription |
| `customer.subscription.deleted` | `_handle_subscription_deleted` | Subscription canceled/expired → revert to starter plan |
| `invoice.paid` | `_handle_invoice_paid` | Successful payment → sync subscription |
| `invoice.payment_failed` | `_handle_invoice_failed` | Card declined → set status to `past_due` |

### Step 6.1: Local Testing with Stripe CLI

For local development, use the Stripe CLI to forward webhook events to your local server.

#### Install Stripe CLI

**Windows (with Scoop):**
```powershell
scoop install stripe
```

**Windows (direct download):**
1. Go to https://github.com/stripe/stripe-cli/releases/latest
2. Download `stripe_X.X.X_windows_x86_64.zip`
3. Extract and add to your PATH

**macOS:**
```bash
brew install stripe/stripe-cli/stripe
```

#### Login to Stripe CLI

```powershell
stripe login
```
Follow the browser prompt to authenticate.

#### Forward Events to Local Server

```powershell
stripe listen --forward-to http://127.0.0.1:8000/billing/webhook/stripe/
```

You'll see output like:
```
Ready! Your webhook signing secret is whsec_abc123...
```

**Copy that `whsec_...` value** — that's your local `STRIPE_WEBHOOK_SECRET`. Add it to `.env` (Step 7).

#### Forward Only the Events Kova Uses

```powershell
stripe listen --events checkout.session.completed,customer.subscription.updated,customer.subscription.deleted,invoice.paid,invoice.payment_failed --forward-to http://127.0.0.1:8000/billing/webhook/stripe/
```

#### Trigger Test Events

In a separate terminal:
```powershell
stripe trigger checkout.session.completed
stripe trigger invoice.paid
stripe trigger customer.subscription.updated
stripe trigger invoice.payment_failed
```

### Step 6.2: Production Webhook (Dashboard)

When you deploy to production:

1. Go to **https://dashboard.stripe.com/webhooks** (switch to **Live mode**)
2. Click **"Create an event destination"**
3. Select **"Your account"** as the event source
4. Select these event types:
   - `checkout.session.completed`
   - `customer.subscription.updated`
   - `customer.subscription.deleted`
   - `invoice.paid`
   - `invoice.payment_failed`
5. Click **"Continue"**, select **"Webhook endpoint"**
6. Click **"Continue"**, set:
   - **Endpoint URL**: `https://yourdomain.com/billing/webhook/stripe/`
   - **Description**: `Kova Agent billing webhooks`
7. Click **"Create destination"**
8. After creation, click the endpoint → **"Click to reveal"** the signing secret
9. Copy the `whsec_...` value — this is your production `STRIPE_WEBHOOK_SECRET`

> **Important**: The production webhook secret is different from the local CLI secret. Use the correct one for each environment.

---

## 7. Add Environment Variables

### Step 7.1: Local Development (`.env` file)

Open your `.env` file in the project root and add:

```env
# Stripe (Test Mode)
STRIPE_PUBLISHABLE_KEY=pk_test_your_publishable_key_here
STRIPE_SECRET_KEY=sk_test_your_secret_key_here
STRIPE_WEBHOOK_SECRET=whsec_your_webhook_secret_here

# Stripe Price IDs (from Step 4)
STRIPE_PRICE_STARTER=price_your_starter_price_id
STRIPE_PRICE_GROWTH=price_your_growth_price_id
STRIPE_PRICE_PRO=price_your_pro_price_id
STRIPE_PRICE_AGENCY=price_your_agency_price_id
```

### Step 7.2: How These Map to Django Settings

In `config/settings/base.py`, these environment variables are loaded as:

```python
STRIPE_SECRET_KEY = env("STRIPE_SECRET_KEY", default="")
STRIPE_PUBLISHABLE_KEY = env("STRIPE_PUBLISHABLE_KEY", default="")
STRIPE_PRICE_STARTER = env("STRIPE_PRICE_STARTER", default="")
STRIPE_PRICE_GROWTH = env("STRIPE_PRICE_GROWTH", default="")
STRIPE_PRICE_PRO = env("STRIPE_PRICE_PRO", default="")
STRIPE_PRICE_AGENCY = env("STRIPE_PRICE_AGENCY", default="")
STRIPE_WEBHOOK_SECRET = env("STRIPE_WEBHOOK_SECRET", default="")
```

And in `apps/billing/services.py`, they map to plan tiers:

```python
PLAN_PRICE_MAP = {
    "starter": settings.STRIPE_PRICE_STARTER,   # → KES 299/mo
    "growth":  settings.STRIPE_PRICE_GROWTH,     # → KES 999/mo
    "pro":     settings.STRIPE_PRICE_PRO,        # → KES 1999/mo
    "agency":  settings.STRIPE_PRICE_AGENCY,     # → KES 2999/mo
}
```

---

## 8. Test the Integration Locally

### Step 8.1: Start the Dev Server

```powershell
cd kova_agent
python manage.py runserver
```

### Step 8.2: Start Stripe CLI Listener (separate terminal)

```powershell
stripe listen --forward-to http://127.0.0.1:8000/billing/webhook/stripe/
```

### Step 8.3: Test the Subscribe Flow

1. Log in to Kova at `http://127.0.0.1:8000/`
2. Go to **Billing** → **Pricing** (or `/billing/pricing/`)
3. Click **"Subscribe"** on any plan (e.g., Growth/Kazi)
4. You'll be redirected to Stripe Checkout (hosted payment page)
5. Use a **test card**:

| Scenario | Card Number | Expiry | CVC |
|----------|-------------|--------|-----|
| **Success** | `4242 4242 4242 4242` | Any future date (e.g. `12/34`) | Any 3 digits (e.g. `123`) |
| **Requires 3DS auth** | `4000 0025 0000 3155` | Any future date | Any 3 digits |
| **Card declined** | `4000 0000 0000 9995` | Any future date | Any 3 digits |

6. After successful payment, you'll be redirected to `/billing/checkout/success/`
7. Check the Stripe CLI terminal — you should see webhook events firing:
   ```
   2026-03-31 --> checkout.session.completed [evt_...]
   2026-03-31 --> customer.subscription.updated [evt_...]
   2026-03-31 --> invoice.paid [evt_...]
   ```

### Step 8.4: Verify in Kova

1. Go to `/billing/` — your plan should show the subscribed tier
2. Check Django admin at `/admin/` → **Billing Events** — you should see processed events

### Step 8.5: Test Customer Portal

1. Go to `/billing/` → click **"Manage Subscription"**
2. You'll be redirected to Stripe's Customer Portal
3. Test: update payment method, switch plan, download an invoice, cancel subscription
4. Each action triggers webhook events that Kova processes automatically

### Step 8.6: Test Plan Enforcement

1. Subscribe to the **Starter** plan (1 social account, 15 posts/month)
2. Connect 1 social account — should work
3. Try to connect a 2nd — you should be redirected to the pricing page with a warning message
4. Try creating posts until you hit the monthly limit — same redirect behavior

---

## 9. Go Live (Production)

When you're ready to accept real payments:

### Step 9.1: Activate Your Stripe Account

Complete the activation process from Step 2.2 if you haven't already. Stripe will verify your identity and business details.

### Step 9.2: Switch to Live Mode Keys

1. In the Stripe Dashboard, toggle from **Test mode** to **Live mode** (top-right)
2. Go to **API keys** tab
3. Copy your **live publishable key** (`pk_live_...`)
4. Reveal and copy your **live secret key** (`sk_live_...`) — **you can only see this once!**

### Step 9.3: Create Live Products & Prices

Repeat Step 4 in **Live mode**. Test mode products don't carry over to live mode.

> **Important**: Use the same structure (4 products, 4 monthly prices) with the same amounts. Copy the 4 new live Price IDs.

### Step 9.4: Create Live Webhook Endpoint

Repeat Step 6.2 in **Live mode**:
- Endpoint URL: `https://yourdomain.com/billing/webhook/stripe/`
- Same 5 event types
- Copy the live webhook signing secret

### Step 9.5: Configure Live Customer Portal

Repeat Step 5 in **Live mode**:
- Add all 4 live products
- Same cancellation and feature settings

### Step 9.6: Update Environment Variables

Replace all test keys with live keys in your production environment:

```env
STRIPE_PUBLISHABLE_KEY=pk_live_...
STRIPE_SECRET_KEY=sk_live_...
STRIPE_WEBHOOK_SECRET=whsec_live_...
STRIPE_PRICE_STARTER=price_live_starter_id
STRIPE_PRICE_GROWTH=price_live_growth_id
STRIPE_PRICE_PRO=price_live_pro_price_id
STRIPE_PRICE_AGENCY=price_live_agency_price_id
```

### Go-Live Checklist

- [ ] Stripe account activated (identity verified, bank account connected)
- [ ] Live API keys copied and stored securely (never in code)
- [ ] 4 live products with correct KES/USD prices created
- [ ] 4 live Price IDs set in production environment variables
- [ ] Live webhook endpoint created with correct URL
- [ ] Live webhook signing secret set in production environment
- [ ] Customer Portal configured in live mode with all 4 products
- [ ] Test a real transaction with a small amount (subscribe to Starter at KES 299)
- [ ] Verify webhook events arrive and process correctly
- [ ] Check BillingEvent records in Django admin
- [ ] Verify plan enforcement works (connect limits, post limits)

---

## 10. Railway Deployment

Kova is deployed on Railway. Here's how to set the Stripe variables there.

### Step 10.1: Add Variables in Railway

1. Go to your Railway project dashboard
2. Click on your Kova service
3. Go to **Variables** tab
4. Click **"New Variable"** for each:

| Variable | Value |
|----------|-------|
| `STRIPE_PUBLISHABLE_KEY` | Your `pk_live_...` key |
| `STRIPE_SECRET_KEY` | Your `sk_live_...` key |
| `STRIPE_WEBHOOK_SECRET` | Your `whsec_...` secret |
| `STRIPE_PRICE_STARTER` | Your live starter Price ID |
| `STRIPE_PRICE_GROWTH` | Your live growth Price ID |
| `STRIPE_PRICE_PRO` | Your live pro Price ID |
| `STRIPE_PRICE_AGENCY` | Your live agency Price ID |

5. Railway will automatically redeploy with the new variables

### Step 10.2: Set the Webhook URL

Your production webhook URL will be:
```
https://kovaagent-production.up.railway.app/billing/webhook/stripe/
```

Use this URL when creating the live webhook endpoint in Step 6.2 / Step 9.4.

### Step 10.3: Verify Deployment

After Railway redeploys:
1. Visit `https://yourdomain.com/billing/pricing/`
2. Click subscribe on a plan — you should see the Stripe Checkout page
3. Check Railway logs for any errors
4. Check Stripe Dashboard → Webhooks → your endpoint — events should show as `Delivered`

---

## 11. Troubleshooting

### Common Issues

| Problem | Cause | Fix |
|---------|-------|-----|
| "No Stripe Price ID configured for plan" | Missing `STRIPE_PRICE_*` env var | Add the Price ID env vars (Step 7) |
| Webhook returns 400 | Invalid payload or signature mismatch | Check `STRIPE_WEBHOOK_SECRET` matches the endpoint |
| Webhook returns 500 | Handler error (check logs) | Check `BillingEvent` in admin for `error_message` |
| User plan doesn't update after checkout | Webhook not reaching Kova | Verify webhook URL is correct and accessible |
| "Invalid webhook signature" in logs | Wrong webhook secret or request body modified | Ensure `@csrf_exempt` is on the webhook view (already done) |
| Customer Portal shows no products | Products not added to portal settings | Go to Dashboard → Settings → Billing → Customer portal → Add products |
| Checkout redirects but nothing happens | Missing `stripe_customer_id` on profile | Check `get_or_create_customer()` runs — look at logs |
| Plan enforcement not working | Middleware not in `MIDDLEWARE` list | Verify `apps.billing.middleware.PlanEnforcementMiddleware` is in settings |

### Debugging Commands

**Check BillingEvents in Django shell:**
```python
python manage.py shell
from apps.billing.models import BillingEvent
BillingEvent.objects.all().order_by('-created_at')[:5]
```

**Check a user's subscription status:**
```python
from django.contrib.auth import get_user_model
User = get_user_model()
user = User.objects.get(email="test@example.com")
p = user.profile
print(f"Plan: {p.plan}")
print(f"Status: {p.subscription_status}")
print(f"Stripe Customer: {p.stripe_customer_id}")
print(f"Stripe Sub: {p.stripe_subscription_id}")
print(f"Trial ends: {p.trial_ends_at}")
print(f"Period end: {p.current_period_end}")
```

**Manually sync a subscription from Stripe:**
```python
from apps.billing.services import sync_subscription
sync_subscription(user)
```

### Stripe CLI Useful Commands

```powershell
# Login
stripe login

# Listen for all events
stripe listen --forward-to http://127.0.0.1:8000/billing/webhook/stripe/

# Listen for specific events only
stripe listen --events checkout.session.completed,invoice.paid,customer.subscription.updated,customer.subscription.deleted,invoice.payment_failed --forward-to http://127.0.0.1:8000/billing/webhook/stripe/

# Trigger a test event
stripe trigger checkout.session.completed
stripe trigger invoice.paid
stripe trigger invoice.payment_failed
stripe trigger customer.subscription.deleted

# List recent events
stripe events list --limit 5

# View a specific event
stripe events retrieve evt_123abc

# Check your Stripe config
stripe config --list
```

### Webhook Signature Verification Flow

```
1. Stripe sends POST to /billing/webhook/stripe/
2. Django view reads raw request.body (payload)
3. Django reads HTTP_STRIPE_SIGNATURE header
4. stripe.Webhook.construct_event(payload, sig_header, webhook_secret)
   → Verifies timestamp (prevents replay attacks — 5 min tolerance)
   → Verifies HMAC-SHA256 signature
   → Returns verified Event object
5. If verification fails → 400 response (logged as warning)
6. If verification succeeds → routes to EVENT_HANDLERS dict
7. Handler processes → saves BillingEvent → returns 200
```

> **Critical**: The `@csrf_exempt` decorator on the webhook view is required. Without it, Django's CSRF middleware would reject Stripe's POST requests (they don't have a CSRF token). This is safe because we verify the Stripe signature instead.

---

## Quick Reference Card

### Environment Variables Checklist

```
STRIPE_PUBLISHABLE_KEY=pk_test_...    # Client-side (safe to expose)
STRIPE_SECRET_KEY=sk_test_...         # Server-side ONLY (never expose)
STRIPE_WEBHOOK_SECRET=whsec_...       # Server-side ONLY (verify webhooks)
STRIPE_PRICE_STARTER=price_...        # Stripe Price ID for Starter plan
STRIPE_PRICE_GROWTH=price_...         # Stripe Price ID for Growth plan
STRIPE_PRICE_PRO=price_...            # Stripe Price ID for Pro plan
STRIPE_PRICE_AGENCY=price_...         # Stripe Price ID for Agency plan
```

### Kova Billing URLs

| URL | View | Purpose |
|-----|------|---------|
| `/billing/` | `billing_overview` | Current plan, usage, manage subscription |
| `/billing/pricing/` | `pricing` | Plan comparison for upgrading |
| `/billing/checkout/` | `checkout` | POST — creates Stripe Checkout Session |
| `/billing/checkout/success/` | `checkout_success` | Post-checkout redirect |
| `/billing/checkout/cancel/` | `checkout_cancel` | User canceled checkout |
| `/billing/portal/` | `portal` | Redirects to Stripe Customer Portal |
| `/billing/webhook/stripe/` | `stripe_webhook` | Stripe webhook endpoint |

### Test Cards Quick Reference

| Card | Result |
|------|--------|
| `4242 4242 4242 4242` | Payment succeeds |
| `4000 0025 0000 3155` | Requires 3D Secure authentication |
| `4000 0000 0000 9995` | Insufficient funds (declined) |
| `4000 0000 0000 0002` | Generic decline |
| `4000 0000 0000 0341` | Attaches to customer, but charges fail |

Use any future expiry date (e.g., `12/34`) and any 3-digit CVC (e.g., `123`).
