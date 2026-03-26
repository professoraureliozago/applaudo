from datetime import datetime

import streamlit as st

from src.laudo_app import ReportData, TemplateEngine
from src.laudo_app.pdf_generator import generate_pdf

st.set_page_config(page_title="Laudo Colonoscopia por Áudio", layout="wide")

st.title("Laudo de Colonoscopia (MVP)")
st.caption("Protótipo: transcrição/narração -> preenchimento por templates -> PDF")

engine = TemplateEngine("templates/colonoscopia_templates.json")

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
