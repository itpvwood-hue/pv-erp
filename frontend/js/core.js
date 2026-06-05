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
