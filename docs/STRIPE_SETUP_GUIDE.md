# ============================================================================
# STRIPE SETUP GUIDE — Kova Agent
# ============================================================================
# Complete guide to configuring Stripe billing for Kova Agent.
# Covers: Account creation, products, webhooks, local testing, and going live.
# Last Updated: March 30, 2026
# ============================================================================


## Table of Contents

1. [Create a Stripe Account](#1-create-a-stripe-account)
2. [Get Your API Keys](#2-get-your-api-keys)
3. [Create Products + Prices](#3-create-products--prices)
4. [Set Up the Webhook](#4-set-up-the-webhook)
5. [Set Environment Variables on Railway](#5-set-environment-variables-on-railway)
6. [Configure the Customer Portal](#6-configure-the-customer-portal)
7. [Test the Flow Locally](#7-test-the-flow-locally)
8. [Going Live (Real Payments)](#8-going-live-real-payments)
9. [Environment Variable Reference](#9-environment-variable-reference)
10. [Test Card Numbers](#10-test-card-numbers)
11. [Troubleshooting](#11-troubleshooting)


---


## 1. Create a Stripe Account

1. Go to **https://dashboard.stripe.com/register**
2. Enter your email, full name, and a password
3. Verify your email (check inbox for confirmation link)
4. You'll land on the **Stripe Dashboard**
5. You're now in **Test Mode** — look for the orange **"Test mode"** badge in the top-right corner
6. **Stay in test mode** until you're ready to charge real money


---


## 2. Get Your API Keys

API keys let your Django code talk to Stripe's servers.

1. In the Stripe Dashboard, click **Developers** (top-right area) → **API keys**
2. You'll see two keys:

| Key | Starts With | Purpose | Safe for Frontend? |
|-----|------------|---------|-------------------|
| **Publishable key** | `pk_test_...` | Identifies your account on the frontend | Yes |
| **Secret key** | `sk_test_...` | Authenticates server-side API calls | **NO — never expose** |

3. The publishable key is visible. For the secret key, click **"Reveal test key"**
4. **Copy both keys** somewhere safe (password manager, not a text file)
5. You'll use these in Step 5

> **SECURITY**: Never commit secret keys to git. Never put them in source code.
> They go in environment variables only.


---


## 3. Create Products + Prices

Kova Agent has 4 plan tiers. **Starter is free** — no Stripe product needed.
You need to create 3 Stripe products (one for each paid tier).

### Navigate to Product Catalog

Dashboard → **Product catalog** → click **+ Add product**

### Product 1: Kazi / Growth

| Field | Value |
|-------|-------|
| **Name** | `Kazi / Growth` |
| **Description** | `3 social accounts, 50 AI posts/month, 4 AI agents, engagement agent, email briefs` |

- Click **Add pricing**
  - **Pricing model**: Recurring
  - **Price**: `$19.00` USD
  - **Billing period**: Monthly
- Click **Save product**
- After saving, click into the product → scroll to **Pricing** section
- You'll see a **Price ID** like `price_1ABC123def456...`
- **Copy this Price ID** — this is your `STRIPE_PRICE_GROWTH`

### Product 2: Biashara / Pro

| Field | Value |
|-------|-------|
| **Name** | `Biashara / Pro` |
| **Description** | `10 social accounts, unlimited AI posts, all 6 agents, auto-approve publishing` |

- **Price**: `$49.00` USD / month
- Save → copy the **Price ID** → this is your `STRIPE_PRICE_PRO`

### Product 3: Wakala / Agency

| Field | Value |
|-------|-------|
| **Name** | `Wakala / Agency` |
| **Description** | `25 social accounts, multi-client dashboard, white-label reports, dedicated support` |

- **Price**: `$99.00` USD / month
- Save → copy the **Price ID** → this is your `STRIPE_PRICE_AGENCY`

### Optional: KES Pricing

To support Kenyan Shilling pricing (for the KES/USD toggle on the pricing page):

1. Click into each product
2. Click **+ Add another price**
3. Set currency to **KES** with the corresponding amount:
   - Growth: KSh 1,000 / month
   - Pro: KSh 2,500 / month
   - Agency: KSh 5,000 / month

> **Note**: For now, USD-only is fine to start. KES prices can be added later.

### After Creating All 3 Products

You should have 3 Price IDs that look like:
```
STRIPE_PRICE_GROWTH  = price_1PqRsT...
STRIPE_PRICE_PRO     = price_1UvWxY...
STRIPE_PRICE_AGENCY  = price_1AbCdE...
```

Keep these handy for Step 5.


---


## 4. Set Up the Webhook

Webhooks are how Stripe notifies your app about payment events (successful payments,
cancellations, failed charges, etc.). Your code already handles these at
`/billing/webhook/stripe/`.

### Create the Webhook Endpoint

1. Go to Dashboard → **Developers** → **Webhooks**
2. Click **+ Add endpoint**
3. **Endpoint URL**:
   - For Railway: `https://YOUR-APP.railway.app/billing/webhook/stripe/`
   - Replace `YOUR-APP` with your actual Railway subdomain
   - If you have a custom domain: `https://yourdomain.com/billing/webhook/stripe/`
4. **Select events to listen to** — click "Select events" and check exactly these 5:

| Event | What It Means | What Our Code Does |
|-------|--------------|-------------------|
| `checkout.session.completed` | User finished checkout | Syncs subscription to UserProfile |
| `customer.subscription.updated` | Plan change, renewal, trial end | Updates plan tier + status |
| `customer.subscription.deleted` | Subscription canceled/expired | Reverts user to Starter (free) |
| `invoice.paid` | Successful payment | Syncs subscription state |
| `invoice.payment_failed` | Card declined, insufficient funds | Sets status to `past_due` |

5. Click **Add endpoint**

### Get the Webhook Signing Secret

1. After creating the endpoint, you'll see its detail page
2. Click **Reveal signing secret**
3. It starts with `whsec_...`
4. **Copy this** — this is your `STRIPE_WEBHOOK_SECRET`

> **Why signing secrets matter**: Without this, anyone could send fake webhook
> requests to your endpoint and give themselves free subscriptions. The signing
> secret lets your code verify that webhooks really came from Stripe.


---


## 5. Set Environment Variables on Railway

1. Go to your **Railway dashboard** → select the Kova Agent service
2. Click the **Variables** tab
3. Add these 6 variables (plus 1 optional):

| Variable | Value | Example |
|----------|-------|---------|
| `STRIPE_SECRET_KEY` | Secret key from Step 2 | `sk_test_51ABC...` |
| `STRIPE_PUBLISHABLE_KEY` | Publishable key from Step 2 | `pk_test_51ABC...` |
| `STRIPE_PRICE_GROWTH` | Price ID for Growth plan | `price_1PqR...` |
| `STRIPE_PRICE_PRO` | Price ID for Pro plan | `price_1StU...` |
| `STRIPE_PRICE_AGENCY` | Price ID for Agency plan | `price_1VwX...` |
| `STRIPE_WEBHOOK_SECRET` | Webhook signing secret | `whsec_abc123...` |
| `STRIPE_PRICE_STARTER` | Leave empty string (free tier) | _(empty)_ |

4. Railway will **auto-redeploy** after you add/change variables
5. Wait for the deployment to finish (check the Deployments tab)

### Verify Deployment

After Railway redeploys:
1. Visit `https://YOUR-APP.railway.app/billing/pricing/` (logged in)
2. You should see the 4-tier pricing page
3. Click "Start free trial" on Growth — you should be redirected to Stripe Checkout


---


## 6. Configure the Customer Portal

The Customer Portal is a Stripe-hosted page where users can:
- View invoices and payment history
- Update their credit card
- Switch between plans (Growth ↔ Pro ↔ Agency)
- Cancel their subscription

Your code redirects to it from `/billing/portal/`.

### Set Up the Portal

1. Go to Dashboard → **Settings** → **Billing** → **Customer portal**
2. Configure these sections:

#### Invoice History
- ✅ **Enabled** — users can view and download invoices

#### Customer Information
- ✅ **Allow customers to update their email addresses**

#### Payment Methods
- ✅ **Allow customers to update their payment methods**

#### Subscriptions
- ✅ **Allow customers to switch plans**
  - Click **+ Add product** and add all 3 products: Growth, Pro, Agency
  - This enables upgrading/downgrading from within Stripe's portal
- ✅ **Allow customers to cancel subscriptions**

#### Cancellations
- Select **"At end of billing period"** (recommended)
  - This means when a user cancels, they keep access until their current billing period ends
  - Their subscription will then not renew

3. Click **Save**


---


## 7. Test the Flow Locally

For local development, webhooks can't reach `localhost` — you need the Stripe CLI
to forward them.

### 7.1 Install Stripe CLI

**Option A — Scoop (Windows)**:
```powershell
scoop install stripe
```

**Option B — Direct download**:
1. Go to https://github.com/stripe/stripe-cli/releases/latest
2. Download `stripe_X.X.X_windows_x86_64.zip`
3. Extract and add to your PATH

### 7.2 Login to Stripe CLI

```powershell
stripe login
```

- It opens a browser window — click "Allow access"
- Terminal shows "Done! The Stripe CLI is configured..."

### 7.3 Forward Webhooks to Localhost

In a **separate terminal** (keep it running while you develop):

```powershell
stripe listen --forward-to http://localhost:8000/billing/webhook/stripe/
```

Output will include:
```
> Ready! Your webhook signing secret is whsec_LOCAL123abc... (^C to quit)
```

**Copy this `whsec_...` value** — use it as your local webhook secret.

### 7.4 Set Local Environment Variables

Create or update your local `.env` file in the project root:

```env
STRIPE_SECRET_KEY=sk_test_...
STRIPE_PUBLISHABLE_KEY=pk_test_...
STRIPE_PRICE_GROWTH=price_...
STRIPE_PRICE_PRO=price_...
STRIPE_PRICE_AGENCY=price_...
STRIPE_WEBHOOK_SECRET=whsec_...
```

> **Important**: The `STRIPE_WEBHOOK_SECRET` for local testing (from `stripe listen`)
> is **different** from the one in Stripe Dashboard. Use the CLI one locally, the
> Dashboard one on Railway.

### 7.5 Test the Full Flow

1. Start Django:
   ```powershell
   python manage.py runserver
   ```

2. Go to `http://localhost:8000/billing/pricing/`

3. Click **"Start free trial"** on any paid plan (e.g., Growth)

4. You'll be redirected to **Stripe Checkout** — a Stripe-hosted payment page

5. Use test card number: `4242 4242 4242 4242`
   - Expiry: any future date (e.g., `12/30`)
   - CVC: any 3 digits (e.g., `123`)
   - Name and address: anything

6. Click **Subscribe** / **Start trial**

7. You'll be redirected to `/billing/checkout/success/`

8. Check your terminal running `stripe listen` — you'll see webhook events flowing:
   ```
   2026-03-30 10:00:00 --> checkout.session.completed [evt_1ABC...]
   2026-03-30 10:00:00 <-- [200] POST http://localhost:8000/billing/webhook/stripe/
   ```

9. Go to `/billing/` — you should see your plan updated to Growth with "trialing" status

10. Go to `/billing/portal/` — you should be redirected to Stripe's Customer Portal

### 7.6 Test Subscription Changes

In the Stripe Dashboard → **Customers** → find your test customer:

- **Cancel subscription**: Dashboard → Subscriptions → Cancel. Watch the webhook fire.
- **Simulate failed payment**: Use card `4000 0000 0000 0341` (attaches but fails on charge)
- **Advance trial**: In Stripe CLI: `stripe trigger customer.subscription.trial_will_end`


---


## 8. Going Live (Real Payments)

When you're ready for real money:

### 8.1 Activate Your Stripe Account

1. In Stripe Dashboard → click **"Activate payments"** or toggle off test mode
2. Fill in required business details:
   - Business name and address
   - Business type (individual/company)
   - Bank account or M-Pesa details for payouts
   - Tax ID (if applicable)

### 8.2 Create Live Products

Stripe keeps **test and live data completely separate**. You need to recreate:

1. Switch to **Live mode** (toggle at top-right of dashboard)
2. Create the same 3 products + prices in live mode (Growth, Pro, Agency)
3. Copy the new **live** Price IDs

### 8.3 Create Live Webhook

1. In live mode, go to Developers → Webhooks → + Add endpoint
2. Same URL, same 5 events as before
3. Copy the new **live** webhook signing secret

### 8.4 Update Railway Environment Variables

Replace ALL test values with live values:

| Variable | Change To |
|----------|-----------|
| `STRIPE_SECRET_KEY` | `sk_live_...` |
| `STRIPE_PUBLISHABLE_KEY` | `pk_live_...` |
| `STRIPE_PRICE_GROWTH` | Live price ID |
| `STRIPE_PRICE_PRO` | Live price ID |
| `STRIPE_PRICE_AGENCY` | Live price ID |
| `STRIPE_WEBHOOK_SECRET` | Live webhook secret |

### 8.5 Verify

1. Wait for Railway to redeploy
2. Do one real test purchase with your own card (you can refund it immediately)
3. Verify the webhook fires and user profile updates

> **Tip**: Keep test mode keys in your local `.env` for development.
> Only Railway production uses live keys.


---


## 9. Environment Variable Reference

How each variable is used in the Kova Agent codebase:

| Env Variable | Used In | Purpose |
|-------------|---------|---------|
| `STRIPE_SECRET_KEY` | `apps/billing/services.py` (line 22) | Authenticates all server-side Stripe API calls |
| `STRIPE_PUBLISHABLE_KEY` | `apps/billing/views.py` (billing_overview) | Passed to templates for potential frontend Stripe.js use |
| `STRIPE_PRICE_STARTER` | `apps/billing/services.py` (PLAN_PRICE_MAP) | Maps "starter" plan → Stripe Price (empty — free tier) |
| `STRIPE_PRICE_GROWTH` | `apps/billing/services.py` (PLAN_PRICE_MAP) | Maps "growth" plan → Stripe Price for checkout |
| `STRIPE_PRICE_PRO` | `apps/billing/services.py` (PLAN_PRICE_MAP) | Maps "pro" plan → Stripe Price for checkout |
| `STRIPE_PRICE_AGENCY` | `apps/billing/services.py` (PLAN_PRICE_MAP) | Maps "agency" plan → Stripe Price for checkout |
| `STRIPE_WEBHOOK_SECRET` | `apps/billing/views.py` (stripe_webhook) | Verifies webhook payloads are legitimately from Stripe |

### Where They're Defined in Settings

File: `config/settings/base.py` (lines 241-258)

```python
STRIPE_SECRET_KEY = env("STRIPE_SECRET_KEY", default="")
STRIPE_PUBLISHABLE_KEY = env("STRIPE_PUBLISHABLE_KEY", default="")
STRIPE_PRICE_STARTER = env("STRIPE_PRICE_STARTER", default="")
STRIPE_PRICE_GROWTH = env("STRIPE_PRICE_GROWTH", default="")
STRIPE_PRICE_PRO = env("STRIPE_PRICE_PRO", default="")
STRIPE_PRICE_AGENCY = env("STRIPE_PRICE_AGENCY", default="")
STRIPE_WEBHOOK_SECRET = env("STRIPE_WEBHOOK_SECRET", default="")
```


---


## 10. Test Card Numbers

Use these in **test mode** only. Stripe provides them for simulating different scenarios.

| Scenario | Card Number | What Happens |
|----------|-------------|-------------|
| **Successful payment** | `4242 4242 4242 4242` | Payment succeeds immediately |
| **Requires 3D Secure** | `4000 0025 0000 3155` | Shows authentication modal |
| **Card declined** | `4000 0000 0000 0002` | Generic decline |
| **Insufficient funds** | `4000 0000 0000 9995` | Decline: insufficient funds |
| **Expired card** | `4000 0000 0000 0069` | Decline: expired card |
| **Attaches but fails later** | `4000 0000 0000 0341` | Attaches to customer but first charge fails |

**For all test cards**:
- Expiry: any future date (e.g., `12/30`)
- CVC: any 3 digits (e.g., `123`)
- ZIP/Name: anything

Full list: https://docs.stripe.com/testing#cards


---


## 11. Troubleshooting

### "No Stripe Price ID configured for plan"
- **Cause**: The environment variable for that plan's price is empty
- **Fix**: Check Railway variables — make sure `STRIPE_PRICE_GROWTH`, `STRIPE_PRICE_PRO`, `STRIPE_PRICE_AGENCY` are all set with valid Price IDs

### Webhook returns 400 (Bad Request)
- **Cause**: Webhook signature verification failed
- **Fix**: Ensure `STRIPE_WEBHOOK_SECRET` matches the signing secret for the correct endpoint. Local (`stripe listen`) and production (Dashboard) have **different** secrets

### Webhook returns 500 (Server Error)
- **Cause**: `STRIPE_WEBHOOK_SECRET` is empty or not configured
- **Fix**: Set the environment variable on Railway

### User's plan doesn't update after checkout
- **Cause**: Webhook not reaching your server, or webhook secret mismatch
- **Debug**:
  1. Check Stripe Dashboard → Developers → Webhooks → click your endpoint → check "Attempts" tab
  2. If showing failures, check the response code and body
  3. Check Django logs on Railway for errors

### "Could not open billing portal"
- **Cause**: User doesn't have a Stripe customer ID yet
- **Fix**: User needs to go through checkout first, which creates the Stripe customer

### Customer Portal doesn't show plan switching
- **Cause**: Customer Portal not configured with your products
- **Fix**: Follow Step 6 — add all 3 products to the portal's subscription switching settings

### Webhooks work locally but not on Railway
- **Cause**: You're using the `stripe listen` webhook secret on Railway
- **Fix**: Railway needs the **Dashboard webhook** signing secret, not the CLI one. They're different.

### Trial period shows 14 days but I set 7
- **Note**: Our code uses 14-day trials (set in `apps/billing/services.py` in the `create_checkout_session` function). To change: update the `trial_period_days` value.


---


## Quick Checklist

Use this to verify everything is set up correctly:

- [ ] Stripe account created
- [ ] API keys copied (publishable + secret)
- [ ] Growth product created → Price ID copied
- [ ] Pro product created → Price ID copied
- [ ] Agency product created → Price ID copied
- [ ] Webhook endpoint added with 5 events selected
- [ ] Webhook signing secret copied
- [ ] All 6 env vars set on Railway
- [ ] Customer Portal configured (invoices, payment methods, plan switching, cancellation)
- [ ] Stripe CLI installed locally for testing
- [ ] Test checkout completed with `4242 4242 4242 4242`
- [ ] Webhook events confirmed flowing (check `stripe listen` output or Dashboard → Webhooks)
- [ ] User plan updates correctly after checkout
- [ ] Billing overview shows correct plan at `/billing/`
- [ ] Customer Portal accessible at `/billing/portal/`
