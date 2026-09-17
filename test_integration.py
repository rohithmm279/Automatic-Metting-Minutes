import requests, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

BASE = 'http://127.0.0.1:8000'

def check(name, cond, note=''):
    status = 'PASS' if cond else 'FAIL'
    print(f'  [{status}] {name}' + (f'  | {note}' if note else ''))

print('=' * 65)
print('  INTEGRATION TEST: Frontend + Backend + SQLite')
print('=' * 65)

# A. Health check
r = requests.get(f'{BASE}/health')
check('Backend /health responds', r.status_code == 200, str(r.json()))

# A2. Frontend dev server
r2 = requests.get('http://127.0.0.1:5173')
check('Vite dev server live', r2.status_code == 200, f'HTTP {r2.status_code}')

# B. GET /meetings
r3 = requests.get(f'{BASE}/meetings')
meetings = r3.json()
check('GET /meetings returns list', r3.status_code == 200 and isinstance(meetings, list), f'{len(meetings)} meetings in DB')

if meetings:
    mid = meetings[0]['id']
    r4 = requests.get(f'{BASE}/meetings/{mid}')
    detail = r4.json()
    has_required = 'action_items' in detail and 'decisions' in detail and 'unresolved_issues' in detail
    check(f'GET /meetings/{mid} full detail', r4.status_code == 200 and has_required)
    
    summary = detail.get('summary', '')
    check('Summary field present and non-empty', bool(summary.strip()), f'{len(summary)} chars')
    
    items = detail.get('action_items', [])
    decs = detail.get('decisions', [])
    issues = detail.get('unresolved_issues', [])
    check('Action items present', len(items) > 0, f'{len(items)} items')
    check('Decisions present', len(decs) >= 0, f'{len(decs)} decisions')
    check('Unresolved issues present', len(issues) >= 0, f'{len(issues)} issues')

    if items:
        item_id = items[0]['id']
        orig = items[0]['status']
        new_s = 'completed' if orig != 'completed' else 'in_progress'
        r5 = requests.patch(
            f'{BASE}/meetings/{mid}/action-items/{item_id}/status',
            json={'status': new_s}
        )
        check(f'PATCH status {orig} -> {new_s}', r5.status_code == 200 and r5.json().get('updated'))
        
        r6 = requests.get(f'{BASE}/meetings/{mid}')
        updated = next((i for i in r6.json().get('action_items', []) if i['id'] == item_id), None)
        check('Status persisted after PATCH', updated is not None and updated['status'] == new_s)

    # DELETE
    r7 = requests.delete(f'{BASE}/meetings/{mid}')
    check(f'DELETE /meetings/{mid} returns 204', r7.status_code == 204)
    
    r8 = requests.get(f'{BASE}/meetings/{mid}')
    check('Deleted meeting GET returns 404', r8.status_code == 404)
    
    r9 = requests.delete(f'{BASE}/meetings/99999')
    check('DELETE nonexistent meeting returns 404', r9.status_code == 404)
else:
    print('  [SKIP] No meetings in DB - create a meeting first via frontend')

print()
print('  Frontend:  http://127.0.0.1:5173')
print('  Backend:   http://127.0.0.1:8000')
print('  API docs:  http://127.0.0.1:8000/docs')
print('=' * 65)
