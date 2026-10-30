"""Gera PDFs sintéticos de fatura usados pelos testes.

Todos os dados são fictícios. Os arquivos incluem uma marca visível de exemplo
e nunca devem ser usados como faturas. Eles são criados em uma pasta temporária
a cada execução dos testes (veja ``helpers.py``) e não ficam no repositório.
"""
from __future__ import annotations

from pathlib import Path

import pymupdf

EXAMPLES = (
    ("fatura_sintetica_01.pdf", "9990 000001", "TST001", "SILVA/JOAO MR TESTE", "LA 4794", "1.150,00", "100,00", "1.250,00"),
    ("fatura_sintetica_02.pdf", "9990 000002", "TST002", "SOUZA/MARIA TESTE", "LA 3019 / LA 3648", "2.454,84", "34,55", "2.489,39"),
)


def gerar_faturas(destino: Path) -> None:
    """Grava em ``destino`` um PDF para cada item de ``EXAMPLES``."""
    for filename, number, locator, passenger, flights, fare, taxes, total in EXAMPLES:
        document = pymupdf.open()
        page = document.new_page()
        page.insert_textbox(
            pymupdf.Rect(48, 48, 547, 760),
            "EXEMPLO SINTÉTICO DE TESTE — NÃO É FATURA NEM DOCUMENTO FISCAL\n\n"
            "MODELO DE LANÇAMENTO DE PASSAGEM\n\n"
            f"{number} - Loc. {locator}\n"
            f"Pax: {passenger}\n"
            f"Voos: {flights}\n\n"
            "TARIFA\nTAXA\nFEE\nSUB-TOTAL\n"
            f"{fare}+\n{taxes}+\n0,00+\n{total}=\n",
            fontsize=12,
            fontname="helv",
        )
        document.save(destino / filename)
        document.close()
