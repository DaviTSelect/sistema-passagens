"""Testes das funções puras de normalização."""
from __future__ import annotations

from decimal import Decimal
import unittest

import helpers  # noqa: F401  (configura o sys.path)

from passagem.extract import converter_valor, normalizar_rotulo, normalizar_numero_bilhete


class MoneyTest(unittest.TestCase):
    def test_formatos_brasileiro_e_internacional(self) -> None:
        cases = {
            "1.080,84": Decimal("1080.84"),
            "R$ 34,55": Decimal("34.55"),
            "1080.84": Decimal("1080.84"),
            "1.234.567": Decimal("1234567.00"),
            "1.234": Decimal("1234.00"),
        }
        for raw, expected in cases.items():
            with self.subTest(raw=raw):
                self.assertEqual(converter_valor(raw), expected)

    def test_valores_invalidos_retornam_none(self) -> None:
        for raw in ("", "R$", "abc"):
            with self.subTest(raw=raw):
                self.assertIsNone(converter_valor(raw))


class NormalizeTest(unittest.TestCase):
    def test_numero_bilhete_mantem_so_digitos(self) -> None:
        self.assertEqual(normalizar_numero_bilhete("9990 000-001"), "9990000001")

    def test_rotulo_remove_acentos_e_espacos(self) -> None:
        self.assertEqual(normalizar_rotulo("  Tarifa   Básica "), "TARIFA BASICA")


if __name__ == "__main__":
    unittest.main()
