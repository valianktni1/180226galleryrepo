from pathlib import Path


SERVER = (Path(__file__).resolve().parents[1] / "server.py").read_text(encoding="utf-8")


def test_voice_message_endpoint_keeps_existing_guest_upload_separate():
    assert '@api_router.post("/share/{token}/voice-message")' in SERVER
    assert '@api_router.post("/share/{token}/upload")' in SERVER
    assert 'share.get("guest_upload_mode")' in SERVER
    assert 'file_type": "audio"' in SERVER


def test_voice_messages_are_nested_and_final_mp3_is_retained():
    assert 'VOICE_MESSAGES_SUBFOLDER = "Personal Voice Messages"' in SERVER
    assert 'VOICE_MESSAGES_PARENT_SUBFOLDER = "Guest Uploads"' in SERVER
    assert 'temporary_source.unlink(missing_ok=True)' in SERVER
    assert 'convert_voice_message(temporary_source, final_path)' in SERVER
    assert '"$addToSet": {"subfolders": VOICE_MESSAGES_SUBFOLDER}' in SERVER


def test_voice_upload_has_limits_and_metadata():
    assert "MAX_VOICE_UPLOAD_BYTES" in SERVER
    assert "check_voice_upload_rate_limit" in SERVER
    assert '"duration_seconds": round(audio_info["duration"], 1)' in SERVER
    assert '"guest_name": clean_guest_name' in SERVER


def test_voice_playback_is_scoped_without_requiring_download_permission():
    assert '@api_router.get("/share/{token}/audio/{file_id}")' in SERVER
    assert 'share_file_query(session, id=file_id, file_type="audio")' in SERVER
    assert 'media_type="audio/mpeg"' in SERVER

