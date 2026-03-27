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

## Windows (VS Code) — execução recomendada

No PowerShell, dentro da pasta do projeto:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
python -m streamlit run app.py
```

Atalho automático:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\run_windows.ps1
```

## Captura de áudio em tempo real (novo)

Na aba **Gerar laudo** agora existem dois modos:

1. **Modo 1: Gravação no microfone (tempo real por trechos)**
   - Clique em **Gravar trecho do exame**.
   - Depois clique em **Transcrever trecho gravado**.
   - O texto transcrito é anexado automaticamente ao rascunho.

2. **Modo 2: Upload de arquivo de áudio**
   - Fluxo anterior, para quando você já tiver um arquivo gravado.

Você pode repetir várias gravações curtas durante o exame e ir acumulando no rascunho.

## Erro comum: `ModuleNotFoundError: No module named 'streamlit'`

Esse erro significa que o VS Code está usando um Python onde o `streamlit` não está instalado.

Passos para corrigir:

1. No VS Code: `Ctrl+Shift+P` → **Python: Select Interpreter**.
2. Escolha o interpretador do projeto: `.venv\Scripts\python.exe`.
3. No terminal do VS Code, execute:

```powershell
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
python -m streamlit run app.py
```

## O que já faz

- Aba **Gerar laudo**:
  - transcreve automaticamente áudio via **faster-whisper local** ou **API OpenAI**,
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

## Próximos passos

- Acionamento automático de transcrição em janelas de tempo (ex.: a cada 20–30 segundos).
- Expandir todos os campos do formulário.
- Melhorar layout do PDF para ficar idêntico ao modelo da clínica.

## Solução de erro no Windows

Se aparecia `Permission denied` no arquivo temporário (`.m4a`), esta versão já salva o áudio em arquivo temporário sem lock antes da transcrição local.
