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
// Consolidated (2.21.51): stock-building PRs now reuse the shared
// multi-material modal (#newPRModal) instead of a duplicate modal. We
// just seed a note so Purchasing can tell these aren't tied to a sales PO.
function msfOpenAdhocPR(){
  const m = document.getElementById('newPRModal');
  if(!m){ alert('Purchase Request modal unavailable.'); return; }
  bootstrap.Modal.getOrCreateInstance(m).show();
  // show.bs.modal primes materials + resets lines; seed the notes after.
  setTimeout(()=>{
    const n = document.getElementById('pr-new-notes');
    if(n && !n.value.trim()) n.value = '[Stock-building, no PO]';
  }, 250);
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





// ════════════════════════════════════════════════════════════
// BOM structured view (list + matPill/gluePill/packPill)
// ════════════════════════════════════════════════════════════
// ══════════════════════════════════════════════════════════
// BOM — structured view
// ══════════════════════════════════════════════════════════
let _allBom=[];
async function loadBom(){
  const rows=await api('/api/fg-bom');
  _allBom=rows;
  renderBom(rows);
}
function searchBom(q){
  const s=q.toLowerCase();
  renderBom(s?_allBom.filter(r=>r.sku_code.toLowerCase().includes(s)||(r.sku_name||'').toLowerCase().includes(s)):_allBom);
}
function matPill(item, role){
  if(!item) return '<span class="text-muted">—</span>';
  const roleCol=role==='face'?'border-primary text-primary':role==='back'?'border-info text-info':'border-secondary text-secondary';
  const roleLabel=role?`<span class="badge ${role==='face'?'bg-primary':'bg-info text-dark'} ms-1" style="font-size:.6rem">${role.toUpperCase()}</span>`:'';
  return `<div class="d-inline-block border rounded px-2 py-1 me-1 mb-1 ${roleCol}" style="font-size:.8rem">
    <code>${item.code}</code>${roleLabel}<br>
    <small class="text-muted">${item.name_th||item.name||''}</small><br>
    <small>qty: <b>${item.qty}</b> ${item.unit||''} &nbsp;|&nbsp; ฿${(item.price||0).toLocaleString()}/unit &nbsp;|&nbsp; <b>฿${(item.cost||0).toLocaleString()}</b></small>
  </div>`;
}
function gluePill(item){
  if(!item) return '<span class="text-muted">—</span>';
  return `<div class="d-inline-block border rounded px-2 py-1 me-1 mb-1 border-warning" style="font-size:.8rem">
    <code class="text-warning-emphasis">${item.code}</code><br>
    <small class="text-muted">${item.usage_g_per_face||'-'} g/face</small><br>
    <small>฿${(item.price||0).toFixed(2)}/kg &nbsp;|&nbsp; <b>฿${(item.cost||0).toLocaleString()}</b></small>
  </div>`;
}
function packPill(item){
  if(!item) return '<span class="text-muted">—</span>';
  return `<div class="d-inline-block border rounded px-2 py-1 border-success" style="font-size:.8rem">
    <code class="text-success">${item.code}</code><br>
    <small class="text-muted">${item.customer||''}</small><br>
    <small><b>฿${(item.cost||0).toLocaleString()}</b>/pallet</small>
  </div>`;
}

function openLogModal(){
  document.getElementById('log-id').value='';
  document.getElementById('log-date').value=new Date().toISOString().slice(0,10);
  populateSel('log-mach',machines,'id','name');
  populateSel('log-prod',products,'id','name');
}
async function saveLog(){
  const body={log_date:document.getElementById('log-date').value,shift:document.getElementById('log-shift').value,machine_id:parseInt(document.getElementById('log-mach').value),sku_id:parseInt(document.getElementById('log-prod').value),planned_qty:parseInt(document.getElementById('log-planned').value),actual_qty:parseInt(document.getElementById('log-actual').value),notes:document.getElementById('log-notes').value};
  try{await api('/api/production-logs','POST',body);bootstrap.Modal.getInstance(document.getElementById('logModal')).hide();toast('Saved');loadLogs();}catch(e){toast(e.message,'danger');}
}


// ════════════════════════════════════════════════════════════
// BOM Builder + Glue/Bleaching formula editor + Packing Spec Management
// ════════════════════════════════════════════════════════════
// ════════════════════════════════════════════════════════════
// BOM BUILDER (embedded in FG BOM tab)
// ════════════════════════════════════════════════════════════
let _bbMats = {};
let _bbPicked = {};
let _bbAllFg = [];
let _bbLoaded = false;

// The BOM Builder is a single panel. For in-place editing we relocate it
// directly beneath the edited card; this records its original home (right
// above the list) so it can be moved back. Restored before any list re-render
// so re-rendering bom-list's innerHTML never destroys the panel.
let _bbPanelHome = null;
function _bbRestorePanelHome(){
  const panel = document.getElementById('bom-builder-panel');
  if(!panel || !_bbPanelHome) return;
  if(panel.parentElement === _bbPanelHome.parent && panel.nextElementSibling === _bbPanelHome.next) return;
  _bbPanelHome.parent.insertBefore(panel, _bbPanelHome.next);
}

// Returns a promise that resolves once the builder is ready to pre-fill.
// The previous version fired loadBomBuilder() without awaiting it, so an
// edit-flow caller could call bbLoadFg before _bbMats.faceG was populated
// with glue recipes — the eventual loadBomBuilder finish then re-rendered
// the dropdown and wiped the user-visible selection.
async function openBomBuilder(){
  const panel = document.getElementById('bom-builder-panel');
  // "New / Edit BOM" opens the builder at the top (its home); in-place card
  // edits relocate it via editBomCard instead.
  _bbRestorePanelHome();
  bootstrap.Collapse.getOrCreateInstance(panel).show();
  if(!_bbLoaded) await loadBomBuilder();
}

async function loadBomBuilder(){
  _bbLoaded = true;
  const [mats, recipes] = await Promise.all([
    api('/api/materials').catch(()=>[]),
    // Glue picker shows GLUE RECIPES (from glue_recipes), not raw "Glue and
    // Additives" ingredients (materials.type='glue_formula'). The recipe is
    // what the line operator mixes; ingredients are tracked via the recipe.
    api('/api/glue-recipes?kind=glue').catch(()=>[]),
  ]);
  // Normalise recipes into the same shape the picker expects (code, name).
  const recipeOpts = (recipes||[]).map(r => ({
    code: r.recipe_code,
    name: r.name || r.recipe_code,
    veneer_thickness: r.veneer_thickness,
    wood_species: r.wood_species,
    core_board: r.core_board,
    type: 'glue_recipe',
  }));
  // Base board pool includes both raw core_board materials AND completed VCMX
  // substrates (type='vcmx') — VCMX SKUs carry a code/board_type/dims so they
  // surface just like any other core board.
  _bbMats = {
    base:  mats.filter(m => m.type==='core_board' || m.type==='vcmx'),
    faceV: mats.filter(m=>m.type==='veneer_sheet'),
    backV: mats.filter(m=>m.type==='veneer_sheet'),
    faceG: recipeOpts,
    backG: recipeOpts,
  };
  _bbAllFg = await api('/api/fg').catch(()=>[]);
  ['base','faceV','backV','faceG','backG'].forEach(c => bbRenderOptions(c, _bbMats[c]));
}

function bbRenderOptions(comp, list){
  const sel = document.getElementById('bb-select-'+comp);
  if(!sel) return;
  sel.innerHTML = list.map(m=>{
    let label;
    if(comp==='base'){
      // Board: CODE — Type Glue Thick W×L (prefix [VCMX] for make-to-stock substrates)
      const dims=[m.thickness_mm?m.thickness_mm+'mm':'', m.width_mm&&m.length_mm?m.width_mm+'×'+m.length_mm:''].filter(Boolean).join(' ');
      const prefix = (m.type==='vcmx') ? '[VCMX] ' : '';
      label = prefix + m.code+' — '+(m.board_type||'')+' '+(m.glue_type||'')+' '+dims;
    } else if(comp==='faceV'||comp==='backV'){
      // Veneer: CODE — Species Cut Thick Grade/Match
      const parts=[m.species,m.cut_type,m.thickness_mm?m.thickness_mm+'mm':'',m.grade,m.matching].filter(Boolean);
      label = m.code+' — '+parts.join(' ');
    } else if(comp==='pack'){
      label = m.code+' — '+(m.name||m.customer||'');
    } else if(comp==='faceG' || comp==='backG'){
      // Glue recipe — show recipe_code + name + any conditioning hints
      const cond = [m.veneer_thickness, m.wood_species, m.core_board].filter(Boolean).join(' · ');
      label = m.code+' — '+(m.name||'') + (cond ? '  ['+cond+']' : '');
    } else {
      label = m.code+' — '+(m.name||'');
    }
    return '<option value="'+m.code+'">'+label.replace(/\s+/g,' ').trim()+'</option>';
  }).join('');
}

function bbFilter(comp, q){
  const s = q.toLowerCase();
  const list = s ? _bbMats[comp].filter(m=>{
    const searchStr = [m.code,m.name,m.species,m.board_type,m.cut_type,m.grade,m.matching,m.glue_type].filter(Boolean).join(' ').toLowerCase();
    return searchStr.includes(s);
  }) : _bbMats[comp];
  bbRenderOptions(comp, list);
}

function bbPick(comp, code){
  if(!code) return;
  const item = _bbMats[comp].find(m=>m.code===code);
  if(!item) return;
  _bbPicked[comp] = item;
  const badge = document.getElementById('bb-badge-'+comp);
  const sel   = document.getElementById('bb-sel-'+comp);
  const clear = document.getElementById('bb-clear-'+comp);
  badge.textContent = item.code + (item.name ? '  |  '+item.name : '');
  sel.classList.remove('d-none');
  clear.classList.remove('d-none');
  const pq = parseInt(document.getElementById('bb-pallet-qty').value)||0;
  const qi = document.getElementById('bb-qty-'+comp);
  if(qi && !qi.value){
    // Boards/veneers default to the pallet qty; glue is left blank so the user
    // must enter the real g/face (no hard-coded 45 g default).
    if(comp!=='faceG' && comp!=='backG') qi.value = pq||'';
  }

  // ── BASE BOARD: show dimension hint ──────────────────────────
  if(comp === 'base'){
    const dimsEl   = document.getElementById('bb-dims-base');
    const dimsText = document.getElementById('bb-dims-base-text');
    if(dimsEl && dimsText){
      const t = item.thickness_mm, w = item.width_mm, l = item.length_mm;
      if(t || w || l){
        const parts = [];
        if(t) parts.push(t+'mm thick');
        if(w && l) parts.push(w+' × '+l+' mm');
        else if(w) parts.push(w+' mm wide');
        else if(l) parts.push(l+' mm long');
        dimsText.textContent = parts.join('  |  ');
        dimsEl.classList.remove('d-none');
      } else {
        dimsEl.classList.add('d-none');
        // No dims stored — show a neutral note
        dimsText.textContent = 'No dimensions stored (set in Materials editor)';
        dimsEl.classList.remove('d-none');
      }
    }
  }

  // ── VENEER: unit-aware label + auto-suggest matching glue ────
  if(comp === 'faceV' || comp === 'backV'){
    const unit = (item.unit || 'sheet').toLowerCase().replace(/\s/g,'');
    const isM2 = unit === 'm2' || unit === 'm²' || unit === 'sqm';
    const labelEl = document.getElementById('bb-unit-label-'+comp);
    if(labelEl) labelEl.textContent = isM2 ? 'Qty (M²/pallet)' : 'Qty (sheets/pallet)';

    // Auto-suggest glue based on veneer species (auto_glue_code field),
    // applied to BOTH face and back glue slots — species determines formula,
    // not which slot the veneer is in.
    const glueSlots = ['faceG', 'backG'];
    glueSlots.forEach(glueComp => {
      if(_bbPicked[glueComp]) return; // already chosen by user
      let autoGlue = null;
      const allGlues = _bbMats[glueComp] || [];
      // 1st choice: explicit auto_glue_code on the veneer material
      if(item.auto_glue_code){
        autoGlue = allGlues.find(g => g.code === item.auto_glue_code);
      }
      // 2nd choice: only one glue formula available
      if(!autoGlue && allGlues.length === 1){
        autoGlue = allGlues[0];
      }
      if(autoGlue){
        const selEl = document.getElementById('bb-select-'+glueComp);
        if(selEl) selEl.value = autoGlue.code;
        bbPick(glueComp, autoGlue.code);
        toast(`Auto-selected glue (${glueComp==='faceG'?'face':'back'}): ${autoGlue.name||autoGlue.code}`, 'secondary');
      }
    });
  }
}

function bbApplyBoardDims(){
  const board = _bbPicked.base;
  if(!board){ toast('No base board selected','warning'); return; }
  let applied = 0;
  const tEl = document.getElementById('bb-thick');
  const wEl = document.getElementById('bb-width');
  const lEl = document.getElementById('bb-length');
  if(board.thickness_mm && tEl){ tEl.value = board.thickness_mm; applied++; }
  if(board.width_mm && wEl){ wEl.value = board.width_mm; applied++; }
  if(board.length_mm && lEl){ lEl.value = board.length_mm; applied++; }
  if(applied) toast('Board dims applied — adjust finished size as needed', 'info');
  else toast('No dimensions stored for this board — enter in Materials editor first', 'warning');
}

function bbClearComp(comp){
  delete _bbPicked[comp];
  document.getElementById('bb-sel-'+comp).classList.add('d-none');
  document.getElementById('bb-clear-'+comp).classList.add('d-none');
  document.getElementById('bb-search-'+comp).value='';
  const qi = document.getElementById('bb-qty-'+comp);
  if(qi) qi.value='';
  // Reset extras
  if(comp === 'base') document.getElementById('bb-dims-base')?.classList.add('d-none');
  if(comp === 'faceV'){ const l=document.getElementById('bb-unit-label-faceV'); if(l) l.textContent='Qty (sheets/pallet)'; }
  if(comp === 'backV'){ const l=document.getElementById('bb-unit-label-backV'); if(l) l.textContent='Qty (sheets/pallet)'; }
  bbRenderOptions(comp, _bbMats[comp]);
}

function bbSyncQtyDefaults(){
  const pq = parseInt(document.getElementById('bb-pallet-qty').value)||0;
  if(!pq) return;
  ['base','faceV','backV'].forEach(c=>{
    if(_bbPicked[c]){ const qi=document.getElementById('bb-qty-'+c); if(qi&&!qi.value) qi.value=pq; }
  });
}

function bbLoadSearch(q){
  const drop = document.getElementById('bb-load-drop');
  if(!q){ drop.classList.add('d-none'); return; }
  const s = q.toLowerCase();
  const hits = _bbAllFg.filter(f=>(f.code+' '+(f.name||'')).toLowerCase().includes(s)).slice(0,10);
  if(!hits.length){ drop.classList.add('d-none'); return; }
  drop.innerHTML = hits.map(f=>
    '<div class="px-3 py-2 border-bottom" style="cursor:pointer;font-size:.85rem" '+
    'onmousedown="event.preventDefault();bbLoadFg(\''+f.code+'\')">'+
    '<span class="fw-bold text-primary">'+f.code+'</span> &nbsp;'+
    '<span class="text-muted">'+(f.name||'')+'</span></div>'
  ).join('');
  drop.classList.remove('d-none');
}

async function bbLoadFg(code){
  document.getElementById('bb-load-drop').classList.add('d-none');
  document.getElementById('bb-load-q').value = code;
  try{
    const bom = await api('/api/fg/'+code+'/bom');
    document.getElementById('bb-code').value = bom.sku_code||'';
    document.getElementById('bb-name').value = bom.sku_name||'';
    document.getElementById('bb-thick').value = bom.thickness_mm||'';
    document.getElementById('bb-width').value = bom.width_mm||'';
    document.getElementById('bb-length').value = bom.length_mm||'';
    document.getElementById('bb-pallet-qty').value = bom.pallet_qty||'';
    const map = [
      ['base',  bom.base_board,  'qty'],
      ['faceV', bom.face_veneer, 'qty'],
      ['backV', bom.back_veneer, 'qty'],
      ['faceG', bom.face_glue,   'usage_g_per_face'],
      ['backG', bom.back_glue,   'usage_g_per_face'],
    ];
    map.forEach(([comp, obj, qKey])=>{
      if(!obj) return;
      if(!_bbMats[comp].find(m=>m.code===obj.code)) _bbMats[comp].unshift({code:obj.code, name:obj.name});
      bbRenderOptions(comp, _bbMats[comp]);
      const sel = document.getElementById('bb-select-'+comp);
      if(sel) sel.value = obj.code;
      bbPick(comp, obj.code);
      const qi = document.getElementById('bb-qty-'+comp);
      if(qi) qi.value = obj[qKey]||'';
      // Pre-fill Waste % (factor → %) for board/veneer lines
      const wi = document.getElementById('bb-waste-'+comp);
      if(wi && obj.waste_factor != null) wi.value = +(obj.waste_factor*100).toFixed(2);
    });
    toast('Loaded BOM for '+code);
  }catch(e){ toast('Could not load BOM: '+e.message,'warning'); }
}

function resetBomBuilder(){
  ['bb-code','bb-name','bb-thick','bb-width','bb-length','bb-pallet-qty','bb-load-q'].forEach(id=>{
    const el=document.getElementById(id); if(el) el.value='';
  });
  document.getElementById('bb-load-drop').classList.add('d-none');
  _bbPicked={};
  ['base','faceV','backV','faceG','backG'].forEach(c=>{
    document.getElementById('bb-sel-'+c)?.classList.add('d-none');
    document.getElementById('bb-clear-'+c)?.classList.add('d-none');
    const s=document.getElementById('bb-search-'+c); if(s) s.value='';
    const qi=document.getElementById('bb-qty-'+c); if(qi) qi.value='';
    bbRenderOptions(c, _bbMats[c]||[]);
  });
  // Reset waste % to defaults (boards 0, veneers 5)
  const wb=document.getElementById('bb-waste-base');  if(wb) wb.value='0';
  const wf=document.getElementById('bb-waste-faceV'); if(wf) wf.value='5';
  const wbk=document.getElementById('bb-waste-backV'); if(wbk) wbk.value='5';
  // Reset extras
  document.getElementById('bb-dims-base')?.classList.add('d-none');
  const lf=document.getElementById('bb-unit-label-faceV'); if(lf) lf.textContent='Qty (sheets/pallet)';
  const lb=document.getElementById('bb-unit-label-backV'); if(lb) lb.textContent='Qty (sheets/pallet)';
}

async function saveBomBuilder(){
  const code = document.getElementById('bb-code').value.trim().toUpperCase();
  const name = document.getElementById('bb-name').value.trim();
  const pq   = parseInt(document.getElementById('bb-pallet-qty').value)||0;
  if(!code){ toast('SKU Code is required','danger'); return; }
  if(!name){ toast('Name is required','danger'); return; }
  if(!pq)  { toast('Pcs/Pallet is required','danger'); return; }
  const gn = k => parseFloat(document.getElementById(k)?.value)||null;
  // Waste % input → factor (e.g. 5 → 0.05). Empty/invalid → 0.
  const gw = k => { const v=parseFloat(document.getElementById(k)?.value); return (isNaN(v)||v<0)?0:v/100; };
  const body = {
    sku_code: code, sku_name: name,
    thickness_mm: gn('bb-thick'), width_mm: gn('bb-width'), length_mm: gn('bb-length'),
    pallet_qty: pq,
    base_board_code:   _bbPicked.base  ? _bbPicked.base.code  : null, base_board_qty:   gn('bb-qty-base'),  base_board_waste:  gw('bb-waste-base'),
    face_veneer_code:  _bbPicked.faceV ? _bbPicked.faceV.code : null, face_veneer_qty:  gn('bb-qty-faceV'), face_veneer_waste: gw('bb-waste-faceV'),
    back_veneer_code:  _bbPicked.backV ? _bbPicked.backV.code : null, back_veneer_qty:  gn('bb-qty-backV'), back_veneer_waste: gw('bb-waste-backV'),
    face_glue_code:    _bbPicked.faceG ? _bbPicked.faceG.code : null, face_glue_usage_g:gn('bb-qty-faceG'),
    back_glue_code:    _bbPicked.backG ? _bbPicked.backG.code : null, back_glue_usage_g:gn('bb-qty-backG'),
  };
  try{
    await api('/api/bom-builder','POST',body);
    toast('BOM saved for '+code);
    _bbAllFg = await api('/api/fg').catch(()=>_bbAllFg);
    // Re-render first (restores the panel to its home), THEN collapse it — so an
    // in-place edit closes cleanly instead of leaving the editor open mid-list.
    await loadBom();
    bootstrap.Collapse.getInstance(document.getElementById('bom-builder-panel'))?.hide();
  }catch(e){ toast('Save failed: '+e.message,'danger'); }
}

// BOM LIST — add Edit button to each card
function renderBom(rows){
  // Move the in-place editor back home first, so replacing bom-list's innerHTML
  // below doesn't destroy the relocated builder panel.
  _bbRestorePanelHome();
  document.getElementById('bom-count').textContent=`${rows.length} SKU${rows.length!==1?'s':''}`;
  document.getElementById('bom-list').innerHTML=rows.map(r=>`
    <div class="card mb-2" data-bomcard="${r.sku_code}">
      <div class="card-body py-2 px-3">
        <div class="d-flex justify-content-between align-items-start mb-2">
          <div>
            <span class="fw-bold text-primary me-2">${r.sku_code}</span>
            <span class="text-secondary">${r.sku_name||''}</span>
          </div>
          <div class="d-flex align-items-center gap-2">
            <span class="badge bg-light text-dark border me-1">${r.pallet_qty} pcs/pallet</span>
            <span class="badge bg-success-subtle text-success border-success border">฿${(r.cost_per_sheet||0).toLocaleString(undefined,{minimumFractionDigits:2,maximumFractionDigits:2})}/sheet</span>
            <span class="badge bg-primary-subtle text-primary border-primary border ms-1">฿${(r.total_cost||0).toLocaleString(undefined,{maximumFractionDigits:0})}/pallet</span>
            <button class="btn btn-sm btn-outline-secondary py-0" onclick="editBomCard('${r.sku_code}')"><i class="bi bi-pencil"></i></button>
            <button class="btn btn-sm btn-outline-danger py-0" title="Delete BOM" onclick="deleteBomCard('${r.sku_code}')"><i class="bi bi-trash"></i></button>
          </div>
        </div>
        <div class="row g-2">
          <div class="col-auto"><small class="text-muted fw-semibold d-block mb-1">BASE BOARD</small>${matPill(r.base_board,'')}</div>
          <div class="col-auto"><small class="text-muted fw-semibold d-block mb-1">FACE VENEER</small>${matPill(r.face_veneer,'face')}</div>
          <div class="col-auto"><small class="text-muted fw-semibold d-block mb-1">BACK VENEER</small>${matPill(r.back_veneer,'back')}</div>
          <div class="col-auto"><small class="text-muted fw-semibold d-block mb-1">FACE GLUE</small>${gluePill(r.face_glue)}</div>
          <div class="col-auto"><small class="text-muted fw-semibold d-block mb-1">BACK GLUE</small>${gluePill(r.back_glue)}</div>
        </div>
      </div>
    </div>`).join('');
}

async function deleteBomCard(skuCode){
  if(!confirm(`Delete the BOM for ${skuCode}?\n\nThis removes the SKU and its recipe. It is blocked if the SKU has sales or production orders.`)) return;
  try{
    await api('/api/fg-bom/'+encodeURIComponent(skuCode),'DELETE');
    toast('BOM deleted: '+skuCode);
    loadBom();
  }catch(e){ toast('Delete failed: '+e.message,'danger'); }
}

async function editBomCard(skuCode){
  const panel = document.getElementById('bom-builder-panel');
  // Capture the builder's home position once, so it can be restored later.
  if(panel && !_bbPanelHome){
    _bbPanelHome = {parent: panel.parentElement, next: panel.nextElementSibling};
  }
  // Relocate the builder directly beneath the edited card BEFORE showing it, so
  // the form expands in place — no scrolling to the top of the page.
  const sel = (window.CSS && CSS.escape) ? CSS.escape(skuCode) : skuCode;
  const card = document.querySelector('[data-bomcard="'+sel+'"]');
  if(card && panel) card.insertAdjacentElement('afterend', panel);
  bootstrap.Collapse.getOrCreateInstance(panel).show();
  // Wait for the picker options to load before populating the form, otherwise
  // the glue dropdown loses its selection when loadBomBuilder finishes late.
  if(!_bbLoaded) await loadBomBuilder();
  await bbLoadFg(skuCode);
  if(card && panel) panel.scrollIntoView({behavior:'smooth', block:'nearest'});
}

// ════════════════════════════════════════════════════════════
// COMPOUND FORMULA MANAGEMENT (Glue + Bleaching)
// ════════════════════════════════════════════════════════════
let _compoundData = { glue: [], bleaching: [] };
let _compoundLoaded = { glue: false, bleaching: false };

async function loadCompoundTab(type){
  if(!_compoundLoaded[type]){ await refreshCompound(type); }
}

// Bridge: open the shared Glue Recipe Builder modal from the BOM tab.
// Must write to _gmRecipes directly — it's declared with `let` so a
// window._gmRecipes assignment creates an unrelated global and the modal's
// lookup still hits an empty array, falling back to the "New Recipe" path.
async function bomGlueEdit(recipeId){
  let rs;
  try {
    rs = await api('/api/glue-recipes?kind=glue') || [];
  } catch(e){
    toast('Failed to load recipes: '+(e.message||e), 'danger');
    return;
  }
  _gmRecipes = rs;
  // Hand the OBJECT to the editor rather than relying on it re-finding the row
  // in the cache. String-safe match avoids number/string id mismatches that
  // used to silently drop into a blank "New Recipe" modal.
  const r = rs.find(x => String(x.id) === String(recipeId));
  if(!r){
    toast(`Glue recipe #${recipeId} not found — cannot edit`, 'danger');
    return;
  }
  if(typeof gmOpenRecipe === 'function') await gmOpenRecipe(r);
}
async function bomGlueDelete(recipeId, code){
  if(!confirm(`Delete glue recipe "${code}"?\n\nThis cannot be undone. Any FG BOM lines pointing at this recipe will lose their cost.`)) return;
  try{
    await api(`/api/glue-recipes/${recipeId}`, 'DELETE');
    toast(`Deleted ${code}`,'success');
    window._glueRecipesCache = null;
    await refreshCompound('glue');
  }catch(e){ alert('Delete failed: '+(e.message||e)); }
}

async function refreshCompound(type){
  _compoundLoaded[type] = true;
  // Glue and bleach share the glue_recipes table but are tagged by `kind`, so
  // each tab only sees (and can delete) its own formulas.
  const kind = (type === 'glue') ? 'glue' : 'bleach';
  const data = await api('/api/glue-recipes/with-ingredients?kind='+kind).catch(()=>[]);
  _compoundData[type] = data;
  renderCompound(type, data);
}

function filterCompound(type, q){
  const s = q.toLowerCase();
  const data = s ? _compoundData[type].filter(c=>(c.code+' '+(c.name||'')).toLowerCase().includes(s)) : _compoundData[type];
  renderCompound(type, data);
}

function renderCompound(type, data){
  const listId = type==='glue' ? 'glue-list' : 'bleach-list';
  const countId = type==='glue' ? 'glue-count' : 'bleach-count';
  const el = document.getElementById(listId);
  const ce = document.getElementById(countId);
  if(ce) ce.textContent = data.length+' formula'+(data.length!==1?'s':'');
  if(!el) return;
  // Glue tab: full BOM Builder list — every row has Edit / Delete.
  // Clicking + New or Edit opens gmRecipeModal (the shared recipe editor).
  if(type === 'glue'){
    if(!data.length){
      el.innerHTML = '<tr><td colspan="7" class="text-center text-muted py-3">No glue recipes yet — click <b>+ New Glue Recipe</b> to create one.</td></tr>';
      return;
    }
    // Need full recipe rows (with veneer_thickness etc.) — fetch from
    // /api/glue-recipes once and cache so the modal can pre-fill correctly
    if(!window._glueRecipesCache){
      api('/api/glue-recipes?kind=glue').then(rs => { window._glueRecipesCache = rs || []; renderCompound('glue', data); }).catch(()=>{});
    }
    el.innerHTML = data.map(c => {
      const cost  = c.cost_per_kg_mixed != null ? Number(c.cost_per_kg_mixed) : 0;
      const batch = c.batch_kg != null ? Number(c.batch_kg) : 0;
      const total = c.typical_batch_cost != null ? Number(c.typical_batch_cost) : cost*batch;
      const cached = (window._glueRecipesCache||[]).find(r => r.id === c.id) || {};
      const conds = [cached.veneer_thickness, cached.wood_species, cached.core_board].filter(Boolean).join(' · ');
      return `<tr>
        <td><code class="text-warning-emphasis fw-semibold">${c.code||''}</code></td>
        <td>${c.name||''}</td>
        <td class="small text-muted">${conds || '—'}</td>
        <td class="text-end">${batch.toFixed(3)}</td>
        <td class="text-end ${cost>0?'fw-semibold':'text-muted'}">${cost>0 ? '฿'+cost.toFixed(2) : '—'}</td>
        <td class="text-end ${total>0?'':'text-muted'}">${total>0 ? '฿'+total.toFixed(2) : '—'}</td>
        <td class="text-end" style="white-space:nowrap">
          <button class="btn btn-xs btn-outline-primary py-0 px-1" title="Edit recipe" onclick="bomGlueEdit(${c.id})">
            <i class="bi bi-pencil"></i>
          </button>
          <button class="btn btn-xs btn-outline-danger py-0 px-1" title="Delete recipe" onclick="bomGlueDelete(${c.id},'${(c.code||'').replace(/'/g,'&apos;')}')">
            <i class="bi bi-trash"></i>
          </button>
        </td>
      </tr>`;
    }).join('');
    return;
  }
  if(!data.length){
    el.innerHTML='<div class="alert alert-light text-muted small">No formulas yet. Click "+ New Formula" to create one.</div>';
    return;
  }
  const borderCol = type==='glue' ? 'border-warning' : 'border-info';
  const codeCol   = type==='glue' ? 'text-warning-emphasis' : 'text-info-emphasis';
  el.innerHTML = data.map(c=>{
    const linesHtml = (c.lines||[]).map(l=>`
      <tr>
        <td><code>${l.material_code}</code> <small class="text-muted">${l.material_name||''}</small></td>
        <td class="text-end">${l.ratio!=null ? l.ratio.toFixed(5) : '—'}</td>
        <td>${l.unit||''}</td>
        <td class="text-end text-muted small">${l.price!=null ? '฿'+parseFloat(l.price).toFixed(2)+'/kg':'—'}</td>
        <td><button class="btn btn-sm btn-outline-danger py-0 px-1" onclick="deleteCompoundLine(${l.id},${c.id},'${type}')"><i class="bi bi-x"></i></button></td>
      </tr>`).join('');
    return `
    <div class="card mb-2 ${borderCol}" style="border-left-width:3px">
      <div class="card-body py-2 px-3">
        <div class="d-flex justify-content-between align-items-center">
          <div>
            <code class="fw-bold ${codeCol}">${c.code}</code>
            <span class="ms-2 fw-semibold">${c.name||''}</span>
            ${c.batch_kg ? `<span class="badge bg-secondary ms-2">${c.batch_kg} kg/batch</span>` : ''}
            ${c.notes ? `<small class="text-muted ms-2">${c.notes}</small>` : ''}
          </div>
          <div class="d-flex gap-1">
            <button class="btn btn-sm btn-outline-secondary" data-bs-toggle="collapse" data-bs-target="#cl-${c.id}">
              <i class="bi bi-list-ul me-1"></i>${(c.lines||[]).length} ingredient${(c.lines||[]).length!==1?'s':''}
            </button>
            <button class="btn btn-sm btn-outline-danger" onclick="deleteCompound(${c.id},'${type}')"><i class="bi bi-trash"></i></button>
          </div>
        </div>
        <div class="collapse mt-2" id="cl-${c.id}">
          <table class="table table-sm table-bordered mb-0" style="font-size:.8rem">
            <thead class="table-light"><tr><th>Material</th><th class="text-end">Ratio (kg/kg-batch)</th><th>Unit</th><th class="text-end">Price</th><th></th></tr></thead>
            <tbody>
              ${linesHtml}
              <tr class="table-light">
                <td><input class="form-control form-control-sm" id="cl-mat-${c.id}" placeholder="Material code" style="min-width:120px"></td>
                <td><input type="number" class="form-control form-control-sm" id="cl-ratio-${c.id}" step="0.00001" placeholder="0.00000"></td>
                <td><input class="form-control form-control-sm" id="cl-unit-${c.id}" value="kg" style="width:55px"></td>
                <td></td>
                <td><button class="btn btn-sm btn-success" onclick="addCompoundLine(${c.id},'${type}')"><i class="bi bi-plus"></i></button></td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>`;
  }).join('');
}

function resetCompoundBuilder(type){
  const prefix = type==='glue' ? 'glue' : 'bleach';
  ['code','name','batch','notes'].forEach(f=>{ const e=document.getElementById(prefix+'-new-'+f); if(e) e.value=''; });
}

async function saveNewCompound(type){
  const prefix = type==='glue' ? 'glue' : 'bleach';
  const code  = document.getElementById(prefix+'-new-code').value.trim();
  const name  = document.getElementById(prefix+'-new-name').value.trim();
  const batch = parseFloat(document.getElementById(prefix+'-new-batch').value)||null;
  const notes = document.getElementById(prefix+'-new-notes').value.trim();
  if(!code){ toast('Code is required','danger'); return; }
  try{
    // Field names map to glue_recipes columns: code → recipe_code, batch_kg → total_kg.
    // Tag by kind so a bleach formula is independent of the glue list.
    await api('/api/glue-recipes','POST',{recipe_code:code, name, total_kg:batch, notes,
                                          kind: (type==='glue'?'glue':'bleach')});
    toast('Formula created: '+code);
    const panelId = type==='glue' ? 'glue-builder-panel' : 'bleach-builder-panel';
    bootstrap.Collapse.getInstance(document.getElementById(panelId))?.hide();
    await refreshCompound(type);
  }catch(e){ toast(e.message,'danger'); }
}

async function deleteCompound(id, type){
  if(!confirm('Delete this formula and all its ingredients?')) return;
  try{
    await api('/api/glue-recipes/'+id,'DELETE');
    toast('Deleted');
    await refreshCompound(type);
  }catch(e){ toast(e.message,'danger'); }
}

// Inline add/delete ingredient buttons (Bleach tab only). These hit endpoints
// that became no-ops during Phase B and need to be rewritten against
// glue_recipes.material_links — tracked as a separate task. Until then the
// canonical path is: click "Edit" on the recipe row to use the full editor.
function addCompoundLine(compoundId, type){
  toast('Use the Edit button on the recipe row to add ingredients.', 'warning');
}
function deleteCompoundLine(lineId, compoundId, type){
  toast('Use the Edit button on the recipe row to remove ingredients.', 'warning');
}

// ════════════════════════════════════════════════════════════
// PACKING SPEC MANAGEMENT
// ════════════════════════════════════════════════════════════
let _packingData = [];
let _packingLoaded = false;
let _packMats = [];   // packing consumables for the line-material picker

async function loadPackingTab(){
  if(!_packingLoaded){ await refreshPacking(); }
}

async function refreshPacking(){
  _packingLoaded = true;
  const [data, mats] = await Promise.all([
    api('/api/packing-skus-full').catch(()=>[]),
    api('/api/materials').catch(()=>[]),
  ]);
  // Packing BOM lines pull from packing/consumable/other materials so the
  // user picks instead of typing codes. 'packing' first.
  const W = { packing:0, adhesive:1, other:2 };
  _packMats = (mats||[]).filter(m => m.type in W)
    .sort((a,b)=> (W[a.type]-W[b.type]) || String(a.code||'').localeCompare(String(b.code||'')));
  _packingData = data;
  renderPacking(data);
}

function _packMatOptions(){
  if(!_packMats.length)
    return '<option value="">— no packing materials yet (add in Raw Materials) —</option>';
  return '<option value="">— select material —</option>' + _packMats.map(m =>
    `<option value="${m.code||''}" data-unit="${m.unit||''}">[${m.code||''}] ${escapeHtml(m.name||'')}${m.unit?' ('+m.unit+')':''}</option>`).join('');
}
function _packPickUnit(pid){
  const sel = document.getElementById('pl-mat-'+pid);
  const u = sel && sel.selectedOptions[0] && sel.selectedOptions[0].dataset.unit;
  if(u){ const ue = document.getElementById('pl-unit-'+pid); if(ue) ue.value = u; }
}

function filterPacking(q){
  const s = q.toLowerCase();
  const data = s ? _packingData.filter(p=>(p.code+' '+(p.name||'')+' '+(p.customer||'')).toLowerCase().includes(s)) : _packingData;
  renderPacking(data);
}

function renderPacking(data){
  const el = document.getElementById('pack-list');
  const ce = document.getElementById('pack-count');
  if(ce) ce.textContent = data.length+' spec'+(data.length!==1?'s':'');
  if(!el) return;
  if(!data.length){
    el.innerHTML='<div class="alert alert-light text-muted small">No packing specs yet. Click "+ New Packing Spec" to create one.</div>';
    return;
  }
  el.innerHTML = data.map(p=>{
    const linesHtml = (p.lines||[]).map(l=>`
      <tr>
        <td class="text-center">${l.seq||''}</td>
        <td><code>${l.material_code}</code> <small class="text-muted">${l.material_name||''}</small></td>
        <td class="text-end">${l.qty!=null?l.qty:''}</td>
        <td>${l.qty_unit||''}</td>
        <td class="text-end text-muted small">${l.price!=null?'฿'+parseFloat(l.price).toFixed(2):'—'}</td>
        <td><button class="btn btn-sm btn-outline-danger py-0 px-1" onclick="deletePackingLine(${l.id},${p.id})"><i class="bi bi-x"></i></button></td>
      </tr>`).join('');
    const nextSeq = (p.lines||[]).length + 1;
    return `
    <div class="card mb-2 border-success" style="border-left-width:3px">
      <div class="card-body py-2 px-3">
        <div class="d-flex justify-content-between align-items-center">
          <div>
            <code class="fw-bold text-success">${p.code}</code>
            <span class="ms-2 fw-semibold">${p.name||''}</span>
            ${p.customer ? `<span class="badge bg-light text-dark border ms-2">${p.customer}</span>` : ''}
            ${p.notes ? `<small class="text-muted ms-2">${p.notes}</small>` : ''}
          </div>
          <div class="d-flex gap-1">
            <button class="btn btn-sm btn-outline-secondary" data-bs-toggle="collapse" data-bs-target="#pl-${p.id}">
              <i class="bi bi-list-ul me-1"></i>${(p.lines||[]).length} material${(p.lines||[]).length!==1?'s':''}
            </button>
            <button class="btn btn-sm btn-outline-danger" onclick="deletePacking(${p.id})"><i class="bi bi-trash"></i></button>
          </div>
        </div>
        <div class="collapse mt-2" id="pl-${p.id}">
          <table class="table table-sm table-bordered mb-0" style="font-size:.8rem">
            <thead class="table-light"><tr><th>Seq</th><th>Material</th><th class="text-end">Qty</th><th>Unit</th><th class="text-end">Unit Price</th><th></th></tr></thead>
            <tbody>
              ${linesHtml}
              <tr class="table-light">
                <td><input type="number" class="form-control form-control-sm" id="pl-seq-${p.id}" value="${nextSeq}" style="width:50px"></td>
                <td><select class="form-select form-select-sm" id="pl-mat-${p.id}" style="min-width:160px" onchange="_packPickUnit(${p.id})">${_packMatOptions()}</select></td>
                <td><input type="number" class="form-control form-control-sm" id="pl-qty-${p.id}" value="1" step="0.01" style="width:70px"></td>
                <td><input class="form-control form-control-sm" id="pl-unit-${p.id}" value="pallet" style="width:75px"></td>
                <td></td>
                <td><button class="btn btn-sm btn-success" onclick="addPackingLine(${p.id})"><i class="bi bi-plus"></i></button></td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>`;
  }).join('');
}

function resetPackingBuilder(){
  ['pack-new-code','pack-new-name','pack-new-customer','pack-new-notes'].forEach(id=>{
    const e=document.getElementById(id); if(e) e.value='';
  });
}

async function saveNewPacking(){
  const code     = document.getElementById('pack-new-code').value.trim();
  const name     = document.getElementById('pack-new-name').value.trim();
  const customer = document.getElementById('pack-new-customer').value.trim();
  const notes    = document.getElementById('pack-new-notes').value.trim();
  if(!code){ toast('Code is required','danger'); return; }
  try{
    await api('/api/packing-skus','POST',{code,name,customer,notes});
    toast('Packing spec created: '+code);
    bootstrap.Collapse.getInstance(document.getElementById('pack-builder-panel'))?.hide();
    await refreshPacking();
  }catch(e){ toast(e.message,'danger'); }
}

async function deletePacking(id){
  if(!confirm('Delete this packing spec and all its material lines?')) return;
  try{
    await api('/api/packing-skus/'+id,'DELETE');
    toast('Deleted');
    await refreshPacking();
  }catch(e){ toast(e.message,'danger'); }
}

async function addPackingLine(packingId){
  const seq  = parseInt(document.getElementById('pl-seq-'+packingId).value)||0;
  const code = document.getElementById('pl-mat-'+packingId).value.trim();
  const qty  = parseFloat(document.getElementById('pl-qty-'+packingId).value)||1;
  const unit = document.getElementById('pl-unit-'+packingId).value.trim()||'pallet';
  if(!code){ toast('Select a packing material first','warning'); return; }
  try{
    await api('/api/packing-skus/'+packingId+'/lines','POST',{material_code:code,qty,qty_unit:unit,seq});
    toast('Material added');
    await refreshPacking();
    setTimeout(()=>{ const el=document.getElementById('pl-'+packingId); if(el&&!el.classList.contains('show')) new bootstrap.Collapse(el).show(); },150);
  }catch(e){ toast(e.message,'danger'); }
}

async function deletePackingLine(lineId, packingId){
  try{
    await api('/api/packing-lines/'+lineId,'DELETE');
    await refreshPacking();
    setTimeout(()=>{ const el=document.getElementById('pl-'+packingId); if(el&&!el.classList.contains('show')) new bootstrap.Collapse(el).show(); },150);
  }catch(e){ toast(e.message,'danger'); }
}




// ════════════════════════════════════════════════════════════
// Smart post-report flow (SL_DEPT_OPTIONS + slPostReportPrompt)
// ════════════════════════════════════════════════════════════
// ══════════════════════════════════════════════════════════════
// SMART POST-REPORT FLOW — split / error / move-and-where
// Wraps existing submit* functions so logging behaviour is unchanged.
// Call slPostReportPrompt(batch, pcsReported) after a successful station log.
// ══════════════════════════════════════════════════════════════
const SL_DEPT_OPTIONS = {
  laminating: ['cold_press'],
  cold_press: ['repair','sanding','hot_press'],
  repair:     ['sanding','hot_press'],
  sanding:    ['hot_press','grading'],
  hot_press:  ['grading','sanding'],
  grading:    ['packing','repair'],
  packing:    ['fg_receiving'],
  fc:         ['laminating'],
};
// Station Leader Hub line options — main production lines only (excludes
// aux PUV/PVS/PSP which don't have a station-leader workflow).
function SL_LINE_OPTIONS_get(){
  // Main lamination lines + FC (its own 'prep' line, where a batch's first
  // step happens). Keeps FC selectable in the Station Hub without putting it
  // on the main line board.
  const codes = [...catalogLineCodes('prep'), ...catalogLineCodes('main')];
  return codes.length ? codes : ['FC','P01','P02','P37'];
}

function slPostReportPrompt(batch, pcsReported, opts){
  opts = opts || {};
  const totalPcs = Number(batch.total_pcs || (batch.quantity*(batch.pallet_qty||1)) || 0);
  const reported = Number(pcsReported || 0);
  const remainder = Math.max(0, totalPcs - reported);
  const dept = (batch.current_department||'').toLowerCase();
  const nexts = SL_DEPT_OPTIONS[dept] || [];
  // Short-circuit: if no discrepancy AND caller pre-selected a destination,
  // do the move immediately without showing the modal at all.
  if(opts.autoConfirmIfClean && remainder === 0 && opts.presetDept){
    const body = {
      to_department: opts.presetDept,
      moved_by: localStorage.getItem('erp_user_display')||'station',
      notes: 'Auto-moved after laminating log',
    };
    if(opts.presetLine) body.production_line = opts.presetLine;
    api(`/api/batches/${batch.id}/move`,'POST',body)
      .then(()=>{ toast(`Moved to ${opts.presetDept.replace(/_/g,' ')}`,'success');
                  if(typeof stLoad==='function') stLoad(); })
      .catch(e => alert('Move failed: '+(e.message||e)));
    return;
  }
  // Build modal HTML on the fly
  const m = document.getElementById('sl-post-modal') || (function(){
    const d=document.createElement('div');
    d.id='sl-post-modal'; d.className='modal fade'; d.tabIndex=-1;
    d.innerHTML=`<div class="modal-dialog"><div class="modal-content">
      <div class="modal-header"><h5 class="modal-title"><i class="bi bi-arrow-right-circle me-2"></i>What next?</h5>
        <button type="button" class="btn-close" data-bs-dismiss="modal"></button></div>
      <div class="modal-body" id="sl-post-body"></div>
      <div class="modal-footer"><button class="btn btn-sm btn-outline-secondary" data-bs-dismiss="modal">Cancel</button></div>
    </div></div>`;
    document.body.appendChild(d); return d;
  })();
  const body = document.getElementById('sl-post-body');
  const discrepancy = remainder > 0;
  body.innerHTML = `
    <div class="${discrepancy?'alert alert-warning':'alert alert-success'} py-2 small">
      <b>${batch.batch_number}</b> — Reported <b>${reported}</b> of <b>${totalPcs}</b> pcs.
      ${discrepancy ? `<span class="text-danger">Remaining ${remainder} pcs unreported.</span>` : 'All units reported.'}
    </div>
    ${discrepancy?`
      <div class="card mb-2"><div class="card-body py-2 small">
        <div class="fw-semibold mb-1"><i class="bi bi-question-circle me-1"></i>Is the difference an error, or a real partial?</div>
        <button class="btn btn-sm btn-outline-warning mb-1 w-100 text-start"
          onclick="slPostFixReport(${batch.id})">
          <i class="bi bi-arrow-counterclockwise me-1"></i><b>Error</b> — open the report again and fix the pcs count
        </button>
        <button class="btn btn-sm btn-outline-info mb-1 w-100 text-start"
          onclick="slPostSplitAndMove(${batch.id}, ${reported}, ${remainder})">
          <i class="bi bi-arrows-collapse-vertical me-1"></i><b>Split</b> — move ${reported} pcs onward, keep ${remainder} pcs at this station
        </button>
        <button class="btn btn-sm btn-outline-danger mb-1 w-100 text-start"
          onclick="slPostMoveAsIs(${batch.id})">
          <i class="bi bi-exclamation-triangle me-1"></i><b>Carry the discrepancy</b> — move whole batch with the ${remainder} pcs flagged as scrap/loss
        </button>
      </div></div>
    `:''}
    <div class="card"><div class="card-body py-2">
      <div class="fw-semibold mb-2 small"><i class="bi bi-arrow-right-circle me-1"></i>Move to…</div>
      <div class="row g-2">
        <div class="col-md-7"><label class="form-label small">Department</label>
          <select class="form-select form-select-sm" id="sl-post-dept">
            ${nexts.map(d=>`<option value="${d}">${d.replace(/_/g,' ')}</option>`).join('')}
            <option disabled>──</option>
            ${Object.keys(SL_DEPT_OPTIONS).filter(d=>!nexts.includes(d)&&d!==dept).map(d=>`<option value="${d}">${d.replace(/_/g,' ')}</option>`).join('')}
          </select></div>
        <div class="col-md-5"><label class="form-label small">Production Line</label>
          <select class="form-select form-select-sm" id="sl-post-line">
            <option value="">— keep current —</option>
            ${SL_LINE_OPTIONS_get().map(l=>`<option value="${l}"${batch.production_line===l?' selected':''}>${l}</option>`).join('')}
          </select></div>
        <div class="col-12"><label class="form-label small">Notes</label>
          <input class="form-control form-control-sm" id="sl-post-notes" placeholder="Optional note for the move"></div>
        <div class="col-12 text-end">
          <button class="btn btn-sm btn-primary" onclick="slPostDoMove(${batch.id}, ${discrepancy?'true':'false'})">
            <i class="bi bi-check2-circle me-1"></i>Confirm Move
          </button>
        </div>
      </div>
    </div></div>`;
  new bootstrap.Modal(m).show();
  // Pre-select dept/line if caller passed presets (always wins over default)
  if(opts.presetDept){
    const dEl = document.getElementById('sl-post-dept');
    if(dEl){
      // Ensure the preset is in the option list
      if(![...dEl.options].some(o => o.value === opts.presetDept)){
        const opt = document.createElement('option'); opt.value = opts.presetDept;
        opt.textContent = opts.presetDept.replace(/_/g,' '); dEl.appendChild(opt);
      }
      dEl.value = opts.presetDept;
    }
  }
  if(opts.presetLine){
    const lEl = document.getElementById('sl-post-line');
    if(lEl) lEl.value = opts.presetLine;
  }
}

async function slPostDoMove(batchId, withDiscrepancy){
  const dept = document.getElementById('sl-post-dept').value;
  const line = document.getElementById('sl-post-line').value;
  const notes= document.getElementById('sl-post-notes').value;
  const body = {to_department: dept, moved_by: localStorage.getItem('erp_user_display')||'station', notes};
  if(line) body.production_line = line;   // backend may ignore — best-effort
  try{
    await api(`/api/batches/${batchId}/move`,'POST',body);
    bootstrap.Modal.getInstance(document.getElementById('sl-post-modal'))?.hide();
    toast(`Moved to ${dept.replace(/_/g,' ')}${withDiscrepancy?' (with reported discrepancy)':''}`);
    if(typeof stLoad === 'function') stLoad();
  }catch(e){ alert('Move failed: '+(e.message||e)); }
}
async function slPostSplitAndMove(batchId, reportedPcs, remainderPcs){
  // Split the batch by pcs: `reportedPcs` part moves on, `remainderPcs` stays at the current station
  try{
    await api(`/api/batches/${batchId}/split-by-pcs`,'POST',
      {pcs_moving: reportedPcs, reason: 'Auto split after partial report'});
    // After split, the original batch keeps `remainderPcs` and a new batch holds `reportedPcs`.
    // Move the new batch to the chosen destination next.
    toast(`Batch split — ${reportedPcs} pcs ready to move, ${remainderPcs} pcs stay`);
    if(typeof stLoad === 'function') await stLoad();
    bootstrap.Modal.getInstance(document.getElementById('sl-post-modal'))?.hide();
  }catch(e){ alert('Split failed: '+(e.message||e)); }
}
function slPostFixReport(batchId){
  bootstrap.Modal.getInstance(document.getElementById('sl-post-modal'))?.hide();
  toast('Open the same station form and re-submit with the corrected pcs count', 'warning');
}
function slPostMoveAsIs(batchId){
  // Just confirm and submit the move (notes pre-filled to mark discrepancy)
  document.getElementById('sl-post-notes').value = 'Moved with reported discrepancy — flagged as scrap/loss';
  toast('Discrepancy noted. Pick destination and confirm.', 'warning');
}




// ════════════════════════════════════════════════════════════
// Station Leader Hub (loadStationLog + slh* + sl*)
// ════════════════════════════════════════════════════════════
// ══════════════════════════════════════════════════════════
// STATION LOG — unified Station Leader Hub (dashboard + batches + station tools)
// ══════════════════════════════════════════════════════════
let _slhTab = 'dashboard';

async function loadStationLog(){
  if(!_allEmployees.length) _allEmployees = await api('/api/employees').catch(()=>[]);
  await msLoadMachines();
  const u = getCurrentUser?.();
  const canSetup = u && (u.role === ROLE.PRODUCTION_PLANNING || u.role === ROLE.MANAGERIAL);
  ['sl-machine-setup-btn','slh-mach-setup-btn'].forEach(id => {
    const el = document.getElementById(id);
    if(el) el.style.display = canSetup ? '' : 'none';
  });
  // Show the Glue & Laminating mix/laminate toggle when that's the current scope.
  _slView = 'lam';
  const _dept0 = document.getElementById('sl-dept-scope')?.value || 'laminating';
  document.getElementById('sl-glue-toggle')?.classList.toggle('d-none', _dept0 !== 'laminating');
  await slLoadBatches();
  slhSwitchTab(_slhTab || 'dashboard');
}

// Auxiliary (request-only) lines — no production stations yet
const SLH_AUX_LINES = {
  PUV: 'UV Line',
  PVS: 'Veneer Slicing',
  PSP: 'Veneer Splicing',
};
let _slhAuxLine = null;

// In aux mode these tabs remain enabled (others are disabled).
const SLH_AUX_ALLOWED_TABS = new Set(['dashboard','stock','forklifts']);
// Original Dashboard label so we can restore on exit
let _slhDashboardLabelOrig = null;

function slhEnterAuxMode(line){
  _slhAuxLine = line;
  // Toggle tab availability: keep dashboard (relabel → Requests), Stock,
  // and Forklifts enabled. Disable the rest.
  document.querySelectorAll('#slh-tabs .nav-link').forEach(b => {
    const t = b.dataset.slhTab;
    const allowed = SLH_AUX_ALLOWED_TABS.has(t);
    if(allowed){
      b.classList.remove('disabled');
      b.style.opacity = '';
      b.style.pointerEvents = '';
    } else {
      b.classList.remove('active');
      b.classList.add('disabled');
      b.style.opacity = '0.45';
      b.style.pointerEvents = 'none';
    }
    if(t === 'dashboard'){
      if(_slhDashboardLabelOrig === null) _slhDashboardLabelOrig = b.innerHTML;
      b.innerHTML = '<i class="bi bi-send me-1"></i>Requests';
    }
  });
  // Synthetic dept for the station-stock / movements endpoints — aux lines
  // get their own "station" namespace keyed by the line code (lowercased).
  const dept = line.toLowerCase();
  const stDept = document.getElementById('st-dept');
  const stLine = document.getElementById('st-line');
  if(stDept) stDept.value = dept;
  if(stLine) stLine.value = line;
  const el = document.getElementById('slh-dynamic-header');
  if(el){
    el.innerHTML =
      `<span class="badge bg-warning text-dark me-2" style="font-size:.85rem">${line}</span>`+
      `<span class="badge bg-secondary me-2" style="font-size:.85rem">${SLH_AUX_LINES[line]}</span>`+
      `<span class="text-muted">AUX HUB</span>`;
  }
  const lbl = document.getElementById('slh-aux-line-label');
  if(lbl) lbl.textContent = `${line} — ${SLH_AUX_LINES[line]}`;
  const chip = document.getElementById('sl-scope-chip');
  if(chip) chip.textContent = `${line} · ${SLH_AUX_LINES[line]}`;
  // Show the aux/requests pane by default
  _slhAuxSwitchPane('dashboard');
}

function slhExitAuxMode(){
  if(_slhAuxLine === null) return;
  _slhAuxLine = null;
  document.querySelectorAll('#slh-tabs .nav-link').forEach(b => {
    b.classList.remove('disabled');
    b.style.opacity = '';
    b.style.pointerEvents = '';
    if(b.dataset.slhTab === 'dashboard' && _slhDashboardLabelOrig !== null){
      b.innerHTML = _slhDashboardLabelOrig;
    }
  });
  _slhDashboardLabelOrig = null;
  // Hide the aux pane; let normal scope flow pick the active tab
  const auxPane = document.getElementById('slh-pane-aux');
  if(auxPane) auxPane.classList.add('d-none');
}

// In aux mode, hand-roll the tab switching (no Batches/Team/HR work).
function _slhAuxSwitchPane(tab){
  if(!SLH_AUX_ALLOWED_TABS.has(tab)) return;
  _slhTab = tab;
  document.querySelectorAll('#slh-tabs .nav-link').forEach(b =>
    b.classList.toggle('active', b.dataset.slhTab === tab));
  document.querySelectorAll('#page-station-log .slh-pane').forEach(p =>
    p.classList.add('d-none'));
  if(tab === 'dashboard'){
    document.getElementById('slh-pane-aux')?.classList.remove('d-none');
    slhAuxLoad();
  } else if(tab === 'stock'){
    // Reuse the existing Stock & Movements embedding (combines both panes)
    try { _slhEmbedStockAndMovements(); } catch{}
    document.getElementById('slh-pane-stock')?.classList.remove('d-none');
    try { _slhEnsureStLoaded?.(); } catch{}
    try { stLoadStock?.(); } catch{}
    try { stLoadMovements?.(); } catch{}
  } else if(tab === 'forklifts'){
    document.getElementById('slh-pane-forklifts')?.classList.remove('d-none');
    try { flkLoad(); } catch{}
    try { oilLoad(); } catch{}
  }
}

async function slhAuxLoad(){
  if(!_slhAuxLine) return;
  // Load consumable + FC transfer requests, filter by this line client-side
  // (the existing endpoints don't take a line filter — small enough to filter here).
  const [crs, fctrs] = await Promise.all([
    api('/api/consumable-requests').catch(()=>[]),
    api('/api/fc/transfer-requests').catch(()=>[]),
  ]);
  const myLine = _slhAuxLine;
  const _prioBadge = p => p==1?'<span class="badge bg-danger">P1</span>':p==3?'<span class="badge bg-success">P3</span>':'<span class="badge bg-warning text-dark">P2</span>';
  const _stat = s => {
    const cls = {NEW:'secondary',PENDING:'secondary',PARTIAL:'warning text-dark',FULFILLED:'success',CANCELLED:'dark'}[s] || 'light text-dark border';
    return `<span class="badge bg-${cls}">${s||'—'}</span>`;
  };
  // Consumable requests
  const crTb = document.getElementById('slh-aux-cr-tbody');
  const crMine = (crs||[]).filter(r => (r.line_id||'').toUpperCase() === myLine);
  if(!crMine.length){
    crTb.innerHTML = '<tr><td colspan="7" class="text-center text-muted py-3">No requests for this line yet.</td></tr>';
  } else {
    crTb.innerHTML = crMine.slice(0,30).map(r=>`
      <tr>
        <td class="small fw-semibold">${r.request_id||('#'+r.id)}</td>
        <td>${r.material_name||''}</td>
        <td class="text-end">${r.qty_requested} ${r.unit||''}</td>
        <td>${_prioBadge(r.priority)}</td>
        <td class="small">${r.needed_by||'—'}</td>
        <td>${_stat(r.status)}</td>
        <td class="small text-muted">${(r.created_at||'').slice(0,16).replace('T',' ')}</td>
      </tr>`).join('');
  }
  // FC transfer requests — these don't natively carry a line; we tag the
  // notes field with "[line:PUV]" on submit so we can filter back.
  const fcTb = document.getElementById('slh-aux-fctr-tbody');
  const fctrMine = (fctrs||[]).filter(r => (r.notes||'').includes(`[line:${myLine}]`));
  if(!fctrMine.length){
    fcTb.innerHTML = '<tr><td colspan="7" class="text-center text-muted py-3">No FC requests for this line yet.</td></tr>';
  } else {
    fcTb.innerHTML = fctrMine.slice(0,30).map(r=>`
      <tr>
        <td class="small fw-semibold">${r.request_id||('#'+r.id)}</td>
        <td>${r.material_name||''}</td>
        <td class="text-end">${r.qty_requested} ${r.unit||''}</td>
        <td>${_prioBadge(r.priority)}</td>
        <td class="small">${r.needed_by||'—'}</td>
        <td>${_stat(r.status)}</td>
        <td class="small text-muted">${(r.created_at||'').slice(0,16).replace('T',' ')}</td>
      </tr>`).join('');
  }
}

async function slhAuxOpenConsumable(){
  if(!_slhAuxLine) return;
  // Reuse the existing consumable modal but pre-fill line + auto-pick a
  // sensible department (use the line code as a synthetic "department")
  await crOpenNew();
  new bootstrap.Modal(document.getElementById('newConsumableModal')).show();
  setTimeout(()=>{
    const lineSel = document.getElementById('cr-line-id');
    if(lineSel){
      // Ensure aux line is in the picker
      if(![...lineSel.options].some(o => o.value === _slhAuxLine)){
        const opt = document.createElement('option');
        opt.value = _slhAuxLine; opt.textContent = _slhAuxLine;
        lineSel.appendChild(opt);
      }
      lineSel.value = _slhAuxLine;
    }
    // Add the aux line code as a department option if user has no depts yet
    const deptSel = document.getElementById('cr-department');
    if(deptSel && (!deptSel.value || deptSel.options.length === 1)){
      const opt = document.createElement('option');
      opt.value = _slhAuxLine.toLowerCase();
      opt.textContent = `${_slhAuxLine} — ${SLH_AUX_LINES[_slhAuxLine]}`;
      deptSel.appendChild(opt);
      deptSel.value = opt.value;
    }
  }, 200);
}

async function slhAuxOpenFcTransfer(){
  if(!_slhAuxLine) return;
  // Reuse the existing FC transfer modal; tag the notes so we can filter back
  if(typeof fctrOpen === 'function'){ fctrOpen(); }
  else new bootstrap.Modal(document.getElementById('fcTransferModal')).show();
  setTimeout(()=>{
    const notesEl = document.getElementById('fctr-notes');
    if(notesEl && !notesEl.value.includes('[line:')){
      notesEl.value = `[line:${_slhAuxLine}] ` + (notesEl.value || '');
    }
  }, 200);
}

// Station-scope labels shared by the buttons + header.
const SLH_DEPT_LABEL = {fc:'Feed Center',production:'Production',glue_mix:'Glue Mixing',
  laminating:'Glue & Laminating',cold_press:'Cold Press',repair:'Repair',sanding:'Sanding',
  hot_press:'Hot Press',grading:'Grading',packing:'Packing'};
// Short labels for the scope chip + dynamic header (FC shows as just "FC";
// the merged station shows the compact "Glue & Lam").
const SLH_DEPT_SHORT = {...SLH_DEPT_LABEL, fc:'FC', laminating:'Glue & Lam'};

// Department Leaders only operate the stations/lines they're assigned to, so the
// free-choice dropdowns are hidden and replaced by buttons for exactly those
// scopes. Everyone else keeps the dropdowns.
function slhRenderScopeButtons(){
  const selects = document.getElementById('sl-scope-selects');
  const btnBar  = document.getElementById('sl-scope-buttons');
  if(!selects || !btnBar) return;
  const user = (typeof getCurrentUser==='function') ? getCurrentUser() : null;
  if(!user || user.role !== ROLE.DEPARTMENT_LEADER){
    selects.classList.remove('d-none');
    btnBar.classList.add('d-none'); btnBar.classList.remove('d-flex');
    return;
  }
  selects.classList.add('d-none');
  btnBar.classList.remove('d-none'); btnBar.classList.add('d-flex');
  const depts = (typeof getCurrentDepts==='function') ? getCurrentDepts() : [];
  if(!depts.length){
    btnBar.innerHTML = '<span class="text-muted small"><i class="bi bi-exclamation-triangle me-1"></i>No station assigned — contact your administrator.</span>';
    return;
  }
  // De-dupe identical (dept,line) scopes; sort for a stable order.
  const seen = new Set();
  const scopes = [];
  depts.forEach(d => {
    let dv = (d.department || '').toLowerCase();
    if(dv === 'glue_mix') dv = 'laminating';  // merged into Glue & Laminating
    if(!SLH_DEPT_LABEL[dv]) return;          // skip unknown/legacy dept codes
    const ln = d.line_id || '';
    const key = dv + '|' + ln;
    if(seen.has(key)) return; seen.add(key);
    scopes.push({dept: dv, line: ln});
  });
  btnBar.innerHTML = scopes.map(s => {
    const lineLbl = s.line || 'All lines';
    return `<button class="btn btn-sm btn-outline-primary sl-scope-btn"
              onclick="slhPickScope('${s.dept}','${s.line}',this)">`+
           `${SLH_DEPT_LABEL[s.dept]} <span class="text-muted">· ${lineLbl}</span></button>`;
  }).join('');
  // Auto-select the first assigned scope.
  const first = btnBar.querySelector('.sl-scope-btn');
  if(first) first.click();
}

// ── Daily station report (print → Save as PDF, physically signed) ──
// One combined Thai + Chinese sheet (production + stock + utilisation). The
// print window's title = systematic filename so Save-as-PDF pre-fills e.g.
// 2026-06-22_P01_LAMINATING_daily.pdf. No digital sign-off — printed & signed.
const _SLH_REPORT_CSS = `
  *{box-sizing:border-box} body{font-family:'Tahoma','Microsoft Sans Serif',Arial,sans-serif;color:#111;margin:24px;font-size:12px}
  .coh{display:flex;align-items:center;gap:14px;border-bottom:3px solid #333;padding-bottom:8px;margin-bottom:8px}
  .coh img{height:50px} .coh .nm{font-size:17px;font-weight:bold} .coh .nm small{font-weight:normal;color:#444}
  .coh .addr{font-size:11px;color:#666}
  h1{font-size:16px;margin:6px 0 2px} h1 small{font-weight:normal;color:#555;font-size:.8em}
  h2{font-size:13px;margin:16px 0 6px;border-bottom:2px solid #333;padding-bottom:2px} h2 small{font-weight:normal;color:#666}
  .meta{font-size:12px;margin-bottom:4px}
  table{width:100%;border-collapse:collapse;margin-bottom:8px}
  th,td{border:1px solid #999;padding:4px 6px;text-align:left;vertical-align:top}
  th{background:#eee;font-size:11px} th small{display:block;color:#666;font-weight:normal}
  td.num,th.num{text-align:right;white-space:nowrap} tfoot td{font-weight:bold;background:#f5f5f5}
  .empty{color:#777;font-style:italic;padding:6px 0}
  .sign{margin-top:36px;display:flex;justify-content:space-between;gap:48px}
  .sign .box{flex:1} .sign .line{margin-top:38px;border-top:1px solid #333;padding-top:3px;text-align:center;font-size:11px}
  .foot{margin-top:20px;font-size:10px;color:#666}
  @media print{body{margin:10mm}}
`;
function _slhEsc(s){return String(s==null?'':s).replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));}
// Thai (primary) + Chinese (secondary) labels. Edit company name/address here.
const _RPT_COMPANY = { th:'บริษัท พีวีวูด', zh:'PVWood', addr:'' }; // addr shown if non-empty
const _RPT = {
  title:['รายงานการผลิตและสต๊อกประจำวัน','每日生产与库存报告'],
  line:['สายการผลิต','生产线'], station:['สถานี','工位'], date:['วันที่','日期'],
  jobs:['งานที่ผลิตเสร็จ','完成生产'], time:['เวลา','时间'], batch:['ล็อต','批次'],
  qty:['จำนวน','数量'], defect:['ของเสีย/NCG','不良品'], operator:['ผู้ปฏิบัติงาน','操作员'],
  notes:['หมายเหตุ','备注'], total:['รวม','合计'],
  balances:['ยอดสต๊อกสถานี','工位库存'], material:['วัสดุ','物料'],
  opening:['ยอดยกมา','期初'], change:['เปลี่ยนแปลง','变动'], closing:['ยอดคงเหลือ','期末'],
  movements:['การเคลื่อนไหวสต๊อก','库存变动'], type:['ประเภท','类型'],
  requests:['คำขอวัสดุสิ้นเปลือง','耗材申请'], status:['สถานะ','状态'],
  none:['ไม่มีข้อมูลในวันนี้','当天无数据'],
  leaderSign:['หัวหน้าสถานี — ลงชื่อ / วันที่','工位负责人 — 签字 / 日期'],
  supSign:['ผู้ควบคุม — ลงชื่อ / วันที่','主管 — 签字 / 日期'],
  gen:['จัดทำโดยระบบ PVWood ERP','由 PVWood ERP 系统生成'],
};
function _LT(k){ return _slhEsc((_RPT[k]||[k])[0]); }            // Thai only
function _LH(k){ const v=_RPT[k]||[k,'']; return `${_slhEsc(v[0])}<small>${_slhEsc(v[1])}</small>`; } // TH + ZH (header)
function _LB(k){ const v=_RPT[k]||[k,'']; return `${_slhEsc(v[0])} / ${_slhEsc(v[1])}`; }            // TH / ZH (inline)
async function _slhFetchDailyReport(){
  const dept = document.getElementById('sl-dept-scope')?.value || '';
  const line = document.getElementById('sl-line')?.value || '';
  const date = document.getElementById('sl-report-date')?.value || new Date().toISOString().slice(0,10);
  const qs = `department=${encodeURIComponent(dept)}${line?`&line_id=${encodeURIComponent(line)}`:''}&date=${date}`;
  const data = await api(`/api/station/daily-report?${qs}`);
  data._deptLabel = (typeof SLH_DEPT_LABEL!=='undefined' && SLH_DEPT_LABEL[dept]) || dept;
  data._lineLabel = line || 'ALL';
  return data;
}
function _slhReportFilename(data, kind){
  return `${data.date}_${(data.line_id||'ALL')}_${(data.department||'').toUpperCase()}_${kind}`;
}
function _slhCompanyHeader(){
  const a = _RPT_COMPANY.addr ? `<div class="addr">${_slhEsc(_RPT_COMPANY.addr)}</div>` : '';
  return `<div class="coh">
      <img src="/static/assets/pvwood-logo.svg" onerror="this.style.display='none'">
      <div><div class="nm">${_slhEsc(_RPT_COMPANY.th)} <small>${_slhEsc(_RPT_COMPANY.zh)}</small></div>${a}</div>
    </div>`;
}
function _slhSignBlock(){
  return `<div class="sign">
      <div class="box"><div class="line">${_LB('leaderSign')}</div></div>
      <div class="box"><div class="line">${_LB('supSign')}</div></div>
    </div>
    <div class="foot">${_LB('gen')} — ${new Date().toLocaleString()}</div>`;
}
function _slhOpenPrint(bodyHtml, filename){
  const w = window.open('', '_blank');
  if(!w){ toast('Allow pop-ups to print/save the report','warning'); return; }
  w.document.write(`<!doctype html><html lang="th"><head><meta charset="utf-8"><title>${_slhEsc(filename)}</title>`+
    `<style>${_SLH_REPORT_CSS}</style></head><body>${bodyHtml}</body></html>`);
  w.document.close();
  setTimeout(()=>{ try{ w.focus(); w.print(); }catch{} }, 350);
}
async function slhPrintDailyReport(){
  let data; try{ data = await _slhFetchDailyReport(); }catch(e){ toast('Report failed: '+(e.message||e),'danger'); return; }
  const jobs = data.jobs||[], bal = data.balances||[], mv = data.movements||[], rq = data.requests||[];
  const anyDefect = jobs.some(j => Number(j.defect)>0);
  // 1) Production jobs
  let qTot=0, dTot=0;
  const jobRows = jobs.map(j=>{ qTot+=Number(j.qty)||0; dTot+=Number(j.defect)||0; return `<tr>
      <td>${_slhEsc((j.logged_at||'').slice(11,16))}</td>
      <td>${_slhEsc(j.batch_id)}</td>
      <td class="num">${_slhEsc(j.qty)} <span style="color:#666">${_slhEsc(j.qty_label)}</span></td>
      ${anyDefect?`<td class="num">${_slhEsc(j.defect)}</td>`:''}
      <td>${_slhEsc(j.operator)}</td>
      <td>${_slhEsc(j.notes)}</td></tr>`; }).join('');
  const jobsTbl = jobs.length
    ? `<table><thead><tr><th>${_LH('time')}</th><th>${_LH('batch')}</th><th class="num">${_LH('qty')}</th>`+
      `${anyDefect?`<th class="num">${_LH('defect')}</th>`:''}<th>${_LH('operator')}</th><th>${_LH('notes')}</th></tr></thead>`+
      `<tbody>${jobRows}</tbody><tfoot><tr><td colspan="2">${_LB('total')}</td><td class="num">${qTot}</td>`+
      `${anyDefect?`<td class="num">${dTot}</td>`:''}<td colspan="2"></td></tr></tfoot></table>`
    : `<div class="empty">${_LB('none')}</div>`;
  // 2) Stock balances (opening / change / closing)
  const balTbl = bal.length
    ? `<table><thead><tr><th>${_LH('material')}</th><th class="num">${_LH('opening')}</th>`+
      `<th class="num">${_LH('change')}</th><th class="num">${_LH('closing')}</th></tr></thead><tbody>`+
      bal.map(b=>`<tr><td>${_slhEsc(b.code)} ${_slhEsc(b.name)}</td>`+
        `<td class="num">${_slhEsc(b.opening)} ${_slhEsc(b.unit||'')}</td>`+
        `<td class="num">${b.change>0?'+':''}${_slhEsc(b.change)}</td>`+
        `<td class="num">${_slhEsc(b.closing)} ${_slhEsc(b.unit||'')}</td></tr>`).join('')+
      `</tbody></table>`
    : `<div class="empty">${_LB('none')}</div>`;
  // 3) Movements
  const mvTbl = mv.length
    ? `<table><thead><tr><th>${_LH('time')}</th><th>${_LH('type')}</th><th>${_LH('material')}</th>`+
      `<th class="num">${_LH('qty')}</th><th>${_LH('batch')}</th><th>${_LH('notes')}</th></tr></thead><tbody>`+
      mv.map(m=>`<tr><td>${_slhEsc((m.created_at||'').slice(11,16))}</td><td>${_slhEsc(m.movement_type)}</td>`+
        `<td>${_slhEsc(m.material_code)} ${_slhEsc(m.material_name)}</td>`+
        `<td class="num">${_slhEsc(m.qty_change)} ${_slhEsc(m.unit||'')}</td>`+
        `<td>${_slhEsc(m.batch_ref)}</td><td>${_slhEsc(m.notes)}</td></tr>`).join('')+
      `</tbody></table>`
    : `<div class="empty">${_LB('none')}</div>`;
  // 4) Consumable requests
  const rqTbl = rq.length
    ? `<table><thead><tr><th>${_LH('time')}</th><th>${_LH('material')}</th><th class="num">${_LH('qty')}</th>`+
      `<th>${_LH('status')}</th></tr></thead><tbody>`+
      rq.map(r=>`<tr><td>${_slhEsc((r.created_at||'').slice(11,16))}</td><td>${_slhEsc(r.material_name)}</td>`+
        `<td class="num">${_slhEsc(r.qty_requested)} ${_slhEsc(r.unit||'')}</td><td>${_slhEsc(r.status)}</td></tr>`).join('')+
      `</tbody></table>`
    : `<div class="empty">${_LB('none')}</div>`;
  const body = _slhCompanyHeader() +
    `<h1>${_LT('title')} <small>${_slhEsc(_RPT.title[1])}</small></h1>` +
    `<div class="meta">${_LB('line')}: <b>${_slhEsc(data._lineLabel)}</b> &nbsp; ${_LB('station')}: <b>${_slhEsc(data._deptLabel)}</b> &nbsp; ${_LB('date')}: <b>${_slhEsc(data.date)}</b></div>` +
    `<h2>${_LT('jobs')} <small>${_slhEsc(_RPT.jobs[1])} (${jobs.length})</small></h2>` + jobsTbl +
    `<h2>${_LT('balances')} <small>${_slhEsc(_RPT.balances[1])}</small></h2>` + balTbl +
    `<h2>${_LT('movements')} <small>${_slhEsc(_RPT.movements[1])} (${mv.length})</small></h2>` + mvTbl +
    `<h2>${_LT('requests')} <small>${_slhEsc(_RPT.requests[1])} (${rq.length})</small></h2>` + rqTbl +
    _slhSignBlock();
  _slhOpenPrint(body, _slhReportFilename(data,'daily'));
}

// ── Daily Review tab — edit-in-place corrections (audited; stock reconciles) ──
let _slhReviewDept = '', _slhReviewLine = '', _slhReviewDate = '';
async function slhLoadReview(){
  const host = document.getElementById('slh-pane-review');
  if(!host) return;
  host.innerHTML = '<div class="text-muted small py-3">Loading…</div>';
  let data;
  try{ data = await _slhFetchDailyReport(); }
  catch(e){ host.innerHTML = `<div class="alert alert-warning py-2 small mb-0">Load failed: ${_slhEsc(e.message||e)}</div>`; return; }
  _slhReviewDept = data.department; _slhReviewLine = data.line_id || ''; _slhReviewDate = data.date;
  const jobs = data.jobs || [], mv = data.movements || [];
  const jobRows = jobs.map(j=>{
    const flagged = Number(j.flagged)>0;
    return `<tr class="${flagged?'table-warning':''}">
      <td class="small text-muted text-nowrap">${_slhEsc((j.logged_at||'').slice(11,16))}${flagged?' <span class="badge bg-warning text-dark" title="Upstream output was corrected — confirm this value, then save to clear.">review</span>':''}</td>
      <td><input class="form-control form-control-sm" style="width:130px" id="rvj-batch-${_slhEsc(j.log_id)}" value="${_slhEsc(j.batch_id)}"></td>
      <td class="text-nowrap"><input type="number" step="0.01" class="form-control form-control-sm d-inline-block" style="width:84px" id="rvj-qty-${_slhEsc(j.log_id)}" value="${_slhEsc(j.qty)}"> <span class="text-muted small">${_slhEsc(j.qty_label)}</span></td>
      <td class="small">${_slhEsc(j.operator)}</td>
      <td class="small">${_slhEsc(j.notes)}</td>
      <td><button class="btn btn-sm btn-primary" onclick="slhSaveJob('${_slhEsc(j.log_id)}')"><i class="bi bi-check2"></i></button></td>
    </tr>`;}).join('');
  const mvRows = mv.map(m=>`<tr>
      <td class="small text-muted text-nowrap">${_slhEsc((m.created_at||'').slice(11,16))}</td>
      <td class="small">${_slhEsc(m.movement_type)}</td>
      <td class="small">${_slhEsc(m.material_code)} ${_slhEsc(m.material_name)}</td>
      <td><input type="number" step="0.01" class="form-control form-control-sm" style="width:90px" id="rvm-qty-${m.id}" value="${_slhEsc(m.qty_change)}"></td>
      <td><input class="form-control form-control-sm" style="width:130px" id="rvm-batch-${m.id}" value="${_slhEsc(m.batch_ref)}"></td>
      <td><button class="btn btn-sm btn-primary" onclick="slhSaveMovement(${m.id})"><i class="bi bi-check2"></i></button></td>
    </tr>`).join('');
  const deptLbl = (typeof SLH_DEPT_LABEL!=='undefined' && SLH_DEPT_LABEL[_slhReviewDept]) || _slhReviewDept;
  host.innerHTML = `
    <div class="d-flex justify-content-between align-items-center mb-2 flex-wrap gap-2">
      <div><span class="badge bg-secondary">${_slhEsc(_slhReviewLine||'ALL')}</span>
        <span class="badge bg-info text-dark">${_slhEsc(deptLbl)}</span> <b>${_slhEsc(_slhReviewDate)}</b>
        <span class="text-muted small ms-2">(change the date in the header, then Refresh)</span></div>
      <div class="small text-muted"><i class="bi bi-info-circle me-1"></i>Edit a value then save — corrections are written to the audit log; movement-qty edits reconcile station stock.</div>
    </div>
    <h6 class="mt-1"><i class="bi bi-clipboard-data me-1"></i>Completed Jobs (${jobs.length})</h6>
    ${jobs.length ? `<div class="table-responsive"><table class="table table-sm table-bordered align-middle mb-3">
      <thead class="table-light"><tr><th>Time</th><th>Batch</th><th>Qty</th><th>Operator</th><th>Notes</th><th></th></tr></thead>
      <tbody>${jobRows}</tbody></table></div>` : '<div class="text-muted small mb-3">No completed jobs for this day.</div>'}
    <h6 class="mt-2"><i class="bi bi-box-seam me-1"></i>Stock Movements (${mv.length})</h6>
    ${mv.length ? `<div class="table-responsive"><table class="table table-sm table-bordered align-middle">
      <thead class="table-light"><tr><th>Time</th><th>Type</th><th>Material</th><th>Qty</th><th>Batch Ref</th><th></th></tr></thead>
      <tbody>${mvRows}</tbody></table></div>` : '<div class="text-muted small">No stock movements for this day.</div>'}`;
}
async function slhSaveJob(logId){
  const qEl = document.getElementById('rvj-qty-'+logId), bEl = document.getElementById('rvj-batch-'+logId);
  const qty = parseFloat(qEl.value), batch = (bEl.value||'').trim();
  try{
    await api(`/api/station/job/${encodeURIComponent(_slhReviewDept)}/${encodeURIComponent(logId)}`,'PATCH',
              {qty: isNaN(qty)?null:qty, batch_id: batch||null});
    toast('Job corrected'); slhLoadReview();
  }catch(e){ toast('Save failed: '+(e.message||e),'danger'); }
}
async function slhSaveMovement(id){
  const qEl = document.getElementById('rvm-qty-'+id), bEl = document.getElementById('rvm-batch-'+id);
  const qty = parseFloat(qEl.value), batch = bEl.value;
  try{
    await api(`/api/station/movement/${id}`,'PATCH',{qty_change: isNaN(qty)?null:qty, batch_ref: batch});
    toast('Movement corrected — stock reconciled'); slhLoadReview();
  }catch(e){ toast('Save failed: '+(e.message||e),'danger'); }
}

function slhPickScope(dept, line, btn){
  const ds = document.getElementById('sl-dept-scope');
  const ls = document.getElementById('sl-line');
  // The dropdowns only list the standard stations/lines. A scoped role can use
  // values that aren't there (e.g. the generic 'production' station), so add a
  // hidden option on the fly before selecting it.
  const ensure = (sel, val, label) => {
    if(!sel || !val) return;
    if(![...sel.options].some(o => o.value===val || o.textContent===val)){
      const o = document.createElement('option');
      o.value = val; o.textContent = label || val; o.hidden = true;
      sel.appendChild(o);
    }
  };
  ensure(ds, dept, SLH_DEPT_LABEL[dept] || dept);
  ensure(ls, line, line);
  if(ds) ds.value = dept;
  if(ls) ls.value = line;
  document.querySelectorAll('#sl-scope-buttons .sl-scope-btn')
    .forEach(b => b.classList.remove('active','btn-primary','text-white'));
  if(btn){ btn.classList.add('active','btn-primary','text-white'); }
  slhSetScope();
}

function slhSetScope(){
  const dept = document.getElementById('sl-dept-scope')?.value || 'laminating';
  let   line = document.getElementById('sl-line')?.value || 'P01';
  // Default the daily-report date picker to today.
  const _rd = document.getElementById('sl-report-date');
  if(_rd && !_rd.value) _rd.value = new Date().toISOString().slice(0,10);
  // PUV/PVS/PSP are now treated as independent lines using the standard Station
  // Leader Hub UX (their own distinct production flow is a later development).
  // They no longer drop into the old request-only aux mode.
  slhExitAuxMode();
  // Packing is a centralised station — all 3 lines feed into one hub.
  // Force the line filter to "ALL" so batches from P01, P02 and P37 mix here.
  const lineEl = document.getElementById('sl-line');
  if(dept === 'packing'){
    if(lineEl){ lineEl.value = ''; lineEl.disabled = true; }
    line = '';
  }else if(dept === 'fc'){
    // FC = Feed Center: its OWN node (a material-prep/QC/staging operation that
    // feeds the lines), not a per-line stage. Every line's batches centralise here
    // for veneer selection/grading, then FC releases them to the line's laminating.
    // Scope the FC view to the 'FC' line (not P01) and lock the selector.
    if(lineEl){ lineEl.value = 'FC'; lineEl.disabled = true; }
    line = 'FC';
  }else{
    if(lineEl){
      if(lineEl.disabled){ lineEl.disabled = false; if(!lineEl.value || lineEl.value==='FC') lineEl.value = 'P01'; }
      line = lineEl.value || 'P01';
    }
  }
  const f = document.getElementById('sl-dept-filter');
  if(f) f.value = dept;
  const chip = document.getElementById('sl-scope-chip');
  if(chip){
    const lbl = SLH_DEPT_SHORT[dept] || dept;
    chip.textContent = (dept === 'packing') ? `ALL LINES · ${lbl}`
                     : (dept === 'fc') ? `FC LINE · ${lbl}`
                     : `${line} · ${lbl}`;
  }
  const stDept = document.getElementById('st-dept');
  const stLine = document.getElementById('st-line');
  if(stDept) stDept.value = dept;
  if(stLine) stLine.value = line;
  _gmSelectedBatches = []; _gmActiveRecipe = null; _gmActiveBatch = null;
  // Merged Glue & Laminating station: show the Laminate / Mix-glue toggle and
  // default to Laminate; every other station hides it and stays in 'lam'.
  _slView = 'lam';
  const _glueTgl = document.getElementById('sl-glue-toggle');
  if(_glueTgl) _glueTgl.classList.toggle('d-none', dept !== 'laminating');
  document.getElementById('sl-view-lam')?.classList.add('active');
  document.getElementById('sl-view-mix')?.classList.remove('active');
  document.getElementById('sl-batch-filters')?.classList.remove('d-none');
  slhUpdateHeader();
  slhRefresh();
}

// Dynamic page header: "[P01] [Cold Press] HUB" — or "[ALL LINES] [Packing] HUB"
// for centralised stations.
function slhUpdateHeader(){
  const el = document.getElementById('slh-dynamic-header');
  if(!el) return;
  const dept = (document.getElementById('sl-dept-scope')?.value || 'laminating').trim();
  const lineSel = document.getElementById('sl-line');
  const line = (lineSel?.value || 'P01').trim();
  const deptLabel = SLH_DEPT_SHORT[dept] || dept;
  const linePart = (dept === 'packing') ? 'ALL LINES' : (dept === 'fc') ? 'FC LINE' : line;
  el.innerHTML =
    `<span class="badge bg-primary me-2" style="font-size:.85rem">${linePart}</span>`+
    `<span class="badge bg-secondary me-2" style="font-size:.85rem">${deptLabel}</span>`+
    `<span class="text-muted">HUB</span>`;
}

function slhRefresh(){
  if(_slhTab === 'dashboard') slhLoadDashboard();
  else if(_slhTab === 'batches') slLoadBatches();
  else if(_slhTab === 'team' && typeof stLoadAttendance==='function') stLoadAttendance();
  else if(_slhTab === 'stock'){
    // Merged Stock & Movements: load both
    if(typeof stLoadStock==='function')     stLoadStock();
    if(typeof stLoadMovements==='function') stLoadMovements();
  }
  else if(_slhTab === 'review') slhLoadReview();
  else if(_slhTab === 'reports' && typeof stLoadSummary==='function') stLoadSummary();
}

function slhSwitchTab(tab){
  // In aux-line mode, only Requests/Stock/Forklifts are allowed.
  if(_slhAuxLine){ _slhAuxSwitchPane(tab); return; }
  _slhTab = tab;
  document.querySelectorAll('#slh-tabs .nav-link').forEach(b => b.classList.toggle('active', b.dataset.slhTab === tab));
  document.querySelectorAll('.slh-pane').forEach(p => p.classList.add('d-none'));
  const target = document.getElementById('slh-pane-' + tab);
  if(target) target.classList.remove('d-none');

  // Lazy-load + move embedded Station Tools panes into the corresponding slh container.
  // The merged "Stock & Movements" tab pulls BOTH the stock and movements panes
  // into one container, separated by a heading.
  const embedMap = {
    team: 'st-pane-team', reports: 'st-pane-summary',
  };
  if(embedMap[tab]){
    _slhEmbedStationToolsPane(tab, embedMap[tab]);
  }else if(tab === 'stock'){
    _slhEmbedStockAndMovements();
  }
  if(tab === 'dashboard') slhLoadDashboard();
  else if(tab === 'batches') slLoadBatches();
  else if(tab === 'team') { _slhEnsureStLoaded(); stLoadAttendance?.(); }
  else if(tab === 'stock') { _slhEnsureStLoaded(); stLoadStock?.(); stLoadMovements?.(); }
  else if(tab === 'review') slhLoadReview();
  else if(tab === 'reports') { _slhEnsureStLoaded(); stLoadSummary?.(); }
  else if(tab === 'forklifts') { flkLoad(); oilLoad(); }
}

// Combine stock + movements panes into the merged "Stock & Movements" tab.
// Idempotent — safe to call on every tab switch; re-attaches panes if they've
// been moved away and ensures both are visible.
function _slhEmbedStockAndMovements(){
  const host = document.getElementById('slh-pane-stock');
  if(!host) return;
  const stockPane = document.getElementById('st-pane-stock');
  const movPane   = document.getElementById('st-pane-movements');
  // Build the header/divider scaffold if not already there
  if(!host.querySelector('[data-section="stock"]')){
    host.innerHTML = `
      <div class="mb-2" data-section="stock-h">
        <h6 class="mb-0 mt-1"><i class="bi bi-box-seam me-1 text-primary"></i>Station Stock</h6>
        <small class="text-muted">Current consumables held at this station — request from WH before goods arrive, then receive on delivery.</small>
        <div class="mt-2 d-flex gap-2 flex-wrap" data-section="stock-actions">
          <button class="btn btn-sm btn-primary" onclick="stOpenWHRequest()">
            <i class="bi bi-cart-plus me-1"></i>Request from Warehouse
          </button>
          <button class="btn btn-sm btn-outline-secondary" onclick="stOpenMyRequests()">
            <i class="bi bi-clock-history me-1"></i>View my open requests
          </button>
        </div>
      </div>
      <div data-section="stock"></div>
      <hr class="my-3">
      <div class="mb-2" data-section="mov-h">
        <h6 class="mb-0 mt-1"><i class="bi bi-arrow-left-right me-1 text-info"></i>Recent Stock Movements</h6>
        <small class="text-muted">Receipts from WH, issues to batches, transfers — all in one feed.</small>
      </div>
      <div data-section="movements"></div>`;
  }
  const stockSlot = host.querySelector('[data-section="stock"]');
  const movSlot   = host.querySelector('[data-section="movements"]');
  if(stockPane && stockSlot && stockPane.parentElement !== stockSlot){
    stockSlot.appendChild(stockPane);
  }
  if(movPane && movSlot && movPane.parentElement !== movSlot){
    movSlot.appendChild(movPane);
  }
  if(stockPane){ stockPane.classList.remove('d-none'); stockPane.style.display=''; }
  if(movPane){   movPane.classList.remove('d-none');   movPane.style.display=''; }
}

// Open the WH-consumable request modal pre-targeted to the current station.
function stOpenWHRequest(){
  const dept = document.getElementById('sl-dept-scope')?.value
            || document.getElementById('sl-dept-filter')?.value
            || document.getElementById('st-dept')?.value
            || 'laminating';
  try{ openWHRequest(dept); }
  catch(e){ alert('Request modal unavailable: '+e.message); }
}

async function _slhEnsureStLoaded(){
  // Make sure st* state (dept, employees, defaults) is initialized.
  if(typeof stLoad === 'function' && !window._stInitialized){
    // Sync scope first
    const dept = document.getElementById('sl-dept-scope')?.value || '';
    const stDept = document.getElementById('st-dept');
    if(stDept && dept) stDept.value = dept;
    await stLoad();
    window._stInitialized = true;
  }
}

function _slhEmbedStationToolsPane(slhTab, stPaneId){
  const target = document.getElementById('slh-pane-' + slhTab);
  const pane = document.getElementById(stPaneId);
  if(!target || !pane) return;
  if(pane.parentElement !== target){
    target.appendChild(pane);
  }
  // Ensure visible inside slh container
  pane.classList.remove('d-none');
}

// ── DASHBOARD: lean production overview ──────────────────────
async function slhLoadDashboard(){
  const dept = document.getElementById('sl-dept-scope')?.value || '';
  const line = document.getElementById('sl-line')?.value || '';
  const today = new Date().toISOString().slice(0, 10);

  // Fetch all dashboard data in parallel
  const [batches, attendance, stock, machines] = await Promise.all([
    api(`/api/batches${dept ? '?department=' + dept : ''}`).catch(() => []),
    dept ? api(`/api/hr/attendance?department=${dept}&work_date=${today}`).catch(() => []) : Promise.resolve([]),
    dept ? api(`/api/station-stock?department=${dept}${line ? '&line_id=' + line : ''}`).catch(() => []) : Promise.resolve([]),
    Promise.resolve(_msMachines || []),
  ]);

  const filteredBatches = (batches || []).filter(b => !line || b.production_line === line);
  const totalPcs = filteredBatches.reduce((s, b) => s + (b.total_pcs || 0), 0);
  const activeMachines = (machines || []).filter(m => (!dept || (m.dept || m.type || '').toLowerCase() === dept) && m.status === 'active').length;
  const totalMachines = (machines || []).filter(m => !dept || (m.dept || m.type || '').toLowerCase() === dept).length;
  const lowStock = (stock || []).filter(s => (s.min_qty || 0) > 0 && (s.current_qty || 0) <= (s.min_qty || 0));
  const presentOps = (attendance || []).filter(a => a.status === 'PRESENT' || a.status === 'LATE');

  // KPIs
  document.getElementById('slh-kpi-batches').textContent = fmt(filteredBatches.length);
  document.getElementById('slh-kpi-pcs-wip').textContent = fmt(totalPcs);
  document.getElementById('slh-kpi-pcs-today').textContent = '—'; // wired below if production_logs available
  document.getElementById('slh-kpi-operators').textContent = fmt(presentOps.length);
  document.getElementById('slh-kpi-machines').textContent = `${activeMachines}/${totalMachines}`;
  document.getElementById('slh-kpi-issues').textContent = fmt(lowStock.length);

  // Update batch tab count badge
  const bc = document.getElementById('slh-batch-count');
  if(bc) bc.textContent = filteredBatches.length;

  // Priorities list — top batches sorted by priority
  const priorityList = document.getElementById('slh-priority-list');
  const sorted = [...filteredBatches].sort((a, b) => (a.priority || 2) - (b.priority || 2)).slice(0, 8);
  if(!sorted.length){
    priorityList.innerHTML = '<p class="text-muted small text-center py-3">No batches at this station.</p>';
  } else {
    priorityList.innerHTML = sorted.map(b => `
      <div class="d-flex justify-content-between align-items-center border-bottom py-2"
           style="cursor:pointer;border-left:3px solid ${b.priority==1?'#ef4444':b.priority==3?'#16a34a':'#eab308'};padding-left:8px"
           onclick="slhSwitchTab('batches');setTimeout(()=>slSelectBatch(${b.id}),100)">
        <div>
          <div class="small fw-semibold text-primary">${b.batch_number}</div>
          <div class="small text-muted text-truncate" style="max-width:240px">${b.product_name||b.sku||''} · ${fmt(b.total_pcs)} pcs</div>
        </div>
        <div class="text-end">
          ${prioBadge(b.priority||2)}
          <div class="small text-muted mt-1">${DEPT_LABEL[b.current_department]||b.current_department}</div>
        </div>
      </div>`).join('');
  }
  document.getElementById('slh-priority-meta').textContent = `${sorted.length} of ${filteredBatches.length} shown`;

  // Team list
  const teamList = document.getElementById('slh-team-list');
  if(!dept){
    teamList.innerHTML = '<p class="text-muted small text-center py-3">Pick a department to view today\'s team.</p>';
  } else if(!attendance.length){
    teamList.innerHTML = `<p class="text-muted small text-center py-3">No team logged today. <a href="#" onclick="event.preventDefault();slhSwitchTab('team')">Log attendance →</a></p>`;
  } else {
    const totalRegHr = attendance.reduce((s,a)=>s+(a.regular_hours||0),0);
    const totalOtHr = attendance.reduce((s,a)=>s+(a.ot_hours||0),0);
    teamList.innerHTML = `
      <div class="d-flex justify-content-around small text-center mb-2 pt-1">
        <div><b class="text-primary fs-5">${attendance.length}</b><div class="text-muted">checked in</div></div>
        <div><b class="text-success fs-5">${totalRegHr.toFixed(1)}</b><div class="text-muted">regular hrs</div></div>
        <div><b class="text-warning fs-5">${totalOtHr.toFixed(1)}</b><div class="text-muted">OT hrs</div></div>
      </div>
      <div class="small text-muted px-2" style="max-height:140px;overflow-y:auto">
        ${attendance.slice(0,10).map(a=>`<div class="border-bottom py-1"><b>${a.emp_name||a.emp_id}</b> <span class="text-muted">· ${a.shift}</span> ${a.time_in?`<span class="text-muted">${a.time_in}-${a.time_out||'now'}</span>`:''}</div>`).join('')}
      </div>`;
  }

  // Stock alerts
  const stockList = document.getElementById('slh-stock-alerts');
  if(!dept){
    stockList.innerHTML = '<p class="text-muted small text-center py-3">Pick a department to see stock alerts.</p>';
  } else if(!lowStock.length){
    stockList.innerHTML = '<p class="text-success small text-center py-3"><i class="bi bi-check-circle me-1"></i>No items below min. All stock healthy.</p>';
  } else {
    stockList.innerHTML = lowStock.slice(0,8).map(s=>`
      <div class="d-flex justify-content-between border-bottom py-2 px-1" style="border-left:3px solid #ef4444;padding-left:8px">
        <div>
          <div class="small fw-semibold">${s.material_name}</div>
          <small class="text-muted">${s.material_code||''}</small>
        </div>
        <div class="text-end small">
          <div class="text-danger fw-bold">${fmt(s.current_qty)} ${s.unit||''}</div>
          <small class="text-muted">min: ${fmt(s.min_qty)}</small>
        </div>
      </div>`).join('');
  }

  // Machine status
  const machList = document.getElementById('slh-machine-status');
  const deptMachines = (machines || []).filter(m => !dept || (m.dept||m.type||'').toLowerCase() === dept);
  if(!deptMachines.length){
    machList.innerHTML = '<p class="text-muted small text-center py-3">No machines configured. Use Machine Setup to add.</p>';
  } else {
    const STATUS = {active:{c:'success',i:'🟢'}, maintenance:{c:'warning',i:'🟡'}, offline:{c:'danger',i:'🔴'}};
    machList.innerHTML = deptMachines.slice(0,8).map(m=>{
      const s = STATUS[m.status] || {c:'secondary',i:'⚪'};
      const cap = m.capacity_per_hour > 0 ? `${m.capacity_per_hour} pcs/hr` :
                  (m.capacity_per_shift > 0 ? `${m.capacity_per_shift} pcs/shift` : '—');
      return `<div class="d-flex justify-content-between border-bottom py-2 px-1">
        <div>
          <div class="small fw-semibold">${s.i} ${m.name}</div>
          <small class="text-muted">${m.production_line||'all lines'}${m.notes?' · '+m.notes:''}</small>
        </div>
        <div class="text-end small">
          <span class="badge bg-${s.c}">${m.status}</span>
          <div class="small text-muted mt-1">${cap}</div>
        </div>
      </div>`;
    }).join('');
  }
}

// ── Machine Setup (Station Log integration) ────────────────────
let _msMachines = [];

async function msLoadMachines(){
  _msMachines = await api('/api/machines').catch(()=>[]);
}

async function msOpenSetup(){
  await msLoadMachines();
  msRenderTable();
  bootstrap.Modal.getOrCreateInstance(document.getElementById('machineSetupModal')).show();
}

function msRenderTable(){
  const dept = document.getElementById('ms-dept-filter')?.value || '';
  const line = document.getElementById('ms-line-filter')?.value || '';
  const q = (document.getElementById('ms-search')?.value || '').toLowerCase().trim();
  const tbody = document.getElementById('ms-tbody');
  const rows = _msMachines.filter(m => {
    const mDept = (m.dept || m.type || '').toLowerCase();
    if(dept && mDept !== dept) return false;
    if(line && (m.production_line || '') !== line) return false;
    if(q && !((m.name||'').toLowerCase().includes(q))) return false;
    return true;
  }).sort((a,b)=>{
    const da = (a.dept||a.type||''), db = (b.dept||b.type||'');
    if(da !== db) return da.localeCompare(db);
    return (a.name||'').localeCompare(b.name||'');
  });
  if(!rows.length){
    tbody.innerHTML = '<tr><td colspan="9" class="text-muted text-center py-4">No machines match the current filters.</td></tr>';
    return;
  }
  const STATUS_COLOR = {active:'success', maintenance:'warning text-dark', offline:'danger'};
  tbody.innerHTML = rows.map(m => {
    const mDept = m.dept || m.type || '';
    const deptLabel = (DEPT_LABEL && DEPT_LABEL[mDept]) || mDept || '—';
    const maint = [m.last_maintenance, m.next_maintenance].filter(Boolean).join(' → ');
    return `<tr>
      <td><b>${m.name||'—'}</b></td>
      <td class="small">${deptLabel}</td>
      <td class="small">${m.production_line||'—'}</td>
      <td class="text-end fw-semibold">${m.capacity_per_hour||0}</td>
      <td class="text-end">${m.capacity_per_shift||0}</td>
      <td><span class="badge bg-${STATUS_COLOR[m.status]||'secondary'}">${m.status||'—'}</span></td>
      <td class="small text-muted">${maint||'—'}</td>
      <td class="small text-muted text-truncate" style="max-width:260px" title="${(m.notes||'').replace(/"/g,'&quot;')}">${m.notes||''}</td>
      <td class="text-end">
        <button class="btn btn-xs btn-outline-secondary py-0 px-1" onclick="msOpenEdit(${m.id})"><i class="bi bi-pencil"></i></button>
        <button class="btn btn-xs btn-outline-danger py-0 px-1" onclick="msDelete(${m.id})"><i class="bi bi-trash"></i></button>
      </td>
    </tr>`;
  }).join('');
}

function msOpenEdit(id){
  const m = id ? _msMachines.find(x => x.id === id) : null;
  document.getElementById('ms-edit-id').value = m?.id || '';
  document.getElementById('ms-edit-name').value = m?.name || '';
  document.getElementById('ms-edit-status').value = m?.status || 'active';
  document.getElementById('ms-edit-dept').value = m?.dept || m?.type || '';
  document.getElementById('ms-edit-line').value = m?.production_line || '';
  document.getElementById('ms-edit-cap-hr').value = m?.capacity_per_hour || '';
  document.getElementById('ms-edit-cap-shift').value = m?.capacity_per_shift || '';
  document.getElementById('ms-edit-last').value = (m?.last_maintenance || '').slice(0,10);
  document.getElementById('ms-edit-next').value = (m?.next_maintenance || '').slice(0,10);
  document.getElementById('ms-edit-notes').value = m?.notes || '';
  document.getElementById('ms-edit-title').textContent = id ? `Edit Machine — ${m?.name||''}` : 'Add Machine';
  bootstrap.Modal.getOrCreateInstance(document.getElementById('machineEditModal')).show();
}

async function msSave(){
  const id = parseInt(document.getElementById('ms-edit-id').value) || 0;
  const body = {
    name: document.getElementById('ms-edit-name').value.trim(),
    dept: document.getElementById('ms-edit-dept').value,
    type: document.getElementById('ms-edit-dept').value,  // keep `type` in sync for backward compat
    production_line: document.getElementById('ms-edit-line').value,
    capacity_per_hour: parseFloat(document.getElementById('ms-edit-cap-hr').value) || 0,
    capacity_per_shift: parseFloat(document.getElementById('ms-edit-cap-shift').value) || 0,
    status: document.getElementById('ms-edit-status').value,
    last_maintenance: document.getElementById('ms-edit-last').value || '',
    next_maintenance: document.getElementById('ms-edit-next').value || '',
    notes: document.getElementById('ms-edit-notes').value || '',
  };
  if(!body.name){ toast('Machine name is required','warning'); return; }
  try {
    if(id) await api(`/api/machines/${id}`, 'PUT', body);
    else   await api('/api/machines', 'POST', body);
    bootstrap.Modal.getInstance(document.getElementById('machineEditModal')).hide();
    toast(id ? 'Machine updated' : 'Machine added','success');
    await msLoadMachines();
    msRenderTable();
  } catch(e){ toast(e.message,'danger'); }
}

async function msDelete(id){
  const m = _msMachines.find(x => x.id === id);
  if(!confirm(`Delete machine "${m?.name||'#'+id}"? This cannot be undone.`)) return;
  try {
    await api(`/api/machines/${id}`,'DELETE');
    toast('Machine deleted','success');
    await msLoadMachines();
    msRenderTable();
  } catch(e){ toast(e.message,'danger'); }
}

// Build machine <option> list for a station form's dropdown, filtered by
// dept + (optionally) line. When no machine matches we now surface a clear
// "not configured" message rather than serving hardcoded fallback codes
// (SND-01/CP-01/HP-01 etc.) that don't exist in the DB — those silently
// created phantom machine records on save.
function msOptionsFor(dept, line){
  let matching = (_msMachines || []).filter(m =>
    (m.dept || m.type || '').toLowerCase() === dept
    && (!line || !m.production_line || m.production_line === line)
  );
  if(!matching.length){
    const lineHint = line ? ' on '+line : '';
    return `<option value="" disabled>No ${dept} machine configured${lineHint} — add one in Admin → Machines</option>`;
  }
  return '<option value="">Select…</option>' + matching.map(m=>{
    const cap = m.capacity_per_hour > 0 ? `${m.capacity_per_hour}/hr`
              : (m.capacity_per_shift > 0 ? `${m.capacity_per_shift}/shift` : '');
    const statusTag = m.status === 'maintenance' ? ' ⚠' : m.status === 'offline' ? ' ✗' : '';
    return `<option value="${m.name}">${m.name}${statusTag}${cap?' — '+cap+' pcs':''}</option>`;
  }).join('');
}

// Build a small capacity-guideline hint HTML for the machine dropdown in station forms.
// Usage: pass dept name (e.g. 'cold_press') → returns hint string or empty.
function msCapacityHint(dept){
  if(!_msMachines || !_msMachines.length) return '';
  const matching = _msMachines.filter(m => (m.dept || m.type || '').toLowerCase() === dept);
  if(!matching.length) return '';
  const items = matching.map(m => {
    const cap = m.capacity_per_hour > 0
      ? `${m.capacity_per_hour}/hr`
      : (m.capacity_per_shift > 0 ? `${m.capacity_per_shift}/shift` : '?');
    const statusIcon = m.status === 'active' ? '🟢' : m.status === 'maintenance' ? '🟡' : '🔴';
    const note = m.notes ? ` · ${m.notes}` : '';
    return `<div class="small"><b>${statusIcon} ${m.name}</b> — ${cap} pcs${m.production_line?' · '+m.production_line:''}${note}</div>`;
  }).join('');
  return `<div class="mt-1 p-2 rounded bg-light" style="font-size:.72rem">
    <div class="text-muted fw-semibold mb-1"><i class="bi bi-info-circle me-1"></i>Machine guidelines:</div>
    ${items}
  </div>`;
}
async function slLoadBatches(){
  const dept=document.getElementById('sl-dept-filter').value;
  // Packing and FC are centralised — show batches from every line. Packing is
  // the shared end station; FC is the shared cutting station every line's
  // batches pass through first. All other stations are line-scoped.
  const isCentralised = (dept === 'packing' || dept === 'fc');
  const line = isCentralised ? '' : (document.getElementById('sl-line').value || '');
  // Glue Mixing is virtual — there are no batches with current_department='glue_mix'.
  // Mixers prepare glue *for* batches currently in laminating, so we pull those.
  const queryDept = (dept === 'glue_mix') ? 'laminating' : dept;
  const params=[];
  if(queryDept) params.push('department='+queryDept);
  let batches=await api(`/api/batches${params.length?'?'+params.join('&'):''}`).catch(()=>[]);
  if(line) batches=batches.filter(b=>b.production_line===line);
  _slBatches=batches.filter(b=>b.status!=='completed');
  // Pre-fetch each batch's glue code so the Glue Mixing queue can colour-code
  // them, let the leader tick multiple sharing the same recipe, AND power the
  // glue-recipe filter. Fetch for the stations where glue matters.
  _slBatchGlue = {};
  if(dept === 'glue_mix' || dept === 'laminating'){
    _gmBatchGlueInfo = {};
    await Promise.all(_slBatches.map(async b => {
      try{ const gi = await api(`/api/batches/${b.id}/glue-info`); _gmBatchGlueInfo[b.id]=gi; _slBatchGlue[b.id]=(gi&&gi.glue_code)||''; }catch{}
    }));
    if(!_gmRecipes.length){
      try{ _gmRecipes = await api('/api/glue-recipes?kind=glue') || []; }catch{}
    }
  }
  if(dept === 'glue_mix' || dept === 'laminating') _gmBatches = _slBatches;
  _slPopulateBatchFilterOptions();
  renderSlBatchList();
}
function slFilterBatches(){ slLoadBatches(); }

// ── Station-Hub batch list filters (customer / priority / glue recipe / search) ──
let _slBatchGlue = {};   // batch_id -> glue_code (for the recipe filter)
function _slBatchFilterState(){
  return {
    q:      (document.getElementById('sl-bf-search')?.value || '').toLowerCase().trim(),
    cust:    document.getElementById('sl-bf-cust')?.value   || '',
    prio:    document.getElementById('sl-bf-prio')?.value   || '',
    recipe:  document.getElementById('sl-bf-recipe')?.value || '',
  };
}
function _slPopulateBatchFilterOptions(){
  const custSel = document.getElementById('sl-bf-cust');
  if(custSel){
    const cur = custSel.value;
    const custs = [...new Set(_slBatches.map(b=>b.customer).filter(Boolean))].sort();
    custSel.innerHTML = '<option value="">All customers</option>' +
      custs.map(c=>`<option${c===cur?' selected':''}>${c}</option>`).join('');
  }
  const recSel = document.getElementById('sl-bf-recipe');
  if(recSel){
    const recs = [...new Set(Object.values(_slBatchGlue).filter(Boolean))].sort();
    recSel.classList.toggle('d-none', recs.length===0);
    const cur = recSel.value;
    recSel.innerHTML = '<option value="">All glue codes</option>' +
      recs.map(r=>`<option${r===cur?' selected':''}>${r}</option>`).join('');
  }
}
function _slApplyBatchFilters(list){
  const f = _slBatchFilterState();
  return list.filter(b=>{
    if(f.cust && b.customer!==f.cust) return false;
    if(f.prio && String(b.priority||2)!==f.prio) return false;
    if(f.recipe && (_slBatchGlue[b.id]||'')!==f.recipe) return false;
    if(f.q){
      const hay=[b.batch_number,b.sku,b.product_name,b.prod_order_number,b.customer].filter(Boolean).join(' ').toLowerCase();
      if(!hay.includes(f.q)) return false;
    }
    return true;
  });
}
function slApplyFilters(){ renderSlBatchList(); }

// Merged Glue & Laminating station: 'lam' = laminate a single batch (+ move),
// 'mix' = the multi-batch glue mixing view. The toggle only shows for that
// station (set in slhSetScope); other stations stay in 'lam'.
let _slView = 'lam';
function slSetView(v){
  _slView = (v === 'mix') ? 'mix' : 'lam';
  document.getElementById('sl-view-lam')?.classList.toggle('active', _slView==='lam');
  document.getElementById('sl-view-mix')?.classList.toggle('active', _slView==='mix');
  // The plain filter bar picks one batch to laminate; the mix view groups by
  // recipe itself, so hide the filters there.
  document.getElementById('sl-batch-filters')?.classList.toggle('d-none', _slView==='mix');
  renderSlBatchList();
  if(_slView === 'mix'){
    if(typeof slRenderGlueMixCard === 'function') slRenderGlueMixCard();
  } else if(_slActiveBatch){
    renderStationForms(_slActiveBatch);
  } else {
    const area=document.getElementById('sl-station-area');
    if(area) area.innerHTML='<div class="card p-5 text-center text-muted"><i class="bi bi-arrow-left fs-3 mb-2"></i><div>Select a batch to log station activity</div></div>';
  }
}
function renderSlBatchList(){
  const el=document.getElementById('sl-batch-list');
  const scopeDept=document.getElementById('sl-dept-filter').value;
  // Glue & Laminating in "Mix glue" mode: render checkboxes grouped by recipe.
  if(scopeDept==='laminating' && _slView==='mix') return _renderSlBatchList_glueMix();
  const list=_slApplyBatchFilters(_slBatches);
  if(!list.length){el.innerHTML='<p class="text-muted small text-center pt-3">No batches match the filters.</p>';return;}
  const sorted=[...list].sort((a,b)=>(a.priority||2)-(b.priority||2)||(a.created_at||'').localeCompare(b.created_at||''));
  el.innerHTML=sorted.map(b=>`
    <div class="border rounded p-2 mb-2 ${_slActiveBatch?.id===b.id?'border-primary bg-light':''}"
         style="cursor:pointer;border-left:4px solid ${b.priority==1?'#ef4444':b.priority==3?'#16a34a':'#eab308'}!important"
         onclick="slSelectBatch(${b.id})"
         oncontextmenu="event.preventDefault();deptBatchDetail(${b.id},'${b.current_department}');return false;"
         title="Click to select · Right-click for full details">
      <div class="d-flex justify-content-between align-items-center">
        <code class="text-primary small">${b.batch_number}</code>
        <div class="d-flex gap-1 align-items-center">
          ${prioBadge(b.priority||2)}
          ${slDeptBadge(b.current_department)}
          <button class="btn btn-xs py-0 px-1 btn-outline-secondary" style="font-size:.65rem" title="View full detail" onclick="event.stopPropagation();deptBatchDetail(${b.id},'${b.current_department}')"><i class="bi bi-box-arrow-up-right"></i></button>
        </div>
      </div>
      <div class="small text-muted mt-1 text-truncate">${b.product_name||b.sku||''} · ${b.production_line||''} · ${fmt(b.quantity)} pallet${b.quantity!=1?'s':''} (${fmt(b.total_pcs ?? b.pcs_actual ?? ((b.quantity||0)*(b.pallet_qty||1)))} pcs)</div>
      <div class="small text-muted mt-1">${(b.created_at||'').slice(0,10)} ${b.prod_order_number?'<span class="badge bg-light text-dark border">PO:'+b.prod_order_number+'</span>':''}</div>
    </div>`).join('');
}
// Render the batch list as multi-select checkboxes when scope=glue_mix
function _renderSlBatchList_glueMix(){
  const el = document.getElementById('sl-batch-list');
  const activeCode = _gmActiveRecipe?.recipe_code || '';
  el.innerHTML = `<div class="small text-muted px-2 pb-2">
      Tick all batches sharing the same recipe to mix glue once for the group.
    </div>` + _gmBatches.map(b => {
      const info = _gmBatchGlueInfo[b.id] || {};
      const code = info.glue_code || '—';
      const isSel = _gmSelectedBatches.some(x => x.id === b.id);
      const disable = activeCode && code !== activeCode && !isSel;
      return `<div class="border rounded p-2 mb-2 ${isSel?'border-warning bg-light':''} ${disable?'opacity-50':''}"
                   style="${disable?'background:#f3f4f6':''}">
        <label class="d-flex align-items-start gap-2 mb-0" style="cursor:${disable?'not-allowed':'pointer'}">
          <input type="checkbox" class="form-check-input mt-1" ${isSel?'checked':''} ${disable?'disabled':''}
                 onchange="slGlueMixToggle(${b.id}, this.checked)">
          <div style="flex:1;min-width:0">
            <code class="text-primary small">${b.batch_number}</code>
            <div class="small text-muted text-truncate">${b.product_name||b.sku||''}</div>
            <div class="small text-muted">${b.production_line||''} · ${fmt(b.quantity)} pallet${b.quantity!=1?'s':''} (${fmt(b.total_pcs ?? b.pcs_actual ?? ((b.quantity||0)*(b.pallet_qty||1)))} pcs)</div>
            <div class="small">
              <span class="badge bg-${code==='—'?'secondary':'warning text-dark'}" style="font-size:.6rem">${code}</span>
              ${info.total_kg?`<span class="text-muted ms-1">· ${fmt(info.total_kg)} kg</span>`:''}
            </div>
          </div>
        </label>
      </div>`;
    }).join('');
}

// Tick / untick a batch into the Glue Mixing selection (Hub version)
async function slGlueMixToggle(id, checked){
  const b = _slBatches.find(x => x.id === id) || _gmBatches.find(x => x.id === id);
  if(!b) return;
  const info = _gmBatchGlueInfo[id] || {};
  if(checked){
    if(!_gmActiveRecipe){
      const recipe = info.recipe || _gmRecipes.find(r => r.recipe_code === info.glue_code);
      if(!recipe){ alert(`Batch ${b.batch_number} has no matching glue recipe yet.`); return; }
      _gmActiveRecipe = recipe;
    }else if(info.glue_code && info.glue_code !== _gmActiveRecipe.recipe_code){
      alert(`Batch ${b.batch_number} uses ${info.glue_code} but the current mix is for ${_gmActiveRecipe.recipe_code}. Uncheck the others first.`);
      return;
    }
    _gmSelectedBatches.push(b);
    _gmActiveBatch = _gmSelectedBatches[0];
  }else{
    _gmSelectedBatches = _gmSelectedBatches.filter(x => x.id !== id);
    if(!_gmSelectedBatches.length){ _gmActiveRecipe = null; _gmActiveBatch = null; }
    else _gmActiveBatch = _gmSelectedBatches[0];
  }
  _renderSlBatchList_glueMix();
  await slRenderGlueMixCard();
}

// Render the Glue Mixing form into the Hub's right pane (in place of the
// per-batch station card). Reuses the existing gm* state and helpers.
async function slRenderGlueMixCard(){
  const area = document.getElementById('sl-station-area');
  if(!area) return;
  const totalKg  = _gmSelectedBatches.reduce((s,b)=>s+Number(_gmBatchGlueInfo[b.id]?.total_kg||0),0);
  const totalPcs = _gmSelectedBatches.reduce((s,b)=>s+Number(b.quantity||0),0);
  area.innerHTML = `
    <div class="card border-warning border-2 mb-3"><div class="card-body py-2 px-3">
      <h5 class="mb-0"><i class="bi bi-droplet-fill me-2 text-warning"></i>Glue Mixing
        <span class="badge bg-${_gmActiveRecipe?'warning text-dark':'secondary'} ms-2">${_gmActiveRecipe?.recipe_code || '— pick a batch —'}</span>
      </h5>
      <div class="small text-muted mt-1" id="slgm-summary">
        ${_gmSelectedBatches.length ?
          _gmSelectedBatches.map(b=>`<span class="badge bg-warning text-dark me-1">${b.batch_number}</span>`).join('') +
          ` · ${_gmSelectedBatches.length} batch(es) · ${fmt(totalPcs)} pallets · suggested ${fmt(totalKg)} kg`
          : 'Tick batches in the queue to start a mix.'}
      </div>
    </div></div>

    <!-- Station shortfall — required component kg across all batches in
         pipeline vs current glue_mix station stock. -->
    <div class="card mb-3" id="slgm-shortfall-card">
      <div class="card-header py-2 d-flex align-items-center flex-wrap gap-2">
        <i class="bi bi-exclamation-triangle me-1 text-danger"></i>
        <span class="fw-bold small">Component Shortfall — Glue Mix Station</span>
        <small class="text-muted">${_gmSelectedBatches.length?'for selected batches':'across all laminating batches'} vs station stock</small>
        <div class="ms-auto d-flex gap-2 align-items-center">
          <button class="btn btn-sm btn-primary" id="slgm-bulk-req-btn"
                  onclick="slgmBulkRequestWH()" disabled
                  title="Send one consumable request per SHORT and LOW component to the warehouse">
            <i class="bi bi-cart-plus me-1"></i>Request All Short + Low from WH (<span id="slgm-bulk-req-count">0</span>)
          </button>
          <button class="btn btn-sm btn-outline-secondary py-0 px-2"
                  onclick="slgmReloadShortfall()" title="Refresh"><i class="bi bi-arrow-clockwise"></i></button>
        </div>
      </div>
      <div id="slgm-shortfall-body" class="p-2 small text-muted">Loading…</div>
    </div>

    ${_gmSelectedBatches.length ? `
    <div class="card">
      <div class="card-header py-2 d-flex align-items-center">
        <i class="bi bi-droplet me-1 text-warning"></i>
        <span class="fw-bold small">Confirm Glue Mix</span>
        <button class="btn btn-link btn-sm py-0 ms-auto" onclick="gmOpenRecipe(_gmActiveRecipe?.id)" title="View / edit this recipe"><i class="bi bi-journal-code"></i> Recipe</button>
      </div>
      <div class="card-body p-3">
        <div class="row g-3">
          <div class="col-md-4"><label class="form-label small fw-semibold">Glue Code</label>
            <input class="form-control form-control-sm bg-light" id="gm-bom-code" readonly value="${_gmActiveRecipe?.recipe_code||''}">
            <input type="hidden" id="gm-recipe-sel" value="${_gmActiveRecipe?.id||''}">
          </div>
          <div class="col-md-3"><label class="form-label small fw-semibold">Total Mix (kg) *</label>
            <input type="number" class="form-control form-control-sm" id="gm-total-kg" min="0.1" step="0.1" value="${totalKg.toFixed(2)}" oninput="gmCalcComponents()">
            <small class="text-muted" id="gm-bom-suggested">Suggested: <b>${fmt(totalKg)} kg</b></small>
          </div>
          <div class="col-md-2"><label class="form-label small fw-semibold">Mix Time (min)</label>
            <input type="number" class="form-control form-control-sm" id="gm-mix-min" min="1" value="${_gmActiveRecipe?.mix_time_min||20}">
          </div>
          <div class="col-md-3"><label class="form-label small fw-semibold">Operator</label>
            <input class="form-control form-control-sm" id="gm-operator" list="sl-emp-list" placeholder="Name or ID">
          </div>
        </div>
        <div class="mt-3 p-2 bg-light rounded" id="gm-components-wrap">
          <div class="d-flex justify-content-between align-items-center mb-2">
            <div class="small fw-semibold text-muted"><i class="bi bi-sliders me-1"></i>Components — defaults from recipe, override if needed</div>
            <button class="btn btn-link btn-sm py-0" onclick="gmCalcComponents()" title="Recalculate"><i class="bi bi-arrow-clockwise"></i></button>
          </div>
          <table class="table table-sm mb-0">
            <thead class="table-light"><tr>
              <th>Component</th><th>Material</th>
              <th class="text-end" style="width:120px">Qty (kg)</th>
              <th class="text-end small text-muted" style="width:130px">Station Stock</th>
              <th class="text-end small text-muted" style="width:90px">After</th>
            </tr></thead>
            <tbody id="gm-comp-tbody"></tbody>
            <tfoot class="table-light fw-semibold small"><tr>
              <td colspan="2" class="text-end">Total:</td>
              <td class="text-end" id="gm-comp-total">—</td><td colspan="2"></td>
            </tr></tfoot>
          </table>
        </div>
        <div class="mt-3"><label class="form-label small fw-semibold">Notes</label>
          <input class="form-control form-control-sm" id="gm-notes" placeholder="Adjustments / observations"></div>
        <div class="mt-3 d-flex gap-2">
          <button class="btn btn-warning btn-sm" onclick="gmSubmitMix()">
            <i class="bi bi-check-circle me-1"></i>Confirm Mix &amp; Deduct Stock
          </button>
          <button class="btn btn-outline-secondary btn-sm" onclick="slGlueMixClear()">Clear Selection</button>
        </div>
        <div class="mt-2 small text-muted" id="gm-submit-status"></div>
      </div>
    </div>` : `<div class="alert alert-info">Tick at least one batch in the left queue. Only batches sharing the same glue recipe can be mixed together.</div>`}
  `;
  if(_gmSelectedBatches.length){
    await gmRefreshStation();
    gmCalcComponents();
  }
  // Lazily populate the shortfall card after the form is in the DOM
  slgmReloadShortfall();
}

let _slgmShortfallRows = [];
async function slgmReloadShortfall(){
  const box = document.getElementById('slgm-shortfall-body');
  if(!box) return;
  box.innerHTML = '<div class="text-muted small p-2"><span class="spinner-border spinner-border-sm me-2"></span>Computing requirements…</div>';
  try{
    const d = await api('/api/glue-mix/material-requirements');
    const rows = (d && d.rows) || [];
    _slgmShortfallRows = rows;
    // Wire the bulk button state
    const requestable = rows.filter(r => (r.status==='SHORT' || r.status==='LOW') && r.material_id && (r.shortfall_kg||r.required_kg) > 0);
    const btn = document.getElementById('slgm-bulk-req-btn');
    const cnt = document.getElementById('slgm-bulk-req-count');
    if(btn){ btn.disabled = requestable.length === 0; }
    if(cnt){ cnt.textContent = requestable.length; }
    if(!rows.length){
      box.innerHTML = '<div class="text-muted small p-2"><i class="bi bi-check2-circle me-1 text-success"></i>No glue-mix component requirements from the current pipeline.</div>';
      return;
    }
    const summary = d.summary || {};
    box.innerHTML = `
      <div class="row g-2 mb-2 px-2 pt-2 small">
        <div class="col-auto"><span class="badge bg-primary">${summary.batches_seen||0} batches</span></div>
        <div class="col-auto"><span class="badge bg-danger">${summary.components_short||0} SHORT</span></div>
        <div class="col-auto"><span class="badge bg-warning text-dark">${summary.components_low||0} LOW</span></div>
        <div class="col-auto"><span class="badge bg-success">${summary.components_ok||0} OK</span></div>
      </div>
      <div class="table-responsive">
        <table class="table table-sm table-hover mb-0">
          <thead class="table-light"><tr>
            <th>Component</th>
            <th class="text-end">Required</th>
            <th class="text-end">On Hand</th>
            <th class="text-end">Shortfall</th>
            <th class="text-end">WH Stock</th>
            <th>Status</th>
            <th class="text-end">Action</th>
          </tr></thead>
          <tbody>${rows.map(r => {
            const stat = {SHORT:['danger','SHORT'],LOW:['warning text-dark','LOW'],OK:['success','OK']}[r.status]||['secondary',r.status];
            const matLabel = r.material_name
              ? `<b>${r.component}</b><br><span class="text-muted small">${r.material_name}</span>`
                + (r.no_station_stock_yet
                    ? `<br><span class="badge bg-warning text-dark" style="font-size:.6rem" title="No station-stock record yet — first request will create one"><i class="bi bi-info-circle me-1"></i>not yet received at station</span>`
                    : '')
              : `<b>${r.component}</b><br><span class="text-danger small">no matching material in catalog — ask admin to add it</span>`;
            const action = (r.status!=='OK' && r.material_id)
              ? `<button class="btn btn-xs btn-info text-white"
                    onclick="slgmRequestFromWH(${r.material_id}, ${r.shortfall_kg||r.required_kg}, '${(r.material_name||r.component).replace(/'/g,'&apos;')}')">
                   <i class="bi bi-cart-plus me-1"></i>Request ${fmt(r.shortfall_kg||r.required_kg)} ${r.unit}
                 </button>`
              : '<span class="text-muted small">—</span>';
            return `<tr>
              <td>${matLabel}</td>
              <td class="text-end fw-semibold">${fmt(r.required_kg)} ${r.unit}</td>
              <td class="text-end ${r.on_hand_kg<=0?'text-muted':''}">${fmt(r.on_hand_kg)}</td>
              <td class="text-end ${r.shortfall_kg>0?'text-danger fw-bold':'text-muted'}">${r.shortfall_kg>0?fmt(r.shortfall_kg):'—'}</td>
              <td class="text-end small">${fmt(r.wh_stock)}</td>
              <td><span class="badge bg-${stat[0]}">${stat[1]}</span></td>
              <td class="text-end" style="white-space:nowrap">${action}</td>
            </tr>`;
          }).join('')}</tbody>
        </table>
      </div>
      ${(summary.no_recipe_batches||[]).length ? `
        <div class="alert alert-warning py-1 px-2 m-2 small">
          <i class="bi bi-exclamation-triangle me-1"></i>
          ${summary.no_recipe_batches.length} batch(es) with no matching glue recipe — set up recipes for:
          ${summary.no_recipe_batches.slice(0,5).map(x => `<code>${x.glue_code}</code> (${x.batch})`).join(', ')}
        </div>`:''}`;
  }catch(e){
    box.innerHTML = `<div class="text-danger small p-2">${e.message||e}</div>`;
  }
}

// The glue-mix station is per-line — its WH requests must carry the parent line
// so they show in My Open Requests (line-scoped) and in the warehouse queue
// (not "no line"). Mirror how stOpenWHRequest resolves the station line.
function _slgmLine(){
  return document.getElementById('sl-line')?.value
      || document.getElementById('st-line')?.value || '';
}
async function slgmRequestFromWH(materialId, qty, name){
  const ask = prompt(`Request from Warehouse for "${name}".\n\nLitres / kg to request:`, String(qty || ''));
  if(ask === null) return;
  const q = Number(ask);
  if(!q || q<=0){ alert('Enter a positive quantity'); return; }
  try{
    await api('/api/consumable-requests','POST',{
      material_id: materialId,
      qty_requested: q,
      department: 'glue_mix',
      line_id: _slgmLine(),
      notes: `From Glue Mixing shortfall — auto suggestion for ${name}`,
    });
    toast(`Request sent to WH for ${q} of ${name}`,'success');
    slgmReloadShortfall();
  }catch(e){ alert('Request failed: '+(e.message||e)); }
}

// One-click: fire a WH request for every SHORT and LOW component currently
// shown in the shortfall card. Suggested qty per row = shortfall (or full
// requirement if there's no on-hand). User can apply a buffer % up-front.
async function slgmBulkRequestWH(){
  const rows = (_slgmShortfallRows || []).filter(r =>
    (r.status==='SHORT' || r.status==='LOW') && r.material_id && (r.shortfall_kg||r.required_kg) > 0);
  if(!rows.length){ toast('No SHORT or LOW components to request','warning'); return; }
  const ctx = _gmSelectedBatches.length
    ? `for ${_gmSelectedBatches.length} selected batch(es)`
    : 'across all laminating batches in the pipeline';
  const bufRaw = prompt(
    `Send ${rows.length} consumable request(s) to Warehouse ${ctx}.\n\n` +
    `Add a buffer % above the shortfall (0 = exact, 10 = +10%):`,
    '0'
  );
  if(bufRaw === null) return;
  const bufPct = Math.max(0, Number(bufRaw)||0);
  let ok=0, fail=0;
  for(const r of rows){
    const base = r.shortfall_kg > 0 ? r.shortfall_kg : r.required_kg;
    const qty  = Math.round(base * (1 + bufPct/100) * 1000) / 1000;
    const tag  = r.status==='LOW' ? 'safety top-up' : 'shortfall';
    try{
      await api('/api/consumable-requests','POST',{
        material_id: r.material_id,
        qty_requested: qty,
        department: 'glue_mix',
        line_id: _slgmLine(),
        notes: `Glue Mixing ${tag} (${r.component}) ${ctx}` +
               (bufPct>0?` · +${bufPct}% buffer`:''),
      });
      ok++;
    }catch(e){ fail++; console.error('WH req failed for', r.component, e); }
  }
  toast(`Sent ${ok} WH request(s)${fail?` · ${fail} failed`:''}${bufPct>0?` · +${bufPct}% buffer`:''}`,
        fail?'warning':'success');
  slgmReloadShortfall();
}

function slGlueMixClear(){
  _gmSelectedBatches = []; _gmActiveBatch = null; _gmActiveRecipe = null;
  _renderSlBatchList_glueMix();
  slRenderGlueMixCard();
}

async function slSelectBatch(id){
  const b=await api(`/api/batches/${id}`).catch(()=>null);
  if(!b)return;
  _slActiveBatch=b;
  // Pre-load presets for this department so the preset bar can be rendered synchronously
  if(b.current_department && PRESET_SCHEMA[b.current_department]){
    await loadPresets(b.current_department);
  }
  renderSlBatchList();
  renderStationForms(b);
  // Populate the multi-row preset dropdown (lam/rep) once DOM is ready
  setTimeout(()=>{ try{ _refreshMultiRowDropdown(b.current_department); }catch{} }, 0);
}
function renderStationForms(batch){
  const area=document.getElementById('sl-station-area');
  const dept=batch.current_department||'fc';
  // Merged Glue & Laminating station in "Mix glue" mode — render the multi-batch
  // glue mix card instead of the regular per-batch station form.
  if((document.getElementById('sl-dept-filter')?.value || '') === 'laminating' && _slView==='mix'){
    return slRenderGlueMixCard();
  }
  const idx=DEPT_ORDER.indexOf(dept);
  const isDone=dept==='fg_warehouse';
  area.innerHTML=`
    <div class="mb-3 d-flex align-items-center gap-3 flex-wrap">
      <div>
        <h5 class="mb-0 d-flex align-items-center gap-2">
          ${prioDot(batch.priority||2)}${batch.batch_number||'B#'+batch.id}
          ${prioBadge(batch.priority||2)}
          <button class="btn btn-sm btn-link p-0 text-muted" title="Open full detail (right-click)" onclick="deptBatchDetail(${batch.id},'${batch.current_department}')"><i class="bi bi-arrows-angle-expand"></i></button>
        </h5>
        <small class="text-muted">${batch.product_name||batch.sku||''} · ${batch.production_line||''} · ${fmt(batch.quantity)} pcs · ${batch.prod_order_number?'PO: '+batch.prod_order_number:''}</small>
      </div>
      <div class="ms-auto d-flex gap-1 flex-wrap">
        ${DEPT_ORDER.filter(d=>d!=='fg_warehouse').map((d,i)=>`
          <span class="badge ${i<idx?'bg-success':i===idx?'bg-primary':'bg-light text-muted border'}" style="font-size:.65rem">
            <i class="bi ${DEPT_ICON[d]} me-1"></i>${DEPT_LABEL[d]}
          </span>`).join('')}
      </div>
    </div>
    <!-- The inline "Route to next station / Move" bar was removed; use
         "Log & Move to Next Station" inside the station card instead. The
         hidden select stays so existing JS that reads sl-route-select
         continues to work (defaults to current department). -->
    <select id="sl-route-select" class="d-none">
      ${DEPT_ORDER.map(d=>`<option value="${d}"${d===dept?' selected':''}>${d}</option>`).join('')}
    </select>
    <div id="sl-form-area">
      ${isDone
        ? '<div class="alert alert-success"><i class="bi bi-check-circle-fill me-2"></i>Batch in FG Warehouse. Production complete.</div>'
        : renderStationCard(batch)}
    </div>
  `;
}
function renderStationCard(batch){
  const s=DEPT_TO_FORM[batch.current_department]||'GLUE_MIX';
  const bid=batch.batch_number||('B#'+batch.id);
  // Station forms work in PCS, not pallets — use total_pcs (computed by backend)
  const pq = batch.total_pcs ?? ((batch.quantity||0) * (batch.pallet_qty||1));
  // Cache total pcs on the batch for the auto-split detector
  window._slBatchTotalPcs = pq;
  window._slBatchId = batch.id;
  // WH requests are now handled inside the merged Stock & Movements tab —
  // station cards no longer expose a "Request from WH" button.
  const whBtn = '';
  const dept=batch.current_department;
  const psBar=PRESET_SCHEMA[dept] && !PRESET_SCHEMA[dept].perRow ? presetBar(dept) : '';
  const formMap={
    GLUE_MIX: `
      <h6><i class="bi bi-clipboard-check text-primary me-1"></i>FC Checkpoint</h6>
      <p class="text-muted small">Batch is at FC. Use the <b>FC Material Check</b> page to verify veneers/boards and release to laminating. Log any notes here.</p>
      <div class="mb-2"><label class="form-label small">Notes</label>
        <input class="form-control form-control-sm" id="sf-notes" placeholder="Any FC notes for this batch"></div>
      <div class="d-flex gap-2 mt-2 flex-wrap">${whBtn}</div>`,

    LAMINATING: `
      <h6><i class="bi bi-table text-primary me-1"></i>Laminating
        <button class="btn btn-link btn-sm py-0" onclick="openPresetManage('laminating')" title="Manage saved presets"><i class="bi bi-bookmarks"></i> Manage Presets</button>
      </h6>
      <p class="small text-muted mb-2"><i class="bi bi-info-circle me-1"></i>Each row has its own preset selector. Or use the dropdown below to load/save the <b>entire current set</b> of tables &amp; operators in one click.</p>
      ${multiRowPresetBar('laminating', bid)}
      <div id="lam-rows-area"></div>
      <button class="btn btn-outline-primary btn-sm mb-2" onclick="addLamRow('${bid}')"><i class="bi bi-plus-lg me-1"></i>Add table row</button>
      <div class="p-2 mt-2 rounded" style="background:#dcfce7;border:1px solid #86efac">
        <div class="row g-2 align-items-end">
          <div class="col-md-5">
            <label class="form-label small fw-semibold mb-1"><i class="bi bi-arrow-right-circle me-1 text-success"></i>Next station (for "Log &amp; Move")</label>
            <select class="form-select form-select-sm" id="lam-next-dept">
              <option value="cold_press" selected>Cold Press</option>
              <option value="repair">Repair</option>
              <option value="sanding">Sanding</option>
              <option value="hot_press">Hot Press</option>
              <option value="grading">Grading</option>
              <option value="packing">Packing</option>
            </select>
          </div>
          <div class="col-md-3">
            <label class="form-label small fw-semibold mb-1">Line</label>
            <select class="form-select form-select-sm" id="lam-next-line">
              <option value="">— keep ${batch.production_line||'current'} —</option>
              <option ${batch.production_line==='P01'?'selected':''}>P01</option>
              <option ${batch.production_line==='P02'?'selected':''}>P02</option>
              <option ${batch.production_line==='P37'?'selected':''}>P37</option>
            </select>
          </div>
          <div class="col-md-4 text-end">
            <span class="small text-muted">Defaults to Cold Press · same line</span>
          </div>
        </div>
      </div>
      <div class="d-flex gap-2 mt-2 flex-wrap">
        <button class="btn btn-primary btn-sm" onclick="submitAllLam('${bid}', false)"><i class="bi bi-floppy me-1"></i>Log Laminating Rows</button>
        <button class="btn btn-success btn-sm" onclick="submitAllLam('${bid}', true)"
                title="Log this laminating batch AND move it onward in one go">
          <i class="bi bi-check2-all me-1"></i>Log &amp; Move to Next Station
        </button>
        <button class="btn btn-outline-warning btn-sm" onclick="openLamFcRequest('${bid}')">
          <i class="bi bi-arrow-down-up me-1"></i>Request Material from FC
        </button>
        <button class="btn btn-outline-danger btn-sm" onclick="openLamFcReturn('${bid}')"
                title="FC sent the wrong material or wrong quantity — return it back">
          <i class="bi bi-arrow-return-left me-1"></i>Return Material to FC
        </button>
        <button class="btn btn-outline-danger btn-sm" onclick='scrapOpen(${JSON.stringify(batch).replace(/'/g,"&apos;")})'
                title="Reject defective pcs into the LG/scrap bin">
          <i class="bi bi-trash3 me-1"></i>Reject to LG Bin
        </button>
        ${whBtn}
      </div>`,

    COLD_PRESS: `
      <h6><i class="bi bi-snow text-info me-1"></i>Cold Press</h6>
      ${psBar}
      <div class="row g-2">
        <div class="col-md-3"><label class="form-label small">Machine <span class="text-danger">*</span></label>
          <select class="form-select form-select-sm" id="sf-cp-machine">${msOptionsFor('cold_press', batch.production_line)}</select>
          ${msCapacityHint('cold_press')}
        </div>
        <div class="col-md-3"><label class="form-label small">Operator</label>
          <input class="form-control form-control-sm" id="sf-cp-op" list="sl-emp-list" placeholder="Operator"></div>
        <div class="col-md-2"><label class="form-label small">Pressure (bar)</label>
          <input type="number" class="form-control form-control-sm" id="sf-cp-bar" min="0" step="0.1"></div>
        <div class="col-md-2"><label class="form-label small">Dwell (min)</label>
          <input type="number" class="form-control form-control-sm" id="sf-cp-min" min="1"></div>
        <div class="col-md-1"><label class="form-label small">Pcs in</label>
          <input type="number" class="form-control form-control-sm" id="sf-cp-in" value="${pq}" min="0"></div>
        <div class="col-md-1"><label class="form-label small">Pcs out</label>
          <input type="number" class="form-control form-control-sm" id="sf-cp-out" min="0"></div>
      </div>
      <div class="d-flex gap-2 mt-3 flex-wrap">
        <button class="btn btn-info btn-sm text-white" onclick="submitColdPress('${bid}')"><i class="bi bi-floppy me-1"></i>Log Cold Press</button>
        ${whBtn}
      </div>`,

    REPAIR: `
      <h6><i class="bi bi-tools text-secondary me-1"></i>Repair
        <button class="btn btn-link btn-sm py-0" onclick="openPresetManage('repair')" title="Manage saved presets"><i class="bi bi-bookmarks"></i> Manage Presets</button>
      </h6>
      ${multiRowPresetBar('repair', bid)}
      <div id="rep-rows-area"></div>
      <button class="btn btn-outline-secondary btn-sm mb-2" onclick="addRepRow('${bid}')"><i class="bi bi-plus-lg me-1"></i>Add repair row</button>
      <div class="d-flex gap-2 mt-2 flex-wrap">
        <button class="btn btn-secondary btn-sm" onclick="submitAllRep('${bid}')"><i class="bi bi-floppy me-1"></i>Log Repair Rows</button>
        ${whBtn}
      </div>`,

    SANDING: `
      <h6><i class="bi bi-eraser text-warning me-1"></i>Sanding</h6>
      ${psBar}
      <div class="row g-2">
        <div class="col-md-3"><label class="form-label small">Machine <span class="text-danger">*</span></label>
          <select class="form-select form-select-sm" id="sf-snd-machine">${msOptionsFor('sanding', batch.production_line)}</select>
          ${msCapacityHint('sanding')}
        </div>
        <div class="col-md-3"><label class="form-label small">Operator</label>
          <input class="form-control form-control-sm" id="sf-snd-op" list="sl-emp-list" placeholder="Operator"></div>
        <div class="col-md-2"><label class="form-label small">Grit <span class="text-danger">*</span></label>
          <select class="form-select form-select-sm" id="sf-snd-grit"><option>80</option><option>100</option><option>120</option><option>150</option><option>180</option></select></div>
        <div class="col-md-2"><label class="form-label small">Feed (m/min)</label>
          <input type="number" class="form-control form-control-sm" id="sf-snd-feed" step="0.1" min="0"></div>
        <div class="col-md-1"><label class="form-label small">Pcs in</label>
          <input type="number" class="form-control form-control-sm" id="sf-snd-in" value="${pq}" min="0"></div>
        <div class="col-md-1"><label class="form-label small">Pcs out</label>
          <input type="number" class="form-control form-control-sm" id="sf-snd-out" min="0"></div>
      </div>
      <div class="d-flex align-items-center gap-3 mt-2">
        <label class="form-label small mb-0">Veneer defects:</label>
        <div class="d-flex align-items-center gap-1">
          <button class="btn btn-sm btn-outline-secondary py-0" onclick="sndStepper(-1)">−</button>
          <span class="fw-bold px-2" id="sf-defect-count" style="min-width:2rem;text-align:center">0</span>
          <button class="btn btn-sm btn-outline-secondary py-0" onclick="sndStepper(1)">+</button>
          <span class="badge ms-1" id="sf-defect-badge" style="display:none"></span>
        </div>
      </div>
      <div class="d-flex gap-2 mt-3 flex-wrap">
        <button class="btn btn-warning btn-sm" onclick="submitSanding('${bid}')"><i class="bi bi-floppy me-1"></i>Log Sanding</button>
        ${whBtn}
      </div>`,

    HOT_PRESS: `
      <h6><i class="bi bi-thermometer-sun text-danger me-1"></i>Hot Press</h6>
      ${psBar}
      <div class="row g-2">
        <div class="col-md-3"><label class="form-label small">Machine <span class="text-danger">*</span></label>
          <select class="form-select form-select-sm" id="sf-hp-machine">${msOptionsFor('hot_press', batch.production_line)}</select>
          ${msCapacityHint('hot_press')}
        </div>
        <div class="col-md-3"><label class="form-label small">Operator</label>
          <input class="form-control form-control-sm" id="sf-hp-op" list="sl-emp-list" placeholder="Operator"></div>
        <div class="col-md-2"><label class="form-label small">Temp (°C) <span class="text-danger">*</span></label>
          <input type="number" class="form-control form-control-sm" id="sf-hp-temp" min="0"></div>
        <div class="col-md-2"><label class="form-label small">Pressure (bar)</label>
          <input type="number" class="form-control form-control-sm" id="sf-hp-bar" step="0.1" min="0"></div>
        <div class="col-md-1"><label class="form-label small">Time (min)</label>
          <input type="number" class="form-control form-control-sm" id="sf-hp-min" min="1"></div>
        <div class="col-md-1"><label class="form-label small">Pcs in</label>
          <input type="number" class="form-control form-control-sm" id="sf-hp-in" value="${pq}" min="0"></div>
      </div>
      <div class="row g-2 mt-1">
        <div class="col-md-2"><label class="form-label small">Pcs out</label>
          <input type="number" class="form-control form-control-sm" id="sf-hp-out" min="0"></div>
      </div>
      <div class="d-flex gap-2 mt-3 flex-wrap">
        <button class="btn btn-danger btn-sm" onclick="submitHotPress('${bid}')"><i class="bi bi-floppy me-1"></i>Log Hot Press</button>
        ${whBtn}
      </div>`,

    GRADING: `
      <h6><i class="bi bi-patch-check text-success me-1"></i>Grading (QC)</h6>
      ${psBar}
      <div class="row g-2 mb-2">
        <div class="col-md-4"><label class="form-label small">Grader</label>
          <input class="form-control form-control-sm" id="sf-grader" list="sl-emp-list" placeholder="Grader name"></div>
        <div class="col-md-2"><label class="form-label small text-success">Grade A pcs</label>
          <input type="number" class="form-control form-control-sm border-success" id="sf-gr-a" min="0" value="0" oninput="grNcgCheck()"></div>
        <div class="col-md-2"><label class="form-label small text-primary">Grade B pcs</label>
          <input type="number" class="form-control form-control-sm border-primary" id="sf-gr-b" min="0" value="0" oninput="grNcgCheck()"></div>
        <div class="col-md-2"><label class="form-label small text-warning">NCG pcs</label>
          <input type="number" class="form-control form-control-sm border-warning" id="sf-gr-ncg" min="0" value="0" oninput="grNcgCheck()"></div>
        <div class="col-md-2"><label class="form-label small text-danger">Reject pcs</label>
          <input type="number" class="form-control form-control-sm border-danger" id="sf-gr-rej" min="0" value="0" oninput="grNcgCheck()"></div>
      </div>
      <div id="sf-grade-total" class="small text-muted mb-2"></div>
      <!-- NCG Issues container (shown when NCG > 0) -->
      <div id="sf-ncg-issues-wrap" class="d-none">
        <div class="d-flex justify-content-between align-items-center mb-1">
          <label class="form-label small fw-semibold mb-0 text-warning"><i class="bi bi-exclamation-triangle me-1"></i>NCG Issue Breakdown</label>
          <button type="button" class="btn btn-outline-warning btn-sm py-0 px-2" style="font-size:.72rem" onclick="addNcgIssueRow()">
            <i class="bi bi-plus-lg me-1"></i>Add Issue
          </button>
        </div>
        <div id="sf-ncg-issues-rows">
          <!-- rows added dynamically -->
        </div>
        <div id="sf-ncg-issue-total" class="small text-muted mt-1"></div>
      </div>
      <div class="mb-2 mt-2">
        <label class="form-label small">Notes</label>
        <input class="form-control form-control-sm" id="sf-gr-notes">
      </div>
      <div class="d-flex gap-2 mt-2 flex-wrap">
        <button class="btn btn-success btn-sm" onclick="submitGrading('${bid}')"><i class="bi bi-patch-check me-1"></i>Submit Grade + auto-backtrack</button>
        ${whBtn}
      </div>`,
    PACKING: `
      <h6><i class="bi bi-boxes text-purple me-1" style="color:#8b5cf6"></i>Packing</h6>
      <div class="alert alert-light border-start border-4 py-2 small mb-3" style="border-color:#8b5cf6!important">
        <i class="bi bi-info-circle me-1"></i>Consolidation point — all lines feed into Packing.
      </div>
      ${psBar}
      <div class="row g-2">
        <div class="col-md-3"><label class="form-label small">Operator <span class="text-danger">*</span></label>
          <input class="form-control form-control-sm" id="sf-pk-op" list="sl-emp-list" placeholder="Operator name"></div>
        <div class="col-md-3"><label class="form-label small">Packing Table</label>
          <select class="form-select form-select-sm" id="sf-pk-table">
            <option value="">Select...</option>
            <option>PKT-01</option><option>PKT-02</option><option>PKT-03</option>
          </select></div>
        <div class="col-md-2"><label class="form-label small">Pcs In</label>
          <input type="number" class="form-control form-control-sm" id="sf-pk-in" value="${pq}" min="0"></div>
        <div class="col-md-2"><label class="form-label small">Pcs Packed</label>
          <input type="number" class="form-control form-control-sm" id="sf-pk-packed" min="0" placeholder="0"></div>
        <div class="col-md-2"><label class="form-label small">Pcs Held</label>
          <input type="number" class="form-control form-control-sm" id="sf-pk-held" min="0" value="0"></div>
      </div>
      <div class="row g-2 mt-1">
        <div class="col-md-2"><label class="form-label small">Cartons</label>
          <input type="number" class="form-control form-control-sm" id="sf-pk-cartons" min="0" placeholder="0"></div>
        <div class="col-md-3"><label class="form-label small">Packaging SKU</label>
          <input class="form-control form-control-sm" id="sf-pk-sku" placeholder="e.g. PKG-STD-12MM"></div>
        <div class="col-md-7"><label class="form-label small">Notes</label>
          <input class="form-control form-control-sm" id="sf-pk-notes"></div>
      </div>
      <div class="d-flex gap-2 mt-3 flex-wrap">
        <button class="btn btn-sm text-white" style="background:#8b5cf6" onclick="submitPacking('${bid}')">
          <i class="bi bi-floppy me-1"></i>Log Packing
        </button>
        ${whBtn}
      </div>`,
  };

  // Filter employees to current department (and unassigned ones who can work anywhere)
  const deptEmps=(_allEmployees||[]).filter(e=>!dept||!e.department||e.department===dept);
  return `<div class="card p-3">${formMap[s]||'<p class="text-muted">Unknown status: '+s+'</p>'}</div>
    <datalist id="sl-emp-list">${deptEmps.map(e=>`<option value="${e.emp_id}">${e.emp_name} (${e.department||'—'})</option>`).join('')}</datalist>`;
}

// Laminating multi-row
let _lamRows=[], _repRows=[];
function addLamRow(bid){
  const id=Date.now();
  _lamRows.push({id});
  const area=document.getElementById('lam-rows-area');
  const div=document.createElement('div');
  div.className='border rounded p-2 mb-2 position-relative'; div.id=`lam-row-${id}`;
  div.innerHTML=`
    <button type="button" class="btn-close position-absolute" style="top:6px;right:8px;font-size:.65rem"
      onclick="this.closest('.border').remove();_lamRows=_lamRows.filter(r=>r.id!=${id})"></button>
    ${presetBar('laminating', id)}
    <div class="row g-2 align-items-end">
      <div class="col-6 col-md-2"><label class="form-label small mb-1">Table</label>
        <select class="form-select form-select-sm" id="lam-tbl-${id}">
          ${['T01','T02','T03','T04','T05','T06','T07','T08','T09','T10'].map(t=>`<option>${t}</option>`).join('')}
        </select></div>
      <div class="col-6 col-md-2"><label class="form-label small mb-1">Operator 1</label>
        <input class="form-control form-control-sm" id="lam-e1-${id}" list="sl-emp-list" placeholder="EMP-001"></div>
      <div class="col-6 col-md-2"><label class="form-label small mb-1">Operator 2</label>
        <input class="form-control form-control-sm" id="lam-e2-${id}" list="sl-emp-list" placeholder="EMP-002"></div>
      <div class="col-4 col-md-1"><label class="form-label small mb-1">Target</label>
        <input type="number" class="form-control form-control-sm" id="lam-tgt-${id}" min="1" placeholder="0"></div>
      <div class="col-4 col-md-1"><label class="form-label small mb-1">Actual</label>
        <input type="number" class="form-control form-control-sm" id="lam-act-${id}" min="0" placeholder="0"></div>
      <div class="col-4 col-md-2">
        <label class="form-label small mb-1">Time (min) <span class="text-danger">*</span></label>
        <div class="input-group input-group-sm">
          <input type="number" class="form-control" id="lam-time-${id}" min="1" placeholder="e.g. 480">
          <span class="input-group-text" style="font-size:.7rem">min</span>
        </div>
      </div>
      <div class="col-12 col-md-2"><label class="form-label small mb-1">Mix ref</label>
        <input class="form-control form-control-sm" id="lam-mix-${id}" placeholder="MIX-..."></div>
    </div>`;
  area.appendChild(div);
}
function addRepRow(bid){
  const id=Date.now();
  _repRows.push({id});
  const area=document.getElementById('rep-rows-area');
  const div=document.createElement('div');
  div.className='border rounded p-2 mb-2 position-relative'; div.id=`rep-row-${id}`;
  div.innerHTML=`
    <button type="button" class="btn-close position-absolute" style="top:6px;right:8px;font-size:.65rem"
      onclick="this.closest('.border').remove();_repRows=_repRows.filter(r=>r.id!=${id})"></button>
    ${presetBar('repair', id)}
    <div class="row g-2 align-items-end">
      <div class="col-6 col-md-2"><label class="form-label small mb-1">Table</label>
        <select class="form-select form-select-sm" id="rep-tbl-${id}">
          ${['T01','T02','T03','T04','T05','T06','T07','T08','T09','T10'].map(t=>`<option>${t}</option>`).join('')}
        </select></div>
      <div class="col-6 col-md-2"><label class="form-label small mb-1">Type</label>
        <select class="form-select form-select-sm" id="rep-type-${id}"><option>ROUGH</option><option>FINE</option></select></div>
      <div class="col-6 col-md-2"><label class="form-label small mb-1">Operator 1</label>
        <input class="form-control form-control-sm" id="rep-e1-${id}" list="sl-emp-list" placeholder="EMP-001"></div>
      <div class="col-6 col-md-2"><label class="form-label small mb-1">Operator 2</label>
        <input class="form-control form-control-sm" id="rep-e2-${id}" list="sl-emp-list" placeholder="EMP-002"></div>
      <div class="col-6 col-md-2"><label class="form-label small mb-1">Pcs repaired</label>
        <input type="number" class="form-control form-control-sm" id="rep-pcs-${id}" min="0"></div>
      <div class="col-12 col-md-2"><label class="form-label small mb-1">Notes</label>
        <input class="form-control form-control-sm" id="rep-notes-${id}"></div>
    </div>`;
  area.appendChild(div);
}

// Sanding defect stepper
let _sndDefects=0;
function sndStepper(d){
  _sndDefects=Math.max(0,_sndDefects+d);
  document.getElementById('sf-defect-count').textContent=_sndDefects;
  const badge=document.getElementById('sf-defect-badge');
  if(_sndDefects>0){
    badge.textContent=_sndDefects+' defect'+ (_sndDefects>1?'s':'');
    badge.className='badge ms-1 '+(_sndDefects>3?'bg-danger':'bg-warning text-dark');
    badge.style.display='';
  } else { badge.style.display='none'; }
}
const NCG_REASONS = [
  {code:'NCG-DELAMINATION',  label:'Veneer delamination'},
  {code:'NCG-SANDED-VENEER', label:'Sanded through veneer'},
  {code:'NCG-GLUE-BLEED',    label:'Glue bleed through'},
  {code:'NCG-SURFACE-ROUGH', label:'Surface roughness'},
  {code:'NCG-THICKNESS-VAR', label:'Thickness variation'},
  {code:'NCG-OTHER',         label:'Other'},
];
let _ncgIssueCount = 0;

function grNcgCheck(){
  const ncg=parseInt(document.getElementById('sf-gr-ncg')?.value)||0;
  const a=parseInt(document.getElementById('sf-gr-a')?.value)||0;
  const b=parseInt(document.getElementById('sf-gr-b')?.value)||0;
  const rej=parseInt(document.getElementById('sf-gr-rej')?.value)||0;
  const total=a+b+ncg+rej;
  const tot=document.getElementById('sf-grade-total');
  if(tot) tot.textContent=`Total: ${total} pcs  |  Yield: ${total?Math.round((a+b)/total*100):0}%`;
  const wrap=document.getElementById('sf-ncg-issues-wrap');
  if(!wrap) return;
  if(ncg>0){
    wrap.classList.remove('d-none');
    if(!document.querySelectorAll('.ncg-issue-row').length) addNcgIssueRow();
    _updateNcgIssueTotals();
  } else {
    wrap.classList.add('d-none');
  }
}

function addNcgIssueRow(){
  _ncgIssueCount++;
  const idx=_ncgIssueCount;
  const opts=NCG_REASONS.map(r=>`<option value="${r.code}">${r.label}</option>`).join('');
  const row=document.createElement('div');
  row.className='ncg-issue-row row g-1 mb-2 align-items-center';
  row.dataset.idx=idx;
  row.innerHTML=`
    <div class="col">
      <select class="form-select form-select-sm" id="ncg-reason-${idx}" onchange="_updateNcgIssueTotals()">
        ${opts}
      </select>
    </div>
    <div class="col-auto" style="min-width:90px">
      <div class="input-group input-group-sm">
        <input type="number" class="form-control" id="ncg-pcs-${idx}" min="1" placeholder="pcs" oninput="_updateNcgIssueTotals()">
        <span class="input-group-text">pcs</span>
      </div>
    </div>
    <div class="col" style="min-width:120px">
      <input type="text" class="form-control form-control-sm" id="ncg-note-${idx}" placeholder="note (optional)">
    </div>
    <div class="col-auto">
      <button type="button" class="btn btn-sm btn-outline-danger py-0 px-1" onclick="this.closest('.ncg-issue-row').remove();_updateNcgIssueTotals()">
        <i class="bi bi-x"></i>
      </button>
    </div>`;
  document.getElementById('sf-ncg-issues-rows').appendChild(row);
}

function _updateNcgIssueTotals(){
  const rows=document.querySelectorAll('.ncg-issue-row');
  const total=Array.from(rows).reduce((s,r)=>{
    const id=r.dataset.idx;
    return s+(parseInt(document.getElementById('ncg-pcs-'+id)?.value)||0);
  },0);
  const ncgTarget=parseInt(document.getElementById('sf-gr-ncg')?.value)||0;
  const el=document.getElementById('sf-ncg-issue-total');
  if(el){
    const diff=ncgTarget-total;
    el.textContent=`Issues total: ${total} pcs${ncgTarget?` (NCG: ${ncgTarget}, ${diff>0?'unallocated: '+diff:diff<0?'over by '+Math.abs(diff):'✓ balanced'})`:''}`;
    el.className='small mt-1 '+(diff===0?'text-success':'text-warning');
  }
}

function _collectNcgIssues(){
  const rows=document.querySelectorAll('.ncg-issue-row');
  return Array.from(rows).map(r=>{
    const id=r.dataset.idx;
    return {
      reason_code: document.getElementById('ncg-reason-'+id)?.value||'',
      pcs_count:   parseInt(document.getElementById('ncg-pcs-'+id)?.value)||0,
      notes:       document.getElementById('ncg-note-'+id)?.value||'',
    };
  }).filter(r=>r.reason_code && r.pcs_count>0);
}

// ── Submit handlers ────────────────────────────────────────────
async function submitGlueMix(bid){
  const body={batch_id:bid,recipe_code:document.getElementById('sf-recipe').value.trim(),
    qty_kg:parseFloat(document.getElementById('sf-glue-kg').value)||0,
    mix_time_min:parseInt(document.getElementById('sf-mix-min').value)||null,
    operator_name:document.getElementById('sf-op-name').value.trim(),
    notes:document.getElementById('sf-notes').value||null};
  if(!body.recipe_code||!body.qty_kg){toast('Recipe code and qty required','danger');return;}
  try{await api('/api/production/glue-mix','POST',body);toast('Glue mix logged');slSelectBatch(_slActiveBatch?.id);}
  catch(e){toast(e.message,'danger');}
}
async function submitAllLam(bid, moveAfter=false){
  if(!_lamRows.length){toast('Add at least one laminating table row','danger');return;}
  let ok=0, totalPcs=0;
  for(const r of _lamRows){
    const timeVal=parseInt(document.getElementById(`lam-time-${r.id}`)?.value)||0;
    if(!timeVal){toast(`Table row ${r.id}: Time (min) is required`,'danger');continue;}
    const body={batch_id:bid,table_id:document.getElementById(`lam-tbl-${r.id}`).value,
      emp_code_1:document.getElementById(`lam-e1-${r.id}`).value.trim()||'—',
      emp_code_2:document.getElementById(`lam-e2-${r.id}`).value.trim()||'—',
      pcs_target:parseInt(document.getElementById(`lam-tgt-${r.id}`).value)||0,
      pcs_actual:parseInt(document.getElementById(`lam-act-${r.id}`).value)||0,
      time_minutes:timeVal,
      glue_mix_ref:document.getElementById(`lam-mix-${r.id}`).value||null};
    if(!body.pcs_target)continue;
    try{await api('/api/production/laminating','POST',body);ok++; totalPcs += body.pcs_actual;}catch(e){toast(e.message,'danger');}
  }
  if(ok>0){
    _lamRows=[];
    if(moveAfter && _slActiveBatch){
      // Use the inline Next Station picker as preferred destination
      const presetDept = document.getElementById('lam-next-dept')?.value || '';
      const presetLine = document.getElementById('lam-next-line')?.value || '';
      toast(`${ok} laminating row${ok>1?'s':''} logged — moving onward`);
      try{ slPostReportPrompt(_slActiveBatch, totalPcs, {presetDept, presetLine, autoConfirmIfClean:true}); }
      catch(e){ console.error(e); }
    }else{
      toast(`${ok} laminating row${ok>1?'s':''} logged`);
      slSelectBatch(_slActiveBatch?.id);
    }
  }
}
async function submitAllRep(bid){
  let ok=0;
  for(const r of _repRows){
    const body={batch_id:bid,table_id:document.getElementById(`rep-tbl-${r.id}`).value,
      repair_type:document.getElementById(`rep-type-${r.id}`).value,
      emp_code_1:document.getElementById(`rep-e1-${r.id}`).value.trim()||'—',
      emp_code_2:document.getElementById(`rep-e2-${r.id}`).value.trim()||'—',
      pcs_repaired:parseInt(document.getElementById(`rep-pcs-${r.id}`).value)||0,
      notes:document.getElementById(`rep-notes-${r.id}`).value||null};
    try{await api('/api/production/repair','POST',body);ok++;}catch(e){toast(e.message,'danger');}
  }
  toast(ok>0?`${ok} repair row${ok>1?'s':''} logged — use Route picker to advance`:'Repair logged — use Route picker to advance');
  _repRows=[];slSelectBatch(_slActiveBatch?.id);
}
// ── Auto-split helper ─────────────────────────────────────────
// Department flow (after which station goes where)
const DEPT_NEXT = {
  fc:'laminating', laminating:'cold_press', cold_press:'repair',
  repair:'sanding', sanding:'hot_press', hot_press:'grading',
  grading:'packing', packing:'fg_receiving', fg_receiving:'fg_warehouse',
};

/* If pcs_completed < batch's total pcs, prompt to split: completed portion moves to next dept,
   remainder stays at current dept. Returns true if split happened (caller should not also route). */
// Replaced with the richer "What next?" modal — gives the station leader
// the explicit choice between fixing the report, splitting, carrying the
// discrepancy, or moving the whole batch to a station/line of their choice.
async function _maybeAutoSplit(batch, pcs_completed, currentStationLabel){
  if(!batch) return false;
  // Always show the modal: it handles both full-report (just move) and
  // partial-report (offer split/error/move) cases cleanly.
  try{ slPostReportPrompt(batch, pcs_completed||0); }catch(e){ console.error(e); }
  return false;
}

async function submitColdPress(bid){
  const body={batch_id:bid,machine_id:document.getElementById('sf-cp-machine').value,
    operator_name:document.getElementById('sf-cp-op').value.trim(),
    pressure_bar:parseFloat(document.getElementById('sf-cp-bar').value)||null,
    dwell_min:parseInt(document.getElementById('sf-cp-min').value)||null,
    pcs_in:parseInt(document.getElementById('sf-cp-in').value)||0,
    pcs_out:parseInt(document.getElementById('sf-cp-out').value)||0};
  if(!body.machine_id){toast('Select a machine','danger');return;}
  try{
    await api('/api/production/cold-press','POST',body);
    toast('Cold press logged');
    await _maybeAutoSplit(_slActiveBatch, body.pcs_out, 'Cold Press');
    slLoadBatches(); // refresh list (batch may have split)
    slSelectBatch(_slActiveBatch?.id);
  }catch(e){toast(e.message,'danger');}
}
async function submitSanding(bid){
  const body={batch_id:bid,machine_id:document.getElementById('sf-snd-machine').value,
    operator_name:document.getElementById('sf-snd-op').value.trim(),
    grit_setting:document.getElementById('sf-snd-grit').value,
    feed_speed:parseFloat(document.getElementById('sf-snd-feed').value)||null,
    pcs_in:parseInt(document.getElementById('sf-snd-in').value)||0,
    pcs_out:parseInt(document.getElementById('sf-snd-out').value)||0,
    defect_count:_sndDefects};
  if(!body.machine_id){toast('Select a machine','danger');return;}
  try{
    await api('/api/production/sanding','POST',body);
    toast('Sanding logged');
    _sndDefects=0;
    await _maybeAutoSplit(_slActiveBatch, body.pcs_out, 'Sanding');
    slLoadBatches();
    slSelectBatch(_slActiveBatch?.id);
  }catch(e){toast(e.message,'danger');}
}
async function submitHotPress(bid){
  const body={batch_id:bid,machine_id:document.getElementById('sf-hp-machine').value,
    operator_name:document.getElementById('sf-hp-op').value.trim(),
    temp_c:parseFloat(document.getElementById('sf-hp-temp').value)||0,
    pressure_bar:parseFloat(document.getElementById('sf-hp-bar').value)||0,
    press_time_min:parseInt(document.getElementById('sf-hp-min').value)||0,
    pcs_in:parseInt(document.getElementById('sf-hp-in').value)||0,
    pcs_out:parseInt(document.getElementById('sf-hp-out').value)||0};
  if(!body.machine_id||!body.temp_c){toast('Machine and temperature required','danger');return;}
  try{
    await api('/api/production/hot-press','POST',body);
    toast('Hot press logged');
    await _maybeAutoSplit(_slActiveBatch, body.pcs_out, 'Hot Press');
    slLoadBatches();
    slSelectBatch(_slActiveBatch?.id);
  }catch(e){toast(e.message,'danger');}
}
async function submitGrading(bid){
  const ncg=parseInt(document.getElementById('sf-gr-ncg').value)||0;
  const issues=_collectNcgIssues();
  // Require at least one issue with a reason when NCG > 0
  if(ncg>0&&!issues.length){toast('Add at least one NCG issue reason when NCG pcs > 0','danger');return;}
  // Use first issue's reason as primary reason_code for backward compat
  const primaryReason=issues[0]?.reason_code||null;
  const body={batch_id:bid,
    grader_name:document.getElementById('sf-grader').value.trim(),
    pcs_grade_a:parseInt(document.getElementById('sf-gr-a').value)||0,
    pcs_grade_b:parseInt(document.getElementById('sf-gr-b').value)||0,
    pcs_ncg:ncg,pcs_reject:parseInt(document.getElementById('sf-gr-rej').value)||0,
    ncg_reason_code:primaryReason,
    notes:document.getElementById('sf-gr-notes').value||null};
  try{
    const result=await api('/api/production/grading','POST',body);
    // Save multi-reason NCG issues
    if(issues.length && result.grade_id){
      await api(`/api/production/grading/${result.grade_id}/ncg-issues`,'POST',{issues});
    }
    toast(`Grade submitted — outcome: ${result.outcome}`,'success');
    if(result.backtrack) renderBacktrackAlert(result.backtrack,bid);
    // Auto-split based on graded pcs (A+B = good, advance to packing)
    const goodPcs = body.pcs_grade_a + body.pcs_grade_b;
    await _maybeAutoSplit(_slActiveBatch, goodPcs, 'Grading');
    slLoadBatches();
    slSelectBatch(_slActiveBatch?.id);
  }catch(e){toast(e.message,'danger');}
}

async function submitPacking(bid){
  const op=document.getElementById('sf-pk-op').value.trim();
  if(!op){toast('Operator name required','danger');return;}
  const body={
    batch_id:bid,
    operator_name:op,
    table_id:document.getElementById('sf-pk-table').value||null,
    pcs_in:parseInt(document.getElementById('sf-pk-in').value)||0,
    pcs_packed:parseInt(document.getElementById('sf-pk-packed').value)||0,
    pcs_held:parseInt(document.getElementById('sf-pk-held').value)||0,
    cartons_count:parseInt(document.getElementById('sf-pk-cartons').value)||0,
    packaging_sku:document.getElementById('sf-pk-sku').value||null,
    notes:document.getElementById('sf-pk-notes').value||null
  };
  try{
    await api('/api/production/packing','POST',body);
    toast('Packing logged — use Route picker to mark Complete');
    await _maybeAutoSplit(_slActiveBatch, body.pcs_packed, 'Packing');
    slLoadBatches();
    slSelectBatch(_slActiveBatch?.id);
  }catch(e){toast(e.message,'danger');}
}
function renderBacktrackAlert(bt,bid){
  const el=document.getElementById('sl-form-area');
  const existing=document.getElementById('sl-backtrack-panel');
  if(existing)existing.remove();
  const div=document.createElement('div');
  div.id='sl-backtrack-panel';div.className='card border-warning mt-3 p-3';
  div.innerHTML=`
    <h6 class="text-warning fw-bold"><i class="bi bi-exclamation-triangle-fill me-1"></i>NCG Backtrack — ${bid}</h6>
    <div class="row g-2 small">
      <div class="col-md-3"><b>Lam tables:</b> ${bt.lam_tables||'—'}</div>
      <div class="col-md-3"><b>Lam pairs:</b> ${bt.lam_pairs||'—'}</div>
      <div class="col-md-3"><b>Lam efficacy:</b> ${bt.lam_efficacy_pct!=null?bt.lam_efficacy_pct+'%':'—'}</div>
      <div class="col-md-3"><b>Glue recipes:</b> ${bt.glue_recipes||'—'}</div>
      <div class="col-md-3"><b>Repair pairs:</b> ${bt.repair_pairs||'—'}</div>
      <div class="col-md-3"><b>Sanding op:</b> ${bt.sanding_operator||'—'}</div>
      <div class="col-md-3"><b>Sanding defects:</b> ${bt.sanding_defects!=null?bt.sanding_defects:'—'}</div>
      <div class="col-md-3"><b>Grit:</b> ${bt.grit_setting||'—'}</div>
      <div class="col-md-3"><b>HP op:</b> ${bt.hotpress_operator||'—'}</div>
      <div class="col-md-3"><b>HP temp:</b> ${bt.temp_c!=null?bt.temp_c+'°C':'—'}</div>
      <div class="col-md-3"><b>HP bar:</b> ${bt.hp_pressure!=null?bt.hp_pressure+' bar':'—'}</div>
      <div class="col-md-3"><b>HP time:</b> ${bt.press_time_min!=null?bt.press_time_min+' min':'—'}</div>
      <div class="col-12"><b>NCG reason:</b> <span class="badge bg-warning text-dark">${bt.ncg_reason_code||'—'}</span></div>
    </div>
    <button class="btn btn-warning btn-sm mt-2" onclick="runBatchDiagnosis('${bid}')"><i class="bi bi-stars me-1"></i>AI Diagnose this batch</button>
    <div id="sl-ai-result" class="mt-2"></div>`;
  el.appendChild(div);
}
// ── Free-form batch routing ─────────────────────────────────
async function slRouteBatch(batchId){
  const sel=document.getElementById('sl-route-select');
  const next=sel?.value;
  if(!next){toast('Select a destination station','warning');return;}
  const cur=_slActiveBatch?.current_department;
  if(next===cur){toast('Batch is already at '+DEPT_LABEL[next],'warning');return;}
  try{
    await api(`/api/batches/${batchId}/move`,'POST',{to_department:next,quantity:_slActiveBatch.quantity,moved_by:'Station Log',notes:'Routed via Station Log'});
    toast(`Batch routed → ${DEPT_LABEL[next]}`,'success');
    slSelectBatch(batchId);
  }catch(e){toast(e.message,'danger');}
}



// ════════════════════════════════════════════════════════════
// Glue Mix Station (_gmRecipes + gmLoad + gmOpenRecipe + gmSaveRecipe + …)
// ════════════════════════════════════════════════════════════
// ══════════════════════════════════════════════════════════
// GLUE MIX STATION
// ══════════════════════════════════════════════════════════
let _gmRecipes=[], _gmBatches=[], _gmActiveBatch=null, _gmActiveRecipe=null;
// Multi-batch selection: every batch sharing the active recipe can join the mix
let _gmSelectedBatches=[];   // array of batch records
let _gmBatchGlueInfo={};     // batch_id -> {glue_code, total_kg, recipe}

async function gmLoad(){
  const [recipes, batches] = await Promise.all([
    api('/api/glue-recipes?kind=glue').catch(()=>[]),
    api('/api/batches?department=laminating').catch(()=>[])
  ]);
  _gmRecipes=recipes||[];
  _gmBatches=batches||[];
  _gmBatchGlueInfo={};
  // Pre-fetch each batch's glue code so the queue can colour-code by recipe
  // (small list — one round-trip per batch is fine; cached for the session)
  await Promise.all((_gmBatches||[]).map(async b => {
    try{ _gmBatchGlueInfo[b.id] = await api(`/api/batches/${b.id}/glue-info`); }catch{}
  }));
  await gmRefreshStation();
  gmRenderRecipeTable();
  gmRenderBatchList();
}

function gmRenderBatchList(){
  const el=document.getElementById('gm-batch-list');
  document.getElementById('gm-queue-count').textContent=_gmBatches.length;
  if(!_gmBatches.length){el.innerHTML='<p class="text-muted small text-center pt-3">No batches in laminating queue.</p>';return;}
  const activeCode = _gmActiveRecipe?.recipe_code || '';
  el.innerHTML=_gmBatches.map(b=>{
    const info = _gmBatchGlueInfo[b.id] || {};
    const code = info.glue_code || '—';
    const matchesActive = activeCode ? (code === activeCode) : true;
    const isSelected = _gmSelectedBatches.some(x=>x.id===b.id);
    const disable = !matchesActive && !isSelected;
    return `
    <div class="border rounded p-2 mb-2 ${isSelected?'border-warning bg-light':''} ${disable?'opacity-50':''}"
         style="${disable?'background:#f3f4f6':''}">
      <label class="d-flex align-items-start gap-2 mb-0" style="cursor:${disable?'not-allowed':'pointer'}">
        <input type="checkbox" class="form-check-input mt-1" ${isSelected?'checked':''} ${disable?'disabled':''}
               onchange="gmToggleBatch(${b.id}, this.checked)">
        <div style="flex:1;min-width:0">
          <div class="fw-semibold small text-primary">${b.batch_number}</div>
          <div class="small text-muted text-truncate">${b.product_name||b.sku||''}</div>
          <div class="small text-muted">${b.production_line||''} · ${fmt(b.quantity)} pcs</div>
          <div class="small">
            <span class="badge bg-${code==='—'?'secondary':'warning text-dark'}" style="font-size:.6rem">${code}</span>
            ${info.total_kg?`<span class="text-muted ms-1">· ${fmt(info.total_kg)} kg</span>`:''}
          </div>
        </div>
      </label>
    </div>`;
  }).join('');
}

async function gmToggleBatch(id, checked){
  const b = _gmBatches.find(x=>x.id===id);
  if(!b) return;
  const info = _gmBatchGlueInfo[id] || {};
  if(checked){
    // First selection sets the active recipe; subsequent selections must match
    if(!_gmActiveRecipe){
      const recipe = info.recipe || _gmRecipes.find(r=>r.recipe_code===info.glue_code);
      if(!recipe){ alert(`Batch ${b.batch_number} has no matching glue recipe yet — open it from the queue to set up.`); return; }
      _gmActiveRecipe = recipe;
      _gmActiveBatch = b;   // keep first batch as "active" for legacy references
    }else if(info.glue_code && info.glue_code !== _gmActiveRecipe.recipe_code){
      alert(`Batch ${b.batch_number} uses ${info.glue_code} but the current mix is for ${_gmActiveRecipe.recipe_code}. Uncheck the others first.`);
      return;
    }
    _gmSelectedBatches.push(b);
  }else{
    _gmSelectedBatches = _gmSelectedBatches.filter(x=>x.id!==id);
    if(_gmSelectedBatches.length===0){
      _gmActiveRecipe = null;
      _gmActiveBatch = null;
    }else{
      _gmActiveBatch = _gmSelectedBatches[0];
    }
  }
  await gmApplySelectionToForm();
  gmRenderBatchList();
}

async function gmApplySelectionToForm(){
  const label = document.getElementById('gm-selected-batch-label');
  const banner = document.getElementById('gm-bom-banner');
  if(!_gmSelectedBatches.length){
    label.textContent = '— Tick one or more batches in the queue —';
    banner.className = 'alert d-none mb-3';
    document.getElementById('gm-bom-code').value = '';
    document.getElementById('gm-total-kg').value = '';
    document.getElementById('gm-bom-suggested').textContent = '';
    document.getElementById('gm-components-wrap').style.display = 'none';
    return;
  }
  // Aggregate selected batches
  const totalKg = _gmSelectedBatches.reduce((s,b)=>s+Number(_gmBatchGlueInfo[b.id]?.total_kg||0),0);
  const totalPcs = _gmSelectedBatches.reduce((s,b)=>s+Number(b.quantity||0),0);
  const list = _gmSelectedBatches.map(b=>`<span class="badge bg-warning text-dark me-1">${b.batch_number}</span>`).join('');
  label.innerHTML = `${list}<span class="text-muted ms-1">${_gmSelectedBatches.length} batch(es) · ${fmt(totalPcs)} pallets · ${fmt(totalKg)} kg target</span>`;

  await gmRefreshStation();
  document.getElementById('gm-bom-code').value = _gmActiveRecipe.recipe_code || '';
  document.getElementById('gm-recipe-sel').value = _gmActiveRecipe.id || '';
  document.getElementById('gm-mix-min').value = _gmActiveRecipe.mix_time_min || 20;
  document.getElementById('gm-total-kg').value = totalKg.toFixed(2);
  document.getElementById('gm-bom-suggested').innerHTML = `Suggested across ${_gmSelectedBatches.length} batch(es): <b>${fmt(totalKg)} kg</b>`;
  const cond=[_gmActiveRecipe.veneer_thickness,_gmActiveRecipe.wood_species,_gmActiveRecipe.core_board].filter(Boolean).join(' · ');
  banner.className = 'alert alert-success py-2 small mb-3';
  banner.innerHTML = `
    <div><i class="bi bi-check-circle me-1"></i><b>Recipe:</b> <code>${_gmActiveRecipe.recipe_code}</code> covering <b>${_gmSelectedBatches.length}</b> batch(es) totalling <b>${fmt(totalKg)} kg</b></div>
    ${cond?`<div class="small text-muted mt-1"><i class="bi bi-funnel me-1"></i>Used for: ${cond}</div>`:''}
    <div class="small text-muted">You can adjust any component amount below — defaults are scaled from the recipe.</div>`;
  document.getElementById('gm-components-wrap').style.display = '';
  gmCalcComponents();
}

// Component definitions for the mix workflow — uses new kg-based fields from PV Wood spreadsheet
const GM_COMPONENTS=[
  {key:'e0',     label:'E0 Glue',          field:'e0_glue_kg'},
  {key:'latex',  label:'Latex G312',       field:'latex_g312_kg'},
  {key:'flour',  label:'Flour',            field:'flour_kg'},
  {key:'yellow', label:'Yellow Pigment',   field:'yellow_pigment_kg'},
  {key:'hard',   label:'Hardener',         field:'hardener_kg'},
  {key:'red',    label:'Red Pigment',      field:'red_pigment_kg'},
  {key:'black',  label:'Black Pigment',    field:'black_pigment_kg'},
  {key:'ti',     label:'Titanium dioxide', field:'titanium_kg'},
];
let _gmStation=[]; // glue_mix station stock cache

async function gmRefreshStation(){
  // Glue mixing is per-line — read the station stock for the current line so it
  // matches where deposits land and where confirm-mix deducts.
  const line=_slgmLine();
  _gmStation=await api(`/api/station-stock?department=glue_mix${line?'&line_id='+encodeURIComponent(line):''}`).catch(()=>[]);
}

async function gmSelectBatch(id){
  _gmActiveBatch=_gmBatches.find(b=>b.id===id)||null;
  gmRenderBatchList();
  const label=document.getElementById('gm-selected-batch-label');
  const banner=document.getElementById('gm-bom-banner');
  if(!_gmActiveBatch){
    label.textContent='— Select a batch from the queue —';
    banner.className='alert d-none mb-3';
    return;
  }
  label.innerHTML=`<span class="badge bg-warning text-dark ms-1">${_gmActiveBatch.batch_number}</span>
    <span class="text-muted ms-1">${_gmActiveBatch.product_name||''} · ${fmt(_gmActiveBatch.quantity)} pcs</span>`;

  // Fetch BOM glue info
  banner.className='alert alert-info py-2 small mb-3';
  banner.innerHTML='<div class="spinner-border spinner-border-sm me-2"></div>Loading BOM glue info…';
  document.getElementById('gm-bom-code').value='';
  document.getElementById('gm-bom-suggested').textContent='';
  document.getElementById('gm-recipe-sel').value='';
  _gmActiveRecipe=null;
  document.getElementById('gm-components-wrap').style.display='none';

  await gmRefreshStation();
  const info=await api(`/api/batches/${id}/glue-info`).catch(e=>({error:e.message}));
  if(info.error){
    banner.className='alert alert-danger py-2 small mb-3';
    banner.innerHTML=`<i class="bi bi-exclamation-triangle me-1"></i><b>${info.error}</b>${info.product_sku?` (SKU ${info.product_sku})`:''}`;
    return;
  }
  // Fill BOM info
  document.getElementById('gm-bom-code').value=info.glue_code||'';
  document.getElementById('gm-bom-suggested').innerHTML=`Suggested: <b>${fmt(info.total_kg)} kg</b>`;
  document.getElementById('gm-total-kg').value=info.total_kg||'';
  // Find/match recipe
  const recipe=info.recipe||_gmRecipes.find(r=>r.recipe_code===info.glue_code);
  if(recipe){
    _gmActiveRecipe=recipe;
    document.getElementById('gm-recipe-sel').value=recipe.id;
    document.getElementById('gm-mix-min').value=recipe.mix_time_min||20;
    const cond=[recipe.veneer_thickness, recipe.wood_species, recipe.core_board].filter(Boolean).join(' · ');
    banner.className='alert alert-success py-2 small mb-3';
    banner.innerHTML=`
      <div><i class="bi bi-check-circle me-1"></i><b>BOM glue:</b> <code>${info.glue_code}</code> · matched recipe — suggested mix <b>${fmt(info.total_kg)} kg</b> for ${fmt(info.batch_quantity)} pallets × ${fmt(info.pallet_qty)} pcs/plt</div>
      ${cond?`<div class="small text-muted mt-1"><i class="bi bi-funnel me-1"></i>Used for: ${cond}</div>`:''}
      <div class="small text-muted">Recipe batch size: ${recipe.total_kg} kg — components scale proportionally to your target qty.</div>`;
    document.getElementById('gm-components-wrap').style.display='';
    gmCalcComponents();
  } else {
    banner.className='alert alert-warning py-2 small mb-3';
    banner.innerHTML=`<i class="bi bi-exclamation-triangle me-1"></i><b>BOM glue:</b> ${info.glue_code} (${info.glue_name||'—'}) · <b>no matching recipe found</b>. Create a glue recipe with code <code>${info.glue_code}</code> to enable auto-fill and stock deduction.`;
  }
}

// Material price cache (keyed by material_id) so the Glue Mixing form can
// roll up real ฿ cost as the operator adjusts kg per ingredient.
let _gmMatPriceById = {};
async function gmEnsureMatPrices(){
  if(Object.keys(_gmMatPriceById).length) return;
  try{
    const mats = await api('/api/materials');
    (mats||[]).forEach(m => { _gmMatPriceById[m.id] = Number(m.price || m.unit_cost || 0); });
  }catch{}
}

// Resolve the linked material_id for an ingredient slot from the recipe's
// material_links JSON (set in the Glue BOM Builder). Falls back to station-
// stock name match if no explicit link.
function _gmResolveMatId(recipe, c){
  try{
    const links = (typeof recipe.material_links === 'string')
                  ? JSON.parse(recipe.material_links || '{}')
                  : (recipe.material_links || {});
    // The Glue BOM Builder + backend store links by the field-derived key
    // (e0_glue_kg -> e0_glue). Earlier this resolver used the short c.key
    // (e0/latex/yellow...) which never matched, so explicit links were ignored.
    const fieldKey = (c.field || '').replace(/_kg$/, '');
    if(links[fieldKey]) return parseInt(links[fieldKey]);
    if(links[c.key])    return parseInt(links[c.key]);   // legacy short-key links
  }catch{}
  // Fallback: match station-stock entry by component label
  const lc = (c.label || '').toLowerCase();
  for(const s of _gmStation){
    const nm = (s.material_name||'').toLowerCase();
    if(nm === lc || (nm && (nm.includes(lc) || lc.includes(nm)))) return s.material_id;
  }
  return null;
}

function gmCalcComponents(){
  if(!_gmActiveRecipe){document.getElementById('gm-comp-tbody').innerHTML='';return;}
  const r = _gmActiveRecipe;
  const recipeBatchKg = parseFloat(r.total_kg)||0;
  const targetKg = parseFloat(document.getElementById('gm-total-kg').value)||0;
  const tbody = document.getElementById('gm-comp-tbody');
  if(!recipeBatchKg){
    tbody.innerHTML = '<tr><td colspan="7" class="text-center text-muted small py-2">Recipe has no total — edit it in Bill of Materials → Glue Formulas.</td></tr>';
    document.getElementById('gm-comp-total').textContent = '—';
    document.getElementById('gm-comp-avg-cost').textContent = '—';
    document.getElementById('gm-comp-total-cost').textContent = '—';
    return;
  }
  if(!targetKg){
    tbody.innerHTML = '<tr><td colspan="7" class="text-center text-muted small py-2">Enter target mix qty above to scale components.</td></tr>';
    document.getElementById('gm-comp-total').textContent = '—';
    document.getElementById('gm-comp-avg-cost').textContent = '—';
    document.getElementById('gm-comp-total-cost').textContent = '—';
    return;
  }
  gmEnsureMatPrices();   // background fetch; rows will repaint on next interaction
  const factor = targetKg / recipeBatchKg;
  let sumKg = 0, sumCost = 0;
  tbody.innerHTML = GM_COMPONENTS.filter(c => (parseFloat(r[c.field])||0) > 0).map(c => {
    const baseKg = parseFloat(r[c.field])||0;
    const qty = baseKg * factor;
    const matId = _gmResolveMatId(r, c);
    const stockRow = matId ? _gmStation.find(s => s.material_id === matId) : null;
    const price = matId ? (_gmMatPriceById[matId] || 0) : 0;
    const cost = qty * price;
    sumKg += qty; sumCost += cost;
    const matLabel = stockRow
      ? `${stockRow.material_name} <small class="text-muted">(stock ${fmt(stockRow.current_qty)} ${stockRow.unit||'kg'})</small>`
      : matId
        ? '<span class="text-muted small">linked to catalog</span>'
        : '<span class="text-warning"><i class="bi bi-exclamation-triangle"></i> no material linked</span>';
    const after = stockRow ? (stockRow.current_qty - qty) : null;
    const afterColor = after!=null ? (after<0?'text-danger fw-bold':after<5?'text-warning':'') : '';
    return `<tr>
      <td><b>${c.label}</b><br><small class="text-muted">${baseKg.toFixed(3)} kg / batch</small></td>
      <td class="small">${matLabel}</td>
      <td class="text-end">
        <input type="number" class="form-control form-control-sm text-end" id="gm-${c.key}-kg"
          value="${qty.toFixed(3)}" step="0.001" min="0" oninput="gmRecalcAfter()"
          data-mid="${matId||''}" data-price="${price}" data-name="${c.label}">
      </td>
      <td class="text-end small ${price>0?'text-muted':'text-danger'}">${price>0 ? '฿'+price.toFixed(2) : 'no price'}</td>
      <td class="text-end small ${cost>0?'fw-semibold':''}" id="gm-${c.key}-cost">${cost>0 ? '฿'+cost.toFixed(2) : '—'}</td>
      <td class="text-end small">${stockRow ? fmt(stockRow.current_qty)+' '+(stockRow.unit||'kg') : '—'}</td>
      <td class="text-end small ${afterColor}" id="gm-${c.key}-after">${after!=null ? fmt(after.toFixed(3)) : '—'}</td>
    </tr>`;
  }).join('');
  document.getElementById('gm-comp-total').textContent = `${sumKg.toFixed(3)} kg (×${factor.toFixed(2)} of recipe batch ${recipeBatchKg.toFixed(2)} kg)`;
  document.getElementById('gm-comp-avg-cost').textContent = sumKg>0 ? '฿'+(sumCost/sumKg).toFixed(2)+'/kg' : '—';
  document.getElementById('gm-comp-total-cost').textContent = sumCost>0 ? '฿'+sumCost.toFixed(2) : '—';
}

function gmRecalcAfter(){
  if(!_gmActiveRecipe) return;
  let sumKg = 0, sumCost = 0;
  for(const c of GM_COMPONENTS){
    const el = document.getElementById('gm-'+c.key+'-kg');
    if(!el) continue;
    const qty = parseFloat(el.value)||0;
    const price = parseFloat(el.dataset.price)||0;
    const cost = qty * price;
    sumKg += qty; sumCost += cost;
    const costCell = document.getElementById('gm-'+c.key+'-cost');
    if(costCell) costCell.textContent = cost>0 ? '฿'+cost.toFixed(2) : '—';
    const mid = parseInt(el.dataset.mid);
    const stockRow = mid ? _gmStation.find(s => s.material_id === mid) : null;
    const aft = document.getElementById('gm-'+c.key+'-after');
    if(aft && stockRow){
      const after = stockRow.current_qty - qty;
      aft.textContent = fmt(after.toFixed(3));
      aft.className = 'text-end small ' + (after<0?'text-danger fw-bold':after<5?'text-warning':'');
    }
  }
  document.getElementById('gm-comp-total').textContent = `${sumKg.toFixed(3)} kg`;
  document.getElementById('gm-comp-avg-cost').textContent = sumKg>0 ? '฿'+(sumCost/sumKg).toFixed(2)+'/kg' : '—';
  document.getElementById('gm-comp-total-cost').textContent = sumCost>0 ? '฿'+sumCost.toFixed(2) : '—';
}

function gmClearForm(){
  _gmActiveBatch=null; _gmActiveRecipe=null; _gmSelectedBatches=[];
  document.getElementById('gm-selected-batch-label').textContent='— Tick one or more batches in the queue —';
  document.getElementById('gm-bom-banner').className='alert d-none mb-3';
  document.getElementById('gm-bom-code').value='';
  document.getElementById('gm-bom-suggested').textContent='';
  document.getElementById('gm-recipe-sel').value='';
  document.getElementById('gm-total-kg').value='';
  document.getElementById('gm-mix-min').value='';
  document.getElementById('gm-operator').value='';
  document.getElementById('gm-notes').value='';
  document.getElementById('gm-components-wrap').style.display='none';
  document.getElementById('gm-comp-tbody').innerHTML='';
  document.getElementById('gm-submit-status').textContent='';
  gmRenderBatchList();
}

async function gmSubmitMix(){
  // Fall back to single-batch flow if nothing in the multi-batch selection
  if((!_gmSelectedBatches || !_gmSelectedBatches.length) && _gmActiveBatch){
    _gmSelectedBatches = [_gmActiveBatch];
  }
  if(!_gmSelectedBatches || !_gmSelectedBatches.length){
    toast('Tick at least one batch in the queue','warning');return;
  }
  if(!_gmActiveRecipe){toast('No recipe matched the BOM glue code — create one first','warning');return;}
  const totalKg=parseFloat(document.getElementById('gm-total-kg').value)||0;
  if(!totalKg){toast('Enter total mix quantity (kg)','warning');return;}
  // Collect components with mapped materials (data-mid attribute is set by gmCalcComponents from station stock match)
  const components=[];
  for(const c of GM_COMPONENTS){
    const el=document.getElementById('gm-'+c.key+'-kg');
    if(!el) continue;
    const qty=parseFloat(el.value)||0;
    if(qty<=0) continue;
    const mid=parseInt(el.dataset.mid)||null;
    components.push({
      name:c.label,
      material_id:mid,
      qty_kg:qty,
    });
  }
  // Warn about negative stock
  const stockMap={};
  for(const s of _gmStation) stockMap[s.material_id]=s.current_qty;
  const shortfalls=components.filter(c=>c.material_id && (stockMap[c.material_id]||0)-c.qty_kg<0);
  if(shortfalls.length){
    const msg=shortfalls.map(c=>`${c.name}: need ${c.qty_kg.toFixed(2)}kg, have ${(stockMap[c.material_id]||0).toFixed(2)}kg`).join('\n');
    if(!confirm(`Warning — station stock will go negative for:\n\n${msg}\n\nProceed anyway?`)) return;
  }
  // If multiple batches are selected, log the mix against the first batch but
  // record all batch numbers in the notes so traceability is preserved.
  const primary = _gmSelectedBatches[0];
  const allBNs = _gmSelectedBatches.map(b=>b.batch_number).join(', ');
  const mixNotes = (document.getElementById('gm-notes').value||'') +
    (_gmSelectedBatches.length>1 ? ` [Shared mix across batches: ${allBNs}]` : '');
  const body={
    batch_id: primary.batch_number,
    batch_numbers: _gmSelectedBatches.map(b=>b.batch_number),
    recipe_code: _gmActiveRecipe.recipe_code,
    line_id: _slgmLine(),
    qty_kg: totalKg,
    mix_time_min: parseInt(document.getElementById('gm-mix-min').value)||_gmActiveRecipe.mix_time_min||20,
    operator_name: document.getElementById('gm-operator').value.trim()||'—',
    notes: mixNotes,
    components,
  };
  try{
    const res=await api('/api/production/glue-mix-confirm','POST',body);
    const dedCount=res.deductions?.length||0;
    const skipCount=res.skipped?.length||0;
    toast(`Mix ${res.mix_id} confirmed · ${dedCount} components deducted from station stock${skipCount?` (${skipCount} skipped)`:''}`,'success');
    let html=`<span class="text-success"><i class="bi bi-check-circle me-1"></i>Mix <b>${res.mix_id}</b> · ${_gmActiveRecipe.recipe_code} · ${totalKg} kg → Batch ${_gmActiveBatch.batch_number}</span>`;
    if(dedCount){
      html+=`<div class="small text-muted mt-1">Deducted: ${res.deductions.map(d=>`${d.name} ${fmt(d.qty)}kg`).join(', ')}</div>`;
    }
    if(skipCount){
      html+=`<div class="small text-warning mt-1"><i class="bi bi-exclamation-triangle me-1"></i>Skipped (no material mapping): ${res.skipped.map(s=>s.name).join(', ')}</div>`;
    }
    document.getElementById('gm-submit-status').innerHTML=html;
    // Refresh station stock view
    await gmRefreshStation();
    gmCalcComponents();
  }catch(e){toast(e.message,'danger');}
}

// ── Glue Recipe CRUD ─────────────────────────────────────────
// (GM_COMPONENTS_NEW removed — it was an unused duplicate of GM_COMPONENTS above.)

function _gmFmtKg(v){return (v==null||v===0||v==='')?'—':Number(v).toFixed(2);}

function gmRenderRecipeTable(){
  const tbody=document.getElementById('gm-recipe-tbody');
  if(!_gmRecipes.length){tbody.innerHTML='<tr><td colspan="13" class="text-center text-muted py-2">No recipes yet</td></tr>';return;}
  // Replace header to match new columns
  const thead=tbody.parentElement?.querySelector('thead');
  if(thead) thead.innerHTML=`<tr>
    <th>Code</th><th>Conditions</th>
    <th class="text-end">E0</th><th class="text-end">Latex</th><th class="text-end">Flour</th>
    <th class="text-end">Yellow</th><th class="text-end">Hard</th><th class="text-end">Red</th>
    <th class="text-end">Black</th><th class="text-end">TiO₂</th>
    <th class="text-end">Total kg</th><th class="text-end">Mix min</th><th></th>
  </tr>`;
  tbody.innerHTML=_gmRecipes.map(r=>{
    const cond=[r.veneer_thickness, r.wood_species, r.core_board].filter(Boolean).join(' · ');
    return `<tr class="${r.is_active?'':'text-muted opacity-50'}">
      <td><code class="small">${r.recipe_code}</code></td>
      <td class="small text-muted" style="max-width:280px"><div class="text-truncate" title="${cond.replace(/"/g,'&quot;')}">${cond||'—'}</div></td>
      <td class="small text-end">${_gmFmtKg(r.e0_glue_kg)}</td>
      <td class="small text-end">${_gmFmtKg(r.latex_g312_kg)}</td>
      <td class="small text-end">${_gmFmtKg(r.flour_kg)}</td>
      <td class="small text-end">${_gmFmtKg(r.yellow_pigment_kg)}</td>
      <td class="small text-end">${_gmFmtKg(r.hardener_kg)}</td>
      <td class="small text-end">${_gmFmtKg(r.red_pigment_kg)}</td>
      <td class="small text-end">${_gmFmtKg(r.black_pigment_kg)}</td>
      <td class="small text-end">${_gmFmtKg(r.titanium_kg)}</td>
      <td class="small text-end fw-semibold">${_gmFmtKg(r.total_kg)}</td>
      <td class="small text-end">${r.mix_time_min||20}</td>
      <td><button class="btn btn-xs btn-outline-secondary py-0 px-1" onclick="gmOpenRecipe(${r.id})"><i class="bi bi-pencil"></i></button></td>
    </tr>`;
  }).join('');
}

function gmPreviewTotal(){
  // Sum all 8 kg fields → set Total. Also paint a % share badge on each row.
  const pairs = GM_INGREDIENT_KEYS.map(k => [k, parseFloat(document.getElementById(GM_KG_INPUT[k])?.value)||0]);
  const sum = pairs.reduce((s,[,v])=>s+v, 0);
  const totalEl = document.getElementById('gm-edit-total');
  if(totalEl) totalEl.value = sum.toFixed(3);
  pairs.forEach(([k, v]) => {
    const badge = document.getElementById('gm-pct-' + k);
    if(!badge) return;
    if(sum <= 0 || v <= 0){ badge.textContent = '—'; badge.style.background=''; return; }
    const pct = (v / sum) * 100;
    badge.textContent = pct < 0.05 ? '<0.1%' : pct.toFixed(pct < 10 ? 1 : 0) + '%';
  });
}

// All material catalog (loaded once per modal open). Includes glue_formula
// rows so users can link to existing Glue catalog entries.
let _gmMatCatalog = [];
const GM_INGREDIENT_KEYS = ['e0_glue','latex_g312','flour','yellow_pigment',
                            'hardener','red_pigment','black_pigment','titanium'];
const GM_KG_INPUT = {
  e0_glue:        'gm-edit-e0',
  latex_g312:     'gm-edit-latex',
  flour:          'gm-edit-flour',
  hardener:       'gm-edit-hardener',
  yellow_pigment: 'gm-edit-yellow',
  red_pigment:    'gm-edit-red',
  black_pigment:  'gm-edit-black',
  titanium:       'gm-edit-ti',
};
// Display label per material type (used as the [category] tag in picker options)
const _GM_CAT_LABEL = {
  'core_board':   'Boards',
  'veneer_sheet': 'Veneers',
  'adhesive':     'Consumable',
  'glue_formula': 'Glue and Additives',
  'packing':      'Packing',
  'other':        'Others',
};
// Sort weight per category — Glue and Additives + Consumable bubble up so
// they're at the top when picking a glue ingredient.
const _GM_CAT_WEIGHT = {
  'glue_formula': 0,   // "Glue and Additives" — urea resin, latex, flour, pigments
  'adhesive':     1,   // generic Consumable
  'other':        2,
  'packing':      3,
  'core_board':   4,
  'veneer_sheet': 4,
};

async function _gmEnsureCatalog(){
  if(_gmMatCatalog.length) return;
  try{
    // include_formulas=true so existing Glue catalog entries surface in the picker
    _gmMatCatalog = await api('/api/materials?include_formulas=true') || [];
    _gmMatCatalog.sort((a,b)=>{
      const wa = _GM_CAT_WEIGHT[a.type] ?? 9;
      const wb = _GM_CAT_WEIGHT[b.type] ?? 9;
      if(wa !== wb) return wa - wb;
      return ((a.code||'')+' '+(a.name||'')).localeCompare((b.code||'')+' '+(b.name||''));
    });
  }catch{ _gmMatCatalog = []; }
}

// Build an <option> tag for a material, with category prefix so search hits
// on terms like "glue" or "consumable" surface the right rows.
function _gmMatOption(m){
  const cat = _GM_CAT_LABEL[m.type] || (m.type || '—');
  const code = m.code ? '['+m.code+'] ' : '';
  const unit = m.unit ? ' ('+m.unit+')' : '';
  // data-search holds all searchable tokens lowercased + concatenated
  const tokens = [m.code, m.name, m.type, cat, m.supplier].filter(Boolean).join(' ').toLowerCase();
  return `<option value="${m.id}" data-search="${tokens.replace(/"/g,'&quot;')}" data-cat="${m.type||''}">[${cat}] ${code}${m.name}${unit}</option>`;
}

function _gmPopulatePickers(linksObj){
  const allOpts = ['<option value="">— not linked —</option>']
    .concat(_gmMatCatalog.map(_gmMatOption))
    .join('');
  GM_INGREDIENT_KEYS.forEach(k => {
    const sel = document.getElementById('gm-mat-' + k);
    if(!sel) return;
    sel.innerHTML = allOpts;
    sel.value = linksObj[k] ? String(linksObj[k]) : '';
    // Also reset any leftover search input + linked-label
    const s = document.querySelector('.gm-mat-search[data-ing="'+k+'"]');
    if(s) s.value = '';
    _gmShowSelectedMat(k);
  });
}

// Live-filter a single picker by a search term. Empty term = restore full list.
function _gmFilterPicker(ingKey, term){
  const sel = document.getElementById('gm-mat-' + ingKey);
  if(!sel) return;
  const currentVal = sel.value;
  const q = (term||'').trim().toLowerCase();
  const filtered = !q
    ? _gmMatCatalog
    : _gmMatCatalog.filter(m => {
        const cat = _GM_CAT_LABEL[m.type] || (m.type || '');
        const tokens = (m.code+' '+m.name+' '+m.type+' '+cat+' '+(m.supplier||'')).toLowerCase();
        return tokens.includes(q);
      });
  sel.innerHTML = ['<option value="">— not linked —</option>']
    .concat(filtered.map(_gmMatOption))
    .join('');
  // If the current selection survived the filter, keep it. Otherwise clear.
  if(currentVal && filtered.some(m=>String(m.id)===String(currentVal))){
    sel.value = currentVal;
  } else if(currentVal){
    // Selection is hidden by the filter — keep the value but stay quiet.
    // Append a phantom option so the value remains valid on save.
    const m = _gmMatCatalog.find(x=>String(x.id)===String(currentVal));
    if(m){ sel.insertAdjacentHTML('beforeend', _gmMatOption(m)); sel.value = currentVal; }
  }
}

// Show the currently-linked material's catalog category + code under the picker.
function _gmShowSelectedMat(ingKey){
  const sel = document.getElementById('gm-mat-' + ingKey);
  const lbl = document.getElementById('gm-linked-' + ingKey);
  if(!sel || !lbl) return;
  const mid = parseInt(sel.value)||0;
  if(!mid){ lbl.innerHTML = '<span class="text-muted">No material linked</span>'; return; }
  const m = _gmMatCatalog.find(x=>x.id===mid);
  if(!m){ lbl.innerHTML = `<span class="text-warning">Linked id ${mid} (not in catalog)</span>`; return; }
  const cat = _GM_CAT_LABEL[m.type] || (m.type || '—');
  const badgeColor = (matTypeBadge && matTypeBadge[m.type]) || 'bg-secondary';
  lbl.innerHTML = `<span class="badge ${badgeColor} me-1" style="font-size:.6rem">${cat}</span><span class="fw-semibold">${m.code||''}</span> <span class="text-muted">${m.name||''}</span>`;
}

async function gmOpenRecipe(idOrRecipe){
  await _gmEnsureCatalog();
  // Accept a recipe object (preferred — no lookup needed), an id, or nothing
  // (=> blank New Recipe form). When given an id, match string-safely and
  // refetch once on a cache miss so a stale/empty cache can't silently turn an
  // edit into a "New Recipe".
  let r = null;
  if(idOrRecipe && typeof idOrRecipe === 'object'){
    r = idOrRecipe;
  } else if(idOrRecipe != null && idOrRecipe !== ''){
    const wanted = String(idOrRecipe);
    r = (_gmRecipes||[]).find(x => String(x.id) === wanted);
    if(!r){
      try { _gmRecipes = await api('/api/glue-recipes?kind=glue') || []; } catch {}
      r = (_gmRecipes||[]).find(x => String(x.id) === wanted);
    }
    if(!r){
      toast(`Glue recipe #${wanted} not found — cannot edit`, 'danger');
      return;
    }
  }
  document.getElementById('gm-edit-id').value=r?.id||'';
  document.getElementById('gm-edit-code').value=r?.recipe_code||'';
  document.getElementById('gm-edit-name').value=r?.name||'';
  document.getElementById('gm-edit-time').value=r?.mix_time_min||20;
  document.getElementById('gm-edit-active').value=r?.is_active??1;
  document.getElementById('gm-edit-vthk').value=r?.veneer_thickness||'';
  document.getElementById('gm-edit-species').value=r?.wood_species||'';
  document.getElementById('gm-edit-core').value=r?.core_board||'';
  document.getElementById('gm-edit-e0').value=r?.e0_glue_kg||'';
  document.getElementById('gm-edit-latex').value=r?.latex_g312_kg||'';
  document.getElementById('gm-edit-flour').value=r?.flour_kg||'';
  document.getElementById('gm-edit-yellow').value=r?.yellow_pigment_kg||'';
  document.getElementById('gm-edit-hardener').value=r?.hardener_kg||'';
  document.getElementById('gm-edit-red').value=r?.red_pigment_kg||'';
  document.getElementById('gm-edit-black').value=r?.black_pigment_kg||'';
  document.getElementById('gm-edit-ti').value=r?.titanium_kg||'';
  document.getElementById('gm-edit-notes').value=r?.notes||'';
  document.getElementById('gm-recipe-modal-title').textContent=r?`Edit: ${r.recipe_code}`:'New Glue Recipe';
  document.getElementById('gm-edit-code').readOnly=!!r;
  // Parse material_links — server stores as JSON string
  let links = {};
  if(r?.material_links){
    try{ links = typeof r.material_links === 'string' ? JSON.parse(r.material_links) : r.material_links; }
    catch{ links = {}; }
  }
  _gmPopulatePickers(links || {});
  gmPreviewTotal();
  bootstrap.Modal.getOrCreateInstance(document.getElementById('gmRecipeModal')).show();
}

async function gmSaveRecipe(){
  const id=parseInt(document.getElementById('gm-edit-id').value)||0;
  const _v=k=>parseFloat(document.getElementById(k).value)||0;
  // Collect ingredient → catalog material_id picks (only non-empty)
  const material_links = {};
  ['e0_glue','latex_g312','flour','yellow_pigment','hardener',
   'red_pigment','black_pigment','titanium'].forEach(k=>{
    const v = parseInt(document.getElementById('gm-mat-'+k)?.value || 0);
    if(v) material_links[k] = v;
  });
  const body={
    id:id||undefined,
    recipe_code:document.getElementById('gm-edit-code').value.trim(),
    name:document.getElementById('gm-edit-name').value.trim(),
    veneer_thickness:document.getElementById('gm-edit-vthk').value.trim(),
    wood_species:document.getElementById('gm-edit-species').value.trim(),
    core_board:document.getElementById('gm-edit-core').value.trim(),
    e0_glue_kg:_v('gm-edit-e0'),
    latex_g312_kg:_v('gm-edit-latex'),
    flour_kg:_v('gm-edit-flour'),
    yellow_pigment_kg:_v('gm-edit-yellow'),
    hardener_kg:_v('gm-edit-hardener'),
    red_pigment_kg:_v('gm-edit-red'),
    black_pigment_kg:_v('gm-edit-black'),
    titanium_kg:_v('gm-edit-ti'),
    mix_time_min:parseInt(document.getElementById('gm-edit-time').value)||20,
    is_active:parseInt(document.getElementById('gm-edit-active').value),
    notes:document.getElementById('gm-edit-notes').value.trim(),
    material_links,
  };
  if(!body.recipe_code||!body.name){toast('Code and name required','warning');return;}
  try{
    if(id) await api(`/api/glue-recipes/${id}`,'PATCH',body);
    else    await api('/api/glue-recipes','POST',body);
    bootstrap.Modal.getInstance(document.getElementById('gmRecipeModal')).hide();
    toast('Recipe saved','success');
    gmLoad();
  }catch(e){toast(e.message,'danger');}
}



// ════════════════════════════════════════════════════════════
// WH Consumable Request (shared by stations)
// ════════════════════════════════════════════════════════════
// ══════════════════════════════════════════════════════════
// WH CONSUMABLE REQUEST (shared by all station logs)
// ══════════════════════════════════════════════════════════
// Multi-line request: type filter, N material lines, needed-by date+time
// (required), production line hard-set from the Station Hub line selector.
// Per-line departments must have a line selected; centralised departments
// (packing / fg_receiving / fg_warehouse) request line-less.
let _whrMats=[], _whrDept='', _whrLine='', _whrLineSeq=0;

const _WHR_CENTRALISED = new Set(['packing','fg_receiving','fg_warehouse']);
function _whrDeptIsCentralised(dept){
  const d = (typeof catalogDeptCode === 'function') ? catalogDeptCode(dept) : null;
  if(d && typeof d.is_centralised !== 'undefined') return !!d.is_centralised;
  return _WHR_CENTRALISED.has(dept);
}

function _whrMatOptions(){
  const t = document.getElementById('whr-type-filter')?.value || '';
  const mats = t ? _whrMats.filter(m => m.type === t) : _whrMats;
  return mats.map(m =>
    `<option value="${m.id}" data-unit="${m.unit||'pcs'}" data-stock="${m.current_stock||0}">`
    + `${m.name}${m.type?' ['+m.type+']':''} — WH: ${fmt(m.current_stock||0)} ${m.unit||'pcs'}</option>`
  ).join('');
}

async function openWHRequest(dept){
  _whrDept = dept || _slActiveBatch?.current_department || 'production';
  // Line is hard-set from the Station Hub line selector (read-only here).
  _whrLine = document.getElementById('sl-line')?.value
          || document.getElementById('st-line')?.value || '';
  const centralised = _whrDeptIsCentralised(_whrDept);

  document.getElementById('whr-dept-label').textContent = DEPT_LABEL[_whrDept] || _whrDept;
  document.getElementById('whr-line-label').textContent =
    centralised ? 'All lines (centralised)' : (_whrLine || '— none —');

  // Per-line dept with no line selected: warn + block submit.
  const warn = document.getElementById('whr-line-warning');
  const submitBtn = document.getElementById('whr-submit-btn');
  if(!centralised && !_whrLine){ warn.style.display=''; submitBtn.disabled=true; }
  else                         { warn.style.display='none'; submitBtn.disabled=false; }

  // Reset form
  document.getElementById('whr-type-filter').value = '';
  document.getElementById('whr-needed-date').value = '';
  document.getElementById('whr-needed-time').value = '';
  document.getElementById('whr-notes').value = _slActiveBatch ? `Batch: ${_slActiveBatch.batch_number||''}` : '';

  if(!_whrMats.length) _whrMats = await api('/api/consumable-materials').catch(()=>[]);

  // Start with one empty material line.
  _whrLineSeq = 0;
  document.getElementById('whr-lines').innerHTML = '';
  whrAddLine();

  bootstrap.Modal.getOrCreateInstance(document.getElementById('whRequestModal')).show();
}

function whrAddLine(){
  const idx = _whrLineSeq++;
  document.getElementById('whr-lines').insertAdjacentHTML('beforeend', `
  <div class="card mb-2 whr-line" data-idx="${idx}">
    <div class="card-body py-2">
      <div class="row g-2 align-items-end">
        <div class="col-md-6">
          <label class="form-label small mb-1">Material</label>
          <input type="text" class="form-control form-control-sm mb-1 whr-l-search" placeholder="Search…" oninput="whrLineSearch(${idx}, this.value)">
          <select class="form-select form-select-sm whr-l-mat" onchange="whrLineSel(${idx})">
            <option value="">— Select material —</option>${_whrMatOptions()}
          </select>
          <div class="small text-muted mt-1 whr-l-stock"></div>
        </div>
        <div class="col-md-4">
          <label class="form-label small mb-1">Quantity</label>
          <div class="input-group input-group-sm">
            <input type="number" class="form-control whr-l-qty" min="0.1" step="0.1" placeholder="0">
            <span class="input-group-text whr-l-unit">pcs</span>
          </div>
        </div>
        <div class="col-md-2 text-end">
          <button class="btn btn-sm btn-outline-danger" title="Remove" onclick="whrRemoveLine(${idx})"><i class="bi bi-x-lg"></i></button>
        </div>
      </div>
    </div>
  </div>`);
}

function whrRemoveLine(idx){
  if(document.querySelectorAll('.whr-line').length <= 1){ toast('At least one material required','warning'); return; }
  document.querySelector(`.whr-line[data-idx="${idx}"]`)?.remove();
}

function whrRerenderLines(){
  // Type filter changed — refresh each line's material options, keeping the
  // current pick if it survives the filter.
  document.querySelectorAll('.whr-line').forEach(line => {
    const sel = line.querySelector('.whr-l-mat');
    const prev = sel.value;
    sel.innerHTML = '<option value="">— Select material —</option>' + _whrMatOptions();
    if([...sel.options].some(o => o.value === prev)) sel.value = prev;
  });
}

function whrLineSearch(idx, q){
  const line = document.querySelector(`.whr-line[data-idx="${idx}"]`);
  if(!line) return;
  const term = (q||'').trim().toLowerCase();
  const t = document.getElementById('whr-type-filter')?.value || '';
  let mats = t ? _whrMats.filter(m => m.type === t) : _whrMats;
  if(term) mats = mats.filter(m => (m.name||'').toLowerCase().includes(term) || (m.type||'').toLowerCase().includes(term));
  line.querySelector('.whr-l-mat').innerHTML = '<option value="">— Select material —</option>' +
    mats.map(m=>`<option value="${m.id}" data-unit="${m.unit||'pcs'}" data-stock="${m.current_stock||0}">${m.name}${m.type?' ['+m.type+']':''} — WH: ${fmt(m.current_stock||0)} ${m.unit||'pcs'}</option>`).join('');
}

function whrLineSel(idx){
  const line = document.querySelector(`.whr-line[data-idx="${idx}"]`);
  if(!line) return;
  const opt = line.querySelector('.whr-l-mat').selectedOptions[0];
  if(opt && opt.value){
    line.querySelector('.whr-l-unit').textContent = opt.dataset.unit || 'pcs';
    line.querySelector('.whr-l-stock').textContent = `WH stock: ${fmt(parseFloat(opt.dataset.stock)||0)} ${opt.dataset.unit||'pcs'}`;
  } else {
    line.querySelector('.whr-l-stock').textContent = '';
  }
}

async function whrSubmit(){
  const centralised = _whrDeptIsCentralised(_whrDept);
  if(!centralised && !_whrLine){ toast('Select a production line in the Station Hub first','warning'); return; }
  const neededDate = document.getElementById('whr-needed-date').value;
  const neededTime = document.getElementById('whr-needed-time').value;
  if(!neededDate){ toast('Needed-by date is required','warning'); return; }
  if(!neededTime){ toast('Needed time is required','warning'); return; }
  const notes = document.getElementById('whr-notes').value.trim();

  // Collect material lines (skip fully-blank rows).
  const lines = [];
  let bad = '';
  document.querySelectorAll('.whr-line').forEach(el => {
    const matId = parseInt(el.querySelector('.whr-l-mat').value) || 0;
    const qty = parseFloat(el.querySelector('.whr-l-qty').value) || 0;
    if(!matId && !qty) return;
    if(!matId){ bad = 'Pick a material for every line'; return; }
    if(qty <= 0){ bad = 'Enter a positive quantity for every line'; return; }
    lines.push({ material_id: matId, qty_requested: qty });
  });
  if(bad){ toast(bad, 'warning'); return; }
  if(!lines.length){ toast('Add at least one material', 'warning'); return; }

  const btn = document.getElementById('whr-submit-btn');
  btn.disabled = true;
  let ok=0, fail=0, firstErr='';
  for(const ln of lines){
    try{
      await api('/api/consumable-requests','POST',{
        material_id: ln.material_id, qty_requested: ln.qty_requested,
        department: _whrDept, line_id: centralised ? '' : _whrLine,
        needed_by: neededDate, needed_time: neededTime, notes,
      });
      ok++;
    }catch(e){ fail++; if(!firstErr) firstErr = e.message||String(e); }
  }
  btn.disabled = false;
  if(fail===0){
    bootstrap.Modal.getInstance(document.getElementById('whRequestModal')).hide();
    toast(`${ok} request${ok===1?'':'s'} submitted to warehouse`,'success');
  } else {
    toast(`${ok} submitted, ${fail} failed (${firstErr})`, fail===lines.length?'danger':'warning');
  }
}

// ── My Open Requests (station-scoped) ────────────────────────
// Shows this station's (department + line) requests that aren't fully
// received. FULFILLED-but-unreceived rows get a 'Confirm Receipt' button
// that deposits the fulfilled qty into station stock.
async function stOpenMyRequests(){
  const dept = document.getElementById('sl-dept-scope')?.value
            || document.getElementById('st-dept')?.value || '';
  const line = document.getElementById('sl-line')?.value
            || document.getElementById('st-line')?.value || '';
  const centralised = _whrDeptIsCentralised(dept);
  document.getElementById('myreq-scope').innerHTML =
    `Department: <b>${DEPT_LABEL[dept]||dept||'—'}</b>` +
    (centralised ? ' <span class="badge bg-secondary">centralised</span>'
                 : ` · Line: <b>${line||'—'}</b>`);

  bootstrap.Modal.getOrCreateInstance(document.getElementById('myRequestsModal')).show();
  const tbody = document.getElementById('myreq-tbody');
  tbody.innerHTML = '<tr><td colspan="8" class="text-center text-muted py-3">Loading…</td></tr>';

  const params = ['open_only=true'];
  if(dept) params.push('department=' + encodeURIComponent(dept));
  if(!centralised && line) params.push('line_id=' + encodeURIComponent(line));
  let rows = await api('/api/consumable-requests?' + params.join('&')).catch(()=>[]);
  if(!Array.isArray(rows)) rows = [];

  if(!rows.length){
    tbody.innerHTML = '<tr><td colspan="8" class="text-center text-muted py-3">No open requests for this station.</td></tr>';
    return;
  }
  tbody.innerHTML = rows.map(r => {
    const fulfilled = Number(r.qty_fulfilled||0);
    const received  = Number(r.qty_received||0);
    const canReceive = fulfilled - received > 0.0001;
    const stCls = { PENDING:'bg-secondary', PARTIAL:'bg-info', FULFILLED:'bg-primary', CANCELLED:'bg-dark' }[r.status] || 'bg-secondary';
    const stLbl = canReceive ? 'READY TO RECEIVE' : r.status;
    const stColor = canReceive ? 'bg-success' : stCls;
    const need = (r.needed_by||'').slice(0,10) + (r.needed_time ? ' · '+r.needed_time : '');
    return `<tr>
      <td><code class="small">${r.request_id}</code><div class="small text-muted">${(r.created_at||'').slice(0,10)}</div></td>
      <td><b>${r.material_name||''}</b>${r.material_type?` <span class="badge bg-light text-dark border small">${r.material_type}</span>`:''}</td>
      <td class="text-end">${fmt(r.qty_requested)} ${r.unit||''}</td>
      <td class="text-end">${fmt(fulfilled)}</td>
      <td class="text-end">${fmt(received)}</td>
      <td class="small">${need||'—'}</td>
      <td><span class="badge ${stColor}" style="font-size:.62rem">${stLbl}</span></td>
      <td class="text-end">
        ${canReceive
          ? `<button class="btn btn-xs btn-success py-0 px-2" style="font-size:.72rem" onclick="whrReceive('${r.request_id}')"><i class="bi bi-box-arrow-in-down me-1"></i>Confirm Receipt</button>`
          : '<span class="text-muted small">awaiting WH</span>'}
      </td>
    </tr>`;
  }).join('');
}

async function whrReceive(requestId){
  try{
    await api(`/api/consumable-requests/${requestId}/receive`, 'PATCH');
    toast('Received into station stock','success');
    stOpenMyRequests();                       // refresh the list
    if(typeof stLoadStock === 'function') stLoadStock();   // refresh stock table
    if(typeof stLoadMovements === 'function') stLoadMovements();
  }catch(e){ toast(e.message||'Receive failed','danger'); }
}



// ════════════════════════════════════════════════════════════
// Station Presets (_presets + preset CRUD)
// ════════════════════════════════════════════════════════════
// ══════════════════════════════════════════════════════════
// STATION PRESETS — saved machine/table/operator combos
// ══════════════════════════════════════════════════════════
let _presets={};  // dept → array of presets (cache)
let _psContext=null; // {dept, fields, target} for save modal

// ── Schema: which form fields belong to each dept's preset ──
// fields = array of {key (preset key), id (DOM id template — use $r for row id)}
const PRESET_SCHEMA={
  laminating:{
    label:'Laminating Table',
    fields:[
      {key:'table_id',    id:'lam-tbl-$r',  label:'Table'},
      {key:'emp_code_1',  id:'lam-e1-$r',   label:'Operator 1'},
      {key:'emp_code_2',  id:'lam-e2-$r',   label:'Operator 2'},
      {key:'glue_mix_ref',id:'lam-mix-$r',  label:'Mix ref'},
    ],
    perRow:true,
  },
  cold_press:{
    label:'Cold Press',
    fields:[
      {key:'machine_id',     id:'sf-cp-machine', label:'Machine'},
      {key:'operator_name',  id:'sf-cp-op',      label:'Operator'},
      {key:'pressure_bar',   id:'sf-cp-bar',     label:'Pressure'},
      {key:'dwell_min',      id:'sf-cp-min',     label:'Dwell'},
    ],
  },
  repair:{
    label:'Repair',
    fields:[
      {key:'table_id',    id:'rep-tbl-$r',   label:'Table'},
      {key:'repair_type', id:'rep-type-$r',  label:'Type'},
      {key:'emp_code_1',  id:'rep-e1-$r',    label:'Operator 1'},
      {key:'emp_code_2',  id:'rep-e2-$r',    label:'Operator 2'},
    ],
    perRow:true,
  },
  sanding:{
    label:'Sanding',
    fields:[
      {key:'machine_id',    id:'sf-snd-machine', label:'Machine'},
      {key:'operator_name', id:'sf-snd-op',      label:'Operator'},
      {key:'grit_setting',  id:'sf-snd-grit',    label:'Grit'},
      {key:'feed_speed',    id:'sf-snd-feed',    label:'Feed'},
    ],
  },
  hot_press:{
    label:'Hot Press',
    fields:[
      {key:'machine_id',    id:'sf-hp-machine', label:'Machine'},
      {key:'operator_name', id:'sf-hp-op',      label:'Operator'},
      {key:'temp_c',        id:'sf-hp-temp',    label:'Temp °C'},
      {key:'pressure_bar',  id:'sf-hp-bar',     label:'Pressure'},
      {key:'press_time_min',id:'sf-hp-min',     label:'Time'},
    ],
  },
  grading:{
    label:'Grading',
    fields:[
      {key:'grader_name', id:'sf-grader', label:'Grader'},
    ],
  },
  packing:{
    label:'Packing',
    fields:[
      {key:'operator_name',id:'sf-pk-op',     label:'Operator'},
      {key:'table_id',     id:'sf-pk-table',  label:'Table'},
      {key:'packaging_sku',id:'sf-pk-sku',    label:'Packaging SKU'},
    ],
  },
  glue_mix:{
    label:'Glue Mix',
    fields:[
      {key:'recipe_code',   id:'sf-recipe',  label:'Recipe'},
      {key:'operator_name', id:'sf-op-name', label:'Operator'},
    ],
  },
};

function _resolveId(idTpl, rowId){ return rowId!=null?idTpl.replace('$r', rowId):idTpl; }

async function loadPresets(dept){
  if(!dept) return [];
  const data=await api('/api/station-presets?department='+dept).catch(()=>[]);
  _presets[dept]=data||[];
  return _presets[dept];
}

function presetBar(dept, rowId){
  /* Returns HTML for the preset selector + save button */
  if(!PRESET_SCHEMA[dept]) return '';
  const list=_presets[dept]||[];
  const opts=list.map(p=>`<option value="${p.id}">${p.name}${p.use_count>0?` (used ${p.use_count}×)`:''}</option>`).join('');
  const rowAttr=rowId!=null?` data-row="${rowId}"`:'';
  return `<div class="d-flex gap-1 align-items-center mb-2 p-2 bg-light rounded"${rowAttr}>
    <i class="bi bi-bookmark-fill text-primary"></i>
    <small class="text-muted me-1">Preset:</small>
    <select class="form-select form-select-sm" style="max-width:280px" onchange="applyPreset('${dept}',this.value,${rowId??'null'})">
      <option value="">— Pick a saved preset —</option>${opts}
    </select>
    <button type="button" class="btn btn-outline-primary btn-sm py-0 px-2" title="Save current values as preset"
      onclick="openPresetSave('${dept}',${rowId??'null'})"><i class="bi bi-bookmark-plus"></i></button>
    <button type="button" class="btn btn-outline-secondary btn-sm py-0 px-2" title="Manage presets"
      onclick="openPresetManage('${dept}')"><i class="bi bi-list"></i></button>
  </div>`;
}

async function applyPreset(dept, presetId, rowId){
  if(!presetId) return;
  const preset=(_presets[dept]||[]).find(p=>p.id==presetId);
  if(!preset) return;
  const data=preset.preset_data||{};
  const sch=PRESET_SCHEMA[dept];
  if(!sch) return;
  // Multi-row preset set (laminating / repair) — recreate all rows
  if(data && data._set && Array.isArray(data.rows)){
    await applyMultiRowPreset(dept, data.rows);
    toast(`Applied set "${preset.name}" (${data.rows.length} row${data.rows.length!==1?'s':''})`,'success');
    api(`/api/station-presets/${presetId}/touch`,'POST').catch(()=>{});
    preset.use_count=(preset.use_count||0)+1;
    return;
  }
  for(const f of sch.fields){
    const el=document.getElementById(_resolveId(f.id, rowId));
    if(el && data[f.key]!=null) el.value=data[f.key];
  }
  toast(`Applied preset "${preset.name}"`,'success');
  api(`/api/station-presets/${presetId}/touch`,'POST').catch(()=>{});
  preset.use_count=(preset.use_count||0)+1;
}

// ── Multi-row preset (laminating + repair) ────────────────────
function multiRowPresetBar(dept, bid){
  // Renders below the row list — Set picker + Save Set button
  return `<div class="d-flex gap-1 align-items-center mb-2 p-2 rounded" style="background:#dbeafe">
    <i class="bi bi-collection text-primary"></i>
    <small class="text-primary fw-semibold me-1">Full Set:</small>
    <select class="form-select form-select-sm" id="mrp-${dept}-pick" style="max-width:280px"
            onchange="applyMultiRowPresetFromDropdown('${dept}','${bid}',this.value)">
      <option value="">— Pick a saved set (all rows) —</option>
    </select>
    <button class="btn btn-sm btn-primary py-0 px-2" type="button"
            onclick="saveMultiRowPreset('${dept}','${bid}')"
            title="Save the current ${dept} rows as a named set">
      <i class="bi bi-collection-fill me-1"></i>Save Set
    </button>
  </div>`;
}

function _currentRowsFor(dept){
  // Returns the in-memory row list the form is rendering from
  if(dept==='laminating') return _lamRows;
  if(dept==='repair')     return _repRows;
  return [];
}

function _collectMultiRow(dept){
  const sch=PRESET_SCHEMA[dept];
  if(!sch) return [];
  const rows = _currentRowsFor(dept);
  const out = [];
  for(const r of rows){
    const data = {};
    for(const f of sch.fields){
      const el = document.getElementById(_resolveId(f.id, r.id));
      if(el) data[f.key] = el.value || '';
    }
    // Only include rows that have at least one filled field
    if(Object.values(data).some(v => v && String(v).trim().length)) out.push(data);
  }
  return out;
}

async function saveMultiRowPreset(dept, bid){
  const rows = _collectMultiRow(dept);
  if(!rows.length){ toast('Add at least one row with values first','warning'); return; }
  const name = prompt(`Name this ${dept} set:\n\nIncludes ${rows.length} row(s).`, '');
  if(!name) return;
  try{
    await api('/api/station-presets','POST',{
      name, department: dept,
      preset_data: { _set: true, rows },
    });
    toast(`Saved set "${name}" with ${rows.length} row(s)`,'success');
    await loadPresets(dept);
    _refreshMultiRowDropdown(dept);
  }catch(e){ toast(e.message,'danger'); }
}

function _refreshMultiRowDropdown(dept){
  const list = (_presets[dept]||[]).filter(p => p.preset_data?._set);
  const sel = document.getElementById(`mrp-${dept}-pick`);
  if(!sel) return;
  sel.innerHTML = '<option value="">— Pick a saved set (all rows) —</option>'+
    list.map(p => `<option value="${p.id}">${p.name} (${(p.preset_data?.rows||[]).length} rows${p.use_count?` · used ${p.use_count}×`:''})</option>`).join('');
}

async function applyMultiRowPresetFromDropdown(dept, bid, presetId){
  if(!presetId) return;
  // Use the same loader as the standard apply, which detects sets
  await applyPreset(dept, presetId, null);
  // Reset dropdown to placeholder
  const sel = document.getElementById(`mrp-${dept}-pick`);
  if(sel) sel.value = '';
}

async function applyMultiRowPreset(dept, rows){
  // Clear existing in-memory rows and recreate
  if(dept==='laminating'){
    _lamRows = [];
    document.getElementById('lam-rows-area').innerHTML = '';
    const bid = _slActiveBatch?.batch_number || '';
    for(const data of rows){
      addLamRow(bid);
      // The newly-added row is the last in _lamRows
      const rid = _lamRows[_lamRows.length-1].id;
      const sch = PRESET_SCHEMA.laminating;
      for(const f of sch.fields){
        const el = document.getElementById(_resolveId(f.id, rid));
        if(el && data[f.key]!=null) el.value = data[f.key];
      }
    }
  } else if(dept==='repair'){
    _repRows = [];
    document.getElementById('rep-rows-area').innerHTML = '';
    const bid = _slActiveBatch?.batch_number || '';
    for(const data of rows){
      addRepRow(bid);
      const rid = _repRows[_repRows.length-1].id;
      const sch = PRESET_SCHEMA.repair;
      for(const f of sch.fields){
        const el = document.getElementById(_resolveId(f.id, rid));
        if(el && data[f.key]!=null) el.value = data[f.key];
      }
    }
  }
}

function _collectPresetData(dept, rowId){
  const sch=PRESET_SCHEMA[dept];
  if(!sch) return {};
  const data={};
  for(const f of sch.fields){
    const el=document.getElementById(_resolveId(f.id, rowId));
    if(el) data[f.key]=el.value||'';
  }
  return data;
}

function openPresetSave(dept, rowId){
  _psContext={dept, rowId};
  const data=_collectPresetData(dept, rowId);
  document.getElementById('ps-dept-label').textContent=PRESET_SCHEMA[dept]?.label||dept;
  document.getElementById('ps-name').value='';
  // Preview values
  const sch=PRESET_SCHEMA[dept];
  const items=sch.fields.filter(f=>data[f.key]).map(f=>`<b>${f.label}:</b> ${data[f.key]}`).join('  ·  ');
  document.getElementById('ps-preview').innerHTML=items||'<span class="text-warning">All form fields are empty — fill them in before saving.</span>';
  bootstrap.Modal.getOrCreateInstance(document.getElementById('presetSaveModal')).show();
}

async function psSave(){
  const name=document.getElementById('ps-name').value.trim();
  if(!name||!_psContext){toast('Enter a preset name','warning');return;}
  const {dept, rowId}=_psContext;
  const data=_collectPresetData(dept, rowId);
  try{
    await api('/api/station-presets','POST',{
      name, department:dept, preset_data:data
    });
    bootstrap.Modal.getInstance(document.getElementById('presetSaveModal')).hide();
    toast('Preset saved','success');
    await loadPresets(dept);
    // Refresh the dropdowns currently visible for this dept
    refreshPresetDropdowns(dept);
  }catch(e){toast(e.message,'danger');}
}

function refreshPresetDropdowns(dept){
  // Update all preset dropdowns currently in DOM for this dept
  const list=_presets[dept]||[];
  const opts='<option value="">— Pick a saved preset —</option>'+
    list.map(p=>`<option value="${p.id}">${p.name}${p.use_count>0?` (used ${p.use_count}×)`:''}</option>`).join('');
  document.querySelectorAll(`select[onchange^="applyPreset('${dept}'"]`).forEach(s=>s.innerHTML=opts);
}

async function openPresetManage(dept){
  await loadPresets(dept);
  const list=_presets[dept]||[];
  const sch=PRESET_SCHEMA[dept];
  document.getElementById('pm-dept-label').textContent=sch?.label||dept;
  const tbody=document.getElementById('pm-tbody');
  if(!list.length){
    tbody.innerHTML='<tr><td colspan="5" class="text-center text-muted py-3">No presets yet for this station.</td></tr>';
  } else {
    tbody.innerHTML=list.map(p=>{
      const d=p.preset_data||{};
      const valStr=sch.fields.filter(f=>d[f.key]).map(f=>`${f.label}: ${d[f.key]}`).join(' · ');
      return `<tr>
        <td><b>${p.name}</b></td>
        <td class="small text-muted">${valStr||'—'}</td>
        <td class="text-end">${p.use_count||0}</td>
        <td class="small text-muted">${(p.last_used_at||'').slice(0,16).replace('T',' ')||'—'}</td>
        <td class="text-end"><button class="btn btn-xs btn-outline-danger py-0 px-1" onclick="pmDelete(${p.id},'${dept}')"><i class="bi bi-trash"></i></button></td>
      </tr>`;
    }).join('');
  }
  bootstrap.Modal.getOrCreateInstance(document.getElementById('presetManageModal')).show();
}

async function pmDelete(pid, dept){
  if(!confirm('Delete this preset?')) return;
  try{
    await api(`/api/station-presets/${pid}`,'DELETE');
    toast('Deleted','success');
    await loadPresets(dept);
    openPresetManage(dept);
    refreshPresetDropdowns(dept);
  }catch(e){toast(e.message,'danger');}
}



// ════════════════════════════════════════════════════════════
// Station Tools — HR Attendance + Station Stock
// ════════════════════════════════════════════════════════════
// ══════════════════════════════════════════════════════════
// STATION TOOLS — HR Attendance + Station Stock
// ══════════════════════════════════════════════════════════
let _stTab='team', _stAtt=[], _stStock=[], _stMvmts=[], _stDeptEmps=[], _stStockMats=[];

async function stLoad(){
  // Default date = today
  const today=new Date().toISOString().slice(0,10);
  const monthAgo=new Date(Date.now()-30*86400000).toISOString().slice(0,10);
  if(!document.getElementById('st-date').value) document.getElementById('st-date').value=today;
  if(!document.getElementById('st-mvmt-from').value) document.getElementById('st-mvmt-from').value=monthAgo;
  if(!document.getElementById('st-mvmt-to').value) document.getElementById('st-mvmt-to').value=today;
  if(!document.getElementById('st-sum-from').value) document.getElementById('st-sum-from').value=monthAgo;
  if(!document.getElementById('st-sum-to').value) document.getElementById('st-sum-to').value=today;
  if(!_allEmployees.length) _allEmployees=await api('/api/employees').catch(()=>[]);
  await stOnDeptChange();
}

function stCurrentDept(){ return document.getElementById('st-dept').value; }
function stCurrentLine(){ return document.getElementById('st-line').value; }

// Helper: case-insensitive dept compare (employee table uses UPPERCASE)
function _empMatchesDept(emp, dept){
  if(!emp.department) return true;
  if(!dept) return true;
  return (emp.department||'').toLowerCase()===dept.toLowerCase();
}

async function stOnDeptChange(){
  // Filter employees to current dept (case-insensitive — employees stored uppercase)
  const dept=stCurrentDept();
  _stDeptEmps=(_allEmployees||[]).filter(e=>_empMatchesDept(e, dept));
  // Refresh active tab
  stSwitchTab(_stTab);
}

function stSwitchTab(tab){
  _stTab=tab;
  document.querySelectorAll('#st-tabs .nav-link').forEach(b=>b.classList.toggle('active', b.dataset.stTab===tab));
  document.querySelectorAll('.st-pane').forEach(p=>p.classList.add('d-none'));
  document.getElementById('st-pane-'+tab).classList.remove('d-none');
  if(tab==='team') stLoadAttendance();
  else if(tab==='stock') stLoadStock();
  else if(tab==='movements') stLoadMovements();
  else if(tab==='summary') stLoadSummary();
}

// ── Attendance ────────────────────────────────────────────────
async function stLoadAttendance(){
  const dept=stCurrentDept();
  const date=document.getElementById('st-date').value;
  const shift=document.getElementById('st-shift-filter').value;
  let rows=await api(`/api/hr/attendance?department=${dept}&work_date=${date}`).catch(()=>[]);
  if(shift) rows=rows.filter(r=>r.shift===shift);
  _stAtt=rows;
  stRenderAttendance();
}

function stRenderAttendance(){
  const tbody=document.getElementById('st-att-tbody');
  if(!_stAtt.length){
    tbody.innerHTML='<tr><td colspan="10" class="text-center text-muted py-3">No attendance entries for this date. Click "Add Entry" to log one.</td></tr>';
    document.getElementById('st-att-total-reg').textContent='—';
    document.getElementById('st-att-total-ot').textContent='—';
    document.getElementById('st-att-total-people').textContent='';
    return;
  }
  const STATUS_COLOR={PRESENT:'success',LATE:'warning text-dark',ABSENT:'danger',LEAVE:'secondary',SICK:'info text-dark',HOLIDAY:'dark'};
  tbody.innerHTML=_stAtt.map(r=>`<tr>
    <td><b>${r.emp_name||r.emp_id}</b><br><small class="text-muted">${r.emp_id}</small></td>
    <td class="small">${r.position||'—'}</td>
    <td><span class="badge bg-light text-dark border">${r.shift}</span></td>
    <td class="small">${r.time_in||'—'}</td>
    <td class="small">${r.time_out||'—'}</td>
    <td class="text-end">${(r.regular_hours||0).toFixed(2)}</td>
    <td class="text-end ${(r.ot_hours||0)>0?'text-warning fw-semibold':''}">${(r.ot_hours||0).toFixed(2)}</td>
    <td><span class="badge bg-${STATUS_COLOR[r.status]||'secondary'}">${r.status}</span></td>
    <td class="small text-muted text-truncate" style="max-width:200px" title="${(r.notes||'').replace(/"/g,'&quot;')}">${r.notes||''}</td>
    <td>
      <button class="btn btn-xs btn-outline-secondary py-0 px-1" onclick="stOpenAttendance(${r.id})" title="Edit"><i class="bi bi-pencil"></i></button>
      <button class="btn btn-xs btn-outline-danger py-0 px-1" onclick="stDeleteAttendance(${r.id})" title="Delete"><i class="bi bi-trash"></i></button>
    </td>
  </tr>`).join('');
  const totalReg=_stAtt.reduce((s,r)=>s+(r.regular_hours||0),0);
  const totalOt=_stAtt.reduce((s,r)=>s+(r.ot_hours||0),0);
  document.getElementById('st-att-total-reg').textContent=totalReg.toFixed(2);
  document.getElementById('st-att-total-ot').textContent=totalOt.toFixed(2);
  const present=_stAtt.filter(r=>r.status==='PRESENT'||r.status==='LATE').length;
  document.getElementById('st-att-total-people').textContent=`${present} present / ${_stAtt.length} entries`;
}

function stPopulateEmpDropdown(selId){
  const sel=document.getElementById(selId);
  sel.innerHTML='<option value="">— Select employee —</option>'+
    _stDeptEmps.map(e=>`<option value="${e.emp_id}">${e.emp_name} (${e.emp_id})${e.position?' · '+e.position:''}</option>`).join('');
}

function stOpenAddAttendance(){ stOpenAttendance(); }

function stOpenAttendance(aid){
  const r=aid?_stAtt.find(x=>x.id===aid):null;
  document.getElementById('st-att-id').value=r?.id||'';
  document.getElementById('st-att-modal-title').textContent=r?'Edit Attendance':'Log Attendance';
  stPopulateEmpDropdown('st-att-emp');
  document.getElementById('st-att-emp').value=r?.emp_id||'';
  document.getElementById('st-att-date').value=r?.work_date||document.getElementById('st-date').value;
  document.getElementById('st-att-shift').value=r?.shift||'MORNING';
  document.getElementById('st-att-in').value=r?.time_in||'';
  document.getElementById('st-att-out').value=r?.time_out||'';
  document.getElementById('st-att-reg').value=r?.regular_hours||'';
  document.getElementById('st-att-ot').value=r?.ot_hours||0;
  document.getElementById('st-att-status').value=r?.status||'PRESENT';
  document.getElementById('st-att-notes').value=r?.notes||'';
  document.getElementById('st-att-hr-info').textContent='';
  bootstrap.Modal.getOrCreateInstance(document.getElementById('stAttModal')).show();
}

function stAttCalcHours(){
  const tIn=document.getElementById('st-att-in').value;
  const tOut=document.getElementById('st-att-out').value;
  if(tIn&&tOut){
    const [h1,m1]=tIn.split(':').map(Number);
    const [h2,m2]=tOut.split(':').map(Number);
    let mins=(h2*60+m2)-(h1*60+m1);
    if(mins<0) mins+=24*60;
    const total=mins/60;
    const ot=parseFloat(document.getElementById('st-att-ot').value)||0;
    const reg=Math.max(0,total-ot);
    document.getElementById('st-att-reg').value=reg.toFixed(2);
    document.getElementById('st-att-hr-info').textContent=`Total: ${total.toFixed(2)} hrs (Reg ${reg.toFixed(2)} + OT ${ot.toFixed(2)})`;
  }
}

async function stSaveAttendance(){
  const aid=parseInt(document.getElementById('st-att-id').value)||0;
  const empId=document.getElementById('st-att-emp').value;
  if(!empId){toast('Select an employee','warning');return;}
  const body={
    work_date:document.getElementById('st-att-date').value,
    emp_id:empId, department:stCurrentDept(),
    shift:document.getElementById('st-att-shift').value,
    time_in:document.getElementById('st-att-in').value||'',
    time_out:document.getElementById('st-att-out').value||'',
    regular_hours:parseFloat(document.getElementById('st-att-reg').value)||0,
    ot_hours:parseFloat(document.getElementById('st-att-ot').value)||0,
    status:document.getElementById('st-att-status').value,
    notes:document.getElementById('st-att-notes').value||'',
  };
  try{
    if(aid) await api(`/api/hr/attendance/${aid}`,'PATCH',body);
    else    await api('/api/hr/attendance','POST',body);
    bootstrap.Modal.getInstance(document.getElementById('stAttModal')).hide();
    toast('Attendance saved','success'); stLoadAttendance();
  }catch(e){toast(e.message,'danger');}
}

async function stDeleteAttendance(aid){
  if(!confirm('Delete this attendance entry?')) return;
  try{await api(`/api/hr/attendance/${aid}`,'DELETE');toast('Deleted');stLoadAttendance();}
  catch(e){toast(e.message,'danger');}
}

async function stBulkCheckIn(){
  // Quick check-in for all dept employees who don't have an entry today
  const date=document.getElementById('st-date').value;
  const shift=document.getElementById('st-shift-filter').value||'MORNING';
  const existing=new Set(_stAtt.filter(r=>r.shift===shift).map(r=>r.emp_id));
  const toAdd=_stDeptEmps.filter(e=>!existing.has(e.emp_id));
  if(!toAdd.length){toast('All employees already logged for this shift','info');return;}
  if(!confirm(`Check-in ${toAdd.length} employee(s) for ${shift} shift on ${date}?`)) return;
  const now=new Date();
  const timeIn=`${String(now.getHours()).padStart(2,'0')}:${String(now.getMinutes()).padStart(2,'0')}`;
  let ok=0;
  for(const e of toAdd){
    try{
      await api('/api/hr/attendance','POST',{
        work_date:date,emp_id:e.emp_id,department:stCurrentDept(),shift,
        time_in:timeIn,status:'PRESENT'
      });
      ok++;
    }catch(err){}
  }
  toast(`${ok}/${toAdd.length} employees checked in`,'success');
  stLoadAttendance();
}

// ── Stock ────────────────────────────────────────────────────
async function stLoadStock(){
  const dept=stCurrentDept();
  const line=stCurrentLine();
  _stStock=await api(`/api/station-stock?department=${dept}${line?'&line_id='+line:''}`).catch(()=>[]);
  stRenderStock();
}

function stRenderStock(){
  const tbody=document.getElementById('st-stock-tbody');
  if(!_stStock.length){
    tbody.innerHTML='<tr><td colspan="7" class="text-center text-muted py-3">No stock recorded yet. Click "Receive" to add materials.</td></tr>';
    return;
  }
  tbody.innerHTML=_stStock.map(s=>{
    const low=(s.min_qty||0)>0&&s.current_qty<=s.min_qty;
    return `<tr class="${low?'table-warning':''}">
      <td><b>${s.material_name}</b>${s.material_code?` <small class="text-muted">${s.material_code}</small>`:''}</td>
      <td><span class="badge bg-light text-dark border small">${s.material_type||''}</span></td>
      <td class="text-end fw-semibold">${fmt(s.current_qty)} ${s.unit||''}</td>
      <td class="text-end small">
        <input type="number" class="form-control form-control-sm text-end" value="${s.min_qty||0}" step="0.01" min="0"
          style="display:inline-block;width:80px" onchange="stSaveMin(${s.id},this.value)">
      </td>
      <td class="text-end small text-muted">${fmt(s.wh_stock||0)}</td>
      <td class="small text-muted">${(s.last_updated||'').slice(0,16).replace('T',' ')}</td>
      <td>${low?'<span class="badge bg-danger" title="Below min">LOW</span>':''}</td>
    </tr>`;
  }).join('');
}

async function stSaveMin(sid,val){
  try{await api(`/api/station-stock/${sid}/min`,'PATCH',{min_qty:parseFloat(val)||0});}
  catch(e){toast(e.message,'danger');}
}

let _stMvmtLineSeq = 0;
let _stMvmtType = 'RECEIVE';

// Issue/Use + Adjust operate ONLY on what the station currently holds, so the
// material picker is built from _stStock (current station stock), never the
// full consumable catalog. You can't issue or recount something you don't have.
function _stStockMatOptions(filter){
  const term = (filter||'').trim().toLowerCase();
  let rows = (_stStock || []);
  if(term) rows = rows.filter(s =>
    (s.material_name||'').toLowerCase().includes(term) ||
    (s.material_type||'').toLowerCase().includes(term));
  return rows.map(s =>
    `<option value="${s.material_id}" data-unit="${s.unit||'pcs'}" data-onhand="${s.current_qty||0}">`
    + `${s.material_name}${s.material_type?' ['+s.material_type+']':''} — on hand: ${fmt(s.current_qty||0)} ${s.unit||''}</option>`
  ).join('');
}

function _stMvmtLineTpl(idx){
  const opts = _stStockMatOptions();
  return `
  <div class="card mb-2 st-mvmt-line" data-idx="${idx}">
    <div class="card-body py-2">
      <div class="d-flex align-items-center mb-2">
        <span class="badge bg-secondary me-2">Line ${idx+1}</span>
        <div class="flex-grow-1 small text-muted">Pick a material + quantity.</div>
        <button class="btn btn-xs btn-outline-danger" title="Remove this line" onclick="stMvmtRemoveLine(${idx})">
          <i class="bi bi-x-lg"></i>
        </button>
      </div>
      <div class="row g-2">
        <div class="col-md-5">
          <label class="form-label small fw-semibold mb-1">Material *</label>
          <input type="text" class="form-control form-control-sm mb-1 st-l-search" placeholder="Search…" oninput="_stMvmtLineSearch(${idx}, this.value)">
          <select class="form-select form-select-sm st-l-mat" onchange="_stMvmtLineMatChange(${idx})">
            <option value="">— Select material —</option>${opts}
          </select>
          <div class="small text-muted mt-1 st-l-stock-info"></div>
        </div>
        <div class="col-md-3">
          <label class="form-label small fw-semibold mb-1 st-l-qty-label">${_stMvmtType==='ADJUST' ? 'New Total Qty *' : 'Quantity *'}</label>
          <div class="input-group input-group-sm">
            <input type="number" class="form-control st-l-qty" min="0" step="0.01">
            <span class="input-group-text st-l-unit">pcs</span>
          </div>
        </div>
        <div class="col-md-4">
          <label class="form-label small fw-semibold mb-1">Batch Ref (optional)</label>
          <input class="form-control form-control-sm st-l-batch" placeholder="BTH-...">
        </div>
      </div>
    </div>
  </div>`;
}

function stMvmtAddLine(){
  const idx = _stMvmtLineSeq++;
  document.getElementById('st-mvmt-lines').insertAdjacentHTML('beforeend', _stMvmtLineTpl(idx));
}
function stMvmtRemoveLine(idx){
  if(document.querySelectorAll('.st-mvmt-line').length <= 1){
    alert('At least one line required.'); return;
  }
  document.querySelector(`.st-mvmt-line[data-idx="${idx}"]`)?.remove();
}

function _stMvmtLineSearch(idx, q){
  const line = document.querySelector(`.st-mvmt-line[data-idx="${idx}"]`);
  if(!line) return;
  const sel = line.querySelector('.st-l-mat');
  const cur = sel.value;
  sel.innerHTML = '<option value="">— Select material —</option>' + _stStockMatOptions(q);
  if(cur) sel.value = cur;
}

function _stMvmtLineMatChange(idx){
  const line = document.querySelector(`.st-mvmt-line[data-idx="${idx}"]`);
  if(!line) return;
  const sel = line.querySelector('.st-l-mat');
  const opt = sel.options[sel.selectedIndex];
  if(opt && opt.value){
    line.querySelector('.st-l-unit').textContent = opt.dataset.unit || 'pcs';
    const matId = parseInt(opt.value);
    const s = (_stStock || []).find(x => x.material_id === matId);
    line.querySelector('.st-l-stock-info').textContent =
      s ? `Current station stock: ${fmt(s.current_qty)} ${s.unit||''}` : 'No current station stock for this material.';
  }
}

async function stOpenStockMove(type){
  _stMvmtType = type;
  document.getElementById('st-mvmt-type').value = type;
  const titles = {ISSUE:'Issue / Use Stock', ADJUST:'Adjust Stock Count'};
  const helps = {
    ISSUE:'<i class="bi bi-arrow-up-circle me-1 text-warning"></i>Record consumables used or transferred out — only materials currently held at this station are selectable.',
    ADJUST:'<i class="bi bi-pencil-square me-1 text-secondary"></i>Set the absolute current quantity after a physical count — only materials currently held at this station.',
  };
  document.getElementById('st-mvmt-modal-title').textContent = titles[type] || 'Stock Movement';
  document.getElementById('st-mvmt-help').innerHTML = helps[type] || '';
  document.getElementById('st-mvmt-help').className =
    'alert alert-' + (type==='ISSUE'?'warning':'secondary') + ' py-2 small mb-3';

  // Date/time = when it actually happened. Label contextually, default to now.
  document.getElementById('st-mvmt-date-label').textContent = type==='ADJUST' ? 'Count date' : 'Issued date';
  document.getElementById('st-mvmt-time-label').textContent = type==='ADJUST' ? 'Count time' : 'Issued time';
  const now = new Date();
  document.getElementById('st-mvmt-date').value = now.toISOString().slice(0,10);
  document.getElementById('st-mvmt-time').value = now.toTimeString().slice(0,5);   // HH:MM local
  document.getElementById('st-mvmt-notes').value = '';

  // Picker is built from current station stock — make sure it's loaded.
  if(!(_stStock && _stStock.length) && typeof stLoadStock === 'function'){
    try { await stLoadStock(); } catch {}
  }
  if(!(_stStock && _stStock.length)){
    toast('No stock at this station yet — receive consumables first (View my open requests).', 'warning');
    return;
  }
  _stMvmtLineSeq = 0;
  document.getElementById('st-mvmt-lines').innerHTML = '';
  stMvmtAddLine();
  bootstrap.Modal.getOrCreateInstance(document.getElementById('stStockMoveModal')).show();
}

async function stSubmitMovement(){
  const type = document.getElementById('st-mvmt-type').value;
  const mvDate = document.getElementById('st-mvmt-date').value || '';
  const mvTime = document.getElementById('st-mvmt-time').value || '';
  const sharedNotes = document.getElementById('st-mvmt-notes').value.trim();
  if(!mvDate){ toast(type==='ADJUST'?'Count date is required':'Issued date is required','warning'); return; }
  // occurred_at = the operator-stated date/time this happened.
  const occurredAt = mvDate + (mvTime ? (' ' + mvTime) : ' 00:00');

  const lines = [];
  let bad = '';
  document.querySelectorAll('.st-mvmt-line').forEach(el => {
    const sel = el.querySelector('.st-l-mat');
    const matId = parseInt(sel.value) || 0;
    const qty = parseFloat(el.querySelector('.st-l-qty').value) || 0;
    const onHand = parseFloat(sel.options[sel.selectedIndex]?.dataset.onhand) || 0;
    if(!matId || qty < 0){ bad = 'Each line needs a material and a non-negative qty.'; return; }
    if(type !== 'ADJUST' && qty <= 0){ bad = 'Quantity must be greater than zero.'; return; }
    // You can only issue what the station holds.
    if(type === 'ISSUE' && qty > onHand){
      bad = `Cannot issue ${qty} — only ${onHand} on hand for ${sel.options[sel.selectedIndex]?.text.split(' — ')[0]}.`;
      return;
    }
    lines.push({
      material_id: matId,
      qty_change:  qty,
      batch_ref:   el.querySelector('.st-l-batch').value.trim() || '',
    });
  });
  if(bad){ toast(bad, 'warning'); return; }
  if(!lines.length){ toast('Add at least one material line.', 'warning'); return; }

  // Fire one movement per line (backend has no bulk endpoint; sequential keeps
  // the per-row validation/error behaviour intact).
  let ok = 0, fail = 0, firstErr = '';
  for(const ln of lines){
    try{
      await api('/api/station-stock/movement', 'POST', {
        department: stCurrentDept(), line_id: stCurrentLine(),
        material_id: ln.material_id, qty_change: ln.qty_change,
        movement_type: type,
        batch_ref: ln.batch_ref,
        notes: sharedNotes,
        occurred_at: occurredAt,
      });
      ok++;
    } catch(e){ fail++; if(!firstErr) firstErr = e.message || String(e); }
  }
  if(fail === 0){
    bootstrap.Modal.getInstance(document.getElementById('stStockMoveModal')).hide();
    toast(`${type}: ${ok} material${ok===1?'':'s'} logged`, 'success');
  } else {
    toast(`${ok} logged, ${fail} failed (${firstErr})`, fail===lines.length?'danger':'warning');
  }
  stLoadStock();
  if(typeof stLoadMovements === 'function') stLoadMovements();
}

// ── Movements history ────────────────────────────────────────
async function stLoadMovements(){
  const dept=stCurrentDept();
  const line=stCurrentLine();
  const from=document.getElementById('st-mvmt-from').value;
  const to=document.getElementById('st-mvmt-to').value;
  const params=[`department=${dept}`];
  if(line) params.push('line_id='+line);
  if(from) params.push('from_date='+from);
  if(to) params.push('to_date='+to);
  _stMvmts=await api(`/api/station-stock/movements?${params.join('&')}`).catch(()=>[]);
  const tbody=document.getElementById('st-mvmt-tbody');
  if(!_stMvmts.length){tbody.innerHTML='<tr><td colspan="7" class="text-center text-muted py-3">No movements in this period.</td></tr>';return;}
  const COLOR={RECEIVE:'success',ISSUE:'warning text-dark',ADJUST:'secondary',BATCH_USE:'info text-dark'};
  // Show occurred_at (when it actually happened) — fall back to created_at for
  // rows logged before that column existed.
  tbody.innerHTML=_stMvmts.map(m=>`<tr>
    <td class="small text-muted">${((m.occurred_at||m.created_at)||'').replace('T',' ').slice(0,16)}</td>
    <td class="small"><b>${m.material_name}</b>${m.material_code?` <span class="text-muted">${m.material_code}</span>`:''}</td>
    <td><span class="badge bg-${COLOR[m.movement_type]||'secondary'}">${m.movement_type}</span></td>
    <td class="text-end ${m.qty_change>0?'text-success':'text-danger'}">${m.qty_change>0?'+':''}${fmt(m.qty_change)} ${m.unit||''}</td>
    <td class="small text-muted">${m.batch_ref||''}</td>
    <td class="small">${m.notes||''}</td>
    <td class="small text-muted">${m.created_by||'—'}</td>
  </tr>`).join('');
}

// ── HR Summary ──────────────────────────────────────────────
async function stLoadSummary(){
  const dept=stCurrentDept();
  const from=document.getElementById('st-sum-from').value;
  const to=document.getElementById('st-sum-to').value;
  if(!from||!to) return;
  const rows=await api(`/api/hr/attendance/summary?from_date=${from}&to_date=${to}&department=${dept}`).catch(()=>[]);
  const tbody=document.getElementById('st-sum-tbody');
  if(!rows.length){tbody.innerHTML='<tr><td colspan="8" class="text-center text-muted py-3">No data for this period.</td></tr>';return;}
  tbody.innerHTML=rows.map(r=>{
    const total=(r.total_regular||0)+(r.total_ot||0);
    return `<tr>
      <td><b>${r.emp_name||r.emp_id}</b><br><small class="text-muted">${r.emp_id}</small></td>
      <td class="small">${r.position||'—'}</td>
      <td class="text-end">${r.days_worked||0}</td>
      <td class="text-end">${(r.total_regular||0).toFixed(2)}</td>
      <td class="text-end ${(r.total_ot||0)>0?'text-warning fw-semibold':''}">${(r.total_ot||0).toFixed(2)}</td>
      <td class="text-end fw-semibold">${total.toFixed(2)}</td>
      <td class="text-end ${(r.absent_count||0)>0?'text-danger':''}">${r.absent_count||0}</td>
      <td class="text-end ${(r.late_count||0)>0?'text-warning':''}">${r.late_count||0}</td>
    </tr>`;
  }).join('');
  window._stSummaryRows=rows;
}

function stExportHRM(){
  const rows=window._stSummaryRows||[];
  if(!rows.length){toast('No data to export','warning');return;}
  const dept=stCurrentDept();
  const from=document.getElementById('st-sum-from').value;
  const to=document.getElementById('st-sum-to').value;
  const headers=['Employee ID','Employee Name','Position','Department','Days Worked','Regular Hours','OT Hours','Total Hours','Absent Days','Late Days','Period From','Period To'];
  const csvLines=[headers.join(',')];
  for(const r of rows){
    const total=(r.total_regular||0)+(r.total_ot||0);
    csvLines.push([
      r.emp_id, `"${(r.emp_name||'').replace(/"/g,'""')}"`, `"${(r.position||'').replace(/"/g,'""')}"`,
      r.department, r.days_worked||0, (r.total_regular||0).toFixed(2),
      (r.total_ot||0).toFixed(2), total.toFixed(2),
      r.absent_count||0, r.late_count||0, from, to
    ].join(','));
  }
  const blob=new Blob([csvLines.join('\n')],{type:'text/csv'});
  const url=URL.createObjectURL(blob);
  const a=document.createElement('a');
  a.href=url; a.download=`HRM_${dept}_${from}_${to}.csv`;
  document.body.appendChild(a); a.click(); document.body.removeChild(a);
  URL.revokeObjectURL(url);
  toast('CSV exported','success');
}

async function runBatchDiagnosis(bid){
  const el=document.getElementById('sl-ai-result');
  el.innerHTML='<div class="spinner-border spinner-border-sm me-2"></div>Analyzing...';
  try{
    const r=await api('/api/production/ai/analyze','POST',{mode:'BATCH_DIAGNOSIS',batch_id:bid});
    el.innerHTML=`<div class="alert alert-warning small"><b>AI Diagnosis</b><br>${(r.analysis||'').replace(/\n/g,'<br>')}</div>`+
      (r.flags?.length?'<div class="d-flex flex-wrap gap-2">'+r.flags.map(f=>`
        <div class="badge bg-${f.severity==='HIGH'?'danger':f.severity==='MEDIUM'?'warning text-dark':'secondary'} p-2 text-wrap" style="max-width:220px;font-size:.75rem">
          <div class="fw-bold">${f.station}${f.operator_id?' · '+f.operator_id:''}</div>
          ${f.message}
        </div>`).join('')+'</div>':'');
  }catch(e){el.innerHTML=`<div class="alert alert-danger small">${e.message}</div>`;}
}

// New-batch modal (createNewBatch / openNewBatchModal) was removed in v2.21.76:
// it created legacy prod_batch rows via the retired /api/prod-batches endpoint
// and was never wired to a button. Batches come from production orders.




// ════════════════════════════════════════════════════════════
// Forklift Report (managerial reports & AI)
// ════════════════════════════════════════════════════════════
// ══════════════════════════════════════════════════════════════
// FORKLIFT REPORT (Reports & AI)
// ══════════════════════════════════════════════════════════════
async function frptLoad(){
  // Default date range to last 30 days if blank
  const fEl=document.getElementById('frpt-from'), tEl=document.getElementById('frpt-to');
  if(!fEl.value){
    const d=new Date(); d.setDate(d.getDate()-30); fEl.value=d.toISOString().slice(0,10);
    tEl.value=new Date().toISOString().slice(0,10);
  }
  try{
    const [flk, reqs] = await Promise.all([api('/api/forklifts'), api('/api/forklifts/oil-requests')]);
    const inRange = (reqs||[]).filter(r => {
      const t=(r.requested_at||'').slice(0,10);
      return t >= fEl.value && t <= tEl.value;
    });
    // KPIs
    const totalL = inRange.filter(r=>r.status==='FULFILLED').reduce((s,r)=>s+Number(r.fulfilled_qty||r.qty_litres||0),0);
    const urgentCnt = inRange.filter(r=>r.priority==='URGENT').length;
    const cards = [
      {l:'Forklifts',          v:(flk||[]).length,         bg:'primary', ico:'bi-truck-flatbed'},
      {l:'Oil Requests',       v:inRange.length,            bg:'info',    ico:'bi-list-ul'},
      {l:'Litres Dispensed',   v:totalL.toFixed(1)+' L',   bg:'success', ico:'bi-droplet-half'},
      {l:'Urgent Requests',    v:urgentCnt,                 bg:'danger',  ico:'bi-exclamation-triangle'},
    ];
    document.getElementById('frpt-kpi').innerHTML = cards.map(c=>`
      <div class="col-md-3 col-6"><div class="card border-${c.bg}"><div class="card-body py-2 px-3">
        <div class="small text-muted"><i class="bi ${c.ico} me-1"></i>${c.l}</div>
        <div class="fs-5 fw-semibold">${c.v}</div></div></div></div>`).join('');
    // Aggregate per forklift
    const agg = {};
    inRange.forEach(r => {
      const k = r.forklift_id;
      if(!agg[k]) agg[k] = {code:r.forklift_code, dept:r.forklift_dept||'', litres:0, count:0};
      if(r.status==='FULFILLED') agg[k].litres += Number(r.fulfilled_qty||r.qty_litres||0);
      agg[k].count++;
    });
    document.getElementById('frpt-by-flk').innerHTML = Object.values(agg)
      .sort((a,b)=>b.litres-a.litres)
      .map(a=>`<tr>
        <td class="small fw-semibold">${a.code}</td>
        <td class="small">${a.dept}</td>
        <td class="text-end">${a.litres.toFixed(1)} L</td>
        <td class="text-end">${a.count}</td>
      </tr>`).join('') || '<tr><td colspan="4" class="text-muted text-center py-3">No data in range</td></tr>';
    document.getElementById('frpt-recent').innerHTML = inRange.slice(0,40).map(r=>`<tr>
      <td class="small">${(r.requested_at||'').slice(0,16).replace('T',' ')}</td>
      <td class="small fw-semibold">${r.forklift_code}</td>
      <td class="small">${r.oil_type}</td>
      <td class="text-end">${Number(r.qty_litres).toFixed(1)}</td>
      <td>${r.priority==='URGENT'?'<span class="badge bg-danger">URG</span>':'<span class="badge bg-light text-dark">N</span>'}</td>
      <td><span class="badge bg-${({PENDING:'warning text-dark',FULFILLED:'success',CANCELLED:'dark'})[r.status]||'secondary'}">${r.status}</span></td>
    </tr>`).join('');
  }catch(e){
    document.getElementById('frpt-by-flk').innerHTML=`<tr><td colspan="4" class="text-danger small p-3">${e.message||e}</td></tr>`;
  }
}


// Refuel Window Settings moved to /static/js/portal_warehouse.js

// Scrap / LG Bin moved to /static/js/portal_warehouse.js

// Hook-ups: oil-drum picker + settings button moved to /static/js/portal_warehouse.js


// Smart post-report flow (SL_DEPT_OPTIONS + slPostReportPrompt) moved to /static/js/portal_planning.js


// ════════════════════════════════════════════════════════════
// Production Logs
// ════════════════════════════════════════════════════════════
// ══════════════════════════════════════════════════════════
// PRODUCTION LOGS
// ══════════════════════════════════════════════════════════
async function loadLogs(){
  try{
    const rows=await api('/api/production-logs?limit=200').catch(()=>[]);
    const tbody=document.querySelector('#logs-table tbody');
    if(!tbody) return;
    if(!rows.length){tbody.innerHTML='<tr><td colspan="7" class="text-center text-muted py-4">No production logs yet.</td></tr>';return;}
    tbody.innerHTML=rows.map(l=>{
      const eff=l.planned_qty?Math.round((l.actual_qty/l.planned_qty)*100):null;
      return `<tr>
        <td>${fmtD(l.log_date||l.created_at)}</td>
        <td>${l.machine_name||l.machine_id||'—'}</td>
        <td>${l.product_name||l.product_id||'—'}</td>
        <td>${fmt(l.planned_qty)}</td>
        <td>${fmt(l.actual_qty)}</td>
        <td>${eff!=null?`<span class="badge ${eff>=90?'bg-success':eff>=70?'bg-warning text-dark':'bg-danger'}">${eff}%</span>`:'—'}</td>
        <td>${l.shift||'—'}</td>
      </tr>`;
    }).join('');
  }catch(e){const tb=document.querySelector('#logs-table tbody');if(tb)tb.innerHTML=`<tr><td colspan="7" class="text-danger text-center py-3">${e.message}</td></tr>`;}
}



// ════════════════════════════════════════════════════════════
// Order Intake + PDF PO Upload
// ════════════════════════════════════════════════════════════
// ══════════════════════════════════════════════════════════
// ORDER INTAKE + PDF PO UPLOAD
// ══════════════════════════════════════════════════════════
async function loadOrderIntake(){
  await preload();
  await loadPoList();
  // Auto-select first PO if none selected
  if(!selectedPoId){
    const pos=await api('/api/purchase-orders').catch(()=>[]);
    if(pos.length) selectPo(pos[0].id);
  }
}

async function loadPoList(){
  const pos=await api('/api/purchase-orders').catch(()=>[]);
  const el=document.getElementById('po-list');
  if(!pos.length){el.innerHTML='<p class="text-muted small">No purchase orders yet.</p>';return;}
  el.innerHTML=pos.map(p=>`
    <div class="border rounded p-2 mb-2 ${selectedPoId===p.id?'border-primary bg-light':''}" style="cursor:pointer" onclick="selectPo(${p.id})">
      <div class="d-flex justify-content-between align-items-start">
        <span class="fw-bold small">${p.po_number}</span>
        <div class="d-flex gap-1">
          ${prioBadge(p.priority||2)}
          <button class="btn btn-xs btn-outline-secondary py-0 px-1" style="font-size:.7rem" onclick="event.stopPropagation();editPoModal(${p.id})" title="Edit PO"><i class="bi bi-pencil"></i></button>
          <button class="btn btn-xs btn-outline-danger py-0 px-1" style="font-size:.7rem" onclick="event.stopPropagation();deletePo(${p.id})" title="Delete PO"><i class="bi bi-trash"></i></button>
        </div>
      </div>
      <small class="text-muted">${p.customer||''} &mdash; ${fmtD(p.delivery_date)}</small>
      <div class="mt-1">${statusBadge(p.status||'open')}</div>
    </div>`).join('');
}

async function selectPo(id){
  selectedPoId=id;
  document.getElementById('btn-add-line').disabled=false;
  document.getElementById('btn-create-po').disabled=false;
  await loadPoList();
  const lines=await api(`/api/purchase-orders/${id}/lines`).catch(()=>[]);
  document.getElementById('po-lines-label').textContent='PO #'+id;
  const el=document.getElementById('po-lines-list');

  // Stash for bulk release; fetch material readiness so we can colour & gate each line
  _poLines = lines.slice();
  let readinessBySku = {};
  let readinessLoaded = false;
  try{
    const mr = await api(`/api/purchase-orders/${id}/material-readiness`).catch(()=>null);
    if(mr && Array.isArray(mr.materials)){
      // For each line's SKU, accumulate the worst material status used by that SKU
      const skuStatus = {};
      mr.materials.forEach(m => {
        (m.used_by||[]).forEach(sku => {
          const cur = skuStatus[sku];
          const rank = {short:3, low:2, ok:1};
          if(!cur || rank[m.status] > rank[cur]) skuStatus[sku] = m.status;
        });
      });
      readinessBySku = skuStatus;
      readinessLoaded = true;
    }
  }catch{}
  // Also note which lines already have a non-draft production order (so we don't re-release)
  const existingPords = await api(`/api/production-orders?po_id=${id}`).catch(()=>[]);
  const lineHasPord = {};
  (existingPords||[]).forEach(p => { if(p.po_line_id) lineHasPord[p.po_line_id]=p.status; });

  if(!lines.length){
    el.innerHTML='<p class="text-muted small">No lines yet.</p>';
  } else {
    // Header bar: select-all + "Release Selected to Production" action
    const header = `
      <div class="d-flex justify-content-between align-items-center mb-2 p-2"
           style="background:#f0fdf4;border:1px solid #bbf7d0;border-radius:6px">
        <div class="d-flex align-items-center gap-2 small">
          <i class="bi bi-info-circle text-success"></i>
          <strong>Bulk-release to production:</strong>
          Tick the lines whose materials are ready, then click Release Selected.
          Lines flagged <span class="badge bg-danger">SHORT</span> are disabled until raw materials are received.
        </div>
        <div class="d-flex gap-2 align-items-center">
          <span class="small text-muted" id="po-release-count">0 selected</span>
          <button class="btn btn-sm btn-success" id="po-release-btn" disabled
                  onclick="releaseSelectedPoLines(${id})">
            <i class="bi bi-play-circle me-1"></i>Release Selected to Production
          </button>
        </div>
      </div>`;
    el.innerHTML = header + `<table class="table table-sm mb-0">
      <thead class="table-light"><tr>
        <th style="width:36px"><input type="checkbox" id="po-line-cb-all" onchange="togglePoLineAll(this.checked)"></th>
        <th>FG Code</th><th>Name</th><th>Line</th>
        <th class="text-center">Pallets</th><th class="text-center">Pcs/Pallet</th>
        <th class="text-center">Total Pcs</th>
        <th class="text-end">Price/pcs <span class="badge bg-primary-subtle text-primary border border-primary" style="font-size:.6rem">USD</span></th>
        <th class="text-end">Line Total <span class="badge bg-primary-subtle text-primary border border-primary" style="font-size:.6rem">USD</span></th>
        <th>Material Readiness</th>
        <th></th></tr></thead>
      <tbody>${lines.map(l=>{
        const ppp=l.pcs_per_pallet||null;
        const totalPcs=ppp?l.quantity*ppp:null;
        const lineTotal = (Number(l.unit_price)||0) * (Number(totalPcs)||0);
        const status = readinessBySku[l.sku] || (readinessLoaded ? 'ok' : 'unknown');
        const already = lineHasPord[l.id];
        const canRelease = (status==='ok' || status==='low') && !already;
        const cb = `<input type="checkbox" class="po-line-cb" data-line-id="${l.id}"
                    ${canRelease?'':'disabled'} onchange="onPoLineCheck()">`;
        let readinessCell;
        if(already){
          readinessCell = `<span class="badge bg-secondary">Already in production (${already})</span>`;
        }else if(!readinessLoaded){
          readinessCell = '<span class="text-muted small">—</span>';
        }else if(status==='short'){
          readinessCell = '<span class="badge bg-danger"><i class="bi bi-exclamation-triangle me-1"></i>SHORT</span>';
        }else if(status==='low'){
          readinessCell = '<span class="badge bg-warning text-dark"><i class="bi bi-exclamation-circle me-1"></i>LOW (covered)</span>';
        }else{
          readinessCell = '<span class="badge bg-success"><i class="bi bi-check2-circle me-1"></i>READY</span>';
        }
        return `<tr class="${already?'table-secondary':(status==='short'?'table-danger':'')}" data-line-id="${l.id}">
          <td>${cb}</td>
          <td><code class="text-primary">${l.sku||l.product_id}</code></td>
          <td>${l.product_name||''}${l.notes?`<br><small class="text-muted">${l.notes}</small>`:''}
              ${l.packing_sku_code?` <span class="badge bg-success-subtle text-success border border-success" style="font-size:.7rem"><i class="bi bi-box me-1"></i>${l.packing_sku_code}</span>`:''}
          </td>
          <td>${lineBadge(l.production_line)}</td>
          <td class="text-center fw-bold">${fmt(l.quantity)}</td>
          <td class="text-center">${ppp?`<span class="badge bg-secondary">${ppp}</span>`:'<span class="text-muted">—</span>'}</td>
          <td class="text-center">${totalPcs?`<strong>${totalPcs.toLocaleString()}</strong>`:'<span class="text-muted">—</span>'}</td>
          <td class="text-end">${l.unit_price?`<span class="text-primary fw-semibold">$${Number(l.unit_price).toLocaleString(undefined,{maximumFractionDigits:4})}</span> <span class="text-muted small">USD</span>`:'<span class="text-muted">—</span>'}</td>
          <td class="text-end">${lineTotal>0?`<span class="text-primary fw-bold">$${lineTotal.toLocaleString(undefined,{minimumFractionDigits:2,maximumFractionDigits:2})}</span>`:'<span class="text-muted">—</span>'}</td>
          <td>${readinessCell}</td>
          <td class="text-end" style="white-space:nowrap">
            <button class="btn btn-xs btn-outline-secondary py-0 px-1 me-1" onclick="editPoLine(${l.id},${l.product_id},'${(l.sku||'').replace(/'/g,"\\'")}','${(l.product_name||'').replace(/'/g,"\\'")}','${l.production_line||'P01'}',${l.quantity},${l.unit_price||0},'${(l.notes||'').replace(/'/g,"\\'")}',${l.packing_sku_id||null},${ppp||null})"><i class="bi bi-pencil"></i></button>
            <button class="btn btn-xs btn-outline-danger py-0 px-1" onclick="deletePoLine(${l.id})"><i class="bi bi-trash"></i></button>
          </td>
        </tr>`;
      }).join('')}</tbody></table>`;
  }
  const pords=await api(`/api/production-orders?po_id=${id}`).catch(()=>[]);
  const pe=document.getElementById('prod-orders-list');
  if(!pords.length){
    pe.innerHTML='<p class="text-muted small">No production orders yet.</p>';
  } else {
    pe.innerHTML=pords.map(o=>`
      <div class="d-flex justify-content-between align-items-center border-bottom py-2">
        <div><small class="fw-bold">${o.prod_order_number||o.order_number||'#'+o.id}</small><small class="text-muted ms-1">${lineBadge(o.production_line)}</small></div>
        <div class="d-flex gap-1 align-items-center">
          ${statusBadge(o.status)}
          ${o.status==='draft'?`<button class="btn btn-success btn-sm" onclick="releasePO(${o.id})" style="padding:1px 8px;font-size:.7rem">Release</button>`:''}
          <button class="btn btn-xs btn-outline-danger py-0 px-1" onclick="deleteProdOrder(${o.id})" title="Delete production order"><i class="bi bi-trash"></i></button>
        </div>
      </div>`).join('');
  }
  loadMaterialReadiness(id);
}

// ── Material Readiness ──────────────────────────────────────
async function loadMaterialReadiness(poId){
  const card=document.getElementById('po-material-readiness-card');
  const panel=document.getElementById('po-material-readiness');
  const badge=document.getElementById('mr-summary-badge');
  if(!card||!panel) return;
  card.style.display='block';
  panel.innerHTML='<div class="text-muted small py-2"><span class="spinner-border spinner-border-sm me-2"></span>Checking material readiness…</div>';
  badge.innerHTML='';
  let data;
  try{
    data=await api(`/api/purchase-orders/${poId}/material-readiness`);
  }catch(e){
    panel.innerHTML=`<div class="alert alert-secondary py-2 mb-0"><i class="bi bi-info-circle me-1"></i>${e.message||'Could not load material readiness.'}</div>`;
    return;
  }

  // Summary badge
  const nShort=(data.materials||[]).filter(m=>m.status==='short').length;
  const nLow=(data.materials||[]).filter(m=>m.status==='low').length;
  const nMissBom=(data.missing_bom_skus||[]).length;
  if(data.all_ok && !nMissBom){
    badge.innerHTML='<span class="badge bg-success"><i class="bi bi-check-circle me-1"></i>All materials ready</span>';
  } else if(nShort>0){
    badge.innerHTML=`<span class="badge bg-danger"><i class="bi bi-exclamation-triangle me-1"></i>${nShort} material${nShort>1?'s':''} short</span>`;
    if(nLow>0) badge.innerHTML+=` <span class="badge bg-warning text-dark ms-1">${nLow} low</span>`;
  } else if(nLow>0){
    badge.innerHTML=`<span class="badge bg-warning text-dark"><i class="bi bi-exclamation-circle me-1"></i>${nLow} material${nLow>1?'s':''} low</span>`;
  } else {
    badge.innerHTML='<span class="badge bg-success"><i class="bi bi-check-circle me-1"></i>Materials OK</span>';
  }

  let html='';

  // Missing BOM warnings
  if(nMissBom>0){
    html+=`<div class="alert alert-warning py-2 mb-2">
      <strong><i class="bi bi-exclamation-triangle me-1"></i>${nMissBom} SKU${nMissBom>1?'s':''} missing BOM — cannot check materials:</strong>
      <ul class="mb-0 mt-1">
        ${(data.missing_bom_skus||[]).map(s=>`<li><code>${s}</code>
          <a href="#" onclick="event.preventDefault();openBomBuilderWithSku('${s}')" class="ms-1 text-warning fw-bold" style="font-size:.78rem">→ Set up BOM</a>
        </li>`).join('')}
      </ul>
    </div>`;
  }

  // All ok — no shortfalls, no missing BOMs
  if(data.all_ok && !nMissBom && (data.materials||[]).length>0){
    html+=`<div class="alert alert-success py-2 mb-2">
      <i class="bi bi-check-circle-fill me-1"></i>
      All <strong>${data.materials.length}</strong> material${data.materials.length>1?'s':''} sufficiently stocked for this PO.
    </div>`;
  }

  // Lines checked / missing BOM note
  if(data.lines_checked!==undefined){
    const checked=data.lines_checked-(data.lines_missing_bom||0);
    html+=`<div class="text-muted mb-2" style="font-size:.72rem">
      <i class="bi bi-bar-chart-steps me-1"></i>
      Checked <strong>${checked}</strong> of <strong>${data.lines_checked}</strong> line${data.lines_checked!==1?'s':''} (${data.lines_missing_bom||0} missing BOM).
      ${data.total_shortfall_cost>0?`Total shortfall cost impact: <strong class="text-danger">฿${data.total_shortfall_cost.toLocaleString('th-TH',{minimumFractionDigits:2,maximumFractionDigits:2})}</strong>`:''}
    </div>`;
  }

  // Materials table (only if we have materials to show)
  const mats=data.materials||[];
  if(mats.length>0){
    const rowBg={short:'#fef2f2',low:'#fffbeb',ok:'#f0fdf4'};
    const statusHtml={
      short:'<span class="status-pill insufficient">Short</span>',
      low:'<span class="status-pill low">Low</span>',
      ok:'<span class="status-pill ok">OK</span>'
    };
    html+=`<div style="max-height:260px;overflow-y:auto;border-radius:6px;border:1px solid #e2e8f0;">
      <table class="table table-sm mb-0" style="font-size:.76rem">
        <thead class="table-light" style="position:sticky;top:0;z-index:1">
          <tr>
            <th>Material</th><th class="text-end">Required</th><th class="text-end">In Stock</th>
            <th class="text-end">Shortfall</th><th class="text-end">Cost Impact</th><th>Used by SKU</th>
          </tr>
        </thead>
        <tbody>
          ${mats.map(m=>{
            const sf=m.shortfall>0?`<span class="text-danger fw-bold">-${fmt(m.shortfall)}</span>`:`<span class="text-success">—</span>`;
            const cost=m.shortfall_cost>0?`<span class="text-danger">฿${m.shortfall_cost.toLocaleString('th-TH',{minimumFractionDigits:2,maximumFractionDigits:2})}</span>`:'—';
            const skus=(m.used_by||[]).map(s=>`<code style="font-size:.68rem">${s}</code>`).join(' ');
            return `<tr style="background:${rowBg[m.status]||''}">
              <td><span class="fw-semibold">${m.material_name||m.material_id}</span><span class="text-muted ms-1" style="font-size:.68rem">${m.unit||''}</span></td>
              <td class="text-end">${fmt(m.required)}</td>
              <td class="text-end">${fmt(m.stock)}</td>
              <td class="text-end">${sf}</td>
              <td class="text-end">${cost}</td>
              <td>${statusHtml[m.status]||''} ${skus}</td>
            </tr>`;
          }).join('')}
        </tbody>
      </table>
    </div>`;
  } else if(!nMissBom){
    html+=`<div class="text-muted small">No BOM materials found for this PO's lines.</div>`;
  }

  panel.innerHTML=html||'<div class="text-muted small">No material data available.</div>';
}

// PDF PO Upload
async function uploadPdfPo(input){
  const file=input.files[0]; if(!file) return;
  const st=document.getElementById('pdf-status');
  st.className='text-muted small';st.textContent='Extracting PO from PDF…';st.classList.remove('d-none');
  try{
    const fd=new FormData(); fd.append('file',file);
    const r=await fetch('/api/upload/po-pdf',{method:'POST',body:fd});
    const data=await r.json();
    if(!r.ok) throw new Error(data.detail||'Extraction failed');

    // Pre-fill PO header modal
    document.getElementById('po-id').value='';
    document.getElementById('po-number').value=data.po_number||'';
    document.getElementById('po-customer').value=data.customer||'';
    document.getElementById('po-order-date').value=data.order_date||'';
    document.getElementById('po-req-date').value=data.delivery_date||'';
    document.getElementById('po-notes').value=data.notes||'';

    // Show extracted lines + BOM warnings in a review panel
    showPdfPoReview(data);

    st.className='text-success small';
    st.textContent=`Extracted: ${data.po_number} — ${(data.lines||[]).length} line(s)${data.has_warnings?' ⚠ BOM warnings':' ✓ All SKUs matched'}`;
    input.value='';
  }catch(e){st.className='text-danger small';st.textContent='Error: '+e.message;}
}

let _pdfExtracted = null; // store last extracted data for import

function showPdfPoReview(data){
  _pdfExtracted = data;
  const lines=data.lines||[];
  const warnings=data.sku_warnings||[];
  const warnMap=Object.fromEntries(warnings.map(w=>[w.sku||`line${w.line}`,w]));
  const totals=data.totals||{};

  const warnHtml=warnings.length?`
    <div class="alert alert-warning py-2 mb-3">
      <strong><i class="bi bi-exclamation-triangle me-1"></i>${warnings.length} SKU issue(s) found:</strong>
      <ul class="mb-0 mt-1">
        ${warnings.map(w=>`<li><code>${w.sku||'(blank)'}</code> — ${w.message}
          ${w.status==='missing_bom'?`<a href="#" onclick="event.preventDefault();openBomBuilderWithSku('${w.sku||''}')" class="ms-1 text-warning fw-bold">→ Set up BOM</a>`:''}
          ${w.status==='unknown_product'?`<a href="#" onclick="event.preventDefault();openBomBuilderWithSku('${w.sku||''}')" class="ms-1 text-warning fw-bold">→ Create in BOM Builder</a>`:''}
        </li>`).join('')}
      </ul>
    </div>`:'<div class="alert alert-success py-2 mb-3"><i class="bi bi-check-circle me-1"></i>All SKUs matched to products with BOM.</div>';

  const lineRows=lines.map((l,i)=>{
    const w=warnMap[l.sku||`line${i+1}`];
    const rowClass=w?'table-warning':'';
    const ppp = l.pcs_per_unit||0;
    const pallets = l.unit||0;
    const totalPcs = pallets*ppp || l.total_pcs||0;
    return `<tr class="${rowClass}">
      <td><code>${l.sku||'—'}</code>${w?` <span class="badge bg-warning text-dark" style="font-size:.6rem">${w.status==='missing_bom'?'NO BOM':w.status==='unknown_product'?'UNKNOWN':'?'}</span>`:' <span class="badge bg-success" style="font-size:.6rem">✓</span>'}</td>
      <td><small>${l.description||''}</small></td>
      <td><small>${l.base||''} ${l.thickness||''}mm &nbsp;${l.width_inch||''}×${l.length_inch||''}"</small></td>
      <td><small>${[l.species,l.cut,l.veneer_thickness,l.face_grade,l.matching].filter(Boolean).join(' ')}</small></td>
      <td class="text-center fw-bold">${pallets}</td>
      <td class="text-center">
        <input type="number" class="form-control form-control-sm text-center p-0" style="width:65px;display:inline-block"
          value="${ppp}" min="1" id="pdf-ppp-${i}" oninput="updatePdfLinePcs(${i})">
      </td>
      <td class="text-center fw-bold" id="pdf-totpcs-${i}">${totalPcs.toLocaleString()}</td>
      <td><small>${l.price_per_msf?`<span class="text-primary">$${l.price_per_msf}</span>/MSF <span class="text-muted">USD</span>`:''}</small></td>
      <td class="fw-bold"><small><span class="text-primary">$${(l.amount_usd||0).toLocaleString()}</span> <span class="text-muted">USD</span></small></td>
    </tr>`;
  }).join('');

  const totRow=`<tr class="table-secondary fw-bold">
    <td colspan="4" class="text-end">TOTAL</td>
    <td class="text-center">${fmt(totals.unit||0)} pallets</td>
    <td></td>
    <td class="text-center">${fmt(totals.total_pcs||0)} pcs</td>
    <td></td>
    <td>$${(totals.amount_usd||0).toLocaleString()}</td>
  </tr>`;

  // Show in a modal
  let rev=document.getElementById('pdfReviewModal');
  if(!rev){
    rev=document.createElement('div');
    rev.id='pdfReviewModal';
    rev.className='modal fade';
    rev.setAttribute('tabindex','-1');
    rev.innerHTML=`<div class="modal-dialog modal-xl"><div class="modal-content">
      <div class="modal-header">
        <h5 class="modal-title"><i class="bi bi-filetype-pdf me-2"></i>PDF PO Review</h5>
        <button class="btn-close" data-bs-dismiss="modal"></button>
      </div>
      <div class="modal-body overflow-auto" id="pdf-review-body"></div>
      <div class="modal-footer gap-2">
        <button class="btn btn-secondary" data-bs-dismiss="modal">Close</button>
        <button class="btn btn-outline-primary" onclick="bootstrap.Modal.getInstance(document.getElementById('pdfReviewModal')).hide();new bootstrap.Modal(document.getElementById('poModal')).show()">
          <i class="bi bi-pencil me-1"></i>Edit PO Header
        </button>
        <button class="btn btn-success" id="pdf-import-btn" onclick="importPdfLinesToPo()">
          <i class="bi bi-download me-1"></i>Import Lines into PO
        </button>
      </div>
    </div></div>`;
    document.body.appendChild(rev);
  }

  document.getElementById('pdf-review-body').innerHTML=`
    <div class="mb-3 d-flex justify-content-between align-items-start">
      <div>
        <h6 class="mb-1">${data.po_number||'PO'} — ${data.customer||''}</h6>
        <small class="text-muted">Order: ${data.order_date||''} &nbsp;|&nbsp; Ship: ${data.delivery_date||''}</small>
      </div>
      <div class="text-muted small text-end">
        <strong>${lines.length}</strong> line${lines.length!==1?'s':''} &nbsp;|&nbsp;
        <strong>${totals.unit||0}</strong> pallets &nbsp;|&nbsp;
        <strong>${fmt(totals.total_pcs||0)}</strong> pcs &nbsp;|&nbsp;
        <strong>$${(totals.amount_usd||0).toLocaleString()}</strong>
      </div>
    </div>
    ${warnHtml}
    <div class="table-responsive">
      <table class="table table-sm table-bordered align-middle" style="font-size:.8rem">
        <thead class="table-dark">
          <tr>
            <th>SKU</th><th>Description</th><th>Base / Thick / Size</th>
            <th>Veneer Spec</th>
            <th class="text-center">Pallets</th>
            <th class="text-center">Pcs/Pallet <span class="text-warning small">(edit)</span></th>
            <th class="text-center">Total Pcs</th>
            <th>US$/MSF</th><th>Amount</th>
          </tr>
        </thead>
        <tbody>${lineRows}${totRow}</tbody>
      </table>
    </div>
    <p class="text-muted small mt-2"><i class="bi bi-pencil me-1"></i>You can edit <strong>Pcs/Pallet</strong> values above before importing. Mixed-pallet lines are shown in blue.</p>`;

  // Import button always enabled — will auto-save PO header if needed
  const importBtn=document.getElementById('pdf-import-btn');
  if(importBtn) importBtn.disabled=false;

  new bootstrap.Modal(rev).show();
}

function updatePdfLinePcs(i){
  const pppEl=document.getElementById('pdf-ppp-'+i);
  const totEl=document.getElementById('pdf-totpcs-'+i);
  if(!pppEl||!totEl) return;
  const l=(_pdfExtracted&&_pdfExtracted.lines||[])[i];
  if(!l) return;
  const ppp=parseInt(pppEl.value)||0;
  const pallets=l.unit||0;
  totEl.textContent=(pallets*ppp).toLocaleString();
}

async function importPdfLinesToPo(){
  if(!_pdfExtracted) return;

  // ── Step 1: ensure PO header is saved ─────────────────────────────────────
  let poId = selectedPoId;
  if(!poId){
    // Auto-save PO from the pre-filled header fields
    const body={
      po_number:  document.getElementById('po-number').value  || (_pdfExtracted.po_number||''),
      customer:   document.getElementById('po-customer').value || (_pdfExtracted.customer||''),
      order_date: document.getElementById('po-order-date').value || (_pdfExtracted.order_date||''),
      delivery_date: document.getElementById('po-req-date').value || (_pdfExtracted.delivery_date||''),
      notes:      document.getElementById('po-notes').value    || (_pdfExtracted.notes||''),
      status: 'open',
    };
    if(!body.po_number){toast('PO Number is required — fill in the header first','warning');return;}
    try{
      const saved = await api('/api/purchase-orders','POST',body);
      poId = saved.id;
      selectedPoId = poId;
      await loadPoList();
    }catch(e){toast('Could not save PO header: '+e.message,'danger');return;}
  }

  // ── Step 2: build import payload from review table ─────────────────────────
  const lines=_pdfExtracted.lines||[];
  const toImport=lines
    .filter(l=>l.sku_id)
    .map((l,i)=>{
      const pppEl=document.getElementById('pdf-ppp-'+i);
      const ppp=pppEl?parseInt(pppEl.value)||null:l.pcs_per_unit||null;
      return {
        sku_id:        l.sku_id,
        quantity:      l.unit||1,
        pcs_per_pallet: ppp||null,
        unit_price:    l.price_per_msf||0,
        notes:         l.notes||'',
        production_line: 'P01',
      };
    });
  if(!toImport.length){toast('No matched SKUs to import — check SKU warnings above','warning');return;}

  // ── Step 3: import ────────────────────────────────────────────────────────
  try{
    const r=await api(`/api/purchase-orders/${poId}/import-pdf-lines`,'POST',{lines:toImport});
    bootstrap.Modal.getInstance(document.getElementById('pdfReviewModal')).hide();
    toast(`Imported ${r.created} line${r.created!==1?'s':''}${r.skipped?' ('+r.skipped+' already existed)':''}`, 'success');
    selectPo(poId);
  }catch(e){toast('Import failed: '+e.message,'danger');}
}

function openBomBuilderWithSku(sku){
  // Close any open modals first
  document.querySelectorAll('.modal.show').forEach(m=>{
    const inst=bootstrap.Modal.getInstance(m);
    if(inst) inst.hide();
  });
  // Navigate to BOM page
  navigateTo('bom');
  // After the page is visible, activate the FG BOM tab and pre-fill the SKU
  setTimeout(()=>{
    // Click the "FG BOM" tab (first tab)
    const firstTab=document.querySelector('#bom-main-tabs .nav-link');
    if(firstTab && !firstTab.classList.contains('active')) firstTab.click();
    // Pre-fill the SKU code field
    if(sku){
      const codeEl=document.getElementById('bb-code');
      if(codeEl){
        codeEl.value=sku.toUpperCase();
        codeEl.focus();
        codeEl.classList.add('is-valid');
        setTimeout(()=>codeEl.classList.remove('is-valid'),2000);
      }
    }
    // Scroll the builder into view
    document.getElementById('bb-code')?.scrollIntoView({behavior:'smooth',block:'center'});
  }, 350);
}

function openPoModal(){
  document.getElementById('po-id').value='';
  document.getElementById('po-number').value='';
  custFillSelect('');
  document.getElementById('po-order-date').value='';
  document.getElementById('po-req-date').value='';
  document.getElementById('po-notes').value='';
  document.getElementById('po-priority').value=2;
  document.querySelector('#poModal .modal-title').textContent='New Purchase Order';
}
async function editPoModal(id){
  const po=await api(`/api/purchase-orders/${id}`).catch(()=>null);
  if(!po){toast('PO not found','danger');return;}
  document.getElementById('po-id').value=po.id;
  document.getElementById('po-number').value=po.po_number||'';
  await custFillSelect(po.customer||'');
  document.getElementById('po-order-date').value=(po.order_date||'').slice(0,10);
  document.getElementById('po-req-date').value=(po.delivery_date||'').slice(0,10);
  document.getElementById('po-notes').value=po.notes||'';
  document.getElementById('po-priority').value=po.priority||2;
  document.querySelector('#poModal .modal-title').textContent=`Edit PO — ${po.po_number}`;
  bootstrap.Modal.getOrCreateInstance(document.getElementById('poModal')).show();
}
async function deletePo(id){
  if(!confirm('Delete this PO and all its lines?')) return;
  try{await api(`/api/purchase-orders/${id}`,'DELETE');if(selectedPoId===id){selectedPoId=null;document.getElementById('po-lines-list').innerHTML='';document.getElementById('prod-orders-list').innerHTML='';}toast('PO deleted');loadPoList();}
  catch(e){toast(e.message,'danger');}
}
async function deleteProdOrder(id){
  if(!confirm('Delete this production order and all its batches/records? This cannot be undone.')) return;
  try{
    await api(`/api/production-orders/${id}`,'DELETE');
    toast('Production order deleted');
    selectPo(selectedPoId);
  }catch(e){toast(e.message,'danger');}
}
async function voidBatch(id, batchNum, dept){
  if(!confirm(`Void batch ${batchNum}? This removes it from the system permanently.`)) return;
  try{
    await api(`/api/batches/${id}`,'DELETE');
    toast(`Batch ${batchNum} voided`);
    loadDeptPage(dept);
  }catch(e){toast(e.message,'danger');}
}
async function savePo(){
  const id=document.getElementById('po-id').value;
  const body={po_number:document.getElementById('po-number').value,customer:document.getElementById('po-customer').value,order_date:document.getElementById('po-order-date').value,delivery_date:document.getElementById('po-req-date').value,priority:parseInt(document.getElementById('po-priority').value),notes:document.getElementById('po-notes').value,status:'open'};
  try{
    if(id) await api(`/api/purchase-orders/${id}`,'PUT',body); else await api('/api/purchase-orders','POST',body);
    bootstrap.Modal.getInstance(document.getElementById('poModal')).hide();
    toast('PO saved'); loadPoList();
  }catch(e){toast(e.message,'danger');}
}

let _polFgAll=[];
async function openPoLineModal(){
  document.getElementById('pol-line-id').value='';
  document.getElementById('pol-modal-title').textContent='Add PO Line';
  document.getElementById('pol-fg-search').value='';
  document.getElementById('pol-notes').value='';
  document.getElementById('pol-qty').value='';
  document.getElementById('pol-price').value='';
  document.getElementById('pol-pcs-per-pallet').value='';
  document.getElementById('pol-total-pcs').value='';
  _polTotalPcsOverridden=false;
  document.getElementById('pol-fg-info').classList.add('d-none');
  document.getElementById('pol-qty-hint').classList.add('d-none');
  document.getElementById('pol-packing-id').value='';

  // Load FG list and packing specs in parallel
  const [fgs, packSpecs] = await Promise.all([
    api('/api/fg'),
    api('/api/packing-skus').catch(()=>[]),
  ]);
  _polFgAll = fgs;
  // Populate packing dropdown
  const packSel = document.getElementById('pol-packing-id');
  packSel.innerHTML = '<option value="">\u2014 No packing selected \u2014</option>' +
    packSpecs.map(p=>`<option value="${p.id}">${p.code}${p.customer?' ('+p.customer+')':''}</option>`).join('');

  const noFg  = document.getElementById('pol-no-fg');
  const picker = document.getElementById('pol-fg-picker');
  const saveBtn = document.getElementById('pol-save-btn');

  if(!fgs.length){
    noFg.classList.remove('d-none');
    picker.classList.add('d-none');
    saveBtn.disabled=true;
    return;
  }
  noFg.classList.add('d-none');
  picker.classList.remove('d-none');
  saveBtn.disabled=false;
  renderPolFgOptions(fgs);
}

function renderPolFgOptions(list){
  const sel=document.getElementById('pol-product-id');
  sel.innerHTML=list.map(s=>`<option value="${s.id}">${s.code} — ${s.name}</option>`).join('');
  if(list.length) onPolFgSelect(sel.value);
}

function filterPolFg(q){
  const s=q.toLowerCase();
  renderPolFgOptions(s?_polFgAll.filter(r=>r.code.toLowerCase().includes(s)||(r.name||'').toLowerCase().includes(s)):_polFgAll);
}

function onPolFgSelect(id){
  const fg=_polFgAll.find(s=>String(s.id)===String(id));
  const info=document.getElementById('pol-fg-info');
  const hint=document.getElementById('pol-qty-hint');
  if(!fg){info.classList.add('d-none');hint.classList.add('d-none');return;}
  info.classList.remove('d-none');
  info.innerHTML=`<span class="fw-bold text-primary">${fg.code}</span>
    &nbsp;|&nbsp; ${fg.thickness_mm||'—'}mm
    &nbsp;|&nbsp; ${fg.width_mm||'—'} × ${fg.length_mm||'—'} mm
    &nbsp;|&nbsp; BOM default: <b>${fg.pallet_qty||'—'}</b> pcs/pallet`;
  const pq=fg.pallet_qty||0;
  document.getElementById('pol-pallet-qty').value=pq;
  // Pre-fill pcs/pallet from BOM if empty
  const pcsEl=document.getElementById('pol-pcs-per-pallet');
  if(!pcsEl.value && pq) pcsEl.value=pq;
  hint.classList.remove('d-none');
  updatePolPalletHint();
}
let _polTotalPcsOverridden = false;
function onPolTotalPcsOverride(){
  // User typed a custom total — mark as overridden so calc doesn't clobber
  _polTotalPcsOverridden = !!document.getElementById('pol-total-pcs').value;
  updatePolPalletHint();
}
function updatePolPalletHint(){
  const pallets=parseFloat(document.getElementById('pol-qty').value)||0;
  const pcsPerPallet=parseInt(document.getElementById('pol-pcs-per-pallet').value)||
                     parseInt(document.getElementById('pol-pallet-qty').value)||0;
  const totalEl=document.getElementById('pol-total-pcs');
  const hint=document.getElementById('pol-qty-hint');
  if(!pallets){hint.innerHTML='<i class="bi bi-info-circle me-1"></i>Enter pallet quantity above';hint.classList.remove('d-none');return;}
  const calculated=Math.round(pallets*(pcsPerPallet||0));
  // Auto-fill total pcs unless user has manually overridden
  if(!_polTotalPcsOverridden){
    totalEl.value = calculated || '';
  }
  const finalPcs = parseInt(totalEl.value) || calculated || 0;
  const isOverride = _polTotalPcsOverridden && finalPcs !== calculated;
  const palletsDisplay = pallets % 1 === 0 ? pallets : pallets.toFixed(2);
  hint.innerHTML = `<i class="bi bi-calculator me-1"></i>
    <b>${palletsDisplay}</b> pallet${pallets!==1?'s':''}
    ${pcsPerPallet?` × <b>${pcsPerPallet}</b> pcs/pallet = <b>${calculated.toLocaleString()}</b> pcs`:''}
    ${isOverride?` &nbsp;<span class="badge bg-warning text-dark ms-1">Override → ${finalPcs.toLocaleString()} pcs</span>`:''}
    ${pcsPerPallet?` &nbsp;<span class="text-muted small">(saved as <b>${finalPcs.toLocaleString()}</b> pcs)</span>`:''}`;
  hint.classList.remove('d-none');
}

async function savePoLine(){
  const lineId=document.getElementById('pol-line-id').value;
  const palletsRaw=parseFloat(document.getElementById('pol-qty').value)||0;
  if(!palletsRaw){toast('Please enter a pallet quantity','danger');return;}
  let pcsPerPallet=parseInt(document.getElementById('pol-pcs-per-pallet').value)||
                   parseInt(document.getElementById('pol-pallet-qty').value)||null;
  // Resolve total pcs (user override or calculated)
  const overrideTotal=parseInt(document.getElementById('pol-total-pcs').value)||0;
  const calculatedTotal=Math.round(palletsRaw*(pcsPerPallet||0));
  const finalTotalPcs = (overrideTotal && overrideTotal!==calculatedTotal) ? overrideTotal : calculatedTotal;
  // Convert to (pallets-as-integer, pcs_per_pallet) so total stays exact
  // For fractional/partial pallets we recalc pcs_per_pallet so quantity*pcs_per_pallet === finalTotalPcs
  let qty, finalPcsPerPallet;
  if(palletsRaw % 1 !== 0 || (overrideTotal && overrideTotal!==calculatedTotal)){
    // Partial pallets OR pcs override → store as 1 pallet with custom pcs_per_pallet = total
    qty = 1;
    finalPcsPerPallet = finalTotalPcs;
    if(palletsRaw % 1 !== 0){
      // Persist the original pallet count info in notes (since DB col is INT)
      const origNotes=document.getElementById('pol-notes').value||'';
      const palletInfo=`[${palletsRaw} pallets × ${pcsPerPallet||'?'} pcs/plt]`;
      if(!origNotes.includes(palletInfo)) document.getElementById('pol-notes').value=(origNotes?origNotes+' ':'')+palletInfo;
    }
  } else {
    qty = parseInt(palletsRaw);
    finalPcsPerPallet = pcsPerPallet;
  }
  const polPackId = document.getElementById('pol-packing-id').value ? parseInt(document.getElementById('pol-packing-id').value) : null;
  const body={
    production_line:document.getElementById('pol-line').value,
    quantity:qty,
    pcs_per_pallet:finalPcsPerPallet,
    unit_price:parseFloat(document.getElementById('pol-price').value)||0,
    notes:document.getElementById('pol-notes').value,
    packing_sku_id: polPackId,
  };

  if(lineId){
    // Edit mode — just PATCH the existing line
    try{
      await api(`/api/po-lines/${lineId}`,'PUT',body);
      bootstrap.Modal.getInstance(document.getElementById('poLineModal')).hide();
      toast('Line updated');
      selectPo(selectedPoId);
    }catch(e){toast(e.message,'danger');}
    return;
  }

  // Add mode — need FG selection
  const sel=document.getElementById('pol-product-id');
  const fg=_polFgAll.find(s=>String(s.id)===String(sel.value));
  if(!fg){toast('Please select an FG code','danger');return;}
  // _polFgAll is the skus (FG) catalog — send sku_id directly.
  body.po_id=selectedPoId;
  body.sku_id=fg.id;
  try{
    await api('/api/po-lines','POST',body);
    bootstrap.Modal.getInstance(document.getElementById('poLineModal')).hide();
    toast('Line added');
    selectPo(selectedPoId);
  }catch(e){toast(e.message,'danger');}
}

async function editPoLine(id, productId, sku, name, line, qty, price, notes, packingSkuId, pcsPerPallet){
  document.getElementById('pol-line-id').value=id;
  document.getElementById('pol-modal-title').textContent=`Edit Line — ${sku}`;
  document.getElementById('pol-line').value=line||'P01';
  document.getElementById('pol-qty').value=qty||'';
  document.getElementById('pol-price').value=price||'';
  document.getElementById('pol-notes').value=notes||'';
  document.getElementById('pol-pcs-per-pallet').value=pcsPerPallet||'';
  document.getElementById('pol-total-pcs').value=(qty&&pcsPerPallet)?Math.round(qty*pcsPerPallet):'';
  _polTotalPcsOverridden=false;
  // Look up pallet_qty from BOM for reference display
  if(!_polFgAll.length) _polFgAll=await api('/api/fg').catch(()=>[]);
  const fgMatch=_polFgAll.find(s=>s.code===sku);
  const pq=fgMatch?fgMatch.pallet_qty||0:0;
  document.getElementById('pol-pallet-qty').value=pq;
  updatePolPalletHint();
  // Show FG info strip with locked badge; hide the picker search
  document.getElementById('pol-fg-search').value='';
  document.getElementById('pol-fg-search').disabled=true;
  document.getElementById('pol-product-id').disabled=true;
  const picker=document.getElementById('pol-fg-picker');
  if(picker) picker.classList.remove('d-none');
  document.getElementById('pol-no-fg').classList.add('d-none');
  const info=document.getElementById('pol-fg-info');
  info.classList.remove('d-none');
  info.innerHTML=`<span class="fw-bold text-primary">${sku}</span> &nbsp;|&nbsp; <span class="text-muted">${name}</span>${pq?` &nbsp;|&nbsp; BOM default: <b>${pq}</b> pcs/pallet`:''} <span class="badge bg-secondary ms-2">FG locked &mdash; delete &amp; re-add to change</span>`;
  document.getElementById('pol-save-btn').disabled=false;
  // Set packing dropdown
  if(document.getElementById('pol-packing-id').options.length <= 1){
    const pks = await api('/api/packing-skus').catch(()=>[]);
    document.getElementById('pol-packing-id').innerHTML = '<option value="">— No packing selected —</option>' +
      pks.map(p=>`<option value="${p.id}">${p.code}${p.customer?' ('+p.customer+')':''}</option>`).join('');
  }
  document.getElementById('pol-packing-id').value = packingSkuId || '';
  bootstrap.Modal.getOrCreateInstance(document.getElementById('poLineModal')).show();
}

document.addEventListener('DOMContentLoaded',()=>{
  // Wrap loose text in each sidebar nav-link with a <span> so the collapsed
  // CSS can hide labels but keep icons + badges visible.
  document.querySelectorAll('#sidebar a.nav-link').forEach(a => {
    [...a.childNodes].forEach(n => {
      if(n.nodeType === Node.TEXT_NODE && n.textContent.trim()){
        const sp = document.createElement('span');
        sp.className = 'sb-label';
        sp.textContent = n.textContent;
        a.replaceChild(sp, n);
      }
    });
  });
  // Restore pinned state from localStorage
  if(localStorage.getItem('erp_sb_pinned') === '1'){
    document.getElementById('sidebar')?.classList.add('pinned');
    document.body.classList.add('sb-pinned');
    const ic = document.getElementById('sidebar-pin-icon');
    if(ic){ ic.classList.remove('bi-pin-angle-fill'); ic.classList.add('bi-pin-fill'); }
  }
  window.toggleSidebarPin = function(ev){
    ev?.stopPropagation();
    const sb = document.getElementById('sidebar');
    const ic = document.getElementById('sidebar-pin-icon');
    const pinned = sb.classList.toggle('pinned');
    document.body.classList.toggle('sb-pinned', pinned);
    localStorage.setItem('erp_sb_pinned', pinned ? '1' : '0');
    if(ic){
      ic.classList.toggle('bi-pin-fill', pinned);
      ic.classList.toggle('bi-pin-angle-fill', !pinned);
    }
  };
  const poLineModal=document.getElementById('poLineModal');
  if(poLineModal){
    poLineModal.addEventListener('hidden.bs.modal',()=>{
      document.getElementById('pol-line-id').value='';
      document.getElementById('pol-modal-title').textContent='Add PO Line';
      document.getElementById('pol-fg-search').disabled=false;
      document.getElementById('pol-product-id').disabled=false;
    });
  }
});

async function deletePoLine(id){
  if(!confirm('Remove this line from the PO?')) return;
  try{
    await api(`/api/po-lines/${id}`,'DELETE');
    toast('Line removed');
    selectPo(selectedPoId);
  }catch(e){toast(e.message,'danger');}
}

let _pordLines=[], _pordTotalOverridden=false;
async function openProdOrderModal(){
  document.getElementById('pord-qty').value='';
  document.getElementById('pord-notes').value='';
  document.getElementById('pord-pcs-edit').value='';
  document.getElementById('pord-total-pcs').value='';
  document.getElementById('pord-pcs-per-pallet').value='';
  document.getElementById('pord-qty-hint').classList.add('d-none');
  _pordTotalOverridden=false;
  document.getElementById('pord-start').value=new Date().toISOString().slice(0,10);
  _pordLines = await api(`/api/purchase-orders/${selectedPoId}/lines`).catch(()=>[]);
  const sel=document.getElementById('pord-line-id');
  sel.innerHTML=_pordLines.map(l=>{
    const pcsPerPlt=l.pcs_per_pallet||0;
    const totalPcs=(l.quantity||0)*(pcsPerPlt||1);
    return `<option value="${l.id}">${l.product_name} — ${l.quantity} plt${pcsPerPlt?' × '+pcsPerPlt+'pcs/plt = '+totalPcs+' pcs':''} (${l.production_line})</option>`;
  }).join('');
  onPordLineChange();
}
function onPordLineChange(){
  const lineId=parseInt(document.getElementById('pord-line-id').value);
  const line=_pordLines.find(l=>l.id===lineId);
  if(!line) return;
  // Pre-fill pcs/pallet from PO line
  const pp=line.pcs_per_pallet||0;
  document.getElementById('pord-pcs-per-pallet').value=pp;
  document.getElementById('pord-pcs-edit').value=pp||'';
  document.getElementById('pord-pcs-edit').placeholder=pp?`From PO line: ${pp}`:'Pcs per pallet';
  // Suggest pallets from PO line
  if(!document.getElementById('pord-qty').value) document.getElementById('pord-qty').value=line.quantity||'';
  updatePordHint();
}
function onPordTotalOverride(){
  _pordTotalOverridden = !!document.getElementById('pord-total-pcs').value;
  updatePordHint();
}
function updatePordHint(){
  const pallets=parseFloat(document.getElementById('pord-qty').value)||0;
  const pcsPerPallet=parseInt(document.getElementById('pord-pcs-edit').value)||
                     parseInt(document.getElementById('pord-pcs-per-pallet').value)||0;
  const totalEl=document.getElementById('pord-total-pcs');
  const hint=document.getElementById('pord-qty-hint');
  if(!pallets){hint.innerHTML='<i class="bi bi-info-circle me-1"></i>Enter pallet quantity';hint.classList.remove('d-none');return;}
  const calculated=Math.round(pallets*(pcsPerPallet||0));
  if(!_pordTotalOverridden) totalEl.value=calculated||'';
  const finalPcs=parseInt(totalEl.value)||calculated||0;
  const isOverride=_pordTotalOverridden && finalPcs!==calculated;
  const palletsDisplay=pallets%1===0?pallets:pallets.toFixed(2);
  hint.innerHTML=`<i class="bi bi-calculator me-1"></i>
    <b>${palletsDisplay}</b> pallet${pallets!==1?'s':''}
    ${pcsPerPallet?` × <b>${pcsPerPallet}</b> pcs/pallet = <b>${calculated.toLocaleString()}</b> pcs`:''}
    ${isOverride?` &nbsp;<span class="badge bg-warning text-dark ms-1">Override → ${finalPcs.toLocaleString()} pcs</span>`:''}`;
  hint.classList.remove('d-none');
}
async function saveProdOrder(release){
  const lineId=parseInt(document.getElementById('pord-line-id').value);
  const lines=_pordLines.length?_pordLines:await api(`/api/purchase-orders/${selectedPoId}/lines`).catch(()=>[]);
  const line=lines.find(l=>l.id===lineId)||{};
  const palletsRaw=parseFloat(document.getElementById('pord-qty').value)||0;
  if(!palletsRaw){toast('Enter pallet quantity','danger');return;}
  let pcsPerPallet=parseInt(document.getElementById('pord-pcs-edit').value)||
                   parseInt(document.getElementById('pord-pcs-per-pallet').value)||1;
  const overrideTotal=parseInt(document.getElementById('pord-total-pcs').value)||0;
  const calculatedTotal=Math.round(palletsRaw*pcsPerPallet);
  const finalTotalPcs=(overrideTotal && overrideTotal!==calculatedTotal)?overrideTotal:calculatedTotal;
  // For partial pallets / overrides, store as 1×pcs to keep totals exact
  let qty;
  if(palletsRaw % 1 !== 0 || (overrideTotal && overrideTotal!==calculatedTotal)){
    qty=Math.max(1, Math.round(finalTotalPcs/pcsPerPallet));
    // If still not exact, fall back to qty=1 with pcs_per_pallet=total
    if(qty*pcsPerPallet !== finalTotalPcs){
      qty=1;
    }
  } else {
    qty=parseInt(palletsRaw);
  }
  const notesBase=document.getElementById('pord-notes').value||'';
  const partialNote=(palletsRaw%1!==0)?`[${palletsRaw} pallets ordered]`:'';
  const finalNotes=partialNote && !notesBase.includes(partialNote)?(notesBase?notesBase+' '+partialNote:partialNote):notesBase;
  const body={prod_order_number:'PO-'+Date.now(),sku_id:line.sku_id,production_line:line.production_line||'P01',quantity:qty,po_line_id:lineId,po_id:selectedPoId,planned_start:document.getElementById('pord-start').value,notes:finalNotes,status:'draft',priority:2};
  try{
    const ord=await api('/api/production-orders','POST',body);
    if(release) await api(`/api/production-orders/${ord.id}/release`,'POST');
    bootstrap.Modal.getInstance(document.getElementById('prodOrderModal')).hide();
    toast(release?'Released to production!':'Draft saved');selectPo(selectedPoId);
  }catch(e){toast(e.message,'danger');}
}
async function releasePO(id){try{await api(`/api/production-orders/${id}/release`,'POST');toast('Released');selectPo(selectedPoId);}catch(e){toast(e.message,'danger');}}

// ── Bulk release: PO-lines tick boxes → production orders ────────
let _poLines = [];
function togglePoLineAll(checked){
  document.querySelectorAll('.po-line-cb:not(:disabled)').forEach(cb => cb.checked = checked);
  onPoLineCheck();
}
function onPoLineCheck(){
  const checked = document.querySelectorAll('.po-line-cb:checked').length;
  const cnt = document.getElementById('po-release-count');
  const btn = document.getElementById('po-release-btn');
  if(cnt) cnt.textContent = `${checked} selected`;
  if(btn) btn.disabled = checked === 0;
}
async function releaseSelectedPoLines(poId){
  const cbs = [...document.querySelectorAll('.po-line-cb:checked')];
  if(!cbs.length){ toast('Pick at least one line','warning'); return; }
  const ids = cbs.map(cb => Number(cb.dataset.lineId));
  const lines = _poLines.filter(l => ids.includes(l.id));
  if(!confirm(`Release ${lines.length} PO line(s) to Production?\n\nThis creates a draft production order for each and immediately releases it (creates the batch).`)){
    return;
  }
  const btn = document.getElementById('po-release-btn');
  if(btn){ btn.disabled = true; btn.innerHTML='<span class="spinner-border spinner-border-sm me-2"></span>Releasing…'; }
  let ok=0, fail=0;
  for(const l of lines){
    const ppp = l.pcs_per_pallet || 1;
    const body = {
      prod_order_number: 'PO-'+Date.now()+'-'+l.id,
      sku_id: l.sku_id,
      production_line: l.production_line || 'P01',
      quantity: l.quantity,            // pallets
      po_line_id: l.id,
      po_id: poId,
      planned_start: new Date().toISOString().slice(0,10),
      notes: `Bulk-released from PO line #${l.id}`,
      status: 'draft',
      priority: 2,
    };
    try{
      const ord = await api('/api/production-orders','POST',body);
      await api(`/api/production-orders/${ord.id}/release`,'POST');
      ok++;
    }catch(e){
      fail++; console.error('Release failed for line', l.id, e);
    }
  }
  if(btn){ btn.disabled = false; btn.innerHTML='<i class="bi bi-play-circle me-1"></i>Release Selected to Production'; }
  toast(`Released ${ok} line(s)${fail?` · ${fail} failed`:''}`, fail?'warning':'success');
  selectPo(poId);
}



// ════════════════════════════════════════════════════════════
// Line Board (TrainingPeaks-style)
// ════════════════════════════════════════════════════════════
// ══════════════════════════════════════════════════════════
// LINE BOARD  (TrainingPeaks-style)
// ══════════════════════════════════════════════════════════
async function loadLineBoard(){
  const [flow, porders] = await Promise.all([
    api(`/api/planning/line-board${lbLine!=='all'?'?production_line='+lbLine:''}`).catch(()=>({})),
    api('/api/production-orders').catch(()=>[])
  ]);
  renderLbSidebar(porders);
  renderLbBoard(flow);
}

function setLbLine(line, btn){
  lbLine=line;
  document.querySelectorAll('.lb-line-btns button').forEach(b=>b.classList.remove('active'));
  btn.classList.add('active');
  loadLineBoard();
}

function renderLbSidebar(porders){
  const filtered=lbLine==='all'?porders:porders.filter(o=>o.production_line===lbLine);
  const active=filtered.filter(o=>['planned','in_progress'].includes(o.status))
                       .sort((a,b)=>(a.priority||2)-(b.priority||2));
  document.getElementById('lb-order-list').innerHTML=active.length?active.map(o=>`
    <div class="lb-order-card p${o.priority||2}">
      <div class="d-flex justify-content-between align-items-center">
        <div class="lo-num">${o.prod_order_number||o.order_number||'#'+o.id} ${lineBadge(o.production_line)}</div>
        ${prioBadge(o.priority||2)}
      </div>
      <div class="lo-prod">${o.product_name||''}</div>
      <div class="lo-meta">${fmt(o.quantity)} pcs &middot; ${statusBadge(o.status)}</div>
    </div>`).join(''):'<p class="text-muted small p-2">No active orders.</p>';
}

function renderLbBoard(flow){
  const sections=LINE_FLOW[lbLine]||LINE_FLOW.all;
  document.getElementById('lb-cols').innerHTML=sections.map(dept=>{
    const batches=flow[dept]||[];
    return `<div class="lb-col">
      <div class="lb-col-head"><span><i class="bi ${DICO[dept]} me-1"></i>${DLBL[dept]}</span><span class="cnt">${batches.length}</span></div>
      <div class="lb-col-body" id="lb-body-${dept}">
        ${batches.map(b=>lbCard(b)).join('')}
      </div>
    </div>`;
  }).join('');
}

// Line Board card — read-only planning view. Click opens batch details (read-only);
// priority can be tweaked inline. Stage moves are done in the Station Leader Hub.
function lbCard(b){
  return `<div class="bc p${b.priority||2}" style="cursor:pointer"
    onclick="deptBatchDetail(${b.id},'${b.current_department}',true)"
    title="Click for batch details (planning view)">
    <div class="bc-num d-flex justify-content-between align-items-center">
      <span>${b.batch_number||'B#'+b.id}${b.parent_batch_id?` <span class="badge bg-warning text-dark" style="font-size:.58rem">SPLIT</span>`:''}</span>
      ${prioBadge(b.priority||2)}
    </div>
    <div class="bc-prod">${b.product_name||b.product_sku||''}</div>
    <div class="bc-qty">${fmt(b.quantity)} plt · ${fmt(b.total_pcs ?? b.pcs_actual ?? ((b.quantity||0)*(b.pallet_qty||1)))} pcs</div>
    ${b.po_number?`<div style="font-size:.65rem;color:#94a3b8">PO: ${b.po_number}</div>`:''}
    <div class="mt-1" onclick="event.stopPropagation()">${prioSelect(b.priority||2, b.id, 'batch', 'loadLineBoard()')}</div>
  </div>`;
}



// ════════════════════════════════════════════════════════════
// Kanban (prod-flow)
// ════════════════════════════════════════════════════════════
// ══════════════════════════════════════════════════════════
// KANBAN
// ══════════════════════════════════════════════════════════
// Kanban is a read-only PLANNING viewer: it shows where every batch sits in the
// production flow and lets planners tweak priority. Actual stage moves / splits
// happen in the Station Leader Hub (logged via /api/production/*), never here.
async function loadKanban(){
  const flow=await api('/api/planning/flow').catch(()=>({}));
  document.getElementById('kanban-board').innerHTML=DEPTS.map(dept=>{
    const bs=flow[dept]||[];
    return `<div class="kanban-col">
      <div class="col-head"><span><i class="bi ${DICO[dept]} me-1"></i>${DLBL[dept]}</span><span class="badge bg-secondary">${bs.length}</span></div>
      ${bs.map(b=>`<div class="batch-card priority-${b.priority||2}" style="cursor:pointer"
        onclick="deptBatchDetail(${b.id},'${dept}',true)" title="Click for batch details (planning view)">
        <div class="d-flex justify-content-between align-items-center">
          <span class="fw-bold" style="font-size:.75rem">${b.batch_number||'B#'+b.id}</span>
          ${prioBadge(b.priority||2)}
        </div>
        <div style="font-size:.7rem;color:#64748b">${b.product_name||''}</div>
        <div style="font-size:.72rem;color:#1f4a1f;font-weight:600">${fmt(b.quantity)} plt · ${fmt(b.total_pcs ?? b.pcs_actual ?? ((b.quantity||0)*(b.pallet_qty||1)))} pcs</div>
        <div class="mt-1" onclick="event.stopPropagation()">${prioSelect(b.priority||2, b.id, 'batch', 'loadKanban()')}</div>
      </div>`).join('')}
    </div>`;
  }).join('');
}



// ════════════════════════════════════════════════════════════
// Production Reports
// ════════════════════════════════════════════════════════════
// ══════════════════════════════════════════════════════════
// PRODUCTION REPORTS
// ══════════════════════════════════════════════════════════
function prSetPeriod(days){
  const to=new Date().toISOString().slice(0,10);
  const from=new Date(Date.now()-days*86400000).toISOString().slice(0,10);
  document.getElementById('pr-from').value=from;
  document.getElementById('pr-to').value=to;
}
async function loadProdReports(){
  const line=document.getElementById('pr-line').value||null;
  const from=document.getElementById('pr-from').value||null;
  const to=document.getElementById('pr-to').value||null;
  const qs=(p,v)=>v?`${p}=${encodeURIComponent(v)}`:'';
  const q=(parts)=>{const s=parts.filter(Boolean).join('&');return s?'?'+s:'';};

  const [daily,lam,sand,ncgReason]=await Promise.all([
    api('/api/reports/daily'+q([qs('line_id',line),qs('from_date',from),qs('to_date',to)])).catch(()=>[]),
    api('/api/reports/lam-efficacy'+q([qs('line_id',line),qs('from_date',from)])).catch(()=>[]),
    api('/api/reports/sanding-defects'+q([qs('line_id',line),qs('from_date',from)])).catch(()=>[]),
    api('/api/reports/ncg-reasons'+q([qs('line_id',line)])).catch(()=>[]),
  ]);

  // KPIs
  const totGood=daily.reduce((s,r)=>s+(r.qty_good||0),0);
  const totNcg=daily.reduce((s,r)=>s+(r.qty_ncg||0),0);
  const totAll=daily.reduce((s,r)=>s+(r.qty_good||0)+(r.qty_ncg||0)+(r.qty_reject||0),0);
  const ncgRate=totAll?((totNcg/totAll)*100).toFixed(2):0;
  const avgSand=sand.length?(sand.reduce((s,r)=>s+(r.defect_rate_pct||0),0)/sand.length).toFixed(2):0;
  const avgLam=lam.length?(lam.reduce((s,r)=>s+(r.efficacy_pct||0),0)/lam.length).toFixed(1):0;

  document.getElementById('pr-kpi-boards').textContent=fmt(totGood);
  const ncgEl=document.getElementById('pr-kpi-ncg');
  ncgEl.textContent=ncgRate+'%';
  ncgEl.className='val '+(ncgRate>=4?'text-danger':ncgRate>=2.5?'text-warning':'text-success');
  const sandEl=document.getElementById('pr-kpi-sand');
  sandEl.textContent=avgSand+'%';
  sandEl.className='val '+(avgSand>=3?'text-danger':avgSand>=1.5?'text-warning':'text-success');
  const lamEl=document.getElementById('pr-kpi-lam');
  lamEl.textContent=avgLam+'%';
  lamEl.className='val '+(avgLam<88?'text-danger':avgLam<95?'text-warning':'text-success');

  // Daily table
  const dailyTb=document.querySelector('#pr-daily-table tbody');
  dailyTb.innerHTML=daily.length?daily.map(r=>`<tr>
    <td>${r.production_date||'—'}</td>
    <td><span class="line-badge line-${r.line_id}">${r.line_id||'—'}</span></td>
    <td><code class="text-primary">${r.sku_code||'—'}</code></td>
    <td>${r.batches||0}</td>
    <td>${fmt(r.qty_planned)}</td>
    <td class="text-success fw-bold">${fmt(r.qty_good)}</td>
    <td class="${r.qty_ncg>0?'text-warning fw-bold':''}">${fmt(r.qty_ncg)}</td>
    <td class="${r.qty_reject>0?'text-danger fw-bold':''}">${fmt(r.qty_reject)}</td>
    <td><span class="badge ${(r.ncg_rate_pct||0)>=4?'bg-danger':(r.ncg_rate_pct||0)>=2.5?'bg-warning text-dark':'bg-success'}">${(r.ncg_rate_pct||0).toFixed(1)}%</span></td>
  </tr>`).join(''):'<tr><td colspan="9" class="text-center text-muted py-3">No data for selected period.</td></tr>';

  // Lam efficacy table
  const lamTb=document.querySelector('#pr-lam-table tbody');
  lamTb.innerHTML=lam.length?lam.map(r=>{
    const eff=r.efficacy_pct||0;
    return `<tr>
      <td><span class="badge bg-secondary">${r.table_id}</span></td>
      <td><span class="line-badge line-${r.line_id}">${r.line_id}</span></td>
      <td><code class="text-primary small">${r.sku_code||'—'}</code></td>
      <td>${r.production_date||'—'}</td>
      <td>${r.shift||'—'}</td>
      <td><small>${r.emp_code_1||'—'} + ${r.emp_code_2||'—'}</small></td>
      <td>${fmt(r.pcs_target)}</td>
      <td>${fmt(r.pcs_actual)}</td>
      <td><span class="badge ${eff>=95?'bg-success':eff>=88?'bg-warning text-dark':'bg-danger'}">${eff.toFixed(1)}%</span></td>
    </tr>`;}).join(''):'<tr><td colspan="9" class="text-center text-muted py-3">No laminating data.</td></tr>';

  // Sanding defects table
  const sandTb=document.querySelector('#pr-sand-table tbody');
  sandTb.innerHTML=sand.length?sand.map(r=>{
    const rate=r.defect_rate_pct||0;
    const pct=Math.min(rate*10,100);
    return `<tr>
      <td>${r.operator||'—'}</td>
      <td><span class="line-badge line-${r.line_id}">${r.line_id||'—'}</span></td>
      <td>${r.runs||0}</td>
      <td>${fmt(r.total_pcs)}</td>
      <td class="${rate>2.5?'text-danger fw-bold':rate>1.5?'text-warning':''}">${fmt(r.total_defects)}</td>
      <td><span class="badge ${rate>=3?'bg-danger':rate>=1.5?'bg-warning text-dark':'bg-success'}">${rate.toFixed(2)}%</span></td>
      <td style="width:100px"><div class="progress" style="height:8px"><div class="progress-bar ${rate>=3?'bg-danger':rate>=1.5?'bg-warning':'bg-success'}" style="width:${pct}%"></div></div></td>
    </tr>`;}).join(''):'<tr><td colspan="7" class="text-center text-muted py-3">No sanding data.</td></tr>';

  // Load NCG list
  await loadNcgList();
}
async function loadNcgList(){
  const line=document.getElementById('pr-line').value||null;
  const from=document.getElementById('pr-from').value||null;
  const reason=document.getElementById('pr-ncg-reason-filter').value||null;
  const qs=(p,v)=>v?`${p}=${encodeURIComponent(v)}`:'';
  const q=(parts)=>{const s=parts.filter(Boolean).join('&');return s?'?'+s:'';};
  const rows=await api('/api/reports/ncg-list'+q([qs('line_id',line),qs('from_date',from),qs('reason_code',reason)])).catch(()=>[]);
  const el=document.getElementById('pr-ncg-list');
  if(!rows.length){el.innerHTML='<p class="text-muted small text-center py-3">No NCG batches found.</p>';return;}
  el.innerHTML=rows.map(r=>`
    <div class="card p-2 mb-2 border-warning">
      <div class="d-flex justify-content-between align-items-start">
        <div>
          <code class="text-primary">${r.batch_id}</code>
          <span class="badge bg-warning text-dark ms-2">${r.ncg_reason_code||'—'}</span>
          <span class="line-badge line-${r.line_id} ms-1">${r.line_id}</span>
        </div>
        <small class="text-muted">${r.production_date} ${r.shift}</small>
      </div>
      <div class="small mt-1">
        <span class="text-muted">SKU:</span> <code>${r.sku_code||'—'}</code>
        &nbsp;|&nbsp; <span class="text-danger fw-bold">${r.pcs_ncg||0} NCG</span>
        &nbsp;|&nbsp; <span class="text-muted">Lam efficacy: ${r.lam_efficacy_pct!=null?r.lam_efficacy_pct+'%':'—'}</span>
        &nbsp;|&nbsp; <span class="text-muted">Sand defects: ${r.sanding_defects!=null?r.sanding_defects:'—'}</span>
      </div>
      <div class="small text-muted mt-1">
        Lam pairs: ${r.lam_pairs||'—'} &nbsp;|&nbsp; Repair: ${r.repair_pairs||'—'}
        &nbsp;|&nbsp; Sanding op: ${r.sanding_operator||'—'} &nbsp;|&nbsp; HP op: ${r.hotpress_operator||'—'}
      </div>
    </div>`).join('');
}

// AI Chat for production reports
let _prodAiHistory=[];
function openProdAiChat(){
  bootstrap.Collapse.getOrCreateInstance(document.getElementById('prod-ai-chat-panel')).show();
  if(!_prodAiHistory.length){
    document.getElementById('prod-ai-messages').innerHTML='<p class="text-muted small">Ask me anything about the production data — e.g. "Which sanding operator has the highest defect rate?" or "Is P01 performing worse than P02?"</p>';
  }
}
async function sendProdAiMsg(){
  const input=document.getElementById('prod-ai-input');
  const msg=input.value.trim(); if(!msg)return;
  input.value='';
  _prodAiHistory.push({role:'user',content:msg});
  const el=document.getElementById('prod-ai-messages');
  el.innerHTML+=`<div class="mb-2"><span class="badge bg-primary">You</span> <span class="small">${msg}</span></div>`;
  el.innerHTML+='<div id="ai-typing" class="text-muted small"><div class="spinner-border spinner-border-sm me-1"></div>Thinking...</div>';
  el.scrollTop=el.scrollHeight;
  try{
    const line=document.getElementById('pr-line')?.value||null;
    const r=await api('/api/production/ai/chat','POST',{messages:_prodAiHistory,line_id:line});
    document.getElementById('ai-typing')?.remove();
    _prodAiHistory.push({role:'assistant',content:r.reply});
    el.innerHTML+=`<div class="mb-2 p-2 bg-white border rounded"><span class="badge bg-secondary">AI</span><div class="small mt-1">${(r.reply||'').replace(/\n/g,'<br>')}</div></div>`;
    el.scrollTop=el.scrollHeight;
  }catch(e){document.getElementById('ai-typing')?.remove();el.innerHTML+=`<div class="alert alert-danger small">${e.message}</div>`;}
}

// ── Router integration ─────────────────────────────────────────




// ════════════════════════════════════════════════════════════
// Forklifts (SLH Forklifts tab)
// ════════════════════════════════════════════════════════════
// Material Shortfalls + FC Hub moved to /static/js/portal_planning.js
// ══════════════════════════════════════════════════════════════
// FORKLIFTS (Station Leader Hub → Forklifts tab)
// ══════════════════════════════════════════════════════════════
let _flkRows=[], _oilRows=[];
const _OIL_BADGE_BG={PENDING:'warning text-dark',FULFILLED:'success',CANCELLED:'dark'};
function _flkStatBadge(s){
  const m={active:['success','Active'],maintenance:['warning text-dark','Maintenance'],retired:['secondary','Retired']};
  const x=m[s]||['secondary',s]; return `<span class="badge bg-${x[0]}">${x[1]}</span>`;
}

async function flkLoad(){
  try{
    _flkRows = await api('/api/forklifts');
    if(!Array.isArray(_flkRows)) _flkRows=[];
    const tb=document.getElementById('flk-tbody');
    if(!_flkRows.length){
      tb.innerHTML='<tr><td colspan="8" class="text-center text-muted py-3">No forklifts registered yet.</td></tr>';
    }else{
      tb.innerHTML=_flkRows.map(f=>`<tr>
        <td class="small fw-semibold">${f.code}${f.open_oil_requests?` <span class="badge bg-warning text-dark" title="Open oil request(s)"><i class="bi bi-droplet me-1"></i>${f.open_oil_requests}</span>`:''}</td>
        <td class="small">${f.name||'—'}</td>
        <td class="small">${f.dept||'—'}${f.production_line?' / '+f.production_line:''}</td>
        <td class="small">${f.model||'—'}</td>
        <td class="small">${f.fuel_type||'—'}</td>
        <td class="text-end small">${f.hours_meter?Number(f.hours_meter).toLocaleString():'—'}</td>
        <td>${_flkStatBadge(f.status)}</td>
        <td class="text-end" style="white-space:nowrap">
          <button class="btn btn-xs btn-outline-info text-info" title="Request oil" onclick="oilOpenNew(${f.id})"><i class="bi bi-droplet"></i></button>
          <button class="btn btn-xs btn-outline-secondary" title="Edit" onclick='flkEdit(${JSON.stringify(f).replace(/'/g,"&apos;")})'><i class="bi bi-pencil"></i></button>
          <button class="btn btn-xs btn-outline-danger" title="Retire" onclick="flkDelete(${f.id})"><i class="bi bi-trash"></i></button>
        </td>
      </tr>`).join('');
    }
    // refresh oil request forklift dropdown
    const sel=document.getElementById('oil-flk');
    sel.innerHTML=_flkRows.filter(f=>f.status==='active').map(f=>
      `<option value="${f.id}">${f.code} — ${f.name||''} (${f.dept||'—'}${f.production_line?' / '+f.production_line:''})</option>`).join('');
    flkUpdateBadge();
  }catch(e){
    document.getElementById('flk-tbody').innerHTML=`<tr><td colspan="8" class="text-danger small p-3">${e.message||e}</td></tr>`;
  }
}

function flkOpenNew(){
  document.getElementById('flk-modal-title').textContent='Register Forklift';
  ['flk-id','flk-code','flk-name','flk-line','flk-model','flk-hours','flk-notes'].forEach(id=>document.getElementById(id).value='');
  document.getElementById('flk-dept').value='';
  document.getElementById('flk-status').value='active';
  document.getElementById('flk-fuel').value='diesel';
  new bootstrap.Modal(document.getElementById('flkModal')).show();
}
function flkEdit(f){
  document.getElementById('flk-modal-title').textContent='Edit Forklift';
  document.getElementById('flk-id').value=f.id;
  document.getElementById('flk-code').value=f.code||'';
  document.getElementById('flk-name').value=f.name||'';
  document.getElementById('flk-dept').value=f.dept||'';
  document.getElementById('flk-line').value=f.production_line||'';
  document.getElementById('flk-model').value=f.model||'';
  document.getElementById('flk-fuel').value=f.fuel_type||'diesel';
  document.getElementById('flk-status').value=f.status||'active';
  document.getElementById('flk-hours').value=f.hours_meter||'';
  document.getElementById('flk-notes').value=f.notes||'';
  new bootstrap.Modal(document.getElementById('flkModal')).show();
}
async function flkSubmit(){
  const body={
    id: Number(document.getElementById('flk-id').value)||null,
    code: document.getElementById('flk-code').value.trim(),
    name: document.getElementById('flk-name').value,
    dept: document.getElementById('flk-dept').value,
    production_line: document.getElementById('flk-line').value,
    model: document.getElementById('flk-model').value,
    fuel_type: document.getElementById('flk-fuel').value,
    status: document.getElementById('flk-status').value,
    hours_meter: Number(document.getElementById('flk-hours').value||0),
    notes: document.getElementById('flk-notes').value,
  };
  if(!body.code){ alert('Code is required'); return; }
  try{
    await api('/api/forklifts','POST',body);
    bootstrap.Modal.getInstance(document.getElementById('flkModal'))?.hide();
    toast('Forklift saved');
    flkLoad();
  }catch(e){ alert('Save failed: '+(e.message||e)); }
}
async function flkDelete(id){
  if(!confirm('Retire this forklift? (If it has any oil requests it will be marked retired rather than deleted.)')) return;
  try{ await api('/api/forklifts/'+id,'DELETE'); flkLoad(); }
  catch(e){ alert('Delete failed: '+(e.message||e)); }
}

async function oilLoad(){
  const st=document.getElementById('oil-status-filter')?.value||'';
  try{
    _oilRows = await api('/api/forklifts/oil-requests'+(st?('?status='+st):''));
    if(!Array.isArray(_oilRows)) _oilRows=[];
    const tb=document.getElementById('oil-tbody');
    if(!_oilRows.length){
      tb.innerHTML='<tr><td colspan="6" class="text-center text-muted py-3">No oil requests.</td></tr>';
    }else{
      tb.innerHTML=_oilRows.map(r=>{
        const stat = `<span class="badge bg-${_OIL_BADGE_BG[r.status]||'secondary'}">${r.status}</span>`;
        const act = r.status==='PENDING'
          ? `<button class="btn btn-xs btn-success" title="Mark fulfilled" onclick="oilFulfill(${r.id})"><i class="bi bi-check2"></i></button>
             <button class="btn btn-xs btn-outline-secondary" title="Cancel" onclick="oilCancel(${r.id})"><i class="bi bi-x"></i></button>`
          : '';
        return `<tr>
          <td class="small fw-semibold">${r.forklift_code}<br><span class="text-muted">${r.forklift_dept||''}${r.forklift_line?' / '+r.forklift_line:''}</span></td>
          <td class="small">${r.oil_type}</td>
          <td class="text-end">${Number(r.qty_litres).toFixed(1)} L</td>
          <td class="small">${(r.requested_at||'').slice(0,16).replace('T',' ')}<br><span class="text-muted">${r.requested_by||''}</span></td>
          <td>${stat}</td>
          <td class="text-end" style="white-space:nowrap">${act}</td>
        </tr>`;
      }).join('');
    }
    flkUpdateBadge();
  }catch(e){
    document.getElementById('oil-tbody').innerHTML=`<tr><td colspan="6" class="text-danger small p-3">${e.message||e}</td></tr>`;
  }
}

async function oilOpenNew(prefillId){
  document.getElementById('oil-flk').value = prefillId || (_flkRows[0]?.id || '');
  document.getElementById('oil-type').value='hydraulic';
  document.getElementById('oil-qty').value='';
  document.getElementById('oil-notes').value='';
  document.getElementById('oil-prio-normal').checked = true;
  // Fetch & display the warehouse refueling window
  try{
    const cfg = await api('/api/forklifts/refuel-config');
    if(cfg){
      document.getElementById('oil-window-hint').innerHTML =
        `<i class="bi bi-info-circle me-1"></i>${cfg.description}`;
    }
  }catch{}
  oilUpdateEtaHint();
  // Live update when priority changes
  document.querySelectorAll('input[name="oil-prio"]').forEach(el => el.onchange = oilUpdateEtaHint);
  new bootstrap.Modal(document.getElementById('oilModal')).show();
}

function oilUpdateEtaHint(){
  const prio = document.querySelector('input[name="oil-prio"]:checked')?.value || 'NORMAL';
  const hint = document.getElementById('oil-eta-hint');
  if(prio === 'URGENT'){
    hint.innerHTML = '<span class="text-danger fw-semibold"><i class="bi bi-lightning-fill me-1"></i>Will appear at top of WH queue and be fulfilled as soon as possible.</span>';
    return;
  }
  // Compute today vs tomorrow based on 10:30 cutoff
  const now = new Date();
  const cutoff = new Date(); cutoff.setHours(10,30,0,0);
  const slot = new Date(); slot.setHours(11,0,0,0);
  let when;
  if(now > cutoff){
    slot.setDate(slot.getDate()+1);
    when = `tomorrow ${slot.toISOString().slice(0,10)} 11:00`;
  }else{
    when = `today 11:00`;
  }
  hint.innerHTML = `<i class="bi bi-calendar-check me-1"></i>Scheduled for the <b>${when}</b> refuel slot. Pick URGENT if you can't wait.`;
}

async function oilSubmit(){
  const body={
    forklift_id: Number(document.getElementById('oil-flk').value),
    oil_type: document.getElementById('oil-type').value,
    qty_litres: Number(document.getElementById('oil-qty').value||0),
    priority: document.querySelector('input[name="oil-prio"]:checked')?.value || 'NORMAL',
    notes: document.getElementById('oil-notes').value,
  };
  if(!body.forklift_id || body.qty_litres<=0){ alert('Forklift and positive litres required'); return; }
  try{
    const r = await api('/api/forklifts/oil-requests','POST',body);
    bootstrap.Modal.getInstance(document.getElementById('oilModal'))?.hide();
    const sched = (r?.scheduled_for||'').slice(0,16).replace('T',' ');
    toast(`Oil request submitted (${body.priority}${sched?', scheduled '+sched:''})`, body.priority==='URGENT'?'warning':'success');
    oilLoad(); flkLoad();
  }catch(e){ alert('Submit failed: '+(e.message||e)); }
}
async function oilFulfill(id){
  const q=prompt('Fulfilled litres? (leave blank to use the requested qty)','');
  try{
    await api(`/api/forklifts/oil-requests/${id}`,'PATCH',{
      status:'FULFILLED', fulfilled_qty: q?Number(q):null});
    oilLoad(); flkLoad();
  }catch(e){ alert(e.message||e); }
}
async function oilCancel(id){
  if(!confirm('Cancel this oil request?')) return;
  try{ await api(`/api/forklifts/oil-requests/${id}`,'PATCH',{status:'CANCELLED'}); oilLoad(); flkLoad(); }
  catch(e){ alert(e.message||e); }
}

function flkUpdateBadge(){
  const n=(_oilRows||[]).filter(r=>r.status==='PENDING').length;
  const b=document.getElementById('slh-forklift-badge');
  if(b){ b.textContent=n; b.classList.toggle('d-none', n===0); }
}


// Forklift Refueling (warehouse) moved to /static/js/portal_warehouse.js

// Forklift Dashboard + Oil drum stock moved to /static/js/portal_warehouse.js

// Forklift Report (managerial reports & AI) moved to /static/js/portal_planning.js


// ════════════════════════════════════════════════════════════
// FC Material Check
// ════════════════════════════════════════════════════════════
// Kanban (prod-flow) moved to /static/js/portal_planning.js
// ══════════════════════════════════════════════════════════
// FC — MATERIAL CHECK
// ══════════════════════════════════════════════════════════
let _fcCurrentTab = 'prep';

function fcSwitchTab(tab){
  _fcCurrentTab = tab;
  ['prep','stock'].forEach(t=>{
    const tabEl  = document.getElementById(`fc-tab-${t}`);
    const paneEl = document.getElementById(`fc-pane-${t}`);
    if(tabEl)  tabEl.classList.toggle('active', t===tab);
    if(paneEl) paneEl.classList.toggle('d-none', t!==tab);
  });
  if(tab==='stock') fcLoadStock();
}

function fcRefresh(){
  // Inside FC Hub: load whichever pane the outer tabs currently show.
  const outer = (typeof _fcHubTab !== 'undefined') ? _fcHubTab : null;
  if(outer === 'inventory'){ fciSubReload(); }
  else if(outer === 'check'){ loadFcPage(); }
  else {
    if(typeof loadFcPage === 'function') loadFcPage();
    if(typeof fcLoadStock === 'function') fcLoadStock();
  }
}

// FC Inventory sub-tabs (Stock / Requests / Movements)
let _fciSubTab = 'stock';
function fciSubSwitch(tab){
  _fciSubTab = tab;
  document.querySelectorAll('#fci-sub-tabs .nav-link').forEach(b =>
    b.classList.toggle('active', b.dataset.fciSub === tab));
  ['stock','requests','movements'].forEach(t => {
    const el = document.getElementById('fci-sub-pane-' + t);
    if(el) el.classList.toggle('d-none', t !== tab);
  });
  fciSubReload();
}
function fciSubReload(){
  // fcLoadStock() fetches the grid AND fills the transfer list, the
  // movement log, and the regrade log in one go, so a single call covers
  // all three sub-tabs. Sub-tabs just toggle visibility on existing data.
  if(typeof fcLoadStock === 'function') fcLoadStock();
}

let _fcBatches = [];
let _fcBatchGlue = {};   // batch_id -> glue_code (for the recipe filter)
async function loadFcPage(){
  _fcBatches = await api('/api/fc/batches').catch(()=>[]);
  // Glue code per batch so the leader can filter FC prep by recipe.
  _fcBatchGlue = {};
  await Promise.all(_fcBatches.map(async b => {
    try{ const gi = await api(`/api/batches/${b.id}/glue-info`); _fcBatchGlue[b.id]=(gi&&gi.glue_code)||''; }catch{}
  }));
  _fcPopulateBatchFilterOptions();
  renderFcBatchList();
}
function _fcPopulateBatchFilterOptions(){
  const custSel=document.getElementById('fc-bf-cust');
  if(custSel){
    const cur=custSel.value;
    const custs=[...new Set(_fcBatches.map(b=>b.customer).filter(Boolean))].sort();
    custSel.innerHTML='<option value="">All customers</option>'+custs.map(c=>`<option${c===cur?' selected':''}>${c}</option>`).join('');
  }
  const recSel=document.getElementById('fc-bf-recipe');
  if(recSel){
    const recs=[...new Set(Object.values(_fcBatchGlue).filter(Boolean))].sort();
    recSel.classList.toggle('d-none', recs.length===0);
    const cur=recSel.value;
    recSel.innerHTML='<option value="">All glue codes</option>'+recs.map(r=>`<option${r===cur?' selected':''}>${r}</option>`).join('');
  }
}
function renderFcBatchList(){
  const el=document.getElementById('fc-batch-list');
  if(!el) return;
  if(!_fcBatches.length){
    el.innerHTML='<p class="text-muted small p-2">No batches currently at FC.</p>';
    const det=document.getElementById('fc-detail');
    if(det) det.innerHTML=`<div class="text-center text-muted py-5"><i class="bi bi-check-circle-fill text-success" style="font-size:2.5rem"></i><p class="mt-3 fw-bold">FC is clear — no batches awaiting prep.</p></div>`;
    return;
  }
  const q=(document.getElementById('fc-bf-search')?.value||'').toLowerCase().trim();
  const cust=document.getElementById('fc-bf-cust')?.value||'';
  const prio=document.getElementById('fc-bf-prio')?.value||'';
  const recipe=document.getElementById('fc-bf-recipe')?.value||'';
  const list=_fcBatches.filter(b=>{
    if(cust && b.customer!==cust) return false;
    if(prio && String(b.priority||2)!==prio) return false;
    if(recipe && (_fcBatchGlue[b.id]||'')!==recipe) return false;
    if(q){
      const hay=[b.batch_number,b.product_name,b.product_sku,b.po_number,b.customer].filter(Boolean).join(' ').toLowerCase();
      if(!hay.includes(q)) return false;
    }
    return true;
  });
  if(!list.length){ el.innerHTML='<p class="text-muted small p-2">No batches match the filters.</p>'; return; }
  el.innerHTML=list.map(b=>`
    <div class="fc-batch-card" onclick="loadFcCheck(${b.prod_order_id},this)">
      <div class="d-flex justify-content-between mb-1">
        <span class="fw-bold small">${b.batch_number||'B#'+b.id}</span>
        ${lineBadge(b.production_line)}
      </div>
      <div style="font-size:.78rem;font-weight:600">${b.product_name||''}</div>
      <div class="text-muted" style="font-size:.72rem">${b.po_number||''} &mdash; ${b.customer||''}</div>
      <div class="d-flex justify-content-between mt-1">
        <small class="text-muted">${fmt(b.quantity)} pallet${b.quantity!=1?'s':''} &mdash; ${fmt((b.quantity||0)*(b.pallet_qty||1))} pcs</small>
        <small class="text-muted">Order: ${fmt(b.order_qty)} plt / ${fmt((b.order_qty||0)*(b.pallet_qty||1))} pcs</small>
      </div>
    </div>`).join('');
}

// ── FC Inventory tab ──────────────────────────────────────────
let _fcStockMats = [];

let _fcTypeFilter = 'all'; // 'all' | 'veneer_sheet' | 'core_board'

function fcSetTypeFilter(t){
  _fcTypeFilter = t;
  document.querySelectorAll('#fc-type-filter button').forEach(b=>b.classList.toggle('active', b.dataset.fcType===t));
  fcRenderGrid();
}

function fcRenderGrid(){
  const mats = _fcStockMats || [];
  const grid = document.getElementById('fc-stock-grid');
  if(!grid) return;
  // Only items physically present at FC station (fc_stock > 0)
  const inFc = mats.filter(m => (m.fc_stock || 0) > 0);
  if(!inFc.length){
    grid.innerHTML = '<div class="col-12 text-muted text-center py-4"><i class="bi bi-inbox me-2"></i>No materials currently at FC station. Use <b>Request from WH</b> to bring veneers or boards in.</div>';
    const labelEl0 = document.getElementById('fc-stock-count-label');
    if(labelEl0) labelEl0.innerHTML = '<b>0</b> at FC';
    return;
  }
  // Apply user filters
  const q = (document.getElementById('fc-stock-search')?.value || '').toLowerCase().trim();
  const filtered = inFc.filter(m => {
    if(_fcTypeFilter !== 'all' && m.type !== _fcTypeFilter) return false;
    if(q && !((m.code||'').toLowerCase().includes(q) || (m.name||'').toLowerCase().includes(q))) return false;
    return true;
  });
  // Update count label
  const fcVeneers = inFc.filter(m=>m.type==='veneer_sheet').length;
  const fcBoards = inFc.filter(m=>m.type==='core_board').length;
  const labelEl = document.getElementById('fc-stock-count-label');
  if(labelEl) labelEl.innerHTML = `<b>${filtered.length}</b> shown · ${fcVeneers} veneer${fcVeneers!==1?'s':''} · ${fcBoards} board${fcBoards!==1?'s':''} at FC`;

  if(!filtered.length){
    grid.innerHTML = '<div class="col-12 text-muted text-center py-4">No materials at FC match the current filters.</div>';
    return;
  }
  const byType = {veneer_sheet: filtered.filter(m=>m.type==='veneer_sheet'),
                  core_board: filtered.filter(m=>m.type==='core_board')};
  let html = '';
  [['veneer_sheet','Veneers','bi-layers','primary'],['core_board','Core Boards','bi-grid-3x3','secondary']].forEach(([type,label,icon,color])=>{
    const items = byType[type] || [];
    if(!items.length) return;
    html += `<div class="col-12"><div class="fw-semibold small text-${color} mb-2 mt-2"><i class="bi ${icon} me-1"></i>${label} <span class="badge bg-${color} ms-1">${items.length}</span></div><div class="row g-2">`;
    items.forEach(m=>{
      const fcPct = m.wh_stock>0 ? Math.min(100,Math.round(m.fc_stock/(m.fc_stock+m.wh_stock)*100)) : (m.fc_stock>0?100:0);
      const fcLow = m.fc_stock <= m.reorder_point && m.reorder_point > 0;
      html += `<div class="col-md-4 col-lg-3">
        <div class="card h-100 border-${m.fc_stock>0?color:'light'}" style="border-width:${m.fc_stock>0?'2px':'1px'}">
          <div class="card-body py-2 px-3">
            <div class="d-flex justify-content-between align-items-start">
              <div>
                <div class="fw-semibold small text-truncate" style="max-width:160px" title="${m.name}">${m.name}</div>
                <code class="text-muted" style="font-size:.65rem">${m.code||'—'}</code>
              </div>
              <span class="badge ${m.fc_stock>0?'bg-'+color:'bg-light text-dark border'} ms-1" style="font-size:.65rem">
                ${fmt(m.fc_stock)} ${m.unit}
              </span>
            </div>
            <div class="mt-2">
              <div class="d-flex justify-content-between small mb-1">
                <span class="text-muted">FC Stock</span>
                <span class="${fcLow?'text-danger fw-bold':''}">${fmt(m.fc_stock)} ${m.unit}${fcLow?' ⚠':''}</span>
              </div>
              <div class="progress mb-1" style="height:4px" title="FC vs WH split">
                <div class="progress-bar bg-${color}" style="width:${fcPct}%"></div>
              </div>
              <div class="d-flex justify-content-between align-items-center small text-muted mt-1">
                <span>WH: ${fmt(m.wh_stock)} ${m.unit}</span>
                <div class="d-flex gap-1 flex-wrap">
                  ${m.type==='veneer_sheet' && m.fc_stock>0 ? `
                  <button class="btn btn-outline-warning btn-xs py-0 px-1" style="font-size:.6rem;line-height:1.3"
                    title="Re-grade within FC station"
                    onclick="fcOpenRegradeModal(${m.id},'prep')">Regrade</button>` : ''}
                  ${m.type==='core_board' && m.fc_stock>0 ? `
                  <button class="btn btn-outline-warning btn-xs py-0 px-1" style="font-size:.6rem;line-height:1.3"
                    title="Resize/cut this board into another board code"
                    onclick="fcOpenResizeModal(${m.id})">Resize</button>` : ''}
                  ${m.fc_stock>0 ? `
                  <button class="btn btn-outline-danger btn-xs py-0 px-1" style="font-size:.6rem;line-height:1.3"
                    title="Flag as non-conforming (rejected when sorting)"
                    onclick="ncgFlagOpen(${m.id}, fcLoadStock)"><i class="bi bi-exclamation-octagon"></i></button>` : ''}
                  ${m.fc_stock>0 ? `
                  <button class="btn btn-outline-danger btn-xs py-0 px-1" style="font-size:.6rem;line-height:1.3"
                    title="Request WH to pick up and return to WH stock"
                    onclick="fcOpenReturnModal(${m.id})">↑WH</button>` : ''}
                  <button class="btn btn-outline-${color} btn-xs py-0 px-1" style="font-size:.6rem;line-height:1.3"
                    onclick="fcOpenTransferModal(${m.id})">↓Req</button>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>`;
    });
    html += '</div></div>';
  });
  grid.innerHTML = html;
}

async function fcLoadStock(){
  const [mats, transfers] = await Promise.all([
    api('/api/fc/stock').catch(()=>[]),
    api('/api/fc/transfer-requests').catch(()=>[]),
  ]);
  _fcStockMats = mats;

  // Badge on tab
  const fcCount = mats.filter(m=>m.fc_stock>0).length;
  const badgeEl = document.getElementById('fc-stock-badge');
  if(badgeEl) badgeEl.textContent = fcCount;

  fcRenderGrid();

  // Also load regrade log + resize log + unified movement log
  fcLoadRegradeLog();
  fcLoadResizeLog();
  fcLoadMovements();

  // Transfer requests
  const list = document.getElementById('fc-transfer-list');
  const active = transfers.filter(t=>['PENDING','PARTIAL'].includes(t.status));
  if(!active.length){
    list.innerHTML='<div class="text-muted small text-center py-2">No pending transfer requests.</div>';
  } else {
    const statusColor={PENDING:'warning',PARTIAL:'primary',FULFILLED:'success',CANCELLED:'secondary'};
    list.innerHTML=active.map(t=>{
      const remaining=t.qty_requested-t.qty_fulfilled;
      const pct=Math.round((t.qty_fulfilled/t.qty_requested)*100);
      return `<div class="card mb-2">
        <div class="card-body py-2 px-3">
          <div class="d-flex align-items-start gap-3 flex-wrap">
            <div style="flex:1;min-width:180px">
              <code class="small text-warning">${t.request_id}</code>
              <span class="badge bg-${statusColor[t.status]||'secondary'} ms-2 small">${t.status}</span>
              <div class="fw-semibold small">${t.material_name||'—'} <span class="text-muted">(${t.unit||''})</span></div>
              <div class="small text-muted">${t.notes||''}</div>
            </div>
            <div style="min-width:140px">
              <div class="d-flex justify-content-between small mb-1">
                <span>Transferred: ${t.qty_fulfilled} / ${t.qty_requested} ${t.unit||''}</span>
                <span>${pct}%</span>
              </div>
              <div class="progress" style="height:5px">
                <div class="progress-bar bg-success" style="width:${pct}%"></div>
              </div>
            </div>
            ${t.status==='PENDING'?`<button class="btn btn-xs btn-outline-danger py-0 px-1" onclick="fcCancelTransfer('${t.request_id}')"><i class="bi bi-x"></i> Cancel</button>`:''}
          </div>
        </div>
      </div>`;
    }).join('');
  }
}

function _fctrBuildOpts(mats){
  return '<option value="">— Select veneer or board —</option>' +
    mats.map(m=>`<option value="${m.id}" data-unit="${m.unit}" data-wh="${m.wh_stock}" data-cost="${m.unit_cost}">`+
      `[${m.type==='veneer_sheet'?'Veneer':'Board'}] ${m.name}${m.code?' ('+m.code+')':''} — WH: ${fmt(m.wh_stock)} ${m.unit}`+
    `</option>`).join('');
}
function fctrFilterMats(q){
  const term = (q||'').trim().toLowerCase();
  const mats = term
    ? _fcStockMats.filter(m=>(m.code||'').toLowerCase().includes(term)||(m.name||'').toLowerCase().includes(term))
    : _fcStockMats;
  document.getElementById('fctr-material-id').innerHTML = _fctrBuildOpts(mats);
  fctrOnMatSelect();
}
async function fcOpenTransferModal(preselectedId){
  if(!_fcStockMats.length) _fcStockMats = await api('/api/fc/stock').catch(()=>[]);
  document.getElementById('fctr-mat-search').value = '';
  const sel = document.getElementById('fctr-material-id');
  sel.innerHTML = _fctrBuildOpts(_fcStockMats);
  if(preselectedId){
    sel.value = preselectedId;
    fctrOnMatSelect();
  } else {
    document.getElementById('fctr-wh-stock-note').textContent='';
    document.getElementById('fctr-unit-label').textContent='unit';
    document.getElementById('fctr-cost-note').textContent='';
  }
  document.getElementById('fctr-qty').value='';
  document.getElementById('fctr-notes').value='';
  bootstrap.Modal.getOrCreateInstance(document.getElementById('fcTransferModal')).show();
}

function fctrOnMatSelect(){
  const sel = document.getElementById('fctr-material-id');
  const opt = sel.options[sel.selectedIndex];
  const unit = opt?.dataset?.unit||'unit';
  const wh = parseFloat(opt?.dataset?.wh||0);
  document.getElementById('fctr-unit-label').textContent = unit;
  document.getElementById('fctr-wh-stock-note').textContent = opt?.value ? `WH available: ${fmt(wh)} ${unit}` : '';
  fctrOnQtyInput();
}

function fctrOnQtyInput(){
  const sel = document.getElementById('fctr-material-id');
  const opt = sel.options[sel.selectedIndex];
  const qty = parseFloat(document.getElementById('fctr-qty').value)||0;
  const cost = parseFloat(opt?.dataset?.cost||0);
  document.getElementById('fctr-cost-note').textContent =
    qty>0&&cost>0 ? `Est. value: ฿${(qty*cost).toFixed(2)}` : '';
}

async function fctrSubmit(){
  const matId = parseInt(document.getElementById('fctr-material-id').value);
  const qty = parseFloat(document.getElementById('fctr-qty').value)||0;
  if(!matId||qty<=0){toast('Select a material and enter quantity','warning');return;}
  const body = {material_id:matId, qty_requested:qty,
    notes:document.getElementById('fctr-notes').value||null,
    priority:parseInt(document.getElementById('fctr-priority')?.value)||2,
    needed_by:document.getElementById('fctr-needed-by')?.value||null,
    needed_time:document.getElementById('fctr-needed-time')?.value||null};
  try{
    await api('/api/fc/transfer-requests','POST',body);
    bootstrap.Modal.getInstance(document.getElementById('fcTransferModal')).hide();
    toast('Transfer request submitted to Warehouse');
    fcLoadStock();
  }catch(e){toast(e.message,'danger');}
}

async function fcCancelTransfer(rid){
  if(!confirm('Cancel this transfer request?')) return;
  try{
    await api(`/api/fc/transfer-requests/${rid}/cancel`,'PATCH');
    toast('Cancelled');
    fcLoadStock();
  }catch(e){toast(e.message,'danger');}
}

// ── Veneer Re-grade Modal (multi-line, searchable) ─────────────
// _rgrSrc: veneers physically at FC (fc_stock>0) — the valid re-grade sources.
// _rgrAll: every veneer in the system — the valid re-grade targets (any grade).
// _rgrSeq: monotonic row id so each line's controls have unique element ids.
let _rgrSrc = [];
let _rgrAll = [];
let _rgrSeq = 0;

function _rgrOpt(m){
  const wh = (m.wh_stock!=null ? m.wh_stock : (m.current_stock!=null ? m.current_stock : 0));
  const fc = m.fc_stock || 0;
  const label = `${m.species?m.species+' ':''}${m.grade?'['+m.grade+'] ':''}${m.name||''} (${m.code||''}) — FC:${fmt(fc)} WH:${fmt(wh)}`;
  return `<option value="${m.id}" data-unit="${m.unit||'pcs'}" data-fc="${fc}" data-wh="${wh}">${label}</option>`;
}
function _rgrMatch(m, term){
  if(!term) return true;
  const s=[m.code,m.name,m.species,m.grade,m.matching,m.cut_type].filter(Boolean).join(' ').toLowerCase();
  return s.includes(term.toLowerCase());
}
// (Re)build a row's source/target <select>, filtered by its search box, keeping
// the current selection when it still matches the filter.
function rgrRenderSelect(idx, which, term){
  const sel = document.getElementById(`rgr-${which}-${idx}`);
  if(!sel) return;
  const list = (which==='from' ? _rgrSrc : _rgrAll).filter(m=>_rgrMatch(m, term||''));
  const cur = sel.value;
  sel.innerHTML = `<option value="">— Select ${which==='from'?'source':'target'} veneer —</option>`
    + list.map(_rgrOpt).join('');
  if(cur && list.some(m=>String(m.id)===cur)) sel.value = cur;
}
function rgrFilter(idx, which, q){
  rgrRenderSelect(idx, which, q);
  rgrLineChange(idx);
}

/**
 * Open the multi-line re-grade modal.
 * @param {number|null} preselectedId - veneer id to pre-select as the first row's source
 * @param {string} mode               - kept for call-site compatibility (regrade is always FC→FC)
 */
async function fcOpenRegradeModal(preselectedId=null, mode='prep'){
  // Sources = veneers physically at FC; targets = every veneer (any grade).
  _fcStockMats = await api('/api/fc/stock').catch(()=>_fcStockMats||[]);
  _rgrSrc = _fcStockMats.filter(m=>m.type==='veneer_sheet' && (m.fc_stock||0)>0);
  _rgrAll = await api('/api/materials?type=veneer_sheet').catch(()=>_rgrSrc);

  document.getElementById('rgr-lines').innerHTML = '';
  _rgrSeq = 0;
  rgrAddLine(preselectedId);
  document.getElementById('rgr-notes').value = '';
  document.getElementById('rgr-summary').style.display = 'none';
  bootstrap.Modal.getOrCreateInstance(document.getElementById('fcRegradeModal')).show();
}

// Append one re-grade row: source + target, each with its own search box, a qty,
// and a remove button.
function rgrAddLine(preselectedSrcId){
  const idx = ++_rgrSeq;
  const div = document.createElement('div');
  div.className = 'rgr-line card mb-2'; div.dataset.idx = idx;
  div.innerHTML = `<div class="card-body py-2 px-2"><div class="row g-2 align-items-start">
    <div class="col-md-5">
      <input class="form-control form-control-sm mb-1" placeholder="Search source code / species…" oninput="rgrFilter(${idx},'from',this.value)" autocomplete="off">
      <select class="form-select form-select-sm" id="rgr-from-${idx}" onchange="rgrLineChange(${idx})"></select>
      <div class="small text-muted mt-1" id="rgr-from-stock-${idx}"></div>
    </div>
    <div class="col-md-5">
      <input class="form-control form-control-sm mb-1" placeholder="Search target code / species…" oninput="rgrFilter(${idx},'to',this.value)" autocomplete="off">
      <select class="form-select form-select-sm" id="rgr-to-${idx}" onchange="rgrLineChange(${idx})"></select>
      <div class="small text-muted mt-1" id="rgr-to-stock-${idx}"></div>
    </div>
    <div class="col-md-2">
      <div class="input-group input-group-sm">
        <input type="number" class="form-control" id="rgr-qty-${idx}" min="0.01" step="0.01" placeholder="qty" oninput="rgrUpdateSummary()">
        <span class="input-group-text px-1" id="rgr-qty-unit-${idx}" style="font-size:.7rem">pcs</span>
      </div>
      <button class="btn btn-sm btn-outline-danger mt-1 w-100 py-0" style="font-size:.7rem" onclick="rgrRemoveLine(${idx})" title="Remove row"><i class="bi bi-trash"></i></button>
    </div>
  </div></div>`;
  document.getElementById('rgr-lines').appendChild(div);
  rgrRenderSelect(idx,'from','');
  rgrRenderSelect(idx,'to','');
  if(preselectedSrcId){
    const s = document.getElementById(`rgr-from-${idx}`);
    if(s && _rgrSrc.some(m=>Number(m.id)===Number(preselectedSrcId))) s.value = preselectedSrcId;
  }
  rgrLineChange(idx);
}

function rgrRemoveLine(idx){
  const el = document.querySelector(`.rgr-line[data-idx="${idx}"]`);
  if(el) el.remove();
  if(!document.querySelectorAll('#rgr-lines .rgr-line').length) rgrAddLine();
  rgrUpdateSummary();
}

// Refresh a row's stock notes + qty unit from its current selections.
function rgrLineChange(idx){
  const fs = document.getElementById(`rgr-from-${idx}`);
  const ts = document.getElementById(`rgr-to-${idx}`);
  if(!fs || !ts) return;
  const fo = fs.options[fs.selectedIndex];
  const to = ts.options[ts.selectedIndex];
  const unit = fo?.dataset?.unit || 'pcs';
  const uEl = document.getElementById(`rgr-qty-unit-${idx}`); if(uEl) uEl.textContent = unit;
  const fNote = document.getElementById(`rgr-from-stock-${idx}`);
  const tNote = document.getElementById(`rgr-to-stock-${idx}`);
  if(fNote) fNote.textContent = fo?.value ? `FC: ${fmt(fo.dataset.fc||0)} | WH: ${fmt(fo.dataset.wh||0)} ${unit}` : '';
  if(tNote) tNote.textContent = to?.value ? `Current FC: ${fmt(to.dataset.fc||0)} ${to.dataset.unit||'pcs'}` : '';
  rgrUpdateSummary();
}

// Collect every row's current values (for the summary + submit).
function _rgrCollect(){
  const out = [];
  document.querySelectorAll('#rgr-lines .rgr-line').forEach(l=>{
    const idx = l.dataset.idx;
    const fs = document.getElementById(`rgr-from-${idx}`);
    const ts = document.getElementById(`rgr-to-${idx}`);
    if(!fs || !ts) return;
    const fo = fs.options[fs.selectedIndex], to = ts.options[ts.selectedIndex];
    out.push({
      idx,
      from:   parseInt(fs.value)||0,
      target: parseInt(ts.value)||0,
      qty:    parseFloat(document.getElementById(`rgr-qty-${idx}`).value)||0,
      fromName: (fo?.text||'').split('—')[0].trim(),
      toName:   (to?.text||'').split('—')[0].trim(),
    });
  });
  return out;
}

function rgrUpdateSummary(){
  const parts = _rgrCollect()
    .filter(r=>r.from && r.target && r.qty>0 && r.from!==r.target)
    .map(r=>`<div><span class="text-danger">−${fmt(r.qty)}</span> ${r.fromName} &nbsp;→&nbsp; <span class="text-success">+${fmt(r.qty)}</span> ${r.toName} <span class="text-muted">(within FC)</span></div>`);
  const sumEl  = document.getElementById('rgr-summary');
  const sumTxt = document.getElementById('rgr-summary-text');
  if(parts.length){ sumEl.style.display=''; sumTxt.innerHTML = parts.join(''); }
  else sumEl.style.display='none';
}

async function rgrSubmit(){
  const notes = document.getElementById('rgr-notes').value || null;
  // Drop fully-blank rows; validate the rest.
  const rows = _rgrCollect().filter(r=>r.from || r.target || r.qty);
  if(!rows.length){ toast('Add at least one re-grade row','warning'); return; }
  for(const r of rows){
    if(!r.from || !r.target || r.qty<=0){ toast('Each row needs a source, target and quantity','warning'); return; }
    if(r.from===r.target){ toast('Source and target must differ in every row','warning'); return; }
  }
  let ok=0; const fails=[];
  for(const r of rows){
    try{
      await api('/api/fc/regrade','POST',{from_material_id:r.from, to_material_id:r.target, qty:r.qty, notes});
      ok++;
    }catch(e){ fails.push(`${r.fromName}→${r.toName}: ${e.message||e}`); }
  }
  if(ok){
    toast(`${ok} re-grade${ok>1?'s':''} recorded${fails.length?` · ${fails.length} failed`:''} (WH price unchanged)`,
          fails.length?'warning':'success');
    bootstrap.Modal.getInstance(document.getElementById('fcRegradeModal')).hide();
    fcLoadStock();
  } else {
    toast('Re-grade failed: '+(fails[0]||'unknown error'),'danger');
  }
}

async function fcLoadRegradeLog(){
  const log = await api('/api/fc/regrade-log?limit=20').catch(()=>[]);
  const el = document.getElementById('fc-regrade-log');
  if(!el) return;
  if(!log.length){
    el.innerHTML='<div class="text-muted small text-center py-2">No re-grade records yet.</div>';
    return;
  }
  const locLabel = l => l==='fc_station'?'FC':'WH';
  el.innerHTML = `<div class="table-responsive"><table class="table table-sm table-hover mb-0" style="font-size:.78rem">
    <thead class="table-light"><tr>
      <th>Record</th><th>From</th><th>To</th><th class="text-end">Qty</th><th>Route</th><th>By</th><th>Date</th>
    </tr></thead>
    <tbody>
    ${log.map(r=>`<tr>
      <td><code style="font-size:.7rem">${r.record_id}</code></td>
      <td>
        <span class="text-danger fw-semibold">${r.from_species||''} ${r.from_grade?'['+r.from_grade+']':''}</span>
        <br><span class="text-muted" style="font-size:.7rem">${r.from_material_name||''}</span>
      </td>
      <td>
        <span class="text-success fw-semibold">${r.to_species||''} ${r.to_grade?'['+r.to_grade+']':''}</span>
        <br><span class="text-muted" style="font-size:.7rem">${r.to_material_name||''}</span>
      </td>
      <td class="text-end fw-bold">${fmt(r.qty)}</td>
      <td><span class="badge bg-secondary" style="font-size:.6rem">${locLabel(r.from_location)}→${locLabel(r.to_location)}</span></td>
      <td class="small text-muted">${r.graded_by_name||r.graded_by||'—'}</td>
      <td class="small text-muted">${(r.created_at||'').slice(0,10)}</td>
    </tr>`).join('')}
    </tbody>
  </table></div>`;
}

// ── Board Resize Modal ─────────────────────────────────────────
// _rszAllBoards: cached full core-board list for the resize target dropdown
let _rszAllBoards = [];

/**
 * Open the board resize modal.
 * @param {number|null} preselectedId - material id to pre-select as source (from a card button)
 */
async function fcOpenResizeModal(preselectedId=null){
  // Refresh FC stock for accurate source options; fetch all boards for targets.
  _fcStockMats = await api('/api/fc/stock').catch(()=>_fcStockMats||[]);
  const fcBoards = _fcStockMats.filter(m=>m.type==='core_board' && (m.fc_stock||0)>0);
  _rszAllBoards = await api('/api/materials?type=core_board').catch(()=>fcBoards);

  const dims = m => [m.width_mm,m.length_mm].filter(Boolean).join('×') || '';
  const srcOpt = m => `<option value="${m.id}" data-fc="${m.fc_stock||0}" data-wh="${m.wh_stock||0}" data-unit="${m.unit||'pcs'}">`
    + `${m.name}${dims(m)?' '+dims(m):''} (${m.code||''}) — FC:${fmt(m.fc_stock||0)} WH:${fmt(m.wh_stock||0)}</option>`;
  const tgtOpt = m => {
    const wh = m.wh_stock??m.current_stock??0, fc = m.fc_stock??0;
    return `<option value="${m.id}" data-fc="${fc}" data-wh="${wh}" data-unit="${m.unit||'pcs'}">`
      + `${m.name}${dims(m)?' '+dims(m):''} (${m.code||''}) — FC:${fmt(fc)} WH:${fmt(wh)}</option>`;
  };

  document.getElementById('rsz-from-mat').innerHTML =
    '<option value="">— Select source board —</option>' + fcBoards.map(srcOpt).join('');
  document.getElementById('rsz-to-mat').innerHTML =
    '<option value="">— Select target board —</option>' + (_rszAllBoards.length?_rszAllBoards:fcBoards).map(tgtOpt).join('');

  if(preselectedId){ document.getElementById('rsz-from-mat').value = preselectedId; }
  document.getElementById('rsz-qty-in').value = '';
  document.getElementById('rsz-qty-out').value = '';
  document.getElementById('rsz-notes').value = '';
  document.getElementById('rsz-summary').style.display = 'none';
  document.getElementById('rsz-to-stock').textContent = '';
  rszOnFromChange();
  bootstrap.Modal.getOrCreateInstance(document.getElementById('fcResizeModal')).show();
}

function rszOnFromChange(){
  const sel = document.getElementById('rsz-from-mat');
  const opt = sel.options[sel.selectedIndex];
  const unit = opt?.dataset?.unit || 'pcs';
  document.getElementById('rsz-in-unit').textContent = unit;
  document.getElementById('rsz-from-stock').textContent = opt?.value
    ? `FC stock: ${fmt(opt.dataset.fc||0)} | WH: ${fmt(opt.dataset.wh||0)} ${unit}` : '';
  rszUpdateSummary();
}

function rszOnToChange(){
  const sel = document.getElementById('rsz-to-mat');
  const opt = sel.options[sel.selectedIndex];
  const unit = opt?.dataset?.unit || 'pcs';
  document.getElementById('rsz-out-unit').textContent = unit;
  document.getElementById('rsz-to-stock').textContent = opt?.value
    ? `Current FC stock: ${fmt(opt.dataset.fc||0)} ${unit}` : '';
  rszUpdateSummary();
}

function rszUpdateSummary(){
  const fromSel = document.getElementById('rsz-from-mat');
  const toSel   = document.getElementById('rsz-to-mat');
  const fromOpt = fromSel.options[fromSel.selectedIndex];
  const toOpt   = toSel.options[toSel.selectedIndex];
  const qtyIn   = parseFloat(document.getElementById('rsz-qty-in').value)||0;
  const qtyOut  = parseFloat(document.getElementById('rsz-qty-out').value)||0;
  const sumEl   = document.getElementById('rsz-summary');
  const sumTxt  = document.getElementById('rsz-summary-text');
  if(!fromOpt?.value || !toOpt?.value || !qtyIn || !qtyOut){ sumEl.style.display='none'; return; }
  sumEl.style.display='';
  const fromName = fromOpt.text?.split('—')[0]?.trim()||'?';
  const toName   = toOpt.text?.split('—')[0]?.trim()||'?';
  const fromUnit = fromOpt.dataset.unit||'pcs', toUnit = toOpt.dataset.unit||'pcs';
  sumTxt.innerHTML = `
    <span class="text-danger">−${fmt(qtyIn)} ${fromUnit} from <b>${fromName}</b> (FC)</span><br>
    <span class="text-success">+${fmt(qtyOut)} ${toUnit} to <b>${toName}</b> (FC)</span>`;
}

async function rszSubmit(){
  const fromId = parseInt(document.getElementById('rsz-from-mat').value)||0;
  const toId   = parseInt(document.getElementById('rsz-to-mat').value)||0;
  const qtyIn  = parseFloat(document.getElementById('rsz-qty-in').value)||0;
  const qtyOut = parseFloat(document.getElementById('rsz-qty-out').value)||0;
  const notes  = document.getElementById('rsz-notes').value;
  if(!fromId||!toId||qtyIn<=0||qtyOut<=0){ toast('Fill in all required fields','warning'); return; }
  if(fromId===toId){ toast('Source and target must be different boards','warning'); return; }
  try{
    const res = await api('/api/fc/resize','POST',{
      from_material_id:fromId, to_material_id:toId,
      qty_in:qtyIn, qty_out:qtyOut, notes:notes||null,
    });
    bootstrap.Modal.getInstance(document.getElementById('fcResizeModal')).hide();
    const cb=res&&res.to_unit_cost_before, ca=res&&res.to_unit_cost_after;
    const costMsg=(cb!=null&&ca!=null&&Number(cb)!==Number(ca))
      ? ` · target cost ฿${fmt(cb)}→฿${fmt(ca)} (weighted avg)` : '';
    toast(`Resize recorded — ${fmt(qtyIn)} in → ${fmt(qtyOut)} out${costMsg}`);
    fcLoadStock();
  }catch(e){ toast(e.message,'danger'); }
}

async function fcLoadResizeLog(){
  const log = await api('/api/fc/resize-log?limit=20').catch(()=>[]);
  const el = document.getElementById('fc-resize-log');
  if(!el) return;
  if(!log.length){
    el.innerHTML='<div class="text-muted small text-center py-2">No resize records yet.</div>';
    return;
  }
  el.innerHTML = `<div class="table-responsive"><table class="table table-sm table-hover mb-0" style="font-size:.78rem">
    <thead class="table-light"><tr>
      <th>Record</th><th>From</th><th>To</th><th class="text-end">In</th><th class="text-end">Out</th><th>By</th><th>Date</th>
    </tr></thead>
    <tbody>
    ${log.map(r=>`<tr>
      <td><code style="font-size:.7rem">${r.record_id}</code></td>
      <td><span class="text-danger fw-semibold">${r.from_material_code||''}</span><br><span class="text-muted" style="font-size:.7rem">${r.from_material_name||''}</span></td>
      <td><span class="text-success fw-semibold">${r.to_material_code||''}</span><br><span class="text-muted" style="font-size:.7rem">${r.to_material_name||''}</span></td>
      <td class="text-end fw-bold text-danger">−${fmt(r.qty_in)}</td>
      <td class="text-end fw-bold text-success">+${fmt(r.qty_out)}</td>
      <td class="small text-muted">${r.resized_by_name||r.resized_by||'—'}</td>
      <td class="small text-muted">${(r.created_at||'').slice(0,10)}</td>
    </tr>`).join('')}
    </tbody>
  </table></div>`;
}

// ── FC Daily Printable Report ──────────────────────────────────
// Reuses the shared SLH report helpers (_slhOpenPrint / _slhCompanyHeader /
// _SLH_REPORT_CSS / _slhEsc). Shows current FC department stock (veneers +
// boards, incl. any regraded/resized stock) plus today's FC activity.
async function fcPrintDailyReport(){
  let mats, mv;
  try{
    [mats, mv] = await Promise.all([
      api('/api/fc/stock').catch(()=>[]),
      api('/api/fc/movements?limit=200').catch(()=>[]),
    ]);
  }catch(e){ toast('Report failed: '+(e.message||e),'danger'); return; }

  const esc = _slhEsc;
  const today = new Date().toISOString().slice(0,10);
  const num = n => (Number(n)||0).toLocaleString(undefined,{maximumFractionDigits:2});
  const money = n => '฿'+(Number(n)||0).toLocaleString(undefined,{minimumFractionDigits:2,maximumFractionDigits:2});
  const dims = m => [m.width_mm,m.length_mm].filter(Boolean).join('×');

  const inFc = (mats||[]).filter(m=>(m.fc_stock||0)>0);
  const veneers = inFc.filter(m=>m.type==='veneer_sheet');
  const boards  = inFc.filter(m=>m.type==='core_board');

  // FC stock is valued at its FC cost basis (fc_unit_cost) — for veneers this is
  // the running average of all regrades; for anything without an FC basis it
  // falls back to the warehouse unit_cost.
  const fcCost = m => (m.fc_unit_cost!=null ? Number(m.fc_unit_cost) : (Number(m.unit_cost)||0));

  // ── Section 1: Veneers on hand ──
  let vTot=0, vVal=0;
  const vRows = veneers.map(m=>{
    const uc=fcCost(m); const val=(Number(m.fc_stock)||0)*uc; vTot+=Number(m.fc_stock)||0; vVal+=val;
    return `<tr>
      <td>${esc(m.code||'—')}</td><td>${esc(m.name||'')}</td>
      <td>${esc(m.species||'')}</td><td>${esc(m.grade||'')}</td>
      <td class="num">${num(m.fc_stock)}</td><td>${esc(m.unit||'')}</td>
      <td class="num">${money(uc)}</td><td class="num">${money(val)}</td></tr>`;
  }).join('');
  const vTbl = veneers.length
    ? `<table><thead><tr><th>Code</th><th>Name</th><th>Species</th><th>Grade</th>`+
      `<th class="num">FC Qty</th><th>Unit</th><th class="num">Unit Cost</th><th class="num">Value</th></tr></thead>`+
      `<tbody>${vRows}</tbody><tfoot><tr><td colspan="4">Total — ${veneers.length} veneer code(s)</td>`+
      `<td class="num">${num(vTot)}</td><td></td><td></td><td class="num">${money(vVal)}</td></tr></tfoot></table>`
    : `<div class="empty">No veneers currently at FC.</div>`;

  // ── Section 2: Boards on hand ──
  let bTot=0, bVal=0;
  const bRows = boards.map(m=>{
    const uc=fcCost(m); const val=(Number(m.fc_stock)||0)*uc; bTot+=Number(m.fc_stock)||0; bVal+=val;
    return `<tr>
      <td>${esc(m.code||'—')}</td><td>${esc(m.name||'')}</td>
      <td>${esc(dims(m))}</td>
      <td class="num">${num(m.fc_stock)}</td><td>${esc(m.unit||'')}</td>
      <td class="num">${money(uc)}</td><td class="num">${money(val)}</td></tr>`;
  }).join('');
  const bTbl = boards.length
    ? `<table><thead><tr><th>Code</th><th>Name</th><th>Dims (mm)</th>`+
      `<th class="num">FC Qty</th><th>Unit</th><th class="num">Unit Cost</th><th class="num">Value</th></tr></thead>`+
      `<tbody>${bRows}</tbody><tfoot><tr><td colspan="3">Total — ${boards.length} board code(s)</td>`+
      `<td class="num">${num(bTot)}</td><td></td><td></td><td class="num">${money(bVal)}</td></tr></tfoot></table>`
    : `<div class="empty">No boards currently at FC.</div>`;

  // ── Section 3: Today's FC activity ──
  // Internal re-grading is intentionally EXCLUDED — the report only needs what
  // enters/leaves FC and the final grade coming out, not the regrade churn.
  const kindLabel={TRANSFER_IN:'Transfer In (WH→FC)',RETURN_TO_WH:'Return to WH',
    RESIZE:'Resize',RELEASE_TO_LAM:'Released to Lam'};
  const todayMv = (mv||[]).filter(r=>(r.ts||'').slice(0,10)===today && r.kind!=='REGRADE');
  const aRows = todayMv.map(r=>`<tr>
      <td>${esc((r.ts||'').replace('T',' ').slice(11,16))}</td>
      <td>${esc(kindLabel[r.kind]||r.kind)}</td>
      <td>${esc(r.material_name||'')}${r.material_code?' <small>('+esc(r.material_code)+')</small>':''}</td>
      <td>${esc(r.from_loc||'')} → ${esc(r.to_loc||'')}</td>
      <td class="num">${num(r.qty)} ${esc(r.unit||'')}</td>
      <td>${esc(r.actor||r.requested_by||'')}</td>
      <td>${esc(r.notes||'')}</td></tr>`).join('');
  const aTbl = todayMv.length
    ? `<table><thead><tr><th>Time</th><th>Activity</th><th>Item</th><th>From → To</th>`+
      `<th class="num">Qty</th><th>By</th><th>Notes</th></tr></thead><tbody>${aRows}</tbody></table>`
    : `<div class="empty">No FC activity recorded today.</div>`;

  const body = `
    ${_slhCompanyHeader()}
    <h1>FC (Feed Center) Daily Report <small>รายงานประจำวัน — Feed Center</small></h1>
    <div class="meta"><b>Date:</b> ${esc(today)} &nbsp;·&nbsp; <b>Total FC value:</b> ${money(vVal+bVal)}</div>
    <h2>Veneers on hand <small>at FC station</small></h2>${vTbl}
    <h2>Core Boards on hand <small>at FC station</small></h2>${bTbl}
    <h2>Today's FC Activity <small>transfers in · resizes · releases / returns out</small></h2>${aTbl}
    <div class="sign">
      <div class="box"><div class="line">FC — ลงชื่อ / วันที่</div></div>
      <div class="box"><div class="line">ผู้ควบคุม — ลงชื่อ / วันที่</div></div>
    </div>
    <div class="foot">Generated by PVWood ERP — ${esc(new Date().toLocaleString())}</div>`;

  _slhOpenPrint(body, `${today}_FC_daily_stock`);
}

async function fcLoadMovements(){
  const el=document.getElementById('fc-movement-log');
  if(!el) return;
  const kind=document.getElementById('fc-mvmt-filter')?.value||'';
  const matType=document.getElementById('fc-mvmt-type')?.value||'';
  const q=matType?`?material_type=${matType}&limit=80`:'?limit=80';
  let rows=await api('/api/fc/movements'+q).catch(()=>[]);
  if(kind) rows=rows.filter(r=>r.kind===kind);
  if(!rows.length){
    el.innerHTML='<div class="text-muted small text-center py-3">No FC movements yet matching filters.</div>';
    return;
  }
  // Color/icon per kind
  const meta={
    TRANSFER_IN:   {icon:'bi-box-arrow-in-down', color:'success', label:'Transfer In',     dir:'WH → FC'},
    RETURN_TO_WH:  {icon:'bi-box-arrow-up',      color:'danger',  label:'Return to WH',    dir:'FC → WH'},
    REGRADE:       {icon:'bi-arrow-left-right',  color:'warning', label:'Regrade',         dir:'FC ⇄ FC'},
    RESIZE:        {icon:'bi-scissors',          color:'warning', label:'Resize',          dir:'FC ✂ FC'},
    RELEASE_TO_LAM:{icon:'bi-arrow-right-circle',color:'primary', label:'Released to Lam', dir:'FC → Laminating'},
  };
  const typeBadge=t=>{
    if(t==='veneer_sheet') return '<span class="badge bg-success-subtle text-success border border-success" style="font-size:.6rem">Veneer</span>';
    if(t==='core_board') return '<span class="badge bg-secondary-subtle text-secondary border border-secondary" style="font-size:.6rem">Board</span>';
    if(t==='batch') return '<span class="badge bg-info-subtle text-info border border-info" style="font-size:.6rem">Batch</span>';
    return '';
  };
  el.innerHTML=`<div class="table-responsive"><table class="table table-sm table-hover mb-0" style="font-size:.78rem">
    <thead class="table-light"><tr>
      <th style="width:130px">When</th>
      <th style="width:140px">Kind</th>
      <th>Material / Batch</th>
      <th style="width:80px">Type</th>
      <th class="text-end" style="width:100px">Qty</th>
      <th style="width:140px">Direction</th>
      <th style="width:120px">By</th>
      <th>Notes</th>
    </tr></thead>
    <tbody>
    ${rows.map(r=>{
      const m=meta[r.kind]||{icon:'bi-circle',color:'secondary',label:r.kind,dir:''};
      const ts=(r.ts||'').replace('T',' ').slice(0,16);
      return `<tr>
        <td class="small text-muted">${ts}</td>
        <td><i class="bi ${m.icon} text-${m.color} me-1"></i><span class="badge bg-${m.color}-subtle text-${m.color} border border-${m.color}" style="font-size:.65rem">${m.label}</span></td>
        <td>
          <div class="fw-semibold small text-truncate" style="max-width:300px" title="${(r.material_name||'').replace(/"/g,'&quot;')}">${r.material_name||'—'}</div>
          ${r.material_code?`<code style="font-size:.65rem">${r.material_code}</code>`:''} ${r.ref?`<span class="text-muted small ms-1">${r.ref}</span>`:''}
        </td>
        <td>${typeBadge(r.material_type)}</td>
        <td class="text-end fw-bold">${fmt(r.qty)} ${r.unit||''}</td>
        <td class="small text-muted">${r.from_loc||''} → ${r.to_loc||''}</td>
        <td class="small text-muted">${r.actor||r.requested_by||'—'}</td>
        <td class="small text-muted text-truncate" style="max-width:200px" title="${(r.notes||'').replace(/"/g,'&quot;')}">${r.notes||''}</td>
      </tr>`;
    }).join('')}
    </tbody>
  </table></div>`;
}

async function loadFcCheck(prodOrderId, card){
  document.querySelectorAll('.fc-batch-card').forEach(c=>c.classList.remove('active'));
  if(card) card.classList.add('active');
  const det=document.getElementById('fc-detail');
  det.innerHTML='<p class="text-muted"><i class="bi bi-hourglass-split me-2"></i>Checking materials...</p>';
  try{
    const data=await api(`/api/fc/material-check/${prodOrderId}`);
    const o=data.order;
    const reqs=data.requirements||[];
    const allOk=data.all_ok;
    const opts=data.veneer_options||[];
    window._fcVeneerOpts = opts;          // cache for allocator row builder
    _allocRowCounts = {face:1, back:1};   // reset row counters for new order
    const confirmed=o.fc_confirmed===1||o.fc_confirmed===true;

    // Separate BOM rows by veneer_role
    const faceRows=reqs.filter(r=>r.veneer_role==='face');
    const backRows=reqs.filter(r=>r.veneer_role==='back');
    const otherRows=reqs.filter(r=>!r.veneer_role);

    const matTable=(rows,label)=>{
      if(!rows.length) return '';
      const roleColor={face:'#dbeafe',back:'#fce7f3','':'#f8fafc'}[rows[0].veneer_role||''];
      return `<div class="mb-3">
        <div class="fw-bold small mb-1" style="color:#374151">${label}</div>
        <table class="table table-sm table-bordered mb-0">
          <thead class="table-light"><tr>
            <th>Material</th><th>Code</th><th>Required</th><th>Available</th><th>Status</th><th>Grade Sub / Note</th>
          </tr></thead>
          <tbody>
          ${rows.map(r=>`<tr class="mat-row ${r.status}" style="background:${roleColor}">
            <td><small class="fw-bold">${r.material_name}</small><br><small class="text-muted">${r.supplier||''}</small></td>
            <td><code style="font-size:.7rem">${r.material_code||'—'}</code></td>
            <td><small class="fw-bold">${fmt(r.required_qty)} ${r.unit}</small><br><small class="text-muted">waste ${Math.round((r.waste_factor||0)*100)}%</small></td>
            <td><small class="${r.available_qty<r.required_qty?'text-danger fw-bold':''}">${fmt(r.available_qty)} ${r.unit}</small>
              ${r.stock_location==='fc_station'?'<br><span class="badge bg-info text-dark" style="font-size:.55rem">FC Station</span>':'<br><span class="badge bg-secondary" style="font-size:.55rem">WH</span>'}
              ${r.shortfall>0?`<br><small class="text-danger">-${fmt(r.shortfall)} SHORT</small>`:''}</td>
            <td><span class="status-pill ${r.status}">${r.status==='ok'?'✓ OK':r.status==='low'?'⚠ LOW':'✗ SHORT'}</span></td>
            <td><input class="form-control form-control-sm" style="min-width:140px" placeholder="Grade sub / note…" id="gn-${r.material_id}"></td>
          </tr>`).join('')}
          </tbody>
        </table></div>`;
    };

    // Grade-mix allocator builder
    const existingFace = (data.existing_alloc||[]).filter(a=>a.side==='face');
    const existingBack  = (data.existing_alloc||[]).filter(a=>a.side==='back');

    const allocatorHtml=(side, label, requiredQty, existing)=>{
      const sideId = `alloc-${side}`;
      const noOpts = !opts.length;
      return `<div class="mb-3">
        <div class="d-flex justify-content-between align-items-center mb-1">
          <label class="form-label fw-bold small mb-0">${label}
            <span class="badge bg-info text-dark ms-1" style="font-size:.6rem">FC Stock</span>
          </label>
          <span class="small text-muted">BOM requires <b>${fmt(requiredQty)}</b> pcs</span>
        </div>
        ${noOpts?`<div class="alert alert-warning py-1 small mb-2"><i class="bi bi-exclamation-triangle me-1"></i>No veneers in FC station stock — request a transfer from WH first.</div>`:''}
        <div id="${sideId}-rows" class="mb-2">
          ${existing.length ? existing.map((e,i)=>allocRowHtml(side,i,e.material_id,e.qty_allocated)).join('') : allocRowHtml(side,0,null,null)}
        </div>
        <button class="btn btn-xs btn-outline-secondary py-0 px-2" style="font-size:.75rem"
          onclick="allocAddRow('${side}')"><i class="bi bi-plus me-1"></i>Add another grade</button>
        <div class="d-flex justify-content-between align-items-center mt-2">
          <span class="small text-muted">Total allocated: <b id="${sideId}-total">0</b> pcs</span>
          <span class="small" id="${sideId}-status"></span>
        </div>
      </div>`;
    };

    const allocRowHtml=(side,idx,matId,qty)=>{
      const selOpts = opts.map(v=>`<option value="${v.id}" data-fc="${v.fc_stock}" data-unit="${v.unit}"
        data-species="${v.species||''}" data-grade="${v.grade||''}"
        ${v.id==matId?'selected':''}>${v.species?v.species+' ':''}${v.grade?'['+v.grade+'] ':''}${v.name}${v.code?' ('+v.code+')':''} — ${fmt(v.fc_stock)} FC</option>`).join('');
      return `<div class="d-flex gap-2 mb-1 align-items-center" id="alloc-${side}-row-${idx}">
        <select class="form-select form-select-sm" style="flex:1"
          id="alloc-${side}-mat-${idx}" onchange="allocUpdateTotal('${side}')">
          <option value="">— select grade —</option>${selOpts}
        </select>
        <input type="number" class="form-control form-control-sm" style="width:90px"
          id="alloc-${side}-qty-${idx}" value="${qty||''}" min="0.01" step="1"
          placeholder="qty" oninput="allocUpdateTotal('${side}')">
        <span class="small text-muted" id="alloc-${side}-avail-${idx}" style="min-width:60px;font-size:.7rem"></span>
        ${idx>0?`<button class="btn btn-xs btn-outline-danger py-0 px-1"
          onclick="allocRemoveRow('${side}',${idx})"><i class="bi bi-x"></i></button>`:'<div style="width:26px"></div>'}
      </div>`;
    };

    det.innerHTML=`
      <div class="d-flex justify-content-between align-items-start mb-3">
        <div>
          <h5 class="mb-1">${o.product_name} <span class="text-muted fw-normal">(${o.product_sku||''})</span></h5>
          <small class="text-muted">${o.prod_order_number||'Order #'+o.id} &mdash; ${o.po_number||''} &mdash; ${o.customer||''}</small>
          <div class="mt-1">${lineBadge(o.production_line)} <span class="ms-2 badge bg-secondary">${fmt(o.quantity)} pallet${o.quantity!=1?'s':''} ordered (${fmt((o.quantity||0)*(o.pallet_qty||1))} pcs)</span>
            ${confirmed?'<span class="ms-2 badge bg-success"><i class="bi bi-check-circle me-1"></i>FC Confirmed</span>':''}</div>
        </div>
        <span class="badge ${!reqs.length?'bg-secondary':allOk?'bg-success':'bg-danger'} fs-6">${!reqs.length?'NO BOM':allOk?'MATERIALS OK':'ACTION NEEDED'}</span>
      </div>

      ${!reqs.length?`<div class="alert alert-warning"><i class="bi bi-exclamation-triangle-fill me-2"></i><b>No BOM entries found.</b> Set up the BOM for this product first, then return here to check materials.<br><small class="text-muted">Go to <b>BOM</b> in the main menu → select the product → add materials.</small></div>`:`
        ${matTable(faceRows,'<i class="bi bi-circle-fill text-primary me-1"></i>Face Veneer')}
        ${matTable(backRows,'<i class="bi bi-circle text-info me-1"></i>Back Veneer')}
        ${matTable(otherRows,'<i class="bi bi-box me-1 text-secondary"></i>Other Materials (Adhesive / Core / Banding)')}
      `}

      ${faceRows.length||backRows.length||opts.length?`
      <div class="card p-3 mb-3 border-primary" style="background:#e8f3e8">
        <div class="fw-bold mb-3"><i class="bi bi-check2-square me-1 text-primary"></i>Confirm Veneer Grade Mix for Production
          <span class="badge bg-info text-dark ms-2" style="font-size:.65rem">Multi-grade allowed</span>
        </div>
        <div class="small text-muted mb-3">
          Enter exact quantities per grade below. Totals don't need to match BOM exactly — FC may use grade substitutions. Confirming deducts from FC stock.
        </div>
        <div class="row g-3">
          <div class="col-md-6">
            ${allocatorHtml('face','<i class="bi bi-circle-fill text-primary me-1"></i>Face Veneer',
              faceRows.reduce((s,r)=>s+r.required_qty,0)||0, existingFace)}
          </div>
          <div class="col-md-6">
            ${allocatorHtml('back','<i class="bi bi-circle text-info me-1"></i>Back Veneer',
              backRows.reduce((s,r)=>s+r.required_qty,0)||0, existingBack)}
          </div>
        </div>
      </div>`:''}

      <div class="d-flex gap-2 mt-2 flex-wrap">
        <button class="btn btn-sm btn-success" onclick="confirmFcRelease(${prodOrderId})">
          <i class="bi bi-check-circle me-1"></i>${confirmed?'Update & Re-release to Laminating':'Confirm Materials & Release to Laminating'}
        </button>
        <button class="btn btn-sm btn-outline-secondary" onclick="loadFcCheck(${prodOrderId},null)"><i class="bi bi-arrow-clockwise me-1"></i>Refresh</button>
      </div>`;
  }catch(e){det.innerHTML=`<div class="alert alert-danger">${e.message}</div>`;}
}

// ── Grade-mix allocator helpers ───────────────────────────────
let _allocRowCounts = {face:1, back:1};

function allocRowHtml(side, idx, matId, qty){
  const opts = window._fcVeneerOpts || [];
  const selOpts = opts.map(v=>`<option value="${v.id}" data-fc="${v.fc_stock}" data-unit="${v.unit}"
    data-species="${v.species||''}" data-grade="${v.grade||''}"
    ${Number(v.id)===Number(matId)?'selected':''}>${v.species?v.species+' ':''}${v.grade?'['+v.grade+'] ':''}${v.name}${v.code?' ('+v.code+')':''} — ${fmt(v.fc_stock)} FC</option>`).join('');
  return `<div class="d-flex gap-2 mb-1 align-items-center" id="alloc-${side}-row-${idx}">
    <select class="form-select form-select-sm" style="flex:1"
      id="alloc-${side}-mat-${idx}" onchange="allocUpdateTotal('${side}');allocShowAvail('${side}',${idx})">
      <option value="">— select grade —</option>${selOpts}
    </select>
    <input type="number" class="form-control form-control-sm" style="width:90px"
      id="alloc-${side}-qty-${idx}" value="${qty||''}" min="0.01" step="1"
      placeholder="qty" oninput="allocUpdateTotal('${side}')">
    <span class="small text-muted" id="alloc-${side}-avail-${idx}" style="min-width:60px;font-size:.7rem;white-space:nowrap"></span>
    ${idx>0?`<button class="btn btn-xs btn-outline-danger py-0 px-1"
      onclick="allocRemoveRow('${side}',${idx})"><i class="bi bi-x"></i></button>`:'<div style="width:26px"></div>'}
  </div>`;
}

function allocAddRow(side){
  const count = _allocRowCounts[side] || 1;
  const container = document.getElementById(`alloc-${side}-rows`);
  if(!container) return;
  const div = document.createElement('div');
  div.innerHTML = allocRowHtml(side, count, null, null);
  container.appendChild(div.firstElementChild);
  _allocRowCounts[side] = count + 1;
}

function allocRemoveRow(side, idx){
  const row = document.getElementById(`alloc-${side}-row-${idx}`);
  if(row) row.remove();
  allocUpdateTotal(side);
}

function allocShowAvail(side, idx){
  const sel = document.getElementById(`alloc-${side}-mat-${idx}`);
  const opt = sel?.options[sel.selectedIndex];
  const avail = document.getElementById(`alloc-${side}-avail-${idx}`);
  if(avail && opt?.value) avail.textContent = `avail: ${fmt(opt.dataset.fc||0)}`;
  else if(avail) avail.textContent = '';
}

function allocUpdateTotal(side){
  const rows = document.querySelectorAll(`[id^="alloc-${side}-row-"]`);
  let total = 0;
  rows.forEach(row=>{
    const idx = row.id.split('-').pop();
    const qty = parseFloat(document.getElementById(`alloc-${side}-qty-${idx}`)?.value)||0;
    total += qty;
    allocShowAvail(side, idx);
  });
  const totalEl = document.getElementById(`alloc-${side}-total`);
  if(totalEl) totalEl.textContent = fmt(total);
}

function allocGetLines(side){
  const rows = document.querySelectorAll(`[id^="alloc-${side}-row-"]`);
  const lines = [];
  rows.forEach(row=>{
    const idx = row.id.split('-').pop();
    const matId = parseInt(document.getElementById(`alloc-${side}-mat-${idx}`)?.value)||0;
    const qty = parseFloat(document.getElementById(`alloc-${side}-qty-${idx}`)?.value)||0;
    if(matId && qty > 0) lines.push({material_id: matId, qty_allocated: qty});
  });
  return lines;
}

async function confirmFcRelease(prodOrderId){
  const faceAlloc = allocGetLines('face');
  const backAlloc  = allocGetLines('back');

  if(!faceAlloc.length && !backAlloc.length){
    toast('Please allocate at least one veneer grade before confirming','warning');
    return;
  }

  // Build human-readable notes for the batch move
  const allocLabel = (alloc) => alloc.map(a=>{
    const sel = document.querySelector(`[id^="alloc-face-mat-"], [id^="alloc-back-mat-"]`);
    return `${a.qty_allocated} pcs`;
  }).join(', ');

  const faceNotes = faceAlloc.map(a=>{
    const opt = document.querySelector(`#alloc-face-mat-${faceAlloc.indexOf(a)}`);
    return opt ? `${opt.options[opt.selectedIndex]?.text?.split('—')[0]?.trim()||'?'}: ${a.qty_allocated}` : `mat#${a.material_id}: ${a.qty_allocated}`;
  }).join(' | ');
  const backNotes = backAlloc.map(a=>{
    const opt = document.querySelector(`#alloc-back-mat-${backAlloc.indexOf(a)}`);
    return opt ? `${opt.options[opt.selectedIndex]?.text?.split('—')[0]?.trim()||'?'}: ${a.qty_allocated}` : `mat#${a.material_id}: ${a.qty_allocated}`;
  }).join(' | ');

  try{
    // Save grade-mix allocation (deducts fc_stock)
    await api(`/api/production-orders/${prodOrderId}/veneer-allocation`, 'POST', {
      face_alloc: faceAlloc,
      back_alloc:  backAlloc,
      deduct_fc_stock: true,
    });

    // Find batch at FC and move to laminating
    const batches = await api('/api/fc/batches').catch(()=>[]);
    const b = batches.find(x=>x.prod_order_id===prodOrderId);
    if(!b){ toast('No batch at FC for this order','danger'); return; }

    const moveNotes = [
      faceAlloc.length ? `Face: ${faceNotes}` : '',
      backAlloc.length  ? `Back: ${backNotes}` : '',
    ].filter(Boolean).join(' || ');

    await api(`/api/batches/${b.id}/move`, 'POST', {
      to_department: 'laminating', quantity: b.quantity, time_minutes: 0,
      moved_by: 'FC',
      notes: `Grade mix confirmed — ${moveNotes}`,
    });

    toast('Veneer grade mix confirmed — Batch released to Laminating');
    loadFcPage();
  } catch(e){ toast(e.message, 'danger'); }
}



// ════════════════════════════════════════════════════════════
// Packing Center (deprecated redirect)
// ════════════════════════════════════════════════════════════

// ══════════════════════════════════════════════════════════
// PACKING CENTER
// ══════════════════════════════════════════════════════════
async function loadPackingCenter(){
  // Fetch grading and packing batches from the unified batches table
  const [gradingBatches, packingBatches] = await Promise.all([
    api('/api/batches?department=grading').catch(()=>[]),
    api('/api/batches?department=packing').catch(()=>[])
  ]);
  const allBatches = [...(gradingBatches||[]), ...(packingBatches||[])];
  const byLine={P01:0,P02:0,P37:0};
  packingBatches?.forEach(b=>{ byLine[b.production_line]=(byLine[b.production_line]||0)+(b.quantity||0); });
  const totalPcs=packingBatches?.reduce((s,b)=>s+(b.quantity||0),0)||0;
  document.getElementById('packing-stats').innerHTML=[
    {val:(packingBatches||[]).length, lbl:'Batches at Packing',    ico:'bi-boxes',    c:'purple'},
    {val:(gradingBatches||[]).length, lbl:'In Grading (incoming)', ico:'bi-patch-check',c:'success'},
    {val:totalPcs,                    lbl:'Pcs Being Packed',      ico:'bi-stack',    c:'primary'},
    {val:Object.values(byLine).filter(v=>v>0).length, lbl:'Lines Active', ico:'bi-diagram-3', c:'info'},
  ].map(s=>`<div class="col-6 col-md-3"><div class="stat-card d-flex justify-content-between align-items-start">
    <div><div class="val" style="color:${s.c==='purple'?'#8b5cf6':'var(--'+s.c+')'}">${fmt(s.val)}</div><div class="lbl">${s.lbl}</div></div>
    <i class="bi ${s.ico}" style="font-size:2rem;opacity:.12;color:${s.c==='purple'?'#8b5cf6':''}"></i>
  </div></div>`).join('');
  const grid=document.getElementById('packing-grid');
  if(!allBatches.length){
    grid.innerHTML='<div class="text-center text-muted py-5"><i class="bi bi-boxes" style="font-size:2.5rem;color:#8b5cf6"></i><p class="mt-2">No batches in the grading or packing pipeline.</p></div>';
    return;
  }
  grid.innerHTML=allBatches.map(b=>{
    const isGrading=b.current_department==='grading';
    const borderColor=isGrading?'#16a34a':'#8b5cf6';
    return `
    <div class="pack-card" style="border-top-color:${borderColor};cursor:pointer" onclick="deptBatchDetail(${b.id},'${b.current_department}')">
      <div class="d-flex justify-content-between mb-2">
        <span class="fw-bold small">${b.batch_number||'B#'+b.id}</span>
        ${slDeptBadge(b.current_department)}
      </div>
      <div class="small fw-semibold text-muted">${b.product_name||b.sku||'—'}</div>
      <div class="fw-bold mt-1" style="color:${borderColor}">${fmt(b.quantity||0)} pcs</div>
      <div class="small text-muted mt-1">${(b.created_at||'').slice(0,10)} · ${b.production_line||''}</div>
      <div class="small text-muted mt-1"><i class="bi bi-info-circle me-1"></i>Click to view batch detail</div>
    </div>`;
  }).join('');
}
function lineBadgeColor(line){
  return {P01:'#1f4a1f',P02:'#16a34a',P37:'#9d174d'}[line]||'#64748b';
}



// ════════════════════════════════════════════════════════════
// Generic Dept Pages
// ════════════════════════════════════════════════════════════

// ══════════════════════════════════════════════════════════
// GENERIC DEPT PAGES
// ══════════════════════════════════════════════════════════
const DEPT_EXTRAS={
  laminating:`<div class="mb-2"><label class="form-label">Table #</label><input type="number" class="form-control" id="da-table" min="1" max="10"></div>
    <div class="mb-2"><label class="form-label">Glue BOM Code</label><input class="form-control" id="da-glue"></div>
    <div class="mb-2"><label class="form-label">Planned Qty</label><input type="number" class="form-control" id="da-planned"></div>`,
  repair:`<div class="mb-2"><label class="form-label">Pair Number</label><input type="number" class="form-control" id="da-pair" placeholder="1-20"></div>
    <div class="mb-2"><label class="form-label">Veneer Species</label><input class="form-control" id="da-species"></div>
    <div class="mb-2"><label class="form-label">Repair Type</label><select class="form-select" id="da-repair-type"><option value="face">Face</option><option value="back">Back</option><option value="both">Both</option></select></div>`,
  sanding:`<div class="mb-2"><label class="form-label">Belt Number</label><input type="number" class="form-control" id="da-belt"></div>
    <div class="mb-2"><label class="form-label">Grit</label><input class="form-control" id="da-grit" placeholder="e.g. 120"></div>
    <div class="mb-2"><label class="form-label">NCG Qty (veneer scraped off)</label><input type="number" class="form-control" id="da-ncg" value="0"></div>`,
  grading:`<div class="mb-2"><label class="form-label">LG Grade Qty</label><input type="number" class="form-control" id="da-lg" value="0"></div>
    <div class="mb-2"><label class="form-label">C Grade Qty</label><input type="number" class="form-control" id="da-c" value="0"></div>
    <div class="mb-2"><label class="form-label">C Grade Action</label><select class="form-select" id="da-c-action"><option value="relaminate">Re-laminate</option><option value="downgrade">Downgrade &amp; Pack</option><option value="scrap">Scrap</option></select></div>`,
  bleach:`<div class="mb-2"><label class="form-label">Pieces Bleached</label><input type="number" class="form-control" id="da-bleached"></div>
    <div class="mb-2"><label class="form-label">Chemical Batch ID</label><input class="form-control" id="da-chem"></div>`,
};



// ════════════════════════════════════════════════════════════
// Dept Batch Detail offcanvas
// ════════════════════════════════════════════════════════════

// ══════════════════════════════════════════════════════════════
// DEPT BATCH DETAIL OFFCANVAS
// ══════════════════════════════════════════════════════════════
let _bdcBatch=null, _bdcDept=null, _bdcActiveTab='info', _bdcReadOnly=false;

async function deptBatchDetail(batchId, dept, readOnly=false){
  _bdcDept=dept; _bdcActiveTab='info'; _bdcReadOnly=!!readOnly;
  // Show offcanvas immediately with loader
  const oc=bootstrap.Offcanvas.getOrCreateInstance(document.getElementById('batchDetailCanvas'));
  document.getElementById('bdc-title').innerHTML=`<i class="bi bi-layers me-2"></i>Batch #${batchId}`;
  document.getElementById('bdc-body').innerHTML='<p class="text-muted small p-3">Loading…</p>';
  oc.show();
  // Fetch batch detail from batches API
  try{
    const b=await api(`/api/batches/${batchId}`).catch(()=>null);
    const hist=await api(`/api/batches/${batchId}/history`).catch(()=>[]);
    _bdcBatch=b;
    document.getElementById('bdc-title').innerHTML=`<i class="bi bi-layers me-2"></i>${b?.batch_number||'Batch #'+batchId}`;
    bdcRender('info', b, hist);
  }catch(e){document.getElementById('bdc-body').innerHTML=`<div class="alert alert-danger p-3">${e.message}</div>`;}
}

function bdcTab(tab){
  _bdcActiveTab=tab;
  document.querySelectorAll('#bdc-tabs .nav-link').forEach(a=>a.classList.toggle('active',a.textContent.trim().toLowerCase()===tab));
  if(_bdcBatch) {
    if(tab==='logs') api(`/api/batches/${_bdcBatch.id}/history`).then(hist=>bdcRender('logs',_bdcBatch,hist));
    else bdcRender(tab,_bdcBatch,[]);
  }
}

function bdcRender(tab, b, hist){
  const user=getCurrentUser();
  const canEdit=user?.role=== ROLE.PRODUCTION_PLANNING||user?.role=== ROLE.MANAGERIAL;
  const pq=b?.pallet_qty||1;
  if(tab==='info'){
    const pri=b?.priority||2;
    document.getElementById('bdc-body').innerHTML=`
      <div class="px-3 py-2">
        <!-- Priority editor — top of detail -->
        <div class="card mb-3" style="border-left:4px solid ${pri===1?'#ef4444':pri===3?'#16a34a':'#eab308'}">
          <div class="card-body p-2 d-flex align-items-center gap-2 flex-wrap">
            <i class="bi bi-flag-fill" style="color:${pri===1?'#ef4444':pri===3?'#16a34a':'#eab308'}"></i>
            <span class="fw-semibold small">Priority:</span>
            ${prioBadge(pri)}
            <span class="ms-auto d-flex align-items-center gap-1">
              <small class="text-muted">Change:</small>
              ${prioSelect(pri, b?.id, 'batch', `deptBatchDetail(${b?.id},'${_bdcDept}')`)}
            </span>
          </div>
        </div>
        <div class="row g-2 mb-3">
          <div class="col-6"><div class="card bg-light p-2 text-center"><div class="small text-muted">Quantity</div><div class="fw-bold fs-5">${fmt(b?.total_pcs ?? ((b?.quantity||0)*pq))} pcs</div><div class="small text-muted">${fmt(b?.quantity)} pallet${b?.quantity!=1?'s':''}${b?.pcs_actual!=null?' <span class="badge bg-warning text-dark" style="font-size:.6rem">SPLIT</span>':''}</div></div></div>
          <div class="col-6"><div class="card bg-light p-2 text-center"><div class="small text-muted">Department</div><div class="fw-bold">${DLBL[b?.current_department]||b?.current_department||'—'}</div></div></div>
        </div>
        <table class="table table-sm table-borderless" style="font-size:.82rem">
          <tr><th class="text-muted fw-normal" style="width:38%">Batch #</th><td class="fw-semibold">${b?.batch_number||'—'}</td></tr>
          <tr><th class="text-muted fw-normal">Product</th><td>${b?.product_name||'—'}</td></tr>
          <tr><th class="text-muted fw-normal">Production Order</th><td>${b?.prod_order_number||'—'}</td></tr>
          <tr><th class="text-muted fw-normal">PO / Customer</th><td>${b?.po_number||'—'}${b?.customer?' · '+b.customer:''}</td></tr>
          <tr><th class="text-muted fw-normal">Created</th><td>${b?.created_at?.slice(0,16)||'—'}</td></tr>
          ${b?.parent_batch_id?`<tr><th class="text-muted fw-normal">Split from</th><td><span class="badge bg-warning text-dark">Batch #${b.parent_batch_id}</span></td></tr>`:''}
          ${b?.split_reason?`<tr><th class="text-muted fw-normal">Split reason</th><td class="fst-italic">${b.split_reason}</td></tr>`:''}
        </table>
        <div class="d-flex gap-2 flex-wrap mt-2">
          ${_bdcReadOnly?`<div class="small text-muted fst-italic"><i class="bi bi-eye me-1"></i>Planning view — production moves &amp; splits are done in the Station Leader Hub.</div>`:`
          <button class="btn btn-sm btn-outline-primary" onclick="openMove(${b?.id},'${_bdcDept}',${b?.quantity})"><i class="bi bi-arrow-right-circle me-1"></i>Move</button>
          <button class="btn btn-sm btn-outline-warning" onclick="openSplit(${b?.id},${b?.quantity})"><i class="bi bi-scissors me-1"></i>Split</button>`}
          ${canEdit?`<button class="btn btn-sm btn-outline-secondary" onclick="bdcTab('edit')"><i class="bi bi-pencil me-1"></i>Edit</button>`:''}
        </div>
      </div>`;
  } else if(tab==='logs'){
    const moves=hist||[];
    document.getElementById('bdc-body').innerHTML=`
      <div class="px-3 py-2">
        <h6 class="small fw-bold text-muted text-uppercase mb-2">Movement History</h6>
        ${moves.length?`<table class="table table-sm" style="font-size:.78rem">
          <thead class="table-light"><tr><th>From</th><th>To</th><th>Qty</th><th>When</th><th>By</th><th>Notes</th></tr></thead>
          <tbody>${moves.map(m=>`<tr>
            <td>${DLBL[m.from_department]||m.from_department||'—'}</td>
            <td>${DLBL[m.to_department]||m.to_department||'—'}</td>
            <td>${fmt(m.quantity)}</td>
            <td class="text-muted small">${(m.moved_at||'').slice(0,16)}</td>
            <td class="small">${m.moved_by||'—'}</td>
            <td class="small text-muted">${m.notes||''}</td>
          </tr>`).join('')}</tbody>
        </table>`:'<p class="text-muted small">No movement history yet.</p>'}
      </div>`;
  } else if(tab==='edit'){
    if(!canEdit){document.getElementById('bdc-body').innerHTML='<div class="alert alert-warning m-3">Edit access requires Planning or Managerial role.</div>';return;}
    document.getElementById('bdc-body').innerHTML=`
      <div class="px-3 py-2">
        <h6 class="small fw-bold text-muted text-uppercase mb-3">Edit Batch</h6>
        <div class="mb-3">
          <label class="form-label small fw-semibold">Quantity (pallets)</label>
          <input type="number" class="form-control form-control-sm" id="bdc-edit-qty" value="${b?.quantity||0}" min="0">
        </div>
        <div class="mb-3">
          <label class="form-label small fw-semibold">Notes</label>
          <textarea class="form-control form-control-sm" id="bdc-edit-notes" rows="3">${b?.split_reason||''}</textarea>
        </div>
        <button class="btn btn-primary btn-sm" onclick="bdcSave()"><i class="bi bi-floppy me-1"></i>Save Changes</button>
      </div>`;
  }
}

async function bdcSave(){
  const qty=parseFloat(document.getElementById('bdc-edit-qty').value)||0;
  const notes=document.getElementById('bdc-edit-notes').value||'';
  try{
    await api(`/api/batches/${_bdcBatch.id}`,'PATCH',{quantity:qty,split_reason:notes});
    toast('Batch updated','success');
    const dept=_bdcDept;
    bootstrap.Offcanvas.getInstance(document.getElementById('batchDetailCanvas')).hide();
    loadDeptPage(dept);
  }catch(e){toast(e.message,'danger');}
}

// The legacy prod_batch detail panel (slOpenDetail / _renderProdBatchDetail /
// bdcSlSave) was removed in v2.21.76 — it read/wrote the retired
// /api/prod-batches endpoints and had no live caller. The live batch detail is
// deptBatchDetail (System B: batches + batch_movements + station logs).



// ════════════════════════════════════════════════════════════
// Laminating → FC Material Request
// ════════════════════════════════════════════════════════════

// ══════════════════════════════════════════════════════════════
// LAMINATING → FC MATERIAL REQUEST
// ══════════════════════════════════════════════════════════════
let _lfrMats=[], _lfrBatchRef='', _lfrRole='';

// Role is a label only — all FC stock materials are always shown regardless of role
const LFR_ROLE_FILTER={ face:()=>true, back:()=>true, base:()=>true, other:()=>true };
const LFR_ROLE_LABEL={face:'Face Veneer',back:'Back Veneer',base:'Base Board',other:'Other'};

async function openLamFcReturn(batchRef=''){
  const br = batchRef || _slActiveBatch?.batch_number || '';
  document.getElementById('lfret-batch-info').innerHTML =
    `<i class="bi bi-exclamation-triangle me-1"></i>Return material to FC for batch <b>${br}</b>. FC will see this on the Movements page and re-confirm pickup.`;
  document.getElementById('lfret-qty').value = '';
  document.getElementById('lfret-actual').value = '';
  document.getElementById('lfret-released').value =
    _slActiveBatch?.total_pcs || ((_slActiveBatch?.quantity||0) * (_slActiveBatch?.pallet_qty||1)) || '';
  document.getElementById('lfret-notes').value = '';
  // Populate materials from suggestions (same boards/veneers FC sent for this batch),
  // falling back to the full FC stock list.
  if(!_lfrMats.length) _lfrMats = await api('/api/fc/stock').catch(()=>[]);
  const sel = document.getElementById('lfret-material');
  sel.innerHTML = '<option value="">— Pick the material to return —</option>';
  // Suggested first
  const poId = _slActiveBatch?.prod_order_id;
  let suggestedIds = new Set();
  if(poId){
    const alloc = await api(`/api/production-orders/${poId}/veneer-allocation`).catch(()=>null);
    if(alloc){
      ['face_material','back_material','base_material'].forEach(k => {
        if(alloc[k]?.id) suggestedIds.add(alloc[k].id);
      });
      (alloc.allocations||[]).forEach(a=>{ if(a.material?.id) suggestedIds.add(a.material.id); });
    }
  }
  const suggested = _lfrMats.filter(m => suggestedIds.has(m.id));
  const rest      = _lfrMats.filter(m => !suggestedIds.has(m.id));
  if(suggested.length){
    sel.innerHTML += `<optgroup label="↳ Materials used on this batch">`+
      suggested.map(m=>`<option value="${m.id}" data-unit="${m.unit||'pcs'}">${m.name}${m.code?' ('+m.code+')':''}</option>`).join('')+
      `</optgroup>`;
  }
  if(rest.length){
    sel.innerHTML += `<optgroup label="All FC materials">`+
      rest.map(m=>`<option value="${m.id}" data-unit="${m.unit||'pcs'}">${m.name}${m.code?' ('+m.code+')':''}</option>`).join('')+
      `</optgroup>`;
  }
  sel.onchange = ()=>{
    const o=sel.selectedOptions[0];
    document.getElementById('lfret-uom').textContent=(o?.dataset.unit)||'pcs';
  };
  bootstrap.Modal.getOrCreateInstance(document.getElementById('lamFcReturnModal')).show();
}

function lfretRecalc(){
  const released = Number(document.getElementById('lfret-released').value||0);
  const actual   = Number(document.getElementById('lfret-actual').value||0);
  const surplus  = Math.max(0, actual - released);
  document.getElementById('lfret-qty').value = surplus || '';
  const hint=document.getElementById('lfret-qty-hint');
  if(actual>0 && released>0){
    if(surplus>0)
      hint.innerHTML = `<span class="text-warning"><i class="bi bi-exclamation-circle me-1"></i>FC over-delivered ${surplus} pcs — returning surplus.</span>`;
    else if(actual<released)
      hint.innerHTML = `<span class="text-danger"><i class="bi bi-x-octagon me-1"></i>Under-delivery: missing ${released-actual} pcs. Consider requesting more from FC instead of returning.</span>`;
    else
      hint.innerHTML = '<i class="bi bi-check2-circle text-success me-1"></i>Quantities match — nothing to return.';
  }else{
    hint.textContent='Auto = actual − released.';
  }
}
async function lfretSubmit(){
  const mat=Number(document.getElementById('lfret-material').value);
  const released=Number(document.getElementById('lfret-released').value||0);
  const actual=Number(document.getElementById('lfret-actual').value||0);
  const qty=Number(document.getElementById('lfret-qty').value||0);
  const reason=document.getElementById('lfret-reason').value;
  const notes=document.getElementById('lfret-notes').value;
  if(!mat || qty<=0){ alert('Pick a material and enter a positive quantity to return'); return; }
  const enriched = `${reason} — released ${released}, actual ${actual}, returning ${qty}. ${notes||''}`.trim();
  try{
    await api('/api/fc/return-material','POST',{
      material_id: mat, qty,
      batch_ref: _slActiveBatch?.batch_number||'',
      reason: enriched,
    });
    bootstrap.Modal.getInstance(document.getElementById('lamFcReturnModal'))?.hide();
    toast(`Return request sent to FC for ${qty} pcs surplus`, 'success');
  }catch(e){ alert('Return failed: '+(e.message||e)); }
}

async function openLamFcRequest(batchRef=''){
  _lfrBatchRef=batchRef||_slActiveBatch?.batch_number||'';
  _lfrRole='';
  if(!_lfrMats.length) _lfrMats=await api('/api/fc/stock').catch(()=>[]);
  // Reset form
  document.getElementById('lfr-mat-search').value='';
  document.getElementById('lfr-material-id').innerHTML='<option value="">— Select material type first —</option>';
  document.getElementById('lfr-mat-info').textContent='';
  document.getElementById('lfr-qty').value='';
  document.getElementById('lfr-notes').value='';
  document.getElementById('lfr-unit-label').textContent='pcs';
  document.getElementById('lfr-role').value='';
  // Reset role buttons
  document.querySelectorAll('#lfr-role-btns button').forEach(b=>b.classList.replace('btn-warning','btn-outline-secondary'));
  // Show batch info
  const batchLabel=_lfrBatchRef||_slActiveBatch?.prod_order_number||'';
  document.getElementById('lfr-batch-info').textContent=batchLabel?`Batch: ${_lfrBatchRef}${_slActiveBatch?.prod_order_number?' · PO: '+_slActiveBatch.prod_order_number:''}`:'';
  // Suggest the same materials this batch has consumed before (from BOM / readiness)
  await _lfrLoadSuggestions();
  bootstrap.Modal.getOrCreateInstance(document.getElementById('lamFcRequestModal')).show();
}

async function _lfrLoadSuggestions(){
  const host = document.getElementById('lfr-suggestions');
  if(!host) return;
  host.innerHTML = '';
  // Need the prod_order_id to look up BOM materials used in this batch
  const poId = _slActiveBatch?.prod_order_id;
  if(!poId){ host.innerHTML='<span class="text-muted small">No batch context — pick a material below.</span>'; return; }
  try{
    // Reuse the existing veneer-allocation endpoint to find the boards + veneers
    // already linked to this production order.
    const alloc = await api(`/api/production-orders/${poId}/veneer-allocation`).catch(()=>null);
    const candidates = [];
    const seen = new Set();
    const push = (m, role) => {
      if(!m || !m.id || seen.has(m.id)) return;
      seen.add(m.id);
      candidates.push({id:m.id, code:m.code||'', name:m.name||'', role});
    };
    // Allocation may carry confirmed face / back / base
    if(alloc){
      if(alloc.face_material) push(alloc.face_material, 'face');
      if(alloc.back_material) push(alloc.back_material, 'back');
      if(alloc.base_material) push(alloc.base_material, 'base');
      (alloc.allocations||[]).forEach(a=> push(a.material||a, a.role||a.veneer_role||'face'));
    }
    if(!candidates.length){
      host.innerHTML = '<span class="text-muted small">No material history for this batch yet — pick from the list below.</span>';
      return;
    }
    host.innerHTML = '<span class="small text-muted me-2"><i class="bi bi-magic me-1"></i>Used before:</span>' +
      candidates.map(c => `<button type="button" class="btn btn-sm btn-outline-info me-1 mb-1"
        onclick="_lfrApplySuggestion(${c.id}, '${c.role}')"
        title="Request more of ${c.name}">
        <span class="badge bg-info text-white me-1" style="font-size:.6rem">${c.role||''}</span>${c.code||c.name}</button>`).join('');
  }catch(e){
    host.innerHTML='<span class="text-muted small">Suggestions unavailable.</span>';
  }
}

function _lfrApplySuggestion(matId, role){
  // Pick the appropriate role button to set up filtering, then select the material
  const roleBtn = document.querySelector(`#lfr-role-btns button[data-role="${role}"]`)
                || document.querySelector('#lfr-role-btns button');
  if(roleBtn) roleBtn.click();
  // After role filter applies, try to select the requested material in the dropdown
  setTimeout(()=>{
    const sel = document.getElementById('lfr-material-id');
    const opt = [...sel.options].find(o=>String(o.value)===String(matId));
    if(opt){ sel.value = matId; lfrOnMatSelect(); }
    else { toast('That material is not in current FC stock — pick another','warning'); }
  }, 50);
}

function lfrSelectRole(role, btn){
  _lfrRole=role;
  document.getElementById('lfr-role').value=role;
  // Highlight selected button
  document.querySelectorAll('#lfr-role-btns button').forEach(b=>{
    b.classList.remove('btn-warning','btn-outline-secondary');
    b.classList.add(b===btn?'btn-warning':'btn-outline-secondary');
  });
  // Reset search and filter material list
  document.getElementById('lfr-mat-search').value='';
  _lfrApplyFilter('');
}

function _lfrApplyFilter(q){
  const term=(q||'').trim().toLowerCase();
  const roleFn=_lfrRole?LFR_ROLE_FILTER[_lfrRole]||LFR_ROLE_FILTER.other:LFR_ROLE_FILTER.other;
  const mats=_lfrMats.filter(m=>roleFn(m)&&(!term||((m.code||'').toLowerCase().includes(term)||(m.name||'').toLowerCase().includes(term))));
  const placeholder=_lfrRole?`— Select ${LFR_ROLE_LABEL[_lfrRole]} —`:'— Select material type first —';
  document.getElementById('lfr-material-id').innerHTML=
    `<option value="">${placeholder}</option>`+
    mats.map(m=>`<option value="${m.id}" data-unit="${m.unit||'pcs'}" data-stock="${m.wh_stock||0}">`+
      `${m.name}${m.code?' ('+m.code+')':''} — FC Stock: ${fmt(m.wh_stock||0)} ${m.unit||'pcs'}`+
    `</option>`).join('');
  document.getElementById('lfr-mat-info').textContent=mats.length?`${mats.length} material${mats.length!==1?'s':''} available`:'No matching materials in FC stock';
}

function lfrFilterMats(q){ _lfrApplyFilter(q); }

function lfrOnMatSelect(){
  const sel=document.getElementById('lfr-material-id');
  const opt=sel.selectedOptions[0];
  if(opt&&opt.value){
    const unit=opt.dataset.unit||'pcs';
    document.getElementById('lfr-unit-label').textContent=unit;
    document.getElementById('lfr-mat-info').textContent=`FC Stock: ${fmt(parseFloat(opt.dataset.stock)||0)} ${unit}`;
  }
}

async function lfrSubmit(){
  const role=document.getElementById('lfr-role').value;
  if(!role){toast('Select a material type (Face / Back / Base / Other)','warning');return;}
  const matId=parseInt(document.getElementById('lfr-material-id').value)||0;
  const qty=parseFloat(document.getElementById('lfr-qty').value)||0;
  const notes=document.getElementById('lfr-notes').value.trim();
  if(!matId||qty<=0){toast('Select a specific material and enter quantity','warning');return;}
  if(!notes){toast('Please describe the reason for this request','warning');return;}
  // Auto-populate batch and PO refs from active batch
  const batchRef=_lfrBatchRef||_slActiveBatch?.batch_number||'';
  const poRef=_slActiveBatch?.prod_order_number||'';
  const roleLabel=LFR_ROLE_LABEL[role]||role;
  try{
    await api('/api/fc/laminating-material-request','POST',{
      material_id:matId, qty_requested:qty,
      notes:`[LAM ${roleLabel.toUpperCase()} REQUEST${batchRef?' · '+batchRef:''}] ${notes}`,
      batch_ref:batchRef, po_ref:poRef,
    });
    bootstrap.Modal.getInstance(document.getElementById('lamFcRequestModal')).hide();
    toast(`${roleLabel} request sent to FC station`,'success');
    _lfrMats=[];  // clear cache so FC stock refreshes on next open
  }catch(e){toast(e.message,'danger');}
}

function renderDeptStats(dept,stats){
  if(!stats) return '';
  if(dept==='laminating'&&stats.by_table) return `<div class="card p-3 mb-3"><h6 class="fw-bold mb-2">Table Efficiency</h6><div class="row g-2">${(stats.by_table||[]).map(t=>`<div class="col-3"><div class="stat-card text-center"><div class="fw-bold">T${t.table_number||t.table_id}</div><div class="val text-primary">${Math.round((t.efficiency||0)*100)}%</div></div></div>`).join('')}</div></div>`;
  if(dept==='repair'&&stats.by_pair) return `<div class="row g-3 mb-3">
    <div class="col-md-6"><div class="card p-3"><h6 class="fw-bold mb-2">By Pair</h6>${(stats.by_pair||[]).map(p=>`<div class="d-flex justify-content-between border-bottom py-1"><small>Pair ${p.pair_number}</small><small class="text-muted">${fmt(p.repaired_qty)} pcs | ${Math.round(p.avg_minutes||0)} min avg</small></div>`).join('')||'<small class="text-muted">No data</small>'}</div></div>
    <div class="col-md-6"><div class="card p-3"><h6 class="fw-bold mb-2">By Species</h6>${(stats.by_species||[]).map(s=>`<div class="d-flex justify-content-between border-bottom py-1"><small>${s.veneer_species}</small><small class="text-muted">${fmt(s.repaired_qty)} pcs | ${Math.round(s.avg_minutes||0)} min</small></div>`).join('')||'<small class="text-muted">No data</small>'}</div></div></div>`;
  if(dept==='sanding'&&stats.by_operator) return `<div class="row g-3 mb-3">
    <div class="col-md-6"><div class="card p-3"><h6 class="fw-bold mb-2">Operator NCG</h6>${(stats.by_operator||[]).map(o=>`<div class="d-flex justify-content-between border-bottom py-1"><small>${o.operator_name}</small><small class="text-muted">${fmt(o.sanded_qty)} pcs | NCG ${fmt(o.ncg_qty)} (${Math.round((o.ncg_rate||0)*100)}%)</small></div>`).join('')||'<small class="text-muted">No data</small>'}</div></div>
    <div class="col-md-6"><div class="card p-3"><h6 class="fw-bold mb-2">Belt Efficiency</h6>${(stats.by_belt||[]).map(b=>`<div class="d-flex justify-content-between border-bottom py-1"><small>Belt ${b.belt_number}</small><small class="text-muted">${Math.round((b.efficiency||0)*100)}%</small></div>`).join('')||'<small class="text-muted">No data</small>'}</div></div></div>`;
  return '';
}

function openDeptAct(dept){
  document.getElementById('da-title').textContent='Record Activity — '+DLBL[dept];
  document.getElementById('da-body').innerHTML=`
    <div class="mb-2"><label class="form-label">Batch ID</label><input class="form-control" id="da-batch" placeholder="optional"></div>
    <div class="mb-2"><label class="form-label">Quantity Processed</label><input type="number" class="form-control" id="da-qty" min="1"></div>
    <div class="mb-2">
      <label class="form-label">Veneer Side <span class="text-muted fw-normal">(for efficiency tracking)</span></label>
      <div class="d-flex gap-2">
        <div class="form-check"><input class="form-check-input" type="radio" name="da-vside" id="da-vs-face" value="face"><label class="form-check-label" for="da-vs-face"><span class="badge bg-primary" style="font-size:.7rem">FACE</span></label></div>
        <div class="form-check"><input class="form-check-input" type="radio" name="da-vside" id="da-vs-back" value="back"><label class="form-check-label" for="da-vs-back"><span class="badge bg-info text-dark" style="font-size:.7rem">BACK</span></label></div>
        <div class="form-check"><input class="form-check-input" type="radio" name="da-vside" id="da-vs-both" value="both" checked><label class="form-check-label" for="da-vs-both"><span class="badge bg-secondary" style="font-size:.7rem">BOTH</span></label></div>
      </div>
    </div>
    <div class="mb-2"><label class="form-label">Operator</label><input class="form-control" id="da-op"></div>
    <div class="mb-2"><label class="form-label">Time (min)</label><input type="number" class="form-control" id="da-time"></div>
    ${DEPT_EXTRAS[dept]||''}
    <div class="mb-2"><label class="form-label">Notes</label><textarea class="form-control" id="da-notes" rows="2"></textarea></div>`;
  document.getElementById('da-save').onclick=()=>saveDeptAct(dept);
}

async function saveDeptAct(dept){
  try{
    const vside=document.querySelector('input[name="da-vside"]:checked')?.value||'both';
    const body={
      department:dept,
      batch_id:document.getElementById('da-batch')?.value?parseInt(document.getElementById('da-batch').value):null,
      quantity:parseInt(document.getElementById('da-qty')?.value||0),
      operator:document.getElementById('da-op')?.value||'',
      time_minutes:parseInt(document.getElementById('da-time')?.value||0),
      veneer_side:vside,
      notes:document.getElementById('da-notes')?.value||''
    };
    if(dept==='laminating'){body.table_number=parseInt(document.getElementById('da-table')?.value||1);body.glue_bom_code=document.getElementById('da-glue')?.value;body.planned_qty=parseInt(document.getElementById('da-planned')?.value||0);}
    if(dept==='repair'){body.pair_number=parseInt(document.getElementById('da-pair')?.value||1);body.veneer_species=document.getElementById('da-species')?.value;body.repair_type=document.getElementById('da-repair-type')?.value;}
    if(dept==='sanding'){body.belt_number=parseInt(document.getElementById('da-belt')?.value||1);body.grit=document.getElementById('da-grit')?.value;body.ncg_qty=parseInt(document.getElementById('da-ncg')?.value||0);}
    if(dept==='grading'){body.lg_grade_qty=parseInt(document.getElementById('da-lg')?.value||0);body.c_grade_qty=parseInt(document.getElementById('da-c')?.value||0);body.c_grade_action=document.getElementById('da-c-action')?.value;}
    if(dept==='bleach'){body.pieces_bleached=parseInt(document.getElementById('da-bleached')?.value||0);body.chemical_batch=document.getElementById('da-chem')?.value;}
    await api(`/api/dept/${dept}`,'POST',body);
    bootstrap.Modal.getInstance(document.getElementById('deptActModal')).hide();
    toast('Activity recorded');loadDeptPage(dept);
  }catch(e){toast(e.message,'danger');}
}



// ════════════════════════════════════════════════════════════
// Batch Move / Split / History
// ════════════════════════════════════════════════════════════

// ══════════════════════════════════════════════════════════
// BATCH MOVE / SPLIT / HISTORY
// ══════════════════════════════════════════════════════════
function openMove(batchId,currentDept,qty,targetDept=null){
  document.getElementById('mv-batch-id').value=batchId;
  document.getElementById('mv-info').textContent=`Batch #${batchId} — ${qty||'?'} pcs — currently: ${DLBL[currentDept]||currentDept||'?'}`;
  document.getElementById('mv-qty').value=qty||'';
  document.getElementById('mv-time').value='';document.getElementById('mv-by').value='';document.getElementById('mv-notes').value='';
  if(targetDept) document.getElementById('mv-dept').value=targetDept;
  new bootstrap.Modal(document.getElementById('batchMoveModal')).show();
}
async function confirmMove(){
  const id=document.getElementById('mv-batch-id').value;
  const body={to_department:document.getElementById('mv-dept').value,quantity:parseInt(document.getElementById('mv-qty').value),time_minutes:parseInt(document.getElementById('mv-time').value)||0,moved_by:document.getElementById('mv-by').value||'operator',notes:document.getElementById('mv-notes').value};
  // ── Laminating-log gate ─────────────────────────────────────────
  // Block the move if the batch is currently at laminating and has no
  // laminating_log entry yet — point the user at the Station Log to fill it.
  try{
    const batch = await api(`/api/batches/${id}`).catch(()=>null);
    if(batch && (batch.current_department||'').toLowerCase()==='laminating'){
      const hist = await api(`/api/batches/${id}/history`).catch(()=>null);
      const hasLam = !!(hist && (hist.laminating_logs||hist.laminating||[]).length);
      if(!hasLam){
        if(!confirm(
          `This batch hasn't been logged in the Laminating station yet.\n\n`+
          `OK = jump to Station Leader Hub and log laminating now (recommended)\n`+
          `Cancel = stay here`
        )){ return; }
        bootstrap.Modal.getInstance(document.getElementById('batchMoveModal'))?.hide();
        // Set scope to laminating + select this batch, then navigate
        try{
          localStorage.setItem('erp_pending_batch_select', String(id));
          loadPage('station-log');
          const ds = document.getElementById('sl-dept-scope'); if(ds){ ds.value='laminating'; slhSetScope(); }
          setTimeout(()=>{ try{ slSelectBatch(Number(id)); }catch{} }, 400);
        }catch{}
        return;
      }
    }
  }catch{}
  try{await api(`/api/batches/${id}/move`,'POST',body);bootstrap.Modal.getInstance(document.getElementById('batchMoveModal')).hide();toast('Batch moved');loadKanban();}catch(e){toast(e.message,'danger');}
}

function openSplit(batchId,qty){
  document.getElementById('sp-batch-id').value=batchId;
  document.getElementById('sp-info').textContent=`Batch #${batchId} — ${qty||'?'} pcs available`;
  document.getElementById('sp-qty').value='';document.getElementById('sp-notes').value='';
  new bootstrap.Modal(document.getElementById('batchSplitModal')).show();
}
async function confirmSplit(){
  const id=document.getElementById('sp-batch-id').value;
  const body={split_qty:parseInt(document.getElementById('sp-qty').value),reason:document.getElementById('sp-reason').value,new_dept:document.getElementById('sp-dept').value,notes:document.getElementById('sp-notes').value};
  try{await api(`/api/batches/${id}/split`,'POST',body);bootstrap.Modal.getInstance(document.getElementById('batchSplitModal')).hide();toast('Split created');loadKanban();}catch(e){toast(e.message,'danger');}
}

// ── Merge sibling batches (same prod_order, same dept) ─────────
async function openMergeBatch(batchId){
  let siblings = [];
  try {
    siblings = await api(`/api/batches/${batchId}/mergeable`);
  } catch(e){ toast('Could not load mergeable batches: '+e.message,'danger'); return; }
  if(!siblings || !siblings.length){
    toast('No mergeable sibling batches in this department','info');
    return;
  }
  const main = await api(`/api/batches/${batchId}`).catch(()=>null);
  if(!main){ toast('Batch not found','danger'); return; }
  const mainPcs = main.total_pcs ?? ((main.quantity||0) * (main.pallet_qty||1));
  // Build a quick selection prompt (works for 1+ siblings)
  const labels = siblings.map((s,i)=>{
    const p = s.total_pcs ?? ((s.quantity||0)*(s.pallet_qty||1));
    return `${i+1}. ${s.batch_number} — ${p.toLocaleString()} pcs`;
  });
  const choice = prompt(
    `Merge into batch ${main.batch_number} (${mainPcs.toLocaleString()} pcs)?\n\n`+
    `Select sibling batch to absorb (1–${siblings.length}):\n`+
    labels.join('\n')+'\n\nEnter number (or cancel):'
  );
  const idx = parseInt(choice) - 1;
  if(isNaN(idx) || idx < 0 || idx >= siblings.length) return;
  const other = siblings[idx];
  const otherPcs = other.total_pcs ?? ((other.quantity||0)*(other.pallet_qty||1));
  if(!confirm(
    `Merge:\n  • ${other.batch_number} (${otherPcs.toLocaleString()} pcs)\n`+
    `INTO:\n  • ${main.batch_number} (${mainPcs.toLocaleString()} pcs)\n\n`+
    `Result: ${main.batch_number} with ${(mainPcs+otherPcs).toLocaleString()} pcs.\n`+
    `${other.batch_number} will be deleted; its station logs will be moved into ${main.batch_number}.\n\nProceed?`
  )) return;
  try {
    const res = await api(`/api/batches/${batchId}/merge`,'POST',{other_batch_id: other.id});
    toast(`Merged → ${res.batch_number} (now ${(mainPcs+otherPcs).toLocaleString()} pcs)`,'success');
    // Refresh whatever view called this
    if(typeof loadDeptPage === 'function' && main.current_department) loadDeptPage(main.current_department);
    if(typeof loadLineBoard === 'function') loadLineBoard();
    if(typeof slLoadBatches === 'function') slLoadBatches();
  }catch(e){ toast('Merge failed: '+e.message,'danger'); }
}

async function showHist(batchId){
  try{
    const h=await api(`/api/batches/${batchId}/history`);
    document.getElementById('hist-body').innerHTML=h.length?`<table class="table table-sm"><thead class="table-light"><tr><th>Time</th><th>From</th><th>To</th><th>Qty</th><th>By</th><th>Notes</th></tr></thead>
      <tbody>${h.map(r=>`<tr><td><small>${(r.moved_at||'').slice(0,16)}</small></td><td><small>${DLBL[r.from_department]||r.from_department||'-'}</small></td><td><small>${DLBL[r.to_department]||r.to_department}</small></td><td>${fmt(r.quantity)}</td><td><small>${r.moved_by||''}</small></td><td><small>${r.notes||''}</small></td></tr>`).join('')}</tbody></table>`:'<p class="text-muted">No movement history.</p>';
    new bootstrap.Modal(document.getElementById('histModal')).show();
  }catch(e){toast(e.message,'danger');}
}



// ════════════════════════════════════════════════════════════
// AI — generateReport (daily report)
// ════════════════════════════════════════════════════════════

// ══════════════════════════════════════════════════════════
// AI
// ══════════════════════════════════════════════════════════
async function generateReport(){
  const date=document.getElementById('report-date').value;const type=document.getElementById('report-type').value;
  if(!date){toast('Select a date','warning');return;}
  const el=document.getElementById('report-output');
  el.innerHTML='<span class="text-muted"><i class="bi bi-hourglass-split me-2"></i>Generating...</span>';
  try{const r=await api('/api/ai/daily-report','POST',{date,report_type:type});el.innerHTML=`<div class="ai-msg ai">${marked.parse(r.report)}</div>`;}
  catch(e){el.innerHTML=`<div class="alert alert-danger">${e.message}</div>`;}
}
// Factory Assistant (chat + transcript + addChat/rmChat helpers) moved to /static/js/portal_admin.js


// ════════════════════════════════════════════════════════════
// Consumable Requests (Dept Leader)
// ════════════════════════════════════════════════════════════
// Auth + session lifecycle moved to /static/js/auth.js

// ══════════════════════════════════════════════════════════════
// CONSUMABLE REQUESTS (Dept Leader)
// ══════════════════════════════════════════════════════════════
let _crMaterials=[], _crMyDepts=[];

async function crLoad(){
  const status=document.getElementById('cr-filter-status').value;
  const reqs=await api(`/api/consumable-requests${status?'?status='+status:''}`).catch(()=>[]);
  if(!reqs) return;
  // Summary badges
  const counts={PENDING:0,PARTIAL:0,FULFILLED:0,CANCELLED:0};
  reqs.forEach(r=>{ if(counts[r.status]!==undefined) counts[r.status]++; });
  document.getElementById('cr-summary-row').innerHTML=`
    <div class="col-auto"><div class="card px-3 py-2 border-warning"><div class="small text-muted">Pending</div><div class="h5 mb-0 text-warning fw-bold">${counts.PENDING}</div></div></div>
    <div class="col-auto"><div class="card px-3 py-2 border-primary"><div class="small text-muted">Partial</div><div class="h5 mb-0 text-primary fw-bold">${counts.PARTIAL}</div></div></div>
    <div class="col-auto"><div class="card px-3 py-2 border-success"><div class="small text-muted">Fulfilled</div><div class="h5 mb-0 text-success fw-bold">${counts.FULFILLED}</div></div></div>
  `;
  const statusBadge={PENDING:'warning',PARTIAL:'primary',FULFILLED:'success',CANCELLED:'secondary'};
  const tbody=document.getElementById('cr-tbody');
  if(!reqs.length){tbody.innerHTML='<tr><td colspan="8" class="text-center text-muted py-3">No requests found.</td></tr>';return;}
  tbody.innerHTML=reqs.map(r=>`<tr>
    <td><code class="small">${r.request_id}</code></td>
    <td>${r.material_name||'—'} <small class="text-muted">(${r.unit||''})</small></td>
    <td><span class="badge bg-light text-dark border">${r.department}</span>${r.line_id?` <small>${r.line_id}</small>`:''}</td>
    <td class="text-end">${r.qty_requested}</td>
    <td class="text-end">${r.qty_fulfilled||0}</td>
    <td><span class="badge bg-${statusBadge[r.status]||'secondary'}">${r.status}</span></td>
    <td class="small text-muted">${(r.created_at||'').slice(0,10)}</td>
    <td>${r.status==='PENDING'?`<button class="btn btn-xs btn-outline-danger py-0 px-1" onclick="crCancel('${r.request_id}')"><i class="bi bi-x"></i></button>`:''}</td>
  </tr>`).join('');
}

async function crOpenNew(){
  if(!_crMaterials.length){
    _crMaterials=await api('/api/consumable-materials').catch(()=>[]);
  }
  const sel=document.getElementById('cr-material-id');
  sel.innerHTML='<option value="">Select material...</option>'+
    _crMaterials.map(m=>`<option value="${m.id}" data-unit="${m.unit}" data-cost="${m.unit_cost}" data-stock="${m.current_stock}">${m.name} (${m.unit}) — Stock: ${m.current_stock}</option>`).join('');
  sel.onchange=()=>{
    const opt=sel.options[sel.selectedIndex];
    document.getElementById('cr-unit-label').textContent=opt.dataset.unit||'unit';
    document.getElementById('cr-mat-stock').textContent=`Current stock: ${opt.dataset.stock||0} ${opt.dataset.unit||''}`;
    crUpdateCostEst();
  };
  // Dept select from user's departments
  _crMyDepts=getCurrentDepts();
  const deptSel=document.getElementById('cr-department');
  const deptSet=[...new Set(_crMyDepts.map(d=>d.department))];
  deptSel.innerHTML=deptSet.length
    ? deptSet.map(d=>`<option value="${d}">${STATION_LABEL[d]||d}</option>`).join('')
    : '<option value="">— select —</option>';
  document.getElementById('cr-mat-stock').textContent='';
  document.getElementById('cr-cost-est').textContent='';
}

function crUpdateCostEst(){
  const sel=document.getElementById('cr-material-id');
  const opt=sel.options[sel.selectedIndex];
  const qty=parseFloat(document.getElementById('cr-qty').value)||0;
  const cost=parseFloat(opt?.dataset?.cost)||0;
  if(qty>0&&cost>0)
    document.getElementById('cr-cost-est').textContent=`Est. cost: ฿${(qty*cost).toFixed(2)}`;
  else
    document.getElementById('cr-cost-est').textContent='';
}

async function crSubmitNew(){
  const mid=parseInt(document.getElementById('cr-material-id').value);
  const dept=document.getElementById('cr-department').value;
  const qty=parseFloat(document.getElementById('cr-qty').value)||0;
  if(!mid||!dept||qty<=0){toast('Material, department, and quantity are required','danger');return;}
  const body={
    material_id:mid,department:dept,
    line_id:document.getElementById('cr-line-id').value||null,
    qty_requested:qty,
    priority:parseInt(document.getElementById('cr-priority')?.value)||2,
    needed_by:document.getElementById('cr-needed-by')?.value||null,
    needed_time:document.getElementById('cr-needed-time')?.value||null,
    notes:document.getElementById('cr-notes').value||null
  };
  try{
    await api('/api/consumable-requests','POST',body);
    bootstrap.Modal.getInstance(document.getElementById('newConsumableModal')).hide();
    toast('Request submitted');
    crLoad();
  }catch(e){toast(e.message,'danger');}
}

async function crCancel(rid){
  if(!confirm('Cancel this request?')) return;
  try{await api(`/api/consumable-requests/${rid}/cancel`,'PATCH');toast('Cancelled');crLoad();}
  catch(e){toast(e.message,'danger');}
}

// Warehouse Supply Queue moved to /static/js/portal_warehouse.js

// Dept Cost Report moved to /static/js/portal_accounting.js



// ════════════════════════════════════════════════════════════
// Sales Orders
// ════════════════════════════════════════════════════════════
// ══════════════════════════════════════════════════════════
// SALES ORDERS
// ══════════════════════════════════════════════════════════
let _allOrders=[];
async function loadOrders(){
  try{
    const rows=await api('/api/purchase-orders');
    _allOrders=rows;
    const tbody=document.querySelector('#orders-table tbody');
    if(!tbody) return;
    if(!rows.length){tbody.innerHTML='<tr><td colspan="7" class="text-center text-muted py-4">No sales orders yet. <a href="#" onclick="event.preventDefault();document.getElementById(\'btn-new-po\')&&document.getElementById(\'btn-new-po\').click()">Create one in Order Intake.</a></td></tr>';return;}
    tbody.innerHTML=rows.map(o=>`<tr>
      <td><b>${o.po_number||'#'+o.id}</b></td>
      <td>${o.product_name||'—'}</td>
      <td>${fmt(o.total_qty||o.quantity||0)}</td>
      <td>${fmt(o.produced_qty||0)}</td>
      <td>${fmtD(o.delivery_date||o.required_date)}</td>
      <td>${prioBadge(o.priority||2)}</td>
      <td>${statusBadge(o.status||'open')}</td>
    </tr>`).join('');
  }catch(e){const tb=document.querySelector('#orders-table tbody');if(tb)tb.innerHTML=`<tr><td colspan="7" class="text-danger text-center py-3">${e.message}</td></tr>`;}
}
function openOrderModal(){}



// ════════════════════════════════════════════════════════════
// Finished Goods
// ════════════════════════════════════════════════════════════
// ══════════════════════════════════════════════════════════
// FINISHED GOODS
// ══════════════════════════════════════════════════════════
let _allFg=[];
async function loadFg(){
  const rows=await api('/api/fg');
  _allFg=rows; products=rows; // keep products in sync for other pages that use it
  renderFg(rows);
}
function renderFg(rows){
  document.getElementById('fg-count').textContent=rows.length;
  if(!rows.length){
    document.querySelector('#fg-table tbody').innerHTML=`<tr><td colspan="6" class="text-center py-5">
      <i class="bi bi-grid text-muted" style="font-size:2rem"></i>
      <div class="text-muted mt-2">No finished goods yet.</div>
      <button class="btn btn-primary btn-sm mt-3" onclick="navigateTo('bom');setTimeout(()=>document.querySelector('#bom-main-tabs .nav-link')?.click(),100)">
        <i class="bi bi-plus-lg me-1"></i>Create via BOM Builder →
      </button>
    </td></tr>`;
    return;
  }
  document.querySelector('#fg-table tbody').innerHTML=rows.map(s=>`<tr>
    <td><code class="text-primary fw-bold">${s.code}</code></td>
    <td>${s.name||''}</td>
    <td>${s.thickness_mm||'-'} mm</td>
    <td>${s.width_mm||'-'} × ${s.length_mm||'-'}</td>
    <td class="text-center">${s.pallet_qty||'-'}</td>
    <td><button class="btn btn-xs btn-outline-primary py-0 px-2" onclick="showFgBom('${s.code}')">BOM</button></td>
  </tr>`).join('');
}
function filterFg(q){
  const s=q.toLowerCase();
  renderFg(s?_allFg.filter(r=>r.code.toLowerCase().includes(s)||r.name.toLowerCase().includes(s)):_allFg);
}
async function showFgBom(code){
  const b=await api(`/api/fg/${code}/bom`);
  // Jump to BOM page with this SKU highlighted
  showPage('bom');
  document.getElementById('bom-search').value=code;
  searchBom(code);
}
// Keep legacy loadProducts working for other parts of the app
async function loadProducts(){await loadFg();}
function openProductModal(){}
async function saveProduct(){}

// BOM structured view (list + matPill/gluePill/packPill) moved to /static/js/portal_planning.js
// AI — generateReport (daily report) moved to /static/js/portal_planning.js



// ════════════════════════════════════════════════════════════
// Dashboard (loadDashboard)
// ════════════════════════════════════════════════════════════
// ══════════════════════════════════════════════════════════
// DASHBOARD
// ══════════════════════════════════════════════════════════
async function loadDashboard(){
  try{
    const [stats,flow,matrix,porders]=await Promise.all([
      api('/api/dashboard/stats'),
      api('/api/planning/flow').catch(()=>({})),
      api('/api/planning/po-matrix').catch(()=>({orders:[]})),
      api('/api/production-orders').catch(()=>[])
    ]);
    // Stat cards
    document.getElementById('dash-stats').innerHTML=[
      {val:stats.total_products,lbl:'Products',ico:'bi-grid',c:'primary'},
      {val:stats.total_materials,lbl:'Materials',ico:'bi-stack',c:'success'},
      {val:stats.total_orders,lbl:'Sales Orders',ico:'bi-receipt',c:'info'},
      {val:stats.active_machines,lbl:'Active Machines',ico:'bi-gear',c:'warning'},
    ].map(s=>`<div class="col-6 col-md-3"><div class="stat-card d-flex justify-content-between align-items-start">
      <div><div class="val text-${s.c}">${fmt(s.val)}</div><div class="lbl">${s.lbl}</div></div>
      <i class="bi ${s.ico} ico text-${s.c}"></i></div></div>`).join('');
    // WIP
    let total=0;const chips=DEPTS.map(d=>{const c=(flow[d]||[]).length;total+=c;return `<span class="badge bg-secondary">${DLBL[d]}: ${c}</span>`;}).join('');
    document.getElementById('dash-wip-row').innerHTML=`<div class="col-12"><div class="card p-3"><div class="d-flex flex-wrap gap-2 align-items-center"><span class="fw-bold text-muted small text-uppercase">WIP</span>${chips}<span class="ms-auto badge bg-primary">Total ${total} batches</span></div></div></div>`;
    // PO Matrix
    const orders=matrix.orders||[];
    if(orders.length){
      document.getElementById('po-matrix').innerHTML=`<table class="table table-sm table-bordered" style="font-size:.78rem;white-space:nowrap">
        <thead class="table-light"><tr><th>Order</th><th>PO</th><th>SKU</th><th>Qty</th>${DEPTS.map(d=>`<th class="text-center">${DLBL[d]}</th>`).join('')}<th>Status</th></tr></thead>
        <tbody>${orders.map(o=>`<tr>
          <td><b>${o.order_number||'#'+o.id}</b></td><td>${o.po_number||'-'}</td>
          <td>${o.product_name||'-'}</td><td>${fmt(o.total_quantity)}</td>
          ${DEPTS.map(d=>{const q=(o.dept_dist||{})[d]||0;return `<td class="text-center">${q?`<span style="background:#2d6e2d;color:#fff;border-radius:10px;padding:1px 6px;font-size:.7rem">${fmt(q)}</span>`:''}</td>`;}).join('')}
          <td>${statusBadge(o.status)}</td></tr>`).join('')}</tbody></table>`;
    } else {
      document.getElementById('po-matrix').innerHTML='<p class="text-muted small">No active production orders.</p>';
    }
    // Active prod orders
    const active=(porders||[]).filter(o=>['in_progress','planned'].includes(o.status));
    document.getElementById('dash-po-list').innerHTML=active.length?active.map(o=>`
      <div class="d-flex justify-content-between align-items-center border-bottom py-2">
        <div><small class="fw-bold">${o.order_number||'#'+o.id}</small><small class="text-muted ms-2">${o.product_name||''}</small></div>
        <div class="d-flex gap-2">${statusBadge(o.status)}</div>
      </div>`).join(''):'<p class="text-muted small">No active orders.</p>';
    // Chart
    const logs=await api('/api/production-logs?limit=100').catch(()=>[]);
    const byD={};logs.forEach(l=>{if(!byD[l.log_date])byD[l.log_date]={p:0,a:0};byD[l.log_date].p+=l.planned_qty||0;byD[l.log_date].a+=l.actual_qty||0;});
    const lbls=Object.keys(byD).sort().slice(-7);
    const ctx=document.getElementById('dashChart').getContext('2d');
    if(dashChart) dashChart.destroy();
    dashChart=new Chart(ctx,{type:'bar',data:{labels:lbls,datasets:[
      {label:'Planned',data:lbls.map(d=>byD[d].p),backgroundColor:'rgba(59,130,246,.3)',borderColor:'#2d6e2d',borderWidth:1},
      {label:'Actual',data:lbls.map(d=>byD[d].a),backgroundColor:'rgba(16,185,129,.3)',borderColor:'#10b981',borderWidth:1}
    ]},options:{responsive:true,plugins:{legend:{position:'top'}},scales:{y:{beginAtZero:true}}}});
  }catch(e){console.error(e);}
}


// ── Page loader registry ────────────────────────────────────
// ── Opening WIP import ───────────────────────────────────────
let _wipLastReport = null;
function loadWipImport(){
  document.getElementById('wip-results').innerHTML = '';
  document.getElementById('wip-summary').textContent = '';
  const btn = document.getElementById('wip-import-btn');
  if(btn) btn.disabled = true;
  _wipLastReport = null;
}
async function _wipSend(mode){
  const f = document.getElementById('wip-file').files[0];
  if(!f){ toast('Choose a CSV file first','warning'); return null; }
  const fd = new FormData(); fd.append('file', f);
  const token = localStorage.getItem('erp_token')||'';
  const r = await fetch('/api/upload/wip?mode='+mode, {
    method:'POST', headers:{'X-Auth-Token':token}, body:fd });
  if(r.status===401){ doLogout(); return null; }
  if(!r.ok){ const e=await r.json().catch(()=>({detail:r.statusText})); throw new Error(e.detail||r.statusText); }
  return r.json();
}
function _wipRender(res){
  _wipLastReport = res;
  const btn = document.getElementById('wip-import-btn');
  const committed = res.mode === 'commit';
  document.getElementById('wip-summary').innerHTML =
    `<b>${res.valid}</b> valid · <b class="${res.invalid?'text-danger':''}">${res.invalid}</b> invalid` +
    (committed ? ` · <b class="text-success">${res.created} imported</b>` : '');
  if(btn) btn.disabled = committed || res.valid === 0;
  const rowsHtml = res.report.map(r=>{
    const sug = Object.entries(r.suggestions||{}).map(([k,v])=>
      `<span class="badge bg-warning-subtle text-dark border me-1">${k} → ${v}</span>`).join('');
    const errs = (r.errors||[]).map(e=>`<div class="text-danger">${e}</div>`).join('');
    const status = r.created_batch
      ? `<span class="badge bg-success">imported ${r.created_batch}</span>`
      : (r.ok ? '<span class="badge bg-primary">ready</span>'
              : '<span class="badge bg-danger">fix</span>');
    return `<tr class="${r.ok?'':'table-danger'}">
      <td class="small">${r.row}</td>
      <td class="small"><b>${r.sku_code||'—'}</b></td>
      <td class="small">${r.line||'—'}</td>
      <td class="small">${r.current_station||'—'}</td>
      <td class="small text-end">${r.quantity||'—'}</td>
      <td class="small text-end">${r.pcs||''}</td>
      <td class="small">${r.location?`<span class="badge ${r.location==='WLWH'?'bg-info-subtle text-info-emphasis':'bg-secondary-subtle text-secondary-emphasis'}">${r.location}</span>`:''}</td>
      <td class="small">${r.batch_ref||''}</td>
      <td>${status}${errs?'<div class="small mt-1">'+errs+'</div>':''}${sug?'<div class="small mt-1">'+sug+'</div>':''}</td>
    </tr>`;
  }).join('');
  document.getElementById('wip-results').innerHTML = `
    <div class="table-responsive"><table class="table table-sm table-hover align-middle">
      <thead class="table-light"><tr>
        <th>#</th><th>SKU</th><th>Line</th><th>Station</th><th class="text-end">Pallets</th><th class="text-end">Pcs</th><th>Loc</th><th>Ref</th><th>Status</th>
      </tr></thead><tbody>${rowsHtml}</tbody></table></div>`;
}
async function wipValidate(){
  try{ const res = await _wipSend('validate'); if(res) _wipRender(res); }
  catch(e){ toast('Validation failed: '+e.message,'danger'); }
}
async function wipCommit(){
  if(!_wipLastReport || _wipLastReport.valid===0){ toast('Validate first','warning'); return; }
  if(!confirm(`Import ${_wipLastReport.valid} valid WIP batch(es)? Invalid rows are skipped.`)) return;
  try{
    const res = await _wipSend('commit');
    if(res){ _wipRender(res); toast(`${res.created} WIP batch(es) imported`,'success'); }
  }catch(e){ toast('Import failed: '+e.message,'danger'); }
}

// ── Bulk Order (PO) import ───────────────────────────────────
let _ordLastReport = null;
function loadOrdersImport(){
  document.getElementById('ord-results').innerHTML = '';
  document.getElementById('ord-summary').textContent = '';
  const btn = document.getElementById('ord-import-btn');
  if(btn) btn.disabled = true;
  _ordLastReport = null;
}
async function _ordSend(mode){
  const f = document.getElementById('ord-file').files[0];
  if(!f){ toast('Choose a CSV or Excel file first','warning'); return null; }
  const fd = new FormData(); fd.append('file', f);
  const token = localStorage.getItem('erp_token')||'';
  const r = await fetch('/api/upload/customer-orders?mode='+mode, {
    method:'POST', headers:{'X-Auth-Token':token}, body:fd });
  if(r.status===401){ doLogout(); return null; }
  if(!r.ok){ const e=await r.json().catch(()=>({detail:r.statusText})); throw new Error(e.detail||r.statusText); }
  return r.json();
}
function _ordRender(res){
  _ordLastReport = res;
  const btn = document.getElementById('ord-import-btn');
  const committed = res.mode === 'commit';
  document.getElementById('ord-summary').innerHTML =
    `<b>${res.valid}</b> valid · <b class="${res.invalid?'text-danger':''}">${res.invalid}</b> invalid` +
    (committed ? ` · <b class="text-success">${res.created_pos} PO(s), ${res.created_lines} line(s), ${res.created_customers} new customer(s)</b>` : '');
  if(btn) btn.disabled = committed || res.valid === 0;
  const rowsHtml = res.report.map(r=>{
    const sug = Object.entries(r.suggestions||{}).map(([k,v])=>
      `<span class="badge bg-warning-subtle text-dark border me-1">${k} → ${v}</span>`).join('');
    const errs = (r.errors||[]).map(e=>`<div class="text-danger">${e}</div>`).join('');
    const status = r.created
      ? `<span class="badge bg-success">opened ${r.created}</span>`
      : (r.ok ? '<span class="badge bg-primary">ready</span>'
              : '<span class="badge bg-danger">fix</span>');
    return `<tr class="${r.ok?'':'table-danger'}">
      <td class="small">${r.row}</td>
      <td class="small">${r.customer||'—'}</td>
      <td class="small"><b>${r.po_number||'—'}</b></td>
      <td class="small">${r.sku_code||'—'}</td>
      <td class="small text-end">${r.pallets||'—'}</td>
      <td class="small">${r.production_line||'—'}</td>
      <td>${status}${errs?'<div class="small mt-1">'+errs+'</div>':''}${sug?'<div class="small mt-1">'+sug+'</div>':''}</td>
    </tr>`;
  }).join('');
  document.getElementById('ord-results').innerHTML = `
    <div class="table-responsive"><table class="table table-sm table-hover align-middle">
      <thead class="table-light"><tr>
        <th>#</th><th>Customer</th><th>PO #</th><th>SKU</th><th class="text-end">Pallets</th><th>Line</th><th>Status</th>
      </tr></thead><tbody>${rowsHtml}</tbody></table></div>`;
}
async function ordValidate(){
  try{ const res = await _ordSend('validate'); if(res) _ordRender(res); }
  catch(e){ toast('Validation failed: '+e.message,'danger'); }
}
async function ordCommit(){
  if(!_ordLastReport || _ordLastReport.valid===0){ toast('Validate first','warning'); return; }
  if(!confirm(`Open POs from ${_ordLastReport.valid} valid line(s)? Invalid rows and existing PO numbers are skipped.`)) return;
  try{
    const res = await _ordSend('commit');
    if(res){ _ordRender(res); toast(`${res.created_pos} PO(s) opened · ${res.created_lines} line(s)`,'success'); }
  }catch(e){ toast('Import failed: '+e.message,'danger'); }
}

// ── Customers (rudimentary CRM) ──────────────────────────────
let _custCache = [];
async function loadCustomers(){
  const tb = document.getElementById('cust-tbody');
  try{
    _custCache = await api('/api/customers?active_only=false');
    if(!_custCache.length){ tb.innerHTML='<tr><td colspan="7" class="text-muted small p-3">No customers yet. Click <b>New Customer</b> to add one.</td></tr>'; return; }
    tb.innerHTML = _custCache.map(c=>`<tr class="${c.is_active?'':'text-muted'}">
      <td class="small fw-semibold">${c.name}${c.is_active?'':' <span class="badge bg-secondary">inactive</span>'}</td>
      <td class="small">${c.contact_person||''}</td><td class="small">${c.phone||''}</td><td class="small">${c.email||''}</td>
      <td class="text-end small">${c.order_count||0}</td>
      <td class="small">${(c.last_order||'').slice(0,10)||'—'}</td>
      <td class="text-end text-nowrap">
        <button class="btn btn-sm btn-outline-secondary py-0 px-1" onclick="custOpenForm(${c.id})" title="Edit"><i class="bi bi-pencil"></i></button>
        <button class="btn btn-sm btn-outline-primary py-0 px-1" onclick="custViewOrders(${c.id})" title="Order history"><i class="bi bi-folder2-open"></i></button>
      </td></tr>`).join('');
  }catch(e){ tb.innerHTML='<tr><td colspan="7" class="text-danger small p-3">'+e.message+'</td></tr>'; }
}
function custOpenForm(id){
  const c = id ? _custCache.find(x=>x.id===id) : null;
  document.getElementById('cust-modal-title').textContent = c?'Edit Customer':'New Customer';
  document.getElementById('cust-id').value = c?c.id:'';
  document.getElementById('cust-name').value = c?c.name:'';
  document.getElementById('cust-contact').value = c?(c.contact_person||''):'';
  document.getElementById('cust-phone').value = c?(c.phone||''):'';
  document.getElementById('cust-email').value = c?(c.email||''):'';
  document.getElementById('cust-address').value = c?(c.address||''):'';
  document.getElementById('cust-notes').value = c?(c.notes||''):'';
  document.getElementById('cust-active-wrap').style.display = c?'':'none';
  document.getElementById('cust-active').checked = c? !!c.is_active : true;
  bootstrap.Modal.getOrCreateInstance(document.getElementById('custModal')).show();
}
async function custSave(){
  const id = document.getElementById('cust-id').value;
  const body = {
    name: document.getElementById('cust-name').value.trim(),
    contact_person: document.getElementById('cust-contact').value.trim(),
    phone: document.getElementById('cust-phone').value.trim(),
    email: document.getElementById('cust-email').value.trim(),
    address: document.getElementById('cust-address').value.trim(),
    notes: document.getElementById('cust-notes').value.trim(),
    is_active: document.getElementById('cust-active').checked,
  };
  if(!body.name){ toast('Customer name is required','danger'); return; }
  try{
    await api(id?('/api/customers/'+id):'/api/customers', id?'PUT':'POST', body);
    bootstrap.Modal.getInstance(document.getElementById('custModal')).hide();
    toast('Customer saved'); loadCustomers();
  }catch(e){ toast('Save failed: '+e.message,'danger'); }
}
async function custViewOrders(id){
  try{
    const r = await api('/api/customers/'+id+'/orders');
    document.getElementById('cust-orders-title').textContent = 'Orders — '+r.customer.name;
    const o = r.orders||[];
    document.getElementById('cust-orders-body').innerHTML = o.length
      ? `<div class="table-responsive"><table class="table table-sm mb-0"><thead class="table-light"><tr><th>PO #</th><th>Order date</th><th>Delivery</th><th>Status</th></tr></thead><tbody>`+
        o.map(x=>`<tr><td class="small fw-semibold">${x.po_number}</td><td class="small">${(x.order_date||'').slice(0,10)}</td><td class="small">${(x.delivery_date||'').slice(0,10)||'—'}</td><td class="small">${x.status||''}</td></tr>`).join('')+
        '</tbody></table></div>'
      : '<div class="text-muted small">No orders yet for this customer.</div>';
    bootstrap.Modal.getOrCreateInstance(document.getElementById('custOrdersModal')).show();
  }catch(e){ toast('Could not load orders: '+e.message,'danger'); }
}
// Populate a <select id="po-customer"> with registered customers (Order Intake).
async function custFillSelect(selectedName){
  const sel = document.getElementById('po-customer');
  if(!sel || sel.tagName !== 'SELECT') return;
  try{
    const list = await api('/api/customers');   // active only
    sel.innerHTML = '<option value="">— select customer —</option>' +
      list.map(c=>`<option value="${c.name}">${c.name}</option>`).join('');
    if(selectedName) sel.value = selectedName;
  }catch(e){ /* leave empty */ }
}

Object.assign(PAGE_LOADERS, {
  'customers':           loadCustomers,
  'wip-import':          loadWipImport,
  'orders-import':       loadOrdersImport,
  'dashboard':           loadDashboard,
  'vcmx':                vcmxLoad,
  'vcmx-lam':            vcmxLamLoad,
  'material-shortfalls': msfLoad,
  'fc-hub':              fcHubLoad,
  'bom':                 loadBom,
  'station-log':         loadStationLog,
  'glue-mix-station':    gmLoad,
  'station-tools':       stLoad,
  'order-intake':        loadOrderIntake,
  'line-board':          loadLineBoard,
  'prod-flow':           loadKanban,
  'prod-logs':           loadLogs,
  'prod-reports':        () => { prSetPeriod(30); loadProdReports(); },
  'forklift-report':     frptLoad,
  'consumable-requests': crLoad,
  'orders'                 : loadOrders,
  'fg'                     : loadFg,
  'products'               : loadFg,
});
