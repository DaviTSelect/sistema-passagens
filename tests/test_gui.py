"""Testes das mensagens e dos estados da janela, sem abrir caixas de diálogo."""
from __future__ import annotations

import os
from pathlib import Path
import unittest
from unittest import mock

import helpers  # noqa: F401  (configura o sys.path)

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import QApplication

from passagem import gui
from passagem.conference import ConferenceResult
from passagem.trechos import ExtractionResult


class FuncoesAuxiliaresTest(unittest.TestCase):
    def test_resumo_limita_os_avisos_exibidos(self) -> None:
        avisos = [f"aviso {i}" for i in range(gui.MAX_WARNINGS_SHOWN + 2)]
        texto = gui.formatar_resumo_conferencia(ConferenceResult(1, avisos), Path("r.csv"))
        self.assertIn(f"Avisos ({len(avisos)})", texto)
        self.assertIn("e mais 2 aviso(s)", texto)
        self.assertNotIn(avisos[-1], texto)

    def test_resumo_sem_aviso_nao_menciona_avisos(self) -> None:
        texto = gui.formatar_resumo_extracao(ExtractionResult(3, 4, 1, 2, 1), Path("t.xlsx"))
        self.assertIn("1 novo(s), 2 atualizado(s) e 1 sem alteração", texto)
        self.assertNotIn("Avisos", texto)

    def test_relatorio_tem_data_e_hora_no_nome(self) -> None:
        self.assertRegex(gui.caminho_relatorio("pasta").name, r"^conferencia_\d{8}_\d{6}\.csv$")

    def test_icone_da_janela_e_encontrado(self) -> None:
        self.assertTrue(gui.caminho_recurso(gui.ICON_FILENAME).is_file())


class JanelaTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.qt = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        self.janela = gui.App()
        for nome in ("information", "critical"):
            patcher = mock.patch.object(gui.QMessageBox, nome)
            setattr(self, nome, patcher.start())
            self.addCleanup(patcher.stop)
        patcher_q = mock.patch.object(gui.QMessageBox, "question",
                                      return_value=gui.QMessageBox.StandardButton.No)
        self.question = patcher_q.start()
        self.addCleanup(patcher_q.stop)

    def test_inicio_ignorado_sem_todas_as_selecoes(self) -> None:
        self.janela.tickets_folder = "x"
        self.janela.iniciar_tarefa()
        self.assertFalse(self.janela.started)

    def test_linha_mostra_o_valor_escolhido(self) -> None:
        linha = self.janela.rows[0]
        linha.definir_valor("bilhetes")
        self.assertEqual(linha.current.text(), "bilhetes")
        self.assertEqual(linha.button.text(), "Alterar")

    def test_extracao_concluida_libera_a_janela_e_mostra_o_resumo(self) -> None:
        self.janela.started = True
        resultado = ExtractionResult(1, 1, 1, 0, 0)
        with mock.patch("passagem.trechos.executar_extracao", return_value=resultado):
            self.janela._executar_extracao(Path("p"), Path("t.xlsx"))
        self.qt.processEvents()
        self.assertFalse(self.janela.started)
        self.assertIn("Extração concluída", self.information.call_args.args[2])

    def test_conferencia_com_erro_mostra_a_mensagem(self) -> None:
        self.janela.started = True
        with mock.patch("passagem.conference.executar_conferencia", side_effect=ValueError("sem PDFs")):
            self.janela._executar_conferencia(Path("b"), Path("f"), Path("r.csv"))
        self.qt.processEvents()
        self.assertFalse(self.janela.started)
        self.assertEqual(self.critical.call_args.args[2], "sem PDFs")

    def test_atualizacao_pendente_fecha_o_programa_apos_a_tarefa(self) -> None:
        self.janela.restart_pending = True
        with mock.patch.object(gui.QApplication, "quit") as sair:
            self.janela.ao_concluir_tarefa("Título", "Mensagem")
        sair.assert_called_once()

    def test_download_bloqueia_o_inicio(self) -> None:
        self.janela.tickets_folder = self.janela.invoice_path = self.janela.output_folder = "x"
        self.janela.ao_mudar_download(True)
        self.assertFalse(self.janela.start.isEnabled())
        self.janela.ao_mudar_download(False)
        self.assertTrue(self.janela.start.isEnabled())

    def test_nao_fecha_durante_o_processamento(self) -> None:
        self.janela.started = True
        evento = QCloseEvent()
        self.janela.closeEvent(evento)
        self.assertFalse(evento.isAccepted())

    def test_escolher_planilha_garante_a_extensao(self) -> None:
        with mock.patch.object(gui.QFileDialog, "getSaveFileName", return_value=("C:/x/trechos", "")):
            self.janela.escolher_planilha()
        self.assertEqual(Path(self.janela.spreadsheet_path).suffix, ".xlsx")

    def test_cancelar_a_selecao_nao_altera_nada(self) -> None:
        with mock.patch.object(gui.QFileDialog, "getExistingDirectory", return_value=""):
            self.janela.escolher_bilhetes()
        self.assertEqual(self.janela.tickets_folder, "")

    def test_raiz_de_disco_e_exibida_por_inteiro(self) -> None:
        with mock.patch.object(gui.QFileDialog, "getExistingDirectory", return_value="D:/"):
            self.janela.escolher_destino()
        self.assertEqual(self.janela.rows[2].current.text(), "D:/")


if __name__ == "__main__":
    unittest.main()
