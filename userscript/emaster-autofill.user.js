// ==UserScript==
// @name         e-MASTER Aktivitas Harian Auto Fill
// @namespace    https://github.com/gilelundro01/emaster
// @version      3.0.0
// @description  Skrip pengisian otomatis Aktivitas Kinerja Harian untuk e-MASTER BKD Jatim. Mendukung navigasi halaman Tambah Aktivitas dan state persist.
// @author       gilelundro01
// @match        https://master.bkd.jatimprov.go.id/*
// @match        http://master.bkd.jatimprov.go.id/*
// @grant        GM_setValue
// @grant        GM_getValue
// @grant        GM_deleteValue
// @grant        GM_registerMenuCommand
// @run-at       document-idle
// ==/UserScript==

(function () {
  "use strict";

  // =========================================================================
  // KONFIGURASI
  // =========================================================================
  const CONFIG = {
    DELAY_BEFORE_FILL: 1500,
    DELAY_BEFORE_SAVE: 800,
    DELAY_AFTER_SAVE: 1000,
    DELAY_POPUP: 1500,
  };

  // =========================================================================
  // CSS PANEL
  // =========================================================================
  const PANEL_CSS = `
    #emaster-af-panel {
      position: fixed; top: 10px; right: 10px; z-index: 99999;
      background: #fff; border: 2px solid #1565C0; border-radius: 8px;
      box-shadow: 0 4px 24px rgba(0,0,0,0.18); font-family: Arial, sans-serif;
      font-size: 13px; width: 400px; max-height: 92vh; overflow-y: auto; display: none;
    }
    #emaster-af-panel.visible { display: block; }
    .af-header {
      background: #1565C0; color: #fff; padding: 10px 14px; font-weight: bold;
      font-size: 14px; display: flex; justify-content: space-between;
      align-items: center; cursor: move; border-radius: 6px 6px 0 0;
    }
    .af-header button { background: none; border: none; color: #fff; font-size: 18px; cursor: pointer; }
    .af-body { padding: 12px 14px; }
    .af-group { margin-bottom: 6px; }
    .af-group label { display: block; font-weight: bold; margin-bottom: 2px; color: #333; font-size: 11px; }
    .af-group input, .af-group select, .af-group textarea {
      width: 100%; padding: 5px 8px; border: 1px solid #ccc; border-radius: 4px;
      font-size: 12px; box-sizing: border-box;
    }
    .af-actions { display: flex; gap: 6px; margin-top: 10px; flex-wrap: wrap; }
    .af-btn {
      padding: 7px 14px; border: none; border-radius: 4px; cursor: pointer;
      font-size: 12px; font-weight: bold; flex: 1; min-width: 80px; text-align: center;
    }
    .af-btn-run { background: #4CAF50; color: #fff; }
    .af-btn-run:hover { background: #388E3C; }
    .af-btn-stop { background: #f44336; color: #fff; }
    .af-btn-stop:hover { background: #d32f2f; }
    .af-btn-scan { background: #FF9800; color: #fff; }
    .af-btn-scan:hover { background: #F57C00; }
    .af-btn-load { background: #9C27B0; color: #fff; }
    .af-btn-load:hover { background: #7B1FA2; }
    #emaster-af-toggle {
      position: fixed; top: 10px; right: 10px; z-index: 99998;
      background: #1565C0; color: #fff; border: none; border-radius: 50%;
      width: 48px; height: 48px; font-size: 22px; cursor: pointer;
      box-shadow: 0 2px 12px rgba(0,0,0,0.25); display: flex;
      align-items: center; justify-content: center;
    }
    #emaster-af-toggle:hover { background: #0D47A1; }
    #emaster-af-log {
      margin-top: 8px; padding: 8px; background: #f5f5f5; border-radius: 4px;
      max-height: 200px; overflow-y: auto; font-size: 11px; color: #555;
      font-family: monospace;
    }
    .log-ok { color: #2E7D32; }
    .log-warn { color: #EF6C00; }
    .log-err { color: #C62828; }
    .log-info { color: #1565C0; }
    .af-section-title {
      font-weight: bold; color: #1565C0; margin: 10px 0 5px; font-size: 13px;
      border-bottom: 1px solid #e0e0e0; padding-bottom: 3px;
    }
    .af-progress {
      margin-top: 8px; padding: 6px; background: #E3F2FD; border-radius: 4px;
      font-size: 12px; color: #1565C0;
    }
    .af-progress-bar {
      height: 6px; background: #BBDEFB; border-radius: 3px; margin-top: 4px; overflow: hidden;
    }
    .af-progress-fill {
      height: 100%; background: #1565C0; border-radius: 3px; transition: width 0.3s;
    }
    .af-bd-list { margin: 6px 0; padding: 0; list-style: none; }
    .af-bd-item {
      padding: 6px 8px; margin: 3px 0; background: #f0f4ff; border-radius: 4px;
      font-size: 11px; display: flex; justify-content: space-between; align-items: center;
    }
    .af-bd-item .name { flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
    .af-bd-item .count { font-weight: bold; color: #1565C0; margin-left: 8px; }
    .af-bd-item .status { margin-left: 8px; font-size: 10px; }
    .af-auto-status {
      margin-top: 8px; padding: 8px; border-radius: 4px;
      font-size: 12px; font-weight: bold;
    }
    .af-auto-status.active { background: #C8E6C9; color: #2E7D32; }
    .af-auto-status.idle { background: #E0E0E0; color: #616161; }
  `;

  // =========================================================================
  // UTILITAS
  // =========================================================================

  function sleep(ms) {
    return new Promise((resolve) => setTimeout(resolve, ms));
  }

  /**
   * Convert DD-MM-YYYY to sortable array [YYYY, MM, DD].
   */
  function dateSortKey(dateStr) {
    if (!dateStr) return [9999, 99, 99];
    const parts = dateStr.replace(/\//g, "-").split("-");
    if (parts.length === 3) {
      return [parseInt(parts[2], 10), parseInt(parts[1], 10), parseInt(parts[0], 10)];
    }
    return [9999, 99, 99];
  }

  /**
   * Bandingkan dua date key arrays.
   * Returns: -1 if a < b, 0 if a == b, 1 if a > b
   */
  function compareDateKeys(a, b) {
    for (let i = 0; i < 3; i++) {
      if (a[i] < b[i]) return -1;
      if (a[i] > b[i]) return 1;
    }
    return 0;
  }

  /**
   * Filter entries berdasarkan rentang tanggal.
   */
  function filterEntriesByDate(entries, dateFrom, dateTo) {
    if (!dateFrom && !dateTo) return entries;
    const fromKey = dateFrom ? dateSortKey(dateFrom) : [0, 0, 0];
    const toKey = dateTo ? dateSortKey(dateTo) : [9999, 99, 99];
    return entries.filter(entry => {
      const tgl = entry.tanggal || "";
      if (!tgl) return false;
      const key = dateSortKey(tgl);
      return compareDateKeys(key, fromKey) >= 0 && compareDateKeys(key, toKey) <= 0;
    });
  }

  /**
   * Deteksi jenis halaman e-MASTER saat ini.
   * Returns: "tambah" | "realisasi" | "aktivitas_bulan" | "unknown"
   */
  function detectPageType() {
    const url = window.location.href;
    const params = new URLSearchParams(window.location.search);
    const pageText = document.body?.textContent || "";

    // Halaman "Tambah Aktivitas" - form input baru
    if (pageText.includes("Tambah Aktivitas") &&
        document.querySelector('input[type="submit"][value="Save"], button')) {
      const saveBtn = findSaveButton();
      if (saveBtn) return "tambah";
    }

    // Halaman realisasi breakdown (ada tabel entries + tombol Tambah)
    if (params.get("act") === "realisasi" || url.includes("realisasi")) {
      return "realisasi";
    }

    // Halaman Aktivitas Bulan (daftar breakdown dengan icon kunci pas)
    if (params.get("module") === "aktifitas_bulan" && !params.get("act")) {
      return "aktivitas_bulan";
    }

    return "unknown";
  }

  /**
   * Cari field input berdasarkan teks label di halaman.
   * Form e-MASTER menggunakan teks bold (<b>) sebagai label di atas field.
   */
  function findFieldByLabel(labelText) {
    const normalized = labelText.toLowerCase().trim();

    // 1. Bold text labels (<b>, <strong>) - pola utama form e-MASTER
    for (const el of document.querySelectorAll("b, strong")) {
      if (el.textContent.toLowerCase().trim().includes(normalized)) {
        // Input field setelah label bold
        let next = el.nextElementSibling;
        while (next) {
          if (next.matches("input, select, textarea")) return next;
          const child = next.querySelector("input, select, textarea");
          if (child) return child;
          next = next.nextElementSibling;
        }
        // Atau di parent yang sama
        const parent = el.parentElement;
        if (parent) {
          const inputs = parent.querySelectorAll("input, select, textarea");
          for (const inp of inputs) {
            if (inp.offsetTop >= el.offsetTop) return inp;
          }
          if (inputs.length > 0) return inputs[inputs.length - 1];
        }
      }
    }

    // 2. <label for="...">
    for (const label of document.querySelectorAll("label")) {
      if (label.textContent.toLowerCase().includes(normalized)) {
        const forId = label.getAttribute("for");
        if (forId) { const t = document.getElementById(forId); if (t) return t; }
        const inner = label.querySelector("input, select, textarea");
        if (inner) return inner;
        let sib = label.nextElementSibling;
        while (sib) {
          if (sib.matches("input, select, textarea")) return sib;
          const child = sib.querySelector("input, select, textarea");
          if (child) return child;
          sib = sib.nextElementSibling;
        }
      }
    }

    // 3. Table cells / div containers
    for (const cell of document.querySelectorAll("td, th, div, span, p")) {
      if (cell.textContent.toLowerCase().includes(normalized) && cell.textContent.length < normalized.length + 40) {
        const parent = cell.parentElement;
        if (parent) {
          const inputs = parent.querySelectorAll("input, select, textarea");
          if (inputs.length > 0) return inputs[0];
        }
        const next = cell.nextElementSibling;
        if (next) {
          const inp = next.querySelector("input, select, textarea");
          if (inp) return inp;
        }
      }
    }

    // 4. Attributes (name, id, placeholder)
    for (const inp of document.querySelectorAll("input, select, textarea")) {
      for (const attr of ["placeholder", "name", "id", "aria-label", "title"]) {
        const val = inp.getAttribute(attr);
        if (val && val.toLowerCase().includes(normalized)) return inp;
      }
    }

    return null;
  }

  function setFieldValue(element, value) {
    if (!element || value === undefined || value === null) return false;
    const val = String(value);
    const tag = element.tagName.toLowerCase();
    const type = (element.getAttribute("type") || "").toLowerCase();

    if (tag === "select") {
      for (const opt of element.options) {
        if (opt.value === val || opt.textContent.trim().toLowerCase() === val.toLowerCase() ||
            opt.textContent.toLowerCase().includes(val.toLowerCase())) {
          element.value = opt.value;
          triggerEvents(element);
          return true;
        }
      }
      return false;
    }

    const setter = Object.getOwnPropertyDescriptor(
      tag === "textarea" ? HTMLTextAreaElement.prototype : HTMLInputElement.prototype, "value"
    )?.set;
    if (setter) setter.call(element, val);
    else element.value = val;
    triggerEvents(element);
    return true;
  }

  function triggerEvents(el) {
    for (const e of ["focus", "input", "change", "blur", "keyup"]) {
      el.dispatchEvent(new Event(e, { bubbles: true }));
    }
  }

  // =========================================================================
  // TOMBOL FINDER
  // =========================================================================

  function findTambahButton() {
    // Cari link/button "Tambah" di halaman realisasi
    for (const el of document.querySelectorAll("a, button, input[type='button'], input[type='submit']")) {
      const text = el.textContent?.toLowerCase().trim() || el.value?.toLowerCase().trim() || "";
      if (text === "tambah" || text === "tambah aktivitas" || text.includes("tambah")) {
        return el;
      }
    }
    return null;
  }

  function findSaveButton() {
    for (const el of document.querySelectorAll("input[type='submit'], button, a")) {
      const text = el.textContent?.toLowerCase().trim() || el.value?.toLowerCase().trim() || "";
      if (text === "save" || text === "simpan" || text === "submit") {
        return el;
      }
    }
    return null;
  }

  // =========================================================================
  // STATE MANAGEMENT (persist across page navigations)
  // =========================================================================

  function getAutoFillState() {
    const raw = GM_getValue("emaster_autofill_state", null);
    if (!raw) return null;
    try { return JSON.parse(raw); } catch { return null; }
  }

  function setAutoFillState(state) {
    GM_setValue("emaster_autofill_state", JSON.stringify(state));
  }

  function clearAutoFillState() {
    GM_deleteValue("emaster_autofill_state");
  }

  function isAutoFillRunning() {
    const state = getAutoFillState();
    return state && state.running;
  }

  // =========================================================================
  // AUTO-FILL ENGINE
  // =========================================================================

  let logContainer = null;

  function addLog(msg, type = "info") {
    if (!logContainer) return;
    const line = document.createElement("div");
    line.className = `log-${type}`;
    const time = new Date().toLocaleTimeString("id-ID");
    line.textContent = `[${time}] ${msg}`;
    logContainer.insertBefore(line, logContainer.firstChild);
    while (logContainer.children.length > 150) logContainer.removeChild(logContainer.lastChild);
  }

  function updateProgress(current, total, text) {
    const progText = document.getElementById("af-progress-text");
    const progFill = document.getElementById("af-progress-fill");
    if (progText) progText.textContent = `${text} (${current}/${total})`;
    if (progFill) progFill.style.width = `${(current / total) * 100}%`;
  }

  function updateAutoStatus(active, text) {
    const el = document.getElementById("af-auto-status");
    if (!el) return;
    el.className = "af-auto-status " + (active ? "active" : "idle");
    el.textContent = text;
  }

  /**
   * Cari dan klik tombol "..." (titik 3) di samping field "Detail Aktivitas".
   * Tombol ini membuka popup Kamus Aktifitas Harian.
   */
  function findDetailAktivitasDotButton() {
    // Cari button/input bertipe button dengan teks "..."
    for (const el of document.querySelectorAll("input[type='button'], button")) {
      const text = el.textContent?.trim() || el.value?.trim() || "";
      if (text === "..." || text === "…") return el;
    }
    // Fallback: cari di dekat label "Detail Aktivitas"
    for (const b of document.querySelectorAll("b, strong")) {
      if (b.textContent.toLowerCase().includes("detail aktivitas")) {
        const parent = b.parentElement;
        if (parent) {
          const btns = parent.querySelectorAll("input[type='button'], button");
          for (const btn of btns) return btn;
        }
        // Cari di sibling setelah textarea
        let sib = b.nextElementSibling;
        while (sib) {
          if (sib.matches("input[type='button'], button")) return sib;
          const btn = sib.querySelector("input[type='button'], button");
          if (btn) return btn;
          sib = sib.nextElementSibling;
        }
      }
    }
    return null;
  }

  /**
   * Handle popup Kamus Aktifitas Harian.
   * Cari keyword di popup, klik "Cari", lalu klik hasil pencarian.
   *
   * Popup bisa berupa window.open popup atau iframe.
   */
  async function handleKamusPopup(keyword) {
    addLog(`Mencari popup Kamus...`, "info");
    await sleep(CONFIG.DELAY_POPUP);

    // Coba cari popup window yang baru terbuka
    // Tampermonkey berjalan di konteks halaman utama, jadi kita perlu
    // mendeteksi apakah popup dibuka sebagai window baru atau iframe

    // Strategi 1: Cek apakah ada iframe baru
    const iframes = document.querySelectorAll("iframe");
    for (const iframe of iframes) {
      try {
        const iframeDoc = iframe.contentDocument || iframe.contentWindow?.document;
        if (iframeDoc && iframeDoc.body?.textContent?.includes("Kamus Aktifitas")) {
          return await searchInKamusDocument(iframeDoc, keyword);
        }
      } catch (e) {
        // Cross-origin iframe, skip
      }
    }

    // Strategi 2: Popup sebagai window baru - kita tidak bisa akses langsung
    // dari Tampermonkey. Simpan keyword di GM storage, dan beri instruksi.
    // Tapi kita bisa coba window.open workaround:
    // Sebenarnya popup biasanya bisa diakses via window.open reference

    addLog(`Popup Kamus mungkin terbuka di window baru`, "info");
    addLog(`Keyword: "${keyword}" - cari manual di popup jika perlu`, "warn");

    // Strategi 3: Cek apakah kita sendiri berada di halaman Kamus
    // (mungkin popup mengarah ke halaman dalam domain yang sama)
    if (document.body?.textContent?.includes("Kamus Aktifitas")) {
      return await searchInKamusDocument(document, keyword);
    }

    return false;
  }

  /**
   * Cari dan klik aktivitas di halaman/dokumen Kamus.
   */
  async function searchInKamusDocument(doc, keyword) {
    // Cari input pencarian
    const searchInput = doc.querySelector("input[type='text']");
    if (searchInput) {
      searchInput.value = "";
      searchInput.focus();

      const setter = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value")?.set;
      if (setter) setter.call(searchInput, keyword);
      else searchInput.value = keyword;
      searchInput.dispatchEvent(new Event("input", { bubbles: true }));
      searchInput.dispatchEvent(new Event("change", { bubbles: true }));

      addLog(`Ketik "${keyword}" di pencarian Kamus`, "ok");
    }

    // Klik tombol "Cari"
    await sleep(500);
    for (const btn of doc.querySelectorAll("input[type='button'], input[type='submit'], button")) {
      const text = btn.textContent?.trim() || btn.value?.trim() || "";
      if (text.toLowerCase() === "cari" || text.toLowerCase() === "search") {
        btn.click();
        addLog("Klik Cari", "ok");
        break;
      }
    }

    // Tunggu hasil pencarian
    await sleep(CONFIG.DELAY_POPUP);

    // Klik hasil pencarian (biasanya teks di tabel yang bisa diklik)
    const cells = doc.querySelectorAll("td");
    for (const cell of cells) {
      const text = cell.textContent.trim();
      if (text.toLowerCase().includes(keyword.toLowerCase())) {
        // Cek apakah ada link/anchor di dalam cell
        const link = cell.querySelector("a");
        if (link) {
          link.click();
          addLog(`Klik hasil: "${text.substring(0, 50)}"`, "ok");
          return true;
        }
        // Klik cell langsung
        cell.click();
        addLog(`Klik hasil: "${text.substring(0, 50)}"`, "ok");
        return true;
      }
    }

    addLog("Hasil pencarian Kamus tidak ditemukan!", "warn");
    return false;
  }

  /**
   * Isi field berdasarkan label (untuk field non-popup).
   */
  function fillFieldByLabel(labels, value) {
    if (!value && value !== 0) return false;

    for (const label of labels) {
      const el = findFieldByLabel(label);
      if (el && !el.readOnly && !el.disabled) {
        setFieldValue(el, value);
        addLog(`  ${label}: "${String(value).substring(0, 60)}"`, "ok");
        return true;
      }
    }

    // Fallback: name/id attribute
    const allInputs = document.querySelectorAll(
      'input:not([type="hidden"]):not([type="submit"]):not([type="button"]), select, textarea'
    );
    const keyword = labels[0].replace(/[\s\/]/g, "").toLowerCase();
    for (const inp of allInputs) {
      if (inp.readOnly || inp.disabled) continue;
      if (inp.value && inp.value.trim() !== "") continue;
      const name = (inp.getAttribute("name") || "").toLowerCase();
      const id = (inp.getAttribute("id") || "").toLowerCase();
      if (name.includes(keyword) || id.includes(keyword)) {
        setFieldValue(inp, value);
        addLog(`  ${labels[0]} (by attr): "${String(value).substring(0, 60)}"`, "ok");
        return true;
      }
    }

    addLog(`  ${labels[0]}: TIDAK DITEMUKAN`, "warn");
    return false;
  }

  /**
   * Isi form "Tambah Aktivitas" dengan data entry.
   *
   * Form e-MASTER "Tambah Aktivitas" memiliki field:
   *   1. Kegiatan Tugas Jabatan (readonly - sudah terisi otomatis)
   *   2. Tanggal Aktivitas (input text) ← dari Excel
   *   3. Detail Aktivitas (popup Kamus) ← klik "..." → cari → pilih
   *   4. Satuan (otomatis dari Kamus, tidak perlu diisi)
   *   5. WPT (otomatis dari Kamus, tidak perlu diisi)
   *   6. Volume (input text) ← dari Excel
   *   7. Objek Kerja / Topik (textarea) ← dari Excel
   *   8. Save / Cancel (buttons)
   */
  async function fillFormFields(entry) {
    let filled = 0;

    // 1. Isi Tanggal Aktivitas
    if (fillFieldByLabel(["tanggal aktivitas", "tanggal"], entry.tanggal)) filled++;

    // 2. Detail Aktivitas — via popup Kamus Aktifitas Harian
    // Kata kunci diambil dari entry.kamus_keyword (di-set oleh converter)
    const kamusKeyword = entry.kamus_keyword || entry.detail_aktivitas || "";
    addLog(`Mengisi Detail Aktivitas: "${kamusKeyword}"`, "info");
    const dotBtn = findDetailAktivitasDotButton();
    if (dotBtn) {
      dotBtn.click();
      addLog("Klik tombol '...' untuk buka Kamus", "ok");
      const kamusOk = await handleKamusPopup(kamusKeyword);
      if (kamusOk) {
        filled++;
        await sleep(CONFIG.DELAY_POPUP);
      } else {
        addLog("Kamus popup: gagal memilih. Coba isi manual.", "warn");
        if (fillFieldByLabel(["detail aktivitas", "detail"], kamusKeyword)) filled++;
      }
    } else {
      addLog("Tombol '...' tidak ditemukan, coba isi langsung", "warn");
      if (fillFieldByLabel(["detail aktivitas", "detail"], kamusKeyword)) filled++;
    }

    // 3. Satuan & WPT — otomatis terisi dari Kamus, SKIP

    // 4. Isi Volume
    if (fillFieldByLabel(["volume"], entry.volume)) filled++;

    // 5. Isi Objek Kerja / Topik
    if (fillFieldByLabel(["objek kerja / topik", "objek kerja", "topik"], entry.objek_kerja)) filled++;

    addLog(`${filled} field terisi`, filled > 0 ? "ok" : "warn");
    return filled;
  }

  /**
   * Handler otomatis saat halaman "Tambah Aktivitas" dimuat.
   * Membaca state dari GM storage, mengisi form, dan klik Save.
   */
  async function handleTambahPage() {
    const state = getAutoFillState();
    if (!state || !state.running) return;

    const data = JSON.parse(GM_getValue("emaster_activities", "null"));
    if (!data) { addLog("Data tidak ditemukan!", "err"); clearAutoFillState(); return; }

    const bd = data.breakdowns[state.breakdownIdx];
    if (!bd) { addLog("Breakdown tidak ditemukan!", "err"); clearAutoFillState(); return; }

    const entry = bd.entries[state.entryIdx];
    if (!entry) { addLog("Entry tidak ditemukan!", "err"); clearAutoFillState(); return; }

    updateAutoStatus(true,
      `Auto-fill: BD ${state.breakdownIdx + 1}, Entry ${state.entryIdx + 1}/${bd.entries.length}`);
    updateProgress(state.entryIdx + 1, bd.entries.length,
      `${bd.kegiatan_tugas_jabatan.substring(0, 30)}...`);

    addLog(`=== Entry ${state.entryIdx + 1}/${bd.entries.length} ===`, "info");
    addLog(`Tanggal: ${entry.tanggal}, Objek: ${String(entry.objek_kerja).substring(0, 40)}...`, "info");

    // Tunggu sebelum mengisi (agar halaman fully loaded)
    await sleep(CONFIG.DELAY_BEFORE_FILL);

    // Isi form (async karena ada popup Kamus)
    const filled = await fillFormFields(entry);

    if (filled > 0) {
      // Advance state ke entry berikutnya SEBELUM save
      const nextEntryIdx = state.entryIdx + 1;
      if (nextEntryIdx < bd.entries.length) {
        setAutoFillState({ ...state, entryIdx: nextEntryIdx });
      } else {
        // Breakdown ini selesai
        addLog(`Breakdown "${bd.kegiatan_tugas_jabatan}" selesai!`, "ok");
        clearAutoFillState();
      }

      // Klik Save - ini akan navigasi kembali ke halaman realisasi
      await sleep(CONFIG.DELAY_BEFORE_SAVE);
      const saveBtn = findSaveButton();
      if (saveBtn) {
        addLog("Klik Save...", "info");
        saveBtn.click();
      } else {
        addLog("Tombol Save tidak ditemukan! Silakan save manual.", "err");
      }
    } else {
      addLog("Gagal mengisi form. Auto-fill dihentikan.", "err");
      clearAutoFillState();
    }
  }

  /**
   * Handler otomatis saat halaman realisasi dimuat.
   * Jika auto-fill masih running, klik Tambah untuk entry berikutnya.
   */
  async function handleRealisasiPage() {
    const state = getAutoFillState();
    if (!state || !state.running) return;

    const data = JSON.parse(GM_getValue("emaster_activities", "null"));
    if (!data) return;

    const bd = data.breakdowns[state.breakdownIdx];
    if (!bd) { clearAutoFillState(); return; }

    if (state.entryIdx >= bd.entries.length) {
      addLog(`Breakdown "${bd.kegiatan_tugas_jabatan}" selesai!`, "ok");
      updateAutoStatus(false, "Selesai!");
      clearAutoFillState();
      return;
    }

    updateAutoStatus(true,
      `Lanjut entry ${state.entryIdx + 1}/${bd.entries.length}...`);
    addLog(`Klik Tambah untuk entry ${state.entryIdx + 1}/${bd.entries.length}...`, "info");

    await sleep(CONFIG.DELAY_AFTER_SAVE);

    // Klik tombol Tambah - navigasi ke halaman Tambah Aktivitas
    const tambahBtn = findTambahButton();
    if (tambahBtn) {
      tambahBtn.click();
    } else {
      addLog("Tombol Tambah tidak ditemukan! Auto-fill dihentikan.", "err");
      clearAutoFillState();
    }
  }

  // =========================================================================
  // SCAN HALAMAN
  // =========================================================================

  function scanPage() {
    const pageType = detectPageType();
    addLog("=== Scan Halaman ===", "info");
    addLog(`URL: ${window.location.href}`, "info");
    addLog(`Jenis halaman: ${pageType}`, "info");

    if (pageType === "aktivitas_bulan") {
      const links = document.querySelectorAll('a[href*="realisasi"]');
      addLog(`${links.length} breakdown ditemukan`, "ok");
      links.forEach((link) => {
        const row = link.closest("tr");
        const text = row ? row.textContent.trim().substring(0, 80) : link.href;
        addLog(`  ${text}`, "info");
      });
    }

    if (pageType === "tambah") {
      addLog("Halaman form Tambah Aktivitas terdeteksi!", "ok");
    }

    // Scan input fields
    const inputs = document.querySelectorAll(
      'input:not([type="hidden"]):not([type="submit"]):not([type="button"]), select, textarea'
    );
    addLog(`Input fields: ${inputs.length}`, "info");
    inputs.forEach((inp) => {
      const name = inp.getAttribute("name") || "";
      const id = inp.id || "";
      const type = inp.getAttribute("type") || inp.tagName.toLowerCase();
      const ro = inp.readOnly ? " [readonly]" : "";
      addLog(`  [${type}] name="${name}" id="${id}"${ro}`, "info");
    });

    // Scan bold labels
    const bolds = document.querySelectorAll("b, strong");
    if (bolds.length > 0) {
      addLog(`Bold labels: ${bolds.length}`, "info");
      bolds.forEach((b) => {
        const text = b.textContent.trim();
        if (text.length > 3 && text.length < 60) {
          addLog(`  <b> "${text}"`, "info");
        }
      });
    }
  }

  // =========================================================================
  // IMPORT JSON
  // =========================================================================

  function handleFileImport(file) {
    const reader = new FileReader();
    reader.onload = function (e) {
      try {
        const data = JSON.parse(e.target.result);
        handleFileImportData(data);
        GM_setValue("emaster_activities", JSON.stringify(data));
        addLog(`File "${file.name}" dimuat dan tersimpan`, "ok");
      } catch (err) {
        addLog(`Error parsing file: ${err.message}`, "err");
      }
    };
    reader.readAsText(file);
  }

  function handleFileImportData(data) {
    const breakdowns = data.breakdowns || [];
    const totalEntries = data.total_entries || 0;

    addLog(`Data: ${breakdowns.length} breakdown, ${totalEntries} entry`, "ok");

    const bdListEl = document.getElementById("af-bd-list");
    if (bdListEl) {
      bdListEl.innerHTML = "";
      breakdowns.forEach((bd, idx) => {
        const item = document.createElement("div");
        item.className = "af-bd-item";
        item.innerHTML = `
          <span class="name" title="${bd.kegiatan_tugas_jabatan}">${idx + 1}. ${bd.kegiatan_tugas_jabatan}</span>
          <span class="count">${bd.jumlah_entries}</span>
          <span class="status" id="af-bd-status-${idx}">-</span>
        `;
        bdListEl.appendChild(item);
      });
    }

    const bdSelect = document.getElementById("af-bd-select");
    if (bdSelect) {
      bdSelect.innerHTML = "";
      breakdowns.forEach((bd, idx) => {
        const opt = document.createElement("option");
        opt.value = idx;
        opt.textContent = `${idx + 1}. ${bd.kegiatan_tugas_jabatan} (${bd.jumlah_entries} entry)`;
        bdSelect.appendChild(opt);
      });
    }
  }

  // =========================================================================
  // UI PANEL
  // =========================================================================

  function createPanel() {
    const style = document.createElement("style");
    style.textContent = PANEL_CSS;
    document.head.appendChild(style);

    const toggle = document.createElement("button");
    toggle.id = "emaster-af-toggle";
    toggle.innerHTML = "&#9998;";
    toggle.title = "e-MASTER Auto Fill";
    document.body.appendChild(toggle);

    const panel = document.createElement("div");
    panel.id = "emaster-af-panel";
    panel.innerHTML = `
      <div class="af-header">
        <span>e-MASTER Auto Fill v3.0</span>
        <button id="af-close-btn" title="Tutup">&times;</button>
      </div>
      <div class="af-body">
        <div class="af-section-title">1. Import Data (JSON)</div>
        <div class="af-group">
          <label>Pilih file JSON (hasil convert_excel.py):</label>
          <input type="file" id="af-file-import" accept=".json" />
        </div>
        <p style="font-size:11px;color:#666;margin:4px 0;">
          Jalankan <code>python convert_excel.py file.xlsx</code> untuk buat JSON.
        </p>

        <div class="af-section-title">2. Pilih Breakdown</div>
        <div id="af-bd-list" class="af-bd-list">
          <div style="color:#999;font-size:11px;">Belum ada data. Import JSON dulu.</div>
        </div>
        <div class="af-group">
          <label>Breakdown yang akan diisi:</label>
          <select id="af-bd-select">
            <option value="">-- Import JSON dulu --</option>
          </select>
        </div>
        <div class="af-group">
          <label>Mulai dari entry ke-:</label>
          <input type="number" id="af-start-entry" value="1" min="1" />
          <span style="font-size:10px;color:#999;">(default: 1 = dari awal)</span>
        </div>
        <div class="af-group">
          <label>Filter Tanggal:</label>
          <div style="display:flex;gap:6px;align-items:center;">
            <input type="text" id="af-date-from" placeholder="DD-MM-YYYY" style="width:45%;" />
            <span style="font-size:11px;">s/d</span>
            <input type="text" id="af-date-to" placeholder="DD-MM-YYYY" style="width:45%;" />
          </div>
          <span style="font-size:10px;color:#999;">(kosongkan = semua tanggal)</span>
        </div>

        <div class="af-section-title">3. Aksi</div>
        <p style="font-size:11px;color:#666;margin:4px 0;">
          <b>Cara pakai:</b><br>
          1. Import JSON<br>
          2. Buka halaman realisasi breakdown (klik icon kunci pas)<br>
          3. Pilih breakdown yang sesuai di dropdown<br>
          4. Klik "Mulai Auto Fill"<br>
          Script akan otomatis: klik Tambah → isi form → Save → ulangi.
        </p>
        <div class="af-actions">
          <button class="af-btn af-btn-run" id="af-btn-run">Mulai Auto Fill</button>
          <button class="af-btn af-btn-stop" id="af-btn-stop">Stop Auto Fill</button>
        </div>
        <div class="af-actions">
          <button class="af-btn af-btn-scan" id="af-btn-scan">Scan Halaman</button>
          <button class="af-btn af-btn-load" id="af-btn-load">Muat Data Tersimpan</button>
        </div>

        <div id="af-auto-status" class="af-auto-status idle">Tidak aktif</div>

        <div class="af-progress">
          <span id="af-progress-text">Belum dimulai</span>
          <div class="af-progress-bar"><div id="af-progress-fill" class="af-progress-fill" style="width:0%"></div></div>
        </div>

        <div id="emaster-af-log"></div>
      </div>
    `;
    document.body.appendChild(panel);

    logContainer = document.getElementById("emaster-af-log");

    // Event handlers
    toggle.addEventListener("click", () => {
      panel.classList.add("visible");
      toggle.style.display = "none";
    });
    document.getElementById("af-close-btn").addEventListener("click", () => {
      panel.classList.remove("visible");
      toggle.style.display = "flex";
    });

    document.getElementById("af-file-import").addEventListener("change", function () {
      if (this.files.length > 0) handleFileImport(this.files[0]);
    });

    // Mulai Auto Fill
    document.getElementById("af-btn-run").addEventListener("click", () => {
      const bdSelect = document.getElementById("af-bd-select");
      const bdIdx = parseInt(bdSelect?.value);
      if (isNaN(bdIdx)) {
        addLog("Pilih breakdown dulu!", "err");
        return;
      }

      const savedData = GM_getValue("emaster_activities", null);
      if (!savedData) {
        addLog("Tidak ada data! Import file JSON dulu.", "err");
        return;
      }

      const data = JSON.parse(savedData);
      const bd = data.breakdowns[bdIdx];
      if (!bd) {
        addLog("Breakdown tidak ditemukan!", "err");
        return;
      }

      // Filter entries berdasarkan tanggal
      const dateFrom = (document.getElementById("af-date-from")?.value || "").trim();
      const dateTo = (document.getElementById("af-date-to")?.value || "").trim();
      let filteredEntries = filterEntriesByDate(bd.entries, dateFrom, dateTo);

      if (filteredEntries.length === 0) {
        addLog("Tidak ada entry yang sesuai filter tanggal!", "err");
        return;
      }

      if (dateFrom || dateTo) {
        addLog(`Filter tanggal: ${dateFrom || "awal"} s/d ${dateTo || "akhir"}`, "info");
        addLog(`${filteredEntries.length}/${bd.entries.length} entry sesuai filter`, "info");
        // Simpan filtered entries ke data sementara
        bd.entries = filteredEntries;
        GM_setValue("emaster_activities", JSON.stringify(data));
      }

      const startEntry = parseInt(document.getElementById("af-start-entry")?.value || "1") - 1;
      const entryIdx = Math.max(0, Math.min(startEntry, bd.entries.length - 1));

      addLog(`Mulai auto-fill: "${bd.kegiatan_tugas_jabatan}"`, "info");
      addLog(`Entry ${entryIdx + 1} s/d ${bd.entries.length}`, "info");

      // Simpan state
      setAutoFillState({
        running: true,
        breakdownIdx: bdIdx,
        entryIdx: entryIdx,
      });

      // Deteksi halaman saat ini
      const pageType = detectPageType();
      if (pageType === "realisasi") {
        // Klik Tambah untuk mulai
        handleRealisasiPage();
      } else if (pageType === "tambah") {
        // Sudah di form, langsung isi
        handleTambahPage();
      } else {
        addLog("Buka halaman realisasi dulu (klik icon kunci pas)!", "warn");
        clearAutoFillState();
      }
    });

    // Stop Auto Fill
    document.getElementById("af-btn-stop").addEventListener("click", () => {
      clearAutoFillState();
      updateAutoStatus(false, "Dihentikan oleh user");
      addLog("Auto-fill dihentikan", "warn");
    });

    document.getElementById("af-btn-scan").addEventListener("click", scanPage);

    document.getElementById("af-btn-load").addEventListener("click", () => {
      const saved = GM_getValue("emaster_activities", null);
      if (saved) {
        const data = JSON.parse(saved);
        handleFileImportData(data);
        addLog("Data tersimpan dimuat", "ok");
      } else {
        addLog("Tidak ada data tersimpan", "warn");
      }
    });

    // Draggable
    let isDragging = false, offsetX, offsetY;
    const header = panel.querySelector(".af-header");
    header.addEventListener("mousedown", (e) => {
      isDragging = true;
      offsetX = e.clientX - panel.getBoundingClientRect().left;
      offsetY = e.clientY - panel.getBoundingClientRect().top;
    });
    document.addEventListener("mousemove", (e) => {
      if (!isDragging) return;
      panel.style.left = (e.clientX - offsetX) + "px";
      panel.style.top = (e.clientY - offsetY) + "px";
      panel.style.right = "auto";
    });
    document.addEventListener("mouseup", () => { isDragging = false; });

    if (typeof GM_registerMenuCommand !== "undefined") {
      GM_registerMenuCommand("Buka Panel Auto Fill", () => {
        panel.classList.add("visible");
        toggle.style.display = "none";
      });
    }

    // Auto-load saved data
    const saved = GM_getValue("emaster_activities", null);
    if (saved) {
      try {
        const data = JSON.parse(saved);
        handleFileImportData(data);
        addLog("Data sebelumnya dimuat otomatis", "info");
      } catch (e) { /* ignore */ }
    }

    addLog(`Halaman: ${detectPageType()}`, "info");
    addLog("Panel siap. Import JSON untuk mulai.", "info");
  }

  // =========================================================================
  // INIT
  // =========================================================================

  function init() {
    createPanel();

    // Auto-detect halaman dan jalankan auto-fill jika state aktif
    const pageType = detectPageType();
    const state = getAutoFillState();

    if (state && state.running) {
      // Auto-show panel saat auto-fill aktif
      const panel = document.getElementById("emaster-af-panel");
      const toggle = document.getElementById("emaster-af-toggle");
      if (panel) panel.classList.add("visible");
      if (toggle) toggle.style.display = "none";

      addLog(`Auto-fill aktif. Halaman: ${pageType}`, "info");

      if (pageType === "tambah") {
        handleTambahPage();
      } else if (pageType === "realisasi") {
        handleRealisasiPage();
      }
    }
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
