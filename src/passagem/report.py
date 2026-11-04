"""Comparação campo a campo entre bilhete e fatura e geração do CSV."""
from __future__ import annotations

import csv
from decimal import Decimal
from pathlib import Path
import re

from .models import InvoiceEntry, Ticket

STATUS_OK = "OK"
STATUS_DIVERGENT = "DIVERGENTE"
STATUS_NOT_FOUND = "NÃO ENCONTRADO"
STATUS_NOT_CHECKED = "NÃO CONFERIDO"

NOT_EXTRACTED = "NÃO EXTRAÍDO"
NO_MATCH = "SEM CORRESPONDÊNCIA"

# Diferença máxima aceita entre os totais para considerar a conferência OK.
TOTAL_TOLERANCE = Decimal("0.01")

CSV_COLUMNS = [
    "numero_bilhete",
    "campo",
    "valor_bilhete",
    "valor_fatura",
    "resultado",
    "divergencia",
    "arquivo_bilhete",
    "arquivo_fatura",
]
CSV_DELIMITER = ";"
# utf-8-sig grava o BOM para o Excel reconhecer os acentos.
CSV_ENCODING = "utf-8-sig"

Row = dict[str, str]
Value = str | Decimal | None


def comparar(ticket: Ticket, entry: InvoiceEntry | None) -> list[Row]:
    """Gera uma linha do relatório para cada campo conferido do bilhete.

    ``entry`` é ``None`` quando o bilhete não foi localizado em nenhuma fatura;
    nesse caso todas as linhas saem como ``NÃO ENCONTRADO``.
    """
    checks: list[tuple[str, Value, Value]] = [
        ("Número do bilhete", ticket.number, entry.number if entry else ""),
        ("Localizador", ticket.locator, entry.locator if entry else ""),
        ("Passageiro", ticket.passenger, entry.passenger if entry else ""),
        ("Voos", " | ".join(ticket.flights), " | ".join(entry.flights) if entry else ""),
        ("Total", ticket.total, entry.total if entry else None),
    ]
    rows = []
    for label, ticket_value, invoice_value in checks:
        if entry is None:
            status, issue = STATUS_NOT_FOUND, "Bilhete não localizado na fatura"
        elif label == "Total":
            status, issue = _comparar_valores(ticket_value, invoice_value)
        elif label == "Passageiro":
            status, issue = _comparar_passageiro(ticket_value, invoice_value)
        else:
            status, issue = _comparar_textos(ticket_value, invoice_value)

        rows.append({
            "numero_bilhete": ticket.number or NOT_EXTRACTED,
            "campo": label,
            "valor_bilhete": _formatar_para_exibicao(ticket_value) or NOT_EXTRACTED,
            "valor_fatura": _formatar_para_exibicao(invoice_value) or (NO_MATCH if entry is None else NOT_EXTRACTED),
            "resultado": status,
            "divergencia": issue,
            "arquivo_bilhete": Path(ticket.source).name,
            "arquivo_fatura": Path(entry.source).name if entry else "",
        })
    return rows


def gravar_csv(path: Path, rows: list[Row]) -> None:
    """Grava o relatório em CSV compatível com o Excel em português."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding=CSV_ENCODING) as file:
        writer = csv.DictWriter(file, fieldnames=CSV_COLUMNS, delimiter=CSV_DELIMITER)
        writer.writeheader()
        writer.writerows(rows)


def _comparar_valores(ticket_value: Value, invoice_value: Value) -> tuple[str, str]:
    """Retorna ``(status, divergência)`` dos totais, aceitando ``TOTAL_TOLERANCE``."""
    if not isinstance(ticket_value, Decimal) or not isinstance(invoice_value, Decimal):
        return STATUS_NOT_CHECKED, "Valor não extraído de um dos PDFs"
    difference = ticket_value - invoice_value
    if abs(difference) <= TOTAL_TOLERANCE:
        return STATUS_OK, ""
    return STATUS_DIVERGENT, f"Diferença: R$ {difference:+.2f} (bilhete menos fatura)"


def _comparar_passageiro(ticket_value: Value, invoice_value: Value) -> tuple[str, str]:
    """Compara nomes ignorando espaços internos que o PyPDF2 insere dentro das palavras."""
    if _normalizar_passageiro(ticket_value) == _normalizar_passageiro(invoice_value):
        return STATUS_OK, ""
    return STATUS_DIVERGENT, f"Bilhete: {ticket_value or '(vazio)'}; fatura: {invoice_value or '(vazio)'}"


def _normalizar_passageiro(value: Value) -> str:
    """Remove todos os espaços e pronomes de tratamento para comparar nomes IATA."""
    text = re.sub(r"\s(?:MRS|MR|MS|MISS)(?=\s|$)", "", str(value or "").upper())
    return re.sub(r"\s+", "", text)


def _comparar_textos(ticket_value: Value, invoice_value: Value) -> tuple[str, str]:
    """Retorna ``(status, divergência)`` de campos de texto, já normalizados."""
    if _normalizar_para_comparacao(ticket_value) == _normalizar_para_comparacao(invoice_value):
        return STATUS_OK, ""
    return STATUS_DIVERGENT, f"Bilhete: {ticket_value or '(vazio)'}; fatura: {invoice_value or '(vazio)'}"


def _normalizar_para_comparacao(value: Value) -> str:
    """Ignora maiúsculas, espaços extras e pronomes de tratamento (MR/MRS/MS/MISS)."""
    text = re.sub(r"\s(?:MRS|MR|MS|MISS)(?=\s|$)", "", str(value or "").upper())
    return " ".join(text.split())


def _formatar_para_exibicao(value: Value) -> str:
    """Formata o valor para a planilha (moeda no padrão brasileiro)."""
    if value is None:
        return ""
    if isinstance(value, Decimal):
        return f"R$ {value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return str(value)
