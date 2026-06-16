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


// ════════════════════════════════════════════════════════════
// Raw Material Receiving
// ════════════════════════════════════════════════════════════
// ══════════════════════════════════════════════════════════════
// RAW MATERIAL RECEIVING (Warehouse)
// ══════════════════════════════════════════════════════════════
let _rrecRows=[];
function _rrecNum(n){return n==null||n===''?'—':Number(n).toLocaleString(undefined,{maximumFractionDigits:2});}
function _rrecStatBadge(s){
  const m={PLANNED:['secondary','Planned','bi-calendar-event'],
           UNPLANNED:['warning text-dark','Unplanned (PR open)','bi-question-circle'],
           PARTIAL:['warning text-dark','Partial','bi-hourglass-split'],
           RECEIVED:['success','Received','bi-check2-circle'],
           CANCELLED:['dark','Cancelled','bi-x-circle']};
  const x=m[s]||['secondary',s,'bi-circle'];
  return `<span class="badge bg-${x[0]}"><i class="bi ${x[2]} me-1"></i>${x[1]}</span>`;
}
async function rrecLoad(){
  try{
    // include_implicit so PRs in-flight WITHOUT scheduled shipments still show up
    _rrecRows = await api('/api/shipments?include_implicit=true');
    if(!Array.isArray(_rrecRows)) _rrecRows=[];
    rrecRender(); rrecRenderKpi();
    rrecUpdateBadge();
  }catch(e){
    document.getElementById('rrec-tbody').innerHTML=`<tr><td colspan="10" class="text-danger small p-3">${e.message||e}</td></tr>`;
  }
}
function rrecRenderKpi(){
  const today=new Date().toISOString().slice(0,10);
  const k={unplanned:0,planned:0,partial:0,arriving7d:0,overdue:0,received_today:0};
  _rrecRows.forEach(r=>{
    if(r.status==='UNPLANNED') k.unplanned++;
    if(r.status==='PLANNED')   k.planned++;
    if(r.status==='PARTIAL')   k.partial++;
    if(r.status==='RECEIVED' && (r.received_at||'').slice(0,10)===today) k.received_today++;
    if((r.status==='PLANNED'||r.status==='PARTIAL'||r.status==='UNPLANNED') && r.planned_arrival){
      if(r.planned_arrival < today) k.overdue++;
      else if(r.planned_arrival <= new Date(Date.now()+7*86400000).toISOString().slice(0,10)) k.arriving7d++;
    }
  });
  document.getElementById('rrec-kpi').innerHTML=[
    {l:'Unplanned (PR open)',v:k.unplanned, bg:'warning',  ico:'bi-question-circle'},
    {l:'Planned',         v:k.planned,        bg:'secondary',ico:'bi-calendar-event'},
    {l:'Partial',         v:k.partial,        bg:'warning',  ico:'bi-hourglass-split'},
    {l:'Arriving ≤ 7 days',v:k.arriving7d,    bg:'info',     ico:'bi-truck'},
    {l:'Overdue',         v:k.overdue,        bg:'danger',   ico:'bi-exclamation-triangle'},
    {l:'Received Today',  v:k.received_today, bg:'success',  ico:'bi-check2-circle'},
  ].map(c=>`<div class="col-md col-6"><div class="card border-${c.bg}"><div class="card-body py-2 px-3">
    <div class="small text-muted" style="font-size:.7rem"><i class="bi ${c.ico} me-1"></i>${c.l}</div>
    <div class="fs-5 fw-semibold">${c.v}</div></div></div></div>`).join('');
}
function rrecRender(){
  const state=document.getElementById('rrec-state').value;
  const cat=(document.getElementById('rrec-cat')?.value)||'';
  const q=(document.getElementById('rrec-filter').value||'').toLowerCase();
  let rows=_rrecRows;
  if(state==='OPEN')        rows=rows.filter(r=>r.status==='PLANNED'||r.status==='PARTIAL'||r.status==='UNPLANNED');
  else if(state)            rows=rows.filter(r=>r.status===state);
  if(cat)                   rows=rows.filter(r=>r.material_type===cat);
  if(q) rows=rows.filter(r=>JSON.stringify(r).toLowerCase().includes(q));
  const today=new Date().toISOString().slice(0,10);
  // Only Warehouse + Managerial actually receive; other roles (e.g. Production
  // Planning) get this page read-only for arrival planning.
  const canReceive = ['WAREHOUSE','MANAGERIAL'].includes(((typeof getCurrentUser==='function'?getCurrentUser():null)||{}).role);
  const tb=document.getElementById('rrec-tbody');
  if(!rows.length){
    tb.innerHTML='<tr><td colspan="10" class="text-center text-muted py-4">No shipments match the filter.</td></tr>';
    return;
  }
  tb.innerHTML=rows.map(r=>{
    const remaining=Math.max(0,Number(r.planned_qty||0)-Number(r.received_qty||0));
    const arrCls=r.planned_arrival
      ? (r.planned_arrival<today && r.status!=='RECEIVED' ? 'text-danger fw-bold' : 'small')
      : 'small text-muted';
    let action;
    if(canReceive && (r.status==='PLANNED'||r.status==='PARTIAL')){
      action=`<button class="btn btn-xs btn-success"
        onclick='rrecOpenReceive(${JSON.stringify(r).replace(/'/g,"&apos;")})'>
        <i class="bi bi-box-arrow-in-down me-1"></i>Receive</button>`;
    }else if(canReceive && r.status==='UNPLANNED'){
      action=`<button class="btn btn-xs btn-warning text-dark" title="No schedule yet — receive walk-in goods"
        onclick='rrecOpenReceive(${JSON.stringify(r).replace(/'/g,"&apos;")})'>
        <i class="bi bi-box-arrow-in-down me-1"></i>Walk-in Receive</button>`;
    }else if(r.status==='RECEIVED'){
      action=`<span class="small text-muted">${(r.received_at||'').slice(0,16).replace('T',' ')}<br>by ${r.received_by||'—'}</span>`;
    }else{
      action='<span class="text-muted small">—</span>';
    }
    const docs=(r.doc_count||0)>0
      ? `<span class="badge bg-danger"><i class="bi bi-file-earmark-pdf me-1"></i>${r.doc_count}</span>`
      : '<span class="text-muted small">—</span>';
    return `<tr>
      <td class="small"><b>${r.request_number||('PR-'+r.pr_id)}</b><br><span class="text-muted">Shipment #${r.sequence}</span></td>
      <td class="small"><span class="badge bg-light text-dark border" style="font-size:.6rem">${(r.material_type||'').toUpperCase()}</span> <b>${r.material_code||''}</b> ${r.material_name||''}</td>
      <td class="small">${r.supplier_po_ref||r.supplier_ref||'—'}${r.carrier?'<br><span class="text-muted">'+r.carrier+'</span>':''}</td>
      <td class="text-end">${_rrecNum(r.planned_qty)} <span class="text-muted small">${r.uom||''}</span></td>
      <td class="text-end ${r.received_qty>0?'text-success':'text-muted'}">${_rrecNum(r.received_qty)}</td>
      <td class="text-end ${remaining>0&&r.status!=='RECEIVED'?'text-warning fw-semibold':'text-muted'}">${remaining>0?_rrecNum(remaining):'—'}</td>
      <td class="${arrCls}">${r.planned_arrival||'—'}</td>
      <td>${_rrecStatBadge(r.status)}</td>
      <td>${docs}</td>
      <td class="text-end" style="white-space:nowrap">${action}</td>
    </tr>`;
  }).join('');
}
function rrecOpenReceive(r){
  // Two flavours: real shipment row (id is integer) vs synthesised UNPLANNED row (id null)
  const isUnplanned = (r.status === 'UNPLANNED') || !r.id;
  document.getElementById('rrec-ship-id').value = isUnplanned ? `pr:${r.pr_id}` : r.id;
  const remaining=Math.max(0,Number(r.planned_qty||0)-Number(r.received_qty||0));
  document.getElementById('rrec-qty').value=remaining||r.planned_qty;
  document.getElementById('rrec-uom').textContent=r.uom||'';
  document.getElementById('rrec-lot').value='';
  document.getElementById('rrec-cost').value='';
  document.getElementById('rrec-expiry').value='';
  document.getElementById('rrec-supref').value=r.supplier_ref||'';
  document.getElementById('rrec-notes').value='';
  if(isUnplanned){
    document.getElementById('rrec-ctx').innerHTML=
      `<b>${r.material_code||''} ${r.material_name}</b><br>`+
      `PR <b>${r.request_number}</b> · <span class="badge bg-warning text-dark">No shipment scheduled</span><br>`+
      `Unscheduled qty: <b>${_rrecNum(r.planned_qty)} ${r.uom||''}</b> · PR ETA: <b>${r.pr_eta||'—'}</b>`+
      (r.supplier_po_ref?` · Supplier PO <b>${r.supplier_po_ref}</b>`:'');
    document.getElementById('rrec-qty-hint').textContent =
      `Receive walk-in goods directly. A shipment row will be created automatically for the qty you enter.`;
  }else{
    document.getElementById('rrec-ctx').innerHTML=
      `<b>${r.material_code||''} ${r.material_name}</b><br>`+
      `PR <b>${r.request_number}</b> · Shipment <b>#${r.sequence}</b> · Planned <b>${_rrecNum(r.planned_qty)} ${r.uom||''}</b>`+
      (r.received_qty>0?` · Already received <b>${_rrecNum(r.received_qty)}</b>`:'')+
      (r.planned_arrival?` · Planned arrival <b>${r.planned_arrival}</b>`:'');
    document.getElementById('rrec-qty-hint').textContent =
      `Remaining on this shipment: ${_rrecNum(remaining)} ${r.uom||''}. Enter less for a partial receipt.`;
  }
  // Destination (WH/WLWH) only for boards & veneers
  const isBV = (r.material_type==='core_board'||r.material_type==='veneer_sheet');
  const dw=document.getElementById('rrec-dest-wrap'); if(dw) dw.style.display = isBV?'':'none';
  const ds=document.getElementById('rrec-dest'); if(ds) ds.value='WH';
  new bootstrap.Modal(document.getElementById('rrecReceiveModal')).show();
}
async function rrecSubmit(){
  const ref=document.getElementById('rrec-ship-id').value;
  const body={
    received_qty: Number(document.getElementById('rrec-qty').value||0),
    lot_code:     document.getElementById('rrec-lot').value.trim(),
    unit_cost:    Number(document.getElementById('rrec-cost').value||0),
    expiry_date:  document.getElementById('rrec-expiry').value||null,
    supplier_lot_ref: document.getElementById('rrec-supref').value,
    notes:        document.getElementById('rrec-notes').value,
    destination:  (document.getElementById('rrec-dest-wrap')?.style.display!=='none'
                    ? (document.getElementById('rrec-dest')?.value||'WH') : 'WH'),
  };
  if(body.received_qty<=0){ alert('Quantity must be greater than zero'); return; }
  try{
    let r;
    if(ref.startsWith('pr:')){
      // UNPLANNED row → quick-receive (creates shipment + lot atomically)
      const prId = Number(ref.slice(3));
      r = await api(`/api/purchase-requests/${prId}/quick-receive`, 'POST', body);
    }else{
      r = await api(`/api/shipments/${ref}/receive`, 'POST', body);
    }
    bootstrap.Modal.getInstance(document.getElementById('rrecReceiveModal'))?.hide();
    toast(`Receipt confirmed — Lot ${r.lot_code} created (${r.shipment_status})`);
    rrecLoad();
  }catch(e){ alert('Receipt failed: '+(e.message||e)); }
}
function rrecUpdateBadge(){
  // Count "needs attention" = anything not yet fully received + (due or unscheduled)
  const today=new Date().toISOString().slice(0,10);
  const n=_rrecRows.filter(r=>
    (r.status==='PLANNED'||r.status==='PARTIAL'||r.status==='UNPLANNED') &&
    (!r.planned_arrival || r.planned_arrival<=today || r.status==='UNPLANNED')).length;
  const b=document.getElementById('nav-raw-recv-badge');
  if(b){ b.textContent=n; b.classList.toggle('d-none', n===0); }
}
async function rrecRefreshBadge(){
  try{
    const rows=await api('/api/shipments?include_implicit=true');
    if(Array.isArray(rows)){ _rrecRows=rows; rrecUpdateBadge(); }
  }catch{}
}
setTimeout(rrecRefreshBadge, 6000);
setInterval(rrecRefreshBadge, 300000);


// ════════════════════════════════════════════════════════════
// Forklift Refueling (warehouse)
// ════════════════════════════════════════════════════════════
// ══════════════════════════════════════════════════════════════
// WAREHOUSE — Forklift Refueling Dashboard
// ══════════════════════════════════════════════════════════════
let _frflAll=[], _frflConfig=null;
function _frflTodayStr(){
  const d = document.getElementById('frfl-date');
  if(d && d.value) return d.value;
  return new Date().toISOString().slice(0,10);
}
function _frflPrioBadge(p){
  return p==='URGENT'
    ? '<span class="badge bg-danger"><i class="bi bi-exclamation-triangle me-1"></i>URGENT</span>'
    : '<span class="badge bg-success-subtle text-success border border-success">Normal</span>';
}

async function frflLoad(){
  // Default the date filter to today on first open
  const dEl=document.getElementById('frfl-date');
  if(dEl && !dEl.value) dEl.value = new Date().toISOString().slice(0,10);
  try{
    if(!_frflConfig){
      _frflConfig = await api('/api/forklifts/refuel-config').catch(()=>null);
      if(_frflConfig){
        document.getElementById('frfl-window-label').textContent =
          `Window: ${String(_frflConfig.window_hour).padStart(2,'0')}:00 daily · cutoff ${String(_frflConfig.request_cutoff).padStart(2,'0')}:30`;
      }
    }
    const status=document.getElementById('frfl-status-filter').value;
    const qs=[];
    if(status) qs.push('status='+status);
    _frflAll = await api('/api/forklifts/oil-requests'+(qs.length?'?'+qs.join('&'):''));
    if(!Array.isArray(_frflAll)) _frflAll=[];
    frflRender();
    frflUpdateBadge();
    // Also pull last 7 days of fulfilled history independently
    const done = await api('/api/forklifts/oil-requests?status=FULFILLED').catch(()=>[]);
    frflRenderDone(done);
  }catch(e){
    document.getElementById('frfl-today-tbody').innerHTML=`<tr><td colspan="7" class="text-danger small p-3">${e.message||e}</td></tr>`;
  }
}

function frflRender(){
  const today = _frflTodayStr();
  const urgent = _frflAll.filter(r => r.status==='PENDING' && r.priority==='URGENT');
  const todayBatch = _frflAll.filter(r => r.status==='PENDING' && r.priority!=='URGENT'
    && (r.scheduled_for||'').slice(0,10) === today);
  const future = _frflAll.filter(r => r.status==='PENDING' && r.priority!=='URGENT'
    && (r.scheduled_for||'').slice(0,10) > today);

  // KPI strip
  document.getElementById('frfl-kpi').innerHTML=[
    {l:'URGENT',         v:urgent.length,    bg:'danger',  ico:'bi-exclamation-triangle'},
    {l:'Today\'s Batch', v:todayBatch.length,bg:'info',    ico:'bi-clock'},
    {l:'Future / Scheduled', v:future.length,bg:'secondary',ico:'bi-calendar-week'},
    {l:'Litres Needed Today', v:(urgent.concat(todayBatch).reduce((s,r)=>s+Number(r.qty_litres||0),0)).toFixed(1)+' L', bg:'primary', ico:'bi-droplet-half'},
  ].map(c=>`<div class="col-md-3 col-6"><div class="card border-${c.bg}"><div class="card-body py-2 px-3">
    <div class="small text-muted"><i class="bi ${c.ico} me-1"></i>${c.l}</div>
    <div class="fs-5 fw-semibold">${c.v}</div></div></div></div>`).join('');

  // Urgent block
  const ucard=document.getElementById('frfl-urgent-card');
  const utb=document.getElementById('frfl-urgent-tbody');
  document.getElementById('frfl-urgent-count').textContent = urgent.length;
  ucard.style.display = urgent.length ? '' : 'none';
  utb.innerHTML = urgent.map(r=>frflRowHtml(r,true)).join('');

  // Today's batch
  document.getElementById('frfl-today-label').textContent =
    `${today} ${(_frflConfig?.window_hour ?? 11).toString().padStart(2,'0')}:00 Refuel Batch`;
  document.getElementById('frfl-today-count').textContent = todayBatch.length;
  document.getElementById('frfl-today-tbody').innerHTML = todayBatch.length
    ? todayBatch.map(r=>frflRowHtml(r,false)).join('')
    : '<tr><td colspan="7" class="text-center text-muted py-3">No requests scheduled for this slot.</td></tr>';

  // Future
  document.getElementById('frfl-future-count').textContent = future.length;
  document.getElementById('frfl-future-tbody').innerHTML = future.length
    ? future.map(r=>`<tr>
        <td class="small fw-semibold">${r.forklift_code}</td>
        <td class="small">${r.forklift_dept||'—'}${r.forklift_line?' / '+r.forklift_line:''}</td>
        <td class="small">${r.oil_type}</td>
        <td class="text-end">${Number(r.qty_litres).toFixed(1)} L</td>
        <td class="small">${(r.scheduled_for||'').slice(0,16).replace('T',' ')}</td>
        <td class="small">${r.postponed_count?`<span class="badge bg-warning text-dark">${r.postponed_count}×</span>`:'—'}</td>
        <td class="small text-muted">${(r.notes||'').slice(0,60)}</td>
      </tr>`).join('')
    : '<tr><td colspan="7" class="text-center text-muted py-3">Nothing scheduled for future slots.</td></tr>';

  // Disable fulfill-all if nothing
  document.getElementById('frfl-fulfill-all').disabled = todayBatch.length === 0;
}

function frflRowHtml(r, isUrgent){
  return `<tr ${isUrgent?'style="background:#fef2f2"':''}>
    <td class="small fw-semibold">${r.forklift_code} <span class="text-muted">${r.forklift_name||''}</span></td>
    <td class="small">${r.forklift_dept||'—'}${r.forklift_line?' / '+r.forklift_line:''}</td>
    <td class="small">${r.oil_type}</td>
    <td class="text-end">${Number(r.qty_litres).toFixed(1)} L</td>
    <td class="small">${(r.requested_at||'').slice(0,16).replace('T',' ')}<br><span class="text-muted">${r.requested_by||''}</span></td>
    <td class="small text-muted" style="max-width:240px">${(r.notes||'').slice(0,120)}</td>
    <td class="text-end" style="white-space:nowrap">
      <button class="btn btn-xs btn-success" title="Mark fulfilled" onclick="frflFulfill(${r.id}, ${r.qty_litres})">
        <i class="bi bi-check2"></i>
      </button>
      ${!isUrgent?`<button class="btn btn-xs btn-outline-warning" title="Postpone to next slot" onclick="frflPostpone(${r.id})">
        <i class="bi bi-arrow-clockwise"></i>
      </button>`:''}
      <button class="btn btn-xs btn-outline-secondary" title="Cancel" onclick="frflCancel(${r.id})">
        <i class="bi bi-x"></i>
      </button>
    </td>
  </tr>`;
}

function frflRenderDone(done){
  if(!Array.isArray(done)) done=[];
  const cutoff = new Date(Date.now() - 7*86400000).toISOString().slice(0,10);
  const recent = done.filter(r => (r.fulfilled_at||'').slice(0,10) >= cutoff);
  document.getElementById('frfl-done-count').textContent = recent.length;
  document.getElementById('frfl-done-tbody').innerHTML = recent.length
    ? recent.slice(0,50).map(r=>`<tr>
        <td class="small fw-semibold">${r.forklift_code} <span class="text-muted">${r.forklift_name||''}</span></td>
        <td class="small">${r.oil_type}</td>
        <td class="text-end">${Number(r.qty_litres).toFixed(1)} L</td>
        <td class="text-end text-success">${Number(r.fulfilled_qty||0).toFixed(1)} L</td>
        <td class="small">${(r.fulfilled_at||'').slice(0,16).replace('T',' ')}</td>
        <td class="small">${r.fulfilled_by||'—'}</td>
      </tr>`).join('')
    : '<tr><td colspan="6" class="text-center text-muted py-3">No fulfilled requests in the last 7 days.</td></tr>';
}

async function frflFulfill(id, suggestedQty){
  const q = prompt(`Fulfilled litres? (blank = requested qty ${suggestedQty} L)`, '');
  try{
    await api(`/api/forklifts/oil-requests/${id}`,'PATCH',{
      status:'FULFILLED', fulfilled_qty: q ? Number(q) : null});
    frflLoad();
  }catch(e){ alert('Update failed: '+(e.message||e)); }
}
async function frflPostpone(id){
  const days = prompt('Postpone how many days?', '1');
  if(days===null) return;
  const reason = prompt('Reason for postponing?', '');
  if(reason===null) return;
  try{
    await api(`/api/forklifts/oil-requests/${id}/postpone`,'POST',
      {days:Number(days)||1, reason});
    frflLoad();
  }catch(e){ alert('Postpone failed: '+(e.message||e)); }
}
async function frflCancel(id){
  if(!confirm('Cancel this oil request?')) return;
  try{
    await api(`/api/forklifts/oil-requests/${id}`,'PATCH',{status:'CANCELLED'});
    frflLoad();
  }catch(e){ alert(e.message||e); }
}
async function frflFulfillAll(){
  const today = _frflTodayStr();
  const batch = _frflAll.filter(r => r.status==='PENDING' && r.priority!=='URGENT'
    && (r.scheduled_for||'').slice(0,10) === today);
  if(!batch.length) return;
  if(!confirm(`Fulfill all ${batch.length} request(s) in today's batch using requested litres?`)) return;
  let ok=0, fail=0;
  for(const r of batch){
    try{
      await api(`/api/forklifts/oil-requests/${r.id}`,'PATCH',{
        status:'FULFILLED', fulfilled_qty: r.qty_litres});
      ok++;
    }catch{ fail++; }
  }
  toast(`Fulfilled ${ok} request(s)${fail?` · ${fail} failed`:''}`, fail?'warning':'success');
  frflLoad();
}

function frflUpdateBadge(){
  // Red badge counts URGENT + today's overdue
  const today = _frflTodayStr();
  const urgent = (_frflAll||[]).filter(r => r.status==='PENDING' && r.priority==='URGENT').length;
  const dueToday = (_frflAll||[]).filter(r => r.status==='PENDING' && r.priority!=='URGENT'
    && (r.scheduled_for||'').slice(0,10) <= today).length;
  const n = urgent + dueToday;
  const b = document.getElementById('nav-forklift-refuel-badge');
  if(b){ b.textContent = n; b.classList.toggle('d-none', n===0); }
}
async function frflRefreshBadge(){
  try{
    const rows = await api('/api/forklifts/oil-requests?status=PENDING');
    if(Array.isArray(rows)){ _frflAll = rows; frflUpdateBadge(); }
  }catch{}
}
setTimeout(frflRefreshBadge, 7000);
setInterval(frflRefreshBadge, 180000);  // every 3 minutes


// ════════════════════════════════════════════════════════════
// Forklift Dashboard + Oil drum stock
// ════════════════════════════════════════════════════════════
// ══════════════════════════════════════════════════════════════
// WAREHOUSE — FORKLIFT DASHBOARD + Oil drum stock
// ══════════════════════════════════════════════════════════════
let _fkdashFlk=[], _fkdashOil=[];
async function fkDashLoad(){
  try{
    const [flk, oil, oilReqs] = await Promise.all([
      api('/api/forklifts'),
      api('/api/forklifts/oil-drums').catch(()=>[]),
      api('/api/forklifts/oil-requests?status=FULFILLED').catch(()=>[]),
    ]);
    _fkdashFlk = flk||[]; _fkdashOil = oil||[];
    // last-refuel lookup
    const lastBy = {};
    (oilReqs||[]).forEach(r=>{
      const cur = lastBy[r.forklift_id];
      if(!cur || (r.fulfilled_at||'') > (cur.fulfilled_at||'')) lastBy[r.forklift_id]=r;
    });
    document.getElementById('fkdash-kpi').innerHTML = [
      {l:'Total Forklifts',  v:_fkdashFlk.length,                                  bg:'primary',ico:'bi-truck-flatbed'},
      {l:'Active',           v:_fkdashFlk.filter(f=>f.status==='active').length,   bg:'success',ico:'bi-check2-circle'},
      {l:'In Maintenance',   v:_fkdashFlk.filter(f=>f.status==='maintenance').length, bg:'warning',ico:'bi-wrench'},
      {l:'Oil Drums Stocked',v:_fkdashOil.length,                                  bg:'info',   ico:'bi-droplet'},
    ].map(c=>`<div class="col-md-3 col-6"><div class="card border-${c.bg}"><div class="card-body py-2 px-3">
      <div class="small text-muted"><i class="bi ${c.ico} me-1"></i>${c.l}</div>
      <div class="fs-5 fw-semibold">${c.v}</div></div></div></div>`).join('');
    document.getElementById('fkdash-flk-tbody').innerHTML = _fkdashFlk.length
      ? _fkdashFlk.map(f=>{
        const lr = lastBy[f.id];
        const stat = {active:'success',maintenance:'warning text-dark',retired:'secondary'}[f.status]||'secondary';
        return `<tr>
          <td class="small fw-semibold">${f.code}</td>
          <td class="small">${f.name||'—'}</td>
          <td class="small">${f.dept||'—'}${f.production_line?' / '+f.production_line:''}</td>
          <td class="small">${f.model||'—'}</td>
          <td class="small">${f.fuel_type||'—'}</td>
          <td class="text-end small">${f.hours_meter?Number(f.hours_meter).toLocaleString():'—'}</td>
          <td><span class="badge bg-${stat}">${f.status}</span></td>
          <td class="text-end small text-muted">${lr ? lr.fulfilled_at.slice(0,16).replace('T',' ')+' · '+Number(lr.fulfilled_qty||0).toFixed(1)+'L' : 'never'}</td>
        </tr>`;
      }).join('')
      : '<tr><td colspan="8" class="text-center text-muted py-3">No forklifts registered.</td></tr>';
    document.getElementById('fkdash-oil-tbody').innerHTML = _fkdashOil.length
      ? _fkdashOil.map(o=>{
        const low = o.reorder_point > 0 && o.current_stock <= o.reorder_point;
        return `<tr ${low?'class="table-danger"':''}>
          <td class="small">${o.name}${o.code?' <span class="text-muted">('+o.code+')</span>':''}</td>
          <td class="small">${o.unit||'L'}</td>
          <td class="text-end fw-semibold">${Number(o.current_stock||0).toFixed(1)}</td>
          <td class="text-end small text-muted">${o.reorder_point||'—'}</td>
          <td class="small">${low?'<span class="badge bg-danger">LOW</span>':''}</td>
        </tr>`;
      }).join('')
      : '<tr><td colspan="5" class="text-muted py-3 text-center">No materials tagged as oil/lubricant. Add some on the Raw Materials page (any material whose name contains "oil", "hydraulic" or "lubric" will appear here).</td></tr>';
  }catch(e){
    document.getElementById('fkdash-flk-tbody').innerHTML=`<tr><td colspan="8" class="text-danger small p-3">${e.message||e}</td></tr>`;
  }
}


// ════════════════════════════════════════════════════════════
// Refuel Window Settings
// ════════════════════════════════════════════════════════════
// ══════════════════════════════════════════════════════════════
// REFUEL WINDOW SETTINGS  (called from frfl page Settings button)
// ══════════════════════════════════════════════════════════════
async function rfwOpen(){
  await rfwLoad();
  new bootstrap.Modal(document.getElementById('rfwModal')).show();
}
async function rfwLoad(){
  const rows = await api('/api/forklifts/refuel-windows');
  document.getElementById('rfw-tbody').innerHTML = (rows||[]).length
    ? rows.map(w=>`<tr>
        <td>${w.label}</td>
        <td>${String(w.start_hour).padStart(2,'0')}:${String(w.start_min).padStart(2,'0')}</td>
        <td>${String(w.cutoff_hour).padStart(2,'0')}:${String(w.cutoff_min).padStart(2,'0')}</td>
        <td class="small">${w.days_of_week}</td>
        <td>${w.active ? '<span class="badge bg-success">on</span>' : '<span class="badge bg-secondary">off</span>'}</td>
        <td><button class="btn btn-xs btn-outline-danger" onclick="rfwDelete(${w.id})"><i class="bi bi-trash"></i></button></td>
      </tr>`).join('')
    : '<tr><td colspan="6" class="text-muted text-center small py-2">No windows configured — system uses 11:00 default.</td></tr>';
}
async function rfwAdd(){
  const body = {
    label: document.getElementById('rfw-label').value.trim(),
    start_hour: Number(document.getElementById('rfw-sh').value||11),
    start_min:  Number(document.getElementById('rfw-sm').value||0),
    cutoff_hour:Number(document.getElementById('rfw-ch').value||10),
    cutoff_min: Number(document.getElementById('rfw-cm').value||30),
    days_of_week: document.getElementById('rfw-days').value || 'mon,tue,wed,thu,fri,sat',
    active: 1,
  };
  if(!body.label){ alert('Label required'); return; }
  try{
    await api('/api/forklifts/refuel-windows','POST',body);
    document.getElementById('rfw-label').value='';
    rfwLoad();
    _frflConfig = null;  // force frfl to re-fetch
  }catch(e){ alert('Save failed: '+(e.message||e)); }
}
async function rfwDelete(id){
  if(!confirm('Delete this refuel window?')) return;
  try{ await api('/api/forklifts/refuel-windows/'+id,'DELETE'); rfwLoad(); _frflConfig=null; }
  catch(e){ alert(e.message||e); }
}


// ════════════════════════════════════════════════════════════
// Scrap / LG Bin
// ════════════════════════════════════════════════════════════
// ══════════════════════════════════════════════════════════════
// SCRAP / LG BIN
// ══════════════════════════════════════════════════════════════
let _scrapReasons=['GLUE_DEFECT','CRACK','WARP','DELAMINATION','COLOUR_MISMATCH','SURFACE_DAMAGE','WRONG_THICKNESS','EDGE_DAMAGE','OTHER'];
async function scrapLoad(){
  const disp=document.getElementById('scrap-disp-filter').value;
  try{
    const rows = await api('/api/scrap'+(disp?('?disposition='+disp):''));
    if(!Array.isArray(rows)) return;
    const tb=document.getElementById('scrap-tbody');
    if(!rows.length){
      tb.innerHTML='<tr><td colspan="9" class="text-center text-muted py-3">No scrap entries.</td></tr>';
    }else{
      tb.innerHTML=rows.map(r=>{
        const dispOpts = ['REWORK','DOWNGRADE','RECYCLE','DISPOSE']
          .map(d=>`<button class="btn btn-xs btn-outline-secondary" onclick="scrapDispose(${r.id},'${d}')">${d}</button>`).join(' ');
        return `<tr>
          <td class="small">${(r.created_at||'').slice(0,16).replace('T',' ')}</td>
          <td class="small fw-semibold">${r.batch_number||('#'+r.batch_id)}</td>
          <td class="small">${r.product_sku||''} ${r.product_name||''}</td>
          <td class="small">${r.dept}${r.production_line?' / '+r.production_line:''}</td>
          <td class="text-end fw-semibold text-danger">${r.pcs_scrapped}</td>
          <td class="small"><span class="badge bg-warning text-dark">${r.reason_code}</span>${r.reason_detail?'<br><span class="text-muted small">'+r.reason_detail.slice(0,80)+'</span>':''}</td>
          <td class="small">${r.created_by||'—'}</td>
          <td><span class="badge bg-${({PENDING_REVIEW:'warning text-dark',REWORK:'info',DOWNGRADE:'primary',RECYCLE:'success',DISPOSE:'dark'})[r.disposition]||'secondary'}">${r.disposition}</span>${r.reviewed_by?'<br><span class="text-muted small">by '+r.reviewed_by+'</span>':''}</td>
          <td class="text-end" style="white-space:nowrap">${r.disposition==='PENDING_REVIEW'?dispOpts:''}</td>
        </tr>`;
      }).join('');
    }
    // Update sidebar badge
    const pending = rows.filter(r=>r.disposition==='PENDING_REVIEW').length;
    const b=document.getElementById('nav-scrap-badge');
    if(b){ b.textContent=pending; b.classList.toggle('d-none', pending===0); }
  }catch(e){
    document.getElementById('scrap-tbody').innerHTML=`<tr><td colspan="9" class="text-danger small p-3">${e.message||e}</td></tr>`;
  }
}
async function scrapDispose(id, disposition){
  const notes = prompt(`Notes for ${disposition} decision (optional)`, '') || '';
  try{
    await api(`/api/scrap/${id}/disposition`,'PATCH',{disposition, notes});
    scrapLoad();
  }catch(e){ alert(e.message||e); }
}
// Called from station card "Reject to LG Bin" buttons
async function scrapOpen(batch){
  document.getElementById('scrap-batch-id').value = batch.id;
  document.getElementById('scrap-dept').value = batch.current_department || '';
  document.getElementById('scrap-pcs').value = '';
  document.getElementById('scrap-detail').value = '';
  try{
    if(!_scrapReasons || !_scrapReasons.length)
      _scrapReasons = await api('/api/scrap/reasons');
  }catch{}
  document.getElementById('scrap-reason').innerHTML = _scrapReasons.map(r=>`<option>${r}</option>`).join('');
  document.getElementById('scrap-ctx').innerHTML =
    `<i class="bi bi-exclamation-triangle me-1"></i>Reject pcs from <b>${batch.batch_number||'#'+batch.id}</b> at <b>${batch.current_department}</b>. These will be reviewed by a manager.`;
  new bootstrap.Modal(document.getElementById('scrapModal')).show();
}
async function scrapSubmit(){
  const body = {
    batch_id:     Number(document.getElementById('scrap-batch-id').value),
    dept:         document.getElementById('scrap-dept').value,
    pcs_scrapped: Number(document.getElementById('scrap-pcs').value||0),
    reason_code:  document.getElementById('scrap-reason').value,
    reason_detail:document.getElementById('scrap-detail').value,
  };
  if(!body.batch_id || body.pcs_scrapped<=0 || !body.reason_code){ alert('Pcs + reason required'); return; }
  try{
    await api('/api/scrap','POST',body);
    bootstrap.Modal.getInstance(document.getElementById('scrapModal'))?.hide();
    toast('Sent to LG bin','warning');
  }catch(e){ alert('Failed: '+(e.message||e)); }
}


// ════════════════════════════════════════════════════════════
// Hook-ups: oil-drum picker + settings button
// ════════════════════════════════════════════════════════════
// ══════════════════════════════════════════════════════════════
// Hook up extra UI: oil drum picker on fulfill, settings button on refuel page
// ══════════════════════════════════════════════════════════════
// Wrap frflLoad to also inject a Settings button on first render
const _orig_frflLoad = window.frflLoad;
window.frflLoad = async function(){
  await _orig_frflLoad?.();
  // Add settings button into the page header once
  if(!document.getElementById('frfl-settings-btn')){
    const headerDiv = document.querySelector('#page-forklift-refuel .d-flex.justify-content-between .d-flex.gap-2');
    if(headerDiv){
      const btn = document.createElement('button');
      btn.id='frfl-settings-btn';
      btn.className='btn btn-sm btn-outline-info';
      btn.innerHTML='<i class="bi bi-gear me-1"></i>Window Settings';
      btn.onclick=rfwOpen;
      headerDiv.insertBefore(btn, headerDiv.firstChild);
    }
  }
};

// Wrap frflFulfill to prompt for an oil drum (so warehouse stock decrements)
const _orig_frflFulfill = window.frflFulfill;
window.frflFulfill = async function(id, suggestedQty){
  let drums=[];
  try{ drums = await api('/api/forklifts/oil-drums'); }catch{}
  let pickedDrum = null;
  if(drums && drums.length){
    const options = drums.map((d,i)=>`${i+1}. ${d.name} (stock: ${d.current_stock||0} ${d.unit||'L'})`).join('\n');
    const choice = prompt(
      `Which oil drum did you dispense from? Enter the number (Cancel = skip stock deduction)\n\n${options}`, '1');
    if(choice !== null){
      const idx = parseInt(choice) - 1;
      if(idx >= 0 && idx < drums.length) pickedDrum = drums[idx];
    }
  }
  const q = prompt(`Fulfilled litres? (blank = requested qty ${suggestedQty} L)`, '');
  try{
    await api(`/api/forklifts/oil-requests/${id}`,'PATCH',{
      status:'FULFILLED',
      fulfilled_qty: q ? Number(q) : null,
      oil_material_id: pickedDrum ? pickedDrum.id : null,
    });
    frflLoad();
  }catch(e){ alert('Update failed: '+(e.message||e)); }
};

// ════════════════════════════════════════════════════════════
// Warehouse Supply Queue
// ════════════════════════════════════════════════════════════
// ══════════════════════════════════════════════════════════════
// WAREHOUSE SUPPLY QUEUE
// ══════════════════════════════════════════════════════════════
let _wqTab='PENDING', _wqFulfillId=null, _wqFulfillMat=null;
let _wqSection='consumable', _wqRmTab='PENDING', _wqRetTab='PENDING';
let _wqFcFulfillId=null, _wqFcFulfillMat=null;

function wqSetSection(sec){
  _wqSection=sec;
  ['consumable','rawmat','returns'].forEach(s=>{
    const tabEl = document.getElementById(`wq-sectab-${s}`);
    const paneEl = document.getElementById(`wq-pane-${s}`);
    if(tabEl) tabEl.classList.toggle('active',s===sec);
    if(paneEl) paneEl.classList.toggle('d-none',s!==sec);
  });
  if(sec==='rawmat') wqLoadRm();
  if(sec==='returns') wqLoadReturns();
}

function wqSetTab(tab){
  _wqTab=tab;
  ['PENDING','PARTIAL',''].forEach(t=>{
    const key=t||'all';
    const btn=document.getElementById(`wq-tab-${key.toLowerCase()}`);
    if(btn){ btn.classList.toggle('active',tab===t); btn.classList.toggle('btn-warning',tab===t&&t==='PENDING');
      btn.classList.toggle('btn-outline-secondary',tab!==t); }
  });
  wqLoad();
}

function wqRmSetTab(tab){
  _wqRmTab=tab;
  ['PENDING','PARTIAL',''].forEach(t=>{
    const key=t||'all';
    const btn=document.getElementById(`wq-rm-tab-${key.toLowerCase()}`);
    if(btn){ btn.classList.toggle('active',tab===t); btn.classList.toggle('btn-warning',tab===t&&t==='PENDING');
      btn.classList.toggle('btn-outline-secondary',tab!==t); }
  });
  wqLoadRm();
}

// Warehouse Portal pages moved to /static/js/portal_warehouse.js

let _wqAllReqs = [];   // cached so client-side filter/sort don't re-fetch
async function wqLoad(){
  const [reqs, rmReqs, retReqs, mats] = await Promise.all([
    api(`/api/consumable-requests${_wqTab?'?status='+_wqTab:''}`).catch(()=>[]),
    api('/api/fc/transfer-requests?direction=inbound&status=PENDING').catch(()=>[]),
    api('/api/fc/transfer-requests?direction=outbound&status=PENDING').catch(()=>[]),
    // Pull live materials snapshot in parallel so we can back-fill
    // current_stock onto request rows. This protects against deployments
    // where the consumable-requests endpoint hasn't yet been redeployed
    // with current_stock in its SELECT — the displayed value will still
    // match the Raw Materials page either way.
    api('/api/materials?include_formulas=true').catch(()=>[]),
  ]);
  if(!reqs) return;
  const matStock = {};
  if(Array.isArray(mats)) mats.forEach(m => { matStock[m.id] = m.current_stock; });
  reqs.forEach(r => {
    const live = matStock[r.material_id];
    if(live != null) r.current_stock = live;   // always trust the materials snapshot
  });
  _wqAllReqs = reqs;
  // KPI combined
  const totPending=reqs.filter(r=>r.status==='PENDING').length;
  const totPartial=reqs.filter(r=>r.status==='PARTIAL').length;
  const totRmPending=(rmReqs||[]).filter(r=>r.status==='PENDING').length;
  const totRetPending=(retReqs||[]).filter(r=>r.status==='PENDING').length;
  const totVal=reqs.filter(r=>['PENDING','PARTIAL'].includes(r.status))
    .reduce((s,r)=>(s+(r.qty_requested-r.qty_fulfilled)*(r.unit_cost||0)),0);
  document.getElementById('wq-cnt-pending').textContent=totPending;
  document.getElementById('wq-cnt-partial').textContent=totPartial;
  document.getElementById('wq-consumable-cnt').textContent=totPending+totPartial;
  document.getElementById('wq-rawmat-cnt').textContent=totRmPending;
  document.getElementById('wq-returns-cnt').textContent=totRetPending;
  document.getElementById('wq-kpi-row').innerHTML=`
    <div class="col-6 col-md"><div class="stat-card bg-warning bg-opacity-10 border-warning" style="padding:8px 12px"><div class="small text-muted">Consumable Pending</div><div class="h5 mb-0 fw-bold text-warning">${totPending}</div></div></div>
    <div class="col-6 col-md"><div class="stat-card bg-primary bg-opacity-10 border-primary" style="padding:8px 12px"><div class="small text-muted">Consumable Partial</div><div class="h5 mb-0 fw-bold text-primary">${totPartial}</div></div></div>
    <div class="col-6 col-md"><div class="stat-card bg-info bg-opacity-10 border-info" style="padding:8px 12px"><div class="small text-muted">FC Inbound Pending</div><div class="h5 mb-0 fw-bold text-info">${totRmPending}</div></div></div>
    <div class="col-6 col-md"><div class="stat-card bg-danger bg-opacity-10 border-danger" style="padding:8px 12px"><div class="small text-muted">FC Returns Pending</div><div class="h5 mb-0 fw-bold text-danger">${totRetPending}</div></div></div>
    <div class="col-12 col-md"><div class="stat-card" style="padding:8px 12px"><div class="small text-muted">Est. Consumable Value</div><div class="h5 mb-0 fw-bold">฿${totVal.toLocaleString('th-TH',{minimumFractionDigits:2,maximumFractionDigits:2})}</div></div></div>
  `;
  wqRenderTable();
}

function wqRenderTable(){
  const reqs = _wqAllReqs || [];
  const statusColor={PENDING:'warning',PARTIAL:'primary',FULFILLED:'success',CANCELLED:'secondary'};
  // Build filter strip once
  if(!document.getElementById('wq-filter-bar')){
    const host = document.getElementById('wq-cards');
    if(host){
      const bar = document.createElement('div');
      bar.id='wq-filter-bar';
      bar.className='card p-2 mb-2';
      bar.innerHTML = `
        <div class="d-flex flex-wrap align-items-center gap-2 small">
          <i class="bi bi-funnel text-muted"></i>
          <span class="fw-semibold">Filters:</span>
          <select class="form-select form-select-sm" id="wq-prio-filter" style="width:140px" onchange="wqRenderTable()">
            <option value="">All Priorities</option>
            <option value="1">P1 Urgent</option>
            <option value="2">P2 Normal</option>
            <option value="3">P3 Low</option>
          </select>
          <select class="form-select form-select-sm" id="wq-line-filter" style="width:130px" onchange="wqRenderTable()">
            <option value="">All Lines</option>
            <option value="P01">P01</option><option value="P02">P02</option><option value="P37">P37</option>
            <option value="PUV">PUV</option><option value="PVS">PVS</option><option value="PSP">PSP</option>
            <option value="__none__">(no line)</option>
          </select>
          <select class="form-select form-select-sm" id="wq-time-filter" style="width:130px" onchange="wqRenderTable()" title="Filter by required delivery time-of-day">
            <option value="">Any Time</option>
            <option value="morning">Morning</option>
            <option value="afternoon">Afternoon</option>
            <option value="__none__">(any time)</option>
          </select>
          <span class="text-muted ms-2">Needed:</span>
          <input type="date" class="form-control form-control-sm" id="wq-date-from" style="width:140px" onchange="wqRenderTable()" title="Needed-by from">
          <span class="text-muted">to</span>
          <input type="date" class="form-control form-control-sm" id="wq-date-to" style="width:140px" onchange="wqRenderTable()" title="Needed-by to">
          <select class="form-select form-select-sm" id="wq-when-filter" style="width:140px" onchange="wqRenderTable()">
            <option value="">Quick: Any</option>
            <option value="overdue">Overdue / Today</option>
            <option value="7d">≤ 7 days</option>
            <option value="30d">≤ 30 days</option>
          </select>
          <select class="form-select form-select-sm" id="wq-sort" style="width:200px" onchange="wqRenderTable()">
            <option value="prio_then_needed">Sort: Priority → Needed-by</option>
            <option value="needed_then_prio">Sort: Needed-by → Priority</option>
            <option value="newest">Sort: Newest first</option>
            <option value="oldest">Sort: Oldest first</option>
          </select>
          <button class="btn btn-sm btn-outline-secondary ms-auto" onclick="wqClearFilters()" title="Clear all filters"><i class="bi bi-x-circle me-1"></i>Clear</button>
        </div>`;
      host.parentNode.insertBefore(bar, host);
    }
  }
  // Apply filters
  const prio = document.getElementById('wq-prio-filter')?.value || '';
  const lineF = document.getElementById('wq-line-filter')?.value || '';
  const timeF = document.getElementById('wq-time-filter')?.value || '';
  const dateFrom = document.getElementById('wq-date-from')?.value || '';
  const dateTo   = document.getElementById('wq-date-to')?.value || '';
  const when = document.getElementById('wq-when-filter')?.value || '';
  const sort = document.getElementById('wq-sort')?.value || 'prio_then_needed';
  const today = new Date().toISOString().slice(0,10);
  const in7   = new Date(Date.now()+7*86400000).toISOString().slice(0,10);
  const in30  = new Date(Date.now()+30*86400000).toISOString().slice(0,10);
  let rows = reqs.filter(r => {
    if(prio && String(r.priority||2) !== String(prio)) return false;
    if(lineF){
      const l = (r.line_id||'').toUpperCase();
      if(lineF === '__none__'){ if(l) return false; }
      else if(l !== lineF) return false;
    }
    if(timeF){
      const t = (r.needed_time||'').toLowerCase();
      if(timeF === '__none__'){ if(t) return false; }
      else if(t !== timeF) return false;
    }
    const n = (r.needed_by||'').slice(0,10);
    if(dateFrom && (!n || n < dateFrom)) return false;
    if(dateTo   && (!n || n > dateTo))   return false;
    if(when){
      if(!n && when) return false;
      if(when==='overdue' && !(n<=today)) return false;
      if(when==='7d'     && !(n<=in7))   return false;
      if(when==='30d'    && !(n<=in30))  return false;
    }
    return true;
  });
  rows.sort((a,b)=>{
    const pa=Number(a.priority||2), pb=Number(b.priority||2);
    const na=(a.needed_by||'9999-12-31'), nb=(b.needed_by||'9999-12-31');
    if(sort==='needed_then_prio'){ if(na!==nb) return na<nb?-1:1; return pa-pb; }
    if(sort==='newest'){ return (b.created_at||'').localeCompare(a.created_at||''); }
    if(sort==='oldest'){ return (a.created_at||'').localeCompare(b.created_at||''); }
    // default prio_then_needed
    if(pa!==pb) return pa-pb;
    return na<nb?-1:(na>nb?1:0);
  });
  if(!rows.length){
    document.getElementById('wq-cards').innerHTML='<div class="text-center text-muted py-5"><i class="bi bi-inbox" style="font-size:2rem"></i><p class="mt-2">No consumable requests match the filter.</p></div>';
    return;
  }
  const prioBadge = p => {
    const m={1:['danger','P1 Urgent'],2:['warning text-dark','P2'],3:['success','P3']};
    const x=m[Number(p)||2]; return `<span class="badge bg-${x[0]}" title="Priority ${p}">${x[1]}</span>`;
  };
  const timeBadge = t => {
    if(t === 'morning')   return '<span class="badge bg-info text-white" title="Morning delivery window"><i class="bi bi-sunrise me-1"></i>AM</span>';
    if(t === 'afternoon') return '<span class="badge bg-warning text-dark" title="Afternoon delivery window"><i class="bi bi-sunset me-1"></i>PM</span>';
    return '<span class="text-muted small">—</span>';
  };
  document.getElementById('wq-cards').innerHTML = `<div class="card"><div class="table-responsive">
    <table class="table table-sm table-hover mb-0" style="font-size:.78rem">
      <thead class="table-light">
        <tr>
          <th style="width:50px">Prio</th>
          <th style="width:110px">Request</th>
          <th>Material</th>
          <th style="width:90px">Line</th>
          <th style="width:100px">Department</th>
          <th class="text-end" style="width:120px">Qty (filled / req)</th>
          <th style="width:110px">Needed By</th>
          <th style="width:80px">Time</th>
          <th class="text-end" style="width:110px" title="Live warehouse stock for this material (matches Raw Materials page)">Stock in WH</th>
          <th style="width:90px">Status</th>
          <th class="text-end" style="width:110px">Action</th>
        </tr>
      </thead>
      <tbody>
      ${rows.map(r=>{
        const remaining=r.qty_requested-r.qty_fulfilled;
        const pct=Math.round((r.qty_fulfilled/r.qty_requested)*100);
        const nb = (r.needed_by||'').slice(0,10);
        const nbCls = nb && nb<=today ? 'text-danger fw-bold'
                    : nb && nb<=in7   ? 'text-warning fw-semibold' : 'small';
        return `<tr>
          <td>${prioBadge(r.priority||2)}</td>
          <td><code class="small text-primary">${r.request_id}</code>
            <div class="small text-muted">${(r.created_at||'').slice(0,10)}</div></td>
          <td>
            <div class="fw-semibold text-truncate" style="max-width:280px" title="${(r.material_name||'').replace(/"/g,'&quot;')}">${r.material_name||'—'}</div>
            <div class="small text-muted">By ${r.requester_name||'—'}</div>
            ${r.notes?`<div class="small text-muted fst-italic text-truncate" style="max-width:280px" title="${r.notes.replace(/"/g,'&quot;')}">${r.notes}</div>`:''}
          </td>
          <td class="small">${r.line_id?'<span class="badge bg-secondary">'+r.line_id+'</span>':'<span class="text-muted">—</span>'}</td>
          <td class="small">${r.department}</td>
          <td class="text-end small">
            <b>${r.qty_fulfilled}</b> / ${r.qty_requested} ${r.unit||''}
            <div class="progress mt-1" style="height:5px"><div class="progress-bar bg-success" style="width:${pct}%"></div></div>
          </td>
          <td class="${nbCls}">${nb||'<span class="text-muted">—</span>'}</td>
          <td>${timeBadge(r.needed_time)}</td>
          <td class="text-end small ${(r.current_stock||0) < remaining ? 'text-danger fw-bold' : ''}" title="Live warehouse stock">
            ${_whFmtQty(r.current_stock)} <span class="text-muted">${r.unit||''}</span>
            ${(r.current_stock||0) < remaining ? '<div class="small text-danger">short by '+_whFmtQty(remaining-(r.current_stock||0))+'</div>' : ''}
          </td>
          <td><span class="badge bg-${statusColor[r.status]||'secondary'}">${r.status}</span></td>
          <td class="text-end">
            ${['PENDING','PARTIAL'].includes(r.status)?
              `<button class="btn btn-success btn-sm py-0 px-2" style="font-size:.72rem"
                onclick="wqOpenFulfill('${r.request_id}','${(r.material_name||'').replace(/'/g,'&apos;')}','${r.unit||''}',${r.unit_cost||0},${remaining},${r.current_stock||0})">
                <i class="bi bi-box-seam me-1"></i>Fulfill
              </button>`:''}
          </td>
        </tr>`;
      }).join('')}
      </tbody>
    </table>
  </div></div>`;
}

function wqClearFilters(){
  ['wq-prio-filter','wq-line-filter','wq-time-filter','wq-date-from','wq-date-to','wq-when-filter'].forEach(id=>{
    const el = document.getElementById(id); if(el) el.value = '';
  });
  wqRenderTable();
}

async function wqLoadRm(){
  const url=`/api/fc/transfer-requests?direction=inbound${_wqRmTab?'&status='+_wqRmTab:''}`;
  const [reqs, mats] = await Promise.all([
    api(url).catch(()=>[]),
    api('/api/materials?include_formulas=true').catch(()=>[]),
  ]);
  if(!reqs) return;
  // Back-fill wh_stock from the live materials snapshot — same approach
  // as wqLoad(), ensures the column matches what Raw Materials shows.
  const matStock = {};
  if(Array.isArray(mats)) mats.forEach(m => { matStock[m.id] = m.current_stock; });
  reqs.forEach(r => {
    const live = matStock[r.material_id];
    if(live != null) r.wh_stock = live;
  });
  const totPending=reqs.filter(r=>r.status==='PENDING').length;
  const totPartial=reqs.filter(r=>r.status==='PARTIAL').length;
  document.getElementById('wq-rm-cnt-pending').textContent=totPending;
  document.getElementById('wq-rm-cnt-partial').textContent=totPartial;
  const statusColor={PENDING:'warning',PARTIAL:'primary',FULFILLED:'success',CANCELLED:'secondary'};
  const el=document.getElementById('wq-rm-cards');
  if(!reqs.length){
    el.innerHTML='<div class="text-center text-muted py-5"><i class="bi bi-inbox" style="font-size:2rem"></i><p class="mt-2">No FC raw material transfer requests.</p></div>';
    return;
  }
  el.innerHTML = `<div class="card border-info"><div class="table-responsive">
    <table class="table table-sm table-hover mb-0" style="font-size:.78rem">
      <thead class="table-light">
        <tr>
          <th style="width:110px">Request</th>
          <th>Material</th>
          <th style="width:80px">Type</th>
          <th class="text-end" style="width:120px">Qty (filled / req)</th>
          <th style="width:140px">Progress</th>
          <th class="text-end" style="width:100px">WH Stock</th>
          <th class="text-end" style="width:90px">FC Stock</th>
          <th style="width:90px">Status</th>
          <th class="text-end" style="width:130px">Action</th>
        </tr>
      </thead>
      <tbody>
      ${reqs.map(r=>{
        const remaining=r.qty_requested-r.qty_fulfilled;
        const pct=Math.round((r.qty_fulfilled/r.qty_requested)*100);
        const typeBadge=r.material_type==='veneer_sheet'
          ?'<span class="badge bg-primary" style="font-size:.62rem">Veneer</span>'
          :'<span class="badge bg-secondary" style="font-size:.62rem">Board</span>';
        return `<tr>
          <td><code class="small text-info">${r.request_id}</code>
            <div class="small text-muted">${(r.created_at||'').slice(0,10)}</div></td>
          <td>
            <div class="fw-semibold text-truncate" style="max-width:260px" title="${(r.material_name||'').replace(/"/g,'&quot;')}">${r.material_name||'—'}</div>
            <div class="small text-muted">By FC: ${r.requester_name||'—'}</div>
            ${r.notes?`<div class="small text-muted fst-italic text-truncate" style="max-width:260px" title="${r.notes.replace(/"/g,'&quot;')}">${r.notes}</div>`:''}
          </td>
          <td>${typeBadge}</td>
          <td class="text-end small"><b>${r.qty_fulfilled}</b> / ${r.qty_requested} ${r.unit||''}</td>
          <td>
            <div class="d-flex align-items-center gap-1">
              <div class="progress flex-fill" style="height:6px"><div class="progress-bar bg-info" style="width:${pct}%"></div></div>
              <span class="small text-muted" style="min-width:32px;text-align:right">${pct}%</span>
            </div>
          </td>
          <td class="text-end small ${r.wh_stock<remaining?'text-danger fw-bold':''}">${fmt(r.wh_stock)}</td>
          <td class="text-end small text-info">${fmt(r.fc_stock)}</td>
          <td><span class="badge bg-${statusColor[r.status]||'secondary'}">${r.status}</span></td>
          <td class="text-end">
            ${['PENDING','PARTIAL'].includes(r.status)?
              `<button class="btn btn-info btn-sm text-white py-0 px-2" style="font-size:.72rem"
                onclick="wqOpenFcFulfill('${r.request_id}','${(r.material_name||'').replace(/'/g,'&apos;')}','${r.unit||''}',${remaining},${r.wh_stock||0})">
                <i class="bi bi-arrow-down-up me-1"></i>Issue
              </button>`:''}
          </td>
        </tr>`;
      }).join('')}
      </tbody>
    </table>
  </div></div>`;
}

function wqOpenFcFulfill(rid, name, unit, remaining, whStock){
  _wqFcFulfillId=rid; _wqFcFulfillMat={name,unit,remaining,whStock};
  document.getElementById('fcfulfill-info').innerHTML=`
    <div class="mb-1"><b>${name}</b></div>
    <div class="small text-muted">Outstanding: <b>${remaining} ${unit}</b></div>
    <div class="small text-muted">WH stock available: <b>${whStock} ${unit}</b></div>`;
  document.getElementById('fcfulfill-unit').textContent=unit||'unit';
  document.getElementById('fcfulfill-qty').value=Math.min(remaining,whStock)||'';
  document.getElementById('fcfulfill-stock-note').textContent=
    whStock<remaining?`Warning: only ${whStock} ${unit} in WH stock.`:'WH stock sufficient.';
  bootstrap.Modal.getOrCreateInstance(document.getElementById('fcFulfillModal')).show();
}

async function wqDoFcFulfill(){
  if(!_wqFcFulfillId) return;
  const qty=parseFloat(document.getElementById('fcfulfill-qty').value)||0;
  if(qty<=0){toast('Enter a quantity to transfer','warning');return;}
  try{
    await api(`/api/fc/transfer-requests/${_wqFcFulfillId}/fulfill`,'PATCH',{qty_fulfilled:qty});
    bootstrap.Modal.getInstance(document.getElementById('fcFulfillModal')).hide();
    toast(`Transferred ${qty} ${_wqFcFulfillMat?.unit||''} to FC station`,'success');
    wqLoad(); wqLoadRm();
  }catch(e){toast(e.message,'danger');}
}

// ── FC Returns (FC→WH pickup) — WH side ─────────────────────────

function wqRetSetTab(tab){
  _wqRetTab = tab;
  ['PENDING',''].forEach(t=>{
    const key = t||'all';
    const btn = document.getElementById(`wq-ret-tab-${key.toLowerCase()}`);
    if(btn){
      btn.classList.toggle('active', tab===t);
      btn.classList.toggle('btn-warning', tab===t && t==='PENDING');
      btn.classList.toggle('btn-outline-secondary', tab!==t);
    }
  });
  wqLoadReturns();
}

let _wqRetFulfillId=null, _wqRetFulfillMat=null;

async function wqLoadReturns(){
  const url = `/api/fc/transfer-requests?direction=outbound${_wqRetTab?'&status='+_wqRetTab:''}`;
  const reqs = await api(url).catch(()=>[]);
  if(!reqs) return;
  const totPending = reqs.filter(r=>r.status==='PENDING').length;
  document.getElementById('wq-ret-cnt-pending').textContent = totPending;
  document.getElementById('wq-returns-cnt').textContent = totPending;
  const el = document.getElementById('wq-ret-cards');
  if(!reqs.length){
    el.innerHTML='<div class="text-center text-muted py-5"><i class="bi bi-inbox" style="font-size:2rem"></i><p class="mt-2">No FC return requests in this view.</p></div>';
    return;
  }
  const statusColor={PENDING:'warning',PARTIAL:'primary',FULFILLED:'success',CANCELLED:'secondary'};
  el.innerHTML = `<div class="card border-danger"><div class="table-responsive">
    <table class="table table-sm table-hover mb-0" style="font-size:.78rem">
      <thead class="table-light">
        <tr>
          <th style="width:110px">Request</th>
          <th>Material</th>
          <th style="width:80px">Type</th>
          <th class="text-end" style="width:110px">Return Qty</th>
          <th class="text-end" style="width:100px">FC Stock</th>
          <th style="width:90px">Status</th>
          <th class="text-end" style="width:150px">Action</th>
        </tr>
      </thead>
      <tbody>
      ${reqs.map(r=>{
        const typeBadge = r.material_type==='veneer_sheet'
          ?'<span class="badge bg-primary" style="font-size:.62rem">Veneer</span>'
          :'<span class="badge bg-secondary" style="font-size:.62rem">Board</span>';
        return `<tr>
          <td><code class="small text-danger">${r.request_id}</code>
            <div class="small text-muted">${(r.created_at||'').slice(0,10)}</div></td>
          <td>
            <div class="fw-semibold text-truncate" style="max-width:260px" title="${(r.material_name||'').replace(/"/g,'&quot;')}">${r.material_name||'—'}</div>
            <div class="small text-muted">By FC: ${r.requester_name||'—'}</div>
            ${r.notes?`<div class="small text-muted fst-italic text-truncate" style="max-width:260px" title="${r.notes.replace(/"/g,'&quot;')}">${r.notes}</div>`:''}
          </td>
          <td>${typeBadge}</td>
          <td class="text-end small fw-semibold">${fmt(r.qty_requested)} ${r.unit||''}</td>
          <td class="text-end small text-danger fw-semibold">${fmt(r.fc_stock)}</td>
          <td><span class="badge bg-${statusColor[r.status]||'secondary'}">${r.status}</span></td>
          <td class="text-end">
            ${['PENDING','PARTIAL'].includes(r.status)?
              `<button class="btn btn-danger btn-sm py-0 px-2" style="font-size:.72rem"
                onclick="wqOpenRetPickup('${r.request_id}','${(r.material_name||'').replace(/'/g,'&apos;')}','${r.unit||''}',${r.qty_requested},${r.fc_stock||0})">
                <i class="bi bi-check2-circle me-1"></i>Confirm Pickup
              </button>`:
              (r.status==='FULFILLED'?`<span class="small text-success">✓ ${(r.fulfilled_at||'').slice(0,10)}</span>`:'')}
          </td>
        </tr>`;
      }).join('')}
      </tbody>
    </table>
  </div></div>`;
}

function wqOpenRetPickup(rid, name, unit, qtyReq, fcStock){
  _wqRetFulfillId = rid;
  _wqRetFulfillMat = {name, unit, qtyReq, fcStock};
  document.getElementById('fcfulfill-info').innerHTML=`
    <div class="mb-1"><b>${name}</b></div>
    <div class="small text-muted">Return qty requested: <b>${qtyReq} ${unit}</b></div>
    <div class="small text-muted">FC stock available: <b>${fcStock} ${unit}</b></div>
    <div class="small text-warning mt-1"><i class="bi bi-exclamation-triangle me-1"></i>Confirm that you have physically collected this from FC station.</div>`;
  document.getElementById('fcfulfill-unit').textContent = unit||'unit';
  document.getElementById('fcfulfill-qty').value = Math.min(qtyReq, fcStock)||'';
  document.getElementById('fcfulfill-stock-note').textContent = '';
  // Swap modal title and button for return pickup context
  document.querySelector('#fcFulfillModal .modal-title').innerHTML =
    '<i class="bi bi-arrow-up-circle me-2 text-danger"></i>Confirm FC → WH Return Pickup';
  document.querySelector('#fcFulfillModal .btn-success').innerHTML =
    '<i class="bi bi-check-lg me-1"></i>Confirm Pickup & Move to WH';
  document.querySelector('#fcFulfillModal .text-success').textContent = 'Stock will move: FC Station → Main WH';
  document.querySelector('#fcFulfillModal .btn-success').onclick = wqDoRetPickup;
  bootstrap.Modal.getOrCreateInstance(document.getElementById('fcFulfillModal')).show();
}

async function wqDoRetPickup(){
  if(!_wqRetFulfillId) return;
  const qty = parseFloat(document.getElementById('fcfulfill-qty').value)||0;
  if(qty<=0){toast('Enter quantity collected','warning');return;}
  try{
    await api(`/api/fc/transfer-requests/${_wqRetFulfillId}/fulfill`,'PATCH',{qty_fulfilled:qty});
    bootstrap.Modal.getInstance(document.getElementById('fcFulfillModal')).hide();
    // Restore modal defaults for next inbound use
    document.querySelector('#fcFulfillModal .modal-title').innerHTML =
      '<i class="bi bi-arrow-down-up me-2"></i>Issue to FC Station';
    document.querySelector('#fcFulfillModal .btn-success').innerHTML =
      '<i class="bi bi-check-lg me-1"></i>Transfer to FC';
    document.querySelector('#fcFulfillModal .text-success').textContent = 'Stock will move: WH → FC Station';
    document.querySelector('#fcFulfillModal .btn-success').onclick = wqDoFcFulfill;
    toast(`Return confirmed — ${qty} ${_wqRetFulfillMat?.unit||''} moved back to WH`,'success');
    wqLoad(); wqLoadReturns();
    _wqRetFulfillId = null; _wqRetFulfillMat = null;
  }catch(e){toast(e.message,'danger');}
}

// ── FC Return Modal (FC side — create return request) ─────────────

function _fcrtnBuildOpts(mats){
  return '<option value="">— Select veneer or board —</option>'
    + mats.map(m=>`<option value="${m.id}" data-unit="${m.unit||'pcs'}" data-fc="${m.fc_stock||0}">`+
        `${m.name}${m.code?' ('+m.code+')':''}${m.grade?' ['+m.grade+']':''} — FC: ${fmt(m.fc_stock)} ${m.unit||'pcs'}`+
      `</option>`).join('');
}
function fcrtnFilterMats(q){
  if(!_fcStockMats.length) return;
  const term = (q||'').trim().toLowerCase();
  const eligible = _fcStockMats.filter(m=>m.fc_stock>0);
  const mats = term
    ? eligible.filter(m=>(m.code||'').toLowerCase().includes(term)||(m.name||'').toLowerCase().includes(term))
    : eligible;
  document.getElementById('fcrtn-material-id').innerHTML = _fcrtnBuildOpts(mats);
  fcrtnOnMatSelect();
}
async function fcOpenReturnModal(preselectedId=null){
  // Populate material dropdown with FC stock items that have fc_stock > 0
  if(!_fcStockMats.length) _fcStockMats = await api('/api/fc/stock').catch(()=>[]);
  const eligible = _fcStockMats.filter(m=>m.fc_stock>0);
  document.getElementById('fcrtn-mat-search').value = '';
  const sel = document.getElementById('fcrtn-material-id');
  sel.innerHTML = _fcrtnBuildOpts(eligible);
  if(preselectedId){
    sel.value = String(preselectedId);
  }
  document.getElementById('fcrtn-qty').value='';
  document.getElementById('fcrtn-notes').value='';
  document.getElementById('fcrtn-fc-stock-note').textContent='';
  document.getElementById('fcrtn-unit-label').textContent='pcs';
  fcrtnOnMatSelect();
  bootstrap.Modal.getOrCreateInstance(document.getElementById('fcReturnModal')).show();
}

function fcrtnOnMatSelect(){
  const sel = document.getElementById('fcrtn-material-id');
  const opt = sel.options[sel.selectedIndex];
  if(!opt?.value){
    document.getElementById('fcrtn-fc-stock-note').textContent='';
    document.getElementById('fcrtn-unit-label').textContent='pcs';
    return;
  }
  const unit = opt.dataset.unit||'pcs';
  const fc   = parseFloat(opt.dataset.fc||0);
  document.getElementById('fcrtn-unit-label').textContent = unit;
  document.getElementById('fcrtn-fc-stock-note').textContent = `FC stock: ${fmt(fc)} ${unit}`;
  // Auto-fill qty with full FC stock as convenience default
  if(!document.getElementById('fcrtn-qty').value){
    document.getElementById('fcrtn-qty').value = fc;
  }
}

async function fcrtnSubmit(){
  const matId = parseInt(document.getElementById('fcrtn-material-id').value)||0;
  const qty   = parseFloat(document.getElementById('fcrtn-qty').value)||0;
  const notes = document.getElementById('fcrtn-notes').value;
  if(!matId||qty<=0){ toast('Select a material and enter quantity','warning'); return; }
  try{
    await api('/api/fc/return-requests','POST',{
      material_id:matId, qty_requested:qty, notes:notes||''
    });
    bootstrap.Modal.getInstance(document.getElementById('fcReturnModal')).hide();
    toast('Return request submitted — WH will pick up from FC station','success');
    fcLoadStock();
  }catch(e){ toast(e.message,'danger'); }
}

// ── FC Inventory Data Tools ───────────────────────────────────

async function dtFcUpload(input){
  const file = input.files[0]; if(!file) return;
  const mode = document.querySelector('input[name="dt-mode-fc-stock"]:checked')?.value || 'add';
  await _dtFcDoUpload(file, mode);
  input.value = '';
}

function dtFcUploadDrop(event){
  const file = event.dataTransfer?.files?.[0];
  const el = document.getElementById('dt-result-fc-stock');
  if(!file || !file.name.endsWith('.csv')){
    el.innerHTML = '<div class="alert alert-warning py-2 small">Please drop a .csv file</div>';
    return;
  }
  const mode = document.querySelector('input[name="dt-mode-fc-stock"]:checked')?.value || 'add';
  _dtFcDoUpload(file, mode);
}

async function _dtFcDoUpload(file, mode){
  const el = document.getElementById('dt-result-fc-stock');
  el.innerHTML = '<div class="d-flex align-items-center gap-2 text-muted small"><div class="spinner-border spinner-border-sm"></div>Uploading '+file.name+'…</div>';
  try{
    const fd = new FormData(); fd.append('file', file);
    const token = localStorage.getItem('erp_token')||'';
    const r = await fetch(`/api/upload/fc-stock?mode=${mode}`, {
      method:'POST', body:fd, headers:{'X-Auth-Token':token}
    });
    const data = await r.json();
    if(!r.ok) throw new Error(data.detail || 'Upload failed');
    const modeLabel = mode==='adjust' ? 'adjusted' : 'set';
    let h = `<div class="alert alert-success py-2 small"><i class="bi bi-check-circle me-1"></i><strong>${data.processed}</strong> FC stock records ${modeLabel} successfully</div>`;
    if(data.errors?.length) h += `<div class="alert alert-warning py-2 small"><strong>${data.errors.length} row(s) skipped:</strong><br>${data.errors.slice(0,6).map(e=>'• '+e).join('<br>')}${data.errors.length>6?`<br>…and ${data.errors.length-6} more`:''}</div>`;
    el.innerHTML = h;
    fcLoadStock();  // refresh the FC stock grid
  }catch(e){
    el.innerHTML = `<div class="alert alert-danger py-2 small"><i class="bi bi-exclamation-triangle me-1"></i>${e.message}</div>`;
  }
}

function wqOpenFulfill(rid,name,unit,unitCost,remaining,stock){
  _wqFulfillId=rid;_wqFulfillMat={name,unit,unitCost,remaining,stock};
  document.getElementById('fulfill-info').innerHTML=`
    <div class="mb-1"><b>${name}</b></div>
    <div class="small text-muted">Outstanding: <b>${remaining} ${unit}</b></div>
    <div class="small text-muted">Warehouse stock: <b>${stock} ${unit}</b></div>`;
  document.getElementById('fulfill-unit').textContent=unit||'unit';
  document.getElementById('fulfill-qty').value=Math.min(remaining,stock)||'';
  document.getElementById('fulfill-stock-note').textContent=
    stock<remaining?`Warning: only ${stock} ${unit} in stock.`:'Stock sufficient.';
  document.getElementById('fulfill-cost-note').textContent='';
  document.getElementById('fulfill-qty').oninput=()=>{
    const q=parseFloat(document.getElementById('fulfill-qty').value)||0;
    document.getElementById('fulfill-cost-note').textContent=
      q>0?`Cost to allocate: ฿${(q*unitCost).toFixed(2)}`:'';
  };
  bootstrap.Modal.getOrCreateInstance(document.getElementById('fulfillModal')).show();
}

async function wqDoFulfill(){
  if(!_wqFulfillId) return;
  const qty=parseFloat(document.getElementById('fulfill-qty').value)||0;
  if(qty<=0){toast('Enter a quantity to issue','warning');return;}
  try{
    await api(`/api/consumable-requests/${_wqFulfillId}/fulfill`,'PATCH',{qty_fulfilled:qty});
    bootstrap.Modal.getInstance(document.getElementById('fulfillModal')).hide();
    toast(`Issued ${qty} ${_wqFulfillMat?.unit||''} — cost allocated`,'success');
    wqLoad();
  }catch(e){toast(e.message,'danger');}
}



// ════════════════════════════════════════════════════════════
// FG Warehouse — stock, open POs, incoming batches
// ════════════════════════════════════════════════════════════
// ══════════════════════════════════════════════════════════════
// FG WAREHOUSE — stock, open POs, incoming batches
// ══════════════════════════════════════════════════════════════
let _fgwData = null, _fgwTab = 'stock';

async function loadFgWarehouse(){
  // Render shell loading state
  ['fgw-stock-tbody','fgw-incoming-tbody'].forEach(id=>{
    const el=document.getElementById(id); if(el) el.innerHTML='<tr><td colspan="9" class="text-muted text-center py-3"><span class="spinner-border spinner-border-sm me-2"></span>Loading…</td></tr>';
  });
  const posList=document.getElementById('fgw-pos-list');
  if(posList) posList.innerHTML='<div class="text-muted text-center py-3"><span class="spinner-border spinner-border-sm me-2"></span>Loading…</div>';
  try {
    _fgwData = await api('/api/fg-warehouse/dashboard');
  } catch(e){
    toast('Failed to load FG warehouse: '+e.message,'danger');
    return;
  }
  // KPIs
  const k = _fgwData.kpis || {};
  document.getElementById('fgw-kpi-skus').textContent = fmt(k.skus_in_stock);
  document.getElementById('fgw-kpi-pcs').textContent = fmt(k.total_pcs_in_stock);
  document.getElementById('fgw-kpi-pallets').textContent = fmt(k.total_pallets_in_stock);
  document.getElementById('fgw-kpi-pos').textContent = fmt(k.open_pos);
  document.getElementById('fgw-kpi-pending').textContent = fmt(k.pending_receipt_batches);
  document.getElementById('fgw-kpi-in-prod').textContent = fmt(k.in_production_batches);
  // Tab counts
  document.getElementById('fgw-stock-count').textContent = (_fgwData.stock_by_sku||[]).length;
  document.getElementById('fgw-pos-count').textContent = (_fgwData.open_pos||[]).length;
  document.getElementById('fgw-pending-count').textContent = (_fgwData.pending_receipt||[]).length;
  document.getElementById('fgw-production-count').textContent = (_fgwData.in_production||[]).length;
  // Auto-switch to Pending tab if there are batches awaiting confirmation
  if((_fgwData.pending_receipt||[]).length > 0 && _fgwTab !== 'pending'){
    fgwSwitchTab('pending');
  }
  // Render
  fgwRenderStock(); fgwRenderPos(); fgwRenderPending(); fgwRenderProduction();
}

function fgwSwitchTab(tab){
  _fgwTab = tab;
  document.querySelectorAll('#fgw-tabs .nav-link').forEach(b=>b.classList.toggle('active', b.dataset.fgwTab===tab));
  document.querySelectorAll('.fgw-pane').forEach(p=>p.classList.add('d-none'));
  document.getElementById('fgw-pane-'+tab).classList.remove('d-none');
}

// ── Tab 1: Stock by SKU ──────────────────────────────────
function fgwRenderStock(){
  if(!_fgwData) return;
  const q = (document.getElementById('fgw-stock-search')?.value || '').toLowerCase().trim();
  const rows = (_fgwData.stock_by_sku || []).filter(r =>
    !q || (r.sku_code||'').toLowerCase().includes(q) || (r.product_name||'').toLowerCase().includes(q)
  );
  const tbody = document.getElementById('fgw-stock-tbody');
  if(!rows.length){
    tbody.innerHTML = '<tr><td colspan="9" class="text-center text-muted py-4">No FG stock currently in warehouse. Batches arrive here from packing.</td></tr>';
    return;
  }
  tbody.innerHTML = rows.map(r => {
    const dims = (r.thickness_mm && r.width_mm && r.length_mm)
      ? `${r.thickness_mm}×${r.width_mm}×${r.length_mm}` : '—';
    const fgP   = Number(r.fg_pallets||0), wlP = Number(r.wlwh_pallets||0);
    const wlBadge = wlP>0 ? `<span class="badge bg-info-subtle text-info-emphasis">${fmt(wlP)} plt</span>` : '<span class="text-muted">—</span>';
    // Page is warehouse-scoped; backend require_role enforces the actual move.
    const moveBtn = `<button class="btn btn-xs btn-outline-primary" onclick="fgMoveOpen('${(r.sku_code||'').replace(/'/g,"\\'")}')" title="Move pallets between FG and WLWH"><i class="bi bi-arrow-left-right me-1"></i>Move</button>`;
    return `<tr>
      <td><code class="text-success fw-semibold">${r.sku_code||''}</code></td>
      <td class="small">${r.product_name||'—'}</td>
      <td class="text-center small text-muted">${dims}</td>
      <td class="text-end fw-bold text-success">${fmt(r.in_stock_pcs)} pcs</td>
      <td class="text-end">${fmt(r.in_stock_pallets)}</td>
      <td class="text-end small">${fgP>0?fmt(fgP)+' plt':'<span class="text-muted">—</span>'}</td>
      <td class="text-end small">${wlBadge}</td>
      <td class="text-end small">${r.batch_count}</td>
      <td class="text-end">${moveBtn}</td>
    </tr>`;
  }).join('');
}

// ── FG <-> WLWH move dialog ──────────────────────────────────
let _fgMoveSku = null, _fgMoveBatches = [];
async function fgMoveOpen(sku){
  _fgMoveSku = sku;
  document.getElementById('fgmove-sku').textContent = sku;
  document.getElementById('fgmove-dest').value = 'WLWH';
  const body = document.getElementById('fgmove-tbody');
  body.innerHTML = '<tr><td colspan="6" class="text-center text-muted py-3"><span class="spinner-border spinner-border-sm me-2"></span>Loading batches…</td></tr>';
  new bootstrap.Modal(document.getElementById('fgMoveModal')).show();
  try {
    _fgMoveBatches = await api('/api/fg-warehouse/batches?sku='+encodeURIComponent(sku));
  } catch(e){ toast('Failed to load batches: '+e.message,'danger'); return; }
  fgMoveRenderBatches();
}
function fgMoveRenderBatches(){
  const dest = document.getElementById('fgmove-dest').value;
  // Only batches NOT already at the destination can move there.
  const rows = (_fgMoveBatches||[]).filter(b => (b.fg_location||'FG') !== dest);
  const body = document.getElementById('fgmove-tbody');
  if(!rows.length){
    body.innerHTML = `<tr><td colspan="6" class="text-center text-muted py-3">No batches available to move to ${dest}.</td></tr>`;
    return;
  }
  body.innerHTML = rows.map(b => `<tr>
      <td><input type="checkbox" class="form-check-input fgmove-chk" value="${b.id}"></td>
      <td><code class="small">${b.batch_number||''}</code></td>
      <td class="text-center"><span class="badge ${ (b.fg_location||'FG')==='WLWH' ? 'bg-info-subtle text-info-emphasis' : 'bg-secondary-subtle text-secondary-emphasis'}">${b.fg_location||'FG'}</span></td>
      <td class="text-end">${fmt(b.pallets)}</td>
      <td class="text-end">${fmt(b.pcs)} pcs</td>
      <td class="small text-muted">${(b.created_at||'').slice(0,10)}</td>
    </tr>`).join('');
}
function fgMoveToggleAll(cb){ document.querySelectorAll('.fgmove-chk').forEach(c=>c.checked=cb.checked); }
async function fgMoveSubmit(){
  const dest = document.getElementById('fgmove-dest').value;
  const ids = Array.from(document.querySelectorAll('.fgmove-chk:checked')).map(c=>parseInt(c.value));
  if(!ids.length){ toast('Select at least one batch to move','warning'); return; }
  const notes = (document.getElementById('fgmove-notes').value||'').trim();
  const btn = document.getElementById('fgmove-submit'); btn.disabled = true;
  try {
    const r = await api('/api/fg-warehouse/move-location', {method:'POST',
      body: JSON.stringify({batch_ids: ids, to_location: dest, notes})});
    toast(`Moved ${r.count} batch${r.count===1?'':'es'} to ${dest}`,'success');
    bootstrap.Modal.getInstance(document.getElementById('fgMoveModal')).hide();
    loadFgWarehouse();
  } catch(e){ toast('Move failed: '+e.message,'danger'); }
  finally { btn.disabled = false; }
}

// ── Tab 2: Open POs ──────────────────────────────────────
// Track which POs are expanded so re-renders keep their open state
let _fgwPosExpanded = new Set();

function fgwTogglePo(poKey){
  if(_fgwPosExpanded.has(poKey)) _fgwPosExpanded.delete(poKey);
  else _fgwPosExpanded.add(poKey);
  fgwRenderPos();
}
function fgwPosExpandAll(){
  (_fgwData?.open_pos||[]).forEach((p,i)=> _fgwPosExpanded.add(p.id ? `id:${p.id}` : `k:${i}`));
  fgwRenderPos();
}
function fgwPosCollapseAll(){
  _fgwPosExpanded.clear();
  fgwRenderPos();
}

function fgwRenderPos(){
  if(!_fgwData) return;
  const q = (document.getElementById('fgw-po-search')?.value || '').toLowerCase().trim();
  const pos = (_fgwData.open_pos || []).filter(p =>
    !q || (p.po_number||'').toLowerCase().includes(q) || (p.customer||'').toLowerCase().includes(q)
  );
  const el = document.getElementById('fgw-pos-list');
  if(!pos.length){
    el.innerHTML = '<div class="text-center text-muted py-4">No open POs.</div>';
    return;
  }
  const toolbar = `
    <div class="d-flex justify-content-between align-items-center px-3 py-2 border-bottom bg-light small">
      <span class="text-muted">${pos.length} open PO${pos.length===1?'':'s'} — click a row to expand line details</span>
      <div class="d-flex gap-1">
        <button class="btn btn-xs btn-outline-secondary" onclick="fgwPosExpandAll()"><i class="bi bi-arrows-expand me-1"></i>Expand All</button>
        <button class="btn btn-xs btn-outline-secondary" onclick="fgwPosCollapseAll()"><i class="bi bi-arrows-collapse me-1"></i>Collapse All</button>
      </div>
    </div>`;
  el.innerHTML = toolbar + pos.map((po,i) => {
    const poKey = po.id ? `id:${po.id}` : `k:${i}`;
    const expanded = _fgwPosExpanded.has(poKey);
    const pct = po.fulfillment_pct || 0;
    const pctColor = pct >= 100 ? 'success' : pct >= 50 ? 'warning' : 'danger';
    const lineCount = (po.lines||[]).length;
    const readyLines = (po.lines||[]).filter(l => (l.fulfillment_pct||0) >= 100).length;
    const linesHtml = expanded ? (po.lines || []).map(l => {
      const lpct = l.fulfillment_pct || 0;
      const lc = lpct >= 100 ? 'success' : lpct >= 50 ? 'warning' : 'danger';
      const ready = lpct >= 100 ? '✓ ready' : `${(l.pcs_ordered - l.pcs_in_stock).toLocaleString()} pcs short`;
      return `<tr>
        <td class="small"><code>${l.sku||''}</code></td>
        <td class="small text-truncate" style="max-width:280px" title="${(l.product_name||'').replace(/"/g,'&quot;')}">${l.product_name||'—'}</td>
        <td class="text-end small">${l.production_line||''}</td>
        <td class="text-end small">${fmt(l.pallets_ordered)}</td>
        <td class="text-end small">${fmt(l.pcs_ordered)}</td>
        <td class="text-end small fw-semibold ${lpct>=100?'text-success':'text-muted'}">${fmt(l.pcs_in_stock)}</td>
        <td>
          <div class="d-flex align-items-center gap-2" style="min-width:160px">
            <div class="progress flex-fill" style="height:6px"><div class="progress-bar bg-${lc}" style="width:${Math.min(lpct,100)}%"></div></div>
            <span class="small text-${lc} fw-semibold" style="min-width:42px;text-align:right">${lpct}%</span>
          </div>
        </td>
        <td class="small text-muted">${ready}</td>
      </tr>`;
    }).join('') : '';
    return `<div class="border-bottom">
      <div class="d-flex justify-content-between align-items-center p-3 flex-wrap gap-2 fgw-po-header"
           style="cursor:pointer;user-select:none" onclick="fgwTogglePo('${poKey}')">
        <div class="d-flex align-items-center gap-2">
          <i class="bi bi-${expanded?'chevron-down':'chevron-right'} text-muted"></i>
          <code class="text-warning fw-bold">${po.po_number||'PO #'+po.id}</code>
          ${po.customer?`<span class="ms-1 fw-semibold">${po.customer}</span>`:''}
          ${po.delivery_date?`<span class="badge bg-light text-dark border ms-1 small">Delivery: ${po.delivery_date}</span>`:''}
          <span class="badge bg-light text-dark border small">${readyLines}/${lineCount} line${lineCount===1?'':'s'} ready</span>
        </div>
        <div class="d-flex align-items-center gap-2" style="min-width:280px">
          <div class="text-end small text-muted">
            <b class="text-${pctColor}">${fmt(po.total_pcs_in_stock)}</b> / ${fmt(po.total_pcs_ordered)} pcs
          </div>
          <div class="progress flex-fill" style="height:8px;min-width:140px">
            <div class="progress-bar bg-${pctColor}" style="width:${Math.min(pct,100)}%"></div>
          </div>
          <span class="badge bg-${pctColor}" style="min-width:50px">${pct}%</span>
        </div>
      </div>
      ${expanded ? (linesHtml ? `<div class="table-responsive px-3 pb-3"><table class="table table-sm mb-0" style="font-size:.78rem">
        <thead class="table-light"><tr>
          <th>SKU</th><th>Product</th><th class="text-end">Line</th>
          <th class="text-end">Pallets</th><th class="text-end">Pcs Ordered</th>
          <th class="text-end">In Stock</th><th>Fulfillment</th><th>Status</th>
        </tr></thead>
        <tbody>${linesHtml}</tbody>
      </table></div>` : '<div class="text-muted small text-center py-2">No lines on this PO.</div>') : ''}
    </div>`;
  }).join('');
}

// ── Tab: Pending Receipt (released from packing, awaiting WH confirmation) ──
function fgwRenderPending(){
  if(!_fgwData) return;
  const q = (document.getElementById('fgw-pending-search')?.value || '').toLowerCase().trim();
  const rows = (_fgwData.pending_receipt || []).filter(b => {
    if(q && !((b.batch_number||'').toLowerCase().includes(q) || (b.product_name||'').toLowerCase().includes(q) || (b.sku||'').toLowerCase().includes(q))) return false;
    return true;
  });
  const tbody = document.getElementById('fgw-pending-tbody');
  if(!rows.length){
    tbody.innerHTML = '<tr><td colspan="9" class="text-center text-muted py-4"><i class="bi bi-check-circle me-1 text-success"></i>No batches awaiting receipt. The receiving zone is clear.</td></tr>';
    return;
  }
  tbody.innerHTML = rows.map(b => {
    const pri = b.priority || 2;
    const released = b.released_at ? b.released_at.replace('T',' ').slice(0,16) : '—';
    return `<tr class="table-warning">
      <td><code class="small">${b.batch_number}</code></td>
      <td class="small">${b.product_name||'—'} <span class="text-muted ms-1">(${b.sku||''})</span></td>
      <td class="text-end fw-bold">${fmt(b.total_pcs)}</td>
      <td class="text-center small">${fmt(b.quantity)}</td>
      <td class="small">${b.production_line||''}</td>
      <td>${prioBadge(pri)}</td>
      <td class="small text-muted">${b.po_number?b.po_number+(b.customer?' · '+b.customer:''):'—'}</td>
      <td class="small text-muted">${released}</td>
      <td class="text-end">
        <button class="btn btn-xs btn-success py-0 px-2" style="font-size:.72rem"
          onclick="fgwReceive(${b.id},'${b.batch_number}')"
          title="Mark as received into warehouse stock">
          <i class="bi bi-check-circle me-1"></i>Confirm Receipt
        </button>
      </td>
    </tr>`;
  }).join('');
}

async function fgwReceive(batchId, batchNumber){
  if(!confirm(`Confirm receipt of batch ${batchNumber}?\n\nThis will move the batch from the receiving zone into warehouse stock.`)) return;
  try {
    await api(`/api/fg-warehouse/receive/${batchId}`, 'POST');
    toast(`Batch ${batchNumber} received into warehouse stock`, 'success');
    loadFgWarehouse();
  } catch(e){ toast('Failed to confirm receipt: '+e.message, 'danger'); }
}

async function fgwReceiveAllPending(){
  if(!_fgwData){ toast('Refresh the page first','warning'); return; }
  const eligible = _fgwData.pending_receipt || [];
  if(!eligible.length){
    toast('No batches awaiting receipt', 'info'); return;
  }
  const totalPcs = eligible.reduce((s,b)=>s+(b.total_pcs||0), 0);
  if(!confirm(`Confirm receipt of all ${eligible.length} batch${eligible.length>1?'es':''} in the receiving zone (${totalPcs.toLocaleString()} pcs total)?`)) return;
  let ok = 0, fail = 0;
  for(const b of eligible){
    try { await api(`/api/fg-warehouse/receive/${b.id}`, 'POST'); ok++; }
    catch(e){ fail++; console.error('Receive failed for', b.batch_number, e); }
  }
  toast(`Confirmed receipt: ${ok}/${eligible.length} batches${fail?' ('+fail+' failed)':''}`, fail?'warning':'success');
  loadFgWarehouse();
}

// ── Tab: In Production (read-only ETA preview) ──────────────
function fgwRenderProduction(){
  if(!_fgwData) return;
  const q = (document.getElementById('fgw-prod-search')?.value || '').toLowerCase().trim();
  const dept = document.getElementById('fgw-prod-dept')?.value || '';
  const rows = (_fgwData.in_production || []).filter(b => {
    if(dept && b.current_department !== dept) return false;
    if(q && !((b.batch_number||'').toLowerCase().includes(q) || (b.product_name||'').toLowerCase().includes(q) || (b.sku||'').toLowerCase().includes(q))) return false;
    return true;
  });
  const tbody = document.getElementById('fgw-prod-tbody');
  if(!rows.length){
    tbody.innerHTML = '<tr><td colspan="9" class="text-center text-muted py-4">No batches in production matching filters.</td></tr>';
    return;
  }
  // Stages remaining (count of depts between current and packing)
  const flowToPacking = ['fc','laminating','cold_press','repair','sanding','hot_press','grading','packing'];
  tbody.innerHTML = rows.map(b => {
    const idx = flowToPacking.indexOf(b.current_department);
    const remaining = idx >= 0 ? (flowToPacking.length - 1 - idx) : '?';
    const pri = b.priority || 2;
    return `<tr>
      <td><code class="small">${b.batch_number}</code></td>
      <td class="small">${b.product_name||'—'} <span class="text-muted ms-1">(${b.sku||''})</span></td>
      <td class="text-end fw-bold">${fmt(b.total_pcs)}</td>
      <td class="text-center small">${fmt(b.quantity)}</td>
      <td><span class="badge bg-info text-white" style="font-size:.7rem"><i class="bi ${DEPT_ICON[b.current_department]||'bi-circle'} me-1"></i>${DEPT_LABEL[b.current_department]||b.current_department}</span></td>
      <td class="small">${b.production_line||''}</td>
      <td>${prioBadge(pri)}</td>
      <td class="small text-muted">${b.po_number?b.po_number+(b.customer?' · '+b.customer:''):'—'}</td>
      <td class="small text-muted">${remaining} stage${remaining===1?'':'s'} → Packing</td>
    </tr>`;
  }).join('');
}

async function loadDeptPage(dept){
  const container=document.querySelector(`#page-dept-${dept} .dept-page`);
  if(!container) return;
  const label=container.dataset.label;
  try{
    const [batches,stats]=await Promise.all([
      api(`/api/batches?department=${dept}`).catch(()=>[]),
      api(`/api/dept/${dept}/stats`).catch(()=>null)
    ]);
    container.innerHTML=`
      <div class="d-flex justify-content-between align-items-center mb-3">
        <div><h4 class="mb-0"><i class="bi ${DICO[dept]} me-2"></i>${label}</h4>
        <small class="text-muted">${batches.length} active batch(es)</small></div>
        <button class="btn btn-sm btn-primary" onclick="openDeptAct('${dept}')" data-bs-toggle="modal" data-bs-target="#deptActModal">+ Record Activity</button>
      </div>
      ${renderDeptStats(dept,stats)}
      ${dept==='laminating'?`
      <div class="mb-3">
        <button class="btn btn-sm btn-outline-warning" onclick="openLamFcRequest()">
          <i class="bi bi-arrow-down-up me-1"></i>Request Veneer / Board from FC
        </button>
      </div>`:''}
      <div class="row g-3 mb-3">
      ${batches.length?(()=>{
        // Group batches by prod_order_id so we can detect mergeable siblings
        const sortedBatches=[...batches].sort((a,b)=>(a.priority||2)-(b.priority||2));
        const orderCounts={};
        sortedBatches.forEach(b=>{orderCounts[b.prod_order_id]=(orderCounts[b.prod_order_id]||0)+1;});
        return sortedBatches.map(b=>{
        const palletQty = b.pallet_qty||1;
        const pcs = b.total_pcs ?? ((b.quantity||0) * palletQty);
        const pri = b.priority||2;
        const borderColor = pri===1?'#ef4444':pri===3?'#16a34a':'#eab308';
        const hasSiblings = orderCounts[b.prod_order_id] > 1;
        return `
        <div class="col-md-4 col-lg-3">
          <div class="card h-100" style="border-left:4px solid ${borderColor};cursor:pointer"
               onclick="deptBatchDetail(${b.id},'${dept}')"
               oncontextmenu="event.preventDefault();deptBatchDetail(${b.id},'${dept}');return false;"
               title="Click for details · Right-click for details">
            <div class="card-body p-3">
              <div class="d-flex justify-content-between align-items-start mb-1">
                <span class="fw-bold small text-primary">${b.batch_number||'B#'+b.id}</span>
                ${prioBadge(pri)}
              </div>
              <div class="small fw-semibold text-truncate mb-1" title="${b.product_name||''}">${b.product_name||'—'}</div>
              <div class="d-flex align-items-baseline gap-2">
                <span class="fs-5 fw-bold text-primary">${fmt(pcs)}</span>
                <span class="small text-muted">pcs</span>
                <span class="badge bg-light text-dark border" style="font-size:.7rem">${fmt(b.quantity)} pallet${b.quantity!=1?'s':''}</span>
                ${b.pcs_actual!=null?'<span class="badge bg-warning text-dark" style="font-size:.6rem">SPLIT</span>':''}
              </div>
              ${b.parent_batch_id?`<div class="mt-1"><span class="badge bg-warning text-dark" style="font-size:.65rem"><i class="bi bi-scissors me-1"></i>Split from #${b.parent_batch_id}</span></div>`:''}
              ${hasSiblings?`<div class="mt-1"><span class="badge bg-info text-white" style="font-size:.65rem"><i class="bi bi-link-45deg me-1"></i>Has mergeable sibling${orderCounts[b.prod_order_id]>2?'s ('+(orderCounts[b.prod_order_id]-1)+')':''}</span></div>`:''}
              ${b.prod_order_number?`<div class="small text-muted mt-1 text-truncate">${b.prod_order_number}</div>`:''}
              ${b.created_at?`<div class="small text-muted mt-1">${timeAgo(b.created_at)}</div>`:''}
            </div>
            <div class="card-footer bg-transparent py-1 px-3 d-flex gap-1 flex-wrap" onclick="event.stopPropagation()">
              <button class="btn btn-xs btn-outline-primary py-0 px-2" style="font-size:.72rem" onclick="openMove(${b.id},'${dept}',${b.quantity})"><i class="bi bi-arrow-right-circle me-1"></i>Move</button>
              <button class="btn btn-xs btn-outline-warning py-0 px-2" style="font-size:.72rem" onclick="openSplit(${b.id},${b.quantity})"><i class="bi bi-scissors me-1"></i>Split</button>
              ${hasSiblings?`<button class="btn btn-xs btn-outline-info py-0 px-2" style="font-size:.72rem" onclick="openMergeBatch(${b.id})"><i class="bi bi-link-45deg me-1"></i>Merge</button>`:''}
              <button class="btn btn-xs btn-outline-danger py-0 px-2" style="font-size:.72rem" onclick="voidBatch(${b.id},'${b.batch_number||'B#'+b.id}','${dept}')"><i class="bi bi-trash me-1"></i>Void</button>
            </div>
          </div>
        </div>`;
      }).join('');})():'<div class="col-12"><p class="text-muted">No batches in this department.</p></div>'}
      </div>`;
  }catch(e){container.innerHTML=`<div class="alert alert-danger">${e.message}</div>`;}
}
// Dept Batch Detail offcanvas moved to /static/js/portal_planning.js



// ════════════════════════════════════════════════════════════
// Lots & Documents
// ════════════════════════════════════════════════════════════
// ══════════════════════════════════════════════════════════════
// LOTS & DOCUMENTS
// ══════════════════════════════════════════════════════════════
async function lotsPrimeMatSelect(){
  await prPrimeMaterialSelects();
  lotMatPicked();   // reflect the unit of the initially-selected material
  // Also populate PR dropdown in lot modal
  try{
    const prs = await api('/api/purchase-requests?status=APPROVED');
    const sel=document.getElementById('lot-new-pr');
    sel.innerHTML='<option value="">— none —</option>'+prs.map(p=>
      `<option value="${p.id}">${p.request_number} — ${p.material_name} (${p.qty_requested} ${p.uom||''})</option>`).join('');
  }catch{}
}
// When a material is picked in the lot modal, show its unit next to Qty and
// fill the (read-only) Unit field — so receivers know what unit the FIFO
// quantity is in without typing it.
function lotMatPicked(){
  const id = Number(document.getElementById('lot-new-material')?.value || 0);
  const pool = (typeof _prMaterials !== 'undefined' && _prMaterials) ? _prMaterials : [];
  const m = pool.find(x => x.id === id);
  const unit = m ? (m.unit || '') : '';
  const uomEl = document.getElementById('lot-new-uom'); if(uomEl) uomEl.value = unit;
  const hint  = document.getElementById('lot-qty-unit'); if(hint) hint.textContent = unit ? '('+unit+')' : '';
}
async function lotsLoad(){
  const matId=document.getElementById('lot-mat-filter').value;
  const url='/api/material-lots'+(matId?('?material_id='+matId):'');
  try{
    _allLots = await api(url);
    lotsRender(_allLots);
    // Also refresh the doc upload modal's lot dropdown when material picked
    const dml=document.getElementById('doc-mat'); if(dml){ dml.onchange=()=>docRefreshLotSelect(dml.value); }
    docsLoad();
  }catch(e){
    document.getElementById('lots-tbody').innerHTML=`<tr><td colspan="9" class="text-danger small p-3">${e.message||e}</td></tr>`;
  }
}
function lotsRender(rows){
  if(!Array.isArray(rows)) rows=[];
  const tb=document.getElementById('lots-tbody');
  if(!rows.length){tb.innerHTML='<tr><td colspan="9" class="text-center text-muted py-3">No lots</td></tr>';return;}
  tb.innerHTML=rows.map(l=>{
    const consumed = Number(l.received_qty||0) - Number(l.remaining_qty||0);
    const pct = l.received_qty>0 ? Math.round(consumed/l.received_qty*100) : 0;
    return `<tr>
      <td class="small fw-semibold">${l.lot_code}</td>
      <td><span class="badge bg-light text-dark me-1">${(l.material_type||'').toUpperCase()}</span>${l.material_name}</td>
      <td class="small">${l.supplier||'—'}${l.supplier_lot_ref?'<br><span class="text-muted">'+l.supplier_lot_ref+'</span>':''}</td>
      <td class="text-end">${_accFmtN(l.received_qty)}</td>
      <td class="text-end ${l.remaining_qty<=0?'text-muted':''}">${_accFmtN(l.remaining_qty)} <span class="small text-muted">(${pct}% used)</span></td>
      <td class="small text-muted">${l.uom||''}</td>
      <td class="small">${(l.received_at||'').slice(0,10)}</td>
      <td class="small">${l.expiry_date||'—'}</td>
      <td>${l.doc_count?`<span class="badge bg-danger"><i class="bi bi-file-earmark-pdf me-1"></i>${l.doc_count}</span>`:'<span class="text-muted small">—</span>'}</td>
    </tr>`;
  }).join('');
}
async function lotSubmit(){
  const body={
    material_id: Number(document.getElementById('lot-new-material').value),
    lot_code:    document.getElementById('lot-new-code').value.trim(),
    received_qty:Number(document.getElementById('lot-new-qty').value||0),
    supplier:    document.getElementById('lot-new-supplier').value,
    supplier_lot_ref: document.getElementById('lot-new-supref').value,
    uom:         document.getElementById('lot-new-uom').value,
    unit_cost:   Number(document.getElementById('lot-new-cost').value||0),
    expiry_date: document.getElementById('lot-new-expiry').value||null,
    purchase_request_id: Number(document.getElementById('lot-new-pr').value)||null,
    notes:       document.getElementById('lot-new-notes').value,
  };
  if(!body.material_id||!body.lot_code||body.received_qty<=0){ alert('Material, lot code and positive quantity are required.'); return; }
  try{
    await api('/api/material-lots', 'POST', body);
    bootstrap.Modal.getInstance(document.getElementById('newLotModal'))?.hide();
    ['lot-new-code','lot-new-supplier','lot-new-supref','lot-new-qty','lot-new-uom','lot-new-cost','lot-new-expiry','lot-new-notes'].forEach(id=>document.getElementById(id).value='');
    lotsLoad();
  }catch(e){ alert('Save lot failed: '+(e.message||e)); }
}
async function docsLoad(){
  try{
    _allDocs = await api('/api/material-documents');
    const tb=document.getElementById('docs-tbody');
    if(!_allDocs.length){tb.innerHTML='<tr><td colspan="6" class="text-center text-muted py-3">No documents</td></tr>';return;}
    tb.innerHTML=_allDocs.map(d=>`<tr>
      <td><span class="badge bg-danger">${d.doc_type}</span></td>
      <td class="small">${d.material_name}</td>
      <td class="small">${d.lot_code||'—'}</td>
      <td class="small"><a href="/api/material-documents/${d.id}/download" target="_blank">${d.filename}</a></td>
      <td class="small text-muted">${(d.uploaded_at||'').slice(0,16).replace('T',' ')}</td>
      <td class="text-end"><button class="btn btn-xs btn-outline-danger" onclick="docDelete(${d.id})"><i class="bi bi-trash"></i></button></td>
    </tr>`).join('');
  }catch(e){
    document.getElementById('docs-tbody').innerHTML=`<tr><td colspan="6" class="text-danger small p-3">${e.message||e}</td></tr>`;
  }
}
function docRefreshLotSelect(matId){
  const lotSel=document.getElementById('doc-lot');
  const lots=_allLots.filter(l=>String(l.material_id)===String(matId));
  lotSel.innerHTML='<option value="">— material-level —</option>'+lots.map(l=>
    `<option value="${l.id}">${l.lot_code} (${_accFmtN(l.remaining_qty)} ${l.uom||''} left)</option>`).join('');
}
async function docUpload(){
  const matId=document.getElementById('doc-mat').value;
  const lotId=document.getElementById('doc-lot').value;
  const type=document.getElementById('doc-type').value;
  const file=document.getElementById('doc-file').files[0];
  const notes=document.getElementById('doc-notes').value;
  if(!matId){ alert('Pick a material'); return; }
  if(!file){ alert('Pick a PDF file'); return; }
  const fd=new FormData(); fd.append('file', file);
  const tok=localStorage.getItem('erp_token')||'';
  const url=`/api/material-documents/upload?material_id=${matId}&doc_type=${encodeURIComponent(type)}${lotId?('&lot_id='+lotId):''}${notes?('&notes='+encodeURIComponent(notes)):''}`;
  try{
    const r=await fetch(url,{method:'POST',headers:{'X-Auth-Token':tok},body:fd});
    if(!r.ok){ throw new Error((await r.json()).detail||('HTTP '+r.status)); }
    bootstrap.Modal.getInstance(document.getElementById('uploadDocModal'))?.hide();
    document.getElementById('doc-file').value='';
    document.getElementById('doc-notes').value='';
    docsLoad(); lotsLoad();
  }catch(e){ alert('Upload failed: '+(e.message||e)); }
}
async function docDelete(id){
  if(!confirm('Delete this document?')) return;
  try{ await api('/api/material-documents/'+id, 'DELETE'); docsLoad(); lotsLoad(); }
  catch(e){ alert('Delete failed: '+(e.message||e)); }
}




// ════════════════════════════════════════════════════════════
// Materials
// ════════════════════════════════════════════════════════════
// ══════════════════════════════════════════════════════════
// MATERIALS
// ══════════════════════════════════════════════════════════
let _allMaterials=[], _allConsumables=[], _matFilter='', _matSearch='';
let _matPage=1, _matPageSize=50, _matFilteredRows=[];
const matTypeLabel={'core_board':'Boards','veneer_sheet':'Veneers','adhesive':'Consumable','packing':'Packing','glue_formula':'Glue and Additives','other':'Others'};
const matTypeBadge={'core_board':'bg-secondary','veneer_sheet':'bg-success','adhesive':'bg-warning text-dark','packing':'bg-info text-dark','glue_formula':'bg-danger','other':'bg-light text-dark border'};
// Phase B re-org: the `glue_formula` type slot is now used for real glue
// ingredients (urea resin, latex, flour, pigments, etc.) — i.e. the 8 chemicals
// used by glue recipes. The old "glue placeholder" rows were deleted in Phase B.
const RAW_TYPES=new Set(['core_board','veneer_sheet','adhesive','glue_formula','packing','other']);

async function loadMaterials(){
  let rows;
  try {
    // include_formulas=true so glue_formula rows are visible in the Glue tab
    rows = await api('/api/materials?include_formulas=true');
  } catch(e) {
    toast('Failed to load materials: '+e.message,'danger');
    console.error('loadMaterials API error:', e);
    return;
  }
  if(!Array.isArray(rows)){
    toast('Materials API returned unexpected data','danger');
    console.error('loadMaterials: rows is not an array', rows);
    return;
  }
  console.log('loadMaterials: got', rows.length, 'rows. Sample types:', rows.slice(0,5).map(r=>r.type));
  materials=rows;
  _allMaterials=rows.filter(m=>RAW_TYPES.has(m.type));
  // Legacy: some pages still call into _allConsumables expecting packing rows
  // (e.g. veneer dropdown population). Keep that subset alive.
  _allConsumables=rows.filter(m=>m.type==='packing');
  console.log('loadMaterials: _allMaterials.length=', _allMaterials.length, '_allConsumables.length=', _allConsumables.length);
  // Render with try/catch so one failure doesn't block others
  try { renderMaterials(_allMaterials); } catch(e) { console.error('renderMaterials error:', e); }
  try { renderConsumables(_allConsumables); } catch(e) { console.error('renderConsumables error:', e); }
  try { updateMatFilterCounts(); } catch(e) { console.error('updateMatFilterCounts error:', e); }
  try { populateVeneerDropdowns(); } catch(e) { console.error('populateVeneerDropdowns error:', e); }
}
function openMatById(id){
  const m=[..._allMaterials,..._allConsumables].find(x=>x.id===id);
  if(m) openMaterialModal(m);
}
const _editBtn = id=>`<button class="btn btn-xs btn-outline-secondary py-0 px-1" data-bs-toggle="modal" data-bs-target="#materialModal" onclick="openMatById(${id})"><i class="bi bi-pencil"></i></button>`;
// Move stock between warehouse locations (WH <-> WLWH) — boards/veneers only.
const _moveBtn = id=>`<button class="btn btn-xs btn-outline-info py-0 px-1 me-1" title="Move stock WH ↔ WLWH" onclick="whMoveOpen(${id})"><i class="bi bi-arrow-left-right"></i></button>`;
function whMoveOpen(id){
  const m=[..._allMaterials].find(x=>x.id===id); if(!m){ toast('Material not found','warning'); return; }
  _whMoveMat=m;
  document.getElementById('whmove-title').textContent=`Move stock — ${m.code||''} ${m.name||''}`;
  document.getElementById('whmove-id').value=m.id;
  document.getElementById('whmove-unit').textContent=m.unit||'';
  document.getElementById('whmove-from').value='WH';
  document.getElementById('whmove-to').value='WLWH';
  document.getElementById('whmove-qty').value='';
  document.getElementById('whmove-notes').value='';
  whMoveRefreshAvail();
  bootstrap.Modal.getOrCreateInstance(document.getElementById('whMoveModal')).show();
}
function whMoveRefreshAvail(){
  const m=_whMoveMat; if(!m) return;
  const from=document.getElementById('whmove-from').value;
  const avail=from==='WH'?(m.current_stock||0):(m.wlwh_stock||0);
  document.getElementById('whmove-avail').textContent=`Available at ${from}: ${fmt(avail)} ${m.unit||''}`;
  // keep from/to different
  const toSel=document.getElementById('whmove-to');
  if(toSel.value===from) toSel.value = from==='WH'?'WLWH':'WH';
}
async function whMoveSubmit(){
  const id=parseInt(document.getElementById('whmove-id').value)||0;
  const from=document.getElementById('whmove-from').value;
  const to=document.getElementById('whmove-to').value;
  const qty=parseFloat(document.getElementById('whmove-qty').value)||0;
  const notes=document.getElementById('whmove-notes').value;
  if(from===to){ toast('From and To must differ','warning'); return; }
  if(qty<=0){ toast('Enter a quantity','warning'); return; }
  try{
    await api('/api/warehouse/move-stock','POST',{material_id:id, from_location:from, to_location:to, qty, notes});
    bootstrap.Modal.getInstance(document.getElementById('whMoveModal')).hide();
    toast(`Moved ${fmt(qty)} from ${from} to ${to}`);
    loadMaterials();
  }catch(e){ toast(e.message,'danger'); }
}
let _whMoveMat=null;
// Single-location stock cell (consumables / generic) — just the number.
const _stockCell = m=>{
  const low=(m.current_stock||0)<(m.reorder_point||0);
  return `<td class="${low?'text-danger fw-bold':''}">${fmt(m.current_stock)}${low?' <i class="bi bi-exclamation-triangle-fill text-danger" style="font-size:.7rem"></i>':''}</td>`;
};
// Boards/veneers can sit in 2 warehouse locations (WH + WLWH). Render each
// location that holds stock as a Location | Qty column pair (two pairs; the
// 2nd is blank when stock is in a single location). FC (production floor)
// is shown on the FC Hub, not here.
const _locBadge = loc => `<span class="badge ${loc==='WLWH'?'bg-info-subtle text-info border border-info':'bg-secondary-subtle text-secondary border'}" style="font-size:.62rem">${loc}</span>`;
function _locStockCells(m){
  const wh=Number(m.current_stock||0), wl=Number(m.wlwh_stock||0);
  const locs=[];
  if(wh>0) locs.push(['WH',wh]);
  if(wl>0) locs.push(['WLWH',wl]);
  if(!locs.length) locs.push(['WH',0]);
  const low=(m.current_stock||0)<(m.reorder_point||0)&&(m.reorder_point||0)>0;
  const cell = pair => pair
    ? `<td>${_locBadge(pair[0])}</td><td class="text-end ${pair[0]==='WH'&&low?'text-danger fw-bold':''}">${fmt(pair[1])}</td>`
    : `<td class="text-muted">—</td><td class="text-end text-muted">—</td>`;
  return cell(locs[0]) + cell(locs[1]||null);
}
const _fscBadge = f=>f&&f!=='-'?`<span class="badge bg-success-subtle text-success border border-success" style="font-size:.65rem">${f}</span>`:'<span class="text-muted">—</span>';

// ── Board row ──────────────────────────────────────────────────
function boardRow(m){
  const dims = (m.width_mm&&m.length_mm)?`${m.width_mm}×${m.length_mm}`:'—';
  return `<tr>
    <td><code class="text-primary fw-semibold">${m.code||''}</code></td>
    <td>${m.board_type||'—'}</td>
    <td>${m.glue_type||'—'}</td>
    <td class="text-center">${m.thickness_mm||'—'}</td>
    <td class="text-center">${dims}</td>
    <td>${_fscBadge(m.fsc)}</td>
    <td>${m.unit||''}</td>
    ${_locStockCells(m)}
    <td>${fmt(m.reorder_point)}</td>
    <td class="fw-bold">${fmtB(m.price||m.unit_cost)}</td>
    <td class="text-nowrap">${(m.type==='core_board'||m.type==='veneer_sheet')?_moveBtn(m.id):''}${_editBtn(m.id)}</td>
  </tr>`;
}

// ── Veneer row ─────────────────────────────────────────────────
function veneerRow(m){
  const dims = (m.width_mm&&m.length_mm)?`${m.width_mm}×${m.length_mm}`:'—';
  const gradeMatch=[m.grade, m.matching].filter(Boolean).join(' / ')||'—';
  return `<tr>
    <td><code class="text-primary fw-semibold">${m.code||''}</code></td>
    <td>${m.species||'—'}</td>
    <td>${m.cut_type||'—'}</td>
    <td class="text-center">${m.thickness_mm||'—'}</td>
    <td class="text-center">${dims}</td>
    <td>${gradeMatch}</td>
    <td>${_fscBadge(m.fsc)}</td>
    <td>${m.unit||''}</td>
    ${_locStockCells(m)}
    <td>${fmt(m.reorder_point)}</td>
    <td class="fw-bold">${fmtB(m.price||m.unit_cost)}</td>
    <td class="text-nowrap">${(m.type==='core_board'||m.type==='veneer_sheet')?_moveBtn(m.id):''}${_editBtn(m.id)}</td>
  </tr>`;
}

// ── Generic row (adhesive / other / all) ──────────────────────
function matRow(m, showType=true){
  const typeCell=showType?`<td><span class="badge ${matTypeBadge[m.type]||'bg-secondary'}" style="font-size:.65rem">${matTypeLabel[m.type]||m.type||''}</span></td>`:'';
  return `<tr>
    <td><code class="text-primary">${m.code||''}</code></td>
    <td>${matDisplayName(m)}</td>
    ${typeCell}
    <td>${m.unit||''}</td>
    ${_stockCell(m)}
    <td>${fmt(m.reorder_point)}</td>
    <td class="fw-bold">${fmtB(m.price||m.unit_cost)}</td>
    <td class="text-nowrap">${(m.type==='core_board'||m.type==='veneer_sheet')?_moveBtn(m.id):''}${_editBtn(m.id)}</td>
  </tr>`;
}

function renderConsumables(rows){
  // Legacy table removed — packing rows now appear only when the user
  // toggles the Packing tab (or All) in the main materials table.
  const el = document.querySelector('#consumables-table tbody');
  if(el) el.innerHTML = rows.map(m=>matRow(m,false)).join('');
}

// Localised description for material rows. When the UI language is Thai
// and the material has a name_th value, prefer that; otherwise fall back
// to the canonical name/code.
function matDisplayName(m){
  if(_LANG === 'th' && m && m.name_th && String(m.name_th).trim()) return m.name_th;
  return m.name || m.code || '';
}

const MAT_HEADS = {
  core_board: `<tr><th>Code</th><th>Board Type</th><th>Glue</th><th class="text-center">Thick(mm)</th><th class="text-center">W×L (mm)</th><th>FSC</th><th>Unit</th><th>Location</th><th class="text-end">Qty</th><th>Location</th><th class="text-end">Qty</th><th>Min</th><th>Price</th><th></th></tr>`,
  veneer_sheet: `<tr><th>Code</th><th>Species</th><th>Cut</th><th class="text-center">V-Thick</th><th class="text-center">W×L (mm)</th><th>Grade / Match</th><th>FSC</th><th>Unit</th><th>Location</th><th class="text-end">Qty</th><th>Location</th><th class="text-end">Qty</th><th>Min</th><th>Price</th><th></th></tr>`,
  _generic: `<tr><th>Code</th><th>Description</th><th>Type</th><th>Unit</th><th>Stock</th><th>Min</th><th>Price</th><th></th></tr>`,
};

function renderMaterials(rows, resetPage=true){
  _matFilteredRows = rows;
  if(resetPage) _matPage = 1;

  const total = rows.length;
  const pageSize = _matPageSize === 0 ? total : _matPageSize; // 0 = All
  const totalPages = pageSize > 0 ? Math.max(1, Math.ceil(total / pageSize)) : 1;
  if(_matPage > totalPages) _matPage = totalPages;

  const start = (_matPage - 1) * pageSize;
  const pageRows = pageSize > 0 ? rows.slice(start, start + pageSize) : rows;

  const thead = document.getElementById('mat-thead');
  if(thead) thead.innerHTML = MAT_HEADS[_matFilter] || MAT_HEADS._generic;

  const html = total === 0
    ? `<tr><td colspan="12" class="text-center text-muted py-4">No materials found</td></tr>`
    : pageRows.map(m=>{
        if(_matFilter==='core_board') return boardRow(m);
        if(_matFilter==='veneer_sheet') return veneerRow(m);
        return matRow(m, true);
      }).join('');
  document.querySelector('#materials-table tbody').innerHTML = html;

  // Update count label
  const cnt = document.getElementById('mat-shown-count');
  if(cnt){
    if(total === 0) cnt.textContent = '0 shown';
    else if(_matPageSize === 0) cnt.textContent = `${total} shown`;
    else cnt.textContent = `${start+1}–${Math.min(start+pageSize, total)} of ${total}`;
  }

  // Render pagination controls
  _renderMatPagination(total, pageSize, totalPages);
}

function _renderMatPagination(total, pageSize, totalPages){
  const el = document.getElementById('mat-pagination');
  if(!el) return;
  if(total === 0 || totalPages <= 1){ el.innerHTML=''; return; }

  const mkBtn = (label, page, disabled=false, active=false) =>
    `<li class="page-item${disabled?' disabled':''}${active?' active':''}">
      <a class="page-link" href="#" onclick="event.preventDefault();${disabled||active?'':`matGoPage(${page})`}">${label}</a>
    </li>`;

  // Show window of pages around current
  const pages = [];
  const wing = 2;
  for(let p=1; p<=totalPages; p++){
    if(p===1 || p===totalPages || (p>=_matPage-wing && p<=_matPage+wing)) pages.push(p);
    else if(pages[pages.length-1] !== '…') pages.push('…');
  }

  let html = `<ul class="pagination pagination-sm mb-0">`;
  html += mkBtn('‹ Prev', _matPage-1, _matPage===1);
  pages.forEach(p=>{
    if(p==='…') html += `<li class="page-item disabled"><a class="page-link">…</a></li>`;
    else html += mkBtn(p, p, false, p===_matPage);
  });
  html += mkBtn('Next ›', _matPage+1, _matPage===totalPages);
  html += `</ul>`;
  el.innerHTML = html;
}

function matGoPage(page){
  _matPage = page;
  renderMaterials(_matFilteredRows, false);
}

function matSetPageSize(n){
  _matPageSize = n;
  _matPage = 1;
  renderMaterials(_matFilteredRows, false);
}

function filterMaterials(type, searchOverride){
  _matFilter = type;
  if(searchOverride !== undefined) _matSearch = searchOverride;
  // Update button states
  document.querySelectorAll('#mat-type-filter button').forEach(b=>{
    b.classList.toggle('active', b.dataset.matType===type);
  });
  // Toggle veneer sub-filters
  const vsf = document.getElementById('veneer-subfilters');
  if(vsf) vsf.classList.toggle('d-none', type!=='veneer_sheet');
  if(type==='veneer_sheet') applyVeneerFilters(); else _renderMatFiltered();
}

function _renderMatFiltered(){
  let rows = _matFilter ? _allMaterials.filter(m=>m.type===_matFilter) : _allMaterials;
  const q = (_matSearch||'').toLowerCase().trim();
  if(q) rows = rows.filter(m=>(m.code||'').toLowerCase().includes(q)||(m.name||'').toLowerCase().includes(q)||(m.species||'').toLowerCase().includes(q)||(m.board_type||'').toLowerCase().includes(q));
  renderMaterials(rows, true);
}

function populateVeneerDropdowns(){
  const veneers = _allMaterials.filter(m=>m.type==='veneer_sheet');
  const fill = (id, vals)=>{
    const el=document.getElementById(id); if(!el) return;
    const cur=el.value;
    el.innerHTML='<option value="">'+el.options[0].text+'</option>'+
      [...new Set(vals.filter(Boolean).map(v=>v.trim()))].sort().map(v=>`<option value="${v}">${v}</option>`).join('');
    if(cur) el.value=cur;
  };
  fill('vf-species', veneers.map(m=>m.species));
  fill('vf-cut',     veneers.map(m=>m.cut_type));
  fill('vf-match',   veneers.map(m=>m.matching));
  fill('vf-thick',   veneers.map(m=>m.thickness_mm!=null?String(m.thickness_mm):''));
}

function applyVeneerFilters(){
  const sp   = document.getElementById('vf-species')?.value||'';
  const cut  = document.getElementById('vf-cut')?.value||'';
  const match= document.getElementById('vf-match')?.value||'';
  const thick= document.getElementById('vf-thick')?.value||'';
  const q    = (_matSearch||'').toLowerCase().trim();
  let rows = _allMaterials.filter(m=>m.type==='veneer_sheet');
  if(sp)    rows = rows.filter(m=>m.species===sp);
  if(cut)   rows = rows.filter(m=>m.cut_type===cut);
  if(match) rows = rows.filter(m=>m.matching===match);
  if(thick) rows = rows.filter(m=>String(m.thickness_mm)===thick);
  if(q)     rows = rows.filter(m=>(m.code||'').toLowerCase().includes(q)||(m.name||'').toLowerCase().includes(q)||(m.species||'').toLowerCase().includes(q));
  renderMaterials(rows, true);
}

function resetVeneerFilters(){
  ['vf-species','vf-cut','vf-match','vf-thick'].forEach(id=>{
    const el=document.getElementById(id); if(el) el.value='';
  });
  const s=document.getElementById('mat-search'); if(s) s.value=''; _matSearch='';
  applyVeneerFilters();
}

function updateMatFilterCounts(){
  const counts={'':_allMaterials.length};
  ['core_board','veneer_sheet','adhesive','glue_formula','packing','other'].forEach(t=>{counts[t]=_allMaterials.filter(m=>m.type===t).length;});
  const labels={'':'All','core_board':'Boards','veneer_sheet':'Veneers','adhesive':'Consumable','glue_formula':'Glue and Additives','packing':'Packing','other':'Others'};
  document.querySelectorAll('#mat-type-filter button').forEach(b=>{
    const t=b.dataset.matType||'';
    const base=labels[t]||t;
    b.textContent=`${base} (${counts[t]||0})`;
  });
}
function matTypeChanged(){
  const t=document.getElementById('mat-cat').value;
  document.getElementById('mat-dims-section').classList.toggle('d-none', t!=='core_board');
  document.getElementById('mat-glue-section').classList.toggle('d-none', t!=='veneer_sheet');
}
function openMaterialModal(m){
  const isEdit=m && m.id;
  document.getElementById('mat-modal-title').textContent=isEdit?'Edit Material':'Add Material';
  document.getElementById('mat-id').value=isEdit?m.id:'';
  document.getElementById('mat-code').value=isEdit?m.code||'':'';
  document.getElementById('mat-name').value=isEdit?m.name||'':'';
  document.getElementById('mat-cat').value=isEdit?m.type||'':'';
  document.getElementById('mat-unit').value=isEdit?m.unit||'sheet':'sheet';
  document.getElementById('mat-stock').value=isEdit?m.current_stock||m.stock||'':'';
  document.getElementById('mat-min').value=isEdit?m.reorder_point||'':'';
  document.getElementById('mat-cost').value=isEdit?m.unit_cost||m.price||'':'';
  document.getElementById('mat-thick').value=isEdit?m.thickness_mm||'':'';
  document.getElementById('mat-width').value=isEdit?m.width_mm||'':'';
  document.getElementById('mat-length').value=isEdit?m.length_mm||'':'';
  document.getElementById('mat-auto-glue').value=isEdit?m.auto_glue_code||'':'';
  matTypeChanged();
}
async function saveMaterial(){
  const id=document.getElementById('mat-id').value;
  const gn=k=>{ const v=parseFloat(document.getElementById(k).value); return isNaN(v)?null:v; };
  const body={
    code:document.getElementById('mat-code').value,
    name:document.getElementById('mat-name').value,
    type:document.getElementById('mat-cat').value,
    unit:document.getElementById('mat-unit').value,
    current_stock:gn('mat-stock')||0,
    reorder_point:gn('mat-min')||0,
    unit_cost:gn('mat-cost')||0,
    thickness_mm:gn('mat-thick'),
    width_mm:gn('mat-width'),
    length_mm:gn('mat-length'),
    auto_glue_code:document.getElementById('mat-auto-glue').value.trim()||null,
  };
  try{
    if(id) await api(`/api/materials/${id}`,'PUT',body);
    else await api('/api/materials','POST',body);
    bootstrap.Modal.getInstance(document.getElementById('materialModal')).hide();
    toast('Saved');
    loadMaterials();
    if(_bbLoaded){ _bbLoaded=false; loadBomBuilder(); } // refresh BOM builder material data
  }catch(e){toast(e.message,'danger');}
}

// ── Page loader registry ────────────────────────────────────
// Self-register the three pages this module owns. Replaces the
// equivalent entries in the main inline script's Object.assign call.
Object.assign(PAGE_LOADERS, {
  'wh-dashboard':    whDashLoad,
  'wh-low-stock':    whLowStockLoad,
  'wh-open-prs':     whOpenPRsLoad,
  'raw-receiving':   rrecLoad,
  'forklift-refuel': frflLoad,
  'forklift-dash':   fkDashLoad,
  'scrap-bin':       scrapLoad,
  'warehouse-queue': wqLoad,
  'dept-fg_warehouse': loadFgWarehouse,
  'lots-docs'              : () => { lotsPrimeMatSelect(); lotsLoad(); docsLoad(); },
  'materials'              : loadMaterials,
});
