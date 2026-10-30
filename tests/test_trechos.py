"""Testes da extração de trechos, da planilha e da troca de função na janela."""
from __future__ import annotations

import os
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest import mock

import helpers  # noqa: F401  (configura o sys.path)

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from openpyxl import load_workbook
from PySide6.QtWidgets import QApplication

from passagem import gui, main, trechos
from passagem.planilha import salvar_planilha

RESERVA = """Reserva
123 4567890123 ABC123 ADT - SILVA/JOAO VIP MUNDI
Voos
GRU - Guarulhos
10 JAN 2026 08:00
CGH - Congonhas
10 JAN 2026 09:10
G3 1234
Tarifamento
Tarifa R$ 100,00
Taxas R$ 20,00
Total R$ 1.120,50
Pagamento
"""


def _registro(trecho: int = 1, passageiro: str = "SILVA JOAO") -> dict:
    return {
        "numero_bilhete": "1234567890123", "trecho_numero": trecho, "localizador": "ABC123",
        "passageiro": passageiro, "origem": "GRU", "data_hora_partida": datetime(2026, 1, 10, 8),
        "destino": "CGH", "data_hora_chegada": datetime(2026, 1, 10, 9, 10), "voo": "G3 1234",
        "valor_total": 1120.5, "arquivo_origem": "a.pdf",
    }


class ParserTest(unittest.TestCase):
    def test_le_trecho_do_texto_de_reserva(self) -> None:
        with mock.patch.object(trechos, "_ler_texto_pdf", return_value=(RESERVA, False)):
            registros = trechos.extrair_pdf(Path("a.pdf"))
        self.assertEqual(len(registros), 1)
        self.assertEqual(registros[0]["numero_bilhete"], "1234567890123")
        self.assertEqual(registros[0]["voo"], "G3 1234")
        self.assertEqual(registros[0]["valor_total"], 1120.5)


class FactoTest(unittest.TestCase):
    TEXTO = """1234567890123 ABC123 ADT - SILVA/JOAO MR FACTO
Voos
GRU - Guarulhos
10 JAN 2026 08:00
CGH - Congonhas
10 JAN 2026 09:10
G3 1234
Tarifamento
R$ 100,00
R$ 1.120,50
Pagamento
"""

    def test_le_trecho_digitalizado_do_modelo_facto(self) -> None:
        with mock.patch.object(trechos, "_ler_texto_pdf", return_value=(self.TEXTO, True)):
            registro = trechos.extrair_pdf(Path("a.pdf"))[0]
        self.assertEqual(registro["passageiro"], "SILVA JOAO")
        self.assertEqual(registro["data_hora_chegada"], datetime(2026, 1, 10, 9, 10))
        self.assertEqual(registro["valor_total"], 1120.5)

    def test_sem_passageiro_gera_erro(self) -> None:
        with self.assertRaises(ValueError):
            trechos._extrair_facto(Path("a.pdf"), "texto sem dados")


class ReservaInvalidaTest(unittest.TestCase):
    def test_sem_secao_de_voos_gera_erro(self) -> None:
        with self.assertRaisesRegex(ValueError, "Seções"):
            trechos._extrair_reserva(Path("a.pdf"), "texto qualquer")

    def test_mes_desconhecido_gera_erro_de_data(self) -> None:
        with self.assertRaisesRegex(ValueError, "Data inválida"):
            trechos._extrair_reserva(Path("a.pdf"), RESERVA.replace("JAN", "XXX"))


class SpreadsheetTest(unittest.TestCase):
    def test_atualizacao_nao_duplica_e_mantem_linhas(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            planilha = Path(tmp) / "trechos.xlsx"
            self.assertEqual(salvar_planilha(planilha, [_registro(1)]), (1, 0, 0))
            self.assertEqual(salvar_planilha(planilha, [_registro(1)]), (0, 0, 1))
            self.assertEqual(salvar_planilha(planilha, [_registro(1, "SILVA JOSE"), _registro(2)]), (1, 1, 0))
            workbook = load_workbook(planilha)
            self.assertEqual(workbook["Trechos"].max_row, 3)
            workbook.close()


class ValidacaoDaPlanilhaTest(unittest.TestCase):
    def test_campo_obrigatorio_ausente_gera_erro(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            registro = {**_registro(), "voo": ""}
            with self.assertRaisesRegex(ValueError, "voo"):
                salvar_planilha(Path(tmp) / "t.xlsx", [registro])

    def test_arquivo_que_nao_e_excel_gera_erro(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            arquivo = Path(tmp) / "t.xlsx"
            arquivo.write_text("não é uma planilha", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "não é uma planilha Excel"):
                salvar_planilha(arquivo, [_registro()])

    def test_duplicados_no_mesmo_lote_viram_uma_linha(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(salvar_planilha(Path(tmp) / "t.xlsx", [_registro(), _registro()]), (1, 0, 0))


class ExtractionTest(unittest.TestCase):
    def _criar_pasta(self, tmp: str) -> Path:
        folder = Path(tmp) / "pdfs"
        folder.mkdir()
        for name in ("a.pdf", "b.PDF", "ruim.pdf"):
            (folder / name).write_bytes(b"")
        return folder

    def test_duplicados_unem_e_pdf_ruim_vira_aviso_sem_conteudo(self) -> None:
        def fake(path: Path) -> list[dict]:
            if path.name == "ruim.pdf":
                raise ValueError("SILVA/JOAO confidencial")
            return [_registro(1)]

        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.object(trechos, "extrair_pdf", side_effect=fake):
                result = trechos.executar_extracao(self._criar_pasta(tmp), Path(tmp) / "t.xlsx")
        self.assertEqual((result.pdf_count, result.segment_count, result.added), (3, 1, 1))
        self.assertEqual(len(result.warnings), 1)
        self.assertNotIn("SILVA", result.warnings[0])

    def test_sem_trechos_nao_cria_planilha(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            planilha = Path(tmp) / "t.xlsx"
            with mock.patch.object(trechos, "extrair_pdf", side_effect=ValueError("x")):
                with self.assertRaises(ValueError):
                    trechos.executar_extracao(self._criar_pasta(tmp), planilha)
            self.assertFalse(planilha.exists())


class CliTest(unittest.TestCase):
    def test_exige_os_dois_parametros_de_extracao(self) -> None:
        with self.assertRaises(SystemExit), mock.patch("sys.stderr"):
            main.main(["--trechos", "x"])

    def test_recusa_misturar_conferencia_e_extracao(self) -> None:
        with self.assertRaises(SystemExit), mock.patch("sys.stderr"):
            main.main(["--trechos", "x", "--planilha", "y.xlsx", "--bilhetes", "z"])


class WindowModeTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.qt = QApplication.instance() or QApplication([])

    def test_cada_modo_exige_so_suas_selecoes(self) -> None:
        window = gui.App()
        window.tickets_folder = window.invoice_path = window.output_folder = "x"
        window.atualizar_estado()
        self.assertTrue(window.start.isEnabled())
        self.assertEqual(window.count.text(), "3 de 3")

        window.definir_modo(gui.MODE_EXTRACTION)
        self.assertFalse(window.start.isEnabled())
        self.assertEqual(window.count.text(), "0 de 2")

        window.extraction_folder = window.spreadsheet_path = "x"
        window.atualizar_estado()
        self.assertTrue(window.start.isEnabled())

    def test_modo_fica_travado_durante_processamento(self) -> None:
        window = gui.App()
        window.started = True
        window.atualizar_estado()
        self.assertFalse(window.mode_buttons[1].isEnabled())


if __name__ == "__main__":
    unittest.main()
