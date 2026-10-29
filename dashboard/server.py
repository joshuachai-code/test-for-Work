import sys, json, secrets, hashlib, hmac
from pathlib import Path
from datetime import datetime, date, timedelta
from zoneinfo import ZoneInfo
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'ctc-billing'/'scripts'))
from records import ROOT, connect
from metrics import summarize
from excel_source import load_source, SourceError
connect().close()
key_file=ROOT/'executive-access-key.txt'
if not key_file.exists():
    key_file.write_text(secrets.token_urlsafe(24));key_file.chmod(0o600)
KEY=key_file.read_text().strip()
SESSION=secrets.token_urlsafe(32)
PAGE=(Path(__file__).parent/'index.html').read_bytes()
class Handler(BaseHTTPRequestHandler):
    def log_message(self,*args): pass
    def send(self,status,data,kind='application/json',cookie=None):
        self.send_response(status);self.send_header('Content-Type',kind);self.send_header('Cache-Control','no-store');self.send_header('X-Content-Type-Options','nosniff');self.send_header('X-Frame-Options','DENY')
        if cookie:self.send_header('Set-Cookie',cookie)
        self.end_headers();self.wfile.write(data if isinstance(data,bytes) else json.dumps(data).encode())
    def authorized(self):
        return any(hmac.compare_digest(c.strip(),'boardroom='+SESSION) for c in self.headers.get('Cookie','').split(';'))
    def do_POST(self):
        if self.path!='/login':return self.send(404,{})
        if self.headers.get('Origin')!='http://127.0.0.1:8765':return self.send(403,{})
        size=int(self.headers.get('Content-Length','0'))
        if size>2048:return self.send(413,{})
        try:p=json.loads(self.rfile.read(size))
        except ValueError:return self.send(400,{})
        if not hmac.compare_digest(str(p.get('key','')),KEY):return self.send(401,{'error':'Access key not recognised'})
        self.send(200,{'ok':True},cookie='boardroom='+SESSION+'; HttpOnly; SameSite=Strict; Path=/')
    def do_GET(self):
        if self.headers.get('Host')!='127.0.0.1:8765':return self.send(403,{})
        u=urlparse(self.path)
        if u.path=='/':return self.send(200,PAGE,'text/html; charset=utf-8')
        if u.path!='/api/summary':return self.send(404,{})
        if not self.authorized():return self.send(401,{'error':'Executive access required'})
        period=parse_qs(u.query).get('period',['all'])[0]
        today=datetime.now(ZoneInfo('Asia/Kuala_Lumpur')).date()
        try: warning=int(parse_qs(u.query).get('warning',['7'])[0])
        except ValueError: return self.send(400,{'error':'Invalid warning period'})
        if warning not in (3,7,14,30):return self.send(400,{'error':'Invalid warning period'})
        try: rows,source=load_source()
        except SourceError as e:return self.send(503,{'error':str(e),'source':{'status':'unavailable','kind':'onedrive_excel'}})
        result=summarize(rows,today,period,warning)
        result.update(updated=datetime.now(ZoneInfo('Asia/Kuala_Lumpur')).isoformat(),temporary=False,source=source)
        self.send(200,result)
if __name__=='__main__':
    print('Dashboard: http://127.0.0.1:8765',flush=True)
    print('Executive access key file: '+str(key_file),flush=True)
    ThreadingHTTPServer(('127.0.0.1',8765),Handler).serve_forever()
