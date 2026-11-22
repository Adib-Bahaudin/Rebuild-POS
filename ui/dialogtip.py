"""Modul dialog input tip kasir kustom berbasis CustomDialog."""

from PySide6.QtCore import Qt
from PySide6.QtGui import QIntValidator
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from util.customdialog import CustomDialog


class DialogTip(CustomDialog):
    """Dialog modal untuk menentukan nominal tip atau bonus kasir pada transaksi."""

    def __init__(
        self,
        parent: QWidget | None = None,
        initial_tip: int = 0,
        change_amount: int = 0,
    ) -> None:
        """Menginisialisasi dialog tip kasir dengan opsi nilai cepat dan kembalian.

        Args:
            parent: Widget induk pemilik jendela dialog.
            initial_tip: Nominal tip transaksi yang saat ini sedang aktif.
            change_amount: Nominal kembalian transaksi yang dapat dialihkan menjadi tip.
        """
        super().__init__(parent)
        self._initial_tip: int = max(0, initial_tip)
        self._change_amount: int = max(0, change_amount)
        self._result_value: int = self._initial_tip

        self.setWindowTitle("Input Tip / Bonus")
        self.setFixedWidth(360)

        self._init_ui()

    def _init_ui(self) -> None:
        """Menyusun seluruh komponen antarmuka pengguna pada area konten dialog."""
        content_layout = QVBoxLayout()
        content_layout.setContentsMargins(18, 16, 18, 16)
        content_layout.setSpacing(10)

        self._label_nominal = QLabel("Nominal Tip (Rp)", self)
        self._label_nominal.setStyleSheet(
            """
            QLabel {
                color: #CDD6F4;
                font-size: 13px;
                font-weight: 600;
                background-color: transparent;
            }
            """
        )
        content_layout.addWidget(self._label_nominal)

        self._input_nominal = QLineEdit(self)
        self._input_nominal.setValidator(QIntValidator(0, 100_000_000, self))
        self._input_nominal.setPlaceholderText("0")
        if self._initial_tip > 0:
            self._input_nominal.setText(str(self._initial_tip))
            self._input_nominal.selectAll()

        self._input_nominal.setStyleSheet(
            """
            QLineEdit {
                background-color: #11111B;
                border: 1px solid #313244;
                border-radius: 6px;
                padding: 8px 12px;
                color: #CDD6F4;
                font-size: 14px;
                font-weight: bold;
                selection-background-color: #89B4FA;
                selection-color: #11111B;
            }
            QLineEdit:focus {
                border: 1px solid #2ECC71;
                background-color: #11111B;
            }
            """
        )
        self._input_nominal.returnPressed.connect(self._handle_apply_clicked)
        content_layout.addWidget(self._input_nominal)

        quick_buttons_layout = QHBoxLayout()
        quick_buttons_layout.setSpacing(8)

        quick_button_style = """
            QPushButton {
                background-color: #1E1E2E;
                color: #CDD6F4;
                border: 1px solid #313244;
                border-radius: 6px;
                padding: 7px 10px;
                font-size: 12px;
                font-weight: 600;
            }
            QPushButton:hover {
                background-color: #313244;
                border-color: #89B4FA;
                color: #FFFFFF;
            }
            QPushButton:pressed {
                background-color: #181825;
            }
            QPushButton:disabled {
                background-color: #181825;
                color: #585B70;
                border: 1px solid #28293D;
            }
        """

        self._btn_5000 = QPushButton("5000", self)
        self._btn_5000.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_5000.setStyleSheet(quick_button_style)
        self._btn_5000.clicked.connect(lambda: self._select_quick_amount(5000))
        quick_buttons_layout.addWidget(self._btn_5000)

        self._btn_10000 = QPushButton("10000", self)
        self._btn_10000.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_10000.setStyleSheet(quick_button_style)
        self._btn_10000.clicked.connect(lambda: self._select_quick_amount(10000))
        quick_buttons_layout.addWidget(self._btn_10000)

        self._btn_ambil_kembalian = QPushButton("ambil kembalian", self)
        self._btn_ambil_kembalian.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_ambil_kembalian.setStyleSheet(quick_button_style)
        self._btn_ambil_kembalian.setEnabled(self._change_amount > 0)
        self._btn_ambil_kembalian.clicked.connect(
            lambda: self._select_quick_amount(self._change_amount)
        )
        quick_buttons_layout.addWidget(self._btn_ambil_kembalian)

        content_layout.addLayout(quick_buttons_layout)

        content_layout.addSpacing(16)

        bottom_layout = QHBoxLayout()
        bottom_layout.setContentsMargins(0, 0, 0, 0)
        bottom_layout.setSpacing(8)

        self._btn_reset = QPushButton("Reset", self)
        self._btn_reset.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_reset.setStyleSheet(
            """
            QPushButton {
                background-color: transparent;
                color: #BAC2DE;
                border: 1px solid #45475A;
                border-radius: 4px;
                padding: 5px 12px;
                font-size: 11px;
                font-weight: 500;
            }
            QPushButton:hover {
                background-color: #313244;
                color: #F38BA8;
                border-color: #F38BA8;
            }
            QPushButton:pressed {
                background-color: #181825;
            }
            """
        )
        self._btn_reset.clicked.connect(self._handle_reset_clicked)
        bottom_layout.addWidget(self._btn_reset)

        bottom_layout.addStretch(1)

        self._btn_batal = QPushButton("Batal", self)
        self._btn_batal.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_batal.setStyleSheet(
            """
            QPushButton {
                background-color: #313244;
                color: #CDD6F4;
                border: 1px solid transparent;
                border-radius: 4px;
                padding: 5px 14px;
                font-size: 11px;
                font-weight: 500;
            }
            QPushButton:hover {
                background-color: #45475A;
                color: #FFFFFF;
            }
            QPushButton:pressed {
                background-color: #181825;
            }
            """
        )
        self._btn_batal.clicked.connect(self.reject)
        bottom_layout.addWidget(self._btn_batal)

        self._btn_terapkan = QPushButton("Terapkan", self)
        self._btn_terapkan.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_terapkan.setStyleSheet(
            """
            QPushButton {
                background-color: #2ECC71;
                color: #11111B;
                border: none;
                border-radius: 4px;
                padding: 5px 16px;
                font-size: 11px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #27AE60;
            }
            QPushButton:pressed {
                background-color: #1E8449;
            }
            """
        )
        self._btn_terapkan.clicked.connect(self._handle_apply_clicked)
        bottom_layout.addWidget(self._btn_terapkan)

        content_layout.addLayout(bottom_layout)

        self.setLayout(content_layout)

    def _select_quick_amount(self, amount: int) -> None:
        """Menetapkan nominal tip dari tombol opsi cepat dan langsung menyetujui dialog.

        Args:
            amount: Nilai tip nominal dari tombol cepat yang ditekan.
        """
        self._result_value = max(0, amount)
        self.accept()

    def _handle_reset_clicked(self) -> None:
        """Mengosongkan input nominal tip dan mengembalikan fokus kursor ke kolom teks."""
        self._input_nominal.clear()
        self._input_nominal.setFocus()

    def _handle_apply_clicked(self) -> None:
        """Membaca teks nominal input, menyimpannya ke hasil akhir, lalu menyetujui dialog."""
        raw_text = self._input_nominal.text().strip()
        parsed_val = int(raw_text) if raw_text else 0
        self._result_value = max(0, parsed_val)
        self.accept()

    def get_value(self) -> int:
        """Mengembalikan nilai nominal tip yang disepakati pengguna.

        Returns:
            Besaran nilai nominal tip dalam rupiah.
        """
        return self._result_value

    @classmethod
    def get_tip(
        cls,
        parent: QWidget | None = None,
        initial_tip: int = 0,
        change_amount: int = 0,
        title: str = "Input Tip / Bonus",
    ) -> tuple[int, bool]:
        """Membuka dialog tip secara modal dan mengembalikan nilai nominal beserta status dialog.

        Args:
            parent: Widget induk pemilik dialog.
            initial_tip: Nominal tip awal yang ada pada transaksi saat ini.
            change_amount: Nilai kembalian aktif saat ini dari input pembayaran.
            title: Teks judul jendela dialog kustom.

        Returns:
            Tuple yang memuat nominal tip terpilih dan boolean True jika disetujui, False jika dibatalkan.
        """
        dialog = cls(parent=parent, initial_tip=initial_tip, change_amount=change_amount)
        if title:
            dialog.setWindowTitle(title)
        accepted = dialog.exec() == QDialog.DialogCode.Accepted
        if accepted:
            return dialog.get_value(), True
        return initial_tip, False
