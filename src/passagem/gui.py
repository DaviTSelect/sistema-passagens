"""Interface gráfica (PySide6): conferência de fatura e extração de trechos.

Como a janela está organizada:

- ``App._montar_*`` desenham cada parte da tela.
- ``MODO_TEXTOS`` guarda os textos que mudam entre as duas funções.
- ``App.iniciar_tarefa`` roda o trabalho em uma thread, para a janela não travar.
- As threads só falam com a tela por sinais (``sinal_*``); acessar um componente
  da tela diretamente de uma thread pode derrubar o programa.

Para adicionar uma nova função: crie um ``MODE_*`` e seus textos, monte as linhas
em ``_montar_paginas`` e trate o novo modo em ``_selecoes`` e ``iniciar_tarefa``.
"""
from __future__ import annotations

import ctypes
from datetime import datetime
import sys
import threading
from pathlib import Path
from typing import TYPE_CHECKING

from PySide6.QtCore import QPointF, Qt, Signal
from PySide6.QtGui import QColor, QFont, QIcon, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import (
    QApplication, QFileDialog, QFrame, QGraphicsDropShadowEffect, QHBoxLayout,
    QLabel, QLayout, QMessageBox, QPushButton, QStackedWidget, QVBoxLayout, QWidget,
)


from . import auto_update
from .version import __version__

# Importados só para checagem de tipo; o carregamento real ocorre ao iniciar a tarefa.
if TYPE_CHECKING:
    from .conference import ConferenceResult
    from .trechos import ExtractionResult

# Mantém o handle do mutex aberto enquanto o processo executa (instância única).
_MUTEX_INSTANCIA = None

# Identidade visual padronizada com os demais painéis da automação.
BG = '#203447'
TEXT = '#efede5'
ACTION = '#e94c1f'
COR_DIVISOR_ESCURO = '#415364'
COR_ICONE = '#7a8791'
COR_SELECIONADO = '#317458'

# Verde é reservado à confirmação de que a versão é a mais recente.
UPDATE_OK = '#53b88c'
UPDATE_BUSY = '#e9b44c'
UPDATE_UNKNOWN = '#85929c'

ESTILO_FUNDO_ICONE = 'background: #e9eef0; border-radius: 12px;'
ESTILO_FUNDO_ICONE_SELECIONADO = 'background: #e5f4ed; border-radius: 12px;'
ESTILO_BOTAO_LINHA = '''QPushButton {background:#ffffff; border:1px solid #d9dddc; border-radius:9px;
    color:#344a5b; font-family:"Segoe UI"; font-size:11px; font-weight:600; padding:0 12px;}
    QPushButton:hover {background:#f1f3f1; border-color:#b5bec3;}'''
ESTILO_INICIAR_ATIVO = f'''QPushButton {{background:{ACTION}; color:white; border:none; border-radius:9px;
    font:600 11px "Segoe UI"; padding:0 19px;}}
    QPushButton:hover {{background:#d74118;}}'''
ESTILO_INICIAR_INATIVO = '''QPushButton {background:#d8dad9; color:#92999b; border:none;
    border-radius:9px; font:600 11px "Segoe UI"; padding:0 19px;}'''

ICON_FILENAME = 'logo.ico'
MAX_WARNINGS_SHOWN = 10
DEFAULT_SPREADSHEET = 'PlanilhaPassagens_por_trecho.xlsx'

MODE_CONFERENCE = 0
MODE_EXTRACTION = 1
# Textos que mudam conforme a função escolhida na janela.
MODE_TEXTS = {
    MODE_CONFERENCE: {
        'eyebrow': 'N O V A   C O N F E R Ê N C I A',
        'intro': 'Selecione os documentos necessários. O sistema irá cruzar os bilhetes com a fatura e gerar um relatório completo.',
        'title': 'Configurar conferência',
        'subtitle': 'Preencha as três etapas para continuar',
        'start': 'Iniciar conferência   →',
        'running': 'Conferência em andamento',
        'running_hint': 'Aguarde: os PDFs estão sendo lidos e comparados.',
        'done': 'Conferência concluída',
    },
    MODE_EXTRACTION: {
        'eyebrow': 'N O V A   E X T R A Ç Ã O',
        'intro': 'Selecione a pasta dos bilhetes. O sistema irá ler cada trecho de voo e atualizar a planilha Excel, sem duplicar o que já existe.',
        'title': 'Configurar extração',
        'subtitle': 'Preencha as duas etapas para continuar',
        'start': 'Iniciar extração   →',
        'running': 'Extração em andamento',
        'running_hint': 'Aguarde: PDFs digitalizados podem levar mais tempo.',
        'done': 'Extração concluída',
    },
}


def _garantir_instancia_unica() -> bool:
    """Cria um mutex nomeado no Windows. Retorna False se já há outra instância."""
    global _MUTEX_INSTANCIA
    if sys.platform != 'win32':
        return True
    ERROR_ALREADY_EXISTS = 183
    _MUTEX_INSTANCIA = ctypes.windll.kernel32.CreateMutexW(None, False, 'SistemaPassagens_Mutex_v1')
    return ctypes.windll.kernel32.GetLastError() != ERROR_ALREADY_EXISTS


def caminho_recurso(filename: str) -> Path:
    """Retorna o caminho de um recurso no Python ou no executável."""
    if getattr(sys, 'frozen', False):
        base_path = Path(getattr(sys, '_MEIPASS', Path(sys.executable).parent))
    else:
        base_path = Path(__file__).resolve().parents[2]
    return base_path / filename


def formatar_resumo_conferencia(result: ConferenceResult, output_file: Path) -> str:
    """Monta a mensagem exibida ao final da conferência."""
    message = (
        f'Conferência concluída. {result.ticket_count} bilhete(s) processado(s).\n'
        f'Planilha: {output_file}'
    )
    return _anexar_avisos(message, result.warnings)


def formatar_resumo_extracao(result: ExtractionResult, output_file: Path) -> str:
    """Monta a mensagem exibida ao final da extração de trechos."""
    message = (
        f'Extração concluída. {result.pdf_count} PDF(s), {result.segment_count} trecho(s): '
        f'{result.added} novo(s), {result.updated} atualizado(s) e {result.unchanged} sem alteração.\n'
        f'Planilha: {output_file}'
    )
    return _anexar_avisos(message, result.warnings)


def _anexar_avisos(message: str, warnings: list[str]) -> str:
    """Acrescenta os avisos à mensagem, limitando quantos aparecem na tela."""
    if warnings:
        message += f'\n\nAvisos ({len(warnings)}):\n'
        message += '\n'.join(warnings[:MAX_WARNINGS_SHOWN])
        hidden = len(warnings) - MAX_WARNINGS_SHOWN
        if hidden > 0:
            message += f'\n... e mais {hidden} aviso(s).'
    return message


def caminho_relatorio(folder: str) -> Path:
    """Gera um nome com data e hora para nunca sobrescrever um relatório anterior."""
    return Path(folder) / f'conferencia_{datetime.now():%Y%m%d_%H%M%S}.csv'


class Icon(QWidget):
    """Ícone em traços, desenhado em uma grade de 24x24. ``kind`` escolhe o desenho."""

    def __init__(self, kind, color=COR_ICONE, size=24, parent=None):
        super().__init__(parent)
        self.kind, self.color = kind, color
        self.setFixedSize(size, size)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.scale(self.width()/24, self.height()/24)
        pen = QPen(QColor(self.color), 1.7, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
        p.setPen(pen)
        p.setBrush(Qt.NoBrush)
        if self.kind in ('folder', 'save'):
            self._desenhar_pasta(p, com_seta=self.kind == 'save')
        elif self.kind == 'file':
            self._desenhar_arquivo(p)
        elif self.kind == 'check':
            pen.setWidthF(2)
            p.setPen(pen)
            self._desenhar_confirmacao(p)
        p.end()

    @staticmethod
    def _desenhar_linha(p, x1, y1, x2, y2):
        p.drawLine(QPointF(x1, y1), QPointF(x2, y2))

    def _desenhar_pasta(self, p, com_seta):
        path = QPainterPath()
        path.moveTo(3.75, 16.25)
        path.lineTo(3.75, 6.75)
        path.cubicTo(3.75, 5.65, 4.65, 4.75, 5.75, 4.75)
        path.lineTo(9.11, 4.75)
        path.lineTo(11.91, 7.75)
        path.lineTo(18.25, 7.75)
        path.cubicTo(19.35, 7.75, 20.25, 8.65, 20.25, 9.75)
        path.lineTo(20.25, 16.25)
        path.cubicTo(20.25, 18, 19, 19.25, 17.25, 19.25)
        path.lineTo(6.75, 19.25)
        path.cubicTo(5, 19.25, 3.75, 18, 3.75, 16.25)
        p.drawPath(path)
        if com_seta:
            self._desenhar_linha(p, 12, 10.5, 12, 15.5)
            self._desenhar_linha(p, 10, 13.5, 12, 15.5)
            self._desenhar_linha(p, 14, 13.5, 12, 15.5)

    def _desenhar_arquivo(self, p):
        path = QPainterPath()
        path.moveTo(7, 3.75)
        path.lineTo(13.17, 3.75)
        path.lineTo(18, 8.58)
        path.lineTo(18, 20.25)
        path.lineTo(7, 20.25)
        path.cubicTo(5.7, 20.25, 5, 19.4, 5, 18.25)
        path.lineTo(5, 5.75)
        path.cubicTo(5, 4.6, 5.8, 3.75, 7, 3.75)
        p.drawPath(path)
        self._desenhar_linha(p, 13.5, 4, 13.5, 8.5)
        self._desenhar_linha(p, 13.5, 8.5, 18, 8.5)
        self._desenhar_linha(p, 8.5, 13, 15.25, 13)
        self._desenhar_linha(p, 8.5, 16.5, 13.25, 16.5)

    @staticmethod
    def _desenhar_confirmacao(p):
        path = QPainterPath()
        path.moveTo(6.75, 12.25)
        path.lineTo(10, 15.5)
        path.lineTo(17.25, 8.25)
        p.drawPath(path)


def criar_rotulo(text, size, color, weight=QFont.Normal, wrap=False):
    """Cria um texto na fonte padrão da janela."""
    w = QLabel(text)
    f = QFont('Segoe UI', size)
    f.setWeight(weight)
    w.setFont(f)
    w.setStyleSheet(f'color: {color}; background: transparent;')
    w.setWordWrap(wrap)
    return w


def criar_divisor(color):
    """Cria uma linha horizontal de 1 pixel."""
    d = QFrame()
    d.setFixedHeight(1)
    d.setStyleSheet(f'background:{color}; border:none;')
    return d


class SelectionRow(QFrame):
    """Etapa do cartão: ícone, textos, valor escolhido e botão de seleção."""

    def __init__(self, number, title, description, button_text, icon_kind, choose):
        super().__init__()
        self.button_text = button_text
        self.icon_kind = icon_kind
        self.setObjectName('selectionRow')
        self.setStyleSheet('#selectionRow { background: transparent; border: none; }')
        self.setMinimumHeight(130)
        outer = QHBoxLayout(self)
        outer.setContentsMargins(16, 22, 16, 22)
        outer.setSpacing(12)
        self.icon_holder = QFrame()
        self.icon_holder.setFixedSize(43, 43)
        self.icon_holder.setStyleSheet(ESTILO_FUNDO_ICONE)
        self.icon_lay = QHBoxLayout(self.icon_holder)
        self.icon_lay.setContentsMargins(0, 0, 0, 0)
        self.icon_lay.addWidget(Icon(icon_kind))
        outer.addWidget(self.icon_holder, 0, Qt.AlignTop)
        outer.addLayout(self._montar_textos(number, title, description), 1)
        self.button = QPushButton(button_text)
        self.button.setCursor(Qt.PointingHandCursor)
        self.button.setMinimumWidth(126)
        self.button.setFixedHeight(39)
        self.button.setStyleSheet(ESTILO_BOTAO_LINHA)
        self.button.clicked.connect(choose)
        outer.addWidget(self.button, 0, Qt.AlignVCenter)

    def _montar_textos(self, number, title, description) -> QLayout:
        content = QVBoxLayout()
        content.setSpacing(0)
        content.setContentsMargins(0, 1, 0, 0)
        head = QHBoxLayout()
        head.setSpacing(9)
        head.setContentsMargins(0, 0, 0, 0)
        head.addWidget(criar_rotulo('ETAPA '+number, 9, '#7b8791', QFont.Bold))
        self.status = criar_rotulo('SELECIONADO', 8, COR_SELECIONADO, QFont.Bold)
        self.status.setStyleSheet(f'color: {COR_SELECIONADO}; background: #e5f4ed; border-radius: 9px; padding: 3px 8px;')
        self.status.hide()
        head.addWidget(self.status)
        head.addStretch()
        content.addLayout(head)
        content.addSpacing(6)
        content.addWidget(criar_rotulo(title, 12, BG, QFont.DemiBold))
        content.addSpacing(5)
        content.addWidget(criar_rotulo(description, 10, '#6d7780', wrap=True))
        self.current = criar_rotulo('', 10, '#344b5e', QFont.Medium)
        self.current.hide()
        content.addSpacing(6)
        content.addWidget(self.current)
        content.addStretch()
        return content

    def definir_valor(self, value):
        """Mostra o valor escolhido e troca o ícone pela marca de confirmação."""
        selected = bool(value)
        self.status.setVisible(selected)
        self.current.setText(value)
        self.current.setToolTip(value)
        self.current.setVisible(selected)
        self.button.setText('Alterar' if selected else self.button_text)
        old = self.icon_lay.takeAt(0)
        if old and old.widget():
            old.widget().deleteLater()
        self.icon_lay.addWidget(Icon('check' if selected else self.icon_kind,
                                     COR_SELECIONADO if selected else COR_ICONE))
        self.icon_holder.setStyleSheet(ESTILO_FUNDO_ICONE_SELECIONADO if selected else ESTILO_FUNDO_ICONE)


class App(QWidget):
    """Janela principal: conferência, extração de trechos e status da versão."""

    # As threads de trabalho só falam com a tela por sinais.
    sinal_status_atualizacao = Signal(str, str)
    sinal_atualizacao_pronta = Signal()
    sinal_download = Signal(bool)
    sinal_tarefa_concluida = Signal(str, str)
    sinal_tarefa_falhou = Signal(str)

    def __init__(self):
        super().__init__()
        self.setWindowTitle(f'Central de passagens - {__version__}')
        self.resize(1240, 740)
        self.setMinimumSize(900, 690)
        # Caminhos escolhidos pelo usuário em cada função.
        self.tickets_folder = ''
        self.invoice_path = ''
        self.output_folder = ''
        self.extraction_folder = ''
        self.spreadsheet_path = ''
        self.mode = MODE_CONFERENCE
        # Estado do processamento e da atualização automática.
        self.started = False
        self.downloading = False
        self.restart_pending = False
        self.setStyleSheet(f'background: {BG};')

        root = QVBoxLayout(self)
        root.setContentsMargins(48, 24, 48, 26)
        root.setSpacing(0)
        self._montar_cabecalho(root)
        center = QHBoxLayout()
        center.setSpacing(65)
        center.addLayout(self._montar_painel_esquerdo(), 5)
        center.addWidget(self._montar_cartao(), 9)
        root.addLayout(center, 1)
        self._montar_rodape(root)

        self.sinal_status_atualizacao.connect(self.exibir_status_atualizacao)
        self.sinal_atualizacao_pronta.connect(self.ao_concluir_atualizacao)
        self.sinal_download.connect(self.ao_mudar_download)
        self.sinal_tarefa_concluida.connect(self.ao_concluir_tarefa)
        self.sinal_tarefa_falhou.connect(self.ao_falhar_tarefa)
        self.exibir_status_atualizacao(UPDATE_BUSY, 'Verificando atualização...')
        self.definir_modo(MODE_CONFERENCE)

    # ------------------------------------------------------------------
    # Montagem da tela
    # ------------------------------------------------------------------

    def _montar_cabecalho(self, root):
        """Título da aplicação e, à direita, o status da versão."""
        header = QHBoxLayout()
        heading = QVBoxLayout()
        heading.setSpacing(5)
        heading.addWidget(criar_rotulo('G E S T Ã O   O P E R A C I O N A L', 9, '#85929c', QFont.Bold))
        heading.addWidget(criar_rotulo('Central de passagens', 14, TEXT, QFont.DemiBold))
        header.addLayout(heading)
        header.addStretch()
        self.update_dot = QLabel('●')
        header.addWidget(self.update_dot)
        self.update_text = criar_rotulo('', 10, '#a0aab1', QFont.Medium)
        header.addWidget(self.update_text)
        root.addLayout(header)
        root.addSpacing(20)
        root.addWidget(criar_divisor(COR_DIVISOR_ESCURO))

    def _montar_painel_esquerdo(self) -> QLayout:
        """Apresentação que acompanha a função escolhida."""
        left = QVBoxLayout()
        left.setContentsMargins(0, 0, 0, 0)
        left.setSpacing(0)
        left.addStretch()
        self.eyebrow = criar_rotulo('', 9, ACTION, QFont.Bold)
        left.addWidget(self.eyebrow)
        left.addSpacing(20)
        left.addWidget(criar_rotulo('Revise seus dados\ncom confiança.', 29, TEXT, QFont.DemiBold, True))
        left.addSpacing(22)
        self.intro = criar_rotulo('', 12, '#a5afb6', wrap=True)
        self.intro.setMinimumWidth(270)
        self.intro.setMaximumWidth(365)
        left.addWidget(self.intro)
        left.addSpacing(37)
        left.addWidget(criar_divisor(COR_DIVISOR_ESCURO))
        left.addSpacing(24)
        security = QHBoxLayout()
        security.setSpacing(14)
        circle = QFrame()
        circle.setFixedSize(34, 34)
        circle.setStyleSheet('background:#304658; border-radius:17px;')
        circle_layout = QHBoxLayout(circle)
        circle_layout.setContentsMargins(5, 5, 5, 5)
        circle_layout.addWidget(Icon('file', '#a6b4bd', 20))
        security.addWidget(circle, 0, Qt.AlignTop)
        security.addWidget(criar_rotulo('Seus arquivos são processados com segurança e não são compartilhados.', 10, '#8998a3', wrap=True), 1)
        left.addLayout(security)
        left.addStretch()
        return left

    def _montar_cartao(self) -> QFrame:
        """Cartão claro da direita, com o seletor de função, as etapas e o botão de início."""
        card = QFrame()
        card.setObjectName('card')
        card.setStyleSheet('#card {background: #f8f7f3; border-radius: 18px;}')
        shadow = QGraphicsDropShadowEffect(card)
        shadow.setBlurRadius(52)
        shadow.setOffset(0, 22)
        shadow.setColor(QColor(6, 18, 28, 80))
        card.setGraphicsEffect(shadow)
        layout = QVBoxLayout(card)
        layout.setSpacing(0)
        layout.setContentsMargins(0, 0, 0, 0)
        self._montar_seletor_modo(layout)
        self._montar_titulo_cartao(layout)
        layout.addWidget(criar_divisor('#dde1df'))
        self._montar_paginas(layout)
        self._montar_rodape_cartao(layout)
        return card

    def _montar_seletor_modo(self, layout):
        modes = QHBoxLayout()
        modes.setContentsMargins(30, 18, 30, 0)
        modes.setSpacing(8)
        self.mode_buttons = []
        for mode, text in ((MODE_CONFERENCE, 'Conferir fatura'), (MODE_EXTRACTION, 'Extrair trechos')):
            button = QPushButton(text)
            button.setFixedHeight(34)
            button.setCursor(Qt.PointingHandCursor)
            button.clicked.connect(lambda _checked=False, m=mode: self.definir_modo(m))
            modes.addWidget(button)
            self.mode_buttons.append(button)
        modes.addStretch()
        layout.addLayout(modes)

    def _montar_titulo_cartao(self, layout):
        top = QHBoxLayout()
        top.setContentsMargins(30, 16, 30, 16)
        titles = QVBoxLayout()
        titles.setSpacing(5)
        self.card_title = criar_rotulo('', 14, BG, QFont.DemiBold)
        self.card_subtitle = criar_rotulo('', 10, '#7a838a')
        titles.addWidget(self.card_title)
        titles.addWidget(self.card_subtitle)
        top.addLayout(titles)
        top.addStretch()
        self.count = criar_rotulo('0 de 3', 9, '#68747d', QFont.Bold)
        self.count.setStyleSheet('color:#68747d; background:transparent; border:1px solid #d9dddc; border-radius:12px; padding:7px 12px;')
        top.addWidget(self.count)
        layout.addLayout(top)

    def _montar_paginas(self, layout):
        """Uma página de etapas para cada função; a ordem acompanha os ``MODE_*``."""
        self.rows = [
            SelectionRow('01', 'Pasta com os bilhetes', 'Selecione a pasta que contém os PDFs dos bilhetes.', 'Selecionar pasta', 'folder', self.escolher_bilhetes),
            SelectionRow('02', 'Fatura de conferência', 'Escolha o PDF da fatura que será usada como referência.', 'Selecionar fatura', 'file', self.escolher_fatura),
            SelectionRow('03', 'Local do resultado', 'Defina a pasta onde o relatório CSV será salvo.', 'Selecionar local', 'save', self.escolher_destino),
        ]
        self.extraction_rows = [
            SelectionRow('01', 'Pasta com os bilhetes', 'Selecione a pasta que contém os PDFs das passagens.', 'Selecionar pasta', 'folder', self.escolher_pasta_extracao),
            SelectionRow('02', 'Planilha de trechos', 'Escolha uma planilha nova ou existente; o que já estiver nela não será duplicado.', 'Selecionar planilha', 'save', self.escolher_planilha),
        ]
        self.pages = QStackedWidget()
        self.pages.setStyleSheet('background: transparent;')
        for rows in (self.rows, self.extraction_rows):
            page = QWidget()
            page_layout = QVBoxLayout(page)
            page_layout.setContentsMargins(0, 0, 0, 0)
            page_layout.setSpacing(0)
            for i, row in enumerate(rows):
                page_layout.addWidget(row)
                if i < len(rows) - 1:
                    page_layout.addWidget(criar_divisor('#e3e5e2'))
            page_layout.addStretch()
            self.pages.addWidget(page)
        layout.addWidget(self.pages)

    def _montar_rodape_cartao(self, layout):
        footer = QFrame()
        footer.setStyleSheet('background: #f1f1ed; border-bottom-left-radius: 18px; border-bottom-right-radius:18px;')
        footer_layout = QHBoxLayout(footer)
        footer_layout.setContentsMargins(30, 20, 30, 20)
        texts = QVBoxLayout()
        texts.setSpacing(5)
        self.ready_title = criar_rotulo('Aguardando configurações', 10, '#344a5b', QFont.DemiBold)
        self.ready_hint = criar_rotulo('Complete as etapas acima para continuar.', 9, '#838c91', wrap=True)
        texts.addWidget(self.ready_title)
        texts.addWidget(self.ready_hint)
        footer_layout.addLayout(texts, 1)
        self.start = QPushButton()
        self.start.setFixedHeight(46)
        self.start.setMinimumWidth(170)
        self.start.setCursor(Qt.PointingHandCursor)
        self.start.clicked.connect(self.iniciar_tarefa)
        footer_layout.addWidget(self.start)
        layout.addWidget(footer)

    def _montar_rodape(self, root):
        root.addWidget(criar_divisor(COR_DIVISOR_ESCURO))
        root.addSpacing(17)
        bottom = QHBoxLayout()
        bottom.addWidget(criar_rotulo('Central de passagens', 9, '#83919c'))
        bottom.addStretch()
        bottom.addWidget(criar_rotulo('Ambiente seguro', 9, '#83919c'))
        root.addLayout(bottom)

    # ------------------------------------------------------------------
    # Seleção da função e dos arquivos
    # ------------------------------------------------------------------

    def definir_modo(self, mode):
        """Troca entre conferência e extração, atualizando textos e etapas."""
        self.mode = mode
        texts = MODE_TEXTS[mode]
        self.pages.setCurrentIndex(mode)
        self.eyebrow.setText(texts['eyebrow'])
        self.intro.setText(texts['intro'])
        self.card_title.setText(texts['title'])
        self.card_subtitle.setText(texts['subtitle'])
        self.start.setText(texts['start'])
        for index, button in enumerate(self.mode_buttons):
            active = index == mode
            button.setStyleSheet(f'''QPushButton {{background:{BG if active else 'transparent'};
                color:{TEXT if active else '#344a5b'}; border:1px solid {BG if active else '#d9dddc'};
                border-radius:8px; font:600 11px "Segoe UI"; padding:0 14px;}}''')
        self.atualizar_estado()

    def _selecionar_pasta(self, titulo, atributo, linha):
        """Pergunta uma pasta, guarda em ``atributo`` e a exibe em ``linha``."""
        v = QFileDialog.getExistingDirectory(self, titulo)
        if v:
            setattr(self, atributo, v)
            linha.definir_valor(Path(v).name or v)  # Raiz de disco não tem nome.
            self.atualizar_estado()

    def escolher_bilhetes(self):
        self._selecionar_pasta('Selecionar pasta com bilhetes', 'tickets_folder', self.rows[0])

    def escolher_fatura(self):
        v, _ = QFileDialog.getOpenFileName(self, 'Selecionar fatura de conferência', '', 'Faturas (*.pdf)')
        if v:
            self.invoice_path = v
            self.rows[1].definir_valor(Path(v).name)
            self.atualizar_estado()

    def escolher_destino(self):
        self._selecionar_pasta('Selecionar local do resultado', 'output_folder', self.rows[2])

    def escolher_pasta_extracao(self):
        self._selecionar_pasta('Selecionar pasta com os PDFs', 'extraction_folder', self.extraction_rows[0])

    def escolher_planilha(self):
        # A planilha existente é atualizada, então não cabe perguntar se deve substituí-la.
        v, _ = QFileDialog.getSaveFileName(self, 'Selecionar planilha de trechos', DEFAULT_SPREADSHEET,
                                           'Planilhas Excel (*.xlsx)',
                                           options=QFileDialog.DontConfirmOverwrite)
        if v:
            self.spreadsheet_path = str(Path(v).with_suffix('.xlsx'))
            self.extraction_rows[1].definir_valor(Path(self.spreadsheet_path).name)
            self.atualizar_estado()

    def _selecoes(self):
        """Valores exigidos pela função atual; vazios significam etapa pendente."""
        if self.mode == MODE_EXTRACTION:
            return (self.extraction_folder, self.spreadsheet_path)
        return (self.tickets_folder, self.invoice_path, self.output_folder)

    def atualizar_estado(self):
        """Sincroniza contador, textos do rodapé e botão de início com o estado atual."""
        selections = self._selecoes()
        count = sum(bool(x) for x in selections)
        ready = count == len(selections)
        blocked = self.downloading or self.restart_pending
        can_start = ready and not self.started and not blocked
        texts = MODE_TEXTS[self.mode]
        self.count.setText(f'{count} de {len(selections)}')
        for button in self.mode_buttons:
            button.setEnabled(not self.started)
        if self.started:
            self.ready_title.setText(texts['running'])
            self.ready_hint.setText(texts['running_hint'])
        elif blocked:
            self.ready_title.setText('Atualização em andamento')
            self.ready_hint.setText('O início será liberado ao final da atualização.')
        else:
            self.ready_title.setText('Tudo pronto para começar' if ready else 'Aguardando configurações')
            self.ready_hint.setText('Revise as escolhas e inicie a análise.' if ready else 'Complete as etapas acima para continuar.')
        self.start.setEnabled(can_start)
        self.start.setStyleSheet(ESTILO_INICIAR_ATIVO if can_start else ESTILO_INICIAR_INATIVO)

    # ------------------------------------------------------------------
    # Processamento em segundo plano
    # ------------------------------------------------------------------

    def iniciar_tarefa(self):
        """Inicia a função atual em uma thread, para a janela continuar respondendo."""
        if not all(self._selecoes()) or self.started:
            return
        self.started = True
        self.start.setText('◌  Processando...')
        self.atualizar_estado()
        if self.mode == MODE_EXTRACTION:
            target, args = self._executar_extracao, (Path(self.extraction_folder), Path(self.spreadsheet_path))
        else:
            target = self._executar_conferencia
            args = (Path(self.tickets_folder), Path(self.invoice_path), caminho_relatorio(self.output_folder))
        threading.Thread(target=target, args=args, daemon=True).start()

    def _executar_conferencia(self, tickets: Path, invoice: Path, output_file: Path):
        from .conference import executar_conferencia  # carregado só aqui; evita 50MB na abertura
        try:
            result = executar_conferencia(tickets, invoice, output_file)
            self.sinal_tarefa_concluida.emit(MODE_TEXTS[MODE_CONFERENCE]['done'], formatar_resumo_conferencia(result, output_file))
        except Exception as exc:
            self.sinal_tarefa_falhou.emit(str(exc))

    def _executar_extracao(self, folder: Path, output_file: Path):
        from .trechos import executar_extracao  # carregado só aqui; evita 50MB na abertura
        try:
            result = executar_extracao(folder, output_file)
            self.sinal_tarefa_concluida.emit(MODE_TEXTS[MODE_EXTRACTION]['done'], formatar_resumo_extracao(result, output_file))
        except Exception as exc:
            self.sinal_tarefa_falhou.emit(str(exc))

    def _encerrar_processamento(self):
        self.started = False
        self.start.setText(MODE_TEXTS[self.mode]['start'])
        self.atualizar_estado()

    def ao_concluir_tarefa(self, title, message):
        self._encerrar_processamento()
        QMessageBox.information(self, title, message)
        self._reiniciar_se_pendente()

    def ao_falhar_tarefa(self, message):
        self._encerrar_processamento()
        QMessageBox.critical(self, 'Não foi possível concluir', message)
        self._reiniciar_se_pendente()

    def closeEvent(self, event):
        if self.started:
            resposta = QMessageBox.question(
                self, 'Fechar',
                'Uma tarefa está em andamento. Fechar agora pode gerar um arquivo incompleto.\n\nFechar mesmo assim?',
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if resposta == QMessageBox.StandardButton.No:
                event.ignore()
                return
        event.accept()

    # ------------------------------------------------------------------
    # Atualização automática
    # ------------------------------------------------------------------

    def exibir_status_atualizacao(self, color, text):
        self.update_dot.setStyleSheet(f'color:{color}; background:transparent; font-size:14px;')
        self.update_text.setText(text)

    def verificar_atualizacoes(self):
        """Consulta a versão em segundo plano, para não atrasar a abertura da janela."""
        threading.Thread(target=self._verificar_atualizacoes, daemon=True).start()

    def _verificar_atualizacoes(self):
        if not auto_update.REPO_GITHUB:
            self.sinal_status_atualizacao.emit(UPDATE_UNKNOWN, f'v{__version__} · atualização não configurada')
            return
        try:
            release = auto_update.buscar_release(auto_update.REPO_GITHUB)
            if not auto_update.tem_versao_nova(release, __version__):
                self.sinal_status_atualizacao.emit(UPDATE_OK, f'v{__version__} · atualizado')
                return
            if not auto_update.pode_instalar():
                self.sinal_status_atualizacao.emit(UPDATE_BUSY, f'Nova versão disponível: {release["tag_name"]}')
                return
            self.sinal_download.emit(True)
            self.sinal_status_atualizacao.emit(UPDATE_BUSY, f'Baixando {release["tag_name"]}...')
            auto_update.instalar(release, auto_update.NOME_EXE)
        except Exception as exc:
            # Falha de rede ou de release não pode impedir a conferência nem parecer "atualizado".
            self.sinal_download.emit(False)
            self.sinal_status_atualizacao.emit(UPDATE_UNKNOWN, f'v{__version__} · {exc}')
            return
        self.sinal_status_atualizacao.emit(UPDATE_BUSY, 'Atualização pronta, reiniciando...')
        self.sinal_atualizacao_pronta.emit()

    def ao_mudar_download(self, downloading):
        self.downloading = downloading
        self.atualizar_estado()

    def ao_concluir_atualizacao(self):
        self.downloading = False
        self.restart_pending = True
        self.atualizar_estado()
        # Um processamento em andamento termina antes; a troca do EXE espera este processo sair.
        if not self.started:
            self._reiniciar_se_pendente()

    def _reiniciar_se_pendente(self):
        if self.restart_pending:
            QApplication.quit()


def abrir_janela() -> int:
    """Abre a janela principal e bloqueia até ela ser fechada."""
    app = QApplication(sys.argv)
    app.setStyle('Fusion')
    if not _garantir_instancia_unica():
        QMessageBox.information(None, 'Sistema de passagens', 'O programa já está aberto.')
        return 0
    icon = caminho_recurso(ICON_FILENAME)
    if icon.is_file():
        app.setWindowIcon(QIcon(str(icon)))
    window = App()
    window.show()
    window.verificar_atualizacoes()
    return app.exec()
