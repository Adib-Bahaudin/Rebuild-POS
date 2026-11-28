"""Utilitas terpusat untuk pembuatan koneksi database SQLCipher.

Modul ini menyediakan factory fungsi pembuka koneksi database terenkripsi
yang konsisten dengan pengaturan foreign keys, row factory, dan mode WAL
opsional melalui modul brankas terkompilasi.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, cast

from sqlcipher3 import dbapi2 as sqlcipher

from util.helper.database.db_vault import open_secure_connection


def create_sqlite_connection(
    db_path: Path,
    *,
    require_exists: bool = True,
    row_factory: bool = True,
    foreign_keys: bool = True,
    wal_mode: bool = False,
) -> sqlcipher.Connection:
    """Membuka koneksi SQLCipher baru dengan konfigurasi standar aplikasi.

    Args:
        db_path: Lokasi file database SQLCipher target.
        require_exists: Jika True, memvalidasi bahwa file database sudah ada.
        row_factory: Jika True, mengaktifkan sqlcipher.Row sebagai row_factory.
        foreign_keys: Jika True, mengaktifkan PRAGMA foreign_keys = ON.
        wal_mode: Jika True, mengaktifkan PRAGMA journal_mode = WAL.

    Returns:
        Objek koneksi database terenkripsi sqlcipher.Connection.

    Raises:
        FileNotFoundError: Jika require_exists bernilai True dan file tidak
            ditemukan.
        RuntimeError: Jika dekripsi database gagal saat verifikasi skema.
    """
    if require_exists and (not db_path.exists() or not db_path.is_file()):
        raise FileNotFoundError(
            f"File database tidak ditemukan di: {db_path.resolve()}"
        )

    if not require_exists:
        db_path.parent.mkdir(parents=True, exist_ok=True)

    conn: Any = open_secure_connection(db_path)
    if row_factory:
        conn.row_factory = sqlcipher.Row
    if foreign_keys:
        conn.execute("PRAGMA foreign_keys = ON;")
    if wal_mode:
        conn.execute("PRAGMA journal_mode = WAL;")
    return cast(sqlcipher.Connection, conn)