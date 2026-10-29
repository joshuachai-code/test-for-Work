"""Read paired CTC workbooks without exposing operational rows in the dashboard API."""
import json, os, re, zipfile, posixpath
from pathlib import Path
from xml.etree import ElementTree as ET
from datetime import datetime, timedelta, timezone, date
from decimal import Decimal

SPEC=json.loads(Path(__file__).with_name('books.json').read_text())
NS={'s':'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
class SourceError(ValueError): pass
def paths():
    root=Path(os.environ.get('BOARDROOM_DATA_ROOT',SPEC['root']))/SPEC['books_folder']
    return {k:root/SPEC[k]['filename'] for k in ('general','cosec')}
def read_book(path,kind):
    with zipfile.ZipFile(path) as z:
        strings=[]
        if 'xl/sharedStrings.xml' in z.namelist():
            strings=[''.join(e.itertext()) for e in ET.fromstring(z.read('xl/sharedStrings.xml')).findall('s:si',NS)]
        workbook=ET.fromstring(z.read('xl/workbook.xml'))
        sheet=next((e for e in workbook.findall('s:sheets/s:sheet',NS) if e.get('name')=='Records'),None)
        if sheet is None: raise SourceError('Records worksheet missing')
        rid=sheet.get('{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id')
        rel=next(e for e in ET.fromstring(z.read('xl/_rels/workbook.xml.rels')) if e.get('Id')==rid)
        target=rel.get('Target');target=target.lstrip('/') if target.startswith('/') else posixpath.normpath('xl/'+target)
        cells={}
        for row in ET.fromstring(z.read(target)).findall('s:sheetData/s:row',NS):
            vals={}
            for c in row.findall('s:c',NS):
                addr=c.get('r');letters=re.match('[A-Z]+',addr)[0];idx=0
                for ch in letters:idx=idx*26+ord(ch)-64
                if c.find('s:f',NS) is not None: raise SourceError('Formula cells are not supported in the source table; enter confirmed values')
                v=c.find('s:v',NS);value=v.text if v is not None else ''
                if c.get('t')=='s':value=strings[int(value)]
                elif c.get('t')=='inlineStr':value=''.join(c.find('s:is',NS).itertext())
                elif c.get('t')=='e':raise SourceError('Excel error cell')
                elif value and c.get('t') not in ('str','d'):value=float(value)
                vals[idx-1]=value
            cells[int(row.get('r'))]=vals
        cols=SPEC[kind]['columns']
        if [cells.get(5,{}).get(i,'') for i in range(len(cols))]!=[x[0] for x in cols]:raise SourceError('Record book headers changed')
        out={}
        for row,vals in cells.items():
            if row<6 or not any(v not in ('',None) for v in vals.values()):continue
            p={key:vals.get(i,'') for i,(_,key) in enumerate(cols)}
            for k,v in list(p.items()):
                if k.endswith('_date') and v!='':
                    if isinstance(v,(int,float)):v=(datetime(1899,12,30)+timedelta(days=v)).date().isoformat()
                    if isinstance(v,str) and 'T' in v:v=datetime.fromisoformat(v.replace('Z','+00:00')).date().isoformat()
                    date.fromisoformat(str(v));p[k]=str(v)
            for k in ('job_id','run_id','company_name','created_date','subcategory','updated_at'):
                if not isinstance(p[k],str) or not p[k].strip():raise SourceError('Required source field missing')
            try:
                timestamp=datetime.fromisoformat(p['updated_at'].replace('Z','+00:00'))
                if timestamp.tzinfo is None:raise ValueError()
            except ValueError:raise SourceError('Updated at UTC requires a timestamp with timezone')
            p['_timestamp']=timestamp
            key=(p['job_id'],p['run_id'])
            if key in out:raise SourceError('Duplicate job/run row')
            out[key]=p
        return out

def cents(value):
    try:
        d=Decimal(str(value))*100
        if not d.is_finite() or d<0 or d!=d.to_integral_value():raise ValueError()
        return int(d)
    except Exception:raise SourceError('Invalid RM amount')

def load_source():
    files=paths()
    try:
        before={k:p.stat().st_mtime_ns for k,p in files.items()}
        books={k:read_book(p,k) for k,p in files.items()}
        if before!={k:p.stat().st_mtime_ns for k,p in files.items()}:raise SourceError('Books changed during read; retry refresh')
        if books['general'].keys()!=books['cosec'].keys():raise SourceError('The two books contain unmatched workflow runs')
        latest={}
        for key,g in books['general'].items():
            c=books['cosec'][key]
            for field in ('company_name','company_id','created_date','subcategory','updated_at'):
                if g[field]!=c[field]:raise SourceError('The two books contain conflicting records')
            if g['subcategory']!='CTC':raise SourceError('Unexpected category in CTC books')
            if not g['general_agent'] or not c['cosec_agent']:raise SourceError('Agent attribution missing')
            p={**c,**g}
            if p['work_status'] not in ('pending','blocked','completed'):raise SourceError('Invalid work status')
            if p['work_status']=='completed' and not p['completed_date']:raise SourceError('Completion date missing')
            if p['billing_status'] not in ('pending','issued','not_required'):raise SourceError('Invalid billing status')
            if p['charge_rm']!='':p['charge_sen']=cents(p['charge_rm'])
            p['billed_sen']=0
            if p['billing_status']=='issued':
                if not p['invoice_id'] or not p['invoice_date']:raise SourceError('Issued invoice reference/date missing')
                p['billed_sen']=cents(p['billed_rm'])
            old=latest.get(p['job_id'])
            if old and old['_timestamp']==p['_timestamp']:raise SourceError('Ambiguous latest workflow run')
            if old is None or old['_timestamp']<p['_timestamp']:latest[p['job_id']]=p
        invoices=[p['invoice_id'] for p in latest.values() if p['billing_status']=='issued']
        if len(invoices)!=len(set(invoices)):raise SourceError('An invoice occurs on more than one job')
        for p in latest.values():p.pop('_timestamp')
        source={'kind':'onedrive_excel','status':'ready','book_count':2,'job_count':len(latest),'last_read':datetime.now(timezone.utc).isoformat(),'cloud_sync':'unverified','modified_at':{k:datetime.fromtimestamp(v/1e9,timezone.utc).isoformat() for k,v in before.items()}}
        return list(latest.values()),source
    except (OSError,zipfile.BadZipFile,ET.ParseError,KeyError,ValueError) as e:
        if isinstance(e,SourceError):raise
        raise SourceError('Excel source unavailable or invalid; check both local workbooks') from e

if __name__=='__main__':
    rows,source=load_source();print(json.dumps(source))
