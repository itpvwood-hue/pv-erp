"""Test login endpoint error messages."""
import urllib.request, urllib.error, json, sys
sys.stdout.reconfigure(encoding='utf-8')

BASE = 'http://localhost:8000'

tests = [
    ('admin', 'admin123', 200, 'valid admin'),
    ('admin', 'wrongpass', 401, 'wrong password'),
    ('nobody', 'admin123', 401, 'unknown user'),
    ('warehouse', 'warehouse123', 200, 'valid warehouse'),
    ('leader', 'leader123', 200, 'valid leader'),
]

all_ok = True
for u, p, expected_status, desc in tests:
    req = urllib.request.Request(BASE+'/api/auth/login',
        data=json.dumps({'username':u,'password':p}).encode(),
        headers={'Content-Type':'application/json'}, method='POST')
    try:
        r = urllib.request.urlopen(req, timeout=5)
        data = json.loads(r.read())
        status = 200
        extra = f"role={data['user']['role']}, display={data['user']['display_name']}"
    except urllib.error.HTTPError as e:
        status = e.code
        body = json.loads(e.read().decode())
        extra = f"detail=\"{body.get('detail')}\""

    ok = status == expected_status
    all_ok = all_ok and ok
    print(f"  {'OK' if ok else 'FAIL'} [{desc}] {u}/{p} -> HTTP {status} {extra}")

print()
print('All login tests PASSED' if all_ok else 'SOME TESTS FAILED')
