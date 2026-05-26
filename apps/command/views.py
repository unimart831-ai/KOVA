from __future__ import annotations

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone

from apps.accounts.segments import build_surface_experience
from apps.briefs.models import DailyBrief
from apps.briefs.standup import enrich_decisions
from apps.briefs.standup import build_standup_context
from apps.utils import fire_task


def _current_or_latest_brief(user):
    today = timezone.now().date()
    brief = DailyBrief.objects.filter(user=user, date=today).first()
    if brief:
        return brief
    return DailyBrief.objects.filter(user=user).first()


def _command_context(request):
    from apps.calendar_intel.models import HolidayDraft
    from apps.calendar_intel.selectors import top_upcoming_for_brief
    from apps.campaigns.models import Campaign
    from apps.content.models import VoiceBrief
    from apps.platforms.models import SocialAccount

    brief = _current_or_latest_brief(request.user)
    standup_context = build_standup_context(request.user, brief) if brief else None
    connected_platforms = list(
        SocialAccount.objects.filter(user=request.user, is_active=True)
        .values_list("platform", flat=True)
    )

    ready_moment_packs = list(
        HolidayDraft.objects.filter(
            user=request.user,
            status=HolidayDraft.Status.DRAFTS_READY,
        )
        .select_related("holiday_occurrence__holiday", "custom_event")
        .order_by("target_date")[:5]
    )
    upcoming_moments = top_upcoming_for_brief(request.user, count=3)
    moment_pack_id = request.GET.get("moment_pack", "").strip()

    recent_briefs = (
        VoiceBrief.objects
        .filter(user=request.user)
        .select_related("campaign", "email_campaign")
        .order_by("-created_at")[:8]
    )
    recent_campaigns = (
        Campaign.objects
        .filter(user=request.user)
        .order_by("-created_at")[:8]
    )
    decisions_needed = []
    if brief and brief.performance_summary:
        decisions_needed = enrich_decisions(
            brief.performance_summary.get("decisions_needed", [])
        )

    return {
        "brief": brief,
        "standup_context": standup_context,
        "decisions_needed": decisions_needed,
        "ready_moment_packs": ready_moment_packs,
        "holiday_drafts_ready": len(ready_moment_packs),
        "upcoming_moments": upcoming_moments,
        "moment_pack_id": moment_pack_id,
        "voice_briefs": recent_briefs,
        "campaigns": recent_campaigns,
        "transcribe_url": reverse("content:voice_campaign_transcribe"),
        "legacy_brief_url": reverse("brief:home"),
        "legacy_listen_url": reverse("content:voice_campaign"),
        "legacy_calendar_url": reverse("calendar_intel:preferences"),
        "segment_surface": build_surface_experience(
            profile=getattr(request.user, "profile", None),
            connected_platforms=connected_platforms,
        ),
    }


def _ensure_command_access(request):
    if not request.user.onboarding_completed:
        return redirect("accounts:onboarding")
    return None


def _command_overview_metrics(ctx):
    brief = ctx.get("brief")
    standup = ctx.get("standup_context") or {}
    return {
        "score": getattr(brief, "kova_score", 0) if brief else 0,
        "posts_pending": standup.get("posts_pending", 0),
        "moment_packs_ready": ctx.get("holiday_drafts_ready", 0),
        "launches_recent": len(ctx.get("voice_briefs") or []),
    }


@login_required
def command_home(request):
    """Premium overview for the Command shadow surface."""
    blocked = _ensure_command_access(request)
    if blocked:
        return blocked

    ctx = _command_context(request)
    ctx["overview_metrics"] = _command_overview_metrics(ctx)
    return render(request, "command/home.html", ctx)


@login_required
def command_standup(request):
    blocked = _ensure_command_access(request)
    if blocked:
        return blocked

    return render(request, "command/standup.html", _command_context(request))


@login_required
def command_moments(request):
    blocked = _ensure_command_access(request)
    if blocked:
        return blocked

    ctx = _command_context(request)
    if not ctx["moment_pack_id"] and ctx["ready_moment_packs"]:
        ctx["moment_pack_id"] = str(ctx["ready_moment_packs"][0].pk)
    return render(request, "command/moments.html", ctx)


@login_required
def command_listen(request):
    blocked = _ensure_command_access(request)
    if blocked:
        return blocked

    if request.method == "POST":
        return _handle_listen_launch(request)

    return render(request, "command/listen.html", _command_context(request))


def _handle_listen_launch(request):
    from apps.campaigns.tasks import ai_build_campaign
    from apps.content.models import VoiceBrief
    from apps.content.tasks import process_voice_brief

    action = request.POST.get("action", "prompt")

    if action == "prompt":
        prompt = request.POST.get("prompt", "").strip()
        if not prompt:
            messages.error(request, "Describe what you want Kova to launch.")
            return redirect(request.POST.get("next") or reverse("command:listen"))

        duration = request.POST.get("duration_days", "7")
        try:
            duration_days = max(1, min(int(duration), 90))
        except (ValueError, TypeError):
            duration_days = 7

        include_email = request.POST.get("include_email") == "on"
        include_status = request.POST.get("include_whatsapp_status") == "on"
        fire_task(
            ai_build_campaign,
            str(request.user.id),
            prompt,
            duration_days,
            include_email,
            include_status,
        )

        channels = ["social Queue"]
        if include_status:
            channels.append("WhatsApp Status")
        if include_email:
            channels.append("email")

        messages.success(
            request,
            f"Command launched your campaign pack - {' + '.join(channels)}.",
        )
        return redirect(request.POST.get("next") or reverse("command:listen"))

    audio = request.FILES.get("audio")
    if not audio:
        messages.error(request, "Please upload or record an audio clip.")
        return redirect(request.POST.get("next") or reverse("command:listen"))

    allowed_types = {
        "audio/mpeg", "audio/mp3", "audio/wav", "audio/x-wav",
        "audio/ogg", "audio/webm", "audio/mp4", "audio/m4a", "audio/x-m4a",
    }
    if audio.content_type not in allowed_types and not audio.name.endswith(
        (".mp3", ".wav", ".ogg", ".webm", ".m4a")
    ):
        messages.error(request, "Unsupported audio format. Use MP3, WAV, OGG, WebM, or M4A.")
        return redirect(request.POST.get("next") or reverse("command:listen"))

    if audio.size > 25 * 1024 * 1024:
        messages.error(request, "Audio file too large. Maximum 25 MB.")
        return redirect(request.POST.get("next") or reverse("command:listen"))

    vb = VoiceBrief.objects.create(user=request.user, audio_file=audio)
    fire_task(process_voice_brief, str(vb.pk))
    messages.success(
        request,
        "Voice captured! Kova is transcribing and building your launch pack.",
    )
    return redirect(request.POST.get("next") or reverse("command:listen"))
