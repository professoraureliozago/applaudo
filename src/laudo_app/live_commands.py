from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from difflib import SequenceMatcher


START_TERMS = [
    "gravar",
    "grava",
    "iniciar gravacao",
    "iniciar",
    "comecar gravacao",
    "comecar",
]

STOP_TERMS = [
    "parar",
    "pare",
    "pausar",
    "pausa",
    "encerrar gravacao",
    "finalizar gravacao",
]


@dataclass
class LiveCommandResult:
    recording_active: bool
    updated_draft: str
    status_message: str


def apply_live_command(transcript_chunk: str, recording_active: bool, current_draft: str) -> LiveCommandResult:
    normalized = _normalize(transcript_chunk)
    command = _detect_command(normalized)

    if command == "stop":
        return LiveCommandResult(
            recording_active=False,
            updated_draft=current_draft,
            status_message="Comando detectado: parar/pausar (captura pausada).",
        )

    if command == "start":
        return LiveCommandResult(
            recording_active=True,
            updated_draft=current_draft,
            status_message="Comando detectado: gravar/iniciar (captura ativa).",
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
        status_message="Trecho ignorado (diga 'gravar', 'iniciar' ou 'começar' para iniciar captura).",
    )


def _detect_command(normalized: str) -> str | None:
    start_pos = _last_term_position(normalized, START_TERMS)
    stop_pos = _last_term_position(normalized, STOP_TERMS)

    # fallback fuzzy detection for ASR imperfections (e.g., "gavar", "pausarh")
    fuzzy = _fuzzy_command_from_tokens(normalized)
    if fuzzy == "start" and start_pos < 0:
        start_pos = 0
    if fuzzy == "stop" and stop_pos < 0:
        stop_pos = 0

    if start_pos < 0 and stop_pos < 0:
        return None
    if stop_pos > start_pos:
        return "stop"
    return "start"


def _fuzzy_command_from_tokens(text: str) -> str | None:
    tokens = text.split()
    if not tokens:
        return None

    if any(_is_similar(token, ["gravar", "grava", "iniciar", "comecar"]) for token in tokens):
        return "start"
    if any(_is_similar(token, ["parar", "pare", "pausar", "pausa"]) for token in tokens):
        return "stop"
    return None


def _is_similar(token: str, candidates: list[str]) -> bool:
    return any(SequenceMatcher(None, token, cand).ratio() >= 0.8 for cand in candidates)


def _last_term_position(text: str, terms: list[str]) -> int:
    last = -1
    for term in terms:
        pattern = rf"\b{re.escape(term)}\b"
        for match in re.finditer(pattern, text):
            last = max(last, match.start())
    return last


def _normalize(text: str) -> str:
    text = text.lower()
    text = "".join(ch for ch in unicodedata.normalize("NFD", text) if unicodedata.category(ch) != "Mn")
    text = re.sub(r"[^\w\s]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text
