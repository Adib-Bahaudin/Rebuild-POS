from PySide6.QtCore import Qt, QSize, Signal, Property, QPropertyAnimation, QEasingCurve, QRect
from PySide6.QtGui import QCursor, QPainter, QIcon, QEnterEvent, QPaintEvent, QIntValidator
from PySide6.QtSvgWidgets import QSvgWidget
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QLineEdit, QPushButton, QComboBox, QTableWidget,
    QHeaderView, QTextEdit, QCheckBox, QStackedWidget, QFrame,
    QTableWidgetItem, QSpinBox
)
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Any, Optional, Union

@dataclass(frozen=True)
class SidebarIconPaths:
    """Menyimpan konfigurasi path ikon sidebar untuk status normal dan hover."""
    normal: Path
    hover: Path

SIDEBAR_ICONS_CONFIG: Dict[str, Dict[str, str]] = {
    "dashboard": {"normal": "assets/icons/Dash_Normal.png", "hover": "assets/icons/Dash_Hover.png"},
    "history": {"normal": "assets/icons/hist_normal.png", "hover": "assets/icons/hist_hover.png"},
    "product": {"normal": "assets/icons/prod_normal.png", "hover": "assets/icons/prod_hover.png"},
    "report": {"normal": "assets/icons/trx_normal.png", "hover": "assets/icons/trx_hover.png"},
    "people": {"normal": "assets/icons/cust_normal.png", "hover": "assets/icons/cust_hover.png"},
    "settings": {"normal": "assets/icons/set_normal.png", "hover": "assets/icons/set_hover.png"},
}

def validate_sidebar_icons(config: Dict[str, Dict[str, str]]) -> List[SidebarIconPaths]:
    """Memeriksa keberadaan file fisik ikon sebelum aplikasi dimuat.
    
    Raises:
        FileNotFoundError: Jika ada path ikon yang tidak ditemukan di disk.
    """
    validated_paths = []
    for key, paths in config.items():
        normal_path = Path(paths["normal"]).resolve()
        hover_path = Path(paths["hover"]).resolve()
        
        if not normal_path.exists() or not normal_path.is_file():
            raise FileNotFoundError(f"GAGAL MEMUAT: Ikon Sidebar (normal) untuk '{key}' tidak ditemukan di {normal_path}")
        if not hover_path.exists() or not hover_path.is_file():
            raise FileNotFoundError(f"GAGAL MEMUAT: Ikon Sidebar (hover) untuk '{key}' tidak ditemukan di {hover_path}")
            
        validated_paths.append(SidebarIconPaths(normal=normal_path, hover=hover_path))
    
    return validated_paths

class CardWidget(QFrame):
    """Widget dasar dengan gaya visual card.
    
    Digunakan sebagai kontainer berlatar belakang gelap dengan border tipis 
    untuk mengelompokkan elemen-elemen UI agar menyerupai referensi desain.
    """
    
    def __init__(self, parent=None):
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

class SidebarButton(QPushButton):
    """Tombol sidebar kustom dengan dukungan animasi transisi ikon cross-fade."""
    
    def __init__(self, icon_paths: SidebarIconPaths, is_active: bool = False, parent=None):
        super().__init__(parent)
        self.setFixedSize(48, 48)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.is_active = is_active
        
        self._normal_icon = QIcon(str(icon_paths.normal))
        self._hover_icon = QIcon(str(icon_paths.hover))
        
        self._hover_progress: float = 1.0 if is_active else 0.0
        
        self._animation = QPropertyAnimation(self, b"hoverProgress", self)
        self._animation.setDuration(150)
        self._animation.setEasingCurve(QEasingCurve.Type.InOutQuad)

    def get_hover_progress(self) -> float:
        return self._hover_progress

    def set_hover_progress(self, value: float) -> None:
        self._hover_progress = value
        self.update()

    hoverProgress = Property(float, get_hover_progress, set_hover_progress)

    def enterEvent(self, event: QEnterEvent) -> None:
        if not self.is_active:
            self._animation.stop()
            self._animation.setStartValue(self._hover_progress)
            self._animation.setEndValue(1.0)
            self._animation.start()
            self.setCursor(Qt.CursorShape.PointingHandCursor)
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:
        if not self.is_active:
            self._animation.stop()
            self._animation.setStartValue(self._hover_progress)
            self._animation.setEndValue(0.0)
            self._animation.start()
        super().leaveEvent(event)

    def paintEvent(self, event: QPaintEvent) -> None:
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        
        icon_size = QSize(24, 24)
        dpr = self.devicePixelRatioF()
        target_pixel_size = QSize(int(icon_size.width() * dpr), int(icon_size.height() * dpr))
        
        x_pos = (self.width() - icon_size.width()) // 2
        y_pos = (self.height() - icon_size.height()) // 2
        target_rect = QRect(x_pos, y_pos, icon_size.width(), icon_size.height())

        if self._hover_progress < 1.0:
            normal_pixmap = self._normal_icon.pixmap(target_pixel_size)
            normal_pixmap.setDevicePixelRatio(dpr)
            painter.setOpacity(1.0 - self._hover_progress)
            painter.drawPixmap(target_rect, normal_pixmap)

        if self._hover_progress > 0.0:
            hover_pixmap = self._hover_icon.pixmap(target_pixel_size)
            hover_pixmap.setDevicePixelRatio(dpr)
            painter.setOpacity(self._hover_progress)
            painter.drawPixmap(target_rect, hover_pixmap)

        painter.end()


class Sidebar(QFrame):
    """Area navigasi di sisi kiri dashboard.
    
    Menampilkan ikon navigasi vertikal tanpa label teks untuk mempertahankan 
    tampilan yang ringkas (compact) sesuai gambar referensi.
    """

    nav_changed = Signal(str)
    
    def __init__(self, parent=None):
        """Menginisialisasi sidebar dan menyusun ikon navigasi."""
        super().__init__(parent)
        self.setFixedWidth(64)
        self.setStyleSheet(
            """
            Sidebar {
                background-color: #11111B;
                border-right: 1px solid #313244;
            }
            QPushButton {
                background-color: transparent;
                border: none;
                padding: 12px 0;
                border-radius: 8px;
            }
            QPushButton:hover {
                background-color: #313244;
            }
            QPushButton[active="true"] {
                background-color: rgba(46, 204, 113, 0.15);
                border-left: 3px solid #2ECC71;
                border-radius: 8px;
            }
            """
        )
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 16, 8, 16)
        layout.setSpacing(12)
        
        validated_icons = validate_sidebar_icons(SIDEBAR_ICONS_CONFIG)
        self.nav_buttons: Dict[str, SidebarButton] = {}
        
        for i, (key, paths) in enumerate(SIDEBAR_ICONS_CONFIG.items()):
            icon_paths = validated_icons[i]
            is_active = (i == 0)
            
            btn = SidebarButton(icon_paths, is_active=is_active)
            if is_active:
                btn.setProperty("active", "true")
            
            btn.clicked.connect(lambda checked=False, k=key: self._on_button_clicked(k))
            self.nav_buttons[key] = btn
            layout.addWidget(btn)
            
        layout.addStretch()

    def _on_button_clicked(self, key: str) -> None:
        """Menangani klik tombol navigasi dan memancarkan sinyal menu terpilih.

        Args:
            key: Kunci pengenal navigasi yang diklik.
        """
        self.set_active_nav(key)
        self.nav_changed.emit(key)

    def set_active_nav(self, active_key: str) -> None:
        """Mengatur tombol sidebar aktif berdasarkan kunci menu.

        Args:
            active_key: Kunci menu navigasi yang akan diaktifkan.
        """
        for key, btn in self.nav_buttons.items():
            is_target = (key == active_key)
            btn.is_active = is_target
            btn.setProperty("active", "true" if is_target else "false")
            btn.set_hover_progress(1.0 if is_target else 0.0)
            btn.style().unpolish(btn)
            btn.style().polish(btn)


class TransactionHeader(QWidget):
    """Bagian header untuk area transaksi utama.
    
    Menampilkan judul halaman, identitas kasir, dan role akses pengguna.
    """
    
    def __init__(self, user_name: str = "KASIR", user_role: str = "USER", parent=None):
        """Menginisialisasi elemen header transaksi.
        
        Args:
            user_name: Nama kasir yang sedang login.
            user_role: Role / level akses pengguna yang sedang login.
        """
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        kasir_icon = QSvgWidget("assets/icons/kasir_100.svg")
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
    
    def __init__(self, parent=None):
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
            """
        )
        
        self.category_combo = QComboBox()
        self.category_combo.addItems(["Semua Produk", "Produk Satuan", "Produk Paket", "Jasa"])
        self.category_combo.setFixedWidth(200)
        self.category_combo.setStyleSheet(
            """
            QComboBox {
                background-color: #11111B;
                border: 1px solid #313244;
                border-radius: 6px;
                padding: 10px;
                color: #CDD6F4;
            }
            QComboBox::drop-down {
                subcontrol-origin: padding;
                subcontrol-position: top right;
                width: 24px;
                border-left: 1px solid #313244;
            }
            QComboBox::down-arrow {
                image: url(assets/icons/icon_down.svg);
                width: 12px;
                height: 12px;
            }
            QComboBox QAbstractItemView {
                background-color: #11111B;
                color: white;
                border: 1px solid #313244;
                selection-background-color: #0078D7;
            }
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
            }
            QPushButton:hover {
                background-color: #27AE60;
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

        self.btn_minus.clicked.connect(self._on_minus_clicked)
        self.btn_plus.clicked.connect(self._on_plus_clicked)
        self.qty_spin.editingFinished.connect(self._on_editing_finished)

        layout.addWidget(self.btn_minus)
        layout.addWidget(self.qty_spin)
        layout.addWidget(self.btn_plus)

    def _on_minus_clicked(self) -> None:
        """Menurunkan nilai kuantitas sebanyak satu unit dan memancarkan sinyal."""
        new_val = self.qty_spin.value() - 1
        self.quantity_changed.emit(new_val)

    def _on_plus_clicked(self) -> None:
        """Menaikkan nilai kuantitas sebanyak satu unit dan memancarkan sinyal."""
        new_val = self.qty_spin.value() + 1
        self.quantity_changed.emit(new_val)

    def _on_editing_finished(self) -> None:
        """Memancarkan sinyal kuantitas baru setelah kasir selesai mengetikkan angka."""
        self.quantity_changed.emit(self.qty_spin.value())

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
        self.qty_spin.setValue(int(value))


class CartPanel(CardWidget):
    """Panel keranjang belanja yang menampilkan tabel transaksi.
    
    Menampilkan kolom data produk, status kosong (empty state), dan tombol kontrol.
    """

    clear_cart_requested = Signal()
    item_removed = Signal(int)
    item_quantity_changed = Signal(int, int)
    
    def __init__(self, parent=None):
        """Menginisialisasi tabel keranjang belanja dan status antarmuka kosong."""
        super().__init__(parent)
        self._cart_items: List[Dict[str, Any]] = []
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        
        self.table = QTableWidget(0, 7)
        self.table.setHorizontalHeaderLabels(
            ["SKU", "Produk", "Tipe", "Harga", "Qty", "Subtotal", "Aksi"]
        )
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.table.setColumnWidth(4, 120)
        self.table.setColumnWidth(6, 80)
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
            }
            QPushButton:hover {
                background-color: #313244;
            }
            """
        )
        self.clear_btn.clicked.connect(self.clear_cart_requested.emit)
        bottom_layout.addWidget(self.clear_btn)
        
        layout.addWidget(self.stacked_widget)
        layout.addLayout(bottom_layout)

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

        self.table.setRowCount(len(items))
        for row_idx, item in enumerate(items):
            item_id = item.get("id", row_idx)

            sku_item = QTableWidgetItem(str(item.get("sku", "")))
            sku_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            sku_item.setFlags(sku_item.flags() & ~Qt.ItemFlag.ItemIsEditable)

            name_item = QTableWidgetItem(str(item.get("name", "")))
            name_item.setFlags(name_item.flags() & ~Qt.ItemFlag.ItemIsEditable)

            type_item = QTableWidgetItem(str(item.get("item_type", "Produk")))
            type_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            type_item.setFlags(type_item.flags() & ~Qt.ItemFlag.ItemIsEditable)

            price_val = item.get("price", 0)
            price_text = f"Rp {int(price_val):,}".replace(",", ".")
            price_item = QTableWidgetItem(price_text)
            price_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            price_item.setFlags(price_item.flags() & ~Qt.ItemFlag.ItemIsEditable)

            qty_val = int(item.get("qty", 1))
            qty_control = QuantityControlWidget(initial_qty=qty_val)
            qty_control.quantity_changed.connect(
                lambda val, idx=item_id: self.item_quantity_changed.emit(idx, val)
            )

            subtotal_val = item.get("subtotal", price_val * qty_val)
            subtotal_text = f"Rp {int(subtotal_val):,}".replace(",", ".")
            subtotal_item = QTableWidgetItem(subtotal_text)
            subtotal_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            subtotal_item.setFlags(subtotal_item.flags() & ~Qt.ItemFlag.ItemIsEditable)

            self.table.setItem(row_idx, 0, sku_item)
            self.table.setItem(row_idx, 1, name_item)
            self.table.setItem(row_idx, 2, type_item)
            self.table.setItem(row_idx, 3, price_item)
            self.table.setCellWidget(row_idx, 4, qty_control)
            self.table.setItem(row_idx, 5, subtotal_item)

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
            del_btn.clicked.connect(lambda checked=False, idx=item_id: self.item_removed.emit(idx))
            action_layout.addWidget(del_btn)
            self.table.setCellWidget(row_idx, 6, action_widget)

        self.stacked_widget.setCurrentIndex(1)

    def clear_cart(self) -> None:
        """Mengosongkan isi tabel keranjang belanja dan menampilkan label status kosong."""
        self._cart_items = []
        self.table.setRowCount(0)
        self.stacked_widget.setCurrentIndex(0)

    def get_items(self) -> List[Dict[str, Any]]:
        """Mengembalikan salinan data item yang saat ini ada di keranjang belanja.

        Returns:
            Daftar dictionary item transaksi.
        """
        return list(self._cart_items)


class TransactionSummaryPanel(CardWidget):
    """Panel ringkasan nominal transaksi penjualan.
    
    Menampilkan rincian angka seperti subtotal, diskon, dan total tagihan akhir.
    """
    
    def __init__(self, parent=None):
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
            self.value_labels["Subtotal"].setText(f"Rp {int(subtotal):,}".replace(",", "."))
        if "Diskon" in self.value_labels:
            self.value_labels["Diskon"].setText(f"Rp {int(diskon):,}".replace(",", "."))
        if "Pembulatan" in self.value_labels:
            self.value_labels["Pembulatan"].setText(f"Rp {int(pembulatan):,}".replace(",", "."))
        if "Tip / Bonus" in self.value_labels:
            self.value_labels["Tip / Bonus"].setText(f"Rp {int(tip):,}".replace(",", "."))
        self.total_val.setText(f"Rp {int(total):,}".replace(",", "."))

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
    
    def __init__(self, parent=None):
        """Menginisialisasi form pembayaran."""
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        
        common_input_style = """
            QWidget {
                background-color: #11111B;
                border: 1px solid #313244;
                border-radius: 6px;
                padding: 3px;
                color: #CDD6F4;
                font-size: 12px;
            }
            QComboBox::drop-down {
                subcontrol-origin: padding;
                subcontrol-position: top right;
                width: 24px;
                border-left: 1px solid #313244;
            }
            QComboBox::down-arrow {
                image: url(assets/icons/icon_down.svg);
                width: 10px;
                height: 10px;
            }
        """
        
        method_layout = QHBoxLayout()
        method_lbl = QLabel("Metode Bayar")
        method_lbl.setFixedWidth(100)
        method_lbl.setStyleSheet("color: #CDD6F4; font-size: 12px; background-color: transparent;")
        self.method_combo = QComboBox()
        self.method_combo.addItems(["Tunai", "QRIS", "Transfer"])
        self.method_combo.setStyleSheet(common_input_style)
        self.method_combo.currentTextChanged.connect(self.method_changed.emit)
        method_layout.addWidget(method_lbl)
        method_layout.addWidget(self.method_combo)
        
        amount_layout = QHBoxLayout()
        amount_lbl = QLabel("Nominal Bayar")
        amount_lbl.setFixedWidth(100)
        amount_lbl.setStyleSheet("color: #CDD6F4; font-size: 12px; background-color: transparent;")
        self.amount_input = QLineEdit()
        self.amount_input.setPlaceholderText("Rp. ")
        self.amount_input.setValidator(QIntValidator())
        self.amount_input.setStyleSheet(common_input_style)
        self.amount_input.textChanged.connect(self.amount_changed.emit)
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
        self.note_input.setPlaceholderText("tulis informasi disini")
        self.note_input.setStyleSheet(common_input_style)
        self.change_lbl = QLabel("Kembalian: Rp 0")
        self.change_lbl.setStyleSheet("color: #CDD6F4; font-size: 14px; font-weight: bold; background-color: transparent;")
        self.print_check = QCheckBox("Cetak Nota Transaksi")
        self.print_check.setStyleSheet("color: #A6ADC8; font-size: 12px; background-color: transparent;")
        note_layout.addWidget(note_lbl)
        note_layout.addWidget(self.note_input)
        note_layout.addWidget(self.change_lbl)
        note_layout.addWidget(self.print_check)
        
        layout.addLayout(method_layout)
        layout.addLayout(amount_layout)
        layout.addLayout(cust_layout)
        layout.addLayout(note_layout)

    def get_payment_data(self) -> Dict[str, Any]:
        """Mengambil seluruh data form input pembayaran saat ini.

        Returns:
            Dictionary rincian metode pembayaran, nominal yang diinput,
            nama pelanggan, catatan transaksi, dan status opsi cetak nota.
        """
        raw_text = self.amount_input.text().replace("Rp", "").replace(".", "").replace(",", "").strip()
        parsed_amount = int(raw_text) if raw_text.isdigit() else 0
        return {
            "payment_method": self.method_combo.currentText(),
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
        formatted = f"Rp {int(amount):,}".replace(",", ".")
        self.change_lbl.setText(f"Kembalian: {formatted}")

    def clear_form(self) -> None:
        """Mengosongkan isian formulir pembayaran dan mengembalikan ke status awal."""
        self.method_combo.setCurrentIndex(0)
        self.amount_input.clear()
        self.cust_input.clear()
        self.note_input.clear()
        self.change_lbl.setText("Kembalian: Rp 0")
        self.print_check.setChecked(False)

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
    
    def __init__(self, parent=None):
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
            }
            QPushButton::hover {
                background-color: %s;
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
    
    def __init__(self, user_name: str = "KASIR", user_role: str = "USER", parent=None):
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

    def set_user_info(self, user_name: str, user_role: str) -> None:
        """Memperbarui informasi identitas kasir dan level akses pengguna.

        Args:
            user_name: Nama pengguna aktif.
            user_role: Peran akses pengguna.
        """
        self.header.set_user_info(user_name, user_role)

    def set_cart_items(self, items: List[Dict[str, Any]]) -> None:
        """Memperbarui daftar item transaksi yang ditampilkan di keranjang belanja.

        Args:
            items: Daftar dictionary data item transaksi.
        """
        self.cart_panel.set_items(items)

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

    def set_change_amount(self, amount: Union[int, float]) -> None:
        """Memperbarui nominal estimasi kembalian customer pada panel pembayaran.

        Args:
            amount: Nilai kembalian yang dihitung.
        """
        self.payment_panel.set_change_amount(amount)

    def clear_transaction(self) -> None:
        """Mengosongkan keranjang belanja, ringkasan transaksi, dan formulir pembayaran."""
        self.cart_panel.clear_cart()
        self.summary_panel.reset_summary()
        self.payment_panel.clear_form()
        self.search_panel.clear_search()
