from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Image as RLImage
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from .models import ReportData


FIELD_ORDER = [
    ("indicacao", "Indicação"),
    ("preparo_paciente", "Preparo do paciente"),
    ("duracao", "Duração do exame"),
    ("altura_atingida", "Altura atingida"),
    ("reto", "Reto"),
    ("colon_sigmoide", "Cólon Sigmóide"),
    ("colon_descendente", "Cólon Descendente"),
    ("angulo_esplenico", "Ângulo Esplênico"),
    ("colon_transverso", "Cólon Transverso"),
    ("angulo_hepatico", "Ângulo Hepático"),
    ("colon_ascendente", "Cólon Ascendente"),
    ("ceco", "Ceco"),
    ("ileo_terminal", "Íleo Terminal"),
    ("conclusao", "Conclusão"),
    ("observacao_1", "Observação 1"),
    ("observacao_2", "Observação 2"),
]


def _normalize_text_for_pdf(text: str) -> str:
    return text.replace("\n", "<br/>")


def _has_meaningful_content(text: str) -> bool:
    return bool(text and text.strip())


def _build_image_panel(report: ReportData, body_style: ParagraphStyle) -> list:
    panel: list = []
    image_count = min(4, len(report.image_bytes))

    for i in range(4):
        if i < image_count:
            image = RLImage(BytesIO(report.image_bytes[i]), width=50 * mm, height=34 * mm)
            image.hAlign = "CENTER"
            panel.append(image)
        else:
            placeholder = Table(
                [[Paragraph(f"Imagem {i + 1}", body_style)]],
                colWidths=[50 * mm],
                rowHeights=[34 * mm],
            )
            placeholder.setStyle(
                TableStyle(
                    [
                        ("BOX", (0, 0), (-1, -1), 0.5, colors.grey),
                        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                        ("TEXTCOLOR", (0, 0), (-1, -1), colors.grey),
                    ]
                )
            )
            panel.append(placeholder)
        panel.append(Spacer(1, 2 * mm))

    return panel


def generate_pdf(report: ReportData) -> bytes:
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        topMargin=12 * mm,
        bottomMargin=10 * mm,
        leftMargin=12 * mm,
        rightMargin=12 * mm,
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
    subtitle_style = ParagraphStyle(
        "Subtitle",
        parent=styles["Heading3"],
        alignment=1,
        textColor=colors.HexColor("#d26f2a"),
        fontSize=13,
    )
    laudo_title_style = ParagraphStyle("LaudoTitle", parent=styles["Heading3"], alignment=1, fontSize=12)
    section_style = ParagraphStyle("Section", parent=styles["Heading4"], fontSize=10.5, leading=12, spaceAfter=1)
    body_style = ParagraphStyle("Body", parent=styles["Normal"], fontSize=9.5, leading=12)
    footer_style = ParagraphStyle("Footer", parent=styles["Normal"], alignment=1, fontSize=9, textColor=colors.HexColor("#d26f2a"))

    story = []

    story.append(Paragraph("Videocolonoscopia", title_style))
    story.append(Paragraph("Dr. Aurélio Fabiano Ribeiro Zago", subtitle_style))
    story.append(Spacer(1, 3 * mm))
    story.append(Paragraph("<u><b>Laudo de Videocolonoscopia</b></u>", laudo_title_style))
    story.append(Spacer(1, 3 * mm))

    header_data = [
        [
            Paragraph(f"<b>Paciente:</b> {report.paciente or '-'}", body_style),
            Paragraph(f"<b>Sexo:</b> {report.sexo or '-'}", body_style),
            Paragraph(f"<b>Idade:</b> {report.idade or '-'}", body_style),
        ],
        [
            Paragraph(f"<b>Médico Solicitante:</b> {report.medico or '-'}", body_style),
            Paragraph(f"<b>Data:</b> {report.data_exame or '-'}", body_style),
            Paragraph(f"<b>Hora:</b> {report.hora_exame or '-'}", body_style),
        ],
        [
            Paragraph(f"<b>Convênio:</b> {report.convenio or '-'}", body_style),
            Paragraph("", body_style),
            Paragraph("", body_style),
        ],
    ]

    header_table = Table(header_data, colWidths=[104 * mm, 34 * mm, 28 * mm])
    header_table.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("BOTTOMPADDING", (0, 0), (-1, -1), 3)]))
    story.append(header_table)
    story.append(Spacer(1, 2 * mm))

    separator = Table([[" "]], colWidths=[184 * mm], rowHeights=[0.5 * mm])
    separator.setStyle(TableStyle([("BACKGROUND", (0, 0), (0, 0), colors.black)]))
    story.append(separator)
    story.append(Spacer(1, 2.5 * mm))

    left_column: list = []
    for key, label in FIELD_ORDER:
        raw_text = report.secoes.get(key, "")
        if not _has_meaningful_content(raw_text):
            continue
        left_column.append(Paragraph(f"<b>{label}</b>", section_style))
        left_column.append(Paragraph(_normalize_text_for_pdf(raw_text), body_style))
        left_column.append(Spacer(1, 1.5 * mm))

    if not left_column:
        left_column.append(Paragraph("Sem campos preenchidos para exibição.", body_style))

    right_column = _build_image_panel(report, body_style)

    body_table = Table([[left_column, right_column]], colWidths=[132 * mm, 52 * mm])
    body_table.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP")]))
    story.append(body_table)

    story.append(Spacer(1, 3 * mm))
    footer_line = Table([[" "]], colWidths=[184 * mm], rowHeights=[0.4 * mm])
    footer_line.setStyle(TableStyle([("BACKGROUND", (0, 0), (0, 0), colors.black)]))
    story.append(footer_line)
    story.append(Spacer(1, 1.5 * mm))
    story.append(Paragraph("Avenida Santos Dumont 2335 - Telefone : 3322 4111 - 99199 6369", footer_style))

    doc.build(story)
    return buffer.getvalue()
