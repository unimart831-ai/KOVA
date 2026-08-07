"""Admin dashboard — reel music catalog upload and management."""

from pathlib import Path

from django.contrib import messages
from django.http import FileResponse, Http404
from django.shortcuts import redirect, render
from django.views.decorators.http import require_GET, require_POST

from apps.core.admin_dashboard.decorators import staff_required
from apps.create.content.reel_music import (
    STORAGE_PREFIX,
    VALID_MOODS,
    add_track,
    delete_track,
    get_track_by_id,
    load_music_catalog,
    replace_track_file,
    resolve_track_path,
)


def _track_rows():
    rows = []
    for track in load_music_catalog():
        rows.append({
            **track,
            "file_ok": bool(resolve_track_path(track)),
        })
    return rows


@staff_required
def reel_music_manage(request):
    """Upload and manage royalty-free reel background tracks."""
    by_mood = {mood: [] for mood in VALID_MOODS}
    for row in _track_rows():
        mood = row.get("mood", "upbeat")
        if mood in by_mood:
            by_mood[mood].append(row)

    missing = sum(1 for row in _track_rows() if not row["file_ok"])

    return render(request, "admin_dashboard/reel_music/manage.html", {
        "page_title": "Reel Music",
        "tracks_by_mood": by_mood,
        "moods": VALID_MOODS,
        "music_total": len(_track_rows()),
        "music_missing": missing,
    })


@staff_required
@require_POST
def reel_music_upload(request):
    """Upload a new track to the catalog."""
    title = request.POST.get("title", "").strip()
    mood = request.POST.get("mood", "upbeat").strip()
    attribution = request.POST.get("attribution", "").strip()
    source = request.POST.get("source", "uploaded").strip() or "uploaded"
    duration_raw = request.POST.get("duration_sec", "").strip()
    audio = request.FILES.get("audio")

    if not audio:
        messages.error(request, "Please choose an MP3 file to upload.")
        return redirect("admin_dashboard:reel_music_manage")

    name_lower = (audio.name or "").lower()
    if not name_lower.endswith(".mp3"):
        messages.error(request, "Only MP3 files are supported.")
        return redirect("admin_dashboard:reel_music_manage")

    if audio.size > 15 * 1024 * 1024:
        messages.error(request, "File too large — maximum 15 MB.")
        return redirect("admin_dashboard:reel_music_manage")

    duration_sec = 30
    if duration_raw:
        try:
            duration_sec = max(5, min(int(float(duration_raw)), 120))
        except ValueError:
            messages.error(request, "Duration must be a number (seconds).")
            return redirect("admin_dashboard:reel_music_manage")

    try:
        track = add_track(
            title=title,
            mood=mood,
            uploaded_file=audio,
            attribution=attribution,
            source=source,
            duration_sec=duration_sec,
        )
    except ValueError as exc:
        messages.error(request, str(exc))
        return redirect("admin_dashboard:reel_music_manage")

    messages.success(
        request,
        f"Added “{track['title']}” ({track['mood']}) — reels can use it immediately.",
    )
    return redirect("admin_dashboard:reel_music_manage")


@staff_required
@require_POST
def reel_music_replace(request, track_id):
    """Replace the MP3 for an existing catalog track."""
    audio = request.FILES.get("audio")
    if not audio:
        messages.error(request, "Choose an MP3 file to replace this track.")
        return redirect("admin_dashboard:reel_music_manage")

    if not (audio.name or "").lower().endswith(".mp3"):
        messages.error(request, "Only MP3 files are supported.")
        return redirect("admin_dashboard:reel_music_manage")

    if audio.size > 15 * 1024 * 1024:
        messages.error(request, "File too large — maximum 15 MB.")
        return redirect("admin_dashboard:reel_music_manage")

    try:
        track = replace_track_file(track_id, audio)
    except ValueError as exc:
        messages.error(request, str(exc))
        return redirect("admin_dashboard:reel_music_manage")

    messages.success(request, f"Replaced audio for “{track.get('title', track_id)}”.")
    return redirect("admin_dashboard:reel_music_manage")


@staff_required
@require_POST
def reel_music_delete(request, track_id):
    """Remove a track from the catalog."""
    if delete_track(track_id, remove_file=True):
        messages.success(request, "Track removed from catalog.")
    else:
        messages.error(request, "Track not found.")
    return redirect("admin_dashboard:reel_music_manage")


@staff_required
@require_GET
def reel_music_preview(request, track_id):
    """Stream an MP3 for staff preview in the admin catalog."""
    track = get_track_by_id(track_id)
    if not track:
        raise Http404("Track not found")

    local_path = resolve_track_path(track)
    if local_path and local_path.is_file():
        return FileResponse(
            local_path.open("rb"),
            content_type="audio/mpeg",
            as_attachment=False,
            filename=local_path.name,
        )

    rel = (track.get("file") or "").replace("\\", "/").lstrip("/")
    if not rel:
        raise Http404("Track file not configured")

    from django.core.files.storage import default_storage

    storage_key = f"{STORAGE_PREFIX}{rel}"
    if not default_storage.exists(storage_key):
        raise Http404("Track file missing")

    return FileResponse(
        default_storage.open(storage_key, "rb"),
        content_type="audio/mpeg",
        as_attachment=False,
        filename=Path(rel).name,
    )
