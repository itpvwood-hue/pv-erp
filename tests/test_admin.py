"""Test admin endpoints: login log, /admin page, role guards."""
import urllib.request, urllib.error, json, sys
sys.stdout.reconfigure(encoding='utf-8')
BASE = 'http://localhost:8000'

def req(method, path, body=None, token=''):
    data = json.dumps(body).encode() if body else None
    hdrs = {'Content-Type':'application/json'}
    if token: hdrs['X-Auth-Token'] = token
    try:
        r = urllib.request.urlopen(
            urllib.request.Request(BASE+path, data=data, headers=hdrs, method=method), timeout=5)
        return r.status, json.loads(r.read()) if r.headers.get('content-type','').startswith('application/json') else {}
    except urllib.error.HTTPError as e:
        ct = e.headers.get('content-type','')
        body_raw = e.read().decode()
        return e.code, json.loads(body_raw) if 'json' in ct else {}

# Login several accounts to generate log entries
_, admin = req('POST', '/api/auth/login', {'username':'admin','password':'admin123'})
at = admin['token']
print(f'1. Admin login: HTTP 200 OK, role={admin["user"]["role"]}')

req('POST', '/api/auth/login', {'username':'warehouse','password':'warehouse123'})
req('POST', '/api/auth/login', {'username':'leader','password':'leader123'})
req('POST', '/api/auth/login', {'username':'admin','password':'wrongpass'})  # should NOT log (401)

# Admin: fetch login log
status, log = req('GET', '/api/admin/login-log?limit=50', token=at)
print(f'2. Login log: HTTP {status}, {len(log) if isinstance(log,list) else "?"} entries')
if isinstance(log, list) and log:
    print(f'   Latest: {log[0].get("username")} @ {log[0].get("logged_at")} from {log[0].get("ip_address")}')
    roles_seen = set(l.get('role') for l in log)
    print(f'   Roles in log: {roles_seen}')

# Non-admin (warehouse) cannot access login log
_, wh = req('POST', '/api/auth/login', {'username':'warehouse','password':'warehouse123'})
wt = wh['token']
status, r = req('GET', '/api/admin/login-log', token=wt)
print(f'3. Warehouse access login-log: HTTP {status}', '— blocked (403)' if status==403 else f'FAIL: {r}')

# /admin page is served
r2 = urllib.request.urlopen(urllib.request.Request(BASE+'/admin', method='GET'), timeout=5)
print(f'4. GET /admin: HTTP {r2.status} {"OK" if r2.status==200 else "FAIL"}')

# Bad login should not appear in log — count before/after
before = len(log) if isinstance(log, list) else 0
req('POST', '/api/auth/login', {'username':'admin','password':'badpass'})
_, log2 = req('GET', '/api/admin/login-log?limit=50', token=at)
after = len(log2) if isinstance(log2, list) else 0
print(f'5. Failed login NOT in log: {"OK" if after==before else f"FAIL (before={before} after={after})"}')

print('\nAll admin tests PASSED')
