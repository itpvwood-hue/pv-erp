# Frontend Portal Split — Migration Plan

`frontend/index.html` started as a single 17k-line SPA bundle. Steps 1–3 below
have landed (CSS + i18n + core utilities extracted). The remaining work is
the per-portal carve-up; this file documents how to continue without
breaking the live UI.

## Constraints

- **No build step.** No npm, no esbuild, no bundler. FastAPI already serves
  `frontend/` as `/static/...`.
- **Globals are shared via the script's global lexical environment.** A
  `let foo = …` declared at the top of `js/core.js` is visible to subsequent
  inline `<script>` blocks. This is what makes the split work without imports.
- **One concern per file.** No mixing portal logic across files.

## Final structure

```
frontend/
├── index.html          (thin shell + login screen + script tags)
├── css/
│   └── styles.css      (done — step 1)
├── js/
│   ├── i18n.js         (done — step 2)
│   ├── core.js         (partial — step 3; api, toast, formatters, timeAgo)
│   ├── auth.js         (TODO — login, session, applySession, role+catalog fetch)
│   ├── nav.js          (TODO — sidebar router, PAGE_LOADERS, navigateTo, loadPage)
│   ├── portal_warehouse.js   (TODO)
│   ├── portal_planning.js    (TODO)
│   ├── portal_accounting.js  (TODO)
│   └── portal_admin.js       (TODO)
```

## Load order in `index.html`

```html
<!-- third-party -->
<script src="…bootstrap.bundle.min.js"></script>
<script src="…chart.umd.min.js"></script>
<script src="…marked.min.js"></script>

<!-- shared -->
<script src="/static/js/i18n.js"></script>
<script src="/static/js/core.js"></script>
<script src="/static/js/auth.js"></script>
<script src="/static/js/nav.js"></script>

<!-- one portal per role; chosen dynamically after login -->
<script>
  // applySession reads the role from /api/auth/me and dynamically loads
  // exactly one portal_*.js — the others stay un-fetched.
</script>
```

## Dynamic portal loading

Add this small helper to `auth.js`:

```js
async function loadPortalScript(role){
  const map = {
    MANAGERIAL:           '/static/js/portal_admin.js',
    PRODUCTION_PLANNING:  '/static/js/portal_planning.js',
    DEPARTMENT_LEADER:    '/static/js/portal_planning.js',   // dept leaders share planning views
    WAREHOUSE:            '/static/js/portal_warehouse.js',
  };
  const src = map[role] || '/static/js/portal_admin.js';
  return new Promise((resolve, reject) => {
    const s = document.createElement('script');
    s.src = src;
    s.onload = resolve;
    s.onerror = reject;
    document.head.appendChild(s);
  });
}
```

Called once from `applySession()` after the session is verified. The chosen
portal initialises its sidebar entries and registers its page loaders by
pushing into `PAGE_LOADERS`.

## What goes in each portal file

Use `git grep -l 'function wq'` (etc.) on the current `index.html` to find
all members of each cluster.

**`portal_warehouse.js`** — everything under "WAREHOUSE PORTAL" comment:
- `whDashLoad`, `whLowStockLoad`, `whOpenPRsLoad`, `whSendPRSubmit`,
  `whNewPROpen`, `whNewPRSubmit`, `wqLoad`, `wqLoadRm`, `wqLoadReturns`,
  `rrecLoad`, `rrecRender`, `rrecOpenReceive`, `rrecSubmit`,
  `frflLoad`, `fkDashLoad`, `scrapLoad`.

**`portal_planning.js`** — order intake, line board, BOM, production:
- `loadOrderIntake`, `loadLineBoard`, `loadKanban`, `loadBom`,
  `loadBomBuilder`, `saveBomBuilder`, `editBomCard`,
  `loadStationLog` and all `slh*` helpers, `gmLoad`, `gmOpenRecipe`,
  `loadProdReports`, `loadLogs`, `vcmxLoad`, `vcmxLamLoad`,
  `msfLoad` (material shortfalls), `fcHubLoad`.

**`portal_accounting.js`** — financial views:
- `loadAccounting`, all `_acc*` helpers, `dcLoad` (dept costs).
  Note: `_accFmtB` and `_accFmtU` already live in `core.js`.

**`portal_admin.js`** — admin overlays (currently in `admin.html` and
inside `index.html` as Employees + User Management):
- `loadEmployees`, all `um*` helpers, dashboard widgets.

**`auth.js`** — login screen + session lifecycle:
- `doLogin`, `doLogout`, `applySession`, `getCurrentUser`,
  `getCurrentDepts`, `openMyProfile`, `saveProfile`,
  the `initAuth` IIFE, `loadPortalScript`.

**`nav.js`** — top-level router and sidebar:
- `navigateTo`, `loadPage`, `PAGE_LOADERS`, sidebar pin toggle,
  the `DOMContentLoaded` click-handler binding for `[data-page]`.

## Cross-portal helpers that stay in `core.js`

If a function is used by 2+ portal files, hoist it back into `core.js`.
Likely candidates that turn up during the split:
- `prioBadge / prioDot / prioSelect / setPriority` (used in warehouse + planning)
- `_msMachines` and the machine fetcher (used in planning + warehouse Raw Receiving)
- `matRow`, `matDisplayName` and the materials table renderers

## Step-by-step migration order

1. Extract `auth.js` and `nav.js` first — they have no portal-specific
   dependencies and unblock dynamic loading. Test login + page navigation.
2. Extract `portal_warehouse.js` next — smallest portal, well-bounded,
   already in its own commented region in `index.html`. Test by signing
   in as a warehouse user and exercising every page.
3. Extract `portal_planning.js`. Largest portal — split into chunks
   (line-board, BOM, station-log, glue, VCMX) committed one at a time.
4. Extract `portal_accounting.js`.
5. Extract `portal_admin.js`.
6. Verify `index.html` is now ~500 lines of HTML shell + login + script
   tags only.

## Testing each chunk

- Run `python tests/test_audit.py` — must stay 37/37.
- Hard-refresh in browser, sign in as the role whose portal you just split,
  click every sidebar entry.
- Spot-check JS console for `ReferenceError`. The error catcher already
  surfaces these on the login screen.

## Known cross-cutting concerns

- **`_LANG` change handler** in `i18n.js` calls `slhUpdateHeader()` and
  `_renderMatFiltered()` — both are portal-specific functions. The current
  guarded calls (`typeof X === 'function' && X()`) handle missing handlers
  gracefully, so the split won't break this.
- **`PAGE_LOADERS` dict** is built once at parse time of the main inline
  script. After the split, each portal file should `Object.assign(PAGE_LOADERS, { … })`
  with its own pages.
- **The `<style>` block is fully external** — no per-portal CSS needed,
  but if a portal grows its own large rule set, add a sibling `css/portal_X.css`.
