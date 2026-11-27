"""Utilitas terpusat untuk pembuatan koneksi database SQLite.

Modul ini menyediakan factory fungsi pembuka koneksi SQLite yang konsisten
dengan pengaturan foreign keys, row factory, dan mode WAL opsional.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path


def create_sqlite_connection(
    db_path: Path,
    *,
    require_exists: bool = True,
    row_factory: bool = True,
    foreign_keys: bool = True,
    wal_mode: bool = False,
) -> sqlite3.Connection:
    """Membuka koneksi SQLite baru dengan konfigurasi standar aplikasi.

    Args:
        db_path: Lokasi file database SQLite target.
        require_exists: Jika True, memvalidasi bahwa file database sudah ada.
        row_factory: Jika True, mengaktifkan sqlite3.Row sebagai row_factory.
        foreign_keys: Jika True, mengaktifkan PRAGMA foreign_keys = ON.
        wal_mode: Jika True, mengaktifkan PRAGMA journal_mode = WAL.

    Returns:
        Objek koneksi sqlite3.Connection yang siap digunakan.

    Raises:
        FileNotFoundError: Jika require_exists bernilai True dan file tidak ditemukan.
    """
    if require_exists and (not db_path.exists() or not db_path.is_file()):
        raise FileNotFoundError(
            f"File database tidak ditemukan di: {db_path.resolve()}"
        )

    conn = sqlite3.connect(db_path)
    if row_factory:
        conn.row_factory = sqlite3.Row
    if foreign_keys:
        conn.execute("PRAGMA foreign_keys = ON;")
    if wal_mode:
        conn.execute("PRAGMA journal_mode = WAL;")
    return conn
