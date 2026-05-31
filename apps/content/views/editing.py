import json

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST, require_http_methods

from apps.content.forms import PostEditForm
from apps.content.models import Post
from apps.teams.permissions import can_edit_post
from apps.utils import fire_task


@login_required
@require_POST
def delete_post(request, post_id):
    """Soft-delete a post (HTMX). Removes it from the studio."""
    post = get_object_or_404(Post.objects.select_related("user"), id=post_id)
    if not can_edit_post(request.user, post):
        raise Http404
    if post.status in (Post.Status.PUBLISHED, Post.Status.PUBLISHING):
        return HttpResponse("Cannot delete a published post", status=400)
    post.soft_delete()
    return HttpResponse("")


@login_required
def regenerate_post(request, post_id):
    """Kick off async regeneration and return a polling card."""
    from apps.content.tasks import regenerate_post_async

    post = get_object_or_404(Post.objects.select_related("social_account", "user"), id=post_id)
    if not can_edit_post(request.user, post):
        raise Http404

    if request.method != "POST":
        return HttpResponse(status=405)

    if post.status not in (
        Post.Status.DRAFT,
        Post.Status.PENDING_APPROVAL,
        Post.Status.REJECTED,
    ):
        return render(request, "components/post_card.html", {"post": post})

    request.session[f"regen_{post.id}"] = post.content_text[:100]

    fire_task(regenerate_post_async, str(post.id))

    return render(request, "components/_post_regenerating.html", {"post": post})


@login_required
def regenerate_status(request, post_id):
    """HTMX polling endpoint: returns updated post card once regeneration is done."""
    post = get_object_or_404(Post.objects.select_related("social_account", "user"), id=post_id)
    if not can_edit_post(request.user, post):
        raise Http404

    old_snippet = request.session.get(f"regen_{post.id}", "")
    current_snippet = post.content_text[:100]

    if old_snippet and current_snippet != old_snippet:
        request.session.pop(f"regen_{post.id}", None)
        return render(request, "components/post_card.html", {"post": post})

    return render(request, "components/_post_regenerating.html", {"post": post})


@login_required
def edit_post(request, post_id):
    """Edit a post's content."""
    post = get_object_or_404(Post.objects.select_related("social_account", "seed", "user"), id=post_id)
    if not can_edit_post(request.user, post):
        raise Http404
    if request.method == "POST":
        form = PostEditForm(request.POST, instance=post)
        if form.is_valid():
            old_content = post.content_text
            post = form.save(commit=False)

            content_changed = post.content_text != old_content
            if content_changed and post.status in (
                Post.Status.PENDING_APPROVAL,
                Post.Status.APPROVED,
                Post.Status.SCHEDULED,
            ):
                post.status = Post.Status.DRAFT

            if content_changed and post.status == Post.Status.REJECTED:
                post.status = Post.Status.PENDING_APPROVAL

            update_fields = ["content_text", "updated_at"]
            if content_changed:
                update_fields.append("status")
            update_fields.extend(["cta_type", "cta_text", "cta_url", "first_comment"])
            if post.cta_type != "none" and post.cta_url:
                post.populate_utm()
                update_fields.extend(["utm_source", "utm_medium", "utm_campaign", "utm_content"])
            post.save(update_fields=update_fields)

            if content_changed:
                from apps.agents.memory import record_edit_feedback
                from apps.content.models import PostVersion
                record_edit_feedback(post)
                last_ver = post.versions.order_by("-version_number").values_list("version_number", flat=True).first()
                PostVersion.objects.create(
                    post=post,
                    version_number=(last_ver or 0) + 1,
                    content_text=post.content_text,
                    source="user_edit",
                    edited_by=request.user,
                )

            messages.success(request, "Post updated.")
            return redirect("content:studio")
    else:
        form = PostEditForm(instance=post)

    return render(request, "content/edit.html", {
        "post": post,
        "form": form,
        "page_title": "Edit Post",
        "user_kova_pages": request.user.kova_pages.filter(is_published=True).only("slug", "title")[:10],
    })


@login_required
def upload_media(request, post_id):
    """Upload an image to a post."""
    from io import BytesIO

    from PIL import Image

    from apps.content.models import MediaAttachment

    post = get_object_or_404(Post.objects.select_related("user"), id=post_id)
    if not can_edit_post(request.user, post):
        raise Http404
    if request.method == "POST" and request.FILES.get("file"):
        uploaded = request.FILES["file"]
        if uploaded.size > 10 * 1024 * 1024:
            return HttpResponse("File too large (max 10MB)", status=400)

        allowed_types = ["image/jpeg", "image/png", "image/gif", "image/webp"]
        if uploaded.content_type not in allowed_types:
            return HttpResponse("Unsupported file type", status=400)

        try:
            img = Image.open(uploaded)
            img.verify()
            actual_format = img.format
            if actual_format not in ("JPEG", "PNG", "GIF", "WEBP"):
                return HttpResponse("Invalid image file", status=400)
        except Exception:
            return HttpResponse("Invalid or corrupted image file", status=400)

        uploaded.seek(0)
        if actual_format in ("JPEG", "PNG", "WEBP"):
            try:
                img = Image.open(uploaded)
                clean = BytesIO()
                clean_img = Image.new(img.mode, img.size)
                clean_img.putdata(list(img.getdata()))
                save_fmt = actual_format if actual_format != "JPEG" else "JPEG"
                save_kwargs = {"format": save_fmt}
                if save_fmt == "JPEG":
                    save_kwargs["quality"] = 95
                clean_img.save(clean, **save_kwargs)
                clean.seek(0)
                from django.core.files.uploadedfile import InMemoryUploadedFile
                uploaded = InMemoryUploadedFile(
                    clean, "file", uploaded.name, uploaded.content_type,
                    clean.getbuffer().nbytes, uploaded.charset,
                )
            except Exception:
                uploaded.seek(0)

        file_type = "image"
        if uploaded.content_type == "image/gif":
            file_type = "gif"

        order = post.attachments.count()
        attachment = MediaAttachment.objects.create(
            post=post,
            file=uploaded,
            file_type=file_type,
            alt_text=request.POST.get("alt_text", ""),
            order=order,
        )
        if post.media_status != Post.MediaStatus.GENERATED:
            post.media_status = Post.MediaStatus.UPLOADED
            post.save(update_fields=["media_status", "updated_at"])
        return render(request, "content/_media_item.html", {"attachment": attachment})

    return HttpResponse(status=405)


@login_required
@require_POST
def retry_image(request, post_id):
    """Retry AI image generation for a post that failed."""
    post = get_object_or_404(Post.objects.select_related("user", "social_account"), id=post_id)
    if not can_edit_post(request.user, post):
        raise Http404
    if post.media_status != Post.MediaStatus.FAILED:
        return HttpResponse("Post image did not fail", status=400)

    prompt = post.media_prompt or ""
    if not prompt.strip():
        messages.error(request, "No image prompt available to retry.")
        return redirect("content:edit", post_id=post.id)

    post.media_status = Post.MediaStatus.PENDING
    post.save(update_fields=["media_status", "updated_at"])

    from apps.content.tasks import retry_image_generation
    fire_task(retry_image_generation, str(post.id))

    if request.headers.get("HX-Request"):
        return HttpResponse(
            '<span class="text-[10px] font-medium px-2 py-0.5 rounded-md '
            'bg-yellow-50 text-yellow-600 dark:bg-yellow-950 dark:text-yellow-400">'
            '⏳ Retrying…</span>'
        )
    messages.info(request, "Retrying image generation…")
    return redirect("content:edit", post_id=post.id)


@login_required
@require_POST
def retry_reel(request, post_id):
    """Retry motion reel composition for a failed or stuck reel post."""
    post = get_object_or_404(Post.objects.select_related("user", "social_account"), id=post_id)
    if not can_edit_post(request.user, post):
        raise Http404
    if post.post_format != Post.PostFormat.REEL:
        return HttpResponse("Not a reel post", status=400)

    from apps.content.tasks import _queue_reel_compose

    meta = dict(post.visual_metadata or {})
    meta.pop("video_compose_error", None)
    post.visual_metadata = meta
    post.media_status = Post.MediaStatus.GENERATED
    post.save(update_fields=["visual_metadata", "media_status", "updated_at"])

    _queue_reel_compose(str(post.id))

    if request.headers.get("HX-Request"):
        return render(request, "components/post_card.html", {"post": post})
    messages.info(request, "Re-composing motion reel…")
    return redirect("content:edit", post_id=post.id)


@login_required
@require_POST
def retry_publish(request, post_id):
    """Retry publishing a failed post — resets to APPROVED and fires publish task."""
    from django.utils import timezone
    from apps.content.tasks import publish_post
    from apps.utils import fire_task

    post = get_object_or_404(Post.objects.select_related("user", "social_account"), id=post_id)
    if not can_edit_post(request.user, post):
        raise Http404
    if post.status != Post.Status.FAILED:
        return HttpResponse("Post is not in failed state", status=400)

    post.status = Post.Status.APPROVED
    post.scheduled_at = timezone.now()
    post.ai_reasoning = ""
    post.publish_error = ""
    post.save(update_fields=["status", "scheduled_at", "ai_reasoning", "publish_error", "updated_at"])

    fire_task(publish_post, str(post.id))

    if request.headers.get("HX-Request"):
        return render(request, "components/post_card.html", {"post": post})
    messages.info(request, "Retrying publish…")
    return redirect("content:queue")


@login_required
@require_POST
def update_carousel_slides(request, post_id):
    """Save edited carousel slide content (heading, body, image_prompt)."""
    post = get_object_or_404(Post.objects.select_related("user"), id=post_id)
    if not can_edit_post(request.user, post):
        raise Http404
    if post.post_format != Post.PostFormat.CAROUSEL:
        return HttpResponse("Not a carousel post", status=400)

    try:
        slides_raw = json.loads(request.POST.get("carousel_slides_json", "[]"))
        if not isinstance(slides_raw, list):
            raise ValueError
        clean_slides = []
        for s in slides_raw:
            if not isinstance(s, dict):
                continue
            clean_slides.append({
                "heading": str(s.get("heading", ""))[:200],
                "body": str(s.get("body", ""))[:2000],
                "image_prompt": str(s.get("image_prompt", ""))[:500],
                "image_url": str(s.get("image_url", "")),
            })
    except (json.JSONDecodeError, ValueError):
        if request.headers.get("HX-Request"):
            return HttpResponse("Invalid slide data", status=400)
        messages.error(request, "Invalid slide data.")
        return redirect("content:edit", post_id=post.id)

    post.carousel_slides = clean_slides
    post.save(update_fields=["carousel_slides", "updated_at"])

    if request.headers.get("HX-Request"):
        return HttpResponse(
            '<span id="slides-save-feedback" class="text-xs text-emerald-600 dark:text-emerald-400 font-medium">'
            '✓ Slides saved</span>'
        )
    messages.success(request, "Slides updated.")
    return redirect("content:edit", post_id=post.id)


@login_required
@require_POST
def generate_image(request, post_id):
    """Generate an AI image for a post that doesn't have one yet (opt-in for text-first platforms)."""
    post = get_object_or_404(
        Post.objects.select_related("user", "user__profile", "social_account"), id=post_id,
    )
    if not can_edit_post(request.user, post):
        raise Http404

    if post.media_status in (Post.MediaStatus.GENERATED, Post.MediaStatus.PENDING):
        if request.headers.get("HX-Request"):
            return HttpResponse(
                '<span class="text-[10px] font-medium px-2 py-0.5 rounded-md '
                'bg-yellow-50 text-yellow-600 dark:bg-yellow-950 dark:text-yellow-400">'
                'Image already exists or is generating</span>'
            )
        return redirect("content:edit", post_id=post.id)

    from apps.billing.models import get_user_plan_limits
    from apps.billing.plan_limit_ui import plan_limit_banner_html, plan_limit_redirect

    plan_limits = get_user_plan_limits(post.user)
    if not plan_limits.get("ai_image_generation", False):
        if request.headers.get("HX-Request"):
            return HttpResponse(
                plan_limit_banner_html("Your plan doesn't include AI image generation."),
                status=403,
            )
        return plan_limit_redirect(
            request,
            "Your plan doesn't include AI image generation.",
            "content:edit",
            post_id=post.id,
        )

    from django.utils import timezone as tz
    monthly_limit = plan_limits.get("ai_images_per_month", 5)
    month_start = tz.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    images_this_month = Post.objects.filter(
        user=post.user, media_status="generated", created_at__gte=month_start,
    ).count()
    if images_this_month >= monthly_limit:
        limit_msg = f"Monthly image limit reached ({images_this_month}/{monthly_limit})."
        if request.headers.get("HX-Request"):
            return HttpResponse(plan_limit_banner_html(limit_msg), status=403)
        return plan_limit_redirect(
            request,
            limit_msg,
            "content:edit",
            post_id=post.id,
        )

    prompt = post.media_prompt
    if not prompt:
        prompt = f"Social media image for: {post.content_text[:200]}"
        post.media_prompt = prompt

    post.media_status = Post.MediaStatus.PENDING
    post.save(update_fields=["media_status", "media_prompt", "updated_at"])

    from apps.content.tasks import async_generate_image
    visual_strategy_data = post.visual_metadata.get("strategy_data") if post.visual_metadata else None
    fire_task(async_generate_image, str(post.id), prompt, visual_strategy_data)

    if request.headers.get("HX-Request"):
        return render(request, "components/post_card.html", {"post": post})
    messages.info(request, "Generating AI image…")
    return redirect("content:edit", post_id=post.id)


@login_required
@require_http_methods(["POST", "DELETE"])
def delete_media(request, post_id, attachment_id):
    """Delete a media attachment from a post via HTMX."""
    from apps.content.models import MediaAttachment

    post = get_object_or_404(Post.objects.select_related("user"), id=post_id)
    if not can_edit_post(request.user, post):
        raise Http404
    attachment = get_object_or_404(MediaAttachment, id=attachment_id, post=post)

    if attachment.file:
        attachment.file.delete(save=False)
    attachment.delete()

    if not post.attachments.exists() and not post.media_urls:
        post.media_status = Post.MediaStatus.NONE
        post.save(update_fields=["media_status", "updated_at"])

    return HttpResponse("")


@login_required
@require_POST
def clear_ai_media(request, post_id):
    """Remove AI-generated images from a post (clear media_urls)."""
    post = get_object_or_404(Post.objects.select_related("user", "social_account"), id=post_id)
    if not can_edit_post(request.user, post):
        raise Http404

    post.media_urls = []
    if not post.attachments.exists():
        post.media_status = Post.MediaStatus.NONE
    post.save(update_fields=["media_urls", "media_status", "updated_at"])

    if request.headers.get("HX-Request"):
        return render(request, "components/post_card.html", {"post": post})
    return redirect("content:edit", post_id=post.id)


@login_required
@require_POST
def regenerate_image(request, post_id):
    """Discard the current AI image and generate a fresh one using the stored prompt."""
    post = get_object_or_404(
        Post.objects.select_related("user", "social_account", "user__profile"), id=post_id,
    )
    if not can_edit_post(request.user, post):
        raise Http404
    if post.status not in (Post.Status.DRAFT, Post.Status.PENDING_APPROVAL):
        return HttpResponse("Cannot regenerate image for this post", status=400)

    if post.visual_strategy == "carousel":
        if request.headers.get("HX-Request"):
            return HttpResponse(
                '<span class="text-xs text-amber-600 dark:text-amber-400 px-1">'
                'Update the product to change carousel images.</span>'
            )
        return redirect("content:edit", post_id=post.id)

    post.media_urls = []
    post.media_status = Post.MediaStatus.PENDING
    post.save(update_fields=["media_urls", "media_status", "updated_at"])

    from apps.content.tasks import retry_image_generation
    fire_task(retry_image_generation, str(post.id))

    if request.headers.get("HX-Request"):
        return render(request, "components/post_card.html", {"post": post, "show_angle": True})
    return redirect("content:edit", post_id=post.id)


@login_required
@require_POST
def card_upload_media(request, post_id):
    """Upload an image from the post card. Returns the updated card."""
    from io import BytesIO

    from PIL import Image

    from apps.content.models import MediaAttachment

    post = get_object_or_404(Post.objects.select_related("user", "social_account", "seed"), id=post_id)
    if not can_edit_post(request.user, post):
        raise Http404

    uploaded = request.FILES.get("file")
    if not uploaded:
        return render(request, "components/post_card.html", {"post": post})

    if uploaded.size > 10 * 1024 * 1024:
        messages.error(request, "File too large (max 10MB).")
        return render(request, "components/post_card.html", {"post": post})

    allowed_types = ["image/jpeg", "image/png", "image/gif", "image/webp"]
    if uploaded.content_type not in allowed_types:
        messages.error(request, "Unsupported file type.")
        return render(request, "components/post_card.html", {"post": post})

    try:
        img = Image.open(uploaded)
        img.verify()
        actual_format = img.format
        if actual_format not in ("JPEG", "PNG", "GIF", "WEBP"):
            messages.error(request, "Invalid image file.")
            return render(request, "components/post_card.html", {"post": post})
    except Exception:
        messages.error(request, "Invalid or corrupted image.")
        return render(request, "components/post_card.html", {"post": post})

    uploaded.seek(0)
    if actual_format in ("JPEG", "PNG", "WEBP"):
        try:
            img = Image.open(uploaded)
            clean = BytesIO()
            clean_img = Image.new(img.mode, img.size)
            clean_img.putdata(list(img.getdata()))
            save_fmt = actual_format if actual_format != "JPEG" else "JPEG"
            save_kwargs = {"format": save_fmt}
            if save_fmt == "JPEG":
                save_kwargs["quality"] = 95
            clean_img.save(clean, **save_kwargs)
            clean.seek(0)
            from django.core.files.uploadedfile import InMemoryUploadedFile
            uploaded = InMemoryUploadedFile(
                clean, "file", uploaded.name, uploaded.content_type,
                clean.getbuffer().nbytes, uploaded.charset,
            )
        except Exception:
            uploaded.seek(0)

    file_type = "gif" if uploaded.content_type == "image/gif" else "image"
    order = post.attachments.count()
    MediaAttachment.objects.create(
        post=post,
        file=uploaded,
        file_type=file_type,
        alt_text="",
        order=order,
    )

    post.media_status = Post.MediaStatus.UPLOADED
    post.save(update_fields=["media_status", "updated_at"])

    return render(request, "components/post_card.html", {"post": post})


@login_required
def post_preview(request, post_id):
    """HTMX partial: platform-specific visual preview of a post."""
    post = get_object_or_404(
        Post.objects.select_related("social_account", "user"),
        id=post_id,
    )
    if not can_edit_post(request.user, post):
        raise Http404
    return render(request, "content/preview.html", {"post": post})


@login_required
def post_detail(request, post_id):
    """Full detail view for a single post with metrics and activity."""
    post = get_object_or_404(
        Post.objects.select_related("social_account", "seed", "user"),
        id=post_id,
    )
    if not can_edit_post(request.user, post):
        raise Http404

    metrics = None
    try:
        metrics = post.metrics
    except Exception:
        pass

    notifications = []
    try:
        from apps.notifications.models import Notification
        notifications = Notification.objects.filter(
            related_post=post,
        ).select_related("related_post").order_by("-created_at")[:10]
    except Exception:
        pass

    return render(request, "content/detail.html", {
        "post": post,
        "metrics": metrics,
        "notifications": notifications,
        "page_title": "Post Detail",
    })
