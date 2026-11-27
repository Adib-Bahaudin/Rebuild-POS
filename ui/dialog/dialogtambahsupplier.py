"""Dialog cepat penambahan supplier baru dari halaman Tambah Stok."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ui.dialog._tambahstok_dialog_style import DIALOG_STYLESHEET


class QuickSupplierDialog(QDialog):
    """Dialog cepat untuk menambahkan supplier baru langsung dari halaman kulakan."""

    def __init__(self, parent: QWidget | None = None) -> None:
        """Menginisialisasi QuickSupplierDialog.

        Args:
            parent: Widget induk opsional.
        """
        super().__init__(parent)
        self.setWindowTitle("Tambah Supplier Baru")
        self.setMinimumWidth(400)
        self.setStyleSheet(DIALOG_STYLESHEET)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        title = QLabel("Tambah Supplier Baru", self)
        title.setObjectName("dialogTitle")
        subtitle = QLabel(
            "Supplier baru langsung tersedia dan dipilih pada nota aktif.", self
        )
        subtitle.setObjectName("dialogSubtitle")
        layout.addWidget(title)
        layout.addWidget(subtitle)

        card = QFrame(self)
        card.setObjectName("dialogCard")
        form = QFormLayout(card)
        form.setContentsMargins(12, 12, 12, 12)
        form.setSpacing(10)

        self.name_input = QLineEdit(card)
        self.name_input.setPlaceholderText("Contoh: CV Kertas Nusantara")
        self.phone_input = QLineEdit(card)
        self.phone_input.setPlaceholderText("Contoh: 0812-3456-7890 (opsional)")
        self.address_input = QLineEdit(card)
        self.address_input.setPlaceholderText("Alamat toko / distributor (opsional)")

        form.addRow("Nama Supplier *", self.name_input)
        form.addRow("No. Telepon", self.phone_input)
        form.addRow("Alamat", self.address_input)
        layout.addWidget(card)

        self.error_label = QLabel("", self)
        self.error_label.setObjectName("errorLabel")
        self.error_label.setVisible(False)
        layout.addWidget(self.error_label)

        btn_row = QHBoxLayout()
        btn_row.addStretch(1)
        cancel_btn = QPushButton("Batal", self)
        cancel_btn.setObjectName("secondaryBtn")
        cancel_btn.clicked.connect(self.reject)

        save_btn = QPushButton("Simpan Supplier", self)
        save_btn.setObjectName("primaryBtn")
        save_btn.clicked.connect(self._validate_and_accept)

        btn_row.addWidget(cancel_btn)
        btn_row.addWidget(save_btn)
        layout.addLayout(btn_row)

    def _validate_and_accept(self) -> None:
        """Memvalidasi nama supplier wajib diisi sebelum menutup dialog."""
        if not self.name_input.text().strip():
            self.error_label.setText("Nama supplier wajib diisi.")
            self.error_label.setVisible(True)
            self.name_input.setFocus()
            return
        self.accept()

    def get_values(self) -> tuple[str, str, str]:
        """Mengambil nilai input nama, telepon, dan alamat supplier.

        Returns:
            Tuple (name, phone, address).
        """
        return (
            self.name_input.text().strip(),
            self.phone_input.text().strip(),
            self.address_input.text().strip(),
        )
