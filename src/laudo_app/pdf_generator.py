from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.platypus import BaseDocTemplate, Frame, KeepTogether, PageBreak, PageTemplate, Paragraph, Spacer, Table, TableStyle

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


def _chunk_image_items(image_bytes: list[bytes], image_captions: list[str], chunk_size: int = 4) -> list[tuple[list[bytes], list[str]]]:
    chunks: list[tuple[list[bytes], list[str]]] = []
    for i in range(0, len(image_bytes), chunk_size):
        chunks.append((image_bytes[i : i + chunk_size], image_captions[i : i + chunk_size]))
    return chunks


def _build_text_sections(report: ReportData, section_style: ParagraphStyle, body_style: ParagraphStyle) -> list[list]:
    sections: list[list] = []
    for key, label in FIELD_ORDER:
        raw_text = report.secoes.get(key, "")
        if not _has_meaningful_content(raw_text):
            continue
        sections.append(
            [
                Paragraph(f"<b>{label}</b>", section_style),
                Paragraph(_normalize_text_for_pdf(raw_text), body_style),
                Spacer(1, 1.5 * mm),
            ]
        )

    if not sections:
        sections.append([Paragraph("Sem campos preenchidos para exibicao.", body_style)])
    return sections


def _flatten_text_sections(sections: list[list], keep_sections_together: bool) -> list:
    flow: list = []
    for section in sections:
        if keep_sections_together and len(section) >= 2:
            flow.append(KeepTogether(section[:2]))
            flow.extend(section[2:])
        else:
            flow.extend(section)
    return flow


def generate_pdf(report: ReportData) -> bytes:
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

    image_chunks = _chunk_image_items(report.image_bytes, report.image_captions, chunk_size=4)
    has_images = bool(image_chunks)
    left_margin = 12 * mm
    bottom_margin = 16 * mm
    top_margin = 26 * mm
    full_width = A4[0] - (24 * mm)
    text_width = 132 * mm if has_images else full_width
    first_frame_top = A4[1] - 72 * mm
    later_frame_top = A4[1] - top_margin
    image_x = left_margin + text_width + 4 * mm
    image_width = 50 * mm
    image_height = 40 * mm

    def draw_side_images(canvas, page_number: int):
        chunk_index = page_number - 1
        if chunk_index >= len(image_chunks):
            return

        chunk_images, chunk_captions = image_chunks[chunk_index]
        y = (first_frame_top if page_number == 1 else later_frame_top) - 2 * mm
        for idx in range(4):
            if idx >= len(chunk_images):
                break

            canvas.drawImage(
                ImageReader(BytesIO(chunk_images[idx])),
                image_x,
                y - image_height,
                width=image_width,
                height=image_height,
                preserveAspectRatio=True,
                anchor="c",
            )
            y -= image_height + 1.5 * mm

            caption = chunk_captions[idx] if idx < len(chunk_captions) and chunk_captions[idx] else f"imagem {idx + 1}"
            caption_paragraph = Paragraph(f"<i>{caption}</i>", body_style)
            _, caption_height = caption_paragraph.wrap(image_width, 12 * mm)
            caption_paragraph.drawOn(canvas, image_x, y - caption_height)
            y -= caption_height + 3 * mm

    def draw_common_header_footer(canvas, page_number: int):
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
        draw_side_images(canvas, page_number)
        canvas.restoreState()

    separator = Table([[" "]], colWidths=[184 * mm], rowHeights=[0.5 * mm])
    separator.setStyle(TableStyle([("BACKGROUND", (0, 0), (0, 0), colors.black)]))

    def draw_first_page(canvas, doc):
        draw_common_header_footer(canvas, doc.page)
        title = Paragraph("<u><b>Laudo de Videocolonoscopia</b></u>", laudo_title_style)
        _, title_height = title.wrap(full_width, 12 * mm)
        title.drawOn(canvas, left_margin, A4[1] - 32 * mm - title_height)
        header_table.wrapOn(canvas, full_width, 30 * mm)
        header_table.drawOn(canvas, left_margin, A4[1] - 58 * mm)
        separator.wrapOn(canvas, full_width, 2 * mm)
        separator.drawOn(canvas, left_margin, A4[1] - 65 * mm)

    def draw_later_page(canvas, doc):
        draw_common_header_footer(canvas, doc.page)

    def build_pdf(extra_image_pages: int) -> tuple[bytes, int]:
        buffer = BytesIO()
        doc = BaseDocTemplate(
            buffer,
            pagesize=A4,
            leftMargin=left_margin,
            rightMargin=12 * mm,
            topMargin=top_margin,
            bottomMargin=bottom_margin,
        )
        first_frame = Frame(
            left_margin,
            bottom_margin,
            text_width,
            first_frame_top - bottom_margin,
            id="first_body",
        )
        later_frame = Frame(
            left_margin,
            bottom_margin,
            text_width,
            later_frame_top - bottom_margin,
            id="later_body",
        )
        doc.addPageTemplates(
            [
                PageTemplate(id="First", frames=[first_frame], onPage=draw_first_page, autoNextPageTemplate="Later"),
                PageTemplate(id="Later", frames=[later_frame], onPage=draw_later_page),
            ]
        )

        text_sections = _build_text_sections(report, section_style, body_style)
        story = _flatten_text_sections(text_sections, keep_sections_together=True)
        for _ in range(extra_image_pages):
            story.append(PageBreak())
            story.append(Paragraph("<b>Imagens adicionais</b>", section_style))
        doc.build(story)
        return buffer.getvalue(), doc.page

    pdf_data, page_count = build_pdf(extra_image_pages=0)
    missing_image_pages = max(0, len(image_chunks) - page_count)
    if missing_image_pages:
        pdf_data, _ = build_pdf(extra_image_pages=missing_image_pages)
    return pdf_data
