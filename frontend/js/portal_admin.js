/* PVWood ERP - Admin Portal.
   Carved out of index.html. Self-registers its pages.

   Globals declared:
       _faHistory, _faSessionId, faInit, faReset, faSamplePrompt,
       _faAppendMessage, faSend, faLoadKnowledge, faAddKnowledge
                                (Factory Assistant + Knowledge Base)
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
// Current conversation session id — persisted in localStorage so the chat
// survives reloads + navigation; the backend keys saved turns (fa_conversations)
// by it. The sidebar lists every saved session so past chats can be reopened.
const _faNewId = () => (crypto.randomUUID ? crypto.randomUUID() : 'fa-'+Date.now()+'-'+Math.random().toString(36).slice(2));
let _faSessionId = localStorage.getItem('fa_session_id') || _faNewId();
localStorage.setItem('fa_session_id', _faSessionId);
let _faSessions = [];
let _faRestored = false;

function _faShowWelcome(){
  document.getElementById('fa-chat').innerHTML =
    '<div class="text-muted small fst-italic">Ask anything about production, inventory, costs, or forecasts. The assistant can run SELECT queries, read server logs, and produce Excel reports. Your chats are saved on the left — reopen one any time to continue it.</div>';
}

async function faInit(){
  faLoadKnowledge();          // refresh the Knowledge Base panel
  await faLoadSessions();     // populate the saved-chats sidebar
  // Restore the active session's transcript once (survives reload/navigation).
  if(!_faRestored){
    _faRestored = true;
    if(_faSessions.some(s => s.session_id === _faSessionId)){
      await faOpenSession(_faSessionId);
    } else if(_faHistory.length === 0){
      _faShowWelcome();
    }
  }
}

function faNewChat(){
  _faHistory = [];
  _faSessionId = _faNewId();
  localStorage.setItem('fa_session_id', _faSessionId);
  document.getElementById('fa-chat').innerHTML = '';
  document.getElementById('fa-exports-tray').innerHTML = '';
  _faShowWelcome();
  faRenderSessions();   // de-highlight the previous session
  document.getElementById('fa-input')?.focus();
}
function faReset(){ faNewChat(); }   // backward-compat alias

async function faLoadSessions(){
  try { _faSessions = await api('/api/factory-assistant/sessions') || []; }
  catch { _faSessions = []; }
  faRenderSessions();
}
function _faRelTime(s){
  if(!s) return '';
  const d = new Date(String(s).replace(' ','T') + 'Z');
  const diff = (Date.now() - d.getTime())/1000;
  if(isNaN(diff)) return '';
  if(diff < 60)    return 'just now';
  if(diff < 3600)  return Math.floor(diff/60)+'m ago';
  if(diff < 86400) return Math.floor(diff/3600)+'h ago';
  return Math.floor(diff/86400)+'d ago';
}
function faRenderSessions(){
  const el = document.getElementById('fa-sessions'); if(!el) return;
  if(!_faSessions.length){ el.innerHTML = '<div class="text-muted small p-3">No saved chats yet. Ask a question to start one.</div>'; return; }
  el.innerHTML = _faSessions.map(s=>{
    const active = s.session_id === _faSessionId;
    const title = (s.title || 'New chat').replace(/\s+/g,' ').trim();
    const short = title.length > 46 ? title.slice(0,46)+'…' : title;
    return `<div class="px-2 py-2 border-bottom ${active?'bg-success-subtle':''}" style="cursor:pointer"
              onclick="faOpenSession('${s.session_id}')">
        <div class="d-flex justify-content-between align-items-start">
          <div class="small fw-semibold" style="overflow:hidden;text-overflow:ellipsis" title="${escapeHtml(title)}">${escapeHtml(short)}</div>
          <button class="btn btn-sm btn-link text-danger p-0 ms-1" style="line-height:1" title="Delete chat"
                  onclick="event.stopPropagation();faDeleteSession('${s.session_id}')"><i class="bi bi-trash"></i></button>
        </div>
        <div class="text-muted" style="font-size:.68rem">${_faRelTime(s.last_at)} · ${s.msg_count} msg${s.msg_count==1?'':'s'}</div>
      </div>`;
  }).join('');
}
function _faRenderBubble(role, content){
  const el = document.getElementById('fa-chat');
  const cls  = role === 'user' ? 'ai-msg user' : 'ai-msg ai';
  const icon = role === 'user' ? '<i class="bi bi-person-circle me-2 text-success"></i>'
                               : '<i class="bi bi-cpu me-2 text-success"></i>';
  const div = document.createElement('div'); div.className = cls;
  div.innerHTML = icon + (role === 'user' ? escapeHtml(content) : marked.parse(content||''));
  el.appendChild(div); el.scrollTop = el.scrollHeight;
}
async function faOpenSession(sid){
  if(!sid) return;
  let msgs = [];
  try { msgs = await api('/api/factory-assistant/history/'+encodeURIComponent(sid)) || []; }
  catch(e){ toast('Could not load chat: '+e.message,'danger'); return; }
  _faSessionId = sid;
  localStorage.setItem('fa_session_id', sid);
  _faHistory = msgs.map(m => ({role: m.role, content: m.content}));
  document.getElementById('fa-chat').innerHTML = '';
  document.getElementById('fa-exports-tray').innerHTML = '';
  if(!msgs.length) _faShowWelcome();
  else msgs.forEach(m => _faRenderBubble(m.role, m.content));
  faRenderSessions();
}
async function faDeleteSession(sid){
  if(!confirm('Delete this chat? This cannot be undone.')) return;
  try { await api('/api/factory-assistant/sessions/'+encodeURIComponent(sid),'DELETE'); }
  catch(e){ toast('Delete failed: '+e.message,'danger'); return; }
  if(sid === _faSessionId) faNewChat();
  faLoadSessions();
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

// escapeHtml moved to /static/js/core.js

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
    const r = await api('/api/factory-assistant/chat', 'POST',
                        {messages: _faHistory, session_id: _faSessionId});
    loadingDiv.remove();
    const replyDiv = _faAppendMessage('assistant', r.reply || '(no reply)', true);
    _faHistory.push({role: 'assistant', content: r.reply || ''});
    // Keep the session id the server settled on (it mints one for a brand-new
    // chat if the client somehow sent none).
    if(r.session_id){ _faSessionId = r.session_id; localStorage.setItem('fa_session_id', _faSessionId); }
    // The assistant may have recorded a new insight via save_knowledge —
    // refresh the panel so the manager sees it. Also refresh the saved-chats
    // sidebar so a new conversation shows up (and timestamps update).
    faLoadKnowledge();
    faLoadSessions();
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
          <button type="button" class="btn btn-sm btn-outline-success">
            <i class="bi bi-file-earmark-spreadsheet me-1"></i>${ex.filename}
            <span class="badge bg-success-subtle text-success ms-1">${ex.row_count} rows</span>
          </button>`;
        card.querySelector('button').addEventListener('click',
          () => authedDownload(ex.download_url, ex.filename));
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

// ── Factory Assistant — Knowledge Base ───────────────────────
const FA_KB_CATEGORIES = ['line_behaviour','supplier','seasonal','ncg_pattern','material','general'];
const _FA_KB_BADGE = {
  line_behaviour:'bg-primary-subtle text-primary',
  supplier:'bg-warning-subtle text-warning',
  seasonal:'bg-info-subtle text-info',
  ncg_pattern:'bg-danger-subtle text-danger',
  material:'bg-success-subtle text-success',
  general:'bg-secondary-subtle text-secondary',
};
const _FA_CONF_BADGE = { high:'bg-success', medium:'bg-secondary', low:'bg-light text-dark border' };

async function faLoadKnowledge(){
  const tbody = document.getElementById('fa-kb-tbody');
  if(!tbody) return;   // panel not on the page (non-managerial) — skip
  let rows = await api('/api/factory-assistant/knowledge').catch(()=>[]);
  if(!Array.isArray(rows)) rows = [];
  if(!rows.length){
    tbody.innerHTML = '<tr><td colspan="5" class="text-center text-muted py-2 small">No knowledge recorded yet. Add a fact below, or the assistant will record insights it finds.</td></tr>';
    return;
  }
  tbody.innerHTML = rows.map(k => {
    const catCls = _FA_KB_BADGE[k.category] || _FA_KB_BADGE.general;
    const confCls = _FA_CONF_BADGE[k.confidence] || _FA_CONF_BADGE.medium;
    const src = k.source === 'assistant_observed'
      ? '<span class="badge bg-info-subtle text-info" title="Observed by the assistant from data">AI</span>'
      : '<span class="badge bg-primary-subtle text-primary" title="Entered by a manager">Manager</span>';
    const ref = k.last_referenced_at ? String(k.last_referenced_at).slice(0,16).replace('T',' ') : '—';
    return `<tr>
      <td><span class="badge ${catCls}" style="font-size:.62rem">${k.category}</span></td>
      <td><b class="small">${escapeHtml(k.title||'')}</b><div class="small text-muted">${escapeHtml(k.content||'')}</div></td>
      <td class="text-center">${src}</td>
      <td class="text-center"><span class="badge ${confCls}" style="font-size:.62rem">${k.confidence||'medium'}</span></td>
      <td class="small text-muted">${ref}</td>
    </tr>`;
  }).join('');
}

async function faAddKnowledge(){
  const category   = document.getElementById('fa-kb-category').value;
  const title      = document.getElementById('fa-kb-title').value.trim();
  const content    = document.getElementById('fa-kb-content').value.trim();
  const confidence = document.getElementById('fa-kb-confidence').value;
  if(!title || !content){ toast('Title and detail are both required','warning'); return; }
  const btn = document.getElementById('fa-kb-add-btn');
  btn.disabled = true;
  try{
    await api('/api/factory-assistant/knowledge','POST',{category,title,content,confidence});
    toast('Knowledge added — the assistant will use it from now on','success');
    document.getElementById('fa-kb-title').value = '';
    document.getElementById('fa-kb-content').value = '';
    faLoadKnowledge();
  }catch(e){ toast(e.message||'Failed to add knowledge','danger'); }
  finally{ btn.disabled = false; }
}


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





// ════════════════════════════════════════════════════════════
// Machines
// ════════════════════════════════════════════════════════════
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
            <button class="btn btn-sm btn-outline-secondary" onclick="editMachine(${m.id},'${(m.name||'').replace(/'/g,"\'")}','${m.status||'active'}','${m.type||''}',${m.capacity_per_shift||0})">Edit</button>
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

// Production Logs moved to /static/js/portal_planning.js


// Dashboard moved to /static/js/portal_planning.js
// Order Intake + PDF PO Upload moved to /static/js/portal_planning.js
// Line Board (TrainingPeaks-style) moved to /static/js/portal_planning.js
// FC Material Check moved to /static/js/portal_planning.js
// FG Warehouse moved to /static/js/portal_warehouse.js
// ── Page loader registry ────────────────────────────────────
Object.assign(PAGE_LOADERS, {
  'factory-assistant':  faInit,
  'employees':          loadEmployees,
  'machines':           loadMachines,
  // 'dashboard' is registered by portal_planning.js — every non-warehouse
  // role loads planning, so loadDashboard is always defined there.
});
