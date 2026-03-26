from pathlib import Path
import sys

import pytest

sys.path.append(str(Path(__file__).resolve().parents[1]))

from src.laudo_app.transcriber import transcribe_audio_bytes


def test_invalid_provider_raises_runtime_error():
    with pytest.raises(RuntimeError):
        transcribe_audio_bytes(b"fake", "audio.wav", provider="invalid")
