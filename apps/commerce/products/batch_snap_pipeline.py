"""Batch Snap pipeline status for the live progress modal (Market Day Mode)."""

from __future__ import annotations

from apps.commerce.products.snap_pipeline import build_batch_item_gallery_payload, build_snap_pipeline_status


def build_batch_snap_pipeline_status(product_ids, user, session_id=None):
    """Aggregate Snap pipeline status across multiple batch-created products."""
    from apps.commerce.products.models import BatchSnapSession, Product

    session = None
    if session_id:
        session = BatchSnapSession.objects.filter(pk=session_id, user=user).first()

    if not product_ids:
        return {
            "status": "failed",
            "terminal": True,
            "error_message": "No products in batch",
            "items": [],
            "total_count": 0,
            "completed_count": 0,
            "processing_count": 0,
            "failed_count": 0,
            "progress_percent": 0,
            "steps": [],
            "log": [],
            "session_status": session.status if session else "",
            "shop_url": session.shop_url if session else "",
            "stall_title": session.stall_title if session else "",
        }

    products = list(
        Product.objects.filter(pk__in=product_ids, user=user).order_by("batch_index", "created_at")
    )
    items = []
    completed = processing = failed = 0

    for product in products:
        snap = build_snap_pipeline_status(product, user)
        item_status = snap["status"]
        if item_status == "completed":
            completed += 1
        elif item_status == "failed":
            failed += 1
        else:
            processing += 1

        current_step = next(
            (s for s in snap["steps"] if s["status"] == "running"),
            None,
        )
        if not current_step:
            current_step = next(
                (s for s in reversed(snap["steps"]) if s["status"] in ("completed", "failed")),
                snap["steps"][0] if snap["steps"] else None,
            )

        items.append({
            "product_id": str(product.pk),
            "product_name": product.name,
            "image_url": product.image.url if product.image else "",
            "status": item_status,
            "current_step": current_step["message"] if current_step else "",
            "current_detail": current_step["detail"] if current_step else "",
            "post_count": snap["post_count"],
            "steps": snap["steps"],
            "seed_id": snap.get("seed_id", ""),
            **build_batch_item_gallery_payload(product, user),
        })

    total = len(items)
    session_finalizing = session and session.status == BatchSnapSession.Status.FINALIZING
    session_done = session and session.status == BatchSnapSession.Status.COMPLETED

    if session_finalizing:
        overall = "processing"
        terminal = False
    elif processing:
        overall = "processing"
        terminal = False
    elif session and session.launch_bundle and not session_done:
        overall = "processing"
        terminal = False
    elif failed and not completed:
        overall = "failed"
        terminal = True
    elif failed:
        overall = "completed"
        terminal = True
    else:
        overall = "completed"
        terminal = True

    stall_label = (session.stall_title if session else "") or "Market Day"
    steps = [
        {
            "id": "batch",
            "message": "Stall snap launched",
            "detail": f"{total} photo{'s' if total != 1 else ''} queued — {stall_label}",
            "status": "completed",
        },
        {
            "id": "analyze",
            "message": "AI identifying each item",
            "detail": f"{completed}/{total} catalogued · {processing} in progress",
            "status": "running" if processing else "completed",
        },
        {
            "id": "content",
            "message": "Writing posts for each item",
            "detail": f"{sum(i['post_count'] for i in items)} platform posts drafted",
            "status": "running" if processing else ("completed" if completed else "pending"),
        },
    ]

    if session and session.launch_bundle:
        bundle_status = "pending"
        bundle_detail = "Waiting for items to finish"
        if session_finalizing:
            bundle_status = "running"
            bundle_detail = "Building showcase reel + stall announcement"
        elif session_done:
            bundle_status = "completed"
            parts = ["Shop updated"]
            if session.bundle_post_ids:
                parts.append("showcase reel")
            if session.bundle_seed_id:
                parts.append("collection post")
            if session.whatsapp_sent:
                parts.append("WhatsApp ping sent")
            bundle_detail = " · ".join(parts)

        steps.append({
            "id": "bundle",
            "message": "Opening your stall",
            "detail": bundle_detail,
            "status": bundle_status,
        })

    log = []
    for item in items:
        if item["status"] == "processing":
            log.append({
                "step": item["product_id"],
                "message": item["product_name"],
                "detail": item["current_detail"] or item["current_step"],
            })
    if session_finalizing:
        log.append({
            "step": "bundle",
            "message": "Stall launch",
            "detail": "Creating showcase reel and collection post…",
        })
    if not log and terminal:
        log.append({
            "step": "done",
            "message": "Stall ready",
            "detail": f"{completed} item{'s' if completed != 1 else ''} live in your shop",
        })

    progress_base = ((completed + failed) / max(total, 1)) * 85
    if session_finalizing:
        progress_base = max(progress_base, 88)
    elif session_done:
        progress_base = 100
    progress_percent = min(98 if overall == "processing" else 100, round(progress_base))

    brand_lock = {}
    if session and isinstance(session.stall_context, dict):
        brand_lock = session.stall_context.get("brand_lock") or {}

    hero_picker_ready = any(item.get("hero_picker_ready") for item in items)

    return {
        "status": overall,
        "terminal": terminal,
        "items": items,
        "total_count": total,
        "completed_count": completed,
        "processing_count": processing,
        "failed_count": failed,
        "steps": steps,
        "log": log[:12],
        "progress_percent": progress_percent,
        "error_message": "" if not failed else f"{failed} item(s) failed — check catalog",
        "session_status": session.status if session else "",
        "shop_url": session.shop_url if session else "",
        "stall_title": session.stall_title if session else "",
        "whatsapp_message": session.whatsapp_message if session else "",
        "brand_lock": brand_lock,
        "hero_picker_ready": hero_picker_ready,
    }
