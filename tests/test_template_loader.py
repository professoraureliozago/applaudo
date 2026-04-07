from pathlib import Path
import sys

import pytest

sys.path.append(str(Path(__file__).resolve().parents[1]))

from src.laudo_app.template_loader import load_template_config


def test_loader_repairs_trailing_comma(tmp_path: Path):
    file = tmp_path / "bad.json"
    file.write_text('{"sections": [{"id": "reto",}],}', encoding="utf-8")

    data = load_template_config(str(file))

    assert "sections" in data
    assert data["sections"][0]["id"] == "reto"


def test_loader_raises_for_irreparable_json(tmp_path: Path):
    file = tmp_path / "broken.json"
    file.write_text('{"sections": [', encoding="utf-8")

    with pytest.raises(RuntimeError):
        load_template_config(str(file))
