"""Inject BOM Builder page and JS into index.html"""

with open('index.html','r',encoding='utf-8') as f:
    html = f.read()

# ── 1. PAGE HTML ──────────────────────────────────────────────────────────────
BOM_BUILDER_PAGE = """
<!-- BOM BUILDER -->
<div class="page" id="page-bom-builder">
  <div class="d-flex justify-content-between align-items-center mb-3">
    <div>
      <h4 class="mb-0"><i class="bi bi-pencil-square me-2 text-primary"></i>BOM Builder</h4>
      <p class="text-muted small mb-0">Create or update a Bill of Materials for any Finished Good</p>
    </div>
    <button class="btn btn-sm btn-outline-secondary" onclick="resetBomBuilder()"><i class="bi bi-plus-lg me-1"></i>New BOM</button>
  </div>

  <!-- Load existing -->
  <div class="card p-3 mb-3" style="position:relative">
    <label class="form-label fw-semibold mb-1">Load existing FG to edit</label>
    <input class="form-control" id="bb-load-q" placeholder="Type SKU code or name to search..." oninput="bbLoadSearch(this.value)" autocomplete="off">
    <div id="bb-load-drop" class="d-none" style="position:absolute;top:100%;left:16px;right:16px;z-index:200;background:#fff;border:1px solid #dee2e6;border-radius:0 0 6px 6px;max-height:200px;overflow-y:auto;box-shadow:0 4px 12px rgba(0,0,0,.1)"></div>
  </div>

  <!-- SKU Details -->
  <div class="card p-3 mb-3">
    <h6 class="fw-bold mb-3 text-primary"><i class="bi bi-tag me-1"></i>FG SKU Details</h6>
    <div class="row g-2">
      <div class="col-md-2">
        <label class="form-label small fw-semibold">SKU Code *</label>
        <input class="form-control form-control-sm" id="bb-code" placeholder="e.g. 4ALM52A11" oninput="this.value=this.value.toUpperCase()">
      </div>
      <div class="col-md-4">
        <label class="form-label small fw-semibold">Name / Description *</label>
        <input class="form-control form-control-sm" id="bb-name" placeholder="e.g. MDF 5.2 Alder PC A BM">
      </div>
      <div class="col-md-2">
        <label class="form-label small fw-semibold">Thickness (mm)</label>
        <input type="number" class="form-control form-control-sm" id="bb-thick" step="0.1" placeholder="5.2">
      </div>
      <div class="col-md-2">
        <label class="form-label small fw-semibold">Width (mm)</label>
        <input type="number" class="form-control form-control-sm" id="bb-width" placeholder="1232">
      </div>
      <div class="col-md-2">
        <label class="form-label small fw-semibold">Length (mm)</label>
        <input type="number" class="form-control form-control-sm" id="bb-length" placeholder="2452">
      </div>
    </div>
    <div class="row g-2 mt-1">
      <div class="col-md-2">
        <label class="form-label small fw-semibold">Pcs / Pallet *</label>
        <input type="number" class="form-control form-control-sm" id="bb-pallet-qty" min="1" placeholder="135" oninput="bbSyncQtyDefaults()">
      </div>
    </div>
  </div>

  <!-- Components grid -->
  <div class="row g-3 mb-3">

    <div class="col-md-4">
      <div class="card h-100 p-3">
        <div class="d-flex justify-content-between align-items-center mb-2">
          <h6 class="mb-0 fw-bold"><span class="badge bg-secondary me-1">1</span>Base Board</h6>
          <button class="btn btn-sm btn-outline-danger py-0 px-1 d-none" id="bb-clear-base" onclick="bbClearComp('base')">x</button>
        </div>
        <input class="form-control form-control-sm mb-1" id="bb-search-base" placeholder="Search core boards..." oninput="bbFilter('base',this.value)">
        <select class="form-select form-select-sm" id="bb-select-base" size="5" onchange="bbPick('base',this.value)"></select>
        <div id="bb-sel-base" class="mt-2 d-none">
          <div class="alert alert-secondary py-1 px-2 mb-1 small fw-bold" id="bb-badge-base"></div>
          <label class="form-label small mb-1">Qty (sheets / pallet)</label>
          <input type="number" class="form-control form-control-sm" id="bb-qty-base" min="1">
        </div>
      </div>
    </div>

    <div class="col-md-4">
      <div class="card h-100 p-3">
        <div class="d-flex justify-content-between align-items-center mb-2">
          <h6 class="mb-0 fw-bold"><span class="badge bg-primary me-1">2</span>Face Veneer</h6>
          <button class="btn btn-sm btn-outline-danger py-0 px-1 d-none" id="bb-clear-faceV" onclick="bbClearComp('faceV')">x</button>
        </div>
        <input class="form-control form-control-sm mb-1" id="bb-search-faceV" placeholder="Search veneers..." oninput="bbFilter('faceV',this.value)">
        <select class="form-select form-select-sm" id="bb-select-faceV" size="5" onchange="bbPick('faceV',this.value)"></select>
        <div id="bb-sel-faceV" class="mt-2 d-none">
          <div class="alert alert-primary py-1 px-2 mb-1 small fw-bold" id="bb-badge-faceV"></div>
          <label class="form-label small mb-1">Qty (sheets / pallet)</label>
          <input type="number" class="form-control form-control-sm" id="bb-qty-faceV" min="1">
        </div>
      </div>
    </div>

    <div class="col-md-4">
      <div class="card h-100 p-3">
        <div class="d-flex justify-content-between align-items-center mb-2">
          <h6 class="mb-0 fw-bold"><span class="badge bg-info text-dark me-1">3</span>Back Veneer</h6>
          <button class="btn btn-sm btn-outline-danger py-0 px-1 d-none" id="bb-clear-backV" onclick="bbClearComp('backV')">x</button>
        </div>
        <input class="form-control form-control-sm mb-1" id="bb-search-backV" placeholder="Search veneers..." oninput="bbFilter('backV',this.value)">
        <select class="form-select form-select-sm" id="bb-select-backV" size="5" onchange="bbPick('backV',this.value)"></select>
        <div id="bb-sel-backV" class="mt-2 d-none">
          <div class="alert alert-info py-1 px-2 mb-1 small fw-bold" id="bb-badge-backV"></div>
          <label class="form-label small mb-1">Qty (sheets / pallet)</label>
          <input type="number" class="form-control form-control-sm" id="bb-qty-backV" min="1">
        </div>
      </div>
    </div>

    <div class="col-md-4">
      <div class="card h-100 p-3">
        <div class="d-flex justify-content-between align-items-center mb-2">
          <h6 class="mb-0 fw-bold"><span class="badge bg-warning text-dark me-1">4</span>Face Glue</h6>
          <button class="btn btn-sm btn-outline-danger py-0 px-1 d-none" id="bb-clear-faceG" onclick="bbClearComp('faceG')">x</button>
        </div>
        <input class="form-control form-control-sm mb-1" id="bb-search-faceG" placeholder="Search glue formulas..." oninput="bbFilter('faceG',this.value)">
        <select class="form-select form-select-sm" id="bb-select-faceG" size="5" onchange="bbPick('faceG',this.value)"></select>
        <div id="bb-sel-faceG" class="mt-2 d-none">
          <div class="alert alert-warning py-1 px-2 mb-1 small fw-bold" id="bb-badge-faceG"></div>
          <label class="form-label small mb-1">Usage (g / face press)</label>
          <input type="number" class="form-control form-control-sm" id="bb-qty-faceG" min="1" step="0.5" value="45">
        </div>
      </div>
    </div>

    <div class="col-md-4">
      <div class="card h-100 p-3">
        <div class="d-flex justify-content-between align-items-center mb-2">
          <h6 class="mb-0 fw-bold"><span class="badge bg-warning text-dark me-1">5</span>Back Glue</h6>
          <button class="btn btn-sm btn-outline-danger py-0 px-1 d-none" id="bb-clear-backG" onclick="bbClearComp('backG')">x</button>
        </div>
        <input class="form-control form-control-sm mb-1" id="bb-search-backG" placeholder="Search glue formulas..." oninput="bbFilter('backG',this.value)">
        <select class="form-select form-select-sm" id="bb-select-backG" size="5" onchange="bbPick('backG',this.value)"></select>
        <div id="bb-sel-backG" class="mt-2 d-none">
          <div class="alert alert-warning py-1 px-2 mb-1 small fw-bold" id="bb-badge-backG"></div>
          <label class="form-label small mb-1">Usage (g / face press)</label>
          <input type="number" class="form-control form-control-sm" id="bb-qty-backG" min="1" step="0.5" value="45">
        </div>
      </div>
    </div>

    <div class="col-md-4">
      <div class="card h-100 p-3">
        <div class="d-flex justify-content-between align-items-center mb-2">
          <h6 class="mb-0 fw-bold"><span class="badge bg-success me-1">6</span>Packing Spec</h6>
          <button class="btn btn-sm btn-outline-danger py-0 px-1 d-none" id="bb-clear-pack" onclick="bbClearComp('pack')">x</button>
        </div>
        <input class="form-control form-control-sm mb-1" id="bb-search-pack" placeholder="Search packing specs..." oninput="bbFilter('pack',this.value)">
        <select class="form-select form-select-sm" id="bb-select-pack" size="5" onchange="bbPick('pack',this.value)"></select>
        <div id="bb-sel-pack" class="mt-2 d-none">
          <div class="alert alert-success py-1 px-2 small fw-bold" id="bb-badge-pack"></div>
        </div>
      </div>
    </div>

  </div>

  <!-- Actions -->
  <div class="d-flex justify-content-end gap-2 mb-4">
    <button class="btn btn-outline-secondary" onclick="resetBomBuilder()">Clear</button>
    <button class="btn btn-primary px-5" onclick="saveBomBuilder()"><i class="bi bi-floppy me-1"></i>Save BOM</button>
  </div>
</div>

"""

# ── 2. JS ─────────────────────────────────────────────────────────────────────
BOM_BUILDER_JS = r"""
// ════════════════════════════════════════════════════════════
// BOM BUILDER
// ════════════════════════════════════════════════════════════
let _bbMats = {};   // { base:[], faceV:[], backV:[], faceG:[], backG:[], pack:[] }
let _bbPicked = {}; // { base:{code,name}, faceV:{...}, ... }
let _bbAllFg = [];

async function loadBomBuilder(){
  // Load all material lists in parallel
  const [mats, glues, packing] = await Promise.all([
    api('/api/materials').catch(()=>[]),
    api('/api/materials?include_formulas=true').catch(()=>[]),
    api('/api/packing-skus').catch(()=>[]),
  ]);
  const boards  = mats.filter(m=>m.type==='core_board');
  const veneers = mats.filter(m=>m.type==='veneer_sheet');
  const formulas = glues.filter(m=>m.type==='glue_formula');
  _bbMats = { base:boards, faceV:veneers, backV:veneers, faceG:formulas, backG:formulas, pack:packing };
  _bbAllFg = await api('/api/fg').catch(()=>[]);
  bbRenderAll();
}

function bbRenderAll(){
  const comps = ['base','faceV','backV','faceG','backG','pack'];
  comps.forEach(c => bbRenderOptions(c, _bbMats[c]));
}

function bbRenderOptions(comp, list){
  const sel = document.getElementById('bb-select-'+comp);
  if(!sel) return;
  sel.innerHTML = list.map(m=>{
    const label = comp==='pack'
      ? (m.code+' — '+(m.name||m.customer||''))
      : (m.code+' — '+(m.name||''));
    return '<option value="'+m.code+'">'+label+'</option>';
  }).join('');
}

function bbFilter(comp, q){
  const s = q.toLowerCase();
  const list = s ? _bbMats[comp].filter(m=>(m.code+' '+(m.name||'')).toLowerCase().includes(s)) : _bbMats[comp];
  bbRenderOptions(comp, list);
}

function bbPick(comp, code){
  if(!code) return;
  const list = _bbMats[comp];
  const item = list.find(m=>m.code===code);
  if(!item) return;
  _bbPicked[comp] = item;

  const pq = parseInt(document.getElementById('bb-pallet-qty').value)||0;
  const badge = document.getElementById('bb-badge-'+comp);
  const sel   = document.getElementById('bb-sel-'+comp);
  const clear = document.getElementById('bb-clear-'+comp);

  badge.textContent = item.code + (item.name ? '  |  '+item.name : '');
  sel.classList.remove('d-none');
  clear.classList.remove('d-none');

  // Set default qty
  const qtyInput = document.getElementById('bb-qty-'+comp);
  if(qtyInput && !qtyInput.value){
    if(comp==='faceG'||comp==='backG') qtyInput.value = 45;
    else qtyInput.value = pq || '';
  }
}

function bbClearComp(comp){
  delete _bbPicked[comp];
  document.getElementById('bb-sel-'+comp).classList.add('d-none');
  document.getElementById('bb-clear-'+comp).classList.add('d-none');
  document.getElementById('bb-search-'+comp).value='';
  document.getElementById('bb-qty-'+comp) && (document.getElementById('bb-qty-'+comp).value='');
  bbRenderOptions(comp, _bbMats[comp]);
}

function bbSyncQtyDefaults(){
  const pq = parseInt(document.getElementById('bb-pallet-qty').value)||0;
  if(!pq) return;
  ['base','faceV','backV'].forEach(c=>{
    if(_bbPicked[c]){
      const qi = document.getElementById('bb-qty-'+c);
      if(qi && !qi.value) qi.value = pq;
    }
  });
}

// Load existing FG search dropdown
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
    '<span class="text-muted">'+( f.name||'' )+'</span>'+
    '</div>'
  ).join('');
  drop.classList.remove('d-none');
}

async function bbLoadFg(code){
  document.getElementById('bb-load-drop').classList.add('d-none');
  document.getElementById('bb-load-q').value = code;
  try{
    const bom = await api('/api/fg/'+code+'/bom');
    // Fill SKU fields
    document.getElementById('bb-code').value = bom.sku_code||'';
    document.getElementById('bb-name').value = bom.sku_name||'';
    document.getElementById('bb-thick').value = bom.thickness_mm||'';
    document.getElementById('bb-width').value = bom.width_mm||'';
    document.getElementById('bb-length').value = bom.length_mm||'';
    document.getElementById('bb-pallet-qty').value = bom.pallet_qty||'';

    // Fill component pickers
    const map = [
      ['base',  bom.base_board,  'qty'],
      ['faceV', bom.face_veneer, 'qty'],
      ['backV', bom.back_veneer, 'qty'],
      ['faceG', bom.face_glue,   'usage_g_per_face'],
      ['backG', bom.back_glue,   'usage_g_per_face'],
    ];
    map.forEach(([comp, obj, qKey])=>{
      if(!obj) return;
      // Inject into options list if not already there
      const listHas = _bbMats[comp].find(m=>m.code===obj.code);
      if(!listHas) _bbMats[comp].unshift({code:obj.code, name:obj.name});
      bbRenderOptions(comp, _bbMats[comp]);
      // Select it
      const sel = document.getElementById('bb-select-'+comp);
      if(sel) sel.value = obj.code;
      bbPick(comp, obj.code);
      // Set qty
      const qi = document.getElementById('bb-qty-'+comp);
      if(qi) qi.value = obj[qKey]||'';
    });
    // Packing
    if(bom.packing){
      const listHas = _bbMats['pack'].find(m=>m.code===bom.packing.code);
      if(!listHas) _bbMats['pack'].unshift({code:bom.packing.code, name:bom.packing.name, customer:bom.packing.customer});
      bbRenderOptions('pack', _bbMats['pack']);
      const sel = document.getElementById('bb-select-pack');
      if(sel) sel.value = bom.packing.code;
      bbPick('pack', bom.packing.code);
    }
    toast('Loaded BOM for '+code);
  }catch(e){ toast('Could not load BOM: '+e.message,'warning'); }
}

function resetBomBuilder(){
  ['bb-code','bb-name','bb-thick','bb-width','bb-length','bb-pallet-qty','bb-load-q'].forEach(id=>{
    const el=document.getElementById(id); if(el) el.value='';
  });
  document.getElementById('bb-load-drop').classList.add('d-none');
  _bbPicked={};
  ['base','faceV','backV','faceG','backG','pack'].forEach(c=>{
    document.getElementById('bb-sel-'+c).classList.add('d-none');
    document.getElementById('bb-clear-'+c).classList.add('d-none');
    document.getElementById('bb-search-'+c).value='';
    const qi=document.getElementById('bb-qty-'+c); if(qi) qi.value='';
    bbRenderOptions(c, _bbMats[c]);
  });
}

async function saveBomBuilder(){
  const code = document.getElementById('bb-code').value.trim().toUpperCase();
  const name = document.getElementById('bb-name').value.trim();
  const pq   = parseInt(document.getElementById('bb-pallet-qty').value)||0;
  if(!code){ toast('SKU Code is required','danger'); return; }
  if(!name){ toast('Name is required','danger'); return; }
  if(!pq)  { toast('Pcs/Pallet is required','danger'); return; }

  const g = k => document.getElementById(k)?.value||null;
  const gn= k => parseFloat(document.getElementById(k)?.value)||null;

  const body = {
    sku_code: code, sku_name: name,
    thickness_mm: gn('bb-thick'), width_mm: gn('bb-width'), length_mm: gn('bb-length'),
    pallet_qty: pq,
    base_board_code:  _bbPicked.base  ? _bbPicked.base.code  : null,
    base_board_qty:   gn('bb-qty-base'),
    face_veneer_code: _bbPicked.faceV ? _bbPicked.faceV.code : null,
    face_veneer_qty:  gn('bb-qty-faceV'),
    back_veneer_code: _bbPicked.backV ? _bbPicked.backV.code : null,
    back_veneer_qty:  gn('bb-qty-backV'),
    face_glue_code:   _bbPicked.faceG ? _bbPicked.faceG.code : null,
    face_glue_usage_g:gn('bb-qty-faceG'),
    back_glue_code:   _bbPicked.backG ? _bbPicked.backG.code : null,
    back_glue_usage_g:gn('bb-qty-backG'),
    packing_sku_code: _bbPicked.pack  ? _bbPicked.pack.code  : null,
  };

  try{
    await api('/api/bom-builder','POST',body);
    toast('BOM saved for '+code);
    _bbAllFg = await api('/api/fg').catch(()=>_bbAllFg);
  }catch(e){ toast('Save failed: '+e.message,'danger'); }
}
"""

# Insert JS before </script>
last_script = html.rfind('</script>')
if last_script == -1:
    print("ERROR: </script> not found")
else:
    html = html[:last_script] + BOM_BUILDER_JS + '\n' + html[last_script:]
    print('JS injected at', last_script)

# Insert page HTML
if '<!-- BOM BUILDER -->' in html:
    print('page already exists, skipping HTML inject')
else:
    html = html.replace('<!-- ── BOM AI ── -->', BOM_BUILDER_PAGE + '<!-- ── BOM AI ── -->')
    print('page injected:', '<!-- BOM BUILDER -->' in html)

# Route handler
if "loadBomBuilder()" not in html:
    html = html.replace(
        "else if(p==='bom') loadBom();",
        "else if(p==='bom') loadBom();\n  else if(p==='bom-builder') loadBomBuilder();"
    )
    print('route added')
else:
    print('route already present')

with open('index.html','w',encoding='utf-8') as f:
    f.write(html)
print('done')
