"""Dialog penyesuaian harga jual varian satuan barang langsung saat kulakan."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ui.dialog._tambahstok_dialog_style import DIALOG_STYLESHEET
from ui.tambahstok import CurrencySpinBox, ItemUnitOption
from util.helper.formatrupiah import format_qty as format_quantity, format_rupiah


class EditSellingPriceDialog(QDialog):
    """Dialog penyesuaian harga jual varian satuan barang langsung saat kulakan."""

    def __init__(
        self,
        item_name: str,
        units: list[ItemUnitOption],
        parent: QWidget | None = None,
    ) -> None:
        """Menginisialisasi EditSellingPriceDialog.

        Args:
            item_name: Nama barang yang sedang diedit harga jualnya.
            units: Daftar varian satuan milik barang tersebut.
            parent: Widget induk opsional.
        """
        super().__init__(parent)
        self._spin_by_unit_id: dict[int, CurrencySpinBox] = {}
        self.setWindowTitle(f"Ubah Harga Jual - {item_name}")
        self.setMinimumWidth(460)
        self.setStyleSheet(DIALOG_STYLESHEET)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        title = QLabel(f"Sesuaikan Harga Jual: {item_name}", self)
        title.setObjectName("dialogTitle")
        subtitle = QLabel(
            "Perbarui harga jual apabila harga modal dari supplier mengalami perubahan.",
            self,
        )
        subtitle.setObjectName("dialogSubtitle")
        subtitle.setWordWrap(True)
        layout.addWidget(title)
        layout.addWidget(subtitle)

        card = QFrame(self)
        card.setObjectName("dialogCard")
        form = QFormLayout(card)
        form.setContentsMargins(12, 12, 12, 12)
        form.setSpacing(10)

        for unit in units:
            spin = CurrencySpinBox(parent=card)
            spin.setValue(max(0, unit["selling_price"]))
            spin.setFixedHeight(32)
            label_text = (
                f"{unit['variant_name']} (x{format_quantity(unit['conversion_qty'])})  "
                f"[Modal akhir: {format_rupiah(unit['last_unit_cost'])}]"
            )
            form.addRow(label_text, spin)
            self._spin_by_unit_id[unit["item_unit_id"]] = spin

        layout.addWidget(card)

        btn_row = QHBoxLayout()
        btn_row.addStretch(1)
        cancel_btn = QPushButton("Batal", self)
        cancel_btn.setObjectName("secondaryBtn")
        cancel_btn.clicked.connect(self.reject)

        save_btn = QPushButton("Simpan Harga Jual", self)
        save_btn.setObjectName("primaryBtn")
        save_btn.clicked.connect(self.accept)

        btn_row.addWidget(cancel_btn)
        btn_row.addWidget(save_btn)
        layout.addLayout(btn_row)

    def get_updated_prices(self) -> dict[int, int]:
        """Mengembalikan peta item_unit_id ke harga jual terbaru hasil input pengguna.

        Returns:
            Dictionary item_unit_id -> selling_price.
        """
        return {
            unit_id: spin.value() for unit_id, spin in self._spin_by_unit_id.items()
        }
