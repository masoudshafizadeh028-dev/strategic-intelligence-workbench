#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""OCR فارسی برای PDF؛ متن‌دارها را استخراج می‌کند و برای اسکن‌ها Tesseract اختیاری است."""
from __future__ import annotations
import argparse, json, re, shutil, subprocess, sys, unicodedata
from pathlib import Path


def normalize(text: str) -> str:
    text = unicodedata.normalize('NFKC', text or '')
    for a,b in {'ي':'ی','ك':'ک','ة':'ه','٠':'0','١':'1','٢':'2','٣':'3','٤':'4','٥':'5','٦':'6','٧':'7','٨':'8','٩':'9','۰':'0','۱':'1','۲':'2','۳':'3','۴':'4','۵':'5','۶':'6','۷':'7','۸':'8','۹':'9'}.items(): text=text.replace(a,b)
    text=re.sub(r'[\u064b-\u065f\u0670\u0640]','',text)
    text=re.sub(r'[ \t]+',' ',text)
    return text.strip()


def extract_pdf(path: Path, lang: str='fas+eng', dpi: int=250) -> dict:
    """متن را با pdfminer استخراج می‌کند؛ اگر متن کم باشد، در صورت نصب Tesseract OCR اجرا می‌شود."""
    pages=[]; method='pdf-text'; warning=None
    try:
        from pdfminer.high_level import extract_pages
        from pdfminer.layout import LTTextContainer
        for idx, layout in enumerate(extract_pages(str(path)), start=1):
            text='\n'.join(el.get_text() for el in layout if isinstance(el, LTTextContainer))
            pages.append({'page':idx,'text':normalize(text),'confidence':1.0 if text.strip() else 0.0})
    except ImportError:
        warning='pdfminer.six نصب نیست؛ برای PDF متن‌دار: pip install pdfminer.six'
    except Exception as exc:
        warning=f'استخراج متن PDF ناموفق: {type(exc).__name__}: {exc}'
    chars=sum(len(p['text']) for p in pages)
    if chars < 30:
        if shutil.which('pdftoppm') and shutil.which('tesseract'):
            try:
                import tempfile
                with tempfile.TemporaryDirectory(prefix='pershiaa-ocr-') as td:
                    prefix=str(Path(td)/'page')
                    proc=subprocess.run(['pdftoppm','-r',str(dpi),'-png',str(path),prefix],capture_output=True,text=True,timeout=180)
                    if proc.returncode:
                        raise RuntimeError(proc.stderr[-500:])
                    images=sorted(Path(td).glob('page-*.png'))
                    ocr=[]
                    for idx,img in enumerate(images,1):
                        r=subprocess.run(['tesseract',str(img),'stdout','-l',lang,'tsv'],capture_output=True,text=True,timeout=120)
                        if r.returncode:
                            raise RuntimeError(r.stderr[-500:])
                        lines=r.stdout.splitlines()
                        words=[]; confs=[]
                        for line in lines[1:]:
                            cols=line.split('\t')
                            if len(cols)>=12 and cols[11].strip():
                                words.append(cols[11].strip())
                                try:
                                    if float(cols[10])>=0: confs.append(float(cols[10])/100)
                                except ValueError: pass
                        ocr.append({'page':idx,'text':normalize(' '.join(words)), 'confidence':round(sum(confs)/len(confs),3) if confs else 0.0})
                    if ocr: pages=ocr; method='tesseract-ocr'
            except Exception as exc:
                warning=(warning+'; ' if warning else '')+f'OCR ناموفق: {type(exc).__name__}: {exc}'
        else:
            warning=(warning+'; ' if warning else '')+'PDF احتمالاً اسکن‌شده است؛ برای OCR سیستم، pdftoppm، tesseract و بسته‌ی زبانی fas لازم است.'
    if not pages: pages=[{'page':1,'text':'','confidence':0.0}]
    return {'source':path.name,'method':method,'language':lang,'page_count':len(pages),'pages':pages,'warnings':[warning] if warning else [],'searchable_text':'\n\n'.join(p['text'] for p in pages)}


def selftest():
    sample=normalize('ي ك ۱۲۳ ـ سلامٌ')
    assert sample=='ی ک 123 سلام',repr(sample)
    assert normalize('  آزمون   فارسی ')=='آزمون فارسی'
    print('OCR selftest: PASS (normalization; PDF integrations tested only when installed)')


def main():
    ap=argparse.ArgumentParser(description='استخراج متن و OCR اختیاری PDF فارسی')
    ap.add_argument('pdf',nargs='?'); ap.add_argument('--out'); ap.add_argument('--lang',default='fas+eng'); ap.add_argument('--dpi',type=int,default=250); ap.add_argument('--selftest',action='store_true')
    a=ap.parse_args()
    if a.selftest: selftest(); return 0
    if not a.pdf: ap.error('مسیر PDF لازم است')
    p=Path(a.pdf)
    if not p.is_file() or p.suffix.lower()!='.pdf': ap.error('فایل PDF معتبر پیدا نشد')
    result=extract_pdf(p,a.lang,a.dpi); data=json.dumps(result,ensure_ascii=False,indent=2)
    if a.out: Path(a.out).write_text(data,encoding='utf-8')
    print(data)
    return 0
if __name__=='__main__': sys.exit(main())
