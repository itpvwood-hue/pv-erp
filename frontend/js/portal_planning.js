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


// ── Page loader registry ────────────────────────────────────
Object.assign(PAGE_LOADERS, {
  'vcmx':     vcmxLoad,
  'vcmx-lam': vcmxLamLoad,
});
