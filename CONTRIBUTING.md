# Como Contribuir

## Configurar Ambiente de Desenvolvimento

```powershell
git clone https://github.com/DaviTSelect/sistema-passagens.git
cd "sistema-passagens"

python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## Executar os Testes

```powershell
set PYTHONPATH=src
python -m pytest tests -v
```

## Build (Executável)

```powershell
pip install -r requirements.txt  # inclui pyinstaller
.\build_exe.bat
```

## Convenção de Commits

Usar prefixos [Conventional Commits](https://www.conventionalcommits.org/):

| Prefixo | Uso |
|---------|-----|
| `feat:` | Nova funcionalidade |
| `fix:` | Correção de bug |
| `docs:` | Apenas documentação |
| `refactor:` | Refatoração |
| `test:` | Testes |
| `chore:` | Manutenção |
| `release:` | Preparação de release (`release: vX.Y.Z`) |

## Processo de Release

1. Atualizar versão em `src/passagem/version.py`
2. Mover `[Não lançado]` para `[x.y.z] - YYYY-MM-DD` no CHANGELOG
3. Commitar: `git commit -m "release: vX.Y.Z"`
4. Tag: `git tag vX.Y.Z && git push origin vX.Y.Z`
5. GitHub Actions cria a release automaticamente

## Referência

Ver `docs/desenvolvimento.md` para detalhes de desenvolvimento.
