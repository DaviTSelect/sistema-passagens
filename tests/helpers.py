"""Caminhos e utilitários compartilhados pelos testes."""
from __future__ import annotations

import atexit
import json
from pathlib import Path
import shutil
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]

# Documentos reais ficam fora do controle de versão (contêm dados pessoais).
# Os valores esperados deles ficam em real_documents.json, também ignorado;
# o formato está em docs/desenvolvimento.md.
REAL_TICKETS = ROOT / "pdf"
REAL_INVOICES = ROOT / "fatura"
REAL_EXPECTATIONS = ROOT / "tests" / "real_documents.json"

if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))


# As faturas fictícias são criadas a cada execução, para não ficarem no repositório.
from generate_example_invoices import gerar_faturas  # noqa: E402

FIXTURES = Path(tempfile.mkdtemp(prefix="faturas_sinteticas_"))
atexit.register(shutil.rmtree, FIXTURES, ignore_errors=True)
gerar_faturas(FIXTURES)


def carregar_esperados_reais() -> dict:
    """Retorna os valores esperados dos documentos reais, ou ``{}`` se ausentes."""
    if not REAL_EXPECTATIONS.is_file():
        return {}
    return json.loads(REAL_EXPECTATIONS.read_text(encoding="utf-8"))
