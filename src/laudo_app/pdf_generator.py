from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

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
    "observacoes": "Obs.",
}


def _normalize_text_for_pdf(text: str) -> str:
    return text.replace("\n", "<br/>")


def generate_pdf(report: ReportData) -> bytes:
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        topMargin=12 * mm,
        bottomMargin=12 * mm,
        leftMargin=14 * mm,
        rightMargin=14 * mm,
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "ClinicTitle",
        parent=styles["Title"],
        alignment=1,
        textColor=colors.HexColor("#d26f2a"),
        fontSize=22,
        leading=24,
    )
    subtitle_style = ParagraphStyle("Subtitle", parent=styles["Heading3"], alignment=1, fontSize=12)
    laudo_title_style = ParagraphStyle("LaudoTitle", parent=styles["Heading3"], alignment=1)
    section_style = ParagraphStyle("Section", parent=styles["Heading4"], fontSize=11, leading=13, spaceAfter=2)
    body_style = ParagraphStyle("Body", parent=styles["Normal"], fontSize=10.5, leading=13)
    small_style = ParagraphStyle("Small", parent=styles["Normal"], fontSize=9, textColor=colors.grey)

    story = []

    story.append(Paragraph("Videocolonoscopia", title_style))
    story.append(Paragraph("Dr. Aurélio Fabiano Ribeiro Zago", subtitle_style))
    story.append(Spacer(1, 4 * mm))
    story.append(Paragraph("<u><b>Laudo de Videocolonoscopia</b></u>", laudo_title_style))
    story.append(Spacer(1, 4 * mm))

    header_data = [
        [
            Paragraph(f"<b>Paciente:</b> {report.paciente or '-'}", body_style),
            Paragraph(f"<b>Sexo:</b> {report.sexo or '-'}", body_style),
            Paragraph(f"<b>Idade:</b> {report.idade or '-'}", body_style),
        ],
        [
            Paragraph(f"<b>Médico solicitante:</b> {report.medico or '-'}", body_style),
            Paragraph(f"<b>Data:</b> {report.data_exame or '-'}", body_style),
            Paragraph(f"<b>Hora:</b> {report.hora_exame or '-'}", body_style),
        ],
        [
            Paragraph("<b>Aparelho:</b> Pentax", body_style),
            Paragraph(f"<b>Convênio:</b> {report.convenio or '-'}", body_style),
            Paragraph("", body_style),
        ],
    ]

    header_table = Table(header_data, colWidths=[96 * mm, 40 * mm, 30 * mm])
    header_table.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    story.append(header_table)
    story.append(Spacer(1, 3 * mm))

    line = Table([[" "]], colWidths=[170 * mm], rowHeights=[0.6 * mm])
    line.setStyle(TableStyle([("BACKGROUND", (0, 0), (0, 0), colors.black)]))
    story.append(line)
    story.append(Spacer(1, 3 * mm))

    for key, label in SECTION_LABELS.items():
        text = report.secoes.get(key, "") or "Não informado."
        story.append(Paragraph(f"<b>{label}</b>", section_style))
        story.append(Paragraph(_normalize_text_for_pdf(text), body_style))
        story.append(Spacer(1, 2.5 * mm))

    story.append(Spacer(1, 5 * mm))
    story.append(Paragraph("Avenida Santos Dumont 2335 - MG - Telefone: 3322 4111", small_style))

    doc.build(story)
    return buffer.getvalue()
