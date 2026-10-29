import fs from 'node:fs/promises';
import path from 'node:path';
import {Workbook,SpreadsheetFile} from '@oai/artifact-tool';
const root=path.resolve(import.meta.dirname,'../..');
const spec=JSON.parse(await fs.readFile(path.join(root,'ctc-billing/scripts/books.json'),'utf8'));
const out=path.join(root,'outputs/ctc-books');
await fs.mkdir(out,{recursive:true});
for (const type of ['general','cosec']) {
 const def=spec[type], wb=Workbook.create(), sh=wb.worksheets.add('Records');
 const n=def.columns.length;
 sh.showGridLines=false;sh.tabColor='#152b47';
 sh.getRangeByIndexes(0,0,20,n).format.font={name:'Arial',size:10,color:'#233348'};
 sh.getRangeByIndexes(0,0,20,n).format.columnWidth=20;
 sh.getRangeByIndexes(0,0,20,n).format.rowHeight=24;
 sh.getRange('A2').values=[[def.title]];sh.getRange('A2').format.font={name:'Arial',size:16,bold:true,color:'#152b47'};
 sh.getRange('A3').values=[['One row per workflow run. Keep Job ID and Run ID identical in both books.']];
 sh.getRange('A3').format.font={name:'Arial',size:10,italic:true,color:'#6c7785'};
 sh.getRangeByIndexes(4,0,1,n).values=[def.columns.map(c=>c[0])];
 sh.tables.add(sh.getRangeByIndexes(4,0,2,n),true,type==='general'?'CTCGeneral':'CTCCosec');
 sh.getRangeByIndexes(4,0,1,n).format={fill:'#152b47',font:{name:'Arial',size:10,bold:true,color:'#ffffff'},wrapText:true,rowHeight:36,horizontalAlignment:'center',verticalAlignment:'center'};
 sh.getRangeByIndexes(5,0,15,n).format.fill='#f7f9fc';
 for(let i=0;i<n;i++){
  const [label,key]=def.columns[i],r=sh.getRangeByIndexes(5,i,1995,1);
  if(key.endsWith('_date'))r.setNumberFormat('yyyy-mm-dd');
  else if(key.endsWith('_rm'))r.setNumberFormat('"RM "#,##0.00');
  else if(key==='quantity')r.setNumberFormat('0');
  else r.setNumberFormat('@');
  if(['company_name','general_work','cosec_work','quantity_evidence','company_source','scan_reference','updated_at'].includes(key))sh.getRangeByIndexes(0,i,20,1).format.columnWidth=32;
  const lists={work_status:['pending','blocked','completed'],workflow_stage:['received','preparation','review','approval','finance','completed'],billing_status:['pending','issued','not_required'],subcategory:['CTC'],billing_unit:['copy','set','page']};
  if(lists[key])r.dataValidation={rule:{type:'list',values:lists[key]}};
 }
 sh.freezePanes.freezeRows(5);sh.freezePanes.freezeColumns(2);
 wb.recalculate();
 console.log((await wb.inspect({kind:'table',range:'Records!A5:F6',include:'values',tableMaxRows:2,tableMaxCols:6,maxChars:1000})).ndjson);
 for(let start=0;start<n;start+=5){
  const range=sh.getRangeByIndexes(0,start,9,Math.min(5,n-start));
  const image=await wb.render({sheetName:'Records',range:range.address,scale:1,format:'png'});
  await fs.writeFile(path.join(out,`${type}-${start}.png`),new Uint8Array(await image.arrayBuffer()));
 }
 await (await SpreadsheetFile.exportXlsx(wb)).save(path.join(out,def.filename));
 console.log('Created '+def.filename);
}
