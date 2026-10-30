"""Testes do atualizador e do status de versão exibido na janela."""
from __future__ import annotations

import hashlib
import io
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import helpers  # noqa: F401  (configura o sys.path)

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from passagem import __version__, auto_update, gui
from passagem.conference import executar_conferencia
from helpers import FIXTURES


class VersionTest(unittest.TestCase):
    def test_compara_versoes_numericamente(self) -> None:
        self.assertTrue(auto_update.tem_versao_nova({"tag_name": "v1.10.0"}, "1.9.0"))
        self.assertFalse(auto_update.tem_versao_nova({"tag_name": "v1.0.0"}, "1.0.0"))

    def test_recusa_tag_invalida(self) -> None:
        with self.assertRaises(ValueError):
            auto_update.tem_versao_nova({"tag_name": "beta"}, "1.0.0")

    def test_recusa_release_sem_digest(self) -> None:
        release = {"assets": [{"name": auto_update.NOME_EXE, "browser_download_url": "x"}]}
        with self.assertRaisesRegex(RuntimeError, "SHA-256"):
            auto_update.instalar(release, auto_update.NOME_EXE)


class InstalacaoTest(unittest.TestCase):
    def _instalar(self, conteudo: bytes, digest: str):
        nome_exe = Path(sys.executable).name
        release = {"assets": [{"name": nome_exe, "browser_download_url": "http://x", "digest": f"sha256:{digest}"}]}
        with tempfile.TemporaryDirectory() as pasta,                 mock.patch.object(auto_update.tempfile, "mkdtemp", return_value=pasta),                 mock.patch.object(auto_update.urllib.request, "urlopen", return_value=io.BytesIO(conteudo)),                 mock.patch.object(auto_update.subprocess, "Popen") as popen:
            auto_update.instalar(release, nome_exe)
            self.assertTrue((Path(pasta) / "trocar.ps1").is_file())
            return popen

    def test_download_adulterado_e_recusado(self) -> None:
        with self.assertRaisesRegex(RuntimeError, "não confere"):
            self._instalar(b"exe", "0" * 64)

    def test_download_correto_agenda_a_troca_com_ambiente_limpo(self) -> None:
        popen = self._instalar(b"exe", hashlib.sha256(b"exe").hexdigest())
        popen.assert_called_once()
        self.assertEqual(popen.call_args.kwargs["env"]["PYINSTALLER_RESET_ENVIRONMENT"], "1")

    def test_release_sem_o_executavel_e_recusada(self) -> None:
        with self.assertRaisesRegex(RuntimeError, "Release sem"):
            auto_update.instalar({"assets": []}, auto_update.NOME_EXE)


class UpdateStatusTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.qt = QApplication.instance() or QApplication([])

    def _status_apos_verificar(self, **patches) -> tuple[str, str, gui.App]:
        window = gui.App()
        emitted = []
        window.sinal_status_atualizacao.connect(lambda color, text: emitted.append((color, text)))
        repo = patches.pop("repo", "dono/repo")
        with mock.patch.multiple(auto_update, REPO_GITHUB=repo, **patches):
            window._verificar_atualizacoes()
        self.qt.processEvents()
        return (*emitted[-1], window)

    def test_verde_somente_com_versao_confirmada(self) -> None:
        release = {"tag_name": f"v{__version__}"}
        color, text, _ = self._status_apos_verificar(buscar_release=mock.Mock(return_value=release))
        self.assertEqual(color, gui.UPDATE_OK)
        self.assertIn("atualizado", text)

    def test_falha_de_rede_nao_fica_verde(self) -> None:
        color, _, window = self._status_apos_verificar(buscar_release=mock.Mock(side_effect=OSError("offline")))
        self.assertEqual(color, gui.UPDATE_UNKNOWN)
        self.assertFalse(window.downloading)

    def test_repositorio_ausente_nao_fica_verde(self) -> None:
        color, text, _ = self._status_apos_verificar(repo="")
        self.assertEqual(color, gui.UPDATE_UNKNOWN)
        self.assertIn("não configurada", text)

    def test_versao_nova_nao_fica_verde_e_bloqueia_inicio(self) -> None:
        release = {"tag_name": "v99.0.0"}
        install = mock.Mock()
        with mock.patch.object(gui.QApplication, "quit") as quit_app:
            color, _, window = self._status_apos_verificar(
                buscar_release=mock.Mock(return_value=release),
                pode_instalar=mock.Mock(return_value=True),
                instalar=install,
            )
        install.assert_called_once_with(release, auto_update.NOME_EXE)
        self.assertEqual(color, gui.UPDATE_BUSY)
        self.assertTrue(window.restart_pending)
        self.assertFalse(window.start.isEnabled())
        quit_app.assert_called_once()

    def test_reinicio_espera_processamento_em_andamento(self) -> None:
        window = gui.App()
        window.started = True
        with mock.patch.object(gui.QApplication, "quit") as quit_app:
            window.ao_concluir_atualizacao()
            quit_app.assert_not_called()


class SingleInvoiceTest(unittest.TestCase):
    def test_aceita_arquivo_de_fatura_no_lugar_de_pasta(self) -> None:
        invoice = FIXTURES / "fatura_sintetica_01.pdf"
        with tempfile.TemporaryDirectory() as tmp:
            tickets = Path(tmp) / "vazia"
            tickets.mkdir()
            with mock.patch("passagem.conference.ler_fatura", return_value=[]) as parse:
                with self.assertRaises(ValueError):
                    executar_conferencia(tickets, invoice, Path(tmp) / "saida.csv")
            parse.assert_not_called()
            from passagem.conference import _listar_pdfs

            self.assertEqual(_listar_pdfs(invoice, "faturas"), [invoice])


if __name__ == "__main__":
    unittest.main()
