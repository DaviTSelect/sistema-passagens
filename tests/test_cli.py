"""Testes dos parâmetros e códigos de saída do modo terminal."""
from __future__ import annotations

import contextlib
import io
from pathlib import Path
import unittest
from unittest import mock

import helpers  # noqa: F401  (configura o sys.path)

from passagem import main
from passagem.conference import ConferenceResult
from passagem.trechos import ExtractionResult


def _executar(*argumentos: str) -> tuple[int, str]:
    saida = io.StringIO()
    with contextlib.redirect_stdout(saida), contextlib.redirect_stderr(saida):
        codigo = main.main(list(argumentos))
    return codigo, saida.getvalue()


class ConferenciaTest(unittest.TestCase):
    ARGUMENTOS = ("--bilhetes", "b", "--fatura", "f", "--saida", "s.csv")

    def test_sucesso_com_aviso_retorna_zero(self) -> None:
        resultado = ConferenceResult(ticket_count=2, warnings=["cuidado"])
        with mock.patch.object(main, "executar_conferencia", return_value=resultado) as conferir:
            codigo, saida = _executar(*self.ARGUMENTOS)
        conferir.assert_called_once_with(Path("b"), Path("f"), Path("s.csv"))
        self.assertEqual(codigo, 0)
        self.assertIn("2 bilhete(s)", saida)
        self.assertIn("AVISO: cuidado", saida)

    def test_erro_retorna_um(self) -> None:
        with mock.patch.object(main, "executar_conferencia", side_effect=ValueError("sem PDFs")):
            codigo, saida = _executar(*self.ARGUMENTOS)
        self.assertEqual(codigo, 1)
        self.assertIn("Erro: sem PDFs", saida)

    def test_parametro_faltando_e_recusado(self) -> None:
        with self.assertRaises(SystemExit) as contexto:
            _executar("--bilhetes", "b")
        self.assertEqual(contexto.exception.code, 2)


class ExtracaoTest(unittest.TestCase):
    ARGUMENTOS = ("--trechos", "p", "--planilha", "t.xlsx")

    def test_sucesso_retorna_zero(self) -> None:
        resultado = ExtractionResult(1, 2, 2, 0, 0, [])
        with mock.patch.object(main, "executar_extracao", return_value=resultado):
            codigo, saida = _executar(*self.ARGUMENTOS)
        self.assertEqual(codigo, 0)
        self.assertIn("2 novo(s)", saida)

    def test_pdf_ilegivel_retorna_um_mesmo_gravando_os_demais(self) -> None:
        resultado = ExtractionResult(2, 2, 2, 0, 0, ["ruim.pdf: falha"])
        with mock.patch.object(main, "executar_extracao", return_value=resultado):
            codigo, saida = _executar(*self.ARGUMENTOS)
        self.assertEqual(codigo, 1)
        self.assertIn("AVISO: ruim.pdf", saida)

    def test_erro_retorna_um(self) -> None:
        with mock.patch.object(main, "executar_extracao", side_effect=ValueError("sem trechos")):
            self.assertEqual(_executar(*self.ARGUMENTOS)[0], 1)


class JanelaTest(unittest.TestCase):
    def test_sem_parametros_abre_a_janela(self) -> None:
        with mock.patch("passagem.gui.abrir_janela", return_value=0) as abrir:
            self.assertEqual(main.main([]), 0)
        abrir.assert_called_once()


if __name__ == "__main__":
    unittest.main()
