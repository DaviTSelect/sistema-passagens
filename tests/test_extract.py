"""Testes das regras de leitura de bilhetes e faturas, com textos fictícios."""
from __future__ import annotations

from decimal import Decimal
from pathlib import Path
import unittest
from unittest import mock

import helpers  # noqa: F401  (configura o sys.path)

from passagem import extract

FATURA = """9990 000001 - Loc. TST001
Pax: SILVA/JOAO
Voos: LA 4794
TARIFA
TAXA
FEE
SUB-TOTAL
1.150,00+
100,00+
10,00+
1.260,00=
9990 000002 - Loc. TST002
Pax: SOUZA/MARIA
"""


def _valores(*textos: str) -> list[Decimal]:
    return [Decimal(texto) for texto in textos]


class CamposDoBilheteTest(unittest.TestCase):
    def test_numero_com_rotulo_aceita_separadores(self) -> None:
        self.assertEqual(extract._buscar_numero_bilhete("Bilhete: 999-0000 001"), "9990000001")

    def test_numero_curto_e_ignorado(self) -> None:
        self.assertEqual(extract._buscar_numero_bilhete("Voo 1234 assento 12"), "")

    def test_localizador_logo_apos_o_numero(self) -> None:
        self.assertEqual(extract._buscar_localizador("9990000001 ABC123", "x.pdf"), "ABC123")

    def test_passageiro_sem_pronome_de_tratamento(self) -> None:
        self.assertEqual(extract._buscar_passageiro("ADT - SILVA/JOAO MR\n", "x.pdf"), "SILVA/JOAO")

    def test_passageiro_vem_do_arquivo_como_ultimo_recurso(self) -> None:
        self.assertEqual(extract._buscar_passageiro("", "JOAO SILVA.pdf"), "JOAO SILVA")

    def test_voos_sem_repeticao(self) -> None:
        self.assertEqual(extract._buscar_voos("G3 1651, g3-1651 e LA 4794"), ("G3 1651", "LA 4794"))

    def test_voo_latam_separado_por_simbolo(self) -> None:
        self.assertEqual(extract._buscar_voos("LA a\n3648"), ("LA 3648",))

    def test_artefato_latam_vira_o_primeiro_voo(self) -> None:
        self.assertEqual(extract._buscar_voos("a019 OL G3 1651")[0], "LA 3019")

    def test_normalizar_texto_remove_controle_e_espacos(self) -> None:
        self.assertEqual(extract.normalizar_texto("  A\x00  B\t C "), "A B C")


class TarifasTest(unittest.TestCase):
    def test_tabela_associa_valores_aos_cabecalhos(self) -> None:
        texto = "Tarifamento\nTarifa Taxas Total\nR$ 1.080,84 R$ 34,55 R$ 1.115,39\nPagamento"
        self.assertEqual(extract._extrair_tarifas(texto), tuple(_valores("1080.84", "34.55", "1115.39")))

    def test_rotulos_com_valores_ao_lado(self) -> None:
        texto = "Tarifa: 100,00\nTaxas: 20,00\nTotal: 120,00"
        self.assertEqual(extract._extrair_tarifas(texto), tuple(_valores("100.00", "20.00", "120.00")))

    def test_rotulos_em_linhas_separadas(self) -> None:
        linhas = ["Tarifa", "Taxas", "Total", "R$ 1,00", "R$ 2,00", "R$ 3,00"]
        self.assertEqual(extract._ler_tarifas_com_rotulos_separados(linhas), _valores("1.00", "2.00", "3.00"))

    def test_valores_proximos_de_tarifa_e_taxa(self) -> None:
        linhas = ["Tarifa e taxas", "R$ 1,00 R$ 2,00 R$ 3,00"]
        self.assertEqual(extract._ler_tarifas_proximas(linhas), _valores("1.00", "2.00", "3.00"))

    def test_menos_de_tres_valores_nao_preenche(self) -> None:
        self.assertIsNone(extract._ler_tarifas_proximas(["Tarifa e taxas", "R$ 1,00"]))

    def test_sem_valores_retorna_vazio(self) -> None:
        self.assertEqual(extract._extrair_tarifas("sem valores"), (None, None, None))


class FaturaTest(unittest.TestCase):
    def _ler(self, texto: str) -> list:
        with mock.patch.object(extract, "ler_pdf", return_value=texto):
            return extract.ler_fatura(Path("fatura.pdf"))

    def test_um_lancamento_por_bilhete(self) -> None:
        primeiro, segundo = self._ler(FATURA)
        self.assertEqual((primeiro.number, primeiro.locator), ("9990000001", "TST001"))
        self.assertEqual((segundo.number, segundo.passenger), ("9990000002", "SOUZA/MARIA"))

    def test_subtotal_g3_prevalece_e_inclui_fee(self) -> None:
        primeiro = self._ler(FATURA)[0]
        self.assertEqual((primeiro.fare, primeiro.taxes), tuple(_valores("1150.00", "100.00")))
        self.assertEqual((primeiro.fee, primeiro.total), tuple(_valores("10.00", "1260.00")))

    def test_valores_de_um_lancamento_nao_vazam_para_o_proximo(self) -> None:
        self.assertIsNone(self._ler(FATURA)[1].total)

    def test_numero_e_localizador_em_linhas_diferentes(self) -> None:
        lancamento = self._ler("Bilhete 1234567890123\nLocalizador: ABC123\n")[0]
        self.assertEqual((lancamento.number, lancamento.locator), ("1234567890123", "ABC123"))

    def test_numero_sem_localizador_e_ignorado(self) -> None:
        self.assertEqual(self._ler("Bilhete 1234567890123\n"), [])


class LeituraDoPdfTest(unittest.TestCase):
    def test_arquivo_ausente_gera_erro(self) -> None:
        with self.assertRaises(FileNotFoundError):
            extract.ler_pdf(Path("nao_existe.pdf"))

    def test_texto_suficiente_dispensa_ocr(self) -> None:
        texto = "x" * extract.MIN_SELECTABLE_CHARS
        with mock.patch.object(extract, "_ler_texto_selecionavel", return_value=texto), \
                mock.patch.object(extract, "_executar_ocr") as ocr, \
                mock.patch.object(Path, "is_file", return_value=True):
            self.assertEqual(extract.ler_pdf(Path("a.pdf")), texto)
        ocr.assert_not_called()

    def test_pouco_texto_usa_o_ocr(self) -> None:
        with mock.patch.object(extract, "_ler_texto_selecionavel", return_value="pouco"), \
                mock.patch.object(extract, "_executar_ocr", return_value="texto reconhecido"), \
                mock.patch.object(Path, "is_file", return_value=True):
            self.assertEqual(extract.ler_pdf(Path("a.pdf")), "texto reconhecido")


if __name__ == "__main__":
    unittest.main()
