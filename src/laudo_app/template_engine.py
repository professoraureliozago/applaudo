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
    specificity: int = 0
    start: int = 0
    end: int = 0


@dataclass
class TranscriptScope:
    by_section: Dict[str, str]
    unscoped_text: str


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
        transcript_scope = self._build_transcript_scope(normalized_transcript)
        output: Dict[str, str] = {}

        for section_cfg in self.config.get("sections", []):
            section_id = section_cfg["id"]
            default_text = section_cfg.get("default", "")
            scoped_text = transcript_scope.by_section.get(section_id, transcript_scope.unscoped_text)
            best = self._match_section(section_cfg, scoped_text)
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

        candidates: List[tuple[int, MatchResult]] = []
        fallback_best: MatchResult | None = None
        best: MatchResult | None = None
        for model in section_cfg.get("models", []):
            score = 0
            best_span: tuple[int, int] | None = None
            best_specificity = 0
            for kw in model.get("keywords", []):
                span = self._find_term_span(normalized_transcript, kw)
                if span is not None:
                    score += 1
                    specificity = len(self._keyword_tokens(kw))
                    if specificity > best_specificity:
                        best_specificity = specificity
                        best_span = span

            if section_hits > 0:
                score += 1

            if score <= 0:
                continue

            start, end = best_span or (0, 0)
            candidate = MatchResult(
                section=section_cfg["id"],
                template_name=model["name"],
                score=score,
                text=model["text"],
                specificity=best_specificity,
                start=start,
                end=end,
            )
            if best_specificity > 0:
                candidates.append((len(candidates), candidate))
            elif fallback_best is None or candidate.score > fallback_best.score:
                fallback_best = candidate
            if best is None or candidate.score > best.score:
                best = candidate

        if not candidates:
            return fallback_best or best

        selected: List[tuple[int, MatchResult]] = []
        for original_index, candidate in sorted(
            candidates,
            key=lambda item: (-item[1].specificity, -item[1].score, item[1].start, item[0]),
        ):
            overlaps_selected = any(
                self._ranges_overlap(candidate.start, candidate.end, existing.start, existing.end)
                for _, existing in selected
            )
            if overlaps_selected:
                continue
            selected.append((original_index, candidate))

        selected.sort(key=lambda item: (item[1].start, item[0]))
        rendered_texts = [match.text.strip() for _, match in selected if match.text.strip()]
        if not rendered_texts:
            return fallback_best or best

        first = selected[0][1]
        return MatchResult(
            section=first.section,
            template_name=first.template_name,
            score=sum(match.score for _, match in selected),
            text="\n".join(dict.fromkeys(rendered_texts)),
            specificity=max(match.specificity for _, match in selected),
            start=first.start,
            end=selected[-1][1].end,
        )

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
        text = re.sub(r"(\d+)\s*(mm|milimetros?|milimetro)\b", r"\1 mm", text)
        text = re.sub(r"(\d+)\s*(cm|centimetros?|centimetro)\b", r"\1 cm", text)
        text = re.sub(r"(\d)([a-zA-Z])", r"\1 \2", text)
        text = re.sub(r"([a-zA-Z])(\d)", r"\1 \2", text)
        text = re.sub(r"[^\w\s]", " ", text)
        text = re.sub(r"\s+", " ", text).strip()
        return text

    def _contains_term(self, normalized_transcript: str, raw_term: str) -> bool:
        return self._find_term_span(normalized_transcript, raw_term) is not None

    @staticmethod
    def _ranges_overlap(start_a: int, end_a: int, start_b: int, end_b: int) -> bool:
        return start_a < end_b and start_b < end_a

    def _keyword_tokens(self, raw_term: str) -> List[str]:
        stopwords = {"a", "as", "com", "da", "de", "do", "dos", "e", "em", "o", "os", "que", "um", "uma"}
        return [token for token in self._normalize_text(raw_term).split() if token and token not in stopwords]

    def _find_term_span(self, normalized_transcript: str, raw_term: str) -> tuple[int, int] | None:
        term_tokens = self._keyword_tokens(raw_term)
        if not term_tokens:
            return None

        stopwords = {"a", "as", "com", "da", "de", "do", "dos", "e", "em", "o", "os", "que", "um", "uma"}
        transcript_tokens = [
            (match.group(0), match.start(), match.end())
            for match in re.finditer(r"\S+", normalized_transcript)
        ]
        if not transcript_tokens:
            return None

        for start_idx, (token, start, _) in enumerate(transcript_tokens):
            if token != term_tokens[0]:
                continue
            current_idx = start_idx
            matched = 0
            end = start
            while current_idx < len(transcript_tokens) and matched < len(term_tokens):
                current_token, _, current_end = transcript_tokens[current_idx]
                if current_token == term_tokens[matched]:
                    matched += 1
                    end = current_end
                elif current_token not in stopwords:
                    break
                current_idx += 1
            if matched == len(term_tokens):
                return (start, end)

        return None

    def _build_transcript_scope(self, normalized_transcript: str) -> TranscriptScope:
        scoped_chunks: Dict[str, List[str]] = {}
        section_matches = self._find_section_matches(normalized_transcript)

        if not section_matches:
            return TranscriptScope(by_section={}, unscoped_text=normalized_transcript)

        consumed_ranges: List[tuple[int, int]] = []
        for idx, match in enumerate(section_matches):
            next_start = section_matches[idx + 1][0] if idx + 1 < len(section_matches) else len(normalized_transcript)
            chunk = normalized_transcript[match[1] : next_start].strip()
            if not chunk:
                chunk = normalized_transcript[match[0] : match[1]].strip()
            if chunk:
                scoped_chunks.setdefault(match[2], []).append(chunk)
            consumed_ranges.append((match[0], next_start))

        unscoped_parts: List[str] = []
        cursor = 0
        for start, end in consumed_ranges:
            if cursor < start:
                unscoped_parts.append(normalized_transcript[cursor:start].strip())
            cursor = max(cursor, end)
        if cursor < len(normalized_transcript):
            unscoped_parts.append(normalized_transcript[cursor:].strip())

        by_section = {section_id: " ".join(chunks).strip() for section_id, chunks in scoped_chunks.items()}
        unscoped_text = " ".join(part for part in unscoped_parts if part).strip()
        return TranscriptScope(by_section=by_section, unscoped_text=unscoped_text)

    def _find_section_matches(self, normalized_transcript: str) -> List[tuple[int, int, str]]:
        raw_matches: List[tuple[int, int, str]] = []
        for section_cfg in self.config.get("sections", []):
            section_id = section_cfg["id"]
            for trigger in section_cfg.get("triggers", []):
                normalized_trigger = self._normalize_text(trigger)
                if not normalized_trigger:
                    continue
                pattern = rf"\b{re.escape(normalized_trigger)}\b"
                for match in re.finditer(pattern, normalized_transcript):
                    raw_matches.append((match.start(), match.end(), section_id))

        if not raw_matches:
            return []

        raw_matches.sort(key=lambda item: (item[0], -(item[1] - item[0])))
        selected: List[tuple[int, int, str]] = []
        current_end = -1
        for start, end, section_id in raw_matches:
            if start < current_end:
                continue
            selected.append((start, end, section_id))
            current_end = end

        selected.sort(key=lambda item: item[0])
        return selected
