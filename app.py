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
from io import BytesIO
from math import atan2, cos, pi, sin
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont
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
from src.laudo_app.clickable_image_component import render_clickable_image
from src.laudo_app.image_annotator_component import render_image_annotator
from src.laudo_app.video_recorder_component import render_video_recorder
from src.laudo_app.webrtc_click_component import render_webrtc_click_snapshot

TEMPLATES_PATH = Path("templates/colonoscopia_templates.json")
TEMPLATES_BACKUP_PATH = Path("templates/colonoscopia_templates.backup.json")
TEMPLATES_DEFAULT_PATH = Path("templates/colonoscopia_templates.default.json")
ANNOTATION_COLORS = {
    "Vermelho": "#ff2d2d",
    "Amarelo": "#ffd43b",
    "Verde": "#2fce68",
    "Azul": "#3b82f6",
    "Branco": "#ffffff",
    "Preto": "#111111",
}


def inject_sidebar_button_style() -> None:
    st.markdown(
        """
        <style>
        [data-testid="stSidebar"] div.stButton > button {
            width: 100%;
            min-height: 44px;
            padding: 0.45rem 0.35rem;
            border-radius: 7px;
        }

        [data-testid="stSidebar"] div.stButton > button p {
            font-size: 0.86rem;
            line-height: 1.15;
            text-align: center;
            white-space: normal;
            overflow-wrap: normal;
            word-break: normal;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


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


def _load_annotation_font(size: int) -> ImageFont.ImageFont:
    for font_name in ("arial.ttf", "calibri.ttf", "DejaVuSans.ttf"):
        try:
            return ImageFont.truetype(font_name, size)
        except OSError:
            continue
    return ImageFont.load_default()


def _render_annotated_image_bytes(
    image_path: Path,
    *,
    annotation_text: str,
    start_x: float,
    start_y: float,
    end_x: float,
    end_y: float,
    color_hex: str,
    line_width: int,
    font_size: int,
) -> bytes:
    with Image.open(image_path) as original:
        image = original.convert("RGBA")

    width, height = image.size
    start = (int(width * start_x / 100), int(height * start_y / 100))
    end = (int(width * end_x / 100), int(height * end_y / 100))
    draw = ImageDraw.Draw(image)
    font = _load_annotation_font(font_size)
    label = annotation_text.strip()

    if label:
        padding = max(6, font_size // 3)
        bbox = draw.textbbox((0, 0), label, font=font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]
        box_left = max(0, min(start[0], width - text_width - padding * 2))
        box_top = max(0, min(start[1], height - text_height - padding * 2))
        box_right = box_left + text_width + padding * 2
        box_bottom = box_top + text_height + padding * 2
        draw.rounded_rectangle(
            (box_left, box_top, box_right, box_bottom),
            radius=max(4, padding // 2),
            fill=(0, 0, 0, 175),
        )
        draw.text((box_left + padding, box_top + padding), label, fill="#ffffff", font=font)
        line_start = (box_right, (box_top + box_bottom) // 2) if end[0] >= start[0] else (box_left, (box_top + box_bottom) // 2)
    else:
        line_start = start

    draw.line((line_start, end), fill=color_hex, width=line_width)
    angle = atan2(end[1] - line_start[1], end[0] - line_start[0])
    head_len = max(16, line_width * 5)
    head_angle = pi / 7
    left = (
        end[0] - head_len * cos(angle - head_angle),
        end[1] - head_len * sin(angle - head_angle),
    )
    right = (
        end[0] - head_len * cos(angle + head_angle),
        end[1] - head_len * sin(angle + head_angle),
    )
    draw.polygon([end, left, right], fill=color_hex)

    output = BytesIO()
    if image_path.suffix.lower() == ".png":
        image.save(output, format="PNG")
    else:
        image.convert("RGB").save(output, format="JPEG", quality=95)
    return output.getvalue()


def _render_image_annotation_editor(exam_id: int | None) -> None:
    editing_path = st.session_state.get("editing_image_path")
    if not editing_path:
        return

    image_path = Path(editing_path)
    if not image_path.exists():
        st.warning("A imagem selecionada para edição não existe mais.")
        st.session_state["editing_image_path"] = None
        return

    st.markdown("---")
    st.markdown("### Editor de imagem")
    st.caption(image_path.name)

    active_key = str(image_path)
    if st.session_state.get("annotation_active_image") != active_key:
        st.session_state["annotation_active_image"] = active_key
        st.session_state["annotation_text"] = ""
        st.session_state["annotation_start_x"] = 18.0
        st.session_state["annotation_start_y"] = 22.0
        st.session_state["annotation_end_x"] = 70.0
        st.session_state["annotation_end_y"] = 52.0
        st.session_state["annotation_color"] = "Vermelho"
        st.session_state["annotation_width"] = 6
        st.session_state["annotation_font_size"] = 28

    canvas_col, control_col = st.columns([2, 1])
    with control_col:
        annotation_text = st.text_input("Texto", key="annotation_text", placeholder="Ex.: pólipo")
        color_name = st.selectbox("Cor da seta", list(ANNOTATION_COLORS), key="annotation_color")
        line_width = st.slider("Espessura", min_value=2, max_value=16, key="annotation_width")
        font_size = st.slider("Tamanho do texto", min_value=14, max_value=56, key="annotation_font_size")
        st.caption("Arraste as bolinhas na imagem: a branca move o texto/início da seta; a colorida move a ponta.")

    with canvas_col:
        annotation_result = render_image_annotator(
            image_path,
            key=f"annotator_{image_path.name}",
            annotation_text=annotation_text,
            color_hex=ANNOTATION_COLORS[color_name],
            line_width=line_width,
            font_size=font_size,
            start_x=float(st.session_state.get("annotation_start_x", 18.0)),
            start_y=float(st.session_state.get("annotation_start_y", 22.0)),
            end_x=float(st.session_state.get("annotation_end_x", 70.0)),
            end_y=float(st.session_state.get("annotation_end_y", 52.0)),
        )

    if annotation_result:
        for source, target in (
            ("start_x", "annotation_start_x"),
            ("start_y", "annotation_start_y"),
            ("end_x", "annotation_end_x"),
            ("end_y", "annotation_end_y"),
        ):
            value = annotation_result.get(source)
            if isinstance(value, (int, float)):
                st.session_state[target] = float(value)

    save_col, cancel_col = st.columns(2)
    if save_col.button("Salvar imagem anotada", use_container_width=True):
        preview_bytes = _render_annotated_image_bytes(
            image_path,
            annotation_text=annotation_text,
            start_x=float(st.session_state.get("annotation_start_x", 18.0)),
            start_y=float(st.session_state.get("annotation_start_y", 22.0)),
            end_x=float(st.session_state.get("annotation_end_x", 70.0)),
            end_y=float(st.session_state.get("annotation_end_y", 52.0)),
            color_hex=ANNOTATION_COLORS[color_name],
            line_width=line_width,
            font_size=font_size,
        )
        image_path.write_bytes(preview_bytes)
        set_image_caption(image_path, get_image_caption(image_path, exam_id=exam_id), exam_id=exam_id)
        st.session_state["editing_image_path"] = None
        st.success("Imagem anotada salva.")
        st.rerun()
    if cancel_col.button("Cancelar edição", use_container_width=True):
        st.session_state["editing_image_path"] = None
        st.rerun()


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
    if len(audio_bytes) < 4096:
        st.session_state["last_voice_status"] = "Trecho de áudio muito curto; aguardando mais fala."
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
            elif isinstance(audio_bytes, (bytes, bytearray)) and len(audio_bytes) > 0:
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
            with col:
                clicked_at = render_clickable_image(img, key=f"click_img_{exam_id}_{img.name}")
            last_click_key = f"last_click_img_{exam_id}_{img.name}"
            if clicked_at and clicked_at != st.session_state.get(last_click_key):
                st.session_state[last_click_key] = clicked_at
                st.session_state["editing_image_path"] = str(img)
                st.rerun()
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

    _render_image_annotation_editor(exam_id)

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
    inject_sidebar_button_style()
    st.title("Laudo de Colonoscopia (MVP)")
    st.caption("Protótipo: cadastro seguro de paciente/exame -> áudio/transcrição -> revisão -> PDF")
    ensure_db()

    try:
        templates_data = load_templates()
    except RuntimeError as exc:
        st.error(str(exc))
        st.warning("Usando configuração mínima vazia para permitir correção no Gerenciar modelos.")
        templates_data = {"sections": []}

    engine = TemplateEngine(config=templates_data)

    st.session_state.setdefault("transcript_input", "")
    st.session_state.setdefault("recording_active", True)
    st.session_state.setdefault("last_mic_chunk_hash", None)
    st.session_state.setdefault("last_voice_transcript", "")
    st.session_state.setdefault("last_voice_status", "")
    st.session_state.setdefault("selected_gallery_paths", [])
    st.session_state.setdefault("current_exam_id", None)
    st.session_state.setdefault("current_patient_id", None)
    st.session_state.setdefault("current_patient_name", "")
    st.session_state.setdefault("current_patient_birth_date", "")
    st.session_state.setdefault("current_patient_sexo", "")
    st.session_state.setdefault("current_patient_convenio", "")
    st.session_state.setdefault("draft_doctor_name", "Dr(a).")
    st.session_state.setdefault("draft_executante_name", "Dr(a).")
    st.session_state.setdefault("draft_footer_text", "Avenida Santos Dumont 2335 - Telefone : 3322 4111 - 99199 6369")
    st.session_state.setdefault("draft_exam_date", date.today())
    st.session_state.setdefault("draft_exam_time", datetime.now().time().replace(second=0, microsecond=0))
    st.session_state.setdefault("draft_birth_date_text", "")
    st.session_state.setdefault("birth_input", "")
    st.session_state.setdefault("new_patient_name_input", "")
    st.session_state.setdefault("selected_existing_patient_id", None)
    st.session_state.setdefault("flow_mode", "Novo exame")
    st.session_state.setdefault("pending_transcript_append", "")
    st.session_state.setdefault("pending_section_updates", {})
    st.session_state.setdefault("last_auto_sections", {})
    st.session_state.setdefault("cleaned_unassigned_once", False)
    st.session_state.setdefault("last_video_capture_ts", 0)
    st.session_state.setdefault("last_webrtc_capture_ts", 0)
    st.session_state.setdefault("last_continuous_audio_ts", 0)
    st.session_state.setdefault("audio_metrics", {"chunks_processed": 0, "commands_detected": 0, "transcription_failures": 0})
    st.session_state.setdefault("pdf_preview_exam_id", None)
    st.session_state.setdefault("editing_image_path", None)
    if not st.session_state.get("cleaned_unassigned_once"):
        clear_unassigned_images()
        draft_video_dir = Path("captured_videos") / "unassigned"
        if draft_video_dir.exists():
            for p in draft_video_dir.glob("*"):
                if p.is_file():
                    p.unlink(missing_ok=True)
        st.session_state["cleaned_unassigned_once"] = True

    with st.sidebar:
        st.header("Exames")
        b_new, b_open = st.columns(2)
        new_clicked = b_new.button("Novo exame", use_container_width=True)
        open_clicked = b_open.button("Abrir existente", help="Abrir exame existente", use_container_width=True)
        if new_clicked:
            st.session_state["flow_mode"] = "Novo exame"
        if open_clicked:
            st.session_state["flow_mode"] = "Abrir exame existente"
        flow = st.session_state.get("flow_mode", "Novo exame")

        if new_clicked:
            st.session_state["current_patient_id"] = None
            st.session_state["current_patient_name"] = ""
            st.session_state["current_patient_birth_date"] = ""
            st.session_state["current_patient_sexo"] = ""
            st.session_state["current_patient_convenio"] = ""
            st.session_state["current_exam_id"] = None
            st.session_state["selected_gallery_paths"] = []
            st.session_state["report"] = None
            st.session_state["last_auto_sections"] = {}
            st.session_state["transcript_input"] = ""
            st.session_state["draft_doctor_name"] = "Dr(a)."
            st.session_state["draft_executante_name"] = "Dr(a)."
            st.session_state["draft_footer_text"] = "Avenida Santos Dumont 2335 - Telefone : 3322 4111 - 99199 6369"
            st.session_state["draft_exam_date"] = date.today()
            st.session_state["draft_exam_time"] = datetime.now().time().replace(second=0, microsecond=0)
            st.session_state["draft_birth_date_text"] = ""
            st.session_state["birth_input"] = ""
            st.session_state["new_patient_name_input"] = ""
            st.session_state["selected_existing_patient_id"] = None
            st.session_state["last_video_capture_ts"] = 0
            st.session_state["last_webrtc_capture_ts"] = 0
            st.session_state["last_continuous_audio_ts"] = 0
            st.session_state["audio_metrics"] = {"chunks_processed": 0, "commands_detected": 0, "transcription_failures": 0}
            st.session_state["pdf_preview_exam_id"] = None
            clear_unassigned_images()
            draft_video_dir = Path("captured_videos") / "unassigned"
            if draft_video_dir.exists():
                for p in draft_video_dir.glob("*"):
                    if p.is_file():
                        p.unlink(missing_ok=True)

        if flow == "Novo exame":
            st.markdown("### Cadastro do paciente e exame")
            patient_name = st.text_input("Nome do Paciente", key="new_patient_name_input")
            existing_candidates = search_patients_by_name(patient_name) if patient_name.strip() else []
            normalized_input = _normalize_for_search(patient_name)
            prefix_matches = [p for p in existing_candidates if p.normalized_name.startswith(normalized_input)] if normalized_input else []
            if prefix_matches:
                labels = [f"{p.name} ({_to_br_date(p.birth_date)})" for p in prefix_matches]
                chosen_label = st.selectbox("Pacientes já cadastrados (refino automático)", ["-- selecionar --"] + labels, key="existing_patient_quickpick")
                if chosen_label != "-- selecionar --":
                    chosen = prefix_matches[labels.index(chosen_label)]
                    st.session_state["selected_existing_patient_id"] = chosen.id
                    st.session_state["birth_input"] = _to_br_date(chosen.birth_date)
                    st.session_state["current_patient_sexo"] = chosen.sexo
                    st.session_state["current_patient_convenio"] = chosen.convenio
                    patient_name = chosen.name
            sexo_options = ["", "Feminino", "Masculino"]
            sexo_default = st.session_state.get("current_patient_sexo", "")
            sexo_index = sexo_options.index(sexo_default) if sexo_default in sexo_options else 0
            sexo = st.selectbox("Sexo", sexo_options, index=sexo_index)
            birth_text = st.text_input(
                "Data de Nascimento (DD/MM/AAAA)",
                key="birth_input",
                placeholder="DD/MM/AAAA",
                max_chars=10,
                on_change=_auto_format_birth_input,
            )
            st.session_state["draft_birth_date_text"] = birth_text
            nascimento = _parse_br_date(birth_text)
            idade_calc = calculate_age(_to_iso_date(nascimento)) if nascimento else 0
            st.text_input("Idade (automática)", value=str(max(idade_calc, 0)) if nascimento else "", disabled=True)
            doctor_options = ["Dr(a)."] + [d for d in list_doctor_names() if d != "Dr(a)."]
            doctor_default = st.session_state.get("draft_doctor_name", "Dr(a).")
            if doctor_default not in doctor_options:
                doctor_options.append(doctor_default)
            medico_sugestao = st.selectbox(
                "Nome do Médico Solicitante (com sugestões)",
                options=doctor_options,
                index=doctor_options.index(doctor_default),
            )
            medico_novo = st.text_input("Ou digite novo médico solicitante (opcional)")
            medico = medico_novo.strip() or medico_sugestao
            if medico_novo.strip() and medico_novo.strip() not in doctor_options:
                if st.button("Cadastrar novo médico solicitante"):
                    add_doctor_suggestion(medico_novo.strip())
                    st.success("Novo médico solicitante cadastrado nas sugestões.")

            executante_options = ["Dr(a)."] + [d for d in list_executante_names() if d != "Dr(a)."]
            executante_default = st.session_state.get("draft_executante_name", "Dr(a).")
            if executante_default not in executante_options:
                executante_options.append(executante_default)
            executante_sugestao = st.selectbox(
                "Médico Executante (com sugestões)",
                options=executante_options,
                index=executante_options.index(executante_default),
            )
            executante_novo = st.text_input("Ou digite novo médico executante (opcional)")
            executante = executante_novo.strip() or executante_sugestao
            footer_text = st.session_state.get("draft_footer_text", "")
            if executante_novo.strip() and executante_novo.strip() not in executante_options:
                st.caption("Novo médico executante: preencha os dados do rodapé antes de cadastrar.")
                footer_text = st.text_area(
                    "Dados do rodapé (endereço, telefones etc.)",
                    value=footer_text,
                    key="executante_footer_input",
                    height=80,
                )
                if st.button("Cadastrar médico executante"):
                    if not footer_text.strip():
                        st.warning("Informe os dados do rodapé para cadastrar o médico executante.")
                    else:
                        upsert_executante_profile(executante_novo.strip(), footer_text.strip())
                        st.session_state["draft_footer_text"] = footer_text.strip()
                        st.success("Médico executante cadastrado com dados de rodapé.")
            else:
                st.session_state["draft_footer_text"] = get_executante_footer(executante) or st.session_state.get(
                    "draft_footer_text",
                    "",
                )

            convenio_options = [""] + list_convenios()
            convenio_default = st.session_state.get("current_patient_convenio", "")
            if convenio_default and convenio_default not in convenio_options:
                convenio_options.append(convenio_default)
            convenio_sugestao = st.selectbox(
                "Convênio (com sugestões)",
                options=convenio_options,
                index=convenio_options.index(convenio_default) if convenio_default in convenio_options else 0,
            )
            convenio_novo = st.text_input("Ou digite novo convênio (opcional)")
            convenio = convenio_novo.strip() or convenio_sugestao
            if convenio_novo.strip() and convenio_novo.strip() not in convenio_options:
                if st.button("Cadastrar novo convênio"):
                    add_convenio_suggestion(convenio_novo.strip())
                    st.success("Novo convênio cadastrado nas sugestões.")
            now = datetime.now()
            data_exame_dt = st.date_input("Data do Exame", value=st.session_state.get("draft_exam_date", now.date()), format="DD/MM/YYYY")
            hora_exame_dt = st.time_input("Hora do exame", value=st.session_state.get("draft_exam_time", now.time().replace(second=0, microsecond=0)))

            if st.button("Salvar dados do paciente"):
                if not patient_name.strip():
                    st.error("Nome do paciente é obrigatório.")
                elif not nascimento:
                    st.error("Informe a data de nascimento no formato DD/MM/AAAA.")
                elif nascimento > date.today():
                    st.error("Data de nascimento não pode ser futura.")
                else:
                    duplicate = None
                    candidates = search_patients_by_name(patient_name.strip())
                    duplicate = next(
                        (p for p in candidates if p.normalized_name == " ".join(patient_name.strip().lower().split()) and p.birth_date == _to_iso_date(nascimento)),
                        None,
                    )
                    if duplicate:
                        st.info("Paciente já cadastrado: usando cadastro existente para novo exame.")
                    patient, _ = create_or_get_patient(
                        name=patient_name.strip(),
                        sexo=sexo,
                        birth_date_iso=_to_iso_date(nascimento),
                    )
                    st.session_state["current_patient_id"] = patient.id
                    st.session_state["current_patient_name"] = patient.name
                    st.session_state["current_patient_birth_date"] = patient.birth_date
                    st.session_state["current_patient_sexo"] = patient.sexo
                    st.session_state["current_patient_convenio"] = convenio
                    st.session_state["draft_doctor_name"] = medico
                    st.session_state["draft_executante_name"] = executante
                    st.session_state["draft_exam_date"] = data_exame_dt
                    st.session_state["draft_exam_time"] = hora_exame_dt
                    exam = create_exam(
                        patient_id=patient.id,
                        doctor_name=medico,
                        exam_date_iso=_to_iso_date(data_exame_dt),
                        exam_time_hhmm=hora_exame_dt.strftime("%H:%M"),
                        convenio=convenio,
                        executante=executante,
                    )
                    st.session_state["current_exam_id"] = exam.id
                    st.session_state["selected_gallery_paths"] = []
                    st.success(f"Paciente {patient.name} pronto. Exame ativo #{exam.id} criado para autosave de mídias.")

        else:
            st.markdown("### Buscar paciente")
            search_name = st.text_input("Busca por nome do paciente", key="search_patient_name")
            patients = search_patients_by_name(search_name) if search_name.strip() else []
            patient_id_for_exams: int | None = None
            if patients:
                labels = [f"{p.name} ({_to_br_date(p.birth_date)})" for p in patients]
                chosen_label = st.selectbox("Pacientes encontrados", labels)
                chosen = patients[labels.index(chosen_label)]
                patient_id_for_exams = chosen.id

            if search_name.strip():
                exams = list_exams(patient_id=patient_id_for_exams) if patient_id_for_exams else []
            else:
                exams = list_exams()
            if not exams:
                st.info("Nenhum exame salvo encontrado.")
            else:
                exam_labels = [
                    f"#{e['id']} | {e['patient_name']} | {_to_br_date(e['exam_date'])} {e['exam_time']}"
                    for e in exams
                ]
                selected_exam_label = st.selectbox("Exames salvos", exam_labels)
                selected_exam = exams[exam_labels.index(selected_exam_label)]

                c_open, c_pdf, c_delete = st.columns(3)
                if c_open.button("Abrir exame", use_container_width=True):
                    new_exam = create_exam(
                        patient_id=selected_exam["patient_id"],
                        doctor_name=selected_exam["doctor_name"],
                        exam_date_iso=_to_iso_date(date.today()),
                        exam_time_hhmm=datetime.now().strftime("%H:%M"),
                        convenio=selected_exam.get("convenio", ""),
                        executante=selected_exam.get("executante", ""),
                    )
                    st.session_state["current_exam_id"] = new_exam.id
                    st.session_state["current_patient_id"] = selected_exam["patient_id"]
                    st.session_state["current_patient_name"] = selected_exam["patient_name"]
                    st.session_state["current_patient_birth_date"] = selected_exam["birth_date"]
                    st.session_state["current_patient_sexo"] = selected_exam["sexo"]
                    st.session_state["current_patient_convenio"] = selected_exam["convenio"]
                    st.session_state["draft_doctor_name"] = selected_exam["doctor_name"]
                    st.session_state["draft_executante_name"] = selected_exam.get("executante", "Dr(a).")
                    st.session_state["draft_footer_text"] = get_executante_footer(selected_exam.get("executante", ""))
                    st.session_state["draft_exam_date"] = date.today()
                    st.session_state["draft_exam_time"] = datetime.now().time().replace(second=0, microsecond=0)
                    st.session_state["selected_gallery_paths"] = _clone_exam_media(selected_exam["id"], new_exam.id)
                    report_data = get_exam_report(selected_exam["id"])
                    if report_data:
                        loaded = ReportData(
                            paciente=selected_exam["patient_name"],
                            medico=selected_exam["doctor_name"],
                            medico_executante=selected_exam.get("executante", ""),
                            sexo=selected_exam["sexo"],
                            idade=str(max(calculate_age(selected_exam["birth_date"]), 0)),
                            data_exame=_to_br_date(selected_exam["exam_date"]),
                            hora_exame=selected_exam["exam_time"],
                            convenio=selected_exam["convenio"],
                            footer_text=get_executante_footer(selected_exam.get("executante", "")),
                        )
                        loaded.secoes = report_data.get("sections", {})
                        loaded.ensure_sections()
                        st.session_state["report"] = loaded
                        st.session_state["last_auto_sections"] = dict(loaded.secoes)
                        st.session_state["transcript_input"] = report_data.get("transcript", "")
                    st.success(f"Exame #{selected_exam['id']} carregado como base para novo laudo (novo exame ativo #{new_exam.id}).")
                if c_pdf.button("Abrir PDF", use_container_width=True):
                    st.session_state["pdf_preview_exam_id"] = selected_exam["id"]
                    st.rerun()
                if c_delete.button("Excluir", help="Excluir exame (2 cliques)", use_container_width=True):
                    pending = st.session_state.get("delete_exam_pending")
                    current = selected_exam["id"]
                    if pending == current:
                        delete_exam(current)
                        st.session_state["delete_exam_pending"] = None
                        if st.session_state.get("current_exam_id") == current:
                            st.session_state["current_exam_id"] = None
                        st.success("Exame excluído.")
                        st.rerun()
                    else:
                        st.session_state["delete_exam_pending"] = current
                        st.warning("Clique novamente para confirmar exclusão.")

        st.markdown("---")
        uploaded_images: list = []
        selected_preview = st.session_state.get("selected_gallery_paths", [])
        existing_selected_preview = [path for path in selected_preview if Path(path).exists()]
        if existing_selected_preview:
            st.markdown("**Imagens selecionadas para o PDF**")
            for path in existing_selected_preview:
                st.image(path, use_container_width=True)
                st.caption(get_image_caption(Path(path), exam_id=st.session_state.get("current_exam_id")))
        elif selected_preview:
            st.warning("Algumas imagens selecionadas não existem mais. Atualize a seleção na aba Imagens.")

    pdf_preview_exam_id = st.session_state.get("pdf_preview_exam_id")
    if pdf_preview_exam_id:
        pdf_path = Path("saved_reports") / f"exam_{pdf_preview_exam_id}.pdf"
        st.subheader(f"PDF salvo do exame #{pdf_preview_exam_id}")
        if pdf_path.exists():
            pdf_bytes = pdf_path.read_bytes()
            encoded = base64.b64encode(pdf_bytes).decode("ascii")
            st.download_button(
                label="Baixar PDF salvo",
                data=pdf_bytes,
                file_name=pdf_path.name,
                mime="application/pdf",
                use_container_width=False,
            )
            st.markdown(
                f'<iframe src="data:application/pdf;base64,{encoded}" width="100%" height="900" style="border:1px solid #444;border-radius:8px;"></iframe>',
                unsafe_allow_html=True,
            )
        else:
            st.warning(f"PDF do exame #{pdf_preview_exam_id} ainda não foi salvo.")
        if st.button("Retornar ao início", use_container_width=False):
            st.session_state["pdf_preview_exam_id"] = None
            st.rerun()
        return

    current_exam = get_exam(st.session_state["current_exam_id"]) if st.session_state.get("current_exam_id") else None
    if current_exam:
        st.success(
            f"Exame ativo #{current_exam['id']} • Paciente: {current_exam['patient_name']} • "
            f"Data: {_to_br_date(current_exam['exam_date'])} {current_exam['exam_time']}"
        )
        with st.expander("Editar dados do exame ativo"):
            new_doctor = st.text_input("Médico solicitante (edição)", value=current_exam["doctor_name"], key="edit_doctor_name")
            new_convenio = st.text_input("Convênio (edição)", value=current_exam.get("convenio", ""), key="edit_convenio")
            new_executante = st.text_input("Médico executante (edição)", value=current_exam.get("executante", ""), key="edit_executante")
            footer_edit = st.text_area(
                "Dados do rodapé do médico executante",
                value=get_executante_footer(new_executante) or st.session_state.get("draft_footer_text", ""),
                key="edit_executante_footer",
                height=80,
            )
            new_exam_date = st.date_input(
                "Data do exame (edição)",
                value=datetime.strptime(current_exam["exam_date"], "%Y-%m-%d").date(),
                format="DD/MM/YYYY",
                key="edit_exam_date",
            )
            new_exam_time = st.time_input(
                "Hora do exame (edição)",
                value=datetime.strptime(current_exam["exam_time"], "%H:%M").time(),
                key="edit_exam_time",
            )
            if st.button("Salvar alterações do exame"):
                update_exam(
                    exam_id=current_exam["id"],
                    doctor_name=new_doctor,
                    exam_date_iso=_to_iso_date(new_exam_date),
                    exam_time_hhmm=new_exam_time.strftime("%H:%M"),
                    convenio=new_convenio,
                    executante=new_executante,
                )
                st.session_state["current_patient_convenio"] = new_convenio
                st.session_state["draft_executante_name"] = new_executante
                st.session_state["draft_footer_text"] = footer_edit
                upsert_executante_profile(new_executante, footer_edit)
                st.success("Dados do exame atualizados.")
                st.rerun()
    else:
        if st.session_state.get("current_patient_id"):
            st.info(
                f"Paciente ativo: {st.session_state.get('current_patient_name')} "
                f"(nasc. {_to_br_date(st.session_state.get('current_patient_birth_date')) if st.session_state.get('current_patient_birth_date') else '-'})"
            )
            st.caption("Gere e revise o laudo; depois clique em 'Salvar exame' para persistir o exame ativo sem perda de mídia.")
        else:
            st.warning("Nenhum paciente/exame ativo. Cadastre paciente ou abra exame para continuar.")

    tab_procedimento, tab_modelos = st.tabs(["Procedimento", "Gerenciar modelos"])
    with tab_modelos:
        render_template_manager(templates_data)

    with tab_procedimento:
        st.caption("Tela única do procedimento: capture imagens/filmagem e dite o laudo no mesmo fluxo.")
        render_auto_transcription()
        st.markdown("---")
        render_image_capture_tab(st.session_state.get("current_exam_id"))
        st.markdown("---")
        st.subheader("Narração/Transcrição")
        pending_text = st.session_state.get("pending_transcript_append", "")
        if pending_text:
            previous = st.session_state.get("transcript_input", "")
            st.session_state["transcript_input"] = f"{previous} {pending_text}".strip()
            st.session_state["pending_transcript_append"] = ""
        st.text_area("Cole aqui a transcrição do áudio (ou narração convertida):", height=220, key="transcript_input")

        can_generate = bool(st.session_state.get("transcript_input", "").strip())
        if st.button("Gerar laudo sugerido", disabled=not can_generate):
            selected_gallery_items = load_selected_images_with_captions(
                st.session_state.get("selected_gallery_paths", []),
                exam_id=st.session_state.get("current_exam_id"),
            )
            gallery_bytes = [b for b, _ in selected_gallery_items]
            gallery_captions = [c for _, c in selected_gallery_items]
            manual_captions = [f"imagem enviada {idx + 1}" for idx in range(len(uploaded_images))]
            birth_iso = current_exam["birth_date"] if current_exam else st.session_state.get("current_patient_birth_date", "")
            birth_date = datetime.strptime(birth_iso, "%Y-%m-%d").date() if birth_iso else date.today()
            paciente_nome = current_exam["patient_name"] if current_exam else st.session_state.get("current_patient_name", "")
            medico_nome = current_exam["doctor_name"] if current_exam else st.session_state.get("draft_doctor_name", "Dr(a).")
            sexo_nome = current_exam["sexo"] if current_exam else st.session_state.get("current_patient_sexo", "")
            convenio_nome = current_exam["convenio"] if current_exam else st.session_state.get("current_patient_convenio", "")
            executante_nome = current_exam.get("executante", "") if current_exam else st.session_state.get("draft_executante_name", "Dr(a).")
            footer_text = get_executante_footer(executante_nome) or st.session_state.get("draft_footer_text", "")
            data_exam_iso = current_exam["exam_date"] if current_exam else _to_iso_date(st.session_state.get("draft_exam_date", date.today()))
            hora_exam = current_exam["exam_time"] if current_exam else st.session_state.get("draft_exam_time", datetime.now().time()).strftime("%H:%M")
            report = st.session_state.get("report")
            if report is None:
                report = ReportData(
                    paciente=paciente_nome,
                    medico=medico_nome,
                    sexo=sexo_nome,
                    idade=str(max(calculate_age(_to_iso_date(birth_date)), 0)),
                    data_exame=_to_br_date(data_exam_iso),
                    hora_exame=hora_exam,
                    convenio=convenio_nome,
                    medico_executante=executante_nome,
                    footer_text=footer_text,
                    image_bytes=gallery_bytes + [img.getvalue() for img in uploaded_images],
                    image_captions=gallery_captions + manual_captions,
                )
            else:
                report.paciente = paciente_nome
                report.medico = medico_nome
                report.sexo = sexo_nome
                report.idade = str(max(calculate_age(_to_iso_date(birth_date)), 0))
                report.data_exame = _to_br_date(data_exam_iso)
                report.hora_exame = hora_exam
                report.convenio = convenio_nome
                report.medico_executante = executante_nome
                report.footer_text = footer_text
                report.image_bytes = gallery_bytes + [img.getvalue() for img in uploaded_images]
                report.image_captions = gallery_captions + manual_captions

            rendered_sections = engine.render_from_transcript(st.session_state["transcript_input"])
            last_auto_sections = st.session_state.get("last_auto_sections", {})
            report.ensure_sections()
            for section, new_text in rendered_sections.items():
                current_text = report.secoes.get(section, "")
                previous_auto = str(last_auto_sections.get(section, ""))
                should_update = (not str(current_text).strip()) or (str(current_text).strip() == previous_auto.strip())
                if should_update and str(new_text).strip():
                    report.secoes[section] = new_text
                    st.session_state[f"sec_{section}"] = new_text
            report.ensure_sections()
            st.session_state["last_auto_sections"] = dict(rendered_sections)
            st.session_state["report"] = report

        report: ReportData | None = st.session_state.get("report")
        if report:
            selected_gallery_items_live = load_selected_images_with_captions(
                st.session_state.get("selected_gallery_paths", []),
                exam_id=st.session_state.get("current_exam_id"),
            )
            report.image_bytes = [b for b, _ in selected_gallery_items_live]
            report.image_captions = [c for _, c in selected_gallery_items_live]
            st.subheader("Revisão por seção")
            pending_updates = st.session_state.get("pending_section_updates", {})
            if pending_updates:
                for section, reviewed in pending_updates.items():
                    report.secoes[section] = reviewed
                    st.session_state[f"sec_{section}"] = reviewed
                st.session_state["pending_section_updates"] = {}
            for section, text in report.secoes.items():
                report.secoes[section] = st.text_area(section.replace("_", " ").title(), value=text, key=f"sec_{section}")
                if st.button("Revisar texto", key=f"review_{section}"):
                    before_text = report.secoes[section]
                    reviewed = _apply_models_for_single_section(
                        engine=engine,
                        section_id=section,
                        input_text=report.secoes[section],
                        current_text=report.secoes[section],
                    )
                    report.secoes[section] = reviewed
                    st.session_state["pending_section_updates"] = {section: reviewed}
                    if reviewed != before_text:
                        st.success(f"Campo {section.replace('_', ' ')} revisado com modelos desta seção.")
                    else:
                        st.warning("Nenhum modelo aplicável encontrado para o texto informado nesta seção.")
                    st.rerun()

            pdf_data = generate_pdf(report)
            st.download_button(
                label="Baixar PDF",
                data=pdf_data,
                file_name=f"laudo_colonoscopia_{report.paciente or 'paciente'}.pdf",
                mime="application/pdf",
            )
            if st.button("Salvar exame", disabled=not bool(st.session_state.get("current_patient_id"))):
                active_exam_id = st.session_state.get("current_exam_id")
                if active_exam_id:
                    update_exam(
                        exam_id=int(active_exam_id),
                        doctor_name=st.session_state.get("draft_doctor_name", report.medico or "Dr(a)."),
                        exam_date_iso=_to_iso_date(st.session_state.get("draft_exam_date", date.today())),
                        exam_time_hhmm=st.session_state.get("draft_exam_time", datetime.now().time()).strftime("%H:%M"),
                        convenio=st.session_state.get("current_patient_convenio", ""),
                        executante=st.session_state.get("draft_executante_name", report.medico_executante or "Dr(a)."),
                    )
                    exam = get_exam(int(active_exam_id))
                    if not exam:
                        st.error("Não foi possível localizar o exame ativo para salvar.")
                        st.stop()
                    exam_id = int(active_exam_id)
                else:
                    created = create_exam(
                        patient_id=int(st.session_state["current_patient_id"]),
                        doctor_name=st.session_state.get("draft_doctor_name", report.medico or "Dr(a)."),
                        exam_date_iso=_to_iso_date(st.session_state.get("draft_exam_date", date.today())),
                        exam_time_hhmm=st.session_state.get("draft_exam_time", datetime.now().time()).strftime("%H:%M"),
                        convenio=st.session_state.get("current_patient_convenio", ""),
                        executante=st.session_state.get("draft_executante_name", report.medico_executante or "Dr(a)."),
                    )
                    exam_id = created.id
                moved_images = reassign_images_to_exam(st.session_state.get("selected_gallery_paths", []), exam_id)
                for image_path in moved_images:
                    add_exam_image(exam_id, str(image_path), get_image_caption(image_path, exam_id=exam_id))
                draft_video_dir = Path("captured_videos") / "unassigned"
                exam_video_dir = Path("captured_videos") / f"exam_{exam_id}"
                exam_video_dir.mkdir(parents=True, exist_ok=True)
                if draft_video_dir.exists():
                    for draft_video in sorted(draft_video_dir.glob("*")):
                        if draft_video.suffix.lower() not in {".mp4", ".webm", ".mov"}:
                            continue
                        target = exam_video_dir / draft_video.name
                        if target.exists():
                            target = exam_video_dir / f"{target.stem}_{datetime.now().strftime('%H%M%S%f')}{target.suffix}"
                        shutil.move(str(draft_video), str(target))
                        add_exam_video(exam_id, str(target))
                save_exam_report(
                    exam_id=exam_id,
                    transcript=st.session_state.get("transcript_input", ""),
                    sections=report.secoes,
                )
                reports_dir = Path("saved_reports")
                reports_dir.mkdir(parents=True, exist_ok=True)
                (reports_dir / f"exam_{exam_id}.pdf").write_bytes(pdf_data)
                st.session_state["current_exam_id"] = exam_id
                existing_selected = [p for p in st.session_state.get("selected_gallery_paths", []) if Path(p).exists()]
                st.session_state["selected_gallery_paths"] = sorted(set(existing_selected + [str(p) for p in moved_images]), reverse=True)
                st.success(f"Exame #{exam_id} salvo com sucesso para o paciente {report.paciente}.")


if __name__ == "__main__":
    render_app()
