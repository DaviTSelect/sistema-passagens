"""Modelos de dados compartilhados entre extração, conferência e relatório."""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class Ticket:
    """Dados extraídos de um PDF de bilhete aéreo."""

    source: str
    number: str
    locator: str
    passenger: str
    flights: tuple[str, ...]
    fare: Decimal | None
    taxes: Decimal | None
    total: Decimal | None


@dataclass(frozen=True)
class InvoiceEntry:
    """Lançamento de um bilhete dentro de um PDF de fatura."""

    source: str
    number: str
    locator: str
    passenger: str
    flights: tuple[str, ...]
    fare: Decimal | None
    taxes: Decimal | None
    fee: Decimal | None
    total: Decimal | None
