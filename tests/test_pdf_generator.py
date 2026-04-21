from __future__ import annotations

import base64
from pathlib import Path
import sys

import pytest

sys.path.append(str(Path(__file__).resolve().parents[1]))

pytest.importorskip("reportlab")

from src.laudo_app.models import ReportData
from src.laudo_app.pdf_generator import generate_pdf


_ONE_PIXEL_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO7ZxFYAAAAASUVORK5CYII="
)


def test_generate_pdf_returns_pdf_bytes():
    report = ReportData(paciente="Paciente Teste", medico="Dr. Teste", data_exame="01/01/2026", hora_exame="10:00")
    report.ensure_sections()
    report.secoes["reto"] = "O reto tem calibre e mucosa normais."
    pdf = generate_pdf(report)

    assert isinstance(pdf, bytes)
    assert pdf.startswith(b"%PDF")


def test_generate_pdf_supports_more_than_four_images():
    report = ReportData(
        paciente="Paciente Imagens",
        medico="Dr. Teste",
        data_exame="01/01/2026",
        hora_exame="10:00",
        image_bytes=[_ONE_PIXEL_PNG] * 7,
        image_captions=[f"Imagem {idx + 1}" for idx in range(7)],
    )
    report.ensure_sections()
    report.secoes["conclusao"] = "Teste com mais de quatro imagens no PDF."

    pdf = generate_pdf(report)

    assert pdf.startswith(b"%PDF")
    assert len(pdf) > 1500


def test_generate_pdf_handles_long_report_text_across_pages():
    report = ReportData(paciente="Paciente Texto Longo", medico="Dr. Teste", data_exame="01/01/2026", hora_exame="10:00")
    report.ensure_sections()
    long_finding = "Achado descritivo longo em reto com detalhes adicionais. " * 220
    report.secoes["reto"] = long_finding
    report.secoes["colon_descendente"] = long_finding

    pdf = generate_pdf(report)

    assert pdf.startswith(b"%PDF")
    assert len(pdf) > 2500


def test_generate_pdf_keeps_side_images_with_long_report_text():
    report = ReportData(
        paciente="Paciente Texto e Imagens",
        medico="Dr. Teste",
        data_exame="01/01/2026",
        hora_exame="10:00",
        image_bytes=[_ONE_PIXEL_PNG] * 4,
        image_captions=[f"Imagem {idx + 1}" for idx in range(4)],
    )
    report.ensure_sections()
    long_finding = "Achado descritivo longo em reto com detalhes adicionais. " * 220
    report.secoes["reto"] = long_finding
    report.secoes["colon_descendente"] = long_finding

    pdf = generate_pdf(report)

    assert pdf.startswith(b"%PDF")
    assert len(pdf) > 2500
