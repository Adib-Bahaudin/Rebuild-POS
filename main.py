import sys
import logging

from PySide6.QtWidgets import QApplication
from pyqttoast import Toast, ToastPreset

from core.logging_config import setup_logging
from ui.customwindowtitlebar import (
    FramelessMainWindow,
    TitleBarIconConfig,
    ICON_PATHS,
)
from ui.loginpage import LoginPage
from core.login_auth import LoginAuthService
from util.helper.initdatabase import InitDatabase

logger = logging.getLogger(__name__)


def main() -> int:
    """Titik masuk utama untuk menjalankan aplikasi POS.

    Returns:
        Kode status keluar aplikasi kepada sistem operasi.
    """
    setup_logging()
    logger.info("Aplikasi POS dimulai")

    app = QApplication(sys.argv)

    title_bar_config = TitleBarIconConfig.from_dict(ICON_PATHS)

    window = FramelessMainWindow(
        icon_config=title_bar_config,
        page_title="Aktivasi Lisensi"
    )

    db_init = InitDatabase("barokah_database.db")
    db_init.run()

    login_page = LoginPage()

    def on_login_attempt(key: str) -> None:
        """Menerima dan memproses sinyal login dari UI (Placeholder)."""
        auth_service = LoginAuthService("barokah_database.db")
        result = auth_service.authenticate(key)

        if result.is_success and result.user_data is not None:
            logger.info("Login berhasil untuk user: %s", result.user_data['name'])
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
