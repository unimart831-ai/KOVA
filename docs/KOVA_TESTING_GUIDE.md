# KOVA AI — Complete A-to-Z Testing Guide

> **Version:** 1.0 | **Last Updated:** April 2026
> **Comprehensive testing procedures for every Kova feature**

---

## Table of Contents

1. [Test Environment Setup](#1-test-environment-setup)
2. [Running Automated Tests](#2-running-automated-tests)
3. [Testing Accounts & Onboarding](#3-testing-accounts--onboarding)
4. [Testing Social Platform Connections](#4-testing-social-platform-connections)
5. [Testing Content Creation & Publishing](#5-testing-content-creation--publishing)
6. [Testing AI Agents](#6-testing-ai-agents)
7. [Testing Daily Briefings](#7-testing-daily-briefings)
8. [Testing WhatsApp Business Suite](#8-testing-whatsapp-business-suite)
9. [Testing Meme Intelligence Engine](#9-testing-meme-intelligence-engine)
10. [Testing Engagement & Community](#10-testing-engagement--community)
11. [Testing Analytics & Intelligence](#11-testing-analytics--intelligence)
12. [Testing Revenue Attribution & Kova Pixel](#12-testing-revenue-attribution--kova-pixel)
13. [Testing Competitor Intelligence](#13-testing-competitor-intelligence)
14. [Testing Media Queue](#14-testing-media-queue)
15. [Testing Campaigns](#15-testing-campaigns)
16. [Testing Email Marketing](#16-testing-email-marketing)
17. [Testing Product Catalog](#17-testing-product-catalog)
18. [Testing Lead Capture & CRM](#18-testing-lead-capture--crm)
19. [Testing Kova Pages (Link-in-Bio)](#19-testing-kova-pages-link-in-bio)
20. [Testing Teams & Collaboration](#20-testing-teams--collaboration)
21. [Testing Billing & Payments](#21-testing-billing--payments)
22. [Testing Notifications](#22-testing-notifications)
23. [Testing Help Center](#23-testing-help-center)
24. [Testing Growth Partners Program](#24-testing-growth-partners-program)
25. [Testing Admin Dashboard](#25-testing-admin-dashboard)
26. [Testing REST API](#26-testing-rest-api)
27. [Testing Celery Tasks](#27-testing-celery-tasks)
28. [Testing Webhooks](#28-testing-webhooks)
29. [Testing Middleware & Security](#29-testing-middleware--security)
30. [Testing Public Pages](#30-testing-public-pages)
31. [Automated Test Reference](#31-automated-test-reference)

---

## 1. Test Environment Setup

### Prerequisites

```bash
# 1. Activate virtual environment
cd A:\SYSTEMS_2026\SOCIAL_FUTURE
.venv\Scripts\activate

# 2. Navigate to project
cd kova_agent

# 3. Ensure development settings are active
set DJANGO_SETTINGS_MODULE=config.settings.development
```

### Development Settings (Key Differences from Production)

| Setting | Value | Why |
|---------|-------|-----|
| Database | SQLite | Fast local testing, no PostgreSQL needed |
| `CELERY_TASK_ALWAYS_EAGER` | `True` | Tasks run synchronously — no Redis/worker needed |
| `ACCOUNT_EMAIL_VERIFICATION` | `"none"` | No email verification required for testing |
| `ALLOWED_HOSTS` | Includes `"testserver"` | Pytest's test client works |
| Cache | In-memory | No Redis needed |
| Channels | In-memory | No Redis needed |

### Create a Test User

```bash
# Option 1: Via management command (superuser)
python manage.py createsuperuser --email admin@test.com

# Option 2: Via Django shell (regular user)
python manage.py shell
```

```python
from apps.accounts.models import User
user = User.objects.create_user(email='test@test.com', password='testpass123', full_name='Test User')
user.plan = 'agency'  # Set to highest plan to test all features
user.save()
```

### Start the Dev Server

```bash
python manage.py runserver
```

Then open: `http://127.0.0.1:8000/`

### Test Data Helpers

```python
# In Django shell — create test data for various features
from apps.accounts.models import User, UserProfile

user = User.objects.get(email='test@test.com')
profile = user.profile  # Auto-created

# Set up brand profile for AI features
profile.company_name = 'Test Company'
profile.industry = 'Technology'
profile.brand_voice = 'Professional but friendly, innovative, clear'
profile.content_pillars = ['tech tips', 'product updates', 'industry insights']
profile.save()
```

---

## 2. Running Automated Tests

### Run All Tests

```bash
pytest
```

### Run Specific Test Files

```bash
pytest tests/test_auth.py          # Authentication tests
pytest tests/test_accounts.py      # Account model tests
pytest tests/test_content.py       # Content model + view tests
pytest tests/test_billing.py       # Billing model tests
pytest tests/test_agents.py        # Agent model tests
```

### Run with Verbose Output

```bash
pytest -v                          # Verbose — show each test name
pytest -v --tb=long                # Long traceback on failures
pytest -s                          # Show print statements
```

### Run by Marker

```bash
pytest -m slow                     # Only slow-marked tests
pytest -m "not slow"               # Skip slow tests
```

### Existing Test Coverage

| Test File | Tests | Covers |
|-----------|:-----:|--------|
| `tests/conftest.py` | 5 fixtures | `user`, `staff_user`, `superuser`, `rf`, `auth_client` |
| `tests/test_auth.py` | 5 tests | Login redirect, valid/invalid login, `@superuser_required`, `@senior_staff_required` |
| `tests/test_accounts.py` | 8 tests | User CRUD, `__str__`, `first_initial`, soft delete/restore, UserProfile, encrypted fields |
| `tests/test_content.py` | 10 tests | ContentSeed/Post CRUD, scheduling, media status, edit distance, studio view |
| `tests/test_billing.py` | 5 tests | BillingEvent, MpesaPayment PROTECT, PLAN_LIMITS dict |
| `tests/test_agents.py` | 5 tests | AgentConfig types/unique, AgentAction logging/outcome, composite indexes |

### Test Fixtures (conftest.py)

```python
# Available fixtures for all tests:
@pytest.fixture
def user()          # Regular user (email: 'tester@kova.co.ke', plan: 'starter')
@pytest.fixture
def staff_user()    # Staff user (is_staff=True)
@pytest.fixture
def superuser()     # Superuser (is_superuser=True)
@pytest.fixture
def rf()            # Django RequestFactory
@pytest.fixture
def auth_client()   # Logged-in test client (returns the user too)
```

---

## 3. Testing Accounts & Onboarding

### 3.1 Registration

| # | Test | Steps | Expected Result |
|---|------|-------|-----------------|
| 1 | Sign up with valid email | Go to `/accounts/signup/` → fill email + password + phone → submit | Account created, redirected to `/accounts/onboarding/start/` |
| 2 | Sign up with existing email | Try to register with an email that already exists | Error: "A user is already registered with this e-mail address" |
| 3 | Sign up with weak password | Use password like "123" | Validation error — password too short/common |
| 4 | UserProfile auto-creation | After signup, check `user.profile` exists | UserProfile created with default values |

### 3.2 Login / Logout

| # | Test | Steps | Expected Result |
|---|------|-------|-----------------|
| 1 | Login with valid credentials | Go to `/accounts/login/` → enter email + password | Redirected to `/brief/` (LOGIN_REDIRECT_URL) |
| 2 | Login with wrong password | Enter correct email, wrong password | Error: "The email address and/or password you specified are not correct" |
| 3 | Login with non-existent email | Enter unknown email | Same generic error (no email enumeration) |
| 4 | Logout | Click logout | Redirected to `/` (LOGOUT_REDIRECT_URL) |
| 5 | Access protected page while logged out | Go to `/content/studio/` without logging in | Redirected to `/accounts/login/?next=/content/studio/` |

### 3.3 Express Onboarding (Kova Express)

| # | Test | Steps | Expected Result |
|---|------|-------|-----------------|
| 1 | Phone required | Sign up without phone, or OAuth login without phone on file | Redirect to `/accounts/onboarding/phone/` before wizard |
| 2 | Platform connect blocked | User without phone tries `/platforms/connect/instagram/` | Redirect to `/accounts/onboarding/phone/` |
| 3 | Path choice | After phone, open `/accounts/onboarding/start/` | Intent screen: sell / grow / both + optional link |
| 4 | Step 1 — Basics | Fill business name, industry → next | Saved to UserProfile; magic fill if link provided |
| 5 | Step 2 — Confirm brand | Review preview card → "Looks good — start my agency" | Onboarding marked complete; agency chain starts |
| 6 | Commerce redirect | User chose sell or ecommerce industry | After completion, lands on `/products/snap/?completed=1` |
| 7 | Grow redirect | User chose grow intent | After completion, lands on Content Studio |
| 8 | OAuth mid-flow | Connect platform during Step 1 | Callback returns to `/accounts/onboarding/?step=2` |
| 9 | Platform connect optional | Finish onboarding without connecting | No blocker; connect anytime from `/platforms/` |
| 10 | Check progress endpoint | `GET /accounts/onboarding/progress/` | Returns JSON with completed steps |

### 3.4 User Settings

| # | Test | URL | Steps | Expected Result |
|---|------|-----|-------|-----------------|
| 1 | Update profile | `/accounts/settings/` | Change full name, timezone → save | Settings saved, success message |
| 2 | Update brand profile | `/accounts/settings/` | Change company name, brand voice, tone, pillars → save | UserProfile updated |
| 3 | CTA settings | `/accounts/settings/cta/` | Set default CTA text and URL → save | Defaults applied to new posts |
| 4 | Emergency pause | `/accounts/settings/emergency-pause/` | Click emergency pause | All scheduled posts paused, agents deactivated |

### 3.5 AI Brand Builder

| # | Test | URL | Steps | Expected Result |
|---|------|-----|-------|-----------------|
| 1 | AI brand analysis | `/accounts/api/ai-brand-builder/` | POST with website URL or description | Returns AI-generated brand voice, tone, pillars |
| 2 | Apply AI suggestions | Accept AI brand builder output | Brand profile fields populated |

---

## 4. Testing Social Platform Connections

### 4.1 Platform List

| # | Test | URL | Expected Result |
|---|------|-----|-----------------|
| 1 | View platforms page | `/platforms/` | Shows all 10 platforms with connect/disconnect buttons |
| 2 | Plan limit enforcement | Connect more accounts than plan allows | Error message about plan limit |

### 4.2 OAuth Connection Flow (Per Platform)

Test each of the 10 platforms:

| # | Platform | Connect URL | Callback URL | Special Notes |
|---|----------|------------|--------------|---------------|
| 1 | Twitter | `/platforms/connect/twitter/` | `/platforms/callback/twitter/` | OAuth 2.0 PKCE |
| 2 | LinkedIn | `/platforms/connect/linkedin/` | `/platforms/callback/linkedin/` | Then select page at `/platforms/linkedin/select-page/` |
| 3 | Instagram | `/platforms/connect/instagram/` | `/platforms/callback/instagram/` | Via Facebook OAuth → Instagram Graph API |
| 4 | Facebook | `/platforms/connect/facebook/` | `/platforms/callback/facebook/` | Page token exchange |
| 5 | TikTok | `/platforms/connect/tiktok/` | `/platforms/callback/tiktok/` | OAuth 2.0 |
| 6 | YouTube | `/platforms/connect/youtube/` | `/platforms/callback/youtube/` | OAuth 2.0 |
| 7 | Pinterest | `/platforms/connect/pinterest/` | `/platforms/callback/pinterest/` | OAuth 2.0 |
| 8 | Threads | `/platforms/connect/threads/` | `/platforms/callback/threads/` | Meta OAuth |
| 9 | Bluesky | `/platforms/connect/bluesky/` | `/platforms/callback/bluesky/` | App Password (not OAuth) |
| 10 | WhatsApp | `/platforms/connect/whatsapp/` | `/platforms/callback/whatsapp/` | Permanent access token |

### 4.3 Connection Tests

| # | Test | Steps | Expected Result |
|---|------|-------|-----------------|
| 1 | Successful connect | Complete OAuth flow | SocialAccount created, `is_active=True`, tokens encrypted |
| 2 | Cancel OAuth | Cancel on platform's OAuth screen | Redirected back with error message, no account created |
| 3 | Disconnect account | Click disconnect on `/platforms/` | `POST /platforms/disconnect/<uuid>/` → account deactivated |
| 4 | Reconnect after disconnect | Re-connect the same platform account | Account reactivated, tokens refreshed |
| 5 | Token stored encrypted | Check DB: `SocialAccount.access_token` | Value is Fernet-encrypted (not plaintext) |

### 4.4 Token Refresh

| # | Test | Steps | Expected Result |
|---|------|-------|-----------------|
| 1 | Auto-refresh | Token nearing expiry (within 24h) | `refresh_expiring_tokens` task refreshes it |
| 2 | 3-strike deactivation | Simulate 3 consecutive API failures | `SocialAccount.is_active` becomes `False`, user notified |

---

## 5. Testing Content Creation & Publishing

### 5.1 Content Studio

| # | Test | URL | Steps | Expected Result |
|---|------|-----|-------|-----------------|
| 1 | View studio | `/content/studio/` | Navigate to studio | Shows content hub with seeds and posts |
| 2 | Filter posts | `/content/studio/posts/` | Use status/platform filters | Filtered results returned (HTMX) |

### 5.2 Content Seeds

| # | Test | URL | Steps | Expected Result |
|---|------|-----|-------|-----------------|
| 1 | Create seed | `/content/studio/submit/` | Fill topic, notes, select platforms → submit | Seed created, status changes to `generating` |
| 2 | Seed plan limit | Exceed monthly seed limit for plan | Submit seed | Error: plan limit reached |
| 3 | Voice-to-seed | `/content/studio/voice/` | Submit voice memo or text | Seed created from voice input |
| 4 | Check seed status | `/content/studio/seed/<uuid>/status/` | Poll status | Returns current status (generating/completed/failed) |
| 5 | Batch approve | `/content/studio/seed/<uuid>/batch-approve/` | Click batch approve | All draft posts from seed → approved |
| 6 | Dismiss failed | `/content/studio/dismiss-failed/` | Click dismiss | Failed seeds cleared from view |

### 5.3 Post Management

| # | Test | URL | Steps | Expected Result |
|---|------|-----|-------|-----------------|
| 1 | View post detail | `/content/<uuid>/` | Click on a post | Full post detail with content, media, metadata |
| 2 | Edit post | `/content/<uuid>/edit/` | Change content_text, CTA, hashtags → save | Post updated |
| 3 | Approve post | `/content/<uuid>/approve/` | POST | Status: `draft` → `approved` |
| 4 | Reject post | `/content/<uuid>/reject/` | POST | Status → `rejected` |
| 5 | Delete post | `/content/<uuid>/delete/` | POST | Post deleted |
| 6 | Regenerate post | `/content/<uuid>/regenerate/` | POST | AI regenerates content, check status at `/content/<uuid>/regenerate/status/` |
| 7 | Preview post | `/content/<uuid>/preview/` | GET | Shows platform-specific preview |
| 8 | Rate post | `/content/<uuid>/rate/` | POST with rating | Rating saved |
| 9 | Post plan limit | Exceed monthly post limit | Try to approve/schedule | Error: plan limit reached |

### 5.4 Media Management

| # | Test | URL | Steps | Expected Result |
|---|------|-----|-------|-----------------|
| 1 | Upload media | `/content/<uuid>/upload/` | Upload image/video | Media attached, EXIF stripped from images |
| 2 | Card upload | `/content/<uuid>/card-upload/` | Upload via card UI | Same as above, HTMX response |
| 3 | Delete media | `/content/<uuid>/media/<media_uuid>/delete/` | POST | Media removed from post |
| 4 | Clear AI media | `/content/<uuid>/clear-media/` | POST | AI-generated media cleared |
| 5 | Generate AI image | `/content/<uuid>/generate-image/` | POST | AI image generated (plan-gated) |
| 6 | Retry image | `/content/<uuid>/retry-image/` | POST | Retry failed image generation |
| 7 | EXIF stripping | Upload a photo with GPS data | Check stored file | GPS/location metadata removed |

### 5.5 Scheduling

| # | Test | Steps | Expected Result |
|---|------|-------|-----------------|
| 1 | Schedule — post_now | Select "Post Now" intent | Post published immediately (status → publishing → published) |
| 2 | Schedule — next_best | Select "Next Best Time" | AI picks optimal slot, post status → scheduled |
| 3 | Schedule — smart_queue | Select "Smart Queue" | Posts distributed across optimal slots |
| 4 | Schedule — quick | Select "30 min" / "1 hour" / "3 hours" / "tomorrow" | Post scheduled at relative time |
| 5 | Schedule — exact | Pick exact date/time | Post scheduled for that exact time |
| 6 | Auto-publish | Wait for scheduled time (or trigger `check_and_publish_due_posts` task) | Post published to platform, `platform_post_id` set |
| 7 | Publish failure | Simulate platform API failure | Status → `failed`, notification created |

### 5.6 Content Queue & Calendar

| # | Test | URL | Expected Result |
|---|------|-----|-----------------|
| 1 | View queue | `/content/queue/` | All scheduled posts in chronological order |
| 2 | View calendar | `/content/calendar/` | Visual calendar view of scheduled content |

### 5.7 A/B Testing

| # | Test | URL | Steps | Expected Result |
|---|------|-----|-------|-----------------|
| 1 | List A/B tests | `/content/ab-tests/` | Navigate | Shows all tests with status |
| 2 | Create A/B test | `/content/ab-tests/create/` | Select post, submit | AI generates variant, ABTest created |
| 3 | View test detail | `/content/ab-tests/<uuid>/` | Click test | Shows control vs variant with metrics |
| 4 | Start test | `/content/ab-tests/<uuid>/start/` | POST | Both posts published, test status → running |
| 5 | Conclude test | `/content/ab-tests/<uuid>/conclude/` | POST | Winner determined, test status → completed |
| 6 | Cancel test | `/content/ab-tests/<uuid>/cancel/` | POST | Test cancelled |
| 7 | Plan gate | Starter plan user tries to create test | Error: A/B testing requires Growth+ |
| 8 | Auto-evaluation | Wait for `evaluate_ab_tests` task (hourly) | Running tests evaluated for winner |

---

## 6. Testing AI Agents

### 6.1 Agent Control Center

| # | Test | URL | Steps | Expected Result |
|---|------|-----|-------|-----------------|
| 1 | View control center | `/agents/` | Navigate | Shows all 6 agents with status |
| 2 | Agent plan gating | Starter user views agents | Only Create + Analyst available |
| 3 | View agent detail | `/agents/<slug>/` | Click agent (e.g., `/agents/research/`) | Agent detail with config |
| 4 | Toggle agent | `/agents/<slug>/toggle/` | POST | Agent enabled/disabled |
| 5 | Check agent status | `/agents/<slug>/status/` | GET | Returns current status (HTMX) |
| 6 | Update instructions | `/agents/<slug>/instructions/` | POST with custom instructions | Instructions saved to AgentConfig |
| 7 | View activity log | `/agents/activity/` | Navigate | Shows all agent actions |
| 8 | View strategist | `/agents/strategist/` | Navigate | Strategist dashboard with strategy history |

### 6.2 Research Agent

| # | Test | Steps | Expected Result |
|---|------|-------|-----------------|
| 1 | Manual trigger | Via Django shell: `from apps.agents.research_agent import discover_trends; discover_trends(user)` | Returns trending topics for user's industry |
| 2 | Content angles | `generate_content_angles(user, 'AI in marketing')` | Returns specific content angle suggestions |
| 3 | Plan gating | Starter user | Research Agent not available |
| 4 | Task execution | Trigger `run_daily_research` Celery task | Trends discovered for all eligible users |

### 6.3 Create Agent

| # | Test | Steps | Expected Result |
|---|------|-------|-----------------|
| 1 | Generate from seed | Create seed → trigger generation | Posts created for each target platform |
| 2 | Regenerate post | `regenerate_single_post(post)` | New content generated for the post |
| 3 | Repurpose post | `repurpose_post(post, ['linkedin', 'twitter'])` | New posts created for target platforms |
| 4 | Brand voice | Check generated content | Matches user's brand voice and tone |
| 5 | Platform adaptation | Compare posts across platforms | Twitter: shorter with hashtags, LinkedIn: professional, etc. |

### 6.4 Adapt Agent

| # | Test | Steps | Expected Result |
|---|------|-------|-----------------|
| 1 | Suggest times | `suggest_optimal_times(user)` | Returns optimal posting times per platform |
| 2 | Auto-schedule | `auto_schedule_post(post)` | Post scheduled to AI-picked optimal time |

### 6.5 Engage Agent

| # | Test | Steps | Expected Result |
|---|------|-------|-----------------|
| 1 | Full engage cycle | Trigger `run_engage_cycle` task | Interactions fetched, analyzed, replies generated |
| 2 | Fetch interactions | `fetch_interactions(user)` | Comments/mentions pulled from platforms |
| 3 | Generate replies | `generate_replies(user)` | AI replies generated in brand voice |
| 4 | Auto-respond threshold | Set confidence > 0.8 | Reply auto-sent |
| 5 | Draft threshold | Confidence 0.5-0.8 | Reply saved as draft |
| 6 | Escalation | Confidence < 0.5 | Conversation flagged for human |

### 6.6 Analyst Agent

| # | Test | Steps | Expected Result |
|---|------|-------|-----------------|
| 1 | Performance analysis | `analyze_performance(user, days=30)` | AI analysis of post performance |
| 2 | Content DNA extraction | `extract_content_dna(post)` | Returns: format, hook, tone, CTA, emotion, length |
| 3 | Engagement prediction | `predict_engagement(post)` | Returns score 0-100 |
| 4 | Prediction validation | After publishing, `validate_prediction(post)` | Compares predicted vs actual, stores error |
| 5 | A/B test evaluation | `evaluate_ab_test(ab_test)` | Winner determined with confidence level |

### 6.7 Strategist Agent

| # | Test | Steps | Expected Result |
|---|------|-------|-----------------|
| 1 | Strategy cycle | Trigger `run_strategy_cycle` task | Full cycle: gather → decide → create seeds |
| 2 | Growth correlation | `_get_content_growth_correlation(user, 30)` | Correlates content types with follower growth |
| 3 | Revenue signals | `_get_revenue_signals(user, 30)` | Identifies revenue-driving content patterns |

### 6.8 Memory & Learning

| # | Test | Steps | Expected Result |
|---|------|-------|-----------------|
| 1 | Edit tracking | Edit AI-generated post, then check `record_edit_feedback(post)` | Edit patterns recorded |
| 2 | Prediction accuracy | `get_prediction_accuracy(user, 30)` | Returns accuracy stats |
| 3 | Learning context | `get_agent_learning_context(user, 'create', 'generate')` | Returns past outcomes for prompt injection |
| 4 | User edit patterns | `get_user_edit_patterns(user, 30)` | Shows what users typically change |

### 6.9 LLM Integration

| # | Test | Steps | Expected Result |
|---|------|-------|-----------------|
| 1 | Model resolution | `get_model_for_task('create.generate', 'pro', user)` | Returns correct model for task+plan |
| 2 | Generate call | `generate(prompt='Hello', system='Be brief')` | Returns `LLMResponse` with content |
| 3 | JSON parsing | `parse_llm_json('```json\n{"key": "value"}\n```')` | Successfully parses despite fences |
| 4 | Truncated JSON repair | `parse_llm_json('{"posts": [{"title": "A"}, {"title":')` | Repairs and returns complete objects |
| 5 | Fallback chain | Block primary model, check logs | Falls back to next model in chain |

### 6.10 AI Image Generation

| # | Test | Steps | Expected Result |
|---|------|-------|-----------------|
| 1 | Generate image | POST to `/content/<uuid>/generate-image/` | Image generated via FLUX.1-schnell |
| 2 | Provider fallback | Primary provider fails | Falls back: Together → HuggingFace → Pollinations |
| 3 | Plan gating | Starter user tries to generate | Error: image generation not available on Starter |
| 4 | Monthly limit | Exceed plan's monthly image limit | Error: monthly limit reached |

---

## 7. Testing Daily Briefings

| # | Test | URL | Steps | Expected Result |
|---|------|-----|-------|-----------------|
| 1 | View brief | `/brief/` | Navigate (logged in) | Today's brief displayed with all sections |
| 2 | Brief auto-generation | Trigger `generate_all_daily_briefs` task | Brief created for user |
| 3 | Brief mark read | Visit `/brief/` | `is_read` set to `True` |
| 4 | Past briefs | `/brief/` | Scroll down | 7 recent past briefs visible |
| 5 | Quick stats | `/brief/` | Check stats section | Published today, failed, scheduled counts accurate |
| 6 | Superfans section | `/brief/` | Check superfans | Top 5 superfans displayed |
| 7 | Setup checklist | New user within first 14 days | Checklist shown: connect platform, set voice, publish, read brief |
| 8 | Value summary | `/brief/` | Check weekly summary | "What Kova did this week" with real counts |
| 9 | Platform nudge | User with no connected platforms | "Connect a platform" nudge displayed |

---

## 8. Testing WhatsApp Business Suite

### 8.1 WhatsApp Inbox

| # | Test | URL | Steps | Expected Result |
|---|------|-----|-------|-----------------|
| 1 | View inbox | `/whatsapp/` | Navigate | Conversations listed with filters |
| 2 | View conversation | `/whatsapp/conversation/<uuid>/` | Click conversation | Full message thread displayed |
| 3 | Send message | `/whatsapp/conversation/<uuid>/send/` | Type message → send (POST) | Message sent to contact |
| 4 | Toggle AI | `/whatsapp/conversation/<uuid>/toggle-ai/` | POST | AI auto-reply toggled on/off |
| 5 | Plan gating | Starter/Growth user | WhatsApp features blocked |
| 6 | Language detection | Send message in Swahili/Sheng | Language detected and noted on conversation |
| 7 | 24-hour window | Check `window_expires_at` | Cannot send templated-only after window expires |

### 8.2 WhatsApp Webhook

| # | Test | URL | Steps | Expected Result |
|---|------|-----|-------|-----------------|
| 1 | Webhook verification | `GET /whatsapp/webhook/?hub.mode=subscribe&hub.verify_token=<token>&hub.challenge=<challenge>` | Returns challenge value |
| 2 | Incoming message | `POST /whatsapp/webhook/` with valid payload + signature | Message saved, AI reply triggered |
| 3 | Invalid signature | POST with wrong `X-Hub-Signature-256` | 403 Forbidden |
| 4 | Status update | POST with message status update | Message status updated (delivered/read) |

### 8.3 Status Studio

| # | Test | URL | Steps | Expected Result |
|---|------|-----|-------|-----------------|
| 1 | View studio | `/whatsapp/status/` | Navigate | Status content queue displayed |
| 2 | Create status | `/whatsapp/status/create/` | Fill text/caption → POST | StatusContent created (state: draft/ready) |
| 3 | Share status | `/whatsapp/status/<uuid>/share/` | POST | State → shared, share URL generated |
| 4 | Skip status | `/whatsapp/status/<uuid>/skip/` | POST | State → skipped |
| 5 | Repurpose post | `/whatsapp/status/repurpose/<uuid>/` | POST (post UUID) | Existing post adapted to Status format |
| 6 | View calendar | `/whatsapp/status/calendar/` | Navigate | 7-day visual planner with content mix |

### 8.4 Templates

| # | Test | URL | Steps | Expected Result |
|---|------|-----|-------|-----------------|
| 1 | List templates | `/whatsapp/templates/` | Navigate | All templates with status |
| 2 | Create template | `/whatsapp/templates/create/` | Fill name, category, body → POST | Template created (status: draft) |

### 8.5 Broadcasts

| # | Test | URL | Steps | Expected Result |
|---|------|-----|-------|-----------------|
| 1 | List broadcasts | `/whatsapp/broadcasts/` | Navigate | Broadcasts + drip sequences listed |
| 2 | Create broadcast | `/whatsapp/broadcasts/create/` | Fill name, template, segment → POST | Broadcast created (status: draft) |
| 3 | View broadcast | `/whatsapp/broadcasts/<uuid>/` | Click broadcast | Detail with recipient count, metrics |
| 4 | Launch broadcast | `/whatsapp/broadcasts/<uuid>/launch/` | POST | Recipients resolved, messages sent |
| 5 | Pause broadcast | `/whatsapp/broadcasts/<uuid>/pause/` | POST | Broadcast paused/cancelled |

### 8.6 Drip Sequences

| # | Test | URL | Steps | Expected Result |
|---|------|-----|-------|-----------------|
| 1 | Create sequence | `/whatsapp/sequences/create/` | Fill name, type → POST | Sequence created (status: draft) |
| 2 | View sequence | `/whatsapp/sequences/<uuid>/` | Click sequence | Steps and enrollments displayed |
| 3 | Add step | `/whatsapp/sequences/<uuid>/add-step/` | Fill template, delay → POST | Step added with order |
| 4 | Toggle sequence | `/whatsapp/sequences/<uuid>/toggle/` | POST | Active ↔ paused |
| 5 | Auto-processing | Trigger `process_sequence_steps` task | Due steps sent to enrolled contacts |

### 8.7 Channels

| # | Test | URL | Steps | Expected Result |
|---|------|-----|-------|-----------------|
| 1 | View channels | `/whatsapp/channels/` | Navigate | Channel dashboard |
| 2 | Create channel | `/whatsapp/channels/create/` | Fill name → POST | Channel created |
| 3 | View channel | `/whatsapp/channels/<uuid>/` | Click channel | Channel detail with posts |
| 4 | Create post | `/whatsapp/channels/<uuid>/post/` | Fill text → POST | ChannelPost created |
| 5 | Publish post | `/whatsapp/channels/<uuid>/post/<uuid>/publish/` | POST | Post published to channel |
| 6 | Toggle auto-curation | `/whatsapp/channels/<uuid>/toggle-curate/` | POST | Auto-curate enabled/disabled |

### 8.8 WhatsApp Analytics

| # | Test | URL | Steps | Expected Result |
|---|------|-----|-------|-----------------|
| 1 | View analytics | `/whatsapp/analytics/` | Navigate | Metrics dashboard with charts |
| 2 | View digest | `/whatsapp/analytics/digest/<uuid>/` | Click digest | Weekly AI digest with recommendations |
| 3 | Daily aggregation | Trigger `aggregate_daily_analytics` task | WhatsAppAnalytics record created for today |
| 4 | Weekly digest | Trigger `generate_weekly_digest` task | WeeklyDigest created with AI summary |

---

## 9. Testing Meme Intelligence Engine

| # | Test | URL | Steps | Expected Result |
|---|------|-----|-------|-----------------|
| 1 | View discover | `/memes/` | Navigate | Trending memes displayed |
| 2 | View queue | `/memes/queue/` | Navigate | User's adapted meme queue |
| 3 | Meme settings | `/memes/settings/` | Set risk tolerance, categories, quota → save | Preferences saved |
| 4 | View meme detail | `/memes/<uuid>/` | Click meme | Full meme detail with scores |
| 5 | Adapt meme | `/memes/<uuid>/adapt/` | POST | AI creates brand-adapted version |
| 6 | View meme card | `/memes/<uuid>/card/` | GET | HTMX meme card partial |
| 7 | Approve adaptation | `/memes/adaptation/<uuid>/approve/` | POST | Adaptation approved for posting |
| 8 | Reject adaptation | `/memes/adaptation/<uuid>/reject/` | POST | Adaptation rejected |
| 9 | Convert to post | `/memes/adaptation/<uuid>/to-post/` | POST | ContentSeed/Post created from adaptation |
| 10 | Discovery task | Trigger `discover_trending_memes` | 5-8 new memes discovered with virality/safety/cultural scores |
| 11 | Adaptation task | Trigger `adapt_memes_for_users` | 2 adaptations per eligible user |
| 12 | Lifecycle task | Trigger `update_meme_lifecycle` | Memes age: emerging→trending→peaked→fading→dead |
| 13 | Plan gating | Starter/Growth user | Meme features blocked — requires Pro+ |
| 14 | Kenyan calendar | Create upcoming KenyanEvent | Discovery considers it for meme context |

---

## 10. Testing Engagement & Community

| # | Test | URL | Steps | Expected Result |
|---|------|-----|-------|-----------------|
| 1 | View inbox | `/engage/` | Navigate | All interactions with filters (status, sentiment, platform) |
| 2 | Send reply | `/engage/reply/<uuid>/` | Edit reply → POST | Reply sent via platform API |
| 3 | Trigger engage | `/engage/trigger/` | POST | Engage Agent cycle runs: fetch → analyze → reply |
| 4 | Interaction filters | `/engage/?status=new&platform=twitter` | Filter | Filtered results |
| 5 | Superfan display | Check superfans section | Superfans listed with tier (rising/loyal/superfan) |
| 6 | AI reply quality | Review AI-suggested replies | Matches brand voice, contextually appropriate |
| 7 | Edit AI reply | Modify suggested reply before sending | `user_edited_reply` flag set to True |

---

## 11. Testing Analytics & Intelligence

### 11.1 Insights Dashboard

| # | Test | URL | Steps | Expected Result |
|---|------|-----|-------|-----------------|
| 1 | View insights | `/analytics/` | Navigate | Performance dashboard with metrics |
| 2 | Post metrics | Publish posts, wait for metric fetch | Impressions, reach, likes, comments, shares populated |
| 3 | Metric fetch task | Trigger `fetch_all_recent_metrics` | PostMetric records updated for recent posts |

### 11.2 Content DNA

| # | Test | Steps | Expected Result |
|---|------|-------|-----------------|
| 1 | Extract DNA | Publish a post, run `extract_content_dna(post)` | Returns: format, hook_type, tone, CTA, emotion, length |
| 2 | DNA summary | `get_content_dna_summary(user, 30)` | Aggregated patterns showing what works |

### 11.3 Audience Growth

| # | Test | Steps | Expected Result |
|---|------|-------|-----------------|
| 1 | Growth tracking | Trigger `track_audience_growth` task | GrowthSnapshot created for each social account |
| 2 | Growth summary | `GrowthSnapshot.get_growth_summary(user, 30)` | Per-platform: followers, delta, velocity, trend |

---

## 12. Testing Revenue Attribution & Kova Pixel

### 12.1 Revenue Dashboard

| # | Test | URL | Steps | Expected Result |
|---|------|-----|-------|-----------------|
| 1 | View revenue | `/analytics/revenue/` | Navigate | Revenue dashboard with totals, by-platform, by-content |
| 2 | Connect Shopify | `/analytics/revenue/shopify/connect/` | Enter shop domain + token | ShopifyStore created |
| 3 | Disconnect Shopify | `/analytics/revenue/shopify/<uuid>/disconnect/` | POST | Store deactivated |

### 12.2 Kova Pixel

| # | Test | URL | Steps | Expected Result |
|---|------|-----|-------|-----------------|
| 1 | Pixel settings | `/analytics/pixel/` | Navigate | Shows pixel token and install instructions |
| 2 | Regenerate token | `/analytics/pixel/regenerate/` | POST | New token generated |
| 3 | View events | `/analytics/pixel/events/` | Navigate | All captured events listed |
| 4 | Test pixel | `/analytics/pixel/test/` | Navigate | Test pixel integration page |
| 5 | Get pixel JS | `GET /analytics/pixel/kova-pixel.js` | Request | JavaScript tracking code returned |
| 6 | Track event | `POST /analytics/pixel/track/` with `{pixel_token, event_type, page_url}` | WebsiteEvent created |
| 7 | Invalid token | POST with wrong `pixel_token` | 403 or ignored |
| 8 | Rate limit | Send 121+ requests/min | Rate limited after 120 |
| 9 | CORS headers | OPTIONS request from external domain | Correct CORS headers returned |
| 10 | Page view tracking | Send `event_type: "page_view"` | Page view event recorded |
| 11 | Purchase tracking | Send `event_type: "purchase"` with `revenue` | Purchase event + conversion created |

### 12.3 Multi-Touch Attribution

| # | Test | Steps | Expected Result |
|---|------|-------|-----------------|
| 1 | Single touch | One touchpoint → conversion | 100% credit to that touchpoint |
| 2 | Two touches | First click → second click → conversion | 40% first, 60% last |
| 3 | Three+ touches | First → middle → last → conversion | 40% first, 20% middle, 40% last |
| 4 | Journey creation | Pixel events with same `visitor_id` | ConversionJourney created linking touchpoints |
| 5 | UTM attribution | Post with UTM tags → pixel click | Conversion attributed to specific post |

---

## 13. Testing Competitor Intelligence

| # | Test | URL | Steps | Expected Result |
|---|------|-----|-------|-----------------|
| 1 | View competitors | `/analytics/competitors/` | Navigate | Competitor dashboard |
| 2 | Add competitor | `/analytics/competitors/add/` | Fill name, handles → POST | Competitor created |
| 3 | Competitor landscape | `/analytics/competitors/landscape/` | Navigate | Visual competitive landscape |
| 4 | View detail | `/analytics/competitors/<uuid>/` | Click competitor | Detail with strengths, weaknesses, patterns |
| 5 | Edit competitor | `/analytics/competitors/<uuid>/edit/` | Update handles → POST | Competitor updated |
| 6 | Trigger analysis | `/analytics/competitors/<uuid>/analyze/` | POST | AI analysis triggered (async task) |
| 7 | Delete competitor | `/analytics/competitors/<uuid>/delete/` | POST | Competitor deleted |
| 8 | Act on insight | `/analytics/insights/<uuid>/action/` | POST | Insight marked as acted on |
| 9 | Analysis output | Wait for analysis task to complete | CompetitorAnalysis created with SWOT, insights |
| 10 | Insight types | Check generated insights | Types: content_gap, trend_ahead, weakness, strategy_shift, viral_content, opportunity |
| 11 | Weekly auto-analysis | Trigger `analyze-all-competitors` task | All competitors not analyzed in 6+ days queued |

---

## 14. Testing Media Queue

| # | Test | URL | Steps | Expected Result |
|---|------|-----|-------|-----------------|
| 1 | View queues | `/media-queue/` | Navigate | List of media queues per account |
| 2 | Create queue | `/media-queue/create/` | Select social account, rhythm → POST | MediaQueue created |
| 3 | View queue detail | `/media-queue/<uuid>/` | Click queue | Queue items displayed |
| 4 | Queue settings | `/media-queue/<uuid>/settings/` | Change rhythm (daily/weekly) → POST | Settings updated, schedule recalculated |
| 5 | Toggle queue | `/media-queue/<uuid>/toggle/` | POST | Queue active ↔ paused |
| 6 | Delete queue | `/media-queue/<uuid>/delete/` | POST | Queue deleted |
| 7 | Upload media | `/media-queue/<uuid>/upload/` | Upload images → POST | QueueItems created with auto-scheduled times |
| 8 | Reorder items | `/media-queue/<uuid>/reorder/` | Drag-drop reorder → POST | Order updated, times recalculated |
| 9 | Edit item | `/media-queue/item/<uuid>/edit/` | Change caption → POST | Item updated |
| 10 | Delete item | `/media-queue/item/<uuid>/delete/` | POST | Item removed, queue recalculated |
| 11 | Retry failed item | `/media-queue/item/<uuid>/retry/` | POST | Failed item retried |
| 12 | Auto-publish | Trigger `process_queues` task | Due items published to platform |

---

## 15. Testing Campaigns

| # | Test | URL | Steps | Expected Result |
|---|------|-----|-------|-----------------|
| 1 | List campaigns | `/campaigns/` | Navigate | Campaign hub with filters |
| 2 | Create campaign | `/campaigns/create/` | Fill name, objective, dates → POST | Campaign created (status: draft) |
| 3 | View detail | `/campaigns/<uuid>/` | Click campaign | Dashboard with linked content + emails + metrics |
| 4 | Edit campaign | `/campaigns/<uuid>/edit/` | Update fields → POST | Campaign updated |
| 5 | Change status | `/campaigns/<uuid>/status/` | POST with new status | Valid transitions enforced |
| 6 | Delete campaign | `/campaigns/<uuid>/delete/` | POST | Only draft/cancelled campaigns deletable |
| 7 | Add content seed | `/campaigns/<uuid>/add-seed/` | Select seed, role → POST | CampaignSeed created |
| 8 | Remove seed | `/campaigns/<uuid>/remove-seed/<uuid>/` | POST | Seed removed from campaign |
| 9 | Add email campaign | `/campaigns/<uuid>/add-email/` | Select email campaign → POST | CampaignEmail linked |
| 10 | Remove email | `/campaigns/<uuid>/remove-email/<uuid>/` | POST | Email removed from campaign |
| 11 | Add note | `/campaigns/<uuid>/add-note/` | Write note → POST | CampaignNote created |
| 12 | Plan gating | Starter user tries to create | Campaigns not available on Starter |
| 13 | Monthly limit | Growth user exceeds 3/month | Error: monthly limit reached |

**Status Transitions:**
- draft → pending_approval → approved → active → paused → completed
- draft / cancelled → deletable
- active → paused (and back)
- active → completed
- Any → cancelled

---

## 16. Testing Email Marketing

### 16.1 Email Dashboard

| # | Test | URL | Steps | Expected Result |
|---|------|-----|-------|-----------------|
| 1 | View dashboard | `/emails/marketing/` | Navigate | Overview: subscriber stats, campaign stats, recent campaigns, active sequences |

### 16.2 Subscribers

| # | Test | URL | Steps | Expected Result |
|---|------|-----|-------|-----------------|
| 1 | List subscribers | `/emails/subscribers/` | Navigate | Subscribers with status/search filters |
| 2 | Add subscriber | `/emails/subscribers/add/` | Fill name, email → POST | Subscriber created (plan-gated) |
| 3 | Plan limit | Exceed subscriber limit | Error: plan limit reached |
| 4 | Duplicate email | Add same email twice | Existing subscriber returned/updated |

### 16.3 Email Lists

| # | Test | URL | Steps | Expected Result |
|---|------|-----|-------|-----------------|
| 1 | List all lists | `/emails/lists/` | Navigate | All email lists displayed |
| 2 | Create list | `/emails/lists/create/` | Fill name → POST | EmailList created |
| 3 | View list detail | `/emails/lists/<uuid>/` | Click list | Subscribers in this list |
| 4 | Edit list | `/emails/lists/<uuid>/edit/` | Update → POST | List updated |
| 5 | Smart list | Create list with `is_smart=True` + filter rules | List auto-populates based on rules |

### 16.4 Email Campaigns

| # | Test | URL | Steps | Expected Result |
|---|------|-----|-------|-----------------|
| 1 | List campaigns | `/emails/campaigns/` | Navigate | All campaigns with status filter |
| 2 | Create campaign | `/emails/campaigns/create/` | Fill subject, content, target list → POST | Campaign created (status: draft) |
| 3 | View detail | `/emails/campaigns/<uuid>/` | Click campaign | Metrics: sent, opened, clicked, bounced |
| 4 | Edit campaign | `/emails/campaigns/<uuid>/edit/` | Update → POST | Campaign updated (only draft/scheduled) |
| 5 | Plan limit | Exceed monthly campaign limit | Error: monthly limit reached |

### 16.5 Email Sequences (Drip Campaigns)

| # | Test | URL | Steps | Expected Result |
|---|------|-----|-------|-----------------|
| 1 | List sequences | `/emails/sequences/` | Navigate | All sequences displayed |
| 2 | View sequence | `/emails/sequences/<uuid>/` | Click sequence | Steps and enrollments visible |
| 3 | Trigger types | Test each: form_submission, tag_added, subscriber_added, lead_status_change, manual | Subscriber enrolled in sequence |

### 16.6 Email Delivery & Webhooks

| # | Test | Steps | Expected Result |
|---|------|-------|-----------------|
| 1 | Email sending | Create campaign → send | Emails delivered via Resend |
| 2 | Delivery webhook | Resend sends delivery event | EmailLog status → delivered |
| 3 | Open tracking | Recipient opens email | EmailLog status → opened |
| 4 | Click tracking | Recipient clicks link | EmailLog status → clicked |
| 5 | Bounce handling | Email bounces | EmailLog status → bounced, subscriber bounce_count++ |
| 6 | Unsubscribe | `GET /emails/unsubscribe/<token>/` | Unsubscribe page shown (no login required) |
| 7 | Confirm unsubscribe | `POST /emails/unsubscribe/<token>/` | Subscriber status → unsubscribed |
| 8 | Invalid token | `/emails/unsubscribe/invalid-token/` | 404 or error message |

### 16.7 Trial Expiry Emails

| # | Test | Steps | Expected Result |
|---|------|-------|-----------------|
| 1 | Day 7 email | User 7 days into trial | "Trial halfway" email sent |
| 2 | Day 3 email | User 11 days into trial | "3 days left" email sent |
| 3 | Day 1 email | User 13 days into trial | "Last day" email sent |
| 4 | Day 0 email | Trial expired | "Trial expired" email sent |

---

## 17. Testing Product Catalog

| # | Test | URL | Steps | Expected Result |
|---|------|-----|-------|-----------------|
| 1 | List products | `/products/` | Navigate | Products with filters (status, category, featured, search) |
| 2 | Add product | `/products/add/` | Fill name, price, stock → POST | Product created |
| 3 | View detail | `/products/<uuid>/` | Click product | Detail with stock history + alerts |
| 4 | Edit product | `/products/<uuid>/edit/` | Update fields → POST | Product updated, stock change logged |
| 5 | Delete product | `/products/<uuid>/delete/` | POST | Soft delete (`is_active=False`) |
| 6 | Update stock | `/products/<uuid>/stock/` | Change quantity → POST (HTMX) | StockUpdate created with reason |
| 7 | Import products | `/products/import/` | Upload CSV or paste text → POST | Products bulk-created |
| 8 | Categories | `/products/categories/` | Navigate | Categories with product counts |
| 9 | Add category | `/products/categories/add/` | Fill name → POST | Category created |
| 10 | Plan limit | Exceed product limit for plan | Error: plan limit reached |
| 11 | Stock alerts | Low stock product exists, trigger `check-stock-alerts` task | StockAlert created (low_stock type) |
| 12 | Featured + no content | Featured product with no recent posts | StockAlert: "featured_no_content" |
| 13 | Product types | Create product, service, and digital offering | Each type saved correctly |

---

## 18. Testing Lead Capture & CRM

| # | Test | URL | Steps | Expected Result |
|---|------|-----|-------|-----------------|
| 1 | List leads | `/leads/` | Navigate | Lead inbox with status/priority/source/search filters |
| 2 | Create lead | `/leads/create/` | Fill name, email → POST | Lead created (status: new) |
| 3 | View detail | `/leads/<uuid>/` | Click lead | Activity timeline + note/tag forms |
| 4 | Edit lead | `/leads/<uuid>/edit/` | Update fields → POST | Lead updated |
| 5 | Change status | `/leads/<uuid>/status/` | POST with new status | Status updated, LeadActivity logged |
| 6 | Add note | `/leads/<uuid>/note/` | Write note → POST | Note added, LeadActivity logged |
| 7 | Add tag | `/leads/<uuid>/tag/` | Enter tag → POST | Tag added to JSON array |
| 8 | Remove tag | `/leads/<uuid>/tag/remove/` | POST with tag name | Tag removed |
| 9 | Lead analytics | `/leads/analytics/` | Navigate | Funnel: by status, source, priority, conversion rate |
| 10 | Plan limit | Exceed lead limit for plan | Error: plan limit reached |
| 11 | Duplicate email | Create lead with existing email | Existing lead returned/updated (unique per user) |
| 12 | Form → Lead | Submit a Kova Form on a public page | Lead auto-created from submission |

---

## 19. Testing Kova Pages (Link-in-Bio)

### 19.1 Page Management

| # | Test | URL | Steps | Expected Result |
|---|------|-----|-------|-----------------|
| 1 | List pages | `/links/` | Navigate | All user's Kova pages |
| 2 | Create page | `/links/create/` | Fill title, slug, bio, theme → POST | KovaPage created |
| 3 | View detail | `/links/<uuid>/` | Click page | Dashboard: links, forms, analytics |
| 4 | Edit page | `/links/<uuid>/edit/` | Update fields → POST | Page updated |
| 5 | Delete page | `/links/<uuid>/delete/` | POST | Page + all links/forms deleted |
| 6 | Plan limit | Starter: >1 page, Growth: >3, Pro: >10 | Error: plan limit reached |
| 7 | Unique slug | Create page with existing slug | Validation error |

### 19.2 Links

| # | Test | URL | Steps | Expected Result |
|---|------|-----|-------|-----------------|
| 1 | Add link | `/links/<uuid>/links/add/` | Fill title, URL, type → POST | KovaLink created |
| 2 | Edit link | `/links/<uuid>/links/<link_uuid>/edit/` | Update → POST | Link updated |
| 3 | Delete link | `/links/<uuid>/links/<link_uuid>/delete/` | POST | Link deleted |
| 4 | Link types | Create each: url, social, email, phone, header | All types saved correctly |
| 5 | Plan limit | Exceed links-per-page limit | Error: plan limit reached |

### 19.3 Lead Capture Forms

| # | Test | URL | Steps | Expected Result |
|---|------|-----|-------|-----------------|
| 1 | Add form | `/links/<uuid>/forms/add/` | Fill type, title → POST | KovaForm created |
| 2 | Edit form | `/links/<uuid>/forms/<form_uuid>/edit/` | Update → POST | Form updated |
| 3 | Delete form | `/links/<uuid>/forms/<form_uuid>/delete/` | POST | Form deleted |
| 4 | Form types | Create each: contact, newsletter, waitlist, booking, custom | All types work |
| 5 | Plan gating | Starter user tries to add form | Forms require Growth+ |

### 19.4 Public Page & Submissions

| # | Test | URL | Steps | Expected Result |
|---|------|-----|-------|-----------------|
| 1 | View public page | `/k/<slug>/` | Visit (no auth needed) | Page rendered with links + forms |
| 2 | Click link | Click link on public page | `/k/<slug>/click/<uuid>/` → redirects to URL, LinkClick recorded |
| 3 | Submit form | Fill form on public page → POST to `/k/<slug>/form/<uuid>/` | FormSubmission created, Lead auto-created |
| 4 | Page view tracking | Visit public page | PageView count incremented |
| 5 | Unpublished page | Set `is_published=False` | 404 on public page |
| 6 | View submissions | `/links/submissions/` | Navigate | All form submissions across pages |
| 7 | Mark read | `/links/submissions/<uuid>/read/` | POST | Submission marked as read |

---

## 20. Testing Teams & Collaboration

| # | Test | URL | Steps | Expected Result |
|---|------|-----|-------|-----------------|
| 1 | List teams | `/teams/` | Navigate | User's teams listed |
| 2 | Create team | `/teams/create/` | Fill name → POST | Team created, user = owner |
| 3 | View team | `/teams/<slug>/` | Click team | Team detail with members + brands |
| 4 | Invite member | `/teams/<slug>/invite/` | Enter email, select role → POST | TeamInvitation created, email sent |
| 5 | Accept invitation | `/teams/invite/<token>/` | Click invite link | User added as team member with specified role |
| 6 | Invalid/expired token | `/teams/invite/invalid-token/` | Visit | Error: invalid invitation |
| 7 | Leave team | `/teams/<slug>/leave/` | POST | User removed from team |
| 8 | Change member role | `/teams/<slug>/members/<uuid>/role/` | POST with new role | Role updated (owner/admin only) |
| 9 | Remove member | `/teams/<slug>/members/<uuid>/remove/` | POST | Member removed (owner/admin only) |
| 10 | Cancel invitation | `/teams/<slug>/invitations/<uuid>/cancel/` | POST | Invitation cancelled |
| 11 | Create brand | `/teams/<slug>/brands/create/` | Fill name, voice → POST | Brand created under team |
| 12 | View brand | `/teams/<slug>/brands/<uuid>/` | Click brand | Brand detail |
| 13 | Edit brand | `/teams/<slug>/brands/<uuid>/edit/` | Update → POST | Brand updated |
| 14 | Toggle brand | `/teams/<slug>/brands/<uuid>/toggle/` | POST | Brand active ↔ inactive |
| 15 | Plan limit | Exceed team member limit | Error: plan limit (Pro: 5, Agency: 25) |
| 16 | Activity log | Check TeamActivity records | All team actions logged |

**Role Permission Tests:**

| Action | Owner | Admin | Editor | Viewer |
|--------|:-----:|:-----:|:------:|:------:|
| Manage members | ✅ | ✅ | ❌ | ❌ |
| Manage brands | ✅ | ✅ | ❌ | ❌ |
| Create content | ✅ | ✅ | ✅ | ❌ |
| View content | ✅ | ✅ | ✅ | ✅ |
| Manage billing | ✅ | ❌ | ❌ | ❌ |
| Delete team | ✅ | ❌ | ❌ | ❌ |

---

## 21. Testing Billing & Payments

### 21.1 Billing Overview

| # | Test | URL | Steps | Expected Result |
|---|------|-----|-------|-----------------|
| 1 | Billing overview | `/billing/` | Navigate | Current plan, usage stats, payment history |
| 2 | View pricing | `/billing/pricing/` | Navigate | All 4 plan tiers with features |

### 21.2 Stripe Payments

| # | Test | URL | Steps | Expected Result |
|---|------|-----|-------|-----------------|
| 1 | Checkout | `/billing/checkout/` | Select plan → POST | Redirects to Stripe hosted checkout |
| 2 | Success callback | `/billing/checkout/success/` | Complete Stripe payment | Redirected here, plan updated |
| 3 | Cancel callback | `/billing/checkout/cancel/` | Cancel on Stripe checkout | Returned to Kova, no changes |
| 4 | Customer portal | `/billing/portal/` | Click manage subscription | Redirects to Stripe portal |
| 5 | Plan upgrade | Change from Starter → Growth | Plan updated, prorated billing |
| 6 | Plan downgrade | Change from Pro → Growth | Plan updated at next billing cycle |

**Stripe Test Cards:**
| Card | Result |
|------|--------|
| `4242 4242 4242 4242` | Success |
| `4000 0000 0000 0002` | Decline |
| `4000 0000 0000 3220` | 3D Secure required |

### 21.3 M-Pesa Payments

| # | Test | URL | Steps | Expected Result |
|---|------|-----|-------|-----------------|
| 1 | M-Pesa checkout | `/billing/mpesa/checkout/` | Enter phone number → POST | STK push sent to phone |
| 2 | Waiting page | `/billing/mpesa/waiting/` | After STK push | Polling page shown |
| 3 | Check status | `/billing/mpesa/status/` | Auto-polled via HTMX | Returns current payment status |
| 4 | Success page | `/billing/mpesa/success/` | Payment confirmed | Success page, plan updated |
| 5 | Timeout | Don't complete STK push | Timeout after waiting period |

### 21.4 14-Day Trial

| # | Test | Steps | Expected Result |
|---|------|-------|-----------------|
| 1 | Trial starts | New user registers | `trial_end` set to 14 days from now |
| 2 | During trial | Access all features | Full access regardless of plan |
| 3 | Trial expired | Set `trial_end` to past date | `PlanEnforcementMiddleware` blocks premium features |
| 4 | After payment | Subscribe during trial | Trial status irrelevant, paid access |
| 5 | Trial expiry emails | Trigger `check_trial_expiry_emails` | Correct email sent based on trial day |

---

## 22. Testing Notifications

| # | Test | URL | Steps | Expected Result |
|---|------|-----|-------|-----------------|
| 1 | View notifications | `/notifications/` | Navigate | Full notification list (auto-marks all read) |
| 2 | Bell badge | `/notifications/bell/` | GET (HTMX partial) | Badge with unread count |
| 3 | Dropdown | `/notifications/dropdown/` | GET (HTMX partial) | Recent notifications in dropdown |
| 4 | Mark all read | `/notifications/mark-all-read/` | POST | All notifications marked as read |
| 5 | Preferences | `/notifications/preferences/` | Toggle types → POST | Preferences saved |
| 6 | Post published notification | Publish a post successfully | Notification created: "post_published" |
| 7 | Publish failed notification | Simulate publish failure | Notification created: "publish_failed" |
| 8 | Preference respected | Disable "post_published", publish post | No notification created |

---

## 23. Testing Help Center

| # | Test | URL | Steps | Expected Result |
|---|------|-----|-------|-----------------|
| 1 | Help center (auth) | `/help/` | Navigate (logged in) | Articles by category |
| 2 | Help article (auth) | `/help/<slug>/` | Click article | Article with prev/next navigation |
| 3 | Help center (public) | `/learn/` | Visit (no auth) | Public help center |
| 4 | Help article (public) | `/learn/<slug>/` | Visit (no auth) | Public article |
| 5 | View tracking | Visit article as logged-in user | HelpPageView created |
| 6 | All 20 articles | Visit each slug | All render correctly |

**Article Slugs to Test:**
`welcome-to-kova`, `connecting-platforms`, `setting-up-brand-voice`, `content-studio`, `content-queue`, `content-calendar`, `media-queue`, `understanding-agents`, `configuring-agents`, `daily-brief`, `analytics-insights`, `competitor-tracking`, `engagement-inbox`, `kova-pixel`, `leads`, `kova-links`, `plans-and-pricing`, `managing-your-account`, `teams-and-brands`, `faq`

---

## 24. Testing Growth Partners Program

### 24.1 Public Pages

| # | Test | URL | Steps | Expected Result |
|---|------|-----|-------|-----------------|
| 1 | Landing page | `/partners/` | Visit (no auth) | Program overview with tiers |
| 2 | Articles | `/partners/articles/<slug>/` | Visit | Program explainer articles |
| 3 | Apply | `/partners/apply/` | Fill form → POST | PartnerApplication created (status: pending) |
| 4 | Existing applicant | Apply again with same email | Error: application already exists |
| 5 | Existing partner | Partner tries to apply again | Error: already a partner |

### 24.2 Partner Dashboard

| # | Test | URL | Steps | Expected Result |
|---|------|-----|-------|-----------------|
| 1 | Dashboard | `/partners/dashboard/` | Navigate (approved partner) | Stats, referrals, earnings, milestones |
| 2 | Referral code | Check dashboard | Unique code displayed (e.g., `KOVA-JAMES-A3X7`) |
| 3 | Referral tracking | New user signs up with `?ref=KOVA-JAMES-A3X7` in URL | `ReferralMiddleware` captures code, Referral created |
| 4 | Commission calculation | Referred user makes payment | Commission created with correct rate per tier |

### 24.3 Commission Tiers

| Test | Referred Clients | Expected Rate |
|------|:----------------:|:-------------:|
| Starter tier | 1-25 | 15% |
| Connector tier | 26-75 | 20% |
| Catalyst tier | 76-150 | 25% |
| Powerhouse tier | 150+ | 30% |

### 24.4 Anti-Fraud

| # | Test | Steps | Expected Result |
|---|------|-------|-----------------|
| 1 | IP tracking | Same IP signs up multiple referrals | `signup_ip` tracked, flagging possible |
| 2 | Flagged referral | Flag a referral | `is_flagged=True`, `flag_reason` set |
| 3 | Payment tracking | Referred user stops paying | `consecutive_paid_months` tracks reality |

---

## 25. Testing Admin Dashboard

**Prerequisite:** Log in as superuser/staff at `/admin/` or `/dashboard/`.

### 25.1 Overview & System

| # | Test | URL | Expected Result |
|---|------|-----|-----------------|
| 1 | Admin overview | `/dashboard/` | Platform-wide metrics, activity feed |
| 2 | System health | `/dashboard/system/` | System health indicators |
| 3 | Error log | `/dashboard/system/errors/` | Recent errors |
| 4 | Activity log | `/dashboard/logs/` | Full activity log |
| 5 | Export logs | `/dashboard/logs/export/` | CSV download |
| 6 | HTMX stat cards | `/dashboard/_partials/stat-cards/` | Auto-refreshing stat cards |
| 7 | HTMX activity | `/dashboard/_partials/activity-feed/` | Auto-refreshing activity feed |
| 8 | HTMX agent health | `/dashboard/_partials/agent-health/` | Auto-refreshing agent health |

### 25.2 User Management

| # | Test | URL | Steps | Expected Result |
|---|------|-----|-------|-----------------|
| 1 | User list | `/dashboard/users/` | Navigate | All users with stats |
| 2 | User detail | `/dashboard/users/<pk>/` | Click user | Full user profile + activity |
| 3 | Change plan | `/dashboard/users/<pk>/change-plan/` | POST with new plan | User's plan changed |
| 4 | Toggle staff | `/dashboard/users/<pk>/toggle-staff/` | POST | Staff status toggled |
| 5 | Export users | `/dashboard/users/export/` | Click export | CSV download |
| 6 | User health | `/dashboard/users/health/` | Navigate | User health scores |

### 25.3 LLM Configuration

| # | Test | URL | Steps | Expected Result |
|---|------|-----|-------|-----------------|
| 1 | View config | `/dashboard/llm/` | Navigate | Current LLM settings |
| 2 | Update config | `/dashboard/llm/update/` | Change model → POST | LLMConfig updated |
| 3 | Task model override | `/dashboard/llm/task-model/` | Set per-task model → POST | Task override saved |
| 4 | Plan models | `/dashboard/llm/plan-models/` | Set per-plan models → POST | Plan routing saved |
| 5 | Rate limits | `/dashboard/llm/rate-limits/` | Set per-plan limits → POST | Rate limits saved |
| 6 | Apply preset | `/dashboard/llm/apply-preset/` | Select preset → POST | Preset config applied |
| 7 | Image config | `/dashboard/llm/image-config/` | Configure image gen → POST | Image settings saved |
| 8 | Image plan models | `/dashboard/llm/image-plan-models/` | Per-plan image routing → POST | Plan image config saved |

### 25.4 Billing Admin

| # | Test | URL | Steps | Expected Result |
|---|------|-----|-------|-----------------|
| 1 | Billing overview | `/dashboard/billing/` | Navigate | Revenue, subscribers, MRR |
| 2 | Payments | `/dashboard/billing/payments/` | Navigate | All payments |
| 3 | Events | `/dashboard/billing/events/` | Navigate | Billing event log |
| 4 | Subscriptions | `/dashboard/billing/subscriptions/` | Navigate | Active subscriptions |
| 5 | Subscription action | `/dashboard/billing/subscriptions/action/` | Override → POST | SubscriptionOverride created |
| 6 | Bulk grant | `/dashboard/billing/bulk-grant/` | Grant plan to users → POST | Multiple overrides created |
| 7 | Pricing config | `/dashboard/billing/pricing/` | Navigate | PlanPrice configuration |
| 8 | Update pricing | `/dashboard/billing/pricing/update/` | Change prices → POST | PlanPrice updated |
| 9 | Discount codes | `/dashboard/billing/discounts/` | Navigate | All discount codes |
| 10 | Create discount | `/dashboard/billing/discounts/create/` | Fill code → POST | DiscountCode created |

### 25.5 Other Admin Sections

| Section | URL | What to Test |
|---------|-----|-------------|
| Content | `/dashboard/content/` | All posts, seeds, failed publishes |
| Agents | `/dashboard/agents/` | Agent overview, activity log, token economics |
| Platforms | `/dashboard/platforms/` | Connected account stats |
| Costs | `/dashboard/costs/` | Cost analysis, calculator |
| Engagement | `/dashboard/engage/` | Interaction/superfan overview |
| Analytics | `/dashboard/analytics/` | Content DNA, competitor tracking |
| Revenue | `/dashboard/revenue/` | Conversions, Shopify, journeys |
| Pixel | `/dashboard/pixel/` | Pixel tracking, events, per-user stats |
| Teams | `/dashboard/teams/` | Team management |
| A/B Tests | `/dashboard/ab-tests/` | Test management |
| Emails | `/dashboard/emails/` | Email log, test send, broadcast |
| Partners | `/dashboard/partners/` | Applications, partner management |
| Help | `/dashboard/help/` | Article analytics |
| Media Queue | `/dashboard/media-queue/` | Queue admin |
| Products | `/dashboard/products/` | Product/stock admin |
| Campaigns | `/dashboard/campaigns/` | Campaign overview |
| Memes | `/dashboard/memes/` | Meme discovery, adaptations |
| WhatsApp | `/dashboard/whatsapp/` | Conversations, templates, broadcasts |

---

## 26. Testing REST API

**Prerequisite:** Pro or Agency plan. Obtain API token.

### 26.1 Authentication

| # | Test | Steps | Expected Result |
|---|------|-------|-----------------|
| 1 | Token auth | `Authorization: Token <token>` header | 200 OK |
| 2 | No auth | Request without token | 401 Unauthorized |
| 3 | Invalid token | `Authorization: Token invalid123` | 401 Unauthorized |
| 4 | Plan gating | Starter/Growth user's token | 403 Forbidden (Pro+ required) |

### 26.2 Endpoints

| # | Method | URL | Test | Expected Result |
|---|--------|-----|------|-----------------|
| 1 | GET | `/api/v1/platforms/` | List accounts | Array of connected social accounts |
| 2 | GET | `/api/v1/seeds/` | List seeds | Paginated seed list |
| 3 | POST | `/api/v1/seeds/` | Create seed | Seed created, 201 |
| 4 | GET | `/api/v1/seeds/<uuid>/` | Get seed | Single seed detail |
| 5 | GET | `/api/v1/posts/` | List posts | Paginated post list |
| 6 | GET | `/api/v1/posts/?status=published` | Filter posts | Only published posts |
| 7 | GET | `/api/v1/posts/<uuid>/` | Get post | Single post detail |
| 8 | PATCH | `/api/v1/posts/<uuid>/` | Update post | Post updated |
| 9 | GET | `/api/v1/analytics/summary/` | Get analytics | Aggregate analytics |
| 10 | GET | `/api/v1/analytics/metrics/<uuid>/` | Get post metrics | PostMetric for specific post |
| 11 | GET | `/api/v1/agents/` | List agents | Agent configurations |
| 12 | GET | `/api/v1/agents/actions/` | List actions | Recent agent actions |
| 13 | GET | `/api/v1/agents/actions/?agent_type=create` | Filter actions | Only Create Agent actions |
| 14 | GET | `/api/v1/conversions/` | List conversions | Conversion events |
| 15 | POST | `/api/v1/conversions/` | Create conversion | Conversion created, 201 |

### 26.3 Rate Limiting

| # | Test | Steps | Expected Result |
|---|------|-------|-----------------|
| 1 | Under limit | Send 100 requests/min | All succeed (200) |
| 2 | Over limit | Send 121+ requests/min | 429 Too Many Requests |
| 3 | Anonymous limit | No auth, 21+ requests/min | 429 Too Many Requests |

### 26.4 Pagination

| # | Test | Steps | Expected Result |
|---|------|-------|-----------------|
| 1 | Default page | `GET /api/v1/posts/` | Returns first 25 results |
| 2 | Page 2 | `GET /api/v1/posts/?page=2` | Returns next 25 results |
| 3 | Page size | `GET /api/v1/posts/?page_size=10` | Returns 10 results |

---

## 27. Testing Celery Tasks

### Running Tasks Manually

In development (`CELERY_TASK_ALWAYS_EAGER=True`), tasks run synchronously. Test via Django shell:

```python
from apps.content.tasks import check_and_publish_due_posts
result = check_and_publish_due_posts()
# Runs immediately, returns result
```

### Critical Queue Tasks

| # | Task | How to Test | Expected Result |
|---|------|------------|-----------------|
| 1 | `check_and_publish_due_posts` | Schedule a post for past time, run task | Post published |
| 2 | `process_queues` | Create media queue item due now, run task | Item published |
| 3 | `refresh_expiring_tokens` | Set token_expires to near-future, run task | Token refreshed |

### Default Queue Tasks

| # | Task | How to Test | Expected Result |
|---|------|------------|-----------------|
| 4 | `generate_from_seed` | Create seed, call task | Posts generated from seed |
| 5 | `generate_all_daily_briefs` | Run task | Briefs created for all users |
| 6 | `run_daily_research` | Run task | Trends discovered per user |
| 7 | `run_engage_cycle` | Run task | Interactions fetched, replies generated |
| 8 | `run_strategy_cycle` | Run task | Strategy decisions made, seeds created |

### Low Queue Tasks

| # | Task | How to Test | Expected Result |
|---|------|------------|-----------------|
| 9 | `fetch_all_recent_metrics` | Publish posts first, run task | PostMetric records created |
| 10 | `evaluate_ab_tests` | Create running A/B test, run task | Test evaluated for winner |
| 11 | `measure_agent_outcomes` | Have recent agent actions, run task | Outcomes scored |
| 12 | `track_audience_growth` | Have connected accounts, run task | GrowthSnapshot created |
| 13 | `check_mpesa_subscriptions` | Have M-Pesa payment, run task | Subscription status verified |
| 14 | `analyze-all-competitors` | Have active competitors, run task | Analysis queued for stale competitors |
| 15 | `check_trial_expiry_emails` | Have users at trial milestones, run task | Correct emails sent |
| 16 | `discover_trending_memes` | Run task | 5-8 trending memes discovered |
| 17 | `adapt_memes_for_users` | Have trending memes + users, run task | Adaptations created |
| 18 | `update_meme_lifecycle` | Have memes at various ages, run task | Memes age through lifecycle |
| 19 | `check-stock-alerts` | Have low stock products, run task | Stock alerts created |
| 20 | `generate_status_queue` | Run task | WhatsApp Status content generated |
| 21 | `process_sequence_steps` | Have active WA sequences, run task | Due steps sent |
| 22 | `aggregate_daily_wa_analytics` | Have WA messages today, run task | WhatsAppAnalytics record created |
| 23 | `generate_weekly_wa_digest` | Have WA analytics data, run task | WeeklyDigest created |
| 24 | `curate_channel_content` | Have WA channel with auto-curate, run task | ChannelPost created from other platforms |

---

## 28. Testing Webhooks

### 28.1 Stripe Webhook

| # | Test | URL | Steps | Expected Result |
|---|------|-----|-------|-----------------|
| 1 | Endpoint | `POST /billing/webhook/stripe/` | Send Stripe event | Processed correctly |
| 2 | Signature verification | Valid `Stripe-Signature` header | 200 OK |
| 3 | Invalid signature | Wrong/missing signature | 400 Bad Request |
| 4 | `checkout.session.completed` | Send event | Plan updated, BillingEvent created |
| 5 | `customer.subscription.updated` | Send event | Plan change processed |
| 6 | `customer.subscription.deleted` | Send event | Plan downgraded to starter |
| 7 | `invoice.payment_failed` | Send event | Failure notification sent |

**Stripe CLI testing:**
```bash
stripe listen --forward-to localhost:8000/billing/webhook/stripe/
stripe trigger checkout.session.completed
```

### 28.2 M-Pesa Webhook

| # | Test | URL | Steps | Expected Result |
|---|------|-----|-------|-----------------|
| 1 | Endpoint | `POST /billing/webhook/mpesa/` | Send M-Pesa callback | Payment processed |
| 2 | Success callback | ResultCode=0 | MpesaPayment updated, plan activated |
| 3 | Failed callback | ResultCode!=0 | Payment marked failed |

### 28.3 Resend Email Webhook

| # | Test | URL | Steps | Expected Result |
|---|------|-----|-------|-----------------|
| 1 | Endpoint | `POST /emails/webhooks/resend/` | Send delivery event | EmailLog status updated |
| 2 | HMAC verification | Valid signature header | 200 OK |
| 3 | Invalid signature | Wrong signature | 403 Forbidden |
| 4 | Delivered event | `type: "email.delivered"` | EmailLog → delivered |
| 5 | Opened event | `type: "email.opened"` | EmailLog → opened |
| 6 | Clicked event | `type: "email.clicked"` | EmailLog → clicked |
| 7 | Bounced event | `type: "email.bounced"` | EmailLog → bounced, subscriber bounce_count++ |
| 8 | Complained event | `type: "email.complained"` | EmailLog → spam, subscriber status → complained |

### 28.4 Shopify Webhook

| # | Test | URL | Steps | Expected Result |
|---|------|-----|-------|-----------------|
| 1 | Endpoint | `POST /analytics/webhooks/shopify/order/` | Send order payload | Conversion created |
| 2 | HMAC verification | Valid `X-Shopify-Hmac-Sha256` | 200 OK |
| 3 | Invalid HMAC | Wrong signature | 401 Unauthorized |
| 4 | UTM attribution | Order from UTM-tagged link | Conversion attributed to specific post |
| 5 | Revenue tracking | Order with line items | Revenue recorded on ShopifyStore |

### 28.5 M-Pesa Commerce Webhook

| # | Test | URL | Steps | Expected Result |
|---|------|-----|-------|-----------------|
| 1 | Endpoint | `POST /analytics/webhooks/mpesa/commerce/` | Send payment callback | Conversion created |
| 2 | Revenue tracking | Payment with amount | Revenue recorded |

### 28.6 WhatsApp Webhook

| # | Test | URL | Steps | Expected Result |
|---|------|-----|-------|-----------------|
| 1 | Verification | `GET /whatsapp/webhook/?hub.mode=subscribe&hub.verify_token=<token>&hub.challenge=12345` | Returns `12345` |
| 2 | Wrong token | GET with wrong verify_token | 403 Forbidden |
| 3 | Incoming message | POST with message payload + valid signature | WhatsAppMessage created, AI reply triggered |
| 4 | Invalid signature | POST with wrong `X-Hub-Signature-256` | 403 Forbidden |
| 5 | Message status | POST with status update (delivered/read) | Message status updated |
| 6 | Duplicate message | Send same `wamid` twice | Second message ignored (idempotent) |

---

## 29. Testing Middleware & Security

### 29.1 OnboardingMiddleware

| # | Test | Steps | Expected Result |
|---|------|-------|-----------------|
| 1 | New user redirect | Login as user who hasn't completed onboarding | Redirected to `/accounts/onboarding/` |
| 2 | Completed user | Login as user with onboarding complete | Normal navigation |
| 3 | Allowed paths | New user accesses `/accounts/onboarding/`, `/accounts/login/`, static files | Not redirected |

### 29.2 PlanEnforcementMiddleware

| # | Test | Steps | Expected Result |
|---|------|-------|-----------------|
| 1 | Starter accessing WhatsApp | Navigate to `/whatsapp/` | Redirected to upgrade page |
| 2 | Pro accessing WhatsApp | Navigate to `/whatsapp/` | Access granted |
| 3 | Expired trial | Set `trial_end` to past, access premium feature | Blocked |
| 4 | Active trial | Within 14 days, access any feature | Access granted |
| 5 | Staff bypass | Staff user accesses anything | Always granted |
| 6 | Admin bypass | Superuser accesses anything | Always granted |

### 29.3 ReferralMiddleware

| # | Test | Steps | Expected Result |
|---|------|-------|-----------------|
| 1 | Capture code | Visit any page with `?ref=KOVA-CODE` | Code saved in session |
| 2 | Apply on signup | Sign up after visiting with ref code | Referral created linking to partner |
| 3 | No code | Visit without ref parameter | No referral tracking |

### 29.4 CSRF Protection

| # | Test | Steps | Expected Result |
|---|------|-------|-----------------|
| 1 | Form without CSRF | POST to any form endpoint without CSRF token | 403 Forbidden |
| 2 | Form with CSRF | POST with valid CSRF token | Request processed |
| 3 | Pixel endpoint exempt | POST to `/analytics/pixel/track/` without CSRF | 200 OK (CSRF exempt) |
| 4 | Webhook exempt | POST to webhook endpoints without CSRF | 200 OK (CSRF exempt) |

### 29.5 Authentication

| # | Test | Steps | Expected Result |
|---|------|-------|-----------------|
| 1 | Protected page unauthenticated | Visit `/content/studio/` | Redirect to login |
| 2 | Public page unauthenticated | Visit `/k/some-slug/` | Page renders |
| 3 | Admin page non-staff | Non-staff visits `/dashboard/` | 403 Forbidden |
| 4 | API without token | `GET /api/v1/posts/` no auth | 401 Unauthorized |

### 29.6 Security Features

| # | Test | Steps | Expected Result |
|---|------|-------|-----------------|
| 1 | Token encryption | Check `SocialAccount.access_token` in DB | Fernet-encrypted value |
| 2 | EXIF stripping | Upload photo with GPS data → check stored file | Location metadata removed |
| 3 | UUID primary keys | Check any model's `id` | UUID format (non-sequential) |
| 4 | Rate limiting (login) | Attempt 6 logins in 1 minute | Rate limited |
| 5 | XSS in post content | Enter `<script>alert('xss')</script>` in post content | Script escaped in output |
| 6 | SQL injection | Enter `'; DROP TABLE --` in search fields | Query parameterized, no injection |

---

## 30. Testing Public Pages

Pages accessible without authentication:

| # | URL | Test | Expected Result |
|---|-----|------|-----------------|
| 1 | `/` | Landing page | Marketing page (auth users → redirected to `/brief/`) |
| 2 | `/health/` | Health check | 200 OK (for monitoring) |
| 3 | `/privacy/` | Privacy policy | Static page rendered |
| 4 | `/terms/` | Terms of service | Static page rendered |
| 5 | `/cookies/` | Cookie policy | Static page rendered |
| 6 | `/acceptable-use/` | Acceptable use policy | Static page rendered |
| 7 | `/dpa/` | Data processing agreement | Static page rendered |
| 8 | `/campus-rep/` | Campus rep program | Static page rendered |
| 9 | `/sw.js` | Service worker | JavaScript file served |
| 10 | `/k/<slug>/` | Public Kova Page | Link-in-bio page rendered |
| 11 | `/k/<slug>/click/<uuid>/` | Link click tracking | Redirect to URL, click recorded |
| 12 | `/k/<slug>/form/<uuid>/` | Form submission | Form processed, lead created |
| 13 | `/learn/` | Public help center | Help articles listed |
| 14 | `/learn/<slug>/` | Public help article | Article rendered |
| 15 | `/partners/` | Partners landing | Program overview |
| 16 | `/partners/apply/` | Partner application | Application form |
| 17 | `/partners/articles/<slug>/` | Partner article | Article rendered |
| 18 | `/emails/unsubscribe/<token>/` | Email unsubscribe | Unsubscribe page (no auth) |
| 19 | `/accounts/login/` | Login page | Login form |
| 20 | `/accounts/signup/` | Signup page | Registration form |

---

## 31. Automated Test Reference

### Existing Test Suite

```
tests/
├── conftest.py         # 5 fixtures: user, staff_user, superuser, rf, auth_client
├── test_auth.py        # 5 tests: login redirect, valid/invalid login, decorators
├── test_accounts.py    # 8 tests: User CRUD, str, soft delete, UserProfile, encryption
├── test_content.py     # 10 tests: Seed/Post CRUD, scheduling, media, studio views
├── test_billing.py     # 5 tests: BillingEvent, MpesaPayment, PLAN_LIMITS
└── test_agents.py      # 5 tests: AgentConfig types, AgentAction logging, indexes
```

**Total (June 2026):** ~**800+ pytest** functions across **83+** files + **15 Playwright E2E** tests (`test_critical_paths.py`, `test_wedge_flow.py`). CI enforces **70% coverage** on PRs.

**Phase 3 additions:** `tests/test_phase3_score_sprint.py` (10) — wedge E2E mock, unified inbox, M-Pesa renewal, webhook signatures, support staff, money KPI.

**CI security (Phase 3):** Bandit **hard-fails** on medium+ severity (`ci.yml` security job). pip-audit runs without `|| true` but emits `::warning::` if advisories exist (dependency pins may need updates). Secrets grep blocks `INSECURE-dev-key` and Daraja sandbox passkey in `apps/` + `config/`.

### pytest Configuration (pyproject.toml)

```ini
[tool.pytest.ini_options]
DJANGO_SETTINGS_MODULE = "config.settings.development"
python_files = ["tests.py", "test_*.py", "*_tests.py"]
addopts = "--tb=short --strict-markers -q"
markers = ["slow: marks tests as slow"]
```

### Running Tests

```bash
# All tests
pytest

# Specific file
pytest tests/test_content.py

# Specific test
pytest tests/test_content.py::test_post_scheduling

# Verbose
pytest -v

# With coverage (install pytest-cov first)
pip install pytest-cov
pytest --cov=apps --cov-report=html

# Skip slow tests
pytest -m "not slow"
```

### Django Admin Testing

Access Django Admin at `/admin/` (superuser required). Verify all 50+ models are registered and manageable:

| App | Models to Check |
|-----|----------------|
| accounts | User, UserProfile |
| agents | AgentConfig, AgentAction |
| analytics | PostMetric, Competitor, CompetitorAnalysis, CompetitorInsight, Conversion, ConversionJourney, ShopifyStore, WebsiteEvent |
| billing | BillingEvent, MpesaPayment, PlanPrice, DiscountCode, DiscountRedemption |
| briefs | DailyBrief |
| campaigns | Campaign |
| content | Post, ABTest |
| emails | EmailLog, EmailSubscriber, EmailList, EmailCampaign, EmailSequence, SequenceEnrollment |
| engage | Interaction, Superfan |
| leads | Lead, LeadActivity |
| links | KovaPage, KovaLink, KovaForm, FormSubmission, LinkClick, PageView |
| media_queue | MediaQueue, QueueItem |
| memes | TrendingMeme, MemeAdaptation, KenyanEvent, MemePreferences |
| notifications | Notification, NotificationPreference |
| partners | PartnerApplication, Partner, Referral, Commission, MilestoneAward |
| platforms | SocialAccount |
| products | ProductCategory, Product, StockUpdate, StockAlert |
| teams | Team, Brand, TeamActivity |
| whatsapp | All 13 models |

---

## Quick Reference: Test User Plans

For manual testing, create users at each plan level:

```python
from apps.accounts.models import User

# Create test users for each plan
for plan in ['starter', 'growth', 'pro', 'agency']:
    User.objects.create_user(
        email=f'{plan}@test.com',
        password='testpass123',
        full_name=f'Test {plan.title()} User',
        plan=plan,
    )

# Create staff/admin users
User.objects.create_superuser(
    email='admin@test.com',
    password='adminpass123',
    full_name='Admin User',
)
```

## Quick Reference: Feature → Plan → URL

| Feature | Min Plan | Primary URL |
|---------|----------|-------------|
| Content Studio | Starter | `/content/studio/` |
| Content Queue | Starter | `/content/queue/` |
| Calendar | Starter | `/content/calendar/` |
| A/B Testing | Growth | `/content/ab-tests/` |
| AI Images | Growth | `/content/<uuid>/generate-image/` |
| Agents (all 6) | Pro | `/agents/` |
| WhatsApp Suite | Pro | `/whatsapp/` |
| Meme Intelligence | Pro | `/memes/` |
| Campaigns | Growth | `/campaigns/` |
| Email Marketing | Growth | `/emails/marketing/` |
| Kova Pixel | Growth | `/analytics/pixel/` |
| Revenue Dashboard | Growth | `/analytics/revenue/` |
| Competitor Tracking | Growth | `/analytics/competitors/` |
| Teams | Pro | `/teams/` |
| REST API | Pro | `/api/v1/` |
| Lead Capture Forms | Growth | `/links/<uuid>/forms/add/` |
| Admin Dashboard | Staff | `/dashboard/` |

---

*Kova AI — Test everything. Ship with confidence.*
