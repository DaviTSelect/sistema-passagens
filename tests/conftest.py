"""Configuração do pytest para PySide6.

Instala um hook de finalização que processa eventos Qt pendentes antes do
processo sair, evitando o crash 0xC0000005 que ocorre no cleanup do PySide6.
"""
from __future__ import annotations

import os
import sys


def pytest_configure(config):
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def pytest_sessionfinish(session, exitstatus):
    try:
        from PySide6.QtWidgets import QApplication
        app = QApplication.instance()
        if app is not None:
            app.processEvents()
    except Exception:
        pass
