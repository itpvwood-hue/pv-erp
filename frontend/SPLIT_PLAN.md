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
│   ├── i18n.js                (done — step 2)
│   ├── core.js                (partial — api/toast/formatters/timeAgo;
│   │                           still TODO: prioBadge family, escapeHtml,
│   │                           matRow renderers used by 2+ portals)
│   ├── nav.js                 (done — step 4: PAGE_LOADERS as empty
│   │                           {} populated via Object.assign by other
│   │                           scripts; navigateTo / loadPage; sidebar
│   │                           click binding)
│   ├── auth.js                (done — step 5: login, session, applySession,
│   │                           openMyProfile, userCanActOnBatch,
│   │                           initAuth IIFE; loads AFTER main inline so
│   │                           it can see ROLE_PAGES / NAV_SEC_ROLES /
│   │                           _PORTAL_MODE)
│   ├── portal_warehouse.js    (done — step 6: wh-dashboard / wh-low-stock
│   │                           / wh-open-prs. Self-registers via
│   │                           Object.assign(PAGE_LOADERS, ...). Still
│   │                           TODO inside the inline script: wqLoad,
│   │                           rrecLoad, frflLoad, fkDashLoad, scrapLoad)
│   ├── portal_planning.js     (TODO)
│   ├── portal_accounting.js   (TODO)
│   └── portal_admin.js        (TODO)
```

## Load order in `index.html` (current)

```html
<head>
  <script src="…chart.umd.min.js"></script>
  <script src="…marked.min.js"></script>
</head>
<body>
  …HTML for every page lives here, in the body…

  <!-- Static script tags, in this order -->
  <script src="…bootstrap.bundle.min.js"></script>
  <script src="/static/js/i18n.js"></script>
  <script src="/static/js/core.js"></script>
  <script src="/static/js/nav.js"></script>          <!-- declares PAGE_LOADERS = {} -->

  <script>
    /* main inline script — registers most pages, declares ROLE_PAGES,
       NAV_SEC_ROLES, _PORTAL_MODE, and the dozens of loaders that haven't
       been moved into a portal_*.js yet. */
  </script>

  <script src="/static/js/portal_warehouse.js"></script>  <!-- self-registers its 3 pages -->
  <script src="/static/js/auth.js"></script>              <!-- runs initAuth IIFE last -->
</body>
```

Reasoning for the order:

1. **nav.js before the inline script** — the inline script does
   `Object.assign(PAGE_LOADERS, {…})` with most of the page-id keys. That
   line needs `PAGE_LOADERS` declared upstream.
2. **portal_warehouse.js after the inline script** — its
   `Object.assign(PAGE_LOADERS, {…})` references `whDashLoad` etc. defined
   in the same file, so it doesn't depend on the inline script. But its
   `_whFmtQty` calls live in core.js (already loaded). The only reason it
   sits AFTER the inline script is so a future `auth.js → navigateTo()`
   call finds the registered pages.
3. **auth.js LAST** — references `ROLE_PAGES`/`NAV_SEC_ROLES`/`_PORTAL_MODE`
   declared in the inline script. The `initAuth` IIFE runs at parse time
   and calls `applySession` → `navigateTo` → looks up `PAGE_LOADERS`. By
   the time it runs, everything is in place.

## Dynamic portal loading (once all 4 portals exist)

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

## Step-by-step migration order — progress

| # | Step | Status | Notes |
|---|---|---|---|
| 1 | `css/styles.css` | ✅ done | 14k chars |
| 2 | `js/i18n.js` | ✅ done | 190 lines; declares `_LANG`, `I18N`, `t`, `applyI18n`, `setLang` |
| 3 | `js/core.js` (partial) | ✅ done | `api`, `toast`, `CURRENCY_SYMBOL`, formatters, `timeAgo` |
| 4 | `js/nav.js` | ✅ done | `PAGE_LOADERS`, `navigateTo`, `loadPage`, sidebar click binding |
| 5 | `js/auth.js` | ✅ done | login, session, `applySession`, `initAuth` IIFE |
| 6 | `js/portal_warehouse.js` (new pages only) | ✅ done | `wh-dashboard`, `wh-low-stock`, `wh-open-prs` |
| 7 | Extend `portal_warehouse.js` | TODO | move `wq*`, `rrec*`, `frfl*`, `fkDash*`, `scrap*` |
| 8 | `portal_planning.js` | TODO | line-board, BOM, station-log, glue, VCMX, FC hub, msf |
| 9 | `portal_accounting.js` | TODO | accounting hub, `dc*` (dept costs) |
| 10 | `portal_admin.js` | TODO | employees, user mgmt |
| 11 | Extend `core.js` | TODO | `prioBadge` family, `escapeHtml`, `matRow` renderers used by 2+ portals |
| 12 | Trim `index.html` | TODO | target: ~500 lines (HTML shell + login + script tags) |
| 13 | Dynamic portal loader | TODO | replace per-role `<script src>` tags with `loadPortalScript(role)` |

Test each chunk by hard-refreshing in the browser, signing in as the
relevant role, and clicking every sidebar entry. The audit (37/37 today)
should stay green throughout.

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
