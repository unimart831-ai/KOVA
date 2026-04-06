"""
Views for the Media Queue app.

Provides queue management, bulk photo upload, drag-drop reorder,
rhythm settings, and queue item CRUD — all with HTMX support.
"""

import json
import logging
import uuid

from django.contrib.auth.decorators import login_required
from django.core.files.base import ContentFile
from django.db import models
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from apps.platforms.models import SocialAccount

from .image_utils import auto_crop
from .models import MediaQueue, QueueItem
from .scheduling import recalculate_schedule

logger = logging.getLogger(__name__)


# ── Queue List ────────────────────────────────────────────────────────────────

@login_required
def queue_list(request):
    """Show all media queues for the user and available platforms."""
    queues = (
        MediaQueue.objects
        .filter(user=request.user)
        .select_related("social_account")
    )
    # Platforms that don't have a queue yet
    existing_account_ids = queues.values_list("social_account_id", flat=True)
    available_accounts = (
        SocialAccount.objects
        .filter(user=request.user, is_active=True)
        .exclude(id__in=existing_account_ids)
    )
    return render(request, "media_queue/queue_list.html", {
        "queues": queues,
        "available_accounts": available_accounts,
    })


# ── Queue Create ──────────────────────────────────────────────────────────────

@login_required
@require_POST
def queue_create(request):
    """Create a new media queue for a social account."""
    account_id = request.POST.get("social_account_id")
    account = get_object_or_404(SocialAccount, pk=account_id, user=request.user, is_active=True)

    queue, created = MediaQueue.objects.get_or_create(
        user=request.user,
        social_account=account,
        defaults={
            "name": f"{account.get_platform_display()} Photos",
            "time_slots": ["09:00", "13:00", "18:00"],
            "active_days": [0, 1, 2, 3, 4],  # Mon-Fri
        },
    )
    return redirect("media_queue:detail", queue_id=queue.pk)


# ── Queue Detail ──────────────────────────────────────────────────────────────

@login_required
def queue_detail(request, queue_id):
    """Show all items in a queue with drag-drop reorder UI."""
    queue = get_object_or_404(MediaQueue, pk=queue_id, user=request.user)
    queued_items = queue.items.filter(status=QueueItem.Status.QUEUED).order_by("order", "created_at")
    published_items = queue.items.filter(status=QueueItem.Status.PUBLISHED).order_by("-published_at")[:20]
    failed_items = queue.items.filter(status=QueueItem.Status.FAILED).order_by("-updated_at")

    return render(request, "media_queue/queue_detail.html", {
        "queue": queue,
        "queued_items": queued_items,
        "published_items": published_items,
        "failed_items": failed_items,
    })


# ── Queue Settings ────────────────────────────────────────────────────────────

@login_required
def queue_settings(request, queue_id):
    """Update rhythm settings for a queue."""
    queue = get_object_or_404(MediaQueue, pk=queue_id, user=request.user)

    if request.method == "POST":
        queue.name = request.POST.get("name", queue.name)
        queue.rhythm_type = request.POST.get("rhythm_type", queue.rhythm_type)
        queue.timezone = request.POST.get("timezone", queue.timezone)
        queue.notify_when_low = int(request.POST.get("notify_when_low", 3))

        # Parse time slots
        rhythm_type = queue.rhythm_type
        if rhythm_type == "daily":
            raw_times = request.POST.getlist("time_slots")
            queue.time_slots = [t.strip() for t in raw_times if t.strip()]
            raw_days = request.POST.getlist("active_days")
            queue.active_days = [int(d) for d in raw_days]
        else:
            # Weekly: parse day+time pairs
            days = request.POST.getlist("slot_day")
            times = request.POST.getlist("slot_time")
            queue.time_slots = [
                {"day": int(d), "time": t.strip()}
                for d, t in zip(days, times)
                if t.strip()
            ]
            queue.active_days = []

        queue.save()
        recalculate_schedule(queue)

        if request.headers.get("HX-Request"):
            return HttpResponse(
                '<div class="text-sm text-green-600 dark:text-green-400">'
                'Settings saved. Schedule recalculated.</div>'
            )
        return redirect("media_queue:detail", queue_id=queue.pk)

    return render(request, "media_queue/queue_settings.html", {"queue": queue})


# ── Queue Toggle (Pause / Resume) ────────────────────────────────────────────

@login_required
@require_POST
def queue_toggle(request, queue_id):
    """Pause or resume a queue."""
    queue = get_object_or_404(MediaQueue, pk=queue_id, user=request.user)
    queue.is_active = not queue.is_active
    queue.save(update_fields=["is_active", "updated_at"])
    if request.headers.get("HX-Request"):
        status = "Active" if queue.is_active else "Paused"
        color = "green" if queue.is_active else "amber"
        return HttpResponse(
            f'<span class="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium '
            f'bg-{color}-100 text-{color}-800 dark:bg-{color}-900/30 dark:text-{color}-400">'
            f'{status}</span>'
        )
    return redirect("media_queue:detail", queue_id=queue.pk)


# ── Queue Delete ──────────────────────────────────────────────────────────────

@login_required
@require_POST
def queue_delete(request, queue_id):
    """Delete a queue and all its items."""
    queue = get_object_or_404(MediaQueue, pk=queue_id, user=request.user)
    queue.delete()
    return redirect("media_queue:list")


# ── Bulk Upload ───────────────────────────────────────────────────────────────

@login_required
@require_POST
def queue_upload(request, queue_id):
    """Upload one or more photos to a queue. Handles auto-crop."""
    queue = get_object_or_404(MediaQueue, pk=queue_id, user=request.user)
    files = request.FILES.getlist("images")

    if not files:
        if request.headers.get("HX-Request"):
            return HttpResponse('<p class="text-sm text-red-500">No files selected.</p>')
        return redirect("media_queue:detail", queue_id=queue.pk)

    # Get current max order
    max_order = queue.items.aggregate(m=models.Max("order"))["m"] or 0
    platform = queue.social_account.platform

    created_items = []
    for i, f in enumerate(files):
        # Validate it's an image
        if not f.content_type.startswith("image/"):
            continue

        item = QueueItem(
            queue=queue,
            order=max_order + i + 1,
        )
        item.image.save(f.name, f, save=False)

        # Auto-crop for the platform
        try:
            cropped_bytes = auto_crop(f, platform)
            crop_name = f"cropped_{uuid.uuid4().hex[:8]}.jpg"
            item.image_cropped.save(crop_name, ContentFile(cropped_bytes), save=False)
        except Exception as exc:
            logger.warning("Auto-crop failed for %s: %s", f.name, exc)

        item.save()
        created_items.append(item)

    # Recalculate schedule with new items
    if created_items:
        recalculate_schedule(queue)

    if request.headers.get("HX-Request"):
        return render(request, "media_queue/partials/queue_items.html", {
            "queue": queue,
            "queued_items": queue.items.filter(status=QueueItem.Status.QUEUED).order_by("order"),
        })

    return redirect("media_queue:detail", queue_id=queue.pk)


# ── Reorder ───────────────────────────────────────────────────────────────────

@login_required
@require_POST
def queue_reorder(request, queue_id):
    """Update item order from drag-drop. Expects JSON: {"order": ["uuid", "uuid", ...]}"""
    queue = get_object_or_404(MediaQueue, pk=queue_id, user=request.user)

    try:
        data = json.loads(request.body)
        item_ids = data.get("order", [])
    except (json.JSONDecodeError, AttributeError):
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    # Bulk update order
    items = QueueItem.objects.filter(queue=queue, pk__in=item_ids, status=QueueItem.Status.QUEUED)
    id_to_item = {str(item.pk): item for item in items}

    for position, item_id in enumerate(item_ids):
        item = id_to_item.get(item_id)
        if item:
            item.order = position

    QueueItem.objects.bulk_update(list(id_to_item.values()), ["order"])
    recalculate_schedule(queue)

    return JsonResponse({"success": True, "reordered": len(item_ids)})


# ── Item Edit (Caption) ──────────────────────────────────────────────────────

@login_required
@require_POST
def item_edit(request, item_id):
    """Update caption for a queue item."""
    item = get_object_or_404(QueueItem, pk=item_id, queue__user=request.user)
    item.caption = request.POST.get("caption", "")
    item.save(update_fields=["caption", "updated_at"])

    if request.headers.get("HX-Request"):
        return render(request, "media_queue/partials/queue_item_card.html", {
            "item": item, "queue": item.queue,
        })
    return redirect("media_queue:detail", queue_id=item.queue_id)


# ── Item Delete ───────────────────────────────────────────────────────────────

@login_required
@require_POST
def item_delete(request, item_id):
    """Remove a single item from the queue."""
    item = get_object_or_404(QueueItem, pk=item_id, queue__user=request.user)
    queue = item.queue
    item.delete()
    recalculate_schedule(queue)

    if request.headers.get("HX-Request"):
        return HttpResponse("")  # Item removed from DOM
    return redirect("media_queue:detail", queue_id=queue.pk)


# ── Item Retry ────────────────────────────────────────────────────────────────

@login_required
@require_POST
def item_retry(request, item_id):
    """Re-queue a failed item."""
    item = get_object_or_404(QueueItem, pk=item_id, queue__user=request.user)
    if item.status == QueueItem.Status.FAILED:
        item.status = QueueItem.Status.QUEUED
        item.error_message = ""
        item.save(update_fields=["status", "error_message", "updated_at"])
        recalculate_schedule(item.queue)

    if request.headers.get("HX-Request"):
        return render(request, "media_queue/partials/queue_item_card.html", {
            "item": item, "queue": item.queue,
        })
    return redirect("media_queue:detail", queue_id=item.queue_id)
