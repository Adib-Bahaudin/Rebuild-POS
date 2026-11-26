"""Utilitas pemformatan nominal mata uang Rupiah."""

from __future__ import annotations


def format_rupiah(amount: int, show_sign: bool = False) -> str:
    """Memformat nominal integer menjadi string mata uang Rupiah.

    Args:
        amount: Nilai nominal dalam satuan Rupiah bulat.
        show_sign: Jika True, nilai positif diberi tanda '+' di depan Rupiah.

    Returns:
        String nominal terformat, misalnya 'Rp 15.000', '-Rp 500', atau '+Rp 200'.
    """
    formatted_abs = f"{abs(amount):,}".replace(",", ".")
    if amount < 0:
        return f"-Rp {formatted_abs}"
    if amount > 0 and show_sign:
        return f"+Rp {formatted_abs}"
    return f"Rp {formatted_abs}"
