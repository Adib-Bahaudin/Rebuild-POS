from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QLabel,
    QVBoxLayout,
    QWidget,
)


def build_demo_content() -> QWidget:
    """Membangun widget konten contoh untuk pengujian integrasi jendela utama.

    Returns:
        Objek QWidget yang berisi informasi status aplikasi.
    """
    container = QWidget()
    layout = QVBoxLayout(container)
    layout.setContentsMargins(32, 32, 32, 32)

    info_label = QLabel(
        "Custom Title Bar Aktif\n\n"
        "• Geser jendela dengan menahan area kosong pada title bar.\n"
        "• Klik ganda pada title bar untuk Maximize / Restore.\n"
        "• Arahkan kursor ke tombol kontrol untuk melihat transisi ikon hover.\n"
        "• Arahkan kursor ke tepi jendela untuk mengubah ukuran (resize)."
    )
    info_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
    info_label.setStyleSheet(
        """
        QLabel {
            color: #BAC2DE;
            font-size: 14px;
            line-height: 1.6;
            background-color: #1E1E2E;
            border: 1px solid #313244;
            border-radius: 8px;
            padding: 24px;
        }
        """
    )
    layout.addWidget(info_label)
    return container
