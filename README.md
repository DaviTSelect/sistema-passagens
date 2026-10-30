# Central de passagens

Aplicação desktop (Windows) com duas funções para **PDFs de bilhetes aéreos**:

- **Conferir fatura:** compara os bilhetes com a **fatura da agência** e gera um CSV, pronto para o Excel, apontando o que confere, o que diverge e o que não foi encontrado.
- **Extrair trechos:** lê cada trecho de voo e atualiza uma planilha Excel, sem duplicar o que já existe.

![Python](https://img.shields.io/badge/python-3.10%2B-blue) ![Plataforma](https://img.shields.io/badge/plataforma-Windows-lightgrey)

## Como funciona a conferência

1. Lê todos os PDFs de uma pasta de bilhetes e de uma pasta de faturas.
2. Extrai número do bilhete, localizador, passageiro, voos e valores (tarifa, taxas, fee, total), usando o texto do PDF ou OCR quando o PDF é digitalizado.
3. Cruza cada bilhete com a fatura pelo **número do bilhete** (ou pelo localizador, se o número não bater).
4. Gera um CSV com uma linha por campo conferido e o resultado: `OK`, `DIVERGENTE`, `NÃO ENCONTRADO` ou `NÃO CONFERIDO`.

Funciona pela **interface gráfica** (PySide6) ou pela **linha de comando**.

## Início rápido

Pré-requisitos: Python 3.10+ e, só para PDFs digitalizados, o [Tesseract OCR](https://github.com/UB-Mannheim/tesseract/wiki) com o idioma português.

```powershell
git clone <url-do-repositorio>
cd "Extrair dados de passagem"
py -m venv venv
.\venv\Scripts\python.exe -m pip install -r requirements.txt

# Interface gráfica
.\venv\Scripts\python.exe src\passagem\main.py

# Linha de comando
.\venv\Scripts\python.exe src\passagem\main.py --bilhetes .\pdf --fatura .\fatura --saida .\conferencia.csv
.\venv\Scripts\python.exe src\passagem\main.py --trechos .\pdf --planilha .\PlanilhaPassagens_por_trecho.xlsx
```

Na janela, escolha a função no topo do cartão. Em **Conferir fatura**, indique a pasta dos bilhetes, o PDF da fatura e a pasta do resultado; o relatório é salvo como `conferencia_AAAAMMDD_HHMMSS.csv`. Em **Extrair trechos**, indique a pasta dos PDFs e a planilha, nova ou existente.

## Atualização automática

Ao abrir, a janela consulta a última *Release* do GitHub e mostra o status no canto superior direito:

| Bolinha | Significado |
|---|---|
| Verde | Confirmado: esta é a versão mais recente |
| Amarela | Verificando, baixando ou com versão nova disponível |
| Cinza | Não foi possível verificar, ou o repositório não está configurado |

O executável baixa a versão nova, confere o SHA-256 e reinicia sozinho. As releases são publicadas em [github.com/DaviTSelect/sistema-passagens](https://github.com/DaviTSelect/sistema-passagens/releases); veja [como publicar uma versão](docs/desenvolvimento.md#publicar-uma-nova-versão).

## Exemplo de saída

| numero_bilhete | campo | valor_bilhete | valor_fatura | resultado | divergencia |
|---|---|---|---|---|---|
| 1234567890 | Total | R$ 1.250,00 | R$ 1.250,00 | OK | |
| 1234567890 | Passageiro | SILVA/JOAO | SILVA/JOSE | DIVERGENTE | Bilhete: SILVA/JOAO; fatura: SILVA/JOSE |
| 9876543210 | Localizador | ABC123 | SEM CORRESPONDÊNCIA | NÃO ENCONTRADO | Bilhete não localizado na fatura |

O CSV usa `;` como separador e UTF-8 com BOM, para abrir direto no Excel em português. Detalhes de cada coluna e regra em [docs/uso.md](docs/uso.md).

## Modelos de documento suportados

| Tipo | Modelo |
|---|---|
| Bilhete | FACTO/GOL, FACTO/LATAM |
| Fatura | Fatura GOL (TARIFA / TAXA / FEE / SUB-TOTAL) |

Para adicionar um novo modelo, siga [docs/desenvolvimento.md](docs/desenvolvimento.md#como-adicionar-um-novo-modelo-de-pdf).

## Estrutura do projeto

```
├── src/passagem/
│   ├── main.py          # Ponto de entrada (CLI ou interface)
│   ├── gui.py           # Interface PySide6
│   ├── auto_update.py   # Verificação e instalação de novas versões
│   ├── conference.py    # Orquestração: lê PDFs, cruza e grava o CSV
│   ├── extract.py       # Leitura de PDF/OCR e extração dos campos
│   ├── report.py        # Comparação campo a campo e escrita do CSV
│   ├── trechos.py       # Extração dos trechos de voo dos PDFs
│   ├── planilha.py      # Criação e atualização da planilha Excel
│   └── models.py        # Dataclasses Ticket e InvoiceEntry
├── tests/               # Testes automatizados
├── docs/                # Documentação detalhada
├── build_exe.bat        # Gera o executável Windows
├── logo.ico             # Ícone da janela e do executável
├── pyproject.toml
└── requirements.txt
```

A arquitetura e o fluxo de dados estão em [docs/arquitetura.md](docs/arquitetura.md).

## Gerar o executável

```powershell
.\build_exe.bat
```

Cria `dist\ConferenciaPassagens.exe` (arquivo único, sem console, com o ícone `logo.ico`). O PyInstaller é instalado no `venv` se ainda não estiver.

## Testes

```powershell
$env:PYTHONPATH = "src"
.\venv\Scripts\python.exe -m unittest discover -s tests -v
```

Os testes com PDFs reais só rodam se as pastas `pdf\` e `fatura\` existirem localmente; caso contrário são pulados. O CI do GitHub Actions roda os demais a cada push.

## Privacidade

As pastas `pdf\` e `fatura\`, os CSVs gerados e os executáveis estão no `.gitignore`. A pasta `projeto\`, com o projeto de origem da extração, também está. **Não versione bilhetes, faturas ou relatórios reais**: eles contêm nomes de passageiros e valores. O repositório não traz documentos de exemplo: os testes criam faturas fictícias na hora (veja `tests/generate_example_invoices.py`).

## Documentação

- [Guia de uso](docs/uso.md): instalação, execução, OCR e leitura do relatório
- [Arquitetura](docs/arquitetura.md): módulos, fluxo de dados e decisões
- [Desenvolvimento](docs/desenvolvimento.md): ambiente, testes, padrões e como suportar novos modelos
- [Roadmap](docs/roadmap.md): próximas implementações sugeridas
- [Changelog](CHANGELOG.md)
