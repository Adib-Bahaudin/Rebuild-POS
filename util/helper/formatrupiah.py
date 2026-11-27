"""Utilitas pemformatan nominal angka, kuantitas, dan mata uang Rupiah."""

from __future__ import annotations


def format_ribuan(amount: int | float) -> str:
    """Memformat angka bulat menjadi string dengan pemisah ribuan titik.

    Args:
        amount: Nilai numerik yang akan diformat.

    Returns:
        String angka dengan pemisah ribuan titik, misalnya '15.000'.
    """
    return f"{int(amount):,}".replace(",", ".")


def format_rupiah(amount: int | float, show_sign: bool = False) -> str:
    """Memformat nominal angka menjadi string mata uang Rupiah.

    Args:
        amount: Nilai nominal dalam satuan Rupiah bulat atau desimal.
        show_sign: Jika True, nilai positif diberi tanda '+' di depan Rupiah.

    Returns:
        String nominal terformat, misalnya 'Rp 15.000', '-Rp 500', atau '+Rp 200'.
    """
    rounded = int(round(amount))
    formatted_abs = format_ribuan(abs(rounded))
    if rounded < 0:
        return f"-Rp {formatted_abs}"
    if rounded > 0 and show_sign:
        return f"+Rp {formatted_abs}"
    return f"Rp {formatted_abs}"


def format_qty(value: float, symbol: str = "") -> str:
    """Memformat angka kuantitas agar ringkas tanpa nol desimal berlebih.

    Args:
        value: Nilai kuantitas bertipe float.
        symbol: Simbol satuan opsional seperti 'Lbr' atau 'Pcs'.

    Returns:
        String kuantitas terformat dengan pemisah ribuan titik dan koma desimal.
    """
    if abs(value - round(value)) < 1e-6:
        num_str = format_ribuan(int(round(value)))
    else:
        num_str = f"{value:,.2f}".rstrip("0").rstrip(".")
        num_str = num_str.replace(",", "_").replace(".", ",").replace("_", ".")
    clean_symbol = symbol.strip()
    return f"{num_str} {clean_symbol}" if clean_symbol else num_str
