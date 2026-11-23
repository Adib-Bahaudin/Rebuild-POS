"""Modul dialog input diskon atau bonus kasir kustom berbasis CustomDialog."""

from PySide6.QtCore import QRegularExpression, Qt
from PySide6.QtGui import QIntValidator, QRegularExpressionValidator
from PySide6.QtWidgets import (
    QDialog,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from util.customdialog import CustomDialog


class DialogBonus(CustomDialog):
    """Dialog modal untuk menentukan diskon transaksi berbasis nominal atau persentase."""

    def __init__(
        self,
        parent: QWidget | None = None,
        initial_nominal: int = 0,
        initial_percent: float = 0.0,
    ) -> None:
        """Menginisialisasi dialog bonus dengan opsi diskon nominal atau persentase.

        Args:
            parent: Widget induk pemilik jendela dialog.
            initial_nominal: Nilai nominal diskon awal dalam rupiah.
            initial_percent: Nilai persentase diskon awal antara 0 hingga 100.
        """
        super().__init__(parent)
        self._initial_nominal: int = max(0, initial_nominal)
        self._initial_percent: float = max(0.0, min(100.0, initial_percent))

        self._discount_type: str = "none"
        self._result_value: float = 0.0

        if self._initial_nominal > 0:
            self._discount_type = "nominal"
            self._result_value = float(self._initial_nominal)
        elif self._initial_percent > 0.0:
            self._discount_type = "percent"
            self._result_value = self._initial_percent

        self.setWindowTitle("Input Diskon / Bonus")
        self.setFixedWidth(380)

        self._init_ui()

    def _init_ui(self) -> None:
        """Menyusun seluruh komponen antarmuka pengguna pada area konten dialog."""
        content_layout = QVBoxLayout()
        content_layout.setContentsMargins(18, 16, 18, 16)
        content_layout.setSpacing(12)

        form_layout = QGridLayout()
        form_layout.setHorizontalSpacing(12)
        form_layout.setVerticalSpacing(12)

        label_style = """
            QLabel {
                color: #CDD6F4;
                font-size: 13px;
                font-weight: 600;
                background-color: transparent;
            }
        """

        input_style = """
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
            QLineEdit:disabled {
                background-color: #181825;
                border: 1px solid #28293D;
                color: #585B70;
            }
        """

        self._label_nominal = QLabel("Diskon Nominal", self)
        self._label_nominal.setStyleSheet(label_style)
        form_layout.addWidget(self._label_nominal, 0, 0, Qt.AlignmentFlag.AlignVCenter)

        self._input_nominal = QLineEdit(self)
        self._input_nominal.setValidator(QIntValidator(0, 1_000_000_000, self))
        self._input_nominal.setPlaceholderText("Rp 0")
        self._input_nominal.setStyleSheet(input_style)
        self._input_nominal.textChanged.connect(self._handle_nominal_changed)
        self._input_nominal.returnPressed.connect(self._handle_apply_clicked)
        form_layout.addWidget(self._input_nominal, 0, 1)

        self._label_percent = QLabel("Diskon Persen (%)", self)
        self._label_percent.setStyleSheet(label_style)
        form_layout.addWidget(self._label_percent, 1, 0, Qt.AlignmentFlag.AlignVCenter)

        self._input_percent = QLineEdit(self)
        percent_regex = QRegularExpression(r"^([0-9]{1,2}(\.[0-9]{0,2})?|100(\.0{0,2})?)$")
        self._input_percent.setValidator(QRegularExpressionValidator(percent_regex, self))
        self._input_percent.setPlaceholderText("0 %")
        self._input_percent.setStyleSheet(input_style)
        self._input_percent.textChanged.connect(self._handle_percent_changed)
        self._input_percent.returnPressed.connect(self._handle_apply_clicked)
        form_layout.addWidget(self._input_percent, 1, 1)

        content_layout.addLayout(form_layout)

        if self._initial_nominal > 0:
            self._input_nominal.setText(str(self._initial_nominal))
            self._input_nominal.selectAll()
            self._input_percent.setEnabled(False)
        elif self._initial_percent > 0.0:
            formatted_percent = (
                f"{self._initial_percent:.2f}".rstrip("0").rstrip(".")
            )
            self._input_percent.setText(formatted_percent)
            self._input_percent.selectAll()
            self._input_nominal.setEnabled(False)

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

    def _handle_nominal_changed(self, text: str) -> None:
        """Mengatur status aktif kolom persentase berdasarkan isi kolom nominal.

        Args:
            text: Teks yang sedang dimasukkan pada kolom diskon nominal.
        """
        has_content = bool(text.strip())
        self._input_percent.setEnabled(not has_content)

    def _handle_percent_changed(self, text: str) -> None:
        """Mengatur status aktif kolom nominal berdasarkan isi kolom persentase.

        Args:
            text: Teks yang sedang dimasukkan pada kolom diskon persen.
        """
        has_content = bool(text.strip())
        self._input_nominal.setEnabled(not has_content)

    def _handle_reset_clicked(self) -> None:
        """Mengosongkan kedua kolom input diskon dan mengaktifkan kembali seluruh kolom."""
        self._input_nominal.blockSignals(True)
        self._input_percent.blockSignals(True)
        self._input_nominal.clear()
        self._input_percent.clear()
        self._input_nominal.blockSignals(False)
        self._input_percent.blockSignals(False)

        self._input_nominal.setEnabled(True)
        self._input_percent.setEnabled(True)
        self._input_nominal.setFocus()

    def _handle_apply_clicked(self) -> None:
        """Membaca input diskon aktif, menyimpannya ke variabel hasil, lalu menyetujui dialog."""
        nominal_text = self._input_nominal.text().strip()
        percent_text = self._input_percent.text().strip()

        if nominal_text:
            try:
                self._discount_type = "nominal"
                self._result_value = float(max(0, int(nominal_text)))
            except ValueError:
                self._discount_type = "none"
                self._result_value = 0.0
        elif percent_text:
            try:
                parsed_percent = float(percent_text)
                self._discount_type = "percent"
                self._result_value = max(0.0, min(100.0, parsed_percent))
            except ValueError:
                self._discount_type = "none"
                self._result_value = 0.0
        else:
            self._discount_type = "none"
            self._result_value = 0.0

        self.accept()

    def get_discount_type(self) -> str:
        """Mengembalikan jenis diskon yang dipilih kasir.

        Returns:
            String penanda jenis diskon: 'nominal', 'percent', atau 'none'.
        """
        return self._discount_type

    def get_value(self) -> float:
        """Mengembalikan nilai diskon dalam bentuk angka desimal.

        Returns:
            Besaran nilai nominal dalam rupiah atau persentase antara 0 hingga 100.
        """
        return self._result_value

    def get_nominal_value(self) -> int:
        """Mengembalikan nilai diskon jika jenis diskon adalah nominal.

        Returns:
            Nominal diskon rupiah atau 0 jika jenis diskon bukan nominal.
        """
        if self._discount_type == "nominal":
            return int(self._result_value)
        return 0

    def get_percent_value(self) -> float:
        """Mengembalikan nilai persentase diskon jika jenis diskon adalah persen.

        Returns:
            Persentase diskon atau 0.0 jika jenis diskon bukan persentase.
        """
        if self._discount_type == "percent":
            return self._result_value
        return 0.0

    @classmethod
    def get_bonus(
        cls,
        parent: QWidget | None = None,
        initial_nominal: int = 0,
        initial_percent: float = 0.0,
        title: str = "Input Diskon / Bonus",
    ) -> tuple[str, float, bool]:
        """Membuka dialog bonus secara modal dan mengembalikan tipe diskon, nilai, serta status dialog.

        Args:
            parent: Widget induk pemilik dialog.
            initial_nominal: Nilai nominal diskon awal dalam rupiah.
            initial_percent: Nilai persentase diskon awal antara 0 hingga 100.
            title: Teks judul jendela dialog kustom.

        Returns:
            Tuple yang memuat jenis diskon ('nominal', 'percent', atau 'none'), nilai diskon,
            dan status boolean True jika disetujui, False jika dibatalkan.
        """
        dialog = cls(
            parent=parent,
            initial_nominal=initial_nominal,
            initial_percent=initial_percent,
        )
        if title:
            dialog.setWindowTitle(title)
        accepted = dialog.exec() == QDialog.DialogCode.Accepted
        if accepted:
            return dialog.get_discount_type(), dialog.get_value(), True

        fallback_type = (
            "nominal"
            if initial_nominal > 0
            else ("percent" if initial_percent > 0.0 else "none")
        )
        fallback_value = (
            float(initial_nominal) if initial_nominal > 0 else initial_percent
        )
        return fallback_type, fallback_value, False
