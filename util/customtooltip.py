"""Modul komponen tooltip kustom modern dengan animasi halus untuk PySide6."""

from dataclasses import dataclass
from enum import StrEnum

from PySide6.QtCore import (
    QEasingCurve,
    QEvent,
    QObject,
    QParallelAnimationGroup,
    QPoint,
    QPointF,
    QPropertyAnimation,
    QRectF,
    QSize,
    Qt,
    QTimer,
)
from PySide6.QtGui import (
    QBrush,
    QColor,
    QFont,
    QFontMetrics,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPaintEvent,
    QPen,
    QTextOption,
)
from PySide6.QtWidgets import QWidget

_SHADOW_PAD: int = 10
_ARROW_SIZE: int = 6
_ACCENT_WIDTH: int = 3
_ACCENT_GAP: int = 8
_PAD_X: int = 12
_PAD_Y: int = 8
_SLIDE_OFFSET: int = 8
_TARGET_GAP: int = 6


class TooltipPosition(StrEnum):
    """Menentukan posisi kemunculan tooltip relatif terhadap widget target."""

    RIGHT = "right"
    LEFT = "left"
    TOP = "top"
    BOTTOM = "bottom"


@dataclass(frozen=True)
class TooltipStyle:
    """Menyimpan konfigurasi tampilan visual dan warna tooltip kustom.

    Attributes:
        bg_top: Kode warna hex bagian atas gradasi latar tooltip.
        bg_bottom: Kode warna hex bagian bawah gradasi latar tooltip.
        border_color: Kode warna hex garis tepi tooltip.
        accent_color: Kode warna hex indikator aksen vertikal di sisi kiri teks.
        text_color: Kode warna hex teks utama tooltip.
        border_radius: Radius lengkungan sudut tooltip dalam piksel.
        delay_ms: Jeda waktu dalam milidetik sebelum tooltip muncul saat hover.
    """

    bg_top: str = "#252638"
    bg_bottom: str = "#181926"
    border_color: str = "#3E4158"
    accent_color: str = "#2ECC71"
    text_color: str = "#ECEFF4"
    border_radius: int = 8
    delay_ms: int = 120


class CustomTooltip(QWidget):
    """Widget tooltip mengambang kustom dengan panah penunjuk dan animasi fade-slide."""

    def __init__(
        self,
        text: str,
        position: TooltipPosition = TooltipPosition.RIGHT,
        style: TooltipStyle | None = None,
    ) -> None:
        """Menginisialisasi widget tooltip dengan teks, posisi, dan tema tertentu.

        Args:
            text: Teks label yang ditampilkan pada tooltip.
            position: Arah kemunculan tooltip terhadap widget target.
            style: Konfigurasi tema visual opsional.
        """
        super().__init__(None)
        self._text: str = text
        self._position: TooltipPosition = position
        self._style: TooltipStyle = style if style is not None else TooltipStyle()
        self._is_hiding: bool = False

        self._font: QFont = QFont("Segoe UI")
        self._font.setPixelSize(13)
        self._font.setWeight(QFont.Weight.DemiBold)

        self.setWindowFlags(
            Qt.WindowType.ToolTip
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.WindowTransparentForInput
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)

        opacity_anim = QPropertyAnimation(self, b"windowOpacity", self)
        pos_anim = QPropertyAnimation(self, b"pos", self)
        self._animations: tuple[QPropertyAnimation, QPropertyAnimation] = (
            opacity_anim,
            pos_anim,
        )

        self._anim_group: QParallelAnimationGroup = QParallelAnimationGroup(self)
        self._anim_group.addAnimation(opacity_anim)
        self._anim_group.addAnimation(pos_anim)
        self._anim_group.finished.connect(self._on_animation_finished)

        self.resize(self.sizeHint())

    def set_text(self, text: str) -> None:
        """Memperbarui teks tooltip dan menyesuaikan ulang dimensinya.

        Args:
            text: Teks baru yang akan ditampilkan.
        """
        self._text = text
        self.resize(self.sizeHint())
        self.update()

    def sizeHint(self) -> QSize:
        """Menghitung ukuran total ideal widget termasuk ruang panah dan bayangan.

        Returns:
            Objek QSize berisi lebar dan tinggi total tooltip.
        """
        metrics = QFontMetrics(self._font)
        text_width = metrics.horizontalAdvance(self._text)
        text_height = metrics.height()

        bubble_w = (_PAD_X * 2) + _ACCENT_WIDTH + _ACCENT_GAP + text_width
        bubble_h = max(34, text_height + (_PAD_Y * 2))

        if self._position in (TooltipPosition.RIGHT, TooltipPosition.LEFT):
            return QSize(
                bubble_w + (_SHADOW_PAD * 2) + _ARROW_SIZE,
                bubble_h + (_SHADOW_PAD * 2),
            )

        return QSize(
            bubble_w + (_SHADOW_PAD * 2),
            bubble_h + (_SHADOW_PAD * 2) + _ARROW_SIZE,
        )

    def show_for_widget(self, target: QWidget) -> None:
        """Menampilkan tooltip di sekitar widget target dengan animasi masuk.

        Args:
            target: Widget acuan tempat kursor sedang berada.
        """
        self._is_hiding = False
        self._anim_group.stop()
        self.resize(self.sizeHint())

        end_pos = self._calculate_position(target)
        start_pos = self._get_slide_start(end_pos)

        opacity_anim, pos_anim = self._animations
        start_opacity = self.windowOpacity() if self.isVisible() else 0.0

        opacity_anim.setDuration(160)
        opacity_anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        opacity_anim.setStartValue(start_opacity)
        opacity_anim.setEndValue(1.0)

        pos_anim.setDuration(160)
        pos_anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        pos_anim.setStartValue(start_pos)
        pos_anim.setEndValue(end_pos)

        self.move(start_pos)
        if not self.isVisible():
            self.setWindowOpacity(0.0)
            self.show()

        self._anim_group.start()

    def hide_animated(self) -> None:
        """Menyembunyikan tooltip secara halus menggunakan animasi fade-out."""
        if not self.isVisible() or self._is_hiding:
            return

        self._is_hiding = True
        self._anim_group.stop()

        opacity_anim, pos_anim = self._animations
        current_pos = self.pos()

        opacity_anim.setDuration(110)
        opacity_anim.setEasingCurve(QEasingCurve.Type.InCubic)
        opacity_anim.setStartValue(self.windowOpacity())
        opacity_anim.setEndValue(0.0)

        pos_anim.setDuration(110)
        pos_anim.setEasingCurve(QEasingCurve.Type.InCubic)
        pos_anim.setStartValue(current_pos)
        pos_anim.setEndValue(current_pos)

        self._anim_group.start()

    def _on_animation_finished(self) -> None:
        """Menutup tampilan widget setelah animasi keluar selesai dijalankan."""
        if self._is_hiding:
            self.hide()
            self._is_hiding = False

    def _get_slide_start(self, end_pos: QPoint) -> QPoint:
        """Menghitung titik awal pergeseran animasi berdasarkan arah tooltip.

        Args:
            end_pos: Koordinat akhir tooltip saat berhenti.

        Returns:
            Koordinat awal sebelum animasi slide dijalankan.
        """
        offsets: dict[TooltipPosition, QPoint] = {
            TooltipPosition.RIGHT: QPoint(-_SLIDE_OFFSET, 0),
            TooltipPosition.LEFT: QPoint(_SLIDE_OFFSET, 0),
            TooltipPosition.TOP: QPoint(0, _SLIDE_OFFSET),
            TooltipPosition.BOTTOM: QPoint(0, -_SLIDE_OFFSET),
        }
        return end_pos + offsets[self._position]

    def _calculate_position(self, target: QWidget) -> QPoint:
        """Menghitung koordinat global tooltip agar tepat menunjuk tengah widget.

        Args:
            target: Widget referensi untuk penempatan tooltip.

        Returns:
            Koordinat global QPoint yang aman di dalam batas layar.
        """
        global_pos = target.mapToGlobal(QPoint(0, 0))
        target_w = target.width()
        target_h = target.height()
        tip_w = self.width()
        tip_h = self.height()

        if self._position == TooltipPosition.RIGHT:
            pos_x = global_pos.x() + target_w + _TARGET_GAP - _SHADOW_PAD
            pos_y = global_pos.y() + (target_h - tip_h) // 2
        elif self._position == TooltipPosition.LEFT:
            pos_x = global_pos.x() - _TARGET_GAP - tip_w + _SHADOW_PAD
            pos_y = global_pos.y() + (target_h - tip_h) // 2
        elif self._position == TooltipPosition.TOP:
            pos_x = global_pos.x() + (target_w - tip_w) // 2
            pos_y = global_pos.y() - _TARGET_GAP - tip_h + _SHADOW_PAD
        else:
            pos_x = global_pos.x() + (target_w - tip_w) // 2
            pos_y = global_pos.y() + target_h + _TARGET_GAP - _SHADOW_PAD

        screen = target.screen()
        if screen is not None:
            bounds = screen.availableGeometry()
            pos_x = max(bounds.left(), min(pos_x, bounds.right() - tip_w))
            pos_y = max(bounds.top(), min(pos_y, bounds.bottom() - tip_h))

        return QPoint(pos_x, pos_y)

    def _get_bubble_rect(self) -> QRectF:
        """Menghitung area persegi utama badan tooltip tanpa panah dan bayangan.

        Returns:
            Area QRectF untuk bagian badan utama tooltip.
        """
        left = float(_SHADOW_PAD)
        top = float(_SHADOW_PAD)
        width = float(self.width() - (_SHADOW_PAD * 2))
        height = float(self.height() - (_SHADOW_PAD * 2))

        if self._position == TooltipPosition.RIGHT:
            left += float(_ARROW_SIZE)
            width -= float(_ARROW_SIZE)
        elif self._position == TooltipPosition.LEFT:
            width -= float(_ARROW_SIZE)
        elif self._position == TooltipPosition.TOP:
            height -= float(_ARROW_SIZE)
        elif self._position == TooltipPosition.BOTTOM:
            top += float(_ARROW_SIZE)
            height -= float(_ARROW_SIZE)

        return QRectF(left, top, width, height)

    def _build_arrow_path(self, bubble_rect: QRectF) -> QPainterPath:
        """Membuat jalur segitiga panah penunjuk sesuai posisi tooltip.

        Args:
            bubble_rect: Area badan utama tooltip sebagai acuan tepi panah.

        Returns:
            Objek QPainterPath berisi poligon segitiga panah.
        """
        path = QPainterPath()
        arrow = float(_ARROW_SIZE)
        mid_x = bubble_rect.center().x()
        mid_y = bubble_rect.center().y()

        if self._position == TooltipPosition.RIGHT:
            path.moveTo(QPointF(bubble_rect.left() - arrow, mid_y))
            path.lineTo(QPointF(bubble_rect.left() + 1.5, mid_y - arrow))
            path.lineTo(QPointF(bubble_rect.left() + 1.5, mid_y + arrow))
        elif self._position == TooltipPosition.LEFT:
            path.moveTo(QPointF(bubble_rect.right() + arrow, mid_y))
            path.lineTo(QPointF(bubble_rect.right() - 1.5, mid_y - arrow))
            path.lineTo(QPointF(bubble_rect.right() - 1.5, mid_y + arrow))
        elif self._position == TooltipPosition.TOP:
            path.moveTo(QPointF(mid_x, bubble_rect.bottom() + arrow))
            path.lineTo(QPointF(mid_x - arrow, bubble_rect.bottom() - 1.5))
            path.lineTo(QPointF(mid_x + arrow, bubble_rect.bottom() - 1.5))
        else:
            path.moveTo(QPointF(mid_x, bubble_rect.top() - arrow))
            path.lineTo(QPointF(mid_x - arrow, bubble_rect.top() + 1.5))
            path.lineTo(QPointF(mid_x + arrow, bubble_rect.top() + 1.5))

        path.closeSubpath()
        return path

    def _build_shape_path(self, bubble_rect: QRectF) -> QPainterPath:
        """Menggabungkan badan lengkung tooltip dan panah menjadi satu siluet utuh.

        Args:
            bubble_rect: Area persegi badan utama tooltip.

        Returns:
            Objek QPainterPath gabungan yang telah disederhanakan.
        """
        bubble_path = QPainterPath()
        radius = float(self._style.border_radius)
        bubble_path.addRoundedRect(bubble_rect, radius, radius)
        arrow_path = self._build_arrow_path(bubble_rect)
        return bubble_path.united(arrow_path).simplified()

    def _draw_shadow(self, painter: QPainter, shape_path: QPainterPath) -> None:
        """Menggambar bayangan lembut berlapis di belakang siluet tooltip.

        Args:
            painter: Objek QPainter aktif untuk proses rendering.
            shape_path: Siluet jalur tooltip yang akan diberi bayangan.
        """
        painter.save()
        painter.translate(0.0, 2.0)
        painter.setBrush(Qt.BrushStyle.NoBrush)

        for step in range(4, 0, -1):
            shadow_color = QColor(0, 0, 0, 14 * (5 - step))
            shadow_pen = QPen(
                QBrush(shadow_color),
                float(step * 2),
                Qt.PenStyle.SolidLine,
                Qt.PenCapStyle.RoundCap,
                Qt.PenJoinStyle.RoundJoin,
            )
            painter.setPen(shadow_pen)
            painter.drawPath(shape_path)

        painter.restore()

    def paintEvent(self, event: QPaintEvent) -> None:
        """Merender bayangan, latar gradasi, garis tepi, aksen, dan teks tooltip.

        Args:
            event: Objek QPaintEvent dari siklus render Qt.
        """
        event.accept()
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)

        bubble_rect = self._get_bubble_rect()
        shape_path = self._build_shape_path(bubble_rect)

        self._draw_shadow(painter, shape_path)

        gradient = QLinearGradient(bubble_rect.topLeft(), bubble_rect.bottomLeft())
        gradient.setColorAt(0.0, QColor(self._style.bg_top))
        gradient.setColorAt(1.0, QColor(self._style.bg_bottom))

        border_pen = QPen(QBrush(QColor(self._style.border_color)), 1.0)
        painter.setPen(border_pen)
        painter.setBrush(QBrush(gradient))
        painter.drawPath(shape_path)

        accent_rect = QRectF(
            bubble_rect.left() + float(_PAD_X),
            bubble_rect.top() + float(_PAD_Y),
            float(_ACCENT_WIDTH),
            bubble_rect.height() - float(_PAD_Y * 2),
        )
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(QColor(self._style.accent_color)))
        painter.drawRoundedRect(accent_rect, 1.5, 1.5)

        text_left = accent_rect.right() + float(_ACCENT_GAP)
        text_rect = QRectF(
            text_left,
            bubble_rect.top(),
            bubble_rect.right() - text_left - float(_PAD_X),
            bubble_rect.height(),
        )
        text_option = QTextOption(
            Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft
        )
        painter.setFont(self._font)
        painter.setPen(QColor(self._style.text_color))
        painter.drawText(text_rect, self._text, text_option)
        painter.end()


class TooltipController(QObject):
    """Pengendali event hover untuk menampilkan dan menyembunyikan CustomTooltip."""

    def __init__(
        self,
        target: QWidget,
        text: str,
        position: TooltipPosition = TooltipPosition.RIGHT,
        style: TooltipStyle | None = None,
    ) -> None:
        """Menghubungkan filter event hover pada widget target dengan tooltip kustom.

        Args:
            target: Widget yang akan dipasangi tooltip kustom.
            text: Teks yang ditampilkan saat widget di-hover.
            position: Posisi kemunculan tooltip relatif terhadap widget.
            style: Konfigurasi gaya visual opsional.
        """
        super().__init__(target)
        resolved_style = style if style is not None else TooltipStyle()
        self._target: QWidget = target
        self._tooltip: CustomTooltip = CustomTooltip(text, position, resolved_style)

        self._delay_timer: QTimer = QTimer(self)
        self._delay_timer.setSingleShot(True)
        self._delay_timer.setInterval(resolved_style.delay_ms)
        self._delay_timer.timeout.connect(self._show_tooltip)

        self._target.installEventFilter(self)
        self._target.destroyed.connect(self._on_target_destroyed)

    def set_text(self, text: str) -> None:
        """Mengubah teks tooltip secara dinamis saat aplikasi berjalan.

        Args:
            text: Teks tooltip terbaru.
        """
        self._tooltip.set_text(text)

    def _show_tooltip(self) -> None:
        """Memicu kemunculan tooltip apabila kursor masih berada di atas target."""
        if self._target.isVisible() and self._target.underMouse():
            self._tooltip.show_for_widget(self._target)

    def _on_target_destroyed(self) -> None:
        """Membersihkan timer dan objek tooltip saat widget target dihapus."""
        self._delay_timer.stop()
        self._tooltip.deleteLater()

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        """Menyaring event mouse dan visibilitas pada widget target.

        Args:
            watched: Objek Qt yang sedang dipantau.
            event: Objek event Qt yang sedang diproses.

        Returns:
            Status boolean penerusan event dari kelas induk.
        """
        if watched is self._target:
            event_type = event.type()
            if event_type == QEvent.Type.Enter:
                self._delay_timer.start()
            elif event_type in (
                QEvent.Type.Leave,
                QEvent.Type.MouseButtonPress,
                QEvent.Type.Hide,
            ):
                self._delay_timer.stop()
                self._tooltip.hide_animated()

        return super().eventFilter(watched, event)


def attach_tooltip(
    widget: QWidget,
    text: str,
    position: TooltipPosition = TooltipPosition.RIGHT,
    style: TooltipStyle | None = None,
) -> TooltipController:
    """Memasang tooltip kustom beranimasi pada widget atau tombol PySide6 apa pun.

    Args:
        widget: Tombol, ikon, atau widget target yang ingin diberi tooltip.
        text: Teks keterangan yang muncul saat widget di-hover.
        position: Posisi tooltip terhadap widget, default di sisi kanan.
        style: Konfigurasi warna dan jeda waktu opsional.

    Returns:
        Objek TooltipController yang terikat pada siklus hidup widget target.
    """
    return TooltipController(widget, text, position=position, style=style)