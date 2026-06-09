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
const DEPT_LABEL={fc:'FC / Glue Mixing',laminating:'Laminating',cold_press:'Cold Press',repair:'Repair',
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
