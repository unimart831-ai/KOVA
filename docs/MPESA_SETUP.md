# M-Pesa Daraja Setup Guide — Kova Agent

> Step-by-step guide to set up M-Pesa (Lipa Na M-Pesa Online / STK Push) for Kova Agent billing.

**Last updated:** March 31, 2026

---

## Table of Contents

1. [Overview — How M-Pesa Billing Works in Kova](#1-overview)
2. [Register on Safaricom Daraja Portal](#2-register-on-safaricom-daraja-portal)
3. [Create a Daraja App (Sandbox)](#3-create-a-daraja-app-sandbox)
4. [Get Your Sandbox Credentials](#4-get-your-sandbox-credentials)
5. [Configure Environment Variables](#5-configure-environment-variables)
6. [Set Up ngrok for Local Callback Testing](#6-set-up-ngrok-for-local-callback-testing)
7. [Test the Full Payment Flow Locally](#7-test-the-full-payment-flow-locally)
8. [Understanding the Code Architecture](#8-understanding-the-code-architecture)
9. [Go Live — Production Credentials](#9-go-live--production-credentials)
10. [Deploy to Railway](#10-deploy-to-railway)
11. [Subscription Lifecycle & Renewals](#11-subscription-lifecycle--renewals)
12. [Troubleshooting](#12-troubleshooting)

---

## 1. Overview

### How M-Pesa Billing Works in Kova

Unlike Stripe (which handles recurring billing automatically), M-Pesa uses a **manual subscription model**:

```
User clicks "Pay with M-Pesa"
  → Enters phone number (or uses saved number)
  → Kova sends STK Push to phone via Daraja API
  → User sees M-Pesa prompt on phone → enters PIN
  → Safaricom sends callback to Kova's webhook endpoint
  → Kova activates 30-day subscription
  → Daily Celery task checks for expiring subscriptions
  → 3 days before expiry: sends renewal reminder
  → If no renewal after 3-day grace period: downgrades to Starter
```

### Kova File Architecture (M-Pesa)

| File | Purpose |
|------|---------|
| `apps/billing/mpesa.py` | Daraja API client (auth, STK Push, callback parsing, phone formatting) |
| `apps/billing/mpesa_services.py` | Business logic (initiate checkout, process callback, activate/expire subscription, trials) |
| `apps/billing/views.py` | M-Pesa views (checkout, waiting page, status polling, success, webhook) |
| `apps/billing/models.py` | `MpesaPayment` model + `BillingEvent` audit trail + plan limits |
| `apps/billing/tasks.py` | Celery task: expire stale payments, warn before expiry, downgrade after grace period |
| `apps/billing/urls.py` | URL routes for all M-Pesa endpoints |
| `apps/accounts/models.py` | `UserProfile.mpesa_phone` + `UserProfile.payment_provider` fields |
| `config/settings/base.py` | All `MPESA_*` settings |
| `templates/billing/pricing.html` | M-Pesa checkout UI (phone input modal) |
| `templates/billing/mpesa_waiting.html` | HTMX polling page (waiting for PIN confirmation) |
| `templates/billing/mpesa_success.html` | Payment success page |

### Plan Tiers & KES Pricing

| Plan | Swahili Name | Price (KES) | Price (USD) | Platforms | Posts/month |
|------|-------------|-------------|-------------|-----------|-------------|
| Starter | Jipange | 99 | ~$1 | 1 | 15 |
| Growth | Kazi | 500 | ~$5 | 3 | 50 |
| Pro | Biashara | 1,500 | ~$15 | 10 | Unlimited |
| Agency | Wakala | 3,500 | ~$29 | 25 | Unlimited |

All plans include a **14-day free trial** (no M-Pesa payment required).

---

## 2. Register on Safaricom Daraja Portal

### Step 1: Go to the Daraja Developer Portal

**URL:** https://developer.safaricom.co.ke/

### Step 2: Create an Account

1. Click **"Sign Up"** (top right)
2. Fill in:
   - **First Name / Last Name**: Your legal name
   - **Email**: Use a business email (you'll receive API notifications here)
   - **Password**: At least 8 characters
3. Check your email → click the **verification link**
4. Log in to the portal

### Step 3: Complete Your Profile

After login:
1. Go to **Profile** → ensure your email and phone are verified
2. This is required before you can create apps or request Go Live

> **Note:** The Daraja sandbox is free for testing. No business registration required for sandbox. Production requires KYC (see [Section 9](#9-go-live--production-credentials)).

---

## 3. Create a Daraja App (Sandbox)

### Step 1: Create a New App

1. Log in to https://developer.safaricom.co.ke/
2. Click **"My Apps"** (top navigation)
3. Click **"Add a New App"**
4. Fill in:
   - **App Name**: `Kova Agent`
   - **Select Product(s)**: Check **"Lipa Na M-Pesa Sandbox"**
     - This is the STK Push product (customer-initiated payment prompt)
   - You can also check **"M-Pesa Sandbox"** for additional APIs (optional)
5. Click **"Create App"**

### Step 2: Note Your App Keys

After creation, you'll see your app with:
- **Consumer Key**: A long alphanumeric string (e.g., `Abc123def456...`)
- **Consumer Secret**: Another long string (e.g., `Xyz789ghi012...`)

> **⚠️ Keep these secret.** Never commit them to Git. They go in your `.env` file only.

---

## 4. Get Your Sandbox Credentials

The Daraja sandbox provides **pre-configured test credentials** that work with their simulated environment.

### Sandbox Test Credentials (Default)

These are provided by Safaricom for all sandbox apps:

| Credential | Value | Description |
|-----------|-------|-------------|
| **Business Shortcode** | `174379` | Test paybill number |
| **Passkey** | `bfb279f9aa9bdbcf158e97dd71a467cd2e0c893059b10f78e6b72ada1ed2c919` | Used to generate the API password |
| **Test Phone Number** | `254708374149` | Simulated M-Pesa customer number |

### Where to Find Them

1. Go to https://developer.safaricom.co.ke/
2. Click **"APIs"** → **"Lipa Na M-Pesa"**
3. Click **"Simulate"** tab
4. The test credentials are pre-filled on the simulation page

### Sandbox Behavior

- STK Push with the sandbox **always succeeds** (simulated confirmation)
- The callback fires automatically after a few seconds
- You can use any phone number in format `254XXXXXXXXX` (doesn't need to be real)
- No real money is charged

---

## 5. Configure Environment Variables

### Add to Your `.env` File

Open `kova_agent/.env` and add:

```env
# ─── M-Pesa Daraja ──────────────────────────────────────────────
MPESA_ENVIRONMENT=sandbox
MPESA_CONSUMER_KEY=your_consumer_key_from_daraja_app
MPESA_CONSUMER_SECRET=your_consumer_secret_from_daraja_app
MPESA_SHORTCODE=174379
MPESA_PASSKEY=bfb279f9aa9bdbcf158e97dd71a467cd2e0c893059b10f78e6b72ada1ed2c919
MPESA_CALLBACK_URL=https://your-ngrok-url.ngrok-free.app/billing/webhook/mpesa/
MPESA_TRIAL_DAYS=14
```

### Variable Reference

| Variable | Required | Description | Example |
|----------|----------|-------------|---------|
| `MPESA_ENVIRONMENT` | Yes | `sandbox` for testing, `production` for live | `sandbox` |
| `MPESA_CONSUMER_KEY` | Yes | From your Daraja app | `Abc123def456...` |
| `MPESA_CONSUMER_SECRET` | Yes | From your Daraja app | `Xyz789ghi012...` |
| `MPESA_SHORTCODE` | Yes | Business shortcode (paybill number) | `174379` (sandbox default) |
| `MPESA_PASSKEY` | Yes | Lipa Na M-Pesa passkey | `bfb279f9...` (sandbox default) |
| `MPESA_CALLBACK_URL` | Yes | Public URL where Daraja sends payment results | `https://xxxx.ngrok-free.app/billing/webhook/mpesa/` |
| `MPESA_TRIAL_DAYS` | No | Free trial length (default: 14) | `14` |

### How These Map to Django Settings

In `config/settings/base.py`:

```python
MPESA_ENVIRONMENT = env("MPESA_ENVIRONMENT", default="sandbox")
MPESA_CONSUMER_KEY = env("MPESA_CONSUMER_KEY", default="")
MPESA_CONSUMER_SECRET = env("MPESA_CONSUMER_SECRET", default="")
MPESA_SHORTCODE = env("MPESA_SHORTCODE", default="174379")
MPESA_PASSKEY = env("MPESA_PASSKEY", default="bfb279f9aa9bdbcf158e97dd71a467cd2e0c893059b10f78e6b72ada1ed2c919")
MPESA_CALLBACK_URL = env("MPESA_CALLBACK_URL", default="")
MPESA_TRIAL_DAYS = env.int("MPESA_TRIAL_DAYS", default=14)
```

---

## 6. Set Up ngrok for Local Callback Testing

M-Pesa's Daraja API sends payment results to a **callback URL**. This URL must be publicly accessible — `localhost` doesn't work. We use ngrok to create a public tunnel.

### Step 1: Install ngrok

**Option A — Download directly:**
1. Go to https://ngrok.com/download
2. Download the Windows version
3. Extract `ngrok.exe` to a folder in your PATH (e.g., `C:\tools\`)

**Option B — via Chocolatey:**
```powershell
choco install ngrok
```

**Option C — via Winget:**
```powershell
winget install ngrok.ngrok
```

### Step 2: Create a Free ngrok Account

1. Go to https://dashboard.ngrok.com/signup
2. Sign up (free plan is fine for development)
3. Go to **"Your Authtoken"** → copy the token
4. Run:
```powershell
ngrok config add-authtoken YOUR_AUTH_TOKEN
```

### Step 3: Start the Tunnel

Start your Django server first:
```powershell
cd kova_agent
python manage.py runserver
```

In a **separate terminal**, start ngrok:
```powershell
ngrok http 8000
```

You'll see output like:
```
Forwarding  https://a1b2-c3d4.ngrok-free.app → http://localhost:8000
```

### Step 4: Update Your Callback URL

Copy the `https://` URL from ngrok output and update your `.env`:

```env
MPESA_CALLBACK_URL=https://a1b2-c3d4.ngrok-free.app/billing/webhook/mpesa/
```

> **⚠️ Important:**
> - The ngrok URL changes every time you restart ngrok (free plan)
> - Always update `MPESA_CALLBACK_URL` in `.env` when the URL changes
> - Restart Django after changing `.env` to pick up the new URL
> - The callback path must be exactly `/billing/webhook/mpesa/` (matches `urls.py`)

### Step 5: Verify the Tunnel

Open your ngrok URL in a browser:
```
https://a1b2-c3d4.ngrok-free.app/
```
- If you see the Kova landing page → tunnel is working
- If you see an ngrok error page → check that Django is running on port 8000

---

## 7. Test the Full Payment Flow Locally

### Prerequisites Checklist

Before testing, confirm:
- [ ] Django server running (`python manage.py runserver`)
- [ ] ngrok tunnel running (`ngrok http 8000`)
- [ ] `.env` has all `MPESA_*` variables set
- [ ] `MPESA_CALLBACK_URL` matches your current ngrok URL
- [ ] Migrations applied (`python manage.py migrate`)
- [ ] You have a registered user account in Kova

### Test 1: Free Trial Activation

1. Log in to Kova
2. Go to **Billing → Pricing** (`/billing/pricing/`)
3. Click **"Start Free Trial"** on any plan
4. Enter phone number: `0712345678` (or any valid format)
5. Click **"Start Trial"**

**Expected result:**
- Redirects to success page
- Profile shows: Plan = selected tier, Status = Trialing, Expires in 14 days
- No M-Pesa prompt (trial is free)
- Check Django admin → UserProfile: `subscription_status=trialing`, `payment_provider=mpesa`

### Test 2: M-Pesa STK Push Payment

1. Log in (use a user whose trial has expired, or a fresh user)
2. Go to **Billing → Pricing** (`/billing/pricing/`)
3. Click **"Pay with M-Pesa"** on any plan
4. Enter phone: `254708374149` (sandbox test number)
5. Click **"Pay KES XXX via M-Pesa"**

**Expected flow:**
```
Step 1: Kova sends STK Push → you see the "Waiting for M-Pesa" page
Step 2: Page shows spinning animation + "Check your phone" message
Step 3: (Sandbox auto-confirms after ~5 seconds)
Step 4: Daraja sends callback to your ngrok URL → /billing/webhook/mpesa/
Step 5: HTMX polling detects completion → auto-redirects to success page
Step 6: Success page shows "Karibu sana! 🎉" with your plan details
```

**Verify in Django admin:**
- `MpesaPayment`: status=completed, receipt_number filled, subscription period set
- `BillingEvent`: event_type=mpesa.stk_callback, provider=mpesa
- `UserProfile`: plan=selected, subscription_status=active, payment_provider=mpesa

### Test 3: Check the ngrok Inspector

ngrok provides a web inspector at `http://localhost:4040`:
1. Open http://localhost:4040 in your browser
2. You'll see all HTTP traffic through the tunnel
3. Look for the `POST /billing/webhook/mpesa/` request
4. Click it to see the full callback payload from Daraja

The callback payload looks like this (on success):
```json
{
  "Body": {
    "stkCallback": {
      "MerchantRequestID": "29115-34620561-1",
      "CheckoutRequestID": "ws_CO_191220191020363925",
      "ResultCode": 0,
      "ResultDesc": "The service request is processed successfully.",
      "CallbackMetadata": {
        "Item": [
          { "Name": "Amount", "Value": 500.00 },
          { "Name": "MpesaReceiptNumber", "Value": "NLJ7RT61SV" },
          { "Name": "TransactionDate", "Value": 20191219102115 },
          { "Name": "PhoneNumber", "Value": 254708374149 }
        ]
      }
    }
  }
}
```

### Test 4: Phone Number Formats

Test that Kova correctly handles all Kenyan phone formats:

| Input | Formatted Output | Valid? |
|-------|-----------------|--------|
| `0712345678` | `254712345678` | ✅ |
| `+254712345678` | `254712345678` | ✅ |
| `254712345678` | `254712345678` | ✅ |
| `712345678` | `254712345678` | ✅ |
| `0712 345 678` | `254712345678` | ✅ (spaces stripped) |
| `0712-345-678` | `254712345678` | ✅ (dashes stripped) |
| `123456` | Error | ❌ (too short) |
| `0112345678` | Error | ❌ (not a mobile number starting with 07/7) |

### Test 5: Check Django Management Console

```powershell
cd kova_agent
python manage.py shell
```

```python
# Verify M-Pesa settings loaded
from django.conf import settings
print(settings.MPESA_ENVIRONMENT)       # → "sandbox"
print(settings.MPESA_SHORTCODE)         # → "174379"
print(bool(settings.MPESA_CONSUMER_KEY))  # → True
print(settings.MPESA_CALLBACK_URL)      # → "https://xxxx.ngrok-free.app/billing/webhook/mpesa/"

# Check M-Pesa payments
from apps.core.billing.models import MpesaPayment
MpesaPayment.objects.all()  # → list of payment records

# Test phone formatting
from apps.core.billing.mpesa import format_phone_number
format_phone_number("0712345678")   # → "254712345678"
format_phone_number("+254712345678")  # → "254712345678"
```

---

## 8. Understanding the Code Architecture

### The Payment Flow in Detail

```
┌──────────────────────────────────────────────────────────────────────┐
│ USER (Browser)                                                       │
│  1. Clicks "Pay with M-Pesa" → POST /billing/mpesa/checkout/        │
│  2. Sees waiting page → GET /billing/mpesa/waiting/                  │
│  3. HTMX polls every 3s → GET /billing/mpesa/status/                │
│  4. Auto-redirects on success → GET /billing/mpesa/success/          │
└──────────────┬────────────────────────────┬──────────────────────────┘
               │                            │
               │ (1) STK Push Request       │ (3) Poll Status
               │                            │
┌──────────────▼────────────────────────────▼──────────────────────────┐
│ KOVA SERVER (Django)                                                 │
│                                                                      │
│  mpesa_checkout() view:                                              │
│    → Validates phone number (format_phone_number)                    │
│    → Expires any existing pending payments                           │
│    → Calls initiate_stk_push() from mpesa.py                        │
│    → Creates MpesaPayment(status=pending)                            │
│    → Saves checkout_id in session                                    │
│    → Redirects to waiting page                                       │
│                                                                      │
│  mpesa_webhook() view (callback from Daraja):                        │
│    → Receives POST from Safaricom                                    │
│    → Calls process_mpesa_callback() from mpesa_services.py           │
│    → If success: MpesaPayment.status=completed + activate_sub()      │
│    → If failed: MpesaPayment.status=failed                           │
│    → Returns 200 OK to Safaricom                                     │
│                                                                      │
│  mpesa_check_status() view (HTMX polling):                           │
│    → Checks MpesaPayment.status for the session's checkout_id        │
│    → If completed: returns HX-Redirect header → success page         │
│    → If failed: returns error HTML inline                            │
│    → If pending: returns polling HTML (continues polling)             │
└──────────────┬───────────────────────────────────────────────────────┘
               │
               │ (1) STK Push API call
               │ (callback) POST to MPESA_CALLBACK_URL
               │
┌──────────────▼───────────────────────────────────────────────────────┐
│ SAFARICOM DARAJA API                                                 │
│                                                                      │
│  1. Receives STK Push request                                        │
│  2. Sends payment prompt to customer's phone                         │
│  3. Customer enters M-Pesa PIN                                       │
│  4. Sends callback to MPESA_CALLBACK_URL with result                 │
└──────────────────────────────────────────────────────────────────────┘
```

### Key Functions

| Function | File | What It Does |
|----------|------|--------------|
| `get_access_token()` | mpesa.py | Gets OAuth bearer token from Daraja (valid 1 hour) |
| `initiate_stk_push()` | mpesa.py | Sends the payment prompt to customer's phone |
| `query_stk_push()` | mpesa.py | Queries status of an STK transaction |
| `parse_stk_callback()` | mpesa.py | Parses Daraja's callback JSON into clean dict |
| `format_phone_number()` | mpesa.py | Normalizes any Kenyan phone format → `254XXXXXXXXX` |
| `initiate_mpesa_checkout()` | mpesa_services.py | Full checkout flow: validate → expire old → STK push → save record |
| `process_mpesa_callback()` | mpesa_services.py | Handle callback: find payment → activate subscription or mark failed |
| `activate_subscription()` | mpesa_services.py | Set plan, status, 30-day period on user profile |
| `activate_trial()` | mpesa_services.py | 14-day free trial (no payment needed) |
| `expire_subscription()` | mpesa_services.py | Downgrade to Starter plan after grace period |
| `check_mpesa_subscriptions()` | tasks.py | Daily Celery task: expire stale, warn, downgrade |

### URL Routes

| URL | View | Method | Purpose |
|-----|------|--------|---------|
| `/billing/mpesa/checkout/` | `mpesa_checkout` | POST | Initiate STK Push |
| `/billing/mpesa/waiting/` | `mpesa_waiting` | GET | Waiting page with HTMX polling |
| `/billing/mpesa/status/` | `mpesa_check_status` | GET | HTMX status check endpoint |
| `/billing/mpesa/success/` | `mpesa_success` | GET | Payment success page |
| `/billing/webhook/mpesa/` | `mpesa_webhook` | POST | Daraja callback endpoint (no auth, CSRF exempt) |

---

## 9. Go Live — Production Credentials

### Step 1: Apply for Production Access (Go Live)

1. Log in to https://developer.safaricom.co.ke/
2. Go to **"Go Live"** (in the navigation menu)
3. Fill in the application form:
   - **Organization Name**: Your registered business name
   - **Business Shortcode**: Your M-Pesa paybill or till number
     - If you don't have one, apply at the nearest Safaricom shop or via the Safaricom Business portal
   - **App**: Select your "Kova Agent" sandbox app
   - **API Products**: Select **"Lipa Na M-Pesa Online"** (STK Push)
4. Upload required documents:
   - **Business registration certificate** (CR12 or equivalent)
   - **KRA PIN certificate**
   - **Director's ID copy**
5. Submit the application

### Step 2: Wait for Approval

- Safaricom reviews your application (typically **2-5 business days**)
- You'll receive an email with:
  - **Production Consumer Key**
  - **Production Consumer Secret**
  - **Production Shortcode** (your actual paybill number)
  - **Production Passkey**
  - Confirmation of your callback URL whitelist

### Step 3: Update Environment Variables

Replace sandbox values with production credentials:

```env
MPESA_ENVIRONMENT=production
MPESA_CONSUMER_KEY=your_production_consumer_key
MPESA_CONSUMER_SECRET=your_production_consumer_secret
MPESA_SHORTCODE=your_actual_paybill_number
MPESA_PASSKEY=your_production_passkey
MPESA_CALLBACK_URL=https://kovaagent-production.up.railway.app/billing/webhook/mpesa/
```

### Step 4: Verify Production Works

1. Make a real KES 1 test payment (you can refund via M-Pesa)
2. Check that the callback arrives at your production URL
3. Verify the subscription activates correctly
4. Check Django admin for the payment record

### Go-Live Checklist

- [ ] Daraja Go Live approved
- [ ] Production credentials in environment variables
- [ ] `MPESA_ENVIRONMENT=production` (not `sandbox`)
- [ ] `MPESA_CALLBACK_URL` points to production domain (Railway URL)
- [ ] Railway environment variables updated
- [ ] Test transaction successful with real M-Pesa
- [ ] Payment receipt shows correct business name on customer's phone
- [ ] Subscription activates correctly after payment

---

## 10. Deploy to Railway

### Step 1: Add Environment Variables

1. Go to your Railway project dashboard
2. Click your Kova Agent service
3. Go to **Variables** tab
4. Click **"New Variable"** and add each one:

| Variable | Value |
|----------|-------|
| `MPESA_ENVIRONMENT` | `production` |
| `MPESA_CONSUMER_KEY` | Your production key |
| `MPESA_CONSUMER_SECRET` | Your production secret |
| `MPESA_SHORTCODE` | Your paybill number |
| `MPESA_PASSKEY` | Your production passkey |
| `MPESA_CALLBACK_URL` | `https://kovaagent-production.up.railway.app/billing/webhook/mpesa/` |
| `MPESA_TRIAL_DAYS` | `14` |

### Step 2: Verify Callback URL is Accessible

After deployment, test that the callback endpoint responds:

```powershell
# Should return 405 (Method Not Allowed) — because GET isn't allowed, only POST
curl -s -o /dev/null -w "%{http_code}" https://kovaagent-production.up.railway.app/billing/webhook/mpesa/
```

Expected: `405` (the endpoint exists but only accepts POST). If you get `404`, check your URL configuration.

### Step 3: Whitelist Callback URL on Daraja

For production, Safaricom may require you to whitelist your callback URL:
1. Log in to Daraja portal
2. Go to your production app settings
3. Add your Railway URL to the callback URL whitelist
4. Ensure HTTPS is used (Railway provides this automatically)

### Step 4: Verify Celery Beat Task

The `check_mpesa_subscriptions` task runs daily via Celery Beat. Ensure your Railway worker process is running:

```
# In your Procfile, the worker should be:
worker: celery -A config worker -l info -B
```

The `-B` flag runs Celery Beat in the same process (handles scheduling).

---

## 11. Subscription Lifecycle & Renewals

### Lifecycle States

```
┌──────────┐   Trial Start   ┌──────────┐   Payment   ┌──────────┐
│   none   │ ───────────────→ │ trialing │ ──────────→ │  active  │
└──────────┘                  └──────────┘             └──────────┘
                                    │                       │
                              Trial Expires          Sub Expires
                                    │                       │
                                    ▼                       ▼
                              ┌──────────┐           ┌──────────┐
                              │ canceled │           │ past_due │
                              └──────────┘           └──────────┘
                                                          │
                                                    3-Day Grace
                                                          │
                                                          ▼
                                                    ┌──────────┐
                                                    │ canceled │
                                                    └──────────┘
                                                    (→ Starter plan)
```

### What the Daily Celery Task Does

The `check_mpesa_subscriptions` task runs once per day and handles:

| Condition | Action |
|-----------|--------|
| Pending payment older than 5 minutes | Mark as `expired` (user didn't enter PIN) |
| Subscription expires in ≤ 3 days | Email + in-app notification via `send_mpesa_renewal_warning()` (once/day per tier) |
| Subscription expired (within 3-day grace) | Set status to `past_due` + renewal warning (days=0) |
| Subscription expired 3+ days ago | Downgrade to Starter plan (`canceled`) |

### Renewal Flow

M-Pesa doesn't auto-renew. Users must manually renew:

1. User sees "Your plan expires in X days" (notification / Daily Brief)
2. User goes to Billing → clicks "Renew"
3. Same STK Push flow as initial payment
4. On success: subscription extended by 30 days **from current expiry date** (not from payment date)

The smart renewal logic in `activate_subscription()`:
```python
# If renewing before expiry, extend from current end date (no lost days)
if payment.is_renewal and profile.current_period_end > now:
    period_start = profile.current_period_end  # extend from expiry
else:
    period_start = now  # fresh start

period_end = period_start + timedelta(days=30)
```

This means if a user renews 5 days before expiry, they get 30 + 5 = 35 days of service. No days are lost.

---

## 12. Troubleshooting

### Common Errors

| Error | Cause | Fix |
|-------|-------|-----|
| `M-Pesa auth failed: 400` | Invalid Consumer Key/Secret | Check `MPESA_CONSUMER_KEY` and `MPESA_CONSUMER_SECRET` in `.env` |
| `M-Pesa auth failed: 401` | Expired or revoked credentials | Re-generate credentials on Daraja portal |
| `STK Push failed: Bad Request - Invalid BusinessShortCode` | Wrong shortcode for environment | Sandbox: use `174379`. Production: use your actual paybill |
| `STK Push failed: The initiator information is invalid` | Wrong passkey | Check `MPESA_PASSKEY` matches your environment |
| `Callback never arrives` | ngrok not running or wrong callback URL | Verify ngrok is running, URL in `.env` is current, Django is running |
| `Callback arrives but payment not found` | Checkout ID mismatch | Check `MpesaPayment` records in Django admin |
| `Invalid Kenyan phone number` | Bad phone format | Must be 07XX, +254XX, 254XX, or 7XX format |
| `MPESA_CONSUMER_KEY not set` | Missing env variable | Add to `.env` and restart Django |
| `"M-Pesa service unavailable"` | Daraja API down or network issue | Check https://developer.safaricom.co.ke/status |

### Checking Logs

```powershell
# Django logs (look for M-Pesa entries)
cd kova_agent
python manage.py runserver
# Logs appear in terminal — look for lines containing "M-Pesa" or "mpesa"

# Check specific payment in Django shell
python manage.py shell
```

```python
from apps.core.billing.models import MpesaPayment

# Last 5 payments
for p in MpesaPayment.objects.all()[:5]:
    print(f"{p.user.email} | {p.amount} KES | {p.status} | {p.result_desc}")

# Check a specific checkout
p = MpesaPayment.objects.get(checkout_request_id="ws_CO_xxxx")
print(p.status, p.result_code, p.result_desc)
```

### Daraja API Status Codes

| ResultCode | Meaning | Action |
|-----------|---------|--------|
| `0` | Success | Activate subscription |
| `1` | Insufficient balance | Show "insufficient funds" to user |
| `1032` | Transaction cancelled by user | Show "cancelled" message |
| `1037` | Timeout — user didn't enter PIN | Expire payment, prompt to retry |
| `2001` | Wrong PIN entered | Show "incorrect PIN" message |
| `1001` | Unable to lock subscriber | Retry after a few moments |

### Useful Debug Commands

```powershell
# Test M-Pesa auth (in Django shell)
python manage.py shell -c "from apps.core.billing.mpesa import get_access_token; print(get_access_token()[:20] + '...')"

# Test phone formatting
python manage.py shell -c "from apps.core.billing.mpesa import format_phone_number; print(format_phone_number('0712345678'))"

# Check pending payments
python manage.py shell -c "from apps.core.billing.models import MpesaPayment; print(MpesaPayment.objects.filter(status='pending').count(), 'pending')"

# Manually run the subscription check task
python manage.py shell -c "from apps.core.billing.tasks import check_mpesa_subscriptions; print(check_mpesa_subscriptions())"
```

### ngrok Inspector

Always available at http://localhost:4040 when ngrok is running:
- See all incoming requests
- Inspect callback payloads
- Replay failed callbacks (useful for debugging)

---

## Quick Reference Card

```
SANDBOX:
  Portal:     https://developer.safaricom.co.ke/
  Auth URL:   https://sandbox.safaricom.co.ke/oauth/v1/generate
  STK Push:   https://sandbox.safaricom.co.ke/mpesa/stkpush/v1/processrequest
  Query:      https://sandbox.safaricom.co.ke/mpesa/stkpushquery/v1/query
  Shortcode:  174379
  Test Phone: 254708374149

PRODUCTION:
  Auth URL:   https://api.safaricom.co.ke/oauth/v1/generate
  STK Push:   https://api.safaricom.co.ke/mpesa/stkpush/v1/processrequest
  Query:      https://api.safaricom.co.ke/mpesa/stkpushquery/v1/query
  Shortcode:  Your paybill number
  Callback:   https://kovaagent-production.up.railway.app/billing/webhook/mpesa/

KOVA URLS:
  Pricing:    /billing/pricing/
  Checkout:   /billing/mpesa/checkout/       (POST)
  Waiting:    /billing/mpesa/waiting/        (GET)
  Status:     /billing/mpesa/status/         (GET — HTMX)
  Success:    /billing/mpesa/success/        (GET)
  Webhook:    /billing/webhook/mpesa/        (POST — Daraja callback)
  Overview:   /billing/                      (GET)
```

---

*This guide covers the complete M-Pesa integration for Kova Agent. Stripe billing remains available for future international expansion — both systems coexist.*
