"""Debug the production module API directly (no server needed)."""
import sys, os
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, os.path.dirname(__file__))

from database import (
    save_employee, create_prod_batch,
    log_glue_mix, log_laminating, log_cold_press,
    log_repair, log_sanding, log_hot_press, log_grading,
    advance_prod_batch_status, get_prod_batch,
    get_daily_production, get_ncg_backtrack_list, get_lam_efficacy_report
)

print("Testing save_employee...")
try:
    emp = save_employee({'emp_name':'Test Op','department':'LAMINATING','role':'Laminator','line_id':'P01'})
    print("OK:", emp)
except Exception as e:
    print("ERROR:", e)
    import traceback; traceback.print_exc()

print("\nTesting create_prod_batch...")
try:
    b = create_prod_batch({'sku_code':'TEST-SKU','line_id':'P01','qty_planned':100,'shift':'MORNING'})
    print("OK:", b)
    bid = b['batch_id']

    print("\nGlue mix...")
    mid = log_glue_mix({'batch_id':bid,'recipe_code':'GLU-01','qty_kg':72.5,'operator_name':'Test Op'})
    print("mix_id:", mid)
    print("batch status after glue:", get_prod_batch(bid)['status'])

    print("\nLaminating...")
    lid = log_laminating({'batch_id':bid,'table_id':'T01','emp_code_1':'EMP-001','emp_code_2':'EMP-002','pcs_target':100,'pcs_actual':97})
    advance_prod_batch_status(bid, 'COLD_PRESS')
    print("lam_id:", lid, "| status:", get_prod_batch(bid)['status'])

    print("\nCold press...")
    cid = log_cold_press({'batch_id':bid,'machine_id':'CP-01','pcs_in':97,'pcs_out':97,'pressure_bar':8.5,'dwell_min':45})
    print("cp_id:", cid, "| status:", get_prod_batch(bid)['status'])

    print("\nRepair...")
    rid = log_repair({'batch_id':bid,'table_id':'T01','repair_type':'ROUGH','emp_code_1':'EMP-003','emp_code_2':'EMP-004','pcs_repaired':97})
    advance_prod_batch_status(bid, 'SANDING')
    print("rep_id:", rid)

    print("\nSanding...")
    sid = log_sanding({'batch_id':bid,'machine_id':'SND-01','grit_setting':'120','pcs_in':97,'pcs_out':95,'defect_count':2})
    print("sand_id:", sid, "| status:", get_prod_batch(bid)['status'])

    print("\nHot press...")
    hid = log_hot_press({'batch_id':bid,'machine_id':'HP-01','temp_c':180,'pressure_bar':12,'press_time_min':8,'pcs_in':95,'pcs_out':95})
    print("hp_id:", hid, "| status:", get_prod_batch(bid)['status'])

    print("\nGrading with NCG...")
    result = log_grading({'batch_id':bid,'grader_name':'QC Lead','pcs_grade_a':88,'pcs_grade_b':4,'pcs_ncg':3,'pcs_reject':0,'ncg_reason_code':'NCG-SANDED-VENEER'})
    print("grading result:", result)
    print("final status:", get_prod_batch(bid)['status'])

    print("\n--- Reports ---")
    daily = get_daily_production()
    print(f"Daily rows: {len(daily)}")
    ncg = get_ncg_backtrack_list()
    print(f"NCG backtrack rows: {len(ncg)}")
    if ncg:
        n = ncg[0]
        print(f"  {n['batch_id']} | lam={n.get('lam_efficacy_pct')}% | defects={n.get('sanding_defects')} | reason={n.get('ncg_reason_code')}")

    print("\nAll DB tests PASSED")

except Exception as e:
    print("ERROR:", e)
    import traceback; traceback.print_exc()
