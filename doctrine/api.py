#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""API محلی دکترین؛ فقط stdlib، سازگار با شبکه‌ی آفلاین."""
from __future__ import annotations
import argparse, json, os, sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse, parse_qs
HERE=Path(__file__).resolve().parent
for _p in (HERE, HERE.parent):
    if str(_p) not in sys.path:
        sys.path.insert(0,str(_p))
try:
    from doctrine import doctrine_engine as de  # type: ignore
except ImportError:
    import doctrine_engine as de  # type: ignore

def _data_dir()->Path:
    override=os.environ.get('PERSHIAA_DATA_DIR','').strip()
    if override:
        p=Path(override)
        return p if p.is_absolute() else (HERE.parent/p).resolve()
    return (HERE.parent/'data').resolve()
DATA=_data_dir()
CORPUS_PATH=os.environ.get('PERSHIAA_CORPUS',str(DATA/'corpus'))
class Handler(BaseHTTPRequestHandler):
    server_version='PerShiaA-Doctrine/1.0'
    def _json(self,status,obj):
        raw=json.dumps(obj,ensure_ascii=False,indent=2).encode()
        self.send_response(status); self.send_header('Content-Type','application/json; charset=utf-8'); self.send_header('Content-Length',str(len(raw))); self.send_header('Access-Control-Allow-Origin','*'); self.send_header('Access-Control-Allow-Headers','Content-Type'); self.send_header('Access-Control-Allow-Methods','GET,POST,OPTIONS'); self.end_headers(); self.wfile.write(raw)
    def do_OPTIONS(self): self._json(200,{'ok':True})
    def do_GET(self):
        route=urlparse(self.path)
        if route.path=='/api/health': return self._json(200,{'ok':True,'service':'doctrine','version':de.VERSION,'offline':True})
        if route.path=='/api/schema': return self._json(200,de.schema())
        if route.path=='/api/evaluations': return self._json(200,de.check_manifest())
        if route.path=='/api/search':
            q=parse_qs(route.query).get('q',[''])[0]
            ledger=de.SourceLedger(); corpus=de.Corpus.load(CORPUS_PATH,ledger)
            return self._json(200,{'query':q,'results':corpus.search(q)})
        if route.path=='/':
            page=(Path(__file__).parent/'doctrine_app.html').read_bytes()
            self.send_response(200); self.send_header('Content-Type','text/html; charset=utf-8'); self.send_header('Content-Length',str(len(page))); self.end_headers(); self.wfile.write(page); return
        return self._json(404,{'error':'not_found','detail':'مسیر پیدا نشد'})
    def do_POST(self):
        if urlparse(self.path).path!='/api/analyze': return self._json(404,{'error':'not_found','detail':'مسیر پیدا نشد'})
        try:
            n=int(self.headers.get('Content-Length','0'))
            if n>2_000_000: return self._json(413,{'error':'payload_too_large','detail':'حجم بدنه بیش از حد مجاز است'})
            body=json.loads(self.rfile.read(n) or b'{}')
            text=body.get('request') or body.get('text')
            if not isinstance(text,str) or not text.strip(): return self._json(400,{'error':'request_required','detail':'فیلد request لازم است'})
            if len(text)>100_000: return self._json(413,{'error':'request_too_long','detail':'طول درخواست بیش از حد مجاز است'})
            ledger=de.SourceLedger(); corpus=de.Corpus.load(CORPUS_PATH,ledger)
            # متن‌های افزوده‌شده صریح و محلی‌اند؛ فایل/URL بیرونی خودکار خوانده نمی‌شود.
            for idx,item in enumerate(body.get('documents',[])[:30]):
                if isinstance(item,dict) and isinstance(item.get('text'),str):
                    corpus.add(str(item.get('title') or f'ورودی {idx+1}'),item['text'],origin='api:inline')
            result=de.build_dossier(text,corpus,requester=str(body.get('requester','api'))[:100])
            return self._json(200,result)
        except json.JSONDecodeError: return self._json(400,{'error':'invalid_json','detail':'بدنه‌ی JSON نامعتبر است'})
        except Exception as exc: return self._json(500,{'error':'internal_error','detail':f'{type(exc).__name__}: {exc}'})
    def log_message(self,fmt,*args): print('[doctrine-api]',fmt%args)

def serve(port=8001,host='127.0.0.1'):
    srv=ThreadingHTTPServer((host,port),Handler); print(f'Doctrine API: http://{host}:{port} (stdlib, local-only default)')
    try: srv.serve_forever()
    except KeyboardInterrupt: print('\nstopping')
    finally: srv.server_close()
def main():
    p=argparse.ArgumentParser(); p.add_argument('--port',type=int,default=8001); p.add_argument('--host',default='127.0.0.1'); p.add_argument('--selftest',action='store_true'); a=p.parse_args()
    if a.selftest:
        from urllib.request import Request,urlopen
        import threading,time
        t=threading.Thread(target=serve,args=(a.port,'127.0.0.1'),daemon=True);t.start();time.sleep(.3)
        try:
            assert json.load(urlopen(f'http://127.0.0.1:{a.port}/api/health'))['ok']
            req=Request(f'http://127.0.0.1:{a.port}/api/analyze',data=json.dumps({'request':'آزمون تحلیل راهبردی تمدن و رسانه'}).encode(),headers={'Content-Type':'application/json'})
            obj=json.load(urlopen(req)); assert obj['dossier_id'] and len(obj['evaluations'])==52
            print('Doctrine API selftest: PASS')
        finally: pass
        return 0
    serve(a.port,a.host); return 0
if __name__=='__main__': sys.exit(main())
