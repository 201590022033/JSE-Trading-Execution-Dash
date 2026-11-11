"""Loopback-only synthetic dashboard fixture for testing the alert banner.

No actual alerts, market data, model calls, provider calls or POSTs are allowed.
"""
import json
import mimetypes
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import re
from urllib.parse import urlsplit

ROOT=Path(__file__).resolve().parents[1]
TEMPLATE=(ROOT/'templates/dashboard.html').read_text(encoding='utf-8')
TEMPLATE=re.sub(r"\{\{\s*url_for\('static',\s*filename='([^']+)'\)\s*\}\}",r'/static/\1',TEMPLATE)
TEMPLATE=TEMPLATE.replace('<body>','<body><div style="background:#ffe766;color:#111;padding:8px">SYNTHETIC TEST ONLY — NOT A REAL ALERT</div>',1)


class Handler(BaseHTTPRequestHandler):
    def log_message(self,*args): pass
    def send(self,status,body,content_type):
        self.send_response(status); self.send_header('Content-Type',content_type)
        self.send_header('Cache-Control','no-store'); self.end_headers(); self.wfile.write(body)
    def do_POST(self): self.send(405,b'{}','application/json')
    def do_GET(self):
        path=urlsplit(self.path).path
        if path=='/': return self.send(200,TEMPLATE.encode('utf-8'),'text/html; charset=utf-8')
        if path.startswith('/static/'):
            target=(ROOT/path.lstrip('/')).resolve()
            if target.is_relative_to((ROOT/'static').resolve()) and target.is_file():
                return self.send(200,target.read_bytes(),mimetypes.guess_type(target.name)[0] or 'application/octet-stream')
        if path=='/api/v1/strategy-radar/monitor':
            data={'config':{'enabled':1,'interval_seconds':900,'profile':'intraday_30m_research_v1',
                    'desktop':0,'autostart':0,'last_status':'SYNTHETIC','last_check':'2026-11-10T11:00:00Z','last_error':None},
                  'worker_running':False,'events':[{'id':101,'instrument':'TEST_ONLY','state':'DEVELOPING',
                    'observed_at':'2026-11-10T11:00:00Z','desktop_status':'TEST_ONLY',
                    'trace':{'strategy_id':'synthetic','strategy_version':'1','passed':4,'applicable':5,'unknown':0,'rules':[]}}]}
            return self.send(200,json.dumps(data).encode(),'application/json')
        if path=='/api/v1/strategy-radar/watches': return self.send(200,b'{"watches":[]}','application/json')
        if path=='/api/v1/strategy-radar/swing': return self.send(200,b'{"evaluations":{}}','application/json')
        if path=='/api/v1/strategy-radar/catalog': return self.send(200,b'{"instruments":[]}','application/json')
        return self.send(404,b'{"error":"synthetic fixture unavailable"}','application/json')


if __name__=='__main__':
    server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
    print(json.dumps({'port':server.server_port,'pid':os.getpid()}),flush=True)
    server.serve_forever()
