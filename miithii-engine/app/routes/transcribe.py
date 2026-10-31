"""POST /v1/transcribe — dictation: audio bytes in, words out.

The composer records a clip in the browser and posts it raw (body IS the
audio — no multipart, no storage); this relays it to Sarvam's speech-to-text
and hands back words. saaras:v4 over Whisper because the sibling project's
own Assamese testing showed Whisper drifts on Indic audio, and code-mixed
support speech is exactly that. The key lives server-side, the audio lives
for one request, and nothing is stored — a dictation is a keystroke, not an
attachment.
"""

import httpx
import structlog
from fastapi import APIRouter, Depends, HTTPException, Request

from app.config import get_settings
from app.security import Principal, require_principal

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/v1/transcribe", tags=["transcribe"])

SARVAM_STT_URL = "https://api.sarvam.ai/speech-to-text"
TRANSCRIPTION_MODEL = "saaras:v4"

# The recorder stops itself well before this; the check here is the backstop
# for a clip that gets past the UI.
MAX_CLIP_BYTES = 25 * 1024 * 1024

# Sarvam reads the container off the filename, and the request's Content-Type
# is the only clue we have about what MediaRecorder wrote. Anything
# unrecognized rides in as webm — every browser we support records webm or mp4.
CONTAINER_EXTENSIONS: dict[str, str] = {
    "audio/webm": "webm",
    "audio/ogg": "ogg",
    "audio/mp4": "mp4",
    "audio/mpeg": "mp3",
    "audio/mpga": "mp3",
    "audio/wav": "wav",
    "audio/x-wav": "wav",
    "audio/flac": "flac",
}


def _clip_filename(content_type: str) -> str:
    container = content_type.split(";")[0].strip().lower()
    return f"dictation.{CONTAINER_EXTENSIONS.get(container, 'webm')}"


def _failure_message(status: int) -> str:
    """What the user reads when transcription fails. The provider's own
    detail is ours to log and noise to them, so they get a sentence that says
    what happened and what to do about it."""
    if status == 429:
        return "Voice input is busy right now. Give it a moment and try again."
    if status == 413:
        return "That recording was too long to transcribe. Try a shorter one."
    if status in (401, 403):
        return (
            "Voice input isn't authorized right now. "
            "This one's on us — try again later."
        )
    return "Voice input couldn't transcribe that. Try again?"


def _stt_client() -> httpx.AsyncClient:
    """The outbound client, as its own seam: tests swap in a MockTransport
    here instead of faking the whole provider exchange."""
    return httpx.AsyncClient(timeout=httpx.Timeout(30.0))


async def _sarvam_transcribe(audio: bytes, content_type: str, api_key: str) -> dict:
    """One request to Sarvam; raises HTTPException on any non-200."""
    container = content_type.split(";")[0].strip().lower() or "audio/webm"
    form = {
        "model": TRANSCRIPTION_MODEL,
        # Omitted language_code = saaras auto-detect. Corpo support speech is
        # English-first code-mixed; the sibling pins as-IN because its users
        # speak Assamese, which corpo agents mostly don't.
    }
    try:
        async with _stt_client() as client:
            response = await client.post(
                SARVAM_STT_URL,
                headers={"api-subscription-key": api_key},
                files={
                    "file": (
                        _clip_filename(content_type),
                        audio,
                        container,
                    )
                },
                data=form,
            )
    except httpx.HTTPError as exc:
        logger.error("transcription_unreachable", error=str(exc))
        raise HTTPException(
            status_code=502,
            detail="Voice input couldn't reach the transcription service. Try again?",
        ) from exc

    if response.status_code != 200:
        detail = response.text[:500]
        logger.error(
            "transcription_failed", status=response.status_code, detail=detail
        )
        raise HTTPException(
            status_code=429 if response.status_code == 429 else 502,
            detail=_failure_message(response.status_code),
        )

    payload = response.json()
    return {
        "text": (payload.get("transcript") or payload.get("text") or "").strip(),
        "language_code": payload.get("language_code"),
        "request_id": payload.get("request_id"),
    }


@router.post("")
async def transcribe(
    request: Request,
    principal: Principal = Depends(require_principal),
) -> dict:
    settings = get_settings()
    if not settings.sarvam_api_key:
        raise HTTPException(
            status_code=503,
            detail="Voice input isn't configured on this deployment yet.",
        )

    audio = await request.body()
    if not audio:
        raise HTTPException(
            status_code=400, detail="That recording came through empty. Try again?"
        )
    if len(audio) > MAX_CLIP_BYTES:
        raise HTTPException(
            status_code=413,
            detail="That recording was too long to transcribe. Try a shorter one.",
        )

    content_type = request.headers.get("content-type", "audio/webm")
    result = await _sarvam_transcribe(audio, content_type, settings.sarvam_api_key)
    logger.info(
        "transcribed",
        bytes=len(audio),
        language=result.get("language_code"),
        user_id=str(principal.user.id) if principal.user else None,
    )
    return result
