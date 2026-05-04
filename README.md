# e-MASTER Auto Fill

Skrip pengisian otomatis **Aktivitas Kinerja Harian** untuk aplikasi [Si-MASTER (Manajemen ASN Terpadu)](https://master.bkd.jatimprov.go.id/) BKD Provinsi Jawa Timur.

## Fitur

- Konversi data Excel Aktivitas Kinerja Harian ke format JSON (dikelompokkan per breakdown kegiatan)
- Pengisian otomatis form di e-MASTER
- Mendukung **elemen dinamis** (flexible selectors untuk field yang dibuat JavaScript)
- Login otomatis dengan NIP + Password, pause untuk **2FA/OTP** manual
- **3 metode**: GUI (tkinter), Tampermonkey Userscript (browser), dan Python Selenium (CLI)

## Alur Kerja di e-MASTER

```
1. Login (NIP + Password + OTP 2FA)
2. Buka halaman Aktivitas Bulan: essmedia.php?module=aktifitas_bulan&bulan=04
3. Ada 5 breakdown "Kegiatan Tugas Jabatan" (dari SKP, tanpa Briefing & Timbang terima)
4. Untuk setiap breakdown:
   a. Klik icon kunci pas (wrench) → masuk halaman realisasi
   b. Klik "Tambah" → buka halaman form "Tambah Aktivitas"
   c. Isi field: Tanggal Aktivitas, Detail Aktivitas, Satuan, WPT, Volume, Objek Kerja / Topik
   d. Klik Save → kembali ke halaman realisasi
   e. Ulangi b-d untuk setiap entry harian
```

## Struktur Proyek

```
emaster/
├── README.md
├── requirements.txt
├── emaster_gui.py              # GUI (double-click untuk jalankan)
├── scripts/
│   ├── convert_excel.py       # Konversi Excel → JSON (per breakdown)
│   └── autofill_selenium.py   # Auto-fill via Selenium (CLI)
├── userscript/
│   └── emaster-autofill.user.js  # Tampermonkey userscript (v3.0)
└── data/
    └── sample_output.json     # Contoh output JSON
```

## Instalasi

### Prasyarat

- Python 3.10+
- Google Chrome (untuk Selenium)
- [Tampermonkey](https://www.tampermonkey.net/) (untuk userscript)

### Install dependencies

```bash
pip install -r requirements.txt
```

## Penggunaan

### Metode 1: GUI (Paling Mudah — untuk Windows)

```bash
# Install dulu (sekali saja)
pip install openpyxl selenium

# Jalankan GUI (double-click atau dari terminal)
python emaster_gui.py
```

Tampilan GUI:
1. **Pilih File** — klik "Pilih File..." untuk pilih file Excel
2. **Login** — masukkan NIP dan Password
3. **Mulai Auto Fill** — klik tombol hijau
4. Chrome terbuka → login otomatis → **masukkan OTP di browser** → klik "OTP Sudah Diisi"
5. Tunggu sampai selesai — progress dan log terlihat di GUI

Tidak perlu buka Command Prompt, tidak perlu konversi Excel manual.

---

### Metode 2: Selenium CLI (Full Otomatis via Terminal)

#### 1. Konversi Excel ke JSON

```bash
python scripts/convert_excel.py "Aktifitas Kinerja Harian.xlsx"
```

Output JSON akan otomatis dikelompokkan per "Kegiatan Tugas Jabatan":

```json
{
  "info": {
    "nama": "Adheelia Laras Dinda, A.Md.Kep",
    "nip": "19940909 201903 2 026",
    "unit_kerja": "Gawat Darurat"
  },
  "bulan": "04",
  "total_entries": 220,
  "total_breakdowns": 5,
  "breakdowns": [
    {
      "kegiatan_tugas_jabatan": "Melaksanakan asuhan keperawatan sesuai SOP",
      "jumlah_entries": 20,
      "entries": [
        {
          "hari": "Rabu",
          "tanggal": "01-04-2026",
          "detail_aktivitas": "Melaksanakan asuhan keperawatan sesuai SOP",
          "objek_kerja": "Melakukan asuhan keperawatan mulai dari pengkajian...",
          "satuan": "Pasien",
          "wpt_menit": "28",
          "volume": "3"
        }
      ]
    }
  ]
}
```

### Metode 3: Tampermonkey (Browser Userscript)

1. Install [Tampermonkey](https://www.tampermonkey.net/) di browser
2. Buat script baru → paste isi file `userscript/emaster-autofill.user.js`
3. Login ke e-MASTER (NIP + Password + OTP)
4. Klik icon pensil di pojok kanan atas untuk buka panel
5. Import file JSON (hasil konversi)
6. Panel akan menampilkan daftar breakdown kegiatan
7. **Untuk setiap breakdown:**
   - Buka halaman Aktivitas Bulan
   - Klik icon kunci pas pada breakdown yang ingin diisi → masuk halaman realisasi
   - Di panel Auto Fill, pilih breakdown yang sesuai dari dropdown
   - Klik **"Mulai Auto Fill"**
   - Script akan otomatis: klik Tambah → isi form → Save → ulangi
   - State tersimpan, jadi jika halaman reload, proses akan lanjut otomatis
   - Ulangi untuk breakdown berikutnya

### Metode 2B: Selenium CLI (alternatif dari terminal)

```bash
# Langkah 1: Konversi Excel ke JSON
python scripts/convert_excel.py "Aktifitas Kinerja Harian.xlsx"

# Langkah 2: Jalankan auto-fill (NIP & password diinput di terminal)
python scripts/autofill_selenium.py "Aktifitas Kinerja Harian.json"

# Atau dengan kredensial langsung:
python scripts/autofill_selenium.py data.json --nip "19940909 201903 2 026" --password "PASSWORD"

# Mode simulasi (tanpa menyimpan, untuk test dulu):
python scripts/autofill_selenium.py data.json --dry-run
```

**Anda hanya perlu melakukan 1 hal manual: input kode OTP.**

Alur otomatis setelah OTP:
1. Deteksi bulan dari data JSON (misal `bulan: "04"`)
2. Buka halaman Aktivitas Bulan (`?module=aktifitas_bulan&bulan=04`)
3. Untuk setiap breakdown (5 breakdown):
   - Klik icon kunci pas → masuk halaman realisasi
   - Klik Tambah → klik "..." → cari di Kamus → pilih → isi Volume & Objek Kerja → Save
   - Ulangi untuk setiap entry dalam breakdown
   - Kembali ke Aktivitas Bulan → lanjut ke breakdown berikutnya
4. Selesai — **220 entry** terisi otomatis (BD1: 20, BD2: 20, BD3: 80, BD4: 80, BD5: 20)

## Format Data Excel

File Excel harus memiliki kolom-kolom berikut:

| Kolom | Deskripsi | Contoh |
|-------|-----------|--------|
| No | Nomor urut per hari | 1, 2, 3, ... |
| Hari | Nama hari | Rabu |
| Tanggal | Tanggal aktivitas | 01-04-2026 |
| Kegiatan Tugas Jabatan | Nama breakdown kegiatan | Briefing |
| Obyek Kerja | Detail/uraian kegiatan | Melakukan asuhan keperawatan... |
| Volume | Jumlah volume | 3 |
| Durasi (Menit) | Durasi dalam menit (= WPT) | 28 |
| Beban Kerja (Menit) | Durasi × Volume | 84 |

## Catatan Keamanan

- Jangan simpan password dalam file kode
- Gunakan mode interaktif Selenium untuk input kredensial
- Untuk Tampermonkey, data disimpan di storage lokal browser (GM_setValue)
- File JSON tidak mengandung kredensial login

## Lisensi

MIT
