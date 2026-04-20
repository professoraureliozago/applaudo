from src.laudo_app.models import DEFAULT_SECTIONS, ReportData


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
