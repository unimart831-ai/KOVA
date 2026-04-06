# Voice Memo — Content Studio Feature Guide

## What Is It?

Voice Memo lets users **speak their content ideas** instead of typing them. The recording is sent to OpenAI's Whisper API, transcribed to text, and placed into the "Drop your idea" textarea in the Content Studio — ready for the user to review, edit, and hit "Generate posts."

This removes the friction of typing on mobile and lets users capture ideas on the go.

---

## How It Works

### User Flow

1. User opens **Content Studio** (`/content/studio/`)
2. Clicks the **mic icon** (bottom-right of the idea textarea)
3. Browser asks for microphone permission (one-time popup)
4. **Red pulsing dot + timer** shows recording is active
5. User clicks **STOP** → audio uploads to the server
6. **"Transcribing…"** spinner appears for 2-3 seconds
7. Transcribed text **fills the textarea** — user can review/edit
8. User hits **"Generate posts"** → normal pipeline kicks in

### Technical Flow

```
Browser MediaRecorder API          Server                         OpenAI
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
User clicks mic
  → getUserMedia({audio: true})
  → MediaRecorder starts
  → Audio chunks collected (250ms intervals)

User clicks STOP
  → MediaRecorder stops
  → Audio blob created (webm/opus)
  → POST /content/studio/voice/  ───→  voice_to_seed(request)
                                          │
                                          ├─ Validates audio file
                                          │   (type, size, min length)
                                          │
                                          ├─ transcribe_audio()  ──────→  whisper-1
                                          │                               transcription
                                          │                           ←── {"text": "...", "duration": 12.3}
                                          │
                                          ├─ Returns JSON
  ←── {"text": "transcribed text"}        │
                                          │
JS populates textarea                    │
User reviews & edits                     │
User clicks "Generate posts"             │
  → POST /content/studio/submit/ ───→ submit_seed() (existing flow)
                                          │
                                          └─ generate_from_seed Celery task
                                              → Create Agent → Content DNA → Prediction → Schedule
```

---

## Files

| File | Purpose |
|------|---------|
| `apps/content/voice.py` | Whisper transcription service — validates audio, calls OpenAI API |
| `apps/content/views.py` → `voice_to_seed()` | Django view — accepts audio POST, returns transcribed text as JSON |
| `apps/content/urls.py` → `studio/voice/` | URL routing for the voice endpoint |
| `templates/content/studio.html` | Voice recorder UI — Alpine.js `voiceRecorder()` component |

---

## Voice Transcription Service (`voice.py`)

### `transcribe_audio(audio_file, content_type) → dict`

**Input:**
- `audio_file` — Django `UploadedFile` (from `request.FILES['audio']`)
- `content_type` — MIME type (default: `audio/webm`)

**Output:**
- Success: `{"text": "transcribed text here", "duration": 12.3}`
- Error: `{"error": "descriptive error message"}`

**Validations:**
- Checks `OPENAI_API_KEY` is set
- Validates MIME type against allowed list
- Max file size: **25 MB** (Whisper API hard limit)
- Min file size: **1 KB** (rejects empty/broken recordings)

**Supported Formats:**
| Format | MIME Type | Notes |
|--------|-----------|-------|
| WebM | `audio/webm` | Default from Chrome/Firefox MediaRecorder |
| OGG | `audio/ogg` | Firefox fallback |
| MP4/M4A | `audio/mp4`, `audio/x-m4a` | Safari |
| MP3 | `audio/mpeg`, `audio/mp3` | Universal |
| WAV | `audio/wav`, `audio/x-wav` | Uncompressed |
| FLAC | `audio/flac` | Lossless |

---

## Voice Upload Endpoint (`views.py`)

### `POST /content/studio/voice/`

**Authentication:** Login required
**Rate Limit:** 10 requests/minute per user

**Request:** `multipart/form-data`
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `audio` | File | Yes | Audio recording blob |
| `mode` | String | No | `transcribe` (default) or `submit` |
| `target_platforms` | JSON | No | Used only with `mode=submit` |
| `notes` | String | No | Used only with `mode=submit` |

**Response (JSON):**
```json
// mode=transcribe (default)
{"text": "My idea about AI in marketing...", "duration": 8.5, "submitted": false}

// mode=submit
{"text": "My idea about...", "duration": 8.5, "seed_id": "uuid", "submitted": true}
```

**Modes:**
- **`transcribe`** (default) — Returns text for the user to review/edit before submitting. This is the primary flow.
- **`submit`** — Creates a ContentSeed directly from the transcription and kicks off the generation pipeline. Useful for future one-tap workflows.

---

## Voice Recorder UI Component

### Alpine.js `voiceRecorder()` Component

**States:**
| State | UI | Description |
|-------|----|-------------|
| `idle` | Mic icon + "Voice" label | Ready to record |
| `recording` | Red pulsing dot + timer + STOP button | Actively recording |
| `transcribing` | Spinner + "Transcribing…" | Waiting for Whisper API |
| `error` | Error message + Dismiss button | Something went wrong |

**Key Methods:**
- `startRecording()` — Requests mic access, starts MediaRecorder with best available codec
- `stopRecording()` — Stops recording, triggers upload
- `_sendAudio()` — POSTs audio blob to `/content/studio/voice/`
- `_startTimer()` / `_stopTimer()` — Manages the recording duration display

**Codec Selection:**
```
audio/webm;codecs=opus  →  audio/webm  →  audio/ogg  (tried in order)
```

**Event System:**
- On successful transcription, dispatches `window.CustomEvent('voice-transcribed', {detail: {text, duration}})`
- The textarea div listens via `@voice-transcribed.window` and populates the input

---

## Cost

| Metric | Value |
|--------|-------|
| Whisper API Price | **$0.006 / minute** of audio |
| Avg voice memo | ~15-30 seconds |
| Cost per memo | **$0.0015 - $0.003** |
| 100 memos/month | **$0.15 - $0.30** |

This is negligible relative to LLM costs ($0.20-$4.60/user/month for text generation).

---

## Browser Compatibility

| Browser | Status | Notes |
|---------|--------|-------|
| Chrome 49+ | ✅ | Full support, webm/opus |
| Firefox 25+ | ✅ | Full support, webm/opus or ogg |
| Safari 14.1+ | ✅ | MP4/M4A codec |
| Edge 79+ | ✅ | Same as Chrome |
| Mobile Chrome | ✅ | Works on Android |
| Mobile Safari | ✅ | Works on iOS 14.5+ |

**Requirement:** HTTPS is required for `getUserMedia()`. Localhost is exempt for development.

---

## Error Handling

| Error | Cause | User Message |
|-------|-------|-------------|
| `NotAllowedError` | User denied mic permission | "Microphone access denied. Please allow mic access in your browser." |
| No API key | `OPENAI_API_KEY` not set | "Voice transcription is not configured." |
| Bad format | Unsupported MIME type | "Unsupported audio format. Use WebM, MP3, WAV, or M4A." |
| Too large | File > 25MB | "Audio file too large. Maximum size is 25MB." |
| Too short | File < 1KB | "Audio too short. Please record at least a second." |
| No speech | Whisper returned empty text | "Could not detect any speech. Try speaking louder." |
| API failure | OpenAI error | "Transcription failed: [error details]" |
| Network | Fetch failed | "Network error: [error details]" |

---

## Configuration

The only required configuration is `OPENAI_API_KEY` in your environment variables. This is already set in `config/settings/base.py`:

```python
OPENAI_API_KEY = env("OPENAI_API_KEY", default="")
```

No database migrations are needed — voice recordings are not stored, only transcribed on-the-fly.

---

## Future Enhancements

- **Audio waveform visualization** during recording
- **Language detection** — Whisper supports 90+ languages including Swahili and Sheng
- **Voice-to-seed shortcut** — One-tap record → auto-generate (skip review step)
- **Plan-gated limits** — Limit voice memos per day by plan tier
- **Audio playback** — Let user replay before submitting
