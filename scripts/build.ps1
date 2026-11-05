param([string]$OutputDir = "dist")
$ErrorActionPreference = 'Stop'
$env:PYTHONPATH = "src"
$version = python -c "from passagem.version import __version__; print(__version__)"
if (-not $version) { Write-Error "Nao foi possivel ler __version__"; exit 1 }
Write-Host "Versao: $version"
python -m PyInstaller --noconfirm --clean --onefile --windowed `
    --name "sistema-passagens" `
    --icon "logo.ico" `
    --add-data "logo.ico;." `
    --collect-all pymupdf `
    --collect-all rapidocr_onnxruntime `
    --collect-all pypdfium2 `
    --collect-all pypdfium2_raw `
    --paths "src" `
    --distpath $OutputDir `
    --workpath "build" `
    --specpath "build" `
    "src\passagem\main.py"
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
Write-Host "Executavel criado em: $OutputDir\sistema-passagens.exe"
