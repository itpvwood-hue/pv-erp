import urllib.request, json, sys; sys.stdout.reconfigure(encoding='utf-8')
BASE='http://localhost:8000'
at=json.loads(urllib.request.urlopen(urllib.request.Request(BASE+'/api/auth/login',
    data=json.dumps({'username':'admin','password':'admin123'}).encode(),
    headers={'Content-Type':'application/json'},method='POST'),timeout=5).read())['token']
log=json.loads(urllib.request.urlopen(urllib.request.Request(BASE+'/api/admin/login-log',
    headers={'X-Auth-Token':at},method='GET'),timeout=5).read())
valid_users={'admin','warehouse','leader','planner'}
print('All log entries:')
for l in log:
    print(f"  {l['logged_at']}  {l['username']:12}  {l['role']:20}  {l['ip_address']}")
no_failures = all(l['username'] in valid_users for l in log)
print(f"\nFailed logins NOT logged: {'YES - correct' if no_failures else 'NO - bug!'}")
print(f"Total entries: {len(log)}")
