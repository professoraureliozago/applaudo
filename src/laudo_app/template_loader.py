from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


def load_template_config(path: str) -> dict[str, Any]:
    raw = Path(path).read_text(encoding="utf-8")

    try:
        return json.loads(raw)
    except json.JSONDecodeError as first_error:
        repaired = _repair_common_json_issues(raw)
        try:
            return json.loads(repaired)
        except json.JSONDecodeError as second_error:
            raise RuntimeError(
                f"Arquivo de templates inválido ({path}). Erro original: {first_error}. Erro após tentativa de reparo: {second_error}."
            ) from second_error


def _repair_common_json_issues(raw: str) -> str:
    text = raw.lstrip("\ufeff")
    text = re.sub(r"^\s*//.*$", "", text, flags=re.MULTILINE)
    text = re.sub(r",\s*([}\]])", r"\1", text)
    return text
