"""Utilitas tampilan notifikasi Toast mengambang untuk antarmuka PySide6.

Modul ini membungkus pemanggilan library pyqttoast secara aman agar komponen
UI maupun bridge/helper dapat menampilkan notifikasi sukses atau kesalahan
secara konsisten tanpa duplikasi logika.
"""

from __future__ import annotations

import logging

from PySide6.QtWidgets import QWidget

try:
    from pyqttoast import Toast, ToastPreset

    _HAS_TOAST = True
except ImportError:
    Toast = None
    ToastPreset = None
    _HAS_TOAST = False

logger = logging.getLogger(__name__)


def show_toast(
    parent: QWidget,
    title: str,
    message: str,
    is_success: bool = True,
    duration_ms: int = 4000,
    border_radius: int = 6,
) -> None:
    """Menampilkan notifikasi popup Toast pada widget induk yang diberikan.

    Args:
        parent: Widget induk tempat notifikasi Toast akan ditampilkan.
        title: Judul singkat notifikasi.
        message: Isi pesan ringkas notifikasi.
        is_success: True untuk preset sukses, False untuk preset kesalahan.
        duration_ms: Durasi tampilan Toast dalam milidetik.
        border_radius: Radius sudut kotak notifikasi dalam piksel.
    """
    if not _HAS_TOAST or Toast is None or ToastPreset is None:
        return

    try:
        toast = Toast(parent)
        toast.setDuration(duration_ms)
        toast.setBorderRadius(border_radius)
        toast.setTitle(title)
        toast.setText(message)
        preset = ToastPreset.SUCCESS if is_success else ToastPreset.ERROR
        toast.applyPreset(preset)
        toast.show()
    except Exception:
        logger.debug("Gagal menampilkan widget Toast pada %s", type(parent).__name__)
