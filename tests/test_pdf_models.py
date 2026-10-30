"""Testes de extração para cada modelo de PDF suportado."""
from __future__ import annotations

from decimal import Decimal
import unittest

from helpers import FIXTURES, REAL_INVOICES, REAL_TICKETS, carregar_esperados_reais

from passagem.extract import _extrair_valor_rotulado, _buscar_localizador, ler_fatura, ler_bilhete

REAL = carregar_esperados_reais()
MONEY_FIELDS = {"fare", "taxes", "fee", "total"}


def _valor_esperado(field: str, value: object) -> object:
    """Converte o valor do JSON para o tipo retornado pelo extrator."""
    if field in MONEY_FIELDS:
        return Decimal(value)
    if field == "flights":
        return tuple(value)
    return value


class FieldRulesTest(unittest.TestCase):
    def test_palavras_comuns_nao_sao_localizador(self) -> None:
        self.assertEqual(_buscar_localizador("Reserva: Viagem", "x.pdf"), "")
        self.assertEqual(_buscar_localizador("", "fatura.pdf"), "")

    def test_localizador_lido_do_rotulo_e_do_arquivo(self) -> None:
        self.assertEqual(_buscar_localizador("Localizador: ABC123", "x.pdf"), "ABC123")
        self.assertEqual(_buscar_localizador("", "bilhete ABC123.pdf"), "ABC123")

    def test_valor_rotulado_exige_centavos(self) -> None:
        self.assertIsNone(_extrair_valor_rotulado("Total 2 bilhetes", ("Total",)))
        self.assertEqual(_extrair_valor_rotulado("Total: R$ 1.250,00", ("Total",)), Decimal("1250.00"))
        self.assertEqual(_extrair_valor_rotulado("Total 1080.84", ("Total",)), Decimal("1080.84"))


class SyntheticInvoiceTest(unittest.TestCase):
    def test_faturas_sinteticas_sao_lidas(self) -> None:
        expected = {
            "fatura_sintetica_01.pdf": ("9990000001", "TST001", Decimal("1250.00")),
            "fatura_sintetica_02.pdf": ("9990000002", "TST002", Decimal("2489.39")),
        }
        for filename, (number, locator, total) in expected.items():
            with self.subTest(filename=filename):
                entry = ler_fatura(FIXTURES / filename)[0]
                self.assertEqual(entry.number, number)
                self.assertEqual(entry.locator, locator)
                self.assertEqual(entry.total, total)


@unittest.skipUnless(REAL.get("tickets"), "tests/real_documents.json ausente")
class RealTicketModelsTest(unittest.TestCase):
    def test_bilhetes_reais_sao_lidos(self) -> None:
        for filename, fields in REAL["tickets"].items():
            path = REAL_TICKETS / filename
            with self.subTest(filename=filename):
                if not path.is_file():
                    self.skipTest(f"PDF real ausente: {path}")
                ticket = ler_bilhete(path)
                for field, value in fields.items():
                    self.assertEqual(getattr(ticket, field), _valor_esperado(field, value), field)


@unittest.skipUnless(REAL.get("invoices"), "tests/real_documents.json ausente")
class RealInvoiceModelsTest(unittest.TestCase):
    def test_faturas_reais_sao_lidas(self) -> None:
        for filename, expected in REAL["invoices"].items():
            path = REAL_INVOICES / filename
            with self.subTest(filename=filename):
                if not path.is_file():
                    self.skipTest(f"PDF real ausente: {path}")
                entries = ler_fatura(path)
                self.assertEqual(len(entries), expected["entry_count"])
                by_number = {entry.number: entry for entry in entries}
                for number, fields in expected["entries"].items():
                    for field, value in fields.items():
                        self.assertEqual(getattr(by_number[number], field), _valor_esperado(field, value), field)


if __name__ == "__main__":
    unittest.main()
