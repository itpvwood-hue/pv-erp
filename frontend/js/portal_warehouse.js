/* PVWood ERP - Warehouse Portal (Dashboard + Low Stock + Open PRs).
   First portal carve-up from the main inline script. Self-registers its
   three pages via Object.assign(PAGE_LOADERS, ...) so nav.js can find
   them without knowing about warehouse-specific code.

   Load order: AFTER nav.js (so PAGE_LOADERS exists) AND after the main
   inline script (so _LANG / marked / bootstrap are bound). Loaded near
   the end of <body>.

   Globals declared:
       WH_TYPE_LABEL, WH_TYPE_BADGE, WH_PR_STATUS_BADGE
       _whFmtDate, _whMatName, _whWeekEndDisplay
       _whLowCache, _whPRMat, _whNewPRMats, _whNewPRMatsLoaded, _whNewSelected
       whDashLoad, whLowStockLoad, whOpenSendPR, whSendPRSubmit
       whNewPROpen, whNewPRMatRefresh, whNewPRMatSelected, whNewPRSubmit
       whOpenPRsLoad
*/
// ════════════════════════════════════════════════════════════
// WAREHOUSE PORTAL — Dashboard / Low Stock / Open Purchase Requests
// ════════════════════════════════════════════════════════════
// Three pages added to /warehouse (and to the WAREHOUSE role's
// regular sidebar). They share the simple PR modal at #whSendPRModal.
// All compose from /api/warehouse/* endpoints.

const WH_TYPE_LABEL = {
  adhesive:'Consumable', glue_formula:'Glue & Additives',
  packing:'Packing', other:'Others',
  core_board:'Boards', veneer_sheet:'Veneers',
};
const WH_TYPE_BADGE = {
  adhesive:'bg-info-subtle text-info',
  glue_formula:'bg-warning-subtle text-warning',
  packing:'bg-secondary-subtle text-secondary',
  other:'bg-light text-muted',
  core_board:'bg-success-subtle text-success',
  veneer_sheet:'bg-primary-subtle text-primary',
};
const WH_PR_STATUS_BADGE = {
  NEW:'bg-secondary', APPROVED:'bg-info',
  PO_ISSUED:'bg-primary', AWAITING_ARRIVAL:'bg-warning text-dark',
  OVER_RECEIVED:'bg-danger',
};

function _whFmtDate(iso){
  if(!iso) return '—';
  const s = String(iso).slice(0,10);
  return s || '—';
}
// _whFmtQty now aliases to fmtNum (declared centrally).
function _whMatName(m){
  // Materials returned by /api/warehouse/* carry name_th; respect language toggle.
  if(typeof _LANG !== 'undefined' && _LANG === 'th' && m.material_name_th) return m.material_name_th;
  return m.material_name || m.name_th && _LANG==='th' ? m.name_th : (m.name || m.material_name || '');
}

// ── DASHBOARD ─────────────────────────────────────────────
async function whDashLoad(){
  let data;
  try { data = await api('/api/warehouse/dashboard'); }
  catch(e){ toast('Dashboard load failed: '+e.message, 'danger'); return; }

  // Week label
  const lbl = document.getElementById('whd-week-label');
  if(lbl) lbl.textContent = `This week — ${data.week_start} → ${_whWeekEndDisplay(data.week_end_exclusive)}`;

  // KPI cards
  const kpis = [
    { lbl:'Low stock items',  val:data.low_stock_count, color:'danger',  icon:'bi-exclamation-triangle', goto:'wh-low-stock' },
    { lbl:'Open PRs',         val:data.open_pr_count,   color:'primary', icon:'bi-clipboard2-check',     goto:'wh-open-prs' },
    { lbl:'Arriving this week',val:data.arriving_count, color:'success', icon:'bi-truck',                goto:'raw-receiving' },
    { lbl:'Material requests',val:(data.pending_requests_count ?? 0), color:'warning', icon:'bi-inbox-fill', goto:'warehouse-queue' },
  ];
  document.getElementById('whd-kpi-row').innerHTML = kpis.map(k => `
    <div class="col-6 col-md-3">
      <div class="card border-${k.color} h-100" ${k.goto?`onclick="navigateTo('${k.goto}')" style="cursor:pointer"`:''}>
        <div class="card-body py-2">
          <div class="small text-${k.color}"><i class="bi ${k.icon} me-1"></i>${k.lbl}</div>
          <div class="fs-3 fw-bold text-${k.color}">${k.val||0}</div>
        </div>
      </div>
    </div>
  `).join('');

  // Sidebar low-stock badge
  const badge = document.getElementById('nav-wh-low-badge');
  if(badge){
    if(data.low_stock_count > 0){ badge.textContent = data.low_stock_count; badge.classList.remove('d-none'); }
    else badge.classList.add('d-none');
  }
  const prb = document.getElementById('nav-wh-open-prs-badge');
  if(prb){
    if(data.open_pr_count > 0){ prb.textContent = data.open_pr_count; prb.classList.remove('d-none'); }
    else prb.classList.add('d-none');
  }
  // Material Requests sidebar badge (PENDING + PARTIAL consumable requests)
  const wqb = document.getElementById('nav-wq-badge');
  if(wqb){
    const n = data.pending_requests_count || 0;
    if(n > 0){ wqb.textContent = n; wqb.classList.remove('d-none'); }
    else wqb.classList.add('d-none');
  }

  // Receiving table
  const recvTb = document.getElementById('whd-recv-tbody');
  document.getElementById('whd-recv-count').textContent = data.arriving_count;
  if(!data.arriving.length){
    recvTb.innerHTML = '<tr><td colspan="5" class="text-center text-muted py-3">Nothing scheduled this week</td></tr>';
  } else {
    recvTb.innerHTML = data.arriving.map(s => `
      <tr>
        <td>${_whFmtDate(s.planned_arrival)}</td>
        <td><code class="small">${s.request_number||''}</code></td>
        <td><code class="text-primary small">${s.material_code||''}</code><br><span class="small text-muted">${_whMatName(s)}</span></td>
        <td class="text-end">${_whFmtQty(s.planned_qty)} ${s.unit||''}</td>
        <td><span class="badge bg-${s.shipment_status==='RECEIVED'?'success':'warning text-dark'}">${s.shipment_status||'PLANNED'}</span></td>
      </tr>
    `).join('');
  }

  // Exporting table
  const expTb = document.getElementById('whd-exp-tbody');
  document.getElementById('whd-exp-count').textContent = data.exporting_count;
  if(!data.exporting.length){
    expTb.innerHTML = '<tr><td colspan="5" class="text-center text-muted py-3">No outbound this week</td></tr>';
  } else {
    expTb.innerHTML = data.exporting.map(c => `
      <tr>
        <td>${_whFmtDate(c.needed_by || c.created_at)}</td>
        <td><code class="text-primary small">${c.material_code||''}</code><br><span class="small text-muted">${_whMatName(c)}</span></td>
        <td class="text-end">${_whFmtQty(c.qty_requested)} ${c.unit||''}</td>
        <td><span class="small">${c.department||'—'}</span></td>
        <td><span class="badge ${c.status==='FULFILLED'?'bg-success':'bg-warning text-dark'}">${c.status||'—'}</span></td>
      </tr>
    `).join('');
  }
}

function _whWeekEndDisplay(exclusive){
  // backend returns next Monday (exclusive). Display as the Sunday before.
  try {
    const d = new Date(exclusive + 'T00:00:00');
    d.setDate(d.getDate() - 1);
    return d.toISOString().slice(0,10);
  } catch { return exclusive; }
}

// ── LOW STOCK WORKLIST ────────────────────────────────────
let _whLowCache = [];
async function whLowStockLoad(){
  const cat = document.getElementById('wh-low-cat-filter')?.value || '';
  const url = '/api/warehouse/low-stock' + (cat ? `?category=${encodeURIComponent(cat)}` : '');
  let rows;
  try { rows = await api(url); }
  catch(e){ toast('Low stock load failed: '+e.message, 'danger'); return; }
  _whLowCache = rows;
  const tb = document.getElementById('wh-low-tbody');
  if(!rows.length){
    const msg = cat
      ? 'No items in this category are below min stock.'
      : 'All consumables / glue / packing / others are above min stock.';
    tb.innerHTML = `<tr><td colspan="9" class="text-center text-muted py-3"><i class="bi bi-check-circle text-success me-1"></i>${msg}</td></tr>`;
    return;
  }
  tb.innerHTML = rows.map(r => {
    const desc = (_LANG==='th' && r.name_th) ? r.name_th : (r.name || r.code);
    const typeLbl = WH_TYPE_LABEL[r.type] || r.type;
    const typeCls = WH_TYPE_BADGE[r.type] || 'bg-light text-muted';
    return `<tr>
      <td><code class="text-primary">${r.code}</code></td>
      <td>${desc}</td>
      <td><span class="badge ${typeCls}" style="font-size:.65rem">${typeLbl}</span></td>
      <td>${r.unit||''}</td>
      <td class="text-end text-danger fw-bold">${_whFmtQty(r.current_stock)}</td>
      <td class="text-end">${_whFmtQty(r.reorder_point)}</td>
      <td class="text-end fw-semibold">${_whFmtQty(r.suggested_qty)}</td>
      <td>${r.supplier || '<span class="text-muted small">—</span>'}</td>
      <td class="text-end"><button class="btn btn-sm btn-success" onclick="whOpenSendPR(${r.id})"><i class="bi bi-send me-1"></i>Send PR</button></td>
    </tr>`;
  }).join('');
}

// ── SEND PR MODAL ─────────────────────────────────────────
let _whPRMat = null;
function whOpenSendPR(materialId){
  const m = _whLowCache.find(x => x.id === materialId);
  if(!m){ toast('Material not found', 'danger'); return; }
  _whPRMat = m;
  document.getElementById('whpr-code').textContent = m.code;
  document.getElementById('whpr-name').textContent = (_LANG==='th' && m.name_th) ? m.name_th : (m.name || '');
  document.getElementById('whpr-current').value = _whFmtQty(m.current_stock);
  document.getElementById('whpr-min').value = _whFmtQty(m.reorder_point);
  document.getElementById('whpr-qty').value = m.suggested_qty;
  document.getElementById('whpr-unit').value = m.unit || '';
  document.getElementById('whpr-supplier').value = m.supplier || '';
  document.getElementById('whpr-needed').value = '';
  document.getElementById('whpr-notes').value = '';
  bootstrap.Modal.getOrCreateInstance(document.getElementById('whSendPRModal')).show();
}

async function whSendPRSubmit(){
  if(!_whPRMat) return;
  const qty = parseFloat(document.getElementById('whpr-qty').value);
  if(!(qty > 0)){ toast('Enter a positive order qty', 'warning'); return; }
  const btn = document.getElementById('whpr-submit-btn');
  btn.disabled = true;
  try {
    await api('/api/purchase-requests', 'POST', {
      request_type: 'CONSUMABLE',
      material_id:  _whPRMat.id,
      qty_requested: qty,
      uom: _whPRMat.unit || '',
      priority: 2,
      needed_by: document.getElementById('whpr-needed').value || null,
      suggested_supplier: document.getElementById('whpr-supplier').value.trim(),
      notes: document.getElementById('whpr-notes').value.trim(),
    });
    toast('Purchase request sent — visible in Open Purchase Requests', 'success');
    bootstrap.Modal.getInstance(document.getElementById('whSendPRModal')).hide();
    // Reset the Open PRs category filter so the new PR is guaranteed to show
    // up the next time the user visits that page.
    const f = document.getElementById('wh-pr-cat-filter');
    if(f) f.value = '';
    whLowStockLoad();      // refresh worklist
    whDashLoad();          // refresh badge counts
    whOpenPRsLoad();       // refresh Open PRs list in the background
  } catch(e){
    toast('Failed: '+e.message, 'danger');
  } finally {
    btn.disabled = false;
  }
}

// ── NEW PR MODAL (warehouse self-service, from Open PRs page) ─
let _whNewPRMats = [];        // cached material list (all warehouse-managed types)
let _whNewPRMatsLoaded = false;
let _whNewSelected = null;    // currently picked material row

async function whNewPROpen(){
  // Reset form
  document.getElementById('whnew-search').value = '';
  document.getElementById('whnew-qty').value = '';
  document.getElementById('whnew-priority').value = '2';
  document.getElementById('whnew-needed').value = '';
  document.getElementById('whnew-supplier').value = '';
  document.getElementById('whnew-notes').value = '';
  document.getElementById('whnew-current').value = '';
  document.getElementById('whnew-min').value = '';
  document.getElementById('whnew-unit').value = '';
  _whNewSelected = null;
  // Default category mirrors whatever the Open PRs page is currently filtered to,
  // falling back to "adhesive" — by far the most common warehouse-side request.
  const curCat = document.getElementById('wh-pr-cat-filter')?.value;
  const allowedCats = new Set(['adhesive','glue_formula','packing','other','core_board','veneer_sheet']);
  document.getElementById('whnew-cat').value = allowedCats.has(curCat) ? curCat : 'adhesive';
  if(!_whNewPRMatsLoaded){
    document.getElementById('whnew-mat-status').textContent = 'Loading materials…';
    try {
      const rows = await api('/api/materials?include_formulas=true');
      _whNewPRMats = Array.isArray(rows) ? rows : [];
      _whNewPRMatsLoaded = true;
    } catch(e){
      document.getElementById('whnew-mat-status').textContent = 'Failed to load materials: ' + e.message;
      _whNewPRMats = [];
    }
  }
  whNewPRMatRefresh();
  bootstrap.Modal.getOrCreateInstance(document.getElementById('whNewPRModal')).show();
}

function whNewPRMatRefresh(){
  const cat = document.getElementById('whnew-cat').value;
  const q   = (document.getElementById('whnew-search').value||'').trim().toLowerCase();
  let rows = _whNewPRMats.filter(m => m.type === cat);
  if(q){
    rows = rows.filter(m =>
      (m.code||'').toLowerCase().includes(q) ||
      (m.name||'').toLowerCase().includes(q) ||
      (m.name_th||'').toLowerCase().includes(q));
  }
  rows = rows.slice(0, 200);  // cap for the <select size=6>
  const sel = document.getElementById('whnew-mat');
  if(!rows.length){
    sel.innerHTML = '<option disabled>(no materials match)</option>';
    document.getElementById('whnew-mat-status').textContent =
      _whNewPRMatsLoaded ? 'No materials match the filter.' : '';
    _whNewSelected = null;
    document.getElementById('whnew-current').value = '';
    document.getElementById('whnew-min').value = '';
    document.getElementById('whnew-unit').value = '';
    return;
  }
  sel.innerHTML = rows.map(m => {
    const desc = (_LANG==='th' && m.name_th) ? m.name_th : (m.name || m.code);
    const low  = (m.current_stock||0) <= (m.reorder_point||0) && (m.reorder_point||0) > 0;
    return `<option value="${m.id}" data-low="${low?1:0}">${(m.code||'').padEnd(14)} ${desc}${low ? '  ⚠ LOW' : ''}</option>`;
  }).join('');
  document.getElementById('whnew-mat-status').textContent =
    `${rows.length} material${rows.length===1?'':'s'} shown · ⚠ = currently at or below min`;
  // Auto-pick first row so qty/unit context shows up immediately
  sel.value = String(rows[0].id);
  whNewPRMatSelected();
}

function whNewPRMatSelected(){
  const id = Number(document.getElementById('whnew-mat').value);
  const m  = _whNewPRMats.find(x => x.id === id);
  _whNewSelected = m || null;
  if(!m) return;
  document.getElementById('whnew-current').value = _whFmtQty(m.current_stock);
  document.getElementById('whnew-min').value     = _whFmtQty(m.reorder_point);
  document.getElementById('whnew-unit').value    = m.unit || '';
  document.getElementById('whnew-supplier').value = m.supplier || '';
  // Suggested qty: min*2 - current (clamped). Only auto-fill if qty is empty
  // — the staffer may have already typed a number for a different material.
  const qtyEl = document.getElementById('whnew-qty');
  if(!qtyEl.value){
    const suggested = Math.max(0, (Number(m.reorder_point||0) * 2) - Number(m.current_stock||0));
    qtyEl.value = suggested > 0 ? suggested.toFixed(2).replace(/\.00$/,'') : '';
  }
}

async function whNewPRSubmit(){
  const m = _whNewSelected;
  if(!m){ toast('Pick a material first', 'warning'); return; }
  const qty = parseFloat(document.getElementById('whnew-qty').value);
  if(!(qty > 0)){ toast('Enter a positive order qty', 'warning'); return; }
  // Boards / Veneers → RAW_MATERIAL; everything else → CONSUMABLE,
  // matching how Material Shortfalls / Planning categorises PRs.
  const isRaw = (m.type === 'core_board' || m.type === 'veneer_sheet');
  const btn = document.getElementById('whnew-submit-btn');
  btn.disabled = true;
  try {
    await api('/api/purchase-requests', 'POST', {
      request_type: isRaw ? 'RAW_MATERIAL' : 'CONSUMABLE',
      material_id:  m.id,
      qty_requested: qty,
      uom: m.unit || '',
      priority: parseInt(document.getElementById('whnew-priority').value, 10) || 2,
      needed_by: document.getElementById('whnew-needed').value || null,
      suggested_supplier: document.getElementById('whnew-supplier').value.trim(),
      notes: document.getElementById('whnew-notes').value.trim(),
    });
    toast('Purchase request sent', 'success');
    bootstrap.Modal.getInstance(document.getElementById('whNewPRModal')).hide();
    // Make sure the new PR is visible: if the page filter doesn't cover the
    // new PR's category, switch the filter to match it before reloading.
    const f = document.getElementById('wh-pr-cat-filter');
    if(f && f.value && f.value !== m.type) f.value = m.type;
    whOpenPRsLoad();
    whDashLoad();
  } catch(e){
    toast('Failed: '+e.message, 'danger');
  } finally {
    btn.disabled = false;
  }
}

// ── OPEN PURCHASE REQUESTS ────────────────────────────────
async function whOpenPRsLoad(){
  const cat = document.getElementById('wh-pr-cat-filter')?.value || '';
  const url = '/api/warehouse/open-purchase-requests' + (cat ? `?category=${encodeURIComponent(cat)}` : '');
  let prs;
  try { prs = await api(url); }
  catch(e){ toast('Open PRs load failed: '+e.message, 'danger'); return; }
  const tb = document.getElementById('wh-prs-tbody');
  if(!prs.length){
    tb.innerHTML = '<tr><td colspan="8" class="text-center text-muted py-3">No open purchase requests in this category.</td></tr>';
    return;
  }
  tb.innerHTML = prs.map(p => {
    const desc = (_LANG==='th' && p.material_name_th) ? p.material_name_th : (p.material_name || p.material_code);
    const typeLbl = WH_TYPE_LABEL[p.material_type] || p.material_type;
    const typeCls = WH_TYPE_BADGE[p.material_type] || 'bg-light text-muted';
    const stCls = WH_PR_STATUS_BADGE[p.status] || 'bg-secondary';
    const ships = (p.shipments || []);
    const plan = ships.length
      ? ships.map(s => `<div class="small">
            <span class="text-muted">#${s.sequence}</span>
            <b>${_whFmtDate(s.planned_arrival)}</b>
            — ${_whFmtQty(s.planned_qty)}${p.uom?' '+p.uom:''}
            <span class="badge bg-${s.status==='RECEIVED'?'success':'light text-dark border'}" style="font-size:.6rem">${s.status||'PLANNED'}</span>
         </div>`).join('')
      : (p.estimated_arrival
          ? `<div class="small text-muted">ETA ${_whFmtDate(p.estimated_arrival)} (no split)</div>`
          : '<div class="small text-muted fst-italic">No shipment plan yet</div>');
    return `<tr>
      <td><code class="small">${p.request_number||''}</code></td>
      <td><code class="text-primary small">${p.material_code||''}</code><br><span class="small">${desc}</span></td>
      <td><span class="badge ${typeCls}" style="font-size:.65rem">${typeLbl}</span></td>
      <td class="text-end">${_whFmtQty(p.qty_requested)} ${p.uom||''}</td>
      <td>${p.supplier_po_ref ? `<code class="small">${p.supplier_po_ref}</code>` : '<span class="text-muted small">—</span>'}</td>
      <td><span class="badge ${stCls}" style="font-size:.65rem">${p.status}</span></td>
      <td>${_whFmtDate(p.needed_by)}</td>
      <td>${plan}</td>
    </tr>`;
  }).join('');
}

// ── Page loader registry ────────────────────────────────────
// Self-register the three pages this module owns. Replaces the
// equivalent entries in the main inline script's Object.assign call.
Object.assign(PAGE_LOADERS, {
  'wh-dashboard':  whDashLoad,
  'wh-low-stock':  whLowStockLoad,
  'wh-open-prs':   whOpenPRsLoad,
});
