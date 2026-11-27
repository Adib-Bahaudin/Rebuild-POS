"""Bridge penghubung halaman UI Tambah Stok dengan backend SQLite FIFO.

Modul ini menyediakan fungsi binder serta factory untuk membuat halaman maupun
jendela TambahStok yang langsung terhubung ke TambahStokService dan
TambahStokController tanpa menggabungkan logika database ke dalam lapisan UI.
"""

from __future__ import annotations

import logging
from pathlib import Path

from PySide6.QtWidgets import QWidget

from config import DEFAULT_DB_PATH
from core.tambah_stok_backend import TambahStokController, TambahStokService
from ui.customwindowtitlebar import ICON_PATHS, TitleBarIconConfig
from ui.tambahstok import TambahStokPage, TambahStokWindow

logger = logging.getLogger(__name__)


def bind_tambah_stok_backend(
    page: TambahStokPage,
    db_path: str | Path | None = None,
) -> TambahStokController:
    """Menghubungkan instance TambahStokPage dengan layanan backend SQLite siap pakai.

    Args:
        page: Widget TambahStokPage yang akan dihubungkan ke basis data.
        db_path: Path file database SQLite opsional; default memakai DEFAULT_DB_PATH.

    Returns:
        Instance TambahStokController yang sudah terikat pada seluruh sinyal UI.
    """
    resolved_db = Path(db_path) if db_path is not None else DEFAULT_DB_PATH
    service = TambahStokService(db_path=resolved_db)
    controller = TambahStokController(page=page, service=service, parent=page)
    setattr(page, "_tambah_stok_controller", controller)
    setattr(page, "_tambah_stok_service", service)
    logger.info("TambahStokController terhubung ke database: %s", resolved_db)
    return controller


def create_connected_tambah_stok_page(
    db_path: str | Path | None = None,
    parent: QWidget | None = None,
) -> TambahStokPage:
    """Membuat TambahStokPage baru sekaligus mengikatnya dengan backend SQLite.

    Args:
        db_path: Lokasi file database SQLite. Default memakai DEFAULT_DB_PATH.
        parent: Widget induk opsional.

    Returns:
        Instance TambahStokPage yang siap didaftarkan ke MainShell.
    """
    page = TambahStokPage(parent=parent)
    bind_tambah_stok_backend(page=page, db_path=db_path)
    return page


def create_connected_tambah_stok_window(
    db_path: str | Path | None = None,
    icon_config: TitleBarIconConfig | None = None,
    parent: QWidget | None = None,
) -> TambahStokWindow:
    """Membuat jendela mandiri TambahStokWindow yang terhubung ke backend SQLite.

    Args:
        db_path: Lokasi file database SQLite. Default memakai DEFAULT_DB_PATH.
        icon_config: Konfigurasi ikon custom title bar. Jika None, memakai ICON_PATHS.
        parent: Widget induk opsional.

    Returns:
        Instance TambahStokWindow siap ditampilkan dengan data database asli.
    """
    resolved_icons = (
        icon_config
        if icon_config is not None
        else TitleBarIconConfig.from_dict(ICON_PATHS)
    )
    window = TambahStokWindow(icon_config=resolved_icons, parent=parent)
    bind_tambah_stok_backend(page=window.page, db_path=db_path)
    return window
