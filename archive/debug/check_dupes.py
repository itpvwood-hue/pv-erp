import re, sys, os
sys.stdout.reconfigure(encoding='utf-8')
with open(os.path.join(os.path.dirname(__file__), '..', 'frontend', 'index.html'), encoding='utf-8') as f:
    content = f.read()
ids = re.findall(r'id=["\']([^"\']+)["\']', content)
from collections import Counter
dupes = {id_: count for id_, count in Counter(ids).items() if count > 1}
login_dupes = {k:v for k,v in dupes.items() if any(x in k for x in ['login','dept-selector','myProfile','prof-','deptSelector'])}
print('Login-related duplicates:', login_dupes if login_dupes else 'NONE — clear!')
print(f'Total duplicate IDs in file: {len(dupes)}')
if dupes:
    print('All dupes:', list(dupes.items())[:20])
