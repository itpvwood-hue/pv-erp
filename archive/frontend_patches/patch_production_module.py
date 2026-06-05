"""
Patch: integrate production module pages into index.html.
Adds: Employees page, Station Log page, Production Reports page, and nav links.
"""
import sys, re
sys.stdout.reconfigure(encoding='utf-8')

html = open('index.html', encoding='utf-8').read()
ok = []; warn = []

def replace1(old, new, tag):
    global html
    if old in html:
        html = html.replace(old, new, 1)
        ok.append(tag)
    else:
        warn.append(f'NOT FOUND: {tag}')

# ══════════════════════════════════════════════════════════
# 1. NAV — add Production group before Settings/Reports
# ══════════════════════════════════════════════════════════
NAV_PRODUCTION = """
        <div class="sidebar-section-label">Production Module</div>
        <a href="#" data-page="station-log" class="nav-item"><i class="bi bi-kanban me-2"></i>Station Log</a>
        <a href="#" data-page="prod-reports" class="nav-item"><i class="bi bi-bar-chart-line me-2"></i>Prod Reports</a>
        <a href="#" data-page="employees" class="nav-item"><i class="bi bi-people me-2"></i>Employees</a>"""

# Insert before the closing </nav> or before Reports nav item
replace1(
    'data-page="reports"',
    NAV_PRODUCTION.strip() + '\n        <a href="#" data-page="reports"',
    'production nav items added'
)

# ══════════════════════════════════════════════════════════
# 2. HTML PAGES — insert before </div><!-- /main -->
# ══════════════════════════════════════════════════════════
PROD_PAGES = """
<!-- ══ EMPLOYEES ════════════════════════════════════════════ -->
<div class="page" id="page-employees">
  <div class="d-flex justify-content-between align-items-center mb-3">
    <div>
      <h4 class="mb-0">Employees <span class="badge bg-secondary fs-6" id="emp-count">0</span></h4>
      <small class="text-muted">Production floor operators by department and line</small>
    </div>
    <button class="btn btn-primary btn-sm" onclick="openEmpModal()"><i class="bi bi-plus-lg me-1"></i>Add Employee</button>
  </div>
  <div class="row g-2 mb-3">
    <div class="col-auto">
      <select class="form-select form-select-sm" id="emp-dept-filter" onchange="filterEmployees()">
        <option value="">All Depts</option>
        <option>LAMINATING</option><option>REPAIR</option><option>SANDING</option>
        <option>PRESSING</option><option>QC</option><option>MIXING</option>
      </select>
    </div>
    <div class="col-auto">
      <select class="form-select form-select-sm" id="emp-line-filter" onchange="filterEmployees()">
        <option value="">All Lines</option>
        <option>P01</option><option>P02</option><option>P37</option>
      </select>
    </div>
    <div class="col"><input class="form-control form-control-sm" id="emp-search" placeholder="Search name or ID..." oninput="filterEmployees()"></div>
  </div>
  <div class="card"><div class="card-body p-0">
    <table class="table table-sm table-hover mb-0" id="emp-table">
      <thead class="table-light"><tr><th>ID</th><th>Name</th><th>Department</th><th>Role</th><th>Line</th><th></th></tr></thead>
      <tbody></tbody>
    </table>
  </div></div>
</div>

<!-- ══ STATION LOG (Production Kanban) ══════════════════════ -->
<div class="page" id="page-station-log">
  <div class="d-flex justify-content-between align-items-center mb-3">
    <div>
      <h4 class="mb-0"><i class="bi bi-kanban me-2 text-primary"></i>Station Log</h4>
      <small class="text-muted">Batch traceability across all 7 production stations</small>
    </div>
    <div class="d-flex gap-2">
      <select class="form-select form-select-sm" id="sl-line" style="width:120px" onchange="slFilterBatches()">
        <option value="">All Lines</option>
        <option>P01</option><option>P02</option><option>P37</option>
      </select>
      <button class="btn btn-primary btn-sm" onclick="openNewBatchModal()"><i class="bi bi-plus-lg me-1"></i>New Batch</button>
    </div>
  </div>

  <div class="row g-3">
    <!-- Left: batch list -->
    <div class="col-md-4 col-lg-3">
      <div class="card h-100">
        <div class="card-header py-2 d-flex justify-content-between align-items-center">
          <span class="fw-bold small">Active Batches</span>
          <select class="form-select form-select-sm w-auto" id="sl-status-filter" onchange="slFilterBatches()">
            <option value="">All Status</option>
            <option>GLUE_MIX</option><option>LAMINATING</option><option>COLD_PRESS</option>
            <option>REPAIR</option><option>SANDING</option><option>HOT_PRESS</option>
            <option>GRADING</option><option>COMPLETE</option>
          </select>
        </div>
        <div class="card-body p-2 overflow-auto" id="sl-batch-list" style="max-height:calc(100vh - 220px)">
          <p class="text-muted small text-center pt-3">Loading...</p>
        </div>
      </div>
    </div>
    <!-- Right: station forms -->
    <div class="col-md-8 col-lg-9">
      <div id="sl-station-area">
        <div class="card p-5 text-center text-muted">
          <i class="bi bi-arrow-left fs-3 mb-2"></i>
          <div>Select a batch to log station activity</div>
        </div>
      </div>
    </div>
  </div>
</div>

<!-- ══ PRODUCTION REPORTS ════════════════════════════════════ -->
<div class="page" id="page-prod-reports">
  <div class="d-flex justify-content-between align-items-center mb-3">
    <div>
      <h4 class="mb-0"><i class="bi bi-bar-chart-line me-2 text-primary"></i>Production Reports</h4>
      <small class="text-muted">Quality · NCG backtrack · Laminating efficacy · Sanding defects</small>
    </div>
  </div>

  <!-- Filters -->
  <div class="d-flex gap-2 flex-wrap mb-3">
    <select class="form-select form-select-sm w-auto" id="pr-line">
      <option value="">All Lines</option>
      <option>P01</option><option>P02</option><option>P37</option>
    </select>
    <select class="form-select form-select-sm w-auto" id="pr-period" onchange="prSetPeriod(this.value)">
      <option value="7">Last 7 days</option>
      <option value="30" selected>Last 30 days</option>
      <option value="90">Last 90 days</option>
    </select>
    <input type="date" class="form-control form-control-sm w-auto" id="pr-from">
    <input type="date" class="form-control form-control-sm w-auto" id="pr-to">
    <button class="btn btn-primary btn-sm" onclick="loadProdReports()"><i class="bi bi-arrow-clockwise me-1"></i>Refresh</button>
    <button class="btn btn-outline-secondary btn-sm ms-auto" onclick="openProdAiChat()"><i class="bi bi-stars me-1"></i>Ask AI</button>
  </div>

  <!-- KPI cards -->
  <div class="row g-3 mb-3" id="pr-kpis">
    <div class="col-6 col-md-3"><div class="stat-card"><div class="val text-primary" id="pr-kpi-boards">—</div><div class="lbl">Boards Produced</div></div></div>
    <div class="col-6 col-md-3"><div class="stat-card"><div class="val" id="pr-kpi-ncg">—</div><div class="lbl">NCG Rate</div></div></div>
    <div class="col-6 col-md-3"><div class="stat-card"><div class="val" id="pr-kpi-sand">—</div><div class="lbl">Avg Sanding Defect</div></div></div>
    <div class="col-6 col-md-3"><div class="stat-card"><div class="val" id="pr-kpi-lam">—</div><div class="lbl">Avg Lam Efficacy</div></div></div>
  </div>

  <!-- Tabs -->
  <ul class="nav nav-tabs mb-0" id="pr-tabs">
    <li class="nav-item"><button class="nav-link active" data-bs-toggle="tab" data-bs-target="#pr-tab-daily">Daily Summary</button></li>
    <li class="nav-item"><button class="nav-link" data-bs-toggle="tab" data-bs-target="#pr-tab-lam">Lam Efficacy</button></li>
    <li class="nav-item"><button class="nav-link" data-bs-toggle="tab" data-bs-target="#pr-tab-sand">Sanding Defects</button></li>
    <li class="nav-item"><button class="nav-link" data-bs-toggle="tab" data-bs-target="#pr-tab-ncg">NCG Backtrack</button></li>
  </ul>
  <div class="tab-content border border-top-0 rounded-bottom p-3 mb-3">
    <div class="tab-pane fade show active" id="pr-tab-daily">
      <table class="table table-sm table-hover mb-0" id="pr-daily-table">
        <thead class="table-light"><tr><th>Date</th><th>Line</th><th>SKU</th><th>Batches</th><th>Planned</th><th>Good</th><th>NCG</th><th>Reject</th><th>NCG%</th></tr></thead>
        <tbody></tbody>
      </table>
    </div>
    <div class="tab-pane fade" id="pr-tab-lam">
      <table class="table table-sm table-hover mb-0" id="pr-lam-table">
        <thead class="table-light"><tr><th>Table</th><th>Line</th><th>SKU</th><th>Date</th><th>Shift</th><th>Pair</th><th>Target</th><th>Actual</th><th>Efficacy</th></tr></thead>
        <tbody></tbody>
      </table>
    </div>
    <div class="tab-pane fade" id="pr-tab-sand">
      <table class="table table-sm table-hover mb-0" id="pr-sand-table">
        <thead class="table-light"><tr><th>Operator</th><th>Line</th><th>Runs</th><th>Total Pcs</th><th>Defects</th><th>Defect Rate</th><th>Bar</th></tr></thead>
        <tbody></tbody>
      </table>
    </div>
    <div class="tab-pane fade" id="pr-tab-ncg">
      <div class="d-flex gap-2 mb-3">
        <select class="form-select form-select-sm w-auto" id="pr-ncg-reason-filter">
          <option value="">All reasons</option>
          <option value="NCG-DELAMINATION">Delamination</option>
          <option value="NCG-SANDED-VENEER">Sanded veneer</option>
          <option value="NCG-GLUE-BLEED">Glue bleed</option>
          <option value="NCG-SURFACE-ROUGH">Surface rough</option>
          <option value="NCG-THICKNESS-VAR">Thickness var</option>
          <option value="NCG-OTHER">Other</option>
        </select>
        <button class="btn btn-sm btn-outline-secondary" onclick="loadNcgList()">Filter</button>
      </div>
      <div id="pr-ncg-list"></div>
    </div>
  </div>

  <!-- AI chat panel (collapsible) -->
  <div class="collapse" id="prod-ai-chat-panel">
    <div class="card p-3">
      <div class="d-flex justify-content-between align-items-center mb-2">
        <h6 class="mb-0"><i class="bi bi-stars me-1 text-warning"></i>Production AI Assistant</h6>
        <button class="btn btn-sm btn-outline-secondary" data-bs-toggle="collapse" data-bs-target="#prod-ai-chat-panel">Close</button>
      </div>
      <div id="prod-ai-messages" style="min-height:120px;max-height:360px;overflow-y:auto" class="mb-2 border rounded p-2 bg-light"></div>
      <div class="d-flex gap-2">
        <input class="form-control form-control-sm" id="prod-ai-input" placeholder="Ask about production data..." onkeydown="if(event.key==='Enter')sendProdAiMsg()">
        <button class="btn btn-sm btn-primary" onclick="sendProdAiMsg()"><i class="bi bi-send"></i></button>
      </div>
    </div>
  </div>
</div>
"""

replace1(
    '</div><!-- /main -->',
    PROD_PAGES + '\n</div><!-- /main -->',
    'production module pages added'
)

# ══════════════════════════════════════════════════════════
# 3. MODALS — Employee modal + New Batch modal
# ══════════════════════════════════════════════════════════
PROD_MODALS = """
<!-- Employee Modal -->
<div class="modal fade" id="empModal" tabindex="-1"><div class="modal-dialog"><div class="modal-content">
  <div class="modal-header"><h5 class="modal-title" id="emp-modal-title">Add Employee</h5><button class="btn-close" data-bs-dismiss="modal"></button></div>
  <div class="modal-body">
    <input type="hidden" id="emp-id">
    <div class="row g-2">
      <div class="col-4"><label class="form-label small">Emp ID</label><input class="form-control form-control-sm" id="emp-emp-id" placeholder="EMP-001"></div>
      <div class="col-8"><label class="form-label small">Name <span class="text-danger">*</span></label><input class="form-control form-control-sm" id="emp-name" placeholder="Somchai K."></div>
      <div class="col-6"><label class="form-label small">Department <span class="text-danger">*</span></label>
        <select class="form-select form-select-sm" id="emp-dept">
          <option value="">Select...</option>
          <option>LAMINATING</option><option>REPAIR</option><option>SANDING</option>
          <option>PRESSING</option><option>QC</option><option>MIXING</option>
        </select>
      </div>
      <div class="col-6"><label class="form-label small">Role</label><input class="form-control form-control-sm" id="emp-role" placeholder="Laminator"></div>
      <div class="col-6"><label class="form-label small">Line</label>
        <select class="form-select form-select-sm" id="emp-line">
          <option value="">—</option><option>P01</option><option>P02</option><option>P37</option>
        </select>
      </div>
    </div>
  </div>
  <div class="modal-footer"><button class="btn btn-secondary" data-bs-dismiss="modal">Cancel</button><button class="btn btn-primary" onclick="saveEmployee()">Save</button></div>
</div></div></div>

<!-- New Production Batch Modal -->
<div class="modal fade" id="newBatchModal" tabindex="-1"><div class="modal-dialog"><div class="modal-content">
  <div class="modal-header"><h5 class="modal-title">New Production Batch</h5><button class="btn-close" data-bs-dismiss="modal"></button></div>
  <div class="modal-body">
    <div class="mb-2"><label class="form-label small">SKU Code <span class="text-danger">*</span></label>
      <input class="form-control form-control-sm" id="nb-sku" placeholder="e.g. 4ALM52A11" list="nb-sku-list" oninput="this.value=this.value.toUpperCase()">
      <datalist id="nb-sku-list"></datalist>
    </div>
    <div class="row g-2 mb-2">
      <div class="col-6"><label class="form-label small">Line <span class="text-danger">*</span></label>
        <select class="form-select form-select-sm" id="nb-line"><option>P01</option><option>P02</option><option>P37</option></select>
      </div>
      <div class="col-6"><label class="form-label small">Shift <span class="text-danger">*</span></label>
        <select class="form-select form-select-sm" id="nb-shift"><option>MORNING</option><option>AFTERNOON</option><option>NIGHT</option></select>
      </div>
    </div>
    <div class="row g-2 mb-2">
      <div class="col-6"><label class="form-label small">Qty Planned <span class="text-danger">*</span></label>
        <input type="number" class="form-control form-control-sm" id="nb-qty" min="1"></div>
      <div class="col-6"><label class="form-label small">Production Date</label>
        <input type="date" class="form-control form-control-sm" id="nb-date"></div>
    </div>
    <div class="mb-2"><label class="form-label small">Work Order (optional)</label>
      <select class="form-select form-select-sm" id="nb-order"><option value="">— No WO —</option></select>
    </div>
  </div>
  <div class="modal-footer"><button class="btn btn-secondary" data-bs-dismiss="modal">Cancel</button><button class="btn btn-primary" onclick="createNewBatch()">Create Batch</button></div>
</div></div></div>
"""

replace1(
    '<!-- Employee Modal -->',
    '<!-- [existing placeholder guard] -->',
    'emp modal guard check'
)
# If the guard replaced, there was already one — restore and skip adding
if '<!-- [existing placeholder guard] -->' in html:
    html = html.replace('<!-- [existing placeholder guard] -->', '<!-- Employee Modal -->')
    warn.append('Employee modal already present — skipped')
else:
    # No employee modal existed, find insertion point
    pass

# Always try to add before the closing </body>
if '<!-- Employee Modal -->' not in html:
    replace1(
        '</body>',
        PROD_MODALS + '\n</body>',
        'production modals added'
    )

# ══════════════════════════════════════════════════════════
# 4. JAVASCRIPT — add all production module JS before closing </script>
# ══════════════════════════════════════════════════════════
PROD_JS = """
// ══════════════════════════════════════════════════════════
// PRODUCTION MODULE
// ══════════════════════════════════════════════════════════
let _allEmployees=[], _slBatches=[], _slActiveBatch=null;
let _prodAiMessages=[];

// ── Helpers ────────────────────────────────────────────────
const STATION_ORDER=['GLUE_MIX','LAMINATING','COLD_PRESS','REPAIR','SANDING','HOT_PRESS','GRADING','COMPLETE'];
const STATION_LABEL={'GLUE_MIX':'Glue Mix','LAMINATING':'Laminating','COLD_PRESS':'Cold Press',
  'REPAIR':'Repair','SANDING':'Sanding','HOT_PRESS':'Hot Press','GRADING':'Grading','COMPLETE':'Complete'};
const STATION_ICON={'GLUE_MIX':'bi-droplet-fill','LAMINATING':'bi-table','COLD_PRESS':'bi-snow',
  'REPAIR':'bi-tools','SANDING':'bi-eraser','HOT_PRESS':'bi-thermometer-sun','GRADING':'bi-patch-check','COMPLETE':'bi-check-circle-fill'};
const STATION_COLOR={'GLUE_MIX':'warning','LAMINATING':'primary','COLD_PRESS':'info',
  'REPAIR':'secondary','SANDING':'orange','HOT_PRESS':'danger','GRADING':'success','COMPLETE':'dark'};

function slStatusBadge(s){
  const c={GLUE_MIX:'warning',LAMINATING:'primary',COLD_PRESS:'info',REPAIR:'secondary',
    SANDING:'warning text-dark',HOT_PRESS:'danger',GRADING:'success',COMPLETE:'dark'};
  return `<span class="badge bg-${c[s]||'secondary'}" style="font-size:.65rem">${STATION_LABEL[s]||s}</span>`;
}

// ══════════════════════════════════════════════════════════
// EMPLOYEES
// ══════════════════════════════════════════════════════════
async function loadEmployees(){
  _allEmployees = await api('/api/employees').catch(()=>[]);
  document.getElementById('emp-count').textContent=_allEmployees.length;
  filterEmployees();
}
function filterEmployees(){
  const dept=document.getElementById('emp-dept-filter').value;
  const line=document.getElementById('emp-line-filter').value;
  const q=(document.getElementById('emp-search').value||'').toLowerCase();
  const rows=_allEmployees.filter(e=>
    (!dept||e.department===dept)&&
    (!line||e.line_id===line)&&
    (!q||e.emp_name.toLowerCase().includes(q)||e.emp_id.toLowerCase().includes(q))
  );
  document.querySelector('#emp-table tbody').innerHTML=rows.length?rows.map(e=>`
    <tr>
      <td><code class="text-primary">${e.emp_id}</code></td>
      <td>${e.emp_name}</td>
      <td><span class="badge bg-secondary">${e.department}</span></td>
      <td><small class="text-muted">${e.role||'—'}</small></td>
      <td>${e.line_id?`<span class="line-badge line-${e.line_id}">${e.line_id}</span>`:'—'}</td>
      <td class="text-end">
        <button class="btn btn-xs btn-outline-secondary py-0 px-1 me-1" onclick="openEmpModal(${JSON.stringify(e)})"><i class="bi bi-pencil"></i></button>
        <button class="btn btn-xs btn-outline-danger py-0 px-1" onclick="deleteEmployee('${e.emp_id}')"><i class="bi bi-trash"></i></button>
      </td>
    </tr>`).join(''):
    '<tr><td colspan="6" class="text-center text-muted py-4">No employees found.</td></tr>';
}
function openEmpModal(emp=null){
  document.getElementById('emp-id').value=emp?emp.emp_id:'';
  document.getElementById('emp-emp-id').value=emp?emp.emp_id:'';
  document.getElementById('emp-name').value=emp?emp.emp_name:'';
  document.getElementById('emp-dept').value=emp?emp.department:'';
  document.getElementById('emp-role').value=emp?emp.role||'':'';
  document.getElementById('emp-line').value=emp?emp.line_id||'':'';
  document.getElementById('emp-modal-title').textContent=emp?'Edit Employee':'Add Employee';
  document.getElementById('emp-emp-id').disabled=!!emp;
  bootstrap.Modal.getOrCreateInstance(document.getElementById('empModal')).show();
}
async function saveEmployee(){
  const id=document.getElementById('emp-id').value;
  const body={
    emp_id:document.getElementById('emp-emp-id').value||undefined,
    emp_name:document.getElementById('emp-name').value.trim(),
    department:document.getElementById('emp-dept').value,
    role:document.getElementById('emp-role').value.trim(),
    line_id:document.getElementById('emp-line').value||null,
  };
  if(!body.emp_name||!body.department){toast('Name and department are required','danger');return;}
  try{
    if(id) await api(`/api/employees/${id}`,'PUT',body);
    else await api('/api/employees','POST',body);
    bootstrap.Modal.getInstance(document.getElementById('empModal')).hide();
    toast('Saved');loadEmployees();
  }catch(e){toast(e.message,'danger');}
}
async function deleteEmployee(id){
  if(!confirm('Remove this employee?'))return;
  try{await api(`/api/employees/${id}`,'DELETE');toast('Removed');loadEmployees();}
  catch(e){toast(e.message,'danger');}
}

// ══════════════════════════════════════════════════════════
// STATION LOG
// ══════════════════════════════════════════════════════════
async function loadStationLog(){
  await slLoadBatches();
  // Populate SKU datalist for new batch modal
  const skus=await api('/api/fg').catch(()=>[]);
  document.getElementById('nb-sku-list').innerHTML=skus.map(s=>`<option value="${s.code}">${s.name}</option>`).join('');
  // Populate WO list
  const orders=await api('/api/mfg-orders').catch(()=>[]);
  document.getElementById('nb-order').innerHTML='<option value="">— No WO —</option>'+
    orders.map(o=>`<option value="${o.order_id}">${o.order_id} — ${o.sku_code} (${o.line_id})</option>`).join('');
  // Default date
  document.getElementById('nb-date').value=new Date().toISOString().slice(0,10);
}
async function slLoadBatches(){
  const line=document.getElementById('sl-line').value;
  const status=document.getElementById('sl-status-filter').value;
  _slBatches=await api(`/api/prod-batches${line?'?line_id='+line:''}${status?(line?'&':'?')+'status='+status:''}`).catch(()=>[]);
  renderSlBatchList();
}
function slFilterBatches(){ slLoadBatches(); }
function renderSlBatchList(){
  const el=document.getElementById('sl-batch-list');
  if(!_slBatches.length){el.innerHTML='<p class="text-muted small text-center pt-3">No batches found.</p>';return;}
  el.innerHTML=_slBatches.map(b=>`
    <div class="border rounded p-2 mb-2 ${_slActiveBatch?.batch_id===b.batch_id?'border-primary bg-light':''}" style="cursor:pointer" onclick="slSelectBatch('${b.batch_id}')">
      <div class="d-flex justify-content-between align-items-center">
        <code class="text-primary small">${b.batch_id}</code>
        ${slStatusBadge(b.status)}
      </div>
      <div class="small text-muted mt-1">${b.sku_code} · ${b.line_id} · ${b.qty_planned} pcs</div>
      <div class="small text-muted">${b.production_date} ${b.shift?'<span class="badge bg-light text-dark border">'+b.shift+'</span>':''}</div>
    </div>`).join('');
}
async function slSelectBatch(id){
  const b=await api(`/api/prod-batches/${id}`).catch(()=>null);
  if(!b)return;
  _slActiveBatch=b;
  renderSlBatchList();
  renderStationForms(b);
}
function renderStationForms(batch){
  const area=document.getElementById('sl-station-area');
  const idx=STATION_ORDER.indexOf(batch.status);
  area.innerHTML=`
    <div class="mb-3 d-flex align-items-center gap-3 flex-wrap">
      <div>
        <h5 class="mb-0">${batch.batch_id}</h5>
        <small class="text-muted">${batch.sku_code} · ${batch.line_id} · ${batch.qty_planned} pcs planned · ${batch.production_date}</small>
      </div>
      <div class="ms-auto d-flex gap-1 flex-wrap">
        ${STATION_ORDER.filter(s=>s!=='COMPLETE').map((s,i)=>`
          <span class="badge ${i<idx?'bg-success':i===idx?'bg-primary':'bg-light text-muted border'}" style="font-size:.65rem">
            <i class="bi ${STATION_ICON[s]} me-1"></i>${STATION_LABEL[s]}
          </span>`).join('')}
      </div>
    </div>
    <div id="sl-form-area">
      ${batch.status==='COMPLETE'
        ? '<div class="alert alert-success"><i class="bi bi-check-circle-fill me-2"></i>Batch complete. All stations logged.</div>'
        : renderStationCard(batch)}
    </div>
  `;
}
function renderStationCard(batch){
  const s=batch.status;
  const pq=batch.qty_planned;
  const formMap={
    GLUE_MIX: `
      <h6><i class="bi bi-droplet-fill text-warning me-1"></i>Glue Mix</h6>
      <div class="row g-2">
        <div class="col-md-4"><label class="form-label small">Recipe Code <span class="text-danger">*</span></label>
          <input class="form-control form-control-sm" id="sf-recipe" placeholder="e.g. GLU-16" list="sf-compound-list">
          <datalist id="sf-compound-list"></datalist>
        </div>
        <div class="col-md-2"><label class="form-label small">Qty (kg) <span class="text-danger">*</span></label>
          <input type="number" class="form-control form-control-sm" id="sf-glue-kg" min="0.1" step="0.1"></div>
        <div class="col-md-2"><label class="form-label small">Mix time (min)</label>
          <input type="number" class="form-control form-control-sm" id="sf-mix-min" min="1"></div>
        <div class="col-md-4"><label class="form-label small">Operator</label>
          <input class="form-control form-control-sm" id="sf-op-name" list="sl-emp-list" placeholder="Operator name or ID"></div>
      </div>
      <div class="mt-2"><label class="form-label small">Notes</label><input class="form-control form-control-sm" id="sf-notes"></div>
      <button class="btn btn-warning btn-sm mt-3" onclick="submitGlueMix('${batch.batch_id}')"><i class="bi bi-floppy me-1"></i>Log Glue Mix → advance to Laminating</button>`,

    LAMINATING: `
      <h6><i class="bi bi-table text-primary me-1"></i>Laminating</h6>
      <div id="lam-rows-area"></div>
      <button class="btn btn-outline-primary btn-sm mb-2" onclick="addLamRow('${batch.batch_id}')"><i class="bi bi-plus-lg me-1"></i>Add table row</button>
      <div class="d-flex gap-2 mt-2">
        <button class="btn btn-primary btn-sm" onclick="submitAllLam('${batch.batch_id}')"><i class="bi bi-check-lg me-1"></i>Done — advance to Cold Press</button>
      </div>`,

    COLD_PRESS: `
      <h6><i class="bi bi-snow text-info me-1"></i>Cold Press</h6>
      <div class="row g-2">
        <div class="col-md-3"><label class="form-label small">Machine <span class="text-danger">*</span></label>
          <select class="form-select form-select-sm" id="sf-cp-machine"><option value="">Select...</option><option>CP-01</option><option>CP-02</option></select></div>
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
      <button class="btn btn-info btn-sm mt-3 text-white" onclick="submitColdPress('${batch.batch_id}')"><i class="bi bi-floppy me-1"></i>Log Cold Press → Repair</button>`,

    REPAIR: `
      <h6><i class="bi bi-tools text-secondary me-1"></i>Repair</h6>
      <div id="rep-rows-area"></div>
      <button class="btn btn-outline-secondary btn-sm mb-2" onclick="addRepRow('${batch.batch_id}')"><i class="bi bi-plus-lg me-1"></i>Add repair row</button>
      <div class="d-flex gap-2 mt-2">
        <button class="btn btn-secondary btn-sm" onclick="submitAllRep('${batch.batch_id}')"><i class="bi bi-check-lg me-1"></i>Done — advance to Sanding</button>
      </div>`,

    SANDING: `
      <h6><i class="bi bi-eraser text-warning me-1"></i>Sanding</h6>
      <div class="row g-2">
        <div class="col-md-3"><label class="form-label small">Machine <span class="text-danger">*</span></label>
          <select class="form-select form-select-sm" id="sf-snd-machine"><option value="">Select...</option><option>SND-01</option><option>SND-02</option><option>SND-37</option></select></div>
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
      <button class="btn btn-warning btn-sm mt-3" onclick="submitSanding('${batch.batch_id}')"><i class="bi bi-floppy me-1"></i>Log Sanding → Hot Press</button>`,

    HOT_PRESS: `
      <h6><i class="bi bi-thermometer-sun text-danger me-1"></i>Hot Press</h6>
      <div class="row g-2">
        <div class="col-md-3"><label class="form-label small">Machine <span class="text-danger">*</span></label>
          <select class="form-select form-select-sm" id="sf-hp-machine"><option value="">Select...</option><option>HP-01</option><option>HP-02</option><option>HP-37</option></select></div>
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
      <button class="btn btn-danger btn-sm mt-3" onclick="submitHotPress('${batch.batch_id}')"><i class="bi bi-floppy me-1"></i>Log Hot Press → Grading</button>`,

    GRADING: `
      <h6><i class="bi bi-patch-check text-success me-1"></i>Grading (QC)</h6>
      <div class="row g-2">
        <div class="col-md-4"><label class="form-label small">Grader</label>
          <input class="form-control form-control-sm" id="sf-grader" list="sl-emp-list" placeholder="Grader name"></div>
        <div class="col-md-4"><label class="form-label small">NCG Reason (if NCG > 0)</label>
          <select class="form-select form-select-sm" id="sf-ncg-reason">
            <option value="">None</option>
            <option value="NCG-DELAMINATION">Delamination</option>
            <option value="NCG-SANDED-VENEER">Sanded veneer</option>
            <option value="NCG-GLUE-BLEED">Glue bleed</option>
            <option value="NCG-SURFACE-ROUGH">Surface rough</option>
            <option value="NCG-THICKNESS-VAR">Thickness variation</option>
            <option value="NCG-OTHER">Other</option>
          </select>
        </div>
      </div>
      <div class="row g-2 mt-1">
        <div class="col-md-2"><label class="form-label small text-success">Grade A pcs</label>
          <input type="number" class="form-control form-control-sm border-success" id="sf-gr-a" min="0" value="0"></div>
        <div class="col-md-2"><label class="form-label small text-primary">Grade B pcs</label>
          <input type="number" class="form-control form-control-sm border-primary" id="sf-gr-b" min="0" value="0"></div>
        <div class="col-md-2"><label class="form-label small text-warning">NCG pcs</label>
          <input type="number" class="form-control form-control-sm border-warning" id="sf-gr-ncg" min="0" value="0" oninput="grNcgCheck()"></div>
        <div class="col-md-2"><label class="form-label small text-danger">Reject pcs</label>
          <input type="number" class="form-control form-control-sm border-danger" id="sf-gr-rej" min="0" value="0"></div>
        <div class="col-md-4"><label class="form-label small">Notes</label>
          <input class="form-control form-control-sm" id="sf-gr-notes"></div>
      </div>
      <div id="sf-grade-total" class="small text-muted mt-1"></div>
      <button class="btn btn-success btn-sm mt-3" onclick="submitGrading('${batch.batch_id}')"><i class="bi bi-patch-check me-1"></i>Submit Grade + auto-backtrack</button>`,
  };

  return `<div class="card p-3">${formMap[s]||'<p class="text-muted">Unknown status: '+s+'</p>'}</div>
    <datalist id="sl-emp-list">${(_allEmployees||[]).map(e=>`<option value="${e.emp_id}">${e.emp_name} (${e.department})</option>`).join('')}</datalist>`;
}

// Laminating multi-row
let _lamRows=[], _repRows=[];
function addLamRow(bid){
  const id=Date.now();
  _lamRows.push({id});
  const area=document.getElementById('lam-rows-area');
  const div=document.createElement('div');
  div.className='row g-2 mb-2 align-items-end'; div.id=`lam-row-${id}`;
  div.innerHTML=`
    <div class="col-2"><label class="form-label small">Table</label>
      <select class="form-select form-select-sm" id="lam-tbl-${id}">
        ${['T01','T02','T03','T04','T05','T06','T07','T08','T09','T10'].map(t=>`<option>${t}</option>`).join('')}
      </select></div>
    <div class="col-2"><label class="form-label small">Operator 1</label>
      <input class="form-control form-control-sm" id="lam-e1-${id}" list="sl-emp-list" placeholder="EMP-001"></div>
    <div class="col-2"><label class="form-label small">Operator 2</label>
      <input class="form-control form-control-sm" id="lam-e2-${id}" list="sl-emp-list" placeholder="EMP-002"></div>
    <div class="col-2"><label class="form-label small">Target</label>
      <input type="number" class="form-control form-control-sm" id="lam-tgt-${id}" min="1"></div>
    <div class="col-2"><label class="form-label small">Actual</label>
      <input type="number" class="form-control form-control-sm" id="lam-act-${id}" min="0"></div>
    <div class="col-2"><label class="form-label small">Mix ref</label>
      <input class="form-control form-control-sm" id="lam-mix-${id}" placeholder="MIX-..."></div>`;
  area.appendChild(div);
}
function addRepRow(bid){
  const id=Date.now();
  _repRows.push({id});
  const area=document.getElementById('rep-rows-area');
  const div=document.createElement('div');
  div.className='row g-2 mb-2 align-items-end'; div.id=`rep-row-${id}`;
  div.innerHTML=`
    <div class="col-2"><label class="form-label small">Table</label>
      <select class="form-select form-select-sm" id="rep-tbl-${id}">
        ${['T01','T02','T03','T04','T05','T06','T07','T08','T09','T10'].map(t=>`<option>${t}</option>`).join('')}
      </select></div>
    <div class="col-2"><label class="form-label small">Type</label>
      <select class="form-select form-select-sm" id="rep-type-${id}"><option>ROUGH</option><option>FINE</option></select></div>
    <div class="col-2"><label class="form-label small">Operator 1</label>
      <input class="form-control form-control-sm" id="rep-e1-${id}" list="sl-emp-list" placeholder="EMP-001"></div>
    <div class="col-2"><label class="form-label small">Operator 2</label>
      <input class="form-control form-control-sm" id="rep-e2-${id}" list="sl-emp-list" placeholder="EMP-002"></div>
    <div class="col-2"><label class="form-label small">Pcs repaired</label>
      <input type="number" class="form-control form-control-sm" id="rep-pcs-${id}" min="0"></div>
    <div class="col-2"><label class="form-label small">Notes</label>
      <input class="form-control form-control-sm" id="rep-notes-${id}"></div>`;
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
function grNcgCheck(){
  const ncg=parseInt(document.getElementById('sf-gr-ncg').value)||0;
  const a=parseInt(document.getElementById('sf-gr-a').value)||0;
  const b=parseInt(document.getElementById('sf-gr-b').value)||0;
  const rej=parseInt(document.getElementById('sf-gr-rej').value)||0;
  const total=a+b+ncg+rej;
  document.getElementById('sf-grade-total').textContent=`Total: ${total} pcs  |  Yield: ${total?Math.round((a+b)/total*100):0}%`;
  if(ncg>0) document.getElementById('sf-ncg-reason').style.borderColor='#ffc107';
  else document.getElementById('sf-ncg-reason').style.borderColor='';
}

// ── Submit handlers ────────────────────────────────────────────
async function submitGlueMix(bid){
  const body={batch_id:bid,recipe_code:document.getElementById('sf-recipe').value.trim(),
    qty_kg:parseFloat(document.getElementById('sf-glue-kg').value)||0,
    mix_time_min:parseInt(document.getElementById('sf-mix-min').value)||null,
    operator_name:document.getElementById('sf-op-name').value.trim(),
    notes:document.getElementById('sf-notes').value||null};
  if(!body.recipe_code||!body.qty_kg){toast('Recipe code and qty required','danger');return;}
  try{await api('/api/production/glue-mix','POST',body);toast('Glue mix logged');slSelectBatch(bid);}
  catch(e){toast(e.message,'danger');}
}
async function submitAllLam(bid){
  if(!_lamRows.length){toast('Add at least one laminating table row','danger');return;}
  let ok=0;
  for(const r of _lamRows){
    const body={batch_id:bid,table_id:document.getElementById(`lam-tbl-${r.id}`).value,
      emp_code_1:document.getElementById(`lam-e1-${r.id}`).value.trim()||'—',
      emp_code_2:document.getElementById(`lam-e2-${r.id}`).value.trim()||'—',
      pcs_target:parseInt(document.getElementById(`lam-tgt-${r.id}`).value)||0,
      pcs_actual:parseInt(document.getElementById(`lam-act-${r.id}`).value)||0,
      glue_mix_ref:document.getElementById(`lam-mix-${r.id}`).value||null};
    if(!body.pcs_target)continue;
    try{await api('/api/production/laminating','POST',body);ok++;}catch(e){toast(e.message,'danger');}
  }
  if(ok>0){
    await api(`/api/prod-batches/${bid}/advance`,'POST',{next_status:'COLD_PRESS'});
    toast(`${ok} laminating rows logged`);_lamRows=[];slSelectBatch(bid);
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
  await api(`/api/prod-batches/${bid}/advance`,'POST',{next_status:'SANDING'});
  toast(ok>0?`${ok} repair rows logged`:'Repair stage complete (no rows)');
  _repRows=[];slSelectBatch(bid);
}
async function submitColdPress(bid){
  const body={batch_id:bid,machine_id:document.getElementById('sf-cp-machine').value,
    operator_name:document.getElementById('sf-cp-op').value.trim(),
    pressure_bar:parseFloat(document.getElementById('sf-cp-bar').value)||null,
    dwell_min:parseInt(document.getElementById('sf-cp-min').value)||null,
    pcs_in:parseInt(document.getElementById('sf-cp-in').value)||0,
    pcs_out:parseInt(document.getElementById('sf-cp-out').value)||0};
  if(!body.machine_id){toast('Select a machine','danger');return;}
  try{await api('/api/production/cold-press','POST',body);toast('Cold press logged');slSelectBatch(bid);}
  catch(e){toast(e.message,'danger');}
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
  try{await api('/api/production/sanding','POST',body);toast('Sanding logged');_sndDefects=0;slSelectBatch(bid);}
  catch(e){toast(e.message,'danger');}
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
  try{await api('/api/production/hot-press','POST',body);toast('Hot press logged');slSelectBatch(bid);}
  catch(e){toast(e.message,'danger');}
}
async function submitGrading(bid){
  const ncg=parseInt(document.getElementById('sf-gr-ncg').value)||0;
  const reason=document.getElementById('sf-ncg-reason').value;
  if(ncg>0&&!reason){toast('NCG reason required when NCG pcs > 0','danger');return;}
  const body={batch_id:bid,
    grader_name:document.getElementById('sf-grader').value.trim(),
    pcs_grade_a:parseInt(document.getElementById('sf-gr-a').value)||0,
    pcs_grade_b:parseInt(document.getElementById('sf-gr-b').value)||0,
    pcs_ncg:ncg,pcs_reject:parseInt(document.getElementById('sf-gr-rej').value)||0,
    ncg_reason_code:reason||null,notes:document.getElementById('sf-gr-notes').value||null};
  try{
    const result=await api('/api/production/grading','POST',body);
    toast(`Grade submitted — outcome: ${result.outcome}`,'success');
    if(result.backtrack){
      renderBacktrackAlert(result.backtrack,bid);
    }
    slSelectBatch(bid);
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
async function runBatchDiagnosis(bid){
  const el=document.getElementById('sl-ai-result');
  el.innerHTML='<div class="spinner-border spinner-border-sm me-2"></div>Analyzing...';
  try{
    const r=await api('/api/production/ai/analyze','POST',{mode:'BATCH_DIAGNOSIS',batch_id:bid});
    el.innerHTML=`<div class="alert alert-warning small"><b>AI Diagnosis</b><br>${(r.analysis||'').replace(/\\n/g,'<br>')}</div>`+
      (r.flags?.length?'<div class="d-flex flex-wrap gap-2">'+r.flags.map(f=>`
        <div class="badge bg-${f.severity==='HIGH'?'danger':f.severity==='MEDIUM'?'warning text-dark':'secondary'} p-2 text-wrap" style="max-width:220px;font-size:.75rem">
          <div class="fw-bold">${f.station}${f.operator_id?' · '+f.operator_id:''}</div>
          ${f.message}
        </div>`).join('')+'</div>':'');
  }catch(e){el.innerHTML=`<div class="alert alert-danger small">${e.message}</div>`;}
}

// New batch modal
async function openNewBatchModal(){
  bootstrap.Modal.getOrCreateInstance(document.getElementById('newBatchModal')).show();
}
async function createNewBatch(){
  const body={sku_code:document.getElementById('nb-sku').value.trim().toUpperCase(),
    line_id:document.getElementById('nb-line').value,
    shift:document.getElementById('nb-shift').value,
    qty_planned:parseInt(document.getElementById('nb-qty').value)||0,
    production_date:document.getElementById('nb-date').value,
    order_id:document.getElementById('nb-order').value||null};
  if(!body.sku_code||!body.qty_planned){toast('SKU and quantity required','danger');return;}
  try{
    const b=await api('/api/prod-batches','POST',body);
    bootstrap.Modal.getInstance(document.getElementById('newBatchModal')).hide();
    toast('Batch '+b.batch_id+' created');
    await slLoadBatches();
    slSelectBatch(b.batch_id);
  }catch(e){toast(e.message,'danger');}
}

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
    el.innerHTML+=`<div class="mb-2 p-2 bg-white border rounded"><span class="badge bg-secondary">AI</span><div class="small mt-1">${(r.reply||'').replace(/\\n/g,'<br>')}</div></div>`;
    el.scrollTop=el.scrollHeight;
  }catch(e){document.getElementById('ai-typing')?.remove();el.innerHTML+=`<div class="alert alert-danger small">${e.message}</div>`;}
}

// ── Router integration ─────────────────────────────────────────
// Hook into loadPage
const _origLoadPage=loadPage;
function loadPage(p){
  if(p==='employees') loadEmployees();
  else if(p==='station-log') loadStationLog();
  else if(p==='prod-reports'){prSetPeriod(30);loadProdReports();}
  else _origLoadPage(p);
}
"""

# Find the last </script> before </body>
last_script = html.rfind('</script>')
if last_script >= 0:
    html = html[:last_script] + PROD_JS + '\n</script>' + html[last_script+9:]
    ok.append('production JS injected before last </script>')
else:
    warn.append('No </script> found to inject JS')

# ══════════════════════════════════════════════════════════
# 5. sidebar-section-label CSS (if not present)
# ══════════════════════════════════════════════════════════
if '.sidebar-section-label' not in html:
    replace1(
        '.nav-item {',
        '.sidebar-section-label{font-size:.65rem;font-weight:700;letter-spacing:.08em;text-transform:uppercase;color:#94a3b8;padding:8px 16px 2px;}\n.nav-item {',
        'sidebar-section-label CSS added'
    )

# ══════════════════════════════════════════════════════════
# WRITE
# ══════════════════════════════════════════════════════════
with open('index.html', 'w', encoding='utf-8') as f:
    f.write(html)

print('=' * 55)
print('PRODUCTION MODULE PATCH RESULTS')
print('=' * 55)
for msg in ok:
    print(f'  OK   {msg}')
for msg in warn:
    print(f'  WARN {msg}')
print(f'\nTotal: {len(ok)} applied, {len(warn)} notes')
