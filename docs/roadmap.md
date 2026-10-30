# Roadmap

Sugestões de próximas implementações, em ordem aproximada de valor. Cada item indica onde mexer na arquitetura atual.

## Curto prazo

### Conferir tarifa, taxas e fee
Os valores já são extraídos (`Ticket.fare/taxes`, `InvoiceEntry.fare/taxes/fee`), mas só o total é comparado.
**Onde:** `report.comparar()`. Acrescentar entradas em `checks` reutilizando `_comparar_valores()`. Lembrar que o total G3 inclui o fee.

### Log em arquivo
Registrar avisos e erros com `logging` em um arquivo ao lado do CSV, para auditoria.
**Onde:** `conference.py` (avisos) e `main.py` (configuração do logger).

## Médio prazo

### Registro de modelos de documento (strategy)
Com mais layouts, `extract.py` tende a crescer com regras condicionais. Evoluir para um parser por modelo:

```python
class InvoiceParser(Protocol):
    def matches(self, text: str) -> bool: ...
    def parse(self, text: str, source: Path) -> list[InvoiceEntry]: ...

PARSERS: list[InvoiceParser] = [GolInvoiceParser(), GenericInvoiceParser()]
```

`ler_fatura()` escolhe o primeiro parser cujo `matches()` retornar verdadeiro. Cada modelo ganha seu módulo (`passagem/parsers/gol.py`) e seus próprios testes.

### Exportar para Excel (.xlsx)
Formatação condicional (verde/vermelho), filtros e uma aba de resumo.
**Onde:** novo `report_xlsx.py` com a mesma assinatura de `gravar_csv()`; o formato é escolhido pela extensão do arquivo de saída.

### Arquivo de configuração
Pastas padrão, caminho do Tesseract e tolerância do total em um `config.toml` ao lado do executável, em vez de constantes no código.

### Resumo da conferência
Totais por status (quantos OK, divergentes, não encontrados) e lançamentos da fatura sem bilhete correspondente, que hoje não aparecem no relatório.
**Onde:** `ConferenceResult` e `executar_conferencia()`.

## Longo prazo

- **Novas companhias e agências:** Azul (AD), faturas de outras agências.
- **Release automatizada:** workflow do GitHub Actions que roda `build_exe.bat` ao criar uma tag `v*` e anexa o `.exe` à Release.
- **Qualidade de código:** adicionar `ruff` (lint/format) e `mypy` ao CI.
- **Leitura de e-mails/pastas monitoradas:** processar automaticamente novos PDFs que chegarem em uma pasta.
