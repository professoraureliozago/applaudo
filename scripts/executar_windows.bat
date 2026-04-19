@echo off
setlocal

cd /d "%~dp0\.."

echo.
echo ================================================
echo  Applaudo - iniciar aplicativo
echo ================================================
echo.

if not exist ".venv\Scripts\python.exe" (
  echo O ambiente virtual ainda nao existe.
  echo Vou executar a instalacao agora.
  echo.
  call "%~dp0instalar_windows.bat"
  if errorlevel 1 (
    echo.
    echo A instalacao falhou. O aplicativo nao sera iniciado.
    echo.
    pause
    exit /b 1
  )
)

echo Abrindo o Applaudo no navegador...
echo Se o navegador nao abrir sozinho, acesse:
echo http://localhost:8501
echo.

".venv\Scripts\python.exe" -m streamlit run app.py

echo.
echo O aplicativo foi encerrado.
pause
