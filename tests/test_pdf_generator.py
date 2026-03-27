from pathlib import Path
import sys

import pytest

sys.path.append(str(Path(__file__).resolve().parents[1]))

pytest.importorskip("reportlab")

from src.laudo_app.models import ReportData
from src.laudo_app.pdf_generator import generate_pdf


def test_generate_pdf_returns_pdf_bytes():
    report = ReportData(paciente="Paciente Teste", medico="Dr. Teste", data_exame="01/01/2026", hora_exame="10:00")
    report.ensure_sections()
    report.secoes["reto"] = "O reto tem calibre e mucosa normais."
    pdf = generate_pdf(report)

    assert isinstance(pdf, bytes)
    assert pdf.startswith(b"%PDF")
