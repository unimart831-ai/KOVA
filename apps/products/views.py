import csv
import io
import logging

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from apps.billing.models import get_user_plan_limits
from apps.billing.plan_limit_ui import plan_limit_redirect
from apps.products.forms import BulkImportForm, ProductCategoryForm, ProductForm
from apps.products.models import Product, ProductCategory, RestockScan, StockAlert, StockUpdate
from apps.products.plan_gates import product_plan_context
from apps.products.stock_actions import log_stock_change, record_sale

logger = logging.getLogger(__name__)


def _plan_ctx(request):
    return product_plan_context(request.user)


@login_required
def product_list(request):
    products = Product.objects.filter(user=request.user, is_active=True)

    # Filters
    status = request.GET.get("status")
    if status:
        products = products.filter(stock_status=status)
    cat = request.GET.get("category")
    if cat:
        products = products.filter(category_id=cat)
    q = request.GET.get("q", "").strip()
    if q:
        from apps.utils.search import full_text_search
        products = full_text_search(products, q, ["name", "description"])
    featured_only = request.GET.get("featured")
    if featured_only:
        products = products.filter(is_featured=True)

    products = products.select_related("category").order_by("-updated_at")
    paginator = Paginator(products, 24)
    page_obj = paginator.get_page(request.GET.get("page"))

    # Stats
    all_products = Product.objects.filter(user=request.user, is_active=True)
    stats = {
        "total": all_products.count(),
        "in_stock": all_products.filter(stock_status=Product.StockStatus.IN_STOCK).count(),
        "low_stock": all_products.filter(stock_status=Product.StockStatus.LOW_STOCK).count(),
        "out_of_stock": all_products.filter(stock_status=Product.StockStatus.OUT_OF_STOCK).count(),
        "featured": all_products.filter(is_featured=True).count(),
    }

    categories = ProductCategory.objects.filter(user=request.user, is_active=True)
    unread_alerts = StockAlert.objects.filter(user=request.user, is_read=False).count()

    return render(request, "products/product_list.html", {
        "products": page_obj,
        "page_obj": page_obj,
        "stats": stats,
        "categories": categories,
        "unread_alerts": unread_alerts,
        "current_status": status or "",
        "current_category": cat or "",
        "current_q": q,
        "plan_ctx": _plan_ctx(request),
        "batch_product_ids": request.GET.get("batch", ""),
        "batch_session_id": request.GET.get("session", ""),
    })


@login_required
def product_add(request):
    # Plan limit check
    limits = get_user_plan_limits(request.user)
    current_count = Product.objects.filter(user=request.user, is_active=True).count()
    max_products = limits.get("max_products", 5)
    if current_count >= max_products:
        return plan_limit_redirect(
            request,
            f"Your plan allows up to {max_products} products. Upgrade to add more.",
            "products:list",
        )

    if request.method == "POST":
        form = ProductForm(request.POST, request.FILES, user=request.user, plan_ctx=_plan_ctx(request))
        if form.is_valid():
            product = form.save(commit=False)
            product.user = request.user
            if not product.tracks_stock:
                product.stock_status = Product.StockStatus.UNLIMITED
                product.quantity = None
            product.check_low_stock()
            product.save()
            messages.success(request, f"'{product.name}' added to your catalog.")
            return redirect("products:list")
    else:
        form = ProductForm(user=request.user, plan_ctx=_plan_ctx(request))

    return render(request, "products/product_form.html", {
        "form": form,
        "title": "Add to Catalog",
        "submit_label": "Add to Catalog",
        "plan_ctx": _plan_ctx(request),
    })


@login_required
def product_detail(request, product_id):
    product = get_object_or_404(Product, pk=product_id, user=request.user)
    stock_history = product.stock_updates.all()[:20]
    alerts = product.alerts.filter(is_read=False)[:10]

    from apps.content.models import Post
    from apps.products.commerce_autopilot import commerce_autopilot_active, is_placeholder_product_name
    from apps.products.commerce_links import commerce_link_url, ensure_commerce_slug
    from apps.products.commerce_seo import commerce_seo_checklist, shop_index_url
    from apps.products.snap_pipeline import build_snap_pipeline_status

    if not product.commerce_slug:
        ensure_commerce_slug(product)
        product.refresh_from_db()

    commerce_url = commerce_link_url(product, request)
    shop_url = shop_index_url(request.user.profile, request)
    seo_checklist = commerce_seo_checklist(product, request.user.profile)
    pipeline = build_snap_pipeline_status(product, request.user)

    all_posts = list(
        product.posts.select_related("social_account").order_by("-created_at")[:24]
    )
    reel_posts = [p for p in all_posts if p.post_format == Post.PostFormat.REEL]
    carousel_posts = [
        p for p in all_posts
        if p.visual_strategy == "carousel" and p.post_format != Post.PostFormat.REEL
    ]
    feed_posts = [p for p in all_posts if p not in reel_posts and p not in carousel_posts]

    show_autopilot_panel = (
        request.GET.get("snap") == "1"
        or pipeline["status"] == "processing"
        or (
            product.source == Product.Source.SNAP
            and (
                is_placeholder_product_name(product.name)
                or not all_posts
                or pipeline["status"] != "completed"
            )
        )
    )

    import json

    return render(request, "products/product_detail.html", {
        "product": product,
        "stock_history": stock_history,
        "alerts": alerts,
        "reel_posts": reel_posts,
        "carousel_posts": carousel_posts,
        "feed_posts": feed_posts,
        "recent_posts": all_posts[:10],
        "plan_ctx": _plan_ctx(request),
        "snap_building": request.GET.get("snap") == "1",
        "show_autopilot_panel": show_autopilot_panel,
        "commerce_autopilot": commerce_autopilot_active(request.user),
        "name_is_placeholder": is_placeholder_product_name(product.name),
        "commerce_url": commerce_url,
        "shop_url": shop_url,
        "seo_checklist": seo_checklist,
        "pipeline_initial_json": json.dumps(pipeline),
    })


@login_required
def snap_pipeline_status(request, product_id):
    """JSON status for live Snap to Sell pipeline modal."""
    product = get_object_or_404(Product, pk=product_id, user=request.user)
    from apps.products.snap_pipeline import build_snap_pipeline_status

    data = build_snap_pipeline_status(product, request.user)
    data["queue_url"] = reverse("content:queue")
    data["studio_url"] = reverse("content:studio")
    return JsonResponse(data)


@login_required
def restock_pipeline_status(request, scan_id):
    """JSON status for live Receipt to Restock pipeline modal."""
    from apps.products.models import RestockScan
    from apps.products.restock_pipeline import build_restock_pipeline_status

    scan = get_object_or_404(RestockScan, pk=scan_id, user=request.user)
    data = build_restock_pipeline_status(scan)
    data["studio_url"] = reverse("content:studio")
    data["queue_url"] = reverse("content:queue")
    return JsonResponse(data)


@login_required
def batch_snap_pipeline_status(request):
    """JSON status for live Batch Snap pipeline modal."""
    from apps.products.batch_snap_pipeline import build_batch_snap_pipeline_status

    raw = request.GET.get("ids", "")
    product_ids = [p.strip() for p in raw.split(",") if p.strip()]
    session_id = request.GET.get("session", "").strip() or None
    data = build_batch_snap_pipeline_status(
        product_ids, request.user, session_id=session_id,
    )
    data["studio_url"] = reverse("content:studio")
    data["queue_url"] = reverse("content:queue")
    data["catalog_url"] = reverse("products:list")
    return JsonResponse(data)


@login_required
def product_edit(request, product_id):
    product = get_object_or_404(Product, pk=product_id, user=request.user)

    if request.method == "POST":
        old_status = product.stock_status
        old_quantity = product.quantity
        form = ProductForm(request.POST, request.FILES, instance=product, user=request.user, plan_ctx=_plan_ctx(request))
        if form.is_valid():
            product = form.save(commit=False)
            if not product.tracks_stock:
                product.stock_status = Product.StockStatus.UNLIMITED
                product.quantity = None
            product.check_low_stock()
            product.save()

            log_stock_change(
                product,
                previous_status=old_status,
                previous_quantity=old_quantity,
                reason=StockUpdate.Reason.MANUAL,
            )

            messages.success(request, f"'{product.name}' updated.")
            return redirect("products:detail", product_id=product.pk)
    else:
        form = ProductForm(instance=product, user=request.user, plan_ctx=_plan_ctx(request))

    return render(request, "products/product_form.html", {
        "form": form,
        "product": product,
        "title": f"Edit {product.name}",
        "submit_label": "Save Changes",
        "plan_ctx": _plan_ctx(request),
    })


@login_required
@require_POST
def product_delete(request, product_id):
    product = get_object_or_404(Product, pk=product_id, user=request.user)
    name = product.name
    product.is_active = False
    product.save(update_fields=["is_active"])
    messages.success(request, f"'{name}' removed from your catalog.")
    return redirect("products:list")


@login_required
@require_POST
def product_update_stock(request, product_id):
    """Quick stock status/quantity update via HTMX or form POST."""
    product = get_object_or_404(Product, pk=product_id, user=request.user)
    old_status = product.stock_status
    old_quantity = product.quantity

    new_status = request.POST.get("stock_status")
    new_quantity = request.POST.get("quantity")

    if new_status and new_status in Product.StockStatus.values:
        product.stock_status = new_status
    if new_quantity is not None and new_quantity != "":
        product.quantity = int(new_quantity)
        product.check_low_stock()

    product.save(update_fields=["stock_status", "quantity", "updated_at"])

    log_stock_change(
        product,
        previous_status=old_status,
        previous_quantity=old_quantity,
        reason=StockUpdate.Reason.MANUAL,
    )

    if request.headers.get("HX-Request"):
        return render(request, "products/partials/stock_badge.html", {"product": product})

    messages.success(request, f"Stock updated for '{product.name}'.")
    return redirect("products:detail", product_id=product.pk)


@login_required
def product_import(request):
    plan_ctx = _plan_ctx(request)
    if not plan_ctx["csv_import"]:
        return plan_limit_redirect(
            request,
            "CSV import is available on Growth and Pro plans. Upgrade to import products in bulk.",
            "products:list",
        )

    if request.method == "POST":
        form = BulkImportForm(request.POST, request.FILES)
        if form.is_valid():
            limits = get_user_plan_limits(request.user)
            max_products = limits.get("max_products", 5)
            current_count = Product.objects.filter(user=request.user, is_active=True).count()
            remaining = max_products - current_count

            imported = 0
            errors = []

            if form.cleaned_data.get("csv_file"):
                imported, errors = _import_csv(request.user, form.cleaned_data["csv_file"], remaining)
            elif form.cleaned_data.get("bulk_text"):
                imported, errors = _import_bulk_text(request.user, form.cleaned_data["bulk_text"], remaining)

            if imported:
                messages.success(request, f"Imported {imported} product{'s' if imported != 1 else ''}.")
            if errors:
                messages.warning(request, f"{len(errors)} row(s) skipped: {'; '.join(errors[:3])}")
            return redirect("products:list")
    else:
        form = BulkImportForm()

    return render(request, "products/product_import.html", {"form": form, "plan_ctx": plan_ctx})


@login_required
def stock_alerts(request):
    """Stock alert inbox — view and dismiss automation notifications."""
    show = request.GET.get("show", "unread")
    alerts = StockAlert.objects.filter(user=request.user).select_related("product")
    if show != "all":
        alerts = alerts.filter(is_read=False)
    alerts = alerts.order_by("-created_at")[:100]

    unread_count = StockAlert.objects.filter(user=request.user, is_read=False).count()

    return render(request, "products/stock_alerts.html", {
        "alerts": alerts,
        "unread_count": unread_count,
        "show": show,
    })


@login_required
@require_POST
def stock_alert_read(request, alert_id):
    alert = get_object_or_404(StockAlert, pk=alert_id, user=request.user)
    alert.is_read = True
    alert.save(update_fields=["is_read"])
    if request.headers.get("HX-Request"):
        return render(request, "products/partials/alert_row.html", {"alert": alert, "dismissed": True})
    return redirect("products:alerts")


@login_required
@require_POST
def stock_alerts_read_all(request):
    StockAlert.objects.filter(user=request.user, is_read=False).update(is_read=True)
    messages.success(request, "All stock alerts marked as read.")
    return redirect("products:alerts")


@login_required
@require_POST
def product_record_sale(request, product_id):
    """Record a sale and decrement stock (Growth+ quantity tracking)."""
    product = get_object_or_404(Product, pk=product_id, user=request.user)
    plan_ctx = _plan_ctx(request)
    if not plan_ctx["quantity_tracking"]:
        return plan_limit_redirect(
            request,
            "Quantity tracking is available on Growth and Pro plans.",
            "products:detail",
            product_id=product.pk,
        )

    qty_raw = request.POST.get("quantity", "1").strip()
    try:
        qty = max(1, int(qty_raw))
    except ValueError:
        qty = 1

    if not product.tracks_stock or product.quantity is None:
        messages.warning(request, "This product does not track quantity.")
        return redirect("products:detail", product_id=product.pk)

    record_sale(product, quantity=qty)
    messages.success(request, f"Recorded sale of {qty} unit{'s' if qty != 1 else ''} for '{product.name}'.")
    return redirect("products:detail", product_id=product.pk)


def _import_csv(user, csv_file, remaining):
    """Import products from a CSV file. Returns (count, errors)."""
    imported = 0
    errors = []
    try:
        decoded = csv_file.read().decode("utf-8-sig")
        reader = csv.DictReader(io.StringIO(decoded))
        for i, row in enumerate(reader, 1):
            if imported >= remaining:
                errors.append(f"Row {i}: plan limit reached")
                break
            name = row.get("name", "").strip()
            if not name:
                errors.append(f"Row {i}: missing name")
                continue
            price = row.get("price", "").strip()
            status = row.get("stock_status", "in_stock").strip()
            if status not in Product.StockStatus.values:
                status = "in_stock"
            qty = row.get("quantity", "").strip()
            _, created = Product.objects.get_or_create(
                user=user, name=name,
                defaults={
                    "price": float(price) if price else None,
                    "stock_status": status,
                    "quantity": int(qty) if qty else None,
                    "description": row.get("description", "").strip(),
                    "product_url": row.get("product_url", "").strip(),
                    "external_id": row.get("external_id", row.get("sku", "")).strip(),
                    "source": Product.Source.CSV,
                },
            )
            if created:
                imported += 1
            else:
                errors.append(f"Row {i}: '{name}' already exists")
    except Exception as e:
        logger.warning("CSV import error: %s", e)
        errors.append(f"CSV parse error: {e}")
    return imported, errors


def _import_bulk_text(user, text, remaining):
    """Import from pasted text. Each line: name, price, stock_status."""
    imported = 0
    errors = []
    for i, line in enumerate(text.strip().splitlines(), 1):
        if imported >= remaining:
            errors.append(f"Line {i}: plan limit reached")
            break
        line = line.strip()
        if not line:
            continue
        parts = [p.strip() for p in line.split(",")]
        name = parts[0] if parts else ""
        if not name:
            errors.append(f"Line {i}: missing name")
            continue
        price = None
        if len(parts) > 1 and parts[1]:
            try:
                price = float(parts[1])
            except ValueError:
                pass
        status = parts[2] if len(parts) > 2 else "in_stock"
        if status not in Product.StockStatus.values:
            status = "in_stock"
        _, created = Product.objects.get_or_create(
            user=user, name=name,
            defaults={"price": price, "stock_status": status, "source": Product.Source.CSV},
        )
        if created:
            imported += 1
        else:
            errors.append(f"Line {i}: '{name}' already exists")
    return imported, errors


@login_required
def category_list(request):
    categories = ProductCategory.objects.filter(user=request.user, is_active=True).annotate(
        product_count=Count("products", filter=Q(products__is_active=True))
    )
    return render(request, "products/category_list.html", {"categories": categories})


@login_required
def category_add(request):
    if request.method == "POST":
        form = ProductCategoryForm(request.POST)
        if form.is_valid():
            cat = form.save(commit=False)
            cat.user = request.user
            cat.save()
            messages.success(request, f"Category '{cat.name}' created.")
            return redirect("products:categories")
    else:
        form = ProductCategoryForm()

    return render(request, "products/category_form.html", {
        "form": form,
        "title": "Add Category",
    })


@login_required
def category_edit(request, category_id):
    category = get_object_or_404(ProductCategory, pk=category_id, user=request.user)
    if request.method == "POST":
        form = ProductCategoryForm(request.POST, instance=category)
        if form.is_valid():
            form.save()
            messages.success(request, f"Category '{category.name}' updated.")
            return redirect("products:categories")
    else:
        form = ProductCategoryForm(instance=category)

    return render(request, "products/category_form.html", {
        "form": form,
        "title": f"Edit {category.name}",
        "category": category,
    })


@login_required
@require_POST
def category_delete(request, category_id):
    category = get_object_or_404(ProductCategory, pk=category_id, user=request.user)
    name = category.name
    category.is_active = False
    category.save(update_fields=["is_active"])
    Product.objects.filter(user=request.user, category=category).update(category=None)
    messages.success(request, f"Category '{name}' removed.")
    return redirect("products:categories")


@login_required
@require_POST
def promote_product(request, product_id):
    """
    One-click: create a ContentSeed pre-filled with product data, then fire the AI pipeline.
    Creates a seed like "Promote [Product Name] — [Price] — [Description snippet]"
    with the product FK set, so the Create Agent gets full product context.
    """
    from apps.content.models import ContentSeed
    from apps.content.tasks import generate_from_seed
    from apps.utils import fire_task

    product = get_object_or_404(Product, pk=product_id, user=request.user)

    if product.stock_status == Product.StockStatus.OUT_OF_STOCK:
        messages.error(request, f"Cannot promote '{product.name}' — it's out of stock.")
        return redirect("products:detail", product_id=product.pk)

    # Build a rich seed idea from product data
    idea_parts = [f"Promote {product.name}"]
    if product.display_price:
        idea_parts.append(f"at {product.display_price}")
    if product.description:
        desc = product.description[:200]
        idea_parts.append(f"— {desc}")

    notes_parts = []
    if product.product_url:
        notes_parts.append(f"Purchase link: {product.product_url}")
    if product.tags:
        notes_parts.append(f"Tags: {', '.join(product.tags)}")
    if product.stock_status == Product.StockStatus.LOW_STOCK:
        notes_parts.append(f"LOW STOCK — only {product.quantity or 'few'} left. Create urgency!")
    if product.is_featured:
        notes_parts.append("This is a FEATURED product — push harder.")

    seed = ContentSeed.objects.create(
        user=request.user,
        product=product,
        idea=" ".join(idea_parts),
        notes="\n".join(notes_parts),
    )

    fire_task(generate_from_seed, str(seed.id))

    messages.success(request, f"Creating content for '{product.name}' — watch the Autopilot panel below.")
    return redirect(f"{reverse('products:detail', kwargs={'product_id': product.pk})}?snap=1")


@login_required
@require_POST
def quick_post_product(request, product_id):
    """Post product photo as-is to all connected platforms."""
    from apps.products.tasks import quick_post_product_photo
    from apps.utils import fire_task

    product = get_object_or_404(Product, pk=product_id, user=request.user)
    if not product.image and not product.additional_images:
        messages.error(request, "Add a product photo first.")
        return redirect("products:detail", product_id=product.pk)

    fire_task(quick_post_product_photo, str(product.pk))
    messages.success(
        request,
        f"Posting '{product.name}' photo to your connected platforms — appears below in ~30 seconds.",
    )
    return redirect(f"{reverse('products:detail', kwargs={'product_id': product.pk})}?snap=1")


@login_required
@require_POST
def reidentify_product(request, product_id):
    """Re-read product name from photo using vision AI."""
    from apps.products.tasks import reidentify_product_from_photo
    from apps.utils import fire_task

    product = get_object_or_404(Product, pk=product_id, user=request.user)
    fire_task(reidentify_product_from_photo, str(product.pk))
    messages.success(request, "AI is reading the label on your photo to find the product name…")
    return redirect(f"{reverse('products:detail', kwargs={'product_id': product.pk})}?snap=1")


@login_required
@require_POST
def fix_and_promote(request, product_id):
    """One tap: read name → quick photo post → full AI campaign."""
    from apps.products.tasks import fix_and_promote_product
    from apps.utils import fire_task

    product = get_object_or_404(Product, pk=product_id, user=request.user)
    if not product.image and not product.additional_images:
        messages.error(request, "Add a product photo first.")
        return redirect("products:detail", product_id=product.pk)

    if product.stock_status == Product.StockStatus.OUT_OF_STOCK:
        messages.error(request, f"Cannot promote '{product.name}' — it's out of stock.")
        return redirect("products:detail", product_id=product.pk)

    fire_task(fix_and_promote_product, str(product.pk))
    messages.success(
        request,
        "Fix & Promote started — AI is reading your label, posting your photo, "
        "then building reels and platform content. Watch the panel below.",
    )
    return redirect(f"{reverse('products:detail', kwargs={'product_id': product.pk})}?snap=1")


@login_required
@require_POST
def expand_product_photos_view(request, product_id):
    """Manually regenerate scene variations from the primary product photo."""
    from apps.billing.visual_credits import check_visual_credit_limit
    from apps.products.photo_variations import VISUAL_MODE_PRO_SCENE, normalize_visual_mode
    from apps.products.tasks import expand_product_photo_set
    from apps.utils import fire_task

    product = get_object_or_404(Product, pk=product_id, user=request.user)
    if not product.image:
        messages.error(request, "Add a product photo first.")
        return redirect("products:detail", product_id=product.pk)

    visual_mode = normalize_visual_mode(request.POST.get("visual_mode", product.visual_mode))
    if visual_mode not in (Product.VisualMode.AS_IS, VISUAL_MODE_PRO_SCENE):
        visual_mode = normalize_visual_mode(product.visual_mode)

    if visual_mode == VISUAL_MODE_PRO_SCENE:
        allowed, msg = check_visual_credit_limit(request.user)
        if not allowed:
            return plan_limit_redirect(request, msg, "products:detail", product_id=product.pk)

    if visual_mode == Product.VisualMode.AS_IS:
        product.visual_mode = visual_mode
        product.save(update_fields=["visual_mode", "updated_at"])
        messages.info(request, f"Using '{product.name}' photos as uploaded — no enhancement applied.")
        return redirect(f"{reverse('products:detail', kwargs={'product_id': product.pk})}?snap=1")

    product.visual_mode = visual_mode
    product.save(update_fields=["visual_mode", "updated_at"])

    fire_task(expand_product_photo_set, str(product.pk))
    messages.success(
        request,
        f"Plus scene pack started for '{product.name}' — AI backgrounds, studio, and category scenes in ~2 minutes.",
    )
    return redirect(f"{reverse('products:detail', kwargs={'product_id': product.pk})}?snap=1")


@login_required
@require_POST
def toggle_primary_image_view(request, product_id):
    """Hide or restore the original upload in carousels/posts (requires other photos)."""
    product = get_object_or_404(Product, pk=product_id, user=request.user)

    if not product.image:
        messages.error(request, "This product has no original photo.")
        return redirect("products:detail", product_id=product.pk)

    action = request.POST.get("action", "toggle")
    if action == "exclude":
        if not product.additional_images:
            messages.warning(
                request,
                "Generate or add other photos first — you need at least one scene besides the original.",
            )
            return redirect("products:detail", product_id=product.pk)
        product.exclude_primary_image = True
        messages.success(request, "Original photo hidden from carousels and posts. Plus scenes will be used.")
    elif action == "include":
        product.exclude_primary_image = False
        messages.success(request, "Original photo restored for carousels and posts.")
    else:
        if not product.exclude_primary_image and not product.additional_images:
            messages.warning(request, "Add other photos before hiding the original.")
            return redirect("products:detail", product_id=product.pk)
        product.exclude_primary_image = not product.exclude_primary_image
        if product.exclude_primary_image:
            messages.success(request, "Original photo hidden from carousels and posts.")
        else:
            messages.success(request, "Original photo restored for carousels and posts.")

    product.save(update_fields=["exclude_primary_image", "updated_at"])
    return redirect("products:detail", product_id=product.pk)


# ── Snap to Sell ─────────────────────────────────────────────────────

@login_required
def snap_to_sell(request):
    """Camera/upload page — user snaps a product photo."""
    from apps.products.commerce_autopilot import commerce_autopilot_active
    from apps.products.photoroom import studio_polish_unavailable_message

    plan_ctx = _plan_ctx(request)
    return render(
        request,
        "products/snap_to_sell.html",
        {
            "plan_ctx": plan_ctx,
            "commerce_autopilot": commerce_autopilot_active(request.user),
            "visual_credits": plan_ctx.get("visual_credits"),
            "studio_polish_notice": studio_polish_unavailable_message(),
        },
    )


@login_required
@require_POST
def snap_launch(request):
    """
    Receive multiple photos + name + price, create a Product, and fire the
    Snap to Sell background task (vision AI → content pipeline).
    """
    from apps.billing.models import get_user_plan_limits
    from apps.products.commerce_autopilot import commerce_autopilot_active, sanitize_product_name
    from apps.products.image_utils import normalize_uploaded_image
    from apps.products.photo_variations import normalize_visual_mode
    from apps.products.tasks import snap_to_sell_analyze
    from apps.utils import fire_task
    from django.core.files.storage import default_storage

    # Plan limit check
    limits = get_user_plan_limits(request.user)
    current_count = Product.objects.filter(user=request.user, is_active=True).count()
    max_products = limits.get("max_products", 5)
    if current_count >= max_products:
        return plan_limit_redirect(
            request,
            f"Your plan allows up to {max_products} products. Upgrade to add more.",
            "products:snap",
        )

    # Validate required fields
    autopilot = commerce_autopilot_active(request.user)
    name = sanitize_product_name(request.POST.get("name", ""))
    photos = request.FILES.getlist("photos")

    offering_type = request.POST.get("offering_type", "product").strip() or "product"
    if not name:
        messages.error(request, "Please enter a product name.")
        return redirect("products:snap")
    if not photos:
        messages.error(request, "Please upload or take at least one photo.")
        return redirect("products:snap")

    # Cap at 6 images
    photos = photos[:6]

    # Parse required price
    price_raw = request.POST.get("price", "").strip()
    if not price_raw:
        messages.error(request, "Please enter a price.")
        return redirect("products:snap")
    try:
        price = float(price_raw)
        if price <= 0:
            raise ValueError("non-positive")
    except ValueError:
        messages.error(request, "Please enter a valid price greater than zero.")
        return redirect("products:snap")

    currency = request.POST.get("currency", "KES").strip() or "KES"
    description = request.POST.get("description", "").strip()
    photo_context = request.POST.get("photo_context", "").strip()
    raw_visual = request.POST.get("visual_mode", Product.VisualMode.PRO_SCENE).strip()
    if raw_visual not in (Product.VisualMode.AS_IS, Product.VisualMode.PRO_SCENE):
        raw_visual = Product.VisualMode.PRO_SCENE
    visual_mode = normalize_visual_mode(raw_visual)

    if visual_mode == Product.VisualMode.PRO_SCENE:
        from apps.billing.visual_credits import check_visual_credit_limit
        from apps.products.photoroom import studio_polish_unavailable_message

        allowed, msg = check_visual_credit_limit(request.user)
        if not allowed:
            return plan_limit_redirect(
                request,
                msg,
                "products:snap",
            )
        notice = studio_polish_unavailable_message()
        if notice:
            messages.warning(request, notice)

    # Validate offering_type
    valid_types = {c[0] for c in Product.OfferingType.choices}
    if offering_type not in valid_types:
        offering_type = "product"

    # Create the product with the first image as primary
    stock_status = (
        Product.StockStatus.UNLIMITED
        if offering_type in ("service", "digital")
        else Product.StockStatus.IN_STOCK
    )
    product = Product.objects.create(
        user=request.user,
        name=name,
        offering_type=offering_type,
        price=price,
        currency=currency,
        description=description,
        image=normalize_uploaded_image(photos[0]),
        stock_status=stock_status,
        source=Product.Source.SNAP,
        visual_mode=visual_mode,
    )

    # Save additional images (2nd onward) to storage, store URLs
    additional_urls = []
    for extra_photo in photos[1:]:
        normalized = normalize_uploaded_image(extra_photo)
        filename = f"product_images/{product.pk}_{len(additional_urls) + 1}.jpg"
        saved_path = default_storage.save(filename, normalized)
        additional_urls.append(default_storage.url(saved_path))

    if additional_urls:
        product.additional_images = additional_urls
        product.save(update_fields=["additional_images"])

    # Fire background task: vision AI → content generation
    fire_task(snap_to_sell_analyze, str(product.pk), photo_context)

    photo_count = len(photos)
    messages.success(
        request,
        f"📸 '{product.name}' added with {photo_count} photo{'s' if photo_count != 1 else ''}! "
        f"AI is analyzing and creating content — watch the progress popup."
    )
    url = reverse("products:detail", kwargs={"product_id": product.pk})
    return redirect(f"{url}?snap=1")


# ── Batch Snap ───────────────────────────────────────────────────────

@login_required
def snap_batch(request):
    """Batch Snap — Market Day Mode: photograph your whole stall."""
    from django.conf import settings

    return render(request, "products/snap_batch.html", {
        "plan_ctx": _plan_ctx(request),
        "voice_transcribe_url": reverse("products:snap_batch_transcribe"),
        "whatsapp_configured": bool(
            getattr(settings, "WHATSAPP_PHONE_NUMBER_ID", "")
            and getattr(settings, "WHATSAPP_ACCESS_TOKEN", "")
        ),
    })


@login_required
@require_POST
def snap_batch_transcribe(request):
    """Transcribe a voice price brief for Batch Snap."""
    from apps.content.voice import transcribe_audio

    audio = request.FILES.get("audio")
    if not audio:
        return JsonResponse({"error": "No audio file provided."}, status=400)

    content_type = audio.content_type or "audio/webm"
    result = transcribe_audio(audio, content_type)
    if result.get("error"):
        return JsonResponse({"error": result["error"]}, status=400)
    return JsonResponse({"text": result.get("text", ""), "duration": result.get("duration")})


@login_required
@require_POST
def snap_batch_launch(request):
    """
    Market Day Mode launch — up to 10 stall photos → BatchSnapSession → AI pipeline.
    """
    from decimal import Decimal, InvalidOperation

    from apps.billing.models import get_user_plan_limits
    from apps.products.commerce_autopilot import sanitize_product_name
    from apps.products.models import BatchSnapSession
    from apps.products.tasks import snap_batch_process
    from apps.utils import fire_task

    limits = get_user_plan_limits(request.user)
    current_count = Product.objects.filter(user=request.user, is_active=True).count()
    max_products = limits.get("max_products", 5)

    photos = request.FILES.getlist("photos")
    if not photos:
        messages.error(request, "Please add at least one product photo.")
        return redirect("products:snap_batch")

    photos = photos[:10]
    remaining_slots = max_products - current_count
    if remaining_slots <= 0:
        return plan_limit_redirect(
            request,
            f"Your plan allows up to {max_products} products. Upgrade to add more.",
            "products:snap_batch",
        )
    if len(photos) > remaining_slots:
        photos = photos[:remaining_slots]
        messages.warning(
            request,
            f"Only processing {remaining_slots} product(s) — plan limit is {max_products}.",
        )

    offering_type = request.POST.get("offering_type", "product").strip()
    valid_types = {c[0] for c in Product.OfferingType.choices}
    if offering_type not in valid_types:
        offering_type = "product"

    stall_title = request.POST.get("stall_title", "").strip()[:120]
    stall_notes = request.POST.get("stall_notes", "").strip()
    voice_transcript = request.POST.get("voice_transcript", "").strip()
    launch_bundle = request.POST.get("launch_bundle", "1") in ("1", "true", "on")

    default_price = None
    default_price_raw = request.POST.get("default_price", "").strip()
    default_currency = request.POST.get("default_currency", "KES").strip() or "KES"
    if default_price_raw:
        try:
            default_price = Decimal(default_price_raw)
            if default_price <= 0:
                default_price = None
        except (InvalidOperation, ValueError):
            default_price = None

    if not voice_transcript and request.FILES.get("voice_note"):
        from apps.content.voice import transcribe_audio

        vn = request.FILES["voice_note"]
        tr = transcribe_audio(vn, vn.content_type or "audio/webm")
        if tr.get("text"):
            voice_transcript = tr["text"].strip()

    stock_status = (
        Product.StockStatus.UNLIMITED
        if offering_type in ("service", "digital")
        else Product.StockStatus.IN_STOCK
    )

    session = BatchSnapSession.objects.create(
        user=request.user,
        stall_title=stall_title,
        voice_transcript=voice_transcript,
        stall_notes=stall_notes,
        offering_type=offering_type,
        default_price=default_price,
        default_currency=default_currency,
        launch_bundle=launch_bundle,
        product_count=len(photos),
    )

    product_ids = []
    form_prices = {}
    from apps.products.image_utils import normalize_uploaded_image

    for i, photo in enumerate(photos):
        name = sanitize_product_name(request.POST.get(f"name_{i}", ""))
        price_raw = request.POST.get(f"price_{i}", "").strip()
        currency = request.POST.get(f"currency_{i}", default_currency).strip() or default_currency
        context = request.POST.get(f"context_{i}", "").strip()

        if not name:
            name = f"Listing {i + 1}"

        price = None
        if price_raw:
            try:
                price = float(price_raw)
            except ValueError:
                price = None
        elif default_price is not None:
            price = float(default_price)

        product = Product.objects.create(
            user=request.user,
            name=name,
            offering_type=offering_type,
            price=price,
            currency=currency,
            image=normalize_uploaded_image(photo),
            stock_status=stock_status,
            source=Product.Source.SNAP,
            batch_snap_session=session,
            batch_index=i,
        )
        pid = str(product.pk)
        product_ids.append(pid)
        form_prices[pid] = price_raw or (str(default_price) if default_price else "")
        if context:
            session.stall_context.setdefault("item_contexts", {})[pid] = context

    session.stall_context["_form_prices"] = form_prices
    session.save(update_fields=["stall_context"])

    fire_task(snap_batch_process, str(session.pk))

    count = len(product_ids)
    messages.success(
        request,
        f"Market day launched — {count} item{'s' if count != 1 else ''} queued. "
        "AI is identifying each photo and opening your stall.",
    )
    ids_param = ",".join(product_ids)
    url = reverse("products:list")
    return redirect(f"{url}?batch={ids_param}&session={session.pk}")


# ─── RECEIPT TO RESTOCK ─────────────────────────────────────────────────────


@login_required
def restock_scan(request):
    """Upload a receipt photo to auto-restock products."""
    from apps.products.models import RestockScan
    from apps.products.tasks import process_restock_scan
    from apps.utils import fire_task

    if request.method == "POST":
        image = request.FILES.get("receipt")
        if not image:
            messages.error(request, "Please upload a receipt photo.")
            return redirect("products:restock")

        if image.size > 10 * 1024 * 1024:
            messages.error(request, "Image too large. Maximum 10 MB.")
            return redirect("products:restock")

        scan = RestockScan.objects.create(user=request.user, image=image)
        fire_task(process_restock_scan, str(scan.pk))
        messages.success(
            request,
            "Receipt uploaded! Watch the progress popup as AI extracts items and updates stock."
        )
        url = reverse("products:restock")
        return redirect(f"{url}?restock={scan.pk}")

    scans = (
        RestockScan.objects
        .filter(user=request.user)
        .order_by("-created_at")[:30]
    )

    return render(request, "products/restock_scan.html", {
        "scans": scans,
        "plan_ctx": _plan_ctx(request),
        "restock_scan_id": request.GET.get("restock", ""),
    })


@login_required
@require_POST
def restock_retry(request, scan_id):
    """Re-queue a stuck or failed restock scan."""
    from apps.products.models import RestockScan
    from apps.products.tasks import process_restock_scan
    from apps.utils import fire_task

    scan = get_object_or_404(RestockScan, pk=scan_id, user=request.user)
    if scan.status not in (RestockScan.Status.UPLOADED, RestockScan.Status.FAILED):
        messages.info(request, "This scan is already processing or completed.")
        return redirect("products:restock")

    scan.status = RestockScan.Status.UPLOADED
    scan.error_message = ""
    scan.save(update_fields=["status", "error_message"])
    fire_task(process_restock_scan, str(scan.pk))
    messages.success(request, "Scan re-queued — watch the progress popup.")
    url = reverse("products:restock")
    return redirect(f"{url}?restock={scan.pk}")


@login_required
@require_POST
def restock_add_unmatched(request, scan_id):
    """Add an unmatched receipt line to the catalog and apply restock quantity."""
    scan = get_object_or_404(RestockScan, pk=scan_id, user=request.user)
    name = request.POST.get("name", "").strip()
    if not name:
        messages.error(request, "Product name is required.")
        return redirect("products:restock")

    limits = get_user_plan_limits(request.user)
    max_products = limits.get("max_products", 5)
    if Product.objects.filter(user=request.user, is_active=True).count() >= max_products:
        return plan_limit_redirect(
            request,
            f"Your plan allows up to {max_products} products. Upgrade to add more.",
            "products:restock",
        )

    qty_raw = request.POST.get("quantity", "1").strip()
    price_raw = request.POST.get("unit_price", "").strip()
    try:
        quantity = max(1, int(qty_raw))
    except ValueError:
        quantity = 1
    price = None
    if price_raw:
        try:
            price = float(price_raw)
        except ValueError:
            pass

    product = Product.objects.create(
        user=request.user,
        name=name,
        price=price,
        quantity=quantity,
        stock_status=Product.StockStatus.IN_STOCK,
        source=Product.Source.MANUAL,
    )

    log_stock_change(
        product,
        previous_status=Product.StockStatus.IN_STOCK,
        previous_quantity=0,
        reason=StockUpdate.Reason.RESTOCK,
        notes=f"[Receipt to Restock] Added from unmatched line on scan {scan.pk}",
    )

    if name in (scan.items_not_matched or []):
        scan.items_not_matched = [i for i in scan.items_not_matched if i != name]
        scan.products_matched = (scan.products_matched or 0) + 1
        scan.products_updated = (scan.products_updated or 0) + 1
        scan.save(update_fields=["items_not_matched", "products_matched", "products_updated"])

    messages.success(request, f"'{name}' added to catalog with {quantity} units.")
    return redirect("products:restock")
