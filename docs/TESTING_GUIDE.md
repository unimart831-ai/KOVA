# Kova — Full System Testing Guide

> Step-by-step manual QA checklist for all features implemented in the May 2026 overhaul.  
> Work through each section sequentially. Mark items ✅ as you confirm them.

---

## Prerequisites

- Application deployed and accessible at your production URL
- At least one test user account (or create fresh during onboarding tests)
- A phone number that can receive M-Pesa STK push (for commerce tests)
- Access to at least one social platform account (Instagram, Facebook, X, LinkedIn, or TikTok)
- Admin/superuser access for Control panel tests
- A second browser or incognito window for public-facing tests

---

## 1. Onboarding Flow

### 1.1 Fresh User Registration
- [ ] Navigate to the signup/registration page
- [ ] Register a new account with email and phone number
- [ ] Verify you're redirected to the onboarding flow (not the dashboard)

### 1.2 Choose Path Screen
- [ ] Confirm you see the "Choose Path" screen with a URL input field
- [ ] Verify helper text mentions both websites and social profiles
- [ ] Enter a **website URL** (e.g., `https://yoursite.com`) → should proceed to brand inference
- [ ] Go back and enter a **social profile URL** (e.g., `https://instagram.com/testbrand`) → should redirect to magic connect flow

### 1.3 Brand Inference (Website Path)
- [ ] After entering a website URL, confirm the "Read website" button appears
- [ ] Click it and verify the loading state shows (no "network error")
- [ ] Confirm brand details are populated (name, description, colors, etc.)
- [ ] If inference fails, verify a user-friendly error message appears (not a raw 500)
- [ ] Check the "Edit details" link works (should go to `/accounts/settings/`, not be blocked)

### 1.4 Magic Connect (Social Profile Path)
- [ ] Entering an Instagram/Facebook/X/LinkedIn URL should redirect to platform connection
- [ ] Verify the OAuth flow initiates correctly

### 1.5 Business Mode Detection
- [ ] During onboarding, confirm that business type detection occurs
- [ ] After completion, check your profile has a `business_mode` set (merchant/service/digital/expert)

### 1.6 Onboarding Completion
- [ ] Complete all onboarding steps
- [ ] Verify redirect to the main dashboard (Today tab)
- [ ] Confirm the onboarding middleware no longer blocks navigation

---

## 2. Navigation & Layout

### 2.1 Navigation Labels
- [ ] Confirm the 7 navigation tabs are visible: **Today**, **Workspace**, **Channels**, **Leads**, **Snap2sell**, **Reach**, **Control**
- [ ] Each tab should be clickable and route to the correct section
- [ ] On mobile: verify bottom navigation renders correctly and is tappable

### 2.2 Navigation Badges
- [ ] If you have items in content queue → verify badge count appears on **Workspace**
- [ ] If you have unread messages → verify badge on relevant tab
- [ ] Badges should update without full page reload (HTMX partial)

### 2.3 Toast Notifications
- [ ] Perform any action that triggers a Django message (e.g., save settings)
- [ ] Verify a toast notification appears (slides in from top-right)
- [ ] Toast should auto-dismiss after a few seconds
- [ ] Confirm no full page reload is needed to see the notification

### 2.4 Accessibility
- [ ] Tab through the interface using keyboard only — verify focus rings are visible
- [ ] Enable "Reduce Motion" in your OS settings → animations should be suppressed
- [ ] Check that skip-to-content link appears on focus (top of page)

---

## 3. Today (Daily Brief)

### 3.1 Daily Brief Display
- [ ] Navigate to **Today** tab
- [ ] Confirm today's brief is generated/displayed
- [ ] Verify sections: trends, suggestions, actionable items

### 3.2 Brief Actions (One-Click Seed)
- [ ] Find a suggestion/recommendation in the brief
- [ ] Click the "Create content" or seed action button
- [ ] Verify it creates a content draft in the Workspace queue
- [ ] Confirm a success toast appears

### 3.3 Brief Archive
- [ ] Navigate to the brief archive section (archive link/button)
- [ ] Verify past briefs are listed with dates
- [ ] Archive a brief → confirm it moves to the archive list
- [ ] Restore an archived brief → confirm it returns to main view

---

## 4. Workspace (Content Studio & Queue)

### 4.1 Content Queue
- [ ] Navigate to **Workspace** → Queue
- [ ] Verify content items are listed with status indicators
- [ ] Check that empty state shows an illustrated component with CTA (if no content exists)
- [ ] Loading state should show skeleton components (briefly visible on slow connections)

### 4.2 Visual Content Calendar
- [ ] Navigate to **Workspace** → Calendar (or calendar grid link)
- [ ] Verify a monthly grid is displayed
- [ ] Check that scheduled posts appear as colored dots on their respective days
- [ ] Use month navigation (← →) → verify HTMX loads next/previous month without full reload
- [ ] On mobile: verify compact view renders correctly
- [ ] Click a day with posts → verify post details are shown

### 4.3 Content Creation
- [ ] Create a new content piece from the studio
- [ ] Verify the AI agent assists with creation
- [ ] Schedule it for a future date → confirm it appears on the calendar

### 4.4 Content Views Split (Stability)
- [ ] Navigate between Queue, Calendar, Studio, Campaigns, and Autopilot sections
- [ ] Verify no 500 errors or broken imports (content views were refactored into modules)

---

## 5. Channels (Platform Connections)

### 5.1 Platform Connection
- [ ] Navigate to **Channels**
- [ ] Verify all supported platforms are listed (Instagram, Facebook, X, LinkedIn, TikTok, YouTube, Google Business, WhatsApp)
- [ ] Connect a platform via OAuth
- [ ] **Twitter/X specifically**: Verify OAuth completes without PKCE error (was previously broken)

### 5.2 Token Refresh
- [ ] If a platform shows "needs reconnection" → reconnect it
- [ ] Verify token expiry is displayed consistently (not showing raw timestamps)
- [ ] After reconnection, confirm the platform shows as active

### 5.3 Emergency Pause
- [ ] Navigate to **Control** → Settings → Danger Zone
- [ ] Click "Pause All Platforms" (emergency pause)
- [ ] Verify a **global banner** appears across the top of all pages
- [ ] Confirm no content is published while paused
- [ ] Unpause → verify banner disappears and operations resume

---

## 6. Leads

### 6.1 Leads Dashboard
- [ ] Navigate to **Leads** tab
- [ ] Verify leads are listed (or empty state with CTA if none exist)
- [ ] Check that lead source is tracked (WhatsApp, website, commerce, etc.)

### 6.2 Lead from Commerce
- [ ] After a commerce purchase (Section 8), verify the buyer appears as a lead
- [ ] Confirm phone number and interaction history are captured

---

## 7. Snap2sell (Batch Snap & Products)

### 7.1 Product Management
- [ ] Navigate to **Snap2sell**
- [ ] View your product catalog
- [ ] Verify products show correct `offering_type` (product/service/digital/expert)
- [ ] Check stock status indicators (IN_STOCK, LOW_STOCK, OUT_OF_STOCK)

### 7.2 Batch Snap Pipeline
- [ ] Start a new Batch Snap session
- [ ] Upload multiple product images
- [ ] Verify the AI pipeline processes them (status polling should work)
- [ ] Confirm products are created with auto-generated descriptions
- [ ] Check pipeline status endpoint responds (no 500 error)

### 7.3 Fulfillment-Aware Products
- [ ] Edit a product → verify `booking_link` field is available (for services)
- [ ] Edit a digital product → verify `fulfillment_url` field is available
- [ ] Save and confirm the fields persist

### 7.4 Commerce Links
- [ ] Open a product's public commerce link in an incognito window
- [ ] Verify the public page displays correctly with product details
- [ ] Verify price and buy button are visible

---

## 8. Commerce & M-Pesa Payment

### 8.1 Payment Initiation
- [ ] On a public commerce link, enter a phone number and click "Pay"
- [ ] Verify the STK push is sent to the phone
- [ ] Confirm the **polling UI** appears (Alpine.js state machine showing "Waiting for payment...")

### 8.2 Payment Status Polling
- [ ] While waiting, verify the UI polls the status endpoint (`/shop/payment/<id>/status/`)
- [ ] If payment completes → verify UI transitions to "Payment confirmed" state
- [ ] If payment times out → verify UI shows appropriate message

### 8.3 Idempotency & Race Conditions
- [ ] Try clicking "Pay" multiple times rapidly
- [ ] Verify only ONE STK push is sent (idempotency key prevents duplicates)
- [ ] Check that `transaction_ref` is generated correctly

### 8.4 Stock Decrement
- [ ] After successful payment on a product with limited stock
- [ ] Verify stock count decreases by the purchased quantity
- [ ] If stock reaches 0 → verify product status changes to OUT_OF_STOCK
- [ ] Verify a stock alert is created for the seller

### 8.5 Payment Expiry
- [ ] Leave a payment in "pending" state for the configured timeout period
- [ ] Verify it transitions to "expired" status (via Celery task `expire_stale_commerce_payments`)

---

## 9. Reach (Analytics)

### 9.1 Insights Dashboard
- [ ] Navigate to **Reach** tab
- [ ] Verify the insights dashboard loads
- [ ] Check for the **week-over-week engagement comparison** card
- [ ] Verify the CSS bar chart shows weekly trends

### 9.2 Recommendations
- [ ] Scroll to the recommendations section
- [ ] Verify AI-generated actionable recommendations are displayed
- [ ] Confirm they're contextual to your actual data (not generic placeholders)

### 9.3 Platform Analytics
- [ ] If connected platforms have data, verify metrics are pulling correctly
- [ ] Check that engagement metrics update (likes, shares, comments, reach)

---

## 10. Control (Admin & Settings)

### 10.1 User Settings
- [ ] Navigate to **Control** → Settings
- [ ] Edit profile details → save → verify toast confirmation
- [ ] Change business mode → verify it persists

### 10.2 Plan & Billing
- [ ] Check current plan is displayed correctly
- [ ] Verify plan limits match the tier (Starter/Growth/Pro)
- [ ] For Growth+ plans: verify Adapt v2 is accessible
- [ ] For Starter plans: verify Adapt v2 is gated with upgrade prompt

### 10.3 Admin Dashboard (Superuser Only)
- [ ] Log in as superuser
- [ ] Navigate to Django admin (`/admin/`)
- [ ] Verify the admin reflects all model changes:
  - `CommercePayment` shows `transaction_ref`, `attempts_count`, `status` (with expired)
  - `Product` shows `fulfillment_url`, `booking_link`, `offering_type`
  - `UserProfile` shows `business_mode`
  - `DailyBrief` shows `is_archived`
- [ ] Check `PlanPrice` model is manageable from admin

### 10.4 Emergency Pause (Admin)
- [ ] Toggle emergency pause from settings
- [ ] Verify global banner appears/disappears
- [ ] Confirm scheduled posts are held during pause

---

## 11. AI Agents

### 11.1 Segment-Aware Behavior
- [ ] As a **merchant** user: verify agents suggest product-focused content
- [ ] As a **service** user: verify agents suggest booking/appointment content
- [ ] As a **digital** user: verify agents suggest download/access content
- [ ] As an **expert** user: verify agents suggest thought-leadership content

### 11.2 Adapt Agent v2
- [ ] On a Growth+ plan: trigger content adaptation
- [ ] Verify Adapt v2 produces platform-specific variations
- [ ] On a Starter plan: verify you see an upgrade gate (not a crash)

### 11.3 Brand Builder (LLM JSON Parsing)
- [ ] Trigger brand inference during onboarding or settings
- [ ] Verify the AI response is parsed correctly (no JSON errors)
- [ ] If the AI returns malformed JSON → verify retry logic handles it gracefully

---

## 12. WhatsApp Integration

### 12.1 Message Processing
- [ ] Send a command via WhatsApp to your Kova number
- [ ] Verify the response is contextual and timely
- [ ] Check that WhatsApp interactions appear in leads/analytics

### 12.2 Seller Notifications
- [ ] Complete a commerce payment as a buyer
- [ ] Verify the seller receives a WhatsApp notification about the sale

---

## 13. UI/UX Components

### 13.1 Loading Skeletons
- [ ] Navigate between sections on a slower connection (throttle in DevTools)
- [ ] Verify skeleton loading states appear (card/table/list variants)
- [ ] Confirm they transition smoothly to actual content

### 13.2 Empty States
- [ ] View a section with no data (e.g., new user's leads page)
- [ ] Verify an illustrated empty state with a clear CTA appears
- [ ] Click the CTA → verify it routes to the correct creation flow

### 13.3 Form Validation (Client-Side)
- [ ] On any form with email field → enter invalid email → verify instant error
- [ ] On URL field → enter malformed URL → verify client-side validation fires
- [ ] On phone field → enter invalid phone → verify pattern check
- [ ] Submit valid data → verify no false validation blocks

### 13.4 Responsive Design
- [ ] Test on mobile viewport (375px width)
- [ ] Verify bottom navigation is functional
- [ ] Tables should have horizontal scroll wrappers
- [ ] Cards should stack vertically

---

## 14. Security & Stability

### 14.1 SSRF Protection
- [ ] Try to infer a brand from a private IP (e.g., `http://192.168.1.1`)
- [ ] Verify it's blocked with an appropriate error message
- [ ] Try `http://169.254.169.254` (metadata endpoint) → should be blocked

### 14.2 Database Connection Stability
- [ ] Monitor the application under load
- [ ] Verify no "too many clients" errors in logs
- [ ] Confirm connections are reused (CONN_MAX_AGE=600)

### 14.3 CONN_HEALTH_CHECKS
- [ ] After a period of inactivity, make a request
- [ ] Verify no stale connection errors (health check validates before use)

---

## 15. CI/CD Pipeline

### 15.1 Migration Check
- [ ] Push a code change with model modifications but no migration
- [ ] Verify CI fails with "Your models have changes not reflected in migrations"

### 15.2 Security Scanning
- [ ] Verify `pip-audit` runs in CI (checks for known vulnerabilities)
- [ ] Verify `bandit` runs in CI (checks for Python security issues)
- [ ] Both should pass on current codebase

---

## Troubleshooting

| Symptom | Likely Cause | Fix |
|---------|-------------|-----|
| "Network error" on onboarding | Middleware blocking API | Check `/accounts/api/` is in `ALLOWED_PREFIXES` |
| Payment stuck on "pending" | Celery worker not running | Verify Celery is processing `expire_stale_commerce_payments` |
| "Too many clients" | DB connection exhaustion | Check `CONN_MAX_AGE` is set; reduce worker count |
| OAuth fails for Twitter/X | PKCE code_verifier issue | Clear session, retry; verify `code_verifier` stored correctly |
| Toast not appearing | Alpine.js not loaded | Check `app.html` includes Alpine and toast dispatch |
| Calendar shows no posts | Content not scheduled | Create and schedule content for current month |
| Adapt v2 not working | Plan gate active | Upgrade to Growth+ plan or check `adapt_v2_enabled` flag |

---

## Test Completion Checklist

| Section | Status |
|---------|--------|
| 1. Onboarding | ⬜ |
| 2. Navigation & Layout | ⬜ |
| 3. Today (Daily Brief) | ⬜ |
| 4. Workspace | ⬜ |
| 5. Channels | ⬜ |
| 6. Leads | ⬜ |
| 7. Snap2sell | ⬜ |
| 8. Commerce & M-Pesa | ⬜ |
| 9. Reach (Analytics) | ⬜ |
| 10. Control | ⬜ |
| 11. AI Agents | ⬜ |
| 12. WhatsApp | ⬜ |
| 13. UI/UX Components | ⬜ |
| 14. Security & Stability | ⬜ |
| 15. CI/CD Pipeline | ⬜ |

---

*Last updated: May 29, 2026*
