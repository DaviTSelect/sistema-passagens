# Arquitetura

## Visão geral

```
            ┌──────────┐      ┌──────────┐
            │  main.py │─────▶│  gui.py  │   (sem argumentos)
            └────┬─────┘      └────┬─────┘
   (CLI) ────────┤                 │
                 ▼                 ▼
            ┌───────────────────────────┐
            │      conference.py        │  executar_conferencia()
            └────┬──────────────────┬───┘
                 ▼                  ▼
          ┌────────────┐     ┌────────────┐
          │ extract.py │     │ report.py  │
          └─────┬──────┘     └─────┬──────┘
                └──────┬───────────┘
                       ▼
                 ┌───────────┐
                 │ models.py │  Ticket, InvoiceEntry
                 └───────────┘
```

As dependências apontam sempre para baixo: `models.py` não conhece ninguém, e a regra de negócio (`conference`, `extract`, `report`) não conhece a interface. Por isso a mesma conferência serve à janela, ao terminal e a qualquer integração futura.

## Módulos

| Módulo | Responsabilidade |
|---|---|
| `models.py` | Dataclasses imutáveis `Ticket` (bilhete) e `InvoiceEntry` (lançamento na fatura). Valores monetários em `Decimal`. |
| `extract.py` | Lê o texto do PDF (pypdf), recorre a OCR (PyMuPDF + Tesseract) quando necessário e extrai os campos com expressões regulares. Expõe `ler_bilhete()` e `ler_fatura()`. |
| `report.py` | `comparar()` gera as linhas do relatório para um bilhete; `gravar_csv()` grava o CSV. Define os status e a tolerância do total. |
| `conference.py` | `executar_conferencia()` lista os PDFs, lê bilhetes e faturas, cruza os registros e grava o relatório. Retorna `ConferenceResult` com a contagem e os avisos. |
| `gui.py` | Janela PySide6 com a paleta visual padrão dos painéis de automação. Roda a conferência e a verificação de versão em threads, falando com a tela por sinais. |
| `trechos.py` | Extrai um registro por trecho de voo (pypdf, com OCR RapidOCR nos PDFs FACTO digitalizados). `executar_extracao()` coordena a pasta e grava a planilha. É independente de `extract.py`, pois os dois leem campos e modelos diferentes. |
| `planilha.py` | Valida os registros e cria ou atualiza a aba `Trechos` do Excel, usando bilhete e trecho como chave. |
| `auto_update.py` | Consulta a última release do GitHub, baixa o EXE, confere o SHA-256 e agenda a troca do executável. |
| `main.py` | Ponto de entrada: interpreta argumentos e decide entre CLI e interface. Também é o script de entrada do PyInstaller. |

## Fluxo de dados

1. `executar_conferencia()` lista `*.pdf` das duas pastas (erro se alguma estiver vazia).
2. Cada bilhete passa por `ler_bilhete()` → `Ticket`. Duplicados pelo número são descartados.
3. Cada fatura passa por `ler_fatura()` → lista de `InvoiceEntry` (um por bilhete na fatura).
4. Os lançamentos são indexados por número e por localizador.
5. Para cada bilhete, `comparar()` gera cinco linhas (número, localizador, passageiro, voos, total).
6. `gravar_csv()` grava tudo em um único CSV.

Falhas por arquivo viram avisos em `ConferenceResult.warnings`; só a ausência total de dados interrompe a execução.

## Extração de texto

`ler_pdf()` tenta primeiro o texto selecionável. Se houver menos de `MIN_SELECTABLE_CHARS` (40) caracteres, executa OCR e fica com o resultado mais longo. Isso cobre PDFs que misturam páginas digitalizadas e textuais.

## Extração de campos

Cada campo tem uma função dedicada em `extract.py`, que testa padrões **do mais específico para o mais genérico**:

| Função | Estratégia |
|---|---|
| `_buscar_numero_bilhete` | Número após rótulo (“Bilhete”, “Ticket”…), depois 13 dígitos isolados, depois 10–12 |
| `_buscar_localizador` | Código de 6 caracteres logo após o número do bilhete, depois após rótulos, depois no nome do arquivo |
| `_buscar_passageiro` | Após `ADT -` ou `Passageiro:`, depois pelo nome do arquivo |
| `_buscar_voos` | Sigla de companhia + número; inclui correções para artefatos conhecidos do PDF LATAM |
| `_extrair_tarifas` | Seção “Tarifamento”, valores rotulados e layouts tabulares (cabeçalho em uma linha, valores na seguinte) |
| `_extrair_subtotal_agencia` | Layout G3 de fatura: TARIFA / TAXA / FEE / SUB-TOTAL em linhas |

Cada regra de layout tem um comentário com o exemplo do texto que ela trata. Mantenha esse padrão ao adicionar novas.

## Decisões de projeto

- **`Decimal` para dinheiro**: evita erros de arredondamento de `float`.
- **Campos vazios em vez de exceção**: um campo não encontrado aparece como `NÃO EXTRAÍDO` no relatório, para conferência manual, em vez de abortar o lote.
- **Casamento por identificador, nunca por valor**: evita falsos positivos quando dois bilhetes têm o mesmo preço.
- **CSV em vez de XLSX**: sem dependências extras e abre direto no Excel (`;` + UTF-8 com BOM).
- **Import duplo em `main.py`**: permite rodar como script, como módulo (`-m passagem.main`) e empacotado pelo PyInstaller.
