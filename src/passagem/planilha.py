"""Criação e atualização idempotente da planilha Excel."""

from pathlib import Path
from tempfile import NamedTemporaryFile

from openpyxl import Workbook, load_workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.worksheet.table import Table, TableStyleInfo


CAMPOS = [
    "numero_bilhete", "trecho_numero", "localizador", "passageiro",
    "origem", "data_hora_partida", "destino", "data_hora_chegada",
    "voo", "valor_total", "arquivo_origem",
]
CABECALHOS = [
    "Número do bilhete", "Trecho nº", "Localizador da reserva",
    "Nome do passageiro", "Origem", "Data/hora de partida", "Destino",
    "Data/hora de chegada", "Voo", "Valor total do bilhete (R$)",
    "Arquivo de origem",
]


def _preparar(caminho: Path):
    """Abre a planilha existente ou cria uma nova, conferindo as colunas."""
    if caminho.exists():
        try:
            workbook = load_workbook(caminho)
        except Exception as erro:
            raise ValueError("O arquivo de saída não é uma planilha Excel válida") from erro
        if "Trechos" not in workbook.sheetnames:
            raise ValueError("A planilha existente não contém a aba 'Trechos'")
        sheet = workbook["Trechos"]
    else:
        workbook = Workbook()
        sheet = workbook.active
        sheet.title = "Trechos"

    existentes = [sheet.cell(1, col).value for col in range(1, len(CABECALHOS) + 1)]
    if sheet.max_row == 1 and all(valor is None for valor in existentes):
        for col, nome in enumerate(CABECALHOS, start=1):
            sheet.cell(1, col, nome)
    elif existentes != CABECALHOS:
        raise ValueError("As colunas da aba 'Trechos' não correspondem ao formato esperado")
    return workbook, sheet


def _linhas_existentes(sheet) -> dict[tuple[str, int], int]:
    """Mapeia cada ``(bilhete, trecho)`` já gravado para o número da sua linha."""
    # Arquivos com o mesmo nome continuam distintos quando têm números de bilhete diferentes.
    linhas = {}
    for numero_linha in range(2, sheet.max_row + 1):
        bilhete, trecho = sheet.cell(numero_linha, 1).value, sheet.cell(numero_linha, 2).value
        if bilhete is None and trecho is None:
            continue
        if bilhete is None or trecho is None:
            raise ValueError(f"A linha {numero_linha} tem chave de bilhete/trecho incompleta")
        try:
            chave = (str(bilhete).strip(), int(trecho))
        except (TypeError, ValueError) as erro:
            raise ValueError(f"A chave da linha {numero_linha} é inválida") from erro
        if chave in linhas:
            raise ValueError("A planilha contém bilhete/trecho duplicado")
        linhas[chave] = numero_linha
    return linhas


def _formatar(sheet) -> None:
    """Aplica cabeçalho, formatos de data e moeda, larguras e tabela do Excel."""
    for cell in sheet[1]:
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = PatternFill("solid", fgColor="164E80")
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
    sheet.freeze_panes = "A2"
    sheet.auto_filter.ref = sheet.dimensions
    sheet.row_dimensions[1].height = 32
    for row in sheet.iter_rows(min_row=2):
        row[0].number_format = "@"
        row[5].number_format = row[7].number_format = "dd/mm/yyyy hh:mm"
        row[9].number_format = '"R$" #,##0.00'
    for coluna, largura in enumerate([20, 12, 22, 32, 12, 23, 12, 23, 16, 25, 28], 1):
        sheet.column_dimensions[sheet.cell(1, coluna).column_letter].width = largura
    if "TabelaTrechos" in sheet.tables:
        del sheet.tables["TabelaTrechos"]
    if sheet.max_row > 1:
        tabela = Table(displayName="TabelaTrechos", ref=sheet.dimensions)
        tabela.tableStyleInfo = TableStyleInfo(name="TableStyleMedium2", showRowStripes=True)
        sheet.add_table(tabela)


def _validar_registros(registros: list[dict]) -> list[dict]:
    """Confere os campos obrigatórios e mantém um registro por bilhete/trecho."""
    registros_unicos = []
    chaves_recebidas = set()
    for numero, registro in enumerate(registros, start=1):
        ausentes = [campo for campo in CAMPOS if registro.get(campo) in (None, "")]
        if ausentes:
            raise ValueError(f"Registro {numero} sem campos obrigatórios: {', '.join(ausentes)}")
        try:
            chave = (str(registro["numero_bilhete"]).strip(), int(registro["trecho_numero"]))
            valor_total = float(registro["valor_total"])
        except (TypeError, ValueError) as erro:
            raise ValueError(f"Registro {numero} tem chave ou valor inválido") from erro
        if not chave[0] or chave[1] < 1 or valor_total < 0:
            raise ValueError(f"Registro {numero} tem chave ou valor inválido")
        if chave in chaves_recebidas:
            continue
        chaves_recebidas.add(chave)
        registros_unicos.append(registro)
    return registros_unicos


def _gravar_com_seguranca(workbook, caminho: Path) -> None:
    """Grava em um arquivo temporário antes de substituir, para não corromper a planilha."""
    caminho.parent.mkdir(parents=True, exist_ok=True)
    temporario = None
    try:
        with NamedTemporaryFile(dir=caminho.parent, suffix=caminho.suffix, delete=False) as arquivo:
            temporario = Path(arquivo.name)
        workbook.save(temporario)
        temporario.replace(caminho)
    except PermissionError as erro:
        raise PermissionError("Não foi possível salvar; feche a planilha no Excel e tente novamente") from erro
    finally:
        if temporario is not None and temporario.exists():
            temporario.unlink()


def salvar_planilha(caminho: Path, registros: list[dict]) -> tuple[int, int, int]:
    """Salva os registros e retorna (adicionados, atualizados, inalterados)."""
    caminho = Path(caminho)
    registros = _validar_registros(registros)
    workbook, sheet = _preparar(caminho)
    linhas = _linhas_existentes(sheet)
    adicionados = atualizados = inalterados = 0
    for registro in registros:
        valores = [registro[campo] for campo in CAMPOS]
        chave = (str(registro["numero_bilhete"]).strip(), int(registro["trecho_numero"]))
        if chave in linhas:
            linha = linhas[chave]
            antigos = [sheet.cell(linha, col).value for col in range(1, len(valores) + 1)]
            if antigos == valores:
                inalterados += 1
                continue
            atualizados += 1
        else:
            sheet.append(valores)
            linha = sheet.max_row
            linhas[chave] = linha
            adicionados += 1
        for coluna, valor in enumerate(valores, start=1):
            sheet.cell(linha, coluna, valor)
        sheet.cell(linha, 1).number_format = "@"

    _formatar(sheet)
    _gravar_com_seguranca(workbook, caminho)
    return adicionados, atualizados, inalterados
