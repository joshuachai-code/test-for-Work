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

def record_work(job):
    from excel_source import paths, read_book, load_source
    from review_file import deliver
    allowed = {'task_id','job_id','run_id','company_name','company_id','created_date','due_date',
               'completed_date','pages','copies','printed','file'}
    if set(job) - allowed:
        raise ValueError('Only work identifiers, dates, counts and the completed file belong in this receipt.')
    for field in ('pages','copies','printed'):
        value = job.get(field)
        if field == 'printed' and value is None:
            continue
        if type(value) is not int or not (int(field != 'printed') <= value <= 9999):
            raise ValueError('Invalid count: ' + field)
    for field in ('task_id','job_id','run_id','company_name','company_id','file'):
        if not isinstance(job.get(field),str) or not job[field].strip():
            raise ValueError('Missing ' + field)
    for field in ('created_date','completed_date'):
        date.fromisoformat(job[field])
    if job.get('due_date'): date.fromisoformat(job['due_date'])
    file = deliver(job['file'],job['task_id'])
    printed = job.get('printed')
    counts = f"CTC counts v1: pages={job['pages']} copies={job['copies']} printed={printed if printed is not None else 'unknown'}"
    evidence = f"{counts}\nReview file: {file['review_file']}\nSHA256: {file['sha256']}"
    entry = {k:job[k] for k in ('job_id','run_id','company_name','company_id','created_date','completed_date')}
    entry.update(subcategory='CTC', due_date=job.get('due_date'), general_agent='GWork', cosec_agent='GWork',
                 work_status='completed', workflow_stage='review', billing_status='pending',
                 quantity=job['pages']*job['copies'], billing_unit='page', quantity_evidence=evidence,
                 general_work=counts, cosec_work=counts, scan_reference=file['review_file'])
    key = (job['job_id'],job['run_id'])
    books = paths()
    def existing():
        rows = {}
        for kind,path in books.items():
            row = read_book(path,kind).get(key)
            if row is None: continue
            fields = ['company_id','company_name','completed_date','scan_reference','general_work'] if kind=='general' else ['company_id','company_name','quantity','quantity_evidence','cosec_work']
            if any(row[f] != entry[f] for f in fields) or (kind=='cosec' and any(row[f] != '' for f in ('rate_rm','printing_rm','charge_rm','billed_rm'))):
                raise ValueError(f'{kind}: existing run has different data. Check its receipt before retrying.')
            rows[kind] = row
        return rows
    prior = existing()
    if len(prior) != 2:
        entry['updated_at'] = next(iter(prior.values()))['updated_at'] if prior else datetime.now(timezone.utc).isoformat()
        record_excel(entry, insert_missing=True)
    load_source()
    if len(existing()) != 2: raise ValueError('Could not verify both books.')
    return {**file,'task_id':job['task_id'],'run_id':job['run_id'],'job_id':job['job_id'],
            'quantity':entry['quantity'],'verified_books':[p.name for p in books.values()],'completion_note':evidence}


if __name__=='__main__':
    try:
        if len(sys.argv)!=3 or sys.argv[1] != 'record-work':
            raise ValueError('Usage: records.py record-work job.json')
        print(json.dumps(record_work(json.loads(Path(sys.argv[2]).read_text()))))
    except (ValueError,KeyError,OSError) as e:
        print(str(e),file=sys.stderr);sys.exit(1)
