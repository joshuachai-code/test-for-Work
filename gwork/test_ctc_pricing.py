import os
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'ctc-billing/scripts'))
from records import record_work
from excel_source import paths, read_book
from review_file import deliver

class QuantityReceipt(unittest.TestCase):
    def test_save_retry_and_conflict(self):
        with tempfile.TemporaryDirectory() as d, patch.dict(os.environ, BOARDROOM_DATA_ROOT=d):
            root=Path(d)
            folder=root/'CTC Records'
            folder.mkdir()
            from openpyxl import Workbook
            from openpyxl.worksheet.table import Table
            from excel_source import SPEC
            for kind,target in paths().items():
                wb=Workbook()
                ws=wb.active; ws.title='Records'; ws['A1']='CTC records'
                for i, (title,_) in enumerate(SPEC[kind]['columns'],1): ws.cell(5,i,title)
                from openpyxl.utils import get_column_letter
                ws.add_table(Table(displayName='Entries',ref=f'A5:{get_column_letter(ws.max_column)}6'))
                wb.save(target)
            source=root/'review.pdf';source.write_bytes(b'checked content')
            p=dict(task_id='task-A',job_id='job-A',run_id='run-01',company_name='Example',company_id='A',
                   created_date='2026-11-26',completed_date='2026-11-26',pages=6,copies=5,printed=35,file=str(source))
            with self.assertRaises(ValueError): record_work(dict(p,rate_rm=5))
            for _ in range(2):
                saved=record_work(p)
                self.assertEqual(saved['quantity'],30)
                self.assertIn('CTC counts v1: pages=6 copies=5 printed=35',saved['completion_note'])
                self.assertEqual((root/saved['review_file']).read_bytes(),source.read_bytes())
            for kind,path in paths().items():
                rows=read_book(path,kind);self.assertEqual(len(rows),1)
                if kind=='cosec':
                    for field in ('rate_rm','printing_rm','charge_rm','billed_rm'):self.assertEqual(next(iter(rows.values()))[field],'')
            with self.assertRaises(ValueError):record_work(dict(p,copies=4))
            source.write_bytes(b'changed')
            with self.assertRaises(ValueError):deliver(source,'task-A',root)
            with self.assertRaises(ValueError):deliver(source,'../escape',root)
