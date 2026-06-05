"""UX fixes: P0 (showPage, missing functions), P1, P2."""
import re, sys
sys.stdout.reconfigure(encoding='utf-8')

html = open('index.html', encoding='utf-8').read()
ok = []
warn = []

def replace1(old, new, tag):
    global html
    if old in html:
        html = html.replace(old, new, 1)
        ok.append(tag)
    else:
        warn.append(f'NOT FOUND: {tag}')

# ══════════════════════════════════════════════════════════
# P0-A  showPage() helper (called 4 places but never defined)
# ══════════════════════════════════════════════════════════
replace1(
    'function navigateTo(page){',
    'function showPage(p){ navigateTo(p); }\nfunction navigateTo(page){',
    'showPage() added'
)

# ══════════════════════════════════════════════════════════
# P0-B  loadOrders / loadMachines / loadLogs / saveMachine
#        openMachineModal / openOrderModal
# ══════════════════════════════════════════════════════════
STUB_BLOCK = """
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
    if(!rows.length){tbody.innerHTML='<tr><td colspan="7" class="text-center text-muted py-4">No sales orders yet. <a href="#" onclick="event.preventDefault();document.getElementById(\\'btn-new-po\\')&&document.getElementById(\\'btn-new-po\\').click()">Create one in Order Intake.</a></td></tr>';return;}
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

// ══════════════════════════════════════════════════════════
// MACHINES
// ══════════════════════════════════════════════════════════
let _allMachines=[];
async function loadMachines(){
  try{
    const rows=await api('/api/machines').catch(()=>[]);
    _allMachines=rows;
    const grid=document.getElementById('machines-grid');
    if(!grid) return;
    if(!rows.length){grid.innerHTML='<div class="col-12"><p class="text-muted">No machines added yet.</p></div>';return;}
    grid.innerHTML=rows.map(m=>`
      <div class="col-md-4 col-lg-3">
        <div class="card p-3">
          <div class="d-flex justify-content-between align-items-start mb-1">
            <span class="fw-bold">${m.name||'Machine #'+m.id}</span>
            ${statusBadge(m.status||'active')}
          </div>
          <small class="text-muted">${m.type||''}</small>
          ${m.capacity_per_shift?`<div class="text-muted small mt-1">Cap: <b>${fmt(m.capacity_per_shift)}</b>/shift</div>`:''}
          <div class="d-flex gap-1 mt-2">
            <button class="btn btn-sm btn-outline-secondary" onclick="editMachine(${m.id},'${(m.name||'').replace(/'/g,"\\'")}','${m.status||'active'}','${m.type||''}',${m.capacity_per_shift||0})">Edit</button>
            <button class="btn btn-sm btn-outline-danger" onclick="deleteMachine(${m.id})">Delete</button>
          </div>
        </div>
      </div>`).join('');
  }catch(e){const g=document.getElementById('machines-grid');if(g)g.innerHTML=`<div class="col-12"><div class="alert alert-danger">${e.message}</div></div>`;}
}
function openMachineModal(){
  document.getElementById('mach-id').value='';
  ['mach-name','mach-type','mach-cap'].forEach(id=>{const e=document.getElementById(id);if(e)e.value='';});
  const s=document.getElementById('mach-status');if(s)s.value='active';
  document.querySelector('#machineModal .modal-title').textContent='Add Machine';
}
function editMachine(id,name,status,type,cap){
  document.getElementById('mach-id').value=id;
  document.getElementById('mach-name').value=name;
  document.getElementById('mach-status').value=status;
  document.getElementById('mach-type').value=type;
  document.getElementById('mach-cap').value=cap||'';
  document.querySelector('#machineModal .modal-title').textContent='Edit Machine';
  bootstrap.Modal.getOrCreateInstance(document.getElementById('machineModal')).show();
}
async function saveMachine(){
  const id=document.getElementById('mach-id').value;
  const body={
    name:document.getElementById('mach-name').value.trim(),
    status:document.getElementById('mach-status').value,
    type:document.getElementById('mach-type').value.trim(),
    capacity_per_shift:parseFloat(document.getElementById('mach-cap').value)||null,
  };
  if(!body.name){toast('Machine name is required','danger');return;}
  try{
    if(id) await api(`/api/machines/${id}`,'PUT',body);
    else await api('/api/machines','POST',body);
    bootstrap.Modal.getInstance(document.getElementById('machineModal')).hide();
    toast('Machine saved');
    loadMachines();
  }catch(e){toast(e.message,'danger');}
}
async function deleteMachine(id){
  if(!confirm('Delete this machine?')) return;
  try{await api(`/api/machines/${id}`,'DELETE');toast('Deleted');loadMachines();}catch(e){toast(e.message,'danger');}
}

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
"""

# Insert after the navigateTo / loadPage block (before UTILS)
replace1(
    '// ══════════════════════════════════════════════════════════\n// UTILS',
    STUB_BLOCK + '\n// ══════════════════════════════════════════════════════════\n// UTILS',
    'loadOrders/loadMachines/loadLogs/saveMachine stubs added'
)

# ══════════════════════════════════════════════════════════
# P0-C  loadLogs() already had one reference in saveLogModal; also openLogModal
#        The existing openLogModal is in a different part — don't re-define, just ensure
#        the log modal save works (it already calls loadLogs via try block at line 2215)
# ══════════════════════════════════════════════════════════

# ══════════════════════════════════════════════════════════
# P1-A  Toast: extend error delay to 6000ms
# ══════════════════════════════════════════════════════════
replace1(
    "bootstrap.Toast.getOrCreateInstance(el,{delay:3000}).show();",
    "bootstrap.Toast.getOrCreateInstance(el,{delay:type==='success'?3000:6000}).show();",
    'toast error delay extended to 6000ms'
)

# ══════════════════════════════════════════════════════════
# P1-B  Required field markers on Material modal
# ══════════════════════════════════════════════════════════
replace1(
    '<label class="form-label">Code</label><input class="form-control" id="mat-code"',
    '<label class="form-label">Code <span class="text-danger">*</span></label><input class="form-control" id="mat-code"',
    'mat-code required marker'
)
replace1(
    '<label class="form-label">Name</label><input class="form-control" id="mat-name"',
    '<label class="form-label">Name <span class="text-danger">*</span></label><input class="form-control" id="mat-name"',
    'mat-name required marker'
)
replace1(
    '<label class="form-label">Type</label>',
    '<label class="form-label">Type <span class="text-danger">*</span></label>',
    'mat-type required marker'
)

# ══════════════════════════════════════════════════════════
# P1-C  Required markers on BOM Builder fields (SKU Code, Name, Pcs/Pallet)
# ══════════════════════════════════════════════════════════
replace1(
    '<label class="form-label small">SKU Code</label>',
    '<label class="form-label small">SKU Code <span class="text-danger">*</span></label>',
    'bb SKU code required marker'
)
replace1(
    '<label class="form-label small">Product Name</label>',
    '<label class="form-label small">Product Name <span class="text-danger">*</span></label>',
    'bb product name required marker'
)
replace1(
    '<label class="form-label small">Pcs / Pallet</label>',
    '<label class="form-label small">Pcs / Pallet <span class="text-danger">*</span></label>',
    'bb pcs/pallet required marker'
)

# ══════════════════════════════════════════════════════════
# P1-D  Dynamic pallet count hint on PO line qty field
#        Update onPolFgSelect to show "= N pallets" on input
# ══════════════════════════════════════════════════════════
OLD_ON_FG = """  const pq=fg.pallet_qty||0;
  document.getElementById('pol-pallet-qty').value=pq;
  if(pq){
    hint.textContent=`Must be a multiple of ${pq} pcs/pallet`;
    hint.classList.remove('d-none');
  } else {
    hint.classList.add('d-none');
  }
}"""

NEW_ON_FG = """  const pq=fg.pallet_qty||0;
  document.getElementById('pol-pallet-qty').value=pq;
  if(pq){
    hint.classList.remove('d-none');
    updatePolPalletHint();
  } else {
    hint.classList.add('d-none');
  }
}
function updatePolPalletHint(){
  const pq=parseInt(document.getElementById('pol-pallet-qty').value)||0;
  const qty=parseInt(document.getElementById('pol-qty').value)||0;
  const hint=document.getElementById('pol-qty-hint');
  if(!pq){hint.classList.add('d-none');return;}
  const pallets=pq?Math.round(qty/pq*10)/10:0;
  const ok=qty&&qty%pq===0;
  hint.innerHTML=`Must be a multiple of <b>${pq}</b> pcs/pallet`+(qty?` &nbsp;<span class="badge ${ok?'bg-success':'bg-danger'}">${pallets.toFixed(1)} pallets</span>`:'');
  hint.classList.remove('d-none');
}"""

replace1(OLD_ON_FG, NEW_ON_FG, 'onPolFgSelect pallet hint dynamic')

# Wire up oninput on pol-qty to call updatePolPalletHint
replace1(
    '<input type="number" class="form-control" id="pol-qty" min="1">',
    '<input type="number" class="form-control" id="pol-qty" min="1" oninput="updatePolPalletHint()">',
    'pol-qty oninput for pallet hint'
)

# Also update editPoLine pq hint to use same function
OLD_EDIT_HINT = """  const hint=document.getElementById('pol-qty-hint');
  if(pq){hint.textContent=`Must be a multiple of ${pq} pcs/pallet`;hint.classList.remove('d-none');}
  else{hint.classList.add('d-none');}"""
NEW_EDIT_HINT = """  const hint=document.getElementById('pol-qty-hint');
  if(pq){hint.classList.remove('d-none');updatePolPalletHint();}
  else{hint.classList.add('d-none');}"""
replace1(OLD_EDIT_HINT, NEW_EDIT_HINT, 'editPoLine pallet hint dynamic')

# ══════════════════════════════════════════════════════════
# P1-E  Elapsed time on dept batch cards
# ══════════════════════════════════════════════════════════
# Add timeAgo helper near other util functions
replace1(
    'function fmt(n){return n!=null?Number(n).toLocaleString():\'-\';}',
    'function fmt(n){return n!=null?Number(n).toLocaleString():\'-\';}\nfunction timeAgo(ts){if(!ts)return \'\';const d=new Date(ts.endsWith(\'Z\')||ts.includes(\'+\')?ts:ts+\'Z\');const m=Math.round((Date.now()-d)/60000);if(m<1)return \'just now\';if(m<60)return m+\'m ago\';const h=Math.floor(m/60),rm=m%60;if(h<24)return h+\'h\'+(rm?` ${rm}m`:\'\')+\' ago\';return Math.floor(h/24)+\'d ago\';}',
    'timeAgo helper added'
)

# Add elapsed time badge to dept batch cards
OLD_BATCH_CARD = """          <div class="fw-bold small">${b.batch_number||'B#'+b.id}</div>
          <div class="text-muted small">${b.product_name||''}</div>
          <div class="fs-5 fw-bold text-primary">${fmt(b.quantity)} pcs</div>
          ${b.parent_batch_id?`<span class="badge bg-warning text-dark mt-1">Split #${b.parent_batch_id}</span>`:''}"""
NEW_BATCH_CARD = """          <div class="d-flex justify-content-between align-items-start">
            <div class="fw-bold small">${b.batch_number||'B#'+b.id}</div>
            ${b.created_at?`<span class="badge bg-light text-muted border" style="font-size:.65rem">${timeAgo(b.created_at)}</span>`:''}
          </div>
          <div class="text-muted small">${b.product_name||''}</div>
          <div class="fs-5 fw-bold text-primary">${fmt(b.quantity)} pcs</div>
          ${b.parent_batch_id?`<span class="badge bg-warning text-dark mt-1">Split #${b.parent_batch_id}</span>`:''}"""
replace1(OLD_BATCH_CARD, NEW_BATCH_CARD, 'dept batch card elapsed time badge')

# ══════════════════════════════════════════════════════════
# P2-A  Material filter buttons: count badges
# ══════════════════════════════════════════════════════════
# Update filterMaterials to also update button labels with counts
OLD_FILTER_MAT = """function filterMaterials(type){
  _matFilter=type;
  document.querySelectorAll('#mat-type-filter button').forEach(b=>{
    const labels={'':'All','core_board':'Core Boards','veneer_sheet':'Veneers','adhesive':'Adhesive'};
    b.classList.toggle('active', b.textContent.trim()===(labels[type]||'All'));
  });
  renderMaterials(type?_allMaterials.filter(m=>m.type===type):_allMaterials);
}"""
NEW_FILTER_MAT = """function filterMaterials(type){
  _matFilter=type;
  const labels={'':'All','core_board':'Core Boards','veneer_sheet':'Veneers','adhesive':'Adhesive'};
  document.querySelectorAll('#mat-type-filter button').forEach(b=>{
    const t=b.dataset.matType!==undefined?b.dataset.matType:Object.keys(labels).find(k=>b.textContent.trim().startsWith(labels[k]))||'';
    b.classList.toggle('active',t===type);
  });
  renderMaterials(type?_allMaterials.filter(m=>m.type===type):_allMaterials);
}
function updateMatFilterCounts(){
  const counts={'':_allMaterials.length};
  ['core_board','veneer_sheet','adhesive'].forEach(t=>{counts[t]=_allMaterials.filter(m=>m.type===t).length;});
  const labels={'':'All','core_board':'Core Boards','veneer_sheet':'Veneers','adhesive':'Adhesive'};
  document.querySelectorAll('#mat-type-filter button').forEach(b=>{
    const t=b.dataset.matType!==undefined?b.dataset.matType:Object.keys(labels).find(k=>b.textContent.trim().startsWith(labels[k]))||'';
    b.dataset.matType=t;
    b.textContent=`${labels[t]||t} (${counts[t]||0})`;
  });
}"""
replace1(OLD_FILTER_MAT, NEW_FILTER_MAT, 'filterMaterials with count badges')

# Call updateMatFilterCounts after loadMaterials renders data
replace1(
    'renderMaterials(_allMaterials);\n  renderConsumables(_allConsumables);',
    'renderMaterials(_allMaterials);\n  renderConsumables(_allConsumables);\n  updateMatFilterCounts();',
    'updateMatFilterCounts called after loadMaterials'
)

# ══════════════════════════════════════════════════════════
# P2-B  FG page: empty state with BOM Builder link
# ══════════════════════════════════════════════════════════
OLD_RENDER_FG = """  document.getElementById('fg-count').textContent=rows.length;
  document.querySelector('#fg-table tbody').innerHTML=rows.map(s=>`<tr>"""
NEW_RENDER_FG = """  document.getElementById('fg-count').textContent=rows.length;
  if(!rows.length){
    document.querySelector('#fg-table tbody').innerHTML=`<tr><td colspan="7" class="text-center py-5">
      <i class="bi bi-grid text-muted" style="font-size:2rem"></i>
      <div class="text-muted mt-2">No finished goods yet.</div>
      <button class="btn btn-primary btn-sm mt-3" onclick="navigateTo('bom');setTimeout(()=>document.querySelector('#bom-main-tabs .nav-link')?.click(),100)">
        <i class="bi bi-plus-lg me-1"></i>Create via BOM Builder →
      </button>
    </td></tr>`;
    return;
  }
  document.querySelector('#fg-table tbody').innerHTML=rows.map(s=>`<tr>"""
replace1(OLD_RENDER_FG, NEW_RENDER_FG, 'FG empty state with BOM Builder link')

# Close the if block - we need to close the map chain properly
# The issue is we inserted a return but the map chain hasn't started yet
# Check if there's a trailing issue - the existing code after rows.map would be fine

# ══════════════════════════════════════════════════════════
# P2-C  Auto-select first PO on loadOrderIntake
# ══════════════════════════════════════════════════════════
OLD_ORDER_INTAKE = "async function loadOrderIntake(){await preload();await loadPoList();}"
NEW_ORDER_INTAKE = """async function loadOrderIntake(){
  await preload();
  await loadPoList();
  // Auto-select first PO if none selected
  if(!selectedPoId){
    const pos=await api('/api/purchase-orders').catch(()=>[]);
    if(pos.length) selectPo(pos[0].id);
  }
}"""
replace1(OLD_ORDER_INTAKE, NEW_ORDER_INTAKE, 'loadOrderIntake auto-select first PO')

# ══════════════════════════════════════════════════════════
# P2-D  Spinner placeholders in Glue / Bleaching / Packing tab panes
# ══════════════════════════════════════════════════════════
replace1(
    '      <div id="glue-list"></div>\n    </div>',
    '      <div id="glue-list"><div class="text-center text-muted py-4"><div class="spinner-border spinner-border-sm me-2"></div>Loading...</div></div>\n    </div>',
    'glue tab spinner placeholder'
)

# Find bleach and pack list divs
replace1(
    '      <div id="bleach-list"></div>',
    '      <div id="bleach-list"><div class="text-center text-muted py-4"><div class="spinner-border spinner-border-sm me-2"></div>Loading...</div></div>',
    'bleach tab spinner placeholder'
)
replace1(
    '      <div id="pack-list"></div>',
    '      <div id="pack-list"><div class="text-center text-muted py-4"><div class="spinner-border spinner-border-sm me-2"></div>Loading...</div></div>',
    'pack tab spinner placeholder'
)

# ══════════════════════════════════════════════════════════
# WRITE & REPORT
# ══════════════════════════════════════════════════════════
with open('index.html', 'w', encoding='utf-8') as f:
    f.write(html)

print()
print('=' * 55)
print('UX PATCH RESULTS')
print('=' * 55)
for msg in ok:
    print(f'  OK   {msg}')
for msg in warn:
    print(f'  WARN {msg}')
print()
print(f'Total: {len(ok)} applied, {len(warn)} not found')
