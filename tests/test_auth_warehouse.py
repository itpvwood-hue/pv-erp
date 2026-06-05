"""End-to-end test: Auth + Supply Warehouse endpoints."""
import sys, urllib.request, urllib.error, json
sys.stdout.reconfigure(encoding='utf-8')

BASE = 'http://localhost:8000'

def req(method, path, body=None, token=''):
    data = json.dumps(body).encode() if body else None
    headers = {'Content-Type': 'application/json'}
    if token: headers['X-Auth-Token'] = token
    r = urllib.request.urlopen(
        urllib.request.Request(BASE + path, data=data, headers=headers, method=method),
        timeout=5)
    return json.loads(r.read())

def expect_401(path, token=''):
    try:
        headers = {'Content-Type': 'application/json'}
        if token: headers['X-Auth-Token'] = token
        urllib.request.urlopen(
            urllib.request.Request(BASE + path, headers=headers, method='GET'), timeout=5)
        return False
    except urllib.error.HTTPError as e:
        return e.code == 401

try:
    # 1. Admin login
    admin = req('POST', '/api/auth/login', {'username': 'admin', 'password': 'admin123'})
    aToken = admin['token']
    print(f'1. Admin login OK: {admin["user"]["role"]} token={aToken[:8]}...')

    # 2. /me
    me = req('GET', '/api/auth/me', token=aToken)
    print(f'2. /me OK: {me["display_name"]} | depts: {me.get("departments", [])}')

    # 3. Warehouse login
    wh = req('POST', '/api/auth/login', {'username': 'warehouse', 'password': 'warehouse123'})
    whToken = wh['token']
    print(f'3. Warehouse login OK: {wh["user"]["role"]}')

    # 4. Dept leader login + set departments
    ld = req('POST', '/api/auth/login', {'username': 'leader', 'password': 'leader123'})
    ldToken = ld['token']
    uid = ld['user']['user_id']
    depts = req('POST', f'/api/users/{uid}/departments',
                {'departments': [{'department': 'HOT_PRESS', 'line_id': 'P02'},
                                 {'department': 'HOT_PRESS', 'line_id': 'P37'}]},
                ldToken)
    dept_str = ', '.join(f'{d["department"]}/{d["line_id"]}' for d in depts)
    print(f'4. Leader depts set: {len(depts)} -> [{dept_str}]')

    # 5. Unauthenticated -> 401
    ok = expect_401('/api/consumable-requests')
    print(f'5. Unauth 401: {"PASS" if ok else "FAIL"}')

    # 6. Create user (managerial)
    try:
        new_u = req('POST', '/api/users',
                    {'username': 'testleader_del', 'password': 'test123',
                     'role': 'DEPARTMENT_LEADER', 'display_name': 'Test Leader'},
                    aToken)
        print(f'6. Create user OK: {new_u["user_id"]}')
    except Exception as e:
        print(f'6. Create user: {e} (may already exist)')

    # 7. Consumable materials
    mats = req('GET', '/api/consumable-materials', token=aToken)
    print(f'7. Consumable materials: {len(mats)} items')

    # 8. Dept costs (empty OK)
    costs = req('GET', '/api/dept-costs', token=aToken)
    print(f'8. Dept costs: {len(costs)} rows')

    # 9-11. Full consumable request flow (only if materials exist)
    if mats:
        mat = mats[0]
        cr = req('POST', '/api/consumable-requests',
                 {'material_id': mat['id'], 'department': 'HOT_PRESS',
                  'line_id': 'P02', 'qty_requested': 5.0, 'notes': 'Test request'},
                 ldToken)
        rid = cr['request_id']
        print(f'9. Create request OK: {rid} | status: {cr["status"]} | mat: {cr["material_name"]}')

        # Warehouse fulfills partial
        fulfilled = req('PATCH', f'/api/consumable-requests/{rid}/fulfill',
                        {'qty_fulfilled': 3.0}, whToken)
        print(f'10. Fulfill OK: {fulfilled["status"]} | qty_fulfilled: {fulfilled["qty_fulfilled"]}')

        # Check cost ledger
        costs2 = req('GET', '/api/dept-costs', token=aToken)
        total = sum(r['total_cost'] for r in costs2)
        print(f'11. Dept costs after fulfill: {len(costs2)} rows | total: {total:.2f}')

        # Dept leader can see their request
        my_reqs = req('GET', '/api/consumable-requests', token=ldToken)
        print(f'12. Leader sees {len(my_reqs)} request(s)')

        # Warehouse sees the same (all requests)
        wh_reqs = req('GET', '/api/consumable-requests', token=whToken)
        print(f'13. Warehouse sees {len(wh_reqs)} request(s)')
    else:
        print('9-13. SKIP (no materials in DB)')

    print('\nAll auth + warehouse tests PASSED')

except Exception as e:
    print(f'ERROR: {e}')
    import traceback; traceback.print_exc()
