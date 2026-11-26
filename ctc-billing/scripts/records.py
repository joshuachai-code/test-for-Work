"""Temporary Boardroom records. CLI: records.py record path/to/job.json"""
import json, os, sqlite3, sys, tempfile, subprocess
from pathlib import Path
from datetime import date, datetime, timezone
ROOT = Path(tempfile.gettempdir()) / ('boardroom-dashboard-' + str(os.getuid()))
def connect():
    ROOT.mkdir(mode=0o700, exist_ok=True)
    os.chmod(ROOT, 0o700)
    db = sqlite3.connect(ROOT / 'records.sqlite3')
    db.execute('CREATE TABLE IF NOT EXISTS jobs (id TEXT PRIMARY KEY, payload TEXT NOT NULL)')
    db.execute('CREATE TABLE IF NOT EXISTS runs (job TEXT, run TEXT, payload TEXT NOT NULL, PRIMARY KEY(job,run))')
    return db

def validate(p):
    for k in ('job_id','run_id','subcategory','created_date','work_status','general_agent','cosec_agent'):
        if not isinstance(p.get(k),str) or not p[k].strip(): raise ValueError('Required text field: '+k)
    if p['subcategory'] != 'CTC': raise ValueError('This workflow writer records CTC jobs only.')
    if p['work_status'] not in ('pending','blocked','completed'): raise ValueError('Invalid work_status')
    date.fromisoformat(p['created_date'])
    if p.get('due_date'): date.fromisoformat(p['due_date'])
    if p.get('workflow_stage') and p['workflow_stage'] not in ('received','preparation','review','approval','finance','completed'): raise ValueError('Invalid workflow_stage')
    if 'charge_sen' in p and (type(p['charge_sen']) is not int or p['charge_sen']<0): raise ValueError('charge_sen must be a nonnegative integer')
    if p['work_status']=='completed': date.fromisoformat(p['completed_date'])
    if p.get('billing_status','pending') not in ('pending','issued','not_required'): raise ValueError('Invalid billing_status')
    if p.get('billing_status')=='issued':
        if not p.get('invoice_id'): raise ValueError('Issued invoice requires invoice_id')
        date.fromisoformat(p['invoice_date'])
        if type(p.get('billed_sen')) is not int or p['billed_sen']<0: raise ValueError('billed_sen must be a nonnegative integer')
    else:
        p['billed_sen']=0
    return p

def record(p):
    validate(p)
    with connect() as db:
        for job_id, raw in db.execute('SELECT id,payload FROM jobs'):
            old=json.loads(raw)
            if job_id!=p['job_id'] and p.get('invoice_id') and old.get('invoice_id')==p['invoice_id']:
                raise ValueError('Invoice already assigned to another job; confirm allocation before recording')
        raw=json.dumps(p)
        db.execute('INSERT OR REPLACE INTO jobs VALUES (?,?)',(p['job_id'],raw))
        db.execute('INSERT OR REPLACE INTO runs VALUES (?,?,?)',(p['job_id'],p['run_id'],raw))
    return {'saved':True,'job_id':p['job_id'],'run_id':p['run_id']}

def record_excel(p, *, insert_missing=False):
    validate(p)
    p.setdefault('billing_status','pending')
    if not p.get('company_name'):raise ValueError('company_name is required for the Excel books')
    from excel_source import paths, read_book, load_source
    existing=read_book(paths()['cosec'],'cosec')
    for old in existing.values():
        if old['job_id']!=p['job_id'] and p.get('invoice_id') and old.get('invoice_id')==p['invoice_id']:
            raise ValueError('Invoice belongs to another job; confirm allocation first')
    for key in ('rate_rm','printing_rm'):
        if key in p:
            from excel_source import cents
            cents(p[key])
    if 'quantity' in p and (type(p['quantity']) is not int or p['quantity']<0):raise ValueError('quantity must be a nonnegative integer')
    node=Path.home()/'.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node'
    fd,filename=tempfile.mkstemp(suffix='.json',prefix='ctc-entry-')
    try:
        with os.fdopen(fd,'w') as f:json.dump(p,f)
        args=[str(node), str(Path(__file__).with_name('write_books.mjs')), filename]
        if insert_missing:
            args.append('--insert-missing')
        result=subprocess.run(args,capture_output=True,text=True)
        if result.returncode:raise ValueError(result.stderr.strip() or 'Workbook update failed')
        rows,source=load_source()
        # Verify the exact requested run in each saved workbook, not only the newest job snapshot.
        key=(p['job_id'],p['run_id'])
        g=read_book(paths()['general'],'general')[key];c=read_book(paths()['cosec'],'cosec')[key]
        if g['general_agent']!=p['general_agent'] or c['cosec_agent']!=p['cosec_agent']:raise ValueError('Attribution readback failed')
        return {'saved':True,'books_verified':2,'job_id':p['job_id'],'run_id':p['run_id'],'cloud_sync':'unverified'}
    finally:Path(filename).unlink(missing_ok=True)

def record_confirmed(p):
    """Insert the user-priced billing run once; preserve existing verified rows."""
    from excel_source import cents, load_source, paths, read_book

    validate(p)
    if not p.get('company_id') or not p.get('company_name'):
        raise ValueError('The company name and ID are required before saving.')
    if p.get('billing_unit') != 'page' or type(p.get('quantity')) is not int or p['quantity'] < 0:
        raise ValueError('A verified number of certified pages is required.')
    if any(p.get(field) in (None, '') for field in ('rate_rm', 'printing_rm')):
        raise ValueError('Ask for the CTC rate per page and total printing charge before saving.')
    total = p['quantity'] * cents(p['rate_rm']) + cents(p['printing_rm'])
    if 'charge_sen' in p and p['charge_sen'] != total:
        raise ValueError('The agreed total differs from CTC plus printing.')
    p['charge_sen'] = total
    key = (p['job_id'], p['run_id'])
    books = paths()

    def read_existing():
        found = {}
        for kind, path in books.items():
            row = read_book(path, kind).get(key)
            if row is None:
                continue
            if row['company_id'] != p.get('company_id') or row['company_name'] != p.get('company_name'):
                raise ValueError(f'{kind}: job/run already belongs to another company.')
            if kind == 'cosec' and (
                    row['quantity'] != p['quantity'] or row['billing_unit'] != 'page'
                    or cents(row['rate_rm']) != cents(p['rate_rm'])
                    or cents(row['printing_rm']) != cents(p['printing_rm'])
                    or cents(row['charge_rm']) != total):
                raise ValueError('Cosec row has different saved billing details. Review before changing it.')
            found[kind] = row
        return found

    previous = read_existing()
    if len(previous) < len(books):
        for kind, row in previous.items():
            field = kind + '_agent'
            p[field] = row[field]
        p['updated_at'] = (next(iter(previous.values()))['updated_at'] if previous
                           else datetime.now(timezone.utc).isoformat())
        record_excel(p, insert_missing=True)
    load_source()
    verified = read_existing()
    if set(verified) != set(books):
        raise ValueError('Both record-book rows could not be verified.')
    return {'saved': True, 'verified_books': [path.name for path in books.values()],
            'job_id': key[0], 'run_id': key[1], 'charge_sen': total, 'cloud_sync': 'unverified'}


if __name__=='__main__':
    try:
        actions = {'record': record_excel, 'record-confirmed': record_confirmed, 'stage': record}
        if len(sys.argv)!=3 or sys.argv[1] not in actions:
            raise ValueError('Usage: records.py {record|record-confirmed|stage} job.json')
        payload=json.loads(Path(sys.argv[2]).read_text())
        print(json.dumps(actions[sys.argv[1]](payload)))
    except (ValueError,KeyError,OSError) as e:
        print(str(e),file=sys.stderr);sys.exit(1)
