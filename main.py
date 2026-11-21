from typing import Optional
import sys
import logging
import ctypes
from pathlib import Path

from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QIcon
from pyqttoast import Toast, ToastPreset

from core.logging_config import setup_logging
from ui.customwindowtitlebar import (
    FramelessMainWindow,
    TitleBarIconConfig,
    ICON_PATHS,
)
from PySide6.QtCore import (
    QEasingCurve,
    QParallelAnimationGroup,
    QPropertyAnimation,
)
from ui.loginpage import LoginPage
from core.login_auth import LoginAuthService
from util.helper.initdatabase import InitDatabase
from util.core.dashboard_transaksi_helper import create_connected_dashboard
from util.ui.MainShell import MainShell, create_placeholder_page

logger = logging.getLogger(__name__)


def main() -> int:
    """Titik masuk utama untuk menjalankan aplikasi POS.

    Returns:
        Kode status keluar aplikasi kepada sistem operasi.
    """
    try:
        myappid = "barokahpos.posapp.rebuild.version.1.0"
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
    except Exception:
        pass

    setup_logging()
    logger.info("Aplikasi POS dimulai")

    app = QApplication(sys.argv)
    
    base_dir = Path(__file__).resolve().parent
    icon_path = str(base_dir / "assets" / "icons" / "B_Logo.svg")
    app_icon = QIcon(icon_path)
    app.setWindowIcon(app_icon)

    db_init = InitDatabase("barokah_database.db")
    db_init.run()

    title_bar_config = TitleBarIconConfig.from_dict(ICON_PATHS)

    window = FramelessMainWindow(
        icon_config=title_bar_config,
        page_title="Aktivasi Lisensi"
    )
    window.setWindowIcon(app_icon)

    login_page = LoginPage()
    dashboard_window: Optional[MainShell] = None

    def on_login_attempt(key: str) -> None:
        """Menerima dan memproses sinyal login dari UI (Placeholder)."""
        nonlocal dashboard_window
        auth_service = LoginAuthService("barokah_database.db")
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
                    db_path="barokah_database.db",
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

            toast = Toast(window)
            toast.setDuration(4000)
            toast.setBorderRadius(5)
            toast.setTitle("Login Gagal")
            toast.setText(result.message)
            toast.applyPreset(ToastPreset.ERROR)
            toast.show()

    def on_create_key_attempt() -> None:
        """Menerima sinyal permintaan pembuatan key baru dari UI (Placeholder)."""
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
