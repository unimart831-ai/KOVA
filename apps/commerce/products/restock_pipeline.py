"""Receipt to Restock pipeline status for the live progress modal."""

from __future__ import annotations

from datetime import timedelta

from django.utils import timezone as tz

SCAN_TIMEOUT = timedelta(minutes=10)
SEED_TIMEOUT = timedelta(minutes=5)


def _step(step_id, message, detail="", status="pending"):
    return {"id": step_id, "message": message, "detail": detail, "status": status}


def build_restock_pipeline_status(scan):
    """Derive restock scan progress from scan record and linked content seed."""
    now = tz.now()
    stale = scan.created_at < now - SCAN_TIMEOUT
    seed = scan.content_seed
    error_message = scan.error_message or ""

    steps = []

    steps.append(
        _step("upload", "Receipt uploaded", "Photo saved and queued for analysis", "completed")
    )

    # Analyze
    if scan.status in ("uploaded", "analyzing"):
        if stale:
            analyze_status = "failed"
            analyze_detail = "Analysis timed out — try uploading again"
            error_message = error_message or analyze_detail
        else:
            analyze_status = "running"
            analyze_detail = (
                "Vision AI is extracting line items and prices…"
                if scan.status == "analyzing"
                else "Waiting for AI to read your receipt…"
            )
    elif scan.extracted_items or scan.status in ("matching", "updating", "completed"):
        analyze_status = "completed"
        count = len(scan.extracted_items or [])
        analyze_detail = f"{count} line item{'s' if count != 1 else ''} extracted from receipt"
        if scan.supplier_name:
            analyze_detail += f" · Supplier: {scan.supplier_name}"
    elif scan.status == "failed":
        analyze_status = "failed"
        analyze_detail = error_message or "Could not read receipt"
    else:
        analyze_status = "pending"
        analyze_detail = "Waiting to start…"

    steps.append(_step("analyze", "AI reading receipt", analyze_detail, analyze_status))

    # Match
    if analyze_status != "completed":
        match_status = "skipped" if analyze_status == "failed" else "pending"
        match_detail = (
            "Waiting for receipt analysis…"
            if analyze_status != "failed"
            else "Skipped — analysis failed"
        )
    elif scan.status == "matching":
        match_status = "running"
        match_detail = "Fuzzy-matching item names to your catalog…"
    else:
        match_status = "completed"
        matched = scan.products_matched or 0
        unmatched = len(scan.items_not_matched or [])
        match_detail = f"{matched} matched to catalog"
        if unmatched:
            match_detail += f", {unmatched} need manual add"

    steps.append(_step("match", "Matching to catalog", match_detail, match_status))

    # Stock
    if scan.status == "updating":
        stock_status = "running"
        stock_detail = "Adding quantities to matched products…"
    elif scan.status == "completed":
        stock_status = "completed"
        updated = scan.products_updated or 0
        stock_detail = f"{updated} product{'s' if updated != 1 else ''} restocked"
    elif scan.status == "failed" and scan.products_updated:
        stock_status = "completed"
        stock_detail = f"{scan.products_updated} updated before failure"
    elif scan.status == "failed":
        stock_status = "skipped"
        stock_detail = "Stock update did not complete"
    elif match_status == "completed":
        stock_status = "running"
        stock_detail = "Updating inventory quantities…"
    else:
        stock_status = "pending"
        stock_detail = "Waiting for product matching…"

    steps.append(_step("stock", "Updating stock levels", stock_detail, stock_status))

    # Content
    if scan.status != "completed":
        if scan.status == "failed":
            content_status = "skipped"
            content_detail = "Skipped — pipeline did not finish"
        else:
            content_status = "pending"
            content_detail = "Will queue 'back in stock' posts after stock updates"
    elif not scan.products_updated:
        content_status = "skipped"
        content_detail = "No matched products — add unmatched items to catalog first"
    elif seed:
        if seed.status in ("new", "processing"):
            if seed.updated_at < now - SEED_TIMEOUT:
                content_status = "failed"
                content_detail = "Content generation timed out"
            else:
                content_status = "running"
                content_detail = "Create Agent is writing 'back in stock' announcement posts…"
        elif seed.status == "failed":
            content_status = "failed"
            content_detail = seed.error_message or "Content generation failed"
        else:
            content_status = "completed"
            content_detail = f"Back-in-stock campaign ready ({seed.posts.count()} posts)"
    else:
        content_status = "skipped"
        content_detail = "No content seed created"

    steps.append(_step("content", "Back-in-stock content", content_detail, content_status))

    if scan.status == "completed":
        overall = "completed"
    elif scan.status == "failed":
        overall = "failed"
    elif stale and scan.status == "uploaded":
        overall = "failed"
    else:
        overall = "processing"

    terminal = overall in ("completed", "failed") and (
        overall == "failed"
        or content_status in ("completed", "skipped", "failed")
    )

    log = []
    for step in steps:
        if step["status"] == "skipped":
            continue
        log.append({"step": step["id"], "message": step["message"], "detail": step["detail"]})
        if step["status"] == "running":
            break

    completed_steps = sum(1 for s in steps if s["status"] == "completed")
    progress_percent = min(
        98 if overall == "processing" else 100,
        round((completed_steps / max(len(steps), 1)) * 100),
    )

    posts = []
    if seed:
        posts = [
            {
                "id": str(p.id),
                "platform": (
                    p.social_account.get_platform_display()
                    if p.social_account
                    else p.platform
                ),
                "preview": (p.content_text or "")[:120],
                "media_status": p.media_status,
                "status": p.status,
            }
            for p in seed.posts.select_related("social_account").order_by("created_at")
        ]

    return {
        "scan_id": str(scan.pk),
        "status": overall,
        "scan_status": scan.status,
        "steps": steps,
        "log": log,
        "extracted_items": scan.extracted_items or [],
        "items_not_matched": scan.items_not_matched or [],
        "products_matched": scan.products_matched or 0,
        "products_updated": scan.products_updated or 0,
        "supplier_name": scan.supplier_name or "",
        "posts": posts,
        "post_count": len(posts),
        "seed_id": str(seed.pk) if seed else "",
        "error_message": error_message,
        "terminal": terminal,
        "progress_percent": progress_percent,
    }
