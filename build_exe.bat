@echo off
setlocal

set "ROOT=%~dp0"
set "PYTHON=%ROOT%venv\Scripts\python.exe"

if not exist "%PYTHON%" (
    echo Ambiente virtual nao encontrado em "%ROOT%venv".
    echo Crie-o com: py -m venv venv
    exit /b 1
)

"%PYTHON%" -m PyInstaller --version >nul 2>&1
if errorlevel 1 (
    echo Instalando PyInstaller no ambiente virtual...
    "%PYTHON%" -m pip install pyinstaller
    if errorlevel 1 exit /b 1
)

"%PYTHON%" -m PyInstaller --noconfirm --clean --onefile --windowed ^
    --name "ConferenciaPassagens" ^
    --icon "%ROOT%logo.ico" ^
    --add-data "%ROOT%logo.ico;." ^
    --collect-all pymupdf ^
    --collect-all rapidocr_onnxruntime ^
    --collect-all pypdfium2 ^
    --collect-all pypdfium2_raw ^
    --paths "%ROOT%src" ^
    --distpath "%ROOT%dist" ^
    --workpath "%ROOT%build" ^
    --specpath "%ROOT%build" ^
    "%ROOT%src\passagem\main.py"

if errorlevel 1 exit /b 1

echo.
echo Executavel criado em: "%ROOT%dist\ConferenciaPassagens.exe"
