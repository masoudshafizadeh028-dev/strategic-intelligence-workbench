#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""PerShiaA OSINT: تحلیل حداقلیِ هدف‌های عمومی و مجاز.

حالت آفلاین برای DNS از resolver سیستم استفاده می‌کند؛ GitHub فقط با انتخاب صریح
و اتصال اینترنت، متادیتای عمومی API را می‌خواند. اسکن پورت، بهره‌برداری، ورود،
داده‌ی نقض‌شده و منابع دارک‌وب عمداً پیاده‌سازی نشده‌اند.
"""
from __future__ import annotations
import argparse, json, os, re, socket, sys, urllib.error, urllib.request
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

VERSION='1.0.0'
DOMAIN_RE=re.compile(r'^(?=.{1,253}$)(?:[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?)(?:\.(?:[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?))+$')
IPV4_RE=re.compile(r'^(?:\d{1,3}\.){3}\d{1,3}$')
GITHUB_RE=re.compile(r'^[A-Za-z0-9-]{1,39}$')
TLD_ALPHA_RE=re.compile(r'\.[A-Za-z]{2,}$')

def now(): return datetime.now(timezone.utc).replace(microsecond=0).isoformat()
def valid_domain(value: str)->bool:
 """نام دامنه‌ی عمومی معتبر: رد IP، localhost و برچسب‌های نامعتبر."""
 value=(value or '').strip().rstrip('.').lower()
 if not value or '..' in value or len(value)>253: return False
 if IPV4_RE.fullmatch(value) or ':' in value: return False
 if value=='localhost' or value.endswith('.localhost') or value.endswith('.local'): return False
 if not TLD_ALPHA_RE.search(value): return False
 if not DOMAIN_RE.fullmatch(value): return False
 return all(lbl and not lbl.startswith('-') and not lbl.endswith('-') for lbl in value.split('.'))

def resolve_dns(domain: str)->Dict[str,Any]:
 if not valid_domain(domain): return {'status':'rejected','reason':'هدف باید نام دامنه‌ی معتبر باشد؛ IP یا URL خام پذیرفته نیست.','records':[]}
 records=[]
 try:
  for family,_,_,_,sockaddr in socket.getaddrinfo(domain,None,proto=socket.IPPROTO_TCP):
   ip=sockaddr[0]; typ='AAAA' if family==socket.AF_INET6 else 'A'
   rec={'type':typ,'value':ip}
   if rec not in records: records.append(rec)
  return {'status':'ok' if records else 'empty','records':records,'source':'system-resolver','checked_at':now()}
 except socket.gaierror as e:
  return {'status':'unavailable','records':[],'reason':str(e),'source':'system-resolver','checked_at':now()}

def github_public_user(name: str)->Dict[str,Any]:
 if not GITHUB_RE.fullmatch(name or ''): return {'status':'rejected','reason':'نام کاربری گیت‌هاب معتبر نیست.'}
 url='https://api.github.com/users/'+name
 req=urllib.request.Request(url,headers={'Accept':'application/vnd.github+json','User-Agent':'PerShiaA-OSINT/1.0'})
 try:
  with urllib.request.urlopen(req,timeout=12) as r: data=json.loads(r.read().decode())
  safe={k:data.get(k) for k in ('login','html_url','type','public_repos','followers','following','created_at','updated_at')}
  return {'status':'ok','source':'GitHub public REST API','data':safe,'checked_at':now()}
 except urllib.error.HTTPError as e:
  return {'status':'not_found' if e.code==404 else 'unavailable','reason':f'HTTP {e.code}','source':'GitHub public REST API'}
 except (urllib.error.URLError,OSError,ValueError) as e:
  return {'status':'unavailable','reason':f'{type(e).__name__}: {e}','source':'GitHub public REST API'}

def run_scan(target: str, modules: Optional[List[str]]=None)->Dict[str,Any]:
 mods=modules or ['dns']
 allowed={'dns','github'}
 bad=sorted(set(mods)-allowed)
 result={'engine':{'name':'PerShiaA OSINT','version':VERSION},'target':target,'started_at':now(),'modules':{},'graph':{'nodes':[],'edges':[]},'scope':{'authorized_public_sources_only':True,'port_scanning':False,'breach_data':False,'dark_web':False}}
 if bad:
  result['error']={'code':'unsupported_modules','modules':bad,'allowed':sorted(allowed)}
  return result
 if 'dns' in mods:
  dns=resolve_dns(target); result['modules']['dns']=dns
  if dns.get('status')=='ok':
   rootid='domain:'+target.lower(); result['graph']['nodes'].append({'data':{'id':rootid,'label':target,'kind':'domain'}})
   for i,r in enumerate(dns['records']):
    nid='ip:'+r['value']; result['graph']['nodes'].append({'data':{'id':nid,'label':r['value'],'kind':'ip'}}); result['graph']['edges'].append({'data':{'id':f'e{i}','source':rootid,'target':nid,'label':r['type']}})
 if 'github' in mods:
  gh=github_public_user(target); result['modules']['github']=gh
  if gh.get('status')=='ok':
   data=gh['data']; rid='github:'+str(data.get('login','')); result['graph']['nodes'].append({'data':{'id':rid,'label':str(data.get('login','')),'kind':'github'}})
 result['completed_at']=now(); result['summary']={'modules':len(result['modules']),'nodes':len(result['graph']['nodes']),'edges':len(result['graph']['edges'])}
 return result

def selftest()->int:
 fails=[]
 for d in ('example.com','sub.domain.org','a-b.example.ir'):
  if not valid_domain(d): fails.append('domain validation rejected '+d)
 for d in ('https://example.com','127.0.0.1','localhost','bad..example.com','-bad.com','192.168.1.1','foo','a.local','2001:db8::1'):
  if valid_domain(d): fails.append('domain validation accepted '+d)
 out=run_scan('example.invalid',['dns'])
 if out['summary']['modules']!=1: fails.append('offline scan structure')
 if 'darkweb' not in run_scan('example.com',['darkweb']).get('error',{}).get('modules',[]): fails.append('unsupported module guard')
 print('OSINT selftest:', 'FAIL '+repr(fails) if fails else 'PASS (scope validation, offline DNS path, unsupported-module guard)')
 return int(bool(fails))

def main():
 p=argparse.ArgumentParser(description='OSINT محدود به منابع عمومی و مجاز')
 p.add_argument('--target'); p.add_argument('--modules',default='dns'); p.add_argument('--json',action='store_true'); p.add_argument('--out'); p.add_argument('--selftest',action='store_true'); a=p.parse_args()
 if a.selftest:return selftest()
 if not a.target:p.error('--target لازم است')
 out=run_scan(a.target,[x.strip() for x in a.modules.split(',') if x.strip()])
 text=json.dumps(out,ensure_ascii=False,indent=2)
 if a.out: open(a.out,'w',encoding='utf-8').write(text)
 print(text if a.json else json.dumps(out,ensure_ascii=False))
 return 1 if out.get('error') else 0
if __name__=='__main__':sys.exit(main())
