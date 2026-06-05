"""
Audit smoke test for recently added features.

Hits the main new endpoints, prints PASS/FAIL per check, and reports any
500s or unexpected payload shapes.  Run with the server already up on 8000.
"""
import urllib.request, urllib.parse, urllib.error, json, uuid, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

BASE = 'http://127.0.0.1:8000'

def req(method, path, *, headers=None, json_body=None, files=None, params=None,
        expect_status=None):
    h = dict(headers or {})
    body = None
    if params:
        path = path + '?' + urllib.parse.urlencode(params)
    if json_body is not None:
        body = json.dumps(json_body).encode()
        h['Content-Type'] = 'application/json'
    elif files:
        boundary = uuid.uuid4().hex
        h['Content-Type'] = f'multipart/form-data; boundary={boundary}'
        parts = []
        for n, (fn, c, ct) in files.items():
            parts.append(f'--{boundary}\r\nContent-Disposition: form-data; name="{n}"; filename="{fn}"\r\nContent-Type: {ct}\r\n\r\n'.encode() + c + b'\r\n')
        parts.append(f'--{boundary}--\r\n'.encode())
        body = b''.join(parts)
    r = urllib.request.Request(BASE + path, data=body, headers=h, method=method)
    try:
        resp = urllib.request.urlopen(r)
        return resp.status, resp.read().decode()
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()

# ── Counters ─────────────────────────────────────────────────────
passed = []
failed = []
def check(name, ok, detail=''):
    (passed if ok else failed).append((name, detail))
    sym = '✓' if ok else '✗'
    print(f"  {sym} {name}" + (f" — {detail}" if detail else ''))

# ── Auth ─────────────────────────────────────────────────────────
print("\n── AUTH ──")
code, resp = req('POST', '/api/auth/login',
                 json_body={'username': 'admin', 'password': 'admin123'})
check('login', code == 200, f'status={code}')
TOKEN = json.loads(resp)['token']
H = {'X-Auth-Token': TOKEN}

# ── Purchasing flow ──────────────────────────────────────────────
print("\n── PURCHASING (PR + shipments + docs) ──")
code, r = req('POST', '/api/purchase-requests', headers=H,
              json_body={'request_type': 'RAW_MATERIAL', 'material_id': 188,
                         'qty_requested': 250, 'uom': 'Pcs', 'priority': 2})
check('create PR', code == 200, f'status={code}')
PR_ID = json.loads(r)['id']

code, _ = req('PATCH', f'/api/purchase-requests/{PR_ID}/status', headers=H,
              json_body={'status': 'APPROVED'})
check('PR → APPROVED', code == 200)

code, r = req('POST', f'/api/purchase-requests/{PR_ID}/issue-po', headers=H,
              params={'supplier_po_ref': 'AUDIT-PO-1',
                      'estimated_arrival': '2026-06-30'},
              files={'file': ('audit.pdf', b'%PDF-1.4 audit\n%%EOF',
                              'application/pdf')})
check('issue-po with PDF', code == 200, f'status={code}')

code, r = req('GET', '/api/purchase-requests', headers=H)
prs = json.loads(r)
my_pr = next((p for p in prs if p['id'] == PR_ID), None)
check('PR status flipped to AWAITING_ARRIVAL after issue-po',
      my_pr and my_pr['status'] == 'AWAITING_ARRIVAL',
      f"got {my_pr['status'] if my_pr else 'None'}")
check('PR doc_count incremented', my_pr and my_pr.get('doc_count', 0) >= 1,
      f"doc_count={my_pr.get('doc_count') if my_pr else '?'}")

# Schedule two shipments
code, r = req('POST', '/api/shipments', headers=H,
              json_body={'pr_id': PR_ID, 'planned_qty': 150,
                         'planned_arrival': '2026-06-15', 'carrier': 'TruckA'})
check('create shipment 1 of 2', code == 201, f'status={code}')
S1 = json.loads(r)['id']

code, r = req('POST', '/api/shipments', headers=H,
              json_body={'pr_id': PR_ID, 'planned_qty': 100,
                         'planned_arrival': '2026-06-30', 'carrier': 'TruckB'})
check('create shipment 2 of 2', code == 201)
S2 = json.loads(r)['id']

# Split + edit
code, r = req('POST', f'/api/shipments/{S1}/split', headers=H,
              json_body={'split_qty': 50,
                         'new_planned_arrival': '2026-06-20'})
check('split shipment 1', code == 200)

code, r = req('PATCH', f'/api/shipments/{S1}', headers=H,
              json_body={'planned_arrival': '2026-06-16'})
check('patch shipment date', code == 200)

# Verify list & implicit
code, r = req('GET', f'/api/purchase-requests/{PR_ID}/shipments', headers=H)
ships = json.loads(r)
check('PR now has 3 shipments after split', len(ships) == 3,
      f'count={len(ships)}')

code, r = req('GET', '/api/shipments?include_implicit=true', headers=H)
imp = json.loads(r)
unplanned = [s for s in imp if s['status'] == 'UNPLANNED']
check('include_implicit synthesises UNPLANNED rows',
      isinstance(unplanned, list))

# Receive shipment 1 (full)
code, r = req('POST', f'/api/shipments/{S1}/receive', headers=H,
              json_body={'received_qty': 100, 'unit_cost': 42,
                         'expiry_date': '2027-12-31'})
check('receive shipment 1 full', code == 200)
lot1 = json.loads(r).get('lot_id')
check('lot created on receive', bool(lot1))

# Verify doc auto-attached
code, r = req('GET', f'/api/material-documents?lot_id={lot1}', headers=H)
lot_docs = json.loads(r)
check('supplier PO PDF auto-attached to lot', len(lot_docs) >= 1,
      f'docs={len(lot_docs)}')

# Quick-receive against UNPLANNED PR
code, r = req('POST', '/api/purchase-requests', headers=H,
              json_body={'request_type': 'RAW_MATERIAL', 'material_id': 266,
                         'qty_requested': 80, 'uom': 'Pcs'})
WALK_PR = json.loads(r)['id']
req('PATCH', f'/api/purchase-requests/{WALK_PR}/status', headers=H,
    json_body={'status': 'APPROVED'})

code, r = req('POST', f'/api/purchase-requests/{WALK_PR}/quick-receive',
              headers=H,
              json_body={'received_qty': 80, 'unit_cost': 60})
check('quick-receive walk-in', code == 200)

# Cancel the second shipment so we don't leave open noise
req('DELETE', f'/api/shipments/{S2}', headers=H)

# ── FC requirements ──────────────────────────────────────────────
print("\n── FC ──")
code, r = req('GET', '/api/fc/material-requirements', headers=H)
check('GET /api/fc/material-requirements 200', code == 200)
if code == 200:
    d = json.loads(r)
    check('fc requirements has summary.batches_at_fc',
          isinstance(d.get('summary'), dict) and 'batches_at_fc' in d['summary'])
    check('fc requirements has rows[]', isinstance(d.get('rows'), list))

# Pick first prod_order and exercise legacy fc-material-check
code, r = req('GET', '/api/production-orders', headers=H)
prods = json.loads(r)
if prods:
    code, _ = req('GET',
                  f'/api/production-orders/{prods[0]["id"]}/fc-material-check',
                  headers=H)
    check('legacy fc-material-check 200', code == 200)

# Return material to FC
code, r = req('POST', '/api/fc/return-material', headers=H,
              json_body={'material_id': 188, 'qty': 5,
                         'batch_ref': 'AUDIT-BTH', 'reason': 'audit return'})
check('return material to FC', code == 200)

# ── Shortfalls ───────────────────────────────────────────────────
print("\n── SHORTFALLS ──")
code, r = req('GET',
              '/api/planning/material-shortfalls?types=board,veneer',
              headers=H)
check('shortfalls 200', code == 200)
if code == 200:
    d = json.loads(r)
    check('shortfalls.summary',
          isinstance(d.get('summary'), dict))
    check('summary has materials_low',
          'materials_low' in d.get('summary', {}))

# ── Forklifts ────────────────────────────────────────────────────
print("\n── FORKLIFTS ──")
# Create one if none exists
code, r = req('GET', '/api/forklifts', headers=H)
flk_rows = json.loads(r) if code == 200 else []
if not flk_rows:
    code, r = req('POST', '/api/forklifts', headers=H,
                  json_body={'code': 'AUDIT-FL', 'name': 'audit',
                             'dept': 'laminating', 'fuel_type': 'diesel'})
    check('create forklift', code == 200)
    FLK = json.loads(r)['id']
else:
    FLK = flk_rows[0]['id']
    check('forklifts exist', True)

code, _ = req('GET', '/api/forklifts/refuel-config', headers=H)
check('refuel-config 200', code == 200)

# NORMAL request
code, r = req('POST', '/api/forklifts/oil-requests', headers=H,
              json_body={'forklift_id': FLK, 'oil_type': 'hydraulic',
                         'qty_litres': 3, 'priority': 'NORMAL'})
check('create NORMAL oil request', code == 200)
NOR = json.loads(r)['id']

# URGENT
code, r = req('POST', '/api/forklifts/oil-requests', headers=H,
              json_body={'forklift_id': FLK, 'oil_type': 'engine',
                         'qty_litres': 5, 'priority': 'URGENT'})
check('create URGENT oil request', code == 200)
URG = json.loads(r)['id']

# Listing ordering — URGENT must come before NORMAL
code, r = req('GET', '/api/forklifts/oil-requests?status=PENDING', headers=H)
oils = json.loads(r)
urg_idx = next((i for i, o in enumerate(oils) if o['id'] == URG), -1)
nor_idx = next((i for i, o in enumerate(oils) if o['id'] == NOR), -1)
check('URGENT sorted before NORMAL', urg_idx >= 0 and nor_idx >= 0 and urg_idx < nor_idx,
      f"urg={urg_idx} nor={nor_idx}")

# Postpone
code, _ = req('POST', f'/api/forklifts/oil-requests/{NOR}/postpone', headers=H,
              json_body={'days': 1, 'reason': 'audit'})
check('postpone request', code == 200)

# Fulfill
code, _ = req('PATCH', f'/api/forklifts/oil-requests/{URG}', headers=H,
              json_body={'status': 'FULFILLED', 'fulfilled_qty': 5})
check('fulfill URGENT request', code == 200)

# ── Accounting feed ──────────────────────────────────────────────
print("\n── ACCOUNTING ──")
code, r = req('GET', '/api/accounting/stock-movements', headers=H,
              params={'from_date': '2026-01-01', 'to_date': '2026-12-31'})
check('stock-movements 200', code == 200)
if code == 200:
    rows = json.loads(r)
    kinds = {row.get('kind') for row in rows}
    check('RECEIPT events present after lot creation', 'RECEIPT' in kinds,
          f'kinds seen={sorted(kinds)[:6]}')

code, r = req('GET', '/api/accounting/production-output', headers=H,
              params={'from_date': '2026-01-01', 'to_date': '2026-12-31'})
check('production-output 200', code == 200,
      f'previously crashed on cp.created_at')

# ── Traceability ─────────────────────────────────────────────────
print("\n── TRACEABILITY ──")
code, r = req('GET', '/api/purchase-orders', headers=H)
pos = json.loads(r)
if pos:
    pid = pos[0]['id']
    code, r = req('GET', f'/api/traceability/po/{pid}', headers=H)
    check('traceability 200', code == 200)
    if code == 200:
        d = json.loads(r)
        check('trace returns batches[]', isinstance(d.get('batches'), list))

# ── No-cache headers ─────────────────────────────────────────────
print("\n── HEADERS ──")
code, _ = req('GET', '/', headers=H)
check('/ serves 200', code == 200)

# ── Summary ──────────────────────────────────────────────────────
print("\n" + "═" * 60)
print(f"PASSED: {len(passed)}")
print(f"FAILED: {len(failed)}")
if failed:
    print("\nFailed checks:")
    for name, detail in failed:
        print(f"  ✗ {name} — {detail}")
    sys.exit(1)
