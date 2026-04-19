@echo off
setlocal

cd /d "%~dp0\.."

echo.
echo ================================================
echo  Applaudo - instalacao no Windows
echo ================================================
echo.

if not exist "requirements.txt" (
  echo ERRO: nao encontrei o arquivo requirements.txt.
  echo Abra este arquivo pela pasta scripts dentro do projeto Applaudo.
  echo.
  pause
  exit /b 1
)

set "PY_CMD="
py -3.12 --version >nul 2>nul
if not errorlevel 1 set "PY_CMD=py -3.12"

if "%PY_CMD%"=="" (
  py -3 --version >nul 2>nul
  if not errorlevel 1 set "PY_CMD=py -3"
)

if "%PY_CMD%"=="" (
  python --version >nul 2>nul
  if not errorlevel 1 set "PY_CMD=python"
)

if "%PY_CMD%"=="" (
  echo ERRO: Python nao encontrado.
  echo Instale o Python 3.12 pelo site https://www.python.org/downloads/
  echo Durante a instalacao, marque a opcao "Add python.exe to PATH".
  echo Depois feche esta janela e execute este instalador novamente.
  echo.
  pause
  exit /b 1
)

echo Python encontrado:
%PY_CMD% --version
echo.

if not exist ".venv\Scripts\python.exe" (
  echo Criando ambiente virtual .venv...
  %PY_CMD% -m venv .venv
  if errorlevel 1 (
    echo.
    echo ERRO: nao foi possivel criar o ambiente virtual.
    echo Confira se o Python foi instalado corretamente.
    echo.
    pause
    exit /b 1
  )
) else (
  echo Ambiente virtual .venv ja existe.
)

echo.
echo Atualizando pip...
".venv\Scripts\python.exe" -m pip install --upgrade pip
if errorlevel 1 (
  echo.
  echo ERRO: falha ao atualizar o pip.
  echo Verifique sua conexao com a internet e tente novamente.
  echo.
  pause
  exit /b 1
)

echo.
echo Instalando bibliotecas do projeto...
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 (
  echo.
  echo ERRO: falha ao instalar as bibliotecas.
  echo Verifique sua conexao com a internet e tente novamente.
  echo.
  pause
  exit /b 1
)

echo.
echo ================================================
echo  Instalacao concluida com sucesso.
echo ================================================
echo.
echo Para abrir o aplicativo, execute:
echo scripts\executar_windows.bat
echo.
pause
