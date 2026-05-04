#!/usr/bin/env python3
"""
Skrip auto-fill Aktivitas Kinerja Harian e-MASTER menggunakan Selenium.
Membaca data dari file JSON (hasil konversi Excel) dan mengisi form di e-MASTER.

Alur:
  1. Login (NIP + Password) → Pause untuk 2FA/OTP
  2. Buka halaman Aktivitas Bulan
  3. Untuk setiap breakdown kegiatan:
     a. Klik icon kunci pas (wrench) → masuk halaman realisasi
     b. Untuk setiap entry: klik Tambah → isi form → Simpan
  4. Selesai

Penggunaan:
    python autofill_selenium.py <file.json> --nip 1234567890 --password pass123

Fitur:
    - Login otomatis (NIP + Password)
    - Pause untuk input OTP 2FA secara manual
    - Otomatis navigasi ke setiap breakdown kegiatan
    - Pengisian form aktivitas harian secara otomatis
    - Menangani elemen dinamis dengan retry & wait
    - Mode dry-run untuk simulasi tanpa menyimpan
"""

import argparse
import json
import logging
import sys
import time
from pathlib import Path

try:
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.common.by import By
    from selenium.webdriver.common.keys import Keys
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.webdriver.support.ui import Select, WebDriverWait
except ImportError:
    print("Error: selenium belum terinstall. Jalankan: pip install selenium")
    sys.exit(1)

# ============================================================================
# KONFIGURASI
# ============================================================================
BASE_URL = "https://master.bkd.jatimprov.go.id"
LOGIN_URL = BASE_URL
AKTIVITAS_URL = f"{BASE_URL}/essmedia.php?module=aktifitas_bulan&bulan={{bulan}}"

DELAY_SHORT = 1       # detik
DELAY_MEDIUM = 2      # detik
DELAY_LONG = 3        # detik
WAIT_TIMEOUT = 15     # detik



logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("emaster")


# ============================================================================
# SELENIUM HELPERS
# ============================================================================

def dismiss_alert(driver):
    """Dismiss any alert/popup yang muncul di browser."""
    try:
        alert = driver.switch_to.alert
        alert.accept()
        return True
    except Exception:
        return False


def safe_get(driver, url: str):
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


def _get_profile_dir():
    """Folder profil Chrome di samping script ini untuk simpan cookies."""
    return str(Path(__file__).parent.parent / "emaster_chrome_profile")


def create_driver(headless: bool = False) -> webdriver.Chrome:
    """Buat instance Chrome WebDriver dengan profil tersimpan."""
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


def is_logged_in(driver, bulan: str = "04") -> bool:
    """Cek apakah sudah login dengan buka halaman aktivitas."""
    test_url = AKTIVITAS_URL.format(bulan=bulan)
    safe_get(driver, test_url)
    time.sleep(DELAY_LONG)
    dismiss_alert(driver)
    current_url = driver.current_url.lower()
    page_src = driver.page_source.lower()
    if ("login" in page_src and "password" in page_src and "nip" in page_src) or \
       current_url.rstrip("/") == BASE_URL.lower().rstrip("/"):
        return False
    return True


def find_by_labels(driver, labels: list[str], tag: str = "*"):
    """Cari input/select/textarea berdasarkan label teks.

    Form e-MASTER "Tambah Aktivitas" menggunakan teks bold (<b>)
    sebagai label di atas field input.
    """
    lower = "translate(text(),'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz')"
    lower_attr = "translate(@{attr},'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz')"

    for label_text in labels:
        lt = label_text.lower()

        # 1. Bold text labels (<b>, <strong>) — pola utama form e-MASTER
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
                # Cari di sibling berikutnya
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

        # 2. Cari <label> mengandung teks
        try:
            label_els = driver.find_elements(
                By.XPATH,
                f"//label[contains({lower},'{lt}')]",
            )
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

        # 3. Cari berdasarkan td/th yg mengandung teks
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

        # 4. Cari berdasarkan name/id/placeholder
        for attr in ["name", "id", "placeholder"]:
            try:
                la = lower_attr.format(attr=attr)
                els = driver.find_elements(
                    By.XPATH,
                    f"//{tag}[contains({la},'{lt}')]",
                )
                if els:
                    return els[0]
            except Exception:
                pass

    return None


def safe_set_value(driver, element, value: str):
    """Set nilai input dengan trigger event yang benar."""
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
                element,
                normalize_date(value),
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

    except Exception as e:
        log.warning(f"Error set value: {e}")
        return False


def normalize_date(date_str: str) -> str:
    """Normalisasi format tanggal ke YYYY-MM-DD."""
    if not date_str:
        return ""
    parts = date_str.replace("/", "-").split("-")
    if len(parts) == 3:
        if len(parts[0]) == 4:
            return date_str
        return f"{parts[2]}-{parts[1]}-{parts[0]}"
    return date_str


# ============================================================================
# LOGIN
# ============================================================================

def login(driver, nip: str, password: str):
    """Login ke e-MASTER dengan NIP dan password."""
    nip = nip.replace(" ", "")
    log.info(f"Membuka halaman login: {LOGIN_URL}")
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

    if nip_field:
        safe_set_value(driver, nip_field, nip)
        log.info("NIP terisi")
    else:
        log.error("Field NIP tidak ditemukan!")
        return False

    # Field Password: id="password", name="password"
    pwd_field = None
    try:
        pwd_field = driver.find_element(By.ID, "password")
    except Exception:
        try:
            pwd_field = driver.find_element(By.CSS_SELECTOR, "input[type='password']")
        except Exception:
            pwd_field = find_by_labels(driver, ["password"], "input")

    if pwd_field:
        safe_set_value(driver, pwd_field, password)
        log.info("Password terisi")
    else:
        log.error("Field password tidak ditemukan!")
        return False

    # Klik tombol Login: <button type="submit">Login</button> di #loginform
    try:
        btn = driver.find_element(By.CSS_SELECTOR, "#loginform button[type='submit']")
        btn.click()
        log.info("Klik tombol Login")
        time.sleep(DELAY_LONG)
        return True
    except Exception:
        pass

    for el in driver.find_elements(By.CSS_SELECTOR, "button[type='submit'], input[type='submit']"):
        text = el.get_attribute("value") or el.text or ""
        if "login" in text.lower() or "masuk" in text.lower():
            el.click()
            log.info("Klik tombol Login")
            time.sleep(DELAY_LONG)
            return True

    log.error("Tombol Login tidak ditemukan!")
    return False


def handle_2fa(driver, bulan: str = "04"):
    """Handle 2FA - menunggu input OTP manual dari user, lalu verifikasi login."""
    log.info("=" * 50)
    log.info("Masukkan kode OTP di browser!")
    log.info("Setelah berhasil login, tekan ENTER di terminal ini.")
    log.info("=" * 50)
    input(">>> Tekan ENTER setelah memasukkan OTP dan berhasil login... ")
    time.sleep(DELAY_MEDIUM)

    # Verifikasi login: coba buka halaman aktivitas
    test_url = AKTIVITAS_URL.format(bulan=bulan)
    log.info(f"Verifikasi login: membuka {test_url}")
    safe_get(driver, test_url)
    time.sleep(DELAY_LONG)

    current_url = driver.current_url.lower()
    page_src = driver.page_source.lower()
    if ("login" in page_src and "password" in page_src and "nip" in page_src) or \
       current_url.rstrip("/") == BASE_URL.lower().rstrip("/"):
        log.warning("Login belum berhasil! Coba masukkan OTP lagi.")
        input(">>> Tekan ENTER setelah login berhasil... ")
        time.sleep(DELAY_MEDIUM)
        safe_get(driver, test_url)
        time.sleep(DELAY_LONG)

    log.info("Login berhasil!")
    return True


# ============================================================================
# NAVIGASI & PENGISIAN
# ============================================================================

def find_breakdown_link(driver, kegiatan_name: str):
    """Cari link realisasi (icon kunci pas) untuk breakdown tertentu.

    Pada halaman Aktivitas Bulan, setiap breakdown punya baris tabel dengan
    nama kegiatan dan icon wrench (kunci pas) untuk masuk ke halaman realisasi.
    """
    rows = driver.find_elements(By.CSS_SELECTOR, "table#sort-table1 tbody tr")
    for row in rows:
        try:
            row_text = row.text.lower()
            if kegiatan_name.lower() in row_text:
                link = row.find_element(By.CSS_SELECTOR, "a[href*='realisasi']")
                return link
        except Exception:
            continue

    # Fallback: cari semua link realisasi dan cocokkan
    links = driver.find_elements(By.CSS_SELECTOR, "a[href*='realisasi']")
    for link in links:
        try:
            parent_row = link.find_element(By.XPATH, "./ancestor::tr")
            if kegiatan_name.lower() in parent_row.text.lower():
                return link
        except Exception:
            continue

    return None


def find_tambah_button(driver):
    """Cari tombol Tambah di halaman realisasi."""
    for el in driver.find_elements(By.CSS_SELECTOR, "a, button, input[type='button'], input[type='submit']"):
        text = (el.text or el.get_attribute("value") or "").lower()
        if "tambah" in text or "add" in text or "input baru" in text:
            return el
    for el in driver.find_elements(By.CSS_SELECTOR, "a.btn, button"):
        icons = el.find_elements(By.CSS_SELECTOR, ".ui-icon-plus, .ui-icon-plusthick")
        if icons:
            return el
    return None


def find_simpan_button(driver):
    """Cari tombol Simpan/Save."""
    for el in driver.find_elements(By.CSS_SELECTOR, "a, button, input[type='button'], input[type='submit']"):
        text = (el.text or el.get_attribute("value") or "").lower()
        if "simpan" in text or "save" in text or "submit" in text or "kirim" in text:
            return el
    return None


def _search_and_click_kamus(driver, keyword: str) -> bool:
    """Cari keyword di popup Kamus yang sudah aktif, lalu klik hasil."""
    search_input = None
    for selector in ["input[type='text']", "input[name*='cari']",
                     "input[name*='search']", "input[id*='cari']",
                     "input[id*='search']", "input.text"]:
        try:
            search_input = driver.find_element(By.CSS_SELECTOR, selector)
            if search_input:
                break
        except Exception:
            continue

    if search_input:
        search_input.clear()
        search_input.send_keys(keyword)
        log.info(f"    Ketik '{keyword}' di pencarian Kamus")
        time.sleep(DELAY_SHORT)
    else:
        log.warning("    Input pencarian Kamus tidak ditemukan")

    # Klik tombol "Cari"
    cari_clicked = False
    for btn in driver.find_elements(By.CSS_SELECTOR,
            "input[type='button'], input[type='submit'], button, a"):
        text = (btn.text or btn.get_attribute("value") or "").strip().lower()
        if text in ("cari", "search"):
            btn.click()
            log.info("    Klik Cari")
            time.sleep(DELAY_MEDIUM)
            cari_clicked = True
            break
    if not cari_clicked:
        log.warning("    Tombol 'Cari' tidak ditemukan")

    # Klik hasil pencarian
    cells = driver.find_elements(By.CSS_SELECTOR, "td")
    for cell in cells:
        text = cell.text.strip()
        if keyword.lower() in text.lower():
            links = cell.find_elements(By.CSS_SELECTOR, "a")
            if links:
                links[0].click()
            else:
                cell.click()
            log.info(f"    Klik hasil: '{text[:50]}'")
            time.sleep(DELAY_MEDIUM)
            return True

    log.warning(f"    Hasil pencarian '{keyword}' tidak ditemukan di Kamus")
    return False


def handle_detail_aktivitas_popup(driver, keyword: str, dry_run: bool = False) -> bool:
    """Handle popup Kamus Aktifitas Harian untuk field Detail Aktivitas.

    Mendukung popup sebagai: window baru, iframe, atau modal dialog.

    Alur:
      1. Klik tombol "..." di samping field Detail Aktivitas
      2. Popup Kamus terbuka (window baru / iframe / modal)
      3. Ketik keyword di kotak pencarian
      4. Klik "Cari"
      5. Klik hasil pencarian
    """
    # Cari tombol "..." (titik 3)
    dot_btn = None
    for el in driver.find_elements(By.CSS_SELECTOR, "input[type='button'], button, a"):
        text = (el.text or el.get_attribute("value") or "").strip()
        if text in ("...", "\u2026"):
            dot_btn = el
            break

    if not dot_btn:
        log.warning("    Tombol '...' untuk Detail Aktivitas tidak ditemukan")
        return False

    if dry_run:
        log.info(f"    [DRY-RUN] Klik '...' dan cari '{keyword}'")
        return True

    # Simpan handle window utama
    main_window = driver.current_window_handle
    windows_before = set(driver.window_handles)

    dot_btn.click()
    log.info("    Klik tombol '...' untuk buka Kamus")
    time.sleep(DELAY_LONG)

    # Deteksi jenis popup
    windows_after = set(driver.window_handles)
    new_windows = windows_after - windows_before
    popup_type = None

    if new_windows:
        driver.switch_to.window(list(new_windows)[0])
        popup_type = "window"
        log.info("    Popup Kamus: window baru")
    else:
        # Cek iframe
        iframes = driver.find_elements(By.CSS_SELECTOR, "iframe")
        for iframe in iframes:
            try:
                src = iframe.get_attribute("src") or ""
                if "kamus" in src.lower() or iframe.is_displayed():
                    driver.switch_to.frame(iframe)
                    popup_type = "iframe"
                    log.info("    Popup Kamus: iframe")
                    break
            except Exception:
                continue

    if not popup_type:
        # Cek modal dialog
        modals = driver.find_elements(By.CSS_SELECTOR,
            "div.modal, div[role='dialog'], div.ui-dialog, div.popup, "
            "#dialog, #popup, div[style*='display: block']")
        for modal in modals:
            try:
                if modal.is_displayed():
                    popup_type = "modal"
                    log.info("    Popup Kamus: modal dialog")
                    break
            except Exception:
                continue

    if not popup_type:
        log.warning("    Popup Kamus tidak ditemukan (tidak ada window/iframe/modal baru)")
        return False

    try:
        result = _search_and_click_kamus(driver, keyword)

        # Kembali ke konteks utama
        if popup_type == "window":
            try:
                driver.switch_to.window(main_window)
            except Exception:
                pass
        elif popup_type == "iframe":
            driver.switch_to.default_content()

        return result

    except Exception as e:
        log.warning(f"    Error di popup Kamus: {e}")

    # Cleanup: kembali ke konteks utama
    try:
        if popup_type == "window":
            try:
                driver.close()
            except Exception:
                pass
            driver.switch_to.window(main_window)
        elif popup_type == "iframe":
            driver.switch_to.default_content()
    except Exception:
        pass

    return False


def fill_single_entry(driver, entry: dict, dry_run: bool = False) -> bool:
    """Isi satu entry aktivitas.

    Alur:
      1. Di halaman realisasi, klik Tambah → navigasi ke halaman form
      2. Isi field pada form "Tambah Aktivitas":
         - Tanggal Aktivitas (dari Excel)
         - Detail Aktivitas (via popup Kamus → cari "Manajemen Asuhan Keperawatan")
         - Satuan & WPT (otomatis dari Kamus, tidak perlu diisi)
         - Volume (dari Excel)
         - Objek Kerja / Topik (dari Excel)
      3. Klik Save → kembali ke halaman realisasi
    """
    log.info(f"  Mengisi: tgl={entry.get('tanggal')}, objek={entry.get('objek_kerja', '')[:40]}...")

    dismiss_alert(driver)

    # Klik Tambah — navigasi ke halaman form
    tambah = find_tambah_button(driver)
    if tambah:
        if not dry_run:
            tambah.click()
        log.info("  Klik Tambah")
        time.sleep(DELAY_LONG)
    else:
        log.warning("  Tombol Tambah tidak ditemukan")
        return False

    filled = 0

    # 1. Isi Tanggal Aktivitas
    tanggal = entry.get("tanggal", "")
    if tanggal:
        el = find_by_labels(driver, ["tanggal aktivitas", "tanggal"])
        if el:
            if not dry_run:
                if safe_set_value(driver, el, str(tanggal)):
                    filled += 1
                    log.info(f"    tanggal aktivitas: '{tanggal}'")
            else:
                filled += 1
                log.info(f"    [DRY-RUN] tanggal aktivitas: '{tanggal}'")

    # 2. Detail Aktivitas — via popup Kamus Aktifitas Harian
    # Kata kunci diambil dari entry.kamus_keyword (di-set oleh converter)
    kamus_keyword = entry.get("kamus_keyword") or entry.get("detail_aktivitas", "")
    log.info(f"    Detail Aktivitas keyword: '{kamus_keyword}'")
    if handle_detail_aktivitas_popup(driver, kamus_keyword, dry_run):
        filled += 1
    else:
        # Fallback: coba isi langsung
        if kamus_keyword:
            el = find_by_labels(driver, ["detail aktivitas", "detail"])
            if el:
                safe_set_value(driver, el, str(kamus_keyword))
                filled += 1

    # 3. Satuan & WPT — otomatis terisi dari Kamus, SKIP
    log.info("    satuan & wpt: otomatis dari Kamus")

    # 4. Isi Volume
    volume = entry.get("volume", "")
    if volume:
        el = find_by_labels(driver, ["volume"])
        if el:
            if not dry_run:
                if safe_set_value(driver, el, str(volume)):
                    filled += 1
                    log.info(f"    volume: '{volume}'")
            else:
                filled += 1
                log.info(f"    [DRY-RUN] volume: '{volume}'")

    # 5. Isi Objek Kerja / Topik
    objek = entry.get("objek_kerja", "")
    if objek:
        el = find_by_labels(driver, ["objek kerja", "topik"])
        if el:
            if not dry_run:
                if safe_set_value(driver, el, str(objek)):
                    filled += 1
                    log.info(f"    objek kerja: '{str(objek)[:60]}'")
            else:
                filled += 1
                log.info(f"    [DRY-RUN] objek kerja: '{str(objek)[:60]}'")

    # Klik Save — kembali ke halaman realisasi
    if filled > 0 and not dry_run:
        time.sleep(DELAY_SHORT)
        simpan = find_simpan_button(driver)
        if simpan:
            simpan.click()
            log.info("  Klik Save")
            time.sleep(DELAY_LONG)
        else:
            log.warning("  Tombol Save tidak ditemukan!")

    return filled > 0


def _navigate_to_realisasi(driver, bulan: str, kegiatan: str, dry_run: bool = False):
    """Navigasi ke halaman realisasi breakdown tertentu.

    Returns: True jika berhasil, False jika gagal.
    """
    aktivitas_url = AKTIVITAS_URL.format(bulan=bulan)
    safe_get(driver, aktivitas_url)
    time.sleep(DELAY_LONG)

    link = find_breakdown_link(driver, kegiatan)
    if link:
        if not dry_run:
            link.click()
        time.sleep(DELAY_LONG)
        return True

    return False


def _is_on_realisasi_page(driver):
    """Cek apakah masih di halaman realisasi (ada tombol Tambah)."""
    return find_tambah_button(driver) is not None


def process_breakdown(driver, breakdown: dict, bulan: str, dry_run: bool = False):
    """Proses satu breakdown: navigasi ke realisasi dan isi semua entry."""
    kegiatan = breakdown["kegiatan_tugas_jabatan"]
    entries = breakdown["entries"]
    log.info(f"\n{'='*60}")
    log.info(f"Breakdown: {kegiatan}")
    log.info(f"Jumlah entry: {len(entries)}")
    log.info(f"{'='*60}")

    # Navigasi pertama ke halaman realisasi
    if not _navigate_to_realisasi(driver, bulan, kegiatan, dry_run):
        log.error(f"Link realisasi untuk '{kegiatan}' TIDAK DITEMUKAN!")
        log.error("Pastikan nama kegiatan cocok dengan yang ada di e-MASTER.")
        return 0, len(entries)

    log.info(f"Berhasil buka halaman realisasi: {kegiatan[:50]}")

    # Isi setiap entry
    success_count = 0
    fail_count = 0
    for i, entry in enumerate(entries):
        log.info(f"\n--- Entry {i+1}/{len(entries)} ---")

        # Cek apakah masih di halaman realisasi, jika tidak → navigasi ulang
        if i > 0 and not _is_on_realisasi_page(driver):
            log.info("  Halaman realisasi hilang, navigasi ulang...")
            if not _navigate_to_realisasi(driver, bulan, kegiatan, dry_run):
                log.error("  Gagal kembali ke halaman realisasi!")
                fail_count += 1
                continue

        try:
            ok = fill_single_entry(driver, entry, dry_run)
            if ok:
                success_count += 1
            else:
                fail_count += 1
        except Exception as e:
            log.error(f"  Error: {e}")
            fail_count += 1
        time.sleep(DELAY_SHORT)

    return success_count, fail_count


def _date_sort_key(date_str: str) -> tuple:
    """Convert DD-MM-YYYY to sortable tuple (YYYY, MM, DD)."""
    try:
        parts = date_str.replace("/", "-").split("-")
        if len(parts) == 3:
            return (int(parts[2]), int(parts[1]), int(parts[0]))
    except (ValueError, IndexError):
        pass
    return (9999, 99, 99)


def filter_entries_by_date(entries: list, date_from: str = None, date_to: str = None) -> list:
    """Filter entries berdasarkan rentang tanggal."""
    if not date_from and not date_to:
        return entries

    from_key = _date_sort_key(date_from) if date_from else (0, 0, 0)
    to_key = _date_sort_key(date_to) if date_to else (9999, 99, 99)

    filtered = []
    for entry in entries:
        tgl = entry.get("tanggal", "")
        if tgl:
            key = _date_sort_key(tgl)
            if from_key <= key <= to_key:
                filtered.append(entry)
    return filtered


def run_autofill(driver, data: dict, dry_run: bool = False,
                 date_from: str = None, date_to: str = None):
    """Jalankan auto-fill untuk semua breakdown."""
    breakdowns = data.get("breakdowns", [])
    if not breakdowns:
        log.error("Tidak ada breakdown dalam data!")
        return

    bulan = data.get("bulan", "04")
    info = data.get("info", {})

    log.info(f"Nama: {info.get('nama', '-')}")
    log.info(f"NIP: {info.get('nip', '-')}")
    log.info(f"Total entry: {data.get('total_entries', 0)}")
    log.info(f"Jumlah breakdown: {len(breakdowns)}")
    log.info(f"Bulan: {bulan}")
    if date_from or date_to:
        log.info(f"Filter tanggal: {date_from or 'awal'} s/d {date_to or 'akhir'}")
    if dry_run:
        log.info("MODE: DRY-RUN (tidak menyimpan)")

    total_success = 0
    total_fail = 0

    for bd in breakdowns:
        # Filter entries berdasarkan tanggal jika ada
        if date_from or date_to:
            original_entries = bd["entries"]
            bd = dict(bd)
            bd["entries"] = filter_entries_by_date(original_entries, date_from, date_to)
            if not bd["entries"]:
                log.info(f"Skip '{bd['kegiatan_tugas_jabatan']}' — tidak ada entry dalam rentang tanggal")
                continue
            log.info(f"'{bd['kegiatan_tugas_jabatan']}': {len(bd['entries'])}/{len(original_entries)} entry sesuai filter")

        s, f = process_breakdown(driver, bd, bulan, dry_run)
        total_success += s
        total_fail += f

    log.info(f"\n{'='*60}")
    log.info(f"SELESAI!")
    log.info(f"  Berhasil: {total_success}")
    log.info(f"  Gagal: {total_fail}")
    log.info(f"{'='*60}")


# ============================================================================
# MAIN
# ============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Auto-fill Aktivitas Kinerja Harian e-MASTER dengan Selenium"
    )
    parser.add_argument("json_file", help="Path ke file JSON (hasil convert_excel.py)")
    parser.add_argument("--nip", help="NIP untuk login", default=None)
    parser.add_argument("--password", help="Password untuk login", default=None)
    parser.add_argument("--headless", action="store_true", help="Jalankan tanpa tampilan browser")
    parser.add_argument("--dry-run", action="store_true", help="Simulasi tanpa menyimpan")
    parser.add_argument("--skip-login", action="store_true", help="Lewati proses login (jika sudah login)")
    parser.add_argument("--date-from", help="Tanggal mulai filter (format: DD-MM-YYYY)", default=None)
    parser.add_argument("--date-to", help="Tanggal akhir filter (format: DD-MM-YYYY)", default=None)

    args = parser.parse_args()

    # Baca JSON
    json_path = Path(args.json_file)
    if not json_path.exists():
        log.error(f"File '{json_path}' tidak ditemukan!")
        sys.exit(1)

    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    log.info(f"File: {json_path}")
    log.info(f"Breakdowns: {data.get('total_breakdowns', 0)}")
    log.info(f"Total entries: {data.get('total_entries', 0)}")

    # Buat driver
    driver = create_driver(headless=args.headless)

    try:
        bulan = data.get("bulan", "04")

        # Cek apakah sudah login dari session/cookies sebelumnya
        if not args.skip_login:
            log.info("Cek session login dari cookies tersimpan...")
            if is_logged_in(driver, bulan):
                log.info("Session masih aktif! Skip login & OTP.")
            else:
                log.info("Belum login. Memulai proses login...")
                nip = args.nip
                password = args.password

                if not nip:
                    nip = input("Masukkan NIP: ").strip()
                if not password:
                    import getpass
                    password = getpass.getpass("Masukkan Password: ").strip()

                if not login(driver, nip, password):
                    log.error("Login gagal!")
                    return

                handle_2fa(driver, bulan=bulan)

        # Jalankan auto-fill
        run_autofill(driver, data, dry_run=args.dry_run,
                     date_from=args.date_from, date_to=args.date_to)

        log.info("\nBrowser tetap terbuka untuk verifikasi.")
        input("Tekan ENTER untuk menutup browser...")

    except KeyboardInterrupt:
        log.info("\nDihentikan oleh user")
    finally:
        driver.quit()


if __name__ == "__main__":
    main()
