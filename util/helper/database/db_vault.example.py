"""Templat modul brankas kunci database untuk repositori Git.

Salin file ini menjadi database/db_vault.pyx, ganti seluruh nilai byte dengan hasil
dari tools/generate_vault_bytes.py, ubah def _assemble_raw_hex_key menjadi cdef str,
lalu kompilasi menggunakan setup_vault.py.
"""

import hashlib
from pathlib import Path
from typing import Any

from sqlcipher3 import dbapi2 as sqlcipher

_MASK = 0x00
_PART_A = bytes([0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00])
_PART_B = bytes([0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00])
_SALT_MASKED = bytes([
    0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
    0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
])


def _assemble_raw_hex_key() -> str:
    """Merakit bahan kunci ter-XOR dan menurunkannya menjadi kunci AES-256.

    Returns:
        String heksadesimal 64 karakter untuk PRAGMA key SQLCipher.
    """
    seed = bytes(byte ^ _MASK for byte in (_PART_A + _PART_B))
    salt = bytes(byte ^ _MASK for byte in _SALT_MASKED)
    raw_key = hashlib.pbkdf2_hmac(
        hash_name="sha512",
        password=seed,
        salt=salt,
        iterations=256000,
        dklen=32,
    )
    return raw_key.hex()


def open_secure_connection(db_path: Path) -> Any:
    """Membuka koneksi SQLCipher terverifikasi tanpa mengembalikan nilai kunci.

    Args:
        db_path: Lokasi file database SQLCipher.

    Returns:
        Objek koneksi database SQLCipher yang aktif.

    Raises:
        RuntimeError: Jika dekripsi database gagal saat verifikasi skema.
    """
    hex_key = _assemble_raw_hex_key()
    conn = sqlcipher.connect(str(db_path))
    try:
        conn.execute(f"PRAGMA key = \"x'{hex_key}'\";")
        conn.execute("PRAGMA cipher_compatibility = 4;")
        conn.execute("SELECT count(*) FROM sqlite_master;").fetchone()
    except sqlcipher.DatabaseError as exc:
        conn.close()
        raise RuntimeError("Gagal membuka koneksi database terenkripsi.") from exc
    return conn