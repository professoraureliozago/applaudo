from io import BytesIO

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

from .models import ReportData


SECTION_LABELS = {
    "preparo_paciente": "Preparo do paciente",
    "duracao": "Duração",
    "altura_atingida": "Altura atingida",
    "reto": "Reto",
    "colon_sigmoide": "Cólon sigmoide",
    "colon_descendente": "Cólon descendente",
    "angulo_esplenico": "Ângulo esplênico",
    "colon_transverso": "Cólon transverso",
    "angulo_hepatico": "Ângulo hepático",
    "colon_ascendente": "Cólon ascendente",
    "ceco": "Ceco",
    "conclusao": "Conclusão",
    "observacoes": "Observações",
}


def generate_pdf(report: ReportData) -> bytes:
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4)
    styles = getSampleStyleSheet()
    story = []

    story.append(Paragraph("<b>Laudo de Videocolonoscopia</b>", styles["Title"]))
    story.append(Spacer(1, 12))

    header = (
        f"<b>Paciente:</b> {report.paciente} &nbsp;&nbsp; "
        f"<b>Médico:</b> {report.medico} &nbsp;&nbsp; "
        f"<b>Data:</b> {report.data_exame} {report.hora_exame}"
    )
    story.append(Paragraph(header, styles["Normal"]))
    story.append(Spacer(1, 12))

    for key, label in SECTION_LABELS.items():
        text = report.secoes.get(key, "") or "Não informado."
        story.append(Paragraph(f"<b>{label}</b>", styles["Heading4"]))
        story.append(Paragraph(text, styles["Normal"]))
        story.append(Spacer(1, 8))

    doc.build(story)
    return buffer.getvalue()
