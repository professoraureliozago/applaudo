import re
import unicodedata
from dataclasses import dataclass
from typing import Any, Dict, List

from .template_loader import load_template_config


@dataclass
class MatchResult:
    section: str
    template_name: str
    score: int
    text: str


class TemplateEngine:
    def __init__(self, config_path: str | None = None, config: dict[str, Any] | None = None) -> None:
        if config is not None:
            self.config = config
            self.config_path = config_path or ""
        elif config_path:
            self.config_path = config_path
            self.config = load_template_config(config_path)
        else:
            raise ValueError("Informe 'config_path' ou 'config' para inicializar TemplateEngine.")

    def render_from_transcript(self, transcript: str) -> Dict[str, str]:
        normalized_transcript = self._normalize_text(transcript)
        output: Dict[str, str] = {}

        for section_cfg in self.config.get("sections", []):
            section_id = section_cfg["id"]
            default_text = section_cfg.get("default", "")
            best = self._match_section(section_cfg, normalized_transcript)
            if best:
                output[section_id] = self._apply_placeholders(best.text, transcript)
            else:
                output[section_id] = default_text

        current_conclusion = output.get("conclusao", "").strip()
        if not current_conclusion:
            output["conclusao"] = self._build_conclusion(output)

        return output

    def _match_section(self, section_cfg: Dict[str, Any], normalized_transcript: str) -> MatchResult | None:
        section_hits = 0
        for trigger in section_cfg.get("triggers", []):
            if self._contains_term(normalized_transcript, trigger):
                section_hits += 1

        best: MatchResult | None = None
        for model in section_cfg.get("models", []):
            score = 0
            for kw in model.get("keywords", []):
                if self._contains_term(normalized_transcript, kw):
                    score += 1

            if section_hits > 0:
                score += 1

            if score <= 0:
                continue

            candidate = MatchResult(
                section=section_cfg["id"],
                template_name=model["name"],
                score=score,
                text=model["text"],
            )
            if best is None or candidate.score > best.score:
                best = candidate

        return best

    def _apply_placeholders(self, template_text: str, transcript: str) -> str:
        size_cm = self._extract_size_cm(transcript)
        result = template_text.replace("{tamanho_cm}", size_cm if size_cm else "não informado")
        return result

    @staticmethod
    def _extract_size_cm(transcript: str) -> str | None:
        patterns = [
            r"(\d+(?:[\.,]\d+)?)\s*cm",
            r"(\d+(?:[\.,]\d+)?)\s*cent[ií]metro",
            r"(\d+(?:[\.,]\d+)?)\s*cent[ií]metros",
        ]
        for pattern in patterns:
            match = re.search(pattern, transcript.lower())
            if match:
                return match.group(1).replace(".", ",")
        return None

    @staticmethod
    def _build_conclusion(output: Dict[str, str]) -> str:
        findings: List[str] = []
        for key, text in output.items():
            if key == "conclusao":
                continue
            if "pólipo" in text.lower() or "polipo" in text.lower():
                findings.append(text)

        if findings:
            return "\n".join([f"- {f}" for f in findings])

        return ""

    @staticmethod
    def _normalize_text(text: str) -> str:
        text = text.lower()
        text = "".join(ch for ch in unicodedata.normalize("NFD", text) if unicodedata.category(ch) != "Mn")
        text = re.sub(r"[^\w\s]", " ", text)
        text = re.sub(r"\s+", " ", text).strip()
        return text

    def _contains_term(self, normalized_transcript: str, raw_term: str) -> bool:
        normalized_term = self._normalize_text(raw_term)
        if not normalized_term:
            return False
        return normalized_term in normalized_transcript
