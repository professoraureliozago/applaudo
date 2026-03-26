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
- Aba **Gerenciar modelos**:
  - cria novos modelos por campo,
  - edita um modelo salvo ao clicar em **Editar**,
  - exclui com confirmação em **2 cliques** no botão **Excluir (2 cliques)**,
  - salva no arquivo `templates/colonoscopia_templates.json`.
- Edição avançada do JSON completo de templates dentro da interface.
- Matching mais robusto (ignora acentos/maiúsculas/pontuação) para facilitar reconhecimento dos modelos salvos.
- Geração de PDF com cabeçalho e seções principais.

## Exemplo rápido (criar/editar modelo)

1. Abra a aba **Gerenciar modelos**.
2. Escolha o campo (ex.: `colon_descendente`).
3. Para novo modelo: preencha nome, palavras-chave e texto e clique em **Salvar modelo**.
4. Para editar: clique em **Editar**, altere e clique em **Atualizar modelo**.
5. Volte para **Gerar laudo** e teste com uma transcrição contendo as palavras-chave.

## Próximos passos

- Integrar transcrição automática de áudio (Whisper local/API).
- Expandir todos os campos do formulário.
- Melhorar layout do PDF para ficar idêntico ao modelo da clínica.
