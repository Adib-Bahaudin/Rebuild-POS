import sys

from PySide6.QtWidgets import QApplication

from content import build_demo_content
from customwindowtitlebar import (
    FramelessMainWindow,
    IconLoadError,
    TitleBarIconConfig,
    ICON_PATHS,
)


def main() -> int:
    """Titik masuk utama untuk menjalankan contoh integrasi FramelessMainWindow.

    Returns:
        Kode status keluar aplikasi kepada sistem operasi.
    """
    app = QApplication(sys.argv)

    try:
        icon_config = TitleBarIconConfig.from_dict(ICON_PATHS)
        window = FramelessMainWindow(
            icon_config=icon_config,
        )
    except (FileNotFoundError, IconLoadError, KeyError) as error:
        sys.stderr.write(f"[Kesalahan Konfigurasi Ikon]: {error}\n")
        return 1

    window.set_content_widget(build_demo_content())
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
