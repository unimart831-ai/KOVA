# Profile Audit — How to Test

A step-by-step guide to verifying the audit → suggest → apply loop works end-to-end. Three test modes:

1. **Automated** — `pytest` runs the unit + view tests with mocked APIs (no real network calls)
2. **Local manual (mocked APIs)** — exercise the full UX in your browser without burning real social-account state
3. **Production-like (real APIs)** — point at a real Facebook Page / Instagram Business / LinkedIn Company you control

Read modes 1 and 2 first. Mode 3 is for confirming the actual API calls work before promoting to production.

---

## Mode 1: Automated unit + integration tests

```powershell
# Windows PowerShell
cd a:\SYSTEMS_2026\SOCIAL_FUTURE\kova_agent
.\venv\Scripts\python.exe -m pytest tests/test_profile_audit.py -v
```

Expected: **26 passed**. Covers:

- Facebook field normalization (silhouette pic = missing, empty containers, hours dict)
- Scoring math (full / empty / thin profiles)
- Suggester static path (phone/website pulled from profile, no LLM call)
- Suggester category mapping (food_restaurant → Restaurant)
- Suggester LLM path (mocked response)
- Suggester refusal when no brand voice + no products
- Auditor full cycle with mocked provider
- Auditor missing-token handling
- Suggestion-generation triggered automatically after audit
- Apply success + failure paths
- View list, detail, approve, dismiss, 404 cross-user

Run a single test for fast iteration:

```powershell
.\venv\Scripts\python.exe -m pytest tests/test_profile_audit.py::test_fb_audit_scoring_full_profile -v
```

---

## Mode 2: Local manual test (no real social accounts)

This walks through the full UX in your browser using fake data. **No real Facebook/Instagram/LinkedIn API calls happen.**

### Setup (one-time)

```powershell
cd a:\SYSTEMS_2026\SOCIAL_FUTURE\kova_agent

# Make sure the new migration is applied
.\venv\Scripts\python.exe manage.py migrate profile_audit

# Start the dev server in one terminal
.\venv\Scripts\python.exe manage.py runserver
```

### Step 1: Seed a test user + fake connected account + a stale audit

In a **second** PowerShell terminal:

```powershell
cd a:\SYSTEMS_2026\SOCIAL_FUTURE\kova_agent
.\venv\Scripts\python.exe manage.py shell
```

Then paste:

```python
from apps.core.accounts.models import User, UserProfile
from apps.core.platforms.models import SocialAccount
from apps.core.profile_audit.models import ProfileAudit, ProfileUpdateSuggestion

# 1. Create the test user (or reuse if you already made one)
u = User.objects.create_user(
    username="audit_demo",
    email="audit_demo@kova.test",
    password="Demo123!",
    full_name="Iranzi Demo",
)
u.onboarding_completed = True
u.is_superuser = True   # so /dashboard/profile-audits/ works too
u.is_staff = True
u.save()

# 2. Profile gives the suggester something to work with
UserProfile.objects.filter(user=u).update(
    country="RW",
    city="Kigali",
    industry="food_restaurant",
    company_name="Briquettes Co",
    brand_voice="Direct, no-nonsense voice for busy households who care about cost and the planet.",
    website_url="https://briquettes.co",
    cta_phone="+250 7xx xxx xxx",
    cta_email="iranzi@briquettes.co",
)

# 3. Fake a connected Facebook Page (real auth not needed for the UI path)
sa = SocialAccount.objects.create(
    user=u, platform="facebook",
    platform_user_id="1234567890",
    username="briquettes_page",
    display_name="Briquettes Co",
    is_active=True,
    access_token="fake_token_for_local_testing",
    metadata={"page_id": "1234567890"},
)

# 4. Manually create a ProfileAudit with realistic gaps
audit = ProfileAudit.objects.create(
    user=u, social_account=sa,
    completeness_score=42,
    fields_present={
        "about": "Briquettes.",
        "website": "https://briquettes.co",
    },
    fields_missing=["phone", "emails", "single_line_address", "hours", "category", "picture"],
    fields_thin=["about"],
)

# 5. Use the real suggester to populate suggestions
#    (this WILL call Claude for the 'about' field — see Step 1b below to mock it)
from apps.core.profile_audit.auditor import _generate_suggestions_for_audit
n = _generate_suggestions_for_audit(audit)
print(f"Created {n} suggestions")
```

### Step 1b: If you don't want to call Claude

Skip the suggester call above and create suggestions manually:

```python
ProfileUpdateSuggestion.objects.create(
    audit=audit, user=u, social_account=sa,
    field_name="phone",
    current_value="",
    suggested_value="+250 7xx xxx xxx",
    reasoning="Pulled from your Kova profile.",
)
ProfileUpdateSuggestion.objects.create(
    audit=audit, user=u, social_account=sa,
    field_name="about",
    current_value="Briquettes.",
    suggested_value="Eco-friendly briquettes for Kigali kitchens. Same-day delivery before noon.",
    reasoning="Brand-voice-aligned and product-anchored.",
)
ProfileUpdateSuggestion.objects.create(
    audit=audit, user=u, social_account=sa,
    field_name="category",
    current_value="",
    suggested_value="Restaurant",
    reasoning="Best match for your industry (food_restaurant).",
)
```

### Step 2: Verify the UI

Log in as `audit_demo@kova.test` / `Demo123!` and visit:

| URL | Expect to see |
|---|---|
| `/platforms/` | Facebook card with a yellow/red **"Profile health · 42/100 · 7 gaps"** badge. Click → goes to detail. |
| `/profile-health/` | Card listing the FB account. Score 42 in red. **"Review →"** button on the right. |
| `/profile-health/<sa.id>/` | Suggestions panel showing each field with current value, suggested value (in kova-blue card), Apply + Dismiss buttons. |
| `/brief/` | Sidebar has a yellow **"Profile health"** alerts card (because score < 70). |
| `/dashboard/profile-audits/` | Ops view: stat cards, score buckets (1 in "Low"), top pending fields, lowest-scoring accounts. |
| `/admin/profile_audit/profileaudit/` | Django admin row with inline suggestions. |

### Step 3: Test the Approve flow (with mocked API)

Without configuring real Facebook OAuth, **clicking Apply will fail** — that's expected. The provider will try to call the real Graph API and get an auth error. To test the success path locally, mock the provider:

```python
# In a separate shell — patch the provider before clicking Apply
from unittest.mock import patch, MagicMock
from apps.core.platforms.providers.base import ProfileUpdateResult

fake_result = ProfileUpdateResult(
    success=True, field_name="phone",
    applied_value="+250 7xx xxx xxx",
)

with patch("apps.core.profile_audit.auditor.get_provider") as mock_get:
    provider = MagicMock()
    provider.update_profile.return_value = fake_result
    mock_get.return_value = provider

    # Click "Apply" in the browser NOW (or simulate it):
    from apps.core.profile_audit.auditor import apply_suggestion
    s = ProfileUpdateSuggestion.objects.filter(field_name="phone").first()
    apply_suggestion(s)

    s.refresh_from_db()
    print(f"Status: {s.status}")  # → 'applied'
    print(f"Applied value: {s.applied_value}")
```

Refresh `/profile-health/<sa.id>/` → the row should now appear under **"Recently applied"** with a green ✓.

### Step 4: Test the Dismiss flow

In the browser, click **Dismiss** on a pending suggestion. The row should swap to a dismissed state via HTMX. Verify in the shell:

```python
ProfileUpdateSuggestion.objects.filter(status="dismissed").count()  # → 1
```

### Step 5: Test the Daily Brief callout

Visit `/brief/`. Because the user has an account scoring < 70, the sidebar should show a yellow **Profile health** alerts card listing the Facebook account. Click → goes to the detail page.

### Step 6: Test the Re-audit button

On the detail page, click **"Re-audit now"**. This queues a new audit. With no real API connected, the audit will fail (with a friendly error) and add a new row. Verify history:

```python
ProfileAudit.objects.filter(social_account=sa).count()  # → 2 or more
```

### Cleanup

```python
SocialAccount.objects.filter(user=u).delete()
ProfileAudit.objects.filter(user=u).delete()
User.objects.filter(pk=u.pk).delete()
```

---

## Mode 3: Production-like test (real APIs)

Use this **only** after Mode 2 passes. You need a real Facebook Page (or IG Business / LinkedIn Company) that **you control** and don't mind Kova editing.

### Step 1: Connect a real account

1. Log in to your dev Kova install
2. Visit `/platforms/` → click **Connect Facebook**
3. Complete the OAuth flow with a test FB account that has at least one Page
4. Pick a test Page (preferably one you don't use publicly)

### Step 2: Manually trigger an audit

In the shell:

```python
from apps.core.platforms.models import SocialAccount
from apps.core.profile_audit.auditor import audit_social_account

sa = SocialAccount.objects.filter(user__email="your@email.test", platform="facebook").first()
audit = audit_social_account(sa, generate_suggestions=True)

print(f"Score: {audit.completeness_score}/100")
print(f"Missing: {audit.fields_missing}")
print(f"Thin: {audit.fields_thin}")
print(f"Suggestions: {audit.suggestions.count()}")

# Inspect raw API response
import json
print(json.dumps(audit.raw_profile, indent=2)[:500])
```

If the audit succeeds, you'll see real field values from the FB Graph API. If it fails, the `audit.error` field will tell you why (usually a scope problem).

### Step 3: Apply a real suggestion

**Warning: this writes to your actual Facebook Page.** Pick a low-stakes field like `about`:

```python
s = audit.suggestions.filter(field_name="about").first()
print(f"Will set 'about' to: {s.suggested_value}")

# Confirm via the web UI by clicking Apply at /profile-health/<sa.id>/
# OR force it from the shell:
from apps.core.profile_audit.auditor import apply_suggestion
apply_suggestion(s)
s.refresh_from_db()
print(f"Status: {s.status}")
print(f"Error: {s.error_message}")
print(f"API response: {s.api_response}")
```

Then visit the actual Facebook Page in a browser and confirm the About field updated.

### Step 4: Verify re-audit reflects the change

```python
audit2 = audit_social_account(sa, generate_suggestions=False)
print(f"New score: {audit2.completeness_score}/100")  # Should be higher
print(f"Old missing: {audit.fields_missing}")
print(f"New missing: {audit2.fields_missing}")  # 'about' should no longer be thin/missing
```

---

## Running the nightly task on demand (any mode)

The Celery beat schedule runs `profile_audit.run_profile_audits` daily at 02:00 UTC. To run it immediately:

```python
from apps.core.profile_audit.tasks import run_profile_audits, audit_one_account

# Fan-out (queues per-account tasks)
result = run_profile_audits()
print(result)  # → {'audited': N, 'errors': 0}

# Or audit a specific account synchronously
from apps.core.platforms.models import SocialAccount
sa = SocialAccount.objects.filter(platform="facebook").first()
result = audit_one_account(str(sa.id))
print(result)
```

If you have Celery running, `.delay()` works:

```python
audit_one_account.delay(str(sa.id))   # async — check the worker log
```

---

## Common issues

| Symptom | Cause | Fix |
|---|---|---|
| Audit row has `error="No access token stored"` | Token never set or wiped | Reconnect the account at `/platforms/` |
| Audit row has `error="Authentication failed"` | Token expired / revoked / wrong scopes | For FB/IG: the OAuth flow asks for `pages_manage_metadata`. If user revoked, reconnect. |
| Audit succeeds but no suggestions | User has no brand voice + no products set | Fill in `brand_voice` and at least one product in settings — the suggester refuses to generate generic text without context |
| Apply fails with HTTP 400 | Platform rejected the value (too short / wrong format) | Check `suggestion.error_message` and `suggestion.api_response` for the platform's explanation. Edit the suggestion in Django admin and retry. |
| Apply succeeds but UI still shows old value | Browser cache, or re-audit hasn't run | Click "Re-audit now" or wait for the post-apply auto re-audit |
| LinkedIn member-profile suggestion appears | Bug — member profiles can't be updated via API | Filter the suggestion out manually; LinkedIn doesn't support member writes |

---

## Quick smoke test (one-liner)

After any change to the auditor or suggester:

```powershell
.\venv\Scripts\python.exe manage.py check && .\venv\Scripts\python.exe -m pytest tests/test_profile_audit.py
```

If both pass with 26 tests green, the core engine is healthy.

---

## What to check in production after Railway redeploys

1. Visit `/dashboard/profile-audits/` (as a superuser) — should show "No audits yet" until the nightly task runs at 02:00 UTC
2. Connect a Facebook Page to a test user
3. Manually trigger the audit via the shell on Railway:

   ```bash
   railway run python manage.py shell
   >>> from apps.core.profile_audit.tasks import run_profile_audits
   >>> run_profile_audits()
   ```

4. Verify the audit row appears in `/admin/profile_audit/profileaudit/`
5. Visit `/profile-health/` as that test user — score should be visible
6. Don't push real API updates from production until you've tested in dev with the same FB account first
