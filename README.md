# MVP — Laudo de colonoscopia por narração

Protótipo em Python para transformar narração/transcrição em laudo estruturado com exportação em PDF.

## Como executar

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

> Se você rodar `python app.py`, o sistema agora relança automaticamente com `streamlit run app.py`.

## O que já faz

- Preenche seções com base em palavras-chave usando templates JSON (`templates/colonoscopia_templates.json`).
- Permite revisão manual por seção.
- Gera PDF com cabeçalho e seções principais.

## Próximos passos

- Integrar transcrição automática de áudio (Whisper local/API).
- Expandir todos os campos do formulário.
- Melhorar layout do PDF para ficar idêntico ao modelo da clínica.
