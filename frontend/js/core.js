/* PVWood ERP - shared core utilities.
   Extracted from index.html. Globals declared at top-level here are visible
   to subsequent inline scripts (shared global lexical environment):
       api(path, method, body)             - typed fetch client
       toast(msg, type)                    - Bootstrap toast helper
       CURRENCY_SYMBOL                     - { THB: chr, USD: chr }
       fmtNum / fmtMoney / fmtDate / fmtQty  (canonical)
       fmt, fmtB, fmtD                     - legacy aliases
       _accFmt, _accFmtB, _accFmtU, _accFmtN  - accounting aliases
       _whFmtQty                           - warehouse alias
       timeAgo(ts)                         - relative-time helper
*/
async function api(path,method='GET',body=null){
  const token=localStorage.getItem('erp_token')||'';
  const opts={method,headers:{'Content-Type':'application/json','X-Auth-Token':token}};
  if(body) opts.body=JSON.stringify(body);
  const r=await fetch(path,opts);
  if(r.status===401){doLogout();return null;}
  if(!r.ok){const e=await r.json().catch(()=>({detail:r.statusText}));throw new Error(e.detail||r.statusText);}
  const ct=r.headers.get('content-type')||'';
  return ct.includes('json')?r.json():{};
}
// Download a file from an AUTH-GATED endpoint. A plain <a href>/window.open
// can't attach the X-Auth-Token header, so the browser hits the endpoint
// unauthenticated (401). Fetch it with the header, then save the blob.
async function authedDownload(url, filename){
  const token=localStorage.getItem('erp_token')||'';
  try{
    const r=await fetch(url,{headers:{'X-Auth-Token':token}});
    if(r.status===401){doLogout();return;}
    if(!r.ok){const e=await r.json().catch(()=>({detail:r.statusText}));throw new Error(e.detail||r.statusText);}
    const blob=await r.blob();
    const obj=URL.createObjectURL(blob);
    const a=document.createElement('a');
    a.href=obj; a.download=filename||'download';
    document.body.appendChild(a); a.click(); a.remove();
    setTimeout(()=>URL.revokeObjectURL(obj),1000);
  }catch(e){ toast('Download failed: '+(e.message||e),'danger'); }
}
function toast(msg,type='success'){
  const el=document.getElementById('toast');
  el.className=`toast align-items-center text-bg-${type} border-0`;
  document.getElementById('toast-msg').textContent=msg;
  bootstrap.Toast.getOrCreateInstance(el,{delay:type==='success'?3000:6000}).show();
}
// ── Formatters ────────────────────────────────────────────
// Canonical: fmtNum / fmtMoney(n, ccy) / fmtDate / fmtQty.
// Consolidated from fmt/fmtB/fmtD + _accFmt/_accFmtN + _whFmtQty.
// Null/empty/NaN render as em-dash '—' for visual consistency.
//
// fmtMoney is currency-aware so the upcoming dual-currency accounting
// surface (THB + USD invoices, USD-priced imports) needs zero new helpers
// to add another currency — register the symbol in CURRENCY_SYMBOL and
// you can call fmtMoney(amount, 'EUR') anywhere.
const CURRENCY_SYMBOL = {
  THB: '฿',
  USD: '$',
};
function fmtNum(n){
  if(n == null || n === '') return '—';
  const v = Number(n);
  return Number.isFinite(v)
    ? v.toLocaleString(undefined, {maximumFractionDigits: 2})
    : '—';
}
function fmtMoney(n, ccy){
  if(n == null || n === '') return '—';
  const v = Number(n);
  if(!Number.isFinite(v)) return '—';
  const sym = CURRENCY_SYMBOL[ccy] || CURRENCY_SYMBOL.THB;
  return sym + v.toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2});
}
function fmtDate(d){ return d ? String(d).slice(0,10) : '—'; }
function fmtQty(n, unit){ return fmtNum(n) + (unit ? ' ' + unit : ''); }

// Hoisted aliases — old call sites work untouched from anywhere in script.
function fmt(n){ return fmtNum(n); }
function fmtB(n){ return fmtMoney(n, 'THB'); }   // legacy ฿ helper
function fmtD(d){ return fmtDate(d); }
function _accFmt(n){ return fmtMoney(n, 'THB'); }   // legacy accounting alias
function _accFmtB(n){ return fmtMoney(n, 'THB'); }  // explicit Thai Baht
function _accFmtU(n){ return fmtMoney(n, 'USD'); }  // explicit USD
function _accFmtN(n){ return fmtNum(n); }
function _whFmtQty(n){ return fmtNum(n); }

function timeAgo(ts){if(!ts)return '';const d=new Date(ts.endsWith('Z')||ts.includes('+')?ts:ts+'Z');const m=Math.round((Date.now()-d)/60000);if(m<1)return 'just now';if(m<60)return m+'m ago';const h=Math.floor(m/60),rm=m%60;if(h<24)return h+'h'+(rm?` ${rm}m`:'')+' ago';return Math.floor(h/24)+'d ago';}


// ── Priority helpers ─────────────────────────────────────────
function prioBadge(p){
  const cls={1:'p1',2:'p2',3:'p3'}[p]||'p2';
  const lbl={1:'P1 HIGH',2:'P2 MED',3:'P3 LOW'}[p]||'P'+p;
  return `<span class="prio-pill ${cls}">${lbl}</span>`;
}
function prioDot(p){return `<span class="prio-dot p${p||2}" title="Priority ${p||2}"></span>`;}
const PRIO_LABEL={1:'High',2:'Medium',3:'Low'};

// Editable inline priority selector. Pass batchId (uses /api/batches/{id}/priority)
// or set targetType='order' to use /api/production-orders/{id}/priority
function prioSelect(currentPri, targetId, targetType='batch', onChangeExtra=''){
  const p=currentPri||2;
  const cls={1:'p1',2:'p2',3:'p3'}[p]||'p2';
  const url=targetType==='order'?`/api/production-orders/${targetId}/priority`:`/api/batches/${targetId}/priority`;
  return `<select class="prio-select ${cls}" onclick="event.stopPropagation()"
    onchange="setPriority(this,'${url}',${onChangeExtra?`()=>${onChangeExtra}`:'null'})">
    <option value="1"${p==1?' selected':''}>🔴 P1 High</option>
    <option value="2"${p==2?' selected':''}>🟡 P2 Med</option>
    <option value="3"${p==3?' selected':''}>🟢 P3 Low</option>
  </select>`;
}
async function setPriority(sel, url, cb){
  const v=parseInt(sel.value);
  // Optimistic UI: switch class immediately
  sel.className=`prio-select p${v}`;
  try{
    await api(url,'PATCH',{priority:v});
    toast(`Priority set to ${PRIO_LABEL[v]} (P${v})`,'success');
    if(typeof cb==='function') cb();
  }catch(e){toast('Failed to update priority: '+e.message,'danger');}
}
function statusBadge(s){const m={draft:'secondary',planned:'info',in_progress:'primary',completed:'success',on_hold:'warning',open:'info',active:'success'};return `<span class="badge bg-${m[s]||'secondary'}">${s}</span>`;}
function lineBadge(l){return `<span class="line-badge line-${l}">${l}</span>`;}
function populateSel(id,items,vk,lk){
  const el=document.getElementById(id);if(!el)return;
  el.innerHTML=items.map(i=>`<option value="${i[vk]}">${typeof lk==='function'?lk(i):i[lk]}</option>`).join('');
}

// ── Station / Department constants + badge helpers ───────────
// STATION_* keys are uppercase form codes used by the production module
// (matching prod_batch.status). DEPT_* keys are lowercase batches.current_
// department codes. Both sets exist because legacy code mixes them.
const STATION_ORDER=['GLUE_MIX','LAMINATING','COLD_PRESS','REPAIR','SANDING','HOT_PRESS','GRADING','PACKING','COMPLETE'];
const STATION_LABEL={'GLUE_MIX':'Glue Mix','LAMINATING':'Laminating','COLD_PRESS':'Cold Press',
  'REPAIR':'Repair','SANDING':'Sanding','HOT_PRESS':'Hot Press','GRADING':'Grading','PACKING':'Packing','COMPLETE':'Complete'};
const STATION_ICON={'GLUE_MIX':'bi-droplet-fill','LAMINATING':'bi-table','COLD_PRESS':'bi-snow',
  'REPAIR':'bi-tools','SANDING':'bi-eraser','HOT_PRESS':'bi-thermometer-sun','GRADING':'bi-patch-check','PACKING':'bi-boxes','COMPLETE':'bi-check-circle-fill'};
const STATION_COLOR={'GLUE_MIX':'warning','LAMINATING':'primary','COLD_PRESS':'info',
  'REPAIR':'secondary','SANDING':'orange','HOT_PRESS':'danger','GRADING':'success','PACKING':'packing','COMPLETE':'dark'};
// Department-based constants (for batches table / Line Board unified flow)
const DEPT_ORDER=['fc','laminating','cold_press','repair','sanding','hot_press','grading','packing','fg_receiving','fg_warehouse'];
const DEPT_LABEL={fc:'Feed Center',laminating:'Glue & Laminating',cold_press:'Cold Press',repair:'Repair',
  sanding:'Sanding',hot_press:'Hot Press',grading:'Grading',packing:'Packing',
  fg_receiving:'FG Receiving',fg_warehouse:'Complete'};
const DEPT_ICON={fc:'bi-droplet-fill',laminating:'bi-table',cold_press:'bi-snow',repair:'bi-tools',
  sanding:'bi-eraser',hot_press:'bi-thermometer-sun',grading:'bi-patch-check',packing:'bi-boxes',
  fg_receiving:'bi-truck',fg_warehouse:'bi-check-circle-fill'};
const DEPT_TO_FORM={fc:'GLUE_MIX',laminating:'LAMINATING',cold_press:'COLD_PRESS',repair:'REPAIR',
  sanding:'SANDING',hot_press:'HOT_PRESS',grading:'GRADING',packing:'PACKING',
  fg_receiving:'RECEIVING',fg_warehouse:'COMPLETE'};

function slStatusBadge(s){
  const c={GLUE_MIX:'warning',LAMINATING:'primary',COLD_PRESS:'info',REPAIR:'secondary',
    SANDING:'warning text-dark',HOT_PRESS:'danger',GRADING:'success',PACKING:'packing',COMPLETE:'dark'};
  return `<span class="badge bg-${c[s]||'secondary'}" style="font-size:.65rem">${STATION_LABEL[s]||s}</span>`;
}
function slDeptBadge(dept){
  const c={fc:'warning',laminating:'primary',cold_press:'info',repair:'secondary',
    sanding:'warning text-dark',hot_press:'danger',grading:'success',packing:'packing',fg_warehouse:'dark'};
  return `<span class="badge bg-${c[dept]||'secondary'}" style="font-size:.65rem">${DEPT_LABEL[dept]||dept}</span>`;
}

// ── escapeHtml ───────────────────────────────────────────────
// Tiny HTML-entity escaper, used by the Factory Assistant chat and
// anywhere else that injects user-typed text into innerHTML.
function escapeHtml(s){
  return String(s).replace(/[&<>"']/g, c => (
    {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]
  ));
}

// ════════════════════════════════════════════════════════════
// Flag NCG (non-conforming goods) — shared by Warehouse + FC views.
// Removes qty from the chosen stock bucket and raises a QA/QC review item.
// ════════════════════════════════════════════════════════════
let _ncgReasons = null, _ncgRefreshFn = null;
const _NCG_LOC_LABEL = { FC:'FC station', WH:'Warehouse', WLWH:'WLWH' };

async function ncgFlagOpen(materialId, refreshFn){
  _ncgRefreshFn = (typeof refreshFn === 'function') ? refreshFn : null;
  let m;
  try { m = await api('/api/materials/' + materialId); }
  catch(e){ toast('Could not load material: ' + e.message, 'danger'); return; }
  document.getElementById('ncg-mat-id').value = m.id;
  document.getElementById('ncg-ctx').innerHTML =
    `<b>${m.code||''} ${m.name||''}</b> · ${(m.unit||'')}`;
  // Build source options only for buckets that hold stock.
  const buckets = [['FC', m.fc_stock], ['WH', m.current_stock], ['WLWH', m.wlwh_stock]];
  const opts = buckets.filter(b => Number(b[1]||0) > 0);
  const srcSel = document.getElementById('ncg-source');
  srcSel.innerHTML = (opts.length ? opts : buckets).map(b =>
    `<option value="${b[0]}" data-avail="${Number(b[1]||0)}">${_NCG_LOC_LABEL[b[0]]} (${Number(b[1]||0).toLocaleString()})</option>`).join('');
  // Reasons (cached)
  if(!_ncgReasons){ try { _ncgReasons = await api('/api/ncg/reasons'); } catch { _ncgReasons = ['OTHER']; } }
  document.getElementById('ncg-reason').innerHTML =
    _ncgReasons.map(r => `<option value="${r}">${r.replace(/_/g,' ')}</option>`).join('');
  document.getElementById('ncg-qty').value = '';
  document.getElementById('ncg-detail').value = '';
  ncgSourceChanged();
  new bootstrap.Modal(document.getElementById('ncgFlagModal')).show();
}
function ncgSourceChanged(){
  const sel = document.getElementById('ncg-source');
  const avail = Number(sel.selectedOptions[0]?.dataset.avail || 0);
  document.getElementById('ncg-avail').textContent = `(avail ${avail.toLocaleString()})`;
  document.getElementById('ncg-qty').max = avail;
}
async function ncgFlagSubmit(){
  const sel = document.getElementById('ncg-source');
  const avail = Number(sel.selectedOptions[0]?.dataset.avail || 0);
  const qty = parseFloat(document.getElementById('ncg-qty').value);
  if(!qty || qty <= 0){ toast('Enter a positive qty', 'warning'); return; }
  if(qty > avail){ toast(`Only ${avail} available at ${sel.value}`, 'warning'); return; }
  const body = {
    material_id: Number(document.getElementById('ncg-mat-id').value),
    qty, source: sel.value,
    reason_code: document.getElementById('ncg-reason').value,
    reason_detail: document.getElementById('ncg-detail').value.trim(),
  };
  const btn = document.getElementById('ncg-submit'); btn.disabled = true;
  try {
    await api('/api/ncg/flag', 'POST', body);
    bootstrap.Modal.getInstance(document.getElementById('ncgFlagModal')).hide();
    toast(`Flagged ${qty} as NCG — QA/QC notified`, 'success');
    if(_ncgRefreshFn) _ncgRefreshFn();
  } catch(e){ toast('Flag failed: ' + e.message, 'danger'); }
  finally { btn.disabled = false; }
}

// ════════════════════════════════════════════════════════════
// Undo my last action — floating button (#undo-fab). Per-user,
// single-level. Confirms with the action summary before reversing,
// then refreshes the current page.
// ════════════════════════════════════════════════════════════
function undoFabShow(){
  const b = document.getElementById('undo-fab');
  if(b) b.style.display = '';
}
function _currentPage(){
  const a = document.querySelector('.nav-link.active[data-page]');
  return a ? a.dataset.page : null;
}
async function undoLast(){
  let preview;
  try { preview = await api('/api/undo/last'); }
  catch(e){ toast('Undo unavailable: ' + e.message, 'danger'); return; }
  const act = preview && preview.action;
  if(!act){ toast('Nothing to undo', 'info'); return; }
  if(!confirm(`Undo your last action?\n\n${act.summary || act.action_type}\n(${(act.created_at||'').slice(0,16).replace('T',' ')})`)) return;
  try {
    const r = await api('/api/undo/last', 'POST', {});
    toast('Undone: ' + (r.summary || r.action_type), 'success');
    const pg = _currentPage();
    if(pg && typeof navigateTo === 'function') navigateTo(pg);   // refresh current view
  } catch(e){ toast('Undo failed: ' + e.message, 'danger'); }
}
