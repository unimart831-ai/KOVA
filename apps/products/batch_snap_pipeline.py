"""Batch Snap pipeline status for the live progress modal."""

from __future__ import annotations

from apps.products.snap_pipeline import build_snap_pipeline_status


def build_batch_snap_pipeline_status(product_ids, user):
    """Aggregate Snap pipeline status across multiple batch-created products."""
    from apps.products.models import Product

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
        }

    products = list(
        Product.objects.filter(pk__in=product_ids, user=user).order_by("created_at")
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
        })

    total = len(items)
    if processing:
        overall = "processing"
    elif failed and not completed:
        overall = "failed"
    elif failed:
        overall = "completed"
    else:
        overall = "completed"

    terminal = processing == 0

    steps = [
        {
            "id": "batch",
            "message": "Batch Snap launched",
            "detail": f"{total} product{'s' if total != 1 else ''} queued for AI analysis",
            "status": "completed",
        },
        {
            "id": "analyze",
            "message": "Analyzing each product photo",
            "detail": f"{completed}/{total} complete · {processing} in progress",
            "status": "running" if processing else "completed",
        },
        {
            "id": "content",
            "message": "Generating platform posts",
            "detail": f"{sum(i['post_count'] for i in items)} posts drafted so far",
            "status": "running" if processing else ("completed" if completed else "pending"),
        },
    ]

    log = []
    for item in items:
        if item["status"] == "processing":
            log.append({
                "step": item["product_id"],
                "message": item["product_name"],
                "detail": item["current_detail"] or item["current_step"],
            })
    if not log and terminal:
        log.append({
            "step": "done",
            "message": "Batch complete",
            "detail": f"{completed} product{'s' if completed != 1 else ''} ready",
        })

    progress_percent = min(
        98 if overall == "processing" else 100,
        round(((completed + failed) / max(total, 1)) * 100),
    )

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
        "error_message": "" if not failed else f"{failed} product(s) failed — check catalog for details",
    }
