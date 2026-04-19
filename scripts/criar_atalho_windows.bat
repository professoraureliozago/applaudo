@echo off
setlocal

cd /d "%~dp0\.."

echo.
echo ================================================
echo  Applaudo - criar atalho na Area de Trabalho
echo ================================================
echo.

if not exist "scripts\executar_windows.bat" (
  echo ERRO: nao encontrei scripts\executar_windows.bat.
  echo Execute este arquivo dentro da pasta scripts do projeto Applaudo.
  echo.
  pause
  exit /b 1
)

set "APPLAUDO_TARGET=%CD%\scripts\executar_windows.bat"
set "APPLAUDO_WORKDIR=%CD%"
set "APPLAUDO_SHORTCUT=%USERPROFILE%\Desktop\Applaudo.lnk"

powershell -NoProfile -ExecutionPolicy Bypass -Command "$shell = New-Object -ComObject WScript.Shell; $shortcut = $shell.CreateShortcut($env:APPLAUDO_SHORTCUT); $shortcut.TargetPath = $env:ComSpec; $shortcut.Arguments = '/c ""' + $env:APPLAUDO_TARGET + '""'; $shortcut.WorkingDirectory = $env:APPLAUDO_WORKDIR; $shortcut.IconLocation = $env:SystemRoot + '\System32\shell32.dll,220'; $shortcut.Save()"

if errorlevel 1 (
  echo.
  echo ERRO: nao foi possivel criar o atalho.
  echo Tente executar este arquivo novamente.
  echo.
  pause
  exit /b 1
)

echo Atalho criado com sucesso:
echo %APPLAUDO_SHORTCUT%
echo.
echo Agora voce pode abrir o Applaudo pelo icone na Area de Trabalho.
echo.
pause
