"""Atualizador Windows/PyInstaller --onefile para GitHub Releases públicos.

Fluxo: ``buscar_release`` consulta a última versão, ``tem_versao_nova`` compara
com a atual e ``instalar`` baixa o executável e agenda a troca. A janela chama
essas funções em ``gui.App._verificar_atualizacoes``.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import urllib.request

# Repositório que publica as releases, no formato "usuario/repositorio".
# O repositório precisa ser público; a API do GitHub não exige autenticação para releases públicas.
REPO_GITHUB = 'DaviTSelect/sistema-passagens'
NOME_EXE = 'ConferenciaPassagens.exe'

_USER_AGENT = 'kit-funcoes-updater/1.0'

# Roda depois que o programa fecha, pois o Windows não deixa substituir um EXE em uso.
# Em caso de falha, restaura o executável antigo e o abre de novo.
_SCRIPT_TROCA = '''param([string]$Origem, [string]$Destino, [int]$PIDAntigo)
$ErrorActionPreference = 'Stop'
try { Wait-Process -Id $PIDAntigo -ErrorAction SilentlyContinue } catch {}
$Backup = "$Destino.bak"
for ($tentativa = 0; $tentativa -lt 60; $tentativa++) {
    try {
        if (Test-Path -LiteralPath $Backup) { Remove-Item -LiteralPath $Backup -Force }
        if (Test-Path -LiteralPath $Destino) { Move-Item -LiteralPath $Destino -Destination $Backup }
        Move-Item -LiteralPath $Origem -Destination $Destino
        Start-Process -FilePath $Destino
        exit 0
    } catch {
        if (-not (Test-Path -LiteralPath $Destino) -and (Test-Path -LiteralPath $Backup)) {
            try { Move-Item -LiteralPath $Backup -Destination $Destino } catch {}
        }
        Start-Sleep -Seconds 1
    }
}
if (Test-Path -LiteralPath $Destino) { Start-Process -FilePath $Destino }
exit 1
'''


def _versao(tag: str) -> tuple[int, ...]:
    """Converte ``v1.2.3`` em ``(1, 2, 3)`` para comparar versões como números."""
    v = tag.removeprefix('v')
    if not v or any(not p.isdigit() for p in v.split('.')):
        raise ValueError(f'Versão inválida: {tag!r}. Use versões numéricas, ex.: v1.2.3')
    return tuple(int(p) for p in v.split('.'))


def pode_instalar() -> bool:
    """Só o executável no Windows pode se substituir; em desenvolvimento apenas consulta."""
    return sys.platform == 'win32' and bool(getattr(sys, 'frozen', False))


def buscar_release(repo: str) -> dict:
    """Consulta a última release publicada. Lança exceção se não conseguir confirmar."""
    url = f'https://api.github.com/repos/{repo}/releases/latest'
    req = urllib.request.Request(
        url,
        headers={'Accept': 'application/vnd.github+json', 'User-Agent': _USER_AGENT},
    )
    with urllib.request.urlopen(req, timeout=12) as resposta:
        return json.load(resposta)


def tem_versao_nova(release: dict, versao_atual: str) -> bool:
    """Indica se a release publicada é mais recente que a versão em execução."""
    return _versao(release['tag_name']) > _versao(versao_atual)


def instalar(release: dict, nome_exe: str) -> None:
    """Baixa o EXE, confere o SHA-256 e agenda a troca para quando o processo encerrar."""
    asset = next((a for a in release.get('assets', []) if a['name'] == nome_exe), None)
    if asset is None:
        raise RuntimeError(f'Release sem {nome_exe}')
    esperado = asset.get('digest', '')
    if not esperado.startswith('sha256:'):
        raise RuntimeError('Release sem digest SHA-256; atualização recusada')
    hash_esperado = esperado.split(':', 1)[1].lower()
    exe_atual = Path(sys.executable).resolve()
    if exe_atual.name.lower() != nome_exe.lower():
        raise RuntimeError(f'O executável instalado deve se chamar {nome_exe}')
    pasta = Path(tempfile.mkdtemp(prefix='kit_update_'))
    baixado = pasta / nome_exe
    _baixar_exe(asset['browser_download_url'], baixado, hash_esperado)
    _agendar_troca(pasta, baixado, exe_atual)


def _baixar_exe(url: str, destino: Path, hash_esperado: str) -> None:
    """Salva o arquivo em ``destino`` e o apaga se o SHA-256 não conferir."""
    h = hashlib.sha256()
    req_asset = urllib.request.Request(url, headers={'User-Agent': _USER_AGENT})
    with urllib.request.urlopen(req_asset, timeout=60) as resposta, open(destino, 'wb') as f:
        while bloco := resposta.read(1048576):
            f.write(bloco)
            h.update(bloco)
    if h.hexdigest() != hash_esperado:
        destino.unlink(missing_ok=True)
        raise RuntimeError('SHA-256 do EXE baixado não confere')


def _agendar_troca(pasta: Path, baixado: Path, exe_atual: Path) -> None:
    """Inicia o script que substitui o executável assim que este processo terminar."""
    script = pasta / 'trocar.ps1'
    script.write_text(_SCRIPT_TROCA, encoding='utf-8-sig')
    # Sem o reset, o novo EXE herdaria as variáveis do --onefile antigo e tentaria
    # usar a pasta temporária dele, que já terá sido apagada.
    subprocess.Popen(
        [
            'powershell.exe', '-NoProfile', '-NonInteractive', '-ExecutionPolicy', 'Bypass',
            '-File', str(script), '-Origem', str(baixado), '-Destino', str(exe_atual),
            '-PIDAntigo', str(os.getpid()),
        ],
        creationflags=subprocess.CREATE_NO_WINDOW,
        close_fds=True,
        env={**os.environ, 'PYINSTALLER_RESET_ENVIRONMENT': '1'},
    )
