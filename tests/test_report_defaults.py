from src.laudo_app.models import DEFAULT_SECTIONS, ReportData
from src.laudo_app.template_engine import TemplateEngine

import app


def test_new_report_sections_start_with_default_texts():
    report = ReportData()
    report.ensure_sections()

    assert report.secoes["indicacao"] == "Rastreamento."
    assert report.secoes["preparo_paciente"] == "Preparo adequado com discreta quantidade de resíduos líquidos. Escala de Boston 09 pontos."
    assert report.secoes["duracao"] == "A duração do exame foi de aproximadamente 20 minutos."
    assert report.secoes["altura_atingida"] == "O colonoscópio foi introduzido pelo ânus até o ceco."
    assert report.secoes["reto"] == "O reto tem calibre e mucosa normais."
    assert report.secoes["colon_sigmoide"] == "O cólon sigmoide apresenta luz conservada com paredes cobertas com mucosa integra."
    assert report.secoes["colon_descendente"] == "O cólon descendente possui luz e mucosas normais."
    assert report.secoes["angulo_esplenico"] == "O ângulo esplênico foi ultrapassado sem dificuldades."
    assert report.secoes["colon_transverso"] == "O cólon transverso tem calibre, haustrações e mucosas normais."
    assert report.secoes["angulo_hepatico"] == "O ângulo hepático foi ultrapassado sem dificuldades."
    assert report.secoes["colon_ascendente"] == "O cólon ascendente é amplo e com mucosa preservada."
    assert report.secoes["ceco"] == "O ceco é normal e foi identificado pelo óstio apendicular e convergências das tênias."
    assert report.secoes["ileo_terminal"] == "O íleo apresenta luz de calibre e mucosa normais."
    assert report.secoes["conclusao"] == "Exame macroscopicamente normal."
    assert report.secoes["observacao_1"] == "Este exame não é indicado para avaliação do canal anal."
    assert report.secoes["observacao_2"] == ""
    assert list(report.secoes) == DEFAULT_SECTIONS


def test_existing_report_text_is_preserved_when_ensuring_sections():
    report = ReportData(secoes={"reto": "Texto manual do reto."})

    report.ensure_sections()

    assert report.secoes["reto"] == "Texto manual do reto."
    assert report.secoes["indicacao"] == "Rastreamento."


def test_review_models_are_added_to_existing_default_text():
    engine = TemplateEngine(
        config={
            "sections": [
                {
                    "id": "reto",
                    "triggers": ["reto"],
                    "default": "",
                    "models": [
                        {
                            "name": "polipo_menor",
                            "keywords": ["polipo sessil menor que 10 milimetros"],
                            "text": "Presença de pólipo séssil menor que 10 mm em reto.",
                        }
                    ],
                }
            ]
        }
    )
    report = ReportData()
    report.ensure_sections()

    reviewed = app._apply_models_for_single_section(
        engine=engine,
        section_id="reto",
        input_text="reto polipo sessil menor 10mm",
        current_text=report.secoes["reto"],
    )

    assert reviewed == (
        "O reto tem calibre e mucosa normais.\n"
        "Presença de pólipo séssil menor que 10 mm em reto."
    )


def test_merge_section_text_does_not_duplicate_same_model_text():
    merged = app._merge_section_text("Texto inicial.\nAchado.", "Achado.")

    assert merged == "Texto inicial.\nAchado."


def test_numbered_conclusion_uses_only_findings_added_to_target_sections():
    report = ReportData()
    report.ensure_sections()
    report.secoes["reto"] = app._merge_section_text(
        report.secoes["reto"],
        "PÃ³lipo sÃ©ssil menor que 10 mm.",
    )
    report.secoes["colon_sigmoide"] = app._merge_section_text(
        report.secoes["colon_sigmoide"],
        "DivertÃ­culos em sigmoide.",
    )

    conclusion = app._build_numbered_conclusion_from_sections(report.secoes)

    assert conclusion == (
        "1- Reto - PÃ³lipo sÃ©ssil menor que 10 mm.\n"
        "2- Cólon sigmoide - DivertÃ­culos em sigmoide."
    )
    assert "calibre e mucosa normais" not in conclusion


def test_reviewed_model_can_refresh_numbered_conclusion():
    engine = TemplateEngine(
        config={
            "sections": [
                {
                    "id": "reto",
                    "triggers": ["reto"],
                    "default": "",
                    "models": [
                        {
                            "name": "polipo_menor",
                            "keywords": ["polipo sessil menor que 10 milimetros"],
                            "text": "PÃ³lipo sÃ©ssil menor que 10 mm.",
                        }
                    ],
                }
            ]
        }
    )
    report = ReportData()
    report.ensure_sections()
    report.secoes["reto"] = app._apply_models_for_single_section(
        engine=engine,
        section_id="reto",
        input_text="reto polipo sessil menor 10mm",
        current_text=report.secoes["reto"],
    )

    app._refresh_conclusion_from_sections(report)

    assert report.secoes["conclusao"] == "1- Reto - PÃ³lipo sÃ©ssil menor que 10 mm."


def test_ceco_finding_is_included_in_numbered_conclusion():
    report = ReportData()
    report.ensure_sections()
    report.secoes["ceco"] = app._merge_section_text(
        report.secoes["ceco"],
        "Ceco com pÃ³lipo sÃ©ssil menor que 10 mm.",
    )

    app._refresh_conclusion_from_sections(report)

    assert report.secoes["conclusao"] == "1- Ceco - Ceco com pÃ³lipo sÃ©ssil menor que 10 mm."
