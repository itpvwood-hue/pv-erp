"""
PVWood ERP — single source of truth for application version.

Versioning scheme: MAJOR.MINOR.PATCH
  MAJOR — incompatible schema or API breaks (bump rarely)
  MINOR — new features, backwards-compatible (e.g. new module)
  PATCH — bug fixes / small UX tweaks (bump for every shipped change)

When shipping any change, bump PATCH (or MINOR/MAJOR if warranted), update
BUILD_DATE to today, and prepend a 1-line entry to CHANGELOG below.
"""
from datetime import date

VERSION    = "2.14.0"
BUILD_DATE = "2026-06-08"

# Newest first. Format: ("X.Y.Z", "YYYY-MM-DD", "one-line description")
CHANGELOG = [
    ("2.14.0", "2026-06-08", "Portal split major milestone: completed portal_planning.js (BOM cluster + SLH cluster + order-intake/line-board/kanban/prod-logs/prod-reports/forklift-report — now 14 pages, 372k), created portal_accounting.js (193 lines, 2 pages) and portal_admin.js (353 lines, 2 pages — Factory Assistant + Employees + User Management). index.html now 525k (started at 1.2 MB, ~44% of original). 27 page loaders owned by the four portal files; main inline script keeps the truly cross-cutting pages (dashboard, materials, fg, orders, machines, purchasing, lots-docs, traceability, …)"),
    ("2.13.0", "2026-06-05", "Portal split progress: portal_warehouse.js gained wq/rrec/frfl/fkDash/scrap (+1,218 lines); new portal_planning.js created with VCMX (chunk 1, 562 lines) and Material Shortfalls + FC Material Requests + FC Hub (chunk 2, 958 lines). index.html down from ~1.2 MB to 835k (~30% smaller). 8 page loaders self-registered out of inline script. SPLIT_PLAN.md updated"),
    ("2.12.0", "2026-06-05", "Portal split progress: extracted /static/js/nav.js (PAGE_LOADERS empty + navigateTo + loadPage; main script registers loaders via Object.assign), /static/js/auth.js (login + session + applySession + initAuth IIFE; loads at end of body to see main-script globals), and /static/js/portal_warehouse.js (the three new warehouse-portal pages — wh-dashboard, wh-low-stock, wh-open-prs — self-register via Object.assign(PAGE_LOADERS, {...})). SPLIT_PLAN.md updated with current load order and 13-step progress table"),
    ("2.11.1", "2026-06-05", "Stations: new `stations` table joins lines × departments — 27 rows seeded (8 per-line depts × 3 main lines + 3 centralised hubs with line_code NULL). UNIQUE(line_code, department_code) prevents duplicates. /api/catalog/stations endpoint (filter by line_code='' for centralised, by department_code, or both). dept_activities and station_presets gained line_id columns so per-station analytics can JOIN against stations going forward"),
    ("2.11.0", "2026-06-05", "Factory Assistant AI: Claude-powered chat surface (Managerial role) replacing the unrouted BOM-AI + Capacity placeholders. Five tools — query_database (SELECT only, PRAGMA query_only enforced, 10k row cap), list_tables, describe_table, read_server_log, export_to_excel. Excel files saved under backups/factory_assistant/ and served via /api/factory-assistant/export/{file}. Frontend chat page with transcript, exports tray, and 4 sample prompts. Also: frontend portal split foundation (extracted styles.css, i18n.js, core.js; SPLIT_PLAN.md documents the per-portal carve-up)"),
    ("2.10.0", "2026-06-05", "Lines/Stations DB foundation: new `departments` and `line_flow` tables, manufacturing_line extended with line_type ('main'|'aux') + sort_order; seeded 6 lines (P01/P02/P37 main + PUV/PVS/PSP aux), 11 departments, default flow for the 3 main lines; new /api/catalog/{lines,departments,line-flow,lines/{code}/flow} endpoints; frontend now fetches the catalog at preload and exposes catalogLineCodes/DeptLabel/DeptIcon helpers; 2 unambiguous line-list sites migrated (LINE_OPTIONS, SL_LINE_OPTIONS) — LINE_FLOW kept (PM2 conflict) and HTML dropdowns left for the portal split. Adding 'P38' is now one DB insert; 5 files no longer need editing"),
    ("2.9.0", "2026-06-05", "Cleanup chunk 3: backend `class Role` + frontend `const ROLE` identifier constants (catches role-string typos at parse/load time); _mat_by_id/_mat_by_code/_mat_id_by_code helpers in database.py with 5 inline sites migrated; hardcoded SND-01/CP-01/HP-01 fallback machine codes replaced with a clear 'no machine configured' empty state; formatters consolidated into 4 canonical (fmtNum/fmtMoney/fmtDate/fmtQty) with currency-aware fmtMoney(n,ccy) now backing _accFmtB (Thai Baht) + _accFmtU (USD) ahead of dual-currency accounting"),
    ("2.8.4", "2026-06-05", "Glue Recipe edit fix on BOM tab: clicking the pencil icon on a recipe row was opening a blank 'New Glue Recipe' modal because bomGlueEdit() set window._gmRecipes after fetching but _gmRecipes is a let-bound lexical (not a window property) so the modal's lookup hit an empty array. Now assigns _gmRecipes directly"),
    ("2.8.3", "2026-06-05", "BOM Builder fix: glue recipe selection now persists when editing an existing BOM. Was a race: openBomBuilder fired loadBomBuilder without awaiting, editBomCard ran bbLoadFg after a 150ms timer, and the late-finishing loadBomBuilder re-rendered the dropdown and wiped the selection. openBomBuilder is now an async function that awaits the picker fetch; the 150ms hack is gone"),
    ("2.8.2", "2026-06-05", "BOM fix: Glue BOM now displays on existing FG list (get_structured_bom switched from INNER JOIN materials to LEFT JOIN materials + LEFT JOIN glue_recipes; 93 of 125 BOMs were silently missing their glue); new-BOM Glue picker pulls from /api/glue-recipes (was loading raw 'Glue and Additives' ingredients); save_bom_for_sku resolves glue codes against glue_recipes.recipe_code with legacy materials.code fallback; UI base font-size dropped to 14px so the dense ERP doesn't need manual zoom-out"),
    ("2.8.1", "2026-06-05", "Cleanup chunk 2 (zero behaviour change for live paths): canonicalise glue API as /api/glue-recipes (delete /api/compound-skus, /api/glue-formulas, /api/glue duplicates); rename backend get_all_compound_skus->get_glue_recipes_summary, get_compound_sku->get_glue_recipe_detail, get_compound_skus_with_lines->get_glue_recipes_with_ingredients; drop dept-fc/fc-requests/packing-center router redirects (no callers); refactor 40-branch loadPage() if/else into PAGE_LOADERS dict (also fixed latent station-log double-chain bug); hoist 18 lazy from-database imports to module top; spawned task for non-functional Glue BOM add/delete-ingredient buttons. Audit 37/37 throughout."),
    ("2.8.0", "2026-06-05", "Cleanup chunk 1 (zero behaviour change): drop resync_glue_placeholder_prices no-op + /api/price-sync, drop ORDERED->PO_ISSUED write-side alias + ordered_at stamping (read paths still handle legacy rows), remove fcHubLoadInventory_legacy frontend stub, delete archive/debug/ (pre-server-log diagnostics) and scripts/_phaseB_cleanup.py (executed 2.5.0). Git repo initialised; this work is on branch cleanup/2.7.x"),
    ("2.7.6", "2026-06-04", "Material Requests page: always back-fill Stock-in-WH / WH-Stock columns from a live /api/materials snapshot fetched in parallel with the request lists, so the value matches Raw Materials even on deployments where the consumable-requests endpoint hasn't been redeployed with current_stock in its SELECT"),
    ("2.7.5", "2026-06-04", "Material Requests page: 'Remaining ฿' column replaced with 'Stock in WH' showing live warehouse stock per material (now matches Raw Materials page); shortfall flagged in red with 'short by N' hint when current stock < remaining outstanding; backend get_consumable_requests now joins current_stock/reorder_point/name_th so the row carries truthful inventory data"),
    ("2.7.4", "2026-06-04", "Warehouse Portal: rename Supply Queue → Material Requests (clearer label for requests from production lines), add pending count badge to sidebar, swap the 4th dashboard KPI to 'Material requests' linking to the same page, and label the right-column dashboard table 'Material requests this week' with click-through"),
    ("2.7.3", "2026-06-04", "Warehouse Portal bugfixes: Raw Material Receiving sidebar link now appears in /warehouse (NAV_SEC_ROLES no longer overrides portal allowlist for nav-links); new PRs always become visible after submit (Send PR clears Open-PRs category filter, New PR auto-switches filter to match the new request's category); Arriving/Exporting KPI tiles clickable to Receiving / Supply Queue"),
    ("2.7.2", "2026-06-04", "Warehouse Portal: category filter on Low Stock + Raw Material Receiving; New PR button on Open Purchase Requests (material picker modal with low-stock indicator, suggested qty, priority — covers all 6 raw-material categories)"),
    ("2.7.1", "2026-06-04", "Warehouse Portal: new Dashboard (KPIs + this-week receiving/exporting), Low Stock worklist with one-click Send PR modal (suggested qty = min×2 − current; covers consumable/glue/packing/others — boards & veneers stay with Planning), Open Purchase Requests view with category filter and delivery plan column"),
    ("2.7.0", "2026-06-04", "Warehouse Portal at /warehouse: sidebar locked to Raw Materials + Supply Queue + FG Warehouse regardless of signed-in role; empty section headings auto-hide; admins can visit /warehouse without being bounced back to /"),
    ("2.6.3", "2026-06-04", "Raw Materials page: drop standalone Packing table at bottom (packing now shows only via Packing or All tab); description column uses name_th when Thai language is active"),
    ("2.6.2", "2026-06-04", "Bulk import hardening: cp1252 encoding fallback, silent skip of trailing blank rows (Excel artifact), type alias normalization (Consumables→adhesive, Glue and additives→glue_formula, Packing→packing, Others→other); Data Tools card relabeled to 3 buckets (Veneer/Boards/Consumables)"),
    ("2.6.1", "2026-06-02", "Raw material CSV exports + templates: rename reorder_point→min_stock, add acc_code, name_th, fc_stock columns; auto_glue_code on veneers; dims on consumables; importer accepts both old + new headers"),
    ("2.6.0", "2026-05-29", "Glue BOM Builder is now in Bill of Materials → Glue Formulas tab (full editor); Glue Mixing recipes are read-only; batch logger captures per-ingredient actual kg + actual ฿ cost"),
    ("2.5.1", "2026-05-29", "Glue ingredients moved to dedicated 'Glue and Additives' category; BOM → Glue Formulas tab now redirects to the Glue Mixing editor"),
    ("2.5.0", "2026-05-29", "Glue Phase B: glue_recipes is now sole source of truth; placeholder material rows + compound_skus/compound_lines/compound_cost dropped; bom_lines.material_id nullable; legacy normalize/sync code removed"),
    ("2.4.0", "2026-05-29", "Glue Phase A: hide glue_formula placeholders from Raw Materials; 8 mis-typed ingredients reclassified; BOM lines dual-linked via new glue_recipe_id"),
    ("2.3.0", "2026-05-29", "Glue recipe BOM editor links ingredients to catalog materials; bug fix: editing material code now persists"),
    ("2.2.0", "2026-05-27", "i18n: language switcher (EN/TH/ZH) on main app + admin + finance portals; shell strings translated"),
    ("2.1.0", "2026-05-27", "Versioning system, persistent server logs, admin log-tail endpoint"),
    ("2.0.9", "2026-05-27", "Stock & Movements multi-material + required date/time; glue-mix catalog fallback"),
    ("2.0.8", "2026-05-27", "PVWood brand: logo SVG, green/brown theme, /warehouse portal, aux line assignment"),
    ("2.0.7", "2026-05-27", "Material requests: needed_time (AM/PM); WH queue filters; FG warehouse PO collapse"),
    ("2.0.6", "2026-05-27", "Aux lines (PUV/PVS/PSP) — request hub, forklifts + stock tabs enabled"),
    ("2.0.5", "2026-05-27", "Aux lines added to SLH; consumable + FC request flow extended"),
    ("2.0.4", "2026-05-26", "VCMX fixes: catalog pair-lookup, FC stock check, weighted avg, partial completion, traceability"),
    ("2.0.3", "2026-05-26", "VCMX BOMs moved under Bill of Materials; dim fields surface in FG BOM builder"),
    ("2.0.2", "2026-05-26", "VCMX make-to-stock: BOMs, production orders, VCMX-Lam station, cost rollup"),
    ("2.0.1", "2026-05-26", "Multi-material PR with split deliveries; ad-hoc stock-building PR upgraded"),
    ("2.0.0", "2026-05-26", "Priority + needed_by cascade across PO → shortfall → FC prep"),
]

def get_info() -> dict:
    """Return current version metadata as a dict (for /api/version)."""
    return {
        "name":        "PVWood ERP",
        "version":     VERSION,
        "build_date":  BUILD_DATE,
        "patch":       VERSION.rsplit(".", 1)[-1],
        "minor":       VERSION.split(".")[1],
        "major":       VERSION.split(".")[0],
        "today":       date.today().isoformat(),
        "changelog":   [{"version": v, "date": d, "note": n} for v, d, n in CHANGELOG[:20]],
    }
