"""
PVWood ERP — FastAPI Backend
Run: python -m uvicorn execution.main:app --host 0.0.0.0 --port 8000 --reload
"""
import os, sys, json, csv, io, hashlib, logging
from logging.handlers import RotatingFileHandler
from datetime import date, datetime
from typing import Optional, Any, List
from fastapi import FastAPI, HTTPException, UploadFile, File, Depends, Header, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, StreamingResponse, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

sys.path.insert(0, os.path.dirname(__file__))

# Central config (loads .env once, exposes typed constants)
import config as _cfg

# ── Persistent logging ────────────────────────────────────────────
# All server output (info + errors + tracebacks) lands in logs/server.log
# (path configurable via LOG_DIR env var). The log rotates at 5 MB and
# keeps the 5 most recent files.
_LOG_DIR = _cfg.LOG_DIR
os.makedirs(_LOG_DIR, exist_ok=True)
LOG_PATH = _cfg.LOG_PATH

_log_fmt = logging.Formatter(
    '%(asctime)s %(levelname)-7s %(name)s | %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S')
_log_handler = RotatingFileHandler(LOG_PATH, maxBytes=5_000_000, backupCount=5,
                                   encoding='utf-8')
_log_handler.setFormatter(_log_fmt)
# Attach to the root logger so uvicorn + fastapi + our code all flow into it.
_root = logging.getLogger()
if not any(getattr(h, 'baseFilename', None) == LOG_PATH for h in _root.handlers):
    _root.addHandler(_log_handler)
_root.setLevel(logging.INFO)
# Also send uvicorn's named loggers to the file handler.
for _ln in ('uvicorn', 'uvicorn.error', 'uvicorn.access', 'fastapi'):
    _l = logging.getLogger(_ln)
    if not any(getattr(h, 'baseFilename', None) == LOG_PATH for h in _l.handlers):
        _l.addHandler(_log_handler)
    _l.setLevel(logging.INFO)
logging.getLogger('pvwood').info('Server bootstrapping; log path = %s', LOG_PATH)

from database import (
    init_db, get_db, row_to_dict,
    # Production module
    get_employees, save_employee, delete_employee,
    get_manufacturing_lines, get_prod_machines,
    get_departments, get_line_flow, get_all_line_flows, get_stations,
    get_mfg_orders, create_mfg_order,
    get_prod_batches, create_prod_batch, advance_prod_batch_status, get_prod_batch,
    get_glue_recipes, save_glue_recipe, get_batch_glue_info, log_glue_mix_with_stock,
    get_attendance, save_attendance, delete_attendance, get_attendance_summary,
    get_station_stock, get_station_stock_movements, log_station_stock_movement,
    get_station_day_jobs, get_station_day_balances,
    correct_station_job, correct_stock_movement, fold_glue_mix_blank_stock,
    update_station_stock_min,
    get_station_presets, save_station_preset, delete_station_preset, touch_station_preset,
    log_glue_mix, log_laminating, advance_laminating,
    log_cold_press, log_repair, advance_repair,
    log_sanding, log_hot_press, log_grading, log_packing,
    get_daily_production, get_lam_efficacy_report,
    get_sanding_defect_report, get_ncg_by_reason_report,
    get_ncg_backtrack_report, get_ncg_backtrack_list,
    get_prod_ai_snapshot, get_batch_station_logs, get_ncg_reasons,
    save_ncg_issues, get_ncg_issues, get_batch_full_history,
    # Core
    get_all_materials, get_material, create_material, update_material, delete_material, bulk_upsert_material,
    delete_fg_bom,
    get_all_products, get_product, create_product, update_product, delete_product,
    get_bom_for_product, get_all_bom, create_bom_entry, update_bom_entry, delete_bom_entry, bulk_upsert_bom,
    get_all_machines, get_machine, create_machine, update_machine, delete_machine,
    get_all_orders, get_order, create_order, update_order, delete_order,
    get_all_production_logs, create_production_log, delete_production_log,
    get_all_reports, save_report,
    get_dashboard_stats, get_full_bom_context, get_capacity_context,
    # New
    get_all_purchase_orders, get_purchase_order, create_purchase_order, update_purchase_order, delete_purchase_order,
    get_customers, create_customer, update_customer, get_customer_orders,
    wh_move_stock, get_wh_transfer_log,
    create_wh_move_request, list_wh_move_requests, fulfill_wh_move_request, cancel_wh_move_request,
    list_fg_batches, move_fg_batches, get_fg_location_log,
    get_po_lines, create_po_line, update_po_line, delete_po_line, get_po_material_readiness,
    get_all_production_orders, get_production_order, create_production_order, update_production_order, release_production_order, delete_production_order,
    get_all_batches, get_batch, move_batch, split_batch, split_batch_by_pcs,
    import_wip_batches,
    merge_batches, find_mergeable_siblings, get_batch_history, delete_batch,
    get_planning_flow, get_po_flow_matrix,
    create_laminating_record, get_laminating_records, get_laminating_stats,
    create_repair_record, get_repair_records, get_repair_stats,
    create_sanding_record, get_sanding_records, get_sanding_stats,
    create_grading_record, get_grading_records,
    create_dept_activity, get_dept_activities,
    get_fc_material_requirements, get_all_fc_batches, get_line_board,
    confirm_veneer_selection,
    # Auth module
    create_user, get_user_by_username, create_session, get_session_user, delete_session,
    get_users, update_user, save_user_departments, get_user_departments,
    log_login, get_login_log,
    # Supply warehouse module
    create_consumable_request, get_consumable_requests, fulfill_consumable_request,
    receive_consumable_request,
    cancel_consumable_request, get_dept_cost_summary, get_dept_cost_detail,
    get_consumable_materials,
    # FC Station stock / transfer requests
    get_fc_stock_materials, get_fc_transfer_requests, get_fc_movements,
    get_fg_warehouse_dashboard, receive_batch_to_warehouse,
    get_accounting_stock_movements, get_accounting_production_output, get_accounting_summary,
    # Purchasing
    create_purchase_request, create_purchase_requests_bulk,
    list_purchase_requests, update_purchase_request_status,
    create_vcmx_bom, update_vcmx_bom, list_vcmx_boms,
    vcmx_check_inputs, create_vcmx_production_order,
    complete_vcmx_batch, list_vcmx_batches, list_vcmx_batch_events,
    auto_generate_purchase_requests_for_po, get_material_shortfalls,
    link_document_to_prs, get_fc_aggregate_requirements,
    get_glue_mix_station_requirements,
    create_pr_shipment, list_pr_shipments, receive_pr_shipment,
    update_pr_shipment, delete_pr_shipment,
    quick_receive_for_pr, split_pr_shipment,
    list_forklifts, upsert_forklift, delete_forklift,
    create_oil_request, list_oil_requests, update_oil_request_status,
    postpone_oil_request, REFUEL_WINDOW_HOUR, REFUEL_REQUEST_CUTOFF,
    list_refuel_windows, upsert_refuel_window, delete_refuel_window,
    list_oil_drum_materials,
    create_scrap_entry, list_scrap_entries, set_scrap_disposition,
    flag_material_ncg, list_ncg_items, review_ncg_item, add_ncg_disposition,
    get_qc_summary, NCG_REASONS,
    record_action, get_last_action, undo_last_action,
    return_material_to_fc,
    # Material lots (FIFO) & documents & traceability
    create_material_lot, list_material_lots, fifo_consume_lots,
    register_material_document, list_material_documents, get_material_document,
    delete_material_document, get_po_traceability,
    get_po_document_trace, get_po_document_trace_files, DOCS_DIR,
    create_fc_transfer_request, create_fc_return_request,
    fulfill_fc_transfer_request, cancel_fc_transfer_request, adjust_fc_stock,
    # FC re-grading & veneer grade-mix allocation
    create_veneer_regrade, get_veneer_regrade_log,
    save_veneer_alloc_and_confirm, get_veneer_alloc,
    # Proper BOM module
    get_all_skus, get_sku, get_sku_bom, get_sku_cost,
    get_glue_recipes_summary, get_glue_recipe_detail,
    get_all_packing_skus, get_packing_sku,
    get_glue_recipes_with_ingredients,
    get_packing_skus_with_lines, save_packing_sku, delete_packing_sku,
    add_packing_line, delete_packing_line,
    update_material_price, get_material_usage,
    get_structured_bom, save_bom_for_sku,
)
from claude_ai import query_bom, generate_production_report, check_capacity, extract_po_from_pdf
try:
    from production_agent import ProductionAgent
    _prod_agent = ProductionAgent()
except Exception:
    _prod_agent = None

init_db()

from version import get_info as _ver_info, VERSION as _APP_VERSION
app = FastAPI(title="PVWood ERP", version=_APP_VERSION)
# CORS — origins come from CORS_ORIGINS env var (default: localhost + 127.0.0.1).
# Set CORS_ORIGINS="*" to allow any origin (dev only).
_cors_origins = _cfg.CORS_ORIGINS if _cfg.CORS_ORIGINS != ['*'] else ['*']
app.add_middleware(CORSMiddleware,
                   allow_origins=_cors_origins,
                   allow_methods=["*"],
                   allow_headers=["*"],
                   allow_credentials=False)

FRONTEND_DIR = os.path.join(os.path.dirname(__file__), '..', 'frontend')

# ── Version + log + config endpoints (always-on; safe metadata) ───
@app.get("/api/version")
def get_version():
    """Application version + recent changelog. Surface in the SPA footer."""
    return _ver_info()

# Server boot time (process-local) — used by /api/health to report uptime.
_PROC_START = datetime.now()

@app.get("/api/health")
def health_check():
    """Liveness + readiness probe. Anonymous (no auth) so monitoring
    tools — uptime checkers, load balancers, Task Scheduler heartbeats —
    can hit it without provisioning credentials.

    Returns:
      ok            -- bool: True if the DB is reachable AND disk has
                       headroom (>500 MB).
      db_reachable  -- bool
      version       -- string (matches /api/version)
      uptime_s      -- int: seconds since this process started
      disk_free_mb  -- float: free space on the DB's drive
      now           -- string: ISO timestamp from the server clock
    """
    from database import get_db
    out = {
        "ok":            True,
        "version":       _ver_info().get("version"),
        "uptime_s":      int((datetime.now() - _PROC_START).total_seconds()),
        "now":           datetime.now().isoformat(timespec="seconds"),
        "db_reachable":  False,
        "disk_free_mb":  None,
    }
    # DB ping
    try:
        conn = get_db()
        conn.execute("SELECT 1").fetchone()
        conn.close()
        out["db_reachable"] = True
    except Exception as e:
        out["ok"] = False
        out["db_error"] = str(e)[:200]
    # Disk free on the DB's drive
    try:
        from config import DB_PATH
        import shutil as _shutil
        free_bytes = _shutil.disk_usage(os.path.dirname(DB_PATH)).free
        out["disk_free_mb"] = round(free_bytes / (1024 * 1024), 1)
        if free_bytes < 500 * 1024 * 1024:   # < 500 MB headroom
            out["ok"] = False
            out["disk_warning"] = "low disk space"
    except Exception as e:
        out["ok"] = False
        out["disk_error"] = str(e)[:200]
    return out

@app.get("/api/admin/config")
def get_config():
    """Effective server config (no secrets). Surface in the admin portal
    so ops can verify env vars took effect on the running server without
    shelling into the host."""
    return _cfg.summary()

@app.get("/api/admin/logs/tail")
def tail_server_log(n: int = 200, user: dict = Depends(lambda: None)):
    """Return the last N lines of the rotating server log. n is clamped to
    [10, 5000]. Used by the admin portal so you can copy/paste errors here
    without shelling into the host."""
    try:
        n = max(10, min(int(n or 200), 5000))
    except Exception:
        n = 200
    if not os.path.exists(LOG_PATH):
        return {"path": LOG_PATH, "lines": [], "missing": True}
    # Tail efficiently — read from end in 8 KB chunks
    try:
        with open(LOG_PATH, 'rb') as f:
            f.seek(0, os.SEEK_END)
            size = f.tell()
            block = 8192
            data = b''
            while size > 0 and data.count(b'\n') <= n:
                read = min(block, size)
                f.seek(size - read)
                data = f.read(read) + data
                size -= read
        text = data.decode('utf-8', errors='replace')
        lines = text.splitlines()[-n:]
        return {"path": LOG_PATH, "version": _APP_VERSION,
                "line_count": len(lines), "lines": lines}
    except Exception as e:
        return {"path": LOG_PATH, "error": str(e), "lines": []}

# ── Pydantic Models ───────────────────────────────────────────

class MaterialIn(BaseModel):
    name: str; type: str; unit: str; code: str = ""
    current_stock: float = 0; reorder_point: float = 0; unit_cost: float = 0; supplier: str = ""
    thickness_mm: Optional[float] = None
    width_mm: Optional[float] = None
    length_mm: Optional[float] = None
    auto_glue_code: Optional[str] = None
    # Veneer attributes (only meaningful for type='veneer_sheet')
    species: Optional[str] = None
    cut_type: Optional[str] = None
    grade: Optional[str] = None
    matching: Optional[str] = None
    face_back: Optional[str] = None
    fsc: Optional[str] = None

class ProductIn(BaseModel):
    name: str; sku: str; description: str = ""; unit: str = "sheet"; selling_price: float = 0

class BomIn(BaseModel):
    product_id: int; material_id: int; quantity_per_unit: float
    waste_factor: float = 0.05; veneer_role: str = ""; notes: str = ""

class BomUpdate(BaseModel):
    quantity_per_unit: float; waste_factor: float = 0.05; notes: str = ""

class MachineIn(BaseModel):
    name: str
    type: str = ""
    dept: str = ""
    production_line: str = ""
    capacity_per_shift: float = 0
    capacity_per_hour: float = 0
    status: str = "active"
    last_maintenance: str = ""
    next_maintenance: str = ""
    notes: str = ""

class OrderIn(BaseModel):
    order_number: str; customer: str; product_id: int; quantity: int
    produced_qty: int = 0; due_date: str; status: str = "pending"; priority: int = 3; notes: str = ""

class ProductionLogIn(BaseModel):
    log_date: str; shift: str; product_id: int; machine_id: int
    order_id: Optional[int] = None; planned_qty: int; actual_qty: int
    downtime_minutes: int = 0; downtime_reason: str = ""; operator_count: int = 1
    material_usage: dict = {}; notes: str = ""

class AIQuery(BaseModel):
    question: str

class ReportRequest(BaseModel):
    date: str; report_type: str = "daily"

# ── Production Module Models ───────────────────────────────────
class EmployeeIn(BaseModel):
    emp_id: Optional[str] = None
    emp_name: str; department: str; role: str = ""
    line_id: Optional[str] = None; active: int = 1

class MfgOrderIn(BaseModel):
    sku_code: str; line_id: str; qty_ordered: int
    po_ref: str = ""; customer_code: str = ""; due_date: str = ""

class ProdBatchIn(BaseModel):
    sku_code: str; line_id: str; qty_planned: int
    order_id: Optional[str] = None
    production_date: Optional[str] = None
    shift: str = "MORNING"

class BatchAdvanceIn(BaseModel):
    next_status: str

class GlueMixIn(BaseModel):
    batch_id: str; recipe_code: str; qty_kg: float
    operator_id: Optional[str] = None; operator_name: str = ""
    mix_time_min: Optional[int] = None; notes: Optional[str] = None

class LaminatingIn(BaseModel):
    batch_id: str; table_id: str
    emp_code_1: str; emp_code_2: str
    pcs_target: int; pcs_actual: int
    time_minutes: Optional[int] = None
    glue_mix_ref: Optional[str] = None; notes: Optional[str] = None

class ColdPressIn(BaseModel):
    batch_id: str; machine_id: str
    operator_id: Optional[str] = None; operator_name: str = ""
    pressure_bar: Optional[float] = None; dwell_min: Optional[int] = None
    pcs_in: int; pcs_out: int

class RepairIn(BaseModel):
    batch_id: str; table_id: str; repair_type: str
    emp_code_1: str; emp_code_2: str
    pcs_repaired: int; notes: Optional[str] = None

class SandingIn(BaseModel):
    batch_id: str; machine_id: str
    operator_id: Optional[str] = None; operator_name: str = ""
    grit_setting: str; feed_speed: Optional[float] = None
    pcs_in: int; pcs_out: int; defect_count: int = 0
    notes: Optional[str] = None

class HotPressIn(BaseModel):
    batch_id: str; machine_id: str
    operator_id: Optional[str] = None; operator_name: str = ""
    temp_c: float; pressure_bar: float; press_time_min: int
    pcs_in: int; pcs_out: int

class GradingIn(BaseModel):
    batch_id: str
    grader_id: Optional[str] = None; grader_name: str = ""
    pcs_grade_a: int = 0; pcs_grade_b: int = 0
    pcs_ncg: int = 0; pcs_reject: int = 0
    ncg_reason_code: Optional[str] = None; notes: Optional[str] = None

class PackingIn(BaseModel):
    batch_id: str
    operator_name: str = ""
    table_id: Optional[str] = None
    pcs_in: int = 0; pcs_packed: int = 0; pcs_held: int = 0
    cartons_count: int = 0
    packaging_sku: Optional[str] = None; notes: Optional[str] = None

class ProdAIAnalyze(BaseModel):
    mode: str = "FLEET_ANALYSIS"
    batch_id: Optional[str] = None
    line_id: Optional[str] = None
    days: int = 30

class ProdAIChat(BaseModel):
    messages: list
    line_id: Optional[str] = None
    days: int = 30

# New models
class PurchaseOrderIn(BaseModel):
    po_number: str; customer: str; order_date: str; delivery_date: str = ""
    status: str = "open"; notes: str = ""
    priority: Optional[int] = 2          # 1=High 2=Med 3=Low — cascades into shortfalls + FC prep

class POLineIn(BaseModel):
    po_id: int; product_id: int; quantity: int; unit_price: float = 0
    production_line: str = "P01"; notes: str = ""
    packing_sku_id: Optional[int] = None
    pcs_per_pallet: Optional[int] = None

class POLineUpdate(BaseModel):
    quantity: int; unit_price: float = 0; production_line: str = "P01"; notes: str = ""
    packing_sku_id: Optional[int] = None
    pcs_per_pallet: Optional[int] = None

class BomBuilderIn(BaseModel):
    sku_code: str; sku_name: str
    thickness_mm: Optional[float] = None
    width_mm: Optional[float] = None
    length_mm: Optional[float] = None
    pallet_qty: int = 1
    base_board_code: Optional[str] = None; base_board_qty: Optional[float] = None
    base_board_waste: Optional[float] = None
    face_veneer_code: Optional[str] = None; face_veneer_qty: Optional[float] = None
    face_veneer_waste: Optional[float] = None
    back_veneer_code: Optional[str] = None; back_veneer_qty: Optional[float] = None
    back_veneer_waste: Optional[float] = None
    face_glue_code: Optional[str] = None; face_glue_usage_g: Optional[float] = None
    back_glue_code: Optional[str] = None; back_glue_usage_g: Optional[float] = None
    packing_sku_code: Optional[str] = None

class ProductionOrderIn(BaseModel):
    prod_order_number: str; product_id: int; production_line: str; quantity: int
    po_line_id: Optional[int] = None; po_id: Optional[int] = None
    status: str = "planned"; priority: int = 3
    planned_start: str = ""; planned_end: str = ""; notes: str = ""

class ProductionOrderUpdate(BaseModel):
    prod_order_number: str; production_line: str; quantity: int
    status: str = "planned"; priority: int = 3
    planned_start: str = ""; planned_end: str = ""
    actual_start: str = ""; actual_end: str = ""; notes: str = ""

class BatchMoveIn(BaseModel):
    to_department: str; quantity: int; time_minutes: int = 0
    notes: str = ""; moved_by: str = ""

class BatchSplitIn(BaseModel):
    split_qty: int; reason: str; new_dept: Optional[str] = None
    new_status: str = "ncg"

class LaminatingRecordIn(BaseModel):
    batch_id: int; record_date: str; shift: str = "morning"
    tables_open: int = 1; glue_code: str = ""; glue_qty_kg: float = 0
    planned_qty: int = 0; actual_qty: int = 0; ncg_qty: int = 0
    operator_count: int = 2; time_minutes: int = 480; notes: str = ""

class RepairRecordIn(BaseModel):
    batch_id: int; record_date: str; pair_name: str; repair_type: str
    veneer_species: str = ""; pcs_repaired: int = 0; pcs_rejected: int = 0
    time_minutes: int = 0; notes: str = ""

class SandingRecordIn(BaseModel):
    batch_id: int; record_date: str; operator: str; machine_name: str = ""
    belt_id: str = ""; belt_life_pcs: int = 0; planned_qty: int = 0
    actual_qty: int = 0; ncg_qty: int = 0; ncg_reason: str = ""
    time_minutes: int = 0; notes: str = ""

class GradingRecordIn(BaseModel):
    batch_id: int; record_date: str; total_graded: int = 0
    grade_lg: int = 0; grade_c: int = 0; ncg_qty: int = 0
    send_to_repair: int = 0; send_to_sanding: int = 0
    grader: str = ""; notes: str = ""

class DeptActivityIn(BaseModel):
    batch_id: int; department: str; record_date: str
    planned_qty: int = 0; actual_qty: int = 0; ncg_qty: int = 0
    operator: str = ""; time_minutes: int = 0; veneer_side: str = ""
    extra_data: dict = {}; notes: str = ""

class VeneerConfirmIn(BaseModel):
    face_veneer_id: Optional[int] = None
    back_veneer_id: Optional[int] = None

# ── Dashboard ─────────────────────────────────────────────────
@app.get("/api/dashboard/stats")
def dashboard_stats(): return get_dashboard_stats()

# ── Materials ─────────────────────────────────────────────────
@app.get("/api/materials")
def list_materials(include_formulas: bool = False, type: Optional[str] = None):
    """Raw stocked materials + packing. Glue compound formulas excluded by default."""
    rows = get_all_materials()
    # Phase B: glue_formula placeholder rows no longer exist; the
    # `include_formulas` query param is kept for API back-compat but is a no-op.
    if type:
        rows = [r for r in rows if r.get('type') == type]
    return rows

@app.get("/api/materials/{mid}")
def get_one_material(mid: int):
    m = get_material(mid)
    if not m: raise HTTPException(404,"Material not found")
    return m

@app.post("/api/materials", status_code=201)
def add_material(body: MaterialIn): return create_material(body.dict())

@app.put("/api/materials/{mid}")
def edit_material(mid: int, body: MaterialIn):
    if not get_material(mid): raise HTTPException(404,"Material not found")
    return update_material(mid, body.dict())

@app.delete("/api/materials/{mid}")
def remove_material(mid: int):
    try:
        return delete_material(mid)
    except ValueError as e:
        raise HTTPException(400, str(e))

@app.delete("/api/fg-bom/{sku_code}")
def remove_fg_bom(sku_code: str):
    try:
        return delete_fg_bom(sku_code)
    except ValueError as e:
        raise HTTPException(400, str(e))

# ── Products ──────────────────────────────────────────────────
@app.get("/api/products")
def list_products(): return get_all_products()

@app.post("/api/products", status_code=201)
def add_product(body: ProductIn): return create_product(body.dict())

@app.put("/api/products/{pid}")
def edit_product(pid: int, body: ProductIn):
    if not get_product(pid): raise HTTPException(404,"Product not found")
    return update_product(pid, body.dict())

@app.delete("/api/products/{pid}")
def remove_product(pid: int): delete_product(pid); return {"ok":True}

# ── BOM ───────────────────────────────────────────────────────
@app.get("/api/bom")
def list_bom(): return get_all_bom()

@app.get("/api/bom/product/{pid}")
def get_product_bom(pid: int): return get_bom_for_product(pid)

@app.post("/api/bom", status_code=201)
def add_bom_entry(body: BomIn): return create_bom_entry(body.dict())

@app.put("/api/bom/{bid}")
def edit_bom_entry(bid: int, body: BomUpdate): return update_bom_entry(bid, body.dict())

@app.delete("/api/bom/{bid}")
def remove_bom_entry(bid: int): delete_bom_entry(bid); return {"ok":True}

# ── Production Lines / Departments / Line Flow ────────────────
# Replaces the hardcoded ['P01','P02','P37','PUV','PVS','PSP'], DEPARTMENTS
# list, and LINE_FLOW dict in the frontend. /api/catalog/lines+departments+flow
# is what the frontend fetches once at startup; the others are convenience.
@app.get("/api/catalog/lines")
def catalog_lines(line_type: Optional[str] = None,
                  include_inactive: bool = False):
    return get_manufacturing_lines(active_only=not include_inactive,
                                   line_type=line_type)

@app.get("/api/catalog/departments")
def catalog_departments(include_inactive: bool = False):
    return get_departments(active_only=not include_inactive)

@app.get("/api/catalog/line-flow")
def catalog_line_flow():
    """All line flows as { line_code: [dept_code, ...] }. One round trip."""
    return get_all_line_flows()

@app.get("/api/catalog/lines/{code}/flow")
def catalog_line_flow_one(code: str):
    flow = get_line_flow(code)
    if not flow: return []
    return flow

@app.get("/api/catalog/stations")
def catalog_stations(line_code: Optional[str] = None,
                     department_code: Optional[str] = None,
                     include_inactive: bool = False):
    """Concrete (line, department) stations. line_code='' returns the
    centralised stations (packing/fg_receiving/fg_warehouse) which have
    line_code NULL in the DB."""
    return get_stations(line_code=line_code,
                        department_code=department_code,
                        active_only=not include_inactive)

# ── Machines ──────────────────────────────────────────────────
@app.get("/api/machines")
def list_machines(): return get_all_machines()

@app.post("/api/machines", status_code=201)
def add_machine(body: MachineIn): return create_machine(body.dict())

@app.put("/api/machines/{mid}")
def edit_machine(mid: int, body: MachineIn):
    if not get_machine(mid): raise HTTPException(404,"Machine not found")
    return update_machine(mid, body.dict())

@app.delete("/api/machines/{mid}")
def remove_machine(mid: int): delete_machine(mid); return {"ok":True}

# ── Orders ────────────────────────────────────────────────────
@app.get("/api/orders")
def list_orders(): return get_all_orders()

@app.post("/api/orders", status_code=201)
def add_order(body: OrderIn): return create_order(body.dict())

@app.put("/api/orders/{oid}")
def edit_order(oid: int, body: OrderIn):
    if not get_order(oid): raise HTTPException(404,"Order not found")
    return update_order(oid, body.dict())

@app.delete("/api/orders/{oid}")
def remove_order(oid: int): delete_order(oid); return {"ok":True}

# ── Production Logs ───────────────────────────────────────────
@app.get("/api/production-logs")
def list_production_logs(date: Optional[str] = None): return get_all_production_logs(date_filter=date)

@app.post("/api/production-logs", status_code=201)
def add_production_log(body: ProductionLogIn): return create_production_log(body.dict())

@app.delete("/api/production-logs/{lid}")
def remove_production_log(lid: int): delete_production_log(lid); return {"ok":True}

# ── Reports ───────────────────────────────────────────────────
@app.get("/api/reports")
def list_reports(): return get_all_reports()

@app.post("/api/reports/generate")
def generate_report(body: ReportRequest):
    logs = get_all_production_logs(date_filter=body.date)
    content = generate_production_report(body.date, logs, body.report_type)
    return save_report({"report_date":body.date,"report_type":body.report_type,
                        "title":f"{body.report_type.capitalize()} Report — {body.date}","content":content})

# ── AI ────────────────────────────────────────────────────────
@app.post("/api/ai/bom-query")
def ai_bom_query(body: AIQuery):
    return {"question":body.question,"answer":query_bom(body.question, get_full_bom_context())}

@app.post("/api/ai/capacity-check")
def ai_capacity_check(body: AIQuery):
    return {"question":body.question,"answer":check_capacity(body.question, get_capacity_context())}

@app.post("/api/ai/daily-report")
def ai_daily_report(body: ReportRequest):
    logs = get_all_production_logs(date_filter=body.date)
    report = generate_production_report(body.date, logs, body.report_type)
    return {"date": body.date, "report_type": body.report_type, "report": report}

# ══════════════════════════════════════════════════════════════
# PURCHASE ORDERS
# ══════════════════════════════════════════════════════════════
@app.get("/api/purchase-orders")
def list_purchase_orders(): return get_all_purchase_orders()

@app.get("/api/purchase-orders/{po_id}")
def get_one_purchase_order(po_id: int):
    po = get_purchase_order(po_id)
    if not po: raise HTTPException(404,"PO not found")
    return po

@app.post("/api/purchase-orders", status_code=201)
def add_purchase_order(body: PurchaseOrderIn):
    try:
        return create_purchase_order(body.dict())
    except ValueError as e:
        raise HTTPException(400, str(e))

@app.put("/api/purchase-orders/{po_id}")
def edit_purchase_order(po_id: int, body: PurchaseOrderIn):
    if not get_purchase_order(po_id): raise HTTPException(404,"PO not found")
    return update_purchase_order(po_id, body.dict())

@app.delete("/api/purchase-orders/{po_id}")
def remove_purchase_order(po_id: int): delete_purchase_order(po_id); return {"ok":True}

# ── Customers (rudimentary CRM) ───────────────────────────────
class CustomerIn(BaseModel):
    name: str
    contact_person: str = ""
    phone: str = ""
    email: str = ""
    address: str = ""
    notes: str = ""
    is_active: bool = True

@app.get("/api/customers")
def list_customers(active_only: bool = True): return get_customers(active_only=active_only)

@app.post("/api/customers", status_code=201)
def add_customer(body: CustomerIn):
    try:
        return create_customer(body.dict())
    except ValueError as e:
        raise HTTPException(400, str(e))

@app.put("/api/customers/{cid}")
def edit_customer(cid: int, body: CustomerIn):
    try:
        return update_customer(cid, body.dict())
    except ValueError as e:
        raise HTTPException(400, str(e))

@app.get("/api/customers/{cid}/orders")
def customer_orders(cid: int):
    res = get_customer_orders(cid)
    if 'error' in res: raise HTTPException(404, res['error'])
    return res

@app.get("/api/purchase-orders/{po_id}/lines")
def list_po_lines(po_id: int): return get_po_lines(po_id)

@app.get("/api/purchase-orders/{po_id}/material-readiness")
def po_material_readiness(po_id: int):
    result = get_po_material_readiness(po_id)
    if not result: raise HTTPException(404, "PO not found")
    return result

@app.post("/api/po-lines", status_code=201)
def add_po_line(body: POLineIn): return create_po_line(body.dict())

@app.put("/api/po-lines/{line_id}")
def edit_po_line(line_id: int, body: POLineUpdate): return update_po_line(line_id, body.dict())

@app.delete("/api/po-lines/{line_id}")
def remove_po_line(line_id: int): delete_po_line(line_id); return {"ok":True}

# ══════════════════════════════════════════════════════════════
# PRODUCTION ORDERS
# ══════════════════════════════════════════════════════════════
@app.get("/api/production-orders")
def list_production_orders(po_id: Optional[int] = None): return get_all_production_orders(po_id=po_id)

@app.get("/api/production-orders/{order_id}")
def get_one_production_order(order_id: int):
    o = get_production_order(order_id)
    if not o: raise HTTPException(404,"Production order not found")
    return o

@app.post("/api/production-orders", status_code=201)
def add_production_order(body: ProductionOrderIn): return create_production_order(body.dict())


# ─── VCMX BOMs + production ─────────────────────────────────────
class VcmxBomIn(BaseModel):
    sku_code: str
    sku_name: str
    core_material_id: int
    face_material_id: int
    back_material_id: int
    thickness_mm: float
    width_mm: float
    length_mm: float
    pcs_per_pallet: int
    glue_material_id: Optional[int] = None
    glue_qty_per_panel: Optional[float] = 0
    labour_cost_per_panel: Optional[float] = 0
    notes: Optional[str] = ''

class VcmxBomUpdate(BaseModel):
    sku_name: Optional[str] = None
    core_material_id: Optional[int] = None
    face_material_id: Optional[int] = None
    back_material_id: Optional[int] = None
    thickness_mm: Optional[float] = None
    width_mm: Optional[float] = None
    length_mm: Optional[float] = None
    pcs_per_pallet: Optional[int] = None
    glue_material_id: Optional[int] = None
    glue_qty_per_panel: Optional[float] = None
    labour_cost_per_panel: Optional[float] = None
    notes: Optional[str] = None
    active: Optional[int] = None

class VcmxOrderIn(BaseModel):
    vcmx_bom_id: int
    quantity: int
    production_line: Optional[str] = 'P01'
    priority: Optional[int] = 2
    planned_start: Optional[str] = ''
    planned_end: Optional[str] = ''
    notes: Optional[str] = ''

class VcmxCompleteIn(BaseModel):
    qty_produced: int
    qty_ncg: Optional[int] = 0
    glue_actual_kg: Optional[float] = None
    operator: Optional[str] = ''
    notes: Optional[str] = ''
    close_short: Optional[bool] = False


@app.get("/api/vcmx/boms")
def vcmx_boms_list(active_only: bool = False):
    return list_vcmx_boms(active_only=active_only)

@app.post("/api/vcmx/boms")
def vcmx_boms_create(body: VcmxBomIn):
    try:
        return create_vcmx_bom(
            sku_code=body.sku_code, sku_name=body.sku_name,
            core_material_id=body.core_material_id,
            face_material_id=body.face_material_id,
            back_material_id=body.back_material_id,
            thickness_mm=body.thickness_mm, width_mm=body.width_mm,
            length_mm=body.length_mm, pcs_per_pallet=body.pcs_per_pallet,
            glue_material_id=body.glue_material_id,
            glue_qty_per_panel=body.glue_qty_per_panel or 0,
            labour_cost_per_panel=body.labour_cost_per_panel or 0,
            notes=body.notes or '')
    except ValueError as e:
        raise HTTPException(400, str(e))

@app.patch("/api/vcmx/boms/{bom_id}")
def vcmx_boms_update(bom_id: int, body: VcmxBomUpdate):
    try:
        return update_vcmx_bom(bom_id, {k: v for k, v in body.dict().items() if v is not None})
    except ValueError as e:
        raise HTTPException(400, str(e))

@app.get("/api/vcmx/boms/{bom_id}/check-inputs")
def vcmx_check(bom_id: int, qty: int):
    try:
        return vcmx_check_inputs(bom_id, qty)
    except ValueError as e:
        raise HTTPException(400, str(e))

@app.post("/api/vcmx/orders")
def vcmx_order_create(body: VcmxOrderIn):
    try:
        return create_vcmx_production_order(
            vcmx_bom_id=body.vcmx_bom_id, quantity=body.quantity,
            production_line=body.production_line or 'P01',
            priority=body.priority or 2,
            planned_start=body.planned_start or '',
            planned_end=body.planned_end or '',
            notes=body.notes or '')
    except ValueError as e:
        detail = {'message': str(e), 'shortages': getattr(e, 'shortages', None)}
        raise HTTPException(409 if getattr(e, 'shortages', None) else 400, detail)

@app.get("/api/vcmx/batches")
def vcmx_batches_list(status: Optional[str] = 'open'):
    return list_vcmx_batches(status=status)

@app.get("/api/vcmx/batches/{batch_id}/events")
def vcmx_batch_events(batch_id: int):
    return list_vcmx_batch_events(batch_id)

@app.post("/api/vcmx/batches/{batch_id}/complete")
def vcmx_batch_complete(batch_id: int, body: VcmxCompleteIn):
    try:
        return complete_vcmx_batch(
            batch_id=batch_id, qty_produced=body.qty_produced,
            qty_ncg=body.qty_ncg or 0,
            glue_actual_kg=body.glue_actual_kg,
            operator=body.operator or '',
            notes=body.notes or '',
            close_short=bool(body.close_short))
    except ValueError as e:
        raise HTTPException(400, str(e))


@app.put("/api/production-orders/{order_id}")
def edit_production_order(order_id: int, body: ProductionOrderUpdate): return update_production_order(order_id, body.dict())

@app.patch("/api/production-orders/{order_id}/priority")
def patch_production_order_priority(order_id: int, body: dict):
    """Quick priority-only update — used by batch cards."""
    new_pri = int(body.get('priority', 2))
    if new_pri not in (1, 2, 3):
        raise HTTPException(400, "Priority must be 1 (high), 2 (medium), or 3 (low)")
    conn = get_db()
    conn.execute("UPDATE production_orders SET priority=? WHERE id=?", (new_pri, order_id))
    conn.commit(); conn.close()
    return {"ok": True, "priority": new_pri}

@app.patch("/api/batches/{batch_id}/priority")
def patch_batch_priority(batch_id: int, body: dict):
    """Update priority of the batch's production order via batch ID."""
    new_pri = int(body.get('priority', 2))
    if new_pri not in (1, 2, 3):
        raise HTTPException(400, "Priority must be 1 (high), 2 (medium), or 3 (low)")
    conn = get_db()
    row = conn.execute("SELECT prod_order_id FROM batches WHERE id=?", (batch_id,)).fetchone()
    if not row:
        conn.close(); raise HTTPException(404, "Batch not found")
    conn.execute("UPDATE production_orders SET priority=? WHERE id=?", (new_pri, row['prod_order_id']))
    conn.commit(); conn.close()
    return {"ok": True, "priority": new_pri}

@app.post("/api/production-orders/{order_id}/release")
def release_order(order_id: int):
    result = release_production_order(order_id)
    if not result: raise HTTPException(404,"Production order not found")
    return result

@app.delete("/api/production-orders/{order_id}")
def remove_production_order(order_id: int):
    delete_production_order(order_id)
    return {"ok": True}

@app.get("/api/production-orders/{order_id}/batches")
def list_order_batches(order_id: int): return get_all_batches(prod_order_id=order_id)

# ══════════════════════════════════════════════════════════════
# BATCHES
# ══════════════════════════════════════════════════════════════
@app.get("/api/batches")
def list_batches(department: Optional[str] = None): return get_all_batches(department=department)

@app.get("/api/batches/{batch_id}")
def get_one_batch(batch_id: int):
    b = get_batch(batch_id)
    if not b: raise HTTPException(404,"Batch not found")
    return b

@app.post("/api/batches/{batch_id}/move")
def do_move_batch(batch_id: int, body: BatchMoveIn):
    result = move_batch(batch_id, body.to_department, body.quantity,
                        body.time_minutes, body.notes, body.moved_by)
    if not result: raise HTTPException(404,"Batch not found")
    return result

@app.post("/api/batches/{batch_id}/split")
def do_split_batch(batch_id: int, body: BatchSplitIn):
    result = split_batch(batch_id, body.split_qty, body.reason, body.new_dept, body.new_status)
    if not result: raise HTTPException(400,"Cannot split batch (not found or qty too large)")
    return result

@app.post("/api/batches/{batch_id}/split-by-pcs")
def do_split_batch_pcs(batch_id: int, body: dict):
    """Split a batch by piece count (instead of pallet count). Use after a partial station log."""
    pcs = int(body.get('pcs_to_split', 0))
    reason = body.get('reason', 'Partial completion split')
    new_dept = body.get('new_dept')  # if provided, the split-off batch goes here
    result = split_batch_by_pcs(batch_id, pcs, reason, new_dept=new_dept)
    if not result:
        raise HTTPException(400, "Cannot split — invalid pcs count or batch not found")
    return result

@app.get("/api/batches/{batch_id}/mergeable")
def get_mergeable(batch_id: int):
    """Return sibling batches in the same dept + same prod order that can be merged."""
    return find_mergeable_siblings(batch_id)

@app.post("/api/batches/{batch_id}/merge")
def do_merge_batches(batch_id: int, body: dict):
    """Merge another batch into this one (must share prod_order_id and current_department)."""
    other_id = int(body.get('other_batch_id', 0))
    if not other_id:
        raise HTTPException(400, "other_batch_id is required")
    try:
        return merge_batches(batch_id, other_id)
    except ValueError as e:
        raise HTTPException(400, str(e))

@app.get("/api/batches/{batch_id}/history")
def batch_history(batch_id: int): return get_batch_history(batch_id)

@app.delete("/api/batches/{batch_id}")
def void_batch(batch_id: int):
    delete_batch(batch_id)
    return {"ok": True}

# ══════════════════════════════════════════════════════════════
# PLANNING FLOW
# ══════════════════════════════════════════════════════════════
@app.get("/api/planning/flow")
def planning_flow(): return get_planning_flow()

@app.get("/api/planning/po-matrix")
def po_matrix(): return get_po_flow_matrix()

# ══════════════════════════════════════════════════════════════
# DEPARTMENT RECORDS
# ══════════════════════════════════════════════════════════════
@app.get("/api/dept/laminating")
def list_laminating(batch_id: Optional[int] = None): return get_laminating_records(batch_id)

@app.post("/api/dept/laminating", status_code=201)
def add_laminating(body: LaminatingRecordIn): return create_laminating_record(body.dict())

@app.get("/api/dept/laminating/stats")
def laminating_stats(): return get_laminating_stats()

@app.get("/api/dept/repair")
def list_repair(batch_id: Optional[int] = None): return get_repair_records(batch_id)

@app.post("/api/dept/repair", status_code=201)
def add_repair(body: RepairRecordIn): return create_repair_record(body.dict())

@app.get("/api/dept/repair/stats")
def repair_stats(): return get_repair_stats()

@app.get("/api/dept/sanding")
def list_sanding(batch_id: Optional[int] = None): return get_sanding_records(batch_id)

@app.post("/api/dept/sanding", status_code=201)
def add_sanding(body: SandingRecordIn): return create_sanding_record(body.dict())

@app.get("/api/dept/sanding/stats")
def sanding_stats(): return get_sanding_stats()

@app.get("/api/dept/grading")
def list_grading(batch_id: Optional[int] = None): return get_grading_records(batch_id)

@app.post("/api/dept/grading", status_code=201)
def add_grading(body: GradingRecordIn): return create_grading_record(body.dict())

@app.get("/api/dept/activity")
def list_dept_activity(department: Optional[str] = None, batch_id: Optional[int] = None):
    return get_dept_activities(department=department, batch_id=batch_id)

@app.post("/api/dept/activity", status_code=201)
def add_dept_activity(body: DeptActivityIn): return create_dept_activity(body.dict())

# ══════════════════════════════════════════════════════════════
# BULK UPLOAD
# ══════════════════════════════════════════════════════════════
@app.post("/api/upload/inventory")
async def upload_inventory(file: UploadFile = File(...), mode: str = "add",
                           default_type: str = ""):
    """mode=add: upsert (default). mode=replace: delete rows by code then re-insert.

    default_type: category to apply to any row that doesn't carry its own
    `type` column — set by the Veneers/Boards drop zones (whose templates have
    no type column) so their rows aren't all filed as 'other'. A row's explicit
    `type` always wins.

    Encoding: tries UTF-8 (with BOM), then CP1252 / Windows-1252 (most common
    Excel save format), then latin-1 as a last-resort that never fails.
    Empty rows (no code + no name) are silently skipped — they're typically
    Excel trailing-row artifacts, not real errors.
    """
    content = await file.read()
    for enc in ('utf-8-sig', 'cp1252', 'latin-1'):
        try:
            text = content.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    rows_csv = list(csv.DictReader(io.StringIO(text)))
    rows_csv = [{k.strip().lower().replace(' ','_'): (v.strip() if v else '')
                 for k, v in r.items()} for r in rows_csv]

    # Filter out totally-blank rows (typical Excel artifact after the last
    # real data row) BEFORE counting anything — they're not errors.
    def _has_data(row):
        return any(row.get(k) for k in ('code', 'name', 'acc_code'))
    real_rows = [(i+1, r) for i, r in enumerate(rows_csv) if _has_data(r)]
    blank_skipped = len(rows_csv) - len(real_rows)

    results = []; errors = []
    for src_lineno, row in real_rows:
        if not row.get('name'):
            errors.append(f"Row {src_lineno}: missing 'name' (had code={row.get('code') or '?'})")
            continue
        # Apply the drop-zone's category to rows that don't specify their own.
        if default_type and not (row.get('type') or '').strip():
            row['type'] = default_type
        try:
            r = bulk_upsert_material(row)
            results.append(r)
        except Exception as e:
            errors.append(f"Row {src_lineno} ({row.get('name','')[:40]}): {str(e)}")

    # Replace = mirror: after importing, purge same-category materials that are
    # NOT in this file and are truly unused (no BOM, no stock, no lots, no glue
    # link). Anything still in use is kept and reported. Scope = the categories
    # actually present in the upload, so e.g. a Veneers file never touches boards.
    purge = None
    if mode == "replace" and results:
        from database import purge_unused_materials
        scope_types = {r.get('type') for r in results if r.get('type')}
        keep_codes = {r.get('code') for r in results if r.get('code')}
        keep_codes |= {row.get('code') for _, row in real_rows if row.get('code')}
        purge = purge_unused_materials(scope_types, keep_codes)

    out = {
        "processed":      len(results),
        "skipped_blank":  blank_skipped,
        "errors":         errors,
        "results":        results,
        "mode":           mode,
    }
    if purge is not None:
        out["purged"]       = purge["deleted"]
        out["purged_count"] = len(purge["deleted"])
        out["kept_in_use"]  = purge["kept_in_use"]
    return out

@app.post("/api/upload/bom")
async def upload_bom(file: UploadFile = File(...), mode: str = "add"):
    content = await file.read()
    try:
        text = content.decode('utf-8-sig')
    except Exception:
        text = content.decode('latin-1')
    all_rows_raw = list(csv.DictReader(io.StringIO(text)))
    if mode == "replace":
        conn = get_db()
        skus_in_csv = [r.get('product_sku','').strip() for r in all_rows_raw if r.get('product_sku','').strip()]
        for sku_code in set(skus_in_csv):
            prod = conn.execute("SELECT id FROM products WHERE sku=?", (sku_code,)).fetchone()
            if prod:
                conn.execute("DELETE FROM bom WHERE product_id=?", (prod['id'],))
        conn.commit(); conn.close()
    results = []; errors = []
    for i, row in enumerate(all_rows_raw, 1):
        row = {k.strip().lower().replace(' ','_'): v.strip() for k,v in row.items()}
        sku = row.get('product_sku', '').strip()
        if not sku:
            errors.append(f"Row {i}: missing product_sku"); continue

        # ── New flat format: one row per SKU, component codes in columns ──
        if 'base_board_code' in row or 'face_veneer_code' in row:
            try:
                ppu = int(row.get('pieces_per_unit') or 1)
            except ValueError:
                ppu = 1
            try:
                base_qty = int(row.get('base_board_qty') or ppu)
            except ValueError:
                base_qty = ppu

            def _qty(key, default):
                try: return float(row.get(key) or default)
                except ValueError: return float(default)

            face_vnr_qty  = _qty('face_veneer_qty',  ppu)
            back_vnr_qty  = _qty('back_veneer_qty',  ppu)
            face_glue_qty = _qty('face_glue_qty',    1)
            back_glue_qty = _qty('back_glue_qty',    1)

            components = []
            if row.get('base_board_code'):
                components.append({'material_code': row['base_board_code'], 'qty': base_qty,      'veneer_role': ''})
            if row.get('face_veneer_code'):
                components.append({'material_code': row['face_veneer_code'], 'qty': face_vnr_qty, 'veneer_role': 'face'})
            if row.get('face_glue_code'):
                components.append({'material_code': row['face_glue_code'],  'qty': face_glue_qty, 'veneer_role': 'face'})
            if row.get('back_veneer_code'):
                components.append({'material_code': row['back_veneer_code'], 'qty': back_vnr_qty, 'veneer_role': 'back'})
            if row.get('back_glue_code'):
                components.append({'material_code': row['back_glue_code'],  'qty': back_glue_qty, 'veneer_role': 'back'})

            for comp in components:
                bom_data = {
                    'product_sku': sku,
                    'material_code': comp['material_code'],
                    'material_name': comp['material_code'],  # fallback: name = code
                    'veneer_role': comp['veneer_role'],
                    'qty_per_unit': comp['qty'],
                    'waste_factor': float(row.get('waste_factor') or 0.05),
                    'notes': row.get('notes', ''),
                }
                r = bulk_upsert_bom(bom_data)
                if 'error' in r:
                    errors.append(f"Row {i} ({sku}/{comp['material_code']}): {r['error']}")
                else:
                    results.append(r)

        # ── Legacy format: one row per material ──
        else:
            if not row.get('material_name'):
                errors.append(f"Row {i}: missing material_name"); continue
            try:
                r = bulk_upsert_bom(row)
                if 'error' in r:
                    errors.append(f"Row {i}: {r['error']}")
                else:
                    results.append(r)
            except Exception as e:
                errors.append(f"Row {i}: {str(e)}")
    return {"processed": len(results), "errors": errors, "results": results, "mode": mode}

def _esc_csv(v):
    if v is None: return ''
    s = str(v)
    if ',' in s or '"' in s or '\n' in s:
        return '"' + s.replace('"','""') + '"'
    return s

@app.get("/api/export/materials/veneers")
def export_veneers():
    """Export all veneer_sheet materials — matches the veneer upload template format."""
    conn = get_db()
    rows = conn.execute("""
        SELECT code, COALESCE(acc_code,'') AS acc_code,
               name, COALESCE(name_th,'') AS name_th,
               COALESCE(species,'') AS species, COALESCE(cut_type,'') AS cut_type,
               COALESCE(grade,'') AS grade, COALESCE(matching,'') AS matching,
               COALESCE(face_back,'') AS face_back,
               thickness_mm, width_mm, length_mm, COALESCE(fsc,'') AS fsc,
               COALESCE(auto_glue_code,'') AS auto_glue_code,
               COALESCE(unit,'') AS unit,
               COALESCE(current_stock,0) AS current_stock,
               COALESCE(fc_stock,0)      AS fc_stock,
               COALESCE(wlwh_stock,0)    AS wlwh_stock,
               COALESCE(reorder_point,0) AS min_stock,
               COALESCE(unit_cost, COALESCE(price,0)) AS unit_cost,
               COALESCE(supplier,'') AS supplier
        FROM materials WHERE type='veneer_sheet' ORDER BY species, code
    """).fetchall()
    conn.close()
    header = ("code,acc_code,name,name_th,species,cut_type,grade,matching,face_back,"
              "thickness_mm,width_mm,length_mm,fsc,auto_glue_code,unit,"
              "current_stock,fc_stock,wlwh_stock,min_stock,unit_cost,supplier")
    lines = [header] + [",".join(_esc_csv(c) for c in r) for r in rows]
    return Response(content=("\n".join(lines)+"\n").encode("utf-8"), media_type="text/csv",
                    headers={"Content-Disposition": "attachment; filename=veneers_export.csv"})

@app.get("/api/export/materials/boards")
def export_boards():
    """Export all core_board materials — matches the board upload template format."""
    conn = get_db()
    rows = conn.execute("""
        SELECT code, COALESCE(acc_code,'') AS acc_code,
               name, COALESCE(name_th,'') AS name_th,
               COALESCE(board_type,'') AS board_type,
               COALESCE(glue_type,'')  AS glue_type,
               thickness_mm, width_mm, length_mm, COALESCE(fsc,'') AS fsc,
               COALESCE(unit,'') AS unit,
               COALESCE(current_stock,0) AS current_stock,
               COALESCE(fc_stock,0)      AS fc_stock,
               COALESCE(wlwh_stock,0)    AS wlwh_stock,
               COALESCE(reorder_point,0) AS min_stock,
               COALESCE(unit_cost, COALESCE(price,0)) AS unit_cost,
               COALESCE(supplier,'') AS supplier
        FROM materials WHERE type='core_board' ORDER BY board_type, code
    """).fetchall()
    conn.close()
    header = ("code,acc_code,name,name_th,board_type,glue_type,thickness_mm,width_mm,length_mm,fsc,"
              "unit,current_stock,fc_stock,wlwh_stock,min_stock,unit_cost,supplier")
    lines = [header] + [",".join(_esc_csv(c) for c in r) for r in rows]
    return Response(content=("\n".join(lines)+"\n").encode("utf-8"), media_type="text/csv",
                    headers={"Content-Disposition": "attachment; filename=boards_export.csv"})

@app.get("/api/export/materials/consumables")
def export_consumables():
    """Export everything that isn't a Board, Veneer or VCMX substrate — i.e.
    Consumable (adhesive), Glue and Additives (glue_formula), Packing, and Others.
    Includes dimensions for packing materials and Thai names + accounting codes."""
    conn = get_db()
    rows = conn.execute("""
        SELECT code, COALESCE(acc_code,'') AS acc_code,
               name, COALESCE(name_th,'') AS name_th,
               COALESCE(type,'') AS type, COALESCE(unit,'') AS unit,
               thickness_mm, width_mm, length_mm,
               COALESCE(current_stock,0) AS current_stock,
               COALESCE(fc_stock,0)      AS fc_stock,
               COALESCE(wlwh_stock,0)    AS wlwh_stock,
               COALESCE(reorder_point,0) AS min_stock,
               COALESCE(unit_cost, COALESCE(price,0)) AS unit_cost,
               COALESCE(supplier,'') AS supplier
        FROM materials
        WHERE type NOT IN ('veneer_sheet','core_board','vcmx')
        ORDER BY type, code
    """).fetchall()
    conn.close()
    header = ("code,acc_code,name,name_th,type,unit,thickness_mm,width_mm,length_mm,"
              "current_stock,fc_stock,wlwh_stock,min_stock,unit_cost,supplier")
    lines = [header] + [",".join(_esc_csv(c) for c in r) for r in rows]
    return Response(content=("\n".join(lines)+"\n").encode("utf-8"), media_type="text/csv",
                    headers={"Content-Disposition": "attachment; filename=consumables_export.csv"})

@app.get("/api/export/materials")
def export_materials():
    """Export every material (excluding VCMX produced substrates) as one flat CSV."""
    conn = get_db()
    rows = conn.execute("""
        SELECT code, COALESCE(acc_code,'') AS acc_code,
               name, COALESCE(name_th,'') AS name_th,
               type, COALESCE(unit,'') AS unit,
               COALESCE(current_stock,0) AS current_stock,
               COALESCE(fc_stock,0)      AS fc_stock,
               COALESCE(wlwh_stock,0)    AS wlwh_stock,
               COALESCE(reorder_point,0) AS min_stock,
               COALESCE(unit_cost, COALESCE(price,0)) AS unit_cost,
               COALESCE(supplier,'') AS supplier
        FROM materials WHERE type != 'vcmx' ORDER BY type, code
    """).fetchall()
    conn.close()
    header = ("code,acc_code,name,name_th,type,unit,"
              "current_stock,fc_stock,wlwh_stock,min_stock,unit_cost,supplier")
    lines = [header] + [",".join(_esc_csv(c) for c in r) for r in rows]
    return Response(content=("\n".join(lines)+"\n").encode("utf-8"), media_type="text/csv",
                    headers={"Content-Disposition": "attachment; filename=materials_export.csv"})

@app.get("/api/export/bom")
def export_bom():
    """Export all BOM as flat CSV (one row per FG SKU)."""
    skus = get_structured_bom()
    lines = ["product_sku,sku_name,pieces_per_unit,thickness_mm,width_mm,length_mm,"
             "base_board_code,base_board_qty,"
             "face_veneer_code,face_veneer_qty,"
             "face_glue_code,face_glue_usage_g,"
             "back_veneer_code,back_veneer_qty,"
             "back_glue_code,back_glue_usage_g,"
             "packing_sku_code"]
    def v(x): return str(x) if x is not None else ""
    def esc(x): return '"'+str(x or '').replace('"','""')+'"'
    for s in skus:
        bb = s.get('base_board') or {}
        fv = s.get('face_veneer') or {}
        bv = s.get('back_veneer') or {}
        fg = s.get('face_glue') or {}
        bg = s.get('back_glue') or {}
        pk = s.get('packing') or {}
        lines.append(",".join([
            esc(s['sku_code']), esc(s['sku_name']), v(s['pallet_qty']),
            v(s.get('thickness_mm','')), v(s.get('width_mm','')), v(s.get('length_mm','')),
            esc(bb.get('code','')), v(bb.get('qty','')),
            esc(fv.get('code','')), v(fv.get('qty','')),
            esc(fg.get('code','')), v(fg.get('usage_g_per_face','')),
            esc(bv.get('code','')), v(bv.get('qty','')),
            esc(bg.get('code','')), v(bg.get('usage_g_per_face','')),
            esc(pk.get('code','')),
        ]))
    content = "\n".join(lines) + "\n"
    return Response(content=content.encode("utf-8"), media_type="text/csv",
                    headers={"Content-Disposition": "attachment; filename=bom_export.csv"})

def _csv_response(rows, filename):
    content = "\n".join(rows) + "\n"
    return Response(content=content.encode("utf-8"), media_type="text/csv",
                    headers={"Content-Disposition": f"attachment; filename={filename}"})

@app.get("/api/upload/template/inventory")
def inventory_template():
    """Generic 'all materials' template — kept for backward compatibility."""
    rows = [
        "code,name,type,unit,current_stock,reorder_point,unit_cost,supplier",
        "MDF-18,MDF 18mm 4x8ft,core_board,sheet,500,100,285.00,Thai MDF Co.",
        "VNR-OAK-A,Oak Veneer (Grade A),veneer_sheet,sheet,200,50,520.00,Euro Veneer Ltd.",
        "ADH-HP-25,Hot Press Adhesive 25kg,adhesive,bag,40,10,890.00,Chem Thai Co.",
    ]
    return _csv_response(rows, "inventory_template.csv")

@app.get("/api/upload/template/veneers")
def veneers_template():
    """Veneer template — adds acc_code, name_th, fc_stock, auto_glue_code.
    `min_stock` is the trigger level for low-stock alerts (formerly reorder_point)."""
    rows = [
        "code,acc_code,name,name_th,species,cut_type,grade,matching,face_back,thickness_mm,width_mm,length_mm,fsc,auto_glue_code,unit,current_stock,fc_stock,min_stock,unit_cost,supplier",
        "VNR-OAK-A-30,VN-001,W.OAK 0.3mm 1232x2452 (Grade A) Book,วีเนียร์โอ๊คขาว 0.3mm,W.OAK,QC,A,Book,Face,0.3,1232,2452,FSC,Glue 1,Pcs,200,0,50,520.00,Euro Veneer Ltd.",
        "VNR-OAK-B-30,VN-002,W.OAK 0.3mm 1232x2452 (Grade B) Slip,วีเนียร์โอ๊คขาว 0.3mm B,W.OAK,QC,B,Slip,Back,0.3,1232,2452,,Glue 2,Pcs,150,0,40,420.00,Euro Veneer Ltd.",
        "VNR-TEAK-30,VN-003,TEAK DS 0.3mm 1232x2452 (Sound),วีเนียร์สัก 0.3mm,TEAK,DS,Sound,Random,Face,0.3,1232,2452,FSC,Glue 6,Pcs,100,0,30,680.00,Asia Veneer Co.",
        "VNR-WBIRCH-25,VN-004,W.BIRCH 0.25mm 660x2200 #4 Sound,วีเนียร์เบิร์ชขาว 0.25mm,W.BIRCH,DS,#4,Random,Both,0.25,660,2200,,Glue 9,Pcs,80,0,25,250.00,Euro Veneer Ltd.",
        "VNR-MAPLE-A-30,VN-005,W.MAPLE 0.3mm 1232x2452 (Grade A) Book,วีเนียร์เมเปิ้ลขาว 0.3mm,W.MAPLE,QC,A,Book,Face,0.3,1232,2452,FSC,Glue 1,Pcs,60,0,20,610.00,Euro Veneer Ltd.",
    ]
    return _csv_response(rows, "veneers_template.csv")

@app.get("/api/upload/template/boards")
def boards_template():
    """Board template — adds acc_code, name_th, fc_stock columns.
    `min_stock` triggers low-stock alerts (formerly reorder_point)."""
    rows = [
        "code,acc_code,name,name_th,board_type,glue_type,thickness_mm,width_mm,length_mm,fsc,unit,current_stock,fc_stock,min_stock,unit_cost,supplier",
        "BMCN2511,BD-001,MDF CARB P2 2.5mm 1232x2452,MDF 2.5mm,MDF,CARB P2,2.5,1232,2452,,sheet,500,0,100,285.00,Thai MDF Co.",
        "BMCN1801,BD-002,MDF CARB P2 18mm 1245x2465,MDF 18mm,MDF,CARB P2,18,1245,2465,FSC,Pcs,250,0,80,580.00,Thai MDF Co.",
        "BVCN1801,BD-003,VC PLYWOOD CARB P2 18mm 1232x2452,ไม้อัด VC 18mm,VC PLY,CARB P2,18,1232,2452,FSC,Pcs,180,0,60,720.00,Local Plywood",
        "BPCN1801,BD-004,PB CARB P2 18mm 1220x2440,ปาร์ติเคิลบอร์ด 18mm,PB,CARB P2,18,1220,2440,,sheet,300,0,80,220.00,Thai MDF Co.",
        "BVCN0420,BD-005,VC PLYWOOD MR 4.2mm 1232x2452,ไม้อัด VC 4.2mm,VC PLY,MR,4.2,1232,2452,,Pcs,180,0,60,425.00,Local Plywood",
    ]
    return _csv_response(rows, "boards_template.csv")

@app.get("/api/upload/template/consumables")
def consumables_template():
    """Consumables / Glue and Additives / Packing / Others template.
    Adds acc_code, name_th, fc_stock, dimensions (for packing items)."""
    rows = [
        "code,acc_code,name,name_th,type,unit,thickness_mm,width_mm,length_mm,current_stock,fc_stock,min_stock,unit_cost,supplier",
        "UREA-RESIN,GA-001,Urea Formaldehyde Resin E0,กาวยูเรียเรซิน,glue_formula,kg,,,,4000,0,500,19.70,Chem Thai Co.",
        "LATEX-G312,GA-002,Latex G312,กาวลาเท็ก312,glue_formula,kg,,,,400,0,80,94.50,Chem Thai Co.",
        "LATEX-LIQ,GA-003,Liquid Latex,น้ำยางลาเท็กซ์,glue_formula,kg,,,,300,0,60,79.00,Chem Thai Co.",
        "WHEAT-FLOUR,GA-004,Wheat Flour Filler,แป้งสาลี,glue_formula,kg,,,,300,0,60,15.50,Local Mill",
        "TITANIUM-PWD,GA-005,Titanium Dioxide Powder,ไทเทเนียมไดออกไซด์,glue_formula,kg,,,,200,0,40,142.00,Chem Supply TH",
        "OXIDE-YELLOW,GA-006,Yellow Iron Oxide,ออกไซด์เหลือง,glue_formula,kg,,,,40,0,10,73.00,Chem Supply TH",
        "OXIDE-RED,GA-007,Red Iron Oxide,ออกไซด์แดง,glue_formula,kg,,,,30,0,10,80.00,Chem Supply TH",
        "FLUORESCENT,GA-008,Fluorescent Brightener,สารเรืองแสง,glue_formula,kg,,,,30,0,10,11.00,Chem Supply TH",
        "CON-SB150,CN-001,Sanding Belt 150-grit,ผ้าทรายสายพาน 150,adhesive,pcs,,,,60,0,20,45.00,Abrasive Pro",
        "CON-SB220,CN-002,Sanding Belt 220-grit,ผ้าทรายสายพาน 220,adhesive,pcs,,,,60,0,20,50.00,Abrasive Pro",
        "EB-OAK-22,CN-003,Oak Edge Banding 22mm 50m,เอจแบนดิ้งโอ๊ค,adhesive,roll,,,,40,0,15,380.00,Edge Pro TH",
        "CON-RPT,CN-004,Repair Putty 1kg,ผงโป๊ว 1kg,adhesive,jar,,,,20,0,5,180.00,Local Hardware",
        "PKG-SW,PK-001,Stretch Wrap 500m,พลาสติกห่อ 500m,packing,roll,,500,500000,15,0,5,290.00,Pack Supply Co.",
        "PKG-CG,PK-002,Cardboard Corner Guard,กระดาษกันกระแทกมุม,packing,pcs,,50,1200,500,0,100,2.50,Pack Supply Co.",
        "PKG-TP,Packing Tape 48mm,packing,roll,80,20,35.00,Pack Supply Co.",
    ]
    return _csv_response(rows, "consumables_template.csv")

@app.get("/api/upload/template/wip")
def wip_template():
    """Opening work-in-progress template — one in-flight job per row, placed at
    its current station. sku_code must match an existing finished-good SKU;
    line is the manufacturing line; current_station is the department it's at.

    Finished goods: set current_station=fg_warehouse. Two optional columns
    apply only to FG rows — `pcs` (actual pieces; wins over pallets×pcs/pallet)
    and `location` (FG or WLWH overflow). They're ignored for in-flight rows."""
    rows = [
        "sku_code,line,quantity,current_station,batch_ref,po_ref,pcs,location",
        "3ENR24NF1,P01,120,laminating,WIP-A12,POD250389,,",
        "3ENR28NF1,P01,80,sanding,WIP-A13,,,",
        "3ENR30NF1,P02,200,grading,WIP-B07,POD20056,,",
        "3ENR32NF1,P37,60,packing,WIP-C01,,,",
        "3ENR24NF1,P01,40,fg_warehouse,FG-2001,POD250389,2000,FG",
        "3ENR28NF1,P02,15,fg_warehouse,FG-2002,,720,WLWH",
    ]
    return _csv_response(rows, "opening_wip_template.csv")

@app.post("/api/upload/wip")
async def upload_wip(file: UploadFile = File(...), mode: str = "validate"):
    """Validate (mode=validate, default) or import (mode=commit) opening WIP.
    Always returns a per-row report with errors + closest-match suggestions so
    bad SKU/line/station names are caught before anything is written."""
    content = await file.read()
    text = None
    for enc in ('utf-8-sig', 'cp1252', 'latin-1'):
        try:
            text = content.decode(enc); break
        except UnicodeDecodeError:
            continue
    rows_csv = list(csv.DictReader(io.StringIO(text or '')))
    rows_csv = [{(k or '').strip().lower().replace(' ', '_'): (v.strip() if v else '')
                 for k, v in r.items()} for r in rows_csv]
    # drop fully-blank rows (Excel trailing artifact)
    rows_csv = [r for r in rows_csv if any(r.get(k) for k in
                ('sku_code', 'line', 'quantity', 'current_station', 'batch_ref',
                 'po_ref', 'pcs', 'location'))]
    return import_wip_batches(rows_csv, commit=(mode == 'commit'),
                              created_by='wip_import')

@app.post("/api/upload/po-pdf")
async def upload_po_pdf(file: UploadFile = File(...)):
    """Upload a PDF purchase order and extract its data using Claude AI.
    Validates each SKU against ERP products and BOM, flagging any missing entries."""
    if not file.filename.lower().endswith('.pdf'):
        raise HTTPException(400, "Only PDF files are accepted")
    pdf_bytes = await file.read()

    # Pass known SKUs so Claude can match them
    products = get_all_products()
    known_skus = [p['sku'] for p in products if p.get('sku')]

    result = extract_po_from_pdf(pdf_bytes, known_skus=known_skus)
    if 'error' in result:
        raise HTTPException(422, result['error'])

    # Validate each line SKU against products + BOM
    # Check bom_lines/skus system (BOM builder) for SKUs that have a BOM
    import sqlite3 as _sqlite3
    _db = _sqlite3.connect(str(__import__('pathlib').Path(__file__).parent.parent / 'erp.db'))
    bom_skus_rows = _db.execute(
        "SELECT DISTINCT s.code FROM skus s WHERE EXISTS (SELECT 1 FROM bom_lines bl WHERE bl.sku_id=s.id)"
    ).fetchall()
    _db.close()
    bom_skus = {r[0] for r in bom_skus_rows}
    # Also include legacy bom table
    bom_all = get_all_bom()
    bom_skus |= {b['sku'] for b in bom_all if b.get('sku')}
    product_skus = {p['sku']: p for p in products}

    # ── Validate each line and attach product_id ─────────────────────────────
    # Lines are kept exactly as extracted (one per PDF row).
    # Same SKU can appear multiple times with different pallet sizes — that's valid.
    raw_lines = result.get('lines', [])
    sku_warnings = []
    warned_skus = set()  # only warn once per unique SKU
    for i, line in enumerate(raw_lines):
        sku = (line.get('sku') or '').strip()
        if sku in product_skus:
            line['product_id'] = product_skus[sku]['id']
        if not sku:
            sku_warnings.append({
                "line": i + 1, "sku": "",
                "status": "missing_sku",
                "message": f"Line {i+1} has no SKU — please check the PDF or enter manually."
            })
        elif sku not in product_skus:
            if sku not in warned_skus:
                sku_warnings.append({
                    "line": i + 1, "sku": sku,
                    "status": "unknown_product",
                    "message": f"SKU '{sku}' not found in ERP products. Please add the product first."
                })
            warned_skus.add(sku)
        elif sku not in bom_skus:
            if sku not in warned_skus:
                sku_warnings.append({
                    "line": i + 1, "sku": sku,
                    "status": "missing_bom",
                    "message": f"SKU '{sku}' exists as a product but has no BOM. Please set up the BOM before creating a production order.",
                    "product_name": product_skus[sku].get('name', '')
                })
            warned_skus.add(sku)
        else:
            line['bom_status'] = 'ok'

    result['sku_warnings'] = sku_warnings
    result['has_warnings'] = len(sku_warnings) > 0
    result['known_skus'] = known_skus
    return result


@app.post("/api/purchase-orders/{po_id}/import-pdf-lines", status_code=201)
def import_pdf_lines(po_id: int, body: dict):
    """Bulk-import PDF lines into a PO as individual rows (one per PDF line).
    Same SKU with different pallet sizes creates separate po_lines — this is intentional.
    Body: { lines: [{ product_id, quantity(pallets), pcs_per_pallet, unit_price, notes }] }
    Duplicate-prevention: skips a line if an identical (product_id, quantity, pcs_per_pallet)
    already exists in this PO — so re-uploading the same PDF won't double-import.
    """
    conn = __import__('sqlite3').connect(
        str(__import__('pathlib').Path(__file__).parent.parent / 'erp.db'))
    conn.row_factory = __import__('sqlite3').Row

    # Existing lines as (product_id, quantity, pcs_per_pallet) tuples to detect exact duplicates
    existing = {
        (r[0], r[1], r[2])
        for r in conn.execute(
            "SELECT product_id, quantity, pcs_per_pallet FROM po_lines WHERE po_id=?",
            (po_id,)).fetchall()
    }

    created = []
    skipped = []
    for ln in body.get('lines', []):
        pid = ln.get('product_id')
        if not pid:
            skipped.append({'reason': 'no product_id'})
            continue
        qty      = int(ln.get('quantity') or 0)
        ppp      = int(ln['pcs_per_pallet']) if ln.get('pcs_per_pallet') else None
        sig      = (pid, qty, ppp)
        if sig in existing:
            skipped.append({'reason': 'exact duplicate', 'product_id': pid, 'qty': qty, 'ppp': ppp})
            continue
        cur = conn.execute(
            "INSERT INTO po_lines (po_id,product_id,quantity,unit_price,production_line,notes,pcs_per_pallet) "
            "VALUES (?,?,?,?,?,?,?)",
            (po_id, pid, qty,
             float(ln.get('unit_price') or 0),
             ln.get('production_line', 'P01'),
             ln.get('notes', ''),
             ppp)
        )
        existing.add(sig)
        created.append(cur.lastrowid)

    conn.commit()
    conn.close()
    return {"created": len(created), "skipped": len(skipped), "skipped_detail": skipped}

# ══════════════════════════════════════════════════════════════
# FC DEPARTMENT — MATERIAL CHECK
# ══════════════════════════════════════════════════════════════
@app.get("/api/fc/batches")
def fc_batches(): return get_all_fc_batches()

@app.get("/api/fc/material-check/{prod_order_id}")
def fc_material_check(prod_order_id: int):
    result = get_fc_material_requirements(prod_order_id)
    if not result: raise HTTPException(404, "Production order not found")
    return result

@app.post("/api/production-orders/{order_id}/confirm-veneer")
def confirm_veneer(order_id: int, body: VeneerConfirmIn):
    result = confirm_veneer_selection(order_id, body.face_veneer_id, body.back_veneer_id)
    if not result: raise HTTPException(404, "Production order not found")
    return result

# ══════════════════════════════════════════════════════════════
# LINE BOARD
# ══════════════════════════════════════════════════════════════
@app.get("/api/planning/line-board")
def line_board(production_line: Optional[str] = None):
    return get_line_board(production_line)

@app.get("/api/upload/template/bom")
def bom_template():
    # Flat BOM format: one row per finished SKU
    # material codes must match codes in inventory
    # face_veneer_qty / back_veneer_qty = sheets of veneer per pallet (defaults to pieces_per_unit if blank)
    # back_veneer_code and back_glue_code are optional — leave blank if TBD (FC confirms per order)
    rows = [
        "product_sku,pieces_per_unit,base_board_code,base_board_qty,face_veneer_code,face_veneer_qty,face_glue_code,face_glue_qty,back_veneer_code,back_veneer_qty,back_glue_code,back_glue_qty,notes",
        # Oak 18mm — different face/back veneer grade (veneer qty includes 5% waste)
        "VNR-OAK-18,240,MDF-18,240,VNR-OAK-A,252,ADH-HP-25,10,VNR-OAK-B,252,,10,Grade A face / Grade B back",
        # Oak 12mm
        "VNR-OAK-12,240,MDF-12,240,VNR-OAK-A,252,ADH-HP-25,10,VNR-OAK-B,252,,10,",
        # Teak 18mm — same veneer both sides
        "VNR-TEAK-18,240,MDF-18,240,VNR-TEAK,254,ADH-HP-25,10,VNR-TEAK,254,,10,Same species face and back",
        # Walnut 18mm — premium face with oak back
        "VNR-WAL-18,240,MDF-18,240,VNR-WAL,262,ADH-HP-25,10,VNR-OAK-B,252,,10,Walnut face / Oak B back",
        # Engineered oak — back veneer TBD (FC confirms per order)
        "VNR-OAK-ENG-18,240,MDF-18,240,VNR-OAK-ENG,252,ADH-HP-25,10,,,,, Back veneer TBD per order",
    ]
    content = "\n".join(rows) + "\n"
    return Response(content=content.encode("utf-8"), media_type="text/csv",
                    headers={"Content-Disposition": "attachment; filename=bom_template.csv"})

# ══════════════════════════════════════════════════════════════
# PROPER BOM MODULE — /api/skus  /api/bom-materials  /api/glue  /api/packing
# ══════════════════════════════════════════════════════════════

# ── Finished Goods (FG) — canonical FG list from skus table ──
@app.get("/api/fg")
def list_fg(search: Optional[str] = None):
    """All finished goods SKUs from the proper skus table."""
    return get_all_skus(search)

@app.get("/api/fg/{code}")
def fg_detail_route(code: str):
    s = get_sku(code)
    if not s: raise HTTPException(404, f"FG SKU '{code}' not found")
    return s

@app.get("/api/fg/{code}/bom")
def fg_structured_bom(code: str):
    """Structured BOM for one FG: base board, face/back veneer, glue formulas, packing."""
    r = get_structured_bom(code)
    if not r: raise HTTPException(404, f"FG SKU '{code}' not found")
    return r

@app.get("/api/fg-bom")
def fg_bom_all(search: Optional[str] = None):
    """Structured BOM for all FG SKUs (or filtered by search)."""
    rows = get_structured_bom()
    if search:
        s = search.lower()
        rows = [r for r in rows if s in r['sku_code'].lower() or s in (r['sku_name'] or '').lower()]
    return rows

@app.post("/api/bom-builder", status_code=201)
def bom_builder_create(body: BomBuilderIn):
    """Create or update a full BOM via the BOM Builder UI."""
    return save_bom_for_sku(body.dict())

@app.put("/api/bom-builder/{sku_code}")
def bom_builder_update(sku_code: str, body: BomBuilderIn):
    data = body.dict()
    data['sku_code'] = sku_code
    return save_bom_for_sku(data)

@app.get("/api/skus")
def list_skus(search: Optional[str] = None):
    return get_all_skus(search)

@app.get("/api/skus/{code}")
def sku_detail(code: str):
    s = get_sku(code)
    if not s: raise HTTPException(404, f"SKU '{code}' not found")
    return s

@app.get("/api/skus/{code}/bom")
def sku_bom(code: str):
    lines = get_sku_bom(code)
    if not lines and not get_sku(code):
        raise HTTPException(404, f"SKU '{code}' not found")
    return {"sku_code": code, "lines": lines}

@app.get("/api/skus/{code}/cost")
def sku_cost(code: str):
    rows = get_sku_cost(code)
    if not rows and not get_sku(code):
        raise HTTPException(404, f"SKU '{code}' not found")
    total = sum(r.get('section_total') or 0 for r in rows)
    return {"sku_code": code, "sections": rows, "total": round(total, 4)}

@app.get("/api/packing-skus")
def list_packing(): return get_all_packing_skus()

@app.get("/api/packing-skus/{code}")
def packing_detail(code: str):
    p = get_packing_sku(code)
    if not p: raise HTTPException(404, f"Packing SKU '{code}' not found")
    return p

# ── Glue Recipe — list-with-ingredients view ───────────────────────────
# The bare /api/glue-recipes CRUD (raw rows, create/patch/delete) lives further
# down in the file. This endpoint returns the same recipes but each row carries
# its ingredient breakdown — used by the BOM → Glue Formulas editor.
@app.get("/api/glue-recipes/with-ingredients")
def list_glue_recipes_with_ingredients_ep(kind: Optional[str] = None):
    return get_glue_recipes_with_ingredients(kind=kind)

# ── Packing SKU CRUD ──────────────────────────────────────────────────────────

class PackingSkuIn(BaseModel):
    code: str
    name: str = ""
    customer: str = ""
    notes: str = ""

class PackingLineIn(BaseModel):
    material_code: str
    qty: float = 1.0
    qty_unit: str = "pallet"
    seq: int = 0
    notes: str = ""

@app.get("/api/packing-skus-full")
def list_packing_full():
    return get_packing_skus_with_lines()

@app.post("/api/packing-skus")
def create_packing_sku(body: PackingSkuIn):
    return save_packing_sku(body.dict())

@app.put("/api/packing-skus/{pid}")
def update_packing_sku_ep(pid: int, body: PackingSkuIn):
    conn = get_db()
    row = conn.execute("SELECT code FROM packing_skus WHERE id=?", (pid,)).fetchone()
    conn.close()
    if not row: raise HTTPException(404, "Packing spec not found")
    d = body.dict(); d['code'] = row['code']
    return save_packing_sku(d)

@app.delete("/api/packing-skus/{pid}")
def delete_packing_sku_ep(pid: int):
    delete_packing_sku(pid)
    return {"ok": True}

@app.post("/api/packing-skus/{pid}/lines")
def add_packing_line_ep(pid: int, body: PackingLineIn):
    try:
        add_packing_line(pid, body.material_code, body.qty, body.qty_unit, body.seq, body.notes)
        return {"ok": True}
    except ValueError as e:
        raise HTTPException(400, str(e))

@app.delete("/api/packing-lines/{lid}")
def delete_packing_line_ep(lid: int):
    delete_packing_line(lid)
    return {"ok": True}

class PriceUpdateIn(BaseModel):
    price: float

@app.put("/api/bom-materials/{code}/price")
def update_price(code: str, body: PriceUpdateIn):
    """Update a material price — automatically re-syncs glue formula costs."""
    r = update_material_price(code, body.price)
    if not r: raise HTTPException(404, f"Material '{code}' not found")
    return r

@app.get("/api/bom-materials/{code}/usage")
def material_usage(code: str):
    """Show every SKU and formula that uses this material."""
    return get_material_usage(code)

# ══════════════════════════════════════════════════════════════
# PRODUCTION MODULE ROUTES
# ══════════════════════════════════════════════════════════════

# Reference data
@app.get("/api/production/lines")
def list_lines(): return get_manufacturing_lines()

@app.get("/api/production/machines")
def list_prod_machines(machine_type: Optional[str] = None):
    return get_prod_machines(machine_type)

@app.get("/api/production/ncg-reasons")
def list_ncg_reasons(): return get_ncg_reasons()

# Employees
@app.get("/api/employees")
def list_employees(dept: Optional[str] = None, line_id: Optional[str] = None):
    return get_employees(dept, line_id)

@app.post("/api/employees", status_code=201)
def add_employee(body: EmployeeIn): return save_employee(body.dict())

@app.put("/api/employees/{emp_id}")
def edit_employee(emp_id: str, body: EmployeeIn):
    return save_employee(body.dict(), emp_id=emp_id)

@app.delete("/api/employees/{emp_id}")
def remove_employee(emp_id: str): delete_employee(emp_id); return {"ok": True}

# Mfg orders
@app.get("/api/mfg-orders")
def list_mfg_orders(status: Optional[str] = None, line_id: Optional[str] = None):
    return get_mfg_orders(status, line_id)

@app.post("/api/mfg-orders", status_code=201)
def add_mfg_order(body: MfgOrderIn): return create_mfg_order(body.dict())

# Production batches
@app.get("/api/prod-batches")
def list_prod_batches(
    line_id: Optional[str] = None,
    status: Optional[str] = None,
    date: Optional[str] = None,
    order_id: Optional[str] = None
):
    return get_prod_batches(line_id, status, date, order_id)

@app.post("/api/prod-batches", status_code=201)
def add_prod_batch(body: ProdBatchIn): return create_prod_batch(body.dict())

@app.get("/api/prod-batches/{batch_id}")
def get_one_prod_batch(batch_id: str):
    b = get_prod_batch(batch_id)
    if not b: raise HTTPException(404, "Batch not found")
    return b

@app.get("/api/prod-batches/{batch_id}/logs")
def batch_logs(batch_id: str): return get_batch_station_logs(batch_id)

@app.post("/api/prod-batches/{batch_id}/advance")
def advance_batch(batch_id: str, body: BatchAdvanceIn):
    advance_prod_batch_status(batch_id, body.next_status); return {"ok": True}

# Station log endpoints.
# These predate require_auth (defined further down), so they resolve the user
# from the token inline to attribute the action for per-user Undo.
def _act(token, *, action_type, summary, undo_spec):
    try:
        u = get_session_user(token) if token else None
        record_action(user=u, action_type=action_type, summary=summary, undo_spec=undo_spec)
    except Exception:
        pass

def _del(table, col, val):
    return {"table": table, "col": col, "val": val}

def _status_revert(batch_id, prev_status, cur_status):
    # forward set status prev->cur; undo restores prev where it's still cur.
    return {"table": "prod_batch", "set": {"status": prev_status},
            "where": {"batch_id": batch_id, "status": cur_status}}

def _record_undo(user, action_type, summary, result):
    """Record the reversal plan a warehouse function returned in result['undo'],
    then strip it from the response sent to the client."""
    try:
        if isinstance(result, dict) and result.get('undo'):
            record_action(user=user, action_type=action_type, summary=summary,
                          undo_spec=result['undo'])
            result = {k: v for k, v in result.items() if k != 'undo'}
    except Exception:
        pass
    return result

@app.post("/api/production/glue-mix", status_code=201)
def post_glue_mix(body: GlueMixIn, x_auth_token: str = Header(None)):
    d = body.dict(); mid = log_glue_mix(d)
    _act(x_auth_token, action_type='glue-mix', summary=f"Glue mix · batch {d.get('batch_id')}",
         undo_spec={"deletes": [_del('glue_mix_batches', 'mix_id', mid), _del('glue_mix_log', 'mix_id', mid)]})
    return {"mix_id": mid}

@app.post("/api/production/laminating", status_code=201)
def post_laminating(body: LaminatingIn, x_auth_token: str = Header(None)):
    d = body.dict(); lid = log_laminating(d)
    _act(x_auth_token, action_type='laminating', summary=f"Laminating log · batch {d.get('batch_id')}",
         undo_spec={"deletes": [_del('laminating_log', 'lam_id', lid)]})
    return {"lam_id": lid}

@app.post("/api/production/laminating/advance")
def advance_lam(batch_id: str):
    advance_laminating(batch_id); return {"ok": True}

@app.post("/api/production/cold-press", status_code=201)
def post_cold_press(body: ColdPressIn, x_auth_token: str = Header(None)):
    d = body.dict(); cid = log_cold_press(d)
    _act(x_auth_token, action_type='cold-press', summary=f"Cold press · batch {d.get('batch_id')}",
         undo_spec={"deletes": [_del('cold_press_log', 'cp_id', cid)],
                    "updates": [_status_revert(d.get('batch_id'), 'COLD_PRESS', 'REPAIR')]})
    return {"cp_id": cid}

@app.post("/api/production/repair", status_code=201)
def post_repair(body: RepairIn, x_auth_token: str = Header(None)):
    d = body.dict(); rid = log_repair(d)
    _act(x_auth_token, action_type='repair', summary=f"Repair log · batch {d.get('batch_id')}",
         undo_spec={"deletes": [_del('repair_log', 'repair_id', rid)]})
    return {"repair_id": rid}

@app.post("/api/production/repair/advance")
def advance_rep(batch_id: str):
    advance_repair(batch_id); return {"ok": True}

@app.post("/api/production/sanding", status_code=201)
def post_sanding(body: SandingIn, x_auth_token: str = Header(None)):
    d = body.dict(); sid = log_sanding(d)
    _act(x_auth_token, action_type='sanding', summary=f"Sanding log · batch {d.get('batch_id')}",
         undo_spec={"deletes": [_del('sanding_log', 'sand_id', sid)],
                    "updates": [_status_revert(d.get('batch_id'), 'SANDING', 'HOT_PRESS')]})
    return {"sand_id": sid}

@app.post("/api/production/hot-press", status_code=201)
def post_hot_press(body: HotPressIn, x_auth_token: str = Header(None)):
    d = body.dict(); hid = log_hot_press(d)
    _act(x_auth_token, action_type='hot-press', summary=f"Hot press · batch {d.get('batch_id')}",
         undo_spec={"deletes": [_del('hot_press_log', 'hp_id', hid)],
                    "updates": [_status_revert(d.get('batch_id'), 'HOT_PRESS', 'GRADING')]})
    return {"hp_id": hid}

@app.post("/api/production/grading", status_code=201)
def post_grading(body: GradingIn, x_auth_token: str = Header(None)):
    d = body.dict(); result = log_grading(d)
    gid = result.get('grade_id') if isinstance(result, dict) else result
    _act(x_auth_token, action_type='grading', summary=f"Grading log · batch {d.get('batch_id')}",
         undo_spec={"deletes": [_del('grading_log', 'grade_id', gid)],
                    "updates": [_status_revert(d.get('batch_id'), 'GRADING', 'COMPLETE')]})
    return result

@app.post("/api/production/grading/{grade_id}/ncg-issues", status_code=201)
def post_ncg_issues(grade_id: str, body: dict):
    issues = body.get('issues', [])
    save_ncg_issues(grade_id, issues)
    return {"ok": True, "saved": len(issues)}

@app.get("/api/production/grading/{grade_id}/ncg-issues")
def fetch_ncg_issues(grade_id: str):
    return get_ncg_issues(grade_id)

@app.get("/api/prod-batches/{batch_id}/full-history")
def prod_batch_full_history(batch_id: str):
    return get_batch_full_history(batch_id)
    return {"request_id": rid, "ok": True}

@app.post("/api/production/packing", status_code=201)
def post_packing(body: PackingIn, x_auth_token: str = Header(None)):
    d = body.dict(); pid = log_packing(d)
    _act(x_auth_token, action_type='packing', summary=f"Packing log · batch {d.get('batch_id')}",
         undo_spec={"deletes": [_del('packing_log', 'pack_id', pid)]})
    return {"pack_id": pid}

# Reporting endpoints
@app.get("/api/reports/daily")
def report_daily(line_id: Optional[str] = None,
                 from_date: Optional[str] = None,
                 to_date: Optional[str] = None):
    return get_daily_production(line_id, from_date, to_date)

@app.get("/api/reports/lam-efficacy")
def report_lam(line_id: Optional[str] = None, from_date: Optional[str] = None):
    return get_lam_efficacy_report(line_id, from_date)

@app.get("/api/reports/sanding-defects")
def report_sanding(line_id: Optional[str] = None, from_date: Optional[str] = None):
    return get_sanding_defect_report(line_id, from_date)

@app.get("/api/reports/ncg-reasons")
def report_ncg_reasons(line_id: Optional[str] = None):
    return get_ncg_by_reason_report(line_id)

@app.get("/api/reports/ncg-backtrack/{batch_id}")
def report_ncg_backtrack(batch_id: str):
    r = get_ncg_backtrack_report(batch_id)
    if not r: raise HTTPException(404, "No NCG backtrack found for this batch")
    return r

@app.get("/api/reports/ncg-list")
def report_ncg_list(
    line_id: Optional[str] = None,
    from_date: Optional[str] = None,
    reason_code: Optional[str] = None
):
    return get_ncg_backtrack_list(line_id, from_date, reason_code)

# AI endpoints (production module)
@app.post("/api/production/ai/analyze")
def prod_ai_analyze(body: ProdAIAnalyze):
    if not _prod_agent:
        raise HTTPException(503, "Production AI agent not available (check ANTHROPIC_API_KEY)")
    if body.mode == "BATCH_DIAGNOSIS":
        if not body.batch_id:
            raise HTTPException(400, "batch_id required for BATCH_DIAGNOSIS mode")
        data = get_ncg_backtrack_report(body.batch_id) or {}
    else:
        data = get_prod_ai_snapshot(body.line_id, body.days)
    return _prod_agent.analyze(mode=body.mode, data=data)

@app.post("/api/production/ai/chat")
def prod_ai_chat(body: ProdAIChat):
    if not _prod_agent:
        raise HTTPException(503, "Production AI agent not available")
    snapshot = get_prod_ai_snapshot(body.line_id, body.days)
    reply = _prod_agent.chat(messages=body.messages, context_snapshot=snapshot)
    return {"reply": reply}

# ════════════════════════════════════════════════════════════════
# AUTH — dependency + routes
# ════════════════════════════════════════════════════════════════

def _hash_pw(pw: str) -> str:
    return hashlib.sha256(pw.encode('utf-8')).hexdigest()

def require_auth(x_auth_token: str = Header(None)):
    if not x_auth_token:
        raise HTTPException(status_code=401, detail="Authentication required")
    user = get_session_user(x_auth_token)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid or expired session")
    return user

# ── Role identifiers ──────────────────────────────────────────
# Single source of truth for the four roles. Use Role.X instead of bare
# strings in require_role(...) and user['role'] comparisons — a typo in
# 'MANGERIAL' would otherwise lock everyone out of an endpoint silently.
class Role:
    MANAGERIAL          = 'MANAGERIAL'
    PRODUCTION_PLANNING = 'PRODUCTION_PLANNING'
    DEPARTMENT_LEADER   = 'DEPARTMENT_LEADER'
    WAREHOUSE           = 'WAREHOUSE'
    FINANCE             = 'FINANCE'   # Finance / Accounting + Purchasing portal (finance.html)
    QA_QC               = 'QA_QC'     # Quality / NCG review portal (qaqc.html)
    ALL = (MANAGERIAL, PRODUCTION_PLANNING, DEPARTMENT_LEADER, WAREHOUSE)

def require_role(*roles):
    def _dep(user: dict = Depends(require_auth)):
        if user['role'] not in roles:
            raise HTTPException(status_code=403, detail=f"Role '{user['role']}' not permitted")
        return user
    return _dep

# ── Factory Assistant ─────────────────────────────────────────
# General-purpose Claude chat surface with read-only DB + log access and
# Excel export. Replaces the two niche AI placeholders (BOM Query, Capacity
# Planner) that nobody wired into the nav.
class FactoryAssistantBody(BaseModel):
    messages: list                       # chronological [{role, content}, ...]
    session_id: Optional[str] = None     # persists the conversation across turns

@app.post("/api/factory-assistant/chat")
def factory_assistant_chat(body: FactoryAssistantBody,
                           user: dict = Depends(require_role(Role.MANAGERIAL))):
    from factory_assistant import chat as _fa_chat
    return _fa_chat(body.messages or [], session_id=body.session_id,
                    user_id=user.get('user_id'))

@app.get("/api/factory-assistant/sessions")
def factory_assistant_sessions(user: dict = Depends(require_role(Role.MANAGERIAL))):
    """The signed-in manager's saved chat sessions (for the history sidebar)."""
    from database import fa_list_sessions
    return fa_list_sessions(user.get('user_id'))

@app.get("/api/factory-assistant/history/{session_id}")
def factory_assistant_history(session_id: str,
                              user: dict = Depends(require_role(Role.MANAGERIAL))):
    """Full transcript of one past session so it can be reopened + continued."""
    from database import fa_get_session_history
    return fa_get_session_history(session_id, user.get('user_id'))

@app.delete("/api/factory-assistant/sessions/{session_id}")
def factory_assistant_delete_session(session_id: str,
                                     user: dict = Depends(require_role(Role.MANAGERIAL))):
    from database import fa_delete_session
    try:
        return fa_delete_session(session_id, user.get('user_id'))
    except ValueError as e:
        raise HTTPException(400, str(e))

class FAKnowledgeIn(BaseModel):
    category: str
    title: str
    content: str
    confidence: Optional[str] = 'medium'

@app.post("/api/factory-assistant/knowledge", status_code=201)
def factory_assistant_add_knowledge(body: FAKnowledgeIn,
                                    user: dict = Depends(require_role(Role.MANAGERIAL))):
    """Manager injects an operational fact the assistant will reference in
    future answers. source is forced to 'manager_input'."""
    from database import fa_add_knowledge
    try:
        return fa_add_knowledge(category=body.category, title=body.title,
                                content=body.content, source='manager_input',
                                confidence=body.confidence or 'medium')
    except ValueError as e:
        raise HTTPException(400, str(e))

@app.get("/api/factory-assistant/knowledge")
def factory_assistant_list_knowledge(user: dict = Depends(require_role(Role.MANAGERIAL))):
    """All knowledge entries, most-recently-referenced first. Powers the
    Knowledge Base table in the Factory Assistant panel."""
    from database import fa_list_knowledge
    return fa_list_knowledge()

@app.get("/api/factory-assistant/export/{filename}")
def factory_assistant_export(filename: str,
                             user: dict = Depends(require_role(Role.MANAGERIAL))):
    """Download a previously-generated xlsx file. Filenames are timestamped +
    uuid-suffixed by the tool, but we still validate against path traversal."""
    import os as _os, re as _re
    from factory_assistant import EXPORT_DIR
    if not _re.match(r"^[A-Za-z0-9_\-]+\.xlsx$", filename):
        raise HTTPException(400, "Invalid filename")
    path = _os.path.join(EXPORT_DIR, filename)
    if not _os.path.exists(path):
        raise HTTPException(404, "Export not found")
    return FileResponse(
        path,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        filename=filename,
    )

# ── Glue Recipe CRUD ─────────────────────────────────────────
@app.get("/api/glue-recipes")
def list_glue_recipes(kind: Optional[str] = None): return get_glue_recipes(kind=kind)

@app.post("/api/glue-recipes", status_code=201)
def create_glue_recipe_ep(body: dict):
    return save_glue_recipe(body)

@app.patch("/api/glue-recipes/{rid}")
def update_glue_recipe_ep(rid: int, body: dict):
    body['id'] = rid
    return save_glue_recipe(body)

@app.delete("/api/glue-recipes/{rid}")
def delete_glue_recipe_ep(rid: int):
    """Delete a glue recipe. FG BOM lines referencing it lose their cost
    (the bom_lines.glue_recipe_id FK becomes a dangling reference)."""
    conn = get_db()
    try:
        # Glue-only BOM lines (no material fallback) would violate the
        # "material_id IS NOT NULL OR glue_recipe_id IS NOT NULL" CHECK if we
        # nulled the recipe — delete those lines outright. Lines that also carry
        # a material keep the material and just lose the recipe link.
        conn.execute("DELETE FROM bom_lines WHERE glue_recipe_id=? AND material_id IS NULL", (rid,))
        conn.execute("UPDATE bom_lines SET glue_recipe_id=NULL WHERE glue_recipe_id=?", (rid,))
        conn.execute("UPDATE bom       SET glue_recipe_id=NULL WHERE glue_recipe_id=?", (rid,))
        conn.execute("DELETE FROM glue_recipes WHERE id=?", (rid,))
        conn.commit()
        return {"ok": True, "deleted_id": rid}
    finally:
        conn.close()

@app.get("/api/batches/{batch_id}/glue-info")
def batch_glue_info(batch_id: int):
    return get_batch_glue_info(batch_id)

@app.post("/api/production/glue-mix-confirm", status_code=201)
def glue_mix_confirm(body: dict):
    """Log glue mix and deduct components from glue_mix station stock."""
    return log_glue_mix_with_stock(body)

# ── HR Attendance ────────────────────────────────────────────
@app.get("/api/hr/attendance")
def list_attendance(work_date: Optional[str] = None, department: Optional[str] = None,
                    emp_id: Optional[str] = None):
    return get_attendance(work_date=work_date, dept=department, emp_id=emp_id)

@app.post("/api/hr/attendance", status_code=201)
def post_attendance(body: dict, user: dict = Depends(require_auth)):
    body['logged_by'] = user.get('user_id', '')
    return save_attendance(body)

@app.patch("/api/hr/attendance/{aid}")
def patch_attendance(aid: int, body: dict, user: dict = Depends(require_auth)):
    body['id'] = aid
    body['logged_by'] = user.get('user_id', '')
    return save_attendance(body)

@app.delete("/api/hr/attendance/{aid}")
def del_attendance(aid: int):
    delete_attendance(aid); return {"ok": True}

@app.get("/api/hr/attendance/summary")
def attendance_summary(from_date: str, to_date: str, department: Optional[str] = None,
                       user: dict = Depends(require_auth)):
    return get_attendance_summary(from_date, to_date, dept=department)

# ── Station Stock ────────────────────────────────────────────
@app.get("/api/station-stock")
def list_station_stock(department: str, line_id: Optional[str] = None,
                       user: dict = Depends(require_auth)):
    return get_station_stock(department, line_id=line_id)

@app.get("/api/station-stock/movements")
def list_stock_movements(department: str, line_id: Optional[str] = None,
                         from_date: Optional[str] = None, to_date: Optional[str] = None,
                         user: dict = Depends(require_auth)):
    return get_station_stock_movements(department, line_id=line_id,
                                       from_date=from_date, to_date=to_date)

@app.get("/api/station/daily-report")
def station_daily_report(department: str, line_id: Optional[str] = None,
                         date: Optional[str] = None, user: dict = Depends(require_auth)):
    """All data for a station's printable daily reports (Production + Stock &
    Utilization) for one day: completed-job logs, stock movements, and the
    consumable requests raised. Defaults to today."""
    from datetime import date as _date
    day = date or _date.today().isoformat()
    jobs = get_station_day_jobs(department, line_id=line_id, date=day)
    movements = get_station_stock_movements(department, line_id=line_id,
                                            from_date=day, to_date=day, limit=1000)
    balances = get_station_day_balances(department, line_id=line_id, date=day)
    reqs = [r for r in get_consumable_requests(department=department, line_id=line_id)
            if (r.get('created_at') or '')[:10] == day]
    return {"date": day, "department": department, "line_id": line_id or '',
            "jobs": jobs, "movements": movements, "balances": balances, "requests": reqs}

@app.patch("/api/station/job/{dept}/{log_id}")
def correct_job_route(dept: str, log_id: str, body: dict, user: dict = Depends(require_auth)):
    """Daily-review correction of a completed-job log: {qty?, batch_id?}."""
    try:
        return correct_station_job(dept, log_id,
                                   qty=body.get('qty'), batch_id=body.get('batch_id'),
                                   actor=user)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.patch("/api/station/movement/{movement_id}")
def correct_movement_route(movement_id: int, body: dict, user: dict = Depends(require_auth)):
    """Daily-review correction of a station stock movement: {qty_change?, batch_ref?}."""
    try:
        return correct_stock_movement(movement_id,
                                      qty_change=body.get('qty_change'),
                                      batch_ref=body.get('batch_ref'), actor=user)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/api/maintenance/fold-glue-stock")
def fold_glue_stock_route(user: dict = Depends(require_role(Role.MANAGERIAL))):
    """One-time cleanup of the legacy blank-line glue-mix stock bug: fold every
    glue_mix line='' stock row into P01 and re-line its movements. Idempotent."""
    return fold_glue_mix_blank_stock('P01')

@app.post("/api/station-stock/movement", status_code=201)
def post_stock_movement(body: dict, user: dict = Depends(require_auth)):
    body['created_by'] = user.get('user_id', '')
    return log_station_stock_movement(body)

@app.patch("/api/station-stock/{sid}/min")
def patch_stock_min(sid: int, body: dict):
    update_station_stock_min(sid, float(body.get('min_qty', 0)))
    return {"ok": True}

# ── Station Presets (saved machine/table/operator combos) ───
@app.get("/api/station-presets")
def list_station_presets(department: Optional[str] = None,
                          user: dict = Depends(require_auth)):
    return get_station_presets(department=department)

@app.post("/api/station-presets", status_code=201)
def create_station_preset(body: dict, user: dict = Depends(require_auth)):
    body['created_by'] = user.get('user_id', '')
    return save_station_preset(body)

@app.patch("/api/station-presets/{pid}")
def update_station_preset(pid: int, body: dict):
    body['id'] = pid
    return save_station_preset(body)

@app.delete("/api/station-presets/{pid}")
def remove_station_preset(pid: int):
    delete_station_preset(pid); return {"ok": True}

@app.post("/api/station-presets/{pid}/touch")
def touch_preset(pid: int):
    touch_station_preset(pid); return {"ok": True}

# ── Batch PATCH (edit) — requires auth ───────────────────────
@app.patch("/api/batches/{batch_id}")
def patch_batch(batch_id: int, body: dict):
    conn = get_db()
    allowed = {'quantity', 'split_reason', 'notes', 'current_department'}
    updates = {k: v for k, v in body.items() if k in allowed}
    if not updates:
        conn.close(); raise HTTPException(400, "No valid fields")
    sets = ", ".join(f"{k}=?" for k in updates)
    vals = list(updates.values()) + [batch_id]
    conn.execute(f"UPDATE batches SET {sets} WHERE id=?", vals)
    conn.commit()
    row = conn.execute("SELECT * FROM batches WHERE id=?", (batch_id,)).fetchone()
    conn.close()
    return row_to_dict(row)

@app.patch("/api/prod-batches/{batch_id}")
def patch_prod_batch(batch_id: str, body: dict):
    conn = get_db()
    allowed = {'qty_planned', 'notes', 'shift', 'production_date'}
    updates = {k: v for k, v in body.items() if k in allowed}
    if not updates:
        conn.close(); raise HTTPException(400, "No valid fields to update")
    sets = ", ".join(f"{k}=?" for k in updates)
    vals = list(updates.values()) + [batch_id]
    conn.execute(f"UPDATE prod_batch SET {sets} WHERE batch_id=?", vals)
    conn.commit()
    row = conn.execute("SELECT * FROM prod_batch WHERE batch_id=?", (batch_id,)).fetchone()
    conn.close()
    return row_to_dict(row)

@app.post("/api/fc/laminating-material-request", status_code=201)
async def laminating_material_request(body: dict, user: dict = Depends(require_auth)):
    import uuid as _uuid
    conn = get_db()
    rid = "FCR-" + _uuid.uuid4().hex[:8].upper()
    conn.execute("""
        INSERT INTO fc_transfer_requests
            (request_id, material_id, qty_requested, qty_fulfilled, status,
             notes, requested_by, direction, batch_ref, po_ref)
        VALUES (?,?,?,0,'PENDING',?,?,'inbound',?,?)
    """, (rid, body['material_id'], body['qty_requested'],
          body.get('notes',''), user.get('username','laminating'),
          body.get('batch_ref',''), body.get('po_ref','')))
    conn.commit()
    conn.close()
    return {"request_id": rid, "ok": True}

class LoginIn(BaseModel):
    username: str
    password: str

class UserIn(BaseModel):
    username: str; password: str; role: str; display_name: str

class UserUpdateIn(BaseModel):
    display_name: Optional[str] = None
    role: Optional[str] = None
    active: Optional[bool] = None
    password: Optional[str] = None

class UserDeptsIn(BaseModel):
    departments: list   # [{'department': str, 'line_id': str|None}]

class ConsumableRequestIn(BaseModel):
    department: str
    line_id: Optional[str] = None
    material_id: int
    qty_requested: float
    notes: Optional[str] = None
    priority: Optional[int] = 2          # 1=High 2=Med 3=Low
    needed_by: Optional[str] = None       # YYYY-MM-DD
    needed_time: Optional[str] = None     # 'morning' | 'afternoon'

class FulfillIn(BaseModel):
    qty_fulfilled: float

class FcTransferRequestIn(BaseModel):
    material_id: int
    qty_requested: float
    notes: Optional[str] = None
    priority: Optional[int] = 2
    needed_by: Optional[str] = None
    needed_time: Optional[str] = None     # 'morning' | 'afternoon'

class FcStockAdjustIn(BaseModel):
    material_id: int
    qty_delta: float

class VeneerRegradeIn(BaseModel):
    from_material_id: int
    to_material_id: int
    qty: float
    notes: Optional[str] = None

class VeneerAllocItem(BaseModel):
    material_id: int
    qty_allocated: float

class VeneerAllocIn(BaseModel):
    face_alloc: list[VeneerAllocItem] = []
    back_alloc: list[VeneerAllocItem] = []
    deduct_fc_stock: bool = True

@app.post("/api/auth/login")
def login(body: LoginIn, request: Request = None):
    user = get_user_by_username(body.username)
    if not user or user.get('password_hash') != _hash_pw(body.password):
        raise HTTPException(status_code=401, detail="Invalid username or password")
    if not user.get('active', 1):
        raise HTTPException(status_code=403, detail="Account is inactive. Contact your administrator.")
    token = create_session(user['user_id'])
    depts = get_user_departments(user['user_id'])
    # Record login audit event
    ip = None
    if request:
        forwarded = request.headers.get('x-forwarded-for')
        ip = forwarded.split(',')[0].strip() if forwarded else getattr(request.client, 'host', None)
    log_login(user['user_id'], user['username'], user['role'], ip)
    return {
        "token": token,
        "user": {k: user[k] for k in ('user_id','username','role','display_name')},
        "departments": depts
    }

@app.get("/api/auth/me")
def auth_me(user: dict = Depends(require_auth)):
    depts = get_user_departments(user['user_id'])
    return {**user, "departments": depts}

@app.post("/api/auth/logout")
def logout(x_auth_token: str = Header(None)):
    if x_auth_token:
        delete_session(x_auth_token)
    return {"ok": True}

# User management
@app.get("/api/users")
def list_users(user: dict = Depends(require_auth)):
    return get_users()

@app.post("/api/users", status_code=201)
def create_user_route(body: UserIn, user: dict = Depends(require_role(Role.MANAGERIAL))):
    return create_user(body.dict())

@app.patch("/api/users/{user_id}")
def update_user_route(user_id: str, body: UserUpdateIn, user: dict = Depends(require_role(Role.MANAGERIAL))):
    return update_user(user_id, body.dict(exclude_none=True))

@app.post("/api/users/{user_id}/departments")
def set_user_depts(user_id: str, body: UserDeptsIn, user: dict = Depends(require_role(Role.MANAGERIAL))):
    save_user_departments(user_id, body.departments)
    return get_user_departments(user_id)

@app.get("/api/users/{user_id}/departments")
def get_user_depts(user_id: str, user: dict = Depends(require_role(Role.MANAGERIAL))):
    return get_user_departments(user_id)

# ════════════════════════════════════════════════════════════════
# SUPPLY WAREHOUSE — Consumable Requests
# ════════════════════════════════════════════════════════════════

@app.get("/api/consumable-materials")
def list_consumable_materials(user: dict = Depends(require_auth)):
    return get_consumable_materials()

@app.post("/api/consumable-requests", status_code=201)
def create_req(body: ConsumableRequestIn, user: dict = Depends(require_auth)):
    data = body.dict()
    data['requested_by'] = user['user_id']
    return create_consumable_request(data)

@app.get("/api/consumable-requests")
def list_reqs(status: Optional[str] = None, department: Optional[str] = None,
              line_id: Optional[str] = None, open_only: bool = False,
              user: dict = Depends(require_auth)):
    # Dept leaders only see their own requests
    rb = user['user_id'] if user['role'] == Role.DEPARTMENT_LEADER else None
    return get_consumable_requests(status=status, department=department,
                                   requested_by=rb, line_id=line_id,
                                   open_only=open_only)

@app.patch("/api/consumable-requests/{request_id}/fulfill")
def fulfill_req(request_id: str, body: FulfillIn,
                user: dict = Depends(require_role(Role.WAREHOUSE))):
    try:
        r = fulfill_consumable_request(request_id, body.qty_fulfilled, user['user_id'])
        return _record_undo(user, 'fulfill-consumable',
                            f"Fulfil {body.qty_fulfilled} · {r.get('material_name','')}", r)
    except ValueError as e:
        # Insufficient-stock guard (and 'request not found') surface as a
        # 400 with the human message instead of a generic 500.
        raise HTTPException(400, str(e))

@app.patch("/api/consumable-requests/{request_id}/receive")
def receive_req(request_id: str, user: dict = Depends(require_auth)):
    """Station confirms physical receipt — deposits the fulfilled qty into
    station_stock and advances the request. Any signed-in station user can
    receive against their station's request."""
    try:
        return receive_consumable_request(request_id, user['user_id'])
    except ValueError as e:
        raise HTTPException(400, str(e))

@app.patch("/api/consumable-requests/{request_id}/cancel")
def cancel_req(request_id: str):
    return cancel_consumable_request(request_id)

# ════════════════════════════════════════════════════════════════
# FC STATION — Data Tools (export / import / template)
# ════════════════════════════════════════════════════════════════

@app.get("/api/export/fc-stock")
def export_fc_stock(user: dict = Depends(require_auth)):
    """Export all veneers & core boards with wh_stock and fc_stock as CSV."""
    conn = get_db()
    rows = conn.execute("""
        SELECT code, name, type, unit,
               COALESCE(current_stock,0) AS wh_stock,
               COALESCE(fc_stock,0)      AS fc_stock,
               COALESCE(reorder_point,0) AS reorder_point,
               COALESCE(unit_cost,0)     AS unit_cost,
               COALESCE(species,'')      AS species,
               COALESCE(grade,'')        AS grade
        FROM materials
        WHERE type IN ('veneer_sheet','core_board')
        ORDER BY type, species, name
    """).fetchall()
    conn.close()
    def esc(v): return '"'+str(v or '').replace('"','""')+'"'
    lines = ["code,name,type,unit,wh_stock,fc_stock,reorder_point,unit_cost,species,grade"]
    for r in rows:
        lines.append(f"{esc(r[0])},{esc(r[1])},{esc(r[2])},{esc(r[3])},{r[4]},{r[5]},{r[6]},{r[7]},{esc(r[8])},{esc(r[9])}")
    content = "\n".join(lines) + "\n"
    return Response(content=content.encode("utf-8"), media_type="text/csv",
                    headers={"Content-Disposition": "attachment; filename=fc_stock_export.csv"})


@app.get("/api/upload/template/fc-stock")
def fc_stock_template(user: dict = Depends(require_auth)):
    """CSV template for bulk FC stock adjustment."""
    lines = [
        "code,fc_stock",
        "# Only 'code' and 'fc_stock' are required. Use material code from the inventory.",
        "MDF-18,50",
        "VNR-BIRCH-A,120",
        "VNR-OAK-B,80",
    ]
    content = "\n".join(lines) + "\n"
    return Response(content=content.encode("utf-8"), media_type="text/csv",
                    headers={"Content-Disposition": "attachment; filename=fc_stock_template.csv"})


@app.post("/api/upload/fc-stock")
async def upload_fc_stock(file: UploadFile = File(...), mode: str = "add",
                          user: dict = Depends(require_auth)):
    """
    Import FC stock levels from CSV.
    mode=add  → set fc_stock to the given value for each code
    mode=adjust → add/subtract delta to existing fc_stock
    CSV columns required: code, fc_stock
    """
    content = (await file.read()).decode("utf-8", errors="replace")
    reader = csv.DictReader(io.StringIO(content))
    conn = get_db()
    processed = 0
    errors = []
    for i, row in enumerate(reader, 2):
        if row.get('code','').startswith('#'): continue  # skip comment rows
        code = (row.get('code') or '').strip()
        if not code:
            errors.append(f"Row {i}: missing code"); continue
        try:
            fc_qty = float(row.get('fc_stock') or 0)
        except ValueError:
            errors.append(f"Row {i}: invalid fc_stock value '{row.get('fc_stock')}'"); continue

        mat = conn.execute("SELECT id FROM materials WHERE code=? AND type IN ('veneer_sheet','core_board')",
                           (code,)).fetchone()
        if not mat:
            errors.append(f"Row {i}: code '{code}' not found or not a veneer/board"); continue

        if mode == "adjust":
            conn.execute("UPDATE materials SET fc_stock = MAX(0, COALESCE(fc_stock,0)+?) WHERE id=?",
                         (fc_qty, mat['id']))
        else:  # add / set
            conn.execute("UPDATE materials SET fc_stock = MAX(0,?) WHERE id=?",
                         (fc_qty, mat['id']))
        processed += 1

    conn.commit(); conn.close()
    return {"processed": processed, "errors": errors}


# ════════════════════════════════════════════════════════════════
# FC STATION — Stock & Transfer Requests
# ════════════════════════════════════════════════════════════════

@app.get("/api/fc/stock")
def fc_stock_list(user: dict = Depends(require_auth)):
    """All veneers & core boards with both WH stock and FC station stock."""
    return get_fc_stock_materials()

@app.get("/api/fc/transfer-requests")
def list_fc_transfers(status: Optional[str] = None, direction: Optional[str] = None,
                      user: dict = Depends(require_auth)):
    return get_fc_transfer_requests(status=status, direction=direction)

@app.get("/api/fc/movements")
def list_fc_movements(limit: int = 50, material_type: Optional[str] = None,
                      user: dict = Depends(require_auth)):
    """Unified FC movement log — boards, veneers, regrades, releases to laminating."""
    return get_fc_movements(limit=limit, mat_type=material_type)

# ── FG WAREHOUSE ──────────────────────────────────────────────
@app.get("/api/fg-warehouse/dashboard")
def fg_warehouse_dashboard(user: dict = Depends(require_auth)):
    """FG warehouse dashboard — stock by SKU, open POs, incoming batches, KPIs."""
    return get_fg_warehouse_dashboard()

@app.post("/api/fg-warehouse/receive/{batch_id}")
def receive_to_fg_warehouse(batch_id: int, user: dict = Depends(require_auth)):
    """Move a batch into the FG warehouse — typically called when packing finishes a batch."""
    result = receive_batch_to_warehouse(batch_id, received_by=user.get('user_id', ''))
    if not result:
        raise HTTPException(404, "Batch not found")
    return result

@app.get("/api/export/fg-stock")
def export_fg_stock():
    """Export current FG warehouse stock by SKU as CSV."""
    data = get_fg_warehouse_dashboard()
    rows = data.get('stock_by_sku', [])
    def esc(v): return '"'+str(v or '').replace('"','""')+'"'
    lines = ["sku_code,product_name,thickness_mm,width_mm,length_mm,pcs_per_pallet,in_stock_pcs,in_stock_pallets,batch_count"]
    for r in rows:
        lines.append(",".join([
            esc(r.get('sku_code')), esc(r.get('product_name')),
            str(r.get('thickness_mm') or ''), str(r.get('width_mm') or ''), str(r.get('length_mm') or ''),
            str(r.get('pallet_qty') or ''), str(r.get('in_stock_pcs') or 0),
            str(r.get('in_stock_pallets') or 0), str(r.get('batch_count') or 0),
        ]))
    content = "\n".join(lines) + "\n"
    return Response(content=content.encode("utf-8"), media_type="text/csv",
                    headers={"Content-Disposition": "attachment; filename=fg_stock_export.csv"})

# ── Warehouse internal stock movements (WH <-> WLWH) ──────────
class WhMoveIn(BaseModel):
    material_id: int
    from_location: str
    to_location: str
    qty: float
    notes: str = ""

@app.post("/api/warehouse/move-stock", status_code=201)
def warehouse_move_stock(body: WhMoveIn,
                         user: dict = Depends(require_role(Role.WAREHOUSE, Role.MANAGERIAL))):
    try:
        r = wh_move_stock(body.material_id, body.from_location, body.to_location,
                          body.qty, moved_by=(user.get('username') or ''), notes=body.notes)
        return _record_undo(user, 'wh-move',
                            f"Move {body.qty} {body.from_location}→{body.to_location}", r)
    except ValueError as e:
        raise HTTPException(400, str(e))

@app.get("/api/warehouse/move-log")
def warehouse_move_log(material_id: Optional[int] = None, limit: int = 50,
                       user: dict = Depends(require_auth)):
    return get_wh_transfer_log(material_id=material_id, limit=limit)

# ── WH <-> WLWH move requests (request → fulfil) ─────────────
@app.post("/api/warehouse/move-requests", status_code=201)
def create_move_request_ep(body: WhMoveIn,
                           user: dict = Depends(require_role(Role.WAREHOUSE, Role.MANAGERIAL))):
    """Raise a WH↔WLWH movement request. No stock moves until it's fulfilled."""
    try:
        return create_wh_move_request(body.material_id, body.from_location, body.to_location,
                                      body.qty, requested_by=(user.get('username') or ''),
                                      notes=body.notes)
    except ValueError as e:
        raise HTTPException(400, str(e))

@app.get("/api/warehouse/move-requests")
def list_move_requests_ep(status: Optional[str] = None, user: dict = Depends(require_auth)):
    return list_wh_move_requests(status=status)

@app.post("/api/warehouse/move-requests/{request_id}/fulfill", status_code=201)
def fulfill_move_request_ep(request_id: int,
                            user: dict = Depends(require_role(Role.WAREHOUSE, Role.MANAGERIAL))):
    """Warehouse employee fulfils a pending move — only now does stock shift."""
    try:
        r = fulfill_wh_move_request(request_id, fulfilled_by=(user.get('username') or ''))
        return _record_undo(user, 'wh-move-fulfil',
                            f"Fulfil move {r['qty']} {r['from_location']}→{r['to_location']}", r)
    except ValueError as e:
        raise HTTPException(400, str(e))

@app.post("/api/warehouse/move-requests/{request_id}/cancel")
def cancel_move_request_ep(request_id: int,
                           user: dict = Depends(require_role(Role.WAREHOUSE, Role.MANAGERIAL))):
    try:
        return cancel_wh_move_request(request_id, cancelled_by=(user.get('username') or ''))
    except ValueError as e:
        raise HTTPException(400, str(e))

# ── FG warehouse <-> WLWH location moves (Phase 4) ───────────
class FgMoveIn(BaseModel):
    batch_ids: List[int]
    to_location: str
    notes: str = ""

@app.get("/api/fg-warehouse/batches")
def fg_warehouse_batches(sku: Optional[str] = None, location: Optional[str] = None,
                         user: dict = Depends(require_auth)):
    return list_fg_batches(sku=sku, location=location)

@app.post("/api/fg-warehouse/move-location", status_code=201)
def fg_warehouse_move_location(body: FgMoveIn,
                               user: dict = Depends(require_role(Role.WAREHOUSE, Role.MANAGERIAL))):
    try:
        r = move_fg_batches(body.batch_ids, body.to_location,
                            moved_by=(user.get('username') or ''), notes=body.notes)
        return _record_undo(user, 'fg-move',
                            f"Move {r.get('count',0)} FG batch(es) → {body.to_location}", r)
    except ValueError as e:
        raise HTTPException(400, str(e))

@app.get("/api/fg-warehouse/move-log")
def fg_warehouse_move_log(limit: int = 50, user: dict = Depends(require_auth)):
    return get_fg_location_log(limit=limit)

# ── ACCOUNTING — read-only data hub ──────────────────────────
@app.get("/api/accounting/summary")
def acct_summary(from_date: Optional[str] = None, to_date: Optional[str] = None,
                 user: dict = Depends(require_auth)):
    return get_accounting_summary(from_date=from_date, to_date=to_date)

@app.get("/api/accounting/stock-movements")
def acct_stock_movements(from_date: Optional[str] = None, to_date: Optional[str] = None,
                         department: Optional[str] = None, kind: Optional[str] = None,
                         limit: int = 2000):
    kinds = [kind] if kind else None
    return get_accounting_stock_movements(from_date=from_date, to_date=to_date,
                                          dept=department, kinds=kinds, limit=limit)

@app.get("/api/accounting/production-output")
def acct_production(from_date: Optional[str] = None, to_date: Optional[str] = None,
                    department: Optional[str] = None, line: Optional[str] = None,
                    user: dict = Depends(require_auth)):
    return get_accounting_production_output(from_date=from_date, to_date=to_date,
                                            dept=department, line=line)

@app.get("/api/export/accounting/stock-movements")
def export_acct_movements(from_date: Optional[str] = None, to_date: Optional[str] = None,
                          department: Optional[str] = None):
    rows = get_accounting_stock_movements(from_date=from_date, to_date=to_date,
                                          dept=department, limit=10000)
    header = "date,time,source,kind,department,line,material_code,material_name,unit,qty,unit_cost,cost_impact,ref,actor,notes"
    def esc(v):
        if v is None: return ''
        s = str(v); return '"'+s.replace('"','""')+'"' if (',' in s or '"' in s or '\n' in s) else s
    lines = [header]
    for r in rows:
        ts = r.get('ts','') or ''
        date_part = ts[:10]; time_part = ts[11:19] if len(ts) > 10 else ''
        lines.append(",".join([
            esc(date_part), esc(time_part), esc(r.get('source','')), esc(r.get('kind','')),
            esc(r.get('dept','')), esc(r.get('line_id','')),
            esc(r.get('material_code','')), esc(r.get('material_name','')),
            esc(r.get('unit','')), esc(r.get('qty')), esc(r.get('unit_cost')),
            esc(r.get('cost_impact')), esc(r.get('ref','')), esc(r.get('actor','')),
            esc(r.get('notes','')),
        ]))
    return Response(content=("\n".join(lines)+"\n").encode("utf-8"), media_type="text/csv",
                    headers={"Content-Disposition": "attachment; filename=accounting_stock_movements.csv"})

@app.get("/api/export/accounting/production")
def export_acct_production(from_date: Optional[str] = None, to_date: Optional[str] = None):
    rows = get_accounting_production_output(from_date=from_date, to_date=to_date)
    header = "date,department,production_line,sku,pcs_in,pcs_out,defects,yield_pct"
    def esc(v):
        if v is None: return ''
        s = str(v); return '"'+s.replace('"','""')+'"' if (',' in s or '"' in s or '\n' in s) else s
    lines = [header] + [",".join([
        esc(r['date']), esc(r['dept']), esc(r['line']), esc(r['sku']),
        esc(r['pcs_in']), esc(r['pcs_out']), esc(r['defects']), esc(r['yield_pct'])
    ]) for r in rows]
    return Response(content=("\n".join(lines)+"\n").encode("utf-8"), media_type="text/csv",
                    headers={"Content-Disposition": "attachment; filename=accounting_production_output.csv"})


# ════════════════════════════════════════════════════════════════
# PURCHASING — purchase requests
# ════════════════════════════════════════════════════════════════
class PRIn(BaseModel):
    request_type: str
    material_id: int
    qty_requested: float
    uom: Optional[str] = ''
    source_po_id: Optional[int] = None
    priority: Optional[int] = 2
    needed_by: Optional[str] = None
    suggested_supplier: Optional[str] = ''
    notes: Optional[str] = ''

# ════════════════════════════════════════════════════════════════
# WAREHOUSE PORTAL ENDPOINTS
# ════════════════════════════════════════════════════════════════
# The warehouse portal (/warehouse) needs three composite views:
#   1. low-stock worklist — items <= reorder_point, scoped to
#      consumables / glue / packing / others (NOT boards or veneers
#      which are Planning's domain via Material Shortfalls).
#   2. dashboard          — KPIs + this-week receiving + this-week
#      exports (consumable issues out of the warehouse).
#   3. open PR list       — non-terminal PRs with their shipment plan.
# Each endpoint composes from existing DB helpers; no schema changes.

# Categories the warehouse self-services (everything except boards + veneers).
_WH_PR_CATEGORIES = ('adhesive', 'glue_formula', 'packing', 'other')

def _wh_week_bounds():
    """Return Mon 00:00 .. next Mon 00:00 as ISO strings for SQL BETWEEN."""
    from datetime import datetime, timedelta
    today = datetime.now().date()
    monday = today - timedelta(days=today.weekday())
    sunday_end = monday + timedelta(days=7)
    return monday.isoformat(), sunday_end.isoformat()

@app.get("/api/warehouse/low-stock")
def warehouse_low_stock(category: Optional[str] = None,
                        user: dict = Depends(require_auth)):
    """Materials at or below reorder_point, restricted to warehouse-managed
    categories (adhesive / glue_formula / packing / other). When `category`
    is supplied it must be one of those four codes. Each row carries a
    suggested order qty = reorder_point*2 - current_stock (clamped >= 0)."""
    if category and category in _WH_PR_CATEGORIES:
        types = (category,)
    else:
        types = _WH_PR_CATEGORIES
    placeholders = ','.join('?' * len(types))
    conn = get_db()
    rows = conn.execute(f"""
        SELECT id, code, name, name_th, type, unit,
               COALESCE(current_stock,0) AS current_stock,
               COALESCE(reorder_point,0) AS reorder_point,
               COALESCE(unit_cost,0)     AS unit_cost,
               COALESCE(supplier,'')     AS supplier
          FROM materials
         WHERE reorder_point > 0
           AND COALESCE(current_stock,0) <= reorder_point
           AND type IN ({placeholders})
         ORDER BY (COALESCE(current_stock,0) / NULLIF(reorder_point,0)) ASC,
                  code ASC
    """, types).fetchall()
    conn.close()
    out = []
    for r in rows:
        d = dict(r)
        suggested = max(0.0, (d['reorder_point'] * 2) - d['current_stock'])
        d['suggested_qty'] = round(suggested, 2)
        out.append(d)
    return out

@app.get("/api/warehouse/dashboard")
def warehouse_dashboard(user: dict = Depends(require_auth)):
    """One-shot KPI + this-week schedule payload for the warehouse portal."""
    week_start, week_end = _wh_week_bounds()
    placeholders = ','.join('?' * len(_WH_PR_CATEGORIES))
    conn = get_db()

    # Low-stock count (same scope as /api/warehouse/low-stock)
    low_count = conn.execute(f"""
        SELECT COUNT(*) FROM materials
         WHERE reorder_point > 0
           AND COALESCE(current_stock,0) <= reorder_point
           AND type IN ({placeholders})
    """, _WH_PR_CATEGORIES).fetchone()[0]

    # Open PR count (any status that hasn't terminated)
    open_pr_count = conn.execute("""
        SELECT COUNT(*) FROM purchase_requests
         WHERE status IN ('NEW','APPROVED','PO_ISSUED','AWAITING_ARRIVAL','OVER_RECEIVED')
    """).fetchone()[0]

    # Arriving this week: scheduled shipments whose planned_arrival falls
    # in the current Mon..Sun window AND haven't been fully received yet.
    arriving = conn.execute("""
        SELECT s.id, s.pr_id, s.sequence, s.planned_qty, s.planned_arrival,
               s.received_qty, s.status AS shipment_status,
               s.carrier, s.supplier_ref,
               pr.request_number, pr.status AS pr_status, pr.supplier_po_ref,
               m.code AS material_code, m.name AS material_name,
               m.name_th AS material_name_th, m.type AS material_type, m.unit
          FROM pr_shipments s
          JOIN purchase_requests pr ON pr.id = s.pr_id
          JOIN materials m ON m.id = pr.material_id
         WHERE s.planned_arrival >= ?
           AND s.planned_arrival <  ?
           AND COALESCE(s.status,'PLANNED') != 'RECEIVED'
         ORDER BY s.planned_arrival ASC, pr.request_number ASC
    """, (week_start, week_end)).fetchall()

    # Exporting this week: consumable requests issued out of the warehouse
    # this week (status FULFILLED with fulfilled_at in window) OR still
    # pending/partial with needed_by in window — both represent stock flow
    # leaving the warehouse during the week.
    try:
        exporting = conn.execute("""
            SELECT cr.request_id, cr.material_id, cr.qty_requested, cr.qty_fulfilled,
                   cr.status, cr.department, cr.needed_by, cr.created_at, cr.fulfilled_at,
                   m.code AS material_code, m.name AS material_name,
                   m.name_th AS material_name_th, m.unit
              FROM consumable_request cr
              JOIN materials m ON m.id = cr.material_id
             WHERE (
                    (cr.status = 'FULFILLED' AND DATE(cr.fulfilled_at) >= ? AND DATE(cr.fulfilled_at) < ?)
                 OR (cr.status IN ('PENDING','PARTIAL') AND DATE(COALESCE(cr.needed_by, cr.created_at)) >= ? AND DATE(COALESCE(cr.needed_by, cr.created_at)) < ?)
                   )
             ORDER BY COALESCE(cr.needed_by, cr.created_at) ASC
             LIMIT 200
        """, (week_start, week_end, week_start, week_end)).fetchall()
    except Exception:
        # consumable_request schema differs in some installs — fail soft.
        exporting = []

    # Material requests from production line that the warehouse still has
    # work to do on (PENDING + PARTIAL). Drives the sidebar badge.
    try:
        pending_reqs = conn.execute("""
            SELECT COUNT(*) FROM consumable_request
             WHERE status IN ('PENDING','PARTIAL')
        """).fetchone()[0]
    except Exception:
        pending_reqs = 0

    conn.close()
    return {
        "week_start": week_start,
        "week_end_exclusive": week_end,
        "low_stock_count": low_count,
        "open_pr_count":   open_pr_count,
        "arriving_count":  len(arriving),
        "exporting_count": len(exporting),
        "pending_requests_count": pending_reqs,
        "arriving":  [dict(r) for r in arriving],
        "exporting": [dict(r) for r in exporting],
    }

@app.get("/api/warehouse/open-purchase-requests")
def warehouse_open_prs(category: Optional[str] = None,
                       user: dict = Depends(require_auth)):
    """Open PRs joined with their planned shipments, optionally filtered by
    material category. `category` accepts an internal type code (adhesive,
    glue_formula, packing, other, core_board, veneer_sheet)."""
    conn = get_db()
    base = """
        SELECT pr.id, pr.request_number, pr.request_type, pr.material_id,
               pr.qty_requested, pr.uom, pr.priority, pr.needed_by,
               pr.suggested_supplier, pr.supplier_po_ref, pr.status,
               pr.estimated_arrival, pr.requested_at, pr.notes,
               m.code AS material_code, m.name AS material_name,
               m.name_th AS material_name_th, m.type AS material_type, m.unit
          FROM purchase_requests pr
          JOIN materials m ON m.id = pr.material_id
         WHERE pr.status IN ('NEW','APPROVED','PO_ISSUED','AWAITING_ARRIVAL','OVER_RECEIVED')
    """
    params = []
    if category:
        base += " AND m.type = ?"
        params.append(category)
    base += " ORDER BY pr.priority ASC, pr.requested_at DESC LIMIT 500"
    prs = [dict(r) for r in conn.execute(base, params).fetchall()]
    if prs:
        ids = tuple(p['id'] for p in prs)
        ph = ','.join('?' * len(ids))
        ships = conn.execute(f"""
            SELECT id, pr_id, sequence, planned_qty, planned_arrival,
                   received_qty, status, carrier, supplier_ref
              FROM pr_shipments
             WHERE pr_id IN ({ph})
             ORDER BY pr_id ASC, sequence ASC
        """, ids).fetchall()
        by_pr = {}
        for s in ships:
            by_pr.setdefault(s['pr_id'], []).append(dict(s))
        for p in prs:
            p['shipments'] = by_pr.get(p['id'], [])
    conn.close()
    return prs

@app.get("/api/purchase-requests")
def list_prs(status: Optional[str] = None, request_type: Optional[str] = None,
             user: dict = Depends(require_auth)):
    return list_purchase_requests(status=status, request_type=request_type)

@app.post("/api/purchase-requests")
def create_pr(body: PRIn, user: dict = Depends(require_auth)):
    try:
        return create_purchase_request(
            request_type=body.request_type, material_id=body.material_id,
            qty_requested=body.qty_requested, uom=body.uom or '',
            source_po_id=body.source_po_id, priority=body.priority or 2,
            needed_by=body.needed_by, suggested_supplier=body.suggested_supplier or '',
            notes=body.notes or '', requested_by=user.get('username') or user.get('display_name') or '')
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


class PRSplitIn(BaseModel):
    planned_qty: float
    planned_arrival: Optional[str] = None
    carrier: Optional[str] = ''
    notes: Optional[str] = ''

class PRLineIn(BaseModel):
    request_type: str = 'RAW_MATERIAL'
    material_id: int
    qty_requested: float
    uom: Optional[str] = ''
    priority: Optional[int] = None
    needed_by: Optional[str] = None
    suggested_supplier: Optional[str] = ''
    notes: Optional[str] = ''
    splits: Optional[List[PRSplitIn]] = None

class PRBulkIn(BaseModel):
    source_po_id: Optional[int] = None
    priority: Optional[int] = 2
    needed_by: Optional[str] = None
    suggested_supplier: Optional[str] = ''
    notes: Optional[str] = ''
    lines: List[PRLineIn]

@app.post("/api/purchase-requests/bulk")
def create_pr_bulk(body: PRBulkIn, user: dict = Depends(require_auth)):
    try:
        lines = []
        for ln in body.lines:
            d = ln.dict()
            if d.get('splits'):
                d['splits'] = [s for s in d['splits'] if s.get('planned_qty', 0) > 0]
            lines.append(d)
        return create_purchase_requests_bulk(
            lines=lines,
            source_po_id=body.source_po_id,
            priority=body.priority or 2,
            needed_by=body.needed_by,
            suggested_supplier=body.suggested_supplier or '',
            notes=body.notes or '',
            requested_by=user.get('username') or user.get('display_name') or '')
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

class PRStatus(BaseModel):
    status: str
    supplier_po_ref: Optional[str] = ''
    estimated_arrival: Optional[str] = ''  # YYYY-MM-DD
    unit_cost: Optional[float] = None      # purchasing's agreed order price (set at PO issue)

@app.patch("/api/purchase-requests/{pr_id}/status")
def set_pr_status(pr_id: int, body: PRStatus, user: dict = Depends(require_auth)):
    try:
        return update_purchase_request_status(pr_id, body.status,
            actor=user.get('username') or '',
            supplier_po_ref=body.supplier_po_ref or '',
            estimated_arrival=body.estimated_arrival or '',
            unit_cost=body.unit_cost)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/purchase-requests/{pr_id}/issue-po")
async def issue_po_with_doc(
    pr_id: int,
    supplier_po_ref: str = '',
    estimated_arrival: str = '',
    unit_cost: Optional[float] = None,
    file: Optional[UploadFile] = File(None),
    user: dict = Depends(require_auth),
):
    """Combined endpoint Purchasing calls when issuing a PO to a supplier:
    sets PR status to PO_ISSUED (or AWAITING_ARRIVAL if an ETA is provided)
    and optionally stores the supplier PO PDF, linked to the PR so future
    received lots automatically inherit it for traceability."""
    # Find the PR & material first so we know which material the doc belongs to
    prs = list_purchase_requests()
    pr = next((p for p in prs if p.get('id') == pr_id), None)
    if not pr:
        raise HTTPException(status_code=404, detail="Purchase request not found")
    material_id = pr['material_id']

    # Persist the PDF if one was uploaded
    if file is not None:
        if file.content_type not in ALLOWED_DOC_MIME and not (file.filename or '').lower().endswith('.pdf'):
            raise HTTPException(status_code=400, detail="Only PDF files are allowed")
        raw = await file.read()
        if len(raw) > MAX_DOC_BYTES:
            raise HTTPException(status_code=413, detail=f"File exceeds {MAX_DOC_BYTES//1024//1024} MB limit")
        if len(raw) == 0:
            raise HTTPException(status_code=400, detail="Empty file")
        safe_name = ''.join(c for c in (file.filename or 'supplier_po.pdf') if c.isalnum() or c in '._-')
        stored = f"{date.today().isoformat()}_PR{pr_id}_{hashlib.sha1(raw).hexdigest()[:10]}_{safe_name}"
        full = os.path.join(DOCS_DIR, stored)
        with open(full, 'wb') as f:
            f.write(raw)
        notes = f"Supplier PO {supplier_po_ref}" if supplier_po_ref else f"Supplier PO for PR #{pr_id}"
        register_material_document(
            material_id=material_id, lot_id=None, doc_type='SUPPLIER_PO',
            filename=file.filename or safe_name, stored_path=stored, file_size=len(raw),
            content_type=file.content_type or 'application/pdf',
            uploaded_by=user.get('username') or '', notes=notes,
            purchase_request_id=pr_id)

    # Decide target status: AWAITING_ARRIVAL if ETA supplied, otherwise PO_ISSUED
    target = 'AWAITING_ARRIVAL' if (estimated_arrival or '').strip() else 'PO_ISSUED'
    try:
        return update_purchase_request_status(
            pr_id, target,
            actor=user.get('username') or '',
            supplier_po_ref=supplier_po_ref or '',
            estimated_arrival=estimated_arrival or '',
            unit_cost=unit_cost)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/purchase-requests/issue-po-multi")
async def issue_po_with_doc_multi(
    pr_ids: str = '',                # comma-separated list of PR ids
    supplier_po_ref: str = '',
    estimated_arrival: str = '',
    unit_costs: str = '',            # per-PR price map "prid:price,prid:price"
    file: Optional[UploadFile] = File(None),
    user: dict = Depends(require_auth),
):
    """Bundle workflow: issue one supplier PO that covers several PRs.
    The PDF is stored once and linked to every PR via pr_document_links.
    Each PR also flips status to PO_ISSUED / AWAITING_ARRIVAL with the same
    supplier_po_ref and ETA. Lots received against any of those PRs will
    inherit the shared document automatically (traceability stays clean while
    each lot's FIFO consumption is tracked independently)."""
    ids = [int(x) for x in (pr_ids or '').split(',') if x.strip().isdigit()]
    if not ids:
        raise HTTPException(status_code=400, detail="pr_ids is required (comma-separated)")
    prs_all = list_purchase_requests()
    prs = [p for p in prs_all if p.get('id') in ids]
    found_ids = {p['id'] for p in prs}
    missing = [i for i in ids if i not in found_ids]
    if missing:
        raise HTTPException(status_code=404, detail=f"PRs not found: {missing}")

    # Save the PDF once if supplied; the same stored_path / document_id is then
    # reused via pr_document_links.
    primary_doc_id = None
    if file is not None:
        if file.content_type not in ALLOWED_DOC_MIME and not (file.filename or '').lower().endswith('.pdf'):
            raise HTTPException(status_code=400, detail="Only PDF files are allowed")
        raw = await file.read()
        if len(raw) > MAX_DOC_BYTES:
            raise HTTPException(status_code=413, detail=f"File exceeds {MAX_DOC_BYTES//1024//1024} MB limit")
        if len(raw) == 0:
            raise HTTPException(status_code=400, detail="Empty file")
        safe_name = ''.join(c for c in (file.filename or 'supplier_po.pdf') if c.isalnum() or c in '._-')
        stored = f"{date.today().isoformat()}_PRS{('-'.join(str(i) for i in ids))[:30]}_{hashlib.sha1(raw).hexdigest()[:10]}_{safe_name}"
        full = os.path.join(DOCS_DIR, stored)
        with open(full, 'wb') as f:
            f.write(raw)
        notes = (f"Supplier PO {supplier_po_ref} — shared across PRs " +
                 ', '.join(p['request_number'] or ('#'+str(p['id'])) for p in prs))
        # Register against the first PR as primary owner; mat id = first PR's material
        primary = prs[0]
        rec = register_material_document(
            material_id=primary['material_id'], lot_id=None, doc_type='SUPPLIER_PO',
            filename=file.filename or safe_name, stored_path=stored, file_size=len(raw),
            content_type=file.content_type or 'application/pdf',
            uploaded_by=user.get('username') or '', notes=notes,
            purchase_request_id=primary['id'])
        primary_doc_id = rec.get('id')
        # Link to the remaining PRs through the join table
        if primary_doc_id and len(ids) > 1:
            link_document_to_prs(primary_doc_id, [i for i in ids if i != primary['id']])

    # Parse the per-PR price map "prid:price,prid:price" so each line gets its
    # own agreed price (a bundled PO can cover several different materials).
    cost_by_pr = {}
    for chunk in (unit_costs or '').split(','):
        if ':' in chunk:
            k, _, v = chunk.partition(':')
            try:
                cost_by_pr[int(k.strip())] = float(v.strip())
            except (TypeError, ValueError):
                pass

    target = 'AWAITING_ARRIVAL' if (estimated_arrival or '').strip() else 'PO_ISSUED'
    results = []
    for p in prs:
        try:
            r = update_purchase_request_status(
                p['id'], target,
                actor=user.get('username') or '',
                supplier_po_ref=supplier_po_ref or '',
                estimated_arrival=estimated_arrival or '',
                unit_cost=cost_by_pr.get(p['id']))
            results.append({**r, 'request_number': p.get('request_number')})
        except Exception as e:
            results.append({'id': p['id'], 'error': str(e)})
    return {
        'document_id': primary_doc_id,
        'pr_ids': ids,
        'count': len(prs),
        'status_set_to': target,
        'results': results,
    }

@app.post("/api/purchase-requests/auto-from-po/{po_id}")
def auto_pr_from_po(po_id: int, user: dict = Depends(require_auth)):
    return auto_generate_purchase_requests_for_po(po_id,
        requested_by=user.get('username') or '')

# ════════════════════════════════════════════════════════════════
# PR SHIPMENT SCHEDULING + WAREHOUSE RECEIVING
# ════════════════════════════════════════════════════════════════
class ShipmentIn(BaseModel):
    pr_id: int
    planned_qty: float
    planned_arrival: Optional[str] = None
    supplier_ref: Optional[str] = ''
    carrier: Optional[str] = ''
    notes: Optional[str] = ''

@app.get("/api/purchase-requests/{pr_id}/shipments")
def list_shipments_for_pr(pr_id: int):
    return list_pr_shipments(pr_id=pr_id)

@app.get("/api/shipments")
def list_shipments_all(status: Optional[str] = None, only_open: bool = False,
                       include_implicit: bool = False,
                       user: dict = Depends(require_auth)):
    return list_pr_shipments(status=status, only_open=only_open,
                             include_implicit=include_implicit)

@app.post("/api/shipments", status_code=201)
def create_shipment_ep(body: ShipmentIn, user: dict = Depends(require_auth)):
    try:
        return create_pr_shipment(
            pr_id=body.pr_id, planned_qty=body.planned_qty,
            planned_arrival=body.planned_arrival, supplier_ref=body.supplier_ref or '',
            carrier=body.carrier or '', notes=body.notes or '',
            created_by=user.get('username') or '')
    except ValueError as e:
        raise HTTPException(400, str(e))

class ShipmentEditIn(BaseModel):
    planned_qty: Optional[float] = None
    planned_arrival: Optional[str] = None
    supplier_ref: Optional[str] = None
    carrier: Optional[str] = None
    notes: Optional[str] = None
    status: Optional[str] = None

@app.patch("/api/shipments/{shipment_id}")
def edit_shipment_ep(shipment_id: int, body: ShipmentEditIn):
    try:
        return update_pr_shipment(shipment_id=shipment_id, **body.dict(exclude_unset=True))
    except ValueError as e:
        raise HTTPException(400, str(e))

@app.delete("/api/shipments/{shipment_id}")
def delete_shipment_ep(shipment_id: int):
    try:
        return delete_pr_shipment(shipment_id)
    except ValueError as e:
        raise HTTPException(400, str(e))

class ReceiveIn(BaseModel):
    received_qty: float
    lot_code: Optional[str] = ''
    unit_cost: Optional[float] = 0
    expiry_date: Optional[str] = None
    supplier: Optional[str] = ''
    supplier_lot_ref: Optional[str] = ''
    notes: Optional[str] = ''
    destination: Optional[str] = 'WH'   # WH | WLWH (boards/veneers only)

@app.post("/api/shipments/{shipment_id}/receive")
def receive_shipment_ep(shipment_id: int, body: ReceiveIn, user: dict = Depends(require_auth)):
    try:
        r = receive_pr_shipment(
            shipment_id=shipment_id, received_qty=body.received_qty,
            lot_code=body.lot_code or '', unit_cost=body.unit_cost or 0,
            expiry_date=body.expiry_date, supplier=body.supplier or '',
            supplier_lot_ref=body.supplier_lot_ref or '', notes=body.notes or '',
            received_by=user.get('username') or '', destination=body.destination or 'WH')
        return _record_undo(user, 'receive',
                            f"Receive {body.received_qty} → {body.destination or 'WH'} (lot {r.get('lot_code','')})", r)
    except ValueError as e:
        raise HTTPException(400, str(e))

class QuickReceiveIn(BaseModel):
    received_qty: float
    planned_arrival: Optional[str] = None
    supplier_ref: Optional[str] = ''
    carrier: Optional[str] = ''
    lot_code: Optional[str] = ''
    unit_cost: Optional[float] = 0
    expiry_date: Optional[str] = None
    supplier: Optional[str] = ''
    supplier_lot_ref: Optional[str] = ''
    notes: Optional[str] = ''
    destination: Optional[str] = 'WH'   # WH | WLWH (boards/veneers only)

@app.post("/api/purchase-requests/{pr_id}/quick-receive")
def quick_receive_ep(pr_id: int, body: QuickReceiveIn, user: dict = Depends(require_auth)):
    """Receive against a PR that has no scheduled shipment row — creates the
    shipment + lot atomically. Used by Warehouse when goods arrive without
    Purchasing having planned a delivery."""
    try:
        r = quick_receive_for_pr(
            pr_id=pr_id, received_qty=body.received_qty,
            planned_arrival=body.planned_arrival, supplier_ref=body.supplier_ref or '',
            carrier=body.carrier or '', lot_code=body.lot_code or '',
            unit_cost=body.unit_cost or 0, expiry_date=body.expiry_date,
            supplier=body.supplier or '', supplier_lot_ref=body.supplier_lot_ref or '',
            notes=body.notes or '', received_by=user.get('username') or '',
            destination=body.destination or 'WH')
        return _record_undo(user, 'receive',
                            f"Receive {body.received_qty} → {body.destination or 'WH'} (lot {r.get('lot_code','')})", r)
    except ValueError as e:
        raise HTTPException(400, str(e))

class ShipSplitIn(BaseModel):
    split_qty: float
    new_planned_arrival: Optional[str] = None
    new_carrier: Optional[str] = None
    new_supplier_ref: Optional[str] = None

@app.post("/api/shipments/{shipment_id}/split")
def split_shipment_ep(shipment_id: int, body: ShipSplitIn):
    try:
        return split_pr_shipment(
            shipment_id=shipment_id, split_qty=body.split_qty,
            new_planned_arrival=body.new_planned_arrival,
            new_carrier=body.new_carrier, new_supplier_ref=body.new_supplier_ref)
    except ValueError as e:
        raise HTTPException(400, str(e))


# ════════════════════════════════════════════════════════════════
# FORKLIFTS
# ════════════════════════════════════════════════════════════════
class ForkliftIn(BaseModel):
    id: Optional[int] = None
    code: str
    name: Optional[str] = ''
    dept: Optional[str] = ''
    production_line: Optional[str] = ''
    model: Optional[str] = ''
    fuel_type: Optional[str] = 'diesel'
    status: Optional[str] = 'active'
    hours_meter: Optional[float] = 0
    last_service_at: Optional[str] = None
    notes: Optional[str] = ''

@app.get("/api/forklifts")
def list_forklifts_ep(dept: Optional[str] = None, status: Optional[str] = None,
                      user: dict = Depends(require_auth)):
    return list_forklifts(dept=dept, status=status)

@app.post("/api/forklifts")
def upsert_forklift_ep(body: ForkliftIn, user: dict = Depends(require_auth)):
    try:
        return upsert_forklift(
            id=body.id, code=body.code, name=body.name or '', dept=body.dept or '',
            production_line=body.production_line or '', model=body.model or '',
            fuel_type=body.fuel_type or 'diesel', status=body.status or 'active',
            hours_meter=body.hours_meter or 0, last_service_at=body.last_service_at,
            notes=body.notes or '', created_by=user.get('username') or '')
    except ValueError as e:
        raise HTTPException(400, str(e))

@app.delete("/api/forklifts/{fid}")
def delete_forklift_ep(fid: int):
    return delete_forklift(fid)


class OilRequestIn(BaseModel):
    forklift_id: int
    oil_type: Optional[str] = 'hydraulic'
    qty_litres: float
    notes: Optional[str] = ''
    priority: Optional[str] = 'NORMAL'   # NORMAL | URGENT

@app.get("/api/forklifts/oil-requests")
def list_oil_requests_ep(status: Optional[str] = None,
                         forklift_id: Optional[int] = None,
                         priority: Optional[str] = None,
                         scheduled_date: Optional[str] = None,
                         user: dict = Depends(require_auth)):
    return list_oil_requests(status=status, forklift_id=forklift_id,
                             priority=priority, scheduled_date=scheduled_date)

@app.get("/api/forklifts/refuel-config")
def refuel_config_ep(user: dict = Depends(require_auth)):
    """Surface refueling windows so the UI can show 'next slot' hints.
    Returns the full list of configured windows + a one-line description."""
    wins = list_refuel_windows(active_only=True)
    if not wins:
        desc = (f"Default refueling window: {REFUEL_WINDOW_HOUR:02d}:00 daily, "
                f"cutoff {REFUEL_REQUEST_CUTOFF:02d}:30.")
    else:
        parts = [f"{w['label']} @ {w['start_hour']:02d}:{w['start_min']:02d} "
                 f"(cutoff {w['cutoff_hour']:02d}:{w['cutoff_min']:02d})" for w in wins]
        desc = "Refuel windows: " + ", ".join(parts) + ". URGENT requests are fulfilled immediately."
    return {
        'windows': wins,
        'window_hour':    wins[0]['start_hour'] if wins else REFUEL_WINDOW_HOUR,
        'request_cutoff': wins[0]['cutoff_hour'] if wins else REFUEL_REQUEST_CUTOFF,
        'description':    desc,
    }

class RefuelWindowIn(BaseModel):
    id: Optional[int] = None
    label: str
    start_hour: int
    start_min: Optional[int] = 0
    cutoff_hour: Optional[int] = None
    cutoff_min: Optional[int] = 30
    days_of_week: Optional[str] = 'mon,tue,wed,thu,fri,sat'
    active: Optional[int] = 1
    notes: Optional[str] = ''

@app.get("/api/forklifts/refuel-windows")
def list_refuel_windows_ep(active_only: bool = False):
    return list_refuel_windows(active_only=active_only)

@app.post("/api/forklifts/refuel-windows")
def upsert_refuel_window_ep(body: RefuelWindowIn):
    return upsert_refuel_window(
        id=body.id, label=body.label, start_hour=body.start_hour,
        start_min=body.start_min or 0, cutoff_hour=body.cutoff_hour,
        cutoff_min=body.cutoff_min or 30,
        days_of_week=body.days_of_week or 'mon,tue,wed,thu,fri,sat',
        active=body.active or 1, notes=body.notes or '')

@app.delete("/api/forklifts/refuel-windows/{wid}")
def delete_refuel_window_ep(wid: int):
    return delete_refuel_window(wid)

@app.get("/api/forklifts/oil-drums")
def list_oil_drums_ep(user: dict = Depends(require_auth)):
    """Materials usable as forklift oil (drums in warehouse stock)."""
    return list_oil_drum_materials()

@app.post("/api/forklifts/oil-requests")
def create_oil_request_ep(body: OilRequestIn, user: dict = Depends(require_auth)):
    try:
        return create_oil_request(
            forklift_id=body.forklift_id, oil_type=body.oil_type or 'hydraulic',
            qty_litres=body.qty_litres,
            requested_by=user.get('username') or '', notes=body.notes or '',
            priority=body.priority or 'NORMAL')
    except ValueError as e:
        raise HTTPException(400, str(e))

class OilPostponeIn(BaseModel):
    days: Optional[int] = 1
    reason: Optional[str] = ''

@app.post("/api/forklifts/oil-requests/{req_id}/postpone")
def postpone_oil_request_ep(req_id: int, body: OilPostponeIn,
                            user: dict = Depends(require_auth)):
    try:
        return postpone_oil_request(req_id, days=body.days or 1,
            actor=user.get('username') or '', reason=body.reason or '')
    except ValueError as e:
        raise HTTPException(400, str(e))

class OilRequestStatusIn(BaseModel):
    status: str
    fulfilled_qty: Optional[float] = None
    notes: Optional[str] = ''
    oil_material_id: Optional[int] = None   # which drum was dispensed

@app.patch("/api/forklifts/oil-requests/{req_id}")
def set_oil_request_status_ep(req_id: int, body: OilRequestStatusIn,
                              user: dict = Depends(require_auth)):
    try:
        return update_oil_request_status(req_id, body.status,
            fulfilled_qty=body.fulfilled_qty,
            actor=user.get('username') or '', notes=body.notes or '',
            oil_material_id=body.oil_material_id)
    except ValueError as e:
        raise HTTPException(400, str(e))


# ════════════════════════════════════════════════════════════════
# SCRAP / LG BIN
# ════════════════════════════════════════════════════════════════
SCRAP_REASONS = [
    'GLUE_DEFECT', 'CRACK', 'WARP', 'DELAMINATION', 'COLOUR_MISMATCH',
    'SURFACE_DAMAGE', 'WRONG_THICKNESS', 'EDGE_DAMAGE', 'OTHER',
]

class ScrapIn(BaseModel):
    batch_id: int
    dept: str
    pcs_scrapped: int
    reason_code: str
    reason_detail: Optional[str] = ''
    production_line: Optional[str] = ''

@app.get("/api/scrap")
def list_scrap_ep(disposition: Optional[str] = None, dept: Optional[str] = None,
                  user: dict = Depends(require_auth)):
    return list_scrap_entries(disposition=disposition, dept=dept)

@app.get("/api/scrap/reasons")
def list_scrap_reasons_ep(user: dict = Depends(require_auth)):
    return SCRAP_REASONS

@app.post("/api/scrap")
def create_scrap_ep(body: ScrapIn, user: dict = Depends(require_auth)):
    try:
        r = create_scrap_entry(
            batch_id=body.batch_id, dept=body.dept, pcs_scrapped=body.pcs_scrapped,
            reason_code=body.reason_code, reason_detail=body.reason_detail or '',
            production_line=body.production_line or '',
            created_by=user.get('username') or '')
        return _record_undo(user, 'scrap',
                            f"Scrap {body.pcs_scrapped} pcs · {r.get('batch_number','')}", r)
    except ValueError as e:
        raise HTTPException(400, str(e))

class ScrapDispIn(BaseModel):
    disposition: str   # REWORK | DOWNGRADE | DISPOSE | RECYCLE | PENDING_REVIEW
    notes: Optional[str] = ''

@app.patch("/api/scrap/{scrap_id}/disposition")
def set_scrap_disp_ep(scrap_id: int, body: ScrapDispIn,
                      user: dict = Depends(require_auth)):
    try:
        return set_scrap_disposition(scrap_id, body.disposition,
            reviewer=user.get('username') or '', notes=body.notes or '')
    except ValueError as e:
        raise HTTPException(400, str(e))


# ════════════════════════════════════════════════════════════════
# RAW-MATERIAL NCG + QA/QC review
# ════════════════════════════════════════════════════════════════
class NcgFlagIn(BaseModel):
    material_id: int
    qty: float
    source: str               # FC | WH | WLWH
    reason_code: str
    reason_detail: Optional[str] = ''

class NcgReviewIn(BaseModel):
    review_notes: Optional[str] = ''

class NcgDispositionIn(BaseModel):
    disposition: str          # DISPOSE | REGRADE | RESIZE
    qty: float
    target_material_id: Optional[int] = None
    yield_qty: Optional[float] = None
    new_target: Optional[dict] = None   # {code,name,type,unit,thickness_mm,width_mm,length_mm} to resize into a new SKU
    notes: Optional[str] = ''

@app.get("/api/ncg/reasons")
def ncg_reasons_ep(user: dict = Depends(require_auth)):
    return NCG_REASONS

@app.get("/api/ncg")
def list_ncg_ep(status: Optional[str] = None, user: dict = Depends(require_auth)):
    return list_ncg_items(status=status)

@app.post("/api/ncg/flag", status_code=201)
def flag_ncg_ep(body: NcgFlagIn, user: dict = Depends(require_auth)):
    """Flag raw-material stock as NCG (from FC sorting or WH handling). Deducts
    the qty from the source bucket and raises a QA/QC review item."""
    try:
        r = flag_material_ncg(
            material_id=body.material_id, qty=body.qty, source=body.source,
            reason_code=body.reason_code, reason_detail=body.reason_detail or '',
            flagged_by=user.get('username') or '')
        return _record_undo(user, 'ncg-flag',
                            f"Flag {body.qty} NCG from {body.source}", r)
    except ValueError as e:
        raise HTTPException(400, str(e))

@app.post("/api/ncg/{item_id}/review")
def review_ncg_ep(item_id: int, body: NcgReviewIn,
                  user: dict = Depends(require_role(Role.QA_QC, Role.MANAGERIAL))):
    try:
        return review_ncg_item(item_id, reviewer=user.get('username') or '',
                               review_notes=body.review_notes or '')
    except ValueError as e:
        raise HTTPException(400, str(e))

@app.post("/api/ncg/{item_id}/disposition", status_code=201)
def disposition_ncg_ep(item_id: int, body: NcgDispositionIn,
                       user: dict = Depends(require_role(Role.QA_QC, Role.MANAGERIAL))):
    try:
        r = add_ncg_disposition(
            ncg_item_id=item_id, disposition=body.disposition, qty=body.qty,
            target_material_id=body.target_material_id, yield_qty=body.yield_qty,
            new_target=body.new_target,
            notes=body.notes or '', created_by=user.get('username') or '')
        return _record_undo(user, 'ncg-disposition',
                            f"{body.disposition} {body.qty} (NCG #{item_id})", r)
    except ValueError as e:
        raise HTTPException(400, str(e))

@app.get("/api/qc/summary")
def qc_summary_ep(user: dict = Depends(require_auth)):
    return get_qc_summary()


# ════════════════════════════════════════════════════════════════
# UNDO — reverse my last action
# ════════════════════════════════════════════════════════════════
@app.get("/api/undo/last")
def undo_preview_ep(user: dict = Depends(require_auth)):
    """What the Undo button would reverse for this user (or null)."""
    return {"action": get_last_action(user.get('user_id') or user.get('username') or '')}

@app.post("/api/undo/last")
def undo_last_ep(user: dict = Depends(require_auth)):
    try:
        return undo_last_action(user.get('user_id') or user.get('username') or '',
                                undone_by=user.get('username') or '')
    except ValueError as e:
        raise HTTPException(400, str(e))


# ════════════════════════════════════════════════════════════════
# RETURN MATERIAL TO FC  (laminating → FC outbound transfer)
# ════════════════════════════════════════════════════════════════
class ReturnMatIn(BaseModel):
    material_id: int
    qty: float
    batch_ref: Optional[str] = ''
    reason: Optional[str] = ''

@app.post("/api/fc/return-material")
def return_material_ep(body: ReturnMatIn, user: dict = Depends(require_auth)):
    try:
        return return_material_to_fc(
            material_id=body.material_id, qty=body.qty,
            batch_ref=body.batch_ref or '', reason=body.reason or '',
            requested_by=user.get('username') or '')
    except ValueError as e:
        raise HTTPException(400, str(e))


@app.get("/api/fc/material-requirements")
def fc_material_requirements_ep(user: dict = Depends(require_auth)):
    """Suggested FC → laminating transfer requests based on every batch
    currently sitting at FC. Used by the FC Material Requests dashboard."""
    return get_fc_aggregate_requirements()

@app.get("/api/glue-mix/material-requirements")
def glue_mix_material_requirements_ep(user: dict = Depends(require_auth)):
    """Glue Mixing station shortfall: required component kg across all
    laminating batches in the pipeline vs current station stock."""
    return get_glue_mix_station_requirements()


@app.get("/api/planning/material-shortfalls")
def material_shortfalls_ep(types: str = "board,veneer"):
    """Planning view: every raw material short across all open sales POs.
    `types` is a comma-separated list of material types to include (default boards + veneers)."""
    type_list = [t.strip().lower() for t in (types or '').split(',') if t.strip()]
    if not type_list:
        type_list = ['board', 'veneer']
    return get_material_shortfalls(material_types=type_list)

@app.get("/api/export/purchase-requests")
def export_prs(status: Optional[str] = None):
    rows = list_purchase_requests(status=status)
    header = "request_number,request_type,material_code,material_name,qty_requested,uom,priority,needed_by,suggested_supplier,status,source_po_number,requested_by,requested_at,supplier_po_ref,notes"
    def esc(v):
        if v is None: return ''
        s = str(v); return '"'+s.replace('"','""')+'"' if (',' in s or '"' in s or '\n' in s) else s
    lines = [header]
    for r in rows:
        lines.append(",".join([esc(r.get(k,'')) for k in
            ('request_number','request_type','material_code','material_name','qty_requested','uom',
             'priority','needed_by','suggested_supplier','status','source_po_number',
             'requested_by','requested_at','supplier_po_ref','notes')]))
    return Response(content=("\n".join(lines)+"\n").encode("utf-8"), media_type="text/csv",
                    headers={"Content-Disposition": "attachment; filename=purchase_requests.csv"})


# ════════════════════════════════════════════════════════════════
# MATERIAL LOTS (FIFO) + DOCUMENTS
# ════════════════════════════════════════════════════════════════
class LotIn(BaseModel):
    material_id: int
    lot_code: str
    received_qty: float
    supplier: Optional[str] = ''
    supplier_lot_ref: Optional[str] = ''
    uom: Optional[str] = ''
    unit_cost: Optional[float] = 0
    expiry_date: Optional[str] = None
    purchase_request_id: Optional[int] = None
    notes: Optional[str] = ''

@app.get("/api/material-lots")
def get_lots(material_id: Optional[int] = None, only_active: bool = True,
             user: dict = Depends(require_auth)):
    return list_material_lots(material_id=material_id, only_active=only_active)

@app.post("/api/material-lots")
def post_lot(body: LotIn):
    try:
        return create_material_lot(
            material_id=body.material_id, lot_code=body.lot_code,
            received_qty=body.received_qty, supplier=body.supplier or '',
            supplier_lot_ref=body.supplier_lot_ref or '', uom=body.uom or '',
            unit_cost=body.unit_cost or 0, expiry_date=body.expiry_date,
            purchase_request_id=body.purchase_request_id, notes=body.notes or '')
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

class FifoIn(BaseModel):
    material_id: int
    qty: float
    batch_id: Optional[int] = None
    role: Optional[str] = ''
    notes: Optional[str] = ''

@app.post("/api/material-lots/consume")
def consume_lots(body: FifoIn, user: dict = Depends(require_auth)):
    return fifo_consume_lots(material_id=body.material_id, qty=body.qty,
        batch_id=body.batch_id, role=body.role or '',
        consumed_by=user.get('username') or '', notes=body.notes or '')


# ── Document storage (PDFs) ──
os.makedirs(DOCS_DIR, exist_ok=True)

ALLOWED_DOC_MIME = {'application/pdf'}
MAX_DOC_BYTES = 20 * 1024 * 1024  # 20 MB

@app.get("/api/material-documents")
def get_docs(material_id: Optional[int] = None, lot_id: Optional[int] = None,
             user: dict = Depends(require_auth)):
    return list_material_documents(material_id=material_id, lot_id=lot_id)

@app.post("/api/material-documents/upload")
async def upload_material_doc(
    material_id: int,
    doc_type: str = 'OTHER',
    lot_id: Optional[int] = None,
    notes: str = '',
    file: UploadFile = File(...),
    user: dict = Depends(require_auth),
):
    if file.content_type not in ALLOWED_DOC_MIME and not (file.filename or '').lower().endswith('.pdf'):
        raise HTTPException(status_code=400, detail="Only PDF files are allowed")
    raw = await file.read()
    if len(raw) > MAX_DOC_BYTES:
        raise HTTPException(status_code=413, detail=f"File exceeds {MAX_DOC_BYTES//1024//1024} MB limit")
    if len(raw) == 0:
        raise HTTPException(status_code=400, detail="Empty file")
    # Safe filename: prefix with uuid to avoid collisions
    safe_name = ''.join(c for c in (file.filename or 'doc.pdf') if c.isalnum() or c in '._-')
    stored = f"{date.today().isoformat()}_{hashlib.sha1(raw).hexdigest()[:10]}_{safe_name}"
    full = os.path.join(DOCS_DIR, stored)
    with open(full, 'wb') as f:
        f.write(raw)
    return register_material_document(
        material_id=material_id, lot_id=lot_id, doc_type=doc_type,
        filename=file.filename or safe_name, stored_path=stored, file_size=len(raw),
        content_type=file.content_type or 'application/pdf',
        uploaded_by=user.get('username') or '', notes=notes or '')

@app.get("/api/material-documents/{doc_id}/download")
def download_material_doc(doc_id: int):
    d = get_material_document(doc_id)
    if not d:
        raise HTTPException(status_code=404, detail="Document not found")
    full = os.path.join(DOCS_DIR, d['stored_path'])
    if not os.path.exists(full):
        raise HTTPException(status_code=404, detail="File missing on disk")
    return FileResponse(full, media_type=d.get('content_type') or 'application/pdf',
                        filename=d.get('filename') or 'document.pdf')

@app.delete("/api/material-documents/{doc_id}")
def remove_material_doc(doc_id: int):
    d = get_material_document(doc_id)
    if not d:
        raise HTTPException(status_code=404, detail="Document not found")
    result = delete_material_document(doc_id)
    # Best-effort file removal
    try:
        full = os.path.join(DOCS_DIR, d['stored_path'])
        if os.path.exists(full): os.remove(full)
    except Exception:
        pass
    return result


# ════════════════════════════════════════════════════════════════
# TRACEABILITY — per sales PO
# ════════════════════════════════════════════════════════════════
@app.get("/api/traceability/po/{po_id}")
def trace_po(po_id: int):
    """Document-centric traceability: every board/veneer/glue material that fed
    this PO, with all PDFs attached to those materials."""
    res = get_po_document_trace(po_id)
    if 'error' in res:
        raise HTTPException(status_code=404, detail=res['error'])
    return res

@app.get("/api/export/traceability/po/{po_id}/zip")
def export_trace_po_zip(po_id: int):
    """Bundle every supplier PDF for the PO's boards/veneers/glue into one ZIP,
    foldered by section, with an index.csv manifest."""
    import io, zipfile
    res = get_po_document_trace(po_id)
    if 'error' in res:
        raise HTTPException(status_code=404, detail=res['error'])
    po = res['purchase_order']
    po_num = po.get('po_number') or f"PO{po_id}"
    files = get_po_document_trace_files(po_id)

    def _safe(s):
        return ''.join(c if (c.isalnum() or c in ' ._-') else '_' for c in str(s or '')).strip() or 'file'

    buf = io.BytesIO()
    manifest = ["section,material_code,material_name,doc_type,filename,file_size,status"]
    used_names = set()
    with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as zf:
        for f in files:
            section = {'boards': 'Boards', 'veneers': 'Veneers', 'glue': 'Glue'}.get(f['section'], f['section'])
            full = os.path.join(DOCS_DIR, f['stored_path'])
            base = f"{_safe(f['material_code'])}__{_safe(f['doc_type'])}__{_safe(f['filename'])}"
            if not base.lower().endswith('.pdf'):
                base += '.pdf'
            arc = f"{section}/{base}"
            n = 1
            while arc in used_names:
                n += 1; arc = f"{section}/{n}_{base}"
            used_names.add(arc)
            status = 'ok'
            if os.path.exists(full):
                try:
                    zf.write(full, arc)
                except Exception:
                    status = 'read_error'
            else:
                status = 'missing_on_disk'
            mrow = [f['section'], f['material_code'], f['material_name'],
                    f['doc_type'], f['filename'], str(f['file_size']), status]
            manifest.append(",".join('"'+str(v or '').replace('"','""')+'"' for v in mrow))
        zf.writestr("index.csv", "\n".join(manifest) + "\n")

    buf.seek(0)
    fname = f"traceability_{_safe(po_num)}_documents.zip"
    return Response(content=buf.getvalue(), media_type="application/zip",
                    headers={"Content-Disposition": f"attachment; filename={fname}"})


@app.get("/api/export/fg-incoming")
def export_fg_incoming():
    """Export incoming batches (still in production + pending receipt) as CSV."""
    data = get_fg_warehouse_dashboard()
    rows = (data.get('pending_receipt', []) or []) + (data.get('in_production', []) or [])
    def esc(v): return '"'+str(v or '').replace('"','""')+'"'
    lines = ["batch_number,sku,product_name,total_pcs,pallets,current_department,production_line,priority,po_number,customer,created_at"]
    for r in rows:
        lines.append(",".join([
            esc(r.get('batch_number')), esc(r.get('sku')), esc(r.get('product_name')),
            str(r.get('total_pcs') or 0), str(r.get('quantity') or 0),
            esc(r.get('current_department')), esc(r.get('production_line')),
            str(r.get('priority') or ''), esc(r.get('po_number')),
            esc(r.get('customer')), esc(r.get('created_at') or ''),
        ]))
    content = "\n".join(lines) + "\n"
    return Response(content=content.encode("utf-8"), media_type="text/csv",
                    headers={"Content-Disposition": "attachment; filename=fg_incoming_export.csv"})

@app.get("/api/export/fg-open-pos")
def export_fg_open_pos():
    """Export open POs with line-by-line fulfillment as CSV."""
    data = get_fg_warehouse_dashboard()
    pos = data.get('open_pos', [])
    def esc(v): return '"'+str(v or '').replace('"','""')+'"'
    lines = ["po_number,customer,delivery_date,status,sku,product_name,production_line,pallets_ordered,pcs_ordered,pcs_in_stock,fulfillment_pct"]
    for p in pos:
        for ln in p.get('lines', []) or [{'sku':'','product_name':'','production_line':'','pallets_ordered':0,'pcs_ordered':0,'pcs_in_stock':0,'fulfillment_pct':0}]:
            lines.append(",".join([
                esc(p.get('po_number')), esc(p.get('customer')),
                esc(p.get('delivery_date')), esc(p.get('status')),
                esc(ln.get('sku')), esc(ln.get('product_name')),
                esc(ln.get('production_line')),
                str(ln.get('pallets_ordered') or 0), str(ln.get('pcs_ordered') or 0),
                str(ln.get('pcs_in_stock') or 0), str(ln.get('fulfillment_pct') or 0),
            ]))
    content = "\n".join(lines) + "\n"
    return Response(content=content.encode("utf-8"), media_type="text/csv",
                    headers={"Content-Disposition": "attachment; filename=fg_open_pos_export.csv"})

@app.post("/api/fc/transfer-requests", status_code=201)
def create_fc_transfer(body: FcTransferRequestIn, user: dict = Depends(require_auth)):
    data = body.dict()
    data['requested_by'] = user['user_id']
    try:
        return create_fc_transfer_request(data)
    except ValueError as e:
        raise HTTPException(400, str(e))

@app.post("/api/fc/return-requests", status_code=201)
def create_fc_return(body: FcTransferRequestIn, user: dict = Depends(require_auth)):
    """FC requests to return materials from FC stock back to main WH. WH must confirm pickup."""
    data = body.dict()
    data['requested_by'] = user['user_id']
    try:
        return create_fc_return_request(data)
    except ValueError as e:
        raise HTTPException(400, str(e))

@app.patch("/api/fc/transfer-requests/{request_id}/fulfill")
def fulfill_fc_transfer(request_id: str, body: FulfillIn,
                        user: dict = Depends(require_role(Role.WAREHOUSE))):
    try:
        r = fulfill_fc_transfer_request(request_id, body.qty_fulfilled, user['user_id'])
        return _record_undo(user, 'fulfill-fc-transfer',
                            f"Fulfil FC transfer {body.qty_fulfilled}", r)
    except ValueError as e:
        raise HTTPException(400, str(e))

@app.patch("/api/fc/transfer-requests/{request_id}/cancel")
def cancel_fc_transfer(request_id: str):
    return cancel_fc_transfer_request(request_id)

@app.post("/api/fc/stock/adjust")
def fc_stock_adjust(body: FcStockAdjustIn, user: dict = Depends(require_auth)):
    return adjust_fc_stock(body.material_id, body.qty_delta, user['user_id'])

# ── Veneer Re-grading ───────────────────────────────────────────
@app.post("/api/fc/regrade", status_code=201)
def fc_regrade(body: VeneerRegradeIn, user: dict = Depends(require_auth)):
    data = body.dict()
    data['graded_by'] = user['user_id']
    try:
        return create_veneer_regrade(data)
    except ValueError as e:
        raise HTTPException(400, str(e))

@app.get("/api/fc/regrade-log")
def fc_regrade_log(material_id: Optional[int] = None, limit: int = 50,
                   user: dict = Depends(require_auth)):
    return get_veneer_regrade_log(material_id=material_id, limit=limit)

# ── Production Order Veneer Grade-Mix Allocation ────────────────
@app.post("/api/production-orders/{order_id}/veneer-allocation", status_code=201)
def save_veneer_alloc(order_id: int, body: VeneerAllocIn,
                      user: dict = Depends(require_auth)):
    try:
        return save_veneer_alloc_and_confirm(
            order_id,
            [i.dict() for i in body.face_alloc],
            [i.dict() for i in body.back_alloc],
            deduct_fc_stock=body.deduct_fc_stock,
        )
    except ValueError as e:
        raise HTTPException(400, str(e))

@app.get("/api/production-orders/{order_id}/veneer-allocation")
def get_order_veneer_alloc(order_id: int):
    return get_veneer_alloc(order_id)

@app.get("/api/dept-costs")
def dept_costs(month_year: Optional[str] = None):
    return get_dept_cost_summary(month_year)

@app.get("/api/dept-costs/detail")
def dept_costs_detail(month_year: Optional[str] = None, department: Optional[str] = None,
                      user: dict = Depends(require_auth)):
    return get_dept_cost_detail(month_year, department)

# ── Admin endpoints ────────────────────────────────────────────
@app.get("/api/admin/login-log")
def get_login_log_route(limit: int = 200, user: dict = Depends(require_role(Role.MANAGERIAL))):
    return get_login_log(limit)

# ── Static / SPA ──────────────────────────────────────────────
if os.path.exists(FRONTEND_DIR):
    # Our own JS/CSS must REVALIDATE on every load, not be heuristically cached
    # by the browser. Without this, Starlette's StaticFiles sends no
    # Cache-Control, so browsers cache app scripts for ~minutes-to-hours and
    # operators keep running OLD code after we deploy a fix (this is what made
    # shipped bug-fixes appear to "still persist"). `no-cache` = always send a
    # conditional request; the ETag/Last-Modified yields a cheap 304 when the
    # file is unchanged and a fresh 200 the moment it changes.
    class _RevalidatingStatic(StaticFiles):
        async def get_response(self, path, scope):
            resp = await super().get_response(path, scope)
            if path.lower().endswith(('.js', '.css')):
                resp.headers['Cache-Control'] = 'no-cache, must-revalidate'
            return resp

    app.mount("/static", _RevalidatingStatic(directory=FRONTEND_DIR), name="static")

    # Single-page app HTML must never be cached — otherwise users see stale JS
    # after we ship updates. CDN assets (bootstrap etc) stay cacheable.
    _NO_CACHE = {"Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
                 "Pragma": "no-cache", "Expires": "0"}

    @app.get("/")
    def serve_index():
        return FileResponse(os.path.join(FRONTEND_DIR, "index.html"), headers=_NO_CACHE)

    @app.get("/admin")
    def serve_admin():
        return FileResponse(os.path.join(FRONTEND_DIR, "admin.html"), headers=_NO_CACHE)

    @app.get("/finance")
    def serve_finance():
        return FileResponse(os.path.join(FRONTEND_DIR, "finance.html"), headers=_NO_CACHE)

    @app.get("/qaqc")
    def serve_qaqc():
        return FileResponse(os.path.join(FRONTEND_DIR, "qaqc.html"), headers=_NO_CACHE)

    @app.get("/warehouse")
    def serve_warehouse():
        # Warehouse portal — serves the same SPA bundle but the front-end
        # detects window.location.pathname === '/warehouse' and switches into
        # warehouse-only mode (sidebar restricted, brand swap).
        return FileResponse(os.path.join(FRONTEND_DIR, "index.html"), headers=_NO_CACHE)

    @app.get("/{full_path:path}")
    def spa_fallback(full_path: str):
        fp = os.path.join(FRONTEND_DIR, full_path)
        if os.path.exists(fp): return FileResponse(fp)
        return FileResponse(os.path.join(FRONTEND_DIR, "index.html"))
