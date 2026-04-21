from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Image as RLImage
from reportlab.platypus import KeepTogether, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

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


def _build_image_panel(image_bytes: list[bytes], captions: list[str], body_style: ParagraphStyle) -> list:
    panel: list = []
    image_count = min(4, len(image_bytes))

    for i in range(4):
        if i < image_count:
            image = RLImage(BytesIO(image_bytes[i]), width=50 * mm, height=40 * mm)
            image.hAlign = "CENTER"
            panel.append(image)
            caption = captions[i] if i < len(captions) and captions[i] else f"imagem {i + 1}"
            panel.append(Paragraph(f"<i>{caption}</i>", body_style))
        else:
            panel.append(Spacer(50 * mm, 40 * mm))
            panel.append(Paragraph("", body_style))
        panel.append(Spacer(1, 2 * mm))

    return panel


def _chunk_image_items(image_bytes: list[bytes], image_captions: list[str], chunk_size: int = 4) -> list[tuple[list[bytes], list[str]]]:
    chunks: list[tuple[list[bytes], list[str]]] = []
    for i in range(0, len(image_bytes), chunk_size):
        chunks.append((image_bytes[i : i + chunk_size], image_captions[i : i + chunk_size]))
    return chunks


def _build_text_flow(report: ReportData, section_style: ParagraphStyle, body_style: ParagraphStyle) -> list:
    flow: list = []
    for key, label in FIELD_ORDER:
        raw_text = report.secoes.get(key, "")
        if not _has_meaningful_content(raw_text):
            continue
        flow.append(
            KeepTogether(
                [
                    Paragraph(f"<b>{label}</b>", section_style),
                    Paragraph(_normalize_text_for_pdf(raw_text), body_style),
                ]
            )
        )
        flow.append(Spacer(1, 1.5 * mm))

    if not flow:
        flow.append(Paragraph("Sem campos preenchidos para exibição.", body_style))
    return flow


def generate_pdf(report: ReportData) -> bytes:
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        topMargin=26 * mm,
        bottomMargin=16 * mm,
        leftMargin=12 * mm,
        rightMargin=12 * mm,
    )

    styles = getSampleStyleSheet()
    laudo_title_style = ParagraphStyle("LaudoTitle", parent=styles["Heading3"], alignment=1, fontSize=12)
    section_style = ParagraphStyle("Section", parent=styles["Heading4"], fontSize=10.5, leading=12, spaceAfter=1)
    body_style = ParagraphStyle("Body", parent=styles["Normal"], fontSize=9.5, leading=12)

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

    header_table = Table(header_data, colWidths=[92 * mm, 46 * mm, 46 * mm])
    header_table.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("BOTTOMPADDING", (0, 0), (-1, -1), 3)]))

    def draw_header_footer(canvas, _doc):
        canvas.saveState()
        y_top = A4[1] - 10 * mm
        canvas.setFont("Helvetica-Bold", 14)
        canvas.setFillColor(colors.HexColor("#d26f2a"))
        canvas.drawCentredString(A4[0] / 2, y_top, "Videocolonoscopia")
        canvas.setFont("Helvetica", 10)
        canvas.drawCentredString(A4[0] / 2, y_top - 5.5 * mm, report.medico_executante or "Dr(a).")
        canvas.line(12 * mm, y_top - 8 * mm, A4[0] - 12 * mm, y_top - 8 * mm)
        canvas.setFont("Helvetica", 8.5)
        canvas.setFillColor(colors.HexColor("#d26f2a"))
        canvas.line(12 * mm, 12 * mm, A4[0] - 12 * mm, 12 * mm)
        canvas.drawCentredString(A4[0] / 2, 8 * mm, report.footer_text or "")
        canvas.restoreState()

    story = []
    story.append(Paragraph("<u><b>Laudo de Videocolonoscopia</b></u>", laudo_title_style))
    story.append(Spacer(1, 3 * mm))
    story.append(header_table)
    story.append(Spacer(1, 2 * mm))

    separator = Table([[" "]], colWidths=[184 * mm], rowHeights=[0.5 * mm])
    separator.setStyle(TableStyle([("BACKGROUND", (0, 0), (0, 0), colors.black)]))
    story.append(separator)
    story.append(Spacer(1, 2.5 * mm))

    story.extend(_build_text_flow(report, section_style, body_style))

    image_chunks = _chunk_image_items(report.image_bytes, report.image_captions, chunk_size=4)
    for idx, (chunk_images, chunk_captions) in enumerate(image_chunks):
        story.append(PageBreak())
        current_left = [Paragraph("<b>Imagens do exame</b>" if idx == 0 else "<b>Imagens adicionais</b>", section_style)]
        right_column = _build_image_panel(chunk_images, chunk_captions, body_style)
        body_table = Table([[current_left, right_column]], colWidths=[132 * mm, 52 * mm])
        body_table.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP")]))
        story.append(body_table)

    doc.build(story, onFirstPage=draw_header_footer, onLaterPages=draw_header_footer)
    return buffer.getvalue()
