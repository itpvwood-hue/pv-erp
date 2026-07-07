/* PVWood ERP - auth + session lifecycle.
   Extracted from index.html. Declared globals:
       _loginAttempts, WAREHOUSE_PORTAL_PAGES
       getCurrentUser(), getCurrentDepts()
       loginShowError(msg, fieldId)
       doLogin(), doLogout()
       applySession(user, depts)
       openMyProfile(), saveProfile()
       userCanActOnBatch(batch)
   The file ends with an IIFE that runs on first parse to check the
   stored token and either populate the session or show the login overlay.
   Load order: this script must come AFTER the main inline script so the
   constants it reads (ROLE_PAGES, NAV_SEC_ROLES, _PORTAL_MODE) exist.
*/
if (typeof api === 'undefined') { var api = "http://192.168.1.23:8001"; }
if (typeof API_URL === 'undefined') { var API_URL = api; }
function getCurrentUser(){
  try{ return JSON.parse(localStorage.getItem('erp_user')||'null'); }catch{return null;}
}
function getCurrentDepts(){
  try{ return JSON.parse(localStorage.getItem('erp_depts')||'[]'); }catch{return [];}
}

function loginShowError(msg, fieldId){
  const errBox=document.getElementById('login-error');
  document.getElementById('login-error-msg').textContent=msg;
  errBox.classList.remove('d-none');
  if(fieldId){
    const el=document.getElementById(fieldId);
    if(el){el.classList.add('is-invalid');el.focus();}
  }
}
function loginClearError(fieldId){
  if(fieldId){
    const el=document.getElementById(fieldId);
    if(el) el.classList.remove('is-invalid');
  }
  // Only hide the alert if both fields are valid
  const u=document.getElementById('login-username');
  const p=document.getElementById('login-password');
  if(!u.classList.contains('is-invalid') && !p.classList.contains('is-invalid')){
    document.getElementById('login-error').classList.add('d-none');
  }
}

// Restore the "Keep me signed in" choice on this browser (default off).
try{
  const _rb=document.getElementById('login-remember');
  if(_rb) _rb.checked = localStorage.getItem('erp_remember')==='1';
}catch{}

let _loginAttempts=0;
async function doLogin(){
  const btn=document.getElementById('login-btn');
  const u=document.getElementById('login-username').value.trim();
  const p=document.getElementById('login-password').value;

  // Field-level validation
  if(!u && !p){
    loginShowError('Please enter your username and password.','login-username');
    document.getElementById('login-password').classList.add('is-invalid');
    return;
  }
  if(!u){loginShowError('Username is required — please enter your username.','login-username');return;}
  if(!p){loginShowError('Password is required — please enter your password.','login-password');return;}

  btn.disabled=true;
  btn.innerHTML='<span class="spinner-border spinner-border-sm me-2"></span>Signing in...';
  document.getElementById('login-error').classList.add('d-none');

  // "Keep me signed in" → long-lived session; remember the choice per browser.
  const remember = !!document.getElementById('login-remember')?.checked;
  try{ localStorage.setItem('erp_remember', remember?'1':'0'); }catch{}

  try{
    const r=await fetch('/api/auth/login',{
      method:'POST',
      headers:{'Content-Type':'application/json'},
      body:JSON.stringify({username:u,password:p,remember})
    });

    if(r.status===401){
      _loginAttempts++;
      // Specific messages based on what the server returned
      let detail='Incorrect username or password.';
      try{ detail=(await r.json()).detail||detail; }catch{}
      // Shade the error message for repeated failures
      if(_loginAttempts>=2){
        loginShowError(detail+' Check that Caps Lock is off and try again.','login-password');
        document.getElementById('login-hint').classList.remove('d-none');
      } else {
        loginShowError(detail,'login-password');
      }
      document.getElementById('login-password').value='';
      return;
    }
    if(!r.ok){
      let detail='Login failed — unexpected server error.';
      try{ detail=(await r.json()).detail||detail; }catch{}
      loginShowError(detail);
      return;
    }

    _loginAttempts=0;
    const data=await r.json();
    localStorage.setItem('erp_token', data.token);
    localStorage.setItem('erp_user',  JSON.stringify(data.user));
    localStorage.setItem('erp_depts', JSON.stringify(data.departments||[]));
    // Clear validation state
    document.getElementById('login-username').classList.remove('is-invalid');
    document.getElementById('login-password').classList.remove('is-invalid');
    document.getElementById('login-hint').classList.add('d-none');
    // Portal routing: WAREHOUSE users belong on /warehouse; everyone else on /.
    // If the user is on the wrong URL for their role, redirect (token already
    // saved to localStorage so the new page picks up the session).
    const _wantsWh = data.user.role === ROLE.WAREHOUSE;
    // WAREHOUSE users always land on the warehouse portal; other roles can
    // visit /warehouse intentionally (e.g. admin inspecting it) so we don't
    // bounce them back to / from there.
    if(_wantsWh && _PORTAL_MODE !== 'warehouse'){ window.location.href = '/warehouse'; return; }
    await applySession(data.user, data.departments||[]);
    document.getElementById('login-overlay').style.display='none';
  }catch(e){
    if(e instanceof TypeError && e.message.includes('fetch')){
      loginShowError('Cannot reach the server — make sure the ERP server is running and refresh the page.');
    } else {
      loginShowError('Network error: '+e.message);
    }
  }finally{
    btn.disabled=false;
    btn.innerHTML='<i class="bi bi-box-arrow-in-right me-2"></i>Sign In';
  }
}

function doLogout(){
  const token=localStorage.getItem('erp_token');
  if(token) fetch('/api/auth/logout',{method:'POST',headers:{'X-Auth-Token':token}}).catch(()=>{});
  localStorage.removeItem('erp_token');
  localStorage.removeItem('erp_user');
  localStorage.removeItem('erp_depts');
  _loginAttempts=0;
  document.getElementById('login-overlay').style.display='flex';
  document.getElementById('login-password').value='';
  document.getElementById('login-username').classList.remove('is-invalid');
  document.getElementById('login-password').classList.remove('is-invalid');
  document.getElementById('login-error').classList.add('d-none');
  document.getElementById('login-hint').classList.add('d-none');
  document.getElementById('nav-user-name').textContent='—';
  document.getElementById('nav-user-role').textContent='Not signed in';
}

// Warehouse portal — when the SPA is served at /warehouse, the sidebar is
// locked to these three pages regardless of the signed-in user's role.
const WAREHOUSE_PORTAL_PAGES = new Set([
  'wh-dashboard',       // Warehouse Dashboard (default landing)
  'wh-low-stock',       // Low Stock worklist + Send PR
  'wh-open-prs',        // Open Purchase Requests + delivery plan
  'materials',          // Raw Materials
  'warehouse-queue',    // Raw Material Requests from production line
  'raw-receiving',      // Receiving inbound shipments
  'wh-move-fulfill',    // WH<->WLWH movement fulfilment
  'dept-fg_warehouse',  // FG Warehouse
]);

// ── Dynamic portal loader ────────────────────────────────────
// Each role only downloads the portal modules it actually needs. The map
// is conservative — when a role can navigate to a page hosted in a
// portal, that portal is loaded. Cross-role visibility (e.g. Managerial
// inspecting a warehouse page) is preserved.
const PORTAL_FOR_ROLE = {
  WAREHOUSE:           ['warehouse'],
  DEPARTMENT_LEADER:   ['planning', 'warehouse'],          // SLH + supply queue
  PRODUCTION_PLANNING: ['planning', 'warehouse', 'accounting'],
  MANAGERIAL:          ['planning', 'warehouse', 'accounting', 'admin'],
};
const _portalLoadCache = {};   // name -> Promise
let _appVerToken = null;        // cache-bust token = app version

// Fetch the running app version once, to tag portal-script URLs. A new version
// => a new ?v= query => a guaranteed-fresh fetch after every deploy, so
// operators never run stale portal JS (belt-and-suspenders with the server's
// no-cache header on /static/*.js).
async function _portalVerToken(){
  if(_appVerToken !== null) return _appVerToken;
  try { const r = await fetch('/api/version'); const d = await r.json(); _appVerToken = d.version || ''; }
  catch { _appVerToken = ''; }
  return _appVerToken;
}

function loadPortalScript(name, ver){
  if(_portalLoadCache[name]) return _portalLoadCache[name];
  _portalLoadCache[name] = new Promise((resolve, reject) => {
    const s = document.createElement('script');
    s.src = '/static/js/portal_' + name + '.js' + (ver ? ('?v=' + encodeURIComponent(ver)) : '');
    s.onload  = () => resolve(name);
    s.onerror = () => reject(new Error('Failed to load portal_' + name + '.js'));
    document.head.appendChild(s);
  });
  return _portalLoadCache[name];
}

async function loadPortalsForRole(role){
  const ver  = await _portalVerToken();
  const list = PORTAL_FOR_ROLE[role] || ['warehouse'];
  // Parallel — they don't depend on each other.
  return Promise.all(list.map(n => loadPortalScript(n, ver)));
}

async function applySession(user, depts){
  // Load this role's portal bundles BEFORE rendering the sidebar +
  // navigating, so PAGE_LOADERS has all the pages registered when the
  // first navigateTo() fires.
  try { await loadPortalsForRole(user.role); }
  catch(e){ console.warn('portal load failed:', e); }
  // Update user pill
  document.getElementById('nav-user-name').textContent = user.display_name;
  document.getElementById('nav-user-role').textContent  = ROLE_LABEL[user.role]||user.role;
  // Reveal the floating "Undo my last action" button now that we're signed in.
  try { if(typeof undoFabShow === 'function') undoFabShow(); } catch(e){}
  // Apply role-based nav visibility. In warehouse-portal mode the role grant
  // is further intersected with WAREHOUSE_PORTAL_PAGES so the portal stays
  // focused even when a Managerial user signs in to inspect it.
  let allowed = ROLE_PAGES[user.role] || new Set();
  if(_PORTAL_MODE === 'warehouse'){
    allowed = new Set([...allowed, ...WAREHOUSE_PORTAL_PAGES]);
    allowed = new Set([...allowed].filter(p => WAREHOUSE_PORTAL_PAGES.has(p)));
  }
  document.querySelectorAll('.nav-link[data-page]').forEach(a=>{
    const pg = a.dataset.page;
    a.style.display = allowed.has(pg) ? '' : 'none';
  });
  // Hide/show nav section labels (and a handful of role-gated nav links)
  // per NAV_SEC_ROLES. In warehouse-portal mode the WAREHOUSE_PORTAL_PAGES
  // allowlist is authoritative for nav-link entries — we must NOT let
  // NAV_SEC_ROLES re-hide a page the portal wants visible (the original
  // bug: Raw Material Receiving disappeared for portal users) nor un-hide
  // a page the portal hid (e.g. forklift refuel).
  const portal = (_PORTAL_MODE === 'warehouse');
  Object.entries(NAV_SEC_ROLES).forEach(([id,roles])=>{
    const el=document.getElementById(id);
    if(!el) return;
    if(portal && el.classList.contains('nav-link')) return; // allowlist decides
    el.style.display = roles.includes(user.role) ? '' : 'none';
  });
  // Warehouse portal: hide every section label that has no visible nav-link
  // children left (so we don't get empty "Production Module" headings).
  if(_PORTAL_MODE === 'warehouse'){
    document.querySelectorAll('#sidebar .nav-sec').forEach(sec=>{
      let n = sec.nextElementSibling, hasVisible = false;
      while(n && !n.classList.contains('nav-sec')){
        if(n.classList.contains('nav-link') && n.style.display !== 'none'){ hasVisible = true; break; }
        n = n.nextElementSibling;
      }
      sec.style.display = hasVisible ? '' : 'none';
    });
  }
  // Land on appropriate default page
  const defaultPage = _PORTAL_MODE === 'warehouse'
    ? 'wh-dashboard'
    : ({
        MANAGERIAL:'dashboard',
        PRODUCTION_PLANNING:'dashboard',
        DEPARTMENT_LEADER:'station-log',
        WAREHOUSE:'warehouse-queue',
      }[user.role] || 'dashboard');
  navigateTo(defaultPage);
}

// ── Dept / Line constants (used by admin User Management) ─────────
const DEPT_OPTIONS = [
  {label:'Glue Mix',    value:'GLUE_MIX'},
  {label:'Laminating',  value:'LAMINATING'},
  {label:'Cold Press',  value:'COLD_PRESS'},
  {label:'Repair',      value:'REPAIR'},
  {label:'Sanding',     value:'SANDING'},
  {label:'Hot Press',   value:'HOT_PRESS'},
  {label:'Grading',     value:'GRADING'},
  {label:'Feed Center',value:'FC'},
  {label:'Packing',     value:'PACKING'},
];
// LINE_OPTIONS is the canonical list of physical production lines (main +
// aux). Sourced from /api/catalog/lines at startup; falls back to the
// historical hardcoded list if catalog hasn't loaded yet (e.g. during a
// dept-leader self-service action before preload finished).
function LINE_OPTIONS_get(){
  const codes = catalogLineCodes();
  return codes.length ? codes : ['P01','P02','P37','PUV','PVS','PSP'];
}

// ── My Profile Modal (name + password only — no dept editing) ─────
function openMyProfile(){
  const user=getCurrentUser();
  if(!user)return;
  document.getElementById('prof-name').value=user.display_name;
  document.getElementById('prof-pw').value='';
  // Show info note for dept leaders, hide for others
  const deptSec=document.getElementById('prof-depts-section');
  if(user.role=== ROLE.DEPARTMENT_LEADER) deptSec.classList.remove('d-none');
  else deptSec.classList.add('d-none');
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
    if(!updated) return;
    localStorage.setItem('erp_user',JSON.stringify({...user,...updated}));
    document.getElementById('nav-user-name').textContent=updated.display_name||user.display_name;
    bootstrap.Modal.getInstance(document.getElementById('myProfileModal')).hide();
    toast('Profile updated');
  }catch(e){toast(e.message,'danger');}
}

// ── userCanActOnBatch (Dept Leader restriction) ───────────────────
function userCanActOnBatch(batch){
  const user=getCurrentUser();
  if(!user) return false;
  if(user.role!== ROLE.DEPARTMENT_LEADER) return true;
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
    // Portal routing on refresh / revisit
    const _wantsWh = data.role === ROLE.WAREHOUSE;
    if(_wantsWh && _PORTAL_MODE !== 'warehouse'){ window.location.href = '/warehouse'; return; }
    await applySession(data, data.departments||[]);
    document.getElementById('login-overlay').style.display='none';
  }catch(e){
    // Server unreachable — still hide overlay so user can see connection error
    document.getElementById('login-overlay').style.display='none';
    const u=JSON.parse(userStr);
    await applySession(u, getCurrentDepts());
  }
})();
