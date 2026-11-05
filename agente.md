# Contexto do Projeto para Agente IA

## O que este projeto faz

Confere PDFs de bilhetes aéreos contra faturas de agência de viagem e gera um relatório CSV com as discrepâncias. Também extrai trechos de voo (origem/destino/data/valor) de PDFs de fatura para uma planilha Excel consolidada.

## Tecnologias

- Python 3.11+ com layout `src/passagem/`
- PySide6 para interface gráfica
- PyMuPDF + pypdf + RapidOCR para leitura de PDFs
- openpyxl para Excel
- PyInstaller para build do executável
- pytest para testes (10 arquivos de teste)

## Arquitetura

```
src/passagem/
├── main.py         # inicializa QApplication e abre a janela
├── gui.py          # janela principal PySide6 (UI apenas)
├── extract.py      # extração de dados de PDFs de fatura
├── conference.py   # comparação fatura vs. bilhetes
├── trechos.py      # extração de trechos de voo
├── planilha.py     # leitura/escrita de Excel
├── report.py       # geração de relatório CSV
├── auto_update.py  # verificação e instalação de atualizações
├── models.py       # dataclasses (Passagem, Trecho, etc.)
├── version.py      # __version__ = "x.y.z"  (legado; sem VERSION nem REPOSITORY)
└── __init__.py
```

## Como executar

```powershell
# Desenvolvimento
set PYTHONPATH=src
python main.py

# Testes
set PYTHONPATH=src
python -m pytest tests -v

# Build executável
.\build_exe.bat
```

## Padrões do projeto

- Código em português (variáveis, funções, comentários)
- GUI não contém lógica de negócio — usa sinais QThread
- Versão única em `src/passagem/version.py`
- Commits com prefixo convencional
- Atualização automática via GitHub Releases API + PowerShell EXE swap

## Fluxo principal

```
Usuário abre o app
  └─► auto_update.py verifica versão no GitHub (background)
  └─► Usuário seleciona PDF de fatura + pasta de bilhetes
        └─► extract.py extrai dados da fatura
        └─► conference.py compara com bilhetes
              └─► report.py gera CSV com resultado
```

## O que NÃO fazer

- Não commitar PDFs reais (dados de viagem são sensíveis)
- Não commitar a pasta `venv/`, `build/`, `dist/`
- Não modificar `src/passagem/version.py` sem atualizar o CHANGELOG
- O build usa `build_exe.bat` — não usar pyinstaller diretamente

## Referência de padrão corporativo

[PADRAO_EMPRESA/specs/02_ARQUITETURA.spec.md](../PADRAO_EMPRESA/specs/02_ARQUITETURA.spec.md)
