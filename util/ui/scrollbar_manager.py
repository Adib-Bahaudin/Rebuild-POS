"""Modul pengelola styling dan perilaku QScrollBar terpusat untuk aplikasi POS.

Modul ini menyediakan GlobalScrollBarManager yang mencegat instansiasi seluruh
QScrollBar di tingkat QApplication melalui event filter, memberikan tampilan modern
bergaya Catppuccin Mocha / Dark Minimalist dengan efek hover halus, sudut membulat,
serta konfigurasi interaksi scrolling yang responsif.
"""

from __future__ import annotations

from typing import Final

from PySide6.QtCore import QEvent, QObject
from PySide6.QtWidgets import QApplication, QScrollBar


class GlobalScrollBarManager(QObject):
    """Pengelola terpusat untuk mencegat, mendesain, dan mengatur perilaku QScrollBar.

    Menggunakan event filter pada QApplication untuk mendeteksi instansiasi
    atau event Polish dari setiap QScrollBar, kemudian menerapkan gaya QSS modern
    yang serasi dengan tema gelap aplikasi (Catppuccin Mocha) tanpa mengubah fungsionalitas.

    Attributes:
        SCROLLBAR_QSS: String QSS styling scrollbar vertikal dan horizontal.
    """

    SCROLLBAR_QSS: Final[str] = """
        QScrollBar:vertical {
            background-color: transparent;
            width: 8px;
            margin: 4px 2px 4px 2px;
            border: none;
            border-radius: 4px;
        }
        QScrollBar::handle:vertical {
            background-color: rgba(147, 154, 183, 0.32);
            min-height: 28px;
            border-radius: 4px;
            border: none;
        }
        QScrollBar::handle:vertical:hover {
            background-color: #89B4FA;
        }
        QScrollBar::handle:vertical:pressed {
            background-color: #74C7EC;
        }
        QScrollBar::sub-page:vertical, QScrollBar::add-page:vertical {
            background: transparent;
            border: none;
        }
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
            height: 0px;
            width: 0px;
            border: none;
            background: transparent;
        }

        QScrollBar:horizontal {
            background-color: transparent;
            height: 8px;
            margin: 2px 4px 2px 4px;
            border: none;
            border-radius: 4px;
        }
        QScrollBar::handle:horizontal {
            background-color: rgba(147, 154, 183, 0.32);
            min-width: 28px;
            border-radius: 4px;
            border: none;
        }
        QScrollBar::handle:horizontal:hover {
            background-color: #89B4FA;
        }
        QScrollBar::handle:horizontal:pressed {
            background-color: #74C7EC;
        }
        QScrollBar::sub-page:horizontal, QScrollBar::add-page:horizontal {
            background: transparent;
            border: none;
        }
        QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
            height: 0px;
            width: 0px;
            border: none;
            background: transparent;
        }

        QScrollBar::corner {
            background: transparent;
            border: none;
        }
    """

    def __init__(self, app: QApplication) -> None:
        """Menginisialisasi GlobalScrollBarManager dan memasang filter pada aplikasi.

        Args:
            app: Objek QApplication utama aplikasi.
        """
        super().__init__(app)
        self._app: QApplication = app
        self._app.installEventFilter(self)

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        """Menyaring event pada seluruh komponen untuk menangkap pembuatan QScrollBar.

        Args:
            watched: Objek Qt yang sedang diproses event-nya.
            event: Objek event Qt yang diterima.

        Returns:
            bool: Hasil delegasi event handling ke kelas induk.
        """
        if event.type() == QEvent.Type.Polish and isinstance(watched, QScrollBar):
            if not watched.property("_custom_styled"):
                self.configure_scrollbar(watched)
                watched.setProperty("_custom_styled", True)

        return super().eventFilter(watched, event)

    def configure_scrollbar(self, scrollbar: QScrollBar) -> None:
        """Mengatur styling visual dan sensitivitas step pada instance scrollbar.

        Args:
            scrollbar: Objek QScrollBar yang akan dikonfigurasi.
        """
        scrollbar.setStyleSheet(self.SCROLLBAR_QSS)
        scrollbar.setSingleStep(20)
