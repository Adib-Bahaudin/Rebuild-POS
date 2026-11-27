"""Utilitas pembantu komponen antarmuka formulir dialog PySide6.

Modul ini menyediakan fungsi pembangun elemen UI formulir dialog yang dipakai
berulang di berbagai dialog input/edit seperti label kolom, baris tombol footer,
dan tampilan pesan kesalahan validasi inline.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QWidget


def make_field_label(parent: QWidget, text: str) -> QLabel:
    """Membuat widget QLabel dengan objectName seragam untuk judul kolom formulir.

    Args:
        parent: Widget induk pemilik label.
        text: Teks judul kolom masukan.

    Returns:
        Objek QLabel dengan objectName 'FieldLabel'.
    """
    label = QLabel(text, parent)
    label.setObjectName("FieldLabel")
    return label


def build_footer_actions(
    cancel_btn: QPushButton,
    save_btn: QPushButton,
) -> QHBoxLayout:
    """Membangun layout baris tombol aksi Batal dan Simpan di bagian bawah dialog.

    Args:
        cancel_btn: Tombol batal dialog.
        save_btn: Tombol simpan/konfirmasi dialog.

    Returns:
        Objek QHBoxLayout berisi tombol aksi sejajar kanan.
    """
    footer = QHBoxLayout()
    footer.setContentsMargins(0, 2, 0, 0)
    footer.setSpacing(8)

    cancel_btn.setObjectName("CancelBtn")
    cancel_btn.setCursor(Qt.CursorShape.PointingHandCursor)

    save_btn.setObjectName("SaveBtn")
    save_btn.setCursor(Qt.CursorShape.PointingHandCursor)

    footer.addStretch(1)
    footer.addWidget(cancel_btn)
    footer.addWidget(save_btn)
    return footer


def show_inline_error(error_label: QLabel, message: str) -> None:
    """Menampilkan pesan kesalahan validasi secara inline pada label dialog.

    Args:
        error_label: Widget QLabel penampung teks kesalahan.
        message: Pesan kesalahan validasi yang akan ditampilkan.
    """
    error_label.setText(message)
    error_label.show()
