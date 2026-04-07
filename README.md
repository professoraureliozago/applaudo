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

Na aba **Procedimento** agora existem dois modos:

1. **Modo 1: Microfone contínuo + VAD (recomendado)**
   - Inicie o componente contínuo para captar fala por trechos automáticos.
   - Ajuste janela máxima, silêncio de corte e sensibilidade do VAD.
   - O texto é anexado ao rascunho quando a captura lógica estiver ativa.

2. **Fallback manual (`st.audio_input`) e Upload de arquivo**
   - Mantido para contingência, caso o contínuo não esteja disponível.

Você pode repetir várias gravações curtas durante o exame e ir acumulando no rascunho.

## Captura por comando de voz: "gravar" / "parar" (novo)

No modo contínuo (e no fallback manual):


> Observação importante: por segurança do navegador, o início da sessão de microfone ainda depende de interação do usuário no navegador.
> Os comandos de voz (`gravar`/`parar`) controlam o estado de captura lógica do laudo (anexar/pausar transcrição) após o trecho ser processado.

Fluxo recomendado: iniciar contínuo, ditar normalmente e acompanhar **Última transcrição detectada** e **Métricas da sessão**.

- Comandos de início aceitos: **"gravar"**, **"grava"**, **"iniciar"**, **"começar"**.
- Comandos de parada aceitos: **"parar"**, **"pare"**, **"pausar"**.
- Enquanto ativo, cada novo trecho transcrito é **anexado automaticamente** ao rascunho.

Também há botões de fallback (**Ativar captura** / **Pausar captura**) e diagnóstico de comando para conferência rápida.

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


## Rodar pelo VS Code (botão Run/F5)

Incluí a configuração `.vscode/launch.json` para executar Streamlit corretamente pelo VS Code.

- Abra **Run and Debug**
- Escolha **Streamlit: app.py**
- Pressione **F5**

Isso evita precisar digitar manualmente `python -m streamlit run app.py` toda vez.

Também foi adicionada a tarefa `.vscode/tasks.json` para instalar automaticamente os requisitos antes de iniciar (preLaunchTask).

## O que já faz

- Aba **Gerar laudo**:
  - transcreve automaticamente áudio via **faster-whisper local** ou **API OpenAI**,
  - aplica templates por palavras-chave na transcrição,
  - cobre todos os campos do formulário padrão (preparo, duração, altura atingida, segmentos do cólon, conclusão e observações),
  - permite revisão final antes do PDF.
- Aba **Gerenciar modelos**:
  - cria novos modelos por campo,
  - edita modelo salvo ao clicar em **Editar**,
  - exclui com confirmação em **2 cliques**,
  - salva no arquivo `templates/colonoscopia_templates.json`.
- Edição avançada do JSON completo de templates dentro da interface.
- Matching robusto (ignora acentos/maiúsculas/pontuação) para facilitar reconhecimento dos modelos.
- Layout de PDF mais próximo do modelo da clínica (título, cabeçalho clínico e seções em sequência).



## Captura e seleção de imagens do exame

- Abra a aba **Imagens** durante o exame.
- Use a visualização da câmera para capturar e salvar fotos em `captured_images/`.
- A galeria abre na mesma aba com miniaturas e legenda automática para marcar as imagens que irão para o laudo.
- No sidebar, o upload manual para PDF aceita múltiplas imagens de uma vez (sem limite fixo).
- Modo WebRTC custom por componente frontend: stream contínuo com **snapshot por clique direto no frame**.
- A filmagem do exame pode ser gravada no app (iniciar/parar) e vinculada ao exame ativo.
- Ao encerrar a gravação, o app tenta compactar para MP4 (`ffmpeg` quando disponível) e exibe as filmagens salvas com player embutido.
- Mesmo antes de salvar o exame/laudo, filmagens ficam visíveis em rascunho e são vinculadas ao exame no momento do **Salvar exame**.
- Ao iniciar o app/novo exame, mídias temporárias de rascunho são limpas para não exibir gravações antigas.
- As imagens marcadas são anexadas na lateral direita do PDF, em blocos de 4 imagens por página (gerando páginas adicionais conforme necessário).
- A aba mostra quantas imagens estão selecionadas e a estimativa de páginas de imagens no PDF.
- Cada imagem recebe legenda automática (ex.: ceco, pós-polipectomia) exibida abaixo da foto no PDF.
- Imagens e vídeos podem ser excluídos com confirmação em 2 cliques.
- Vídeos salvos aparecem como miniaturas/lista com botão para abrir no reprodutor embutido.

## Cadastro confiável de paciente e exame (SQLite)

- O app agora cria e usa um banco SQLite local em `data/laudo_app.db`.
- Fluxo inicial com dois caminhos: **Novo exame** e **Abrir exame existente**.
- O acionamento dos fluxos é por dois botões dedicados (um para cada função).
- Em **Novo exame**, primeiro salva-se o cadastro do paciente; o exame/laudo é persistido ao clicar em **Salvar exame** na aba de geração.
- Data de nascimento aceita digitação contínua de números e formata automaticamente para `DD/MM/AAAA`.
- Médico solicitante e convênio possuem sugestões com auto preenchimento por histórico já salvo.
- Na revisão por seção, cada campo tem botão **Revisar texto** para aplicar somente modelos daquele campo.
- O arquivo de templates principal é protegido com backup automático (`colonoscopia_templates.backup.json`) para evitar perda acidental de modelos.
- A cada salvamento de templates é criado backup versionado em `templates/backups/` e o arquivo default é sincronizado.
- Não é permitido criar paciente duplicado com a mesma combinação **nome + data de nascimento** (normalização por nome).
- Em **Novo exame**, a idade é calculada automaticamente pela data de nascimento.
- Em **Abrir exame existente**, é possível buscar por nome do paciente, abrir, editar e excluir exame (com confirmação de 2 cliques).
- A busca de paciente ignora acentos para facilitar correspondência parcial por nome.
- Imagens e filmagens ficam vinculadas ao exame ativo.

## Ordem no PDF (modelo da clínica)

O PDF segue o modelo com cabeçalho em laranja, corpo em duas colunas e área no lado direito para blocos de 4 imagens por página, sem limite fixo total.

O PDF segue a ordem:

Indicação, Preparo do paciente, Duração do exame, Altura atingida, Reto, Cólon Sigmóide, Cólon Descendente, Ângulo Esplênico, Cólon Transverso, Ângulo Hepático, Cólon Ascendente, Ceco, Íleo Terminal, Conclusão, Observação 1 e Observação 2.

Somente campos preenchidos são exibidos no documento final.

Rodapé com linha separadora e endereço: Avenida Santos Dumont 2335 - Telefone : 3322 4111 - 99199 6369.

## Próximos passos

- Acionamento automático de transcrição em janelas de tempo (ex.: a cada 20–30 segundos).
- Acionamento hands-free contínuo (sem clique por trecho).
- Inserção automática de imagens do exame no PDF (quando disponíveis).

## Solução de erro no Windows

Se aparecia `Permission denied` no arquivo temporário (`.m4a`), esta versão já salva o áudio em arquivo temporário sem lock antes da transcrição local.
