"""Orquestra a conferência: lê os PDFs, cruza bilhetes com faturas e grava o CSV.

Este módulo não depende de interface gráfica, para poder ser reutilizado pela
linha de comando, pela janela PySide6 ou por integrações futuras.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from .extract import ler_fatura, ler_bilhete
from .models import InvoiceEntry, Ticket
from .report import comparar, gravar_csv


@dataclass
class ConferenceResult:
    """Resumo de uma execução da conferência."""

    ticket_count: int
    warnings: list[str] = field(default_factory=list)


def executar_conferencia(tickets_dir: Path, invoices_dir: Path, output_file: Path) -> ConferenceResult:
    """Confere todos os PDFs de ``tickets_dir`` contra os de ``invoices_dir``.

    ``invoices_dir`` também pode ser o caminho de um único PDF de fatura.
    Falhas em PDFs individuais viram avisos e não interrompem o processamento.
    Lança ``ValueError`` quando não há nada a conferir.
    """
    ticket_paths = _listar_pdfs(tickets_dir, "bilhetes")
    invoice_paths = _listar_pdfs(invoices_dir, "faturas")

    warnings: list[str] = []
    tickets = _ler_bilhetes(ticket_paths, warnings)
    entries = _ler_faturas(invoice_paths, warnings)

    if not tickets:
        raise ValueError("Nenhum bilhete pôde ser lido.\n" + "\n".join(warnings))
    if not entries:
        raise ValueError(
            "Nenhum bilhete foi identificado nas faturas. "
            "Confira se os PDFs permitem seleção de texto.\n" + "\n".join(warnings)
        )

    # A conferência é feita pelo número do bilhete (ou localizador),
    # nunca por valores ou pela ordem das linhas.
    by_number = {entry.number: entry for entry in entries}
    by_locator = {entry.locator: entry for entry in entries}
    rows = [
        row
        for ticket in tickets
        for row in comparar(ticket, by_number.get(ticket.number) or by_locator.get(ticket.locator))
    ]
    gravar_csv(output_file, rows)
    return ConferenceResult(ticket_count=len(tickets), warnings=warnings)


def _listar_pdfs(folder: Path, description: str) -> list[Path]:
    """Lista os PDFs de uma pasta; se receber um arquivo, retorna só ele."""
    if folder.is_file():
        return [folder]
    paths = sorted(folder.glob("*.pdf"))
    if not paths:
        raise ValueError(f"Nenhum PDF encontrado na pasta de {description}: {folder}")
    return paths


def _ler_bilhetes(paths: list[Path], warnings: list[str]) -> list[Ticket]:
    """Lê os bilhetes descartando duplicados pelo número do bilhete."""
    tickets: list[Ticket] = []
    seen: set[str] = set()
    for path in paths:
        try:
            ticket = ler_bilhete(path)
        except Exception as exc:
            warnings.append(f"Bilhete {path.name}: {exc}")
            continue

        identity = ticket.number or str(path.resolve())
        if identity in seen:
            continue
        seen.add(identity)
        tickets.append(ticket)
        if not ticket.number:
            warnings.append(
                f"Bilhete {path.name}: número do bilhete não identificado; "
                "confira manualmente."
            )
    return tickets


def _ler_faturas(paths: list[Path], warnings: list[str]) -> list[InvoiceEntry]:
    """Lê todas as faturas; uma fatura ilegível vira aviso e não interrompe as demais."""
    entries: list[InvoiceEntry] = []
    for path in paths:
        try:
            entries.extend(ler_fatura(path))
        except Exception as exc:
            warnings.append(f"Fatura {path.name}: {exc}")
    return entries
