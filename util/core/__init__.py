"""Paket bridge/binder penghubung antara antarmuka UI dan modul backend."""

from __future__ import annotations

from util.core.dashboard_transaksi_helper import (
    DashboardTransaksiHelper,
    bind_dashboard_to_backend,
    create_connected_dashboard,
)
from util.core.relasi_helper import (
    RelasiHelper,
    bind_relasi_to_backend,
    create_connected_relasi_page,
    create_connected_relasi_window,
)
from util.core.riwayat_transaksi_helper import (
    RiwayatTransaksiHelper,
    TransactionDetailDialog,
    bind_riwayat_to_backend,
    create_connected_riwayat_page,
    create_connected_riwayat_window,
)
from util.core.tambah_stok import (
    bind_tambah_stok_backend,
    create_connected_tambah_stok_page,
    create_connected_tambah_stok_window,
)

__all__ = [
    "DashboardTransaksiHelper",
    "bind_dashboard_to_backend",
    "create_connected_dashboard",
    "RelasiHelper",
    "bind_relasi_to_backend",
    "create_connected_relasi_page",
    "create_connected_relasi_window",
    "RiwayatTransaksiHelper",
    "TransactionDetailDialog",
    "bind_riwayat_to_backend",
    "create_connected_riwayat_page",
    "create_connected_riwayat_window",
    "bind_tambah_stok_backend",
    "create_connected_tambah_stok_page",
    "create_connected_tambah_stok_window",
]
