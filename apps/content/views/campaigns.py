import json

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from apps.utils import fire_task


@login_required
def voice_campaign(request):
    """Listen & Launch — cross-channel campaigns from voice or text."""
    from apps.campaigns.models import Campaign
    from apps.campaigns.tasks import ai_build_campaign
    from apps.content.models import VoiceBrief
    from apps.content.tasks import process_voice_brief

    if request.method == "POST":
        action = request.POST.get("action", "voice")

        if action == "prompt":
            prompt = request.POST.get("prompt", "").strip()
            if not prompt:
                messages.error(request, "Describe what you want your campaign to achieve.")
                return redirect("content:voice_campaign")

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
            if include_email:
                channels.append("email")
            if include_status:
                channels.append("WhatsApp Status")
            messages.success(
                request,
                f"Listen & Launch is building your campaign — {' + '.join(channels)}.",
            )
            return redirect("content:voice_campaign")

        audio = request.FILES.get("audio")
        if not audio:
            messages.error(request, "Please upload or record an audio clip.")
            return redirect("content:voice_campaign")

        allowed_types = [
            "audio/mpeg", "audio/mp3", "audio/wav", "audio/x-wav",
            "audio/ogg", "audio/webm", "audio/mp4", "audio/m4a",
            "audio/x-m4a",
        ]
        if audio.content_type not in allowed_types and not audio.name.endswith(
            (".mp3", ".wav", ".ogg", ".webm", ".m4a")
        ):
            messages.error(request, "Unsupported audio format. Use MP3, WAV, OGG, WebM, or M4A.")
            return redirect("content:voice_campaign")

        if audio.size > 25 * 1024 * 1024:
            messages.error(request, "Audio file too large. Maximum 25 MB.")
            return redirect("content:voice_campaign")

        vb = VoiceBrief.objects.create(user=request.user, audio_file=audio)
        fire_task(process_voice_brief, str(vb.pk))
        messages.success(
            request,
            "Voice captured! Listen & Launch is transcribing and building across your channels.",
        )
        return redirect("content:voice_campaign")

    briefs = (
        VoiceBrief.objects
        .filter(user=request.user)
        .select_related("campaign", "email_campaign")
        .order_by("-created_at")[:20]
    )
    campaigns = (
        Campaign.objects
        .filter(user=request.user)
        .order_by("-created_at")[:15]
    )

    return render(request, "content/voice_campaign.html", {
        "briefs": briefs,
        "campaigns": campaigns,
        "transcribe_url": reverse("content:voice_campaign_transcribe"),
    })


@login_required
@require_POST
def voice_campaign_transcribe(request):
    """Transcribe live mic audio for Listen & Launch prompt field."""
    from apps.content.voice import transcribe_audio

    audio = request.FILES.get("audio")
    if not audio:
        return JsonResponse({"error": "No audio file provided."}, status=400)

    content_type = audio.content_type or "audio/webm"
    result = transcribe_audio(audio, content_type)
    if result.get("error"):
        return JsonResponse({"error": result["error"]}, status=400)
    return JsonResponse({"text": result.get("text", ""), "duration": result.get("duration")})
