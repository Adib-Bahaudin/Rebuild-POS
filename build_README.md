# Setup Enkripsi Database (SQLCipher & Cython Vault)

Repositori ini menggunakan **SQLCipher (AES-256)** untuk mengenkripsi database SQLite lokal. Demi keamanan, file kunci asli (`database/db_vault.pyx`) dan hasil kompilasi binernya (`.pyd`) tidak disertakan di dalam repositori Git.

Ikuti 5 tahap di bawah ini untuk membangun modul kunci secara lokal sebelum menjalankan aplikasi.

---

## 1. Prasyarat dan Instalasi Library

Pastikan Anda menggunakan **Python 3.12+** di dalam *virtual environment* proyek, lalu instal dependensi berikut:

```bash
pip install sqlcipher3-binary cython setuptools
```


**Khusus Pengguna Windows:**
Kompilasi Cython membutuhkan kompilator C/C++. Pasang **Build Tools for Visual Studio** dan centang beban kerja **Desktop development with C++** sebelum melanjutkan ke tahap kompilasi.

---

## 2. Struktur Folder Modul Keamanan

Setelah seluruh tahap selesai, struktur file terkait enkripsi pada proyek akan terlihat seperti berikut:

```text
proyek_aplikasi/
├── .gitignore
├── setup_vault.py
├── tools/
│   └── generate_vault_bytes.py
└── database/
    ├── __init__.py
    ├── db_connection.py
    ├── db_vault.example.py    # Templat aman (ada di Git)
    ├── db_vault.pyi           # Type stub untuk IDE/Pyright (ada di Git)
    ├── db_vault.pyx           # File kunci asli (dibuat lokal, diabaikan Git)
    └── db_vault.*.pyd         # Hasil kompilasi biner (dibuat lokal, diabaikan Git)

```

---

## 3. Membangkitkan Bahan Kunci & Recovery Key

Jalankan skrip utilitas berikut satu kali untuk menghasilkan byte kunci ter-XOR acak beserta *Recovery Key*:

```bash
python tools/generate_vault_bytes.py

```

Skrip akan mencetak:

* `_MASK`
* `_PART_A`
* `_PART_B`
* `_SALT_MASKED`
* `RECOVERY_KEY_HEX` (64 karakter heksadesimal)

> **Penting:** Simpan `RECOVERY_KEY_HEX` secara luring di tempat yang aman (misalnya pengelola sandi atau catatan cetak). Kunci ini diperlukan jika suatu saat Anda harus membuka atau memulihkan file `.db` menggunakan *DB Browser for SQLite* (mode *Raw key* `x'...'`).

---

## 4. Menyiapkan `database/db_vault.pyx`

1. Salin file templat `database/db_vault.example.py` dan ubah namanya menjadi `database/db_vault.pyx`.
2. Buka `database/db_vault.pyx`, lalu ganti nilai `_MASK`, `_PART_A`, `_PART_B`, dan `_SALT_MASKED` dengan hasil dari Tahap 3.
3. Ubah definisi fungsi perakit kunci agar menjadi fungsi internal C (`cdef`) sehingga tidak dapat dipanggil dari luar modul Python:

```cython
cdef str _assemble_raw_hex_key():
    cdef bytes seed = bytes(byte ^ _MASK for byte in (_PART_A + _PART_B))
    cdef bytes salt = bytes(byte ^ _MASK for byte in _SALT_MASKED)
    cdef bytes raw_key = hashlib.pbkdf2_hmac(
        hash_name="sha512",
        password=seed,
        salt=salt,
        iterations=256000,
        dklen=32,
    )
    return raw_key.hex()

```

4. Pada fungsi `open_secure_connection`, pastikan variabel kunci juga bertipe `cdef str`:

```cython
    cdef str hex_key = _assemble_raw_hex_key()

```

---

## 5. Kompilasi Modul Kunci ke Biner (`.pyd`)

Jalankan perintah kompilasi Cython dari direktori akar proyek:

```bash
python setup_vault.py build_ext --inplace

```

Jika berhasil, file biner seperti `database/db_vault.cp312-win_amd64.pyd` (atau `.so` pada Linux/macOS) akan muncul di dalam folder `database/`.

**Pembersihan Artefak Build:**
Hapus file antara `database/db_vault.c` dan folder `build/` setelah kompilasi selesai agar kode C hasil generasi Cython tidak tertinggal di direktori kerja.

> **Catatan Git:** Jangan pernah menghapus aturan `database/db_vault.pyx`, `database/db_vault.c`, dan `database/*.pyd` dari `.gitignore` agar bahan kunci rahasia tidak ikut terunggah ke repositori.

```

```
