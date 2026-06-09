/* PVWood ERP - Accounting Portal.
   Carved out of index.html. Self-registers its pages via
   Object.assign(PAGE_LOADERS, ...) at the file tail.

   Globals declared:
       _accMovements, _accProduction
       _accDateRange, loadAccounting, + various accounting helpers
       dcLoad, dcLoadDetail (dept costs)

   Reads but doesn't define: STATION_LABEL, fmtMoney/fmtNum (core.js),
   _accFmtB / _accFmtU (core.js — currency-aware THB / USD formatters).
*/


// ════════════════════════════════════════════════════════════
// Accounting Hub
// ════════════════════════════════════════════════════════════
// ══════════════════════════════════════════════════════════
// ACCOUNTING HUB
// ══════════════════════════════════════════════════════════
let _accMovements=[], _accProduction=[];
function _accDateRange(){
  const f=document.getElementById('acc-date-from');
  const t=document.getElementById('acc-date-to');
  if(!f.value){
    const d=new Date(); d.setDate(d.getDate()-30);
    f.value=d.toISOString().slice(0,10);
  }
  if(!t.value) t.value=new Date().toISOString().slice(0,10);
  return {from:f.value, to:t.value};
}
// _accFmt / _accFmtN now alias to fmtMoney / fmtNum (declared centrally).

async function loadAccounting(){
  const {from,to}=_accDateRange();
  const qs=`?from_date=${from}&to_date=${to}`;
  try{
    const [sum, mov, prod]=await Promise.all([
      api('/api/accounting/summary'+qs),
      api('/api/accounting/stock-movements'+qs),
      api('/api/accounting/production-output'+qs),
    ]);
    _accMovements=mov.rows||mov||[];
    _accProduction=prod.rows||prod||[];
    accRenderKpi(sum||{});
    accRenderSummary(sum||{});
    accRenderMovements(_accMovements);
    accRenderProduction(_accProduction);
  }catch(e){
    console.error('Accounting load error', e);
    document.getElementById('acc-kpi-row').innerHTML=`<div class="col-12"><div class="alert alert-danger small mb-0">Failed to load accounting data: ${e.message||e}</div></div>`;
  }
}

function accRenderKpi(s){
  const cards=[
    {label:'Consumption Value',  value:_accFmt(s.total_consumption_value), icon:'bi-cash-coin',     bg:'success'},
    {label:'FC Transfers',       value:_accFmt(s.total_fc_transfer_value), icon:'bi-arrow-left-right',bg:'primary'},
    {label:'Batch Releases (FC→Lam)', value:_accFmtN(s.batch_releases),    icon:'bi-box-arrow-right', bg:'info'},
    {label:'Good Pcs Produced',  value:_accFmtN(s.total_good_pcs),         icon:'bi-stack',           bg:'warning'},
    {label:'Yield %',            value:s.yield_pct!=null?Number(s.yield_pct).toFixed(1)+'%':'—', icon:'bi-percent', bg:'secondary'},
  ];
  document.getElementById('acc-kpi-row').innerHTML=cards.map(c=>`
    <div class="col-md col-6">
      <div class="card border-${c.bg} h-100">
        <div class="card-body py-2 px-3">
          <div class="small text-muted"><i class="bi ${c.icon} me-1"></i>${c.label}</div>
          <div class="fs-5 fw-semibold">${c.value}</div>
        </div>
      </div>
    </div>`).join('');
}

function accRenderSummary(s){
  const dept=(s.dept_costs||[]);
  document.getElementById('acc-dept-tbody').innerHTML = dept.length
    ? dept.map(r=>`<tr><td>${(r.department||'—').toString().toUpperCase()}</td><td class="text-end">${_accFmtN(r.request_count)}</td><td class="text-end">${_accFmt(r.total_cost)}</td></tr>`).join('')
    : '<tr><td colspan="3" class="text-center text-muted py-3">No data</td></tr>';
  // Build "Top Materials Consumed" from the movements feed
  const tally={};
  (_accMovements||[]).forEach(r=>{
    const k=r.material_code||r.material_name||'—';
    if(!tally[k]) tally[k]={name:r.material_name||k, qty:0, value:0};
    tally[k].qty   += Number(r.qty||0);
    tally[k].value += Number(r.cost_impact||0);
  });
  const mats=Object.values(tally).sort((a,b)=>b.value-a.value).slice(0,15);
  document.getElementById('acc-mat-tbody').innerHTML = mats.length
    ? mats.map(r=>`<tr><td>${r.name}</td><td class="text-end">${_accFmtN(r.qty)}</td><td class="text-end">${_accFmt(r.value)}</td></tr>`).join('')
    : '<tr><td colspan="3" class="text-center text-muted py-3">No data</td></tr>';
}

function _accMovRow(r){
  const dt = r.ts||r.moved_at||r.date||r.created_at||'';
  return `<tr>
    <td class="small">${dt?String(dt).slice(0,16).replace('T',' '):'—'}</td>
    <td><span class="badge bg-light text-dark">${r.kind||r.source||'—'}</span></td>
    <td>${(r.dept||r.department||'—')}${r.line_id||r.line?' / '+(r.line_id||r.line):''}</td>
    <td><b>${r.material_code||''}</b> ${r.material_name||''}</td>
    <td class="text-end">${_accFmtN(r.qty)}</td>
    <td class="small text-muted">${r.unit||''}</td>
    <td class="text-end small">${_accFmt(r.unit_cost)}</td>
    <td class="text-end fw-semibold">${_accFmt(r.cost_impact)}</td>
    <td class="small">${r.ref||'—'}</td>
    <td class="small">${r.actor||'—'}</td>
  </tr>`;
}
function accRenderMovements(rows){
  const tb=document.getElementById('acc-mov-tbody');
  tb.innerHTML = rows.length
    ? rows.map(_accMovRow).join('')
    : '<tr><td colspan="10" class="text-center text-muted py-3">No stock movements in this date range</td></tr>';
}
function accFilterMovements(q){
  q=(q||'').toLowerCase();
  const filtered=!q?_accMovements:_accMovements.filter(r=>
    JSON.stringify(r).toLowerCase().includes(q));
  accRenderMovements(filtered);
}

function _accProdRow(r){
  return `<tr>
    <td class="small">${r.date||'—'}</td>
    <td>${(r.dept||'—').toString().toUpperCase()}</td>
    <td>${r.line||'—'}</td>
    <td>${r.sku||'—'}</td>
    <td class="text-end">${_accFmtN(r.pcs_in)}</td>
    <td class="text-end fw-semibold">${_accFmtN(r.pcs_out)}</td>
    <td class="text-end">${r.yield_pct!=null?Number(r.yield_pct).toFixed(1)+'%':'—'}</td>
    <td class="text-end">${_accFmtN(r.defects)}</td>
  </tr>`;
}
function accRenderProduction(rows){
  const tb=document.getElementById('acc-prod-tbody');
  tb.innerHTML = rows.length
    ? rows.map(_accProdRow).join('')
    : '<tr><td colspan="8" class="text-center text-muted py-3">No production output in this date range</td></tr>';
}
function accFilterProduction(q){
  q=(q||'').toLowerCase();
  const filtered=!q?_accProduction:_accProduction.filter(r=>
    JSON.stringify(r).toLowerCase().includes(q));
  accRenderProduction(filtered);
}

function accExport(kind){
  const {from,to}=_accDateRange();
  const ep = kind==='movements' ? 'stock-movements' : 'production';
  const url=`/api/export/accounting/${ep}?from_date=${from}&to_date=${to}`;
  window.open(url,'_blank');
}

// Tab switcher
document.addEventListener('click', e=>{
  const t=e.target.closest('[data-acc-tab]');
  if(!t) return;
  e.preventDefault();
  document.querySelectorAll('#acc-tabs .nav-link').forEach(n=>n.classList.remove('active'));
  t.classList.add('active');
  const which=t.dataset.accTab;
  document.querySelectorAll('.acc-pane').forEach(p=>p.classList.add('d-none'));
  const pane=document.getElementById('acc-pane-'+which);
  if(pane) pane.classList.remove('d-none');
});




// ════════════════════════════════════════════════════════════
// Dept Cost Report
// ════════════════════════════════════════════════════════════
// ══════════════════════════════════════════════════════════════
// DEPT COST REPORT
// ══════════════════════════════════════════════════════════════
async function dcLoad(){
  const month=document.getElementById('dc-month').value;
  const rows=await api(`/api/dept-costs${month?'?month_year='+month:''}`).catch(()=>[]);
  if(!rows) return;
  const totalCost=rows.reduce((s,r)=>s+r.total_cost,0);
  const topDept=rows[0]?.department||'—';
  document.getElementById('dc-kpi-row').innerHTML=`
    <div class="col-6 col-md-auto"><div class="card px-3 py-2"><div class="small text-muted">Total Cost (Month)</div><div class="h4 mb-0 fw-bold text-success">฿${totalCost.toFixed(2)}</div></div></div>
    <div class="col-6 col-md-auto"><div class="card px-3 py-2"><div class="small text-muted">Top Cost Dept</div><div class="h4 mb-0 fw-bold">${STATION_LABEL[topDept]||topDept}</div></div></div>
    <div class="col-6 col-md-auto"><div class="card px-3 py-2"><div class="small text-muted">Departments Active</div><div class="h4 mb-0 fw-bold">${rows.length}</div></div></div>
  `;
  if(!rows.length){
    document.getElementById('dc-summary-tbody').innerHTML='<tr><td colspan="5" class="text-center text-muted py-3">No cost data for this month.</td></tr>';
    return;
  }
  document.getElementById('dc-summary-tbody').innerHTML=rows.map(r=>`<tr style="cursor:pointer" onclick="dcLoadDetail('${r.department}','${r.line_id||''}')">
    <td><b>${STATION_LABEL[r.department]||r.department}</b></td>
    <td>${r.line_id||'All'}</td>
    <td class="text-end">${r.request_count}</td>
    <td class="text-end fw-bold">฿${r.total_cost.toFixed(2)}</td>
    <td class="small text-muted" style="max-width:220px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis" title="${(r.materials_used||'').replace(/"/g,'&quot;')}">${r.materials_used||'—'}</td>
  </tr>`).join('');
}

async function dcLoadDetail(dept,line){
  const month=document.getElementById('dc-month').value;
  const rows=await api(`/api/dept-costs/detail?month_year=${month||''}&department=${dept}`).catch(()=>[]);
  if(!rows) return;
  document.getElementById('dc-detail-title').textContent=`Detail — ${STATION_LABEL[dept]||dept} ${line?'· '+line:''}`;
  document.getElementById('dc-detail-card').style.display='';
  document.getElementById('dc-detail-tbody').innerHTML=rows.map(r=>`<tr>
    <td class="small text-muted text-nowrap">${(r.created_at||'').slice(0,10)}</td>
    <td><code class="small text-nowrap">${r.request_id||'—'}</code></td>
    <td style="max-width:180px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis" title="${(r.material_name||'').replace(/"/g,'&quot;')}">${r.material_name||'—'} <small class="text-muted">(${r.unit||''})</small></td>
    <td class="text-end text-nowrap">${r.qty}</td>
    <td class="text-end text-nowrap">฿${parseFloat(r.unit_cost||0).toFixed(2)}</td>
    <td class="text-end fw-bold text-nowrap">฿${parseFloat(r.total_cost||0).toFixed(2)}</td>
    <td class="small text-nowrap">${r.requester_name||'—'}</td>
  </tr>`).join('');
}




// ════════════════════════════════════════════════════════════
// Purchasing Hub
// ════════════════════════════════════════════════════════════
// ══════════════════════════════════════════════════════════════
// PURCHASING HUB
// ══════════════════════════════════════════════════════════════
let _prRows=[], _prMaterials=[], _allLots=[], _allDocs=[], _allPOsForPR=[];
function _prPrioBadge(p){
  const m={1:['danger','High'],2:['warning','Med'],3:['success','Low']};
  const x=m[Number(p)||2]; return `<span class="badge bg-${x[0]}">${x[1]}</span>`;
}
function _prStatusBadge(s){
  const m={NEW:'secondary',APPROVED:'info',PO_ISSUED:'primary',AWAITING_ARRIVAL:'warning text-dark',
           ORDERED:'primary', RECEIVED:'success',OVER_RECEIVED:'danger',CANCELLED:'dark'};
  const labels={NEW:'Purchase Requested',APPROVED:'Approved',PO_ISSUED:'PO Issued',
    AWAITING_ARRIVAL:'Awaiting Materials',ORDERED:'PO Issued',RECEIVED:'Received',
    OVER_RECEIVED:'⚠ Over-Received',CANCELLED:'Cancelled'};
  return `<span class="badge bg-${m[s]||'light text-dark'}">${labels[s]||s}</span>`;
}

async function prLoad(){
  const status=document.getElementById('pr-status-filter').value;
  const type=document.getElementById('pr-type-filter').value;
  const qs=[]; if(status) qs.push('status='+status); if(type) qs.push('request_type='+type);
  try{
    _prRows = await api('/api/purchase-requests'+(qs.length?'?'+qs.join('&'):''));
    prRender(_prRows);
    prRenderKpi(_prRows);
    // Update export link to honor filter
    document.getElementById('pr-export-link').href = '/api/export/purchase-requests'+(status?('?status='+status):'');
    // Refresh material dropdowns in modals
    await prPrimeMaterialSelects();
  }catch(e){
    document.getElementById('pr-tbody').innerHTML=`<tr><td colspan="11" class="text-danger small p-3">${e.message||e}</td></tr>`;
  }
}
function prRenderKpi(rows){
  if(!Array.isArray(rows)) rows=[];
  const counts={NEW:0,APPROVED:0,PO_ISSUED:0,AWAITING_ARRIVAL:0,RECEIVED:0};
  rows.forEach(r=>{
    const s = r.status==='ORDERED' ? 'PO_ISSUED' : r.status;
    if(counts[s]!=null) counts[s]++;
  });
  const cards=[
    {l:'Requested',    v:counts.NEW,              bg:'secondary',ico:'bi-inbox'},
    {l:'Approved',     v:counts.APPROVED,         bg:'info',     ico:'bi-check2'},
    {l:'PO Issued',    v:counts.PO_ISSUED,        bg:'primary',  ico:'bi-file-earmark-text'},
    {l:'Awaiting Mat.',v:counts.AWAITING_ARRIVAL, bg:'warning',  ico:'bi-hourglass-split'},
    {l:'Received',     v:counts.RECEIVED,         bg:'success',  ico:'bi-box-seam'},
  ];
  document.getElementById('pr-kpi-row').innerHTML = cards.map(c=>`
    <div class="col-md col-6"><div class="card border-${c.bg}"><div class="card-body py-2 px-3">
      <div class="small text-muted"><i class="bi ${c.ico} me-1"></i>${c.l}</div>
      <div class="fs-5 fw-semibold">${c.v}</div>
    </div></div></div>`).join('');
}
function prRender(rows){
  if(!Array.isArray(rows)) rows=[];
  const tb=document.getElementById('pr-tbody');
  if(!rows.length){tb.innerHTML='<tr><td colspan="11" class="text-center text-muted py-3">No purchase requests</td></tr>';return;}
  tb.innerHTML=rows.map(r=>{
    const actions=[];
    if(r.status==='NEW')      actions.push(`<button class="btn btn-xs btn-info text-white" title="Approve" onclick="prSetStatus(${r.id},'APPROVED')"><i class="bi bi-check2"></i></button>`);
    if(r.status==='APPROVED') actions.push(`<button class="btn btn-xs btn-primary" title="Issue PO to supplier" onclick="prSetStatus(${r.id},'PO_ISSUED')"><i class="bi bi-file-earmark-text"></i></button>`);
    if(r.status==='PO_ISSUED'||r.status==='ORDERED') actions.push(`<button class="btn btn-xs btn-warning text-dark" title="Supplier confirmed, set ETA" onclick="prSetStatus(${r.id},'AWAITING_ARRIVAL')"><i class="bi bi-hourglass-split"></i></button>`);
    if(r.status==='AWAITING_ARRIVAL') actions.push(`<button class="btn btn-xs btn-success" title="Mark Received" onclick="prSetStatus(${r.id},'RECEIVED')"><i class="bi bi-box-seam"></i></button>`);
    if(r.status!=='RECEIVED' && r.status!=='CANCELLED')
      actions.push(`<button class="btn btn-xs btn-outline-danger" title="Cancel" onclick="prSetStatus(${r.id},'CANCELLED')"><i class="bi bi-x"></i></button>`);
    const eta = r.estimated_arrival ? `<br><span class="badge bg-warning text-dark" style="font-size:.6rem"><i class="bi bi-calendar-event me-1"></i>ETA ${r.estimated_arrival}</span>` : '';
    const grp = r.group_number
      ? `<br><span class="badge bg-info text-white" title="Submitted together with other lines" style="font-size:.55rem"><i class="bi bi-collection me-1"></i>${r.group_number}</span>`
      : '';
    return `<tr>
      <td class="small fw-semibold">${r.request_number||('#'+r.id)}${grp}</td>
      <td><span class="badge bg-light text-dark">${r.request_type==='RAW_MATERIAL'?'Raw':'Consumable'}</span></td>
      <td><b>${r.material_code||''}</b> ${r.material_name||''}</td>
      <td class="text-end">${_accFmtN(r.qty_requested)}</td>
      <td class="small text-muted">${r.uom||''}</td>
      <td>${_prPrioBadge(r.priority)}</td>
      <td class="small">${r.needed_by||'—'}</td>
      <td class="small">${r.source_po_number||'—'}</td>
      <td>${_prStatusBadge(r.status)}${eta}</td>
      <td class="small">${(r.requested_at||'').slice(0,16).replace('T',' ')}<br><span class="text-muted">${r.requested_by||''}</span></td>
      <td class="text-end" style="white-space:nowrap">${actions.join(' ')}</td>
    </tr>`;
  }).join('');
}
function prFilter(q){
  q=(q||'').toLowerCase();
  prRender(!q?_prRows:_prRows.filter(r=>JSON.stringify(r).toLowerCase().includes(q)));
}
async function prSetStatus(id, status){
  const body = {status};
  if(status==='PO_ISSUED' || status==='ORDERED'){
    body.supplier_po_ref = prompt('Supplier PO reference (optional):','')||'';
  }
  if(status==='AWAITING_ARRIVAL'){
    const today = new Date(); today.setDate(today.getDate()+14);
    const def = today.toISOString().slice(0,10);
    const eta = prompt('Estimated arrival date (YYYY-MM-DD):', def);
    if(eta===null) return; // user cancelled
    if(!/^\d{4}-\d{2}-\d{2}$/.test(eta)){ alert('Invalid date — expected YYYY-MM-DD'); return; }
    body.estimated_arrival = eta;
  }
  try{
    await api(`/api/purchase-requests/${id}/status`, 'PATCH', body);
    prLoad();
  }catch(e){ alert('Update failed: '+(e.message||e)); }
}
async function prPrimeMaterialSelects(){
  try{ _prMaterials = await api('/api/materials'); }catch{ _prMaterials=[]; }
  const opts = _prMaterials.map(m=>`<option value="${m.id}">[${(m.type||'').toUpperCase()}] ${m.code||''} — ${m.name}</option>`).join('');
  ['lot-new-material','doc-mat','lot-mat-filter'].forEach(id=>{
    const el=document.getElementById(id);
    if(el){
      const cur=el.value;
      const prefix = id==='lot-mat-filter' ? '<option value="">— all materials —</option>' : '';
      el.innerHTML = prefix + opts;
      if(cur) el.value=cur;
    }
  });
}
async function prPrimePOSelect(){
  try{ _allPOsForPR = await api('/api/purchase-orders'); }catch{ _allPOsForPR=[]; }
  const sel=document.getElementById('pr-auto-po');
  if(!sel) return;
  sel.innerHTML='<option value="">— pick a sales PO —</option>'+_allPOsForPR.map(o=>
    `<option value="${o.id}">${o.po_number||('#'+o.id)} — ${(o.customer||'')} (${o.status||''})</option>`).join('');
}
async function prAutoFromPO(){
  const id=document.getElementById('pr-auto-po').value;
  if(!id){ alert('Please pick a sales PO first.'); return; }
  try{
    const r=await api(`/api/purchase-requests/auto-from-po/${id}`, 'POST');
    alert(`Generated ${r.count||0} purchase request(s) for PO ${r.po_number||id}.`);
    prLoad();
  }catch(e){ alert('Auto-generate failed: '+(e.message||e)); }
}
// ── Multi-material PR modal state ─────────────────────────────────
let _prLineSeq = 0;
function _prLineTpl(idx){
  const opts = (_prMaterials||[]).map(m=>
    `<option value="${m.id}" data-uom="${m.unit||''}" data-type="${(m.type||'').toLowerCase()==='consumable'?'CONSUMABLE':'RAW_MATERIAL'}">[${(m.type||'').toUpperCase()}] ${m.code||''} — ${m.name}</option>`).join('');
  return `
  <div class="card mb-2 pr-line" data-idx="${idx}">
    <div class="card-body py-2">
      <div class="d-flex align-items-center mb-2">
        <span class="badge bg-secondary me-2">Line ${idx+1}</span>
        <div class="flex-grow-1 small text-muted">Pick the material, total qty, then add any split deliveries below.</div>
        <button class="btn btn-xs btn-outline-danger" title="Remove this line" onclick="prRemoveLine(${idx})">
          <i class="bi bi-x-lg"></i>
        </button>
      </div>
      <div class="row g-2">
        <div class="col-md-5">
          <label class="form-label small fw-semibold mb-1">Material *</label>
          <select class="form-select form-select-sm pr-l-mat" onchange="_prOnMatChange(${idx})">
            <option value="">— select —</option>${opts}
          </select>
        </div>
        <div class="col-md-2">
          <label class="form-label small fw-semibold mb-1">Type</label>
          <select class="form-select form-select-sm pr-l-type">
            <option value="RAW_MATERIAL">Raw</option>
            <option value="CONSUMABLE">Consumable</option>
          </select>
        </div>
        <div class="col-md-2">
          <label class="form-label small fw-semibold mb-1">Total Qty *</label>
          <input type="number" class="form-control form-control-sm pr-l-qty" step="0.01" min="0" oninput="_prRecalcSplit(${idx})">
        </div>
        <div class="col-md-1">
          <label class="form-label small fw-semibold mb-1">UoM</label>
          <input class="form-control form-control-sm pr-l-uom" placeholder="pcs">
        </div>
        <div class="col-md-2">
          <label class="form-label small fw-semibold mb-1">Priority</label>
          <select class="form-select form-select-sm pr-l-prio">
            <option value="">use default</option>
            <option value="1">1 — High</option>
            <option value="2">2 — Med</option>
            <option value="3">3 — Low</option>
          </select>
        </div>
      </div>

      <div class="d-flex justify-content-between align-items-center mt-3 mb-1">
        <div class="small fw-semibold text-muted">
          <i class="bi bi-truck me-1"></i>Split Deliveries
          <span class="text-muted ms-2 pr-l-split-sum" style="font-weight:normal"></span>
        </div>
        <button class="btn btn-xs btn-outline-secondary" onclick="prAddSplit(${idx})">
          <i class="bi bi-plus me-1"></i>Add Split
        </button>
      </div>
      <div class="pr-l-splits"></div>
      <div class="form-text small">Leave empty for single delivery. Total of splits must not exceed line qty.</div>
    </div>
  </div>`;
}

function _prSplitTpl(){
  return `
  <div class="row g-1 align-items-end pr-split mb-1">
    <div class="col-md-3">
      <input type="number" class="form-control form-control-sm pr-s-qty" placeholder="Qty" step="0.01" min="0" oninput="prRecalcAllSplits()">
    </div>
    <div class="col-md-3">
      <input type="date" class="form-control form-control-sm pr-s-eta" title="Planned arrival">
    </div>
    <div class="col-md-3">
      <input class="form-control form-control-sm pr-s-carrier" placeholder="Carrier (optional)">
    </div>
    <div class="col-md-2">
      <input class="form-control form-control-sm pr-s-notes" placeholder="Note">
    </div>
    <div class="col-md-1 text-end">
      <button class="btn btn-xs btn-outline-danger" onclick="this.closest('.pr-split').remove(); prRecalcAllSplits();">
        <i class="bi bi-x"></i>
      </button>
    </div>
  </div>`;
}

function prAddLine(){
  const c = document.getElementById('pr-lines-container');
  const idx = _prLineSeq++;
  c.insertAdjacentHTML('beforeend', _prLineTpl(idx));
}
function prRemoveLine(idx){
  const el = document.querySelector(`.pr-line[data-idx="${idx}"]`);
  if(el){
    if(document.querySelectorAll('.pr-line').length<=1){ alert('At least one line required.'); return; }
    el.remove();
  }
}
function prAddSplit(idx){
  const line = document.querySelector(`.pr-line[data-idx="${idx}"]`);
  if(!line) return;
  line.querySelector('.pr-l-splits').insertAdjacentHTML('beforeend', _prSplitTpl());
  _prRecalcSplit(idx);
}
function _prOnMatChange(idx){
  const line = document.querySelector(`.pr-line[data-idx="${idx}"]`);
  if(!line) return;
  const sel = line.querySelector('.pr-l-mat');
  const opt = sel.options[sel.selectedIndex];
  if(opt){
    const uom = opt.getAttribute('data-uom')||'';
    const tp  = opt.getAttribute('data-type')||'RAW_MATERIAL';
    if(!line.querySelector('.pr-l-uom').value) line.querySelector('.pr-l-uom').value = uom;
    line.querySelector('.pr-l-type').value = tp;
  }
}
function _prRecalcSplit(idx){
  const line = document.querySelector(`.pr-line[data-idx="${idx}"]`);
  if(!line) return;
  const total = Number(line.querySelector('.pr-l-qty').value||0);
  let sum = 0;
  line.querySelectorAll('.pr-s-qty').forEach(i=> sum += Number(i.value||0));
  const lbl = line.querySelector('.pr-l-split-sum');
  if(sum>0){
    const ok = sum <= total + 0.0001;
    lbl.innerHTML = `· allocated <b class="${ok?'text-success':'text-danger'}">${sum}</b> / ${total||'—'}`+
                    (ok ? '' : ' <span class="badge bg-danger">over</span>');
  } else { lbl.textContent = ''; }
}
function prRecalcAllSplits(){
  document.querySelectorAll('.pr-line').forEach(el=>{
    const idx = Number(el.getAttribute('data-idx'));
    _prRecalcSplit(idx);
  });
}

function prResetLines(){
  _prLineSeq = 0;
  document.getElementById('pr-lines-container').innerHTML = '';
  prAddLine();
}

// Initialize modal each time it opens
document.addEventListener('DOMContentLoaded', ()=>{
  const m = document.getElementById('newPRModal');
  if(m){
    m.addEventListener('show.bs.modal', async ()=>{
      await prPrimeMaterialSelects();
      prResetLines();
    });
  }
});

async function prSubmit(){
  const lines = [];
  let bad = '';
  document.querySelectorAll('.pr-line').forEach((el)=>{
    const mid = Number(el.querySelector('.pr-l-mat').value||0);
    const qty = Number(el.querySelector('.pr-l-qty').value||0);
    if(!mid || qty<=0){ bad = 'Each line needs a material and positive qty.'; return; }
    const splits = [];
    let sum = 0;
    el.querySelectorAll('.pr-split').forEach(s=>{
      const sq = Number(s.querySelector('.pr-s-qty').value||0);
      if(sq>0){
        splits.push({
          planned_qty: sq,
          planned_arrival: s.querySelector('.pr-s-eta').value||null,
          carrier: s.querySelector('.pr-s-carrier').value||'',
          notes:   s.querySelector('.pr-s-notes').value||'',
        });
        sum += sq;
      }
    });
    if(sum > qty + 0.0001){ bad = `Splits sum (${sum}) exceeds line qty (${qty}).`; return; }
    const prioRaw = el.querySelector('.pr-l-prio').value;
    lines.push({
      request_type: el.querySelector('.pr-l-type').value,
      material_id:  mid,
      qty_requested: qty,
      uom:          el.querySelector('.pr-l-uom').value||'',
      priority:     prioRaw ? Number(prioRaw) : null,
      splits:       splits,
    });
  });
  if(bad){ alert(bad); return; }
  if(!lines.length){ alert('Add at least one material line.'); return; }
  const body = {
    priority:  Number(document.getElementById('pr-new-priority').value||2),
    needed_by: document.getElementById('pr-new-needed').value||null,
    suggested_supplier: document.getElementById('pr-new-supplier').value||'',
    notes:     document.getElementById('pr-new-notes').value||'',
    lines:     lines,
  };
  try{
    const res = await api('/api/purchase-requests/bulk', 'POST', body);
    bootstrap.Modal.getInstance(document.getElementById('newPRModal'))?.hide();
    toast(`Created ${res.count} PR(s) under ${res.group_number}`,'success');
    prLoad();
  }catch(e){ alert('Submit failed: '+(e.message||e)); }
}


// VCMX moved to /static/js/portal_planning.js



// ════════════════════════════════════════════════════════════
// Traceability
// ════════════════════════════════════════════════════════════
// ══════════════════════════════════════════════════════════════
// TRACEABILITY
// ══════════════════════════════════════════════════════════════
async function tracePrimePOSelect(){
  try{ _allPOsForPR = await api('/api/purchase-orders'); }catch{ _allPOsForPR=[]; }
  const sel=document.getElementById('trace-po');
  sel.innerHTML='<option value="">— pick a sales PO —</option>'+_allPOsForPR.map(o=>
    `<option value="${o.id}">${o.po_number||('#'+o.id)} — ${(o.customer||'')}</option>`).join('');
}
async function traceLoad(){
  const id=document.getElementById('trace-po').value;
  if(!id){ document.getElementById('trace-content').innerHTML='<div class="text-muted small">Select a PO to view its full traceability report.</div>'; return; }
  try{
    const r=await api('/api/traceability/po/'+id);
    traceRender(r);
  }catch(e){
    document.getElementById('trace-content').innerHTML=`<div class="alert alert-danger small">${e.message||e}</div>`;
  }
}
function traceExport(ev){
  ev.preventDefault();
  const id=document.getElementById('trace-po').value;
  if(!id){ alert('Pick a PO first'); return false; }
  window.open('/api/export/traceability/po/'+id,'_blank');
  return false;
}
function traceRender(r){
  const po=r.purchase_order||{}; const batches=r.batches||[];
  let html=`<div class="card mb-3"><div class="card-body py-2">
    <div class="row small">
      <div class="col-md-3"><span class="text-muted">PO #</span><br><b>${po.po_number||po.id}</b></div>
      <div class="col-md-3"><span class="text-muted">Customer</span><br>${po.customer||'—'}</div>
      <div class="col-md-3"><span class="text-muted">Delivery</span><br>${po.delivery_date||'—'}</div>
      <div class="col-md-3"><span class="text-muted">Status</span><br>${po.status||'—'}</div>
    </div></div></div>`;
  if(!batches.length){
    html+='<div class="alert alert-warning small">No production batches linked to this PO yet.</div>';
  }
  batches.forEach(b=>{
    html+=`<div class="card mb-2"><div class="card-header py-2 d-flex justify-content-between">
      <span class="fw-semibold small"><i class="bi bi-box me-1"></i>${b.batch_number||('#'+b.id)} — ${b.product_sku||''} ${b.product_name||''}</span>
      <span class="small text-muted">${_accFmtN(b.pcs_actual||b.quantity)} pcs</span>
    </div>`;
    if(!b.lots_consumed || !b.lots_consumed.length){
      html+='<div class="card-body py-2 text-muted small">No lot consumption recorded for this batch.</div>';
    }else{
      html+=`<div class="table-responsive"><table class="table table-sm mb-0">
        <thead class="table-light"><tr>
          <th>Material</th><th>Role</th><th class="text-end">Qty</th>
          <th>Lot</th><th>Supplier</th><th>Received</th><th>Expiry</th><th>Docs</th>
        </tr></thead><tbody>`;
      b.lots_consumed.forEach(l=>{
        const docs=(l.documents||[]).map(d=>
          `<a class="badge bg-danger text-decoration-none me-1" href="/api/material-documents/${d.id}/download" target="_blank"><i class="bi bi-file-earmark-pdf me-1"></i>${d.doc_type}</a>`
        ).join('') || '<span class="text-muted small">—</span>';
        html+=`<tr>
          <td class="small"><span class="badge bg-light text-dark me-1">${(l.material_type||'').toUpperCase()}</span><b>${l.material_code||''}</b> ${l.material_name||''}</td>
          <td class="small">${l.role||'—'}</td>
          <td class="text-end">${_accFmtN(l.qty_consumed)} ${l.uom||''}</td>
          <td class="small fw-semibold">${l.lot_code}</td>
          <td class="small">${l.supplier||'—'}${l.supplier_lot_ref?'<br><span class="text-muted">'+l.supplier_lot_ref+'</span>':''}</td>
          <td class="small">${(l.received_at||'').slice(0,10)}</td>
          <td class="small">${l.expiry_date||'—'}</td>
          <td>${docs}</td>
        </tr>`;
      });
      html+='</tbody></table></div>';
    }
    html+='</div>';
  });
  document.getElementById('trace-content').innerHTML=html;
}


// Forklifts (SLH Forklifts tab) moved to /static/js/portal_planning.js
// ── Page loader registry ────────────────────────────────────
Object.assign(PAGE_LOADERS, {
  'accounting':  loadAccounting,
  'dept-costs':  () => {
    const m = document.getElementById('dc-month');
    if(m && !m.value) m.value = new Date().toISOString().slice(0,7);
    dcLoad();
  },
  'purchasing'             : () => { prLoad(); prPrimePOSelect(); },
  'traceability'           : () => { tracePrimePOSelect(); },
});
