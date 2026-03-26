from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

import streamlit as st
from streamlit.runtime.scriptrunner import get_script_run_ctx

from src.laudo_app import ReportData, TemplateEngine
from src.laudo_app.pdf_generator import generate_pdf

TEMPLATES_PATH = Path("templates/colonoscopia_templates.json")


def ensure_streamlit_context() -> None:
    """If the user runs `python app.py`, relaunch with `streamlit run`."""
    if get_script_run_ctx() is not None:
        return

    if os.environ.get("LAUDO_STREAMLIT_BOOTSTRAPPED") == "1":
        return

    env = os.environ.copy()
    env["LAUDO_STREAMLIT_BOOTSTRAPPED"] = "1"
    cmd = [sys.executable, "-m", "streamlit", "run", os.path.abspath(__file__)]
    raise SystemExit(subprocess.call(cmd, env=env))


def load_templates() -> dict[str, Any]:
    with TEMPLATES_PATH.open("r", encoding="utf-8") as f:
        return json.load(f)


def save_templates(data: dict[str, Any]) -> None:
    with TEMPLATES_PATH.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def render_template_manager(templates_data: dict[str, Any]) -> None:
    st.subheader("Modelos (templates) por campo")
    st.caption("Aqui você cria/ajusta os modelos que serão aplicados por palavras-chave da narração.")

    sections = templates_data.get("sections", [])
    section_ids = [s.get("id", "") for s in sections]

    selected_id = st.selectbox("Campo do laudo", options=section_ids, key="tpl_section")
    selected_section = next((s for s in sections if s.get("id") == selected_id), None)
    if not selected_section:
        st.warning("Seção não encontrada no arquivo de templates.")
        return

    st.markdown("**Modelos atuais deste campo**")
    models = selected_section.get("models", [])
    if models:
        for idx, model in enumerate(models, start=1):
            st.write(f"{idx}. **{model.get('name', 'sem_nome')}**")
            st.write(f"   - Keywords: {', '.join(model.get('keywords', []))}")
            st.write(f"   - Texto: {model.get('text', '')}")
    else:
        st.info("Nenhum modelo cadastrado nesta seção ainda.")

    with st.form("add_model_form"):
        st.markdown("### Adicionar novo modelo")
        model_name = st.text_input("Nome do modelo (ex.: polipo_sessil)")
        keywords_csv = st.text_input("Palavras-chave (separadas por vírgula)")
        model_text = st.text_area(
            "Texto do modelo",
            placeholder="Ex.: Presença de pólipo séssil de {tamanho_cm} cm em cólon descendente...",
        )
        submitted = st.form_submit_button("Salvar modelo")

    if submitted:
        keywords = [k.strip() for k in keywords_csv.split(",") if k.strip()]
        if not model_name.strip() or not model_text.strip() or not keywords:
            st.error("Preencha nome, palavras-chave e texto do modelo.")
        else:
            selected_section.setdefault("models", []).append(
                {
                    "name": model_name.strip(),
                    "keywords": keywords,
                    "text": model_text.strip(),
                }
            )
            save_templates(templates_data)
            st.success("Modelo salvo com sucesso. Ele já será usado na próxima geração de laudo.")
            st.rerun()

    with st.expander("Edição avançada do JSON de templates"):
        json_text = st.text_area(
            "JSON completo",
            value=json.dumps(templates_data, ensure_ascii=False, indent=2),
            height=280,
        )
        if st.button("Salvar JSON completo"):
            try:
                parsed = json.loads(json_text)
                save_templates(parsed)
                st.success("Arquivo de templates atualizado.")
                st.rerun()
            except json.JSONDecodeError as exc:
                st.error(f"JSON inválido: {exc}")


def render_app() -> None:
    st.set_page_config(page_title="Laudo Colonoscopia por Áudio", layout="wide")

    st.title("Laudo de Colonoscopia (MVP)")
    st.caption("Protótipo: transcrição/narração -> preenchimento por templates -> PDF")

    templates_data = load_templates()
    engine = TemplateEngine(str(TEMPLATES_PATH))

    with st.sidebar:
        st.header("Dados do exame")
        paciente = st.text_input("Paciente")
        medico = st.text_input("Médico", value="Dr(a).")
        sexo = st.selectbox("Sexo", ["", "Feminino", "Masculino"])
        idade = st.text_input("Idade")
        convenio = st.text_input("Convênio")
        now = datetime.now()
        data_exame = st.date_input("Data", value=now.date()).strftime("%d/%m/%Y")
        hora_exame = st.time_input("Hora", value=now.time().replace(second=0, microsecond=0)).strftime("%H:%M")

    tab_gerar, tab_modelos = st.tabs(["Gerar laudo", "Gerenciar modelos"])

    with tab_modelos:
        render_template_manager(templates_data)

    with tab_gerar:
        st.subheader("Narração/Transcrição")
        transcript = st.text_area(
            "Cole aqui a transcrição do áudio (ou narração convertida):",
            height=220,
            placeholder="Ex.: Reto com mucosa normal. No cólon descendente, pólipo séssil de 1 cm...",
        )

        if st.button("Gerar laudo sugerido"):
            report = ReportData(
                paciente=paciente,
                medico=medico,
                sexo=sexo,
                idade=idade,
                data_exame=data_exame,
                hora_exame=hora_exame,
                convenio=convenio,
            )
            report.secoes = engine.render_from_transcript(transcript)
            report.ensure_sections()
            st.session_state["report"] = report

        report: ReportData | None = st.session_state.get("report")
        if report:
            st.subheader("Revisão por seção")
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
