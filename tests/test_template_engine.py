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


def test_defaults_when_no_match():
    engine = TemplateEngine("templates/colonoscopia_templates.json")
    rendered = engine.render_from_transcript("Texto sem termos clínicos mapeados.")

    assert rendered["reto"] == "Reto sem descrição específica."


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
