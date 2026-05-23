# Reel music beds

Royalty-free background tracks for motion Reels.

**→ Upload beats in Admin:** `/dashboard/reel-music/`  
**→ Full guide:** `docs/REEL_MUSIC.md`

Metadata lives in `apps/content/data/reel_music_catalog.json` (seed) and
`reel-beds/catalog.json` on cloud storage (live catalog after admin uploads).

## Layout

```
static/audio/reel-beds/
  upbeat/
  calm/
  urgent/
```

Drop MP3 files matching catalog `file` paths (e.g. `upbeat/sunrise-drive.mp3`).

## Populate placeholders (dev)

```bash
python manage.py seed_reel_music_beds
```

Generates silent 30s MP3 placeholders via FFmpeg so compose works before
real tracks are added. Replace with licensed beds from Pixabay, Mixkit,
Uppbeat, or commissioned African beats.

## Production

Run `collectstatic` so beds upload to R2/S3 under `media/` or serve from CDN.
Attribution text is stored per track in the catalog and surfaced in post metadata.
