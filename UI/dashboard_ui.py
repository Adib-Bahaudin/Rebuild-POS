from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QCursor
from PySide6.QtSvgWidgets import QSvgWidget
from PySide6.QtWidgets import ( QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QLineEdit, QPushButton, QComboBox, QTableWidget, QHeaderView, QTextEdit, QCheckBox, QStackedWidget, QFrame
)
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List
from PySide6.QtCore import Property, QPropertyAnimation, QEasingCurve, QRect
from PySide6.QtGui import QPainter, QIcon, QEnterEvent, QPaintEvent

@dataclass(frozen=True)
class SidebarIconPaths:
    """Menyimpan konfigurasi path ikon sidebar untuk status normal dan hover."""
    normal: Path
    hover: Path

SIDEBAR_ICONS_CONFIG: Dict[str, Dict[str, str]] = {
    "dashboard": {"normal": "assets/icons/Dash_Normal.png", "hover": "assets/icons/Dash_Hover.png"},
    "transaction": {"normal": "assets/icons/trx_normal.png", "hover": "assets/icons/trx_hover.png"},
    "product": {"normal": "assets/icons/prod_normal.png", "hover": "assets/icons/prod_hover.png"},
    "history": {"normal": "assets/icons/hist_normal.png", "hover": "assets/icons/hist_hover.png"},
    "customer": {"normal": "assets/icons/cust_normal.png", "hover": "assets/icons/cust_hover.png"},
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
        
        for i, icon_paths in enumerate(validated_icons):
            is_active = (i == 0)
            
            btn = SidebarButton(icon_paths, is_active=is_active)
            if is_active:
                btn.setProperty("active", "true")
                
            layout.addWidget(btn)
            
        layout.addStretch()


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

        title_label = QLabel("TRANSAKSI PENJUALAN")
        title_label.setStyleSheet("font-size: 20px; font-weight: bold; color: #CDD6F4;")
        
        cashier_badge = QLabel(f"NAMA KASIR : {user_name.upper()}")
        cashier_badge.setStyleSheet(
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
        
        role_badge = QLabel(user_role.upper())
        role_badge.setStyleSheet(
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
        title_layout.addWidget(title_label)
        
        badge_layout = QHBoxLayout()
        badge_layout.addWidget(cashier_badge)
        badge_layout.addWidget(role_badge)
        badge_layout.addStretch()
        
        title_layout.addLayout(badge_layout)
        
        layout.addLayout(title_layout)
        layout.addStretch()


class ProductSearchPanel(CardWidget):
    """Panel pencarian produk di atas keranjang belanja.
    
    Berisi field input pencarian, dropdown kategori, dan tombol tambah.
    """
    
    def __init__(self, parent=None):
        """Menginisialisasi form pencarian produk."""
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(8)
        
        input_layout = QHBoxLayout()
        input_layout.setSpacing(12)
        
        search_input = QLineEdit()
        search_input.setPlaceholderText("Ketik nama produk / SKU lalu tekan Enter...")
        search_input.setStyleSheet(
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
        
        category_combo = QComboBox()
        category_combo.addItems(["Semua Produk", "Produk Satuan", "Produk Paket", "Jasa"])
        category_combo.setFixedWidth(200)
        category_combo.setStyleSheet(
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
        
        add_btn = QPushButton("Tambah ke Keranjang")
        add_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        add_btn.setStyleSheet(
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
        
        input_layout.addWidget(search_input, stretch=1)
        input_layout.addWidget(category_combo)
        input_layout.addWidget(add_btn)
        
        helper_label = QLabel("Cari produk berdasarkan SKU atau nama produk.")
        helper_label.setStyleSheet("color: #7F849C; font-size: 11px; background-color: transparent;")
        
        layout.addLayout(input_layout)
        layout.addWidget(helper_label)


class CartPanel(CardWidget):
    """Panel keranjang belanja yang menampilkan tabel transaksi.
    
    Menampilkan kolom data produk, status kosong (empty state), dan tombol kontrol.
    """
    
    def __init__(self, parent=None):
        """Menginisialisasi tabel keranjang belanja dan status antarmuka kosong."""
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        
        self.table = QTableWidget(0, 7)
        self.table.setHorizontalHeaderLabels(
            ["SKU", "Produk", "Tipe", "Harga", "Qty", "Subtotal", "Aksi"]
        )
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
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
        
        clear_btn = QPushButton("Kosongkan Keranjang")
        clear_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        clear_btn.setStyleSheet(
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
        bottom_layout.addWidget(clear_btn)
        
        layout.addWidget(self.stacked_widget)
        layout.addLayout(bottom_layout)


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
            
        layout.addSpacing(8)
        
        total_lbl = QLabel("Total Tagihan")
        total_lbl.setStyleSheet("color: #A6ADC8; font-size: 12px; background-color: transparent;")
        
        total_val = QLabel("Rp 0")
        total_val.setStyleSheet("color: #2ECC71; font-size: 24px; font-weight: bold; padding-left: 3; padding-bottom: 3")
        total_val.setAlignment(Qt.AlignmentFlag.AlignLeft)
        
        layout.addWidget(total_lbl)
        layout.addWidget(total_val)


class PaymentPanel(CardWidget):
    """Panel form input detail pembayaran.
    
    Menyediakan field untuk metode pembayaran, nominal, data customer, 
    catatan, estimasi kembalian, dan preferensi pencetakan nota.
    """
    
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
        method_combo = QComboBox()
        method_combo.addItems(["Tunai", "QRIS", "Transfer"])
        method_combo.setStyleSheet(common_input_style)
        method_layout.addWidget(method_lbl)
        method_layout.addWidget(method_combo)
        
        amount_layout = QHBoxLayout()
        amount_lbl = QLabel("Nominal Bayar")
        amount_lbl.setFixedWidth(100)
        amount_lbl.setStyleSheet("color: #CDD6F4; font-size: 12px; background-color: transparent;")
        amount_input = QLineEdit()
        amount_input.setPlaceholderText("Rp. ")
        amount_input.setStyleSheet(common_input_style)
        amount_layout.addWidget(amount_lbl)
        amount_layout.addWidget(amount_input)
        
        cust_layout = QHBoxLayout()
        cust_lbl = QLabel("Nama Customer")
        cust_lbl.setFixedWidth(100)
        cust_lbl.setStyleSheet("color: #CDD6F4; font-size: 12px; background-color: transparent;")
        cust_input = QLineEdit()
        cust_input.setPlaceholderText("Opsional, misal: Pelanggan ...")
        cust_input.setStyleSheet(common_input_style)
        cust_layout.addWidget(cust_lbl)
        cust_layout.addWidget(cust_input)
        
        note_layout = QVBoxLayout()
        note_lbl = QLabel("Catatan Kasir")
        note_lbl.setStyleSheet("color: #CDD6F4; font-size: 12px; background-color: transparent;")
        note_input = QTextEdit()
        note_input.setPlaceholderText("tulis informasi disini")
        note_input.setStyleSheet(common_input_style)
        change_lbl = QLabel("Kembalian: Rp 0")
        change_lbl.setStyleSheet("color: #CDD6F4; font-size: 14px; font-weight: bold; background-color: transparent;")
        print_check = QCheckBox("Cetak Nota Transaksi")
        print_check.setStyleSheet("color: #A6ADC8; font-size: 12px; background-color: transparent;")
        note_layout.addWidget(note_lbl)
        note_layout.addWidget(note_input)
        note_layout.addWidget(change_lbl)
        note_layout.addWidget(print_check)
        
        layout.addLayout(method_layout)
        layout.addLayout(amount_layout)
        layout.addLayout(cust_layout)
        layout.addLayout(note_layout)


class TransactionActionPanel(CardWidget):
    """Panel aksi utama untuk eksekusi akhir transaksi.
    
    Menampilkan grid tombol aksi pembayaran dan modifikasi transaksi.
    """
    
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
        
        btn_diskon = QPushButton("Diskon")
        btn_diskon.setStyleSheet(btn_style_template % ("#F39C12", "#11111B", "#B7770D"))
        
        btn_pembulatan = QPushButton("Pembulatan")
        btn_pembulatan.setStyleSheet(btn_style_template % ("#3498DB", "#FFFFFF", "#1E6FA5"))
        
        btn_tip = QPushButton("Tip / Bonus")
        btn_tip.setStyleSheet(btn_style_template % ("#1ABC9C", "#FFFFFF", "#128F76"))
        
        btn_bayar = QPushButton("Bayar")
        btn_bayar.setStyleSheet(btn_style_template % ("#2ECC71", "#11111B", "#1E9950"))
        
        cursors = [btn_diskon, btn_pembulatan, btn_tip, btn_bayar]
        for btn in cursors:
            btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
            
        layout.addWidget(btn_diskon, 0, 0)
        layout.addWidget(btn_pembulatan, 0, 1)
        layout.addWidget(btn_tip, 1, 0)
        layout.addWidget(btn_bayar, 1, 1)


class DashboardPOS(QWidget):
    """Komponen utama (root) yang merakit seluruh bagian UI Dashboard POS.
    
    Menggabungkan sidebar navigasi, area transaksi utama, dan panel 
    samping kanan menggunakan layout dinamis.
    """
    
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
