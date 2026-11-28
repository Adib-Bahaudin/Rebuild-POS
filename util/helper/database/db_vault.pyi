"""Definisi tipe statis untuk modul biner database.db_vault."""

from pathlib import Path
from typing import Any


def open_secure_connection(db_path: Path) -> Any:
    """Membuka koneksi SQLCipher terverifikasi tanpa mengembalikan nilai kunci.

    Args:
        db_path: Lokasi file database SQLCipher.

    Returns:
        Objek koneksi database SQLCipher yang aktif.
    """