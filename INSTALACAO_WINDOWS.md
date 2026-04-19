# Instalacao do Applaudo no Windows

Este guia e para instalar e abrir o Applaudo em um notebook com Windows, mesmo sem experiencia com programacao.

## Visao geral

Voce vai fazer quatro coisas:

1. Instalar o Python.
2. Baixar ou clonar o projeto Applaudo.
3. Executar o instalador do projeto.
4. Abrir o aplicativo pelo atalho de execucao.

Depois da primeira instalacao, o uso diario fica simples: basta abrir `scripts\executar_windows.bat`.

## 1. Instalar o Python

1. Abra o site oficial: https://www.python.org/downloads/
2. Clique no botao para baixar o Python para Windows.
3. Abra o instalador baixado.
4. Na primeira tela do instalador, marque a opcao:

```text
Add python.exe to PATH
```

5. Depois clique em `Install Now`.
6. Aguarde terminar.
7. Clique em `Close`.

Essa opcao do PATH e importante. Se ela nao for marcada, o Windows pode nao encontrar o Python depois.

## 2. Conferir se o Python instalou

1. Aperte `Windows + R`.
2. Digite `cmd`.
3. Aperte `Enter`.
4. Na janela preta, digite:

```bat
python --version
```

5. Aperte `Enter`.

Se aparecer algo parecido com `Python 3.12.x`, esta correto.

Agora digite:

```bat
python -m pip --version
```

Se aparecer uma linha com `pip`, tambem esta correto.

## 3. Baixar o projeto

Voce pode usar uma destas duas formas.

### Forma A: pelo GitHub Desktop ou VS Code

Clone este repositorio:

```text
https://github.com/professoraureliozago/applaudo.git
```

Depois abra a pasta clonada no VS Code.

### Forma B: por arquivo ZIP

1. Abra o repositorio no GitHub.
2. Clique em `Code`.
3. Clique em `Download ZIP`.
4. Extraia o ZIP em uma pasta facil, por exemplo:

```text
C:\Applaudo
```

Se usar ZIP, o botao de atualizar pelo GitHub nao vai funcionar automaticamente. O aplicativo vai funcionar normalmente, mas atualizacoes futuras devem ser baixadas de novo ou feitas por Git.

## 4. Instalar as bibliotecas do projeto

1. Abra a pasta do projeto.
2. Entre na pasta `scripts`.
3. De dois cliques em:

```text
instalar_windows.bat
```

4. Aguarde. Na primeira vez pode demorar varios minutos, porque o Windows vai baixar e instalar as bibliotecas.
5. Quando aparecer `Instalacao concluida com sucesso`, aperte qualquer tecla para fechar.

O instalador cria uma pasta chamada `.venv`. Essa pasta guarda as bibliotecas do Applaudo sem misturar com outros programas do computador.

## 5. Abrir o aplicativo

1. Abra a pasta do projeto.
2. Entre na pasta `scripts`.
3. De dois cliques em:

```text
executar_windows.bat
```

4. Aguarde alguns segundos.
5. O navegador deve abrir automaticamente.

Se o navegador nao abrir sozinho, abra o Chrome ou Edge e acesse:

```text
http://localhost:8501
```

Enquanto estiver usando o Applaudo, deixe a janela preta aberta. Ela e o servidor local do aplicativo.

Para fechar o aplicativo, feche a janela preta ou aperte `Ctrl + C` dentro dela.

## 6. Atualizar o projeto depois

Quando houver uma nova versao do Applaudo:

1. Abra a pasta do projeto.
2. Entre na pasta `scripts`.
3. De dois cliques em:

```text
atualizar_windows.bat
```

4. Aguarde terminar.
5. Depois abra novamente com `executar_windows.bat`.

Esse atualizador funciona melhor quando o projeto foi clonado com Git. Se o projeto foi baixado por ZIP, prefira baixar um ZIP novo quando houver atualizacao.

## 7. Como abrir no VS Code

1. Abra o VS Code.
2. Clique em `File`.
3. Clique em `Open Folder`.
4. Selecione a pasta do projeto Applaudo.
5. Clique em `Select Folder`.

Para abrir o terminal no VS Code:

1. Clique em `Terminal`.
2. Clique em `New Terminal`.

Se quiser rodar pelo terminal do VS Code, use:

```bat
.\scripts\executar_windows.bat
```

## 8. Erros comuns

### Python nao encontrado

Mensagem comum:

```text
Python nao encontrado
```

Solucao:

1. Instale o Python novamente.
2. Marque `Add python.exe to PATH`.
3. Feche e abra o terminal novamente.
4. Execute `instalar_windows.bat` de novo.

### Streamlit nao encontrado

Mensagem comum:

```text
No module named streamlit
```

Solucao:

Execute novamente:

```text
scripts\instalar_windows.bat
```

Depois abra com:

```text
scripts\executar_windows.bat
```

### O navegador nao abriu

Solucao:

Abra manualmente:

```text
http://localhost:8501
```

### A instalacao falhou baixando bibliotecas

Isso geralmente e internet, bloqueio de rede ou antivirus.

Tente:

1. Conferir a internet.
2. Fechar e abrir novamente `instalar_windows.bat`.
3. Se estiver em rede de hospital ou clinica, testar em outra rede.

## 9. Onde ficam os dados

O banco local do aplicativo fica em:

```text
data\laudo_app.db
```

As imagens capturadas ficam em:

```text
captured_images\
```

As filmagens ficam em:

```text
captured_videos\
```

Para testar em outro notebook com os mesmos dados, faca backup dessas pastas e arquivos antes de trocar de computador.

## 10. Observacao importante

Esta opcao nao e um instalador profissional ainda. Ela e uma instalacao assistida por scripts, ideal para teste pratico no notebook.

Depois que o fluxo estiver validado na pratica, podemos evoluir para um instalador mais completo, com atalho na area de trabalho e empacotamento mais automatico.
