#!/usr/bin/env python3
"""
e-MASTER Auto Fill — GUI Version

Aplikasi GUI untuk pengisian otomatis Aktivitas Kinerja Harian di e-MASTER.
Double-click file ini untuk menjalankan.

Fitur:
  - Pilih file Excel langsung dari GUI
  - Input NIP & Password di GUI
  - Progress bar dan log real-time
  - Tombol Start / Stop
  - Otomatis konversi Excel → JSON → isi form e-MASTER
"""

import subprocess
import sys

def _ensure_packages():
    """Auto-install selenium & openpyxl jika belum ada."""
    missing = []
    for pkg in ("selenium", "openpyxl"):
        try:
            __import__(pkg)
        except ImportError:
            missing.append(pkg)
    if missing:
        print(f"Installing {', '.join(missing)}...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", *missing])

_ensure_packages()

import json
import os
import threading
import time
import tkinter as tk
from datetime import datetime
from pathlib import Path
from tkinter import filedialog, messagebox, scrolledtext, ttk

# Tambahkan folder scripts ke path
SCRIPT_DIR = Path(__file__).parent / "scripts"
sys.path.insert(0, str(SCRIPT_DIR))

# ============================================================================
# KONFIGURASI
# ============================================================================
BASE_URL = "https://master.bkd.jatimprov.go.id"
LOGIN_URL = BASE_URL
AKTIVITAS_URL = f"{BASE_URL}/essmedia.php?module=aktifitas_bulan&bulan={{bulan}}"
TAMBAH_URL = f"{BASE_URL}/essmedia.php?module=aktifitas_bulan&act=tambahaktifitas&bulan={{bulan}}&id_breakdown={{id_breakdown}}"

DELAY_SHORT = 1
DELAY_MEDIUM = 2
DELAY_LONG = 3


# ============================================================================
# KONVERSI EXCEL
# ============================================================================

def convert_excel_to_json(excel_path: str) -> dict:
    """Konversi Excel ke dict JSON (inline, tanpa perlu file terpisah)."""
    try:
        import openpyxl
    except ImportError:
        raise ImportError("openpyxl belum terinstall. Jalankan: pip install openpyxl")

    from collections import defaultdict

    wb = openpyxl.load_workbook(excel_path, data_only=True)
    ws = wb.active

    # Info pegawai
    info = {"nama": "", "nip": "", "unit_kerja": "", "file_source": str(excel_path)}
    for row_idx in range(1, min(20, ws.max_row + 1)):
        cell_a = ws.cell(row=row_idx, column=1).value
        cell_b = ws.cell(row=row_idx, column=2).value
        if cell_a and isinstance(cell_a, str):
            lower_a = cell_a.strip().lower()
            if lower_a == "nama" and cell_b:
                info["nama"] = str(cell_b).strip().lstrip(": ")
            elif lower_a == "nip" and cell_b:
                info["nip"] = str(cell_b).strip().lstrip(": ").replace(" ", "")
            elif "unit kerja" in lower_a and cell_b:
                info["unit_kerja"] = str(cell_b).strip().lstrip(": ")

    # Cari header
    header_row = None
    for row_idx in range(1, min(30, ws.max_row + 1)):
        cell_a = ws.cell(row=row_idx, column=1).value
        if cell_a and str(cell_a).strip().lower() == "no":
            header_row = row_idx
            break

    if header_row is None:
        raise ValueError("Header tabel (No, Hari, Tanggal, ...) tidak ditemukan!")

    headers = []
    for col_idx in range(1, ws.max_column + 1):
        val = ws.cell(row=header_row, column=col_idx).value
        headers.append(str(val).strip() if val else f"col_{col_idx}")

    # Mapping kolom
    col_map = {}
    for i, h in enumerate(headers):
        h_lower = h.lower()
        if h_lower == "no":
            col_map["no"] = i
        elif h_lower in ("hari",):
            col_map["hari"] = i
        elif "tanggal" in h_lower or "tgl" in h_lower:
            col_map["tanggal"] = i
        elif "kegiatan" in h_lower or "detail" in h_lower or "aktivitas" in h_lower:
            col_map["kegiatan"] = i
        elif "obyek" in h_lower or "objek" in h_lower or "uraian" in h_lower:
            col_map["objek_kerja"] = i
        elif "volume" in h_lower or "vol" in h_lower:
            col_map["volume"] = i
        elif "beban" in h_lower:
            col_map["beban_kerja"] = i
        elif "satuan" in h_lower:
            col_map["satuan"] = i
        elif "durasi" in h_lower or "wpt" in h_lower or (
            "menit" in h_lower and "beban" not in h_lower
        ):
            col_map["durasi"] = i

    # Baca data
    SKIP_KEGIATAN = {"briefing", "timbang terima"}
    grouped = defaultdict(list)
    current_hari = ""
    current_tanggal = ""
    data_start = header_row + 1

    for skip_row in range(data_start, data_start + 3):
        cell = ws.cell(row=skip_row, column=1).value
        if cell is None or (isinstance(cell, str) and not cell.strip().isdigit()):
            data_start = skip_row + 1
        else:
            break

    for row_idx in range(data_start, ws.max_row + 1):
        row_data = []
        for col_idx in range(1, ws.max_column + 1):
            row_data.append(ws.cell(row=row_idx, column=col_idx).value)

        no_val = row_data[col_map.get("no", 0)] if "no" in col_map else None
        if no_val is None:
            continue
        if isinstance(no_val, str) and no_val.strip().lower() in ("total", "nb", ""):
            continue
        if isinstance(no_val, str) and not no_val.strip().isdigit():
            continue

        hari_val = row_data[col_map["hari"]] if "hari" in col_map else None
        tgl_val = row_data[col_map["tanggal"]] if "tanggal" in col_map else None

        if hari_val:
            current_hari = str(hari_val).strip()
        if tgl_val:
            if isinstance(tgl_val, datetime):
                current_tanggal = tgl_val.strftime("%d-%m-%Y")
            else:
                current_tanggal = str(tgl_val).strip()

        kegiatan = ""
        if "kegiatan" in col_map:
            val = row_data[col_map["kegiatan"]]
            kegiatan = str(val).strip() if val else ""

        if not kegiatan or kegiatan.lower().strip() in SKIP_KEGIATAN:
            continue

        objek_kerja = ""
        if "objek_kerja" in col_map:
            val = row_data[col_map["objek_kerja"]]
            objek_kerja = str(val).strip() if val else ""

        volume = ""
        if "volume" in col_map:
            val = row_data[col_map["volume"]]
            volume = str(int(val)) if val and isinstance(val, (int, float)) else str(val or "")

        durasi = ""
        if "durasi" in col_map:
            val = row_data[col_map["durasi"]]
            durasi = str(int(val)) if val and isinstance(val, (int, float)) else str(val or "")

        beban_kerja = ""
        if "beban_kerja" in col_map:
            val = row_data[col_map["beban_kerja"]]
            beban_kerja = str(int(val)) if val and isinstance(val, (int, float)) else str(val or "")

        satuan = "Pasien"
        if "satuan" in col_map:
            val = row_data[col_map["satuan"]]
            satuan = str(val).strip() if val else "Pasien"

        entry = {
            "hari": current_hari,
            "tanggal": current_tanggal,
            "detail_aktivitas": kegiatan,
            "objek_kerja": objek_kerja,
            "satuan": satuan,
            "wpt_menit": durasi,
            "volume": volume,
            "beban_kerja": beban_kerja,
        }

        grouped[kegiatan].append(entry)

    wb.close()

    # Deteksi bulan
    bulan = ""
    all_entries = []
    for entries in grouped.values():
        all_entries.extend(entries)
    if all_entries:
        first_date = all_entries[0].get("tanggal", "")
        parts = first_date.replace("/", "-").split("-")
        if len(parts) == 3:
            bulan = parts[1]

    # Kamus keywords
    KAMUS_KEYWORDS = {
        "Melaksanakan asuhan keperawatan sesuai SOP": {
            "keywords": ["Manajemen Asuhan Keperawatan"],
            "mode": "single",
        },
        "Menginput dokumentasi tindakan keperawatan": {
            "keywords": ["Memasukkan Hasil Pengkajian"],
            "mode": "single",
        },
        "Melaksanakan tindakan keperawatan tepat waktu": {
            "keywords": [
                "Sampling Darah Vena Instalasi",
                "Terapi Injeksi Parenteral",
                "Pasang Infus",
            ],
            "mode": "rotating",
        },
        "Melaksanakan prosedur keperawatan sesuai SOP": {
            "keywords": [
                "Terapi Injeksi Line",
                "Pasang Infus",
                "Mengukur Tanda Tanda",
                "Sampling Darah Vena Instalasi",
            ],
            "mode": "rotating",
        },
        "Menyiapkan alat medis pelayanan": {
            "keywords": ["Memeriksa Kelengkapan Alat"],
            "mode": "single",
        },
    }

    breakdowns = []
    total_expanded = 0
    for kegiatan_name, entries in grouped.items():
        kamus = KAMUS_KEYWORDS.get(kegiatan_name, {
            "keywords": [kegiatan_name],
            "mode": "single",
        })

        if kamus["mode"] == "rotating":
            kw_list = kamus["keywords"]
            expanded_entries = []
            for entry in entries:
                for kw in kw_list:
                    new_entry = dict(entry)
                    new_entry["kamus_keyword"] = kw
                    expanded_entries.append(new_entry)
            entries = expanded_entries
        else:
            for entry in entries:
                entry["kamus_keyword"] = kamus["keywords"][0]

        total_expanded += len(entries)
        breakdowns.append({
            "kegiatan_tugas_jabatan": kegiatan_name,
            "jumlah_entries": len(entries),
            "kamus_config": kamus,
            "entries": entries,
        })

    return {
        "info": info,
        "bulan": bulan,
        "generated_at": datetime.now().isoformat(),
        "total_entries": total_expanded,
        "total_breakdowns": len(breakdowns),
        "breakdowns": breakdowns,
    }


# ============================================================================
# SELENIUM FUNCTIONS (dari autofill_selenium.py)
# ============================================================================

def _get_profile_dir():
    """Folder profil Chrome di samping script ini."""
    return str(Path(__file__).parent / "emaster_chrome_profile")


def create_driver(headless=False):
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options
    options = Options()
    if headless:
        options.add_argument("--headless=new")
    # Simpan session/cookies di folder profil lokal
    profile_dir = _get_profile_dir()
    options.add_argument(f"--user-data-dir={profile_dir}")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1366,768")
    options.add_argument("--disable-gpu")
    driver = webdriver.Chrome(options=options)
    driver.implicitly_wait(5)
    return driver


def dismiss_alert(driver):
    """Dismiss any alert/popup yang muncul di browser."""
    try:
        alert = driver.switch_to.alert
        alert.accept()
        return True
    except Exception:
        return False


def safe_get(driver, url):
    """Navigasi ke URL, otomatis dismiss alert jika muncul."""
    try:
        driver.get(url)
    except Exception:
        dismiss_alert(driver)
        try:
            driver.get(url)
        except Exception:
            pass
    time.sleep(0.5)
    dismiss_alert(driver)


def normalize_date(date_str):
    if not date_str:
        return ""
    parts = date_str.replace("/", "-").split("-")
    if len(parts) == 3:
        if len(parts[0]) == 4:
            return date_str
        return f"{parts[2]}-{parts[1]}-{parts[0]}"
    return date_str


def find_by_labels(driver, labels, tag="*"):
    from selenium.webdriver.common.by import By
    lower = "translate(text(),'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz')"
    lower_attr = "translate(@{attr},'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz')"

    for label_text in labels:
        lt = label_text.lower()
        try:
            bolds = driver.find_elements(
                By.XPATH,
                f"//b[contains({lower},'{lt}')] | //strong[contains({lower},'{lt}')]",
            )
            for bold in bolds:
                parent = bold.find_element(By.XPATH, "..")
                inputs = parent.find_elements(By.CSS_SELECTOR, "input, select, textarea")
                for inp in inputs:
                    if not inp.get_attribute("readonly") and inp.is_enabled():
                        return inp
                try:
                    following = bold.find_elements(
                        By.XPATH, "following-sibling::input | following-sibling::textarea | following-sibling::select"
                    )
                    for inp in following:
                        if not inp.get_attribute("readonly") and inp.is_enabled():
                            return inp
                except Exception:
                    pass
        except Exception:
            pass

        try:
            label_els = driver.find_elements(By.XPATH, f"//label[contains({lower},'{lt}')]")
            for lbl in label_els:
                for_id = lbl.get_attribute("for")
                if for_id:
                    try:
                        return driver.find_element(By.ID, for_id)
                    except Exception:
                        pass
                inputs = lbl.find_elements(By.CSS_SELECTOR, "input, select, textarea")
                if inputs:
                    return inputs[0]
        except Exception:
            pass

        try:
            cells = driver.find_elements(
                By.XPATH,
                f"//td[contains({lower},'{lt}')]"
                "/following-sibling::td//input | "
                f"//td[contains({lower},'{lt}')]"
                "/following-sibling::td//select | "
                f"//td[contains({lower},'{lt}')]"
                "/following-sibling::td//textarea",
            )
            if cells:
                return cells[0]
        except Exception:
            pass

        for attr in ["name", "id", "placeholder"]:
            try:
                la = lower_attr.format(attr=attr)
                els = driver.find_elements(By.XPATH, f"//{tag}[contains({la},'{lt}')]")
                if els:
                    return els[0]
            except Exception:
                pass

    return None


def safe_set_value(driver, element, value):
    from selenium.webdriver.support.ui import Select
    if not element or not value:
        return False
    try:
        tag = element.tag_name.lower()
        input_type = (element.get_attribute("type") or "").lower()

        if tag == "select":
            select = Select(element)
            try:
                select.select_by_visible_text(value)
                return True
            except Exception:
                pass
            try:
                select.select_by_value(value)
                return True
            except Exception:
                pass
            for opt in select.options:
                if value.lower() in opt.text.lower():
                    select.select_by_visible_text(opt.text)
                    return True
            return False

        if input_type == "date":
            driver.execute_script(
                "arguments[0].value = arguments[1]; "
                "arguments[0].dispatchEvent(new Event('input', {bubbles:true})); "
                "arguments[0].dispatchEvent(new Event('change', {bubbles:true}));",
                element, normalize_date(value),
            )
            return True

        element.clear()
        element.send_keys(value)
        driver.execute_script(
            "arguments[0].dispatchEvent(new Event('input', {bubbles:true}));"
            "arguments[0].dispatchEvent(new Event('change', {bubbles:true}));",
            element,
        )
        return True
    except Exception:
        return False


def do_login(driver, nip, password):
    from selenium.webdriver.common.by import By
    nip = nip.replace(" ", "")
    safe_get(driver, LOGIN_URL)
    time.sleep(DELAY_MEDIUM)

    # Field NIP: id="username", name="username"
    nip_field = None
    try:
        nip_field = driver.find_element(By.ID, "username")
    except Exception:
        try:
            nip_field = driver.find_element(By.NAME, "username")
        except Exception:
            nip_field = find_by_labels(driver, ["nip", "username"], "input")

    if not nip_field:
        return False
    safe_set_value(driver, nip_field, nip)

    # Field Password: id="password", name="password"
    pwd_field = None
    try:
        pwd_field = driver.find_element(By.ID, "password")
    except Exception:
        try:
            pwd_field = driver.find_element(By.CSS_SELECTOR, "input[type='password']")
        except Exception:
            pwd_field = find_by_labels(driver, ["password"], "input")

    if not pwd_field:
        return False
    safe_set_value(driver, pwd_field, password)

    # Klik tombol Login: <button type="submit">Login</button>
    try:
        btn = driver.find_element(By.CSS_SELECTOR, "#loginform button[type='submit']")
        btn.click()
        time.sleep(DELAY_LONG)
        return True
    except Exception:
        pass

    for el in driver.find_elements(By.CSS_SELECTOR, "button[type='submit'], input[type='submit']"):
        text = el.get_attribute("value") or el.text or ""
        if "login" in text.lower() or "masuk" in text.lower():
            el.click()
            time.sleep(DELAY_LONG)
            return True

    return False


def find_breakdown_link(driver, kegiatan_name, log_fn=None):
    """Cari link realisasi untuk breakdown tertentu di halaman Aktivitas Bulan.

    Return URL string (bukan element) agar bisa navigasi langsung via safe_get.
    """
    from selenium.webdriver.common.by import By

    def _log(msg):
        if log_fn:
            log_fn(msg)

    # Cari di tabel breakdown
    rows = driver.find_elements(By.CSS_SELECTOR, "table#sort-table1 tbody tr")
    if not rows:
        rows = driver.find_elements(By.CSS_SELECTOR, "table tbody tr")

    _log(f"  [Debug] Jumlah baris tabel: {len(rows)}")

    # Selector link yang mungkin: realisasi, detail, wrench icon
    link_selectors = [
        "a[href*='realisasi']",
        "a[href*='detail']",
        "a.btn",
        "a[href*='aktifitas_bulan']",
        "a",
    ]

    for row in rows:
        try:
            row_text = row.text.strip()
            if not row_text:
                continue
            if kegiatan_name.lower() not in row_text.lower():
                continue

            _log(f"  [Debug] Baris cocok: '{row_text[:60]}...'")

            # Coba setiap selector
            for selector in link_selectors:
                links = row.find_elements(By.CSS_SELECTOR, selector)
                for link in links:
                    href = link.get_attribute("href") or ""
                    if not href or href == "#":
                        continue
                    _log(f"  [Debug] Link ditemukan: {href[:80]}")
                    return href
        except Exception:
            continue

    # Fallback: cari semua link dengan keyword realisasi
    for selector in link_selectors[:2]:
        links = driver.find_elements(By.CSS_SELECTOR, selector)
        for link in links:
            try:
                parent_row = link.find_element(By.XPATH, "./ancestor::tr")
                if kegiatan_name.lower() in parent_row.text.lower():
                    href = link.get_attribute("href") or ""
                    if href and href != "#":
                        _log(f"  [Debug] Link fallback: {href[:80]}")
                        return href
            except Exception:
                continue

    _log(f"  [Debug] Tidak ada link ditemukan untuk: {kegiatan_name[:40]}")
    return None


def find_tambah_button(driver):
    from selenium.webdriver.common.by import By
    for el in driver.find_elements(By.CSS_SELECTOR, "a, button, input[type='button'], input[type='submit']"):
        text = (el.text or el.get_attribute("value") or "").lower()
        if "tambah" in text or "add" in text or "input baru" in text:
            return el
    return None


def get_tambah_url(driver):
    """Ambil URL form Tambah dari onclick tombol Tambah."""
    import re
    from selenium.webdriver.common.by import By
    btn = find_tambah_button(driver)
    if not btn:
        return ""
    onclick = btn.get_attribute("onclick") or ""
    if onclick:
        match = re.search(r"(?:window\.location\.href\s*=\s*['\"])([^'\"]+)", onclick)
        if match:
            url = match.group(1)
            if url.startswith("?"):
                url = BASE_URL + "/essmedia.php" + url
            elif not url.startswith("http"):
                url = BASE_URL + "/" + url
            return url
    href = btn.get_attribute("href") or ""
    if href and href != "#" and "tambah" in href.lower():
        return href
    return ""


def find_simpan_button(driver):
    from selenium.webdriver.common.by import By
    for el in driver.find_elements(By.CSS_SELECTOR, "a, button, input[type='button'], input[type='submit']"):
        text = (el.text or el.get_attribute("value") or "").lower()
        if "simpan" in text or "save" in text or "submit" in text or "kirim" in text:
            return el
    return None


def handle_kamus_popup(driver, keyword, log_fn=None):
    """Handle popup Kamus Aktifitas Harian (window baru).

    Popup buka tab/window baru via open_child('../popup_skp/popup_aktifitas.php',...).
    Setelah klik baris hasil, fungsi pilih() di popup:
      - Set field siteh4nk (detail), satuan, wpt di window utama
      - window.close() → popup tertutup otomatis
    """
    from selenium.webdriver.common.by import By

    def _log(msg):
        if log_fn:
            log_fn(msg)

    # Cari tombol "..."
    dot_btn = None
    for el in driver.find_elements(By.CSS_SELECTOR, "button, input[type='button'], a"):
        text = (el.text or el.get_attribute("value") or "").strip()
        if text in ("...", "\u2026"):
            dot_btn = el
            break

    if not dot_btn:
        _log("      [Kamus] Tombol '...' TIDAK DITEMUKAN")
        return False

    main_window = driver.current_window_handle
    windows_before = set(driver.window_handles)
    dot_btn.click()
    _log("      [Kamus] Klik '...'")
    time.sleep(DELAY_LONG)

    # Tunggu window baru muncul
    windows_after = set(driver.window_handles)
    new_windows = windows_after - windows_before

    if not new_windows:
        time.sleep(DELAY_MEDIUM)
        windows_after = set(driver.window_handles)
        new_windows = windows_after - windows_before

    if not new_windows:
        _log("      [Kamus] Window popup TIDAK terbuka")
        return False

    popup_window = list(new_windows)[0]
    driver.switch_to.window(popup_window)
    _log("      [Kamus] Switch ke window popup")
    time.sleep(DELAY_SHORT)

    try:
        # Cari input pencarian — name="kata", id="kata"
        search_input = None
        for selector in ["input#kata", "input[name='kata']", "input[type='text']"]:
            try:
                search_input = driver.find_element(By.CSS_SELECTOR, selector)
                if search_input:
                    break
            except Exception:
                continue

        if not search_input:
            _log("      [Kamus] Input pencarian TIDAK DITEMUKAN")
            raise Exception("Input pencarian tidak ditemukan")

        search_input.clear()
        search_input.send_keys(keyword)
        _log(f"      [Kamus] Ketik: '{keyword}'")

        # Submit form (klik Cari) — halaman reload
        try:
            cari_btn = driver.find_element(By.CSS_SELECTOR, "input[type='submit'][value='Cari']")
            cari_btn.click()
            _log("      [Kamus] Klik 'Cari'")
        except Exception:
            search_input.submit()
            _log("      [Kamus] Submit form pencarian")
        time.sleep(DELAY_LONG)

        # Klik baris hasil — <tr onclick="javascript:pilih(this);">
        rows = driver.find_elements(By.CSS_SELECTOR, "table#sort-table1 tbody tr")
        if not rows:
            rows = driver.find_elements(By.CSS_SELECTOR, "table tbody tr[onclick]")
        if not rows:
            rows = driver.find_elements(By.CSS_SELECTOR, "tbody tr")

        for row in rows:
            row_text = row.text.strip()
            if keyword.lower() in row_text.lower():
                row.click()
                _log(f"      [Kamus] Klik hasil: '{row_text[:60]}'")
                time.sleep(DELAY_MEDIUM)
                try:
                    driver.switch_to.window(main_window)
                except Exception:
                    pass
                return True

        # Fallback: klik baris pertama
        if rows:
            first_text = rows[0].text.strip()
            if first_text:
                rows[0].click()
                _log(f"      [Kamus] Klik hasil pertama: '{first_text[:60]}'")
                time.sleep(DELAY_MEDIUM)
                try:
                    driver.switch_to.window(main_window)
                except Exception:
                    pass
                return True

        _log(f"      [Kamus] Hasil pencarian '{keyword}' TIDAK DITEMUKAN")

    except Exception as e:
        _log(f"      [Kamus] ERROR: {e}")

    # Cleanup: tutup popup jika masih terbuka, kembali ke window utama
    try:
        if popup_window in driver.window_handles:
            driver.switch_to.window(popup_window)
            driver.close()
        driver.switch_to.window(main_window)
    except Exception:
        try:
            driver.switch_to.window(main_window)
        except Exception:
            pass
    return False


def fill_single_entry(driver, entry, log_fn=None, tambah_url=""):
    from selenium.webdriver.common.by import By

    def _log(msg):
        if log_fn:
            log_fn(msg)

    dismiss_alert(driver)

    # 0. Navigasi ke form Tambah Aktivitas
    if tambah_url:
        _log("    [Step 1] Navigasi langsung ke form Tambah")
        safe_get(driver, tambah_url)
        time.sleep(DELAY_LONG)
    else:
        tambah = find_tambah_button(driver)
        if tambah:
            tambah.click()
            _log("    [Step 1] Klik 'Tambah'")
            time.sleep(DELAY_LONG)
        else:
            _log("    [Step 1] Tombol 'Tambah' TIDAK DITEMUKAN!")
            buttons = driver.find_elements(By.CSS_SELECTOR, "a, button, input[type='button']")
            btn_texts = [f"'{(b.text or b.get_attribute('value') or '')[:30]}'" for b in buttons[:10]]
            _log(f"    [Debug] Tombol yang ada: {', '.join(btn_texts)}")
            return False

    filled = 0

    # 1. Tanggal — name="tgl_kegiatan", id="datepicker"
    tanggal = entry.get("tanggal", "")
    if tanggal:
        el = None
        try:
            el = driver.find_element(By.NAME, "tgl_kegiatan")
        except Exception:
            try:
                el = driver.find_element(By.ID, "datepicker")
            except Exception:
                el = find_by_labels(driver, ["tanggal aktivitas", "tanggal"])
        if el:
            if safe_set_value(driver, el, str(tanggal)):
                filled += 1
                _log(f"    [Step 2] Tanggal: {tanggal} OK")
            else:
                _log(f"    [Step 2] Tanggal: GAGAL set value")
        else:
            _log(f"    [Step 2] Field 'Tanggal Aktivitas' TIDAK DITEMUKAN")

    # 2. Detail Aktivitas via Kamus popup
    #    Field: name="rk", id="siteh4nk" (readonly, diisi via popup)
    kamus_keyword = entry.get("kamus_keyword") or entry.get("detail_aktivitas", "")
    if kamus_keyword:
        _log(f"    [Step 3] Kamus popup: '{kamus_keyword}'")
        if handle_kamus_popup(driver, kamus_keyword, log_fn):
            filled += 1
            _log(f"    [Step 3] Kamus: OK")
            time.sleep(DELAY_SHORT)
        else:
            # Fallback: isi langsung via JavaScript (field readonly)
            try:
                el = driver.find_element(By.NAME, "rk")
                driver.execute_script(
                    "arguments[0].removeAttribute('readonly'); arguments[0].value = arguments[1];",
                    el, str(kamus_keyword))
                filled += 1
                _log(f"    [Step 3] Kamus (fallback JS): OK")
            except Exception:
                _log(f"    [Step 3] Kamus: GAGAL")

    # 3. Volume — name="volume"
    volume = entry.get("volume", "")
    if volume:
        el = None
        try:
            el = driver.find_element(By.NAME, "volume")
        except Exception:
            el = find_by_labels(driver, ["volume"])
        if el:
            if safe_set_value(driver, el, str(volume)):
                filled += 1
                _log(f"    [Step 4] Volume: {volume} OK")
            else:
                _log(f"    [Step 4] Volume: GAGAL set value")
        else:
            _log(f"    [Step 4] Field 'Volume' TIDAK DITEMUKAN")

    # 4. Objek Kerja — name="objek_kerja"
    objek = entry.get("objek_kerja", "")
    if objek:
        el = None
        try:
            el = driver.find_element(By.NAME, "objek_kerja")
        except Exception:
            el = find_by_labels(driver, ["objek kerja", "topik"])
        if el:
            if safe_set_value(driver, el, str(objek)):
                filled += 1
                _log(f"    [Step 5] Objek Kerja: OK")
            else:
                _log(f"    [Step 5] Objek Kerja: GAGAL set value")
        else:
            _log(f"    [Step 5] Field 'Objek Kerja' TIDAK DITEMUKAN")

    # Klik Save — ada confirm() dialog yang harus di-accept
    if filled > 0:
        time.sleep(DELAY_SHORT)
        simpan = find_simpan_button(driver)
        if simpan:
            simpan.click()
            _log(f"    [Step 6] Klik Save ({filled} field terisi)")
            # Accept confirm dialog: "Apakah Anda benar-benar mau menyimpan data?"
            time.sleep(0.5)
            try:
                alert = driver.switch_to.alert
                alert.accept()
                _log(f"    [Step 6] Accept confirm dialog: OK")
            except Exception:
                pass
            time.sleep(DELAY_LONG)
        else:
            _log(f"    [Step 6] Tombol 'Save/Simpan' TIDAK DITEMUKAN!")
    else:
        _log(f"    [GAGAL] Tidak ada field yang berhasil diisi (filled=0)")

    return filled > 0


# ============================================================================
# GUI APPLICATION
# ============================================================================

class EMasterGUI:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("e-MASTER Auto Fill")
        self.root.geometry("620x600")
        self.root.resizable(True, True)

        self.driver = None
        self.running = False
        self.paused = False
        self.data = None
        self.bd_checks = []  # list of (BooleanVar, kegiatan_name)
        self.pause_event = threading.Event()
        self.pause_event.set()  # not paused initially

        self._build_ui()

    def _build_ui(self):
        F = ("Segoe UI", 9)
        FS = ("Segoe UI", 8)
        FB = ("Segoe UI", 10, "bold")
        PAD = 5

        # Header
        header = tk.Frame(self.root, bg="#2c3e50", padx=8, pady=4)
        header.pack(fill=tk.X)
        tk.Label(header, text="e-MASTER Auto Fill", font=FB, fg="white", bg="#2c3e50").pack()

        # Main frame with scrollable canvas for small screens
        main = tk.Frame(self.root, padx=8, pady=4)
        main.pack(fill=tk.BOTH, expand=True)

        # --- File + Login (side by side) ---
        top = tk.Frame(main)
        top.pack(fill=tk.X, pady=(0, PAD))

        # File
        tk.Label(top, text="File Excel:", font=F).grid(row=0, column=0, sticky="w")
        self.file_var = tk.StringVar()
        tk.Entry(top, textvariable=self.file_var, font=FS, width=38).grid(row=0, column=1, sticky="ew", padx=2)
        tk.Button(top, text="...", command=self._pick_file, width=3, font=FS).grid(row=0, column=2)

        # NIP
        tk.Label(top, text="NIP:", font=F).grid(row=1, column=0, sticky="w", pady=1)
        self.nip_var = tk.StringVar()
        tk.Entry(top, textvariable=self.nip_var, font=FS, width=38).grid(row=1, column=1, sticky="ew", padx=2)

        # Password
        tk.Label(top, text="Password:", font=F).grid(row=2, column=0, sticky="w", pady=1)
        self.pwd_var = tk.StringVar()
        tk.Entry(top, textvariable=self.pwd_var, show="*", font=FS, width=38).grid(row=2, column=1, sticky="ew", padx=2)

        top.columnconfigure(1, weight=1)

        # --- Info (single line) ---
        self.info_var = tk.StringVar(value="Pilih file Excel")
        tk.Label(main, textvariable=self.info_var, font=FS, fg="gray", anchor="w").pack(fill=tk.X)

        # --- Pilih Kegiatan ---
        self.bd_frame = tk.LabelFrame(main, text="Kegiatan", font=FS, padx=4, pady=2)
        self.bd_frame.pack(fill=tk.X, pady=(PAD, 2))
        self.bd_placeholder = tk.Label(self.bd_frame, text="Muat file Excel dulu", fg="gray", font=FS)
        self.bd_placeholder.pack(anchor="w")

        # --- Filter Tanggal ---
        df = tk.Frame(main)
        df.pack(fill=tk.X, pady=(2, PAD))
        tk.Label(df, text="Dari:", font=FS).pack(side=tk.LEFT)
        self.date_from_var = tk.StringVar()
        self.date_from_combo = ttk.Combobox(df, textvariable=self.date_from_var, width=12, state="readonly", font=FS)
        self.date_from_combo.pack(side=tk.LEFT, padx=(2, 8))
        tk.Label(df, text="Sampai:", font=FS).pack(side=tk.LEFT)
        self.date_to_var = tk.StringVar()
        self.date_to_combo = ttk.Combobox(df, textvariable=self.date_to_var, width=12, state="readonly", font=FS)
        self.date_to_combo.pack(side=tk.LEFT, padx=2)
        tk.Label(df, text="(kosong = semua)", font=("Segoe UI", 7), fg="gray").pack(side=tk.LEFT, padx=4)

        # --- Objek Kerja ---
        objek_frame = tk.LabelFrame(main, text="Objek Kerja (untuk kegiatan yang dicentang)", font=FS, padx=4, pady=2)
        objek_frame.pack(fill=tk.X, pady=(0, PAD))
        self.objek_var = tk.StringVar()
        tk.Entry(objek_frame, textvariable=self.objek_var, font=FS).pack(fill=tk.X)
        tk.Label(objek_frame, text="Kosongkan = pakai dari Excel. Isi = ganti semua Objek Kerja kegiatan yang dicentang",
                 font=("Segoe UI", 7), fg="gray").pack(anchor="w")

        # --- Buttons + Progress ---
        bp = tk.Frame(main)
        bp.pack(fill=tk.X, pady=(0, PAD))

        self.start_btn = tk.Button(bp, text="Mulai", command=self._start,
                                   bg="#27ae60", fg="white", font=FB, padx=10, pady=2)
        self.start_btn.pack(side=tk.LEFT, padx=(0, 3))

        self.pause_btn = tk.Button(bp, text="Pause", command=self._toggle_pause,
                                    bg="#3498db", fg="white", font=FB, padx=10, pady=2,
                                    state=tk.DISABLED)
        self.pause_btn.pack(side=tk.LEFT, padx=(0, 3))

        self.stop_btn = tk.Button(bp, text="Stop", command=self._stop,
                                  bg="#e74c3c", fg="white", font=FB, padx=10, pady=2,
                                  state=tk.DISABLED)
        self.stop_btn.pack(side=tk.LEFT, padx=(0, 3))

        self.otp_btn = tk.Button(bp, text="OTP Sudah Diisi", command=self._otp_done,
                                 bg="#f39c12", fg="white", font=FB, padx=10, pady=2,
                                 state=tk.DISABLED)
        self.otp_btn.pack(side=tk.LEFT, padx=(0, 5))

        self.progress_var = tk.StringVar(value="")
        tk.Label(bp, textvariable=self.progress_var, font=FS, anchor="w").pack(side=tk.LEFT, fill=tk.X, expand=True)

        self.progress_bar = ttk.Progressbar(main, length=300, mode="determinate")
        self.progress_bar.pack(fill=tk.X, pady=(0, PAD))

        # --- Log ---
        self.log_text = scrolledtext.ScrolledText(main, height=8, wrap=tk.WORD, font=("Consolas", 8))
        self.log_text.pack(fill=tk.BOTH, expand=True)

        self.otp_event = threading.Event()

    def _pick_file(self):
        path = filedialog.askopenfilename(
            title="Pilih File Excel",
            filetypes=[("Excel Files", "*.xlsx *.xls"), ("All Files", "*.*")],
        )
        if path:
            self.file_var.set(path)
            self._load_preview(path)

    def _load_preview(self, path):
        try:
            self.data = convert_excel_to_json(path)
            info = self.data["info"]
            self.info_var.set(
                f"{info['nama']} | NIP: {info['nip']} | Bulan: {self.data['bulan']} | {self.data['total_entries']} entry"
            )
            self._log(f"File dimuat: {self.data['total_entries']} entry, {self.data['total_breakdowns']} breakdown")

            # Auto-fill NIP dari data
            if info["nip"] and not self.nip_var.get():
                self.nip_var.set(info["nip"])

            # Populate breakdown checkboxes
            for w in self.bd_frame.winfo_children():
                w.destroy()
            self.bd_checks = []

            # Select All / Deselect All
            sel_frame = tk.Frame(self.bd_frame)
            sel_frame.pack(fill=tk.X)
            tk.Button(sel_frame, text="Semua", command=self._select_all_bd,
                      font=("Segoe UI", 7)).pack(side=tk.LEFT, padx=(0, 3))
            tk.Button(sel_frame, text="Hapus", command=self._deselect_all_bd,
                      font=("Segoe UI", 7)).pack(side=tk.LEFT)

            for bd in self.data["breakdowns"]:
                var = tk.BooleanVar(value=True)
                name = bd["kegiatan_tugas_jabatan"]
                count = bd["jumlah_entries"]
                # Shorten name for display
                short = name[:45] + "..." if len(name) > 48 else name
                cb = tk.Checkbutton(
                    self.bd_frame, text=f"{short} ({count})",
                    variable=var, anchor="w", font=("Segoe UI", 8),
                )
                cb.pack(fill=tk.X)
                self.bd_checks.append((var, name))

            # Populate date combos
            all_dates = set()
            for bd in self.data["breakdowns"]:
                for entry in bd["entries"]:
                    tgl = entry.get("tanggal", "")
                    if tgl:
                        all_dates.add(tgl)

            sorted_dates = sorted(all_dates, key=self._date_sort_key)
            date_list = [""] + sorted_dates  # empty = no filter
            self.date_from_combo["values"] = date_list
            self.date_to_combo["values"] = date_list
            self.date_from_var.set("")
            self.date_to_var.set("")

        except Exception as e:
            self.info_var.set(f"Error: {e}")
            self._log(f"Error membaca file: {e}")

    def _date_sort_key(self, date_str):
        """Convert DD-MM-YYYY to sortable tuple."""
        try:
            parts = date_str.replace("/", "-").split("-")
            if len(parts) == 3:
                return (int(parts[2]), int(parts[1]), int(parts[0]))
        except (ValueError, IndexError):
            pass
        return (9999, 99, 99)

    def _select_all_bd(self):
        for var, _ in self.bd_checks:
            var.set(True)

    def _deselect_all_bd(self):
        for var, _ in self.bd_checks:
            var.set(False)

    def _log(self, msg):
        timestamp = datetime.now().strftime("%H:%M:%S")
        line = f"[{timestamp}] {msg}\n"
        if threading.current_thread() is threading.main_thread():
            self.log_text.insert(tk.END, line)
            self.log_text.see(tk.END)
        else:
            self.root.after(0, lambda l=line: (self.log_text.insert(tk.END, l), self.log_text.see(tk.END)))

    def _update_progress(self, current, total, text=""):
        pct = int((current / total) * 100) if total > 0 else 0
        self.progress_bar["value"] = pct
        self.progress_var.set(f"{text} ({current}/{total}) - {pct}%")

    def _get_selected_breakdowns(self):
        """Return set of selected breakdown names."""
        return {name for var, name in self.bd_checks if var.get()}

    def _filter_entries_by_date(self, entries):
        """Filter entries by date range if set."""
        date_from = self.date_from_var.get()
        date_to = self.date_to_var.get()
        if not date_from and not date_to:
            return entries

        from_key = self._date_sort_key(date_from) if date_from else (0, 0, 0)
        to_key = self._date_sort_key(date_to) if date_to else (9999, 99, 99)

        filtered = []
        for entry in entries:
            tgl = entry.get("tanggal", "")
            if tgl:
                key = self._date_sort_key(tgl)
                if from_key <= key <= to_key:
                    filtered.append(entry)
        return filtered

    def _start(self):
        if not self.file_var.get():
            messagebox.showwarning("Peringatan", "Pilih file Excel terlebih dahulu!")
            return
        if not self.nip_var.get():
            messagebox.showwarning("Peringatan", "Masukkan NIP!")
            return
        if not self.pwd_var.get():
            messagebox.showwarning("Peringatan", "Masukkan Password!")
            return

        if self.data is None:
            try:
                self.data = convert_excel_to_json(self.file_var.get())
            except Exception as e:
                messagebox.showerror("Error", f"Gagal baca Excel: {e}")
                return

        selected = self._get_selected_breakdowns()
        if not selected:
            messagebox.showwarning("Peringatan", "Pilih minimal 1 kegiatan!")
            return

        self.running = True
        self.paused = False
        self.pause_event.set()
        self.start_btn.config(state=tk.DISABLED)
        self.stop_btn.config(state=tk.NORMAL)
        self.pause_btn.config(state=tk.NORMAL, text="Pause", bg="#3498db")
        self.otp_event.clear()

        thread = threading.Thread(target=self._run_autofill, daemon=True)
        thread.start()

    def _toggle_pause(self):
        if self.paused:
            self.paused = False
            self.pause_event.set()
            self.pause_btn.config(text="Pause", bg="#3498db")
            self._log("DILANJUTKAN")
        else:
            self.paused = True
            self.pause_event.clear()
            self.pause_btn.config(text="Lanjut", bg="#2ecc71")
            self._log("DI-PAUSE — klik 'Lanjut' untuk melanjutkan")

    def _stop(self):
        self.running = False
        self.paused = False
        self.pause_event.set()  # unblock if paused
        self._log("DIHENTIKAN oleh user")
        self.start_btn.config(state=tk.NORMAL)
        self.stop_btn.config(state=tk.DISABLED)
        self.pause_btn.config(state=tk.DISABLED, text="Pause", bg="#3498db")
        self.otp_btn.config(state=tk.DISABLED)
        self.otp_event.set()

    def _otp_done(self):
        self._log("OTP dikonfirmasi, melanjutkan...")
        self.otp_btn.config(state=tk.DISABLED)
        self.otp_event.set()

    def _is_logged_in(self, bulan):
        """Cek apakah sudah login dengan buka halaman aktivitas."""
        import os
        profile_dir = _get_profile_dir()
        self._log(f"  [Debug] Chrome profile: {profile_dir}")
        self._log(f"  [Debug] Profile exists: {os.path.exists(profile_dir)}")

        test_url = AKTIVITAS_URL.format(bulan=bulan)
        safe_get(self.driver, test_url)
        time.sleep(DELAY_LONG)
        dismiss_alert(self.driver)
        current_url = self.driver.current_url.lower()
        page_src = self.driver.page_source.lower()

        self._log(f"  [Debug] URL setelah cek: {current_url[:80]}")

        # Cek apakah halaman login (ada form NIP + password)
        is_login_page = ("login" in page_src and "password" in page_src and "nip" in page_src)
        is_base_url = current_url.rstrip("/") == BASE_URL.lower().rstrip("/")

        if is_login_page or is_base_url:
            self._log(f"  [Debug] Belum login (login_page={is_login_page}, base_url={is_base_url})")
            return False

        self._log(f"  [Debug] Sudah login (halaman bukan login)")
        return True

    def _run_autofill(self):
        try:
            self._log("Membuka Chrome (session tersimpan)...")
            self.driver = create_driver()

            bulan = self.data.get("bulan", "04")

            # Cek apakah sudah login dari session sebelumnya
            self._log("Cek session login...")
            already_logged_in = self._is_logged_in(bulan)

            if already_logged_in:
                self._log("Session masih aktif! Skip login & OTP.")
            else:
                # Login
                self._log(f"Belum login. Login dengan NIP: {self.nip_var.get()}")
                ok = do_login(self.driver, self.nip_var.get(), self.pwd_var.get())
                if not ok:
                    self._log("Login GAGAL! Cek NIP dan Password.")
                    self._finish()
                    return

                self._log("Login terkirim, masukkan OTP...")

                # 2FA
                self._log("=" * 40)
                self._log("Masukkan kode OTP di browser Chrome,")
                self._log("lalu klik tombol 'OTP Sudah Diisi'")
                self._log("=" * 40)
                self.root.after(0, lambda: self.otp_btn.config(state=tk.NORMAL))
                self.otp_event.wait()
                if not self.running:
                    self._finish()
                    return
                time.sleep(DELAY_MEDIUM)

                # Verifikasi login
                if not self._is_logged_in(bulan):
                    self._log("LOGIN BELUM BERHASIL! Pastikan OTP sudah benar.")
                    self._log("Coba lagi: masukkan OTP di browser, lalu klik 'OTP Sudah Diisi'")
                    self.otp_event.clear()
                    self.root.after(0, lambda: self.otp_btn.config(state=tk.NORMAL))
                    self.otp_event.wait()
                    if not self.running:
                        self._finish()
                        return
                    time.sleep(DELAY_MEDIUM)
                    if not self._is_logged_in(bulan):
                        self._log("Login masih gagal. Coba jalankan ulang.")
                        self._finish()
                        return

            self._log("Login berhasil! Mulai auto-fill...")

            # Filter breakdowns & entries berdasarkan pilihan user
            bulan = self.data.get("bulan", "04")
            selected = self._get_selected_breakdowns()
            date_from = self.date_from_var.get()
            date_to = self.date_to_var.get()

            # Build filtered list
            filtered_bds = []
            for bd in self.data.get("breakdowns", []):
                kegiatan = bd["kegiatan_tugas_jabatan"]
                if kegiatan not in selected:
                    continue
                entries = self._filter_entries_by_date(bd["entries"])
                if entries:
                    filtered_bds.append((kegiatan, entries))

            total = sum(len(e) for _, e in filtered_bds)
            if total == 0:
                self._log("Tidak ada entry yang sesuai filter. Cek pilihan kegiatan & tanggal.")
                self._finish()
                return

            # Override Objek Kerja jika user mengisi field
            custom_objek = self.objek_var.get().strip()
            if custom_objek:
                for _, entries in filtered_bds:
                    for entry in entries:
                        entry["objek_kerja"] = custom_objek
                self._log(f"Objek Kerja diganti: \"{custom_objek}\"")

            done = 0
            total_success = 0
            total_fail = 0

            filter_info = ""
            if date_from or date_to:
                filter_info = f", tanggal: {date_from or 'awal'} s/d {date_to or 'akhir'}"
            self._log(f"\nMulai auto-fill: {total} entry, {len(filtered_bds)} kegiatan, bulan={bulan}{filter_info}")

            for bd_idx, (kegiatan, entries) in enumerate(filtered_bds):
                if not self.running:
                    break

                self._log(f"\n{'='*40}")
                self._log(f"Kegiatan {bd_idx+1}/{len(filtered_bds)}: {kegiatan}")
                self._log(f"Jumlah entry: {len(entries)}")

                # Navigasi ke Aktivitas Bulan
                url = AKTIVITAS_URL.format(bulan=bulan)
                safe_get(self.driver, url)
                time.sleep(DELAY_LONG)

                # Cari link realisasi breakdown
                realisasi_url = find_breakdown_link(self.driver, kegiatan, log_fn=self._log)
                if realisasi_url:
                    self._log(f"Navigasi ke realisasi: {realisasi_url[:60]}...")
                    safe_get(self.driver, realisasi_url)
                    time.sleep(DELAY_LONG)
                else:
                    self._log(f"Link realisasi TIDAK DITEMUKAN: {kegiatan}")
                    total_fail += len(entries)
                    done += len(entries)
                    continue

                # Debug: log halaman saat ini
                self._log(f"  [Debug] URL: {self.driver.current_url[:80]}")
                self._log(f"  [Debug] Title: {self.driver.title[:60]}")

                # Ambil URL form Tambah dari tombol
                tambah_url = get_tambah_url(self.driver)
                if tambah_url:
                    self._log(f"Tambah URL: {tambah_url[:60]}...")
                else:
                    self._log("Tidak bisa extract Tambah URL, akan pakai klik tombol")
                    # Debug: log semua tombol/link di halaman
                    from selenium.webdriver.common.by import By
                    all_btns = self.driver.find_elements(By.CSS_SELECTOR,
                        "input[type='button'], button, a.btn")
                    btn_info = []
                    for b in all_btns[:15]:
                        txt = (b.text or b.get_attribute("value") or "").strip()[:30]
                        href = (b.get_attribute("href") or "")[:40]
                        onclick = (b.get_attribute("onclick") or "")[:40]
                        if txt or href or onclick:
                            btn_info.append(f"'{txt}' href={href} onclick={onclick}")
                    self._log(f"  [Debug] Tombol/link: {'; '.join(btn_info[:10])}")

                # Isi entries
                for i, entry in enumerate(entries):
                    if not self.running:
                        break

                    # Cek pause
                    self.pause_event.wait()
                    if not self.running:
                        break

                    done += 1
                    tgl = entry.get("tanggal", "")
                    kw = entry.get("kamus_keyword", "")
                    vol = entry.get("volume", "")
                    objek = entry.get("objek_kerja", "")
                    objek_short = (objek[:40] + "...") if len(objek) > 43 else objek

                    self._log(f"  [{i+1}/{len(entries)}] Tanggal: {tgl}")
                    self._log(f"    Kamus: {kw}")
                    self._log(f"    Volume: {vol}")
                    self._log(f"    Objek Kerja: {objek_short}")

                    self.root.after(0, lambda d=done, t=total, k=kegiatan[:25]:
                                    self._update_progress(d, t, k))

                    try:
                        ok = fill_single_entry(self.driver, entry, log_fn=self._log, tambah_url=tambah_url)
                        if ok:
                            total_success += 1
                            self._log(f"    >> BERHASIL")
                        else:
                            total_fail += 1
                            self._log(f"    >> GAGAL")
                    except Exception as e:
                        total_fail += 1
                        self._log(f"    >> ERROR: {e}")

                    time.sleep(DELAY_SHORT)

            self._log(f"\n{'='*40}")
            self._log(f"SELESAI!")
            self._log(f"  Berhasil: {total_success}")
            self._log(f"  Gagal: {total_fail}")
            self._log(f"{'='*40}")

            self.root.after(0, lambda: self._update_progress(total, total, "Selesai"))
            self.root.after(0, lambda: messagebox.showinfo("Selesai",
                f"Auto-fill selesai!\n\nBerhasil: {total_success}\nGagal: {total_fail}"))

        except Exception as e:
            self._log(f"ERROR: {e}")
            self.root.after(0, lambda: messagebox.showerror("Error", str(e)))

        self._finish()

    def _finish(self):
        self.running = False
        self.paused = False
        self.pause_event.set()
        self.root.after(0, lambda: self.start_btn.config(state=tk.NORMAL))
        self.root.after(0, lambda: self.stop_btn.config(state=tk.DISABLED))
        self.root.after(0, lambda: self.pause_btn.config(state=tk.DISABLED, text="Pause", bg="#3498db"))
        self.root.after(0, lambda: self.otp_btn.config(state=tk.DISABLED))

    def run(self):
        self.root.mainloop()
        if self.driver:
            try:
                self.driver.quit()
            except Exception:
                pass


if __name__ == "__main__":
    app = EMasterGUI()
    app.run()
