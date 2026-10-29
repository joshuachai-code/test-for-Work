"""Temporary Boardroom records. CLI: records.py record path/to/job.json"""
import json, os, sqlite3, sys, tempfile, subprocess
from pathlib import Path
from datetime import date
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

def record_excel(p):
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
        result=subprocess.run([str(node),str(Path(__file__).with_name('write_books.mjs')),filename],capture_output=True,text=True)
        if result.returncode:raise ValueError(result.stderr.strip() or 'Workbook update failed')
        rows,source=load_source()
        # Verify the exact requested run in each saved workbook, not only the newest job snapshot.
        key=(p['job_id'],p['run_id'])
        g=read_book(paths()['general'],'general')[key];c=read_book(paths()['cosec'],'cosec')[key]
        if g['general_agent']!=p['general_agent'] or c['cosec_agent']!=p['cosec_agent']:raise ValueError('Attribution readback failed')
        return {'saved':True,'books_verified':2,'job_id':p['job_id'],'run_id':p['run_id'],'cloud_sync':'unverified'}
    finally:Path(filename).unlink(missing_ok=True)

if __name__=='__main__':
    try:
        if len(sys.argv)!=3 or sys.argv[1] not in ('record','stage'):raise ValueError('Usage: records.py record job.json (both Excel books), or stage job.json (temporary staging only)')
        payload=json.loads(Path(sys.argv[2]).read_text())
        print(json.dumps(record_excel(payload) if sys.argv[1]=='record' else record(payload)))
    except (ValueError,KeyError,OSError) as e:
        print(str(e),file=sys.stderr);sys.exit(1)
