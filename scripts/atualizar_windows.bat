@echo off
setlocal

cd /d "%~dp0\.."

echo.
echo ================================================
echo  Applaudo - atualizar projeto
echo ================================================
echo.

if exist ".git" (
  git --version >nul 2>nul
  if not errorlevel 1 (
    echo Baixando atualizacoes do GitHub...
    git pull
    if errorlevel 1 (
      echo.
      echo AVISO: nao foi possivel atualizar pelo git pull.
      echo Voce ainda pode reinstalar as bibliotecas abaixo.
      echo.
    )
  ) else (
    echo Git nao encontrado. Pulando atualizacao pelo GitHub.
  )
) else (
  echo Esta pasta nao parece ser um clone git. Pulando git pull.
)

if not exist ".venv\Scripts\python.exe" (
  echo.
  echo Ambiente virtual nao encontrado. Executando instalacao completa...
  call "%~dp0instalar_windows.bat"
  exit /b %ERRORLEVEL%
)

echo.
echo Atualizando bibliotecas...
".venv\Scripts\python.exe" -m pip install --upgrade pip
if errorlevel 1 (
  echo.
  echo ERRO: falha ao atualizar pip.
  echo.
  pause
  exit /b 1
)

".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 (
  echo.
  echo ERRO: falha ao atualizar bibliotecas.
  echo.
  pause
  exit /b 1
)

echo.
echo Atualizacao concluida.
echo Para abrir o app, execute scripts\executar_windows.bat
echo.
pause
