"""Modul antarmuka kasir utama (DashboardPOS) berbasis PySide6.

Modul ini menyediakan komponen UI murni untuk layar kasir POS yang mencakup
header kasir, panel pencarian produk, tabel keranjang belanja, ringkasan
pembayaran, panel input pembayaran, dan tombol aksi transaksi.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, QSize, Signal, QEvent, QObject, QTimer
from PySide6.QtGui import (
    QCursor, QKeyEvent, 
    QKeySequence, QShortcut, QShowEvent
)
from PySide6.QtSvgWidgets import QSvgWidget
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QLineEdit, QPushButton, QComboBox, QTableWidget,
    QHeaderView, QTextEdit, QCheckBox, QStackedWidget, QFrame,
    QTableWidgetItem, QSpinBox
)
from typing import Dict, List, Any, Optional, Union

from config import get_asset_path
from ui.customsidebar import (
    Sidebar,
)
from util.helper.formatrupiah import format_rupiah

class CardWidget(QFrame):
    """Widget dasar dengan gaya visual card.
    
    Digunakan sebagai kontainer berlatar belakang gelap dengan border tipis 
    untuk mengelompokkan elemen-elemen UI agar menyerupai referensi desain.
    """
    
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        """Menginisialisasi CardWidget dengan styling QSS dasar."""
        super().__init__(parent)
        self.setStyleSheet(
            """
            CardWidget {
                background-color: #181825;
                border: 1px solid #313244;
                border-radius: 8px;
            }
            """
        )




class TransactionHeader(QWidget):
    """Bagian header untuk area transaksi utama.
    
    Menampilkan judul halaman, identitas kasir, dan role akses pengguna.
    """
    
    def __init__(self, user_name: str = "KASIR", user_role: str = "USER", parent: Optional[QWidget] = None) -> None:
        """Menginisialisasi elemen header transaksi.
        
        Args:
            user_name: Nama kasir yang sedang login.
            user_role: Role / level akses pengguna yang sedang login.
        """
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        kasir_icon_path = str(get_asset_path("icons/kasir_100.svg"))
        kasir_icon = QSvgWidget(kasir_icon_path)
        kasir_icon.setFixedSize(QSize(60, 60))
        layout.addWidget(kasir_icon)

        layout.addSpacing(10)

        self.title_label = QLabel("TRANSAKSI PENJUALAN")
        self.title_label.setStyleSheet("font-size: 20px; font-weight: bold; color: #CDD6F4;")
        
        self.cashier_badge = QLabel(f"NAMA KASIR : {user_name.upper()}")
        self.cashier_badge.setStyleSheet(
            """
            QLabel {
                color: #2ECC71;
                border: 1px solid #2ECC71;
                border-radius: 12px;
                padding: 4px 12px;
                font-size: 11px;
                font-weight: bold;
            }
            """
        )
        
        self.role_badge = QLabel(user_role.upper())
        self.role_badge.setStyleSheet(
            """
            QLabel {
                color: #2ECC71;
                border: 1px solid #2ECC71;
                border-radius: 12px;
                padding: 4px 12px;
                font-size: 11px;
                font-weight: bold;
            }
            """
        )
        
        title_layout = QVBoxLayout()
        title_layout.addWidget(self.title_label)
        
        badge_layout = QHBoxLayout()
        badge_layout.addWidget(self.cashier_badge)
        badge_layout.addWidget(self.role_badge)
        badge_layout.addStretch()
        
        title_layout.addLayout(badge_layout)
        
        layout.addLayout(title_layout)
        layout.addStretch()

    def set_user_info(self, user_name: str, user_role: str) -> None:
        """Memperbarui informasi identitas kasir dan role pada badge header.

        Args:
            user_name: Nama kasir baru.
            user_role: Role akses kasir baru.
        """
        self.cashier_badge.setText(f"NAMA KASIR : {user_name.upper()}")
        self.role_badge.setText(user_role.upper())


class ProductSearchPanel(CardWidget):
    """Panel pencarian produk di atas keranjang belanja.
    
    Berisi field input pencarian, dropdown kategori, dan tombol tambah.
    """

    search_submitted = Signal(str, str)
    add_requested = Signal()
    
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        """Menginisialisasi form pencarian produk."""
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(8)
        
        input_layout = QHBoxLayout()
        input_layout.setSpacing(12)
        
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Ketik nama produk / SKU lalu tekan Enter...")
        self.search_input.setStyleSheet(
            """
            QLineEdit {
                background-color: #11111B;
                border: 1px solid #313244;
                border-radius: 6px;
                padding: 10px;
                color: #CDD6F4;
            }
            QLineEdit:focus {
                border: 1px solid #2ECC71;
            }
            """
        )
        
        self.category_combo = QComboBox()
        self.category_combo.addItems(["Semua Produk", "Produk Satuan", "Produk Paket", "Jasa"])
        self.category_combo.setFixedWidth(200)
        icon_down_path = get_asset_path("icons/icon_down.svg").as_posix()
        self.category_combo.setStyleSheet(
            f"""
            QComboBox {{
                background-color: #11111B;
                border: 1px solid #313244;
                border-radius: 6px;
                padding: 10px;
                color: #CDD6F4;
            }}
            QComboBox::drop-down {{
                subcontrol-origin: padding;
                subcontrol-position: top right;
                width: 24px;
                border-left: 1px solid #313244;
            }}
            QComboBox::down-arrow {{
                image: url({icon_down_path});
                width: 12px;
                height: 12px;
            }}
            QComboBox QAbstractItemView {{
                background-color: #11111B;
                color: white;
                border: 1px solid #313244;
                selection-background-color: #0078D7;
            }}
            QComboBox:focus {{
                border: 1px solid #2ECC71;
            }}
            """
        )
        
        self.add_btn = QPushButton("Tambah ke Keranjang")
        self.add_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.add_btn.setStyleSheet(
            """
            QPushButton {
                background-color: #2ECC71;
                color: #11111B;
                border-radius: 6px;
                padding: 10px 24px;
                font-weight: bold;
                outline: none;
            }
            QPushButton:hover {
                background-color: #27AE60;
            }
            QPushButton:focus {
                border: 2px solid #FFFFFF;
                padding: 8px 22px;
            }
            """
        )
        
        input_layout.addWidget(self.search_input, stretch=1)
        input_layout.addWidget(self.category_combo)
        input_layout.addWidget(self.add_btn)
        
        self.helper_label = QLabel("Cari produk berdasarkan SKU atau nama produk.")
        self.helper_label.setStyleSheet("color: #7F849C; font-size: 11px; background-color: transparent;")
        
        layout.addLayout(input_layout)
        layout.addWidget(self.helper_label)

        self.search_input.returnPressed.connect(self._on_search_enter)
        self.add_btn.clicked.connect(self.add_requested.emit)

    def _on_search_enter(self) -> None:
        """Memancarkan sinyal saat pengguna menekan tombol Enter pada input pencarian."""
        self.search_submitted.emit(
            self.search_input.text().strip(),
            self.category_combo.currentText(),
        )

    def get_search_query(self) -> str:
        """Mengambil teks kata kunci pencarian yang sedang diinput.

        Returns:
            String kata kunci pencarian tanpa spasi di awal dan akhir.
        """
        return self.search_input.text().strip()

    def get_selected_category(self) -> str:
        """Mengambil kategori produk yang sedang dipilih pada dropdown.

        Returns:
            Nama kategori terpilih.
        """
        return self.category_combo.currentText()

    def set_categories(self, categories: List[str]) -> None:
        """Memperbarui daftar pilihan kategori pada dropdown pencarian.

        Args:
            categories: Daftar nama kategori baru.
        """
        self.category_combo.clear()
        self.category_combo.addItems(categories)

    def clear_search(self) -> None:
        """Mengosongkan input pencarian dan mengembalikan teks bantuan ke kondisi awal."""
        self.search_input.clear()
        self.helper_label.setText("Cari produk berdasarkan SKU atau nama produk.")
        self.helper_label.setStyleSheet("color: #7F849C; font-size: 11px; background-color: transparent;")

    def set_helper_text(self, text: str, is_error: bool = False) -> None:
        """Mengubah teks petunjuk atau menampilkan status error pencarian.

        Args:
            text: Pesan teks yang ingin ditampilkan.
            is_error: True jika pesan merupakan notifikasi error.
        """
        self.helper_label.setText(text)
        color = "#E74C3C" if is_error else "#7F849C"
        self.helper_label.setStyleSheet(f"color: {color}; font-size: 11px; background-color: transparent;")


class QuantityControlWidget(QWidget):
    """Widget pengontrol kuantitas item keranjang dengan tombol kurang, tambah, dan spinbox angka."""

    quantity_changed = Signal(int)

    def __init__(self, initial_qty: int = 1, parent: Optional[QWidget] = None) -> None:
        """Menginisialisasi komponen pengatur kuantitas beserta interaksinya.

        Args:
            initial_qty: Nilai kuantitas awal yang ditampilkan.
            parent: Objek widget induk opsional.
        """
        super().__init__(parent)
        self._last_qty: int = int(initial_qty)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 2, 4, 2)
        layout.setSpacing(4)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.btn_minus = QPushButton("-")
        self.btn_minus.setFixedSize(24, 24)
        self.btn_minus.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.btn_minus.setStyleSheet(
            """
            QPushButton {
                background-color: #11111B;
                color: #CDD6F4;
                border: 1px solid #313244;
                border-radius: 4px;
                font-size: 13px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #313244;
                color: #FFFFFF;
            }
            QPushButton:pressed {
                background-color: #181825;
            }
            """
        )

        self.qty_spin = QSpinBox()
        self.qty_spin.setRange(0, 99999)
        self.qty_spin.setValue(int(initial_qty))
        self.qty_spin.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.qty_spin.setFixedSize(50, 24)
        self.qty_spin.setButtonSymbols(QSpinBox.ButtonSymbols.NoButtons)
        self.qty_spin.setStyleSheet(
            """
            QSpinBox {
                background-color: #11111B;
                color: #CDD6F4;
                border: 1px solid #313244;
                border-radius: 4px;
                font-size: 12px;
                font-weight: bold;
                padding: 0px;
            }
            QSpinBox:focus {
                border: 1px solid #2ECC71;
            }
            """
        )

        self.btn_plus = QPushButton("+")
        self.btn_plus.setFixedSize(24, 24)
        self.btn_plus.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.btn_plus.setStyleSheet(
            """
            QPushButton {
                background-color: #11111B;
                color: #CDD6F4;
                border: 1px solid #313244;
                border-radius: 4px;
                font-size: 13px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #313244;
                color: #FFFFFF;
            }
            QPushButton:pressed {
                background-color: #181825;
            }
            """
        )

        self.btn_minus.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.btn_plus.setFocusPolicy(Qt.FocusPolicy.NoFocus)

        self.btn_minus.clicked.connect(self._on_minus_clicked)
        self.btn_plus.clicked.connect(self._on_plus_clicked)
        self.qty_spin.editingFinished.connect(self._on_editing_finished)

        layout.addWidget(self.btn_minus)
        layout.addWidget(self.qty_spin)
        layout.addWidget(self.btn_plus)

    def _on_minus_clicked(self) -> None:
        """Menurunkan nilai kuantitas sebanyak satu unit dan memancarkan sinyal."""
        self.qty_spin.setFocus()
        new_val = self.qty_spin.value() - 1
        self.quantity_changed.emit(new_val)

    def _on_plus_clicked(self) -> None:
        """Menaikkan nilai kuantitas sebanyak satu unit dan memancarkan sinyal."""
        self.qty_spin.setFocus()
        new_val = self.qty_spin.value() + 1
        self.quantity_changed.emit(new_val)

    def _on_editing_finished(self) -> None:
        """Memancarkan sinyal kuantitas baru setelah kasir selesai mengetikkan angka."""
        current_val = self.qty_spin.value()
        if current_val != self._last_qty:
            self._last_qty = current_val
            self.quantity_changed.emit(current_val)

    def get_value(self) -> int:
        """Mengambil nilai kuantitas saat ini dari spinbox.

        Returns:
            Nilai integer kuantitas produk.
        """
        return self.qty_spin.value()

    def set_value(self, value: int) -> None:
        """Mengatur nilai kuantitas pada spinbox.

        Args:
            value: Nilai integer kuantitas baru.
        """
        self._last_qty = int(value)
        self.qty_spin.setValue(int(value))


class CartPanel(CardWidget):
    """Panel keranjang belanja yang menampilkan tabel transaksi.
    
    Menampilkan kolom data produk, status kosong (empty state), dan tombol kontrol.
    """

    clear_cart_requested = Signal()
    item_removed = Signal(int)
    item_quantity_changed = Signal(int, int)
    
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        """Menginisialisasi tabel keranjang belanja dan status antarmuka kosong."""
        super().__init__(parent)
        self._cart_items: List[Dict[str, Any]] = []
        self._qty_inputs: List[QSpinBox] = []
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        
        self.table = QTableWidget(0, 8)
        self.table.verticalHeader().setVisible(False)
        self.table.setTabKeyNavigation(False)
        self.table.setHorizontalHeaderLabels(
            ["No", "SKU", "Produk", "Tipe", "Harga", "Qty", "Subtotal", "Aksi"]
        )
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        header = self.table.horizontalHeader()
        header.setSectionsClickable(False)
        header.setHighlightSections(False)
        header.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.table.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.table.setSelectionMode(QTableWidget.SelectionMode.NoSelection)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setColumnWidth(0, 45)
        self.table.setColumnWidth(5, 120)
        self.table.setColumnWidth(7, 80)
        self.table.setStyleSheet(
            """
            QTableWidget {
                background-color: transparent;
                border: 1px solid #313244;
                border-radius: 6px;
                color: #CDD6F4;
                gridline-color: #313244;
            }
            QHeaderView::section {
                background-color: #11111B;
                color: #A6ADC8;
                padding: 8px;
                border: none;
                border-bottom: 1px solid #313244;
                border-right: 1px solid #313244;
            }
            """
        )
        
        self.empty_state_label = QLabel("Keranjang masih kosong.")
        self.empty_state_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty_state_label.setStyleSheet("color: #7F849C; font-size: 14px;")
        
        self.stacked_widget = QStackedWidget()
        self.stacked_widget.addWidget(self.empty_state_label)
        self.stacked_widget.addWidget(self.table)
        self.stacked_widget.setCurrentIndex(0)
        
        bottom_layout = QHBoxLayout()
        bottom_layout.addStretch()
        
        self.clear_btn = QPushButton("Kosongkan Keranjang")
        self.clear_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.clear_btn.setStyleSheet(
            """
            QPushButton {
                background-color: transparent;
                color: #CDD6F4;
                border: 1px solid #313244;
                border-radius: 6px;
                padding: 8px 16px;
                outline: none;
            }
            QPushButton:hover {
                background-color: #313244;
            }
            QPushButton:focus {
                border: 1px solid #2ECC71;
                color: #2ECC71;
            }
            """
        )
        self.clear_btn.clicked.connect(self.clear_cart_requested.emit)
        bottom_layout.addWidget(self.clear_btn)
        
        layout.addWidget(self.stacked_widget)
        layout.addLayout(bottom_layout)

    def _create_selectable_label(
        self,
        text: str,
        alignment: Qt.AlignmentFlag = Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
    ) -> QLabel:
        """Membuat QLabel transparan yang teksnya dapat diblok dan disalin.

        Args:
            text: Teks yang akan ditampilkan di dalam sel.
            alignment: Perataan teks di dalam sel.

        Returns:
            Widget QLabel dengan interaksi seleksi teks aktif.
        """
        label = QLabel(text)
        label.setAlignment(alignment)
        label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        label.setCursor(QCursor(Qt.CursorShape.IBeamCursor))
        label.setStyleSheet(
            """
            QLabel {
                background-color: transparent;
                color: #CDD6F4;
                padding: 0px 6px;
            }
            """
        )
        return label

    def set_items(self, items: List[Dict[str, Any]]) -> None:
        """Memuat daftar item transaksi ke dalam tabel keranjang belanja.

        Args:
            items: Daftar dictionary informasi item. Setiap elemen dapat memuat:
                sku, name, item_type, price, qty, subtotal, dan opsi id.
        """
        self._cart_items = list(items)
        if not items:
            self.clear_cart()
            return

        focused_row: Optional[int] = None
        for idx, spin in enumerate(self._qty_inputs):
            if spin.hasFocus():
                focused_row = idx
                break
        
        self._qty_inputs.clear()

        self.table.setRowCount(len(items))
        for row_idx, item in enumerate(items):
            item_id = item.get("id", row_idx)

            no_item = QTableWidgetItem(str(row_idx + 1))
            no_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            no_item.setFlags(no_item.flags() & ~Qt.ItemFlag.ItemIsEditable)

            sku_label = self._create_selectable_label(
                str(item.get("sku", "")),
                Qt.AlignmentFlag.AlignCenter,
            )

            name_label = self._create_selectable_label(
                str(item.get("name", "")),
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            )

            type_item = QTableWidgetItem(str(item.get("item_type", "Produk")))
            type_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            type_item.setFlags(type_item.flags() & ~Qt.ItemFlag.ItemIsEditable)

            price_val = item.get("price", 0)
            price_text = format_rupiah(int(price_val))
            price_item = QTableWidgetItem(price_text)
            price_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            price_item.setFlags(price_item.flags() & ~Qt.ItemFlag.ItemIsEditable)

            qty_val = int(item.get("qty", 1))
            qty_control = QuantityControlWidget(initial_qty=qty_val)
            qty_control.quantity_changed.connect(
                lambda val, idx=item_id: self.item_quantity_changed.emit(idx, val)
            )
            self._qty_inputs.append(qty_control.qty_spin)

            subtotal_val = item.get("subtotal", price_val * qty_val)
            subtotal_text = format_rupiah(int(subtotal_val))
            subtotal_item = QTableWidgetItem(subtotal_text)
            subtotal_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            subtotal_item.setFlags(subtotal_item.flags() & ~Qt.ItemFlag.ItemIsEditable)

            self.table.setItem(row_idx, 0, no_item)
            self.table.setCellWidget(row_idx, 1, sku_label)
            self.table.setCellWidget(row_idx, 2, name_label)
            self.table.setItem(row_idx, 3, type_item)
            self.table.setItem(row_idx, 4, price_item)
            self.table.setCellWidget(row_idx, 5, qty_control)
            self.table.setItem(row_idx, 6, subtotal_item)

            action_widget = QWidget()
            action_layout = QHBoxLayout(action_widget)
            action_layout.setContentsMargins(4, 2, 4, 2)
            action_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

            del_btn = QPushButton("Hapus")
            del_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
            del_btn.setStyleSheet(
                """
                QPushButton {
                    background-color: transparent;
                    color: #E74C3C;
                    border: 1px solid #E74C3C;
                    border-radius: 4px;
                    padding: 4px 8px;
                    font-size: 11px;
                    font-weight: bold;
                }
                QPushButton:hover {
                    background-color: rgba(231, 76, 60, 0.15);
                }
                """
            )
            del_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            del_btn.clicked.connect(lambda checked=False, idx=item_id: self.item_removed.emit(idx))
            action_layout.addWidget(del_btn)
            self.table.setCellWidget(row_idx, 7, action_widget)

        self.stacked_widget.setCurrentIndex(1)

        if focused_row is not None and self._qty_inputs:
            target_idx = min(focused_row, len(self._qty_inputs) - 1)
            target_spin = self._qty_inputs[target_idx]
            target_spin.setFocus()
            target_spin.selectAll()

    def clear_cart(self) -> None:
        """Mengosongkan isi tabel keranjang belanja dan menampilkan label status kosong."""
        self._cart_items = []
        self._qty_inputs.clear()
        self.table.setRowCount(0)
        self.stacked_widget.setCurrentIndex(0)

    def get_items(self) -> List[Dict[str, Any]]:
        """Mengembalikan salinan data item yang saat ini ada di keranjang belanja.

        Returns:
            Daftar dictionary item transaksi.
        """
        return list(self._cart_items)

    def get_qty_inputs(self) -> List[QSpinBox]:
        """Mengembalikan daftar widget QSpinBox kuantitas sesuai urutan baris tabel.

        Returns:
            Daftar QSpinBox untuk pengaturan urutan fokus Tab.
        """
        return list(self._qty_inputs)


class TransactionSummaryPanel(CardWidget):
    """Panel ringkasan nominal transaksi penjualan.
    
    Menampilkan rincian angka seperti subtotal, diskon, dan total tagihan akhir.
    """
    
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        """Menginisialisasi layout ringkasan angka transaksi."""
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(3)
        
        self.value_labels: Dict[str, QLabel] = {}
        items = [
            ("Subtotal", "Rp 0"),
            ("Diskon", "Rp 0"),
            ("Pembulatan", "Rp 0"),
            ("Tip / Bonus", "Rp 0")
        ]
        
        for label_text, value_text in items:
            row_layout = QHBoxLayout()
            lbl = QLabel(label_text)
            lbl.setStyleSheet("color: #A6ADC8; font-size: 13px; background-color: transparent;")
            val = QLabel(value_text)
            val.setStyleSheet("color: #CDD6F4; font-size: 13px; font-weight: bold; background-color: transparent;")
            val.setAlignment(Qt.AlignmentFlag.AlignRight)
            row_layout.addWidget(lbl)
            row_layout.addWidget(val)
            layout.addLayout(row_layout)
            self.value_labels[label_text] = val
            
        layout.addSpacing(8)
        
        total_lbl = QLabel("Total Tagihan")
        total_lbl.setStyleSheet("color: #A6ADC8; font-size: 12px; background-color: transparent;")
        
        self.total_val = QLabel("Rp 0")
        self.total_val.setStyleSheet("color: #2ECC71; font-size: 24px; font-weight: bold; padding-left: 3; padding-bottom: 3")
        self.total_val.setAlignment(Qt.AlignmentFlag.AlignLeft)
        
        layout.addWidget(total_lbl)
        layout.addWidget(self.total_val)

    def update_summary(
        self,
        subtotal: Union[int, float] = 0,
        diskon: Union[int, float] = 0,
        pembulatan: Union[int, float] = 0,
        tip: Union[int, float] = 0,
        total: Union[int, float] = 0,
    ) -> None:
        """Memperbarui seluruh rincian angka ringkasan transaksi.

        Args:
            subtotal: Nilai subtotal barang.
            diskon: Nilai potongan harga atau diskon.
            pembulatan: Nilai penyesuaian pembulatan.
            tip: Nilai tip atau bonus kasir.
            total: Nilai akhir total tagihan.
        """
        if "Subtotal" in self.value_labels:
            self.value_labels["Subtotal"].setText(format_rupiah(int(subtotal)))
        if "Diskon" in self.value_labels:
            self.value_labels["Diskon"].setText(format_rupiah(int(diskon)))
        if "Pembulatan" in self.value_labels:
            self.value_labels["Pembulatan"].setText(format_rupiah(int(pembulatan)))
        if "Tip / Bonus" in self.value_labels:
            self.value_labels["Tip / Bonus"].setText(format_rupiah(int(tip)))
        self.total_val.setText(format_rupiah(int(total)))

    def reset_summary(self) -> None:
        """Mengembalikan seluruh tampilan ringkasan nominal ke nilai awal nol."""
        for val_lbl in self.value_labels.values():
            val_lbl.setText("Rp 0")
        self.total_val.setText("Rp 0")


class PaymentPanel(CardWidget):
    """Panel form input detail pembayaran.
    
    Menyediakan field untuk metode pembayaran, nominal, data customer, 
    catatan, estimasi kembalian, dan preferensi pencetakan nota.
    """

    method_changed = Signal(str)
    amount_changed = Signal(str)
    customer_changed = Signal(str)
    
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        """Menginisialisasi form pembayaran."""
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        
        icon_down_path = get_asset_path("icons/icon_down.svg").as_posix()
        common_input_style = f"""
            QComboBox, QLineEdit, QTextEdit {{
                background-color: #11111B;
                border: 1px solid #313244;
                border-radius: 6px;
                padding: 3px;
                color: #CDD6F4;
                font-size: 12px;
            }}
            QComboBox:focus, QLineEdit:focus, QTextEdit:focus {{
                border: 1px solid #2ECC71;
            }}
            QComboBox::drop-down {{
                subcontrol-origin: padding;
                subcontrol-position: top right;
                width: 24px;
                border-left: 1px solid #313244;
            }}
            QComboBox::down-arrow {{
                image: url({icon_down_path});
                width: 10px;
                height: 10px;
            }}
            QComboBox QAbstractItemView {{
                background-color: #11111B;
                color: white;
                border: 1px solid #313244;
                selection-background-color: #0078D7;
            }}
        """
        
        method_layout = QHBoxLayout()
        method_lbl = QLabel("Metode Bayar")
        method_lbl.setFixedWidth(100)
        method_lbl.setStyleSheet("color: #CDD6F4; font-size: 12px; background-color: transparent;")
        self.method_combo = QComboBox()
        self.method_combo.addItems(["Tunai", "QRIS", "Transfer", "Belum Lunas"])
        self.method_combo.setStyleSheet(common_input_style)
        self.method_combo.currentTextChanged.connect(self._on_method_selection_changed)
        method_layout.addWidget(method_lbl)
        method_layout.addWidget(self.method_combo)
        
        amount_layout = QHBoxLayout()
        amount_lbl = QLabel("Nominal Bayar")
        amount_lbl.setFixedWidth(100)
        amount_lbl.setStyleSheet("color: #CDD6F4; font-size: 12px; background-color: transparent;")
        self.amount_input = QLineEdit()
        self.amount_input.setPlaceholderText("Rp. ")
        self.amount_input.setStyleSheet(common_input_style)
        self.amount_input.textChanged.connect(self._on_amount_text_changed)
        amount_layout.addWidget(amount_lbl)
        amount_layout.addWidget(self.amount_input)
        
        cust_layout = QHBoxLayout()
        cust_lbl = QLabel("Nama Customer")
        cust_lbl.setFixedWidth(100)
        cust_lbl.setStyleSheet("color: #CDD6F4; font-size: 12px; background-color: transparent;")
        self.cust_input = QLineEdit()
        self.cust_input.setPlaceholderText("Opsional, misal: Pelanggan ...")
        self.cust_input.setStyleSheet(common_input_style)
        self.cust_input.textChanged.connect(self.customer_changed.emit)
        cust_layout.addWidget(cust_lbl)
        cust_layout.addWidget(self.cust_input)
        
        note_layout = QVBoxLayout()
        note_lbl = QLabel("Catatan Kasir")
        note_lbl.setStyleSheet("color: #CDD6F4; font-size: 12px; background-color: transparent;")
        self.note_input = QTextEdit()
        self.note_input.setFocusPolicy(Qt.FocusPolicy.ClickFocus)
        self.note_input.setPlaceholderText("tulis informasi disini")
        self.note_input.setStyleSheet(common_input_style)
        self.change_lbl = QLabel("Kembalian: Rp 0")
        self.change_lbl.setStyleSheet("color: #CDD6F4; font-size: 14px; font-weight: bold; background-color: transparent;")
        self.print_check = QCheckBox("Cetak Nota Transaksi")
        self.print_check.setStyleSheet(
            """
            QCheckBox {
                color: #A6ADC8;
                font-size: 12px;
                background-color: transparent;
                outline: none;
            }
            QCheckBox:focus {
                color: #2ECC71;
            }
            """
        )
        note_layout.addWidget(note_lbl)
        note_layout.addWidget(self.note_input)
        note_layout.addWidget(self.change_lbl)
        note_layout.addWidget(self.print_check)
        
        layout.addLayout(method_layout)
        layout.addLayout(amount_layout)
        layout.addLayout(cust_layout)
        layout.addLayout(note_layout)

    def _on_amount_text_changed(self, text: str) -> None:
        """Memformat input nominal bayar menjadi format mata uang Rupiah."""
        digits = "".join(ch for ch in text if ch.isdigit())
        formatted = format_rupiah(int(digits)) if digits else ""
        if self.amount_input.text() != formatted:
            self.amount_input.blockSignals(True)
            self.amount_input.setText(formatted)
            self.amount_input.setCursorPosition(len(formatted))
            self.amount_input.blockSignals(False)
        self.amount_changed.emit(formatted)

    def _on_method_selection_changed(self, method: str) -> None:
        """Menangani penyesuaian visual formulir saat metode pembayaran berganti.

        Args:
            method: Nama metode pembayaran yang dipilih.
        """
        if method == "Belum Lunas":
            self.amount_input.setPlaceholderText("Rp. 0 (Tempo) / > 1.000 (DP)")
            self.cust_input.setPlaceholderText("Wajib diisi (Piutang Pelanggan)...")
        else:
            self.amount_input.setPlaceholderText("Rp. ")
            self.cust_input.setPlaceholderText("Opsional, misal: Pelanggan ...")
        self.method_changed.emit(method)

    def get_payment_status(self) -> str:
        """Mendeteksi otomatis payment_status berdasarkan metode bayar dan nominal yang diinput.

        Logika deteksi:
            - Jika metode 'Belum Lunas':
              - Jika nominal bayar (amount_input) > 1000: 'PARTIAL' (uang muka / DP)
              - Jika nominal bayar == 0 (atau <= 1000): 'UNPAID' (tempo / belum bayar sama sekali)
            - Jika metode lainnya (Tunai, QRIS, Transfer): 'PAID'

        Returns:
            String status pelunasan: 'PAID', 'PARTIAL', atau 'UNPAID'.
        """
        method = self.method_combo.currentText().strip()
        raw_text = self.amount_input.text().replace("Rp", "").replace(".", "").replace(",", "").strip()
        parsed_amount = int(raw_text) if raw_text.isdigit() else 0

        if method == "Belum Lunas":
            if parsed_amount > 1000:
                return "PARTIAL"
            return "UNPAID"
        return "PAID"

    def validate_payment(self) -> tuple[bool, str]:
        """Memvalidasi aturan bisnis input pembayaran sebelum transaksi dieksekusi.

        Aturan:
            1. Jika metode 'Belum Lunas':
               - Nominal bayar harus lebih dari 1000 (DP) atau bernilai 0 (tempo penuh).
               - Nominal antara 1 s.d. 1000 tidak diizinkan.
               - Nama Customer wajib diisi agar piutang tertagih ke pelanggan tertentu.
            2. Jika payment_status != 'PAID', Nama Customer wajib diisi.

        Returns:
            Tuple (is_valid, error_message).
        """
        data = self.get_payment_data()
        method = data["payment_method"]
        amount = data["amount_paid"]
        cust = data["customer_name"]
        status = data["payment_status"]

        if method == "Belum Lunas":
            if 0 < amount <= 1000:
                return (
                    False,
                    "Untuk metode 'Belum Lunas', nominal bayar harus Rp 0 (tanpa DP/tempo) "
                    "atau lebih dari Rp 1.000 (uang muka / DP).",
                )
            if not cust:
                return (
                    False,
                    "Nama Customer wajib diisi untuk transaksi 'Belum Lunas' (UNPAID / PARTIAL) "
                    "agar piutang jelas tertagih ke pelanggan tertentu.",
                )
        elif status != "PAID" and not cust:
            return (
                False,
                "Nama Customer wajib diisi ketika status pembayaran belum lunas "
                "agar piutang jelas tertagih ke pelanggan tertentu.",
            )

        return True, ""

    def get_payment_data(self) -> Dict[str, Any]:
        """Mengambil seluruh data form input pembayaran saat ini.

        Returns:
            Dictionary rincian metode pembayaran, payment_status, nominal yang diinput,
            nama pelanggan, catatan transaksi, dan status opsi cetak nota.
        """
        raw_text = self.amount_input.text().replace("Rp", "").replace(".", "").replace(",", "").strip()
        parsed_amount = int(raw_text) if raw_text.isdigit() else 0
        method = self.method_combo.currentText().strip()
        payment_status = self.get_payment_status()

        return {
            "payment_method": method,
            "payment_status": payment_status,
            "amount_paid": parsed_amount,
            "raw_amount_text": self.amount_input.text(),
            "customer_name": self.cust_input.text().strip(),
            "note": self.note_input.toPlainText().strip(),
            "print_receipt": self.print_check.isChecked(),
        }

    def set_change_amount(self, amount: Union[int, float]) -> None:
        """Memperbarui nilai teks nominal kembalian.

        Args:
            amount: Nilai kembalian yang harus diberikan ke customer.
        """
        formatted = format_rupiah(int(amount))
        self.change_lbl.setText(f"Kembalian: {formatted}")

    def clear_form(self) -> None:
        """Mengosongkan isian formulir pembayaran dan mengembalikan ke status awal."""
        self.method_combo.setCurrentIndex(0)
        self.amount_input.clear()
        self.amount_input.setPlaceholderText("Rp. ")
        self.cust_input.clear()
        self.cust_input.setPlaceholderText("Opsional, misal: Pelanggan ...")
        self.note_input.clear()
        self.change_lbl.setText("Kembalian: Rp 0")
        self.print_check.setChecked(False)

    def set_payment_amount(self, amount: Union[int, float, str]) -> None:
        """Memperbarui teks pada input nominal pembayaran.

        Args:
            amount: Nilai nominal yang akan diisikan ke form.
        """
        self.amount_input.setText(str(amount))

    def set_payment_methods(self, methods: List[str]) -> None:
        """Memperbarui daftar opsi metode pembayaran yang tersedia.

        Args:
            methods: Daftar string metode pembayaran.
        """
        self.method_combo.clear()
        self.method_combo.addItems(methods)


class TransactionActionPanel(CardWidget):
    """Panel aksi utama untuk eksekusi akhir transaksi.
    
    Menampilkan grid tombol aksi pembayaran dan modifikasi transaksi.
    """

    discount_clicked = Signal()
    rounding_clicked = Signal()
    tip_clicked = Signal()
    pay_clicked = Signal()
    
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        """Menginisialisasi grid tombol aksi."""
        super().__init__(parent)
        layout = QGridLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)
        
        btn_style_template = """
            QPushButton {
                background-color: %s;
                color: %s;
                border-radius: 8px;
                padding: 8px;
                font-weight: bold;
                font-size: 13px;
                outline: none;
            }
            QPushButton::hover {
                background-color: %s;
            }
            QPushButton:focus {
                border: 2px solid #FFFFFF;
                padding: 6px;
            }
        """
        
        self.btn_diskon = QPushButton("Diskon")
        self.btn_diskon.setStyleSheet(btn_style_template % ("#F39C12", "#11111B", "#B7770D"))
        self.btn_diskon.clicked.connect(self.discount_clicked.emit)
        
        self.btn_pembulatan = QPushButton("Pembulatan")
        self.btn_pembulatan.setStyleSheet(btn_style_template % ("#3498DB", "#FFFFFF", "#1E6FA5"))
        self.btn_pembulatan.clicked.connect(self.rounding_clicked.emit)
        
        self.btn_tip = QPushButton("Tip / Bonus")
        self.btn_tip.setStyleSheet(btn_style_template % ("#1ABC9C", "#FFFFFF", "#128F76"))
        self.btn_tip.clicked.connect(self.tip_clicked.emit)
        
        self.btn_bayar = QPushButton("Bayar")
        self.btn_bayar.setStyleSheet(btn_style_template % ("#2ECC71", "#11111B", "#1E9950"))
        self.btn_bayar.clicked.connect(self.pay_clicked.emit)
        
        cursors = [self.btn_diskon, self.btn_pembulatan, self.btn_tip, self.btn_bayar]
        for btn in cursors:
            btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
            btn.installEventFilter(self)
            
        layout.addWidget(self.btn_diskon, 0, 0)
        layout.addWidget(self.btn_pembulatan, 0, 1)
        layout.addWidget(self.btn_tip, 1, 0)
        layout.addWidget(self.btn_bayar, 1, 1)

    def set_pay_enabled(self, enabled: bool) -> None:
        """Mengatur status ketersediaan tombol Bayar.

        Args:
            enabled: True jika tombol aktif, False jika dinonaktifkan.
        """
        self.btn_bayar.setEnabled(enabled)

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        """Menangkap tombol Enter saat fokus berada pada tombol aksi.

        Args:
            watched: Objek widget yang sedang dipantau.
            event: Objek event yang terjadi pada widget.

        Returns:
            True jika event ditangani, selain itu diteruskan ke superclass.
        """
        if (
            isinstance(watched, QPushButton)
            and event.type() == QEvent.Type.KeyPress
            and isinstance(event, QKeyEvent)
            and event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter)
        ):
            watched.animateClick()
            return True
        return super().eventFilter(watched, event)


class DashboardPOS(QWidget):
    """Komponen utama (root) yang merakit seluruh bagian UI Dashboard POS.
    
    Menggabungkan sidebar navigasi, area transaksi utama, dan panel 
    samping kanan menggunakan layout dinamis.
    """

    navigation_requested = Signal(str)
    search_requested = Signal(str, str)
    add_to_cart_requested = Signal()
    clear_cart_requested = Signal()
    item_removed = Signal(int)
    item_quantity_changed = Signal(int, int)
    discount_requested = Signal()
    rounding_requested = Signal()
    tip_requested = Signal()
    checkout_requested = Signal()
    payment_amount_changed = Signal(str)
    payment_method_changed = Signal(str)
    
    def __init__(self, user_name: str = "KASIR", user_role: str = "USER", parent: Optional[QWidget] = None) -> None:
        """Menginisialisasi dan merakit seluruh sub-komponen dashboard.
        
        Args:
            user_name: Nama kasir yang sedang login, diteruskan ke TransactionHeader.
            user_role: Role pengguna yang sedang login, diteruskan ke TransactionHeader.
        """
        super().__init__(parent)
        self.setStyleSheet("background-color: #11111B;")
        
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        self.sidebar = Sidebar()
        
        center_widget = QWidget()
        center_layout = QVBoxLayout(center_widget)
        center_layout.setContentsMargins(24, 10, 12, 24)
        center_layout.setSpacing(16)
        
        self.header = TransactionHeader(user_name=user_name, user_role=user_role)
        self.search_panel = ProductSearchPanel()
        self.cart_panel = CartPanel()
        
        center_layout.addWidget(self.header)
        center_layout.addWidget(self.search_panel)
        center_layout.addWidget(self.cart_panel, stretch=1)
        
        right_widget = QWidget()
        right_widget.setFixedWidth(360)
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(12, 24, 24, 24)
        right_layout.setSpacing(16)
        
        self.summary_panel = TransactionSummaryPanel()
        self.payment_panel = PaymentPanel()
        self.action_panel = TransactionActionPanel()
        
        right_layout.addWidget(self.summary_panel)
        right_layout.addWidget(self.payment_panel)
        right_layout.addWidget(self.action_panel)
        
        main_layout.addWidget(self.sidebar)
        main_layout.addWidget(center_widget, stretch=1)
        main_layout.addWidget(right_widget)

        self._connect_signals()
        
        self.shortcut_pay = QShortcut(QKeySequence("Ctrl+B"), self)
        self.shortcut_pay.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        self.shortcut_pay.activated.connect(self._on_shortcut_pay)

    def _connect_signals(self) -> None:
        """Menghubungkan sinyal-sinyal komponen sub-panel ke sinyal publik DashboardPOS."""
        self.sidebar.nav_changed.connect(self.navigation_requested.emit)
        self.search_panel.search_submitted.connect(self.search_requested.emit)
        self.search_panel.add_requested.connect(self.add_to_cart_requested.emit)
        self.cart_panel.clear_cart_requested.connect(self.clear_cart_requested.emit)
        self.cart_panel.item_removed.connect(self.item_removed.emit)
        self.cart_panel.item_quantity_changed.connect(self.item_quantity_changed.emit)
        self.action_panel.discount_clicked.connect(self.discount_requested.emit)
        self.action_panel.rounding_clicked.connect(self.rounding_requested.emit)
        self.action_panel.tip_clicked.connect(self.tip_requested.emit)
        self.action_panel.pay_clicked.connect(self.checkout_requested.emit)
        self.payment_panel.amount_changed.connect(self.payment_amount_changed.emit)
        self.payment_panel.method_changed.connect(self.payment_method_changed.emit)

    def set_user_info(self, user_name: str, user_role: str) -> None:
        """Memperbarui informasi identitas kasir dan level akses pengguna.

        Args:
            user_name: Nama pengguna aktif.
            user_role: Peran akses pengguna.
        """
        self.header.set_user_info(user_name, user_role)

    def _update_cart_tab_order(self) -> None:
        """Mengatur urutan fokus Tab dari tombol Tambah, ke semua input Qty, lalu ke tombol Kosongkan."""
        qty_inputs = self.cart_panel.get_qty_inputs()
        if not qty_inputs:
            QWidget.setTabOrder(self.search_panel.add_btn, self.cart_panel.clear_btn)
            return

        QWidget.setTabOrder(self.search_panel.add_btn, qty_inputs[0])
        for idx in range(len(qty_inputs) - 1):
            QWidget.setTabOrder(qty_inputs[idx], qty_inputs[idx + 1])
        QWidget.setTabOrder(qty_inputs[-1], self.cart_panel.clear_btn)
    
    def set_cart_items(self, items: List[Dict[str, Any]]) -> None:
        """Memperbarui daftar item transaksi yang ditampilkan di keranjang belanja.

        Args:
            items: Daftar dictionary data item transaksi.
        """
        self.cart_panel.set_items(items)
        self._update_cart_tab_order()

    def get_cart_items(self) -> List[Dict[str, Any]]:
        """Mengambil data item yang sedang berada di dalam keranjang belanja.

        Returns:
            Daftar data barang dalam keranjang.
        """
        return self.cart_panel.get_items()

    def update_summary(
        self,
        subtotal: Union[int, float] = 0,
        diskon: Union[int, float] = 0,
        pembulatan: Union[int, float] = 0,
        tip: Union[int, float] = 0,
        total: Union[int, float] = 0,
    ) -> None:
        """Memperbarui seluruh nilai nominal pada ringkasan transaksi.

        Args:
            subtotal: Nilai subtotal barang.
            diskon: Nilai diskon potongan.
            pembulatan: Nilai penyesuaian pembulatan.
            tip: Nilai tip kasir.
            total: Nilai total tagihan akhir.
        """
        self.summary_panel.update_summary(
            subtotal=subtotal,
            diskon=diskon,
            pembulatan=pembulatan,
            tip=tip,
            total=total,
        )

    def get_payment_data(self) -> Dict[str, Any]:
        """Mengambil data isian metode pembayaran dan detail transaksi saat ini.

        Returns:
            Dictionary rincian pembayaran dari form.
        """
        return self.payment_panel.get_payment_data()

    def validate_payment(self) -> tuple[bool, str]:
        """Memvalidasi aturan formulir pembayaran sebelum transaksi dieksekusi.

        Returns:
            Tuple (is_valid, error_message).
        """
        return self.payment_panel.validate_payment()

    def set_change_amount(self, amount: Union[int, float]) -> None:
        """Memperbarui nominal estimasi kembalian customer pada panel pembayaran.

        Args:
            amount: Nilai kembalian yang dihitung.
        """
        self.payment_panel.set_change_amount(amount)

    def set_payment_amount(self, amount: Union[int, float, str]) -> None:
        """Memperbarui teks nominal pembayaran pada panel pembayaran.

        Args:
            amount: Nilai nominal yang akan diisikan.
        """
        self.payment_panel.set_payment_amount(amount)

    def _on_shortcut_pay(self) -> None:
        """Memicu klik tombol Bayar saat shortcut Ctrl+B ditekan."""
        if self.action_panel.btn_bayar.isEnabled():
            self.action_panel.btn_bayar.animateClick()

    def clear_transaction(self) -> None:
        """Mengosongkan keranjang belanja, ringkasan transaksi, dan formulir pembayaran."""
        self.cart_panel.clear_cart()
        self.summary_panel.reset_summary()
        self.payment_panel.clear_form()
        self.search_panel.clear_search()
        self._update_cart_tab_order()
        QTimer.singleShot(0, self.focus_search_input)

    def focus_search_input(self) -> None:
        """Memindahkan fokus keyboard ke input pencarian produk."""
        self.search_panel.search_input.setFocus()
        self.search_panel.search_input.selectAll()

    def showEvent(self, event: QShowEvent) -> None:
        """Memfokuskan kolom pencarian secara otomatis saat halaman tampil pertama kali.

        Args:
            event: Objek event saat widget ditampilkan.
        """
        super().showEvent(event)
        QTimer.singleShot(0, self.focus_search_input)
