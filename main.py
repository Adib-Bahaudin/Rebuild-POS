import sys

from PySide6.QtWidgets import QApplication

from customwindowtitlebar import (
    FramelessMainWindow,
    TitleBarIconConfig,
    ICON_PATHS,
)
from loginpage import LoginPage


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

    login_page = LoginPage()

    def on_login_attempt(key: str) -> None:
        """Menerima dan memproses sinyal login dari UI (Placeholder)."""
        print(f"[UI SIGNAL] Permintaan login menggunakan key: {key}")

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
