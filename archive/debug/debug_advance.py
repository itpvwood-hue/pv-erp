"""Debug the advance endpoint directly."""
import sys, urllib.request, urllib.error, json
sys.stdout.reconfigure(encoding='utf-8')

BASE = 'http://localhost:8000'

# Login first
r = urllib.request.urlopen(urllib.request.Request(
    BASE+'/api/auth/login',
    data=json.dumps({'username':'admin','password':'admin123'}).encode(),
    headers={'Content-Type':'application/json'}, method='POST'), timeout=5)
token = json.loads(r.read())['token']
print('Logged in, token:', token[:8]+'...')

# Create a batch
r2 = urllib.request.urlopen(urllib.request.Request(
    BASE+'/api/prod-batches',
    data=json.dumps({'sku_code':'TEST','line_id':'P01','qty_planned':10,'shift':'MORNING'}).encode(),
    headers={'Content-Type':'application/json','X-Auth-Token':token}, method='POST'), timeout=5)
b = json.loads(r2.read())
bid = b['batch_id']
print('Batch:', bid, '| status:', b['status'])

# Try advance WITHOUT token first
try:
    r3 = urllib.request.urlopen(urllib.request.Request(
        BASE+f'/api/prod-batches/{bid}/advance',
        data=json.dumps({'next_status':'LAMINATING'}).encode(),
        headers={'Content-Type':'application/json'}, method='POST'), timeout=5)
    print('Advance (no token):', json.loads(r3.read()))
except urllib.error.HTTPError as e:
    body = e.read().decode()
    print('Advance (no token) ERROR', e.code, ':', body[:500])

# Try advance WITH token
try:
    r4 = urllib.request.urlopen(urllib.request.Request(
        BASE+f'/api/prod-batches/{bid}/advance',
        data=json.dumps({'next_status':'LAMINATING'}).encode(),
        headers={'Content-Type':'application/json','X-Auth-Token':token}, method='POST'), timeout=5)
    print('Advance (with token):', json.loads(r4.read()))
except urllib.error.HTTPError as e:
    body = e.read().decode()
    print('Advance (with token) ERROR', e.code, ':', body[:500])
