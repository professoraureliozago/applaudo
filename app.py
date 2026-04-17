from __future__ import annotations

import base64
import hashlib
import json
import os
import shutil
import subprocess
import sys
import unicodedata
from datetime import date, datetime
from pathlib import Path
from typing import Any

import streamlit as st
from streamlit.runtime.scriptrunner import get_script_run_ctx

from src.laudo_app import ReportData, TemplateEngine
from src.laudo_app.database import (
    add_exam_image,
    add_exam_video,
    add_convenio_suggestion,
    add_doctor_suggestion,
    calculate_age,
    create_exam,
    create_or_get_patient,
    delete_exam,
    ensure_db,
    get_exam,
    get_exam_report,
    list_convenios,
    list_executante_names,
    list_doctor_names,
    list_exams,
    save_exam_report,
    search_patients_by_name,
    get_executante_footer,
    upsert_executante_profile,
    update_exam,
)
from src.laudo_app.image_store import (
    clear_unassigned_images,
    get_image_caption,
    infer_caption_from_text,
    list_captured_images,
    load_selected_images_with_captions,
    reassign_images_to_exam,
    save_captured_image,
    set_image_caption,
)
from src.laudo_app.live_commands import apply_live_command
from src.laudo_app.pdf_generator import generate_pdf
from src.laudo_app.template_loader import load_template_config
from src.laudo_app.transcriber import transcribe_audio_bytes
from src.laudo_app.continuous_audio_component import render_continuous_audio
from src.laudo_app.video_recorder_component import render_video_recorder
from src.laudo_app.webrtc_click_component import render_webrtc_click_snapshot

TEMPLATES_PATH = Path("templates/colonoscopia_templates.json")
TEMPLATES_BACKUP_PATH = Path("templates/colonoscopia_templates.backup.json")
TEMPLATES_DEFAULT_PATH = Path("templates/colonoscopia_templates.default.json")


def ensure_streamlit_context() -> None:
    if get_script_run_ctx() is not None:
        return
    if os.environ.get("LAUDO_STREAMLIT_BOOTSTRAPPED") == "1":
        return

    env = os.environ.copy()
    env["LAUDO_STREAMLIT_BOOTSTRAPPED"] = "1"
    cmd = [sys.executable, "-m", "streamlit", "run", os.path.abspath(__file__)]
    raise SystemExit(subprocess.call(cmd, env=env))


def load_templates() -> dict[str, Any]:
    def _is_valid(data: dict[str, Any]) -> bool:
        return bool(data.get("sections"))

    primary = load_template_config(str(TEMPLATES_PATH))
    if _is_valid(primary):
        return primary

    if TEMPLATES_BACKUP_PATH.exists():
        backup = load_template_config(str(TEMPLATES_BACKUP_PATH))
        if _is_valid(backup):
            TEMPLATES_PATH.write_text(TEMPLATES_BACKUP_PATH.read_text(encoding="utf-8"), encoding="utf-8")
            return backup

    if TEMPLATES_DEFAULT_PATH.exists():
        default = load_template_config(str(TEMPLATES_DEFAULT_PATH))
        if _is_valid(default):
            TEMPLATES_PATH.write_text(TEMPLATES_DEFAULT_PATH.read_text(encoding="utf-8"), encoding="utf-8")
            return default

    return primary


def save_templates(data: dict[str, Any]) -> None:
    if not data.get("sections"):
        raise RuntimeError("Bloqueado: tentativa de salvar templates sem seções (evita apagar modelos).")
    if TEMPLATES_PATH.exists():
        TEMPLATES_BACKUP_PATH.write_text(TEMPLATES_PATH.read_text(encoding="utf-8"), encoding="utf-8")
        backups_dir = Path("templates/backups")
        backups_dir.mkdir(parents=True, exist_ok=True)
        ts_name = f"colonoscopia_templates_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        (backups_dir / ts_name).write_text(TEMPLATES_PATH.read_text(encoding="utf-8"), encoding="utf-8")
    with TEMPLATES_PATH.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    # mantém default sincronizado com última versão estável salva
    TEMPLATES_DEFAULT_PATH.write_text(TEMPLATES_PATH.read_text(encoding="utf-8"), encoding="utf-8")


def _to_iso_date(d: date) -> str:
    return d.strftime("%Y-%m-%d")


def _to_br_date(iso_date: str) -> str:
    return datetime.strptime(iso_date, "%Y-%m-%d").strftime("%d/%m/%Y")


def _normalize_for_search(text: str) -> str:
    lowered = " ".join((text or "").strip().lower().split())
    return "".join(ch for ch in unicodedata.normalize("NFD", lowered) if unicodedata.category(ch) != "Mn")


def _parse_br_date(date_text: str) -> date | None:
    raw = (date_text or "").strip()
    if not raw:
        return None
    try:
        return datetime.strptime(raw, "%d/%m/%Y").date()
    except ValueError:
        return None


def _auto_format_birth_input() -> None:
    raw = "".join(ch for ch in st.session_state.get("birth_input", "") if ch.isdigit())[:8]
    if len(raw) <= 2:
        formatted = raw
    elif len(raw) <= 4:
        formatted = f"{raw[:2]}/{raw[2:]}"
    else:
        formatted = f"{raw[:2]}/{raw[2:4]}/{raw[4:]}"
    st.session_state["birth_input"] = formatted


def _try_convert_video_to_mp4(input_path: Path) -> Path:
    ffmpeg_path = shutil.which("ffmpeg")
    if not ffmpeg_path:
        return input_path
    output_path = input_path.with_suffix(".mp4")
    cmd = [
        ffmpeg_path,
        "-y",
        "-i",
        str(input_path),
        "-vcodec",
        "libx264",
        "-crf",
        "28",
        "-preset",
        "veryfast",
        "-acodec",
        "aac",
        str(output_path),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0 or not output_path.exists():
        return input_path
    input_path.unlink(missing_ok=True)
    return output_path


def _clone_exam_media(source_exam_id: int, target_exam_id: int) -> list[str]:
    copied_selected: list[str] = []
    target_image_dir = Path("captured_images") / f"exam_{target_exam_id}"
    target_image_dir.mkdir(parents=True, exist_ok=True)
    for src_img in list_captured_images(exam_id=source_exam_id):
        target = target_image_dir / src_img.name
        if target.exists():
            target = target_image_dir / f"{target.stem}_{datetime.now().strftime('%H%M%S%f')}{target.suffix}"
        shutil.copy2(src_img, target)
        caption = get_image_caption(src_img, exam_id=source_exam_id)
        add_exam_image(target_exam_id, str(target), caption)
        copied_selected.append(str(target))

    source_video_dir = Path("captured_videos") / f"exam_{source_exam_id}"
    target_video_dir = Path("captured_videos") / f"exam_{target_exam_id}"
    target_video_dir.mkdir(parents=True, exist_ok=True)
    if source_video_dir.exists():
        for src_video in sorted(source_video_dir.glob("*")):
            if src_video.suffix.lower() not in {".mp4", ".webm", ".mov"}:
                continue
            target = target_video_dir / src_video.name
            if target.exists():
                target = target_video_dir / f"{target.stem}_{datetime.now().strftime('%H%M%S%f')}{target.suffix}"
            shutil.copy2(src_video, target)
            add_exam_video(target_exam_id, str(target))
    return copied_selected


def _apply_models_for_single_section(engine: TemplateEngine, section_id: str, input_text: str, current_text: str) -> str:
    section = next((s for s in engine.config.get("sections", []) if s.get("id") == section_id), None)
    if not section:
        return current_text
    normalized = engine._normalize_text(input_text or "")
    best = engine._match_section(section, normalized)
    if not best:
        # fallback para revisão manual: aceita correspondência por token de keyword
        input_tokens = {tok for tok in normalized.split() if tok}
        fallback_model = None
        fallback_score = 0
        for model in section.get("models", []):
            score = 0
            for kw in model.get("keywords", []):
                kw_tokens = [t for t in engine._normalize_text(kw).split() if t]
                # match parcial: ao menos um token significativo em comum
                if any(tok in input_tokens for tok in kw_tokens if len(tok) >= 4):
                    score += 1
            if score > fallback_score:
                fallback_score = score
                fallback_model = model
        if fallback_model and fallback_score > 0:
            model_text = (fallback_model.get("text") or "").strip()
            if model_text:
                class _Best:
                    text = model_text
                best = _Best()
    if best:
        model_text = engine._apply_placeholders(best.text, input_text or "").strip()
        if not model_text:
            return current_text
        return model_text
    return current_text


def render_template_manager(templates_data: dict[str, Any]) -> None:
    st.subheader("Modelos (templates) por campo")
    sections = templates_data.get("sections", [])
    section_ids = [s.get("id", "") for s in sections]

    if not section_ids:
        st.warning("Nenhum campo encontrado nos templates. Corrija o JSON na edição avançada.")
        return

    selected_id = st.selectbox("Campo do laudo", options=section_ids, key="tpl_section")
    selected_section = next((s for s in sections if s.get("id") == selected_id), None)
    if not selected_section:
        st.warning("Seção não encontrada no arquivo de templates.")
        return

    models = selected_section.setdefault("models", [])
    st.markdown("**Modelos atuais deste campo**")

    if models:
        for idx, model in enumerate(models):
            st.write(f"**{idx + 1}. {model.get('name', 'sem_nome')}**")
            st.write(f"- Keywords: {', '.join(model.get('keywords', []))}")
            st.write(f"- Texto: {model.get('text', '')}")

            c1, c2 = st.columns(2)
            if c1.button("Editar", key=f"edit_{selected_id}_{idx}"):
                st.session_state["editing_model"] = {"section": selected_id, "idx": idx}
                st.rerun()

            if c2.button("Excluir (2 cliques)", key=f"delete_{selected_id}_{idx}"):
                pending = st.session_state.get("delete_pending")
                current = f"{selected_id}:{idx}"
                if pending == current:
                    models.pop(idx)
                    save_templates(templates_data)
                    st.session_state["delete_pending"] = None
                    st.success("Modelo excluído.")
                    st.rerun()
                else:
                    st.session_state["delete_pending"] = current
                    st.warning("Clique novamente em 'Excluir (2 cliques)' para confirmar exclusão.")
    else:
        st.info("Nenhum modelo cadastrado nesta seção ainda.")

    edit_state = st.session_state.get("editing_model")
    editing_this_section = bool(edit_state and edit_state.get("section") == selected_id)
    edit_idx = int(edit_state.get("idx", -1)) if editing_this_section else -1

    model_for_form = models[edit_idx] if editing_this_section and 0 <= edit_idx < len(models) else {"name": "", "keywords": [], "text": ""}
    form_title = f"Editando modelo: {model_for_form.get('name', 'sem_nome')}" if editing_this_section and 0 <= edit_idx < len(models) else "Adicionar novo modelo"
    submit_label = "Atualizar modelo" if editing_this_section and 0 <= edit_idx < len(models) else "Salvar modelo"

    name_key = "model_form_name"
    keywords_key = "model_form_keywords"
    text_key = "model_form_text"
    mode_key = "model_form_mode"
    current_mode = f"{selected_id}:{edit_idx}" if editing_this_section and 0 <= edit_idx < len(models) else f"{selected_id}:new"
    if st.session_state.get(mode_key) != current_mode:
        st.session_state[name_key] = model_for_form.get("name", "")
        st.session_state[keywords_key] = ", ".join(model_for_form.get("keywords", []))
        st.session_state[text_key] = model_for_form.get("text", "")
        st.session_state[mode_key] = current_mode

    with st.form("model_form"):
        st.markdown(f"### {form_title}")
        model_name = st.text_input("Nome do modelo", key=name_key)
        keywords_csv = st.text_input("Palavras-chave (separadas por vírgula)", key=keywords_key)
        model_text = st.text_area("Texto do modelo", key=text_key)
        col_a, col_b = st.columns(2)
        submitted = col_a.form_submit_button(submit_label)
        cancel_edit = col_b.form_submit_button("Cancelar edição")

    if cancel_edit:
        st.session_state["editing_model"] = None
        st.session_state[mode_key] = None
        st.rerun()

    if submitted:
        keywords = [k.strip() for k in keywords_csv.split(",") if k.strip()]
        if not model_name.strip() or not model_text.strip() or not keywords:
            st.error("Preencha nome, palavras-chave e texto do modelo.")
        else:
            payload = {"name": model_name.strip(), "keywords": keywords, "text": model_text.strip()}
            if editing_this_section and 0 <= edit_idx < len(models):
                models[edit_idx] = payload
                st.success("Modelo atualizado com sucesso.")
            else:
                models.append(payload)
                st.success("Modelo salvo com sucesso.")
            save_templates(templates_data)
            st.session_state["editing_model"] = None
            st.session_state[mode_key] = None
            st.rerun()


def _get_transcription_settings() -> tuple[str, str, str, str]:
    provider = st.radio(
        "Provedor de transcrição",
        options=["local", "openai"],
        captions=["faster-whisper local (CPU)", "API OpenAI (requer chave)"],
        horizontal=True,
    )
    local_model_size = "small"
    openai_key = ""
    openai_model = "whisper-1"

    if provider == "local":
        local_model_size = st.selectbox("Modelo local", ["tiny", "base", "small", "medium"], index=2)
    else:
        openai_key = st.text_input("OPENAI_API_KEY", type="password")
        openai_model = st.text_input("Modelo API", value="whisper-1")

    return provider, local_model_size, openai_key, openai_model


def _transcribe_chunk(audio_bytes: bytes, filename: str, provider: str, local_model_size: str, openai_key: str, openai_model: str) -> str | None:
    with st.spinner("Transcrevendo áudio..."):
        try:
            return transcribe_audio_bytes(
                audio_bytes=audio_bytes,
                filename=filename,
                provider=provider,
                language="pt",
                local_model_size=local_model_size,
                openai_api_key=openai_key,
                openai_model=openai_model,
            )
        except RuntimeError as exc:
            st.error(str(exc))
            return None


def _handle_mic_audio_bytes(
    audio_bytes: bytes,
    filename: str,
    provider: str,
    local_model_size: str,
    openai_key: str,
    openai_model: str,
    force: bool = False,
) -> None:
    if not audio_bytes:
        return

    chunk_hash = hashlib.md5(audio_bytes).hexdigest()
    if not force and chunk_hash == st.session_state.get("last_mic_chunk_hash"):
        return

    st.session_state["last_mic_chunk_hash"] = chunk_hash
    transcript = _transcribe_chunk(
        audio_bytes=audio_bytes,
        filename=filename,
        provider=provider,
        local_model_size=local_model_size,
        openai_key=openai_key,
        openai_model=openai_model,
    )
    if not transcript:
        st.session_state["last_voice_status"] = "Falha na transcrição do trecho."
        st.session_state["audio_metrics"]["transcription_failures"] += 1
        return

    st.session_state["last_voice_transcript"] = transcript
    st.session_state["audio_metrics"]["chunks_processed"] += 1
    result = apply_live_command(
        transcript_chunk=transcript,
        recording_active=st.session_state["recording_active"],
        current_draft=st.session_state.get("transcript_input", ""),
    )
    st.session_state["recording_active"] = result.recording_active
    st.session_state["transcript_input"] = result.updated_draft
    st.session_state["last_voice_status"] = result.status_message
    if result.status_message.startswith("Comando detectado"):
        st.session_state["audio_metrics"]["commands_detected"] += 1


def _apply_transcript_text(transcript: str) -> None:
    if not transcript.strip():
        return
    st.session_state["last_voice_transcript"] = transcript
    st.session_state["audio_metrics"]["chunks_processed"] += 1
    result = apply_live_command(
        transcript_chunk=transcript,
        recording_active=st.session_state["recording_active"],
        current_draft=st.session_state.get("transcript_input", ""),
    )
    st.session_state["recording_active"] = result.recording_active
    st.session_state["transcript_input"] = result.updated_draft
    st.session_state["last_voice_status"] = result.status_message
    if result.status_message.startswith("Comando detectado"):
        st.session_state["audio_metrics"]["commands_detected"] += 1


def _handle_mic_chunk(mic_audio, provider: str, local_model_size: str, openai_key: str, openai_model: str, force: bool = False) -> None:
    if not mic_audio:
        return
    _handle_mic_audio_bytes(
        audio_bytes=mic_audio.getvalue(),
        filename=mic_audio.name or "audio_live.wav",
        provider=provider,
        local_model_size=local_model_size,
        openai_key=openai_key,
        openai_model=openai_model,
        force=force,
    )


def render_auto_transcription() -> None:
    st.markdown("### Transcrição automática de áudio")
    provider, local_model_size, openai_key, openai_model = _get_transcription_settings()

    status = "ATIVA" if st.session_state["recording_active"] else "PAUSADA"
    st.info(f"Captura por comando de voz: **{status}**. Diga 'gravar'/'iniciar' para ativar e 'parar'/'pausar' para pausar.")
    st.caption("Modo contínuo com VAD ativo: use os comandos de voz para controlar a anexação do texto ao rascunho.")

    b1, b2 = st.columns(2)
    if b1.button("Ativar captura"):  # fallback manual
        st.session_state["recording_active"] = True
    if b2.button("Pausar captura"):  # fallback manual
        st.session_state["recording_active"] = False

    st.markdown("**Modo 1: Microfone contínuo + VAD (recomendado)**")
    st.caption("No provedor local, o modo contínuo prioriza reconhecimento de fala do navegador para evitar falhas de decodificação de áudio.")
    c_cfg1, c_cfg2, c_cfg3 = st.columns(3)
    chunk_ms = c_cfg1.slider("Janela máx. por trecho (ms)", min_value=2000, max_value=8000, value=3500, step=250)
    silence_ms = c_cfg2.slider("Silêncio para cortar (ms)", min_value=500, max_value=3000, value=1100, step=100)
    vad_threshold = c_cfg3.slider("Sensibilidade VAD", min_value=0.005, max_value=0.05, value=0.018, step=0.001, format="%.3f")

    live_chunk = render_continuous_audio(
        key="continuous-audio",
        chunk_ms=chunk_ms,
        silence_ms=silence_ms,
        vad_threshold=vad_threshold,
    )
    if live_chunk:
        audio_bytes = live_chunk.get("audio_bytes")
        mime_type = str(live_chunk.get("mime_type", "audio/wav"))
        capture_ts = int(live_chunk.get("timestamp", 0) or 0)
        transcript_text = str(live_chunk.get("transcript_text", "") or "")
        if capture_ts and capture_ts != st.session_state.get("last_continuous_audio_ts"):
            st.session_state["last_continuous_audio_ts"] = capture_ts
            if transcript_text.strip():
                _apply_transcript_text(transcript_text)
            elif provider == "openai" and isinstance(audio_bytes, (bytes, bytearray)) and len(audio_bytes) > 0:
                suffix = ".webm" if "webm" in mime_type else ".wav"
                _handle_mic_audio_bytes(
                    audio_bytes=bytes(audio_bytes),
                    filename=f"audio_live{suffix}",
                    provider=provider,
                    local_model_size=local_model_size,
                    openai_key=openai_key,
                    openai_model=openai_model,
                    force=False,
                )

    if st.button("Diagnóstico de comando"):
        if st.session_state.get("last_voice_transcript"):
            st.write(f"Última transcrição: {st.session_state['last_voice_transcript']}")
            st.write(f"Status: {st.session_state.get('last_voice_status', '')}")
        else:
            st.write("Ainda não há transcrição de trecho de microfone.")

    with st.expander("Fallback manual (st.audio_input)"):
        mic_audio = st.audio_input("Gravar trecho do exame", key="audio_input_live")
        auto_mode = st.checkbox("Processar automaticamente novos trechos", value=True)
        manual_process = st.button("Processar trecho do microfone agora")
        if manual_process:
            if not mic_audio:
                st.warning("Grave um trecho no microfone antes de processar.")
            else:
                _handle_mic_chunk(
                    mic_audio=mic_audio,
                    provider=provider,
                    local_model_size=local_model_size,
                    openai_key=openai_key,
                    openai_model=openai_model,
                    force=True,
                )
        if auto_mode and mic_audio:
            _handle_mic_chunk(
                mic_audio=mic_audio,
                provider=provider,
                local_model_size=local_model_size,
                openai_key=openai_key,
                openai_model=openai_model,
                force=False,
            )

    if st.session_state.get("last_voice_transcript"):
        st.success(f"Última transcrição detectada: {st.session_state['last_voice_transcript']}")
    if st.session_state.get("last_voice_status"):
        st.info(st.session_state["last_voice_status"])
    metrics = st.session_state.get("audio_metrics", {})
    st.caption(
        "Métricas sessão — "
        f"trechos processados: {metrics.get('chunks_processed', 0)} | "
        f"comandos detectados: {metrics.get('commands_detected', 0)} | "
        f"falhas de transcrição: {metrics.get('transcription_failures', 0)}"
    )

    st.markdown("**Modo 2: Upload de arquivo (opcional)**")
    uploaded_audio = st.file_uploader("Envie o áudio do exame (wav/mp3/m4a)", type=["wav", "mp3", "m4a", "ogg", "webm"], key="audio_upload")

    if st.button("Transcrever arquivo enviado"):
        if not uploaded_audio:
            st.error("Envie um arquivo de áudio para transcrever.")
        else:
            transcript = _transcribe_chunk(
                audio_bytes=uploaded_audio.getvalue(),
                filename=uploaded_audio.name,
                provider=provider,
                local_model_size=local_model_size,
                openai_key=openai_key,
                openai_model=openai_model,
            )
            if transcript:
                previous = st.session_state.get("transcript_input", "")
                st.session_state["transcript_input"] = f"{previous} {transcript}".strip() if previous.strip() else transcript
                st.success("Trecho do arquivo adicionado ao rascunho.")

    c1, c2 = st.columns(2)
    if c1.button("Limpar rascunho da transcrição"):
        st.session_state["transcript_input"] = ""
        st.session_state["last_voice_transcript"] = ""
        st.session_state["last_voice_status"] = ""
        st.success("Rascunho limpo.")
    if c2.button("Usar exemplo de narração"):
        st.session_state["transcript_input"] = "Reto com mucosa normal. No cólon descendente, pólipo séssil de 1 cm, realizada polipectomia."
        st.success("Exemplo carregado no rascunho.")


def render_image_capture_tab(exam_id: int | None) -> None:
    st.subheader("Captura e seleção de imagens")
    st.caption("Capture fotos durante o exame e marque as que devem ir para o laudo.")

    st.markdown("#### Captura WebRTC custom por clique no frame")
    st.caption("Habilite o modo custom para exibir um frame de vídeo contínuo. Clique no próprio frame para capturar a imagem.")
    use_webrtc_custom = st.toggle("Habilitar captura WebRTC custom", value=False)
    if use_webrtc_custom:
        snapshot_record = render_webrtc_click_snapshot(key="exam-webrtc-click", width=960, height=540)
        if snapshot_record:
            snapshot_bytes, capture_ts = snapshot_record
            if capture_ts and capture_ts == st.session_state.get("last_webrtc_capture_ts"):
                snapshot_bytes = b""
            else:
                st.session_state["last_webrtc_capture_ts"] = capture_ts
        else:
            snapshot_bytes = b""
        if snapshot_bytes:
            context_text = st.session_state.get("transcript_input", "") or st.session_state.get("last_voice_transcript", "")
            auto_caption = infer_caption_from_text(context_text)
            saved = save_captured_image(snapshot_bytes, suffix=".jpg", caption=auto_caption, exam_id=exam_id)
            if exam_id:
                add_exam_image(exam_id, str(saved), auto_caption)
            st.success(f"Snapshot salvo por clique: {saved.name} ({auto_caption})")

    st.markdown("#### Filmagem do exame")
    st.caption("Clique em iniciar/parar no gravador abaixo para capturar a filmagem do exame.")
    video_record = render_video_recorder(key=f"video-recorder-{exam_id or 'draft'}")
    if video_record:
        video_bytes, mime_type, capture_ts = video_record
        if capture_ts and capture_ts != st.session_state.get("last_video_capture_ts"):
            st.session_state["last_video_capture_ts"] = capture_ts
            if not exam_id:
                video_dir = Path("captured_videos") / "unassigned"
                video_dir.mkdir(parents=True, exist_ok=True)
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
                suffix = ".webm" if "webm" in mime_type else ".mp4"
                video_path = video_dir / f"filmagem_{timestamp}{suffix}"
                video_path.write_bytes(video_bytes)
                video_path = _try_convert_video_to_mp4(video_path)
                st.success(f"Filmagem salva em rascunho: {video_path.name}")
            else:
                video_dir = Path("captured_videos") / f"exam_{exam_id}"
                video_dir.mkdir(parents=True, exist_ok=True)
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
                suffix = ".webm" if "webm" in mime_type else ".mp4"
                video_path = video_dir / f"filmagem_{timestamp}{suffix}"
                video_path.write_bytes(video_bytes)
                video_path = _try_convert_video_to_mp4(video_path)
                add_exam_video(exam_id, str(video_path))
                st.success(f"Filmagem salva: {video_path.name}")

    st.markdown("---")
    st.markdown("### Galeria de imagens salvas")
    images = list_captured_images(exam_id=exam_id)
    if not images:
        st.info("Nenhuma imagem salva ainda.")
        st.session_state["selected_gallery_paths"] = []
    else:
        st.caption("Marque as imagens que deseja anexar ao laudo.")
        cols = st.columns(4)
        prev_selected = set(st.session_state.get("selected_gallery_paths", []))
        selected_paths: list[str] = []

        for idx, img in enumerate(images):
            col = cols[idx % 4]
            col.image(str(img), use_container_width=True)
            current_caption = get_image_caption(img, exam_id=exam_id)
            new_caption = col.text_input("Legenda", value=current_caption, key=f"cap_{exam_id}_{img.name}")
            if new_caption != current_caption:
                set_image_caption(img, new_caption, exam_id=exam_id)
            checked = col.checkbox(f"Selecionar {img.name}", key=f"sel_{exam_id}_{img.name}", value=str(img) in prev_selected)
            if checked:
                selected_paths.append(str(img))
            if col.button("Excluir imagem (2 cliques)", key=f"del_img_{exam_id}_{img.name}"):
                pending = st.session_state.get("delete_image_pending")
                current_key = str(img)
                if pending == current_key:
                    img.unlink(missing_ok=True)
                    st.session_state["delete_image_pending"] = None
                    st.success(f"Imagem {img.name} excluída.")
                    st.rerun()
                else:
                    st.session_state["delete_image_pending"] = current_key
                    st.warning("Clique novamente para confirmar exclusão da imagem.")

        st.session_state["selected_gallery_paths"] = selected_paths


    st.markdown("### Filmagens salvas")
    video_dir = Path("captured_videos") / (f"exam_{exam_id}" if exam_id else "unassigned")
    videos_raw = [p for p in video_dir.glob("*") if p.suffix.lower() in {".mp4", ".webm", ".mov"}] if video_dir.exists() else []
    # deduplicação defensiva por caminho absoluto
    seen: set[str] = set()
    videos: list[Path] = []
    for p in sorted(videos_raw, reverse=True):
        key = str(p.resolve())
        if key in seen:
            continue
        seen.add(key)
        videos.append(p)
    if not videos:
        st.info("Nenhuma filmagem salva para este exame.")
    else:
        st.markdown("#### Miniaturas de vídeo")
        vcols = st.columns(3)
        for idx, video in enumerate(videos):
            col = vcols[idx % 3]
            col.caption(video.name)
            if col.button("Abrir vídeo", key=f"open_vid_{video.name}"):
                st.session_state["selected_video_path"] = str(video)
            if col.button("Excluir vídeo (2 cliques)", key=f"del_vid_{video.name}"):
                pending = st.session_state.get("delete_video_pending")
                current_key = str(video)
                if pending == current_key:
                    video.unlink(missing_ok=True)
                    st.session_state["delete_video_pending"] = None
                    if st.session_state.get("selected_video_path") == current_key:
                        st.session_state["selected_video_path"] = None
                    st.success(f"Vídeo {video.name} excluído.")
                    st.rerun()
                else:
                    st.session_state["delete_video_pending"] = current_key
                    st.warning("Clique novamente para confirmar exclusão do vídeo.")
        selected_video = st.session_state.get("selected_video_path")
        if selected_video and Path(selected_video).exists():
            st.markdown("#### Reprodutor de vídeo")
            st.video(selected_video)
            if st.button("Fechar reprodutor"):
                st.session_state["selected_video_path"] = None
                st.rerun()


def render_app() -> None:
    st.set_page_config(page_title="Laudo Colonoscopia por Áudio", layout="wide")
    st.title("Laudo de Colonoscopia (MVP)")
    st.caption("Protótipo: cadastro seguro de paciente/exame -> áudio/transcrição -> revisão -> PDF")
    ensure_db()

    try:
        templates_data = load_templates()
    except RuntimeError as exc:
        st.error(str(exc))
        st.warning("Usando configuração mínima vazia para permitir correção no Gerenciar modelos.")
        templates_data = {"sections": []}

    
    