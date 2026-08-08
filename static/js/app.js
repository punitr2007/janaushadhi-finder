/* ============================================================
   Jan Aushadhi Generic Medicine Finder — Frontend Logic
   ============================================================ */

// ── State ────────────────────────────────────────────────────────────────────
const state = {
  searchDebounce: null,
  heroDebounce:   null,
  uploadedFile:   null,
  currentMedicine: null,
};

// ── DOM helpers ──────────────────────────────────────────────────────────────
const $ = (sel, root = document) => root.querySelector(sel);
const $$ = (sel, root = document) => [...root.querySelectorAll(sel)];

function show(el) { if (el) el.style.display = ''; }
function hide(el) { if (el) el.style.display = 'none'; }
function showFlex(el) { if (el) el.style.display = 'flex'; }

// ── Init ─────────────────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  fetchInfo();
  fetchStates();
  initNavbar();
  initHeroSearch();
  initMainSearch();
  initQuickTags();
  initUploadZone();
  initScanBtn();
  initKendraFinder();
  initModal();
});

// ── Navbar scroll effect ─────────────────────────────────────────────────────
function initNavbar() {
  const nav = $('#navbar');
  window.addEventListener('scroll', () => {
    nav.classList.toggle('scrolled', window.scrollY > 60);
  }, { passive: true });
}

// ── Fetch app stats ──────────────────────────────────────────────────────────
async function fetchInfo() {
  try {
    const res = await fetch('/api/info');
    const data = await res.json();
    const mEl = $('#stat-medicines');
    const kEl = $('#stat-kendras');
    if (mEl) mEl.textContent = data.medicines.toLocaleString('en-IN');
    if (kEl) kEl.textContent = data.kendras.toLocaleString('en-IN');
  } catch (_) { /* silent */ }
}

// ── Fetch states for dropdown ─────────────────────────────────────────────────
async function fetchStates() {
  try {
    const res = await fetch('/api/states');
    const data = await res.json();
    const sel = $('#state-select');
    if (!sel) return;
    data.states.forEach(s => {
      const opt = document.createElement('option');
      opt.value = s;
      opt.textContent = s;
      sel.appendChild(opt);
    });
  } catch (_) { /* silent */ }
}

// ── Hero quick search with autocomplete ──────────────────────────────────────
function initHeroSearch() {
  const input  = $('#hero-search-input');
  const btn    = $('#hero-search-btn');
  const dropEl = $('#hero-autocomplete');
  if (!input || !btn || !dropEl) return;

  input.addEventListener('input', () => {
    clearTimeout(state.heroDebounce);
    const q = input.value.trim();
    if (!q || q.length < 2) { dropEl.classList.remove('open'); return; }
    state.heroDebounce = setTimeout(() => fetchAutocomplete(q, dropEl), 280);
  });

  input.addEventListener('keydown', e => {
    if (e.key === 'Enter') doHeroSearch(input.value.trim());
    if (e.key === 'Escape') dropEl.classList.remove('open');
  });

  btn.addEventListener('click', () => doHeroSearch(input.value.trim()));

  // Close on outside click
  document.addEventListener('click', e => {
    if (!e.target.closest('.hero-search-wrap')) dropEl.classList.remove('open');
  });
}

async function fetchAutocomplete(q, dropEl) {
  try {
    const res = await fetch(`/api/search?q=${encodeURIComponent(q)}`);
    const data = await res.json();
    dropEl.innerHTML = '';
    if (!data.results.length) { dropEl.classList.remove('open'); return; }

    data.results.slice(0, 6).forEach(med => {
      const item = document.createElement('div');
      item.className = 'ac-item';
      item.setAttribute('role', 'option');
      item.innerHTML = `
        <div>
          <div class="ac-name">${escHtml(med.product_name)}</div>
          <div class="ac-salt">${escHtml(med.salt_composition)}</div>
        </div>
        <div class="ac-price">₹${med.mrp}</div>
      `;
      item.addEventListener('click', () => {
        dropEl.classList.remove('open');
        openMedicineModal(med);
      });
      dropEl.appendChild(item);
    });
    dropEl.classList.add('open');
  } catch (_) { /* silent */ }
}

function doHeroSearch(q) {
  if (!q) return;
  const mainInput = $('#main-search-input');
  if (mainInput) mainInput.value = q;
  document.getElementById('search-section')?.scrollIntoView({ behavior: 'smooth' });
  setTimeout(() => triggerSearch(q), 400);
}

// ── Main medicine search ──────────────────────────────────────────────────────
function initMainSearch() {
  const input = $('#main-search-input');
  const btn   = $('#main-search-btn');
  if (!input || !btn) return;

  input.addEventListener('keydown', e => {
    if (e.key === 'Enter') triggerSearch(input.value.trim());
  });
  btn.addEventListener('click', () => triggerSearch(input.value.trim()));
}

function initQuickTags() {
  $$('.quick-tag').forEach(tag => {
    tag.addEventListener('click', () => {
      const q = tag.dataset.q;
      const input = $('#main-search-input');
      if (input) input.value = q;
      triggerSearch(q);
    });
  });
}

async function triggerSearch(q) {
  if (!q || q.length < 2) return;

  const emptyEl   = $('#search-empty');
  const loadingEl = $('#search-loading');
  const cardsEl   = $('#search-cards');

  hide(emptyEl);
  show(loadingEl);
  cardsEl.innerHTML = '';

  try {
    const res  = await fetch(`/api/search?q=${encodeURIComponent(q)}`);
    const data = await res.json();
    hide(loadingEl);

    if (!data.results.length) {
      cardsEl.innerHTML = `
        <div class="no-results" style="grid-column:1/-1">
          <i class="fa-solid fa-face-frown-open"></i>
          <h3>No matches found for "${escHtml(q)}"</h3>
          <p>Try a different spelling, the generic salt name, or a brand name</p>
        </div>`;
      return;
    }
    renderMedicineCards(data.results, cardsEl);
  } catch (err) {
    hide(loadingEl);
    cardsEl.innerHTML = `<div class="no-results" style="grid-column:1/-1">
      <i class="fa-solid fa-triangle-exclamation"></i>
      <h3>Error fetching results</h3><p>${escHtml(err.message)}</p></div>`;
  }
}

function renderMedicineCards(medicines, container) {
  medicines.forEach((med, i) => {
    const card = document.createElement('div');
    card.className = 'medicine-card';
    card.style.animationDelay = `${i * 50}ms`;

    const brands = (med.brand_list || []).slice(0, 4);
    const brandTags = brands.map(b => `<span class="brand-tag">${escHtml(b)}</span>`).join('');
    const savingsPct = Math.min(med.savings_pct || 0, 100);

    card.innerHTML = `
      <div class="card-header">
        <span class="card-category">${escHtml(truncate(med.category || 'Medicine', 28))}</span>
        <span class="card-drug-code">${escHtml(med.drug_code)}</span>
      </div>
      <div class="card-name">${escHtml(med.product_name)}</div>
      <div class="card-salt">${escHtml(med.salt_composition)}</div>
      <div class="card-price-row">
        <div class="card-ja-price">₹${med.mrp}</div>
        <div class="card-unit-size">${escHtml(med.dosage_form || '')} · ${escHtml(String(med.unit_size || ''))}</div>
        <div class="card-brand-price">₹${med.estimated_branded_price} branded</div>
      </div>
      <div class="card-savings-bar">
        <div class="card-savings-fill" style="width:${savingsPct}%"></div>
      </div>
      ${brandTags ? `<div class="card-brands">${brandTags}</div>` : ''}
      <div class="card-footer">
        <div class="card-form">
          <i class="fa-solid fa-capsules"></i> Save ~${savingsPct}% over branded
        </div>
        <div class="card-view-btn">View Details →</div>
      </div>
    `;
    card.addEventListener('click', () => openMedicineModal(med));
    container.appendChild(card);
  });
}

// ── OCR Upload ────────────────────────────────────────────────────────────────
function initUploadZone() {
  const zone      = $('#upload-zone');
  const fileInput = $('#file-input');
  const preview   = $('#upload-preview');
  const previewImg = $('#preview-img');
  const content   = $('#upload-content');
  const removeBtn = $('#remove-img');
  const actionRow = $('#ocr-action-row');
  if (!zone) return;

  // Click triggers file input (the file input overlays the zone, so this is handled natively)
  fileInput.addEventListener('change', e => {
    if (e.target.files[0]) handleFileSelect(e.target.files[0]);
  });

  // Drag and drop
  zone.addEventListener('dragover', e => { e.preventDefault(); zone.classList.add('drag-over'); });
  zone.addEventListener('dragleave', () => zone.classList.remove('drag-over'));
  zone.addEventListener('drop', e => {
    e.preventDefault();
    zone.classList.remove('drag-over');
    if (e.dataTransfer.files[0]) handleFileSelect(e.dataTransfer.files[0]);
  });

  removeBtn?.addEventListener('click', e => {
    e.stopPropagation();
    state.uploadedFile = null;
    hide(preview);
    show(content);
    hide(actionRow);
    fileInput.value = '';
    resetOcrPanel();
  });
}

function handleFileSelect(file) {
  if (!file.type.startsWith('image/')) { alert('Please upload an image file.'); return; }
  state.uploadedFile = file;

  const reader = new FileReader();
  reader.onload = e => {
    const img = $('#preview-img');
    if (img) img.src = e.target.result;
    hide($('#upload-content'));
    show($('#upload-preview'));
    show($('#ocr-action-row'));
    resetOcrPanel();
  };
  reader.readAsDataURL(file);
}

function resetOcrPanel() {
  show($('#ocr-idle'));
  hide($('#ocr-scanning'));
  hide($('#ocr-output'));
  hide($('#ocr-error'));
}

function initScanBtn() {
  const btn = $('#scan-btn');
  if (!btn) return;
  btn.addEventListener('click', runOcr);
}

async function runOcr() {
  if (!state.uploadedFile) { alert('Please upload an image first.'); return; }

  hide($('#ocr-idle'));
  hide($('#ocr-output'));
  hide($('#ocr-error'));
  show($('#ocr-scanning'));

  const formData = new FormData();
  formData.append('file', state.uploadedFile);

  try {
    const res  = await fetch('/api/ocr', { method: 'POST', body: formData });
    const data = await res.json();

    hide($('#ocr-scanning'));

    if (!data.success) {
      const errEl = $('#ocr-error');
      const errMsg = $('#ocr-error-msg');
      if (errMsg) errMsg.textContent = data.error || 'OCR failed. Check Tesseract installation.';
      show(errEl);
      return;
    }

    renderOcrResults(data);

  } catch (err) {
    hide($('#ocr-scanning'));
    const errEl = $('#ocr-error');
    const errMsg = $('#ocr-error-msg');
    if (errMsg) errMsg.textContent = `Network error: ${err.message}`;
    show(errEl);
  }
}

function renderOcrResults(data) {
  const output       = $('#ocr-output');
  const countLabel   = $('#ocr-count-label');
  const suggList     = $('#ocr-suggestions');
  const rawBox       = $('#ocr-raw-text');
  const toggleRaw    = $('#toggle-raw-text');

  const suggestions = data.search_suggestions || [];
  const meds = data.medicines || [];

  if (countLabel) {
    countLabel.textContent = suggestions.length > 0
      ? `✓ Found ${meds.length} medicine token${meds.length !== 1 ? 's' : ''} — showing ${suggestions.length} match${suggestions.length !== 1 ? 'es' : ''}`
      : 'No medicine names recognised — try a clearer image';
  }

  suggList.innerHTML = '';
  if (suggestions.length === 0) {
    suggList.innerHTML = `<p style="color:var(--c-text-3);font-size:0.85rem;text-align:center;padding:20px 0">
      No clear medicine names detected. Try better lighting or a printed label.</p>`;
  } else {
    suggestions.forEach(sugg => {
      const item = document.createElement('div');
      item.className = 'ocr-suggestion-item';
      const matchRows = sugg.matches.map(m => `
        <div class="ocr-match-row" data-code="${escHtml(m.drug_code)}">
          <div class="ocr-match-name">${escHtml(m.product_name)}</div>
          <div class="ocr-match-price">₹${m.mrp}</div>
        </div>
      `).join('');
      item.innerHTML = `
        <div class="ocr-term">
          OCR detected: <strong>${escHtml(sugg.ocr_term)}</strong>
          ${sugg.dosage_context ? `<span style="color:var(--c-text-3)"> ${escHtml(sugg.dosage_context)}</span>` : ''}
        </div>
        <div class="ocr-matches">${matchRows}</div>
      `;
      suggList.appendChild(item);
    });

    // Add click handlers for match rows
    $$('.ocr-match-row').forEach(row => {
      row.addEventListener('click', async () => {
        const code = row.dataset.code;
        if (!code) return;
        try {
          const res  = await fetch(`/api/medicine/${encodeURIComponent(code)}`);
          const med  = await res.json();
          openMedicineModal(med);
        } catch (_) {}
      });
    });
  }

  if (rawBox && toggleRaw) {
    rawBox.textContent = data.raw_text || '(empty)';
    show(toggleRaw);
    toggleRaw.addEventListener('click', () => {
      const showing = rawBox.style.display !== 'none';
      rawBox.style.display = showing ? 'none' : 'block';
    });
  }

  show(output);
}

// ── Kendra Finder ─────────────────────────────────────────────────────────────
function initKendraFinder() {
  const btn = $('#find-kendra-btn');
  if (!btn) return;
  btn.addEventListener('click', triggerKendraSearch);

  const pinInput = $('#pin-input');
  if (pinInput) {
    pinInput.addEventListener('keydown', e => { if (e.key === 'Enter') triggerKendraSearch(); });
  }
}

async function triggerKendraSearch() {
  const pin   = ($('#pin-input')?.value || '').trim();
  const state = ($('#state-select')?.value || '').trim();

  if (!pin && !state) {
    alert('Please enter a PIN code or select a state.');
    return;
  }

  const emptyEl   = $('#kendra-empty');
  const loadingEl = $('#kendra-loading');
  const cardsEl   = $('#kendra-cards');

  hide(emptyEl);
  show(loadingEl);
  cardsEl.innerHTML = '';

  try {
    const params = new URLSearchParams();
    if (pin)   params.set('pin', pin);
    if (state) params.set('state', state);

    const res  = await fetch(`/api/kendras?${params}`);
    const data = await res.json();
    hide(loadingEl);

    if (!data.kendras || !data.kendras.length) {
      cardsEl.innerHTML = `
        <div class="no-results" style="grid-column:1/-1">
          <i class="fa-solid fa-store-slash"></i>
          <h3>No Kendras found for this location</h3>
          <p>Try a nearby PIN code or select a broader state</p>
        </div>`;
      return;
    }
    renderKendraCards(data.kendras, cardsEl);
  } catch (err) {
    hide(loadingEl);
    cardsEl.innerHTML = `<div class="no-results" style="grid-column:1/-1">
      <i class="fa-solid fa-triangle-exclamation"></i>
      <h3>Error</h3><p>${escHtml(err.message)}</p></div>`;
  }
}

function renderKendraCards(kendras, container) {
  kendras.forEach((k, i) => {
    const card = document.createElement('div');
    card.className = 'kendra-card';
    card.style.animationDelay = `${i * 50}ms`;

    const mapsUrl = k.latitude && k.longitude
      ? `https://www.google.com/maps/search/?api=1&query=${k.latitude},${k.longitude}`
      : `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(k.name+' '+k.address+' '+k.state)}`;

    const distBadge = k.distance_km != null
      ? `<div class="kendra-distance-badge"><i class="fa-solid fa-route"></i> ${k.distance_km} km away</div>`
      : '';

    const callBtn = k.phone
      ? `<a href="tel:${escHtml(k.phone)}" class="kendra-btn-call">
           <i class="fa-solid fa-phone"></i> ${escHtml(k.phone)}
         </a>`
      : '';

    card.innerHTML = `
      <div class="kendra-header">
        <div class="kendra-icon"><i class="fa-solid fa-store"></i></div>
        <div>
          <div class="kendra-name">${escHtml(k.name)}</div>
          <div class="kendra-id">${escHtml(k.kendra_id)}</div>
        </div>
      </div>
      ${distBadge}
      <div class="kendra-address">
        <i class="fa-solid fa-location-dot"></i>
        <span>${escHtml(k.address)}, ${escHtml(k.district)}, ${escHtml(k.state)}</span>
      </div>
      <div class="kendra-meta">
        <div class="kendra-meta-item">
          <i class="fa-solid fa-hashtag"></i>
          PIN <span class="pin-val">${escHtml(k.pincode)}</span>
        </div>
        <div class="kendra-meta-item">
          <i class="fa-solid fa-map"></i> ${escHtml(k.state)}
        </div>
      </div>
      <div class="kendra-actions">
        ${callBtn}
        <a href="${mapsUrl}" target="_blank" rel="noopener" class="kendra-btn-map">
          <i class="fa-solid fa-map-location-dot"></i> Directions
        </a>
      </div>
    `;
    container.appendChild(card);
  });
}

// ── Medicine Detail Modal ─────────────────────────────────────────────────────
function initModal() {
  const overlay   = $('#medicine-modal');
  const closeBtn  = $('#modal-close-btn');
  const kendraBtn = $('#modal-find-kendra-btn');
  if (!overlay) return;

  closeBtn?.addEventListener('click', closeModal);
  overlay.addEventListener('click', e => { if (e.target === overlay) closeModal(); });
  document.addEventListener('keydown', e => { if (e.key === 'Escape') closeModal(); });

  kendraBtn?.addEventListener('click', () => {
    closeModal();
    document.getElementById('kendra-section')?.scrollIntoView({ behavior: 'smooth' });
  });
}

function openMedicineModal(med) {
  state.currentMedicine = med;
  const overlay = $('#medicine-modal');
  if (!overlay) return;

  // Populate
  $('#modal-category').textContent = med.category || 'Medicine';
  $('#modal-drug-name').textContent = med.product_name || '';
  $('#modal-salt').textContent = med.salt_composition || '';
  $('#modal-ja-price').textContent = `₹${med.mrp}`;
  $('#modal-brand-price').textContent = `₹${med.estimated_branded_price}`;
  $('#modal-unit-size').textContent = med.unit_size ? `per pack of ${med.unit_size}` : '';
  $('#modal-form').textContent = med.dosage_form || '—';
  $('#modal-pack').textContent = med.unit_size || '—';
  $('#modal-code').textContent = med.drug_code || '—';

  const savingsPct = Math.min(med.savings_pct || 0, 100);
  const fillEl = $('#modal-savings-fill');
  const labelEl = $('#modal-savings-label');
  if (fillEl) fillEl.style.width = `${savingsPct}%`;
  if (labelEl) labelEl.textContent = `You save ~${savingsPct}% over branded price`;

  // Brand chips
  const brandsEl = $('#modal-brands');
  if (brandsEl) {
    const brands = med.brand_list || [];
    brandsEl.innerHTML = brands.length
      ? brands.map(b => `<span class="brand-chip">${escHtml(b)}</span>`).join('')
      : '<span style="color:var(--c-text-3);font-size:0.82rem">No brand equivalents listed</span>';
  }

  // Maps link
  const mapsBtn = $('#modal-maps-btn');
  if (mapsBtn) {
    mapsBtn.href = `https://www.google.com/maps/search/?api=1&query=Jan+Aushadhi+Kendra+near+me`;
  }

  overlay.style.display = 'flex';
  document.body.style.overflow = 'hidden';
}

function closeModal() {
  const overlay = $('#medicine-modal');
  if (overlay) overlay.style.display = 'none';
  document.body.style.overflow = '';
  state.currentMedicine = null;
}

// ── Utils ─────────────────────────────────────────────────────────────────────
function escHtml(str) {
  if (!str && str !== 0) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

function truncate(str, n) {
  return str.length > n ? str.slice(0, n - 1) + '…' : str;
}
