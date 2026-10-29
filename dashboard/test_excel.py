import unittest, tempfile, shutil, os, sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'ctc-billing/scripts'))
from records import record_excel
from excel_source import load_source, paths, read_book, SourceError, SPEC
class ExcelIntegration(unittest.TestCase):
 def test_paired_roundtrip(self):
  with tempfile.TemporaryDirectory() as tmp:
   os.environ['BOARDROOM_DATA_ROOT']=tmp
   dest=Path(tmp)/SPEC['books_folder'];dest.mkdir()
   templates=Path(__file__).resolve().parents[1]/'outputs/ctc-books'
   for kind in ('general','cosec'):shutil.copyfile(templates/SPEC[kind]['filename'],dest/SPEC[kind]['filename'])
   p=dict(job_id='TEST-ONLY',run_id='RUN-1',company_name='Test company',created_date='2026-10-29',subcategory='CTC',work_status='pending',workflow_stage='review',general_agent='General agent',cosec_agent='Cosec agent',billing_status='pending',charge_sen=25000,quantity=5,billing_unit='copy',rate_rm=50,updated_at='2026-10-29T06:00:00Z')
   record_excel(p.copy());record_excel(p.copy())
   rows,status=load_source();self.assertEqual(len(rows),1);self.assertEqual(rows[0]['charge_sen'],25000)
   self.assertEqual(len(read_book(paths()['general'],'general')),1)
   p.update(run_id='RUN-2',work_status='completed',workflow_stage='completed',completed_date='2026-10-29',billing_status='issued',invoice_id='TEST-INV',invoice_date='2026-10-29',billed_sen=25000,updated_at='2026-10-29T07:00:00Z')
   record_excel(p)
   rows,status=load_source();self.assertEqual(len(rows),1);self.assertEqual(rows[0]['billed_sen'],25000);self.assertEqual(rows[0]['general_agent'],'General agent');self.assertEqual(rows[0]['cosec_agent'],'Cosec agent')
   self.assertEqual(len(read_book(paths()['general'],'general')),2)
   shutil.copyfile(templates/SPEC['cosec']['filename'],paths()['cosec'])
   with self.assertRaises(SourceError):load_source()
   del os.environ['BOARDROOM_DATA_ROOT']
if __name__=='__main__':unittest.main()
