"""Titik masuk utama eksekusi aplikasi POS Barokah.

Modul ini mengorkestrasi siklus hidup aplikasi, inisialisasi konfigurasi terpusat,
penanganan eksepsi global, autentikasi pengguna, serta transisi tampilan antarmuka.
"""

from __future__ import annotations

import ctypes
import logging
import sys
import traceback
from types import TracebackType
from typing import Optional, Type

from PySide6.QtCore import (
    QCoreApplication,
    QEasingCurve,
    QParallelAnimationGroup,
    QPropertyAnimation,
)
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from config import (
    APP_NAME,
    DEFAULT_DB_PATH,
    IS_DEV,
    IS_PRODUCTION,
    ORGANIZATION_NAME,
    get_asset_path,
)
from core.logging_config import setup_logging
from core.login_auth import LoginAuthService
from ui.customwindowtitlebar import (
    FramelessMainWindow,
    TitleBarIconConfig,
    ICON_PATHS,
)
from ui.loginpage import LoginPage
from util.core.dashboard_transaksi_helper import create_connected_dashboard
from util.helper.initdatabase import InitDatabase
from util.ui.MainShell import MainShell, create_placeholder_page
from util.ui.scrollbar_manager import GlobalScrollBarManager

try:
    from pyqttoast import Toast, ToastPreset

    _HAS_TOAST = True
except ImportError:
    Toast = None
    ToastPreset = None
    _HAS_TOAST = False

logger = logging.getLogger(__name__)


def handle_unhandled_exception(
    exc_type: Type[BaseException],
    exc_value: BaseException,
    exc_traceback: Optional[TracebackType],
) -> None:
    """Menangani eksepsi yang tidak tertangkap secara global.

    Args:
        exc_type: Tipe eksepsi yang terjadi.
        exc_value: Nilai atau objek eksepsi.
        exc_traceback: Objek penelusuran balik (traceback).
    """
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return

    logger.critical(
        "Unhandled Exception terdeteksi:\n%s",
        "".join(traceback.format_exception(exc_type, exc_value, exc_traceback)),
    )


def main() -> int:
    """Titik masuk utama untuk menjalankan aplikasi POS.

    Returns:
        int: Kode status keluar aplikasi kepada sistem operasi.
    """
    try:
        app_user_model_id = f"{ORGANIZATION_NAME.lower()}.{APP_NAME.lower()}.v2"
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(app_user_model_id)
    except (AttributeError, OSError):
        pass

    setup_logging()

    if IS_PRODUCTION:
        sys.excepthook = handle_unhandled_exception

    logger.info(
        "Aplikasi POS dimulai [Mode: %s]",
        "Production" if IS_PRODUCTION else "Development",
    )

    QCoreApplication.setOrganizationName(ORGANIZATION_NAME)
    QCoreApplication.setApplicationName(APP_NAME)

    app = QApplication(sys.argv)

    icon_path = get_asset_path("icons/B_Logo.svg")
    app_icon = QIcon(str(icon_path))
    app.setWindowIcon(app_icon)

    GlobalScrollBarManager(app)

    db_init = InitDatabase(DEFAULT_DB_PATH)
    db_init.run()

    title_bar_config = TitleBarIconConfig.from_dict(ICON_PATHS)

    window = FramelessMainWindow(
        icon_config=title_bar_config,
        page_title="Aktivasi Lisensi",
    )
    window.setWindowIcon(app_icon)

    login_page = LoginPage()
    dashboard_window: Optional[MainShell] = None

    def on_login_attempt(key: str) -> None:
        """Menerima dan memproses sinyal login dari UI.

        Args:
            key: Kunci akses yang dimasukkan oleh pengguna.
        """
        nonlocal dashboard_window
        auth_service = LoginAuthService(DEFAULT_DB_PATH)
        result = auth_service.authenticate(key)

        if result.is_success and result.user_data is not None:
            logger.info(
                "Login berhasil untuk user: %s", result.user_data["name"]
            )

            dashboard_window = MainShell(
                icon_config=title_bar_config,
                page_title="Dashboard Penjualan",
            )
            dashboard_window.setWindowIcon(app_icon)
            setattr(app, "active_dashboard_window", dashboard_window)

            user_name = result.user_data["name"]
            user_role = result.user_data["role"]

            dashboard_window.register_page(
                "dashboard",
                lambda: create_connected_dashboard(
                    user_name=user_name,
                    user_role=user_role,
                    db_path=DEFAULT_DB_PATH,
                ),
                title="Dashboard Penjualan",
            )
            dashboard_window.register_page(
                "history",
                lambda: create_placeholder_page("Riwayat Transaksi"),
                title="Riwayat Transaksi",
            )
            dashboard_window.register_page(
                "product",
                lambda: create_placeholder_page("Manajemen Produk"),
                title="Manajemen Produk",
            )
            dashboard_window.register_page(
                "report",
                lambda: create_placeholder_page("Laporan Penjualan"),
                title="Laporan Penjualan",
            )
            dashboard_window.register_page(
                "people",
                lambda: create_placeholder_page("Manajemen Pelanggan"),
                title="Manajemen Pelanggan",
            )
            dashboard_window.register_page(
                "settings",
                lambda: create_placeholder_page("Pengaturan Sistem"),
                title="Pengaturan Sistem",
            )

            dashboard_window.navigate_to("dashboard")

            dashboard_window.setWindowOpacity(0.0)
            dashboard_window.show()

            fade_in = QPropertyAnimation(
                dashboard_window, b"windowOpacity", dashboard_window
            )
            fade_in.setDuration(250)
            fade_in.setStartValue(0.0)
            fade_in.setEndValue(1.0)
            fade_in.setEasingCurve(QEasingCurve.Type.OutCubic)

            fade_out = QPropertyAnimation(
                window, b"windowOpacity", dashboard_window
            )
            fade_out.setDuration(200)
            fade_out.setStartValue(1.0)
            fade_out.setEndValue(0.0)
            fade_out.setEasingCurve(QEasingCurve.Type.InCubic)

            anim_group = QParallelAnimationGroup(dashboard_window)
            anim_group.addAnimation(fade_in)
            anim_group.addAnimation(fade_out)
            anim_group.finished.connect(window.close)

            dashboard_window._transition_anim = anim_group
            anim_group.start()
        else:
            logger.warning("Login gagal: %s", result.message)

            if _HAS_TOAST and Toast is not None and ToastPreset is not None:
                toast = Toast(window)
                toast.setDuration(4000)
                toast.setBorderRadius(5)
                toast.setTitle("Login Gagal")
                toast.setText(result.message)
                toast.applyPreset(ToastPreset.ERROR)
                toast.show()

    def on_create_key_attempt() -> None:
        """Menerima sinyal permintaan pembuatan key baru dari UI."""
        logger.info("Permintaan pembuatan Access Key baru diterima dari UI")

    login_page.login_requested.connect(on_login_attempt)
    login_page.create_key_requested.connect(on_create_key_attempt)

    window.set_content_widget(login_page)
    window.show()

    logger.info("Jendela utama ditampilkan, event loop dimulai")
    exit_code = app.exec()
    logger.info("Aplikasi POS dihentikan dengan kode: %d", exit_code)

    return exit_code


if __name__ == "__main__":
    sys.exit(main())
