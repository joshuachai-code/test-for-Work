"""Publish an already verified document to two destinations. Does not fill or fact-check forms."""
import argparse
import hashlib
import json
import os
import re
from pathlib import Path

def check_manifest(m, digest):
    if m.get('output_sha256') != digest:
        raise ValueError('Verification refers to different file bytes; reverify the saved output')
    if m.get('status') not in ('verified', 'ready_for_signature'):
        raise ValueError('Only verified or ready-for-signature documents can be released')
    if m.get('unresolved') != []:
        raise ValueError('Unresolved information prevents release')
    for k in ('visual_review_passed', 'structural_review_passed', 'reconciliation_passed'):
        if m.get(k) is not True:
            raise ValueError('Required verification not recorded: ' + k)
    ids = m.get('inventory_ids')
    if not isinstance(ids, list) or not ids or any(not isinstance(i,str) or not i for i in ids) or len(ids)!=len(set(ids)):
        raise ValueError('A nonempty, unique field inventory is required')
    fields=m.get('fields')
    if not isinstance(fields,list) or any(not isinstance(f,dict) for f in fields):
        raise ValueError('Per-field verification is required')
    actual=[f.get('id') for f in fields]
    if len(actual)!=len(ids) or set(actual)!=set(ids):
        raise ValueError('Field checks do not cover the inventory exactly once')
    for f in fields:
        outcome=f.get('outcome')
        if outcome in ('matched','derived'):
            if not f.get('source_ref') or not isinstance(f.get('expected'),str) or not f['expected']:
                raise ValueError('A filled field lacks supporting evidence')
            if f['expected'] != f.get('observed'):
                raise ValueError('A saved field does not match its verified expected value')
            if outcome=='derived' and not f.get('calculation'):
                raise ValueError('Derived values require a documented calculation')
        elif outcome=='not_applicable':
            if not f.get('source_ref') or not f.get('reason') or f.get('observed') not in ('','N/A'):
                raise ValueError('Unsupported not-applicable field')
        elif outcome in ('optional_blank','awaiting_signature'):
            if not f.get('reason') or f.get('observed')!='':
                raise ValueError('An intentionally blank field lacks a reason or is not blank')
            if outcome=='awaiting_signature' and m['status']!='ready_for_signature':
                raise ValueError('Unsigned document must be ready_for_signature')
        else:
            raise ValueError('Unknown or unresolved field outcome')
    actions=m.get('human_actions')
    if not isinstance(actions,list) or any(not isinstance(a,str) or not a.strip() for a in actions):
        raise ValueError('human_actions must be a list of outstanding actions')
    if (m['status']=='verified' and actions) or (m['status']=='ready_for_signature' and not actions):
        raise ValueError('Verification status disagrees with outstanding human actions')

def component(value):
    if not isinstance(value,str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9 ._-]{0,159}',value) or value.endswith((' ','.')):
        raise ValueError('Use a safe single filename/company key without path separators')
    return value

def save_copy(target,data,digest):
    target.parent.mkdir(parents=True,exist_ok=True)
    if target.exists():
        if hashlib.sha256(target.read_bytes()).hexdigest()!=digest:
            raise ValueError('Different output already exists; choose a new filename')
        return 'existing_verified'
    # Exclusive creation prevents an unrelated output from being overwritten.
    # Interrupted writes remain visible as failures and must use a new filename.
    try:
        with target.open('xb') as f:
            f.write(data);f.flush();os.fsync(f.fileno())
    except FileExistsError:
        if hashlib.sha256(target.read_bytes()).hexdigest()!=digest:raise ValueError('Destination changed during save')
    if hashlib.sha256(target.read_bytes()).hexdigest()!=digest:raise ValueError('Saved copy hash mismatch')
    return 'saved_verified'

def deliver(file,manifest,company,filename,config):
    data=Path(file).read_bytes()
    if not data:raise ValueError('Output file is empty')
    digest=hashlib.sha256(data).hexdigest()
    check_manifest(manifest,digest)
    company=component(company);filename=component(filename)
    if Path(filename).suffix.lower()!=Path(file).suffix.lower():raise ValueError('Output extension must match verified file')
    roots=[Path(config[k]).expanduser().resolve() for k in ('local_output_root','onedrive_output_root')]
    if roots[0]==roots[1] or roots[0] in roots[1].parents or roots[1] in roots[0].parents:
        raise ValueError('Local and OneDrive output roots must be separate')
    outputs=[]
    for label,root in zip(('local','onedrive'),roots):
        target=root/company/filename
        try:
            if not target.resolve().is_relative_to(root):raise ValueError('Destination escapes configured output root')
            status=save_copy(target,data,digest)
            outputs.append({'destination':label,'path':str(target),'status':status,'sha256':digest})
        except (OSError,ValueError) as e:
            outputs.append({'destination':label,'path':str(target),'status':'failed','error':str(e)})
    return {'complete':all(x['status']!='failed' for x in outputs),'document_status':manifest['status'],'outputs':outputs,'onedrive_cloud_sync':'unverified','human_actions':manifest['human_actions']}

def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('file','manifest','company','filename'):p.add_argument('--'+name,required=True)
    p.add_argument('--config',default=str(Path(__file__).resolve().parents[1]/'config.json'))
    a=p.parse_args()
    try:
        result=deliver(a.file,json.loads(Path(a.manifest).read_text()),a.company,a.filename,json.loads(Path(a.config).read_text()))
        print(json.dumps(result,indent=2));return 0 if result['complete'] else 2
    except (ValueError,OSError,KeyError,TypeError) as e:
        print(json.dumps({'complete':False,'error':str(e)}));return 1

if __name__=='__main__':raise SystemExit(main())
