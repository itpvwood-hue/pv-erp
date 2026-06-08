/* PVWood ERP - Admin Portal.
   Carved out of index.html. Self-registers its pages.

   Globals declared:
       _faHistory, faInit, faReset, faSamplePrompt, _faAppendMessage,
       escapeHtml, faSend       (Factory Assistant)
       _allEmployees... loadEmployees and related modal handlers
       _umUsers, umLoad, umOpenNew, umEdit, umSave, umDelete, ...
                                (User Management)

   Reads but doesn't define: api / toast / marked (core + cdn).
*/


// ════════════════════════════════════════════════════════════
// Factory Assistant (chat + transcript + addChat/rmChat helpers)
// ════════════════════════════════════════════════════════════
// ── Factory Assistant ─────────────────────────────────────
// Chat surface with read-only DB + log access and Excel export. Replaces
// the niche BOM Intelligence + Capacity Planning chat boxes — same idea,
// real tools, single canonical page.
let _faHistory = [];   // [{role: 'user'|'assistant', content: string}]

function faInit(){
  if(_faHistory.length === 0){
    document.getElementById('fa-chat').innerHTML =
      '<div class="text-muted small fst-italic">Ask anything about production, inventory, costs, or forecasts. The assistant can run SELECT queries, read server logs, and produce Excel reports.</div>';
  }
}

function faReset(){
  _faHistory = [];
  document.getElementById('fa-chat').innerHTML = '';
  document.getElementById('fa-exports-tray').innerHTML = '';
  faInit();
}

function faSamplePrompt(text){
  document.getElementById('fa-input').value = text;
  document.getElementById('fa-input').focus();
}

function _faAppendMessage(role, body, isMarkdown){
  const el = document.getElementById('fa-chat');
  // First message replaces the placeholder
  if(_faHistory.length === 0) el.innerHTML = '';
  const cls = role === 'user' ? 'ai-msg user' : 'ai-msg ai';
  const icon = role === 'user'
    ? '<i class="bi bi-person-circle me-2 text-success"></i>'
    : '<i class="bi bi-cpu me-2 text-success"></i>';
  const div = document.createElement('div');
  div.className = cls;
  div.innerHTML = icon + (isMarkdown ? marked.parse(body) : escapeHtml(body));
  el.appendChild(div);
  el.scrollTop = el.scrollHeight;
  return div;
}

function escapeHtml(s){
  return String(s).replace(/[&<>"']/g, c => (
    {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]
  ));
}

async function faSend(){
  const input = document.getElementById('fa-input');
  const q = input.value.trim();
  if(!q) return;
  input.value = '';
  _faAppendMessage('user', q, false);
  _faHistory.push({role: 'user', content: q});

  const btn = document.getElementById('fa-send-btn');
  btn.disabled = true;
  const loadingDiv = _faAppendMessage('assistant',
    '<span class="text-muted"><i class="bi bi-hourglass-split me-1"></i>Thinking — may run several SQL queries…</span>',
    true);

  try {
    const r = await api('/api/factory-assistant/chat', 'POST', {messages: _faHistory});
    loadingDiv.remove();
    const replyDiv = _faAppendMessage('assistant', r.reply || '(no reply)', true);
    _faHistory.push({role: 'assistant', content: r.reply || ''});
    if(r.tool_calls){
      const meta = document.createElement('div');
      meta.className = 'small text-muted mt-1';
      meta.innerHTML = `<i class="bi bi-tools me-1"></i>${r.tool_calls} tool call${r.tool_calls===1?'':'s'}`;
      replyDiv.appendChild(meta);
    }
    // Export tray — append a download chip for each xlsx the assistant produced.
    if(Array.isArray(r.exports) && r.exports.length){
      const tray = document.getElementById('fa-exports-tray');
      r.exports.forEach(ex => {
        const card = document.createElement('div');
        card.className = 'd-inline-block me-2 mb-2';
        card.innerHTML = `
          <a class="btn btn-sm btn-outline-success" href="${ex.download_url}" target="_blank">
            <i class="bi bi-file-earmark-spreadsheet me-1"></i>${ex.filename}
            <span class="badge bg-success-subtle text-success ms-1">${ex.row_count} rows</span>
          </a>`;
        tray.appendChild(card);
      });
    }
  } catch(e) {
    loadingDiv.remove();
    _faAppendMessage('assistant', 'Error: ' + e.message, false);
  } finally {
    btn.disabled = false;
    input.focus();
  }
}
function addChat(cid,msg,cls,md=false){
  const c=document.getElementById(cid);
  const id='m'+Date.now()+Math.random();
  const d=document.createElement('div');d.className='ai-msg '+cls;d.id=id;
  d.innerHTML=md?marked.parse(msg):msg;c.appendChild(d);c.scrollTop=c.scrollHeight;return id;
}
function rmChat(id){const e=document.getElementById(id);if(e)e.remove();}


// ════════════════════════════════════════════════════════════
// Employees
// ════════════════════════════════════════════════════════════
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

// Station Leader Hub (loadStationLog + slh* + sl*) moved to /static/js/portal_planning.js
// Glue Mix Station (_gmRecipes + gmLoad + gmOpenRecipe + gmSaveRecipe + …) moved to /static/js/portal_planning.js
// WH Consumable Request (shared by stations) moved to /static/js/portal_planning.js
// Station Presets (_presets + preset CRUD) moved to /static/js/portal_planning.js
// Station Tools — HR Attendance + Station Stock moved to /static/js/portal_planning.js
// Production Reports moved to /static/js/portal_planning.js


// ════════════════════════════════════════════════════════════
// User Management (Managerial only)
// ════════════════════════════════════════════════════════════
// ══════════════════════════════════════════════════════════════
// USER MANAGEMENT (Managerial)
// ══════════════════════════════════════════════════════════════
// USER MANAGEMENT (Managerial only)
// ══════════════════════════════════════════════════════════════
let _umEditId=null, _umAllUsers=[];
const UM_ROLE_BADGE={MANAGERIAL:'danger',PRODUCTION_PLANNING:'primary',DEPARTMENT_LEADER:'warning text-dark',WAREHOUSE:'info text-dark'};

function _deptBadges(depts){
  if(!depts||!depts.length) return '<span class="text-muted small">—</span>';
  return depts.map(d=>`<span class="badge bg-light text-dark border me-1 mb-1" style="font-size:.65rem">${d.department}${d.line_id?' · '+d.line_id:' · All'}</span>`).join('');
}

async function umLoad(){
  const users=await api('/api/users').catch(()=>[]);
  if(!users) return;

  // Load depts for all dept leaders in parallel
  const leaderIds=users.filter(u=>u.role=== ROLE.DEPARTMENT_LEADER).map(u=>u.user_id);
  const deptMap={};
  await Promise.all(leaderIds.map(async uid=>{
    deptMap[uid]=await api(`/api/users/${uid}/departments`).catch(()=>[]);
  }));

  _umAllUsers=users.map(u=>({...u, _depts: deptMap[u.user_id]||[]}));

  // Stats
  const counts={MANAGERIAL:0,PRODUCTION_PLANNING:0,DEPARTMENT_LEADER:0,WAREHOUSE:0};
  users.forEach(u=>{ if(counts[u.role]!==undefined && u.active) counts[u.role]++; });
  document.getElementById('um-stats').innerHTML=[
    {role:'MANAGERIAL',        label:'Managerial',          icon:'bi-shield-check',   c:'danger'},
    {role:'PRODUCTION_PLANNING',label:'Production Planning', icon:'bi-clipboard-data', c:'primary'},
    {role:'DEPARTMENT_LEADER', label:'Dept Leaders',         icon:'bi-person-badge',   c:'warning'},
    {role:'WAREHOUSE',         label:'Warehouse',            icon:'bi-boxes',          c:'info'},
  ].map(s=>`
    <div class="col-6 col-md-3">
      <div class="stat-card d-flex justify-content-between align-items-start">
        <div><div class="val text-${s.c}" style="font-size:1.6rem">${counts[s.role]}</div>
        <div class="lbl">${s.label} (active)</div></div>
        <i class="bi ${s.icon} text-${s.c}" style="font-size:2rem;opacity:.15"></i>
      </div>
    </div>`).join('');

  umRender(_umAllUsers);
}

function umRender(users){
  document.getElementById('um-tbody').innerHTML=users.map(u=>`<tr>
    <td><code class="small">${u.username}</code></td>
    <td>${u.display_name}</td>
    <td><span class="badge bg-${UM_ROLE_BADGE[u.role]||'secondary'} small">${ROLE_LABEL[u.role]||u.role}</span></td>
    <td class="small">${_deptBadges(u._depts)}</td>
    <td>${u.active?'<span class="badge bg-success-subtle text-success border border-success-subtle small">Active</span>':'<span class="badge bg-secondary small">Inactive</span>'}</td>
    <td class="small text-muted">${(u.created_at||'').slice(0,10)}</td>
    <td class="text-end text-nowrap">
      <button class="btn btn-xs btn-outline-primary py-0 px-1 me-1" title="Edit"
              onclick="umOpenEdit('${u.user_id}')"><i class="bi bi-pencil"></i></button>
      ${u.active
        ?`<button class="btn btn-xs btn-outline-secondary py-0 px-1" title="Deactivate"
                 onclick="umToggleActive('${u.user_id}',false)"><i class="bi bi-pause-circle"></i></button>`
        :`<button class="btn btn-xs btn-outline-success py-0 px-1" title="Activate"
                 onclick="umToggleActive('${u.user_id}',true)"><i class="bi bi-play-circle"></i></button>`}
    </td>
  </tr>`).join('');
}

function umFilter(q){
  const lq=q.toLowerCase();
  umRender(_umAllUsers.filter(u=>
    u.username.toLowerCase().includes(lq)||u.display_name.toLowerCase().includes(lq)
  ));
}

function _renderDeptGrid(containerId, existingDepts=[]){
  document.getElementById(containerId).innerHTML=DEPT_OPTIONS.map(d=>`
    <div class="col-12 col-md-6">
      <div class="border rounded p-2">
        <div class="fw-semibold small mb-1">${d.label}</div>
        <div class="d-flex gap-2 flex-wrap">
          ${LINE_OPTIONS_get().map(l=>{
            const chk=existingDepts.some(s=>s.department===d.value&&s.line_id===l)?'checked':'';
            return `<div class="form-check form-check-inline mb-0">
              <input class="form-check-input um-dept-check" type="checkbox" value="${d.value}|${l}" id="um-${d.value}-${l}" ${chk}>
              <label class="form-check-label small" for="um-${d.value}-${l}">${l}</label>
            </div>`;
          }).join('')}
          <div class="form-check form-check-inline mb-0">
            <input class="form-check-input um-dept-check" type="checkbox" value="${d.value}|ALL" id="um-${d.value}-ALL"
                   ${existingDepts.some(s=>s.department===d.value&&!s.line_id)?'checked':''}>
            <label class="form-check-label small fw-semibold" for="um-${d.value}-ALL">All Lines</label>
          </div>
        </div>
      </div>
    </div>`).join('');
}

function umOpenNew(){
  _umEditId=null;
  document.getElementById('um-modal-title').innerHTML='<i class="bi bi-person-plus me-2"></i>Add User';
  document.getElementById('um-edit-id').value='';
  document.getElementById('um-username').value='';
  document.getElementById('um-username').disabled=false;
  document.getElementById('um-display-name').value='';
  document.getElementById('um-role').value='DEPARTMENT_LEADER';
  document.getElementById('um-password').value='';
  document.getElementById('um-pw-hint').textContent='(required)';
  umToggleDepts([]);
  bootstrap.Modal.getOrCreateInstance(document.getElementById('newUserModal')).show();
}

async function umOpenEdit(uid){
  const u=_umAllUsers.find(x=>x.user_id===uid);
  if(!u) return;
  _umEditId=uid;
  document.getElementById('um-modal-title').innerHTML='<i class="bi bi-pencil me-2"></i>Edit User';
  document.getElementById('um-edit-id').value=uid;
  document.getElementById('um-username').value=u.username;
  document.getElementById('um-username').disabled=true;   // username cannot be changed
  document.getElementById('um-display-name').value=u.display_name;
  document.getElementById('um-role').value=u.role;
  document.getElementById('um-password').value='';
  document.getElementById('um-pw-hint').textContent='(leave blank to keep)';
  umToggleDepts(u._depts||[]);
  bootstrap.Modal.getOrCreateInstance(document.getElementById('newUserModal')).show();
}

function umToggleDepts(existingDepts){
  const role=document.getElementById('um-role').value;
  const sec=document.getElementById('um-dept-section');
  if(role=== ROLE.DEPARTMENT_LEADER){
    sec.classList.remove('d-none');
    _renderDeptGrid('um-dept-grid', existingDepts||[]);
  }else{
    sec.classList.add('d-none');
  }
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
      if(!uname){toast('Username is required','danger');return;}
      if(!pw){toast('Password is required for new accounts','danger');return;}
      const created=await api('/api/users','POST',{...body,username:uname,password:pw});
      if(!created) return;
      uid=created.user_id;
    }
    // Always save dept assignments for dept leaders (even if empty = clear)
    if(body.role=== ROLE.DEPARTMENT_LEADER){
      const checked=[...document.querySelectorAll('.um-dept-check:checked')].map(c=>{
        const [dept,line]=c.value.split('|');
        return {department:dept, line_id:line==='ALL'?null:line};
      });
      await api(`/api/users/${uid}/departments`,'POST',{departments:checked});
    }
    bootstrap.Modal.getInstance(document.getElementById('newUserModal')).hide();
    toast(editId?'User updated':'User created');
    umLoad();
  }catch(e){toast(e.message,'danger');}
}

async function umToggleActive(uid,active){
  try{
    await api(`/api/users/${uid}`,'PATCH',{active});
    toast(active?'User activated':'User deactivated');
    umLoad();
  }catch(e){toast(e.message,'danger');}
}



// ── Page loader registry ────────────────────────────────────
Object.assign(PAGE_LOADERS, {
  'factory-assistant':  faInit,
  'employees':          loadEmployees,
});
