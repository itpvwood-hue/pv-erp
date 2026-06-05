"""Replace old BOM + BOM-Builder pages with unified tabbed BOM page, add new JS."""
import re

with open('index.html', 'r', encoding='utf-8') as f:
    html = f.read()

# ── 1. New unified BOM page HTML ──────────────────────────────────────────────
NEW_BOM_PAGE = r"""<div class="page" id="page-bom">
  <!-- Header -->
  <div class="d-flex justify-content-between align-items-center mb-2">
    <div>
      <h4 class="mb-0">Bill of Materials</h4>
      <small class="text-muted">FG boards · Glue formulas · Bleaching · Packing specs</small>
    </div>
    <button class="btn btn-outline-secondary btn-sm" data-bs-toggle="collapse" data-bs-target="#dt-collapse-bom"><i class="bi bi-tools me-1"></i>Data Tools</button>
  </div>

  <!-- Data Tools panel (import/export) -->
  <div class="collapse mb-3" id="dt-collapse-bom">
    <div class="card p-3">
      <div class="row g-2 align-items-start">
        <div class="col-auto">
          <p class="text-muted small mb-2 fw-semibold">Export</p>
          <a href="/api/export/bom" download class="btn btn-sm btn-outline-secondary"><i class="bi bi-download me-1"></i>Export CSV</a>
        </div>
        <div class="col-auto">
          <p class="text-muted small mb-2 fw-semibold">Template</p>
          <a href="/api/upload/template/bom" download class="btn btn-sm btn-outline-secondary"><i class="bi bi-file-earmark-text me-1"></i>Download Template</a>
        </div>
        <div class="col">
          <p class="text-muted small mb-2 fw-semibold">Bulk Upload</p>
          <div class="d-flex align-items-center gap-3 mb-2">
            <div class="form-check form-check-inline mb-0">
              <input class="form-check-input" type="radio" name="dt-mode-bom" id="dt-add-bom" value="add" checked>
              <label class="form-check-label small" for="dt-add-bom"><strong>Add / Update</strong> <span class="text-muted">(upsert)</span></label>
            </div>
            <div class="form-check form-check-inline mb-0">
              <input class="form-check-input" type="radio" name="dt-mode-bom" id="dt-rep-bom" value="replace">
              <label class="form-check-label small" for="dt-rep-bom"><strong>Replace</strong> <span class="text-muted">(wipe &amp; re-import)</span></label>
            </div>
          </div>
          <div class="upload-zone" style="padding:12px 16px"
            onclick="document.getElementById('dt-file-bom').click()"
            ondragover="event.preventDefault();this.classList.add('drag-over')"
            ondragleave="this.classList.remove('drag-over')"
            ondrop="this.classList.remove('drag-over');dtUploadDrop('bom',event)">
            <i class="bi bi-cloud-upload me-2 text-muted"></i>
            <span class="text-muted small">Click or drag .csv here</span>
          </div>
          <input type="file" id="dt-file-bom" accept=".csv" class="d-none" onchange="dtUpload('bom',this)">
          <div id="dt-result-bom" class="mt-2"></div>
        </div>
      </div>
    </div>
  </div>

  <!-- Main tabs -->
  <ul class="nav nav-tabs mb-0" id="bom-main-tabs" role="tablist">
    <li class="nav-item">
      <button class="nav-link active" data-bs-toggle="tab" data-bs-target="#bom-tab-fg" type="button" role="tab">
        <i class="bi bi-grid me-1"></i>FG BOM
      </button>
    </li>
    <li class="nav-item">
      <button class="nav-link" data-bs-toggle="tab" data-bs-target="#bom-tab-glue" type="button" role="tab" onclick="loadCompoundTab('glue')">
        <i class="bi bi-moisture me-1"></i>Glue Formulas
      </button>
    </li>
    <li class="nav-item">
      <button class="nav-link" data-bs-toggle="tab" data-bs-target="#bom-tab-bleach" type="button" role="tab" onclick="loadCompoundTab('bleaching')">
        <i class="bi bi-droplet me-1"></i>Bleaching
      </button>
    </li>
    <li class="nav-item">
      <button class="nav-link" data-bs-toggle="tab" data-bs-target="#bom-tab-pack" type="button" role="tab" onclick="loadPackingTab()">
        <i class="bi bi-box me-1"></i>Packing Specs
      </button>
    </li>
  </ul>

  <div class="tab-content border border-top-0 rounded-bottom mb-3" id="bom-tab-content">

    <!-- ── TAB: FG BOM ─────────────────────────────────────────── -->
    <div class="tab-pane fade show active p-3" id="bom-tab-fg" role="tabpanel">

      <div class="d-flex gap-2 align-items-center mb-3">
        <input class="form-control form-control-sm" id="bom-search" placeholder="Search SKU or name..." oninput="searchBom(this.value)" style="width:220px">
        <span class="text-muted small" id="bom-count"></span>
        <div class="ms-auto">
          <button class="btn btn-primary btn-sm" onclick="openBomBuilder()"><i class="bi bi-plus-lg me-1"></i>New / Edit BOM</button>
        </div>
      </div>

      <!-- Inline BOM Builder (collapsible) -->
      <div class="collapse mb-3" id="bom-builder-panel">
        <div class="card p-3 border-primary">
          <div class="d-flex justify-content-between align-items-center mb-3">
            <h6 class="mb-0 fw-bold text-primary"><i class="bi bi-pencil-square me-1"></i>BOM Builder</h6>
            <div class="d-flex gap-2">
              <button class="btn btn-sm btn-outline-secondary" onclick="resetBomBuilder()">Clear</button>
              <button class="btn btn-sm btn-success" onclick="saveBomBuilder()"><i class="bi bi-floppy me-1"></i>Save BOM</button>
              <button class="btn btn-sm btn-outline-secondary" data-bs-toggle="collapse" data-bs-target="#bom-builder-panel"><i class="bi bi-x"></i></button>
            </div>
          </div>

          <!-- Load existing FG -->
          <div class="mb-3" style="position:relative">
            <label class="form-label small fw-semibold">Load existing FG to edit</label>
            <input class="form-control form-control-sm" id="bb-load-q" placeholder="Type SKU code or name to search..." oninput="bbLoadSearch(this.value)" autocomplete="off">
            <div id="bb-load-drop" class="d-none" style="position:absolute;top:100%;left:0;right:0;z-index:300;background:#fff;border:1px solid #dee2e6;border-radius:0 0 6px 6px;max-height:200px;overflow-y:auto;box-shadow:0 4px 12px rgba(0,0,0,.1)"></div>
          </div>

          <!-- SKU Details -->
          <div class="row g-2 mb-3">
            <div class="col-md-2">
              <label class="form-label small fw-semibold">SKU Code *</label>
              <input class="form-control form-control-sm" id="bb-code" placeholder="e.g. 4ALM52A11" oninput="this.value=this.value.toUpperCase()">
            </div>
            <div class="col-md-4">
              <label class="form-label small fw-semibold">Name / Description *</label>
              <input class="form-control form-control-sm" id="bb-name" placeholder="e.g. MDF 5.2 Alder PC A BM">
            </div>
            <div class="col-md-1">
              <label class="form-label small fw-semibold">Thick (mm)</label>
              <input type="number" class="form-control form-control-sm" id="bb-thick" step="0.1">
            </div>
            <div class="col-md-1">
              <label class="form-label small fw-semibold">Width (mm)</label>
              <input type="number" class="form-control form-control-sm" id="bb-width">
            </div>
            <div class="col-md-1">
              <label class="form-label small fw-semibold">Length (mm)</label>
              <input type="number" class="form-control form-control-sm" id="bb-length">
            </div>
            <div class="col-md-2">
              <label class="form-label small fw-semibold">Pcs / Pallet *</label>
              <input type="number" class="form-control form-control-sm" id="bb-pallet-qty" min="1" placeholder="135" oninput="bbSyncQtyDefaults()">
            </div>
          </div>

          <!-- Component pickers -->
          <div class="row g-2">
            <div class="col-md-4">
              <div class="card h-100 p-2 bg-light">
                <div class="d-flex justify-content-between align-items-center mb-1">
                  <span class="small fw-bold"><span class="badge bg-secondary me-1">1</span>Base Board</span>
                  <button class="btn btn-sm btn-outline-danger py-0 px-1 d-none" id="bb-clear-base" onclick="bbClearComp('base')">×</button>
                </div>
                <input class="form-control form-control-sm mb-1" id="bb-search-base" placeholder="Search core boards..." oninput="bbFilter('base',this.value)">
                <select class="form-select form-select-sm" id="bb-select-base" size="4" onchange="bbPick('base',this.value)"></select>
                <div id="bb-sel-base" class="mt-1 d-none">
                  <div class="alert alert-secondary py-1 px-2 mb-1 small fw-bold" id="bb-badge-base"></div>
                  <label class="form-label small mb-0">Qty (sheets/pallet)</label>
                  <input type="number" class="form-control form-control-sm" id="bb-qty-base" min="1">
                </div>
              </div>
            </div>
            <div class="col-md-4">
              <div class="card h-100 p-2 bg-light">
                <div class="d-flex justify-content-between align-items-center mb-1">
                  <span class="small fw-bold"><span class="badge bg-primary me-1">2</span>Face Veneer</span>
                  <button class="btn btn-sm btn-outline-danger py-0 px-1 d-none" id="bb-clear-faceV" onclick="bbClearComp('faceV')">×</button>
                </div>
                <input class="form-control form-control-sm mb-1" id="bb-search-faceV" placeholder="Search veneers..." oninput="bbFilter('faceV',this.value)">
                <select class="form-select form-select-sm" id="bb-select-faceV" size="4" onchange="bbPick('faceV',this.value)"></select>
                <div id="bb-sel-faceV" class="mt-1 d-none">
                  <div class="alert alert-primary py-1 px-2 mb-1 small fw-bold" id="bb-badge-faceV"></div>
                  <label class="form-label small mb-0">Qty (sheets/pallet)</label>
                  <input type="number" class="form-control form-control-sm" id="bb-qty-faceV" min="1">
                </div>
              </div>
            </div>
            <div class="col-md-4">
              <div class="card h-100 p-2 bg-light">
                <div class="d-flex justify-content-between align-items-center mb-1">
                  <span class="small fw-bold"><span class="badge bg-info text-dark me-1">3</span>Back Veneer</span>
                  <button class="btn btn-sm btn-outline-danger py-0 px-1 d-none" id="bb-clear-backV" onclick="bbClearComp('backV')">×</button>
                </div>
                <input class="form-control form-control-sm mb-1" id="bb-search-backV" placeholder="Search veneers..." oninput="bbFilter('backV',this.value)">
                <select class="form-select form-select-sm" id="bb-select-backV" size="4" onchange="bbPick('backV',this.value)"></select>
                <div id="bb-sel-backV" class="mt-1 d-none">
                  <div class="alert alert-info py-1 px-2 mb-1 small fw-bold" id="bb-badge-backV"></div>
                  <label class="form-label small mb-0">Qty (sheets/pallet)</label>
                  <input type="number" class="form-control form-control-sm" id="bb-qty-backV" min="1">
                </div>
              </div>
            </div>
            <div class="col-md-4">
              <div class="card h-100 p-2 bg-light">
                <div class="d-flex justify-content-between align-items-center mb-1">
                  <span class="small fw-bold"><span class="badge bg-warning text-dark me-1">4</span>Face Glue</span>
                  <button class="btn btn-sm btn-outline-danger py-0 px-1 d-none" id="bb-clear-faceG" onclick="bbClearComp('faceG')">×</button>
                </div>
                <input class="form-control form-control-sm mb-1" id="bb-search-faceG" placeholder="Search glue formulas..." oninput="bbFilter('faceG',this.value)">
                <select class="form-select form-select-sm" id="bb-select-faceG" size="4" onchange="bbPick('faceG',this.value)"></select>
                <div id="bb-sel-faceG" class="mt-1 d-none">
                  <div class="alert alert-warning py-1 px-2 mb-1 small fw-bold" id="bb-badge-faceG"></div>
                  <label class="form-label small mb-0">Usage (g/face press)</label>
                  <input type="number" class="form-control form-control-sm" id="bb-qty-faceG" min="1" step="0.5">
                </div>
              </div>
            </div>
            <div class="col-md-4">
              <div class="card h-100 p-2 bg-light">
                <div class="d-flex justify-content-between align-items-center mb-1">
                  <span class="small fw-bold"><span class="badge bg-warning text-dark me-1">5</span>Back Glue</span>
                  <button class="btn btn-sm btn-outline-danger py-0 px-1 d-none" id="bb-clear-backG" onclick="bbClearComp('backG')">×</button>
                </div>
                <input class="form-control form-control-sm mb-1" id="bb-search-backG" placeholder="Search glue formulas..." oninput="bbFilter('backG',this.value)">
                <select class="form-select form-select-sm" id="bb-select-backG" size="4" onchange="bbPick('backG',this.value)"></select>
                <div id="bb-sel-backG" class="mt-1 d-none">
                  <div class="alert alert-warning py-1 px-2 mb-1 small fw-bold" id="bb-badge-backG"></div>
                  <label class="form-label small mb-0">Usage (g/face press)</label>
                  <input type="number" class="form-control form-control-sm" id="bb-qty-backG" min="1" step="0.5">
                </div>
              </div>
            </div>
            <div class="col-md-4">
              <div class="card h-100 p-2 bg-light">
                <div class="d-flex justify-content-between align-items-center mb-1">
                  <span class="small fw-bold"><span class="badge bg-success me-1">6</span>Packing Spec</span>
                  <button class="btn btn-sm btn-outline-danger py-0 px-1 d-none" id="bb-clear-pack" onclick="bbClearComp('pack')">×</button>
                </div>
                <input class="form-control form-control-sm mb-1" id="bb-search-pack" placeholder="Search packing specs..." oninput="bbFilter('pack',this.value)">
                <select class="form-select form-select-sm" id="bb-select-pack" size="4" onchange="bbPick('pack',this.value)"></select>
                <div id="bb-sel-pack" class="mt-1 d-none">
                  <div class="alert alert-success py-1 px-2 small fw-bold" id="bb-badge-pack"></div>
                </div>
              </div>
            </div>
          </div><!-- /row -->
        </div>
      </div><!-- /builder panel -->

      <div id="bom-list"></div>
    </div><!-- /FG BOM tab -->

    <!-- ── TAB: GLUE FORMULAS ─────────────────────────────────────── -->
    <div class="tab-pane fade p-3" id="bom-tab-glue" role="tabpanel">
      <div class="d-flex gap-2 align-items-center mb-3">
        <input class="form-control form-control-sm" id="glue-search" placeholder="Search glue formulas..." oninput="filterCompound('glue',this.value)" style="width:220px">
        <span class="text-muted small" id="glue-count"></span>
        <button class="btn btn-warning btn-sm ms-auto" data-bs-toggle="collapse" data-bs-target="#glue-builder-panel" onclick="resetCompoundBuilder('glue')">
          <i class="bi bi-plus-lg me-1"></i>New Formula
        </button>
      </div>
      <div class="collapse mb-3" id="glue-builder-panel">
        <div class="card p-3 border-warning">
          <h6 class="fw-bold text-warning-emphasis mb-3"><i class="bi bi-beaker me-1"></i>New Glue Formula</h6>
          <div class="row g-2">
            <div class="col-md-2"><label class="form-label small">Code *</label><input class="form-control form-control-sm" id="glue-new-code" placeholder="e.g. Glue-16" oninput="this.value=this.value.toUpperCase()"></div>
            <div class="col-md-4"><label class="form-label small">Name</label><input class="form-control form-control-sm" id="glue-new-name" placeholder="Face glue formula"></div>
            <div class="col-md-2"><label class="form-label small">Batch size (kg)</label><input type="number" class="form-control form-control-sm" id="glue-new-batch" step="0.01" placeholder="72.6"></div>
            <div class="col-md-4"><label class="form-label small">Notes</label><input class="form-control form-control-sm" id="glue-new-notes"></div>
          </div>
          <div class="mt-2 d-flex justify-content-end">
            <button class="btn btn-warning btn-sm" onclick="saveNewCompound('glue')"><i class="bi bi-floppy me-1"></i>Create Formula</button>
          </div>
        </div>
      </div>
      <div id="glue-list"></div>
    </div>

    <!-- ── TAB: BLEACHING ─────────────────────────────────────────── -->
    <div class="tab-pane fade p-3" id="bom-tab-bleach" role="tabpanel">
      <div class="d-flex gap-2 align-items-center mb-3">
        <input class="form-control form-control-sm" id="bleach-search" placeholder="Search bleaching formulas..." oninput="filterCompound('bleaching',this.value)" style="width:220px">
        <span class="text-muted small" id="bleach-count"></span>
        <button class="btn btn-info btn-sm ms-auto" data-bs-toggle="collapse" data-bs-target="#bleach-builder-panel" onclick="resetCompoundBuilder('bleaching')">
          <i class="bi bi-plus-lg me-1"></i>New Formula
        </button>
      </div>
      <div class="collapse mb-3" id="bleach-builder-panel">
        <div class="card p-3 border-info">
          <h6 class="fw-bold text-info-emphasis mb-3"><i class="bi bi-droplet-half me-1"></i>New Bleaching Formula</h6>
          <div class="row g-2">
            <div class="col-md-2"><label class="form-label small">Code *</label><input class="form-control form-control-sm" id="bleach-new-code" placeholder="e.g. BLC-01" oninput="this.value=this.value.toUpperCase()"></div>
            <div class="col-md-4"><label class="form-label small">Name</label><input class="form-control form-control-sm" id="bleach-new-name" placeholder="Bleaching solution"></div>
            <div class="col-md-2"><label class="form-label small">Batch size (kg)</label><input type="number" class="form-control form-control-sm" id="bleach-new-batch" step="0.01"></div>
            <div class="col-md-4"><label class="form-label small">Notes</label><input class="form-control form-control-sm" id="bleach-new-notes"></div>
          </div>
          <div class="mt-2 d-flex justify-content-end">
            <button class="btn btn-info btn-sm" onclick="saveNewCompound('bleaching')"><i class="bi bi-floppy me-1"></i>Create Formula</button>
          </div>
        </div>
      </div>
      <div id="bleach-list"></div>
    </div>

    <!-- ── TAB: PACKING SPECS ─────────────────────────────────────── -->
    <div class="tab-pane fade p-3" id="bom-tab-pack" role="tabpanel">
      <div class="d-flex gap-2 align-items-center mb-3">
        <input class="form-control form-control-sm" id="pack-search" placeholder="Search packing specs..." oninput="filterPacking(this.value)" style="width:220px">
        <span class="text-muted small" id="pack-count"></span>
        <button class="btn btn-success btn-sm ms-auto" data-bs-toggle="collapse" data-bs-target="#pack-builder-panel" onclick="resetPackingBuilder()">
          <i class="bi bi-plus-lg me-1"></i>New Packing Spec
        </button>
      </div>
      <div class="collapse mb-3" id="pack-builder-panel">
        <div class="card p-3 border-success">
          <h6 class="fw-bold text-success mb-3"><i class="bi bi-box-seam me-1"></i>New Packing Spec</h6>
          <div class="row g-2">
            <div class="col-md-3"><label class="form-label small">Code *</label><input class="form-control form-control-sm" id="pack-new-code" placeholder="e.g. PKG-1232x2452-CUST" oninput="this.value=this.value.toUpperCase()"></div>
            <div class="col-md-4"><label class="form-label small">Name</label><input class="form-control form-control-sm" id="pack-new-name" placeholder="Packing 1232×2452 mm"></div>
            <div class="col-md-3"><label class="form-label small">Customer</label><input class="form-control form-control-sm" id="pack-new-customer" placeholder="DARGONPLY"></div>
            <div class="col-md-2"><label class="form-label small">Notes</label><input class="form-control form-control-sm" id="pack-new-notes"></div>
          </div>
          <div class="mt-2 d-flex justify-content-end">
            <button class="btn btn-success btn-sm" onclick="saveNewPacking()"><i class="bi bi-floppy me-1"></i>Create Packing Spec</button>
          </div>
        </div>
      </div>
      <div id="pack-list"></div>
    </div>

  </div><!-- /tab-content -->
</div>

"""

# ── 2. Replace old BOM + BOM-Builder block ────────────────────────────────────
OLD_BOM_START = '<div class="page" id="page-bom">'
OLD_AFTER_BUILDER = '<!-- ── BOM AI ── -->'

si = html.index(OLD_BOM_START)
ei = html.index(OLD_AFTER_BUILDER)
html = html[:si] + NEW_BOM_PAGE + html[ei:]
print('BOM page replaced')

# ── 3. Fix route handler: remove bom-builder route ───────────────────────────
html = re.sub(r"\s*else if\(p==='bom-builder'\)[^\n]*\n", "\n", html)
print('bom-builder route removed:', 'bom-builder' not in html or 'data-page' not in html)

# ── 4. Remove old BOM-Builder JS block and insert new JS ────────────────────
OLD_BB_JS_START = "// ════════════════════════════════════════════════════════════\n// BOM BUILDER"
OLD_BB_JS_END   = "// ════════════════════════════════════════════════════════════\n// DATA TOOLS"

si2 = html.index(OLD_BB_JS_START)
ei2 = html.index(OLD_BB_JS_END)
old_bb_js = html[si2:ei2]
print('Old BOM Builder JS lines:', old_bb_js.count('\n'))

NEW_JS = r"""
// ════════════════════════════════════════════════════════════
// BOM BUILDER (embedded in FG BOM tab)
// ════════════════════════════════════════════════════════════
let _bbMats = {};
let _bbPicked = {};
let _bbAllFg = [];
let _bbLoaded = false;

function openBomBuilder(){
  const panel = document.getElementById('bom-builder-panel');
  const col = bootstrap.Collapse.getOrCreateInstance(panel);
  col.show();
  if(!_bbLoaded) loadBomBuilder();
}

async function loadBomBuilder(){
  _bbLoaded = true;
  const [mats, glues, packing] = await Promise.all([
    api('/api/materials').catch(()=>[]),
    api('/api/materials?include_formulas=true').catch(()=>[]),
    api('/api/packing-skus').catch(()=>[]),
  ]);
  _bbMats = {
    base:  mats.filter(m=>m.type==='core_board'),
    faceV: mats.filter(m=>m.type==='veneer_sheet'),
    backV: mats.filter(m=>m.type==='veneer_sheet'),
    faceG: glues.filter(m=>m.type==='glue_formula'),
    backG: glues.filter(m=>m.type==='glue_formula'),
    pack:  packing,
  };
  _bbAllFg = await api('/api/fg').catch(()=>[]);
  ['base','faceV','backV','faceG','backG','pack'].forEach(c => bbRenderOptions(c, _bbMats[c]));
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
    qi.value = (comp==='faceG'||comp==='backG') ? 45 : (pq||'');
  }
}

function bbClearComp(comp){
  delete _bbPicked[comp];
  document.getElementById('bb-sel-'+comp).classList.add('d-none');
  document.getElementById('bb-clear-'+comp).classList.add('d-none');
  document.getElementById('bb-search-'+comp).value='';
  const qi = document.getElementById('bb-qty-'+comp);
  if(qi) qi.value='';
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
    });
    if(bom.packing){
      if(!_bbMats['pack'].find(m=>m.code===bom.packing.code))
        _bbMats['pack'].unshift({code:bom.packing.code, name:bom.packing.name, customer:bom.packing.customer});
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
    document.getElementById('bb-sel-'+c)?.classList.add('d-none');
    document.getElementById('bb-clear-'+c)?.classList.add('d-none');
    const s=document.getElementById('bb-search-'+c); if(s) s.value='';
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
  const gn = k => parseFloat(document.getElementById(k)?.value)||null;
  const body = {
    sku_code: code, sku_name: name,
    thickness_mm: gn('bb-thick'), width_mm: gn('bb-width'), length_mm: gn('bb-length'),
    pallet_qty: pq,
    base_board_code:   _bbPicked.base  ? _bbPicked.base.code  : null, base_board_qty:   gn('bb-qty-base'),
    face_veneer_code:  _bbPicked.faceV ? _bbPicked.faceV.code : null, face_veneer_qty:  gn('bb-qty-faceV'),
    back_veneer_code:  _bbPicked.backV ? _bbPicked.backV.code : null, back_veneer_qty:  gn('bb-qty-backV'),
    face_glue_code:    _bbPicked.faceG ? _bbPicked.faceG.code : null, face_glue_usage_g:gn('bb-qty-faceG'),
    back_glue_code:    _bbPicked.backG ? _bbPicked.backG.code : null, back_glue_usage_g:gn('bb-qty-backG'),
    packing_sku_code:  _bbPicked.pack  ? _bbPicked.pack.code  : null,
  };
  try{
    await api('/api/bom-builder','POST',body);
    toast('BOM saved for '+code);
    _bbAllFg = await api('/api/fg').catch(()=>_bbAllFg);
    loadBom();
  }catch(e){ toast('Save failed: '+e.message,'danger'); }
}

// BOM LIST — add Edit button to each card
function renderBom(rows){
  document.getElementById('bom-count').textContent=`${rows.length} SKU${rows.length!==1?'s':''}`;
  document.getElementById('bom-list').innerHTML=rows.map(r=>`
    <div class="card mb-2">
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
          </div>
        </div>
        <div class="row g-2">
          <div class="col-auto"><small class="text-muted fw-semibold d-block mb-1">BASE BOARD</small>${matPill(r.base_board,'')}</div>
          <div class="col-auto"><small class="text-muted fw-semibold d-block mb-1">FACE VENEER</small>${matPill(r.face_veneer,'face')}</div>
          <div class="col-auto"><small class="text-muted fw-semibold d-block mb-1">BACK VENEER</small>${matPill(r.back_veneer,'back')}</div>
          <div class="col-auto"><small class="text-muted fw-semibold d-block mb-1">FACE GLUE</small>${gluePill(r.face_glue)}</div>
          <div class="col-auto"><small class="text-muted fw-semibold d-block mb-1">BACK GLUE</small>${gluePill(r.back_glue)}</div>
          <div class="col-auto"><small class="text-muted fw-semibold d-block mb-1">PACKING</small>${packPill(r.packing)}</div>
        </div>
      </div>
    </div>`).join('');
}

async function editBomCard(skuCode){
  openBomBuilder();
  await new Promise(r=>setTimeout(r,150));
  await bbLoadFg(skuCode);
}

// ════════════════════════════════════════════════════════════
// COMPOUND FORMULA MANAGEMENT (Glue + Bleaching)
// ════════════════════════════════════════════════════════════
let _compoundData = { glue: [], bleaching: [] };
let _compoundLoaded = { glue: false, bleaching: false };

async function loadCompoundTab(type){
  if(!_compoundLoaded[type]){ await refreshCompound(type); }
}

async function refreshCompound(type){
  _compoundLoaded[type] = true;
  const data = await api('/api/compound-skus?type='+type).catch(()=>[]);
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
    await api('/api/compound-skus','POST',{code,name,batch_kg:batch,type,notes});
    toast('Formula created: '+code);
    const panelId = type==='glue' ? 'glue-builder-panel' : 'bleach-builder-panel';
    bootstrap.Collapse.getInstance(document.getElementById(panelId))?.hide();
    await refreshCompound(type);
  }catch(e){ toast(e.message,'danger'); }
}

async function deleteCompound(id, type){
  if(!confirm('Delete this formula and all its ingredients?')) return;
  try{
    await api('/api/compound-skus/'+id,'DELETE');
    toast('Deleted');
    await refreshCompound(type);
  }catch(e){ toast(e.message,'danger'); }
}

async function addCompoundLine(compoundId, type){
  const code  = document.getElementById('cl-mat-'+compoundId).value.trim();
  const ratio = parseFloat(document.getElementById('cl-ratio-'+compoundId).value)||null;
  const unit  = document.getElementById('cl-unit-'+compoundId).value.trim()||'kg';
  if(!code){ toast('Material code required','danger'); return; }
  try{
    await api('/api/compound-skus/'+compoundId+'/lines','POST',{material_code:code,ratio,unit});
    toast('Ingredient added');
    await refreshCompound(type);
    setTimeout(()=>{ const el=document.getElementById('cl-'+compoundId); if(el&&!el.classList.contains('show')) new bootstrap.Collapse(el).show(); },150);
  }catch(e){ toast(e.message,'danger'); }
}

async function deleteCompoundLine(lineId, compoundId, type){
  try{
    await api('/api/compound-lines/'+lineId,'DELETE');
    await refreshCompound(type);
    setTimeout(()=>{ const el=document.getElementById('cl-'+compoundId); if(el&&!el.classList.contains('show')) new bootstrap.Collapse(el).show(); },150);
  }catch(e){ toast(e.message,'danger'); }
}

// ════════════════════════════════════════════════════════════
// PACKING SPEC MANAGEMENT
// ════════════════════════════════════════════════════════════
let _packingData = [];
let _packingLoaded = false;

async function loadPackingTab(){
  if(!_packingLoaded){ await refreshPacking(); }
}

async function refreshPacking(){
  _packingLoaded = true;
  const data = await api('/api/packing-skus-full').catch(()=>[]);
  _packingData = data;
  renderPacking(data);
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
                <td><input class="form-control form-control-sm" id="pl-mat-${p.id}" placeholder="Material code" style="min-width:120px"></td>
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
  if(!code){ toast('Material code required','danger'); return; }
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

"""

html = html[:si2] + NEW_JS + html[ei2:]
print('JS replaced')

# ── 5. Fix loadBom to not call renderBom (renderBom is now defined in new JS) ─
# Remove the old renderBom function (it's now in the new JS block above)
OLD_RENDER_BOM = """function renderBom(rows){
  document.getElementById('bom-count').textContent=`${rows.length} SKU${rows.length!==1?'s':''}`;
  document.getElementById('bom-list').innerHTML=rows.map(r=>`"""
if OLD_RENDER_BOM in html:
    # Find and remove old renderBom through the end of its closing bracket
    ri = html.index(OLD_RENDER_BOM)
    # Find the ending: `).join('');` + newline + `}`
    re_end = html.index("}).join('');", ri) + len("}).join('');")
    # skip to end of function
    while html[re_end] != '\n': re_end += 1
    re_end += 1  # past newline
    if html[re_end] == '}': re_end += 1
    html = html[:ri] + html[re_end:]
    print('old renderBom removed')
else:
    print('old renderBom not found separately (may already be in the replaced block)')

with open('index.html', 'w', encoding='utf-8') as f:
    f.write(html)
print('index.html saved')
print()
print('Checks:')
print('  page-bom-builder gone:', 'id="page-bom-builder"' not in html)
print('  bom-builder nav gone:', 'data-page="bom-builder"' not in html)
print('  bom-tab-glue:', 'bom-tab-glue' in html)
print('  bom-tab-bleach:', 'bom-tab-bleach' in html)
print('  bom-tab-pack:', 'bom-tab-pack' in html)
print('  bom-builder-panel:', 'bom-builder-panel' in html)
print('  renderCompound:', 'renderCompound' in html)
print('  renderPacking:', 'renderPacking' in html)
print('  editBomCard:', 'editBomCard' in html)
print('  loadCompoundTab:', 'loadCompoundTab' in html)
