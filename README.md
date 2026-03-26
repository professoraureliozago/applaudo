# MVP — Laudo de colonoscopia por narração

Protótipo em Python para transformar narração/transcrição em laudo estruturado com exportação em PDF.

## Como executar

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

> Se você rodar `python app.py`, o sistema relança automaticamente com `streamlit run app.py`.

## O que já faz

- Aba **Gerar laudo**: aplica templates por palavras-chave na transcrição e permite revisão final antes do PDF.
- Aba **Gerenciar modelos**: cadastra novos modelos por campo (nome, palavras-chave e texto) e salva no arquivo `templates/colonoscopia_templates.json`.
- Edição avançada do JSON completo de templates dentro da interface.
- Geração de PDF com cabeçalho e seções principais.

## Exemplo rápido (criar modelo)

1. Abra a aba **Gerenciar modelos**.
2. Escolha o campo (ex.: `colon_descendente`).
3. Preencha nome do modelo, palavras-chave e texto padrão.
4. Clique em **Salvar modelo**.
5. Volte para **Gerar laudo** e teste com uma transcrição contendo as palavras-chave.

## Próximos passos

- Integrar transcrição automática de áudio (Whisper local/API).
- Expandir todos os campos do formulário.
- Melhorar layout do PDF para ficar idêntico ao modelo da clínica.
