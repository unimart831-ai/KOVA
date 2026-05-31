# Stories Publishing (Instagram & Facebook)

Kova publishes **Stories** to Instagram Professional accounts and Facebook Pages via the Meta Graph API. Stories are ephemeral (24 hours) vertical media — distinct from feed posts and Reels.

## Supported platforms

| Platform | API | Status |
|----------|-----|--------|
| **Instagram** | Instagram Graph API (`media_type=STORIES`) | ✅ Supported |
| **Facebook Page** | Page Stories API (`photo_stories` / `video_stories`) | ✅ Supported |
| TikTok | No standard Stories endpoint | ❌ Not supported |
| LinkedIn | No Stories API | ❌ Not supported |
| WhatsApp Status | Separate app (`apps/whatsapp`) | See Status Studio |

## Post format

Stories use `post_format="story"` on the `Post` model. The publish pipeline routes this to `provider.publish_story()`.

- **Aspect ratio:** 9:16 (`aspect_ratio=story`)
- **Media:** One image (JPEG/PNG) or one video (MP4/MOV, max 60s for FB Page video stories)
- **Caption:** Instagram accepts optional caption on container; Facebook Stories are media-only via this API

## Permissions required

### Instagram

| Permission | Purpose |
|------------|---------|
| `instagram_content_publish` | Create and publish Story containers |
| `pages_manage_metadata` | Resolve linked Page + IG Business account |
| `pages_show_list` | List Pages during OAuth |

Page access token (stored in `SocialAccount.metadata["page_access_token"]`) is used for publishing.

### Facebook Page

| Permission | Purpose |
|------------|---------|
| `pages_manage_posts` | Upload photos and publish Stories |
| `pages_read_engagement` | Optional — story insights |
| `pages_show_list` | Page selection during connect |

Page admin must have **CREATE_CONTENT** task on the Page.

## Publishing flow

### Instagram

1. `POST /{ig-user-id}/media` with `media_type=STORIES` + `image_url` or `video_url` (public HTTPS)
2. Poll container until `status_code=FINISHED`
3. `POST /{ig-user-id}/media_publish` with `creation_id`

Implemented in `InstagramProvider.publish_story()`.

### Facebook Page — photo

1. `POST /{page-id}/photos` with `published=false` (URL or direct upload)
2. `POST /{page-id}/photo_stories` with `photo_id`

### Facebook Page — video

1. `POST /{page-id}/video_stories?upload_phase=start`
2. Upload to `rupload.facebook.com` with `Authorization: OAuth {page_token}` + `file_url`
3. `POST /{page-id}/video_stories?upload_phase=finish&video_id=…`

Implemented in `FacebookProvider.publish_story()`.

## Media URLs

Meta requires **public HTTPS** URLs for Instagram Stories and for Facebook video Stories (hosted upload). Kova resolves storage paths via `_public_url_for_file(..., for_platform_api=True)` — presigned R2/S3 URLs when no custom CDN domain is set.

Photo Stories to Facebook Pages can also use **direct byte upload** from storage when no public URL is available.

## UI entry points

| Location | What |
|----------|------|
| **Studio** | Create Agent generates `post_format=story` for Instagram; filter by Story format |
| **Queue** | Filter by Story format; approve / schedule / publish like other posts |
| **Post detail / cards** | 9:16 story preview frame with STORY badge |
| **Memes pipeline** | Can emit story-format adaptations |

Manual flow: compose a seed targeting Instagram → AI may produce a Story variant → approve → publish or schedule.

## Plan limits

Stories count toward **`max_posts_per_month`** like any other post. No separate stories cap.

## Troubleshooting

| Error | Fix |
|-------|-----|
| `Instagram requires publicly accessible HTTPS image URLs` | Configure `AWS_S3_CUSTOM_DOMAIN` or ensure presigned URLs work |
| `Stories require an image or video` | Regenerate media in Studio or upload a 9:16 attachment |
| `Stories are not supported on {platform}` | Only Instagram and Facebook support Stories in Kova |
| FB video story `NotAuthorizedError` on upload | Ensure Page token uses `OAuth` header (not Bearer) on rupload |

## Related docs

- [KOVA_PLATFORM_SETUP_GUIDE.md](./KOVA_PLATFORM_SETUP_GUIDE.md) — OAuth and App Review
- [platform-audits/FACEBOOK.md](./platform-audits/FACEBOOK.md) — Facebook capability matrix
- WhatsApp Status: `/whatsapp/status/` (separate product surface)
