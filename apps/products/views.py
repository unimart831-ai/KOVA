import csv
import io
import logging

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from apps.billing.models import get_plan_limits
from apps.products.forms import BulkImportForm, ProductCategoryForm, ProductForm
from apps.products.models import Product, ProductCategory, StockAlert, StockUpdate

logger = logging.getLogger(__name__)


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
        products = products.filter(Q(name__icontains=q) | Q(description__icontains=q))
    featured_only = request.GET.get("featured")
    if featured_only:
        products = products.filter(is_featured=True)

    products = products.select_related("category")[:200]

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
        "products": products,
        "stats": stats,
        "categories": categories,
        "unread_alerts": unread_alerts,
        "current_status": status or "",
        "current_category": cat or "",
        "current_q": q,
    })


@login_required
def product_add(request):
    # Plan limit check
    limits = get_plan_limits(request.user.profile.plan)
    current_count = Product.objects.filter(user=request.user, is_active=True).count()
    max_products = limits.get("max_products", 5)
    if current_count >= max_products:
        messages.error(request, f"Your plan allows up to {max_products} products. Upgrade to add more.")
        return redirect("products:list")

    if request.method == "POST":
        form = ProductForm(request.POST, request.FILES, user=request.user)
        if form.is_valid():
            product = form.save(commit=False)
            product.user = request.user
            product.check_low_stock()
            product.save()
            messages.success(request, f"'{product.name}' added to your catalog.")
            return redirect("products:list")
    else:
        form = ProductForm(user=request.user)

    return render(request, "products/product_form.html", {
        "form": form,
        "title": "Add to Catalog",
        "submit_label": "Add to Catalog",
    })


@login_required
def product_detail(request, product_id):
    product = get_object_or_404(Product, pk=product_id, user=request.user)
    stock_history = product.stock_updates.all()[:20]
    alerts = product.alerts.filter(is_read=False)[:10]
    recent_posts = product.posts.order_by("-created_at")[:10]

    return render(request, "products/product_detail.html", {
        "product": product,
        "stock_history": stock_history,
        "alerts": alerts,
        "recent_posts": recent_posts,
    })


@login_required
def product_edit(request, product_id):
    product = get_object_or_404(Product, pk=product_id, user=request.user)

    if request.method == "POST":
        old_status = product.stock_status
        old_quantity = product.quantity
        form = ProductForm(request.POST, request.FILES, instance=product, user=request.user)
        if form.is_valid():
            product = form.save(commit=False)
            product.check_low_stock()
            product.save()

            # Log stock change if status or quantity changed
            if product.stock_status != old_status or product.quantity != old_quantity:
                StockUpdate.objects.create(
                    product=product,
                    previous_status=old_status,
                    new_status=product.stock_status,
                    previous_quantity=old_quantity,
                    new_quantity=product.quantity,
                    reason=StockUpdate.Reason.MANUAL,
                )

            messages.success(request, f"'{product.name}' updated.")
            return redirect("products:detail", product_id=product.pk)
    else:
        form = ProductForm(instance=product, user=request.user)

    return render(request, "products/product_form.html", {
        "form": form,
        "product": product,
        "title": f"Edit {product.name}",
        "submit_label": "Save Changes",
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

    if product.stock_status != old_status or product.quantity != old_quantity:
        StockUpdate.objects.create(
            product=product,
            previous_status=old_status,
            new_status=product.stock_status,
            previous_quantity=old_quantity,
            new_quantity=product.quantity,
            reason=StockUpdate.Reason.MANUAL,
        )

    if request.headers.get("HX-Request"):
        return render(request, "products/partials/stock_badge.html", {"product": product})

    messages.success(request, f"Stock updated for '{product.name}'.")
    return redirect("products:detail", product_id=product.pk)


@login_required
def product_import(request):
    if request.method == "POST":
        form = BulkImportForm(request.POST, request.FILES)
        if form.is_valid():
            limits = get_plan_limits(request.user.profile.plan)
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

    return render(request, "products/product_import.html", {"form": form})


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
            defaults={"price": price, "stock_status": status},
        )
        if created:
            imported += 1
        else:
            errors.append(f"Line {i}: '{name}' already exists")
    return imported, errors


@login_required
def category_list(request):
    categories = ProductCategory.objects.filter(user=request.user).annotate(
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

    messages.success(request, f"Creating content for '{product.name}' — posts will appear in your Content Studio shortly.")
    return redirect("content:studio")
