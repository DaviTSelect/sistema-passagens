"""Ponto de entrada: abre a interface gráfica ou executa pela linha de comando.

Sem argumentos, abre a janela. Com ``--bilhetes``, ``--fatura`` e ``--saida``,
roda a conferência no terminal; com ``--trechos`` e ``--planilha``, extrai os
trechos para o Excel. Retorna código de saída 0 (sucesso) ou 1 (erro).
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

if __package__:  # Execução como módulo: `python -m passagem.main`.
    from .conference import executar_conferencia
    from .trechos import executar_extracao
else:  # Execução direta e ponto de entrada do PyInstaller.
    if not getattr(sys, "frozen", False):
        package_root = Path(__file__).resolve().parent.parent
        if str(package_root) not in sys.path:
            sys.path.insert(0, str(package_root))
    from passagem.conference import executar_conferencia
    from passagem.trechos import executar_extracao


def criar_parser() -> argparse.ArgumentParser:
    """Define os parâmetros aceitos no terminal. Novos parâmetros entram aqui."""
    parser = argparse.ArgumentParser(
        description="Conferência de bilhetes contra faturas e extração de trechos para o Excel."
    )
    parser.add_argument("--bilhetes", type=Path, help="Pasta dos bilhetes (modo terminal)")
    parser.add_argument("--fatura", type=Path, help="Pasta das faturas ou PDF de uma fatura (modo terminal)")
    parser.add_argument("--saida", type=Path, help="Arquivo CSV de saída (modo terminal)")
    parser.add_argument("--trechos", type=Path, help="Pasta dos PDFs para extrair os trechos (modo terminal)")
    parser.add_argument("--planilha", type=Path, help="Planilha Excel a criar ou atualizar (modo terminal)")
    return parser


def executar_conferencia_cli(tickets_dir: Path, invoices_dir: Path, output_file: Path) -> int:
    """Roda a conferência no terminal e retorna o código de saída."""
    try:
        result = executar_conferencia(tickets_dir, invoices_dir, output_file)
    except Exception as exc:
        print(f"Erro: {exc}", file=sys.stderr)
        return 1
    print(f"Concluído: {result.ticket_count} bilhete(s). Planilha: {output_file}")
    _imprimir_avisos(result.warnings)
    return 0


def executar_extracao_cli(folder: Path, output_file: Path) -> int:
    """Roda a extração no terminal; PDFs ilegíveis tornam o código de saída 1."""
    try:
        result = executar_extracao(folder, output_file)
    except Exception as exc:
        print(f"Erro: {exc}", file=sys.stderr)
        return 1
    print(
        f"Concluído: {result.pdf_count} PDF(s), {result.segment_count} trecho(s), "
        f"{result.added} novo(s), {result.updated} atualizado(s), "
        f"{result.unchanged} sem alteração. Planilha: {output_file}"
    )
    _imprimir_avisos(result.warnings)
    return 1 if result.warnings else 0


def _imprimir_avisos(warnings: list[str]) -> None:
    for warning in warnings:
        print(f"AVISO: {warning}")


def main(argv: list[str] | None = None) -> int:
    """Decide entre os modos de terminal e a janela, conforme os parâmetros."""
    parser = criar_parser()
    args = parser.parse_args(argv)
    conference_args = (args.bilhetes, args.fatura, args.saida)
    extraction_args = (args.trechos, args.planilha)
    if any(conference_args) and any(extraction_args):
        parser.error("Use a conferência ou a extração de trechos, não as duas juntas.")
    if any(extraction_args):
        if not all(extraction_args):
            parser.error("Use os dois parâmetros: --trechos e --planilha.")
        return executar_extracao_cli(args.trechos, args.planilha)
    if any(conference_args):
        if not all(conference_args):
            parser.error("Use os três parâmetros: --bilhetes, --fatura e --saida.")
        return executar_conferencia_cli(args.bilhetes, args.fatura, args.saida)

    # Import tardio: o modo terminal não precisa carregar o PySide6.
    if __package__:
        from .gui import abrir_janela
    else:
        from passagem.gui import abrir_janela
    return abrir_janela()


if __name__ == "__main__":
    raise SystemExit(main())
