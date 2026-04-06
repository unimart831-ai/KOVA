"""Voice memo transcription via OpenAI Whisper API."""

import logging
import tempfile

from django.conf import settings

logger = logging.getLogger("kova.voice")

# Max audio file size: 25MB (Whisper API limit)
MAX_AUDIO_SIZE = 25 * 1024 * 1024

# Accepted audio MIME types
ALLOWED_AUDIO_TYPES = {
    "audio/webm",
    "audio/ogg",
    "audio/mp4",
    "audio/mpeg",
    "audio/mp3",
    "audio/wav",
    "audio/x-wav",
    "audio/flac",
    "audio/x-m4a",
}

# Map MIME → file extension for Whisper
MIME_TO_EXT = {
    "audio/webm": ".webm",
    "audio/ogg": ".ogg",
    "audio/mp4": ".m4a",
    "audio/mpeg": ".mp3",
    "audio/mp3": ".mp3",
    "audio/wav": ".wav",
    "audio/x-wav": ".wav",
    "audio/flac": ".flac",
    "audio/x-m4a": ".m4a",
}


def transcribe_audio(audio_file, content_type="audio/webm") -> dict:
    """
    Send an audio file to OpenAI Whisper and return the transcription.

    Args:
        audio_file: A file-like object (e.g., request.FILES['audio'])
        content_type: MIME type of the audio

    Returns:
        dict: {"text": "transcribed text", "duration": seconds}
              or {"error": "error message"}
    """
    api_key = settings.OPENAI_API_KEY
    if not api_key:
        logger.error("OPENAI_API_KEY not set — cannot transcribe voice memo")
        return {"error": "Voice transcription is not configured. Please set OPENAI_API_KEY."}

    # Validate content type
    if content_type not in ALLOWED_AUDIO_TYPES:
        return {"error": f"Unsupported audio format: {content_type}. Use WebM, MP3, WAV, or M4A."}

    # Validate file size
    audio_file.seek(0, 2)
    file_size = audio_file.tell()
    audio_file.seek(0)

    if file_size > MAX_AUDIO_SIZE:
        return {"error": "Audio file too large. Maximum size is 25MB."}

    if file_size < 1000:
        return {"error": "Audio too short. Please record at least a second."}

    ext = MIME_TO_EXT.get(content_type, ".webm")

    try:
        from openai import OpenAI

        client = OpenAI(api_key=api_key)

        # Write to temp file (Whisper needs a named file with extension)
        with tempfile.NamedTemporaryFile(suffix=ext, delete=True) as tmp:
            for chunk in audio_file.chunks():
                tmp.write(chunk)
            tmp.flush()
            tmp.seek(0)

            response = client.audio.transcriptions.create(
                model="whisper-1",
                file=tmp,
                response_format="verbose_json",
            )

        text = response.text.strip() if response.text else ""
        duration = getattr(response, "duration", 0) or 0

        if not text:
            return {"error": "Could not detect any speech. Try speaking louder or closer to the mic."}

        logger.info(
            "Voice memo transcribed: %d chars, %.1fs duration",
            len(text),
            duration,
        )

        return {"text": text, "duration": round(duration, 1)}

    except Exception as e:
        logger.exception("Whisper transcription failed: %s", e)
        return {"error": f"Transcription failed: {str(e)}"}
