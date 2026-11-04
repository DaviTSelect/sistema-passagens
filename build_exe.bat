@echo off
setlocal

set "ROOT=%~dp0"
set "PYTHON=%ROOT%venv\Scripts\python.exe"
set "VERSION_FILE=%ROOT%src\passagem\version.py"

if not exist "%PYTHON%" (
    echo Ambiente virtual nao encontrado em "%ROOT%venv".
    echo Crie-o com: py -m venv venv
    exit /b 1
)

:: Le a versao atual do version.py
for /f "tokens=3 delims== " %%v in ('findstr "__version__" "%VERSION_FILE%"') do set "VERSAO=%%~v"
if "%VERSAO%"=="" (
    echo Nao foi possivel ler __version__ de version.py
    exit /b 1
)

echo Versao: %VERSAO%

"%PYTHON%" -m PyInstaller --version >nul 2>&1
if errorlevel 1 (
    echo Instalando PyInstaller no ambiente virtual...
    "%PYTHON%" -m pip install pyinstaller
    if errorlevel 1 exit /b 1
)

"%PYTHON%" -m PyInstaller --noconfirm --clean --onefile --windowed ^
    --name "sistema-passagens" ^
    --icon "%ROOT%logo.ico" ^
    --add-data "%ROOT%logo.ico;." ^
    --collect-all pymupdf ^
    --collect-all rapidocr_onnxruntime ^
    --collect-all pypdfium2 ^
    --collect-all pypdfium2_raw ^
    --paths "%ROOT%src" ^
    --distpath "%ROOT%dist\v%VERSAO%" ^
    --workpath "%ROOT%build" ^
    --specpath "%ROOT%build" ^
    "%ROOT%src\passagem\main.py"

if errorlevel 1 exit /b 1

echo.
echo Executavel criado em: "%ROOT%dist\v%VERSAO%\sistema-passagens.exe"
