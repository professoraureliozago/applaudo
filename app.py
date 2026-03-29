from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from datetime import date, datetime
from math import ceil
from pathlib import Path
from typing import Any

import streamlit as st
from streamlit.runtime.scriptrunner import get_script_run_ctx

from src.laudo_app import ReportData, TemplateEngine
from src.laudo_app.database import (
    add_exam_image,
    add_exam_video,
    calculate_age,
    create_exam,
    create_or_get_patient,
    delete_exam,
    ensure_db,
    get_exam,
    list_exams,
    search_patients_by_name,
    update_exam,
)
from src.laudo_app.image_store import (
    get_image_caption,
    infer_caption_from_text,
    list_captured_images,
    load_selected_images_with_captions,
    save_captured_image,
)
from src.laudo_app.live_commands import apply_live_command
from src.laudo_app.pdf_generator import generate_pdf
from src.laudo_app.template_loader import load_template_config
from src.laudo_app.transcriber import transcribe_audio_bytes
from src.laudo_app.webrtc_click_component import render_webrtc_click_snapshot

TEMPLATES_PATH = Path("templates/colonoscopia_templates.json")


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
    return load_template_config(str(TEMPLATES_PATH))


def save_templates(data: dict[str, Any]) -> None:
    with TEMPLATES_PATH.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def _to_iso_date(d: date) -> str:
    return d.strftime("%Y-%m-%d")


def _to_br_date(iso_date: str) -> str:
    return datetime.strptime(iso_date, "%Y-%m-%d").strftime("%d/%m/%Y")


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

    with st.form("model_form"):
        st.markdown(f"### {form_title}")
        model_name = st.text_input("Nome do modelo", value=model_for_form.get("name", ""))
        keywords_csv = st.text_input("Palavras-chave (separadas por vírgula)", value=", ".join(model_for_form.get("keywords", [])))
        model_text = st.text_area("Texto do modelo", value=model_for_form.get("text", ""))
        col_a, col_b = st.columns(2)
        submitted = col_a.form_submit_button(submit_label)
        cancel_edit = col_b.form_submit_button("Cancelar edição")

    if cancel_edit:
        st.session_state["editing_model"] = None
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


def _handle_mic_chunk(mic_audio, provider: str, local_model_size: str, openai_key: str, openai_model: str, force: bool = False) -> None:
    if not mic_audio:
        return

    audio_bytes = mic_audio.getvalue()
    chunk_hash = hashlib.md5(audio_bytes).hexdigest()
    if not force and chunk_hash == st.session_state.get("last_mic_chunk_hash"):
        return

    st.session_state["last_mic_chunk_hash"] = chunk_hash
    transcript = _transcribe_chunk(
        audio_bytes=audio_bytes,
        filename=mic_audio.name or "audio_live.wav",
        provider=provider,
        local_model_size=local_model_size,
        openai_key=openai_key,
        openai_model=openai_model,
    )
    if not transcript:
        st.session_state["last_voice_status"] = "Falha na transcrição do trecho."
        return

    st.session_state["last_voice_transcript"] = transcript
    result = apply_live_command(
        transcript_chunk=transcript,
        recording_active=st.session_state["recording_active"],
        current_draft=st.session_state.get("transcript_input", ""),
    )
    st.session_state["recording_active"] = result.recording_active
    st.session_state["transcript_input"] = result.updated_draft
    st.session_state["last_voice_status"] = result.status_message


def render_auto_transcription() -> None:
    st.markdown("### Transcrição automática de áudio")
    provider, local_model_size, openai_key, openai_model = _get_transcription_settings()

    status = "ATIVA" if st.session_state["recording_active"] else "PAUSADA"
    st.info(f"Captura por comando de voz: **{status}**. Diga 'gravar'/'iniciar' para ativar e 'parar'/'pausar' para pausar.")
    st.caption("A captura física do microfone no navegador ainda exige clicar para gravar; os comandos de voz controlam a anexação ao laudo após transcrição do trecho.")

    st.caption("Fluxo recomendado: 1) grave um trecho no microfone; 2) clique em 'Processar trecho do microfone agora'; 3) veja a última transcrição e status abaixo.")

    b1, b2 = st.columns(2)
    if b1.button("Ativar captura"):  # fallback manual
        st.session_state["recording_active"] = True
    if b2.button("Pausar captura"):  # fallback manual
        st.session_state["recording_active"] = False

    st.markdown("**Modo 1: Microfone em tempo real por trechos (automático e cumulativo)**")
    mic_audio = st.audio_input("Gravar trecho do exame", key="audio_input_live")
    auto_mode = st.checkbox("Processar automaticamente novos trechos", value=True)

    c_proc1, c_proc2 = st.columns(2)
    manual_process = c_proc1.button("Processar trecho do microfone agora")
    if c_proc2.button("Diagnóstico de comando"):
        if st.session_state.get("last_voice_transcript"):
            st.write(f"Última transcrição: {st.session_state['last_voice_transcript']}")
            st.write(f"Status: {st.session_state.get('last_voice_status', '')}")
        else:
            st.write("Ainda não há transcrição de trecho de microfone.")

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

    # processamento automático ao detectar novo trecho
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

    st.markdown("#### Captura padrão")
    camera_photo = st.camera_input("Visualização da captura (clique para tirar foto)", key="camera_live")
    if st.button("Salvar foto capturada"):
        if not exam_id:
            st.warning("Crie/abra um exame antes de salvar imagens.")
            return
        if not camera_photo:
            st.warning("Capture uma imagem antes de salvar.")
        else:
            suffix = ".jpg"
            if camera_photo.type == "image/png":
                suffix = ".png"
            context_text = st.session_state.get("transcript_input", "") or st.session_state.get("last_voice_transcript", "")
            auto_caption = infer_caption_from_text(context_text)
            saved = save_captured_image(camera_photo.getvalue(), suffix=suffix, caption=auto_caption, exam_id=exam_id)
            add_exam_image(exam_id, str(saved), auto_caption)
            st.success(f"Imagem salva: {saved.name} ({auto_caption})")

    st.markdown("#### Captura WebRTC custom por clique no frame")
    st.caption("Habilite o modo custom para exibir um frame de vídeo contínuo. Clique no próprio frame para capturar a imagem.")
    use_webrtc_custom = st.toggle("Habilitar captura WebRTC custom", value=False)
    if use_webrtc_custom:
        if not exam_id:
            st.warning("Crie/abra um exame antes de usar snapshot WebRTC.")
        else:
            snapshot_bytes = render_webrtc_click_snapshot(key="exam-webrtc-click", width=960, height=540)
            if snapshot_bytes:
                context_text = st.session_state.get("transcript_input", "") or st.session_state.get("last_voice_transcript", "")
                auto_caption = infer_caption_from_text(context_text)
                saved = save_captured_image(snapshot_bytes, suffix=".jpg", caption=auto_caption, exam_id=exam_id)
                add_exam_image(exam_id, str(saved), auto_caption)
                st.success(f"Snapshot salvo por clique: {saved.name} ({auto_caption})")

    st.markdown("#### Filmagem do exame")
    st.caption("Para maior segurança/compatibilidade, a filmagem pode ser anexada por upload de arquivo.")
    video_file = st.file_uploader("Anexar filmagem (mp4/webm/mov)", type=["mp4", "webm", "mov"], key="exam_video_upload")
    if st.button("Salvar filmagem do exame"):
        if not exam_id:
            st.warning("Crie/abra um exame antes de salvar filmagem.")
        elif not video_file:
            st.warning("Selecione um arquivo de vídeo para anexar.")
        else:
            video_dir = Path("captured_videos") / f"exam_{exam_id}"
            video_dir.mkdir(parents=True, exist_ok=True)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
            suffix = Path(video_file.name).suffix or ".mp4"
            video_path = video_dir / f"filmagem_{timestamp}{suffix}"
            video_path.write_bytes(video_file.getvalue())
            add_exam_video(exam_id, str(video_path))
            st.success(f"Filmagem salva: {video_path.name}")

    st.markdown("---")
    st.markdown("### Galeria de imagens salvas")
    images = list_captured_images(exam_id=exam_id)

    if not images:
        st.info("Nenhuma imagem salva ainda.")
        return

    st.caption("Marque as imagens que deseja anexar ao laudo.")
    cols = st.columns(4)
    selected_paths: list[str] = []

    for idx, img in enumerate(images):
        col = cols[idx % 4]
        col.image(str(img), use_container_width=True)
        col.caption(get_image_caption(img, exam_id=exam_id))
        checked = col.checkbox(f"Selecionar {img.name}", key=f"sel_{exam_id}_{img.name}")
        if checked:
            selected_paths.append(str(img))

    st.session_state["selected_gallery_paths"] = selected_paths

    current = st.session_state.get("selected_gallery_paths", [])
    if current:
        st.info(f"Imagens atualmente marcadas para o PDF: {len(current)} (aprox. {ceil(len(current) / 4)} página(s) de imagens)")
        st.markdown("#### Miniaturas selecionadas para PDF")
        selected_cols = st.columns(4)
        for idx, path in enumerate(current):
            col = selected_cols[idx % 4]
            col.image(path, use_container_width=True)
            col.caption(get_image_caption(Path(path), exam_id=exam_id))


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

    engine = TemplateEngine(config=templates_data)

    st.session_state.setdefault("transcript_input", "")
    st.session_state.setdefault("recording_active", False)
    st.session_state.setdefault("last_mic_chunk_hash", None)
    st.session_state.setdefault("last_voice_transcript", "")
    st.session_state.setdefault("last_voice_status", "")
    st.session_state.setdefault("selected_gallery_paths", [])
    st.session_state.setdefault("current_exam_id", None)
    st.session_state.setdefault("pending_transcript_append", "")

    with st.sidebar:
        st.header("Exames")
        flow = st.radio("Fluxo", ["Novo exame", "Abrir exame existente"], horizontal=True)

        if flow == "Novo exame":
            st.markdown("### Cadastro do paciente e exame")
            patient_name = st.text_input("Nome do Paciente")
            sexo = st.selectbox("Sexo", ["", "Feminino", "Masculino"])
            nascimento = st.date_input("Data de Nascimento", value=date(1980, 1, 1), format="DD/MM/YYYY")
            idade_calc = calculate_age(_to_iso_date(nascimento))
            st.text_input("Idade (automática)", value=str(max(idade_calc, 0)), disabled=True)
            medico = st.text_input("Nome do Médico Solicitante", value="Dr(a).")
            convenio = st.text_input("Convênio")
            now = datetime.now()
            data_exame_dt = st.date_input("Data do Exame", value=now.date(), format="DD/MM/YYYY")
            hora_exame_dt = st.time_input("Hora do exame", value=now.time().replace(second=0, microsecond=0))

            duplicate = None
            if patient_name.strip():
                candidates = search_patients_by_name(patient_name.strip())
                duplicate = next(
                    (p for p in candidates if p.normalized_name == " ".join(patient_name.strip().lower().split()) and p.birth_date == _to_iso_date(nascimento)),
                    None,
                )
            if duplicate:
                st.warning("Paciente já cadastrado com este nome e data de nascimento.")
                if st.checkbox("Completar com dados existentes", key="use_existing_patient"):
                    sexo = duplicate.sexo or sexo
                    convenio = duplicate.convenio or convenio
                    st.info(f"Dados reaproveitados para {duplicate.name}.")

            if st.button("Salvar novo exame"):
                if not patient_name.strip():
                    st.error("Nome do paciente é obrigatório.")
                else:
                    patient, _ = create_or_get_patient(
                        name=patient_name.strip(),
                        sexo=sexo,
                        birth_date_iso=_to_iso_date(nascimento),
                        convenio=convenio,
                    )
                    exam = create_exam(
                        patient_id=patient.id,
                        doctor_name=medico,
                        exam_date_iso=_to_iso_date(data_exame_dt),
                        exam_time_hhmm=hora_exame_dt.strftime("%H:%M"),
                    )
                    st.session_state["current_exam_id"] = exam.id
                    st.session_state["selected_gallery_paths"] = []
                    st.success(f"Exame #{exam.id} criado para {patient.name}.")

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

            exams = list_exams(patient_id=patient_id_for_exams) if patient_id_for_exams else list_exams()
            if not exams:
                st.info("Nenhum exame salvo encontrado.")
            else:
                exam_labels = [
                    f"#{e['id']} | {e['patient_name']} | {_to_br_date(e['exam_date'])} {e['exam_time']}"
                    for e in exams
                ]
                selected_exam_label = st.selectbox("Exames salvos", exam_labels)
                selected_exam = exams[exam_labels.index(selected_exam_label)]

                c_open, c_delete = st.columns(2)
                if c_open.button("Abrir exame"):
                    st.session_state["current_exam_id"] = selected_exam["id"]
                    st.session_state["selected_gallery_paths"] = []
                    st.success(f"Exame #{selected_exam['id']} carregado.")
                if c_delete.button("Excluir exame (2 cliques)"):
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
        st.markdown("**Imagens enviadas manualmente para o PDF (sem limite fixo)**")
        uploaded_images = st.file_uploader(
            "Envie uma ou mais imagens",
            type=["jpg", "jpeg", "png"],
            accept_multiple_files=True,
            key="pdf_imgs_multi",
        )

    current_exam = get_exam(st.session_state["current_exam_id"]) if st.session_state.get("current_exam_id") else None
    if current_exam:
        st.success(
            f"Exame ativo #{current_exam['id']} • Paciente: {current_exam['patient_name']} • "
            f"Data: {_to_br_date(current_exam['exam_date'])} {current_exam['exam_time']}"
        )
        with st.expander("Editar dados do exame ativo"):
            new_doctor = st.text_input("Médico solicitante (edição)", value=current_exam["doctor_name"], key="edit_doctor_name")
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
                )
                st.success("Dados do exame atualizados.")
                st.rerun()
    else:
        st.warning("Nenhum exame ativo. Cadastre ou abra um exame para continuar.")

    tab_gerar, tab_modelos, tab_imagens = st.tabs(["Gerar laudo", "Gerenciar modelos", "Imagens"])
    with tab_modelos:
        render_template_manager(templates_data)
    with tab_imagens:
        render_image_capture_tab(st.session_state.get("current_exam_id"))

    with tab_gerar:
        render_auto_transcription()
        st.subheader("Narração/Transcrição")
        pending_text = st.session_state.get("pending_transcript_append", "")
        if pending_text:
            previous = st.session_state.get("transcript_input", "")
            st.session_state["transcript_input"] = f"{previous} {pending_text}".strip()
            st.session_state["pending_transcript_append"] = ""
        st.text_area("Cole aqui a transcrição do áudio (ou narração convertida):", height=220, key="transcript_input")

        if st.button("Gerar laudo sugerido", disabled=current_exam is None):
            selected_gallery_items = load_selected_images_with_captions(
                st.session_state.get("selected_gallery_paths", []),
                exam_id=st.session_state.get("current_exam_id"),
            )
            gallery_bytes = [b for b, _ in selected_gallery_items]
            gallery_captions = [c for _, c in selected_gallery_items]
            manual_captions = [f"imagem enviada {idx + 1}" for idx in range(len(uploaded_images))]
            birth_date = datetime.strptime(current_exam["birth_date"], "%Y-%m-%d").date() if current_exam else date.today()
            report = ReportData(
                paciente=current_exam["patient_name"] if current_exam else "",
                medico=current_exam["doctor_name"] if current_exam else "",
                sexo=current_exam["sexo"] if current_exam else "",
                idade=str(max(calculate_age(_to_iso_date(birth_date)), 0)),
                data_exame=_to_br_date(current_exam["exam_date"]) if current_exam else "",
                hora_exame=current_exam["exam_time"] if current_exam else "",
                convenio=current_exam["convenio"] if current_exam else "",
                image_bytes=gallery_bytes + [img.getvalue() for img in uploaded_images],
                image_captions=gallery_captions + manual_captions,
            )
            report.secoes = engine.render_from_transcript(st.session_state["transcript_input"])
            report.ensure_sections()
            st.session_state["report"] = report

        report: ReportData | None = st.session_state.get("report")
        if report:
            st.subheader("Revisão por seção")
            st.caption("Você pode continuar sugerindo preenchimento por palavras-chave digitadas abaixo.")
            text_keywords = st.text_input("Complemento por palavras-chave (texto livre)")
            if st.button("Aplicar palavras-chave digitadas"):
                additions = engine.render_from_transcript(text_keywords)
                for section, generated in additions.items():
                    if generated.strip():
                        report.secoes[section] = generated
                st.session_state["pending_transcript_append"] = text_keywords.strip()
                st.success("Complemento aplicado nas seções reconhecidas.")
                st.rerun()
            for section, text in report.secoes.items():
                report.secoes[section] = st.text_area(section.replace("_", " ").title(), value=text, key=f"sec_{section}")

            pdf_data = generate_pdf(report)
            st.download_button(
                label="Baixar PDF",
                data=pdf_data,
                file_name=f"laudo_colonoscopia_{report.paciente or 'paciente'}.pdf",
                mime="application/pdf",
            )


if __name__ == "__main__":
    ensure_streamlit_context()

render_app()
