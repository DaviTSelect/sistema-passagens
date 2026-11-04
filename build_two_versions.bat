@echo off
setlocal

set "ROOT=%~dp0"
set "PYTHON=%ROOT%venv\Scripts\python.exe"
set "VERSION_FILE=%ROOT%src\passagem\version.py"

if not exist "%PYTHON%" (
    echo Ambiente virtual nao encontrado em "%ROOT%venv".
    exit /b 1
)

:: Le a versao atual do version.py
for /f "tokens=3 delims== " %%v in ('findstr "__version__" "%VERSION_FILE%"') do set "NOVA_VERSAO=%%~v"
if "%NOVA_VERSAO%"=="" (
    echo Nao foi possivel ler __version__ de version.py
    exit /b 1
)

set "VERSAO_ANTIGA=0.0.2"

echo ============================================================
echo  Versao antiga : %VERSAO_ANTIGA%
echo  Versao nova   : %NOVA_VERSAO%  (lida de version.py)
echo ============================================================
echo.

echo ============================================================
echo  BUILD v%VERSAO_ANTIGA%  (versao antiga para teste de atualizacao)
echo ============================================================
echo __version__ = "%VERSAO_ANTIGA%"> "%VERSION_FILE%"

"%PYTHON%" -m PyInstaller --noconfirm --clean --onefile --windowed ^
    --name "sistema-passagens" ^
    --icon "%ROOT%logo.ico" ^
    --add-data "%ROOT%logo.ico;." ^
    --collect-all pymupdf ^
    --collect-all rapidocr_onnxruntime ^
    --collect-all pypdfium2 ^
    --collect-all pypdfium2_raw ^
    --paths "%ROOT%src" ^
    --distpath "%ROOT%dist\v%VERSAO_ANTIGA%" ^
    --workpath "%ROOT%build" ^
    --specpath "%ROOT%build" ^
    "%ROOT%src\passagem\main.py"

if errorlevel 1 (
    echo FALHA no build v%VERSAO_ANTIGA%
    goto :restaurar
)

echo.
echo ============================================================
echo  BUILD v%NOVA_VERSAO%  (versao nova que vai no GitHub Release)
echo ============================================================
echo __version__ = "%NOVA_VERSAO%"> "%VERSION_FILE%"

"%PYTHON%" -m PyInstaller --noconfirm --clean --onefile --windowed ^
    --name "sistema-passagens" ^
    --icon "%ROOT%logo.ico" ^
    --add-data "%ROOT%logo.ico;." ^
    --collect-all pymupdf ^
    --collect-all rapidocr_onnxruntime ^
    --collect-all pypdfium2 ^
    --collect-all pypdfium2_raw ^
    --paths "%ROOT%src" ^
    --distpath "%ROOT%dist\v%NOVA_VERSAO%" ^
    --workpath "%ROOT%build" ^
    --specpath "%ROOT%build" ^
    "%ROOT%src\passagem\main.py"

if errorlevel 1 (
    echo FALHA no build v%NOVA_VERSAO%
    goto :restaurar
)

echo.
echo ============================================================
echo  CONCLUIDO
echo   Antiga : "%ROOT%dist\v%VERSAO_ANTIGA%\sistema-passagens.exe"
echo   Nova   : "%ROOT%dist\v%NOVA_VERSAO%\sistema-passagens.exe"
echo ============================================================
echo.
echo Como usar:
echo  1. Suba dist\v%NOVA_VERSAO%\sistema-passagens.exe no GitHub Release com tag v%NOVA_VERSAO%
echo  2. Execute dist\v%VERSAO_ANTIGA%\sistema-passagens.exe na maquina de teste
echo  3. O app ira detectar v%NOVA_VERSAO%, baixar e reiniciar automaticamente

:restaurar
echo __version__ = "%NOVA_VERSAO%"> "%VERSION_FILE%"
