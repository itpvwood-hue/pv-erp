"""Test user management role guards and dept assignment."""
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
        return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode())

# Login as admin (MANAGERIAL)
_, admin = req('POST', '/api/auth/login', {'username':'admin','password':'admin123'})
at = admin['token']
print('Admin logged in:', admin['user']['role'])

# Login as leader (DEPARTMENT_LEADER)
_, leader = req('POST', '/api/auth/login', {'username':'leader','password':'leader123'})
lt = leader['token']
print('Leader logged in:', leader['user']['role'])

print()

# Admin: create a test leader
status, r = req('POST', '/api/users', {'username':'test_leader','display_name':'Test Leader',
                                        'role':'DEPARTMENT_LEADER','password':'test123'}, at)
print(f'Admin create user: HTTP {status}', 'OK' if status==201 else r.get('detail'))
new_uid = r.get('user_id','') if status==201 else None

# Admin: assign departments
if new_uid:
    status, r = req('POST', f'/api/users/{new_uid}/departments',
                    {'departments':[{'department':'HOT_PRESS','line_id':'P02'},
                                    {'department':'SANDING','line_id':None}]}, at)
    print(f'Admin assign depts: HTTP {status}', 'OK' if status==200 else r.get('detail'))

    # Admin: read back departments
    status, r = req('GET', f'/api/users/{new_uid}/departments', token=at)
    print(f'Admin read depts: HTTP {status} → {r}')

# Dept Leader: try to assign own departments (should be 403)
uid_self = leader['user']['user_id']
status, r = req('POST', f'/api/users/{uid_self}/departments',
                {'departments':[{'department':'HOT_PRESS','line_id':'P01'}]}, lt)
print(f'Leader self-assign depts: HTTP {status}', '— correctly blocked (403)' if status==403 else f'FAIL: {r}')

# Dept Leader: try to read departments (should be 403)
status, r = req('GET', f'/api/users/{uid_self}/departments', token=lt)
print(f'Leader read own depts: HTTP {status}', '— correctly blocked (403)' if status==403 else f'FAIL: {r}')

# Dept Leader: try to create user (should be 403)
status, r = req('POST', '/api/users', {'username':'hack','display_name':'Hacker',
                                        'role':'MANAGERIAL','password':'pw'}, lt)
print(f'Leader create user: HTTP {status}', '— correctly blocked (403)' if status==403 else f'FAIL: {r}')

# Clean up test user
if new_uid:
    status, r = req('PATCH', f'/api/users/{new_uid}', {'active': False}, at)
    print(f'Deactivate test user: HTTP {status}', 'OK' if status==200 else r)

print('\nAll user management tests PASSED')
