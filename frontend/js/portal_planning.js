/* PVWood ERP - Planning Portal.
   First chunk: VCMX (make-to-stock substrate: plywood core + MDF face/back).
   Subsequent commits will add: order-intake, line-board, BOM, station-log,
   glue-mix, material-shortfalls, FC hub.

   Self-registers its pages via Object.assign(PAGE_LOADERS, ...). Load
   order: AFTER the main inline script (so its constants are visible).

   Globals declared by this chunk:
       _vcmxBoms, _vcmxMaterials, _vcmxBbEditId, _vcmxBbAllMats,
       _vcmxLamCurrent
       vcmxLoad, vcmxLoadBoms, vcmxLoadOrders, vcmxLoadHistory,
       vcmxBomTabLoad, vcmxBomTabLoadSearch (+ many helpers)
       vcmxLamLoad
*/
// ══════════════════════════════════════════════════════════════
// VCMX (make-to-stock substrate: plywood core + MDF face/back)
// ══════════════════════════════════════════════════════════════
let _vcmxBoms = [], _vcmxMaterials = [];

async function vcmxLoad(){
  try{ _vcmxMaterials = await api('/api/materials'); }catch{ _vcmxMaterials = []; }
  await vcmxLoadBoms();
  await vcmxLoadOrders();
  await vcmxLoadHistory();
  vcmxRefreshBadge();
}

async function vcmxLoadBoms(){
  try{ _vcmxBoms = await api('/api/vcmx/boms'); }catch{ _vcmxBoms = []; }
  const tb = document.getElementById('vcmx-boms-tbody');
  if(!_vcmxBoms.length){
    tb.innerHTML = '<tr><td colspan="10" class="text-center text-muted py-3">No VCMX BOMs defined yet — click "New VCMX BOM" to create one.</td></tr>';
    return;
  }
  tb.innerHTML = _vcmxBoms.map(b => `
    <tr ${b.active?'':'class="text-muted"'}>
      <td class="fw-semibold">${b.sku_code}</td>
      <td>${b.sku_name}</td>
      <td class="small">${b.core_name||'—'}</td>
      <td class="small">${b.face_name||'—'}</td>
      <td class="small">${b.back_name||'—'}</td>
      <td class="small">${b.glue_name ? `${b.glue_name} <span class="text-muted">×${b.glue_qty_per_panel||0}</span>` : '<span class="text-muted">—</span>'}</td>
      <td class="text-end">${Number(b.labour_cost_per_panel||0).toFixed(2)}</td>
      <td class="text-end ${(b.fc_stock||0)>0?'text-success fw-semibold':'text-muted'}">${Number(b.fc_stock||0)}</td>
      <td>${b.active?'<span class="badge bg-success">Active</span>':'<span class="badge bg-secondary">Inactive</span>'}</td>
      <td class="text-end" style="white-space:nowrap">
        <button class="btn btn-xs btn-outline-primary" title="Toggle active" onclick="vcmxToggleBom(${b.id}, ${b.active?0:1})">
          <i class="bi bi-toggle-${b.active?'on':'off'}"></i>
        </button>
      </td>
    </tr>`).join('');
}

async function vcmxLoadOrders(){
  let rows = [];
  try{ rows = await api('/api/vcmx/batches?status=open'); }catch{}
  const tb = document.getElementById('vcmx-orders-tbody');
  if(!rows.length){
    tb.innerHTML = '<tr><td colspan="7" class="text-center text-muted py-3">No open VCMX production orders.</td></tr>';
    return;
  }
  const prioLbl = p => p===1?'<span class="badge bg-danger">P1</span>':p===2?'<span class="badge bg-warning text-dark">P2</span>':'<span class="badge bg-success">P3</span>';
  tb.innerHTML = rows.map(r=>`
    <tr>
      <td class="small fw-semibold">${r.prod_order_number||'—'}</td>
      <td class="small">${r.batch_number}</td>
      <td>${r.sku_code} <span class="text-muted small">${r.sku_name||''}</span></td>
      <td class="text-end">${r.quantity}</td>
      <td>${prioLbl(r.priority)}</td>
      <td><span class="badge bg-info text-white">${r.current_department}</span></td>
      <td class="small text-muted">${(r.created_at||'').slice(0,16).replace('T',' ')}</td>
    </tr>`).join('');
}

async function vcmxLoadHistory(){
  let rows = [];
  try{ rows = await api('/api/vcmx/batches?status=completed'); }catch{}
  const tb = document.getElementById('vcmx-history-tbody');
  if(!rows.length){
    tb.innerHTML = '<tr><td colspan="8" class="text-center text-muted py-3">No completed VCMX batches yet.</td></tr>';
    return;
  }
  // Need cost info — fetch lots once for output mapping
  tb.innerHTML = rows.map(r => `
    <tr>
      <td class="small fw-semibold">${r.batch_number}</td>
      <td>${r.sku_code} <span class="text-muted small">${r.sku_name||''}</span></td>
      <td class="text-end">${r.quantity}</td>
      <td class="text-end text-muted small" colspan="4">(see history log via traceability)</td>
      <td class="small text-muted">${(r.created_at||'').slice(0,16).replace('T',' ')}</td>
    </tr>`).join('');
}

function _vcmxBoardOpts(filterRegex){
  return _vcmxMaterials
    .filter(m => filterRegex.test(m.type||''))
    .sort((a,b)=>(a.name||'').localeCompare(b.name||''))
    .map(m => `<option value="${m.id}">[${(m.type||'').toUpperCase()}] ${m.code||''} — ${m.name}</option>`)
    .join('');
}
function _vcmxGlueOpts(){
  return '<option value="">— none —</option>' + _vcmxMaterials
    .filter(m => /glue|adhesive/i.test(m.type||''))
    .sort((a,b)=>(a.name||'').localeCompare(b.name||''))
    .map(m => `<option value="${m.id}">${m.code||''} — ${m.name}</option>`)
    .join('');
}

async function vcmxOpenBomModal(){
  if(!_vcmxMaterials.length){ try{ _vcmxMaterials = await api('/api/materials'); }catch{} }
  const boards = _vcmxBoardOpts(/board|plywood|mdf/i);
  document.getElementById('vcmx-bom-core').innerHTML = boards;
  document.getElementById('vcmx-bom-face').innerHTML = boards;
  document.getElementById('vcmx-bom-back').innerHTML = boards;
  document.getElementById('vcmx-bom-glue').innerHTML = _vcmxGlueOpts();
  ['vcmx-bom-code','vcmx-bom-name','vcmx-bom-notes'].forEach(id=>document.getElementById(id).value='');
  document.getElementById('vcmx-bom-glueqty').value = '0';
  document.getElementById('vcmx-bom-labour').value = '0';
  new bootstrap.Modal(document.getElementById('vcmxBomModal')).show();
}

async function vcmxSubmitBom(){
  const body = {
    sku_code: document.getElementById('vcmx-bom-code').value.trim(),
    sku_name: document.getElementById('vcmx-bom-name').value.trim(),
    core_material_id: Number(document.getElementById('vcmx-bom-core').value),
    face_material_id: Number(document.getElementById('vcmx-bom-face').value),
    back_material_id: Number(document.getElementById('vcmx-bom-back').value),
    glue_material_id: Number(document.getElementById('vcmx-bom-glue').value)||null,
    glue_qty_per_panel: Number(document.getElementById('vcmx-bom-glueqty').value)||0,
    labour_cost_per_panel: Number(document.getElementById('vcmx-bom-labour').value)||0,
    notes: document.getElementById('vcmx-bom-notes').value||'',
  };
  if(!body.sku_code || !body.sku_name){ alert('SKU code and name required'); return; }
  if(!body.core_material_id || !body.face_material_id || !body.back_material_id){ alert('Core, face, back materials all required'); return; }
  try{
    await api('/api/vcmx/boms', 'POST', body);
    bootstrap.Modal.getInstance(document.getElementById('vcmxBomModal'))?.hide();
    toast('VCMX BOM saved','success');
    vcmxLoadBoms();
  }catch(e){ alert('Save failed: '+(e.message||e)); }
}

async function vcmxToggleBom(id, active){
  try{
    await api(`/api/vcmx/boms/${id}`, 'PATCH', {active});
    vcmxLoadBoms();
  }catch(e){ alert('Update failed: '+(e.message||e)); }
}

async function vcmxOpenOrderModal(){
  if(!_vcmxBoms.length){ await vcmxLoadBoms(); }
  const sel = document.getElementById('vcmx-order-bom');
  sel.innerHTML = '<option value="">— pick a BOM —</option>' + _vcmxBoms
    .filter(b=>b.active)
    .map(b=>`<option value="${b.id}">${b.sku_code} — ${b.sku_name}</option>`).join('');
  document.getElementById('vcmx-order-qty').value = '';
  document.getElementById('vcmx-order-prio').value = '2';
  document.getElementById('vcmx-order-start').value = '';
  document.getElementById('vcmx-order-end').value = '';
  document.getElementById('vcmx-order-notes').value = '';
  document.getElementById('vcmx-order-check').innerHTML = '';
  document.getElementById('vcmx-order-submit').disabled = false;
  new bootstrap.Modal(document.getElementById('vcmxOrderModal')).show();
}

async function vcmxOrderRecheck(){
  const bom = Number(document.getElementById('vcmx-order-bom').value);
  const qty = Number(document.getElementById('vcmx-order-qty').value||0);
  const box = document.getElementById('vcmx-order-check');
  const btn = document.getElementById('vcmx-order-submit');
  if(!bom || qty<=0){ box.innerHTML=''; btn.disabled = !(bom && qty>0); return; }
  try{
    const r = await api(`/api/vcmx/boms/${bom}/check-inputs?qty=${qty}`);
    if(r.ok){
      box.innerHTML = `<div class="alert alert-success py-2 small mb-0"><i class="bi bi-check-circle me-1"></i>All inputs available at FC for ${qty} panels — ready to release.</div>`;
      btn.disabled = false;
    } else {
      const rows = r.shortages.map(s=>`
        <tr><td>${s.name}</td>
            <td class="text-end">${s.required} ${s.uom}</td>
            <td class="text-end text-success">${s.available}</td>
            <td class="text-end text-danger fw-bold">${s.shortfall}</td></tr>`).join('');
      box.innerHTML = `
        <div class="alert alert-danger py-2 small mb-2">
          <i class="bi bi-x-octagon me-1"></i><b>Insufficient FC stock</b> — issue a PR for the missing inputs first.
        </div>
        <table class="table table-sm">
          <thead class="table-light"><tr><th>Material</th><th class="text-end">Required</th><th class="text-end">At FC</th><th class="text-end">Short</th></tr></thead>
          <tbody>${rows}</tbody>
        </table>
        <button class="btn btn-sm btn-warning" onclick='vcmxRaisePRForShortage(${JSON.stringify(r.shortages).replace(/'/g,"&apos;")})'>
          <i class="bi bi-send me-1"></i>Pre-fill PR for these inputs
        </button>`;
      btn.disabled = true;
    }
  }catch(e){
    box.innerHTML = `<div class="alert alert-warning py-2 small mb-0">Check failed: ${e.message||e}</div>`;
  }
}

function vcmxRaisePRForShortage(shortages){
  // Close VCMX order modal, open the multi-PR modal pre-filled with shortage lines
  bootstrap.Modal.getInstance(document.getElementById('vcmxOrderModal'))?.hide();
  new bootstrap.Modal(document.getElementById('newPRModal')).show();
  setTimeout(()=>{
    // Modal show.bs.modal already primed materials and reset lines via prResetLines
    // Replace single empty line with one per shortage
    _prLineSeq = 0;
    document.getElementById('pr-lines-container').innerHTML = '';
    shortages.forEach(s => {
      prAddLine();
      const lastLine = document.querySelector('.pr-line[data-idx="'+(_prLineSeq-1)+'"]');
      const sel = lastLine.querySelector('.pr-l-mat');
      sel.value = String(s.material_id);
      _prOnMatChange(_prLineSeq-1);
      lastLine.querySelector('.pr-l-qty').value = s.shortfall;
      lastLine.querySelector('.pr-l-uom').value = s.uom || lastLine.querySelector('.pr-l-uom').value;
    });
    document.getElementById('pr-new-notes').value = 'For VCMX make-to-stock production';
    document.getElementById('pr-new-priority').value = '1';
  }, 400);
}

async function vcmxSubmitOrder(){
  const body = {
    vcmx_bom_id: Number(document.getElementById('vcmx-order-bom').value),
    quantity:    Number(document.getElementById('vcmx-order-qty').value||0),
    priority:    Number(document.getElementById('vcmx-order-prio').value||2),
    planned_start: document.getElementById('vcmx-order-start').value||'',
    planned_end:   document.getElementById('vcmx-order-end').value||'',
    notes:         document.getElementById('vcmx-order-notes').value||'',
  };
  if(!body.vcmx_bom_id || body.quantity<=0){ alert('Pick a BOM and positive qty'); return; }
  try{
    const r = await api('/api/vcmx/orders', 'POST', body);
    bootstrap.Modal.getInstance(document.getElementById('vcmxOrderModal'))?.hide();
    toast(`Created ${r.prod_order_number} → batch ${r.batch_number} at VCMX-Lam`,'success');
    vcmxLoadOrders();
    vcmxRefreshBadge();
  }catch(e){
    const msg = e.detail?.message || e.message || e;
    alert('Failed: '+msg);
  }
}

async function vcmxRefreshBadge(){
  try{
    const rows = await api('/api/vcmx/batches?status=open');
    const bd = document.getElementById('nav-vcmx-badge');
    if(bd){ bd.textContent = rows.length; bd.classList.toggle('d-none', rows.length===0); }
  }catch{}
}
setTimeout(vcmxRefreshBadge, 6000);
setInterval(vcmxRefreshBadge, 300000);

// ── VCMX BOM tab inside Bill of Materials ─────────────────────
let _vcmxBbEditId = null;
let _vcmxBbAllMats = [];

async function vcmxBomTabLoad(){
  if(!_vcmxBbAllMats.length){
    try{ _vcmxBbAllMats = await api('/api/materials'); }catch{ _vcmxBbAllMats = []; }
  }
  try{ _vcmxBoms = await api('/api/vcmx/boms'); }catch{ _vcmxBoms = []; }
  _vcmxBomTabRender(_vcmxBoms);
  vcmxBbPopulateAllSelects();
}

function vcmxBomTabFilter(q){
  q = (q||'').toLowerCase();
  const rows = !q ? _vcmxBoms : _vcmxBoms.filter(b =>
    (b.sku_code||'').toLowerCase().includes(q) ||
    (b.sku_name||'').toLowerCase().includes(q));
  _vcmxBomTabRender(rows);
}

function _vcmxBomTabRender(rows){
  const c = document.getElementById('vcmx-bom-count');
  if(c) c.textContent = `${rows.length} VCMX BOM${rows.length===1?'':'s'}`;
  const root = document.getElementById('vcmx-bom-tab-list');
  if(!rows.length){
    root.innerHTML = '<div class="text-center text-muted py-4">No VCMX BOMs yet — click <b>New / Edit VCMX BOM</b>.</div>';
    return;
  }
  // colspan unused but keep table header in sync
  root.innerHTML = `
    <div class="card">
      <div class="table-responsive">
        <table class="table table-sm table-hover mb-0 align-middle">
          <thead class="table-light"><tr>
            <th>SKU</th><th>Name</th>
            <th>Dims (T×W×L mm)</th><th class="text-end">pcs/pallet</th>
            <th>Core (plywood)</th><th>Face (MDF)</th><th>Back (MDF)</th>
            <th>Glue / panel</th>
            <th class="text-end">Labour ฿</th>
            <th class="text-end">FC Stock</th>
            <th>Status</th>
            <th class="text-end">Actions</th>
          </tr></thead>
          <tbody>${rows.map(b=>`
            <tr ${b.active?'':'class="text-muted"'}>
              <td class="fw-semibold">${b.sku_code}</td>
              <td>${b.sku_name||''}</td>
              <td class="small">${(b.thickness_mm||'—')} × ${(b.width_mm||'—')} × ${(b.length_mm||'—')}</td>
              <td class="text-end small">${b.pcs_per_pallet||'—'}</td>
              <td class="small">${b.core_name||'—'}</td>
              <td class="small">${b.face_name||'—'}</td>
              <td class="small">${b.back_name||'—'}</td>
              <td class="small">${b.glue_name ? `${b.glue_name} <span class="text-muted">×${b.glue_qty_per_panel||0}</span>` : '<span class="text-muted">—</span>'}</td>
              <td class="text-end">${Number(b.labour_cost_per_panel||0).toFixed(2)}</td>
              <td class="text-end ${(b.fc_stock||0)>0?'text-success fw-semibold':'text-muted'}">${Number(b.fc_stock||0)}</td>
              <td>${b.active?'<span class="badge bg-success">Active</span>':'<span class="badge bg-secondary">Inactive</span>'}</td>
              <td class="text-end" style="white-space:nowrap">
                <button class="btn btn-xs btn-outline-primary" title="Edit" onclick='vcmxBomTabEdit(${b.id})'><i class="bi bi-pencil"></i></button>
                <button class="btn btn-xs btn-outline-secondary" title="Toggle active" onclick="vcmxToggleBom(${b.id}, ${b.active?0:1});setTimeout(vcmxBomTabLoad,300)"><i class="bi bi-toggle-${b.active?'on':'off'}"></i></button>
              </td>
            </tr>`).join('')}
          </tbody>
        </table>
      </div>
    </div>`;
}

function vcmxBomTabToggleBuilder(){
  const el = document.getElementById('vcmx-bom-builder-panel');
  const isOpen = el.classList.contains('show');
  if(isOpen){
    bootstrap.Collapse.getInstance(el)?.hide() || new bootstrap.Collapse(el).hide();
  } else {
    vcmxBomTabReset();
    new bootstrap.Collapse(el).show();
  }
}

function vcmxBomTabReset(){
  _vcmxBbEditId = null;
  ['vcmx-bb-code','vcmx-bb-name','vcmx-bb-notes','vcmx-bb-load-q',
   'vcmx-bb-thick','vcmx-bb-width','vcmx-bb-length','vcmx-bb-pcspal'].forEach(id=>{
    const e=document.getElementById(id); if(e) e.value='';
  });
  document.getElementById('vcmx-bb-glueqty').value = '0';
  document.getElementById('vcmx-bb-labour').value = '0';
  document.getElementById('vcmx-bb-code').readOnly = false;
  vcmxBbPopulateAllSelects();
  ['core','face','back','glue'].forEach(k=>{
    const s = document.getElementById('vcmx-bb-'+k);
    if(s) s.value = '';
  });
}

function _vcmxBoardCandidates(){
  return _vcmxBbAllMats.filter(m=>/board|plywood|mdf/i.test(m.type||''))
                       .sort((a,b)=>(a.name||'').localeCompare(b.name||''));
}
function _vcmxGlueCandidates(){
  return _vcmxBbAllMats.filter(m=>/glue|adhesive/i.test(m.type||''))
                       .sort((a,b)=>(a.name||'').localeCompare(b.name||''));
}

function vcmxBbPopulateAllSelects(){
  const boards = _vcmxBoardCandidates();
  ['core','face','back'].forEach(k=>{
    const sel = document.getElementById('vcmx-bb-'+k);
    if(!sel) return;
    sel.innerHTML = boards.map(m=>`<option value="${m.id}">${m.code||''} ${m.name}</option>`).join('');
  });
  const glue = document.getElementById('vcmx-bb-glue');
  if(glue){
    glue.innerHTML = '<option value="">— none —</option>' +
      _vcmxGlueCandidates().map(m=>`<option value="${m.id}">${m.code||''} ${m.name}</option>`).join('');
  }
}

function vcmxBbFilter(which, q){
  q=(q||'').toLowerCase();
  const sel = document.getElementById('vcmx-bb-'+which);
  if(!sel) return;
  const pool = (which==='glue') ? _vcmxGlueCandidates() : _vcmxBoardCandidates();
  const filtered = !q ? pool : pool.filter(m =>
    (m.name||'').toLowerCase().includes(q) || (m.code||'').toLowerCase().includes(q));
  const prefix = (which==='glue') ? '<option value="">— none —</option>' : '';
  sel.innerHTML = prefix + filtered.map(m=>`<option value="${m.id}">${m.code||''} ${m.name}</option>`).join('');
}

function vcmxBbPickHint(which){
  const sel = document.getElementById('vcmx-bb-'+which);
  const hint = document.getElementById('vcmx-bb-'+which+'-hint');
  if(!sel || !hint) return;
  const mid = Number(sel.value);
  const m = _vcmxBbAllMats.find(x=>x.id===mid);
  if(!m) return;
  const dims = [m.thickness_mm && m.thickness_mm+'mm', m.width_mm && m.width_mm+'mm', m.length_mm && m.length_mm+'mm'].filter(Boolean).join(' × ');
  hint.innerHTML = `<i class="bi bi-check2 me-1 text-success"></i>${m.code||''} ${m.name}${dims?' · '+dims:''}`;
}

function vcmxBomTabLoadSearch(q){
  q=(q||'').toLowerCase();
  const drop = document.getElementById('vcmx-bb-load-drop');
  if(!q){ drop.classList.add('d-none'); return; }
  const matches = _vcmxBoms.filter(b =>
    (b.sku_code||'').toLowerCase().includes(q) ||
    (b.sku_name||'').toLowerCase().includes(q)).slice(0,12);
  if(!matches.length){ drop.innerHTML='<div class="p-2 small text-muted">No matches</div>'; drop.classList.remove('d-none'); return; }
  drop.innerHTML = matches.map(b=>`
    <div class="p-2 border-bottom small" style="cursor:pointer" onmouseover="this.style.background='#f1f3f5'" onmouseout="this.style.background=''" onclick="vcmxBomTabEdit(${b.id})">
      <b>${b.sku_code}</b> — ${b.sku_name||''}
    </div>`).join('');
  drop.classList.remove('d-none');
}

function vcmxBomTabEdit(id){
  const b = _vcmxBoms.find(x=>x.id===id);
  if(!b) return;
  _vcmxBbEditId = id;
  // Make sure builder visible
  const panel = document.getElementById('vcmx-bom-builder-panel');
  if(!panel.classList.contains('show')) new bootstrap.Collapse(panel).show();
  document.getElementById('vcmx-bb-load-drop').classList.add('d-none');
  document.getElementById('vcmx-bb-load-q').value = '';
  vcmxBbPopulateAllSelects();
  document.getElementById('vcmx-bb-code').value = b.sku_code;
  document.getElementById('vcmx-bb-code').readOnly = true; // SKU code immutable on edit
  document.getElementById('vcmx-bb-name').value = b.sku_name||'';
  document.getElementById('vcmx-bb-thick').value  = b.thickness_mm||'';
  document.getElementById('vcmx-bb-width').value  = b.width_mm||'';
  document.getElementById('vcmx-bb-length').value = b.length_mm||'';
  document.getElementById('vcmx-bb-pcspal').value = b.pcs_per_pallet||'';
  document.getElementById('vcmx-bb-core').value = b.core_material_id||'';
  document.getElementById('vcmx-bb-face').value = b.face_material_id||'';
  document.getElementById('vcmx-bb-back').value = b.back_material_id||'';
  document.getElementById('vcmx-bb-glue').value = b.glue_material_id||'';
  document.getElementById('vcmx-bb-glueqty').value = b.glue_qty_per_panel||0;
  document.getElementById('vcmx-bb-labour').value  = b.labour_cost_per_panel||0;
  document.getElementById('vcmx-bb-notes').value   = b.notes||'';
  ['core','face','back'].forEach(vcmxBbPickHint);
}

async function vcmxBomTabSave(){
  const body = {
    sku_code: document.getElementById('vcmx-bb-code').value.trim(),
    sku_name: document.getElementById('vcmx-bb-name').value.trim(),
    thickness_mm:   Number(document.getElementById('vcmx-bb-thick').value)||0,
    width_mm:       Number(document.getElementById('vcmx-bb-width').value)||0,
    length_mm:      Number(document.getElementById('vcmx-bb-length').value)||0,
    pcs_per_pallet: Number(document.getElementById('vcmx-bb-pcspal').value)||0,
    core_material_id: Number(document.getElementById('vcmx-bb-core').value)||0,
    face_material_id: Number(document.getElementById('vcmx-bb-face').value)||0,
    back_material_id: Number(document.getElementById('vcmx-bb-back').value)||0,
    glue_material_id: Number(document.getElementById('vcmx-bb-glue').value)||null,
    glue_qty_per_panel: Number(document.getElementById('vcmx-bb-glueqty').value)||0,
    labour_cost_per_panel: Number(document.getElementById('vcmx-bb-labour').value)||0,
    notes: document.getElementById('vcmx-bb-notes').value||'',
  };
  if(!body.sku_code || !body.sku_name){ alert('SKU code and name required'); return; }
  if(!body.thickness_mm || !body.width_mm || !body.length_mm){
    alert('Thickness, width and length (mm) are all required'); return;
  }
  if(!body.pcs_per_pallet || body.pcs_per_pallet<=0){
    alert('Pcs / pallet must be a positive integer'); return;
  }
  if(!body.core_material_id || !body.face_material_id || !body.back_material_id){
    alert('Pick a board for core, face, and back layers'); return;
  }
  try{
    if(_vcmxBbEditId){
      const upd = {...body}; delete upd.sku_code;
      await api(`/api/vcmx/boms/${_vcmxBbEditId}`, 'PATCH', upd);
      toast('VCMX BOM updated','success');
    } else {
      await api('/api/vcmx/boms', 'POST', body);
      toast('VCMX BOM created','success');
    }
    bootstrap.Collapse.getInstance(document.getElementById('vcmx-bom-builder-panel'))?.hide();
    vcmxBomTabReset();
    await vcmxBomTabLoad();
  }catch(e){ alert('Save failed: '+(e.message||e)); }
}

// ── VCMX-Lam station UI ──────────────────────────────────────
let _vcmxLamCurrent = null;
async function vcmxLamLoad(){
  let open = [];
  try{ open = await api('/api/vcmx/batches?status=open'); }catch{}
  const tb = document.getElementById('vcmx-lam-tbody');
  if(!open.length){
    tb.innerHTML = '<tr><td colspan="7" class="text-center text-muted py-3">No open VCMX batches. Create one from Planning → VCMX (Make-to-Stock).</td></tr>';
  } else {
    const prioLbl = p => p===1?'<span class="badge bg-danger">P1</span>':p===2?'<span class="badge bg-warning text-dark">P2</span>':'<span class="badge bg-success">P3</span>';
    tb.innerHTML = open.map(r=>`
      <tr>
        <td class="small fw-semibold">${r.batch_number}</td>
        <td>${r.sku_code} <span class="text-muted small">${r.sku_name||''}</span></td>
        <td class="text-end fw-semibold">${r.quantity}</td>
        <td>${prioLbl(r.priority)}</td>
        <td class="small">${r.glue_qty_per_panel||0}</td>
        <td class="small text-muted">${(r.created_at||'').slice(0,16).replace('T',' ')}</td>
        <td class="text-end">
          <button class="btn btn-xs btn-success" onclick='vcmxLamOpenComplete(${JSON.stringify(r).replace(/'/g,"&apos;")})'>
            <i class="bi bi-check2 me-1"></i>Complete
          </button>
        </td>
      </tr>`).join('');
  }
  // History tail
  let done = [];
  try{ done = await api('/api/vcmx/batches?status=completed'); }catch{}
  const hb = document.getElementById('vcmx-lam-history');
  if(!done.length){
    hb.innerHTML = '<tr><td colspan="8" class="text-center text-muted py-3">No recent completions.</td></tr>';
  } else {
    hb.innerHTML = done.slice(0,15).map(r=>`
      <tr>
        <td class="small">${r.batch_number}</td>
        <td>${r.sku_code}</td>
        <td class="text-end">${r.quantity}</td>
        <td class="text-end text-muted" colspan="4">—</td>
        <td class="small text-muted">${(r.created_at||'').slice(0,16).replace('T',' ')}</td>
      </tr>`).join('');
  }
  vcmxLamRefreshBadge();
}

async function vcmxLamOpenComplete(batch){
  _vcmxLamCurrent = batch;
  // Fetch cumulative produced so far across prior partials
  let already = 0;
  try{
    const events = await api(`/api/vcmx/batches/${batch.id}/events`);
    already = (events||[]).reduce((a,e)=>a+Number(e.qty_produced||0), 0);
  }catch{}
  const remaining = Math.max(0, Number(batch.quantity) - already);
  document.getElementById('vcmx-lam-c-summary').innerHTML =
    `<b>Batch ${batch.batch_number}</b> — ${batch.sku_code} ${batch.sku_name||''}<br>
     Order qty: <b>${batch.quantity}</b> · Already produced: <b>${already}</b> · Remaining: <b class="${remaining>0?'text-warning':'text-success'}">${remaining}</b> · BOM glue/panel: ${batch.glue_qty_per_panel||0}`;
  document.getElementById('vcmx-lam-c-qty').value = remaining || batch.quantity;
  document.getElementById('vcmx-lam-c-ncg').value = '0';
  document.getElementById('vcmx-lam-c-glue').value = '';
  document.getElementById('vcmx-lam-c-op').value = '';
  document.getElementById('vcmx-lam-c-notes').value = '';
  document.getElementById('vcmx-lam-c-close-short').checked = false;
  new bootstrap.Modal(document.getElementById('vcmxLamCompleteModal')).show();
}

async function vcmxLamSubmitComplete(){
  if(!_vcmxLamCurrent) return;
  const qty = Number(document.getElementById('vcmx-lam-c-qty').value||0);
  if(qty<=0){ alert('Qty produced must be positive'); return; }
  const body = {
    qty_produced: qty,
    qty_ncg: Number(document.getElementById('vcmx-lam-c-ncg').value||0),
    operator: document.getElementById('vcmx-lam-c-op').value||'',
    notes:    document.getElementById('vcmx-lam-c-notes').value||'',
    close_short: document.getElementById('vcmx-lam-c-close-short').checked,
  };
  const glue = document.getElementById('vcmx-lam-c-glue').value;
  if(glue!=='') body.glue_actual_kg = Number(glue);
  try{
    const r = await api(`/api/vcmx/batches/${_vcmxLamCurrent.id}/complete`, 'POST', body);
    bootstrap.Modal.getInstance(document.getElementById('vcmxLamCompleteModal'))?.hide();
    const tag = r.is_final ? 'Final' : `Partial (${r.cumulative_produced}/${r.cumulative_produced+r.qty_remaining})`;
    toast(`${tag}: ${r.qty_produced} panels @ ฿${r.unit_cost.toFixed(2)}/ea → lot ${r.output_lot_code}`,'success');
    vcmxLamLoad();
  }catch(e){ alert('Complete failed: '+(e.message||e)); }
}

async function vcmxLamRefreshBadge(){
  try{
    const open = await api('/api/vcmx/batches?status=open');
    const bd = document.getElementById('nav-vcmx-lam-badge');
    if(bd){ bd.textContent = open.length; bd.classList.toggle('d-none', open.length===0); }
  }catch{}
}
setTimeout(vcmxLamRefreshBadge, 8000);
setInterval(vcmxLamRefreshBadge, 300000);




// ════════════════════════════════════════════════════════════
// Material Shortfalls + FC Material Requests + FC Hub
// ════════════════════════════════════════════════════════════
// ══════════════════════════════════════════════════════════════
// PLANNING — MATERIAL SHORTFALLS
// ══════════════════════════════════════════════════════════════
let _msfRows=[], _msfSelected=new Set();
function _msfNum(n){return n==null||n===''?'—':Number(n).toLocaleString(undefined,{maximumFractionDigits:2});}
function _msfTHB(n){return n==null||n===''?'—':`<span style="color:#15803d;font-weight:600">฿${_msfNum(n)}</span>`;}
function _msfTypeBadge(t){
  const colors={board:'primary',veneer:'success',glue_formula:'warning',glue_component:'warning',consumable:'info'};
  return `<span class="badge bg-${colors[t]||'secondary'}-subtle text-${colors[t]||'secondary'} border border-${colors[t]||'secondary'}" style="font-size:.65rem">${(t||'').toUpperCase()}</span>`;
}
// Map a row → primary status badge reflecting where the material sits in the
// procurement pipeline. SHORT/no PR yet = red. LOW buffer = orange. Any open
// PR overrides with its own lifecycle colour. OK = green.
function _msfStatusBadge(r){
  if(r.latest_pr_status){
    const m={NEW:['secondary','Purchase Requested','bi-inbox'],
             APPROVED:['info','Approved','bi-check2-circle'],
             PO_ISSUED:['primary','PO Issued','bi-file-earmark-text'],
             ORDERED:['primary','PO Issued','bi-file-earmark-text'],
             AWAITING_ARRIVAL:['warning text-dark','Awaiting Materials','bi-hourglass-split']};
    const x=m[r.latest_pr_status]||['secondary',r.latest_pr_status,'bi-circle'];
    return `<span class="badge bg-${x[0]}"><i class="bi ${x[2]} me-1"></i>${x[1]}</span>`;
  }
  if(r.status==='SHORT')   return '<span class="badge bg-danger"><i class="bi bi-exclamation-triangle me-1"></i>SHORT — Not Requested</span>';
  if(r.status==='LOW')     return '<span class="badge text-white" style="background:#ea580c"><i class="bi bi-exclamation-circle me-1"></i>LOW Buffer — Safety Stock</span>';
  return '<span class="badge bg-success"><i class="bi bi-check2-circle me-1"></i>OK</span>';
}
async function msfLoad(){
  const types=[];
  if(document.getElementById('msf-type-board').checked) types.push('board');
  if(document.getElementById('msf-type-veneer').checked) types.push('veneer');
  if(document.getElementById('msf-type-glue').checked) types.push('glue_component','glue_formula');
  if(document.getElementById('msf-type-cons').checked) types.push('consumable');
  if(!types.length){
    document.getElementById('msf-tbody').innerHTML='<tr><td colspan="11" class="text-center text-muted py-3">Pick at least one material type above.</td></tr>';
    return;
  }
  try{
    const data = await api('/api/planning/material-shortfalls?types='+encodeURIComponent(types.join(',')));
    _msfRows = (data && Array.isArray(data.rows)) ? data.rows : [];
    _msfSelected.clear();
    msfRenderKpi(data.summary || {});
    msfRender();
    // Update sidebar badge
    const shortCount=_msfRows.filter(r=>r.status==='SHORT').length;
    const bd=document.getElementById('nav-shortfall-badge');
    if(bd){ bd.textContent=shortCount; bd.classList.toggle('d-none', shortCount===0); }
  }catch(e){
    document.getElementById('msf-tbody').innerHTML=`<tr><td colspan="11" class="text-danger small p-3">${e.message||e}</td></tr>`;
  }
}
function msfRenderKpi(s){
  const tally={NEW:0,APPROVED:0,PO_ISSUED:0,AWAITING_ARRIVAL:0};
  _msfRows.forEach(r=>{
    if(r.status!=='PR_PENDING' || !r.latest_pr_status) return;
    const k = r.latest_pr_status==='ORDERED' ? 'PO_ISSUED' : r.latest_pr_status;
    if(tally[k]!=null) tally[k]++;
  });
  document.getElementById('msf-kpi').innerHTML=[
    {l:'Short — Not Requested', v:s.materials_short||0,        bg:'danger', ico:'bi-exclamation-triangle'},
    {l:'Low Buffer (Safety)',   v:s.materials_low||0,          bg:'warning text-dark', ico:'bi-exclamation-circle',
                                 style:'border-color:#ea580c'},
    {l:'Purchase Requested',    v:tally.NEW,                   bg:'secondary',ico:'bi-inbox'},
    {l:'Approved / PO Issued',  v:tally.APPROVED+tally.PO_ISSUED, bg:'primary',ico:'bi-file-earmark-text'},
    {l:'Awaiting Arrival',      v:tally.AWAITING_ARRIVAL,      bg:'warning',ico:'bi-hourglass-split'},
    {l:'Shortfall Value',       v:'฿'+_msfNum(s.total_shortfall_value_thb||0), bg:'dark', ico:'bi-cash-stack'},
  ].map(c=>`<div class="col-md-2 col-6"><div class="card border-${c.bg.split(' ')[0]}" style="${c.style||''}"><div class="card-body py-2 px-3">
    <div class="small text-muted" style="font-size:.7rem"><i class="bi ${c.ico} me-1"></i>${c.l}</div>
    <div class="fs-5 fw-semibold">${c.v}</div></div></div></div>`).join('');
}
function msfRender(){
  const statusFilter=document.getElementById('msf-status').value;
  const q=(document.getElementById('msf-filter').value||'').toLowerCase();
  let rows=_msfRows;
  if(statusFilter==='ACTIVE')         rows=rows.filter(r=>r.status==='SHORT' || r.status==='PR_PENDING');
  else if(statusFilter==='ACTIVE+LOW')rows=rows.filter(r=>r.status==='SHORT' || r.status==='PR_PENDING' || r.status==='LOW');
  else if(statusFilter==='SHORT')     rows=rows.filter(r=>r.status==='SHORT');
  else if(statusFilter==='LOW')       rows=rows.filter(r=>r.status==='LOW');
  else if(statusFilter==='PR_PENDING')rows=rows.filter(r=>r.status==='PR_PENDING');
  if(q) rows=rows.filter(r=>JSON.stringify(r).toLowerCase().includes(q));
  const tb=document.getElementById('msf-tbody');
  if(!rows.length){
    tb.innerHTML='<tr><td colspan="11" class="text-center text-muted py-4"><i class="bi bi-check2-circle me-1 text-success"></i>No materials match the filter — all required stock is in hand or fully resolved.</td></tr>';
    msfUpdateBulkBtn(); return;
  }
  // Group-by-PO view? — invert the data: one section per sales PO with its
  // short materials nested under it. Planners can tick whole POs (boards +
  // veneers) and request them in one batch.
  const view = (document.querySelector('input[name="msf-view"]:checked')?.value) || 'material';
  if(view === 'po') return _msfRenderByPO(rows);

  tb.innerHTML=rows.map(r=>{
    // Checkboxes only for rows still needing a PR (SHORT or LOW-safety-stock)
    const checkable = r.status==='SHORT' || r.status==='LOW';
    const checked = _msfSelected.has(r.material_id) ? 'checked' : '';
    const cb = checkable ? `<input type="checkbox" class="msf-cb" data-mid="${r.material_id}" ${checked} onchange="msfToggleOne(${r.material_id}, this.checked)">` : '';
    const mp = Number(r.max_priority || 2);
    const mpBadge = mp===1
      ? '<span class="badge bg-danger me-1" title="Driven by an urgent PO">P1</span>'
      : (mp===3 ? '<span class="badge bg-success me-1">P3</span>' : '');
    const poBadges = (r.contributing_pos||[]).slice(0,3).map(p=>{
      const pp = Number(p.priority||2);
      const cls = pp===1?'bg-danger text-white':pp===3?'bg-success text-white':'bg-light text-dark border';
      return `<span class="badge ${cls} me-1" title="P${pp} · ${p.customer||''} · due ${p.delivery_date||'—'}" style="font-size:.65rem">${p.po_number||('#'+p.po_id)}</span>`;
    }).join('') + (r.contributing_pos && r.contributing_pos.length>3 ? `<span class="text-muted small">+${r.contributing_pos.length-3} more</span>`:'');

    // Status column — primary badge + supplementary detail
    let statusCell = _msfStatusBadge(r);
    if(r.latest_pr_status){
      const onOrder = `<div class="small text-muted mt-1"><i class="bi bi-truck me-1"></i>${_msfNum(r.open_pr_qty)} ${r.uom||''} on order</div>`;
      const eta = r.pr_eta ? `<div class="small"><span class="badge bg-warning text-dark" style="font-size:.65rem"><i class="bi bi-calendar-event me-1"></i>ETA ${r.pr_eta}</span></div>` : '';
      statusCell += onOrder + eta;
    }

    // Action column — Request button when material is SHORT or LOW (safety stock).
    // After request, show the PR number + when it was sent (read-only).
    let actionCell;
    if(r.status==='SHORT'){
      actionCell = `<button class="btn btn-xs btn-danger" onclick='msfOpenPR(${JSON.stringify(r).replace(/'/g,"&apos;")})'><i class="bi bi-send me-1"></i>Request</button>`;
    }else if(r.status==='LOW'){
      actionCell = `<button class="btn btn-xs text-white" style="background:#ea580c" title="Top up safety stock — buffer below 20%" onclick='msfOpenPR(${JSON.stringify(r).replace(/'/g,"&apos;")})'><i class="bi bi-shield-plus me-1"></i>Top Up</button>`;
    }else if(r.latest_pr_number){
      const when = (r.latest_pr_requested_at||'').slice(0,16).replace('T',' ');
      actionCell =
        `<div class="small fw-semibold">${r.latest_pr_number}</div>
         <div class="small text-muted"><i class="bi bi-clock-history me-1"></i>${when||'—'}</div>
         ${r.open_pr_count>1?`<div class="small text-muted">+${r.open_pr_count-1} other PR(s)</div>`:''}`;
    }else{
      actionCell = '<span class="text-muted small">—</span>';
    }

    return `<tr>
      <td>${cb}</td>
      <td>${mpBadge}${_msfTypeBadge(r.material_type)} <b>${r.material_code||''}</b> ${r.material_name||''}</td>
      <td class="text-end">${_msfNum(r.on_hand)} <span class="text-muted small">${r.uom||''}</span></td>
      <td class="text-end fw-semibold">${_msfNum(r.required)}</td>
      <td class="text-end ${r.open_pr_qty>0?'text-warning':'text-muted'}">${_msfNum(r.open_pr_qty)}</td>
      <td class="text-end ${r.shortfall>0?'text-danger fw-bold':'text-muted'}">${r.shortfall>0?_msfNum(r.shortfall):'—'}</td>
      <td class="text-end">${r.shortfall_cost_thb>0?_msfTHB(r.shortfall_cost_thb):'—'}</td>
      <td class="small">${r.earliest_delivery||'—'}</td>
      <td>${poBadges||'<span class="text-muted small">—</span>'}</td>
      <td>${statusCell}</td>
      <td class="text-end" style="white-space:nowrap">${actionCell}</td>
    </tr>`;
  }).join('');
  msfUpdateBulkBtn();
}
// PO-grouped renderer — each open sales PO becomes a section, with its short
// boards + veneers listed under it. A master "tick all in this PO" checkbox
// at the top of each section bulk-selects every requestable material for
// that PO. Materials shared across multiple POs appear under each.
function _msfRenderByPO(rows){
  const tb = document.getElementById('msf-tbody');
  // Build PO buckets
  const buckets = {};   // poKey -> {po, items: [...]}
  rows.forEach(r => {
    (r.contributing_pos || []).forEach(p => {
      const k = p.po_id ? `po:${p.po_id}` : `po:${p.po_number||'unknown'}`;
      if(!buckets[k]) buckets[k] = { po: p, items: [], totalCost: 0 };
      buckets[k].items.push(r);
      buckets[k].totalCost += Number(r.shortfall_cost_thb || 0);
    });
  });
  const keys = Object.keys(buckets).sort((a,b)=>{
    // Priority 1 first, then earliest delivery date
    const pa = Number(buckets[a].po.priority || 2);
    const pb = Number(buckets[b].po.priority || 2);
    if(pa !== pb) return pa - pb;
    const ad = buckets[a].po.delivery_date || '';
    const bd = buckets[b].po.delivery_date || '';
    return (ad===bd) ? 0 : (ad<bd ? -1 : 1);
  });
  if(!keys.length){
    tb.innerHTML = '<tr><td colspan="11" class="text-center text-muted py-4">No open POs with shortfalls.</td></tr>';
    msfUpdateBulkBtn(); return;
  }
  tb.innerHTML = keys.map(k => {
    const { po, items, totalCost } = buckets[k];
    // Count requestable items inside this PO (SHORT or LOW only)
    const reqable = items.filter(i => i.status==='SHORT' || i.status==='LOW');
    const allTicked = reqable.length>0 && reqable.every(i => _msfSelected.has(i.material_id));
    const partTicked = reqable.some(i => _msfSelected.has(i.material_id)) && !allTicked;
    const masterCb = reqable.length
      ? `<input type="checkbox" class="msf-po-master" data-po-key="${k}" ${allTicked?'checked':''} onchange="msfTogglePO('${k}',this.checked)" title="${allTicked?'untick':'tick'} all materials for this PO">`
      : '';
    const prio = Number(po.priority || 2);
    const prioCol = prio===1?'danger':prio===2?'warning text-dark':'success';
    const prioLbl = prio===1?'P1 Urgent':prio===2?'P2':'P3';
    const headerBg = prio===1 ? '#fee2e2' : '#dbeafe';
    const header = `<tr style="background:${headerBg}">
      <td>${masterCb}</td>
      <td colspan="10">
        <span class="badge bg-${prioCol} me-2">${prioLbl}</span>
        <b class="text-primary">${po.po_number||('#'+po.po_id)}</b>
        <span class="text-muted ms-1">${po.customer||''}</span>
        <span class="ms-2 small">due <b>${po.delivery_date||'—'}</b></span>
        <span class="badge bg-light text-dark border ms-2">${items.length} material(s) needed</span>
        ${totalCost>0 ? `<span class="ms-2 small">shortfall: ${_msfTHB(totalCost)}</span>`:''}
        ${partTicked ? '<span class="badge bg-warning text-dark ms-2">partial selection</span>':''}
      </td>
    </tr>`;
    const childRows = items.map(r => {
      const checkable = r.status==='SHORT' || r.status==='LOW';
      const checked = _msfSelected.has(r.material_id) ? 'checked' : '';
      const cb = checkable
        ? `<input type="checkbox" class="msf-cb msf-po-child" data-mid="${r.material_id}" data-po-key="${k}" ${checked} onchange="msfToggleOne(${r.material_id}, this.checked)">`
        : '';
      const poBadges = (r.contributing_pos||[]).filter(p=>String(p.po_id)!==String(po.po_id)).slice(0,2).map(p=>
        `<span class="badge bg-light text-dark border me-1" title="also for ${p.customer||''}" style="font-size:.6rem">also ${p.po_number||'#'+p.po_id}</span>`
      ).join('');
      let statusCell = _msfStatusBadge(r);
      if(r.latest_pr_status){
        const onOrder = `<div class="small text-muted mt-1"><i class="bi bi-truck me-1"></i>${_msfNum(r.open_pr_qty)} ${r.uom||''} on order</div>`;
        const eta = r.pr_eta ? `<div class="small"><span class="badge bg-warning text-dark" style="font-size:.65rem"><i class="bi bi-calendar-event me-1"></i>ETA ${r.pr_eta}</span></div>` : '';
        statusCell += onOrder + eta;
      }
      let actionCell;
      if(r.status==='SHORT'){
        actionCell = `<button class="btn btn-xs btn-danger" onclick='msfOpenPR(${JSON.stringify(r).replace(/'/g,"&apos;")})'><i class="bi bi-send me-1"></i>Request</button>`;
      }else if(r.status==='LOW'){
        actionCell = `<button class="btn btn-xs text-white" style="background:#ea580c" onclick='msfOpenPR(${JSON.stringify(r).replace(/'/g,"&apos;")})'><i class="bi bi-shield-plus me-1"></i>Top Up</button>`;
      }else if(r.latest_pr_number){
        const when = (r.latest_pr_requested_at||'').slice(0,16).replace('T',' ');
        actionCell = `<div class="small fw-semibold">${r.latest_pr_number}</div><div class="small text-muted"><i class="bi bi-clock-history me-1"></i>${when||'—'}</div>`;
      }else{
        actionCell = '<span class="text-muted small">—</span>';
      }
      return `<tr>
        <td>${cb}</td>
        <td>${_msfTypeBadge(r.material_type)} <b>${r.material_code||''}</b> ${r.material_name||''}</td>
        <td class="text-end">${_msfNum(r.on_hand)} <span class="text-muted small">${r.uom||''}</span></td>
        <td class="text-end fw-semibold">${_msfNum(r.required)}</td>
        <td class="text-end ${r.open_pr_qty>0?'text-warning':'text-muted'}">${_msfNum(r.open_pr_qty)}</td>
        <td class="text-end ${r.shortfall>0?'text-danger fw-bold':'text-muted'}">${r.shortfall>0?_msfNum(r.shortfall):'—'}</td>
        <td class="text-end">${r.shortfall_cost_thb>0?_msfTHB(r.shortfall_cost_thb):'—'}</td>
        <td class="small">${r.earliest_delivery||'—'}</td>
        <td>${poBadges||'<span class="text-muted small">—</span>'}</td>
        <td>${statusCell}</td>
        <td class="text-end" style="white-space:nowrap">${actionCell}</td>
      </tr>`;
    }).join('');
    return header + childRows;
  }).join('');
  msfUpdateBulkBtn();
}

// Toggle every requestable material of one PO bucket on/off
function msfTogglePO(poKey, checked){
  document.querySelectorAll(`.msf-po-child[data-po-key="${poKey}"]`).forEach(cb=>{
    cb.checked = checked;
    const mid = Number(cb.dataset.mid);
    if(checked) _msfSelected.add(mid); else _msfSelected.delete(mid);
  });
  msfUpdateBulkBtn();
  // Re-render to refresh the master checkbox state on other POs that share materials
  msfRender();
}

function msfToggleOne(mid, checked){
  if(checked) _msfSelected.add(Number(mid)); else _msfSelected.delete(Number(mid));
  msfUpdateBulkBtn();
}
function msfToggleAll(checked){
  document.querySelectorAll('.msf-cb').forEach(cb=>{
    cb.checked=checked;
    const mid=Number(cb.dataset.mid);
    if(checked) _msfSelected.add(mid); else _msfSelected.delete(mid);
  });
  msfUpdateBulkBtn();
}
function msfUpdateBulkBtn(){
  const btn=document.getElementById('msf-bulk-btn');
  const cnt=document.getElementById('msf-bulk-count');
  cnt.textContent=_msfSelected.size;
  btn.disabled=_msfSelected.size===0;
}
function msfOpenPR(r){
  document.getElementById('msf-pr-material-id').value=r.material_id;
  // For LOW rows we suggest the top-up to clear the safety-stock buffer; for
  // SHORT rows we suggest the full shortfall.
  const suggested = (r.suggested_request_qty != null && r.suggested_request_qty > 0)
    ? r.suggested_request_qty
    : (r.shortfall || '');
  document.getElementById('msf-pr-qty').value = suggested;
  document.getElementById('msf-pr-uom').textContent = r.uom||'';
  document.getElementById('msf-pr-needed').value = r.earliest_delivery || '';
  document.getElementById('msf-pr-supplier').value = '';
  const poStr=(r.contributing_pos||[]).map(p=>p.po_number||('#'+p.po_id)).slice(0,5).join(', ');
  const tag = r.status==='LOW' ? 'Safety-stock top-up' : 'Shortfall request';
  document.getElementById('msf-pr-notes').value = `${tag} for ${r.material_name}.${poStr?' Affects POs: '+poStr+'.':''}`;
  let ctx = `<b>${r.material_code||''} ${r.material_name}</b> — On hand <b>${_msfNum(r.on_hand)}</b>, Required <b>${_msfNum(r.required)}</b>, Open PRs <b>${_msfNum(r.open_pr_qty)}</b>`;
  if(r.status==='LOW'){
    ctx += `, Buffer <b style="color:#ea580c">${_msfNum(r.buffer_qty)} ${r.uom||''}</b> (under safety threshold ${_msfNum(r.low_threshold_qty)})`;
  }else{
    ctx += `, Short <b class="text-danger">${_msfNum(r.shortfall)} ${r.uom||''}</b>`;
  }
  document.getElementById('msf-pr-context').innerHTML = ctx;
  document.getElementById('msf-pr-hint').innerHTML =
    r.status==='LOW'
      ? 'Suggested qty brings the safety buffer back above 20%. <b>Type a larger qty to also build extra safety stock.</b>'
      : 'Auto-filled with the full shortfall. <b>You can increase this to also build safety stock</b> (e.g. order 1,200 when shortfall is 1,000).';
  new bootstrap.Modal(document.getElementById('msfPRModal')).show();
}
async function msfSubmitPR(){
  const mid=Number(document.getElementById('msf-pr-material-id').value);
  const r=_msfRows.find(x=>x.material_id===mid) || {};
  const qty=Number(document.getElementById('msf-pr-qty').value||0);
  if(!mid || qty<=0){ alert('Quantity must be greater than zero.'); return; }
  const reqType = (r.material_type==='consumable') ? 'CONSUMABLE' : 'RAW_MATERIAL';
  const body={
    request_type: reqType,
    material_id:  mid,
    qty_requested: qty,
    uom: r.uom||'',
    priority: Number(document.getElementById('msf-pr-priority').value||2),
    needed_by: document.getElementById('msf-pr-needed').value||null,
    suggested_supplier: document.getElementById('msf-pr-supplier').value,
    notes: document.getElementById('msf-pr-notes').value,
    source_po_id: (r.contributing_pos && r.contributing_pos[0]) ? r.contributing_pos[0].po_id : null,
  };
  try{
    await api('/api/purchase-requests', 'POST', body);
    bootstrap.Modal.getInstance(document.getElementById('msfPRModal'))?.hide();
    toast('Purchase request sent to Purchasing.');
    msfLoad();
  }catch(e){ alert('Request failed: '+(e.message||e)); }
}
async function msfBulkRequest(){
  if(_msfSelected.size===0) return;
  // Prompt for a buffer % so planners can build safety stock above the bare
  // shortfall. Default 0 (request the exact shortfall).
  const bufRaw = prompt(
    `Send ${_msfSelected.size} purchase request(s) to Purchasing.\n\n`+
    `Add a buffer above the shortfall to build safety stock?\n`+
    `Enter the percentage (0 = exact, 10 = +10%, 25 = +25%):`,
    '0'
  );
  if(bufRaw === null) return;
  const bufPct = Math.max(0, Number(bufRaw)||0);
  const selected=_msfRows.filter(r=>_msfSelected.has(r.material_id) &&
    ((r.suggested_request_qty||r.shortfall) > 0));
  let ok=0, fail=0;
  for(const r of selected){
    const reqType = (r.material_type==='consumable') ? 'CONSUMABLE' : 'RAW_MATERIAL';
    try{
      const base = r.suggested_request_qty || r.shortfall;
      const qty  = Math.round(base * (1 + bufPct/100) * 1000) / 1000;
      const tag  = r.status==='LOW' ? 'Bulk safety-stock top-up' : 'Bulk shortfall request';
      const bufNote = bufPct>0 ? ` +${bufPct}% safety buffer (${qty} vs shortfall ${base})` : '';
      await api('/api/purchase-requests', 'POST', {
        request_type: reqType, material_id: r.material_id,
        qty_requested: qty, uom: r.uom||'',
        priority: r.status==='SHORT' ? 1 : 3,
        needed_by: r.earliest_delivery||null,
        suggested_supplier: '',
        notes: `${tag} for ${r.material_name}.${bufNote} POs: ${(r.contributing_pos||[]).map(p=>p.po_number).slice(0,5).join(', ')}.`,
        source_po_id: (r.contributing_pos && r.contributing_pos[0]) ? r.contributing_pos[0].po_id : null,
      });
      ok++;
    }catch(e){ fail++; console.error('PR failed for', r.material_name, e); }
  }
  alert(`Created ${ok} purchase request(s)${fail?`; ${fail} failed`:''}${bufPct>0?` with +${bufPct}% buffer.`:'.'}`);
  msfLoad();
}

// ── Ad-hoc PR (no PO link, stock building) ──────────────────────
let _msfAdhocMaterials = [];
let _msfAdhocLineSeq = 0;

function _msfAdhocReqType(matType){
  return /consumable|packing|adhesive/i.test(matType||'') ? 'CONSUMABLE' : 'RAW_MATERIAL';
}

function _msfAdhocLineTpl(idx){
  const opts = (_msfAdhocMaterials||[])
    .filter(m => /board|veneer|consumable|adhesive|packing/i.test(m.type||''))
    .sort((a,b)=>(a.name||'').localeCompare(b.name||''))
    .map(m=>`<option value="${m.id}" data-unit="${m.unit||''}" data-type="${m.type||''}">[${(m.type||'').toUpperCase()}] ${m.code||''} — ${m.name}</option>`)
    .join('');
  return `
  <div class="card mb-2 msf-adhoc-line" data-idx="${idx}">
    <div class="card-body py-2">
      <div class="d-flex align-items-center mb-2">
        <span class="badge bg-secondary me-2">Line ${idx+1}</span>
        <div class="flex-grow-1 small text-muted">Material + total qty, plus optional split deliveries.</div>
        <button class="btn btn-xs btn-outline-danger" title="Remove this line" onclick="msfAdhocRemoveLine(${idx})">
          <i class="bi bi-x-lg"></i>
        </button>
      </div>
      <div class="row g-2">
        <div class="col-md-6">
          <label class="form-label small fw-semibold mb-1">Material *</label>
          <select class="form-select form-select-sm msf-l-mat" onchange="_msfAdhocMatChange(${idx})">
            <option value="">— pick a board / veneer / consumable —</option>${opts}
          </select>
          <div class="form-text small text-muted msf-l-info"></div>
        </div>
        <div class="col-md-2">
          <label class="form-label small fw-semibold mb-1">Total Qty *</label>
          <input type="number" class="form-control form-control-sm msf-l-qty" step="0.01" min="0" oninput="_msfAdhocRecalc(${idx})">
        </div>
        <div class="col-md-1">
          <label class="form-label small fw-semibold mb-1">UoM</label>
          <input class="form-control form-control-sm msf-l-uom" placeholder="pcs">
        </div>
        <div class="col-md-3">
          <label class="form-label small fw-semibold mb-1">Priority</label>
          <select class="form-select form-select-sm msf-l-prio">
            <option value="">use default</option>
            <option value="1">1 — High</option>
            <option value="2">2 — Medium</option>
            <option value="3">3 — Low</option>
          </select>
        </div>
      </div>

      <div class="d-flex justify-content-between align-items-center mt-3 mb-1">
        <div class="small fw-semibold text-muted">
          <i class="bi bi-truck me-1"></i>Split Deliveries
          <span class="text-muted ms-2 msf-l-split-sum" style="font-weight:normal"></span>
        </div>
        <button class="btn btn-xs btn-outline-secondary" onclick="msfAdhocAddSplit(${idx})">
          <i class="bi bi-plus me-1"></i>Add Split
        </button>
      </div>
      <div class="msf-l-splits"></div>
      <div class="form-text small">Leave empty for one delivery. Splits must sum to ≤ line qty.</div>
    </div>
  </div>`;
}

function _msfAdhocSplitTpl(){
  return `
  <div class="row g-1 align-items-end msf-split mb-1">
    <div class="col-md-3"><input type="number" class="form-control form-control-sm msf-s-qty" placeholder="Qty" step="0.01" min="0" oninput="msfAdhocRecalcAll()"></div>
    <div class="col-md-3"><input type="date" class="form-control form-control-sm msf-s-eta" title="Planned arrival"></div>
    <div class="col-md-3"><input class="form-control form-control-sm msf-s-carrier" placeholder="Carrier (optional)"></div>
    <div class="col-md-2"><input class="form-control form-control-sm msf-s-notes" placeholder="Note"></div>
    <div class="col-md-1 text-end"><button class="btn btn-xs btn-outline-danger" onclick="this.closest('.msf-split').remove(); msfAdhocRecalcAll();"><i class="bi bi-x"></i></button></div>
  </div>`;
}

function msfAdhocAddLine(){
  const idx = _msfAdhocLineSeq++;
  document.getElementById('msf-adhoc-lines-container').insertAdjacentHTML('beforeend', _msfAdhocLineTpl(idx));
}
function msfAdhocRemoveLine(idx){
  if(document.querySelectorAll('.msf-adhoc-line').length<=1){ alert('At least one line required.'); return; }
  document.querySelector(`.msf-adhoc-line[data-idx="${idx}"]`)?.remove();
}
function msfAdhocAddSplit(idx){
  const line = document.querySelector(`.msf-adhoc-line[data-idx="${idx}"]`);
  if(!line) return;
  line.querySelector('.msf-l-splits').insertAdjacentHTML('beforeend', _msfAdhocSplitTpl());
  _msfAdhocRecalc(idx);
}
function _msfAdhocMatChange(idx){
  const line = document.querySelector(`.msf-adhoc-line[data-idx="${idx}"]`);
  if(!line) return;
  const sel = line.querySelector('.msf-l-mat');
  const o = sel.options[sel.selectedIndex];
  if(o){
    const u = o.getAttribute('data-unit')||'';
    const t = o.getAttribute('data-type')||'';
    if(!line.querySelector('.msf-l-uom').value) line.querySelector('.msf-l-uom').value = u;
    line.querySelector('.msf-l-info').textContent = t ? `Type: ${t}` : '';
  }
}
function _msfAdhocRecalc(idx){
  const line = document.querySelector(`.msf-adhoc-line[data-idx="${idx}"]`);
  if(!line) return;
  const total = Number(line.querySelector('.msf-l-qty').value||0);
  let sum = 0;
  line.querySelectorAll('.msf-s-qty').forEach(i=> sum += Number(i.value||0));
  const lbl = line.querySelector('.msf-l-split-sum');
  if(sum>0){
    const ok = sum <= total + 0.0001;
    lbl.innerHTML = `· allocated <b class="${ok?'text-success':'text-danger'}">${sum}</b> / ${total||'—'}`+
                    (ok ? '' : ' <span class="badge bg-danger">over</span>');
  } else { lbl.textContent = ''; }
}
function msfAdhocRecalcAll(){
  document.querySelectorAll('.msf-adhoc-line').forEach(el=>{
    _msfAdhocRecalc(Number(el.getAttribute('data-idx')));
  });
}

async function msfOpenAdhocPR(){
  document.getElementById('msf-adhoc-priority').value = '3';
  document.getElementById('msf-adhoc-needed').value = '';
  document.getElementById('msf-adhoc-supplier').value = '';
  document.getElementById('msf-adhoc-notes').value = '';
  if(!_msfAdhocMaterials.length){
    try{ _msfAdhocMaterials = await api('/api/materials'); }catch{ _msfAdhocMaterials = []; }
  }
  _msfAdhocLineSeq = 0;
  document.getElementById('msf-adhoc-lines-container').innerHTML = '';
  msfAdhocAddLine();
  new bootstrap.Modal(document.getElementById('msfAdhocModal')).show();
}

async function msfSubmitAdhoc(){
  const lines = [];
  let bad = '';
  document.querySelectorAll('.msf-adhoc-line').forEach(el=>{
    const sel = el.querySelector('.msf-l-mat');
    const mid = Number(sel.value||0);
    const qty = Number(el.querySelector('.msf-l-qty').value||0);
    if(!mid || qty<=0){ bad = 'Each line needs a material and positive qty.'; return; }
    const matType = sel.options[sel.selectedIndex]?.getAttribute('data-type')||'';
    const splits = [];
    let sum = 0;
    el.querySelectorAll('.msf-split').forEach(s=>{
      const sq = Number(s.querySelector('.msf-s-qty').value||0);
      if(sq>0){
        splits.push({
          planned_qty: sq,
          planned_arrival: s.querySelector('.msf-s-eta').value||null,
          carrier: s.querySelector('.msf-s-carrier').value||'',
          notes:   s.querySelector('.msf-s-notes').value||'',
        });
        sum += sq;
      }
    });
    if(sum > qty + 0.0001){ bad = `Splits sum (${sum}) exceeds line qty (${qty}).`; return; }
    const prioRaw = el.querySelector('.msf-l-prio').value;
    lines.push({
      request_type: _msfAdhocReqType(matType),
      material_id:  mid,
      qty_requested: qty,
      uom: el.querySelector('.msf-l-uom').value||'',
      priority: prioRaw ? Number(prioRaw) : null,
      // Tag + per-line note left null so bulk creator falls back to header notes
      notes: null,
      splits,
    });
  });
  if(bad){ alert(bad); return; }
  if(!lines.length){ alert('Add at least one material line.'); return; }
  const userNotes = document.getElementById('msf-adhoc-notes').value||'';
  const body = {
    priority:  Number(document.getElementById('msf-adhoc-priority').value||3),
    needed_by: document.getElementById('msf-adhoc-needed').value||null,
    suggested_supplier: document.getElementById('msf-adhoc-supplier').value||'',
    notes: (`[Stock-building, no PO] ${userNotes}`).trim(),
    lines,
  };
  try{
    const res = await api('/api/purchase-requests/bulk', 'POST', body);
    bootstrap.Modal.getInstance(document.getElementById('msfAdhocModal'))?.hide();
    toast(`Created ${res.count} stock-building PR(s) — ${res.group_number}`,'success');
    msfLoad();
  }catch(e){ alert('Failed: '+(e.message||e)); }
}

// Background poll so sidebar badge updates without visiting the page
async function msfRefreshBadge(){
  try{
    const data = await api('/api/planning/material-shortfalls?types=board,veneer');
    const n = (data && Array.isArray(data.rows)) ? data.rows.filter(r=>r.status==='SHORT').length : 0;
    const bd=document.getElementById('nav-shortfall-badge');
    if(bd){ bd.textContent=n; bd.classList.toggle('d-none', n===0); }
  }catch{}
}
// Refresh badge after login (delayed) and every 5 minutes
setTimeout(msfRefreshBadge, 4000);
setInterval(msfRefreshBadge, 300000);


// ══════════════════════════════════════════════════════════════
// FC MATERIAL REQUESTS DASHBOARD
// ══════════════════════════════════════════════════════════════
let _fcrRows=[], _fcrSelected=new Set();
function _fcrNum(n){return n==null||n===''?'—':Number(n).toLocaleString(undefined,{maximumFractionDigits:2});}
function _fcrStatusBadge(s){
  const m={SHORT:['danger','SHORT — Not Requested','bi-exclamation-triangle'],
           PARTIAL:['warning text-dark','PARTIAL — Still Short','bi-exclamation-circle'],
           PENDING:['info','In Transit (Pending)','bi-hourglass-split'],
           OK:['success','FC Stock Covers','bi-check2-circle']};
  const x=m[s]||['secondary',s,'bi-circle'];
  return `<span class="badge bg-${x[0]}"><i class="bi ${x[2]} me-1"></i>${x[1]}</span>`;
}

async function fcrLoad(){
  try{
    const data = await api('/api/fc/material-requirements');
    _fcrRows = (data && Array.isArray(data.rows)) ? data.rows : [];
    _fcrSelected.clear();
    fcrRenderKpi(data.summary || {});
    fcrRender();
    fcrUpdateBadge();
  }catch(e){
    document.getElementById('fcr-tbody').innerHTML=`<tr><td colspan="10" class="text-danger small p-3">${e.message||e}</td></tr>`;
  }
}

function fcrRenderKpi(s){
  document.getElementById('fcr-kpi').innerHTML=[
    {l:'Batches at FC',      v:s.batches_at_fc||0,     bg:'primary', ico:'bi-boxes'},
    {l:'Materials Required', v:s.materials_total||0,   bg:'secondary',ico:'bi-list-ul'},
    {l:'SHORT — Not Requested',v:s.materials_short||0, bg:'danger',  ico:'bi-exclamation-triangle'},
    {l:'PARTIAL — Still Short',v:s.materials_partial||0,bg:'warning', ico:'bi-exclamation-circle'},
    {l:'In Transit (Pending)',v:s.materials_pending||0,bg:'info',    ico:'bi-truck'},
    {l:'WH Also Short',      v:s.wh_shortfall_count||0,bg:'dark',    ico:'bi-x-octagon'},
  ].map(c=>`<div class="col-md-2 col-6"><div class="card border-${c.bg}"><div class="card-body py-2 px-3">
    <div class="small text-muted" style="font-size:.7rem"><i class="bi ${c.ico} me-1"></i>${c.l}</div>
    <div class="fs-5 fw-semibold">${c.v}</div></div></div></div>`).join('');
}

function fcrRender(){
  const state=document.getElementById('fcr-state').value;
  const q=(document.getElementById('fcr-filter').value||'').toLowerCase();
  let rows=_fcrRows;
  if(state==='ACTION')   rows=rows.filter(r=>r.status==='SHORT'||r.status==='PARTIAL');
  else if(state==='SHORT')   rows=rows.filter(r=>r.status==='SHORT');
  else if(state==='PARTIAL') rows=rows.filter(r=>r.status==='PARTIAL');
  else if(state==='PENDING') rows=rows.filter(r=>r.status==='PENDING');
  if(q) rows=rows.filter(r=>JSON.stringify(r).toLowerCase().includes(q));
  const tb=document.getElementById('fcr-tbody');
  if(!rows.length){
    tb.innerHTML='<tr><td colspan="10" class="text-center text-muted py-4"><i class="bi bi-check2-circle me-1 text-success"></i>Nothing to request — FC stock covers all upcoming batches.</td></tr>';
    fcrUpdateBulkBtn(); return;
  }
  tb.innerHTML=rows.map(r=>{
    const checkable = r.status==='SHORT' || r.status==='PARTIAL';
    const checked = _fcrSelected.has(r.material_id) ? 'checked' : '';
    const cb = checkable
      ? `<input type="checkbox" class="fcr-cb" data-mid="${r.material_id}" ${checked} onchange="fcrToggleOne(${r.material_id},this.checked)">`
      : '';
    const mp = Number(r.max_priority || 2);
    const mpBadge = mp===1
      ? '<span class="badge bg-danger me-1" title="Driven by urgent order">P1</span>'
      : (mp===3 ? '<span class="badge bg-success me-1">P3</span>' : '');
    const batchBadges = (r.batches||[]).slice(0,4).map(b=>{
      const prio=b.priority||2;
      const color=prio===1?'danger':(prio===2?'warning':'success');
      return `<span class="badge bg-${color}" title="P${prio} · ${b.product_name||''} · ${_fcrNum(b.qty_needed)} ${r.uom||''} needed${b.sales_po_number?' · '+b.sales_po_number:''}" style="font-size:.6rem">
        ${b.batch_number}
      </span>`;
    }).join(' ') + ((r.batches||[]).length>4 ? ` <span class="text-muted small">+${r.batches.length-4}</span>` : '');
    const whInfo = r.wh_shortfall>0
      ? `<span class="text-danger small"><i class="bi bi-x-octagon me-1"></i>WH short ${_fcrNum(r.wh_shortfall)}</span>`
      : (r.wh_stock>0 ? `<span class="text-success">${_fcrNum(r.wh_stock)}</span>` : '<span class="text-muted">—</span>');
    let action;
    if(r.status==='SHORT'||r.status==='PARTIAL'){
      action = `<button class="btn btn-xs btn-info text-white"
        onclick='fcrOpenRequest(${JSON.stringify(r).replace(/'/g,"&apos;")})'>
        <i class="bi bi-send me-1"></i>Request</button>`;
    }else if(r.status==='PENDING'){
      action = `<span class="badge bg-info"><i class="bi bi-truck me-1"></i>${_fcrNum(r.pending_in)} ${r.uom||''} inbound</span>`;
    }else{
      action = '<span class="text-muted small">—</span>';
    }
    return `<tr>
      <td>${cb}</td>
      <td>${mpBadge}<span class="badge bg-light text-dark border" style="font-size:.6rem">${(r.material_type||'').toUpperCase()}</span>
          <b>${r.material_code||''}</b> ${r.material_name||''}</td>
      <td class="text-end fw-semibold">${_fcrNum(r.required)} <span class="text-muted small">${r.uom||''}</span></td>
      <td class="text-end ${r.fc_stock>0?'':'text-muted'}">${_fcrNum(r.fc_stock)}</td>
      <td class="text-end ${r.pending_in>0?'text-info':'text-muted'}">${_fcrNum(r.pending_in)}</td>
      <td class="text-end ${r.shortfall>0?'text-danger fw-bold':'text-muted'}">${r.shortfall>0?_fcrNum(r.shortfall):'—'}</td>
      <td class="text-end small">${whInfo}</td>
      <td>${_fcrStatusBadge(r.status)}</td>
      <td>${batchBadges||'<span class="text-muted small">—</span>'}</td>
      <td class="text-end" style="white-space:nowrap">${action}</td>
    </tr>`;
  }).join('');
  fcrUpdateBulkBtn();
}

function fcrToggleOne(mid, checked){
  if(checked) _fcrSelected.add(Number(mid)); else _fcrSelected.delete(Number(mid));
  fcrUpdateBulkBtn();
}
function fcrToggleAll(checked){
  document.querySelectorAll('.fcr-cb').forEach(cb=>{
    cb.checked=checked;
    const mid=Number(cb.dataset.mid);
    if(checked) _fcrSelected.add(mid); else _fcrSelected.delete(mid);
  });
  fcrUpdateBulkBtn();
}
function fcrUpdateBulkBtn(){
  const btn=document.getElementById('fcr-bulk-btn');
  const cnt=document.getElementById('fcr-bulk-count');
  cnt.textContent=_fcrSelected.size;
  btn.disabled=_fcrSelected.size===0;
}

async function fcrOpenRequest(r){
  const qty = prompt(
    `Request transfer FROM Warehouse TO FC?\n\n${r.material_code||''} ${r.material_name}\nSuggested qty: ${_fcrNum(r.suggested_qty)} ${r.uom||''}\nFC stock: ${_fcrNum(r.fc_stock)}  ·  In-flight: ${_fcrNum(r.pending_in)}  ·  WH stock: ${_fcrNum(r.wh_stock)}` +
    (r.wh_shortfall>0 ? `\n\n⚠ Warehouse is also short ${_fcrNum(r.wh_shortfall)} — a purchase request may be needed first.` : ''),
    String(r.suggested_qty||r.shortfall||''));
  if(qty===null) return;
  const q=Number(qty); if(!q || q<=0){ alert('Enter a positive quantity'); return; }
  const batchRefs=(r.batches||[]).map(b=>b.batch_number).slice(0,5).join(', ');
  try{
    await api('/api/fc/transfer-requests','POST',{
      material_id: r.material_id, qty_requested: q,
      notes: `For upcoming batches: ${batchRefs}` + (r.batches.length>5?` (+${r.batches.length-5})`:''),
    });
    toast('Request sent to Warehouse');
    fcrLoad();
  }catch(e){ alert('Request failed: '+(e.message||e)); }
}

async function fcrBulkRequest(){
  if(_fcrSelected.size===0) return;
  if(!confirm(`Send ${_fcrSelected.size} FC transfer request(s) to Warehouse using the suggested qty for each?`)) return;
  const selected=_fcrRows.filter(r=>_fcrSelected.has(r.material_id) && r.suggested_qty>0);
  let ok=0, fail=0;
  for(const r of selected){
    const batchRefs=(r.batches||[]).map(b=>b.batch_number).slice(0,5).join(', ');
    try{
      await api('/api/fc/transfer-requests','POST',{
        material_id: r.material_id, qty_requested: r.suggested_qty,
        notes: `Bulk request for upcoming batches: ${batchRefs}`+(r.batches.length>5?` (+${r.batches.length-5})`:''),
      });
      ok++;
    }catch(e){ fail++; console.error('FC request failed for', r.material_name, e); }
  }
  toast(`Created ${ok} FC request(s)${fail?` · ${fail} failed`:''}`, fail?'warning':'success');
  fcrLoad();
}

function fcrUpdateBadge(){
  const n = _fcrRows.filter(r=>r.status==='SHORT'||r.status==='PARTIAL').length;
  const b=document.getElementById('nav-fc-requests-badge');
  if(b){ b.textContent=n; b.classList.toggle('d-none', n===0); }
}
async function fcrRefreshBadge(){
  try{
    const data = await api('/api/fc/material-requirements');
    _fcrRows = (data && Array.isArray(data.rows)) ? data.rows : [];
    fcrUpdateBadge();
  }catch{}
}
setTimeout(fcrRefreshBadge, 5000);
setInterval(fcrRefreshBadge, 300000);


// Raw Material Receiving moved to /static/js/portal_warehouse.js

// ══════════════════════════════════════════════════════════════
// FC HUB — wraps the existing dept-fc and fc-requests pages
// ══════════════════════════════════════════════════════════════
let _fcHubTab = 'check';
let _fcHubMounted = false;

function _fcHubMount(){
  if(_fcHubMounted) return;
  const inner = document.getElementById('page-dept-fc');
  const reqs  = document.getElementById('page-fc-requests');
  const prepPane = document.getElementById('fc-hub-pane-check');
  const invPane  = document.getElementById('fc-hub-pane-inventory');
  const reqsPane = document.getElementById('fc-hub-pane-requests');
  if(inner){
    inner.classList.remove('page'); inner.classList.add('d-block');
    // Strip the legacy header + internal tabs — the outer FC Hub tabs do this job.
    const innerHeader = inner.querySelector('.d-flex.justify-content-between.align-items-center.mb-3');
    if(innerHeader) innerHeader.remove();
    const innerTabs = document.getElementById('fc-tabs');
    if(innerTabs) innerTabs.remove();
    // Move each inner pane into its matching outer tab container
    const prep  = document.getElementById('fc-pane-prep');
    const stock = document.getElementById('fc-pane-stock');
    if(prep  && prepPane){ prep.classList.remove('d-none');  prepPane.appendChild(prep);  }
    if(stock && invPane){ stock.classList.remove('d-none'); invPane.appendChild(stock); }
    // The empty shell that used to hold page-dept-fc is no longer needed; drop it
    if(inner.parentElement) inner.parentElement.removeChild(inner);
  }
  if(reqs && reqsPane){
    reqs.classList.remove('page'); reqs.classList.add('d-block');
    reqsPane.appendChild(reqs);
  }
  _fcHubMounted = true;
}

function fcHubSwitch(tab){
  _fcHubTab = tab;
  document.querySelectorAll('#fc-hub-tabs .nav-link').forEach(b =>
    b.classList.toggle('active', b.dataset.fchubTab === tab));
  ['check','inventory','requests','station'].forEach(t => {
    const el = document.getElementById('fc-hub-pane-' + t);
    if(el) el.style.display = (tab === t) ? '' : 'none';
  });
  // Both Material Prep and FC Inventory share the same data load (fcRefresh
  // populates both panes that were originally inside page-dept-fc).
  if(tab === 'check' || tab === 'inventory'){
    if(typeof fcRefresh === 'function') fcRefresh();
    else if(typeof loadFcPage === 'function') loadFcPage();
  }
  if(tab === 'requests')  fcrLoad?.();
  if(tab === 'station')   fcHubLoadStation();
}

function fcHubLoad(){
  _fcHubMount();
  fcHubSwitch(_fcHubTab || 'check');
  // Sidebar badge mirror (FC Hub red badge counts short FC requests)
  try{
    const n = (_fcrRows || []).filter(r => r.status==='SHORT' || r.status==='PARTIAL').length;
    const b = document.getElementById('fc-hub-req-badge');
    if(b){ b.textContent = n; b.classList.toggle('d-none', n===0); }
  }catch{}
}

// ── FC Hub → Station Inventory tab (sub-tabs: Consumables / Movements / Forklifts)
let _fcsiSubTab = 'cons';
async function fcHubLoadStation(){
  const host = document.getElementById('fc-hub-pane-station');
  if(!host) return;
  host.innerHTML = `
    <div class="d-flex justify-content-between align-items-center mb-2">
      <div>
        <h5 class="mb-0"><i class="bi bi-tools me-2 text-primary"></i>FC Station Inventory</h5>
        <small class="text-muted">Consumables held at FC · movement history · forklifts assigned here</small>
      </div>
      <button class="btn btn-sm btn-outline-secondary" onclick="fcHubLoadStation()"><i class="bi bi-arrow-clockwise"></i></button>
    </div>
    <ul class="nav nav-pills nav-fill mb-3" id="fcsi-sub-tabs" style="background:#f1f5f9;padding:4px;border-radius:8px">
      <li class="nav-item"><button type="button" class="nav-link active" data-fcsi-sub="cons"      onclick="fcsiSubSwitch('cons')"><i class="bi bi-box-seam me-1"></i>Consumables</button></li>
      <li class="nav-item"><button type="button" class="nav-link"        data-fcsi-sub="movements" onclick="fcsiSubSwitch('movements')"><i class="bi bi-clock-history me-1"></i>Movements</button></li>
      <li class="nav-item"><button type="button" class="nav-link"        data-fcsi-sub="forklifts" onclick="fcsiSubSwitch('forklifts')"><i class="bi bi-truck-flatbed me-1"></i>Forklifts</button></li>
    </ul>
    <div id="fcsi-sub-pane-cons" class="fcsi-sub-pane"><div class="card">
      <div class="card-header py-2 d-flex align-items-center">
        <i class="bi bi-box-seam me-1 text-warning"></i>
        <span class="fw-bold small">Consumables at FC Station</span>
        <small class="text-muted ms-2">Glue mixing chemicals, packaging, tools</small>
        <button class="btn btn-sm btn-primary ms-auto" onclick="fcsiOpenWHRequest()" title="Request a consumable top-up from warehouse">
          <i class="bi bi-cart-plus me-1"></i>Request from WH
        </button>
      </div>
      <div class="table-responsive" style="max-height:55vh;overflow:auto">
        <table class="table table-sm table-hover mb-0"><thead class="table-light sticky-top"><tr>
          <th>Material</th><th>Type</th>
          <th class="text-end">Current</th><th class="text-end">Min</th>
          <th class="text-end">WH Stock</th><th>Last update</th>
        </tr></thead>
        <tbody id="fcsi-cons-tbody"><tr><td colspan="6" class="text-center text-muted py-3">Loading…</td></tr></tbody>
        </table>
      </div>
    </div></div>
    <div id="fcsi-sub-pane-movements" class="fcsi-sub-pane d-none"><div class="card">
      <div class="card-header py-2 d-flex align-items-center">
        <i class="bi bi-arrow-left-right me-1 text-info"></i>
        <span class="fw-bold small">Recent Station Stock Movements</span>
        <small class="text-muted ms-2">Receipts from WH, issues to batches, adjustments</small>
      </div>
      <div class="table-responsive" style="max-height:55vh;overflow:auto">
        <table class="table table-sm table-hover mb-0"><thead class="table-light sticky-top"><tr>
          <th>When</th><th>Type</th><th>Material</th>
          <th class="text-end">Qty Δ</th><th>Batch / Ref</th><th>Notes</th>
        </tr></thead>
        <tbody id="fcsi-mov-tbody"><tr><td colspan="6" class="text-center text-muted py-3">Loading…</td></tr></tbody>
        </table>
      </div>
    </div></div>
    <div id="fcsi-sub-pane-forklifts" class="fcsi-sub-pane d-none"><div class="card">
      <div class="card-header py-2 d-flex align-items-center">
        <i class="bi bi-truck-flatbed me-1 text-info"></i>
        <span class="fw-bold small">Forklifts assigned to FC</span>
        <button class="btn btn-sm btn-info text-white ms-auto" onclick="oilOpenNew()" title="Request oil for a forklift">
          <i class="bi bi-droplet me-1"></i>Request Oil
        </button>
      </div>
      <div class="table-responsive" style="max-height:55vh;overflow:auto">
        <table class="table table-sm table-hover mb-0"><thead class="table-light sticky-top"><tr>
          <th>Code</th><th>Name</th><th>Model</th><th>Status</th><th class="text-end">Hrs</th><th>Last Refuel</th><th>Open Oil Req</th>
        </tr></thead><tbody id="fcsi-flk-tbody"><tr><td colspan="7" class="text-center text-muted py-3">Loading…</td></tr></tbody></table>
      </div>
    </div></div>
  `;
  await fcsiReload();
}

function fcsiSubSwitch(tab){
  _fcsiSubTab = tab;
  document.querySelectorAll('#fcsi-sub-tabs .nav-link').forEach(b =>
    b.classList.toggle('active', b.dataset.fcsiSub === tab));
  ['cons','movements','forklifts'].forEach(t => {
    const el = document.getElementById('fcsi-sub-pane-' + t);
    if(el) el.classList.toggle('d-none', t !== tab);
  });
}

async function fcsiReload(){
  try{
    const [cons, mov, flk, oilReqs] = await Promise.all([
      api('/api/station-stock?department=fc').catch(()=>[]),
      api('/api/station-stock/movements?department=fc&limit=100').catch(()=>[]),
      api('/api/forklifts?dept=fc').catch(()=>[]),
      api('/api/forklifts/oil-requests?status=FULFILLED').catch(()=>[]),
    ]);
    // Consumables table
    const ctb = document.getElementById('fcsi-cons-tbody');
    if(ctb) ctb.innerHTML = (cons||[]).length
      ? cons.map(s => {
          const low = Number(s.current_qty||0) <= Number(s.min_qty||0);
          return `<tr ${low?'class="table-danger"':''}>
            <td class="small"><b>${s.material_code||''}</b> ${s.material_name||''}</td>
            <td class="small"><span class="badge bg-light text-dark border" style="font-size:.6rem">${(s.material_type||'').toUpperCase()}</span></td>
            <td class="text-end ${low?'fw-bold text-danger':''}">${fmt(s.current_qty||0)} ${s.unit||''}</td>
            <td class="text-end small">${fmt(s.min_qty||0)}</td>
            <td class="text-end small">${fmt(s.wh_stock||0)}</td>
            <td class="small text-muted">${(s.last_updated||'').slice(0,16).replace('T',' ')}</td>
          </tr>`;
        }).join('')
      : '<tr><td colspan="6" class="text-center text-muted py-3">No consumables currently at FC station.</td></tr>';
    // Movements
    const COLOR={RECEIVE:'success',ISSUE:'warning text-dark',ADJUST:'secondary',BATCH_USE:'info text-dark'};
    const mtb = document.getElementById('fcsi-mov-tbody');
    if(mtb) mtb.innerHTML = (mov||[]).length
      ? mov.map(m => `<tr>
          <td class="small text-muted">${(m.created_at||'').replace('T',' ').slice(0,16)}</td>
          <td><span class="badge bg-${COLOR[m.movement_type]||'secondary'}">${m.movement_type||''}</span></td>
          <td class="small"><b>${m.material_code||''}</b> ${m.material_name||''}</td>
          <td class="text-end ${m.qty_change>0?'text-success':'text-danger'}">${m.qty_change>0?'+':''}${fmt(m.qty_change||0)} ${m.unit||''}</td>
          <td class="small">${m.batch_ref||''}</td>
          <td class="small text-muted">${(m.notes||'').slice(0,80)}</td>
        </tr>`).join('')
      : '<tr><td colspan="6" class="text-center text-muted py-3">No recent stock movements at FC station.</td></tr>';
    // Forklifts (with last-refuel timestamp)
    const lastBy = {};
    (oilReqs||[]).forEach(r => {
      const cur = lastBy[r.forklift_id];
      if(!cur || (r.fulfilled_at||'') > (cur.fulfilled_at||'')) lastBy[r.forklift_id] = r;
    });
    const ftb = document.getElementById('fcsi-flk-tbody');
    if(ftb) ftb.innerHTML = (flk||[]).length
      ? flk.map(f => {
          const stat = {active:'success',maintenance:'warning text-dark',retired:'secondary'}[f.status]||'secondary';
          const lr   = lastBy[f.id];
          return `<tr>
            <td class="small fw-semibold">${f.code}</td>
            <td class="small">${f.name||'—'}</td>
            <td class="small">${f.model||'—'}</td>
            <td><span class="badge bg-${stat}">${f.status}</span></td>
            <td class="text-end small">${f.hours_meter?Number(f.hours_meter).toLocaleString():'—'}</td>
            <td class="small text-muted">${lr ? (lr.fulfilled_at||'').slice(0,16).replace('T',' ')+' · '+Number(lr.fulfilled_qty||0).toFixed(1)+'L' : 'never'}</td>
            <td>${f.open_oil_requests?`<span class="badge bg-warning text-dark"><i class="bi bi-droplet me-1"></i>${f.open_oil_requests}</span>`:'<span class="text-muted small">—</span>'}</td>
          </tr>`;
        }).join('')
      : '<tr><td colspan="7" class="text-center text-muted py-3">No forklifts assigned to FC dept. Register one in Station Leader Hub → Forklifts.</td></tr>';
  }catch(e){
    const ctb = document.getElementById('fcsi-cons-tbody');
    if(ctb) ctb.innerHTML = `<tr><td colspan="6" class="text-danger small p-3">${e.message||e}</td></tr>`;
  }
}

function fcsiOpenWHRequest(){
  try{ openWHRequest('fc'); }
  catch(e){ alert('Request modal unavailable: '+e.message); }
}



// ── Page loader registry ────────────────────────────────────
Object.assign(PAGE_LOADERS, {
  'vcmx':                vcmxLoad,
  'vcmx-lam':            vcmxLamLoad,
  'material-shortfalls': msfLoad,
  'fc-hub':              fcHubLoad,
});
