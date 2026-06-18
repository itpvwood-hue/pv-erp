/* PVWood ERP - navigation router.
   Extracted from index.html. Globals declared:
       PAGE_LOADERS    - { page-id: loader-fn } (registered by main script + portals)
       navigateTo(p)   - show page p, run its loader
       loadPage(p)     - dispatch via PAGE_LOADERS, fall through to dept-* handler
       showPage(p)     - legacy alias for navigateTo
   The click handler at the top of this file binds [data-page] elements
   already in the DOM (this script tag sits at the END of <body>, after
   the HTML is parsed). Future portal modules register additional pages
   with: Object.assign(PAGE_LOADERS, { 'their-page': theirLoader });
*/
// ══════════════════════════════════════════════════════════
// NAVIGATION
// ══════════════════════════════════════════════════════════
document.querySelectorAll('[data-page]').forEach(a=>{
  a.addEventListener('click',e=>{e.preventDefault();navigateTo(a.dataset.page);});
});
function showPage(p){ navigateTo(p); }
function navigateTo(page){
  document.querySelectorAll('.page').forEach(p=>p.classList.remove('active'));
  document.querySelectorAll('[data-page]').forEach(a=>a.classList.remove('active'));
  const el=document.getElementById('page-'+page);
  if(el) el.classList.add('active');
  const nav=document.querySelector(`[data-page="${page}"]`);
  if(nav) nav.classList.add('active');
  // Clean up any stuck Bootstrap modal/offcanvas backdrop or scroll lock state
  // (these sometimes linger from previous pages and create empty space at top)
  document.querySelectorAll('.modal-backdrop, .offcanvas-backdrop').forEach(el=>el.remove());
  document.body.classList.remove('modal-open','offcanvas-open');
  document.body.style.removeProperty('overflow');
  document.body.style.removeProperty('padding-right');
  // Also close any still-open Bootstrap collapses from the previous page
  document.querySelectorAll('.collapse.show').forEach(c=>{
    try { bootstrap.Collapse.getInstance(c)?.hide(); } catch(e){}
  });
  // Reset scroll position to top so users always see the page header
  document.documentElement.scrollTop = 0;
  document.body.scrollTop = 0;
  window.scrollTo({top:0, left:0, behavior:'instant'});
  const mainEl = document.getElementById('main');
  if(mainEl) mainEl.scrollTop = 0;
  loadPage(page);
  // Belt-and-suspenders: scroll the new page itself into view after render
  requestAnimationFrame(()=>{
    const newPage = document.getElementById('page-'+page);
    if(newPage) newPage.scrollIntoView({block:'start', behavior:'instant'});
    window.scrollTo(0,0);
  });
}
// ── Page loader registry ─────────────────────────────────────
// Each key maps a `data-page` value to the function (or thunk) that
// fetches/initialises that page. The old 40-branch if/else chain caused
// silent fall-through bugs (e.g. 'station-log' matched two separate chains).
// Add new pages here — that's the only place.
// PAGE_LOADERS starts empty; main inline script + per-portal modules
// register their pages via Object.assign(PAGE_LOADERS, { … }).
// Mirror onto window so a bare `PAGE_LOADERS` reference resolves even if a
// stale/out-of-order script can't see this script's lexical `const` binding
// (which surfaced as "PAGE_LOADERS is not defined" after a cached deploy).
const PAGE_LOADERS = (window.PAGE_LOADERS = window.PAGE_LOADERS || {});

function loadPage(p){
  const fn = PAGE_LOADERS[p];
  if(fn){
    fn();
  } else if(p.startsWith('dept-')){
    // Generic department page (laminating, cold_press, hot_press, bleach,
    // repair, sanding, grading). Wins after the specific 'dept-fg_warehouse'
    // and 'dept-costs' entries above.
    loadDeptPage(p.replace('dept-',''));
  }
  // Station Leader Hub needs an extra scope/header refresh after its loader.
  if(p === 'station-log'){
    try { slhSetScope(); } catch { try { slhUpdateHeader(); } catch {} }
  }
  // user-management moved to /admin portal — no loader here.
}
