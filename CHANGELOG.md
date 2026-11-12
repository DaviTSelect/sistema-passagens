# Changelog

Formato baseado em [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/). Versões seguem [SemVer](https://semver.org/lang/pt-BR/).

## [Não lançado]

---

## [1.1.1] - 2026-11-12

### Corrigido
- `build/sistema-passagens.spec`: `python312.dll`, `vcruntime140.dll` excluídas do UPX — compressão corrompía a DLL causando crash "Failed to load Python DLL" ao tentar executar

## [1.0.5] - 2026-11-05

### Corrigido
- Passageiros com sobrenome iniciado por `MR`/`MRS` (por exemplo `MRAZ`) eram truncados na comparação, o que podia gerar um `OK` falso. `MS` e `MISS` também passam a ser ignorados.
- Valores com ponto de milhar sem centavos (`1.234`) eram lidos como `1,23`.
- Números inteiros após um rótulo (`Total 2 bilhetes`) eram lidos como valor; agora os centavos são obrigatórios.
- Palavras comuns e nomes de arquivo como `fatura.pdf` eram aceitos como localizador; agora ele precisa estar em maiúsculas.
- O aviso de bilhete sem número afirmava, sem verificar, que o PDF não tinha texto.
- `instalar.py` falhava por faltar `plugins/auto_update.py`, reconstruído a partir do bytecode que estava salvo como `README (2).md` e `README (3).md`.
- `.gitignore`: regras globais `*.csv` e `*.xlsx` substituídas por `saida/*.csv` e `saida/*.xlsx` para não ocultar fixtures de teste.
- `.gitignore`: regra `*.spec` substituída por `*_onefile.spec` e `*_debug.spec`, preservando specs de build intencionais.

### Alterado
- A janela usa `passagem.__version__` em vez de repetir o número da versão.
- A interface passou de Tkinter para PySide6, com etapas numeradas, e a conferência roda em segundo plano, sem travar a janela.
- A interface recebe um único PDF de fatura e salva o relatório em uma pasta, com data e hora no nome do arquivo. `--fatura` também aceita um arquivo.
- `requirements.txt` agora reúne todas as dependências.
- Funções, métodos e testes renomeados para português, com comentários voltados a futuras implementações. Funções longas de `extract.py`, `gui.py`, `planilha.py`, `trechos.py` e `auto_update.py` foram divididas.
- A versão agora é definida somente em `src/passagem/version.py`.
- Dependência `PyPDF2` removida; `extract.py` passa a usar `pypdf` (substituto oficial), já listado como dependência.
- Python mínimo elevado para 3.11 (Python 3.10 encerrou suporte em outubro de 2026).
- CI (`tests.yml`): matriz atualizada para Python 3.11 + 3.12; runner passa a usar `pytest` em vez de `unittest discover`.
- Nome do executável uniformizado para `sistema-passagens.exe` em toda a documentação.

### Adicionado
- Unificação com o projeto de extração de trechos: a janela ganhou a função **Extrair trechos**, que grava uma linha por trecho de voo em uma planilha Excel sem duplicar o que já existe. No terminal, use `--trechos` e `--planilha`.
- Verificação automática de versão ao abrir a janela: a bolinha verde indica versão atualizada confirmada e o executável instala sozinho uma release nova.
- `.github/workflows/release.yml`: release automática ao criar uma tag `v*`, com validação de tag vs `__version__`, build, upload de artefato e draft release.
- `requirements-build.txt`: dependências de build separadas (`pyinstaller`).
- `requirements-test.txt`: dependências de teste separadas (`pytest`, `pytest-qt`).
- `scripts/build.ps1`: script de build PowerShell usado pelo CI.

### Removido
- `interface_conferencia.py` (integrado em `gui.py`), `requirem8ents.txt`, `instalar.py`, `plugins/` e `tests/test_instalar.py`. O atualizador agora faz parte do pacote, em `src/passagem/auto_update.py`.
- Documentos e planilhas de exemplo. Os testes agora criam faturas fictícias em uma pasta temporária.

## [1.0.0] - 2026-10-29

### Adicionado
- Conferência de bilhetes FACTO/GOL e FACTO/LATAM contra a fatura GOL.
- Interface gráfica Tkinter e modo linha de comando (`--bilhetes`, `--fatura`, `--saida`).
- OCR automático para PDFs digitalizados, com caminho do Tesseract configurável por `TESSERACT_CMD`.
- Relatório CSV compatível com Excel.
- Testes de normalização, comparação e conferência ponta a ponta com PDFs sintéticos.
- CI no GitHub Actions, `pyproject.toml` e documentação em `docs/`.

### Alterado
- Código separado em `models`, `extract`, `report`, `conference`, `gui` e `main`.
- PDFs sintéticos movidos de `teste/exemplos_sinteticos/` para `tests/fixtures/`.
- `requirements.txt` movido para a raiz.
- Testes com documentos reais passam a ser pulados quando os arquivos não existem.
- PDFs reais renomeados sem nomes de passageiros; valores esperados movidos para `tests/real_documents.json` (fora do git).
- PDFs sintéticos recriados com dados fictícios (`fatura_sintetica_01.pdf`, `fatura_sintetica_02.pdf`).

### Corrigido
- Localizador do layout FACTO/LATAM com tabela fora de ordem passa a ser lido do conteúdo do PDF, e não do nome do arquivo.
