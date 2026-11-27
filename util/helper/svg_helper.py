"""Utilitas rendering ikon SVG inline menjadi QIcon atau QPixmap."""

from __future__ import annotations

from PySide6.QtCore import QByteArray, QSize, Qt
from PySide6.QtGui import QIcon, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer


def build_svg_icon(svg_markup: str, color: str, size: int = 16) -> QIcon:
    """Merender markup SVG inline menjadi objek QIcon tajam berkualitas vektor.

    Args:
        svg_markup: Template string SVG yang mengandung placeholder '{color}'.
        color: Kode warna heksadesimal untuk stroke atau fill ikon.
        size: Dimensi persegi piksel untuk rendering ikon.

    Returns:
        Objek QIcon siap digunakan pada tombol, tab, atau elemen antarmuka.
    """
    rendered_svg = svg_markup.replace("{color}", color).encode("utf-8")
    renderer = QSvgRenderer(QByteArray(rendered_svg))
    pixmap = QPixmap(QSize(size * 2, size * 2))
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    renderer.render(painter)
    painter.end()
    pixmap.setDevicePixelRatio(2.0)
    return QIcon(pixmap)
