"""
Patch index.html — Phase 3: Packing Station
Changes:
  1. CSS: .bg-packing (purple badge class)
  2. STATION_ORDER/LABEL/ICON/COLOR — insert PACKING before COMPLETE
  3. slStatusBadge — add PACKING purple
  4. Status filter select — add <option>PACKING</option>
  5. renderStationCard formMap — add PACKING form
  6. submitPacking() function
  7. ROLE_PAGES — WAREHOUSE gets station-log; DEPT_LEADER gets packing-center
  8. loadPackingCenter() — rewritten to use /api/prod-batches (GRADING+PACKING status)
"""
import sys, os
sys.stdout.reconfigure(encoding='utf-8')

HTML_PATH = os.path.join(os.path.dirname(__file__), 'index.html')
with open(HTML_PATH, encoding='utf-8') as f:
    src = f.read()

changes = 0
def replace1(old, new, label=''):
    global src, changes
    if old not in src:
        print(f'  WARN not found: {label or old[:70]}')
        return
    src = src.replace(old, new, 1)
    changes += 1
    print(f'  OK  {label or old[:70]}')

# ── 1. CSS: purple packing badge ─────────────────────────────────
replace1(
    '/* ══════════════════════════════════════════════\n   Kanban\n══════════════════════════════════════════════ */',
    '.bg-packing{background:#8b5cf6!important;}\n/* ══════════════════════════════════════════════\n   Kanban\n══════════════════════════════════════════════ */',
    'CSS .bg-packing'
)

# ── 2a. STATION_ORDER — insert PACKING before COMPLETE ───────────
replace1(
    "const STATION_ORDER=['GLUE_MIX','LAMINATING','COLD_PRESS','REPAIR','SANDING','HOT_PRESS','GRADING','COMPLETE'];",
    "const STATION_ORDER=['GLUE_MIX','LAMINATING','COLD_PRESS','REPAIR','SANDING','HOT_PRESS','GRADING','PACKING','COMPLETE'];",
    'STATION_ORDER + PACKING'
)

# ── 2b. STATION_LABEL — add Packing ──────────────────────────────
replace1(
    "'GRADING':'Grading','COMPLETE':'Complete'};",
    "'GRADING':'Grading','PACKING':'Packing','COMPLETE':'Complete'};",
    'STATION_LABEL + Packing'
)

# ── 2c. STATION_ICON — add bi-boxes ──────────────────────────────
replace1(
    "'GRADING':'bi-patch-check','COMPLETE':'bi-check-circle-fill'};",
    "'GRADING':'bi-patch-check','PACKING':'bi-boxes','COMPLETE':'bi-check-circle-fill'};",
    'STATION_ICON + PACKING'
)

# ── 2d. STATION_COLOR — add packing ──────────────────────────────
replace1(
    "'GRADING':'success','COMPLETE':'dark'};",
    "'GRADING':'success','PACKING':'packing','COMPLETE':'dark'};",
    'STATION_COLOR + PACKING'
)

# ── 3. slStatusBadge — add PACKING purple ────────────────────────
replace1(
    "const c={GLUE_MIX:'warning',LAMINATING:'primary',COLD_PRESS:'info',REPAIR:'secondary',\n    SANDING:'warning text-dark',HOT_PRESS:'danger',GRADING:'success',COMPLETE:'dark'};",
    "const c={GLUE_MIX:'warning',LAMINATING:'primary',COLD_PRESS:'info',REPAIR:'secondary',\n    SANDING:'warning text-dark',HOT_PRESS:'danger',GRADING:'success',PACKING:'packing',COMPLETE:'dark'};",
    'slStatusBadge + PACKING'
)

# ── 4. Status filter select — add PACKING option ─────────────────
replace1(
    '<option>GRADING</option><option>COMPLETE</option>',
    '<option>GRADING</option><option>PACKING</option><option>COMPLETE</option>',
    'status filter option PACKING'
)

# ── 5. renderStationCard — add PACKING form ───────────────────────
PACKING_FORM = """
    PACKING: `
      <h6><i class="bi bi-boxes text-purple me-1" style="color:#8b5cf6"></i>Packing</h6>
      <div class="alert alert-light border-start border-4 py-2 small mb-3" style="border-color:#8b5cf6!important">
        <i class="bi bi-info-circle me-1"></i>Consolidation point — all lines feed into Packing.
      </div>
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
      <button class="btn btn-sm mt-3 text-white" style="background:#8b5cf6"
              onclick="submitPacking('${batch.batch_id}')">
        <i class="bi bi-floppy me-1"></i>Log Packing
      </button>`,"""

replace1(
    "      <button class=\"btn btn-success btn-sm mt-3\" onclick=\"submitGrading('${batch.batch_id}')\"><i class=\"bi bi-patch-check me-1\"></i>Submit Grade + auto-backtrack</button>`,\n  };",
    "      <button class=\"btn btn-success btn-sm mt-3\" onclick=\"submitGrading('${batch.batch_id}')\"><i class=\"bi bi-patch-check me-1\"></i>Submit Grade + auto-backtrack</button>`," +
    PACKING_FORM + "\n  };",
    'renderStationCard PACKING form'
)

# ── 6. submitPacking() function — insert after submitGrading block ─
SUBMIT_PACKING_FN = """
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
    slSelectBatch(bid);
  }catch(e){toast(e.message,'danger');}
}
"""

replace1(
    'function renderBacktrackAlert(bt,bid){',
    SUBMIT_PACKING_FN + 'function renderBacktrackAlert(bt,bid){',
    'submitPacking() function'
)

# ── 7a. ROLE_PAGES WAREHOUSE — add station-log, packing-center ────
replace1(
    "  WAREHOUSE: new Set([\n    'materials','dept-grading','packing-center','dept-fg_warehouse',\n    'orders','warehouse-queue','dept-costs',\n  ]),",
    "  WAREHOUSE: new Set([\n    'materials','dept-grading','packing-center','dept-fg_warehouse',\n    'orders','machines','warehouse-queue','dept-costs','station-log',\n  ]),",
    'ROLE_PAGES WAREHOUSE + station-log'
)

# ── 7b. ROLE_PAGES DEPARTMENT_LEADER — add packing-center ─────────
replace1(
    "  DEPARTMENT_LEADER: new Set([\n    'dashboard','prod-flow','station-log','consumable-requests',\n  ]),",
    "  DEPARTMENT_LEADER: new Set([\n    'dashboard','prod-flow','station-log','packing-center','consumable-requests',\n  ]),",
    'ROLE_PAGES DEPT_LEADER + packing-center'
)

# ── 8. loadPackingCenter() — rewrite to use prod-batches API ──────
OLD_PACKING_CENTER_FN = """async function loadPackingCenter(){
  const batches=await api('/api/batches?department=packing').catch(()=>[]);
  // Stats
  const totalPcs=batches.reduce((s,b)=>s+(b.quantity||0),0);
  const byLine={P01:0,PM2:0,P37:0};
  batches.forEach(b=>{if(b.production_line) byLine[b.production_line]=(byLine[b.production_line]||0)+b.quantity;});
  document.getElementById('packing-stats').innerHTML=[
    {val:batches.length,lbl:'Batches Awaiting Packing',ico:'bi-boxes',c:'purple'},
    {val:totalPcs,lbl:'Total Pieces',ico:'bi-stack',c:'primary'},
    {val:byLine.P01,lbl:'From P01',ico:'bi-layers',c:'info'},
    {val:byLine.PM2,lbl:'From PM2',ico:'bi-layers',c:'success'},
  ].map(s=>`<div class="col-6 col-md-3"><div class="stat-card d-flex justify-content-between align-items-start">
    <div><div class="val" style="color:${s.c==='purple'?'#8b5cf6':'var(--'+s.c+')'}">${fmt(s.val)}</div><div class="lbl">${s.lbl}</div></div>
    <i class="bi ${s.ico}" style="font-size:2rem;opacity:.12;color:${s.c==='purple'?'#8b5cf6':''}"></i>
  </div></div>`).join('');
  const grid=document.getElementById('packing-grid');
  if(!batches.length){grid.innerHTML='<p class="text-muted">No batches currently at packing.</p>';return;}
  grid.innerHTML=batches.map(b=>`
    <div class="pack-card">
      <div class="d-flex justify-content-between mb-2">
        <span class="fw-bold small">${b.batch_number||'B#'+b.id}</span>
        ${lineBadge(b.production_line||'P01')}"""

NEW_PACKING_CENTER_FN = """async function loadPackingCenter(){
  // Fetch both GRADING (pipeline) and PACKING (active) batches from all lines
  const [gradingBatches, packingBatches] = await Promise.all([
    api('/api/prod-batches?status=GRADING').catch(()=>[]),
    api('/api/prod-batches?status=PACKING').catch(()=>[])
  ]);
  const allBatches = [...(gradingBatches||[]), ...(packingBatches||[])];
  const byLine={P01:0,P02:0,P37:0};
  packingBatches?.forEach(b=>{ byLine[b.line_id]=(byLine[b.line_id]||0)+(b.qty_planned||0); });
  const totalPcs=packingBatches?.reduce((s,b)=>s+(b.qty_planned||0),0)||0;
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
    const isGrading=b.status==='GRADING';
    const borderColor=isGrading?'#16a34a':'#8b5cf6';
    return `
    <div class="pack-card" style="border-top-color:${borderColor};cursor:pointer" onclick="navigateTo('station-log');setTimeout(()=>slSelectBatch('${b.batch_id}'),400)">
      <div class="d-flex justify-content-between mb-2">
        <span class="fw-bold small">${b.batch_id}</span>
        ${slStatusBadge(b.status)}"""

replace1(OLD_PACKING_CENTER_FN, NEW_PACKING_CENTER_FN, 'loadPackingCenter() rewrite (start)')

# Fix the rest of the function (the card body and closing)
OLD_PACK_CARD_BODY = """        ${lineBadge(b.production_line||'P01')}"""
# Don't need to find this as it's part of the replaced block above

# Find and replace the rest of the old function body
OLD_PACK_END = """      </div>
      <div class="small text-muted">${b.product_name||b.sku}</div>
      <div class="fw-bold text-primary mt-1">${fmt(b.quantity)} pcs</div>
      <div class="small mt-1">${b.production_line||''}</div>
    </div>
  `).join('');
}"""

NEW_PACK_END = """        <span class="badge" style="background:${lineBadgeColor(b.line_id)};color:#fff;font-size:.65rem">${b.line_id||'—'}</span>
      </div>
      <div class="small text-muted">${b.sku_code||'—'}</div>
      <div class="fw-bold mt-1" style="color:${borderColor}">${fmt(b.qty_planned||0)} pcs planned</div>
      <div class="small text-muted mt-1">${b.production_date||''} · ${b.shift||''}</div>
      <div class="small mt-1 text-muted"><i class="bi bi-arrow-right-circle me-1"></i>Click to open in Station Log</div>
    </div>`;
  }).join('');
}
function lineBadgeColor(line){
  return {P01:'#2563eb',P02:'#16a34a',P37:'#9d174d'}[line]||'#64748b';
}"""

replace1(OLD_PACK_END, NEW_PACK_END, 'loadPackingCenter() card body + close')

# ─────────────────────────────────────────────────────────────────
with open(HTML_PATH, 'w', encoding='utf-8') as f:
    f.write(src)

print(f'\nDone. {changes} changes applied.')
