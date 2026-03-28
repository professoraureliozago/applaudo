from dataclasses import dataclass, field
from typing import Dict, List


DEFAULT_SECTIONS = [
    "indicacao",
    "preparo_paciente",
    "duracao",
    "altura_atingida",
    "reto",
    "colon_sigmoide",
    "colon_descendente",
    "angulo_esplenico",
    "colon_transverso",
    "angulo_hepatico",
    "colon_ascendente",
    "ceco",
    "ileo_terminal",
    "conclusao",
    "observacao_1",
    "observacao_2",
]


@dataclass
class ReportData:
    paciente: str = ""
    medico: str = ""
    sexo: str = ""
    idade: str = ""
    data_exame: str = ""
    hora_exame: str = ""
    convenio: str = ""
    secoes: Dict[str, str] = field(default_factory=dict)
    image_bytes: List[bytes] = field(default_factory=list)
    image_captions: List[str] = field(default_factory=list)

    def ensure_sections(self) -> None:
        for section in DEFAULT_SECTIONS:
            self.secoes.setdefault(section, "")
