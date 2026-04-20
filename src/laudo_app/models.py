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


DEFAULT_SECTION_TEXTS = {
    "indicacao": "Rastreamento.",
    "preparo_paciente": "Preparo adequado com discreta quantidade de resíduos líquidos. Escala de Boston 09 pontos.",
    "duracao": "A duração do exame foi de aproximadamente 20 minutos.",
    "altura_atingida": "O colonoscópio foi introduzido pelo ânus até o ceco.",
    "reto": "O reto tem calibre e mucosa normais.",
    "colon_sigmoide": "O cólon sigmoide apresenta luz conservada com paredes cobertas com mucosa integra.",
    "colon_descendente": "O cólon descendente possui luz e mucosas normais.",
    "angulo_esplenico": "O ângulo esplênico foi ultrapassado sem dificuldades.",
    "colon_transverso": "O cólon transverso tem calibre, haustrações e mucosas normais.",
    "angulo_hepatico": "O ângulo hepático foi ultrapassado sem dificuldades.",
    "colon_ascendente": "O cólon ascendente é amplo e com mucosa preservada.",
    "ceco": "O ceco é normal e foi identificado pelo óstio apendicular e convergências das tênias.",
    "ileo_terminal": "O íleo apresenta luz de calibre e mucosa normais.",
    "conclusao": "Exame macroscopicamente normal.",
    "observacao_1": "Este exame não é indicado para avaliação do canal anal.",
    "observacao_2": "",
}


@dataclass
class ReportData:
    paciente: str = ""
    medico: str = ""
    medico_executante: str = ""
    sexo: str = ""
    idade: str = ""
    data_exame: str = ""
    hora_exame: str = ""
    convenio: str = ""
    footer_text: str = "Avenida Santos Dumont 2335 - Telefone : 3322 4111 - 99199 6369"
    secoes: Dict[str, str] = field(default_factory=dict)
    image_bytes: List[bytes] = field(default_factory=list)
    image_captions: List[str] = field(default_factory=list)

    def ensure_sections(self) -> None:
        for section in DEFAULT_SECTIONS:
            self.secoes.setdefault(section, DEFAULT_SECTION_TEXTS.get(section, ""))
