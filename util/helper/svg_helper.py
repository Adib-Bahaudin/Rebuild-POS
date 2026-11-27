"""Utilitas rendering ikon SVG inline menjadi QIcon, QPixmap, atau gambar QPainter."""

from __future__ import annotations

from PySide6.QtCore import QByteArray, QRectF, Qt
from PySide6.QtGui import QIcon, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer


def render_svg_pixmap(
    svg_markup: str,
    size: int = 16,
    dpr: float = 2.0,
) -> QPixmap:
    """Merender markup SVG inline menjadi QPixmap transparan tajam (HiDPI-ready).

    Args:
        svg_markup: String XML SVG lengkap yang siap dirender.
        size: Dimensi sisi persegi dalam piksel logis.
        dpr: Faktor skala device-pixel-ratio untuk ketajaman layar HiDPI.

    Returns:
        Objek QPixmap transparan hasil rendering SVG.
    """
    renderer = QSvgRenderer(QByteArray(svg_markup.encode("utf-8")))
    pixel_size = max(1, int(size * dpr))
    pixmap = QPixmap(pixel_size, pixel_size)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    renderer.render(painter, QRectF(0, 0, pixel_size, pixel_size))
    painter.end()
    pixmap.setDevicePixelRatio(dpr)
    return pixmap


def build_svg_icon(
    svg_markup: str,
    color: str = "",
    size: int = 16,
    *,
    disabled_markup: str | None = None,
    dpr: float = 2.0,
) -> QIcon:
    """Merender markup SVG inline menjadi objek QIcon tajam berkualitas vektor.

    Args:
        svg_markup: String XML SVG lengkap atau template dengan placeholder '{color}'.
        color: Kode warna heksadesimal untuk mengganti '{color}' bila ada.
        size: Dimensi persegi piksel logis untuk rendering ikon.
        disabled_markup: Markup SVG opsional untuk status QIcon.Mode.Disabled.
        dpr: Faktor skala device-pixel-ratio.

    Returns:
        Objek QIcon siap digunakan pada tombol, tab, atau elemen antarmuka.
    """
    resolved = svg_markup.replace("{color}", color) if color else svg_markup
    icon = QIcon()
    icon.addPixmap(render_svg_pixmap(resolved, size=size, dpr=dpr), QIcon.Mode.Normal)
    if disabled_markup is not None:
        resolved_disabled = (
            disabled_markup.replace("{color}", color) if color else disabled_markup
        )
        icon.addPixmap(
            render_svg_pixmap(resolved_disabled, size=size, dpr=dpr),
            QIcon.Mode.Disabled,
        )
    return icon


def paint_centered_svg(
    painter: QPainter,
    rect: QRectF,
    svg_markup: str,
    icon_size: float,
) -> None:
    """Menggambar ikon SVG tepat di tengah area persegi panjang yang ditentukan.

    Args:
        painter: Instance QPainter aktif.
        rect: Area target tempat ikon dipusatkan.
        svg_markup: String XML SVG lengkap yang siap dirender.
        icon_size: Lebar dan tinggi ikon dalam piksel.
    """
    renderer = QSvgRenderer(QByteArray(svg_markup.encode("utf-8")))
    x_pos = rect.x() + (rect.width() - icon_size) / 2.0
    y_pos = rect.y() + (rect.height() - icon_size) / 2.0
    renderer.render(painter, QRectF(x_pos, y_pos, icon_size, icon_size))
