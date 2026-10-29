import sys, tempfile, json, unittest, threading, http.client
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'ctc-billing'/'scripts'))
import records
class Checks(unittest.TestCase):
    def test_records(self):
        original=records.ROOT
        with tempfile.TemporaryDirectory() as tmp:
            records.ROOT=Path(tmp)
            p={'job_id':'test-1','run_id':'run-1','subcategory':'CTC','created_date':'2026-10-29','work_status':'pending','general_agent':'agent-a','cosec_agent':'agent-b','billing_status':'pending'}
            records.record(p.copy());records.record(p.copy())
            with records.connect() as db:
                self.assertEqual(db.execute('SELECT COUNT(*) FROM jobs').fetchone()[0],1)
                self.assertEqual(db.execute('SELECT COUNT(*) FROM runs').fetchone()[0],1)
            p.update(run_id='run-2',work_status='completed',completed_date='2026-10-29',billing_status='issued',invoice_id='INV-1',invoice_date='2026-10-29',billed_sen=25000)
            records.record(p.copy())
            with records.connect() as db:
                self.assertEqual(db.execute('SELECT COUNT(*) FROM runs').fetchone()[0],2)
                saved=json.loads(db.execute('SELECT payload FROM jobs').fetchone()[0])
                self.assertEqual(saved['general_agent'],'agent-a');self.assertEqual(saved['cosec_agent'],'agent-b')
            p['job_id']='test-2'
            with self.assertRaises(ValueError):records.record(p)
            p['billed_sen']=2.5
            with self.assertRaises(ValueError):records.record(p)
        records.ROOT=original
    def test_live_api(self):
        c=http.client.HTTPConnection('127.0.0.1',8765)
        c.request('GET','/api/summary');r=c.getresponse();self.assertEqual(r.status,401);r.read()
        key=(records.ROOT/'executive-access-key.txt').read_text()
        c.request('POST','/login',json.dumps({'key':key}),{'Origin':'http://127.0.0.1:8765','Content-Type':'application/json'})
        r=c.getresponse();self.assertEqual(r.status,200);cookie=r.getheader('Set-Cookie').split(';')[0];r.read()
        c.request('GET','/api/summary',headers={'Cookie':cookie});r=c.getresponse();self.assertEqual(r.status,200);p=json.loads(r.read())
        self.assertEqual(set(p['categories'][0]),{'category','billed_sen','pending','completed'})
        self.assertNotIn('agent',json.dumps(p));self.assertEqual(p['categories'][0]['pending'],0)
        c.close()
if __name__=='__main__':unittest.main()
