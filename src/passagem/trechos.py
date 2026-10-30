"""Extração dos trechos de voo dos PDFs de passagem para a planilha Excel.

``executar_extracao`` é a porta de entrada. Cada modelo de PDF tem sua função:
``_extrair_reserva`` (texto selecionável) e ``_extrair_facto`` (FACTO digitalizado,
lido por OCR). Para suportar um novo modelo, crie outra função ``_extrair_*`` e
escolha-a em ``extrair_pdf``.

Este módulo é independente de ``extract.py``: a conferência e a extração leem
campos diferentes, e seus resultados dependem das bibliotecas usadas em cada uma.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
import hashlib
from io import BytesIO
from pathlib import Path
import re

from pypdf import PdfReader

from .planilha import salvar_planilha

MESES = {
    "JAN": 1, "FEV": 2, "FEB": 2, "MAR": 3, "ABR": 4, "APR": 4,
    "MAI": 5, "MAY": 5, "JUN": 6, "JUL": 7, "AGO": 8, "AUG": 8,
    "SET": 9, "SEP": 9, "OUT": 10, "OCT": 10, "NOV": 11,
    "DEZ": 12, "DEC": 12,
}

# Quantidade mínima de caracteres (sem espaços) para aceitar o texto de um PDF.
MINIMO_CARACTERES = 80

# PDFs iguais não são lidos duas vezes: o OCR é demorado e o motor leva tempo para carregar.
_textos_em_cache: dict[str, tuple[str, bool]] = {}
_motor_ocr = None


@dataclass
class ExtractionResult:
    """Resumo de uma extração de trechos para a planilha."""

    pdf_count: int
    segment_count: int
    added: int
    updated: int
    unchanged: int
    warnings: list[str] = field(default_factory=list)


def _contar_caracteres(texto: str) -> int:
    return len(re.sub(r"\s", "", texto))


def _ler_texto_pdf(caminho: Path) -> tuple[str, bool]:
    """Retorna ``(texto, usou_ocr)``. O OCR só é aplicado em arquivos digitalizados."""
    conteudo = caminho.read_bytes()
    digest = hashlib.sha256(conteudo).hexdigest()
    if digest in _textos_em_cache:
        return _textos_em_cache[digest]
    texto = "\n".join(
        pagina.extract_text() or ""
        for pagina in PdfReader(BytesIO(conteudo)).pages
    )
    if _contar_caracteres(texto) >= MINIMO_CARACTERES or "Voos" in texto or "Tarifamento" in texto:
        resultado = (texto, False)
    else:
        resultado = (_aplicar_ocr(caminho), True)
    _textos_em_cache[digest] = resultado
    return resultado


def _aplicar_ocr(caminho: Path) -> str:
    """Reconhece o texto de cada página como imagem, sem depender de programa externo."""
    global _motor_ocr
    # Import tardio: o motor de OCR é pesado e nem todo PDF precisa dele.
    try:
        import pypdfium2 as pdfium
        from rapidocr_onnxruntime import RapidOCR
    except ImportError as erro:
        raise ValueError(
            "PDF digitalizado; instale as dependências de OCR do projeto"
        ) from erro

    if _motor_ocr is None:
        _motor_ocr = RapidOCR()
    paginas = []
    documento = pdfium.PdfDocument(str(caminho))
    for pagina in documento:
        imagem = pagina.render(scale=1.6).to_numpy()
        resultado, _ = _motor_ocr(imagem)
        paginas.append("\n".join(item[1] for item in resultado or []))
    texto = "\n".join(paginas)
    if _contar_caracteres(texto) < MINIMO_CARACTERES:
        raise ValueError("Não foi possível reconhecer texto suficiente no PDF")
    return texto


def _converter_data(dia: str, mes: str, ano: str, hora: str) -> datetime:
    """Monta a data a partir de ``10``, ``JAN``, ``2026`` e ``08:30``."""
    return datetime(int(ano), MESES[mes.upper()], int(dia), int(hora[:2]), int(hora[3:]))


def _extrair_facto(caminho: Path, texto: str) -> list[dict]:
    """Interpreta o modelo FACTO de bilhete eletrônico, inclusive via OCR."""
    plano = re.sub(r"\s+", " ", texto)
    numero_txt = _buscar_numero_facto(plano)
    localizadores = re.findall(r"([A-Z0-9]{6,7})\s+ADT\s*[-–]", plano, re.I)
    if not localizadores:
        localizadores = re.findall(r"([A-Z0-9]{6,7})\s+MR\b", plano, re.I)
    passageiro_match = re.search(r"ADT\s*[-–]\s*([A-Z/ ]+?)(?:MR|MS|MRS)?\s*FACTO", plano, re.I)
    if not numero_txt or not localizadores or not passageiro_match:
        raise ValueError("Bilhete ou passageiro FACTO não identificado")
    passageiro = re.sub(r"\s+", " ", passageiro_match.group(1).replace("/", " ")).strip()
    secao = texto.split("Voos", 1)[-1].split("Tarifamento", 1)[0]
    linhas = [re.sub(r"\s+", " ", l).strip() for l in secao.splitlines() if l.strip()]
    aeroportos = []
    for i, linha in enumerate(linhas):
        m = re.match(r"^([A-Z]{3})\s*[-–]\s*", linha)
        if m:
            aeroportos.append((m.group(1), i))
    tarifas = plano.split("Tarifamento", 1)[-1].split("Pagamento", 1)[0]
    valores = re.findall(r"R[\$S]\s*([\d.,]+)", tarifas, re.I)
    if not valores:
        raise ValueError("Valor total FACTO não identificado")
    total_txt = valores[-1]
    total = float(total_txt.replace(".", "").replace(",", "."))
    registros = []
    # Os aeroportos vêm em pares: origem e destino de cada trecho.
    for indice in range(0, len(aeroportos) - 1, 2):
        origem, pos_origem = aeroportos[indice]
        destino, pos_destino = aeroportos[indice + 1]
        fim = aeroportos[indice + 2][1] if indice + 2 < len(aeroportos) else len(linhas)
        bloco = " ".join(linhas[pos_origem:fim])
        datas = re.findall(r"(\d{1,2})\s*([A-Z]{3})\s*(\d{4})\s*(\d{2}:\d{2})", bloco)
        voos = re.findall(r"\b([A-Z0-9]{2})\s*(\d{3,4})\b", bloco)
        if len(datas) < 2 or not voos:
            continue
        registros.append({
            "numero_bilhete": numero_txt, "trecho_numero": len(registros) + 1,
            "localizador": localizadores[0][-6:], "passageiro": passageiro,
            "origem": origem, "data_hora_partida": _converter_data(*datas[0]),
            "destino": destino, "data_hora_chegada": _converter_data(*datas[1]),
            "voo": f"{voos[0][0]} {voos[0][1]}", "valor_total": total,
            "arquivo_origem": caminho.name,
        })
    if not registros:
        raise ValueError("Nenhum trecho FACTO completo foi identificado")
    return registros


def _buscar_numero_facto(plano: str) -> str | None:
    """O número pode estar inteiro (13 dígitos) ou dividido ao redor de ``ADT ... FACTO``."""
    numero = re.search(r"(\d{13})", plano)
    if numero:
        return numero.group(1)
    numero_partes = re.search(r"(\d{3})\s+ADT\b.*?FACTO\s+(\d{10})", plano, re.I)
    return "".join(numero_partes.groups()) if numero_partes else None


def _extrair_reserva(caminho: Path, texto: str) -> list[dict]:
    """Interpreta o modelo de reserva com texto selecionável."""
    inicio_voos = texto.find("Voos")
    inicio_tarifamento = texto.find("Tarifamento")
    if inicio_voos < 0 or inicio_tarifamento < 0:
        raise ValueError("Seções de voos ou tarifamento não encontradas")

    metadados = re.search(
        r"(\d{3})\s+(\d{10})\s+([A-Z0-9]{6})\s+"
        r"((?:ADT|CHD|INF)\s*-\s*.*?)\s+VIP MUNDI",
        texto[:inicio_voos], re.S,
    )
    if not metadados:
        raise ValueError("Bilhete, localizador ou passageiro não identificado")

    secao = texto[inicio_voos:inicio_tarifamento]
    aeroportos = list(re.finditer(r"(?m)^([A-Z]{3})\s*-", secao))
    registros = []

    passageiro = " ".join(metadados.group(4).split()).split(" - ", 1)[-1]
    # Os aeroportos vêm em pares: origem e destino de cada trecho.
    for indice in range(0, len(aeroportos) - 1, 2):
        origem, destino = aeroportos[indice:indice + 2]
        fim = aeroportos[indice + 2].start() if indice + 2 < len(aeroportos) else len(secao)
        bloco_partida = secao[origem.end():destino.start()]
        bloco_chegada = secao[destino.end():fim]
        padrao_data = r"(?m)^\s*(\d{1,2})\s+([A-Z]{3})\s+(\d{4})\s+(\d{2}:\d{2})"
        partida = re.search(padrao_data, bloco_partida)
        chegada = re.search(padrao_data, bloco_chegada)
        voos = re.findall(r"\b[A-Z0-9]{2}\s+\d{3,4}\b", bloco_chegada)
        numero_trecho = indice // 2 + 1
        if not partida or not chegada or not voos:
            raise ValueError(f"Dados incompletos no trecho {numero_trecho}")
        try:
            registro = {
                # A identidade do bilhete vem do conteúdo do PDF, não do nome do arquivo.
                "numero_bilhete": metadados.group(1) + metadados.group(2),
                "trecho_numero": numero_trecho,
                "localizador": metadados.group(3),
                "passageiro": passageiro,
                "origem": origem.group(1),
                "data_hora_partida": _converter_data(*partida.groups()),
                "destino": destino.group(1),
                "data_hora_chegada": _converter_data(*chegada.groups()),
                "voo": voos[0],
                "arquivo_origem": caminho.name,
            }
        except (KeyError, ValueError) as erro:
            raise ValueError(f"Data inválida no trecho {numero_trecho}") from erro
        registros.append(registro)

    if not registros:
        raise ValueError("Nenhum trecho de voo identificado")

    tarifas = texto.split("Tarifamento", 1)[1].split("Pagamento", 1)[0]
    valores = re.findall(r"R\$\s*([\d.,]+)", tarifas)
    if len(valores) < 3:
        raise ValueError("Valor total da passagem não identificado")
    total = float(valores[-1].replace(".", "").replace(",", "."))
    for registro in registros:
        registro["valor_total"] = total
    return registros


def extrair_pdf(caminho: Path) -> list[dict]:
    """Retorna uma linha de dados para cada trecho encontrado no PDF."""
    caminho = Path(caminho)
    texto, ocr_aplicado = _ler_texto_pdf(caminho)
    if ocr_aplicado and "FACTO" in texto.upper():
        return _extrair_facto(caminho, texto)
    return _extrair_reserva(caminho, texto)


def executar_extracao(folder: Path, output_file: Path) -> ExtractionResult:
    """Extrai os trechos dos PDFs de ``folder`` e atualiza a planilha ``output_file``.

    Falhas em PDFs individuais viram avisos. Lança ``ValueError`` quando não há
    nada a gravar; nesse caso a planilha não é alterada.
    """
    if not folder.is_dir():
        raise ValueError(f"Pasta de entrada inválida: {folder}")
    pdfs = sorted(
        (arquivo for arquivo in folder.iterdir()
         if arquivo.is_file() and arquivo.suffix.lower() == ".pdf"),
        key=lambda arquivo: arquivo.name.casefold(),
    )
    if not pdfs:
        raise ValueError(f"Nenhum PDF encontrado na pasta: {folder}")

    registros_por_chave: dict[tuple[str, int], dict] = {}
    warnings: list[str] = []
    for pdf in pdfs:
        try:
            for registro in extrair_pdf(pdf):
                # Uma mesma passagem pode ter sido enviada em duplicidade.
                chave = (registro["numero_bilhete"], registro["trecho_numero"])
                registros_por_chave.setdefault(chave, registro)
        except Exception as erro:
            # Detalhes internos do parser podem conter trechos do documento.
            warnings.append(f"{pdf.name}: falha na leitura ou extração ({type(erro).__name__}).")

    registros = list(registros_por_chave.values())
    if not registros:
        raise ValueError("Nenhum trecho foi extraído; a planilha não foi alterada.\n" + "\n".join(warnings))
    added, updated, unchanged = salvar_planilha(output_file, registros)
    return ExtractionResult(len(pdfs), len(registros), added, updated, unchanged, warnings)
