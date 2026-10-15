#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""FastAPI وقتی نصب باشد، وگرنه stdlib HTTP API؛ داشبورد محلی.

نمونه:
  python3 app.py --port 8002
  POST /api/scan {"target":"example.com","modules":["dns"]}
"""
from __future__ import annotations
import argparse,json,sys
from pathlib import Path
from urllib.parse import urlparse
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
try:
    from .osint_engine import VERSION,run_scan
    from .agents import ManagerAgent
except ImportError:
    try:
        from osint_engine import VERSION,run_scan  # type: ignore
        from agents import ManagerAgent  # type: ignore
    except ImportError:
        from osint.osint_engine import VERSION,run_scan  # type: ignore
        from osint.agents import ManagerAgent  # type: ignore


def serve_stdlib(host:str,port:int)->None:
 from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
 class H(BaseHTTPRequestHandler):
  def send(self,status,obj,ctype='application/json; charset=utf-8'):
   raw=obj if isinstance(obj,bytes) else json.dumps(obj,ensure_ascii=False,indent=2).encode()
   self.send_response(status);self.send_header('Content-Type',ctype);self.send_header('Content-Length',str(len(raw)));self.send_header('Access-Control-Allow-Origin','*');self.send_header('Access-Control-Allow-Headers','Content-Type');self.send_header('Access-Control-Allow-Methods','GET,POST,OPTIONS');self.end_headers();self.wfile.write(raw)
  def do_OPTIONS(self):self.send(200,{})
  def do_GET(self):
   if urlparse(self.path).path=='/api/health':return self.send(200,{'ok':True,'service':'osint','version':VERSION,'mode':'stdlib'})
   if urlparse(self.path).path=='/api/modules':return self.send(200,{'allowed':['dns','github'],'not_implemented':['social scraping','dark web','breach lookup','port scanning']})
   return self.send(200,(HERE/'static/index.html').read_bytes(),'text/html; charset=utf-8')
  def do_POST(self):
   if urlparse(self.path).path not in ('/api/scan','/api/analyze'):return self.send(404,{'error':'not_found'})
   try:
    n=int(self.headers.get('Content-Length','0'))
    if n>100000:return self.send(413,{'error':'payload_too_large'})
    data=json.loads(self.rfile.read(n) or b'{}');target=data.get('target','');mods=data.get('modules',['dns'])
    if not isinstance(target,str) or not target.strip():return self.send(400,{'error':'target_required'})
    if not isinstance(mods,list):return self.send(400,{'error':'modules_must_be_array'})
    return self.send(200,ManagerAgent().run(target.strip(),mods))
   except json.JSONDecodeError:return self.send(400,{'error':'invalid_json'})
   except Exception as e:return self.send(500,{'error':type(e).__name__,'detail':str(e)[:300]})
  def log_message(self,fmt,*args):print('[osint]',fmt%args)
 server=ThreadingHTTPServer((host,port),H);print(f'OSINT API (stdlib): http://{host}:{port}')
 try:server.serve_forever()
 except KeyboardInterrupt:pass
 finally:server.server_close()

def serve_fastapi(host:str,port:int)->None:
 from fastapi import FastAPI
 from fastapi.responses import FileResponse
 from pydantic import BaseModel,Field
 import uvicorn
 app=FastAPI(title='PerShiaA OSINT',version=VERSION,docs_url='/api/docs',redoc_url=None)
 class Scan(BaseModel):
  target:str=Field(min_length=1,max_length=253)
  modules:list[str]=['dns']
 @app.get('/api/health')
 def health():return {'ok':True,'service':'osint','version':VERSION,'mode':'fastapi'}
 @app.get('/api/modules')
 def modules():return {'allowed':['dns','github'],'not_implemented':['social scraping','dark web','breach lookup','port scanning']}
 @app.get('/')
 def index():return FileResponse(HERE/'static/index.html')
 @app.post('/api/scan')
 def scan(req:Scan):return ManagerAgent().run(req.target,req.modules)
 uvicorn.run(app,host=host,port=port,log_level='info')

def main():
 p=argparse.ArgumentParser();p.add_argument('--host',default='127.0.0.1');p.add_argument('--port',type=int,default=8002);p.add_argument('--stdlib',action='store_true');p.add_argument('--selftest',action='store_true');a=p.parse_args()
 if a.selftest:
  import urllib.request,threading,time
  t=threading.Thread(target=serve_stdlib,args=('127.0.0.1',a.port),daemon=True);t.start();time.sleep(.25)
  try:
   assert json.load(urllib.request.urlopen(f'http://127.0.0.1:{a.port}/api/health'))['ok']
   req=urllib.request.Request(f'http://127.0.0.1:{a.port}/api/scan',data=json.dumps({'target':'example.invalid','modules':['dns']}).encode(),headers={'Content-Type':'application/json'})
   x=json.load(urllib.request.urlopen(req));assert x['review']['approved']
   print('OSINT API selftest: PASS')
  except Exception as e:print('OSINT API selftest: FAIL',e);return 1
  return 0
 try:
  import fastapi,uvicorn
  if not a.stdlib:serve_fastapi(a.host,a.port);return 0
 except ImportError:pass
 serve_stdlib(a.host,a.port);return 0
if __name__=='__main__':sys.exit(main())
