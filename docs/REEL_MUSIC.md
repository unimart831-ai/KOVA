# Reel Music — Admin Upload Guide

Motion reels in Kova Agent combine product photos with a **background music bed** using FFmpeg. This guide explains how to add, replace, and manage beats without editing code.

---

## Quick start (admin dashboard)

1. Log in as a **staff** user (admin account).
2. Open **Admin → Reel Music**  
   URL: `/dashboard/reel-music/`
3. Fill in **Upload new beat**:
   - **Track title** — e.g. `Afro Groove 3`
   - **Mood** — `upbeat`, `calm`, or `urgent`
   - **MP3 file** — royalty-free or licensed audio (max 15 MB)
   - **Duration** — length in seconds (default 30)
   - **Source** — where the music came from (Pixabay, commissioned, etc.)
   - **Attribution** — optional credit line shown in reel metadata
4. Click **Upload beat**.

New reels will pick from the catalog automatically based on post mood.

You can also **Replace** or **Delete** any existing track from the list on the same page.

---

## Moods — when each is used

| Mood | Used for | Examples |
|------|----------|----------|
| **upbeat** | Default product promos, Snap listings | Most commerce reels |
| **calm** | Tips, guides, wellness, authority posts | “How to…”, educational copy |
| **urgent** | Sales, offers, limited stock | “50% off”, “today only” |

The system picks **one track** from the matching mood pool. The same post always gets the same track (stable seed).

---

## Where files are stored

| Location | Purpose |
|----------|---------|
| `static/audio/reel-beds/{mood}/{file}.mp3` | Local copy on the server (FFmpeg reads this) |
| Cloud storage `reel-beds/…` (R2 in production) | Persistent copy — survives Railway redeploys |
| `reel-beds/catalog.json` (cloud) | Live catalog index after admin uploads |
| `apps/content/data/reel_music_catalog.json` (git) | Seed catalog shipped with the codebase |

**Production:** After you upload via the admin UI, the catalog and MP3s are saved to **cloud storage**. You do not need to commit files to git for them to work on Railway.

**Local dev:** Files save under `static/audio/reel-beds/` and update the local JSON catalog.

---

## Replace a silent placeholder

Railway runs `seed_reel_music_beds` on deploy, which creates **silent** MP3 placeholders so compose never crashes. To add real music:

1. Go to **Reel Music** in admin.
2. Find a placeholder track (e.g. `Sunrise Drive`).
3. Use **Replace** → choose your real MP3 → submit.

Or upload a **new beat** with a fresh title.

---

## Legal — what music can you use?

Use only music you have rights to:

- **Royalty-free** libraries: [Pixabay Music](https://pixabay.com/music/), [Mixkit](https://mixkit.co/free-stock-music/), [Uppbeat](https://uppbeat.io/)
- **Commissioned** beats (your own “Kova Original”)
- **Do not** upload trending TikTok/Instagram songs unless you have a commercial license

Set **Attribution** when the license requires it (e.g. `Artist Name — Pixabay`).

---

## Technical requirements

- **Format:** MP3 only  
- **Max size:** 15 MB per upload  
- **Length:** 25–35 seconds recommended (reels are short)  
- **FFmpeg** must be installed on the worker (already on Railway)

---

## Verify music is working

1. **Admin → Reel Music** — track shows **Ready** (green), not **Missing**.
2. **Admin → Operations** — “Reel music catalog” section shows all tracks OK.
3. Snap a product → wait for motion reel compose → open post in Content Studio.
4. Reel preview should show **Music: Upbeat/Calm/Urgent** and play audio when previewing the MP4.

---

## CLI (optional — developers)

```bash
# Create silent placeholders for every catalog slot (dev / first deploy)
python manage.py seed_reel_music_beds

# Force overwrite all placeholders
python manage.py seed_reel_music_beds --force
```

Prefer the **admin dashboard** for real beats.

---

## Troubleshooting

| Problem | Fix |
|---------|-----|
| Track shows **Missing** | Re-upload or Replace the MP3 from Reel Music admin |
| Reel has no sound | Track file missing; run Replace or upload new beat |
| Wrong mood on reel | Post copy drives mood — sales text → urgent, tips → calm |
| Upload fails | Check MP3 format and file size under 15 MB |
| Changes lost after deploy | Ensure R2 env vars are set on Railway (`AWS_STORAGE_BUCKET_NAME`, etc.) |

---

## Architecture (for developers)

```
Admin upload
  → add_track() / replace_track_file()
  → MP3 → static/audio/reel-beds/ + R2 reel-beds/
  → catalog → reel_music_catalog.json + R2 catalog.json

Reel compose (compose_reel_video)
  → infer_mood_from_post() or visual_metadata.music_mood
  → pick_music_track(mood, seed=post_id)
  → resolve_track_path() — local file or download from R2 cache
  → FFmpeg muxes images + audio → MP4
```

Key modules:

- `apps/content/reel_music.py` — catalog + file I/O
- `apps/admin_dashboard/views/reel_music.py` — upload UI
- `apps/content/tasks.py` — `compose_reel_video`
- `apps/content/video_compose.py` — FFmpeg pipeline

---

## Related docs

- `static/audio/reel-beds/README.md` — folder layout
- `docs/platform-audits/REELS_AND_VIDEO_STRATEGY.md` — reel strategy notes
