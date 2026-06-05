"""Patch frontend: move bulk upload into Materials + BOM pages, remove standalone page."""

with open('index.html', 'r', encoding='utf-8') as f:
    html = f.read()

# ── 1. Remove Bulk Upload nav link ───────────────────────────────────────────
html = html.replace(
    '\n  <div class="nav-sec">Utilities</div>\n  <a class="nav-link" data-page="bulk-upload" href="#"><i class="bi bi-upload"></i>Bulk Upload</a>',
    '\n  <div class="nav-sec">Utilities</div>'
)
print("nav removed:", 'bulk-upload' not in html)

# ── 2. Remove standalone bulk-upload page ────────────────────────────────────
import re
html = re.sub(
    r'<!-- ── BULK UPLOAD ── -->.*?</div>\s*\n(?=<!-- ──)',
    '',
    html, flags=re.DOTALL
)
print("page removed:", 'page-bulk-upload' not in html)

# ── 3. DATA TOOLS PANEL snippet (reusable) ───────────────────────────────────
def data_tools(section, export_url, template_url, upload_type, result_id):
    return f"""
  <!-- Data Tools: {section} -->
  <div class="collapse mb-3" id="dt-collapse-{upload_type}">
    <div class="card p-3">
      <div class="row g-2 align-items-start">
        <div class="col-auto">
          <p class="text-muted small mb-2 fw-semibold">Export</p>
          <a href="{export_url}" download class="btn btn-sm btn-outline-secondary"><i class="bi bi-download me-1"></i>Export CSV</a>
        </div>
        <div class="col-auto">
          <p class="text-muted small mb-2 fw-semibold">Template</p>
          <a href="{template_url}" download class="btn btn-sm btn-outline-secondary"><i class="bi bi-file-earmark-text me-1"></i>Download Template</a>
        </div>
        <div class="col">
          <p class="text-muted small mb-2 fw-semibold">Bulk Upload</p>
          <div class="d-flex align-items-center gap-3 mb-2">
            <div class="form-check form-check-inline mb-0">
              <input class="form-check-input" type="radio" name="dt-mode-{upload_type}" id="dt-add-{upload_type}" value="add" checked>
              <label class="form-check-label small" for="dt-add-{upload_type}"><strong>Add / Update</strong> <span class="text-muted">(upsert existing, insert new)</span></label>
            </div>
            <div class="form-check form-check-inline mb-0">
              <input class="form-check-input" type="radio" name="dt-mode-{upload_type}" id="dt-rep-{upload_type}" value="replace">
              <label class="form-check-label small" for="dt-rep-{upload_type}"><strong>Replace</strong> <span class="text-muted">(wipe matching codes, re-import)</span></label>
            </div>
          </div>
          <div class="upload-zone" style="padding:12px 16px"
            onclick="document.getElementById('dt-file-{upload_type}').click()"
            ondragover="event.preventDefault();this.classList.add('drag-over')"
            ondragleave="this.classList.remove('drag-over')"
            ondrop="this.classList.remove('drag-over');dtUploadDrop('{upload_type}',event)">
            <i class="bi bi-cloud-upload me-2 text-muted"></i>
            <span class="text-muted small">Click or drag .csv here</span>
          </div>
          <input type="file" id="dt-file-{upload_type}" accept=".csv" class="d-none" onchange="dtUpload('{upload_type}',this)">
          <div id="{result_id}" class="mt-2"></div>
        </div>
      </div>
    </div>
  </div>"""

MAT_TOOLS = data_tools('Materials', '/api/export/materials', '/api/upload/template/inventory', 'inventory', 'dt-result-inventory')
BOM_TOOLS = data_tools('BOM', '/api/export/bom', '/api/upload/template/bom', 'bom', 'dt-result-bom')

# ── 4. Patch Materials page header ───────────────────────────────────────────
OLD_MAT_HDR = '''<!-- ── MATERIALS ── -->
<div class="page" id="page-materials">
  <!-- RAW MATERIALS section -->
  <div class="d-flex justify-content-between align-items-center mb-2">
    <div>
      <h4 class="mb-0">Raw Materials</h4>
      <small class="text-muted">Core boards · Veneers · Adhesive raw ingredients</small>
    </div>
    <button class="btn btn-primary btn-sm" data-bs-toggle="modal" data-bs-target="#materialModal" onclick="openMaterialModal()">+ Add Material</button>
  </div>'''

NEW_MAT_HDR = '''<!-- ── MATERIALS ── -->
<div class="page" id="page-materials">
  <!-- RAW MATERIALS section -->
  <div class="d-flex justify-content-between align-items-center mb-2">
    <div>
      <h4 class="mb-0">Raw Materials</h4>
      <small class="text-muted">Core boards · Veneers · Adhesive raw ingredients</small>
    </div>
    <div class="d-flex gap-2">
      <button class="btn btn-outline-secondary btn-sm" data-bs-toggle="collapse" data-bs-target="#dt-collapse-inventory"><i class="bi bi-tools me-1"></i>Data Tools</button>
      <button class="btn btn-primary btn-sm" data-bs-toggle="modal" data-bs-target="#materialModal" onclick="openMaterialModal()">+ Add Material</button>
    </div>
  </div>''' + MAT_TOOLS

assert OLD_MAT_HDR in html, "Materials header not found"
html = html.replace(OLD_MAT_HDR, NEW_MAT_HDR, 1)
print("Materials page patched")

# ── 5. Patch BOM page header ─────────────────────────────────────────────────
OLD_BOM_HDR = '''<!-- ── BOM ── -->
<div class="page" id="page-bom">
  <div class="d-flex justify-content-between align-items-center mb-3">
    <div>
      <h4 class="mb-0">Bill of Materials</h4>
      <small class="text-muted">Structured BOM per FG SKU — base board · face veneer · back veneer · glue formula · packing</small>
    </div>
    <div class="d-flex gap-2 align-items-center">
      <input class="form-control form-control-sm" id="bom-search" placeholder="Search SKU or name..." oninput="searchBom(this.value)" style="width:240px">
      <span class="text-muted small" id="bom-count"></span>
    </div>
  </div>
  <div id="bom-list"></div>
</div>'''

NEW_BOM_HDR = '''<!-- ── BOM ── -->
<div class="page" id="page-bom">
  <div class="d-flex justify-content-between align-items-center mb-3">
    <div>
      <h4 class="mb-0">Bill of Materials</h4>
      <small class="text-muted">Structured BOM per FG SKU — base board · face veneer · back veneer · glue formula · packing</small>
    </div>
    <div class="d-flex gap-2 align-items-center">
      <input class="form-control form-control-sm" id="bom-search" placeholder="Search SKU or name..." oninput="searchBom(this.value)" style="width:200px">
      <span class="text-muted small" id="bom-count"></span>
      <button class="btn btn-outline-secondary btn-sm" data-bs-toggle="collapse" data-bs-target="#dt-collapse-bom"><i class="bi bi-tools me-1"></i>Data Tools</button>
    </div>
  </div>''' + BOM_TOOLS + '''
  <div id="bom-list"></div>
</div>'''

assert OLD_BOM_HDR in html, "BOM header not found"
html = html.replace(OLD_BOM_HDR, NEW_BOM_HDR, 1)
print("BOM page patched")

# ── 6. Add JS upload helpers ─────────────────────────────────────────────────
JS = r"""
// ════════════════════════════════════════════════════════════
// DATA TOOLS — Upload with mode (add / replace)
// ════════════════════════════════════════════════════════════
async function dtUpload(type, input){
  const file = input.files[0]; if(!file) return;
  const mode = document.querySelector(`input[name="dt-mode-${type}"]:checked`)?.value || 'add';
  await _dtDoUpload(type, file, mode);
  input.value = '';
}
function dtUploadDrop(type, event){
  const file = event.dataTransfer?.files?.[0];
  const rid = `dt-result-${type}`;
  if(!file || !file.name.endsWith('.csv')){
    document.getElementById(rid).innerHTML = '<div class="alert alert-warning py-2 small">Please drop a .csv file</div>';
    return;
  }
  const mode = document.querySelector(`input[name="dt-mode-${type}"]:checked`)?.value || 'add';
  _dtDoUpload(type, file, mode);
}
async function _dtDoUpload(type, file, mode){
  const rid = `dt-result-${type}`;
  const el = document.getElementById(rid);
  const endpoint = type === 'inventory' ? '/api/upload/inventory' : '/api/upload/bom';
  el.innerHTML = '<div class="d-flex align-items-center gap-2 text-muted small"><div class="spinner-border spinner-border-sm"></div>Uploading '+file.name+'…</div>';
  try{
    const fd = new FormData(); fd.append('file', file);
    const r = await fetch(`${endpoint}?mode=${mode}`, {method:'POST', body:fd});
    const data = await r.json();
    if(!r.ok) throw new Error(data.detail || 'Upload failed');
    const modeLabel = mode === 'replace' ? 'replaced' : 'imported';
    let h = `<div class="alert alert-success py-2 small"><i class="bi bi-check-circle me-1"></i><strong>${data.processed}</strong> rows ${modeLabel} successfully (mode: ${mode})</div>`;
    if(data.errors?.length) h += `<div class="alert alert-warning py-2 small"><strong>${data.errors.length} row(s) skipped:</strong><br>${data.errors.slice(0,6).map(e=>'• '+e).join('<br>')}${data.errors.length>6?`<br>…and ${data.errors.length-6} more`:''}</div>`;
    el.innerHTML = h;
    if(type==='inventory') loadMaterials();
    else if(type==='bom') loadBom();
  }catch(e){
    el.innerHTML = `<div class="alert alert-danger py-2 small"><i class="bi bi-exclamation-triangle me-1"></i>${e.message}</div>`;
  }
}
"""

# Insert before </script>
last_script = html.rfind('</script>')
html = html[:last_script] + JS + '\n' + html[last_script:]
print("JS added")

# ── 7. Remove old route for bulk-upload page ─────────────────────────────────
html = html.replace(
    "\n  else if(p==='bulk-upload') {}",
    ""
)
# Also if there's a generic catch for it
html = re.sub(r"\s*else if\(p===.bulk-upload.\)[^;]*;", "", html)

with open('index.html', 'w', encoding='utf-8') as f:
    f.write(html)
print("index.html saved")
print()
print("Checks:")
print("  bulk-upload nav gone:", 'data-page="bulk-upload"' not in html)
print("  page-bulk-upload gone:", 'id="page-bulk-upload"' not in html)
print("  dt-collapse-inventory:", 'dt-collapse-inventory' in html)
print("  dt-collapse-bom:", 'dt-collapse-bom' in html)
print("  dtUpload JS:", 'dtUpload' in html)
print("  /api/export/materials link:", '/api/export/materials' in html)
print("  /api/export/bom link:", '/api/export/bom' in html)
