#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ورودی AutoEitaa."""
import argparse,os,sys
from pathlib import Path
HERE=Path(__file__).resolve().parent
for _p in (HERE, HERE.parent):
    if str(_p) not in sys.path:
        sys.path.insert(0,str(_p))
try:
    from bot.handlers.custom import bot
    from bot.adapters.http_polling import PollingAdapter
except ImportError:
    try:
        from bots.eitaa.bot.handlers.custom import bot  # type: ignore
        from bots.eitaa.bot.adapters.http_polling import PollingAdapter  # type: ignore
    except ImportError:
        from .bot.handlers.custom import bot  # type: ignore
        from .bot.adapters.http_polling import PollingAdapter  # type: ignore

def selftest():
    out=bot.dispatch({'chat_id':'test','text':'سلام'})
    assert out and out[0]['response']['text'].startswith('سلام')
    cmd=bot.dispatch({'chat_id':'test','text':'/help'})
    assert cmd and 'handler' in cmd[0]
    print('AutoEitaa selftest: PASS (registration, regex route, command route)')
    return 0

def main():
    p=argparse.ArgumentParser();p.add_argument('--selftest',action='store_true');p.add_argument('--demo',action='store_true');p.add_argument('--interval',type=float,default=2);a=p.parse_args()
    if a.selftest:return selftest()
    if a.demo:
        for text in ['سلام','/start','/help','پیام آزاد']:
            print(text,'→',bot.dispatch({'chat_id':'demo','text':text}))
        return 0
    base=os.environ.get('EITAA_BASE_URL','').strip()
    if not base:
        print('EITAA_BASE_URL تنظیم نشده؛ برای نمونه: python3 main.py --demo');return 2
    adapter=PollingAdapter(base,os.environ.get('EITAA_TOKEN',''),os.environ.get('EITAA_UPDATES_PATH','/updates'),os.environ.get('EITAA_SEND_PATH','/send'))
    try:adapter.run(bot.dispatch,lambda:False,a.interval)
    except KeyboardInterrupt:print('\nمتوقف شد')
    return 0
if __name__=='__main__':sys.exit(main())
