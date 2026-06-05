"""End-to-end test: Packing station (Phase 3)."""
import sys, urllib.request, urllib.error, json
sys.stdout.reconfigure(encoding='utf-8')

BASE = 'http://localhost:8000'

def req(method, path, body=None, token=''):
    data = json.dumps(body).encode() if body else None
    headers = {'Content-Type': 'application/json'}
    if token: headers['X-Auth-Token'] = token
    try:
        r = urllib.request.urlopen(
            urllib.request.Request(BASE + path, data=data, headers=headers, method=method),
            timeout=5)
        return json.loads(r.read())
    except urllib.error.HTTPError as e:
        err_body = e.read().decode()[:800]
        print(f'  HTTP {e.code} on {method} {path}: {err_body}')
        raise

try:
    # Login
    admin = req('POST', '/api/auth/login', {'username': 'admin', 'password': 'admin123'})
    token = admin['token']

    # Create a batch and run it through to GRADING, then PACKING
    b = req('POST', '/api/prod-batches',
            {'sku_code': 'PKG-TEST', 'line_id': 'P01', 'qty_planned': 50, 'shift': 'MORNING'},
            token)
    bid = b['batch_id']
    print(f'1. Batch created: {bid} | status: {b["status"]}')

    # Fast-route through all stations to reach PACKING
    for station in ['LAMINATING', 'COLD_PRESS', 'REPAIR', 'SANDING', 'HOT_PRESS', 'GRADING', 'PACKING']:
        result = req('POST', f'/api/prod-batches/{bid}/advance', {'next_status': station}, token)
        print(f'   -> {station}: {result}')
    b2 = req('GET', f'/api/prod-batches/{bid}', token=token)
    print(f'2. Batch routed to: {b2["status"]}')

    # Log packing
    pack_result = req('POST', '/api/production/packing', {
        'batch_id': bid,
        'operator_name': 'Pack Operator A',
        'table_id': 'PKT-01',
        'pcs_in': 50,
        'pcs_packed': 48,
        'pcs_held': 2,
        'cartons_count': 4,
        'packaging_sku': 'PKG-STD-12MM',
        'notes': 'Minor surface marks - 2 pcs held for QC review'
    }, token)
    print(f'3. Packing logged: pack_id={pack_result["pack_id"]}')

    # Check station logs include packing
    logs = req('GET', f'/api/prod-batches/{bid}/logs', token=token)
    pack_logs = logs.get('packing', [])
    print(f'4. Station logs include packing: {len(pack_logs)} entry/entries')
    if pack_logs:
        p = pack_logs[0]
        print(f'   -> {p["operator_name"]} | {p["pcs_packed"]} packed | {p["cartons_count"]} cartons | held: {p["pcs_held"]}')

    # Route to COMPLETE
    req('POST', f'/api/prod-batches/{bid}/advance', {'next_status': 'COMPLETE'}, token)
    b3 = req('GET', f'/api/prod-batches/{bid}', token=token)
    print(f'5. Final status: {b3["status"]}')

    # Test packing center data (GRADING+PACKING batches)
    grading_batches = req('GET', '/api/prod-batches?status=GRADING', token=token)
    packing_batches = req('GET', '/api/prod-batches?status=PACKING', token=token)
    print(f'6. Packing center pipeline: {len(grading_batches)} in GRADING, {len(packing_batches)} in PACKING')

    print('\nAll packing (Phase 3) tests PASSED')

except Exception as e:
    print(f'ERROR: {e}')
    import traceback; traceback.print_exc()
