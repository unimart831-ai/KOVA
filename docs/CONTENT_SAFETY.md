# Content Safety

Kova blocks **clearly sexual or sexually explicit** images and captions **before** they reach social platforms. Moderation runs via OpenRouter vision/text models with a fail-closed default in production (API errors), but **benefit of the doubt** on borderline vision results.

## Policy scope (sexual/explicit only)

- Categories: `adult`, `sexual`, `nudity`, `porn`
- Block only when the model is highly confident (severity ≥ 85 by default)
- **Not flagged:** construction, architecture, normal street/work clothing, news violence, catalog swimwear, medical/educational imagery, etc.
- Text blocklist (slurs, threats, scam patterns) still runs locally and can block captions independently

## Environment variables

| Variable | Default | Description |
|----------|---------|-------------|
| `CONTENT_SAFETY_ENABLED` | `False` (dev), `True` (production) | Deploy kill-switch; when false, moderation never runs |
| `OPENROUTER_API_KEY` | — | Required when safety is enabled |
| `CONTENT_SAFETY_MODEL` | `google/gemini-2.0-flash-001` | OpenRouter model slug for moderation |
| `CONTENT_SAFETY_HIGH_SEVERITY_THRESHOLD` | `85` | Min severity for block, snap block, strikes, staff email |
| `CONTENT_SAFETY_STRIKE_SUSPEND_THRESHOLD` | `3` | Strikes before Snap is blocked via strike count |
| `CONTENT_SAFETY_SNAP_BLOCK_HOURS` | `72` | Per-user Snap block duration after violation |
| `CONTENT_SAFETY_NOTIFY_EMAIL` | — | Optional extra recipient for high-severity alerts |

## OpenRouter model

Default: **`google/gemini-2.0-flash-001`** — vision-capable, fast, and cost-effective for image + text JSON moderation prompts.

Override with `CONTENT_SAFETY_MODEL` if you prefer another OpenRouter vision model (e.g. `openai/gpt-4o-mini`).

## Pipeline gates

1. **Snap upload** (`snap_launch`) — sync image check before product creation
2. **Snap analyze** (`snap_to_sell_analyze`, `snap_batch_process`) — block before content generation
3. **Post approval** (`approve_post_for_user`) — check caption + media
4. **Publish** (`publish_post`) — final gate; sets `post.status=blocked`, never calls Meta
5. **Vision** (`analyze_image(content_safety_check=True)`) — optional early gate

When `CONTENT_SAFETY_ENABLED=true` and the OpenRouter API fails, content is treated as **unsafe** (fail-closed).

## Admin dashboard

Staff → **Content Safety** (`/dashboard/content-safety/`):

- **Overview** — pending review count, incidents today, global auto-publish status
- **Review queue** — flagged incidents (sensitive placeholder, no explicit thumbnails)
- **Incident detail** — dismiss, confirm violation, suspend user, pause auto-publish
- **Safety checks toggle** — pause/resume all moderation (vision, API, blocklist); superuser POST to `/dashboard/content-safety/checks-toggle/`
- **Auto-publish toggle** — separate control; pause/resume platform-wide auto-publish only

When staff pause checks (`SystemSafetyConfig.content_safety_checks_enabled=false`), all `check_*` paths return safe with no API calls or incidents. When `CONTENT_SAFETY_ENABLED=false` at deploy, moderation is off entirely (text blocklist may still run in dev — see tests).

Link to user usage: `/dashboard/users/<uuid>/usage/`

## User-facing messages

- Snap: *"This image violates Kova content policy and cannot be used."*
- Queue (blocked posts): policy message in `publish_error`

## Data model

- `ContentSafetyIncident` — audit log with review workflow
- `SystemSafetyConfig` (singleton) — `auto_publish_paused`, `content_safety_checks_enabled`, pause audit fields
- `UserProfile.content_safety_strike_count`, `suspended_for_policy`, `auto_publish_paused`

## Tests

```bash
pytest tests/test_content_safety.py -v
```
