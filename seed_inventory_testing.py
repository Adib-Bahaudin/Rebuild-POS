"""Modul seeder data inventaris dan jasa untuk pengujian transaksi penjualan.

Modul ini mengisi database SQLite yang diinisialisasi oleh
TransaksiDatabaseInitializer dengan 55+ data barang (komposisi satuan dan
multi-satuan/pack), 13 layanan jasa beserta resep bahan bakunya, serta saldo
stok awal pada tabel inventory_layers dan stock_movements untuk pengujian FIFO.
"""

from __future__ import annotations

from sqlcipher3 import dbapi2 as sqlite3
import sys
from pathlib import Path
from typing import Any, Optional

from config import DEFAULT_DB_PATH
from util.helper.database.init.inittransaksidatabase import TransaksiDatabaseInitializer
from util.helper.database.db_connection import create_sqlite_connection


CATEGORIES_DATA: list[str] = [
    "Kertas & Media Cetak",
    "Alat Tulis",
    "Buku & Kertas Tulis",
    "Map & Pengarsipan",
    "Perekat & Pemotong",
    "Perlengkapan Jilid & Laminating",
    "Perlengkapan Kantor & Sekolah",
]

UNITS_DATA: list[tuple[str, str]] = [
    ("Lembar", "lbr"),
    ("Pcs", "pcs"),
    ("Roll", "roll"),
    ("Botol", "btl"),
    ("Pack", "pack"),
    ("Lusin", "lsn"),
    ("Rim", "rim"),
    ("Box", "box"),
    ("Dus", "dus"),
]

SUPPLIERS_DATA: list[tuple[str, str, str]] = [
    ("CV Mitra Kertas Nusantara", "081234567801", "Jl. Pemuda No. 45, Magelang"),
    ("UD Sumber ATK Grosir", "081234567802", "Jl. Tentara Pelajar No. 12, Yogyakarta"),
]

CUSTOMERS_DATA: list[tuple[str, str, str]] = [
    ("Pelanggan Umum", "-", "-"),
    ("SMK Harapan Bangsa", "081298765432", "Jl. Pendidikan No. 8, Muntilan"),
]

ITEMS_DATA: list[dict[str, Any]] = [
    {
        "sku": "ATK-KRT-001",
        "name": "Kertas HVS A4 70gsm",
        "category": "Kertas & Media Cetak",
        "base_unit": "lbr",
        "description": "Kertas HVS putih ukuran A4 ketebalan 70gsm",
        "variants": [
            ("lbr", "Lembar", 1, 200, 1),
            ("rim", "Rim (500 Lbr)", 500, 48000, 0),
            ("dus", "Dus (5 Rim)", 2500, 230000, 0),
        ],
        "layers": [
            (2500, 82.0, "2026-11-01 08:00:00"),
            (2500, 86.0, "2026-11-10 09:00:00"),
        ],
    },
    {
        "sku": "ATK-KRT-002",
        "name": "Kertas HVS A4 80gsm",
        "category": "Kertas & Media Cetak",
        "base_unit": "lbr",
        "description": "Kertas HVS putih ukuran A4 ketebalan 80gsm",
        "variants": [
            ("lbr", "Lembar", 1, 250, 1),
            ("rim", "Rim (500 Lbr)", 500, 56000, 0),
        ],
        "layers": [(1500, 98.0, "2026-11-02 08:00:00")],
    },
    {
        "sku": "ATK-KRT-003",
        "name": "Kertas HVS F4 70gsm",
        "category": "Kertas & Media Cetak",
        "base_unit": "lbr",
        "description": "Kertas HVS putih ukuran F4/Folio ketebalan 70gsm",
        "variants": [
            ("lbr", "Lembar", 1, 250, 1),
            ("rim", "Rim (500 Lbr)", 500, 54000, 0),
            ("dus", "Dus (5 Rim)", 2500, 260000, 0),
        ],
        "layers": [
            (2000, 92.0, "2026-11-01 08:30:00"),
            (2000, 96.0, "2026-11-12 10:00:00"),
        ],
    },
    {
        "sku": "ATK-KRT-004",
        "name": "Kertas HVS F4 80gsm",
        "category": "Kertas & Media Cetak",
        "base_unit": "lbr",
        "description": "Kertas HVS putih ukuran F4/Folio ketebalan 80gsm",
        "variants": [
            ("lbr", "Lembar", 1, 300, 1),
            ("rim", "Rim (500 Lbr)", 500, 62000, 0),
        ],
        "layers": [(1000, 108.0, "2026-11-02 08:30:00")],
    },
    {
        "sku": "ATK-KRT-005",
        "name": "Kertas Foto Glossy A4 230gsm",
        "category": "Kertas & Media Cetak",
        "base_unit": "lbr",
        "description": "Kertas cetak foto mengkilap A4",
        "variants": [
            ("lbr", "Lembar", 1, 2000, 1),
            ("pack", "Pack (20 Lbr)", 20, 32000, 0),
        ],
        "layers": [(200, 1200.0, "2026-11-03 08:00:00")],
    },
    {
        "sku": "ATK-KRT-006",
        "name": "Kertas Foto Silky Doff A4 260gsm",
        "category": "Kertas & Media Cetak",
        "base_unit": "lbr",
        "description": "Kertas cetak foto tekstur kulit jeruk A4",
        "variants": [
            ("lbr", "Lembar", 1, 2500, 1),
            ("pack", "Pack (20 Lbr)", 20, 42000, 0),
        ],
        "layers": [(160, 1650.0, "2026-11-03 08:15:00")],
    },
    {
        "sku": "ATK-KRT-007",
        "name": "Kertas Buffalo Jilid F4 Warna",
        "category": "Kertas & Media Cetak",
        "base_unit": "lbr",
        "description": "Kertas cover jilid bertekstur ukuran F4",
        "variants": [
            ("lbr", "Lembar", 1, 1000, 1),
            ("pack", "Pack (100 Lbr)", 100, 48000, 0),
        ],
        "layers": [(500, 380.0, "2026-11-03 09:00:00")],
    },
    {
        "sku": "ATK-KRT-008",
        "name": "Kertas Concorde A4 220gsm",
        "category": "Kertas & Media Cetak",
        "base_unit": "lbr",
        "description": "Kertas sertifikat bertekstur garis A4",
        "variants": [
            ("lbr", "Lembar", 1, 1500, 1),
            ("pack", "Pack (20 Lbr)", 20, 24000, 0),
        ],
        "layers": [(200, 900.0, "2026-11-03 09:15:00")],
    },
    {
        "sku": "ATK-KRT-009",
        "name": "Kertas Stiker Glossy A4",
        "category": "Kertas & Media Cetak",
        "base_unit": "lbr",
        "description": "Kertas stiker putih glossy untuk printer inkjet",
        "variants": [
            ("lbr", "Lembar", 1, 2000, 1),
            ("pack", "Pack (20 Lbr)", 20, 30000, 0),
        ],
        "layers": [(200, 1100.0, "2026-11-03 09:30:00")],
    },
    {
        "sku": "ATK-KRT-010",
        "name": "Kertas Art Paper A4 150gsm",
        "category": "Kertas & Media Cetak",
        "base_unit": "lbr",
        "description": "Kertas brosur licin dua sisi ukuran A4",
        "variants": [
            ("lbr", "Lembar", 1, 1000, 1),
            ("pack", "Pack (50 Lbr)", 50, 38000, 0),
        ],
        "layers": [(300, 550.0, "2026-11-03 09:45:00")],
    },
    {
        "sku": "ATK-TLS-001",
        "name": "Pulpen Standard AE7 Hitam",
        "category": "Alat Tulis",
        "base_unit": "pcs",
        "description": "Pulpen tinta minyak 0.5mm warna hitam",
        "variants": [
            ("pcs", "Pcs", 1, 2500, 1),
            ("lsn", "Lusin (12 Pcs)", 12, 24000, 0),
        ],
        "layers": [
            (60, 1500.0, "2026-11-01 10:00:00"),
            (60, 1650.0, "2026-11-11 10:00:00"),
        ],
    },
    {
        "sku": "ATK-TLS-002",
        "name": "Pulpen Standard AE7 Biru",
        "category": "Alat Tulis",
        "base_unit": "pcs",
        "description": "Pulpen tinta minyak 0.5mm warna biru",
        "variants": [
            ("pcs", "Pcs", 1, 2500, 1),
            ("lsn", "Lusin (12 Pcs)", 12, 24000, 0),
        ],
        "layers": [(72, 1550.0, "2026-11-02 10:00:00")],
    },
    {
        "sku": "ATK-TLS-003",
        "name": "Pulpen Joyko Gel GP-265 Hitam",
        "category": "Alat Tulis",
        "base_unit": "pcs",
        "description": "Pulpen gel cetak 0.5mm warna hitam",
        "variants": [
            ("pcs", "Pcs", 1, 3500, 1),
            ("box", "Box (12 Pcs)", 12, 36000, 0),
        ],
        "layers": [(60, 2300.0, "2026-11-02 10:15:00")],
    },
    {
        "sku": "ATK-TLS-004",
        "name": "Pulpen Snowman V5 0.7mm Hitam",
        "category": "Alat Tulis",
        "base_unit": "pcs",
        "description": "Pulpen retractable tinta hitam 0.7mm",
        "variants": [
            ("pcs", "Pcs", 1, 4000, 1),
            ("lsn", "Lusin (12 Pcs)", 12, 42000, 0),
        ],
        "layers": [(48, 2800.0, "2026-11-02 10:30:00")],
    },
    {
        "sku": "ATK-TLS-005",
        "name": "Pensil 2B Faber-Castell",
        "category": "Alat Tulis",
        "base_unit": "pcs",
        "description": "Pensil ujian 2B standar komputer",
        "variants": [
            ("pcs", "Pcs", 1, 5000, 1),
            ("lsn", "Lusin (12 Pcs)", 12, 52000, 0),
        ],
        "layers": [(72, 3500.0, "2026-11-02 11:00:00")],
    },
    {
        "sku": "ATK-TLS-006",
        "name": "Pensil 2B Staedtler Mars Lumograph",
        "category": "Alat Tulis",
        "base_unit": "pcs",
        "description": "Pensil gambar dan ujian 2B biru",
        "variants": [
            ("pcs", "Pcs", 1, 5500, 1),
            ("lsn", "Lusin (12 Pcs)", 12, 58000, 0),
        ],
        "layers": [(48, 3900.0, "2026-11-02 11:15:00")],
    },
    {
        "sku": "ATK-TLS-007",
        "name": "Penghapus Pensil Faber-Castell Kecil",
        "category": "Alat Tulis",
        "base_unit": "pcs",
        "description": "Penghapus karet dust-free ukuran kecil",
        "variants": [
            ("pcs", "Pcs", 1, 3000, 1),
            ("box", "Box (40 Pcs)", 40, 96000, 0),
        ],
        "layers": [(80, 1900.0, "2026-11-02 11:30:00")],
    },
    {
        "sku": "ATK-TLS-008",
        "name": "Correction Tape Joyko CT-522",
        "category": "Alat Tulis",
        "base_unit": "pcs",
        "description": "Tipe-X kertas gulung panjang 12m",
        "variants": [
            ("pcs", "Pcs", 1, 6000, 1),
            ("pack", "Pack (12 Pcs)", 12, 62000, 0),
        ],
        "layers": [(48, 4100.0, "2026-11-02 11:45:00")],
    },
    {
        "sku": "ATK-TLS-009",
        "name": "Spidol Whiteboard Snowman Hitam",
        "category": "Alat Tulis",
        "base_unit": "pcs",
        "description": "Spidol papan tulis mudah dihapus BG-12",
        "variants": [
            ("pcs", "Pcs", 1, 9000, 1),
            ("lsn", "Lusin (12 Pcs)", 12, 96000, 0),
        ],
        "layers": [(36, 6800.0, "2026-11-03 10:00:00")],
    },
    {
        "sku": "ATK-TLS-010",
        "name": "Spidol Permanen Snowman G-12 Hitam",
        "category": "Alat Tulis",
        "base_unit": "pcs",
        "description": "Spidol tinta permanen warna hitam",
        "variants": [
            ("pcs", "Pcs", 1, 8500, 1),
            ("lsn", "Lusin (12 Pcs)", 12, 90000, 0),
        ],
        "layers": [(36, 6300.0, "2026-11-03 10:15:00")],
    },
    {
        "sku": "ATK-TLS-011",
        "name": "Stabilo Boss Original Kuning",
        "category": "Alat Tulis",
        "base_unit": "pcs",
        "description": "Penanda teks highlighter warna kuning neon",
        "variants": [
            ("pcs", "Pcs", 1, 11000, 1),
            ("box", "Box (10 Pcs)", 10, 98000, 0),
        ],
        "layers": [(30, 8200.0, "2026-11-03 10:30:00")],
    },
    {
        "sku": "ATK-TLS-012",
        "name": "Penggaris Plastik Butterfly 30cm",
        "category": "Alat Tulis",
        "base_unit": "pcs",
        "description": "Penggaris mika bening 30cm",
        "variants": [
            ("pcs", "Pcs", 1, 3500, 1),
            ("lsn", "Lusin (12 Pcs)", 12, 34000, 0),
        ],
        "layers": [(48, 2100.0, "2026-11-03 10:45:00")],
    },
    {
        "sku": "ATK-BKU-001",
        "name": "Buku Tulis SiDU 38 Lembar",
        "category": "Buku & Kertas Tulis",
        "base_unit": "pcs",
        "description": "Buku tulis sekolah isi 38 lembar",
        "variants": [
            ("pcs", "Pcs", 1, 4000, 1),
            ("pack", "Pack (10 Buku)", 10, 35000, 0),
        ],
        "layers": [
            (50, 2700.0, "2026-11-01 11:00:00"),
            (50, 2900.0, "2026-11-12 11:00:00"),
        ],
    },
    {
        "sku": "ATK-BKU-002",
        "name": "Buku Tulis SiDU 58 Lembar",
        "category": "Buku & Kertas Tulis",
        "base_unit": "pcs",
        "description": "Buku tulis sekolah isi 58 lembar",
        "variants": [
            ("pcs", "Pcs", 1, 5500, 1),
            ("pack", "Pack (10 Buku)", 10, 49000, 0),
        ],
        "layers": [(60, 4100.0, "2026-11-02 12:00:00")],
    },
    {
        "sku": "ATK-BKU-003",
        "name": "Buku Tulis Campus Big Boss 50 Lembar",
        "category": "Buku & Kertas Tulis",
        "base_unit": "pcs",
        "description": "Buku tulis ukuran B5 boxy 50 lembar",
        "variants": [
            ("pcs", "Pcs", 1, 6000, 1),
            ("pack", "Pack (6 Buku)", 6, 33000, 0),
        ],
        "layers": [(48, 4500.0, "2026-11-02 12:15:00")],
    },
    {
        "sku": "ATK-BKU-004",
        "name": "Buku Gambar A4 SiDU",
        "category": "Buku & Kertas Tulis",
        "base_unit": "pcs",
        "description": "Buku gambar polos ukuran A4",
        "variants": [
            ("pcs", "Pcs", 1, 4500, 1),
            ("pack", "Pack (5 Buku)", 5, 20000, 0),
        ],
        "layers": [(40, 3100.0, "2026-11-02 12:30:00")],
    },
    {
        "sku": "ATK-BKU-005",
        "name": "Buku Gambar A3 SiDU",
        "category": "Buku & Kertas Tulis",
        "base_unit": "pcs",
        "description": "Buku gambar polos ukuran A3",
        "variants": [
            ("pcs", "Pcs", 1, 8000, 1),
            ("pack", "Pack (5 Buku)", 5, 36000, 0),
        ],
        "layers": [(30, 5800.0, "2026-11-02 12:45:00")],
    },
    {
        "sku": "ATK-BKU-006",
        "name": "Kertas Folio Bergaris Double",
        "category": "Buku & Kertas Tulis",
        "base_unit": "lbr",
        "description": "Kertas folio bergaris lipat dua",
        "variants": [
            ("lbr", "Lembar", 1, 500, 1),
            ("pack", "Pack (100 Lbr)", 100, 32000, 0),
        ],
        "layers": [(500, 240.0, "2026-11-03 11:00:00")],
    },
    {
        "sku": "ATK-BKU-007",
        "name": "Buku Nota Kontan 2 Ply Kecil",
        "category": "Buku & Kertas Tulis",
        "base_unit": "pcs",
        "description": "Nota kontan rangkap dua ukuran kecil",
        "variants": [
            ("pcs", "Pcs", 1, 4500, 1),
            ("pack", "Pack (10 Buku)", 10, 38000, 0),
        ],
        "layers": [(40, 3000.0, "2026-11-03 11:15:00")],
    },
    {
        "sku": "ATK-BKU-008",
        "name": "Buku Kwitansi Besar Sinar Dunia",
        "category": "Buku & Kertas Tulis",
        "base_unit": "pcs",
        "description": "Buku bukti pembayaran ukuran besar",
        "variants": [
            ("pcs", "Pcs", 1, 6500, 1),
            ("pack", "Pack (10 Buku)", 10, 58000, 0),
        ],
        "layers": [(30, 4800.0, "2026-11-03 11:30:00")],
    },
    {
        "sku": "ATK-MAP-001",
        "name": "Stopmap Kertas Folio Warna",
        "category": "Map & Pengarsipan",
        "base_unit": "pcs",
        "description": "Map kertas standar ukuran folio",
        "variants": [
            ("pcs", "Pcs", 1, 1500, 1),
            ("pack", "Pack (50 Pcs)", 50, 45000, 0),
        ],
        "layers": [(200, 700.0, "2026-11-03 12:00:00")],
    },
    {
        "sku": "ATK-MAP-002",
        "name": "Map Plastik L Clear Holder F4",
        "category": "Map & Pengarsipan",
        "base_unit": "pcs",
        "description": "Map plastik transparan model L ukuran F4",
        "variants": [
            ("pcs", "Pcs", 1, 2000, 1),
            ("lsn", "Lusin (12 Pcs)", 12, 20000, 0),
        ],
        "layers": [(120, 1200.0, "2026-11-03 12:15:00")],
    },
    {
        "sku": "ATK-MAP-003",
        "name": "Map Plastik Kancing F4",
        "category": "Map & Pengarsipan",
        "base_unit": "pcs",
        "description": "Map plastik berkancing satu ukuran F4",
        "variants": [
            ("pcs", "Pcs", 1, 3500, 1),
            ("lsn", "Lusin (12 Pcs)", 12, 36000, 0),
        ],
        "layers": [(72, 2300.0, "2026-11-03 12:30:00")],
    },
    {
        "sku": "ATK-MAP-004",
        "name": "Map Snelhecter Plastik F4",
        "category": "Map & Pengarsipan",
        "base_unit": "pcs",
        "description": "Map plastik berpenjepit tengah untuk kertas berlubang",
        "variants": [
            ("pcs", "Pcs", 1, 3000, 1),
            ("lsn", "Lusin (12 Pcs)", 12, 30000, 0),
        ],
        "layers": [(72, 1900.0, "2026-11-03 12:45:00")],
    },
    {
        "sku": "ATK-MAP-005",
        "name": "Map Bisnis File F4",
        "category": "Map & Pengarsipan",
        "base_unit": "pcs",
        "description": "Map bisnis file sampul depan transparan",
        "variants": [
            ("pcs", "Pcs", 1, 3500, 1),
            ("lsn", "Lusin (12 Pcs)", 12, 36000, 0),
        ],
        "layers": [(72, 2200.0, "2026-11-04 08:00:00")],
    },
    {
        "sku": "ATK-MAP-006",
        "name": "Amplop Putih Polos 90 PPS",
        "category": "Map & Pengarsipan",
        "base_unit": "pcs",
        "description": "Amplop putih berperekat ukuran panjang",
        "variants": [
            ("pcs", "Pcs", 1, 500, 1),
            ("box", "Box (100 Pcs)", 100, 26000, 0),
        ],
        "layers": [(400, 200.0, "2026-11-04 08:15:00")],
    },
    {
        "sku": "ATK-MAP-007",
        "name": "Amplop Coklat Tali Folio",
        "category": "Map & Pengarsipan",
        "base_unit": "pcs",
        "description": "Amplop lamaran kerja coklat bertali ukuran F4",
        "variants": [
            ("pcs", "Pcs", 1, 2000, 1),
            ("pack", "Pack (10 Pcs)", 10, 16000, 0),
        ],
        "layers": [(100, 1150.0, "2026-11-04 08:30:00")],
    },
    {
        "sku": "ATK-MAP-008",
        "name": "Ordner Bantex Folio 7cm",
        "category": "Map & Pengarsipan",
        "base_unit": "pcs",
        "description": "Map ordner besar punggung 7cm (satuan murni)",
        "variants": [
            ("pcs", "Pcs", 1, 32000, 1),
        ],
        "layers": [(20, 24500.0, "2026-11-04 08:45:00")],
    },
    {
        "sku": "ATK-PRK-001",
        "name": "Lem Kertas Povinal Kecil 22ml",
        "category": "Perekat & Pemotong",
        "base_unit": "btl",
        "description": "Lem cair bening untuk kertas",
        "variants": [
            ("btl", "Botol", 1, 3000, 1),
            ("lsn", "Lusin (12 Btl)", 12, 30000, 0),
        ],
        "layers": [(48, 1900.0, "2026-11-04 09:00:00")],
    },
    {
        "sku": "ATK-PRK-002",
        "name": "Lem Stick UHU 8.2gr",
        "category": "Perekat & Pemotong",
        "base_unit": "pcs",
        "description": "Lem padat batang tidak mengotori kertas",
        "variants": [
            ("pcs", "Pcs", 1, 10000, 1),
            ("box", "Box (24 Pcs)", 24, 215000, 0),
        ],
        "layers": [(24, 7500.0, "2026-11-04 09:15:00")],
    },
    {
        "sku": "ATK-PRK-003",
        "name": "Lakban Bening Daimaru 48mm",
        "category": "Perekat & Pemotong",
        "base_unit": "roll",
        "description": "Lakban bening packing lebar 2 inch",
        "variants": [
            ("roll", "Roll", 1, 12000, 1),
            ("pack", "Pack (6 Roll)", 6, 66000, 0),
        ],
        "layers": [(36, 8800.0, "2026-11-04 09:30:00")],
    },
    {
        "sku": "ATK-PRK-004",
        "name": "Lakban Hitam Kain Jilid 36mm",
        "category": "Perekat & Pemotong",
        "base_unit": "roll",
        "description": "Lakban kain hitam untuk penjilidan dokumen",
        "variants": [
            ("roll", "Roll", 1, 14000, 1),
            ("pack", "Pack (6 Roll)", 6, 78000, 0),
        ],
        "layers": [(30, 10500.0, "2026-11-04 09:45:00")],
    },
    {
        "sku": "ATK-PRK-005",
        "name": "Double Tape Nachi 12mm",
        "category": "Perekat & Pemotong",
        "base_unit": "roll",
        "description": "Perekat dua sisi lebar 12mm",
        "variants": [
            ("roll", "Roll", 1, 5000, 1),
            ("pack", "Pack (12 Roll)", 12, 52000, 0),
        ],
        "layers": [(48, 3400.0, "2026-11-04 10:00:00")],
    },
    {
        "sku": "ATK-PRK-006",
        "name": "Cutter Joyko L-500 Besar",
        "category": "Perekat & Pemotong",
        "base_unit": "pcs",
        "description": "Pisau pemotong ukuran besar dengan pengunci putar (satuan murni)",
        "variants": [
            ("pcs", "Pcs", 1, 16000, 1),
        ],
        "layers": [(25, 11500.0, "2026-11-04 10:15:00")],
    },
    {
        "sku": "ATK-JLD-001",
        "name": "Plastik Mika Bening Jilid F4",
        "category": "Perlengkapan Jilid & Laminating",
        "base_unit": "lbr",
        "description": "Plastik cover jilid transparan ukuran F4",
        "variants": [
            ("lbr", "Lembar", 1, 1000, 1),
            ("pack", "Pack (100 Lbr)", 100, 42000, 0),
        ],
        "layers": [(500, 320.0, "2026-11-04 10:30:00")],
    },
    {
        "sku": "ATK-JLD-002",
        "name": "Plastik Laminating Film A4 100mic",
        "category": "Perlengkapan Jilid & Laminating",
        "base_unit": "lbr",
        "description": "Plastik laminasi panas ukuran A4",
        "variants": [
            ("lbr", "Lembar", 1, 2000, 1),
            ("pack", "Pack (100 Lbr)", 100, 95000, 0),
        ],
        "layers": [
            (200, 780.0, "2026-11-01 12:00:00"),
            (200, 830.0, "2026-11-12 12:00:00"),
        ],
    },
    {
        "sku": "ATK-JLD-003",
        "name": "Plastik Laminating Film F4 100mic",
        "category": "Perlengkapan Jilid & Laminating",
        "base_unit": "lbr",
        "description": "Plastik laminasi panas ukuran F4/Folio",
        "variants": [
            ("lbr", "Lembar", 1, 2500, 1),
            ("pack", "Pack (100 Lbr)", 100, 115000, 0),
        ],
        "layers": [(300, 950.0, "2026-11-04 10:45:00")],
    },
    {
        "sku": "ATK-JLD-004",
        "name": "Plastik Laminating KTP / ID Card",
        "category": "Perlengkapan Jilid & Laminating",
        "base_unit": "lbr",
        "description": "Plastik laminasi ukuran kartu identitas",
        "variants": [
            ("lbr", "Lembar", 1, 1000, 1),
            ("pack", "Pack (100 Lbr)", 100, 28000, 0),
        ],
        "layers": [(300, 220.0, "2026-11-04 11:00:00")],
    },
    {
        "sku": "ATK-JLD-005",
        "name": "Ring Spiral Plastik Jilid 12mm",
        "category": "Perlengkapan Jilid & Laminating",
        "base_unit": "pcs",
        "description": "Ring jilid spiral plastik kapasitas hingga 80 lembar",
        "variants": [
            ("pcs", "Pcs", 1, 3500, 1),
            ("box", "Box (50 Pcs)", 50, 110000, 0),
        ],
        "layers": [(100, 1800.0, "2026-11-04 11:15:00")],
    },
    {
        "sku": "ATK-JLD-006",
        "name": "Isi Staples Kangaro No. 10",
        "category": "Perlengkapan Jilid & Laminating",
        "base_unit": "box",
        "description": "Isi staples kecil No. 10 per kotak kecil",
        "variants": [
            ("box", "Box Kecil", 1, 3500, 1),
            ("pack", "Pack (20 Box)", 20, 58000, 0),
        ],
        "layers": [(60, 2300.0, "2026-11-04 11:30:00")],
    },
    {
        "sku": "ATK-KTR-001",
        "name": "Stapler Kangaro HD-10",
        "category": "Perlengkapan Kantor & Sekolah",
        "base_unit": "pcs",
        "description": "Alat stapler ukuran kecil seri HD-10 (satuan murni)",
        "variants": [
            ("pcs", "Pcs", 1, 18000, 1),
        ],
        "layers": [(20, 13500.0, "2026-11-04 11:45:00")],
    },
    {
        "sku": "ATK-KTR-002",
        "name": "Gunting Kertas Joyko SC-838 Sedang",
        "category": "Perlengkapan Kantor & Sekolah",
        "base_unit": "pcs",
        "description": "Gunting stainless steel ukuran sedang (satuan murni)",
        "variants": [
            ("pcs", "Pcs", 1, 12000, 1),
        ],
        "layers": [(25, 8500.0, "2026-11-04 12:00:00")],
    },
    {
        "sku": "ATK-KTR-003",
        "name": "Paper Clip Joyko No. 3",
        "category": "Perlengkapan Kantor & Sekolah",
        "base_unit": "box",
        "description": "Penjepit kertas logam ukuran standar",
        "variants": [
            ("box", "Box Kecil", 1, 3000, 1),
            ("pack", "Pack (10 Box)", 10, 25000, 0),
        ],
        "layers": [(50, 1900.0, "2026-11-04 12:15:00")],
    },
    {
        "sku": "ATK-KTR-004",
        "name": "Binder Clip Joyko No. 107",
        "category": "Perlengkapan Kantor & Sekolah",
        "base_unit": "box",
        "description": "Penjepit dokumen hitam ukuran 19mm (isi 12/box)",
        "variants": [
            ("box", "Box (12 Pcs)", 1, 5500, 1),
            ("pack", "Pack (12 Box)", 12, 58000, 0),
        ],
        "layers": [(36, 4000.0, "2026-11-04 12:30:00")],
    },
    {
        "sku": "ATK-KTR-005",
        "name": "Materai 10.000 Resmi",
        "category": "Perlengkapan Kantor & Sekolah",
        "base_unit": "pcs",
        "description": "Materai tempel nominal Rp 10.000 (satuan murni)",
        "variants": [
            ("pcs", "Pcs", 1, 12000, 1),
        ],
        "layers": [(100, 10000.0, "2026-11-04 12:45:00")],
    },
]

SERVICES_DATA: list[dict[str, Any]] = [
    {
        "sku": "SRV-FC-001",
        "name": "Fotokopi Hitam Putih A4",
        "description": "Jasa fotokopi 1 sisi kertas HVS A4 70gsm",
        "selling_price": 300,
        "materials": [("ATK-KRT-001", 1.0)],
    },
    {
        "sku": "SRV-FC-002",
        "name": "Fotokopi Hitam Putih F4",
        "description": "Jasa fotokopi 1 sisi kertas HVS F4 70gsm",
        "selling_price": 350,
        "materials": [("ATK-KRT-003", 1.0)],
    },
    {
        "sku": "SRV-PRT-001",
        "name": "Print Hitam Putih A4",
        "description": "Jasa cetak teks hitam putih kertas HVS A4 70gsm",
        "selling_price": 500,
        "materials": [("ATK-KRT-001", 1.0)],
    },
    {
        "sku": "SRV-PRT-002",
        "name": "Print Warna A4 Standar",
        "description": "Jasa cetak warna standar kertas HVS A4 70gsm",
        "selling_price": 1500,
        "materials": [("ATK-KRT-001", 1.0)],
    },
    {
        "sku": "SRV-PRT-003",
        "name": "Print Hitam Putih F4",
        "description": "Jasa cetak teks hitam putih kertas HVS F4 70gsm",
        "selling_price": 600,
        "materials": [("ATK-KRT-003", 1.0)],
    },
    {
        "sku": "SRV-PRT-004",
        "name": "Print Warna F4 Standar",
        "description": "Jasa cetak warna standar kertas HVS F4 70gsm",
        "selling_price": 2000,
        "materials": [("ATK-KRT-003", 1.0)],
    },
    {
        "sku": "SRV-FTO-001",
        "name": "Cetak Pas Foto Paket (1 Lbr A4 Glossy)",
        "description": "Jasa cetak foto ukuran 3x4 atau 4x6 pada 1 lembar A4 Glossy",
        "selling_price": 10000,
        "materials": [("ATK-KRT-005", 1.0)],
    },
    {
        "sku": "SRV-JLD-001",
        "name": "Jilid Lakban Biasa (Mika + Buffalo)",
        "description": "Jasa jilid lakban hitam dengan cover mika bening dan kertas buffalo",
        "selling_price": 5000,
        "materials": [
            ("ATK-JLD-001", 1.0),
            ("ATK-KRT-007", 1.0),
            ("ATK-PRK-004", 0.05),
        ],
    },
    {
        "sku": "SRV-JLD-002",
        "name": "Jilid Spiral Plastik (Mika + Buffalo)",
        "description": "Jasa jilid ring spiral plastik 12mm dengan cover mika dan buffalo",
        "selling_price": 12000,
        "materials": [
            ("ATK-JLD-001", 1.0),
            ("ATK-KRT-007", 1.0),
            ("ATK-JLD-005", 1.0),
        ],
    },
    {
        "sku": "SRV-LMN-001",
        "name": "Laminating Dokumen A4",
        "description": "Jasa laminasi panas ukuran A4",
        "selling_price": 4000,
        "materials": [("ATK-JLD-002", 1.0)],
    },
    {
        "sku": "SRV-LMN-002",
        "name": "Laminating Dokumen F4",
        "description": "Jasa laminasi panas ukuran F4/Folio",
        "selling_price": 5000,
        "materials": [("ATK-JLD-003", 1.0)],
    },
    {
        "sku": "SRV-LMN-003",
        "name": "Laminating KTP / Kartu",
        "description": "Jasa laminasi panas ukuran KTP atau ID card",
        "selling_price": 2500,
        "materials": [("ATK-JLD-004", 1.0)],
    },
    {
        "sku": "SRV-SCN-001",
        "name": "Scan Dokumen per Halaman (PDF/JPG)",
        "description": "Jasa pemindaian dokumen digital tanpa pemakaian bahan baku fisik",
        "selling_price": 1000,
        "materials": [],
    },
]


class InventoryTestingSeeder:
    """Mengelola pengisian data dummy inventaris, varian satuan, jasa, dan stok FIFO.

    Attributes:
        db_path (Path): Lokasi file database SQLite target.
    """

    def __init__(self, db_path: Optional[str | Path] = None) -> None:
        """Menginisialisasi seeder dengan path database target.

        Args:
            db_path: Path menuju file database SQLite. Default menggunakan DEFAULT_DB_PATH.
        """
        self.db_path: Path = Path(db_path) if db_path is not None else DEFAULT_DB_PATH

    def _connect(self) -> sqlite3.Connection:
        """Membuka koneksi SQLite dengan dukungan foreign keys aktif.

        Returns:
            Objek koneksi sqlite3.
        """
        return create_sqlite_connection(
            self.db_path,
            require_exists=False,
            row_factory=False,
            foreign_keys=True,
        )

    def _seed_categories(self, conn: sqlite3.Connection) -> dict[str, int]:
        """Menyisipkan daftar kategori barang dan mengembalikan pemetaan nama ke ID.

        Args:
            conn: Koneksi aktif ke database SQLite.

        Returns:
            Dictionary berisi pasangan {nama_kategori: id}.
        """
        for name in CATEGORIES_DATA:
            conn.execute(
                "INSERT OR IGNORE INTO categories (name, is_active) VALUES (?, 1);",
                (name,),
            )
        rows = conn.execute("SELECT name, id FROM categories;").fetchall()
        return {name: cat_id for name, cat_id in rows}

    def _seed_units(self, conn: sqlite3.Connection) -> dict[str, int]:
        """Menyisipkan daftar satuan dan mengembalikan pemetaan simbol ke ID.

        Args:
            conn: Koneksi aktif ke database SQLite.

        Returns:
            Dictionary berisi pasangan {simbol_satuan: id}.
        """
        for name, symbol in UNITS_DATA:
            conn.execute(
                "INSERT OR IGNORE INTO units (name, symbol) VALUES (?, ?);",
                (name, symbol),
            )
        rows = conn.execute("SELECT symbol, id FROM units;").fetchall()
        return {symbol: unit_id for symbol, unit_id in rows}

    def _seed_master_parties(self, conn: sqlite3.Connection) -> None:
        """Menyisipkan data contoh pemasok dan pelanggan jika tabel masih kosong.

        Args:
            conn: Koneksi aktif ke database SQLite.
        """
        sup_count = conn.execute("SELECT COUNT(*) FROM suppliers;").fetchone()[0]
        if sup_count == 0:
            conn.executemany(
                "INSERT INTO suppliers (name, phone, address, is_active) VALUES (?, ?, ?, 1);",
                SUPPLIERS_DATA,
            )

        cust_count = conn.execute("SELECT COUNT(*) FROM customers;").fetchone()[0]
        if cust_count == 0:
            conn.executemany(
                "INSERT INTO customers (name, phone, address, is_active) VALUES (?, ?, ?, 1);",
                CUSTOMERS_DATA,
            )

    def _seed_items_and_stock(
        self,
        conn: sqlite3.Connection,
        category_map: dict[str, int],
        unit_map: dict[str, int],
    ) -> dict[str, int]:
        """Menyisipkan barang, varian satuan, layer stok FIFO, dan mutasi stok awal.

        Args:
            conn: Koneksi aktif ke database SQLite.
            category_map: Pemetaan nama kategori ke ID.
            unit_map: Pemetaan simbol satuan ke ID.

        Returns:
            Dictionary berisi pasangan {sku_barang: item_id}.
        """
        sku_to_id: dict[str, int] = {}

        for item in ITEMS_DATA:
            conn.execute(
                """
                INSERT OR IGNORE INTO items (
                    sku, name, category_id, base_unit_id, description, is_active
                ) VALUES (?, ?, ?, ?, ?, 1);
                """,
                (
                    item["sku"],
                    item["name"],
                    category_map[item["category"]],
                    unit_map[item["base_unit"]],
                    item["description"],
                ),
            )
            item_id = conn.execute(
                "SELECT id FROM items WHERE sku = ?;",
                (item["sku"],),
            ).fetchone()[0]
            sku_to_id[item["sku"]] = item_id

            for unit_sym, variant_name, conv_qty, sell_price, is_def in item["variants"]:
                conn.execute(
                    """
                    INSERT OR IGNORE INTO item_units (
                        item_id, unit_id, variant_name, conversion_qty,
                        selling_price, is_default, is_active
                    ) VALUES (?, ?, ?, ?, ?, ?, 1);
                    """,
                    (
                        item_id,
                        unit_map[unit_sym],
                        variant_name,
                        conv_qty,
                        sell_price,
                        is_def,
                    ),
                )

            existing_layers = conn.execute(
                "SELECT COUNT(*) FROM inventory_layers WHERE item_id = ?;",
                (item_id,),
            ).fetchone()[0]

            if existing_layers == 0:
                for idx, (qty, unit_cost, received_at) in enumerate(item["layers"], start=1):
                    conn.execute(
                        """
                        INSERT INTO inventory_layers (
                            item_id, source_type, purchase_detail_id,
                            received_qty, remaining_qty, unit_cost, received_at
                        ) VALUES (?, 'OPENING_STOCK', NULL, ?, ?, ?, ?);
                        """,
                        (item_id, qty, qty, unit_cost, received_at),
                    )
                    conn.execute(
                        """
                        INSERT INTO stock_movements (
                            item_id, movement_type, quantity_in, quantity_out,
                            movement_date, notes
                        ) VALUES (?, 'OPENING_STOCK', ?, 0, ?, ?);
                        """,
                        (
                            item_id,
                            qty,
                            received_at,
                            f"Stok awal testing batch #{idx}",
                        ),
                    )

        return sku_to_id

    def _seed_services(
        self,
        conn: sqlite3.Connection,
        sku_to_id: dict[str, int],
    ) -> None:
        """Menyisipkan data layanan jasa beserta komposisi bahan bakunya.

        Args:
            conn: Koneksi aktif ke database SQLite.
            sku_to_id: Pemetaan SKU barang ke ID untuk relasi service_materials.
        """
        for srv in SERVICES_DATA:
            conn.execute(
                """
                INSERT OR IGNORE INTO services (
                    sku, name, description, selling_price, is_active
                ) VALUES (?, ?, ?, ?, 1);
                """,
                (
                    srv["sku"],
                    srv["name"],
                    srv["description"],
                    srv["selling_price"],
                ),
            )
            service_id = conn.execute(
                "SELECT id FROM services WHERE sku = ?;",
                (srv["sku"],),
            ).fetchone()[0]

            for material_sku, qty in srv["materials"]:
                conn.execute(
                    """
                    INSERT OR IGNORE INTO service_materials (
                        service_id, item_id, quantity
                    ) VALUES (?, ?, ?);
                    """,
                    (service_id, sku_to_id[material_sku], qty),
                )

    def run(self) -> dict[str, int]:
        """Menjalankan inisialisasi database dan mengisi seluruh data testing.

        Returns:
            Dictionary berisi jumlah total baris yang tersimpan di tiap tabel utama.
        """
        TransaksiDatabaseInitializer(db_path=self.db_path).initialize()

        with self._connect() as conn:
            category_map = self._seed_categories(conn)
            unit_map = self._seed_units(conn)
            self._seed_master_parties(conn)
            sku_to_id = self._seed_items_and_stock(conn, category_map, unit_map)
            self._seed_services(conn, sku_to_id)
            conn.commit()

            tables = [
                "categories",
                "units",
                "items",
                "item_units",
                "services",
                "service_materials",
                "inventory_layers",
                "stock_movements",
                "suppliers",
                "customers",
            ]
            summary = {
                table: conn.execute(f"SELECT COUNT(*) FROM {table};").fetchone()[0]
                for table in tables
            }

        return summary


if __name__ == "__main__":
    target_db = sys.argv[1] if len(sys.argv) > 1 else str(DEFAULT_DB_PATH)
    seeder = InventoryTestingSeeder(db_path=target_db)
    result = seeder.run()

    print(f"Seeding selesai pada database: {Path(target_db).resolve()}")
    print("-" * 45)
    for table_name, total_rows in result.items():
        print(f"{table_name:<22}: {total_rows} baris")