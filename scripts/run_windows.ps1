Param(
  [string]$PythonExe = "python"
)

$ErrorActionPreference = "Stop"

if (!(Test-Path ".venv")) {
  & $PythonExe -m venv .venv
}

& .\.venv\Scripts\python.exe -m pip install --upgrade pip
& .\.venv\Scripts\python.exe -m pip install -r requirements.txt

Write-Host "Iniciando app..."
& .\.venv\Scripts\python.exe -m streamlit run app.py
