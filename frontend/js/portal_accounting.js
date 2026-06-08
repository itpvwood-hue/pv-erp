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


// ── Page loader registry ────────────────────────────────────
Object.assign(PAGE_LOADERS, {
  'accounting':  loadAccounting,
  'dept-costs':  () => {
    const m = document.getElementById('dc-month');
    if(m && !m.value) m.value = new Date().toISOString().slice(0,7);
    dcLoad();
  },
});
