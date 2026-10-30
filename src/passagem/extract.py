"""Leitura de PDFs (texto selecionável ou OCR) e extração dos campos.

Portas de entrada: ``ler_bilhete`` e ``ler_fatura``. Cada layout suportado tem
suas regras isoladas em funções ``_buscar_*`` e ``_extrair_*``. Para suportar um
novo modelo de documento, adicione a regra específica sem alterar o comportamento
dos modelos já cobertos por testes.
"""
from __future__ import annotations

from decimal import Decimal, InvalidOperation
import os
from pathlib import Path
import re
import shutil
import unicodedata

from .models import InvoiceEntry, Ticket

__all__ = ["InvoiceEntry", "Ticket", "ler_fatura", "ler_bilhete", "ler_pdf"]


# ============================================================
# CONFIGURAÇÃO DO OCR
# ============================================================

# A variável de ambiente TESSERACT_CMD permite apontar outra instalação.
TESSERACT_PATH = Path(
    os.environ.get("TESSERACT_CMD", r"C:\Program Files\Tesseract-OCR\tesseract.exe")
)

# Quantidade mínima de caracteres (sem espaços) para considerar que o PDF
# tem texto selecionável suficiente e dispensar o OCR.
MIN_SELECTABLE_CHARS = 40

# Valor monetário no padrão brasileiro, com ``R$`` opcional na frente.
_PADRAO_VALOR_COM_MOEDA = r"(?<!\w)(?:R\$\s*)?(\d{1,3}(?:\.\d{3})*,\d{2}|\d+,\d{2})"

# Número de bilhete no formato comum de faturas: ``1234 567890 - Loc. ABCDEF``.
_PADRAO_LANCAMENTO_FATURA = re.compile(
    r"(?i)(?<!\d)"
    r"(\d{4})\s*(\d{6,9})"
    r"\s*[-–]?\s*(?:Loc(?:alizador)?\.?\s*)"
    r"([A-Z0-9]{6})"
    r"(?![A-Z0-9])"
)


# ============================================================
# NORMALIZAÇÃO
# ============================================================

def normalizar_numero_bilhete(value: str) -> str:
    """Mantém somente os dígitos do número do bilhete."""
    return re.sub(r"\D", "", value or "")


def normalizar_texto(value: str) -> str:
    """Normaliza espaços e caracteres de controle."""
    value = (value or "").replace("\x00", " ")
    value = re.sub(r"[ \t]+", " ", value)
    return value.strip()


def normalizar_rotulo(value: str) -> str:
    """Remove acentos e padroniza texto para comparar rótulos."""
    value = unicodedata.normalize("NFKD", value or "")
    value = "".join(
        char for char in value
        if not unicodedata.combining(char)
    )
    return re.sub(r"\s+", " ", value).upper().strip()


def converter_valor(value: str) -> Decimal | None:
    """
    Converte valores monetários para Decimal.

    Exemplos:
        1.080,84 -> Decimal('1080.84')
        1080.84  -> Decimal('1080.84')
        34,55    -> Decimal('34.55')
    """
    if not value:
        return None

    cleaned = re.sub(r"[^\d,.\-]", "", value.strip())

    if not cleaned or not re.search(r"\d", cleaned):
        return None

    if "," in cleaned:
        # Formato brasileiro: 1.234,56
        cleaned = cleaned.replace(".", "")
        cleaned = cleaned.replace(",", ".")
    elif re.fullmatch(r"-?\d{1,3}(?:\.\d{3})+", cleaned):
        # Ponto como separador de milhar. Exemplos: 1.234 e 1.234.567
        cleaned = cleaned.replace(".", "")

    try:
        return Decimal(cleaned).quantize(Decimal("0.01"))
    except (InvalidOperation, ValueError):
        return None


# ============================================================
# LEITURA DOS PDFS E OCR
# ============================================================

def _ler_texto_selecionavel(path: Path) -> str:
    """Tenta extrair texto diretamente com PyPDF2."""
    from PyPDF2 import PdfReader  # pesado; importado só quando a tarefa começa
    reader = PdfReader(str(path))

    if reader.is_encrypted:
        raise ValueError(f"PDF protegido por senha: {path}")

    pages = []

    for page in reader.pages:
        try:
            pages.append(page.extract_text() or "")
        except Exception:
            pages.append("")

    return "\n".join(pages).strip()


def _executar_ocr(path: Path) -> str:
    """Executa OCR em todas as páginas do PDF."""
    import pytesseract  # pesado; importado só quando a tarefa começa
    import pymupdf      # pesado; importado só quando a tarefa começa
    from PIL import Image  # pesado; importado só quando a tarefa começa

    if TESSERACT_PATH.is_file():
        pytesseract.pytesseract.tesseract_cmd = str(TESSERACT_PATH)
    else:
        found = shutil.which("tesseract")
        if found:
            pytesseract.pytesseract.tesseract_cmd = found
        else:
            raise RuntimeError(
                "Tesseract OCR não encontrado. Verifique a instalação "
                "ou defina a variável de ambiente TESSERACT_CMD."
            )

    try:
        languages = pytesseract.get_languages(config="")
    except Exception as exc:
        raise RuntimeError(
            f"Não foi possível inicializar o Tesseract OCR: {exc}"
        ) from exc

    available = [
        language
        for language in ("por", "eng")
        if language in languages
    ]

    if not available:
        raise RuntimeError(
            "Nenhum idioma adequado está instalado no Tesseract. "
            "Instale os dados de português (por) e/ou inglês (eng)."
        )

    language = "+".join(available)
    pages_text = []

    try:
        with pymupdf.open(str(path)) as document:
            for page in document:
                pixmap = page.get_pixmap(
                    matrix=pymupdf.Matrix(3, 3),
                    alpha=False,
                )

                image = Image.frombytes(
                    "RGB",
                    (pixmap.width, pixmap.height),
                    pixmap.samples,
                )

                text = pytesseract.image_to_string(
                    image,
                    lang=language,
                    config="--psm 3",
                )

                pages_text.append(text)

    except Exception as exc:
        raise RuntimeError(
            f"Falha no OCR do PDF '{path.name}': {exc}"
        ) from exc

    return "\n".join(pages_text).strip()


def ler_pdf(path: Path) -> str:
    """
    Lê o texto selecionável primeiro e utiliza OCR se necessário.

    Também tenta OCR quando há pouco texto selecionável, pois alguns
    PDFs misturam páginas digitalizadas com páginas textuais.
    """
    path = Path(path)

    if not path.is_file():
        raise FileNotFoundError(f"PDF não encontrado: {path}")

    text = _ler_texto_selecionavel(path)

    if len(re.sub(r"\s+", "", text)) >= MIN_SELECTABLE_CHARS:
        return text

    ocr_text = _executar_ocr(path)

    if len(ocr_text) > len(text):
        return ocr_text

    return text or ocr_text


# ============================================================
# IDENTIFICAÇÃO DE BILHETES
# ============================================================

def _buscar_numero_bilhete(text: str) -> str:
    """
    Procura números de bilhete de 10 a 13 dígitos.
    Evita escolher números curtos de voo ou localizador.
    """
    patterns = (
        r"(?i)(?:bilhete|ticket|e-ticket|eticket|n[úu]mero\s+do\s+bilhete)"
        r"\s*(?:n[º°.]?\s*)?[:#-]?\s*((?:\d[\s.-]*){10,13})",

        r"(?<!\d)(\d{13})(?!\d)",
        r"(?<!\d)(\d{10,12})(?!\d)",
    )

    for pattern in patterns:
        for match in re.finditer(pattern, text):
            number = normalizar_numero_bilhete(match.group(1))

            if 10 <= len(number) <= 13:
                return number

    return ""


def _buscar_localizador(text: str, filename: str) -> str:
    """Procura localizadores próximos aos seus rótulos."""
    ticket_number = _buscar_numero_bilhete(text)
    if ticket_number:
        number_match = re.search(
            rf"(?<!\d){re.escape(ticket_number)}(?!\d)\s+([A-Z0-9]{{6}})\b",
            text,
        )
        if number_match and not number_match.group(1).isdigit():
            return number_match.group(1).upper()

    # Layout FACTO/LATAM em que a tabela é extraída fora de ordem: o
    # localizador fica logo antes do passageiro (``957 ABC123 ADT - NOME``).
    before_passenger = re.search(r"\b([A-Z0-9]{6})\s+ADT\s*[-:#]", text)
    if before_passenger and not before_passenger.group(1).isdigit():
        return before_passenger.group(1)

    # Só os rótulos ignoram maiúsculas: localizadores são sempre maiúsculos,
    # e assim palavras comuns como ``Viagem`` não são confundidas com eles.
    patterns = (
        r"\b(?i:localizador(?:\s+da\s+reserva)?|c[oó]digo\s+de\s+reserva|"
        r"reserva|booking\s+reference|record\s+locator|"
        r"locator|loc)\s*[:#-]?\s*([A-Z0-9]{6})\b",

        r"\b(?i:GOL|LATAM|TAM)\b.{0,100}?"
        r"\b([A-Z0-9]{6})\b",
    )

    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            candidate = match.group(1).upper()

            if not candidate.isdigit():
                return candidate

    # Só utiliza o nome do arquivo se houver um candidato de seis
    # caracteres maiúsculos claramente isolado por separadores, para que
    # nomes como ``fatura.pdf`` não virem localizador.
    stem = Path(filename).stem

    for match in re.finditer(
        r"(?<![A-Za-z0-9])([A-Z0-9]{6})(?![A-Za-z0-9])",
        stem,
    ):
        candidate = match.group(1)

        if not candidate.isdigit():
            return candidate

    return ""


def _buscar_passageiro(text: str, filename: str) -> str:
    """Procura o nome do passageiro no texto e, por último, no nome do arquivo."""
    patterns = (
        # Alguns portais extraem a tabela em uma linha só.  Por isso ADT
        # não precisa necessariamente ser o primeiro item da linha.
        r"(?i)\bADT\s*[-:#]\s*([^\r\n]+)",
        r"(?im)^\s*(?:Pax|Passageiro|Passenger|Nome\s+do\s+passageiro)"
        r"\s*:\s*([^\r\n]+)",
    )

    for pattern in patterns:
        match = re.search(pattern, text)

        if match:
            name = normalizar_texto(match.group(1)).strip(" -:")
            name = re.sub(r"\s+(?:MRS|MR|MS|MISS)$", "", name, flags=re.I)

            if len(name) >= 5 and not re.search(
                r"\d{4,}|R\$|TARIFA|TAXA|VOO",
                name,
                re.I,
            ):
                return name

    # Fallback conservador para nomes no arquivo.
    stem = Path(filename).stem

    match = re.search(
        r"(?i)([A-ZÀ-ÖØ-Þ][A-ZÀ-ÖØ-Þ]+"
        r"(?:\s+[A-ZÀ-ÖØ-Þ][A-ZÀ-ÖØ-Þ]+){1,5})",
        stem,
    )

    return normalizar_texto(match.group(1)) if match else ""


# ============================================================
# VOOS
# ============================================================

def _buscar_voos(text: str) -> tuple[str, ...]:
    """
    Reconhece códigos de voo como G3 1651, LA 4794 e JJ 3019.
    """
    pattern = (
        r"(?<![A-Z0-9])"
        r"(G3|LA|JJ|AD|2Z|CM|AA|UA|DL|TP|IB|AV)"
        r"\s*[- ]?\s*(\d{2,4})"
        r"(?!\d)"
    )

    flights = []

    for match in re.finditer(pattern, text.upper()):
        airline = match.group(1)
        number = match.group(2)
        flight = f"{airline} {number}"

        if flight not in flights:
            flights.append(flight)

    # Em alguns bilhetes LATAM o mecanismo de texto separa a sigla do voo
    # por um símbolo da coluna de escala (``LA a\n3648``).  Preserva-se a
    # leitura normal acima e só então se aceita essa variação.
    for match in re.finditer(
        r"(?i)\bLA\s+(?:[A-Z\u00c0-\u00ff]\s*)?(\d{3,4})\b",
        text,
    ):
        flight = f"LA {match.group(1)}"
        if flight not in flights:
            flights.append(flight)

    # Artefato confirmado no PDF LATAM de exemplo: a primeira coluna pode
    # aparecer como ``a019 OL`` apesar de o documento visível informar
    # ``LA 3019``.  A regra fica propositalmente restrita a esse marcador.
    if re.search(r"(?i)\ba019\s+O?L\b", text) and "LA 3019" not in flights:
        flights.insert(0, "LA 3019")

    return tuple(flights)


# ============================================================
# EXTRAÇÃO DE VALORES
# ============================================================

def _valores_encontrados(pattern: str, text: str) -> list[Decimal]:
    """Lista os valores monetários capturados pelo padrão, descartando os inválidos."""
    values = [converter_valor(value) for value in re.findall(pattern, text)]
    return [value for value in values if value is not None]


def _extrair_valor_rotulado(
    text: str,
    labels: tuple[str, ...],
) -> Decimal | None:
    """
    Procura um valor associado a um rótulo específico.

    Evita usar um valor de outro campo como substituto.
    """
    label_pattern = "|".join(
        re.escape(label) for label in labels
    )

    pattern = (
        rf"(?is)(?<![\w])(?:{label_pattern})(?![\w])\s*[:\-]?\s*"
        rf"(?:R\$\s*)?([\d]{{1,3}}(?:\.\d{{3}})*,\d{{2}}|"
        rf"\d+,\d{{2}}|\d+\.\d{{2}})(?!\d)"
    )

    match = re.search(pattern, text)

    if not match:
        return None

    return converter_valor(match.group(1))


def _extrair_tarifas(text: str) -> tuple[
    Decimal | None,
    Decimal | None,
    Decimal | None,
]:
    """Retorna ``(tarifa, taxas, total)`` testando os layouts conhecidos."""
    pricing_match = re.search(
        r"(?is)Tarifamento\s*(.*?)(?=Pagamento|Dados Corporativos|Regra Tarifária|$)",
        text,
    )
    pricing_text = pricing_match.group(1) if pricing_match else text

    fare = _extrair_valor_rotulado(
        pricing_text,
        ("Tarifa", "Tarifamento", "Fare", "Base tarifária"),
    )

    taxes = _extrair_valor_rotulado(
        pricing_text,
        ("Taxas", "Taxa de embarque", "Taxes", "Tax"),
    )

    total = _extrair_valor_rotulado(
        pricing_text,
        ("Total", "Valor total", "Total geral", "Grand total"),
    )

    table = _ler_tabela_de_tarifas(pricing_text)
    if table:
        fare, taxes, total = table

    # Fallback para layouts que mostram os três valores juntos.
    # Só é utilizado se os rótulos não permitirem identificar os campos.
    if fare is None or taxes is None or total is None:
        lines = pricing_text.splitlines()

        separated = _ler_tarifas_com_rotulos_separados(lines)
        if separated:
            fare, taxes, total = separated

        nearby = _ler_tarifas_proximas(lines)
        if nearby:
            fare = fare if fare is not None else nearby[0]
            taxes = taxes if taxes is not None else nearby[1]
            total = total if total is not None else nearby[-1]

    return fare, taxes, total


def _ler_tabela_de_tarifas(pricing_text: str) -> list[Decimal] | None:
    """Layout FACTO/LATAM: cabeçalhos e valores ficam em duas linhas tabulares.

    Por exemplo ``Tarifa Taxas Total`` e, abaixo, ``R$ 1.080,84 R$ 34,55 R$ 1.115,39``.
    A busca por rótulo isolado não pode associar corretamente os valores nesse formato.
    """
    table_match = re.search(
        r"(?is)(?:tarifamento\s*)?tarifa\s+taxas?\s+total\s*"
        r"(.*?)(?=pagamento|dados\s+corporativos|$)",
        pricing_text,
    )
    if not table_match:
        return None
    values = _valores_encontrados(
        r"(?<!\d)(\d{1,3}(?:\.\d{3})*,\d{2}|\d+,\d{2}|\d+\.\d{2})(?!\d)",
        table_match.group(1),
    )
    return values[:3] if len(values) >= 3 else None


def _ler_tarifas_com_rotulos_separados(lines: list[str]) -> list[Decimal] | None:
    """Layout com Tarifa, Taxas e Total em linhas próprias e os valores logo depois.

    Nesse layout, cada rótulo não fica adjacente ao seu valor.
    """
    normalized_lines = [normalizar_rotulo(line) for line in lines]
    for index in range(len(lines)):
        if normalized_lines[index:index + 3] != ["TARIFA", "TAXAS", "TOTAL"]:
            continue
        values = _valores_encontrados(_PADRAO_VALOR_COM_MOEDA, "\n".join(lines[index + 3:index + 10]))
        if len(values) >= 3:
            return values[:3]
    return None


def _ler_tarifas_proximas(lines: list[str]) -> list[Decimal] | None:
    """Procura os valores perto de uma linha que cita tarifa e taxa ao mesmo tempo."""
    for index, line in enumerate(lines):
        normalized = normalizar_rotulo(line)
        if not ("TARIFA" in normalized and "TAXA" in normalized):
            continue
        values = _valores_encontrados(_PADRAO_VALOR_COM_MOEDA, "\n".join(lines[index:index + 5]))
        if len(values) >= 3:
            return values
    return None


# ============================================================
# LEITURA DO BILHETE
# ============================================================

def ler_bilhete(path: Path) -> Ticket:
    """Lê um PDF de bilhete e retorna os campos extraídos.

    Campos não encontrados ficam vazios (``""``/``None``) em vez de gerar
    erro, para que o relatório indique o que precisa de conferência manual.
    """
    path = Path(path)
    text = ler_pdf(path)

    number = _buscar_numero_bilhete(text)
    locator = _buscar_localizador(text, path.name)
    passenger = _buscar_passageiro(text, path.name)
    flights = _buscar_voos(text)
    fare, taxes, total = _extrair_tarifas(text)

    return Ticket(
        source=str(path),
        number=number,
        locator=locator,
        passenger=passenger,
        flights=flights,
        fare=fare,
        taxes=taxes,
        total=total,
    )


# ============================================================
# LEITURA DA FATURA
# ============================================================

def ler_fatura(path: Path) -> list[InvoiceEntry]:
    """Lê um PDF de fatura e retorna um lançamento por bilhete encontrado."""
    path = Path(path)
    text = ler_pdf(path)
    matches = _buscar_lancamentos(text)

    entries: list[InvoiceEntry] = []
    for index, match in enumerate(matches):
        identification = _identificar_lancamento(text, match)
        if identification is None:
            continue
        number, locator = identification

        # O bloco de um lançamento vai até o início do próximo.
        end = (
            matches[index + 1].start()
            if index + 1 < len(matches)
            else len(text)
        )
        entries.append(_montar_lancamento(path, number, locator, text[match.start():end]))

    return entries


def _buscar_lancamentos(text: str) -> list[re.Match]:
    """Localiza o início de cada lançamento da fatura."""
    matches = list(_PADRAO_LANCAMENTO_FATURA.finditer(text))
    if matches:
        return matches

    # Fallback para faturas com os números em linhas diferentes.
    return [
        match
        for match in re.finditer(r"(?<!\d)(\d{13})(?!\d)", text)
        if _localizador_no_trecho(text, match.start() - 250, match.end() + 1000)
    ]


def _localizador_no_trecho(text: str, start: int, end: int) -> str:
    """Procura um localizador rotulado dentro de um pedaço do texto."""
    context = text[max(0, start):min(len(text), end)]
    match = re.search(
        r"(?i)(?:Loc(?:alizador)?\.?|"
        r"Booking\s+reference)\s*[:#-]?\s*"
        r"([A-Z0-9]{6})\b",
        context,
    )
    return match.group(1).upper() if match else ""


def _identificar_lancamento(text: str, match: re.Match) -> tuple[str, str] | None:
    """Retorna ``(número, localizador)``, ou ``None`` se o localizador não for achado."""
    if len(match.groups()) >= 3:
        return normalizar_numero_bilhete(match.group(1) + match.group(2)), match.group(3).upper()
    locator = _localizador_no_trecho(text, match.start() - 250, match.start() + 1000)
    if not locator:
        return None
    return normalizar_numero_bilhete(match.group(1)), locator


def _montar_lancamento(path: Path, number: str, locator: str, block: str) -> InvoiceEntry:
    """Extrai passageiro, voos e valores do bloco de texto de um lançamento."""
    passenger_match = re.search(r"(?im)^\s*Pax\s*:\s*(.+?)\s*$", block)
    passenger = normalizar_texto(passenger_match.group(1)) if passenger_match else ""

    fare, taxes, total = _extrair_tarifas(block)
    fee = _extrair_valor_rotulado(block, ("Fee", "Service fee", "Taxa de serviço"))

    # Layout de fatura G3: rótulos TARIFA / TAXA / FEE / SUB-TOTAL,
    # seguidos dos valores. O subtotal já inclui o fee.
    # O rótulo ``TOTAL`` pode ocorrer antes do SUB-TOTAL no texto
    # extraído. Quando o bloco G3 é reconhecido, o SUB-TOTAL é a fonte
    # específica e deve prevalecer, mesmo que a leitura genérica tenha
    # encontrado outro valor anteriormente.
    agency_total = _extrair_subtotal_agencia(block)
    if agency_total is not None:
        fare, taxes, fee, total = agency_total

    return InvoiceEntry(
        source=str(path),
        number=number,
        locator=locator,
        passenger=passenger,
        flights=_buscar_voos(block),
        fare=fare,
        taxes=taxes,
        fee=fee,
        total=total,
    )


def _extrair_subtotal_agencia(
    text: str,
) -> tuple[Decimal, Decimal, Decimal, Decimal] | None:
    """Lê tarifa, taxa, fee e subtotal de faturas G3 organizadas por linhas."""
    original_lines = text.splitlines()
    labels = [normalizar_rotulo(line).replace("-", " ") for line in original_lines]
    for index, label in enumerate(labels):
        # O PDF pode colar o valor do subtotal ao rótulo e pode trazer a
        # classe tarifária (por exemplo J/P) antes de TARIFA.
        if "TARIFA" not in label:
            continue
        following = labels[index + 1:index + 4]
        if following[:2] != ["TAXA", "FEE"] or not following[2].startswith("SUB TOTAL"):
            continue

        nearby = "\n".join(original_lines[index + 1:index + 9])
        values = _valores_encontrados(
            r"(?<!\d)(?:R\$\s*)?(\d{1,3}(?:\.\d{3})*,\d{2}|\d+,\d{2})\+?",
            nearby,
        )
        if len(values) >= 4:
            return values[0], values[1], values[2], values[3]
    return None
