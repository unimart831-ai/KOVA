# Content Safety

Kova blocks explicit, violent, or policy-violating images and captions **before** they reach social platforms. Moderation runs via OpenRouter vision/text models with a fail-closed default in production.

## Policy categories

- `adult`, `sexual`, `nudity`, `porn`, `graphic_violence`

Product catalog photos (clothing on mannequins, swimwear listings, etc.) are generally allowed. Explicit nudity, pornography, sexual acts, and graphic gore are blocked.

## Environment variables

| Variable | Default | Description |
|----------|---------|-------------|
| `CONTENT_SAFETY_ENABLED` | `False` (dev), `True` (production) | Master switch |
| `OPENROUTER_API_KEY` | — | Required when safety is enabled |
| `CONTENT_SAFETY_MODEL` | `google/gemini-2.0-flash-001` | OpenRouter model slug for moderation |
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
- **Global controls** — pause/resume platform-wide auto-publish

Link to user usage: `/dashboard/users/<uuid>/usage/`

## User-facing messages

- Snap: *"This image violates Kova content policy and cannot be used."*
- Queue (blocked posts): policy message in `publish_error`

## Data model

- `ContentSafetyIncident` — audit log with review workflow
- `SystemSafetyConfig` (singleton) — `auto_publish_paused`, who toggled, when
- `UserProfile.content_safety_strike_count`, `suspended_for_policy`, `auto_publish_paused`

## Tests

```bash
pytest tests/test_content_safety.py -v
```
