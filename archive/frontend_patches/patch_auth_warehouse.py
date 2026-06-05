"""
Patch index.html — Phase 1 (Auth) + Phase 2 (Supply Warehouse)

Changes:
  1.  Login overlay (full-screen, before SPA loads)
  2.  Sidebar: user pill at bottom + new nav sections (role-gated)
  3.  New pages: consumable-requests, warehouse-queue, dept-costs, user-management
  4.  api() updated to send X-Auth-Token header; 401 → auto-logout
  5.  Auth JS: login/logout, role-based nav filter, dept-selector modal
  6.  Consumable request JS + Warehouse queue JS + Dept costs JS + User mgmt JS
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
        print(f'  WARN: not found — {label or old[:60]}')
        return
    src = src.replace(old, new, 1)
    changes += 1
    print(f'  OK  {label or old[:60]}')

# ─────────────────────────────────────────────────────────────────────────────
# 1. LOGIN OVERLAY  (insert right after <body>)
# ─────────────────────────────────────────────────────────────────────────────
LOGIN_OVERLAY = '''
<!-- ═══════════ LOGIN OVERLAY ═══════════ -->
<div id="login-overlay" style="position:fixed;inset:0;z-index:9999;background:linear-gradient(135deg,#0f172a 0%,#1e3a5f 100%);display:flex;align-items:center;justify-content:center;">
  <div style="width:100%;max-width:400px;padding:20px">
    <div class="card shadow-lg border-0">
      <div class="card-body p-4">
        <div class="text-center mb-4">
          <div style="width:56px;height:56px;background:linear-gradient(135deg,#3b82f6,#1d4ed8);border-radius:14px;display:flex;align-items:center;justify-content:center;margin:0 auto 12px">
            <i class="bi bi-layers-fill text-white" style="font-size:1.5rem"></i>
          </div>
          <h4 class="fw-bold mb-0">PV Veneer ERP</h4>
          <small class="text-muted">Factory Management System</small>
        </div>
        <div id="login-error" class="alert alert-danger d-none py-2 small"></div>
        <div class="mb-3">
          <label class="form-label small fw-semibold">Username</label>
          <input type="text" class="form-control" id="login-username" autocomplete="username" placeholder="Enter your username">
        </div>
        <div class="mb-4">
          <label class="form-label small fw-semibold">Password</label>
          <input type="password" class="form-control" id="login-password" autocomplete="current-password" placeholder="Enter your password"
                 onkeydown="if(event.key==='Enter')doLogin()">
        </div>
        <button class="btn btn-primary w-100 fw-semibold" onclick="doLogin()" id="login-btn">
          <i class="bi bi-box-arrow-in-right me-2"></i>Sign In
        </button>
      </div>
    </div>
    <p class="text-center text-white-50 small mt-3">PV Plywood &amp; Veneer Co.</p>
  </div>
</div>

<!-- ═══════════ DEPT SELECTOR (Dept Leader post-login) ═══════════ -->
<div class="modal fade" id="deptSelectorModal" data-bs-backdrop="static" tabindex="-1">
  <div class="modal-dialog modal-lg">
    <div class="modal-content">
      <div class="modal-header">
        <h5 class="modal-title"><i class="bi bi-person-badge me-2"></i>Select Your Departments &amp; Lines</h5>
      </div>
      <div class="modal-body">
        <p class="text-muted small">Choose every department and line you are responsible for. You can update this later from your profile.</p>
        <div id="dept-selector-grid" class="row g-2"></div>
      </div>
      <div class="modal-footer">
        <button class="btn btn-primary" onclick="saveDeptSelection()"><i class="bi bi-check-lg me-1"></i>Save &amp; Continue</button>
      </div>
    </div>
  </div>
</div>

<!-- ═══════════ USER PROFILE MODAL ═══════════ -->
<div class="modal fade" id="myProfileModal" tabindex="-1">
  <div class="modal-dialog">
    <div class="modal-content">
      <div class="modal-header">
        <h5 class="modal-title"><i class="bi bi-person-circle me-2"></i>My Profile</h5>
        <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
      </div>
      <div class="modal-body">
        <div class="mb-3">
          <label class="form-label small fw-semibold">Display Name</label>
          <input class="form-control form-control-sm" id="prof-name">
        </div>
        <div class="mb-3">
          <label class="form-label small fw-semibold">New Password <span class="text-muted">(leave blank to keep)</span></label>
          <input type="password" class="form-control form-control-sm" id="prof-pw">
        </div>
        <div id="prof-depts-section" class="d-none">
          <label class="form-label small fw-semibold">My Departments &amp; Lines</label>
          <div id="prof-dept-grid" class="row g-2 mb-2"></div>
        </div>
      </div>
      <div class="modal-footer">
        <button class="btn btn-primary btn-sm" onclick="saveProfile()"><i class="bi bi-floppy me-1"></i>Save</button>
        <button class="btn btn-outline-secondary btn-sm" data-bs-dismiss="modal">Cancel</button>
      </div>
    </div>
  </div>
</div>
'''

replace1('<body>\n', '<body>\n' + LOGIN_OVERLAY, 'login overlay')

# ─────────────────────────────────────────────────────────────────────────────
# 2. SIDEBAR — user pill at bottom + new nav sections
# ─────────────────────────────────────────────────────────────────────────────
SIDEBAR_ADDITIONS = '''
  <div class="nav-sec" id="nav-sec-supply">Supply</div>
  <a class="nav-link" data-page="consumable-requests" id="nav-consumable-requests" href="#"><i class="bi bi-cart-plus me-1"></i>Request Consumables</a>

  <div class="nav-sec" id="nav-sec-warehouse">Warehouse Ops</div>
  <a class="nav-link" data-page="warehouse-queue" id="nav-warehouse-queue" href="#"><i class="bi bi-inbox-fill me-1"></i>Supply Queue</a>

  <div class="nav-sec" id="nav-sec-costs">Cost Analysis</div>
  <a class="nav-link" data-page="dept-costs" id="nav-dept-costs" href="#"><i class="bi bi-graph-up-arrow me-1"></i>Dept Costs</a>

  <div class="nav-sec" id="nav-sec-admin">Administration</div>
  <a class="nav-link" data-page="user-management" id="nav-user-management" href="#"><i class="bi bi-person-gear me-1"></i>User Management</a>

  <div style="padding:10px 12px 14px;margin-top:8px;border-top:1px solid rgba(255,255,255,.1)">
    <div class="d-flex align-items-center gap-2" style="background:rgba(255,255,255,.08);border-radius:8px;padding:8px 10px">
      <i class="bi bi-person-circle text-white-50" style="font-size:1.2rem"></i>
      <div style="flex:1;min-width:0">
        <div id="nav-user-name" class="text-white small fw-semibold text-truncate" style="font-size:.8rem">—</div>
        <div id="nav-user-role" class="text-white-50" style="font-size:.65rem;letter-spacing:.3px">Not signed in</div>
      </div>
      <button class="btn btn-sm py-0 px-1" style="background:rgba(255,255,255,.15);color:#fff;border:none"
              title="Profile" onclick="openMyProfile()"><i class="bi bi-gear"></i></button>
      <button class="btn btn-sm py-0 px-1" style="background:rgba(239,68,68,.3);color:#fca5a5;border:none"
              title="Logout" onclick="doLogout()"><i class="bi bi-box-arrow-right"></i></button>
    </div>
  </div>
</nav>'''

replace1('</nav>\n\n<!-- ═══════════ MAIN', SIDEBAR_ADDITIONS + '\n\n<!-- ═══════════ MAIN', 'sidebar user pill + new nav sections')

# ─────────────────────────────────────────────────────────────────────────────
# 3. NEW PAGES (insert before closing </div> of #main)
# ─────────────────────────────────────────────────────────────────────────────
NEW_PAGES = '''
<!-- ══ CONSUMABLE REQUESTS (Dept Leader) ══════════════════════ -->
<div class="page" id="page-consumable-requests">
  <div class="d-flex justify-content-between align-items-center mb-3">
    <div>
      <h4 class="mb-0"><i class="bi bi-cart-plus me-2 text-primary"></i>Request Consumables</h4>
      <small class="text-muted">Request materials from the supply warehouse</small>
    </div>
    <button class="btn btn-sm btn-primary" data-bs-toggle="modal" data-bs-target="#newConsumableModal" onclick="crOpenNew()">
      <i class="bi bi-plus-lg me-1"></i>New Request
    </button>
  </div>
  <!-- Summary badges -->
  <div class="row g-2 mb-3" id="cr-summary-row"></div>
  <!-- Request list -->
  <div class="card">
    <div class="card-header py-2 d-flex gap-2 align-items-center">
      <span class="fw-semibold small">My Requests</span>
      <select class="form-select form-select-sm ms-auto" style="width:130px" id="cr-filter-status" onchange="crLoad()">
        <option value="">All Status</option>
        <option value="PENDING">Pending</option>
        <option value="PARTIAL">Partial</option>
        <option value="FULFILLED">Fulfilled</option>
        <option value="CANCELLED">Cancelled</option>
      </select>
      <button class="btn btn-sm btn-outline-secondary" onclick="crLoad()"><i class="bi bi-arrow-clockwise"></i></button>
    </div>
    <div class="table-responsive">
      <table class="table table-sm table-hover mb-0">
        <thead class="table-light"><tr>
          <th>Request ID</th><th>Material</th><th>Dept / Line</th>
          <th class="text-end">Qty Req.</th><th class="text-end">Qty Filled</th>
          <th>Status</th><th>Date</th><th></th>
        </tr></thead>
        <tbody id="cr-tbody"></tbody>
      </table>
    </div>
  </div>
</div>

<!-- New Consumable Request Modal -->
<div class="modal fade" id="newConsumableModal" tabindex="-1">
  <div class="modal-dialog">
    <div class="modal-content">
      <div class="modal-header">
        <h5 class="modal-title"><i class="bi bi-cart-plus me-2"></i>New Consumable Request</h5>
        <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
      </div>
      <div class="modal-body">
        <div class="mb-3">
          <label class="form-label small fw-semibold">Material <span class="text-danger">*</span></label>
          <select class="form-select form-select-sm" id="cr-material-id">
            <option value="">Select material...</option>
          </select>
          <div class="small text-muted mt-1" id="cr-mat-stock"></div>
        </div>
        <div class="row g-2">
          <div class="col-md-6">
            <label class="form-label small fw-semibold">Department <span class="text-danger">*</span></label>
            <select class="form-select form-select-sm" id="cr-department"></select>
          </div>
          <div class="col-md-6">
            <label class="form-label small fw-semibold">Line</label>
            <select class="form-select form-select-sm" id="cr-line-id">
              <option value="">All / Not specific</option>
              <option>P01</option><option>P02</option><option>P37</option>
            </select>
          </div>
        </div>
        <div class="mt-3">
          <label class="form-label small fw-semibold">Qty Requested <span class="text-danger">*</span></label>
          <div class="input-group input-group-sm">
            <input type="number" class="form-control" id="cr-qty" min="0.01" step="0.01" placeholder="0.00"
                   oninput="crUpdateCostEst()">
            <span class="input-group-text" id="cr-unit-label">unit</span>
          </div>
          <div class="small text-muted mt-1" id="cr-cost-est"></div>
        </div>
        <div class="mt-3">
          <label class="form-label small fw-semibold">Notes</label>
          <input class="form-control form-control-sm" id="cr-notes" placeholder="Optional reason or specification">
        </div>
      </div>
      <div class="modal-footer">
        <button class="btn btn-primary btn-sm" onclick="crSubmitNew()"><i class="bi bi-send me-1"></i>Submit Request</button>
        <button class="btn btn-outline-secondary btn-sm" data-bs-dismiss="modal">Cancel</button>
      </div>
    </div>
  </div>
</div>

<!-- ══ WAREHOUSE SUPPLY QUEUE ══════════════════════════════════ -->
<div class="page" id="page-warehouse-queue">
  <div class="d-flex justify-content-between align-items-center mb-3">
    <div>
      <h4 class="mb-0"><i class="bi bi-inbox-fill me-2 text-warning"></i>Supply Queue</h4>
      <small class="text-muted">Fulfill consumable requests from departments</small>
    </div>
    <button class="btn btn-sm btn-outline-secondary" onclick="wqLoad()"><i class="bi bi-arrow-clockwise me-1"></i>Refresh</button>
  </div>
  <!-- KPI row -->
  <div class="row g-2 mb-3" id="wq-kpi-row"></div>
  <!-- Filter -->
  <div class="d-flex gap-2 mb-3 flex-wrap">
    <button class="btn btn-sm btn-warning active" id="wq-tab-pending" onclick="wqSetTab('PENDING')">
      <i class="bi bi-hourglass-split me-1"></i>Pending <span class="badge bg-dark ms-1" id="wq-cnt-pending">0</span>
    </button>
    <button class="btn btn-sm btn-outline-secondary" id="wq-tab-partial" onclick="wqSetTab('PARTIAL')">
      <i class="bi bi-pie-chart me-1"></i>Partial <span class="badge bg-secondary ms-1" id="wq-cnt-partial">0</span>
    </button>
    <button class="btn btn-sm btn-outline-secondary" id="wq-tab-all" onclick="wqSetTab('')">
      All Requests
    </button>
  </div>
  <div id="wq-cards"></div>
</div>

<!-- Fulfill Modal -->
<div class="modal fade" id="fulfillModal" tabindex="-1">
  <div class="modal-dialog">
    <div class="modal-content">
      <div class="modal-header">
        <h5 class="modal-title"><i class="bi bi-box-seam me-2"></i>Fulfill Request</h5>
        <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
      </div>
      <div class="modal-body">
        <div id="fulfill-info" class="mb-3"></div>
        <label class="form-label small fw-semibold">Quantity to Issue Now <span class="text-danger">*</span></label>
        <div class="input-group input-group-sm">
          <input type="number" class="form-control" id="fulfill-qty" min="0.01" step="0.01">
          <span class="input-group-text" id="fulfill-unit">unit</span>
        </div>
        <div class="small text-muted mt-2" id="fulfill-stock-note"></div>
        <div class="small text-primary mt-1" id="fulfill-cost-note"></div>
      </div>
      <div class="modal-footer">
        <button class="btn btn-success btn-sm" onclick="wqDoFulfill()"><i class="bi bi-check-lg me-1"></i>Issue &amp; Record Cost</button>
        <button class="btn btn-outline-secondary btn-sm" data-bs-dismiss="modal">Cancel</button>
      </div>
    </div>
  </div>
</div>

<!-- ══ DEPT COST REPORT ═════════════════════════════════════════ -->
<div class="page" id="page-dept-costs">
  <div class="d-flex justify-content-between align-items-center mb-3">
    <div>
      <h4 class="mb-0"><i class="bi bi-graph-up-arrow me-2 text-success"></i>Department Cost Report</h4>
      <small class="text-muted">Consumable costs allocated per department per month</small>
    </div>
    <div class="d-flex gap-2">
      <input type="month" class="form-control form-control-sm" id="dc-month" style="width:150px" onchange="dcLoad()">
      <button class="btn btn-sm btn-outline-secondary" onclick="dcLoad()"><i class="bi bi-arrow-clockwise"></i></button>
    </div>
  </div>
  <!-- KPI strip -->
  <div class="row g-2 mb-3" id="dc-kpi-row"></div>
  <!-- Summary table -->
  <div class="card mb-3">
    <div class="card-header py-2 fw-semibold small">Cost by Department</div>
    <div class="table-responsive">
      <table class="table table-sm mb-0">
        <thead class="table-light"><tr>
          <th>Department</th><th>Line</th>
          <th class="text-end">Requests</th><th class="text-end">Total Cost (฿)</th>
          <th>Materials Used</th>
        </tr></thead>
        <tbody id="dc-summary-tbody"></tbody>
      </table>
    </div>
  </div>
  <!-- Detail section -->
  <div class="card" id="dc-detail-card" style="display:none">
    <div class="card-header py-2 d-flex justify-content-between align-items-center">
      <span class="fw-semibold small" id="dc-detail-title">Detail</span>
      <button class="btn btn-sm btn-outline-secondary" onclick="document.getElementById('dc-detail-card').style.display='none'">
        <i class="bi bi-x-lg"></i>
      </button>
    </div>
    <div class="table-responsive">
      <table class="table table-sm mb-0">
        <thead class="table-light"><tr>
          <th>Date</th><th>Request ID</th><th>Material</th>
          <th class="text-end">Qty</th><th class="text-end">Unit Cost</th><th class="text-end">Total</th>
          <th>Requested By</th>
        </tr></thead>
        <tbody id="dc-detail-tbody"></tbody>
      </table>
    </div>
  </div>
</div>

<!-- ══ USER MANAGEMENT (Managerial only) ═══════════════════════ -->
<div class="page" id="page-user-management">
  <div class="d-flex justify-content-between align-items-center mb-3">
    <div>
      <h4 class="mb-0"><i class="bi bi-person-gear me-2 text-primary"></i>User Management</h4>
      <small class="text-muted">Manage ERP user accounts and role assignments</small>
    </div>
    <button class="btn btn-sm btn-primary" data-bs-toggle="modal" data-bs-target="#newUserModal" onclick="umOpenNew()">
      <i class="bi bi-person-plus me-1"></i>Add User
    </button>
  </div>
  <div class="card">
    <div class="table-responsive">
      <table class="table table-sm table-hover mb-0">
        <thead class="table-light"><tr>
          <th>Username</th><th>Display Name</th><th>Role</th><th>Status</th>
          <th>Created</th><th>Departments</th><th class="text-end">Actions</th>
        </tr></thead>
        <tbody id="um-tbody"></tbody>
      </table>
    </div>
  </div>
</div>

<!-- New User Modal -->
<div class="modal fade" id="newUserModal" tabindex="-1">
  <div class="modal-dialog">
    <div class="modal-content">
      <div class="modal-header">
        <h5 class="modal-title" id="um-modal-title"><i class="bi bi-person-plus me-2"></i>Add User</h5>
        <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
      </div>
      <div class="modal-body">
        <input type="hidden" id="um-edit-id">
        <div class="row g-2">
          <div class="col-md-6">
            <label class="form-label small fw-semibold">Username <span class="text-danger">*</span></label>
            <input class="form-control form-control-sm" id="um-username" placeholder="e.g. john.doe">
          </div>
          <div class="col-md-6">
            <label class="form-label small fw-semibold">Display Name <span class="text-danger">*</span></label>
            <input class="form-control form-control-sm" id="um-display-name" placeholder="Full name">
          </div>
        </div>
        <div class="row g-2 mt-1">
          <div class="col-md-6">
            <label class="form-label small fw-semibold">Role <span class="text-danger">*</span></label>
            <select class="form-select form-select-sm" id="um-role" onchange="umToggleDepts()">
              <option value="MANAGERIAL">Managerial</option>
              <option value="PRODUCTION_PLANNING">Production Planning</option>
              <option value="DEPARTMENT_LEADER">Department Leader</option>
              <option value="WAREHOUSE">Warehouse</option>
            </select>
          </div>
          <div class="col-md-6">
            <label class="form-label small fw-semibold">Password <span id="um-pw-hint" class="text-muted">(required)</span></label>
            <input type="password" class="form-control form-control-sm" id="um-password" placeholder="Set password">
          </div>
        </div>
        <div id="um-dept-section" class="mt-3 d-none">
          <label class="form-label small fw-semibold">Department Assignments</label>
          <div id="um-dept-grid" class="row g-2"></div>
        </div>
      </div>
      <div class="modal-footer">
        <button class="btn btn-primary btn-sm" onclick="umSave()"><i class="bi bi-floppy me-1"></i>Save</button>
        <button class="btn btn-outline-secondary btn-sm" data-bs-dismiss="modal">Cancel</button>
      </div>
    </div>
  </div>
</div>
'''

# Insert before the closing tag of #main (just before the first <script> tag that follows the pages)
replace1('<script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/js/bootstrap.bundle.min.js"></script>',
         NEW_PAGES + '\n<script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/js/bootstrap.bundle.min.js"></script>',
         'new pages block')

# ─────────────────────────────────────────────────────────────────────────────
# 4. PATCH api() to include auth token + handle 401
# ─────────────────────────────────────────────────────────────────────────────
replace1(
    '''async function api(path,method='GET',body=null){
  const opts={method,headers:{'Content-Type':'application/json'}};
  if(body) opts.body=JSON.stringify(body);
  const r=await fetch(path,opts);
  if(!r.ok){const e=await r.json().catch(()=>({detail:r.statusText}));throw new Error(e.detail||r.statusText);}
  return r.json();
}''',
    '''async function api(path,method='GET',body=null){
  const token=localStorage.getItem('erp_token')||'';
  const opts={method,headers:{'Content-Type':'application/json','X-Auth-Token':token}};
  if(body) opts.body=JSON.stringify(body);
  const r=await fetch(path,opts);
  if(r.status===401){doLogout();return null;}
  if(!r.ok){const e=await r.json().catch(()=>({detail:r.statusText}));throw new Error(e.detail||r.statusText);}
  const ct=r.headers.get('content-type')||'';
  return ct.includes('json')?r.json():{};
}''',
    'api() auth token injection'
)

# ─────────────────────────────────────────────────────────────────────────────
# 5. AUTH + ROLE JS (insert before </script>)
# ─────────────────────────────────────────────────────────────────────────────
AUTH_JS = r"""
// ══════════════════════════════════════════════════════════════
// AUTH MODULE
// ══════════════════════════════════════════════════════════════
const ROLE_PAGES = {
  MANAGERIAL: new Set([
    'dashboard','line-board','prod-flow','bom','bom-ai','materials','fg',
    'dept-fc','dept-laminating','dept-cold_press','dept-hot_press','dept-bleach',
    'dept-repair','dept-sanding','dept-grading','packing-center','dept-fg_warehouse',
    'orders','machines','prod-logs','reports','capacity',
    'station-log','prod-reports','employees',
    'dept-costs','user-management',
  ]),
  PRODUCTION_PLANNING: new Set([
    'dashboard','order-intake','line-board','prod-flow','bom','bom-ai','materials','fg',
    'dept-fc','dept-laminating','dept-cold_press','dept-hot_press','dept-bleach',
    'dept-repair','dept-sanding','dept-grading','packing-center','dept-fg_warehouse',
    'orders','machines','prod-logs','reports','capacity',
    'station-log','prod-reports','employees',
    'dept-costs',
  ]),
  DEPARTMENT_LEADER: new Set([
    'dashboard','prod-flow','station-log','consumable-requests',
  ]),
  WAREHOUSE: new Set([
    'materials','dept-grading','packing-center','dept-fg_warehouse',
    'orders','warehouse-queue','dept-costs',
  ]),
};

const ROLE_LABEL = {
  MANAGERIAL:'Managerial',
  PRODUCTION_PLANNING:'Production Planning',
  DEPARTMENT_LEADER:'Dept Leader',
  WAREHOUSE:'Warehouse',
};

// Nav sections that should only show for certain roles
const NAV_SEC_ROLES = {
  'nav-sec-supply':    ['DEPARTMENT_LEADER'],
  'nav-sec-warehouse': ['WAREHOUSE'],
  'nav-sec-costs':     ['MANAGERIAL','PRODUCTION_PLANNING','WAREHOUSE'],
  'nav-sec-admin':     ['MANAGERIAL'],
  'nav-consumable-requests': ['DEPARTMENT_LEADER'],
  'nav-warehouse-queue':     ['WAREHOUSE'],
  'nav-dept-costs':          ['MANAGERIAL','PRODUCTION_PLANNING','WAREHOUSE'],
  'nav-user-management':     ['MANAGERIAL'],
};

function getCurrentUser(){
  try{ return JSON.parse(localStorage.getItem('erp_user')||'null'); }catch{return null;}
}
function getCurrentDepts(){
  try{ return JSON.parse(localStorage.getItem('erp_depts')||'[]'); }catch{return [];}
}

async function doLogin(){
  const btn=document.getElementById('login-btn');
  const err=document.getElementById('login-error');
  const u=document.getElementById('login-username').value.trim();
  const p=document.getElementById('login-password').value;
  if(!u||!p){err.textContent='Username and password required.';err.classList.remove('d-none');return;}
  btn.disabled=true;btn.innerHTML='<span class="spinner-border spinner-border-sm me-2"></span>Signing in...';
  err.classList.add('d-none');
  try{
    const r=await fetch('/api/auth/login',{
      method:'POST',
      headers:{'Content-Type':'application/json'},
      body:JSON.stringify({username:u,password:p})
    });
    if(!r.ok){const e=await r.json().catch(()=>({detail:'Login failed'}));
      err.textContent=e.detail||'Invalid credentials';err.classList.remove('d-none');return;}
    const data=await r.json();
    localStorage.setItem('erp_token', data.token);
    localStorage.setItem('erp_user',  JSON.stringify(data.user));
    localStorage.setItem('erp_depts', JSON.stringify(data.departments||[]));
    applySession(data.user, data.departments||[]);
    document.getElementById('login-overlay').style.display='none';
    if(data.user.role==='DEPARTMENT_LEADER' && (!data.departments||data.departments.length===0)){
      openDeptSelector();
    }
  }catch(e){
    err.textContent='Network error — is the server running?';err.classList.remove('d-none');
  }finally{
    btn.disabled=false;btn.innerHTML='<i class="bi bi-box-arrow-in-right me-2"></i>Sign In';
  }
}

function doLogout(){
  const token=localStorage.getItem('erp_token');
  if(token) fetch('/api/auth/logout',{method:'POST',headers:{'X-Auth-Token':token}}).catch(()=>{});
  localStorage.removeItem('erp_token');
  localStorage.removeItem('erp_user');
  localStorage.removeItem('erp_depts');
  document.getElementById('login-overlay').style.display='flex';
  document.getElementById('login-password').value='';
  document.getElementById('login-error').classList.add('d-none');
  document.getElementById('nav-user-name').textContent='—';
  document.getElementById('nav-user-role').textContent='Not signed in';
}

function applySession(user, depts){
  // Update user pill
  document.getElementById('nav-user-name').textContent = user.display_name;
  document.getElementById('nav-user-role').textContent  = ROLE_LABEL[user.role]||user.role;
  // Apply role-based nav visibility
  const allowed = ROLE_PAGES[user.role] || new Set();
  document.querySelectorAll('.nav-link[data-page]').forEach(a=>{
    const pg = a.dataset.page;
    a.style.display = allowed.has(pg) ? '' : 'none';
  });
  // Hide/show nav section labels
  Object.entries(NAV_SEC_ROLES).forEach(([id,roles])=>{
    const el=document.getElementById(id);
    if(el) el.style.display = roles.includes(user.role) ? '' : 'none';
  });
  // Land on appropriate default page
  const defaultPage = {
    MANAGERIAL:'dashboard',
    PRODUCTION_PLANNING:'dashboard',
    DEPARTMENT_LEADER:'station-log',
    WAREHOUSE:'warehouse-queue',
  }[user.role] || 'dashboard';
  navigateTo(defaultPage);
}

// ── Dept Selector (Dept Leader post-login) ──────────────────────
const DEPT_OPTIONS = [
  {label:'Glue Mix',    value:'GLUE_MIX'},
  {label:'Laminating',  value:'LAMINATING'},
  {label:'Cold Press',  value:'COLD_PRESS'},
  {label:'Repair',      value:'REPAIR'},
  {label:'Sanding',     value:'SANDING'},
  {label:'Hot Press',   value:'HOT_PRESS'},
  {label:'Grading',     value:'GRADING'},
  {label:'FC / Cutting',value:'FC'},
  {label:'Packing',     value:'PACKING'},
];
const LINE_OPTIONS = ['P01','P02','P37'];

function openDeptSelector(){
  const grid=document.getElementById('dept-selector-grid');
  const savedDepts=getCurrentDepts();
  grid.innerHTML=DEPT_OPTIONS.map(d=>`
    <div class="col-12">
      <div class="card border p-2">
        <div class="fw-semibold small mb-1">${d.label}</div>
        <div class="d-flex gap-2 flex-wrap">
          ${LINE_OPTIONS.map(l=>{
            const checked=savedDepts.some(s=>s.department===d.value&&s.line_id===l)?'checked':'';
            return `<div class="form-check form-check-inline">
              <input class="form-check-input ds-check" type="checkbox" value="${d.value}|${l}"
                     id="ds-${d.value}-${l}" ${checked}>
              <label class="form-check-label small" for="ds-${d.value}-${l}">${l}</label>
            </div>`;
          }).join('')}
          <div class="form-check form-check-inline">
            <input class="form-check-input ds-check" type="checkbox" value="${d.value}|ALL"
                   id="ds-${d.value}-ALL"
                   ${savedDepts.some(s=>s.department===d.value&&!s.line_id)?'checked':''}>
            <label class="form-check-label small fw-semibold" for="ds-${d.value}-ALL">All Lines</label>
          </div>
        </div>
      </div>
    </div>`).join('');
  bootstrap.Modal.getOrCreateInstance(document.getElementById('deptSelectorModal')).show();
}

async function saveDeptSelection(){
  const checked=[...document.querySelectorAll('.ds-check:checked')].map(c=>{
    const [dept,line]=c.value.split('|');
    return {department:dept, line_id:line==='ALL'?null:line};
  });
  const user=getCurrentUser();
  if(!user)return;
  try{
    const result=await api(`/api/users/${user.user_id}/departments`,'POST',{departments:checked});
    localStorage.setItem('erp_depts',JSON.stringify(result));
    bootstrap.Modal.getInstance(document.getElementById('deptSelectorModal')).hide();
    toast('Departments saved');
    // Refresh station log if open
    if(document.getElementById('page-station-log').classList.contains('active')) slLoadBatches();
  }catch(e){toast(e.message,'danger');}
}

// ── My Profile Modal ─────────────────────────────────────────────
function openMyProfile(){
  const user=getCurrentUser();
  if(!user)return;
  document.getElementById('prof-name').value=user.display_name;
  document.getElementById('prof-pw').value='';
  const deptSec=document.getElementById('prof-depts-section');
  if(user.role==='DEPARTMENT_LEADER'){
    deptSec.classList.remove('d-none');
    // Render dept grid same as selector
    const saved=getCurrentDepts();
    document.getElementById('prof-dept-grid').innerHTML=DEPT_OPTIONS.map(d=>`
      <div class="col-12">
        <div class="d-flex align-items-center gap-2 flex-wrap border rounded p-2">
          <span class="small fw-semibold" style="min-width:80px">${d.label}</span>
          ${LINE_OPTIONS.map(l=>`
            <div class="form-check form-check-inline mb-0">
              <input class="form-check-input pd-check" type="checkbox" value="${d.value}|${l}"
                     id="pd-${d.value}-${l}" ${saved.some(s=>s.department===d.value&&s.line_id===l)?'checked':''}>
              <label class="form-check-label small" for="pd-${d.value}-${l}">${l}</label>
            </div>`).join('')}
          <div class="form-check form-check-inline mb-0">
            <input class="form-check-input pd-check" type="checkbox" value="${d.value}|ALL"
                   id="pd-${d.value}-ALL" ${saved.some(s=>s.department===d.value&&!s.line_id)?'checked':''}>
            <label class="form-check-label small fw-semibold" for="pd-${d.value}-ALL">All Lines</label>
          </div>
        </div>
      </div>`).join('');
  }else{deptSec.classList.add('d-none');}
  bootstrap.Modal.getOrCreateInstance(document.getElementById('myProfileModal')).show();
}

async function saveProfile(){
  const user=getCurrentUser();
  if(!user)return;
  const updates={display_name:document.getElementById('prof-name').value.trim()};
  const pw=document.getElementById('prof-pw').value;
  if(pw) updates.password=pw;
  try{
    const updated=await api(`/api/users/${user.user_id}`,'PATCH',updates);
    localStorage.setItem('erp_user',JSON.stringify({...user,...updated}));
    document.getElementById('nav-user-name').textContent=updated.display_name;
    // Save depts if dept leader
    if(user.role==='DEPARTMENT_LEADER'){
      const checked=[...document.querySelectorAll('.pd-check:checked')].map(c=>{
        const [dept,line]=c.value.split('|');
        return {department:dept,line_id:line==='ALL'?null:line};
      });
      const depts=await api(`/api/users/${user.user_id}/departments`,'POST',{departments:checked});
      localStorage.setItem('erp_depts',JSON.stringify(depts));
    }
    bootstrap.Modal.getInstance(document.getElementById('myProfileModal')).hide();
    toast('Profile updated');
  }catch(e){toast(e.message,'danger');}
}

// ── userCanActOnBatch (Dept Leader restriction) ───────────────────
function userCanActOnBatch(batch){
  const user=getCurrentUser();
  if(!user) return false;
  if(user.role!=='DEPARTMENT_LEADER') return true;
  const depts=getCurrentDepts();
  if(!depts.length) return false;
  return depts.some(d=>
    d.department===batch.status &&
    (!d.line_id || d.line_id===batch.line_id)
  );
}

// On page load: check existing token
(async function initAuth(){
  const token=localStorage.getItem('erp_token');
  const userStr=localStorage.getItem('erp_user');
  if(!token||!userStr){
    document.getElementById('login-overlay').style.display='flex';
    return;
  }
  // Validate token with server
  try{
    const r=await fetch('/api/auth/me',{headers:{'X-Auth-Token':token}});
    if(!r.ok){doLogout();return;}
    const data=await r.json();
    localStorage.setItem('erp_user',JSON.stringify(data));
    localStorage.setItem('erp_depts',JSON.stringify(data.departments||[]));
    applySession(data, data.departments||[]);
    document.getElementById('login-overlay').style.display='none';
  }catch(e){
    // Server unreachable — still hide overlay so user can see connection error
    document.getElementById('login-overlay').style.display='none';
    const u=JSON.parse(userStr);
    applySession(u, getCurrentDepts());
  }
})();

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

// ══════════════════════════════════════════════════════════════
// WAREHOUSE SUPPLY QUEUE
// ══════════════════════════════════════════════════════════════
let _wqTab='PENDING', _wqFulfillId=null, _wqFulfillMat=null;

function wqSetTab(tab){
  _wqTab=tab;
  ['PENDING','PARTIAL',''].forEach(t=>{
    const key=t||'all';
    const btn=document.getElementById(`wq-tab-${key.toLowerCase()}`);
    if(btn){ btn.classList.toggle('active',tab===t); btn.classList.toggle('btn-warning',tab===t&&t==='PENDING');
      btn.classList.toggle('btn-outline-secondary',tab!==t); }
  });
  wqLoad();
}

async function wqLoad(){
  const reqs=await api(`/api/consumable-requests${_wqTab?'?status='+_wqTab:''}`).catch(()=>[]);
  if(!reqs) return;
  // KPI
  const totPending=reqs.filter(r=>r.status==='PENDING').length;
  const totPartial=reqs.filter(r=>r.status==='PARTIAL').length;
  const totVal=reqs.filter(r=>['PENDING','PARTIAL'].includes(r.status))
    .reduce((s,r)=>(s+(r.qty_requested-r.qty_fulfilled)*(r.unit_cost||0)),0);
  document.getElementById('wq-cnt-pending').textContent=totPending;
  document.getElementById('wq-cnt-partial').textContent=totPartial;
  document.getElementById('wq-kpi-row').innerHTML=`
    <div class="col-auto"><div class="card px-3 py-2 bg-warning bg-opacity-10 border-warning"><div class="small text-muted">Pending Requests</div><div class="h4 mb-0 fw-bold text-warning">${totPending}</div></div></div>
    <div class="col-auto"><div class="card px-3 py-2 bg-primary bg-opacity-10 border-primary"><div class="small text-muted">Partial</div><div class="h4 mb-0 fw-bold text-primary">${totPartial}</div></div></div>
    <div class="col-auto"><div class="card px-3 py-2"><div class="small text-muted">Est. Value Pending</div><div class="h4 mb-0 fw-bold">฿${totVal.toFixed(2)}</div></div></div>
  `;
  const statusColor={PENDING:'warning',PARTIAL:'primary',FULFILLED:'success',CANCELLED:'secondary'};
  if(!reqs.length){
    document.getElementById('wq-cards').innerHTML='<div class="text-center text-muted py-5"><i class="bi bi-inbox" style="font-size:2rem"></i><p class="mt-2">No requests in this view.</p></div>';
    return;
  }
  document.getElementById('wq-cards').innerHTML=reqs.map(r=>{
    const remaining=r.qty_requested-r.qty_fulfilled;
    const pct=Math.round((r.qty_fulfilled/r.qty_requested)*100);
    return `<div class="card mb-2">
      <div class="card-body py-2 px-3">
        <div class="d-flex align-items-start gap-3 flex-wrap">
          <div style="flex:1;min-width:200px">
            <div class="d-flex align-items-center gap-2 mb-1">
              <code class="small text-primary">${r.request_id}</code>
              <span class="badge bg-${statusColor[r.status]||'secondary'} small">${r.status}</span>
            </div>
            <div class="fw-semibold">${r.material_name||'—'}</div>
            <div class="small text-muted">${r.department}${r.line_id?' · '+r.line_id:''} · Requested by ${r.requester_name||'—'}</div>
            <div class="small text-muted">${(r.notes||'')}</div>
          </div>
          <div style="min-width:160px">
            <div class="d-flex justify-content-between small mb-1">
              <span>Filled: ${r.qty_fulfilled} / ${r.qty_requested} ${r.unit||''}</span>
              <span>${pct}%</span>
            </div>
            <div class="progress" style="height:6px">
              <div class="progress-bar bg-success" style="width:${pct}%"></div>
            </div>
            <div class="small text-muted mt-1">Est. cost: ฿${((r.qty_requested-r.qty_fulfilled)*(r.unit_cost||0)).toFixed(2)} remaining</div>
          </div>
          ${['PENDING','PARTIAL'].includes(r.status)?`
          <div class="d-flex gap-1">
            <button class="btn btn-success btn-sm" onclick="wqOpenFulfill('${r.request_id}','${r.material_name||''}','${r.unit||''}',${r.unit_cost||0},${remaining},${r.current_stock||0})">
              <i class="bi bi-box-seam me-1"></i>Fulfill
            </button>
          </div>`:''}
        </div>
      </div>
    </div>`;
  }).join('');
}

function wqOpenFulfill(rid,name,unit,unitCost,remaining,stock){
  _wqFulfillId=rid;_wqFulfillMat={name,unit,unitCost,remaining,stock};
  document.getElementById('fulfill-info').innerHTML=`
    <div class="mb-1"><b>${name}</b></div>
    <div class="small text-muted">Outstanding: <b>${remaining} ${unit}</b></div>
    <div class="small text-muted">Warehouse stock: <b>${stock} ${unit}</b></div>`;
  document.getElementById('fulfill-unit').textContent=unit||'unit';
  document.getElementById('fulfill-qty').value=Math.min(remaining,stock)||'';
  document.getElementById('fulfill-stock-note').textContent=
    stock<remaining?`Warning: only ${stock} ${unit} in stock.`:'Stock sufficient.';
  document.getElementById('fulfill-cost-note').textContent='';
  document.getElementById('fulfill-qty').oninput=()=>{
    const q=parseFloat(document.getElementById('fulfill-qty').value)||0;
    document.getElementById('fulfill-cost-note').textContent=
      q>0?`Cost to allocate: ฿${(q*unitCost).toFixed(2)}`:'';
  };
  bootstrap.Modal.getOrCreateInstance(document.getElementById('fulfillModal')).show();
}

async function wqDoFulfill(){
  if(!_wqFulfillId) return;
  const qty=parseFloat(document.getElementById('fulfill-qty').value)||0;
  if(qty<=0){toast('Enter a quantity to issue','warning');return;}
  try{
    await api(`/api/consumable-requests/${_wqFulfillId}/fulfill`,'PATCH',{qty_fulfilled:qty});
    bootstrap.Modal.getInstance(document.getElementById('fulfillModal')).hide();
    toast(`Issued ${qty} ${_wqFulfillMat?.unit||''} — cost allocated`,'success');
    wqLoad();
  }catch(e){toast(e.message,'danger');}
}

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
    <div class="col-auto"><div class="card px-3 py-2"><div class="small text-muted">Total Cost (Month)</div><div class="h4 mb-0 fw-bold text-success">฿${totalCost.toFixed(2)}</div></div></div>
    <div class="col-auto"><div class="card px-3 py-2"><div class="small text-muted">Top Cost Dept</div><div class="h4 mb-0 fw-bold">${STATION_LABEL[topDept]||topDept}</div></div></div>
    <div class="col-auto"><div class="card px-3 py-2"><div class="small text-muted">Departments Active</div><div class="h4 mb-0 fw-bold">${rows.length}</div></div></div>
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
    <td class="small text-muted">${r.materials_used||'—'}</td>
  </tr>`).join('');
}

async function dcLoadDetail(dept,line){
  const month=document.getElementById('dc-month').value;
  const rows=await api(`/api/dept-costs/detail?month_year=${month||''}&department=${dept}`).catch(()=>[]);
  if(!rows) return;
  document.getElementById('dc-detail-title').textContent=`Detail — ${STATION_LABEL[dept]||dept} ${line?'· '+line:''}`;
  document.getElementById('dc-detail-card').style.display='';
  document.getElementById('dc-detail-tbody').innerHTML=rows.map(r=>`<tr>
    <td class="small text-muted">${(r.created_at||'').slice(0,10)}</td>
    <td><code class="small">${r.request_id||'—'}</code></td>
    <td>${r.material_name||'—'} <small class="text-muted">(${r.unit||''})</small></td>
    <td class="text-end">${r.qty}</td>
    <td class="text-end">฿${parseFloat(r.unit_cost||0).toFixed(2)}</td>
    <td class="text-end fw-bold">฿${parseFloat(r.total_cost||0).toFixed(2)}</td>
    <td class="small">${r.requester_name||'—'}</td>
  </tr>`).join('');
}

// ══════════════════════════════════════════════════════════════
// USER MANAGEMENT (Managerial)
// ══════════════════════════════════════════════════════════════
let _umEditId=null;

async function umLoad(){
  const users=await api('/api/users').catch(()=>[]);
  if(!users) return;
  document.getElementById('um-tbody').innerHTML=users.map(u=>{
    const roleBadge={MANAGERIAL:'danger',PRODUCTION_PLANNING:'primary',DEPARTMENT_LEADER:'warning text-dark',WAREHOUSE:'info text-dark'};
    return `<tr>
      <td><code class="small">${u.username}</code></td>
      <td>${u.display_name}</td>
      <td><span class="badge bg-${roleBadge[u.role]||'secondary'} small">${ROLE_LABEL[u.role]||u.role}</span></td>
      <td>${u.active?'<span class="badge bg-success small">Active</span>':'<span class="badge bg-secondary small">Inactive</span>'}</td>
      <td class="small text-muted">${(u.created_at||'').slice(0,10)}</td>
      <td class="small" id="um-depts-${u.user_id}">
        ${u.role==='DEPARTMENT_LEADER'?'<button class="btn btn-xs btn-outline-secondary py-0 px-1" onclick="umLoadDepts(\''+u.user_id+'\')"><i class="bi bi-diagram-3"></i> View</button>':'—'}
      </td>
      <td class="text-end">
        <button class="btn btn-xs btn-outline-primary py-0 px-1 me-1" onclick="umOpenEdit('${u.user_id}','${u.username}','${u.display_name}','${u.role}')"><i class="bi bi-pencil"></i></button>
        ${u.active?`<button class="btn btn-xs btn-outline-secondary py-0 px-1" onclick="umToggleActive('${u.user_id}',false)"><i class="bi bi-pause-circle"></i></button>`
          :`<button class="btn btn-xs btn-outline-success py-0 px-1" onclick="umToggleActive('${u.user_id}',true)"><i class="bi bi-play-circle"></i></button>`}
      </td>
    </tr>`;
  }).join('');
}

async function umLoadDepts(uid){
  const depts=await api(`/api/users/${uid}/departments`).catch(()=>[]);
  const el=document.getElementById(`um-depts-${uid}`);
  if(el) el.innerHTML=depts.length
    ? depts.map(d=>`<span class="badge bg-light text-dark border me-1">${d.department}${d.line_id?' '+d.line_id:''}</span>`).join('')
    : '<span class="text-muted small">None set</span>';
}

function umOpenNew(){
  _umEditId=null;
  document.getElementById('um-modal-title').innerHTML='<i class="bi bi-person-plus me-2"></i>Add User';
  document.getElementById('um-edit-id').value='';
  document.getElementById('um-username').value='';
  document.getElementById('um-display-name').value='';
  document.getElementById('um-role').value='DEPARTMENT_LEADER';
  document.getElementById('um-password').value='';
  document.getElementById('um-pw-hint').textContent='(required)';
  umToggleDepts();
}

function umOpenEdit(uid,username,displayName,role){
  _umEditId=uid;
  document.getElementById('um-modal-title').innerHTML='<i class="bi bi-pencil me-2"></i>Edit User';
  document.getElementById('um-edit-id').value=uid;
  document.getElementById('um-username').value=username;
  document.getElementById('um-display-name').value=displayName;
  document.getElementById('um-role').value=role;
  document.getElementById('um-password').value='';
  document.getElementById('um-pw-hint').textContent='(leave blank to keep)';
  umToggleDepts();
  bootstrap.Modal.getOrCreateInstance(document.getElementById('newUserModal')).show();
}

function umToggleDepts(){
  const role=document.getElementById('um-role').value;
  const sec=document.getElementById('um-dept-section');
  if(role==='DEPARTMENT_LEADER'){
    sec.classList.remove('d-none');
    document.getElementById('um-dept-grid').innerHTML=DEPT_OPTIONS.map(d=>`
      <div class="col-12 col-md-6">
        <div class="border rounded p-2">
          <div class="fw-semibold small mb-1">${d.label}</div>
          <div class="d-flex gap-2 flex-wrap">
            ${LINE_OPTIONS.map(l=>`
              <div class="form-check form-check-inline mb-0">
                <input class="form-check-input um-dept-check" type="checkbox" value="${d.value}|${l}" id="um-${d.value}-${l}">
                <label class="form-check-label small" for="um-${d.value}-${l}">${l}</label>
              </div>`).join('')}
            <div class="form-check form-check-inline mb-0">
              <input class="form-check-input um-dept-check" type="checkbox" value="${d.value}|ALL" id="um-${d.value}-ALL">
              <label class="form-check-label small fw-semibold" for="um-${d.value}-ALL">All</label>
            </div>
          </div>
        </div>
      </div>`).join('');
  }else{sec.classList.add('d-none');}
}

async function umSave(){
  const editId=document.getElementById('um-edit-id').value;
  const body={
    display_name:document.getElementById('um-display-name').value.trim(),
    role:document.getElementById('um-role').value,
  };
  const pw=document.getElementById('um-password').value;
  if(pw) body.password=pw;
  try{
    let uid;
    if(editId){
      await api(`/api/users/${editId}`,'PATCH',body);
      uid=editId;
    }else{
      const uname=document.getElementById('um-username').value.trim();
      if(!uname||!pw){toast('Username and password required for new users','danger');return;}
      const created=await api('/api/users','POST',{...body,username:uname,password:pw});
      if(!created) return;
      uid=created.user_id;
    }
    // Save dept assignments if dept leader
    if(body.role==='DEPARTMENT_LEADER'){
      const checked=[...document.querySelectorAll('.um-dept-check:checked')].map(c=>{
        const [dept,line]=c.value.split('|');
        return {department:dept,line_id:line==='ALL'?null:line};
      });
      await api(`/api/users/${uid}/departments`,'POST',{departments:checked});
    }
    bootstrap.Modal.getInstance(document.getElementById('newUserModal')).hide();
    toast(editId?'User updated':'User created');
    umLoad();
  }catch(e){toast(e.message,'danger');}
}

async function umToggleActive(uid,active){
  try{await api(`/api/users/${uid}`,'PATCH',{active});toast(active?'User activated':'User deactivated');umLoad();}
  catch(e){toast(e.message,'danger');}
}

// ── Page load hooks ─────────────────────────────────────────────
const _origLoadPage2=typeof _origLoadPage!=='undefined'?_origLoadPage:loadPage;
const _prevLoadPage=loadPage;
function loadPage(p){
  if(p==='consumable-requests'){ crLoad(); return; }
  if(p==='warehouse-queue'){ wqLoad(); return; }
  if(p==='dept-costs'){
    // Set current month as default
    const m=document.getElementById('dc-month');
    if(!m.value) m.value=new Date().toISOString().slice(0,7);
    dcLoad(); return;
  }
  if(p==='user-management'){ umLoad(); return; }
  _prevLoadPage(p);
}
"""

replace1('\n</script>\n\n<!-- Employee Modal -->', AUTH_JS + '\n</script>\n\n<!-- Employee Modal -->', 'auth+warehouse JS block')

# ─────────────────────────────────────────────────────────────────────────────
# Write result
# ─────────────────────────────────────────────────────────────────────────────
with open(HTML_PATH, 'w', encoding='utf-8') as f:
    f.write(src)

print(f"\nDone. {changes} changes applied to index.html.")
