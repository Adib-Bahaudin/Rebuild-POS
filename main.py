import sys

from PySide6.QtWidgets import QApplication

from ui.customwindowtitlebar import (
    FramelessMainWindow,
    TitleBarIconConfig,
    ICON_PATHS,
)
from ui.loginpage import LoginPage
from core.login_auth import LoginAuthService
from util.helper.initdatabase import InitDatabase


def main() -> int:
    """Titik masuk utama untuk menjalankan aplikasi POS.

    Returns:
        Kode status keluar aplikasi kepada sistem operasi.
    """
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
            print(f"Login Sukses! Selamat datang {result.user_data['name']}")
        else:
            print(f"Login Gagal: {result.message}")

    def on_create_key_attempt() -> None:
        """Menerima sinyal permintaan pembuatan key baru dari UI (Placeholder)."""
        print("[UI SIGNAL] Permintaan pembuatan Access Key baru")

    login_page.login_requested.connect(on_login_attempt)
    login_page.create_key_requested.connect(on_create_key_attempt)

    window.set_content_widget(login_page)
    window.show()

    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
