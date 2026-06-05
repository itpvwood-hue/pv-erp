"""End-to-end test of the production module via HTTP."""
import sys, urllib.request, urllib.error, json
sys.stdout.reconfigure(encoding='utf-8')

BASE = 'http://localhost:8000'

def req(method, path, body=None):
    data = json.dumps(body).encode() if body else None
    headers = {'Content-Type': 'application/json'}
    try:
        r = urllib.request.urlopen(
            urllib.request.Request(BASE + path, data=data, headers=headers, method=method),
            timeout=5
        )
        content = r.read()
        return json.loads(content) if content else {}
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        print(f'  HTTP {e.code} on {method} {path}: {body[:200]}')
        raise

try:
    # 1. Employee
    emp = req('POST', '/api/employees', {'emp_name':'Test Op','department':'LAMINATING','role':'Laminator','line_id':'P01'})
    print(f'Employee: {emp}')

    # 2. Batch
    batch = req('POST', '/api/prod-batches', {'sku_code':'TEST-SKU','line_id':'P01','qty_planned':100,'shift':'MORNING'})
    bid = batch['batch_id']
    print(f'Batch: {bid} | status: {batch["status"]}')

    # 3. Glue mix
    req('POST', '/api/production/glue-mix', {'batch_id':bid,'recipe_code':'GLU-01','qty_kg':72.5,'operator_name':'Test Op'})
    b = req('GET', f'/api/prod-batches/{bid}')
    print(f'After glue mix: {b["status"]}')

    # 4. Laminating + advance
    req('POST', '/api/production/laminating', {'batch_id':bid,'table_id':'T01','emp_code_1':'EMP-001','emp_code_2':'EMP-002','pcs_target':100,'pcs_actual':97})
    req('POST', f'/api/prod-batches/{bid}/advance', {'next_status':'COLD_PRESS'})
    b = req('GET', f'/api/prod-batches/{bid}')
    print(f'After laminating: {b["status"]}')

    # 5. Cold press
    req('POST', '/api/production/cold-press', {'batch_id':bid,'machine_id':'CP-01','pcs_in':97,'pcs_out':97,'pressure_bar':8.5,'dwell_min':45})
    b = req('GET', f'/api/prod-batches/{bid}')
    print(f'After cold press: {b["status"]}')

    # 6. Repair + advance
    req('POST', '/api/production/repair', {'batch_id':bid,'table_id':'T01','repair_type':'ROUGH','emp_code_1':'EMP-003','emp_code_2':'EMP-004','pcs_repaired':97})
    req('POST', f'/api/prod-batches/{bid}/advance', {'next_status':'SANDING'})

    # 7. Sanding
    req('POST', '/api/production/sanding', {'batch_id':bid,'machine_id':'SND-01','grit_setting':'120','pcs_in':97,'pcs_out':95,'defect_count':2})
    b = req('GET', f'/api/prod-batches/{bid}')
    print(f'After sanding: {b["status"]}')

    # 8. Hot press
    req('POST', '/api/production/hot-press', {'batch_id':bid,'machine_id':'HP-01','temp_c':180,'pressure_bar':12,'press_time_min':8,'pcs_in':95,'pcs_out':95})
    b = req('GET', f'/api/prod-batches/{bid}')
    print(f'After hot press: {b["status"]}')

    # 9. Grading with NCG
    result = req('POST', '/api/production/grading', {
        'batch_id':bid,'grader_name':'QC Lead',
        'pcs_grade_a':88,'pcs_grade_b':4,'pcs_ncg':3,'pcs_reject':0,
        'ncg_reason_code':'NCG-SANDED-VENEER'
    })
    print(f'Grading: outcome={result.get("outcome")}')
    bt = result.get('backtrack')
    if bt:
        print(f'  Backtrack: lam_pairs={bt.get("lam_pairs")} | sanding_defects={bt.get("sanding_defects")} | reason={bt.get("ncg_reason_code")}')
    b = req('GET', f'/api/prod-batches/{bid}')
    print(f'Final status: {b["status"]}')

    # 10. Reports
    daily = req('GET', '/api/reports/daily')
    ncg_list = req('GET', '/api/reports/ncg-list')
    lam = req('GET', '/api/reports/lam-efficacy')
    print(f'\nReports: {len(daily)} daily rows | {len(ncg_list)} NCG batches | {len(lam)} lam efficacy rows')
    if ncg_list:
        n = ncg_list[0]
        print(f'  NCG: {n.get("batch_id")} | lam_efficacy={n.get("lam_efficacy_pct")}% | defects={n.get("sanding_defects")} | reason={n.get("ncg_reason_code")}')

    print('\nAll tests PASSED')

except Exception as e:
    print(f'ERROR: {e}')
    import traceback; traceback.print_exc()
