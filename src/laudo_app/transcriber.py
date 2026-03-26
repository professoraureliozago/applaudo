from __future__ import annotations

import tempfile
from pathlib import Path


def transcribe_audio_bytes(
    audio_bytes: bytes,
    filename: str,
    provider: str,
    language: str = "pt",
    local_model_size: str = "small",
    openai_api_key: str | None = None,
    openai_model: str = "whisper-1",
) -> str:
    """Transcribe audio bytes using local faster-whisper or OpenAI API.

    Raises:
        RuntimeError: for provider/dependency/configuration issues.
    """

    suffix = Path(filename).suffix or ".wav"
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=True) as tmp:
        tmp.write(audio_bytes)
        tmp.flush()

        if provider == "local":
            return _transcribe_local(tmp.name, language=language, model_size=local_model_size)
        if provider == "openai":
            return _transcribe_openai(
                tmp.name,
                language=language,
                api_key=openai_api_key,
                model=openai_model,
            )

    raise RuntimeError("Provider de transcrição inválido. Use 'local' ou 'openai'.")


def _transcribe_local(file_path: str, language: str, model_size: str) -> str:
    try:
        from faster_whisper import WhisperModel
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError(
            "Dependência 'faster-whisper' não encontrada. Instale com: pip install faster-whisper"
        ) from exc

    model = WhisperModel(model_size, device="cpu", compute_type="int8")
    segments, _ = model.transcribe(file_path, language=language, vad_filter=True)
    text = " ".join(segment.text.strip() for segment in segments).strip()
    return text


def _transcribe_openai(file_path: str, language: str, api_key: str | None, model: str) -> str:
    if not api_key:
        raise RuntimeError("Informe a OPENAI_API_KEY para usar transcrição via API.")

    try:
        from openai import OpenAI
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("Dependência 'openai' não encontrada. Instale com: pip install openai") from exc

    client = OpenAI(api_key=api_key)
    with open(file_path, "rb") as audio_file:
        result = client.audio.transcriptions.create(
            model=model,
            file=audio_file,
            language=language,
        )

    return (getattr(result, "text", "") or "").strip()
