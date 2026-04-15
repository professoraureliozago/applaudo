from pathlib import Path
import sys

sys.path.append(str(Path(__file__).resolve().parents[1]))

from src.laudo_app.template_engine import TemplateEngine


def test_polipo_in_descendente_generates_template_with_size():
    engine = TemplateEngine("templates/colonoscopia_templates.json")
    transcript = (
        "No cólon descendente há pólipo séssil de 1,0 cm e foi realizada polipectomia. "
        "Reto com mucosa normal."
    )

    rendered = engine.render_from_transcript(transcript)

    assert "pólipo séssil" in rendered["colon_descendente"].lower()
    assert "1,0" in rendered["colon_descendente"]
    assert "pólipo" in rendered["conclusao"].lower()


def test_defaults_when_no_match_are_blank_for_optional_sections():
    engine = TemplateEngine("templates/colonoscopia_templates.json")
    rendered = engine.render_from_transcript("Texto sem termos clínicos mapeados.")

    assert rendered["reto"] == ""


def test_matching_ignores_accents_and_punctuation():
    engine = TemplateEngine("templates/colonoscopia_templates.json")
    transcript = "No colon descendente: polipo sessil de 1 cm; realizada polipectomia!"

    rendered = engine.render_from_transcript(transcript)

    assert "pólipo séssil" in rendered["colon_descendente"].lower()


def test_templates_cover_all_default_sections():
    from src.laudo_app.models import DEFAULT_SECTIONS

    engine = TemplateEngine("templates/colonoscopia_templates.json")
    section_ids = [s["id"] for s in engine.config.get("sections", [])]

    for section in DEFAULT_SECTIONS:
        assert section in section_ids


def test_explicit_section_prefix_scopes_keywords_to_that_section():
    engine = TemplateEngine(
        config={
            "sections": [
                {
                    "id": "reto",
                    "triggers": ["reto"],
                    "default": "",
                    "models": [
                        {
                            "name": "sangramento_reto",
                            "keywords": ["sangramento"],
                            "text": "Reto com sangramento.",
                        }
                    ],
                },
                {
                    "id": "indicacao",
                    "triggers": ["indicação", "indicacao"],
                    "default": "",
                    "models": [
                        {
                            "name": "sangramento_indicacao",
                            "keywords": ["sangramento"],
                            "text": "Exame indicado por sangramento.",
                        }
                    ],
                },
            ]
        }
    )

    rendered = engine.render_from_transcript("Reto sangramento.")

    assert rendered["reto"] == "Reto com sangramento."
    assert rendered["indicacao"] == ""


def test_explicit_prefix_supports_same_keyword_in_multiple_sections():
    engine = TemplateEngine(
        config={
            "sections": [
                {
                    "id": "reto",
                    "triggers": ["reto"],
                    "default": "",
                    "models": [
                        {
                            "name": "sangramento_reto",
                            "keywords": ["sangramento"],
                            "text": "Reto com sangramento.",
                        }
                    ],
                },
                {
                    "id": "colon_descendente",
                    "triggers": ["cólon descendente", "colon descendente"],
                    "default": "",
                    "models": [
                        {
                            "name": "sangramento_descendente",
                            "keywords": ["sangramento"],
                            "text": "Cólon descendente com sangramento.",
                        }
                    ],
                },
            ]
        }
    )

    rendered = engine.render_from_transcript("Reto sangramento. Colon descendente sangramento.")

    assert rendered["reto"] == "Reto com sangramento."
    assert rendered["colon_descendente"] == "Cólon descendente com sangramento."
