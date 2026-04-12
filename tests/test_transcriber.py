from pathlib import Path
import sys

import pytest

sys.path.append(str(Path(__file__).resolve().parents[1]))

import src.laudo_app.transcriber as transcriber
from src.laudo_app.transcriber import transcribe_audio_bytes


def test_invalid_provider_raises_runtime_error():
    with pytest.raises(RuntimeError):
        transcribe_audio_bytes(b"fake", "audio.wav", provider="invalid")


def test_temp_file_is_created_and_removed_for_local_provider(monkeypatch):
    captured = {"path": None, "exists_during": False}

    def fake_local(file_path: str, language: str, model_size: str) -> str:
        captured["path"] = file_path
        captured["exists_during"] = Path(file_path).exists()
        return "ok"

    monkeypatch.setattr(transcriber, "_transcribe_local", fake_local)

    result = transcribe_audio_bytes(
        audio_bytes=b"123",
        filename="audio.m4a",
        provider="local",
        language="pt",
        local_model_size="small",
    )

    assert result == "ok"
    assert captured["exists_during"] is True
    assert captured["path"] is not None
    assert Path(captured["path"]).exists() is False
