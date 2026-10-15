"""هسته‌ی ثبت handlerها و dispatcher ربات ایتا."""
from __future__ import annotations
import re
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional, Pattern, Union

Message=Dict[str,Any]
Handler=Callable[[Message],Optional[Dict[str,Any]]]
@dataclass
class Route:
    pattern: Optional[Pattern[str]]
    handler: Handler
    command: Optional[str]=None
    name: str='handler'

class Bot:
    def __init__(self): self.routes:List[Route]=[]
    def on_message(self, pattern:Optional[Union[str,Pattern[str]]]=None, *, command:Optional[str]=None, name:Optional[str]=None):
        rx=re.compile(pattern,re.I) if isinstance(pattern,str) else pattern
        def deco(fn:Handler):
            self.routes.append(Route(rx,fn,command,name or fn.__name__))
            return fn
        return deco
    def dispatch(self,message:Message)->List[Dict[str,Any]]:
        text=str(message.get('text',''))
        out=[]
        for route in self.routes:
            if route.command and not text.strip().startswith('/'+route.command): continue
            if route.pattern and not route.pattern.search(text): continue
            try:
                result=route.handler(message)
                if result is not None: out.append({'handler':route.name,'response':result})
            except Exception as exc:
                out.append({'handler':route.name,'error':f'{type(exc).__name__}: {exc}'})
        return out
