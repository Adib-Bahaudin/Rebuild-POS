"""Modul backend untuk halaman Riwayat Transaksi POS.

Modul ini menghubungkan antarmuka pengguna RiwayatTransaksiPage dengan database
transaksi SQLite, menyediakan layanan query berpaginasi, perhitungan ringkasan
statistik dan perbandingan periode, pengambilan detail faktur lengkap, serta
ekspor laporan ke format Excel (.xlsx) dan PDF (.pdf).
"""

from __future__ import annotations

import calendar
import html
import importlib
import logging
import math
import sqlite3
from contextlib import closing
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

from PySide6.QtCore import QMarginsF, QObject, QTimer, Signal
from PySide6.QtGui import QPageLayout, QPageSize, QTextDocument
from PySide6.QtPrintSupport import QPrinter
from PySide6.QtWidgets import QFileDialog, QMessageBox

from config import DEFAULT_DB_PATH
from ui.riwayat_transaksi import (
    FilterCriteria,
    RiwayatTransaksiPage,
    TransactionRowData,
    TrendStatus,
)

logger = logging.getLogger(__name__)

DEFAULT_PAGE_SIZE: int = 9
SEARCH_DEBOUNCE_MS: int = 300
ALL_METHODS_LABEL: str = "Semua Metode"
ALL_STATUSES_LABEL: str = "Semua Status"

PAYMENT_STATUS_FILTER_MAP: dict[str, str] = {
    "Lunas": "PAID",
    "Cicilan": "PARTIAL",
    "Belum Lunas": "UNPAID",
}


@dataclass(frozen=True)
class DateRange:
    """Rentang tanggal periode aktif beserta periode pembandingnya.

    Attributes:
        start_date: Tanggal awal periode aktif.
        end_date: Tanggal akhir periode aktif.
        previous_start: Tanggal awal periode pembanding sebelumnya.
        previous_end: Tanggal akhir periode pembanding sebelumnya.
        comparison_label: Teks akhiran pembanding untuk footer kartu ringkasan.
    """

    start_date: date
    end_date: date
    previous_start: date
    previous_end: date
    comparison_label: str


@dataclass(frozen=True)
class MetricComparison:
    """Hasil perhitungan tren perbandingan satu metrik statistik.

    Attributes:
        text: Teks persentase perbandingan, misalnya '+12.5% dari minggu kemarin'.
        status: Status visual tren ('positive', 'negative', atau 'neutral').
    """

    text: str
    status: TrendStatus


@dataclass(frozen=True)
class SummaryMetrics:
    """Ringkasan metrik utama dan tren perbandingan untuk tiga kartu statistik.

    Attributes:
        total_transactions: Jumlah total transaksi pada periode aktif.
        total_revenue: Total pendapatan kotor/bersih sesuai kolom total penjualan.
        average_transaction: Nilai rata-rata nominal per transaksi.
        tx_comparison: Tren perbandingan jumlah transaksi.
        revenue_comparison: Tren perbandingan total pendapatan.
        average_comparison: Tren perbandingan rata-rata nilai transaksi.
    """

    total_transactions: int
    total_revenue: int
    average_transaction: int
    tx_comparison: MetricComparison
    revenue_comparison: MetricComparison
    average_comparison: MetricComparison


@dataclass(frozen=True)
class SaleMetadata:
    """Informasi identitas utama satu faktur penjualan.

    Attributes:
        sale_id: ID internal transaksi pada tabel sales.
        invoice_number: Nomor faktur unik transaksi.
        sale_date: Tanggal dan waktu transaksi dalam format mentah database.
        customer_name: Nama pelanggan terkait atau 'Umum' jika tanpa pelanggan.
        customer_phone: Nomor telepon pelanggan jika tersedia.
        cashier_name: Nama kasir yang mencatat transaksi.
        notes: Catatan tambahan transaksi jika ada.
    """

    sale_id: int
    invoice_number: str
    sale_date: str
    customer_name: str
    customer_phone: str
    cashier_name: str
    notes: str


@dataclass(frozen=True)
class SaleAmounts:
    """Rincian komponen nominal transaksi penjualan.

    Attributes:
        subtotal: Total harga sebelum diskon, pembulatan, dan tip.
        discount: Nominal potongan harga transaksi.
        rounding: Nilai pembulatan transaksi (positif atau negatif).
        tip: Nominal tip tambahan jika ada.
        total: Nominal total akhir yang harus dibayar.
    """

    subtotal: int
    discount: int
    rounding: int
    tip: int
    total: int


@dataclass(frozen=True)
class SalePaymentSummary:
    """Ringkasan status pembayaran dan pelunasan transaksi.

    Attributes:
        payment_method: Metode pembayaran utama transaksi.
        payment_status: Status pembayaran ('PAID', 'PARTIAL', atau 'UNPAID').
        amount_paid: Total nominal yang sudah dibayarkan pelanggan.
        remaining_amount: Sisa tagihan yang belum dibayarkan.
        change_amount: Total uang kembalian pada transaksi.
        due_date: Tanggal jatuh tempo pembayaran jika ada.
    """

    payment_method: str
    payment_status: str
    amount_paid: int
    remaining_amount: int
    change_amount: int
    due_date: str


@dataclass(frozen=True)
class TransactionItemDetail:
    """Rincian satu baris barang atau jasa pada faktur transaksi.

    Attributes:
        line_type: Jenis baris transaksi ('ITEM' atau 'SERVICE').
        description: Nama atau deskripsi barang/jasa yang dibeli.
        quantity: Jumlah kuantitas yang ditransaksikan.
        unit_price: Harga satuan saat transaksi terjadi.
        subtotal: Subtotal nominal baris transaksi.
    """

    line_type: str
    description: str
    quantity: float
    unit_price: int
    subtotal: int


@dataclass(frozen=True)
class TransactionPaymentRecord:
    """Catatan satu riwayat pembayaran atau cicilan untuk transaksi penjualan.

    Attributes:
        payment_date: Waktu pembayaran dicatat.
        amount: Nominal yang mengurangi tagihan transaksi.
        tendered_amount: Nominal uang yang diserahkan pelanggan.
        change_given: Uang kembalian yang diberikan pada pembayaran ini.
        payment_method: Metode pembayaran yang digunakan.
        reference_number: Nomor referensi transfer/QRIS jika tersedia.
        notes: Catatan pembayaran opsional.
    """

    payment_date: str
    amount: int
    tendered_amount: int
    change_given: int
    payment_method: str
    reference_number: str
    notes: str


@dataclass(frozen=True)
class TransactionFullDetail:
    """Struktur data lengkap satu faktur transaksi untuk tampilan detail dan cetak.

    Attributes:
        metadata: Identitas faktur, pelanggan, kasir, dan catatan.
        amounts: Rincian nominal subtotal, diskon, pembulatan, tip, dan total.
        payment: Ringkasan metode, status pelunasan, dan sisa tagihan.
        items: Daftar rincian item barang dan jasa pada faktur.
        payments: Daftar riwayat pembayaran atau cicilan transaksi.
    """

    metadata: SaleMetadata
    amounts: SaleAmounts
    payment: SalePaymentSummary
    items: list[TransactionItemDetail]
    payments: list[TransactionPaymentRecord]


@dataclass(frozen=True)
class PaginatedTransactionsResult:
    """Hasil pengambilan daftar transaksi berpaginasi beserta ringkasan metriknya.

    Attributes:
        rows: Daftar baris transaksi siap tampil untuk halaman aktif.
        current_page: Nomor halaman aktif setelah validasi batas halaman.
        total_pages: Total seluruh halaman yang tersedia.
        total_items: Total seluruh baris transaksi yang cocok dengan filter.
        summary: Ringkasan metrik untuk tiga kartu statistik.
    """

    rows: list[TransactionRowData]
    current_page: int
    total_pages: int
    total_items: int
    summary: SummaryMetrics


@dataclass(frozen=True)
class ExportReportData:
    """Paket data terfilter penuh untuk proses ekspor laporan Excel maupun PDF.

    Attributes:
        criteria: Kriteria filter UI yang aktif saat ekspor dijalankan.
        date_range: Rentang tanggal terhitung yang dipakai untuk query.
        summary: Ringkasan metrik periode aktif.
        rows: Seluruh baris transaksi yang cocok dengan filter tanpa paginasi.
    """

    criteria: FilterCriteria
    date_range: DateRange
    summary: SummaryMetrics
    rows: list[TransactionRowData]


def format_integer(value: int) -> str:
    """Memformat bilangan bulat menggunakan pemisah ribuan titik bergaya Indonesia.

    Args:
        value: Bilangan bulat yang akan diformat.

    Returns:
        String angka dengan pemisah ribuan titik, misalnya '1.250'.
    """
    return f"{value:,}".replace(",", ".")


def format_rupiah(amount: int, show_sign: bool = False) -> str:
    """Memformat nominal integer menjadi string mata uang Rupiah.

    Args:
        amount: Nilai nominal dalam satuan Rupiah bulat.
        show_sign: Jika True, nilai positif diberi tanda '+' di depan Rupiah.

    Returns:
        String nominal terformat, misalnya 'Rp 15.000', '-Rp 500', atau '+Rp 200'.
    """
    formatted_abs = format_integer(abs(amount))
    if amount < 0:
        return f"-Rp {formatted_abs}"
    if amount > 0 and show_sign:
        return f"+Rp {formatted_abs}"
    return f"Rp {formatted_abs}"


def format_display_datetime(raw_value: str) -> str:
    """Mengonversi string tanggal ISO database menjadi format tampilan tabel UI.

    Args:
        raw_value: String tanggal atau timestamp dari kolom sale_date database.

    Returns:
        String tanggal terformat 'DD/MM/YYYY HH:MM' atau 'DD/MM/YYYY'.
    """
    cleaned = raw_value.strip()
    if not cleaned:
        return "-"

    normalized = cleaned.replace("T", " ")
    for fmt, out_fmt in (
        ("%Y-%m-%d %H:%M:%S", "%d/%m/%Y %H:%M"),
        ("%Y-%m-%d %H:%M", "%d/%m/%Y %H:%M"),
        ("%Y-%m-%d", "%d/%m/%Y"),
    ):
        try:
            parsed = datetime.strptime(normalized[:19], fmt)
            return parsed.strftime(out_fmt)
        except ValueError:
            continue
    return cleaned


def format_payment_method_label(
    payment_method: str,
    payment_status: str,
) -> str:
    """Memformat label kolom Metode Bayar berdasarkan metode dan status pembayaran.

    Jika payment_method bernilai 'Belum Lunas', label dipetakan menjadi 'Cicilan'
    saat status 'PARTIAL' atau 'Hutang' saat status 'UNPAID'.

    Args:
        payment_method: Nilai kolom payment_method pada tabel sales.
        payment_status: Nilai kolom payment_status ('PAID', 'PARTIAL', 'UNPAID').

    Returns:
        Label metode pembayaran terformat rapi untuk ditampilkan pada tabel.
    """
    method_clean = payment_method.strip()
    status_upper = payment_status.strip().upper()

    if method_clean.lower() == "belum lunas":
        if status_upper == "PARTIAL":
            return "Cicilan"
        if status_upper == "UNPAID":
            return "Hutang"

    if not method_clean:
        return "Tunai"
    if method_clean.upper() == "QRIS":
        return "QRIS"
    return method_clean

def format_payment_status_label(payment_status: str) -> str:
    """Mengonversi kode status pembayaran database menjadi label bahasa Indonesia.

    Seluruh status selain 'PAID' akan ditampilkan sebagai 'Belum Lunas'.

    Args:
        payment_status: Nilai kolom payment_status ('PAID', 'PARTIAL', 'UNPAID').

    Returns:
        'Lunas' jika status bernilai 'PAID', selain itu 'Belum Lunas'.
    """
    if payment_status.strip().upper() == "PAID":
        return "Lunas"
    return "Belum Lunas"

def parse_iso_date(raw_date: str, fallback: date) -> date:
    """Mengurai string tanggal ISO (YYYY-MM-DD) secara aman dengan nilai cadangan.

    Args:
        raw_date: String tanggal berformat ISO.
        fallback: Nilai tanggal pengganti apabila proses parsing gagal.

    Returns:
        Objek date hasil parsing atau tanggal cadangan jika format tidak valid.
    """
    try:
        return date.fromisoformat(raw_date.strip())
    except ValueError:
        return fallback


def resolve_date_range(
    criteria: FilterCriteria,
    reference_date: date | None = None,
) -> DateRange:
    """Menentukan rentang tanggal aktif dan periode pembanding sesuai preset filter.

    Args:
        criteria: Objek FilterCriteria yang dikirim dari FilterBarWidget UI.
        reference_date: Tanggal acuan opsional untuk kebutuhan pengujian unit.

    Returns:
        Objek DateRange lengkap dengan periode aktif, periode sebelumnya, dan label.
    """
    today = reference_date if reference_date is not None else date.today()
    preset = criteria.date_preset.strip()

    if preset == "Hari Ini":
        yesterday = today - timedelta(days=1)
        return DateRange(
            start_date=today,
            end_date=today,
            previous_start=yesterday,
            previous_end=yesterday,
            comparison_label="dari kemarin",
        )

    if preset == "Minggu Ini":
        start_of_week = today - timedelta(days=today.weekday())
        return DateRange(
            start_date=start_of_week,
            end_date=today,
            previous_start=start_of_week - timedelta(days=7),
            previous_end=today - timedelta(days=7),
            comparison_label="dari minggu kemarin",
        )

    if preset == "Bulan Ini":
        start_of_month = today.replace(day=1)
        prev_year = today.year - 1 if today.month == 1 else today.year
        prev_month = 12 if today.month == 1 else today.month - 1
        prev_last_day = calendar.monthrange(prev_year, prev_month)[1]
        return DateRange(
            start_date=start_of_month,
            end_date=today,
            previous_start=date(prev_year, prev_month, 1),
            previous_end=date(prev_year, prev_month, min(today.day, prev_last_day)),
            comparison_label="dari bulan kemarin",
        )

    start = parse_iso_date(criteria.start_date, today)
    end = parse_iso_date(criteria.end_date, today)
    if end < start:
        start, end = end, start

    span_days = (end - start).days + 1
    previous_end = start - timedelta(days=1)
    previous_start = previous_end - timedelta(days=span_days - 1)
    return DateRange(
        start_date=start,
        end_date=end,
        previous_start=previous_start,
        previous_end=previous_end,
        comparison_label="dari periode sebelumnya",
    )


def calculate_percentage_trend(
    current: int,
    previous: int,
    comparison_label: str,
) -> MetricComparison:
    """Menghitung persentase perubahan nilai metrik dibanding periode sebelumnya.

    Args:
        current: Nilai metrik pada periode aktif.
        previous: Nilai metrik pada periode pembanding sebelumnya.
        comparison_label: Teks keterangan periode pembanding.

    Returns:
        Objek MetricComparison berisi teks terformat dan status warna tren.
    """
    if previous <= 0:
        if current <= 0:
            return MetricComparison(
                text=f"0% {comparison_label}",
                status="neutral",
            )
        return MetricComparison(
            text=f"+100% {comparison_label}",
            status="positive",
        )

    delta_percent = ((current - previous) / previous) * 100.0
    if abs(delta_percent) < 0.05:
        return MetricComparison(
            text=f"0% {comparison_label}",
            status="neutral",
        )
    if delta_percent > 0:
        return MetricComparison(
            text=f"+{delta_percent:.1f}% {comparison_label}",
            status="positive",
        )
    return MetricComparison(
        text=f"{delta_percent:.1f}% {comparison_label}",
        status="negative",
    )


class RiwayatRepository:
    """Lapisan akses database SQLite khusus untuk pembacaan riwayat transaksi.

    Attributes:
        db_path: Path menuju file database SQLite aplikasi POS.
    """

    def __init__(self, db_path: str | Path | None = None) -> None:
        """Menginisialisasi repository dengan lokasi database target.

        Args:
            db_path: Path opsional file database SQLite. Jika None, memakai
                DEFAULT_DB_PATH dari modul config.
        """
        self.db_path: Path = Path(db_path) if db_path is not None else DEFAULT_DB_PATH

    def _connect(self) -> sqlite3.Connection:
        """Membuka koneksi SQLite baru dengan Row factory dan foreign keys aktif.

        Returns:
            Objek koneksi sqlite3.Connection siap digunakan.

        Raises:
            FileNotFoundError: Apabila file database belum ditemukan pada disk.
        """
        if not self.db_path.exists() or not self.db_path.is_file():
            raise FileNotFoundError(
                f"File database tidak ditemukan di: {self.db_path}"
            )
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")
        return conn

    def is_ready(self) -> bool:
        """Memeriksa apakah file database dan tabel sales telah tersedia.

        Returns:
            True jika database dapat diakses dan tabel sales tersedia, False jika tidak.
        """
        if not self.db_path.exists() or not self.db_path.is_file():
            return False
        try:
            with closing(self._connect()) as conn:
                cursor = conn.execute(
                    """
                    SELECT 1
                    FROM sqlite_master
                    WHERE type = 'table' AND name = 'sales';
                    """
                )
                return cursor.fetchone() is not None
        except sqlite3.Error:
            logger.exception("Gagal memverifikasi kesiapan tabel sales pada database")
            return False

    @staticmethod
    def _build_where_clause(
        start_date: date,
        end_date: date,
        criteria: FilterCriteria,
    ) -> tuple[str, list[Any]]:
        """Menyusun klausa SQL WHERE dan parameter terikat sesuai kriteria filter.

        Args:
            start_date: Batas tanggal awal filter.
            end_date: Batas tanggal akhir filter.
            criteria: Kriteria filter metode bayar, status bayar, dan pencarian UI.

        Returns:
            Tuple berisi string klausa WHERE dan daftar nilai parameter SQL.
        """
        conditions: list[str] = [
            "UPPER(COALESCE(s.status, 'COMPLETED')) = 'COMPLETED'",
            "date(s.sale_date) BETWEEN ? AND ?",
        ]
        params: list[Any] = [start_date.isoformat(), end_date.isoformat()]

        payment_filter = criteria.payment_method.strip()
        if payment_filter and payment_filter != ALL_METHODS_LABEL:
            payment_lower = payment_filter.lower()
            if payment_lower == "cicilan":
                conditions.append(
                    "LOWER(TRIM(s.payment_method)) = 'belum lunas' "
                    "AND UPPER(TRIM(COALESCE(s.payment_status, 'PAID'))) = 'PARTIAL'"
                )
            elif payment_lower == "hutang":
                conditions.append(
                    "LOWER(TRIM(s.payment_method)) = 'belum lunas' "
                    "AND UPPER(TRIM(COALESCE(s.payment_status, 'PAID'))) = 'UNPAID'"
                )
            else:
                conditions.append("LOWER(TRIM(s.payment_method)) = LOWER(TRIM(?))")
                params.append(payment_filter)

        status_filter = criteria.payment_status.strip()
        if status_filter and status_filter != ALL_STATUSES_LABEL:
            if status_filter.lower() == "lunas":
                conditions.append(
                    "UPPER(TRIM(COALESCE(s.payment_status, 'PAID'))) = 'PAID'"
                )
            elif status_filter.lower() == "belum lunas":
                conditions.append(
                    "UPPER(TRIM(COALESCE(s.payment_status, 'PAID'))) != 'PAID'"
                )

        search_term = criteria.search_query.strip()
        if search_term:
            like_pattern = f"%{search_term}%"
            conditions.append(
                "(LOWER(s.invoice_number) LIKE LOWER(?) "
                "OR LOWER(COALESCE(s.notes, '')) LIKE LOWER(?) "
                "OR LOWER(COALESCE(c.name, '')) LIKE LOWER(?) "
                "OR LOWER(COALESCE(s.cashier_name, '')) LIKE LOWER(?))"
            )
            params.extend([like_pattern, like_pattern, like_pattern, like_pattern])

        return " AND ".join(conditions), params

    def _fetch_period_totals(
        self,
        conn: sqlite3.Connection,
        start_date: date,
        end_date: date,
        criteria: FilterCriteria,
    ) -> tuple[int, int]:
        """Menghitung jumlah transaksi dan total pendapatan untuk rentang tanggal tertentu.

        Args:
            conn: Koneksi SQLite aktif.
            start_date: Tanggal awal periode.
            end_date: Tanggal akhir periode.
            criteria: Kriteria metode pembayaran dan kata kunci pencarian.

        Returns:
            Tuple (jumlah_transaksi, total_pendapatan) bertipe integer.
        """
        where_sql, params = self._build_where_clause(start_date, end_date, criteria)
        query = (
            "SELECT "
            "    COUNT(s.id) AS total_transactions, "
            "    COALESCE(SUM(s.total), 0) AS total_revenue "
            "FROM sales AS s "
            "LEFT JOIN customers AS c ON c.id = s.customer_id "
            f"WHERE {where_sql};"
        )
        row = conn.execute(query, params).fetchone()
        if row is None:
            return 0, 0
        return int(row["total_transactions"] or 0), int(row["total_revenue"] or 0)

    def _build_summary_metrics(
        self,
        conn: sqlite3.Connection,
        date_range: DateRange,
        criteria: FilterCriteria,
    ) -> SummaryMetrics:
        """Menghitung seluruh metrik kartu ringkasan beserta persentase trennya.

        Args:
            conn: Koneksi SQLite aktif.
            date_range: Rentang tanggal periode aktif dan periode pembanding.
            criteria: Kriteria filter aktif dari antarmuka pengguna.

        Returns:
            Objek SummaryMetrics lengkap siap diterapkan ke SummaryCardsContainer.
        """
        curr_count, curr_revenue = self._fetch_period_totals(
            conn,
            date_range.start_date,
            date_range.end_date,
            criteria,
        )
        prev_count, prev_revenue = self._fetch_period_totals(
            conn,
            date_range.previous_start,
            date_range.previous_end,
            criteria,
        )

        curr_avg = round(curr_revenue / curr_count) if curr_count > 0 else 0
        prev_avg = round(prev_revenue / prev_count) if prev_count > 0 else 0

        label = date_range.comparison_label
        return SummaryMetrics(
            total_transactions=curr_count,
            total_revenue=curr_revenue,
            average_transaction=curr_avg,
            tx_comparison=calculate_percentage_trend(curr_count, prev_count, label),
            revenue_comparison=calculate_percentage_trend(
                curr_revenue,
                prev_revenue,
                label,
            ),
            average_comparison=calculate_percentage_trend(curr_avg, prev_avg, label),
        )

    @staticmethod
    def _map_rows_to_table_data(
        db_rows: list[sqlite3.Row],
        start_number: int = 1,
    ) -> list[TransactionRowData]:
        """Mengonversi hasil query SQLite menjadi daftar objek TransactionRowData UI.

        Args:
            db_rows: Daftar baris sqlite3.Row dari tabel sales.
            start_number: Nomor urut awal untuk kolom 'No' pada tabel.

        Returns:
            Daftar objek TransactionRowData terformat.
        """
        mapped: list[TransactionRowData] = []
        for idx, row in enumerate(db_rows, start=start_number):
            raw_method = str(row["payment_method"] or "")
            raw_status = str(row["payment_status"] or "PAID")
            mapped.append(
                TransactionRowData(
                    no=idx,
                    invoice=str(row["invoice_number"] or ""),
                    tanggal=format_display_datetime(str(row["sale_date"] or "")),
                    metode_bayar=format_payment_method_label(
                        raw_method,
                        raw_status,
                    ),
                    status_bayar=format_payment_status_label(raw_status),
                    sub_total=format_rupiah(int(row["subtotal"] or 0)),
                    diskon=format_rupiah(int(row["discount"] or 0)),
                    pembulatan=format_rupiah(
                        int(row["rounding"] or 0),
                        show_sign=True,
                    ),
                    total=format_rupiah(int(row["total"] or 0)),
                )
            )
        return mapped

    def fetch_paginated(
        self,
        criteria: FilterCriteria,
        page: int = 1,
        page_size: int = DEFAULT_PAGE_SIZE,
    ) -> PaginatedTransactionsResult:
        """Mengambil daftar transaksi berpaginasi beserta ringkasan metrik periode.

        Args:
            criteria: Objek FilterCriteria dari UI.
            page: Nomor halaman target berbasis 1.
            page_size: Jumlah maksimal baris data per halaman.

        Returns:
            Objek PaginatedTransactionsResult berisi baris tabel, info paginasi,
            dan ringkasan kartu statistik.
        """
        safe_page_size = max(1, page_size)
        date_range = resolve_date_range(criteria)
        where_sql, base_params = self._build_where_clause(
            date_range.start_date,
            date_range.end_date,
            criteria,
        )

        with closing(self._connect()) as conn:
            summary = self._build_summary_metrics(conn, date_range, criteria)
            total_items = summary.total_transactions
            total_pages = max(1, math.ceil(total_items / safe_page_size))
            safe_page = max(1, min(page, total_pages))
            offset = (safe_page - 1) * safe_page_size

            query = (
                "SELECT "
                "    s.invoice_number, "
                "    s.sale_date, "
                "    s.payment_method, "
                "    s.payment_status, "
                "    s.subtotal, "
                "    s.discount, "
                "    s.rounding, "
                "    s.total "
                "FROM sales AS s "
                "LEFT JOIN customers AS c ON c.id = s.customer_id "
                f"WHERE {where_sql} "
                "ORDER BY s.sale_date DESC, s.id DESC "
                "LIMIT ? OFFSET ?;"
            )
            db_rows = conn.execute(
                query,
                [*base_params, safe_page_size, offset],
            ).fetchall()

        rows = self._map_rows_to_table_data(db_rows, start_number=offset + 1)
        return PaginatedTransactionsResult(
            rows=rows,
            current_page=safe_page,
            total_pages=total_pages,
            total_items=total_items,
            summary=summary,
        )

    def fetch_all_filtered(self, criteria: FilterCriteria) -> ExportReportData:
        """Mengambil seluruh transaksi yang cocok dengan filter untuk kebutuhan ekspor.

        Args:
            criteria: Kriteria filter aktif dari antarmuka pengguna.

        Returns:
            Objek ExportReportData berisi seluruh baris transaksi tanpa paginasi.
        """
        date_range = resolve_date_range(criteria)
        where_sql, params = self._build_where_clause(
            date_range.start_date,
            date_range.end_date,
            criteria,
        )

        with closing(self._connect()) as conn:
            summary = self._build_summary_metrics(conn, date_range, criteria)
            query = (
                "SELECT "
                "    s.invoice_number, "
                "    s.sale_date, "
                "    s.payment_method, "
                "    s.payment_status, "
                "    s.subtotal, "
                "    s.discount, "
                "    s.rounding, "
                "    s.total "
                "FROM sales AS s "
                "LEFT JOIN customers AS c ON c.id = s.customer_id "
                f"WHERE {where_sql} "
                "ORDER BY s.sale_date DESC, s.id DESC;"
            )
            db_rows = conn.execute(query, params).fetchall()

        return ExportReportData(
            criteria=criteria,
            date_range=date_range,
            summary=summary,
            rows=self._map_rows_to_table_data(db_rows, start_number=1),
        )

    def fetch_transaction_detail(
        self,
        invoice_number: str,
    ) -> TransactionFullDetail | None:
        """Mengambil detail lengkap satu transaksi berdasarkan nomor invoice.

        Args:
            invoice_number: Nomor faktur unik yang dipilih pengguna pada tabel.

        Returns:
            Objek TransactionFullDetail jika faktur ditemukan, atau None jika tidak.
        """
        with closing(self._connect()) as conn:
            sale_row = conn.execute(
                """
                SELECT
                    s.id,
                    s.invoice_number,
                    s.sale_date,
                    s.subtotal,
                    s.discount,
                    s.rounding,
                    s.tip,
                    s.total,
                    s.payment_method,
                    s.amount_paid,
                    s.remaining_amount,
                    s.change_amount,
                    s.payment_status,
                    s.due_date,
                    s.cashier_name,
                    s.notes,
                    COALESCE(c.name, 'Umum') AS customer_name,
                    COALESCE(c.phone, '') AS customer_phone
                FROM sales AS s
                LEFT JOIN customers AS c ON c.id = s.customer_id
                WHERE s.invoice_number = ?
                LIMIT 1;
                """,
                (invoice_number.strip(),),
            ).fetchone()

            if sale_row is None:
                return None

            sale_id = int(sale_row["id"])
            item_rows = conn.execute(
                """
                SELECT
                    line_type,
                    description,
                    quantity,
                    unit_price,
                    subtotal
                FROM sale_details
                WHERE sale_id = ?
                ORDER BY id ASC;
                """,
                (sale_id,),
            ).fetchall()

            payment_rows = conn.execute(
                """
                SELECT
                    payment_date,
                    amount,
                    tendered_amount,
                    change_given,
                    payment_method,
                    reference_number,
                    notes
                FROM sale_payments
                WHERE sale_id = ?
                ORDER BY payment_date ASC, id ASC;
                """,
                (sale_id,),
            ).fetchall()

        metadata = SaleMetadata(
            sale_id=sale_id,
            invoice_number=str(sale_row["invoice_number"] or ""),
            sale_date=format_display_datetime(str(sale_row["sale_date"] or "")),
            customer_name=str(sale_row["customer_name"] or "Umum"),
            customer_phone=str(sale_row["customer_phone"] or ""),
            cashier_name=str(sale_row["cashier_name"] or "KASIR"),
            notes=str(sale_row["notes"] or ""),
        )
        amounts = SaleAmounts(
            subtotal=int(sale_row["subtotal"] or 0),
            discount=int(sale_row["discount"] or 0),
            rounding=int(sale_row["rounding"] or 0),
            tip=int(sale_row["tip"] or 0),
            total=int(sale_row["total"] or 0),
        )
        payment = SalePaymentSummary(
            payment_method=str(sale_row["payment_method"] or "Tunai"),
            payment_status=str(sale_row["payment_status"] or "PAID"),
            amount_paid=int(sale_row["amount_paid"] or 0),
            remaining_amount=int(sale_row["remaining_amount"] or 0),
            change_amount=int(sale_row["change_amount"] or 0),
            due_date=str(sale_row["due_date"] or ""),
        )
        items = [
            TransactionItemDetail(
                line_type=str(item["line_type"] or "ITEM"),
                description=str(item["description"] or ""),
                quantity=float(item["quantity"] or 0.0),
                unit_price=int(item["unit_price"] or 0),
                subtotal=int(item["subtotal"] or 0),
            )
            for item in item_rows
        ]
        payments = [
            TransactionPaymentRecord(
                payment_date=format_display_datetime(str(pay["payment_date"] or "")),
                amount=int(pay["amount"] or 0),
                tendered_amount=int(pay["tendered_amount"] or 0),
                change_given=int(pay["change_given"] or 0),
                payment_method=str(pay["payment_method"] or "Tunai"),
                reference_number=str(pay["reference_number"] or ""),
                notes=str(pay["notes"] or ""),
            )
            for pay in payment_rows
        ]

        return TransactionFullDetail(
            metadata=metadata,
            amounts=amounts,
            payment=payment,
            items=items,
            payments=payments,
        )


class RiwayatExporter:
    """Layanan ekspor data riwayat transaksi ke dokumen Excel (.xlsx) dan PDF (.pdf)."""

    EXCEL_HEADERS: tuple[str, ...] = (
        "No",
        "Invoice",
        "Tanggal",
        "Metode Bayar",
        "Sub Total",
        "Diskon",
        "Pembulatan",
        "Total",
    )

    @staticmethod
    def _load_openpyxl_modules() -> tuple[Any, Any, Any]:
        """Memuat modul openpyxl secara dinamis untuk pembuatan file Excel.

        Returns:
            Tuple berisi modul (openpyxl, openpyxl.styles, openpyxl.utils).

        Raises:
            RuntimeError: Apabila pustaka openpyxl belum terpasang di environment.
        """
        try:
            openpyxl_mod = importlib.import_module("openpyxl")
            styles_mod = importlib.import_module("openpyxl.styles")
            utils_mod = importlib.import_module("openpyxl.utils")
        except ModuleNotFoundError as exc:
            raise RuntimeError(
                "Library 'openpyxl' belum terpasang. "
                "Jalankan 'pip install openpyxl' untuk menggunakan fitur ekspor Excel."
            ) from exc
        return openpyxl_mod, styles_mod, utils_mod

    @staticmethod
    def _write_excel_header_block(
        worksheet: Any,
        styles_mod: Any,
        report: ExportReportData,
    ) -> None:
        """Menulis judul, informasi periode, dan ringkasan statistik di bagian atas sheet.

        Args:
            worksheet: Worksheet aktif openpyxl.
            styles_mod: Modul openpyxl.styles untuk penataan font dan perataan.
            report: Data laporan terfilter yang akan diekspor.
        """
        period_str = (
            f"{report.date_range.start_date.strftime('%d/%m/%Y')} - "
            f"{report.date_range.end_date.strftime('%d/%m/%Y')}"
        )
        worksheet["A1"] = "LAPORAN RIWAYAT TRANSAKSI"
        worksheet["A1"].font = styles_mod.Font(bold=True, size=14, color="0F172A")

        worksheet["A2"] = f"Periode: {period_str}"
        worksheet["A3"] = f"Metode Bayar: {report.criteria.payment_method}"
        worksheet["E2"] = (
            f"Total Transaksi: {format_integer(report.summary.total_transactions)}"
        )
        worksheet["E3"] = (
            f"Total Revenue: {format_rupiah(report.summary.total_revenue)}"
        )
        worksheet["E4"] = (
            f"Rata-Rata: {format_rupiah(report.summary.average_transaction)}"
        )

    def _write_excel_table_rows(
        self,
        worksheet: Any,
        styles_mod: Any,
        rows: list[TransactionRowData],
    ) -> None:
        """Menulis baris header tabel dan seluruh catatan transaksi ke worksheet Excel.

        Args:
            worksheet: Worksheet aktif openpyxl.
            styles_mod: Modul openpyxl.styles untuk pewarnaan dan batas sel.
            rows: Daftar baris transaksi terformat.
        """
        header_row = 6
        header_fill = styles_mod.PatternFill(
            fill_type="solid",
            start_color="1E293B",
            end_color="1E293B",
        )
        header_font = styles_mod.Font(bold=True, color="FFFFFF", size=11)
        thin_side = styles_mod.Side(style="thin", color="CBD5E1")
        cell_border = styles_mod.Border(
            left=thin_side,
            right=thin_side,
            top=thin_side,
            bottom=thin_side,
        )
        stripe_fill = styles_mod.PatternFill(
            fill_type="solid",
            start_color="F8FAFC",
            end_color="F8FAFC",
        )

        for col_idx, title in enumerate(self.EXCEL_HEADERS, start=1):
            cell = worksheet.cell(row=header_row, column=col_idx, value=title)
            cell.fill = header_fill
            cell.font = header_font
            cell.border = cell_border
            cell.alignment = styles_mod.Alignment(
                horizontal="center",
                vertical="center",
            )

        for offset, row_data in enumerate(rows, start=1):
            excel_row = header_row + offset
            values = (
                row_data.no,
                row_data.invoice,
                row_data.tanggal,
                row_data.metode_bayar,
                row_data.sub_total,
                row_data.diskon,
                row_data.pembulatan,
                row_data.total,
            )
            for col_idx, val in enumerate(values, start=1):
                cell = worksheet.cell(row=excel_row, column=col_idx, value=val)
                cell.border = cell_border
                if offset % 2 == 0:
                    cell.fill = stripe_fill
                if col_idx in (1, 3, 4):
                    align_h = "center"
                elif col_idx >= 5:
                    align_h = "right"
                else:
                    align_h = "left"
                cell.alignment = styles_mod.Alignment(
                    horizontal=align_h,
                    vertical="center",
                )

    @staticmethod
    def _autofit_excel_columns(worksheet: Any, utils_mod: Any) -> None:
        """Menyesuaikan lebar setiap kolom worksheet agar seluruh teks terbaca rapi.

        Args:
            worksheet: Worksheet aktif openpyxl.
            utils_mod: Modul openpyxl.utils penyedia fungsi get_column_letter.
        """
        for col_cells in worksheet.columns:
            max_length = 0
            col_index = col_cells[0].column
            for cell in col_cells:
                if cell.row < 6:
                    continue
                text_len = len(str(cell.value or ""))
                if text_len > max_length:
                    max_length = text_len
            col_letter = utils_mod.get_column_letter(col_index)
            worksheet.column_dimensions[col_letter].width = max(12, max_length + 4)

    def export_excel(self, output_path: Path, report: ExportReportData) -> Path:
        """Menghasilkan file laporan transaksi berformat Excel (.xlsx).

        Args:
            output_path: Lokasi path file .xlsx tujuan penyimpanan.
            report: Paket data transaksi terfilter penuh yang akan diekspor.

        Returns:
            Path file Excel hasil ekspor yang telah tersimpan.
        """
        openpyxl_mod, styles_mod, utils_mod = self._load_openpyxl_modules()
        workbook = openpyxl_mod.Workbook()
        worksheet = workbook.active
        worksheet.title = "Riwayat Transaksi"

        self._write_excel_header_block(worksheet, styles_mod, report)
        self._write_excel_table_rows(worksheet, styles_mod, report.rows)
        self._autofit_excel_columns(worksheet, utils_mod)

        target_path = output_path.with_suffix(".xlsx")
        target_path.parent.mkdir(parents=True, exist_ok=True)
        workbook.save(str(target_path))
        return target_path

    @staticmethod
    def _build_pdf_rows_html(rows: list[TransactionRowData]) -> str:
        """Menyusun potongan markup baris HTML tabel untuk dokumen laporan PDF.

        Args:
            rows: Daftar baris transaksi terformat.

        Returns:
            String HTML berisi kumpulan elemen <tr> untuk isi tabel PDF.
        """
        html_rows: list[str] = []
        for idx, row in enumerate(rows):
            bg_color = "#F8FAFC" if idx % 2 == 1 else "#FFFFFF"
            html_rows.append(
                f"<tr style='background-color:{bg_color};'>"
                f"<td style='text-align:center;'>{row.no}</td>"
                f"<td>{html.escape(row.invoice)}</td>"
                f"<td style='text-align:center;'>{html.escape(row.tanggal)}</td>"
                f"<td style='text-align:center;'>{html.escape(row.metode_bayar)}</td>"
                f"<td style='text-align:right;'>{html.escape(row.sub_total)}</td>"
                f"<td style='text-align:right;'>{html.escape(row.diskon)}</td>"
                f"<td style='text-align:right;'>{html.escape(row.pembulatan)}</td>"
                f"<td style='text-align:right;font-weight:bold;'>"
                f"{html.escape(row.total)}</td>"
                "</tr>"
            )
        return "".join(html_rows)

    def _build_pdf_html(self, report: ExportReportData) -> str:
        """Membangun dokumen HTML lengkap bergaya laporan profesional untuk QTextDocument.

        Args:
            report: Paket data laporan terfilter penuh.

        Returns:
            String dokumen HTML siap cetak menjadi file PDF.
        """
        period_str = (
            f"{report.date_range.start_date.strftime('%d/%m/%Y')} - "
            f"{report.date_range.end_date.strftime('%d/%m/%Y')}"
        )
        printed_at = datetime.now().strftime("%d/%m/%Y %H:%M")
        table_rows_html = self._build_pdf_rows_html(report.rows)
        method_label = html.escape(report.criteria.payment_method)

        return f"""
        <html>
        <head>
            <style>
                body {{
                    font-family: 'Segoe UI', Arial, sans-serif;
                    color: #0F172A;
                    font-size: 9pt;
                }}
                h1 {{
                    margin: 0 0 4px 0;
                    font-size: 15pt;
                    color: #0F172A;
                }}
                .meta {{
                    color: #475569;
                    font-size: 8.5pt;
                    margin-bottom: 12px;
                }}
                .summary-table {{
                    width: 100%;
                    border-collapse: collapse;
                    margin-bottom: 14px;
                }}
                .summary-table td {{
                    border: 1px solid #CBD5E1;
                    background-color: #F1F5F9;
                    padding: 8px 10px;
                }}
                .summary-label {{
                    font-size: 8pt;
                    color: #475569;
                }}
                .summary-value {{
                    font-size: 11pt;
                    font-weight: bold;
                    color: #0F172A;
                }}
                .data-table {{
                    width: 100%;
                    border-collapse: collapse;
                }}
                .data-table th {{
                    background-color: #1E293B;
                    color: #FFFFFF;
                    padding: 7px 6px;
                    font-size: 8.5pt;
                    border: 1px solid #1E293B;
                }}
                .data-table td {{
                    padding: 6px;
                    border: 1px solid #CBD5E1;
                    font-size: 8.5pt;
                }}
            </style>
        </head>
        <body>
            <h1>Laporan Riwayat Transaksi</h1>
            <div class="meta">
                Periode: <b>{period_str}</b> &nbsp;|&nbsp;
                Metode Bayar: <b>{method_label}</b> &nbsp;|&nbsp;
                Dicetak: {printed_at}
            </div>
            <table class="summary-table">
                <tr>
                    <td>
                        <div class="summary-label">Total Transaksi</div>
                        <div class="summary-value">
                            {format_integer(report.summary.total_transactions)}
                        </div>
                    </td>
                    <td>
                        <div class="summary-label">Total Revenue</div>
                        <div class="summary-value">
                            {format_rupiah(report.summary.total_revenue)}
                        </div>
                    </td>
                    <td>
                        <div class="summary-label">Rata-Rata Transaksi</div>
                        <div class="summary-value">
                            {format_rupiah(report.summary.average_transaction)}
                        </div>
                    </td>
                </tr>
            </table>
            <table class="data-table">
                <thead>
                    <tr>
                        <th style="width:5%;">No</th>
                        <th style="width:19%;">Invoice</th>
                        <th style="width:15%;">Tanggal</th>
                        <th style="width:13%;">Metode Bayar</th>
                        <th style="width:12%;">Sub Total</th>
                        <th style="width:11%;">Diskon</th>
                        <th style="width:11%;">Pembulatan</th>
                        <th style="width:14%;">Total</th>
                    </tr>
                </thead>
                <tbody>
                    {table_rows_html}
                </tbody>
            </table>
        </body>
        </html>
        """

    def export_pdf(self, output_path: Path, report: ExportReportData) -> Path:
        """Menghasilkan file laporan transaksi berformat PDF menggunakan Qt PrintSupport.

        Args:
            output_path: Lokasi path file .pdf tujuan penyimpanan.
            report: Paket data transaksi terfilter penuh yang akan diekspor.

        Returns:
            Path file PDF hasil ekspor yang telah tersimpan.
        """
        target_path = output_path.with_suffix(".pdf")
        target_path.parent.mkdir(parents=True, exist_ok=True)

        printer = QPrinter(QPrinter.PrinterMode.HighResolution)
        printer.setOutputFormat(QPrinter.OutputFormat.PdfFormat)
        printer.setOutputFileName(str(target_path))
        printer.setPageSize(QPageSize(QPageSize.PageSizeId.A4))
        printer.setPageOrientation(QPageLayout.Orientation.Landscape)
        printer.setPageMargins(
            QMarginsF(12.0, 12.0, 12.0, 12.0),
            QPageLayout.Unit.Millimeter,
        )

        document = QTextDocument()
        document.setHtml(self._build_pdf_html(report))
        document.print_(printer)
        return target_path


class RiwayatBackend(QObject):
    """Pengendali backend penghubung antara RiwayatTransaksiPage dan database SQLite.

    Kelas ini mendengarkan seluruh sinyal interaksi dari halaman UI, melakukan
    query data secara terstruktur melalui RiwayatRepository, memperbarui kartu
    statistik, tabel, dan paginasi, serta menyediakan sinyal terpisah bagi
    jendela detail transaksi dan pencetakan struk.

    Signals:
        data_loaded: Dipancarkan setiap kali data halaman berhasil dimuat,
            membawa objek PaginatedTransactionsResult.
        detail_loaded: Dipancarkan saat detail faktur berhasil diambil setelah
            tombol Detail diklik, membawa objek TransactionFullDetail.
        print_data_ready: Dipancarkan saat data faktur siap dicetak setelah
            tombol Cetak diklik, membawa objek TransactionFullDetail.
        export_succeeded: Dipancarkan saat ekspor Excel/PDF berhasil, membawa
            pasangan string (format_ekspor, path_file).
        error_occurred: Dipancarkan saat terjadi kesalahan backend, membawa
            pasangan string (judul_kesalahan, pesan_kesalahan).
    """

    data_loaded = Signal(object)
    detail_loaded = Signal(object)
    print_data_ready = Signal(object)
    export_succeeded = Signal(str, str)
    error_occurred = Signal(str, str)

    def __init__(
        self,
        page: RiwayatTransaksiPage,
        db_path: str | Path | None = None,
        page_size: int = DEFAULT_PAGE_SIZE,
        show_dialogs: bool = True,
    ) -> None:
        """Menginisialisasi backend dan menghubungkannya dengan seluruh sinyal UI.

        Args:
            page: Instance RiwayatTransaksiPage yang akan dikelola.
            db_path: Lokasi path file database SQLite opsional.
            page_size: Jumlah baris transaksi per halaman pada tabel.
            show_dialogs: Jika True, menampilkan dialog pesan bawaan untuk status
                ekspor maupun kesalahan.
        """
        super().__init__(page)
        self._page = page
        self._repository = RiwayatRepository(db_path=db_path)
        self._exporter = RiwayatExporter()
        self._page_size = max(1, page_size)
        self._current_page = 1
        self._show_dialogs = show_dialogs

        self._search_timer = QTimer(self)
        self._search_timer.setSingleShot(True)
        self._search_timer.setInterval(SEARCH_DEBOUNCE_MS)

        self._connect_signals()

    def _connect_signals(self) -> None:
        """Menghubungkan seluruh sinyal UI halaman dan timer pencarian ke slot backend."""
        self._page.page_entered.connect(self.refresh)
        self._page.filter_requested.connect(self._on_filter_requested)
        self._page.search_text_changed.connect(self._on_search_text_changed)
        self._page.page_changed.connect(self._on_page_changed)
        self._page.detail_requested.connect(self._on_detail_requested)
        self._page.print_requested.connect(self._on_print_requested)
        self._page.export_excel_requested.connect(self.export_excel)
        self._page.export_pdf_requested.connect(self.export_pdf)
        self._page.filter_bar.custom_date_changed.connect(
            self._on_custom_date_changed
        )
        self._search_timer.timeout.connect(self._on_search_timeout)

    def refresh(self) -> None:
        """Memuat ulang data transaksi pada halaman aktif menggunakan filter UI saat ini."""
        self.load_transactions(
            criteria=self._page.get_filter_criteria(),
            page=self._current_page,
        )

    def load_transactions(
        self,
        criteria: FilterCriteria | None = None,
        page: int = 1,
    ) -> PaginatedTransactionsResult | None:
        """Mengambil data transaksi dari database lalu memperbarui seluruh komponen UI.

        Args:
            criteria: Kriteria filter opsional. Jika None, dibaca langsung dari UI.
            page: Nomor halaman yang akan ditampilkan.

        Returns:
            Objek PaginatedTransactionsResult apabila query berhasil, atau None
            jika terjadi kegagalan akses database.
        """
        active_criteria = (
            criteria if criteria is not None else self._page.get_filter_criteria()
        )
        try:
            result = self._repository.fetch_paginated(
                criteria=active_criteria,
                page=page,
                page_size=self._page_size,
            )
        except (FileNotFoundError, sqlite3.Error) as exc:
            logger.exception("Gagal memuat riwayat transaksi dari database")
            self._reset_ui_on_error()
            self._notify_error(
                "Gagal Memuat Data",
                f"Tidak dapat membaca data riwayat transaksi: {exc}",
            )
            return None

        self._current_page = result.current_page
        self._apply_result_to_ui(result)
        self.data_loaded.emit(result)
        return result

    def _apply_result_to_ui(self, result: PaginatedTransactionsResult) -> None:
        """Menerapkan hasil query ke kartu statistik, tabel transaksi, dan paginasi.

        Args:
            result: Objek hasil paginasi dari RiwayatRepository.
        """
        summary = result.summary
        self._page.set_summary_values(
            total_transaksi=format_integer(summary.total_transactions),
            total_revenue=format_rupiah(summary.total_revenue),
            rata_rata=format_rupiah(summary.average_transaction),
        )
        self._page.card_total_transaksi.set_comparison(
            summary.tx_comparison.text,
            summary.tx_comparison.status,
        )
        self._page.card_total_revenue.set_comparison(
            summary.revenue_comparison.text,
            summary.revenue_comparison.status,
        )
        self._page.card_rata_rata.set_comparison(
            summary.average_comparison.text,
            summary.average_comparison.status,
        )

        self._page.set_transactions(result.rows)
        self._page.set_pagination(
            current_page=result.current_page,
            total_pages=result.total_pages,
            total_items=result.total_items,
        )
        has_data = result.total_items > 0
        self._page.export_excel.setEnabled(has_data)
        self._page.export_pdf.setEnabled(has_data)

    def _reset_ui_on_error(self) -> None:
        """Mengembalikan tampilan data ke kondisi kosong aman saat query gagal."""
        self._page.summary_cards.reset_all()
        self._page.table.clear_rows()
        self._page.navigation_page.reset_pagination()
        self._page.export_excel.setEnabled(False)
        self._page.export_pdf.setEnabled(False)

    def _on_filter_requested(self, criteria: object) -> None:
        """Menangani sinyal filter dari tombol Filter atau penekanan tombol Enter.

        Args:
            criteria: Objek kriteria yang dipancarkan oleh FilterBarWidget.
        """
        self._search_timer.stop()
        self._current_page = 1
        resolved_criteria = (
            criteria
            if isinstance(criteria, FilterCriteria)
            else self._page.get_filter_criteria()
        )
        self.load_transactions(criteria=resolved_criteria, page=1)

    def _on_custom_date_changed(self) -> None:
        """Memuat ulang data dari halaman pertama saat rentang tanggal kustom diterapkan."""
        self._search_timer.stop()
        self._current_page = 1
        self.load_transactions(page=1)

    def _on_search_text_changed(self, _text: str) -> None:
        """Memulai ulang timer debounce ketika teks pencarian berubah."""
        self._search_timer.start()

    def _on_search_timeout(self) -> None:
        """Menjalankan pencarian ke database setelah pengguna berhenti mengetik."""
        self._current_page = 1
        self.load_transactions(page=1)

    def _on_page_changed(self, page: int) -> None:
        """Memuat data transaksi untuk nomor halaman yang dipilih pengguna.

        Args:
            page: Nomor halaman tujuan dari PaginationWidget.
        """
        self._current_page = max(1, page)
        self.load_transactions(page=self._current_page)

    def get_transaction_detail(
        self,
        invoice_number: str,
    ) -> TransactionFullDetail | None:
        """Mengambil detail transaksi lengkap berdasarkan nomor faktur.

        Args:
            invoice_number: Nomor faktur yang ingin diambil detailnya.

        Returns:
            Objek TransactionFullDetail jika ditemukan, atau None jika gagal/tidak ada.
        """
        try:
            detail = self._repository.fetch_transaction_detail(invoice_number)
        except (FileNotFoundError, sqlite3.Error) as exc:
            logger.exception(
                "Gagal mengambil detail transaksi untuk invoice %s",
                invoice_number,
            )
            self._notify_error(
                "Gagal Memuat Detail",
                f"Terjadi kesalahan saat membaca detail invoice {invoice_number}: {exc}",
            )
            return None

        if detail is None:
            self._notify_error(
                "Data Tidak Ditemukan",
                f"Transaksi dengan nomor invoice '{invoice_number}' tidak ditemukan.",
            )
            return None
        return detail

    def _on_detail_requested(self, invoice_number: str) -> None:
        """Mengambil detail transaksi lalu memancarkan sinyal detail_loaded.

        Args:
            invoice_number: Nomor faktur dari baris tabel yang diklik.
        """
        detail = self.get_transaction_detail(invoice_number)
        if detail is not None:
            self.detail_loaded.emit(detail)

    def _on_print_requested(self, invoice_number: str) -> None:
        """Mengambil detail transaksi lalu memancarkan sinyal print_data_ready.

        Args:
            invoice_number: Nomor faktur dari baris tabel yang diklik.
        """
        detail = self.get_transaction_detail(invoice_number)
        if detail is not None:
            self.print_data_ready.emit(detail)

    def export_excel(self, output_path: Path | None = None) -> Path | None:
        """Mengekspor seluruh transaksi terfilter saat ini ke file Excel (.xlsx).

        Args:
            output_path: Path file tujuan opsional. Jika None, akan membuka dialog
                penyimpanan file untuk dipilih pengguna.

        Returns:
            Path file Excel hasil ekspor, atau None jika dibatalkan atau gagal.
        """
        return self._run_export(export_format="excel", output_path=output_path)

    def export_pdf(self, output_path: Path | None = None) -> Path | None:
        """Mengekspor seluruh transaksi terfilter saat ini ke file PDF (.pdf).

        Args:
            output_path: Path file tujuan opsional. Jika None, akan membuka dialog
                penyimpanan file untuk dipilih pengguna.

        Returns:
            Path file PDF hasil ekspor, atau None jika dibatalkan atau gagal.
        """
        return self._run_export(export_format="pdf", output_path=output_path)

    def _run_export(
        self,
        export_format: str,
        output_path: Path | None,
    ) -> Path | None:
        """Menjalankan alur umum pengambilan data penuh dan ekspor dokumen laporan.

        Args:
            export_format: Jenis format ekspor ('excel' atau 'pdf').
            output_path: Path tujuan opsional; dialog file dibuka jika bernilai None.

        Returns:
            Path file hasil ekspor apabila sukses, atau None jika batal/gagal.
        """
        try:
            report = self._repository.fetch_all_filtered(
                self._page.get_filter_criteria()
            )
        except (FileNotFoundError, sqlite3.Error) as exc:
            logger.exception("Gagal mengambil data ekspor riwayat transaksi")
            self._notify_error(
                "Gagal Ekspor",
                f"Tidak dapat membaca data transaksi untuk diekspor: {exc}",
            )
            return None

        if not report.rows:
            self._notify_error(
                "Data Kosong",
                "Tidak ada data transaksi pada filter saat ini untuk diekspor.",
            )
            return None

        target_path = output_path or self._prompt_export_path(export_format)
        if target_path is None:
            return None

        try:
            saved_path = (
                self._exporter.export_excel(target_path, report)
                if export_format == "excel"
                else self._exporter.export_pdf(target_path, report)
            )
        except (OSError, RuntimeError, ValueError) as exc:
            logger.exception("Gagal mengekspor laporan ke format %s", export_format)
            self._notify_error(
                "Gagal Ekspor",
                f"Proses ekspor {export_format.upper()} gagal: {exc}",
            )
            return None

        self.export_succeeded.emit(export_format, str(saved_path))
        if self._show_dialogs:
            QMessageBox.information(
                self._page,
                "Ekspor Berhasil",
                f"Laporan {export_format.upper()} berhasil disimpan ke:\n{saved_path}",
            )
        return saved_path

    def _prompt_export_path(self, export_format: str) -> Path | None:
        """Membuka dialog penyimpanan file bagi pengguna untuk memilih lokasi ekspor.

        Args:
            export_format: Jenis format ekspor ('excel' atau 'pdf').

        Returns:
            Objek Path pilihan pengguna, atau None jika pengguna membatalkan dialog.
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        if export_format == "excel":
            default_name = f"riwayat_transaksi_{timestamp}.xlsx"
            file_filter = "Excel Workbook (*.xlsx)"
            caption = "Simpan Laporan Excel"
        else:
            default_name = f"riwayat_transaksi_{timestamp}.pdf"
            file_filter = "Dokumen PDF (*.pdf)"
            caption = "Simpan Laporan PDF"

        selected_file, _ = QFileDialog.getSaveFileName(
            self._page,
            caption,
            str(Path.home() / default_name),
            file_filter,
        )
        if not selected_file.strip():
            return None
        return Path(selected_file)

    def _notify_error(self, title: str, message: str) -> None:
        """Memancarkan sinyal kesalahan dan menampilkan kotak dialog jika diaktifkan.

        Args:
            title: Judul pesan kesalahan.
            message: Uraian singkat penyebab kesalahan.
        """
        self.error_occurred.emit(title, message)
        if self._show_dialogs:
            QMessageBox.warning(self._page, title, message)