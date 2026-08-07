"""Admin dashboard — Agency / Wakala sales inquiries."""

from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from apps.core.admin_dashboard.decorators import staff_required
from apps.core.billing.models import AgencySalesInquiry


@staff_required
def sales_inquiry_list(request):
    qs = AgencySalesInquiry.objects.select_related("user").order_by("-created_at")

    status = request.GET.get("status")
    if status in dict(AgencySalesInquiry.Status.choices):
        qs = qs.filter(status=status)

    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(
            Q(name__icontains=q)
            | Q(email__icontains=q)
            | Q(company_name__icontains=q)
            | Q(phone__icontains=q),
        )

    paginator = Paginator(qs, 50)
    page = paginator.get_page(request.GET.get("page"))

    status_counts = {
        row["status"]: row["count"]
        for row in AgencySalesInquiry.objects.values("status").annotate(count=Count("id"))
    }

    return render(request, "admin_dashboard/billing/sales_inquiries_list.html", {
        "page_title": "Agency Sales Inquiries",
        "page_obj": page,
        "status_choices": AgencySalesInquiry.Status.choices,
        "current_status": status or "",
        "current_q": q,
        "new_count": status_counts.get(AgencySalesInquiry.Status.NEW, 0),
        "status_counts": status_counts,
    })


@staff_required
def sales_inquiry_detail(request, pk):
    inquiry = get_object_or_404(
        AgencySalesInquiry.objects.select_related("user"),
        pk=pk,
    )

    if request.method == "POST":
        new_status = request.POST.get("status", "").strip()
        staff_notes = request.POST.get("staff_notes", "").strip()
        update_fields = ["staff_notes", "updated_at"]

        if new_status in dict(AgencySalesInquiry.Status.choices):
            if new_status != inquiry.status:
                inquiry.status = new_status
                update_fields.append("status")
                now = timezone.now()
                if new_status == AgencySalesInquiry.Status.CONTACTED and not inquiry.contacted_at:
                    inquiry.contacted_at = now
                    update_fields.append("contacted_at")
                if new_status == AgencySalesInquiry.Status.CLOSED and not inquiry.closed_at:
                    inquiry.closed_at = now
                    update_fields.append("closed_at")
                if new_status == AgencySalesInquiry.Status.NEW:
                    inquiry.contacted_at = None
                    inquiry.closed_at = None
                    update_fields.extend(["contacted_at", "closed_at"])

        inquiry.staff_notes = staff_notes
        inquiry.save(update_fields=list(dict.fromkeys(update_fields)))
        messages.success(request, "Inquiry updated.")
        return redirect("admin_dashboard:sales_inquiry_detail", pk=pk)

    return render(request, "admin_dashboard/billing/sales_inquiry_detail.html", {
        "page_title": f"Inquiry: {inquiry.company_name or inquiry.name}",
        "inquiry": inquiry,
        "status_choices": AgencySalesInquiry.Status.choices,
    })
