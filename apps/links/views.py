import logging

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Max, Sum
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST
from django_ratelimit.decorators import ratelimit

from apps.billing.models import get_user_plan_limits
from apps.billing.plan_limit_ui import plan_limit_redirect
from apps.links.forms import (
    KovaFormForm,
    KovaLinkForm,
    KovaPageForm,
    PublicFormSubmissionForm,
)
from apps.links.models import (
    FormSubmission,
    KovaForm,
    KovaLink,
    KovaPage,
    LinkClick,
    PageView,
)

logger = logging.getLogger(__name__)


# ─── Helper ──────────────────────────────────────────────────────────────────

def _get_page_limit(user):
    """Return the max number of Kova pages this user can create."""
    return get_user_plan_limits(user).get("kova_pages", 1)


def _get_link_limit(user):
    """Return the max number of links per page for this user's plan."""
    return get_user_plan_limits(user).get("kova_links_per_page", 5)


def _can_use_forms(user):
    """Forms require kova_forms on the user's plan."""
    return bool(get_user_plan_limits(user).get("kova_forms"))


# ─── Dashboard views (authenticated) ────────────────────────────────────────


@login_required
def page_list(request):
    """List all of the user's Kova pages."""
    pages = (
        KovaPage.objects.filter(user=request.user)
        .annotate(
            link_count=Count("links"),
            form_count=Count("forms"),
        )
    )
    page_limit = _get_page_limit(request.user)
    return render(request, "links/page_list.html", {
        "page_title": "Kova Links",
        "pages": pages,
        "page_limit": page_limit,
        "can_create": pages.count() < page_limit,
        "can_use_forms": _can_use_forms(request.user),
    })


@login_required
def page_create(request):
    """Create a new Kova page."""
    page_limit = _get_page_limit(request.user)
    current_count = KovaPage.objects.filter(user=request.user).count()
    if current_count >= page_limit:
        return plan_limit_redirect(
            request,
            f"Your plan allows up to {page_limit} Kova page(s). Upgrade for more.",
            "links:list",
        )

    if request.method == "POST":
        form = KovaPageForm(request.POST)
        if form.is_valid():
            page = form.save(commit=False)
            page.user = request.user
            page.save()
            messages.success(request, f"Page '{page.title}' created!")
            return redirect("links:page_detail", page_id=page.pk)
    else:
        form = KovaPageForm()

    return render(request, "links/page_form.html", {
        "page_title": "Create Kova Page",
        "form": form,
        "is_edit": False,
    })


@login_required
def page_detail(request, page_id):
    """Dashboard view for a single Kova page — manage links, forms, analytics."""
    page = get_object_or_404(KovaPage, pk=page_id, user=request.user)
    links = page.links.all()
    forms_list = page.forms.all()
    recent_submissions = FormSubmission.objects.filter(form__page=page).select_related("form")[:10]
    link_limit = _get_link_limit(request.user)

    # Analytics — last 30 days
    thirty_days_ago = timezone.now() - timezone.timedelta(days=30)
    daily_views = page.daily_views.filter(date__gte=thirty_days_ago.date()).order_by("date")
    total_clicks_30d = LinkClick.objects.filter(
        link__page=page, clicked_at__gte=thirty_days_ago
    ).count()
    total_submissions_30d = FormSubmission.objects.filter(
        form__page=page, submitted_at__gte=thirty_days_ago
    ).count()

    return render(request, "links/page_detail.html", {
        "page_title": page.title,
        "page": page,
        "links": links,
        "forms_list": forms_list,
        "recent_submissions": recent_submissions,
        "link_limit": link_limit,
        "can_add_link": links.count() < link_limit,
        "can_use_forms": _can_use_forms(request.user),
        "daily_views": daily_views,
        "total_clicks_30d": total_clicks_30d,
        "total_submissions_30d": total_submissions_30d,
    })


@login_required
def page_edit(request, page_id):
    """Edit a Kova page's settings."""
    page = get_object_or_404(KovaPage, pk=page_id, user=request.user)
    if request.method == "POST":
        form = KovaPageForm(request.POST, instance=page)
        if form.is_valid():
            form.save()
            messages.success(request, "Page updated!")
            return redirect("links:page_detail", page_id=page.pk)
    else:
        form = KovaPageForm(instance=page)

    return render(request, "links/page_form.html", {
        "page_title": f"Edit {page.title}",
        "form": form,
        "page": page,
        "is_edit": True,
    })


@login_required
@require_POST
def page_delete(request, page_id):
    """Delete a Kova page and all its links/forms."""
    page = get_object_or_404(KovaPage, pk=page_id, user=request.user)
    title = page.title
    page.delete()
    messages.success(request, f"Page '{title}' deleted.")
    return redirect("links:list")


# ─── Link CRUD ───────────────────────────────────────────────────────────────

@login_required
def link_add(request, page_id):
    """Add a link to a Kova page."""
    page = get_object_or_404(KovaPage, pk=page_id, user=request.user)
    link_limit = _get_link_limit(request.user)
    if page.links.count() >= link_limit:
        return plan_limit_redirect(
            request,
            f"Your plan allows up to {link_limit} links per page. Upgrade for more.",
            "links:page_detail",
            page_id=page.pk,
        )

    if request.method == "POST":
        form = KovaLinkForm(request.POST)
        if form.is_valid():
            link = form.save(commit=False)
            link.page = page
            # Auto-assign next order number
            max_order = page.links.aggregate(m=Max("order"))["m"] or 0
            if not link.order:
                link.order = max_order + 1
            link.save()
            messages.success(request, f"Link '{link.title}' added!")
            return redirect("links:page_detail", page_id=page.pk)
    else:
        form = KovaLinkForm()

    return render(request, "links/link_form.html", {
        "page_title": "Add Link",
        "form": form,
        "page": page,
        "is_edit": False,
    })


@login_required
def link_edit(request, page_id, link_id):
    """Edit a link on a Kova page."""
    page = get_object_or_404(KovaPage, pk=page_id, user=request.user)
    link = get_object_or_404(KovaLink, pk=link_id, page=page)

    if request.method == "POST":
        form = KovaLinkForm(request.POST, instance=link)
        if form.is_valid():
            form.save()
            messages.success(request, "Link updated!")
            return redirect("links:page_detail", page_id=page.pk)
    else:
        form = KovaLinkForm(instance=link)

    return render(request, "links/link_form.html", {
        "page_title": f"Edit {link.title}",
        "form": form,
        "page": page,
        "link": link,
        "is_edit": True,
    })


@login_required
@require_POST
def link_delete(request, page_id, link_id):
    """Delete a link."""
    page = get_object_or_404(KovaPage, pk=page_id, user=request.user)
    link = get_object_or_404(KovaLink, pk=link_id, page=page)
    link.delete()
    messages.success(request, "Link deleted.")
    return redirect("links:page_detail", page_id=page.pk)


# ─── Form CRUD ───────────────────────────────────────────────────────────────

@login_required
def form_add(request, page_id):
    """Add a lead capture form to a Kova page (Growth+ only)."""
    if not _can_use_forms(request.user):
        return plan_limit_redirect(
            request,
            "Lead capture forms are available on Growth+ plans.",
            "links:page_detail",
            page_id=page_id,
        )

    page = get_object_or_404(KovaPage, pk=page_id, user=request.user)

    if request.method == "POST":
        form = KovaFormForm(request.POST)
        if form.is_valid():
            kova_form = form.save(commit=False)
            kova_form.page = page
            kova_form.save()
            messages.success(request, f"Form '{kova_form.title}' added!")
            return redirect("links:page_detail", page_id=page.pk)
    else:
        form = KovaFormForm()

    return render(request, "links/form_form.html", {
        "page_title": "Add Lead Capture Form",
        "form": form,
        "page": page,
        "is_edit": False,
    })


@login_required
def form_edit(request, page_id, form_id):
    """Edit a lead capture form."""
    page = get_object_or_404(KovaPage, pk=page_id, user=request.user)
    kova_form = get_object_or_404(KovaForm, pk=form_id, page=page)

    if request.method == "POST":
        form = KovaFormForm(request.POST, instance=kova_form)
        if form.is_valid():
            form.save()
            messages.success(request, "Form updated!")
            return redirect("links:page_detail", page_id=page.pk)
    else:
        form = KovaFormForm(instance=kova_form)

    return render(request, "links/form_form.html", {
        "page_title": f"Edit {kova_form.title}",
        "form": form,
        "page": page,
        "kova_form": kova_form,
        "is_edit": True,
    })


@login_required
@require_POST
def form_delete(request, page_id, form_id):
    """Delete a lead capture form."""
    page = get_object_or_404(KovaPage, pk=page_id, user=request.user)
    kova_form = get_object_or_404(KovaForm, pk=form_id, page=page)
    kova_form.delete()
    messages.success(request, "Form deleted.")
    return redirect("links:page_detail", page_id=page.pk)


# ─── Submissions ─────────────────────────────────────────────────────────────

@login_required
def submissions_list(request):
    """Redirect legacy submissions URL to the unified lead inbox."""
    from django.shortcuts import redirect
    return redirect("/leads/?source=form_submission")


@login_required
@require_POST
def submission_mark_read(request, submission_id):
    """Mark a submission as read."""
    submission = get_object_or_404(
        FormSubmission, pk=submission_id, form__page__user=request.user
    )
    submission.is_read = True
    submission.save(update_fields=["is_read"])

    if request.htmx:
        return render(request, "links/partials/submission_row.html", {"sub": submission})
    return redirect("/leads/?source=form_submission")


# ─── Public pages (no auth) ─────────────────────────────────────────────────

def public_page(request, slug):
    """
    Public-facing Kova link page — NO authentication required.
    Tracks page views. Renders the user's links and forms.
    """
    page = get_object_or_404(KovaPage, slug=slug, is_published=True)
    links = page.links.filter(is_active=True)
    forms_list = page.forms.filter(is_active=True)

    # Track page view (aggregate by day)
    today = timezone.now().date()
    pv, _ = PageView.objects.get_or_create(page=page, date=today)
    PageView.objects.filter(pk=pv.pk).update(views=models.F("views") + 1)
    KovaPage.objects.filter(pk=page.pk).update(total_views=models.F("total_views") + 1)

    # Build public form if any form exists
    form_instance = None
    active_form = forms_list.first()
    if active_form:
        form_instance = PublicFormSubmissionForm()
        # Adjust required fields based on form config
        if not active_form.show_name_field:
            form_instance.fields.pop("name", None)
        if not active_form.show_phone_field:
            form_instance.fields.pop("phone", None)
        if not active_form.show_message_field:
            form_instance.fields.pop("message", None)

    return render(request, "links/public_page.html", {
        "page": page,
        "links": links,
        "forms_list": forms_list,
        "active_form": active_form,
        "form_instance": form_instance,
    })


@ratelimit(key="ip", rate="10/m", method="POST", block=True)
@require_POST
def public_form_submit(request, slug, form_id):
    """Handle form submission on a public Kova page."""
    page = get_object_or_404(KovaPage, slug=slug, is_published=True)
    kova_form = get_object_or_404(KovaForm, pk=form_id, page=page, is_active=True)

    form = PublicFormSubmissionForm(request.POST)
    if form.is_valid():
        submission = FormSubmission.objects.create(
            form=kova_form,
            name=form.cleaned_data.get("name", ""),
            email=form.cleaned_data["email"],
            phone=form.cleaned_data.get("phone", ""),
            message=form.cleaned_data.get("message", ""),
            referrer=request.META.get("HTTP_REFERER", ""),
            utm_source=request.GET.get("utm_source", ""),
            utm_medium=request.GET.get("utm_medium", ""),
            utm_campaign=request.GET.get("utm_campaign", ""),
            page_slug=slug,
        )

        # Increment form submission count
        KovaForm.objects.filter(pk=kova_form.pk).update(
            total_submissions=models.F("total_submissions") + 1
        )

        # Create notification for page owner
        try:
            from apps.notifications.models import Notification
            Notification.create_for_user(
                user=page.user,
                notification_type=Notification.NotificationType.SYSTEM,
                message=f"New form submission from {submission.name or submission.email} on {page.title}",
            )
        except Exception:
            logger.warning("Could not create notification for form submission")

        if request.htmx:
            return render(request, "links/partials/form_success.html", {
                "success_message": kova_form.success_message,
            })

        messages.success(request, kova_form.success_message)
        return redirect("links:public_page", slug=slug)

    # Form invalid
    if request.htmx:
        return render(request, "links/partials/public_form.html", {
            "active_form": kova_form,
            "form_instance": form,
            "page": page,
        }, status=422)

    # Fallback: re-render full page with errors
    links = page.links.filter(is_active=True)
    forms_list = page.forms.filter(is_active=True)
    return render(request, "links/public_page.html", {
        "page": page,
        "links": links,
        "forms_list": forms_list,
        "active_form": kova_form,
        "form_instance": form,
    })


def public_link_click(request, slug, link_id):
    """
    Redirect through a tracked link.
    Records the click, then sends the visitor to the target URL.
    """
    page = get_object_or_404(KovaPage, slug=slug, is_published=True)
    link = get_object_or_404(KovaLink, pk=link_id, page=page, is_active=True)

    if not link.url:
        raise Http404("Link has no URL")

    # Detect device type from user agent
    ua = request.META.get("HTTP_USER_AGENT", "").lower()
    device = "desktop"
    if any(kw in ua for kw in ("iphone", "android", "mobile")):
        device = "mobile"
    elif "ipad" in ua or "tablet" in ua:
        device = "tablet"

    # Record click
    LinkClick.objects.create(
        link=link,
        referrer=request.META.get("HTTP_REFERER", ""),
        device_type=device,
        utm_source=request.GET.get("utm_source", ""),
        utm_medium=request.GET.get("utm_medium", ""),
        utm_campaign=request.GET.get("utm_campaign", ""),
    )

    # Record touchpoint for multi-touch attribution
    try:
        from apps.analytics.revenue import record_touchpoint
        visitor_id = request.COOKIES.get("kova_vid") or request.META.get("REMOTE_ADDR", "unknown")
        record_touchpoint(
            user=page.user,
            visitor_id=visitor_id,
            touch_type="link_click",
            utm_source=request.GET.get("utm_source", ""),
            utm_medium=request.GET.get("utm_medium", ""),
            utm_campaign=request.GET.get("utm_campaign", ""),
            utm_content=request.GET.get("utm_content", ""),
            referrer=request.META.get("HTTP_REFERER", ""),
            device_type=device,
        )
    except Exception:
        pass  # Non-critical — don't block the redirect

    # Increment counter
    KovaLink.objects.filter(pk=link.pk).update(
        total_clicks=models.F("total_clicks") + 1
    )

    return redirect(link.url)
