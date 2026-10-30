"""Testes da comparação campo a campo e da conferência ponta a ponta."""
from __future__ import annotations

import csv
from dataclasses import replace
from decimal import Decimal
from pathlib import Path
import tempfile
import unittest

import pymupdf
from helpers import FIXTURES

from passagem.conference import executar_conferencia
from passagem.models import InvoiceEntry, Ticket
from passagem.report import (
    STATUS_DIVERGENT,
    STATUS_NOT_CHECKED,
    STATUS_NOT_FOUND,
    STATUS_OK,
    comparar,
)

TICKET = Ticket(
    source="bilhete.pdf",
    number="9990000001",
    locator="TST001",
    passenger="SILVA/JOAO MR TESTE",
    flights=("LA 4794",),
    fare=Decimal("1150.00"),
    taxes=Decimal("100.00"),
    total=Decimal("1250.00"),
)


def _lancamento(**overrides: object) -> InvoiceEntry:
    fields = dict(
        source="fatura.pdf",
        number=TICKET.number,
        locator=TICKET.locator,
        passenger="SILVA/JOAO TESTE",
        flights=TICKET.flights,
        fare=TICKET.fare,
        taxes=TICKET.taxes,
        fee=Decimal("0.00"),
        total=TICKET.total,
    )
    fields.update(overrides)
    return InvoiceEntry(**fields)


def _status_por_campo(rows: list[dict[str, str]]) -> dict[str, str]:
    return {row["campo"]: row["resultado"] for row in rows}


class CompareTest(unittest.TestCase):
    def test_lancamento_igual_fica_ok_ignorando_pronome(self) -> None:
        statuses = _status_por_campo(comparar(TICKET, _lancamento()))
        self.assertTrue(all(status == STATUS_OK for status in statuses.values()), statuses)

    def test_sobrenome_iniciado_por_pronome_nao_e_cortado(self) -> None:
        ticket = replace(TICKET, passenger="SILVA/JOAO MRAZ")
        rows = comparar(ticket, _lancamento(passenger="SILVA/JOAOAZ"))
        self.assertEqual(_status_por_campo(rows)["Passageiro"], STATUS_DIVERGENT)

    def test_total_dentro_da_tolerancia_fica_ok(self) -> None:
        rows = comparar(TICKET, _lancamento(total=TICKET.total + Decimal("0.01")))
        self.assertEqual(_status_por_campo(rows)["Total"], STATUS_OK)

    def test_diferenca_de_total_e_informada(self) -> None:
        rows = comparar(TICKET, _lancamento(total=Decimal("1100.00")))
        total_row = next(row for row in rows if row["campo"] == "Total")
        self.assertEqual(total_row["resultado"], STATUS_DIVERGENT)
        self.assertIn("+150.00", total_row["divergencia"])

    def test_total_ausente_nao_e_conferido(self) -> None:
        rows = comparar(TICKET, _lancamento(total=None))
        self.assertEqual(_status_por_campo(rows)["Total"], STATUS_NOT_CHECKED)

    def test_bilhete_sem_lancamento_nao_e_encontrado(self) -> None:
        statuses = _status_por_campo(comparar(TICKET, None))
        self.assertEqual(set(statuses.values()), {STATUS_NOT_FOUND})


class RunConferenceTest(unittest.TestCase):
    def test_pasta_de_bilhetes_vazia_gera_erro(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ValueError):
                executar_conferencia(Path(tmp), FIXTURES, Path(tmp) / "saida.csv")

    def test_grava_csv_compativel_com_excel(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tickets_dir = Path(tmp) / "bilhetes"
            tickets_dir.mkdir()
            _criar_bilhete_sintetico(tickets_dir / "bilhete.pdf")
            output = Path(tmp) / "saida.csv"

            result = executar_conferencia(tickets_dir, FIXTURES, output)

            self.assertEqual(result.ticket_count, 1)
            with output.open(encoding="utf-8-sig", newline="") as file:
                rows = list(csv.DictReader(file, delimiter=";"))
        statuses = _status_por_campo(rows)
        self.assertEqual(statuses["Número do bilhete"], STATUS_OK)
        self.assertEqual(statuses["Localizador"], STATUS_OK)
        self.assertEqual(statuses["Total"], STATUS_OK)


def _criar_bilhete_sintetico(path: Path) -> None:
    """Cria um bilhete de teste correspondente a fatura_sintetica_01.pdf."""
    document = pymupdf.open()
    page = document.new_page()
    page.insert_textbox(
        pymupdf.Rect(48, 48, 547, 760),
        "EXEMPLO SINTÉTICO DE TESTE\n"
        f"Bilhete: {TICKET.number}\n"
        f"Localizador: {TICKET.locator}\n"
        f"Passageiro: {TICKET.passenger}\n"
        "Voo LA 4794\n"
        "Tarifa Taxas Total\n"
        "R$ 1.150,00 R$ 100,00 R$ 1.250,00\n",
        fontsize=11,
        fontname="helv",
    )
    document.save(path)
    document.close()


if __name__ == "__main__":
    unittest.main()
