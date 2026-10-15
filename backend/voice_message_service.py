"""Validation and conversion helpers for guest personal voice messages."""

from __future__ import annotations

import json
import re
import secrets
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict


MAX_VOICE_MESSAGE_SECONDS = 240
MAX_VOICE_UPLOAD_BYTES = 64 * 1024 * 1024
VOICE_SAMPLE_RATE = 48_000
VOICE_BITRATE = "192k"
VOICE_CHANNELS = 2


class VoiceMessageError(ValueError):
    """Raised when a voice recording is invalid or cannot be converted."""


def normalise_guest_name(value: str) -> str:
    """Return a short display name safe to use in metadata and a filename."""
    if not isinstance(value, str):
        raise VoiceMessageError("Please enter your name")
    cleaned = re.sub(r"\s+", " ", value).strip()
    if not cleaned:
        raise VoiceMessageError("Please enter your name")
    if len(cleaned) > 80:
        raise VoiceMessageError("Please keep your name under 80 characters")
    if any(ord(char) < 32 for char in cleaned):
        raise VoiceMessageError("Your name contains unsupported characters")
    return cleaned


def voice_message_filename(guest_name: str, now: datetime | None = None) -> str:
    """Build a recognisable, collision-resistant MP3 filename."""
    guest_name = normalise_guest_name(guest_name)
    safe_name = re.sub(r"[^\w .&'()-]", "", guest_name, flags=re.UNICODE)
    safe_name = re.sub(r"\s+", " ", safe_name).strip(" .") or "Wedding Guest"
    stamp = (now or datetime.now(timezone.utc)).strftime("%Y%m%d-%H%M%S")
    return f"Personal Message - {safe_name} - {stamp}-{secrets.token_hex(2)}.mp3"


def probe_audio(path: Path) -> Dict:
    """Read the first audio stream and duration using ffprobe."""
    result = subprocess.run(
        [
            "ffprobe", "-v", "error", "-show_entries",
            "format=duration:stream=codec_type,sample_rate,channels,bit_rate",
            "-of", "json", str(path),
        ],
        capture_output=True,
        text=True,
        timeout=30,
    )
    if result.returncode != 0:
        raise VoiceMessageError("That recording could not be read. Please record it again")
    try:
        payload = json.loads(result.stdout or "{}")
        audio_stream = next(
            stream for stream in payload.get("streams", [])
            if stream.get("codec_type") == "audio"
        )
        duration = float(payload.get("format", {}).get("duration") or 0)
    except (ValueError, TypeError, StopIteration, json.JSONDecodeError) as exc:
        raise VoiceMessageError("That recording does not contain playable audio") from exc
    if duration <= 0:
        raise VoiceMessageError("That recording does not contain playable audio")
    return {
        "duration": duration,
        "sample_rate": int(audio_stream.get("sample_rate") or 0),
        "channels": int(audio_stream.get("channels") or 0),
        "bit_rate": int(audio_stream.get("bit_rate") or 0),
    }


def convert_voice_message(source_path: Path, output_path: Path) -> Dict:
    """Normalise one browser recording to a 48 kHz, stereo, 192 kbps MP3."""
    source_info = probe_audio(source_path)
    if source_info["duration"] > MAX_VOICE_MESSAGE_SECONDS + 1:
        raise VoiceMessageError("Personal messages can be no longer than 4 minutes")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_output = output_path.with_name(f".{output_path.stem}.converting.mp3")
    temporary_output.unlink(missing_ok=True)
    try:
        result = subprocess.run(
            [
                "ffmpeg", "-y", "-v", "error", "-i", str(source_path),
                "-map", "0:a:0", "-vn", "-map_metadata", "-1",
                "-af", "loudnorm=I=-16:TP=-1.5:LRA=11",
                "-codec:a", "libmp3lame", "-b:a", VOICE_BITRATE,
                "-ar", str(VOICE_SAMPLE_RATE), "-ac", str(VOICE_CHANNELS),
                str(temporary_output),
            ],
            capture_output=True,
            text=True,
            timeout=300,
        )
        if result.returncode != 0 or not temporary_output.is_file():
            raise VoiceMessageError("We could not prepare that recording. Please try again")
        output_info = probe_audio(temporary_output)
        if output_info["sample_rate"] != VOICE_SAMPLE_RATE or output_info["channels"] != VOICE_CHANNELS:
            raise VoiceMessageError("The converted recording did not pass its audio checks")
        temporary_output.replace(output_path)
        return output_info
    finally:
        temporary_output.unlink(missing_ok=True)

