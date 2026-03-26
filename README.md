# MVP — Laudo de colonoscopia por narração

Protótipo em Python para transformar áudio/narração em laudo estruturado com exportação em PDF.

## Como executar

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

> Se você rodar `python app.py`, o sistema relança automaticamente com `streamlit run app.py`.

## O que já faz

- Aba **Gerar laudo**:
  - transcreve automaticamente arquivo de áudio via **faster-whisper local** ou **API OpenAI**,
  - aplica templates por palavras-chave na transcrição,
  - permite revisão final antes do PDF.
- Aba **Gerenciar modelos**:
  - cria novos modelos por campo,
  - edita modelo salvo ao clicar em **Editar**,
  - exclui com confirmação em **2 cliques**,
  - salva no arquivo `templates/colonoscopia_templates.json`.
- Edição avançada do JSON completo de templates dentro da interface.
- Matching robusto (ignora acentos/maiúsculas/pontuação) para facilitar reconhecimento dos modelos.
- Geração de PDF com cabeçalho e seções principais.

## Como usar transcrição automática

1. Na aba **Gerar laudo**, envie o áudio em `wav/mp3/m4a`.
2. Escolha o provedor:
   - `local` (faster-whisper): escolha o tamanho do modelo.
   - `openai` (API): informe `OPENAI_API_KEY` e modelo (ex.: `whisper-1`).
3. Clique em **Transcrever áudio**.
4. O texto transcrito será preenchido automaticamente no campo de transcrição.
5. Clique em **Gerar laudo sugerido**.

## Próximos passos

- Captura de áudio em tempo real durante exame (sem upload manual).
- Expandir todos os campos do formulário.
- Melhorar layout do PDF para ficar idêntico ao modelo da clínica.
