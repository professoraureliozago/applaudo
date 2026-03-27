from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass


@dataclass
class LiveCommandResult:
    recording_active: bool
    updated_draft: str
    status_message: str


def apply_live_command(transcript_chunk: str, recording_active: bool, current_draft: str) -> LiveCommandResult:
    normalized = _normalize(transcript_chunk)

    has_start = bool(re.search(r"\bgravar\b", normalized))
    has_stop = bool(re.search(r"\bparar\b", normalized))

    if has_stop:
        return LiveCommandResult(
            recording_active=False,
            updated_draft=current_draft,
            status_message="Comando detectado: parar (captura pausada).",
        )

    if has_start:
        return LiveCommandResult(
            recording_active=True,
            updated_draft=current_draft,
            status_message="Comando detectado: gravar (captura ativa).",
        )

    if recording_active:
        merged = f"{current_draft.strip()} {transcript_chunk.strip()}".strip() if current_draft.strip() else transcript_chunk.strip()
        return LiveCommandResult(
            recording_active=True,
            updated_draft=merged,
            status_message="Trecho adicionado automaticamente ao rascunho.",
        )

    return LiveCommandResult(
        recording_active=False,
        updated_draft=current_draft,
        status_message="Trecho ignorado (diga 'gravar' para iniciar captura).",
    )


def _normalize(text: str) -> str:
    text = text.lower()
    text = "".join(ch for ch in unicodedata.normalize("NFD", text) if unicodedata.category(ch) != "Mn")
    text = re.sub(r"[^\w\s]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text
