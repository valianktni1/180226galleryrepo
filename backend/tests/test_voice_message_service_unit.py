from datetime import datetime, timezone
from pathlib import Path
import subprocess

import pytest

from voice_message_service import (
    VoiceMessageError,
    convert_voice_message,
    normalise_guest_name,
    probe_audio,
    voice_message_filename,
)


def test_guest_name_is_required_and_normalised():
    assert normalise_guest_name("  Auntie   Sarah  ") == "Auntie Sarah"
    with pytest.raises(VoiceMessageError):
        normalise_guest_name("   ")
    with pytest.raises(VoiceMessageError):
        normalise_guest_name("x" * 81)


def test_filename_is_recognisable_and_safe():
    name = voice_message_filename(
        "Sam / Best Man",
        now=datetime(2026, 10, 15, 12, 30, tzinfo=timezone.utc),
    )
    assert name.startswith("Personal Message - Sam Best Man - 20261015-123000-")
    assert name.endswith(".mp3")
    assert "/" not in name and "\\" not in name


def test_real_conversion_is_stereo_48khz_192kbps(tmp_path: Path):
    source = tmp_path / "browser-recording.webm"
    output = tmp_path / "personal-message.mp3"
    generated = subprocess.run(
        [
            "ffmpeg", "-y", "-v", "error", "-f", "lavfi",
            "-i", "sine=frequency=880:duration=1.2", "-c:a", "libopus", str(source),
        ],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert generated.returncode == 0, generated.stderr

    info = convert_voice_message(source, output)

    assert output.is_file()
    assert info["channels"] == 2
    assert info["sample_rate"] == 48_000
    assert 180_000 <= probe_audio(output)["bit_rate"] <= 205_000
    assert not any(tmp_path.glob("*.converting.mp3"))

