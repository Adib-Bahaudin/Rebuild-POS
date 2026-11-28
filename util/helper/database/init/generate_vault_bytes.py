"""Utilitas pembangkit bahan kunci ter-XOR dan Recovery Key SQLCipher."""

import hashlib
import secrets


def format_byte_list(data: bytes) -> str:
    """Memformat objek bytes menjadi representasi daftar heksadesimal Python.

    Args:
        data: Urutan byte yang akan diformat.

    Returns:
        String daftar literal heksadesimal yang siap disalin ke kode sumber.
    """
    return ", ".join(f"0x{byte:02X}" for byte in data)


def generate_vault_material() -> None:
    """Membangkitkan mask, potongan kunci ter-XOR, salt ter-XOR, dan Recovery Key."""
    mask = secrets.randbelow(254) + 1
    seed = secrets.token_bytes(16)
    salt = secrets.token_bytes(16)

    masked_part_a = bytes(byte ^ mask for byte in seed[:8])
    masked_part_b = bytes(byte ^ mask for byte in seed[8:])
    masked_salt = bytes(byte ^ mask for byte in salt)

    recovery_hex_key = hashlib.pbkdf2_hmac(
        hash_name="sha512",
        password=seed,
        salt=salt,
        iterations=256000,
        dklen=32,
    ).hex()

    print(f"_MASK = 0x{mask:02X}")
    print(f"_PART_A = bytes([{format_byte_list(masked_part_a)}])")
    print(f"_PART_B = bytes([{format_byte_list(masked_part_b)}])")
    print(f"_SALT_MASKED = bytes([{format_byte_list(masked_salt)}])")
    print(f"\nRECOVERY_KEY_HEX (simpan luring): {recovery_hex_key}")


if __name__ == "__main__":
    generate_vault_material()