from src.laudo_app.models import DEFAULT_SECTION_TEXTS, DEFAULT_SECTIONS, ReportData
from src.laudo_app.template_engine import TemplateEngine

import app


def test_new_report_sections_start_with_default_texts():
    report = ReportData()
    report.ensure_sections()

    for section_id, expected_text in DEFAULT_SECTION_TEXTS.items():
        assert report.secoes[section_id] == expected_text
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
                            "text": "PresenÃ§a de pÃ³lipo sÃ©ssil menor que 10 mm em reto.",
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
        "PresenÃ§a de pÃ³lipo sÃ©ssil menor que 10 mm em reto."
    )


def test_merge_section_text_does_not_duplicate_same_model_text():
    merged = app._merge_section_text("Texto inicial.\nAchado.", "Achado.")

    assert merged == "Texto inicial.\nAchado."


def test_review_models_replace_default_text_for_indicacao():
    engine = TemplateEngine(
        config={
            "sections": [
                {
                    "id": "indicacao",
                    "triggers": ["indicacao"],
                    "default": "",
                    "models": [
                        {
                            "name": "sangramento",
                            "keywords": ["sangramento"],
                            "text": "Exame indicado por quadro de sangramento digestivo baixo.",
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
        section_id="indicacao",
        input_text="indicacao sangramento",
        current_text=report.secoes["indicacao"],
    )

    assert reviewed == "Exame indicado por quadro de sangramento digestivo baixo."


def test_generate_flow_replaces_default_text_for_duracao():
    current_text = DEFAULT_SECTION_TEXTS["duracao"]
    default_text = DEFAULT_SECTION_TEXTS["duracao"]
    previous_auto = DEFAULT_SECTION_TEXTS["duracao"]
    new_text = "DuraÃ§Ã£o do exame de aproximadamente 30 minutos."
    current_is_default = str(current_text).strip() == str(default_text).strip()
    should_update = (
        not str(current_text).strip()
        or current_is_default
        or (str(current_text).strip() == previous_auto.strip())
    )

    merged_text = current_text
    if should_update and str(new_text).strip():
        if app._should_replace_default_with_model("duracao", current_text):
            merged_text = str(new_text).strip()
        else:
            base_text = default_text if (current_is_default or str(current_text).strip() == previous_auto.strip()) else current_text
            merged_text = app._merge_section_text(base_text, new_text)

    assert merged_text == "DuraÃ§Ã£o do exame de aproximadamente 30 minutos."


def test_numbered_conclusion_uses_only_findings_added_to_target_sections():
    report = ReportData()
    report.ensure_sections()
    report.secoes["reto"] = app._merge_section_text(
        report.secoes["reto"],
        "PÃƒÂ³lipo sÃƒÂ©ssil menor que 10 mm.",
    )
    report.secoes["colon_sigmoide"] = app._merge_section_text(
        report.secoes["colon_sigmoide"],
        "DivertÃƒÂ­culos em sigmoide.",
    )

    conclusion = app._build_numbered_conclusion_from_sections(report.secoes)

    assert conclusion == (
        "1- Reto - PÃƒÂ³lipo sÃƒÂ©ssil menor que 10 mm.\n"
        "2- Cólon sigmoide - DivertÃƒÂ­culos em sigmoide."
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
                            "text": "PÃƒÂ³lipo sÃƒÂ©ssil menor que 10 mm.",
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

    assert report.secoes["conclusao"] == "1- Reto - PÃƒÂ³lipo sÃƒÂ©ssil menor que 10 mm."


def test_ceco_finding_is_included_in_numbered_conclusion():
    report = ReportData()
    report.ensure_sections()
    report.secoes["ceco"] = app._merge_section_text(
        report.secoes["ceco"],
        "Ceco com pÃƒÂ³lipo sÃƒÂ©ssil menor que 10 mm.",
    )

    app._refresh_conclusion_from_sections(report)

    assert report.secoes["conclusao"] == "1- Ceco - Ceco com pÃƒÂ³lipo sÃƒÂ©ssil menor que 10 mm."


def test_observacao_2_enters_conclusion_without_field_label():
    report = ReportData()
    report.ensure_sections()
    report.secoes["observacao_2"] = "PresenÃƒÂ§a de ÃƒÂ³stios diverticulares em sigmoide."

    app._refresh_conclusion_from_sections(report)

    assert report.secoes["conclusao"] == "1- PresenÃƒÂ§a de ÃƒÂ³stios diverticulares em sigmoide."
