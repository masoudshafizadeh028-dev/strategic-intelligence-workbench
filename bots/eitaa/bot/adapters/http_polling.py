"""HTTP polling adapter با قرارداد JSON قابل‌پیکربندی؛ stdlib-only."""
from __future__ import annotations
import json, os, time, urllib.error, urllib.request
from typing import Any, Callable, Dict, Optional

class PollingAdapter:
    """Adapter ساده. آدرس‌ها با EITAA_UPDATES_PATH و EITAA_SEND_PATH قابل تنظیم‌اند.

    قرارداد پیش‌فرض: GET {base}/updates?offset=N → {"updates":[{"update_id":..,"message":..}]}
    POST {base}/send → {"chat_id":...,"text":...}
    این قرارداد را با API مجاز و مستند مورد استفاده تطبیق بده.
    """
    def __init__(self,base_url:str,token:str='',updates_path:str='/updates',send_path:str='/send',timeout:float=20):
        self.base=base_url.rstrip('/');self.token=token;self.updates_path=updates_path;self.send_path=send_path;self.timeout=timeout;self.offset=0
    def _request(self,url:str,payload:Optional[dict]=None)->dict:
        data=json.dumps(payload,ensure_ascii=False).encode() if payload is not None else None
        headers={'Content-Type':'application/json','Accept':'application/json'}
        if self.token: headers['Authorization']='Bearer '+self.token
        req=urllib.request.Request(url,data=data,headers=headers,method='POST' if data is not None else 'GET')
        with urllib.request.urlopen(req,timeout=self.timeout) as r: return json.loads(r.read().decode())
    def poll_once(self)->list:
        url=f'{self.base}{self.updates_path}?offset={self.offset}'
        res=self._request(url); updates=res.get('updates',[])
        for item in updates:
            try:self.offset=max(self.offset,int(item.get('update_id',0))+1)
            except (TypeError,ValueError):pass
        return updates
    def send(self,chat_id:Any,text:str)->dict:
        return self._request(self.base+self.send_path,{'chat_id':chat_id,'text':text})
    def run(self,dispatch:Callable[[dict],list],stop:Callable[[],bool],interval:float=2)->None:
        while not stop():
            try:
                for update in self.poll_once():
                    msg=update.get('message',update)
                    for item in dispatch(msg):
                        response=item.get('response') or {}
                        if response.get('text') is not None and msg.get('chat_id') is not None:
                            self.send(msg['chat_id'],response['text'])
            except (urllib.error.URLError,TimeoutError,ValueError) as exc:
                print(f'[eitaa adapter] {type(exc).__name__}: {exc}')
            time.sleep(interval)
