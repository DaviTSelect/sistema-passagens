"""Testes da fonte única da versão (src/passagem/version.py)."""
from __future__ import annotations

import re
import unittest

from helpers import ROOT

import passagem
from passagem import auto_update, version


class VersaoTest(unittest.TestCase):
    def test_pacote_usa_a_versao_de_version_py(self) -> None:
        self.assertEqual(passagem.__version__, version.__version__)

    def test_formato_e_aceito_pelo_atualizador(self) -> None:
        self.assertRegex(version.__version__, r"^\d+(\.\d+)*$")
        self.assertFalse(auto_update.tem_versao_nova({"tag_name": f"v{version.__version__}"}, version.__version__))

    def test_pyproject_nao_repete_o_numero(self) -> None:
        conteudo = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
        self.assertIn('passagem.version.__version__', conteudo)
        self.assertIsNone(re.search(r'(?m)^version\s*=\s*"', conteudo))


if __name__ == "__main__":
    unittest.main()
