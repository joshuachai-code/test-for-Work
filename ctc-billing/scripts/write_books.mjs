import fs from 'node:fs/promises';
import path from 'node:path';
import crypto from 'node:crypto';
import {FileBlob,SpreadsheetFile} from '@oai/artifact-tool';
const spec=JSON.parse(await fs.readFile(new URL('./books.json',import.meta.url),'utf8'));
const p=JSON.parse(await fs.readFile(process.argv[2],'utf8'));
for(const k of ['company_name','general_agent','cosec_agent'])if(!p[k])throw Error('Missing '+k);
const dir=path.join(process.env.BOARDROOM_DATA_ROOT||spec.root,spec.books_folder);
const lock=path.join(dir,'.ctc-write.lock');
let handle;
try{handle=await fs.open(lock,'wx')}catch{throw Error('CTC writer is busy or a prior write needs review. Check .ctc-write.lock before retrying.')}
const staged=[],saved=[];
const hash=b=>crypto.createHash('sha256').update(b).digest('hex');
try{
 const stamp=p.updated_at||new Date().toISOString();
 const data={...p,updated_at:stamp,charge_rm:p.charge_sen==null?null:p.charge_sen/100,billed_rm:p.billing_status==='issued'?p.billed_sen/100:null};
 for(const kind of ['general','cosec']){
  const def=spec[kind],file=path.join(dir,def.filename);
  try{await fs.access(path.join(dir,'~$'+def.filename));throw Error('Close the Excel record book before updating it')}catch(e){if(e.code!=='ENOENT')throw e}
  const original=await fs.readFile(file), wb=await SpreadsheetFile.importXlsx(await FileBlob.load(file)),sh=wb.worksheets.getItem('Records');
  const n=def.columns.length, values=sh.getUsedRange().values;
  if(JSON.stringify(values[4].slice(0,n))!==JSON.stringify(def.columns.map(c=>c[0])))throw Error('Unexpected workbook headers');
  const row=def.columns.map(([_,key])=>{
   const v=data[key];if(v===undefined||v===null||v==='')return null;
   if(key.endsWith('_date'))return new Date(v+'T12:00:00Z');
   if(typeof v==='string'&&v.startsWith('='))return "'"+v;
   return v;
  });
  const hits=[];for(let r=5;r<values.length;r++)if(values[r]?.[0]===p.job_id&&values[r]?.[1]===p.run_id)hits.push(r);
  if(hits.length>1)throw Error('Duplicate job/run in '+kind);
  if(hits.length)sh.getRangeByIndexes(hits[0],0,1,n).values=[row];
  else if(!values[5]?.[0])sh.getRangeByIndexes(5,0,1,n).values=[row];
  else sh.tables.items[0].rows.add(null,[row]);
  wb.recalculate();
  const tmp=path.join(dir,'.'+kind+'-'+crypto.randomUUID()+'.xlsx');
  await (await SpreadsheetFile.exportXlsx(wb)).save(tmp);
  staged.push({file,tmp,original,originalHash:hash(original)});
 }
 for(const x of staged)if(hash(await fs.readFile(x.file))!==x.originalHash)throw Error('Record book changed during preparation; retry after reviewing it');
 // Keep recovery copies outside OneDrive. Two separate file replacements are not a distributed transaction.
 const backup=await fs.mkdtemp(path.join(process.env.TMPDIR||'/tmp','ctc-backup-'));
 for(const x of staged)await fs.writeFile(path.join(backup,path.basename(x.file)),x.original,{mode:0o600});
 for(const x of staged){if(hash(await fs.readFile(x.file))!==x.originalHash)throw Error('Concurrent change; partial write may require retry');await fs.rename(x.tmp,x.file);saved.push(path.basename(x.file));}
 console.log(JSON.stringify({saved_books:saved,updated_at:stamp,cloud_sync:'unverified'}));
}catch(e){console.error(JSON.stringify({error:e.message,saved_books:saved}));process.exitCode=1}
finally{for(const x of staged)await fs.rm(x.tmp,{force:true});await handle.close();await fs.rm(lock,{force:true})}
