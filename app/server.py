import json
import os
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

from openai import OpenAI

OPENROUTER_KEY = os.environ.get("OPENROUTER_API_KEY")
HF_TOKEN = os.environ.get("HF_TOKEN", "")

CLIENT = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=OPENROUTER_KEY,
) if OPENROUTER_KEY else OpenAI(
    base_url="https://router.huggingface.co/v1",
    api_key=HF_TOKEN,
)

DEFAULT_MODEL = os.environ.get(
    "CHAT_MODEL",
    "meta-llama/llama-3.1-8b-instruct" if OPENROUTER_KEY else "meta-llama/Llama-3.1-8B-Instruct:novita",
)
ROOT = Path(__file__).resolve().parent

API_VERSION = "v1"
MAX_JSON_BYTES = 256 * 1024
MAX_TEXT_CHARS = 20000

try:
    from engine.dossier import build_dossier
except ImportError:  # اجرا به‌صورت python -m app.server از ریشه ریپو
    from app.engine.dossier import build_dossier  # noqa

BRIDGE_HTML = """
<div id="ai-fab" style="position:fixed;bottom:18px;left:18px;z-index:99999;">
<button id="ai-fab-btn" style="width:56px;height:56px;border-radius:50%;border:1px solid #00ffcc;background:#13131f;color:#00ffcc;font-size:24px;cursor:pointer;box-shadow:0 0 18px rgba(0,255,204,.35)">&#128172;</button>
</div>
<div id="ai-panel" style="display:none;position:fixed;bottom:86px;left:18px;width:min(400px,92vw);max-height:70vh;z-index:99999;background:#13131f;border:1px solid #00ffcc;border-radius:14px;overflow:hidden;flex-direction:column;font-family:inherit;">
<div style="padding:10px 14px;border-bottom:1px solid #262640;display:flex;justify-content:space-between;align-items:center;">
<b style="color:#00ffcc;font-size:.9rem;">&#129302; ارسال به مدل</b>
<button id="ai-close" style="background:none;border:none;color:#8a93a8;cursor:pointer;font-size:1rem;">&#10005;</button>
</div>
<div id="ai-msgs" style="padding:12px;overflow-y:auto;flex:1;min-height:120px;max-height:40vh;display:flex;flex-direction:column;gap:8px;font-size:.82rem;"></div>
<div style="padding:10px;border-top:1px solid #262640;display:flex;flex-direction:column;gap:8px;">
<button id="ai-grab" style="background:#1a1a2b;border:1px solid #262640;color:#e8ecf4;border-radius:8px;padding:6px;cursor:pointer;font-family:inherit;font-size:.78rem;">&#128229; درج خروجی‌های صفحه</button>
<div style="display:flex;gap:8px;">
<textarea id="ai-input" rows="2" placeholder="...پیام یا پرامپت" style="flex:1;background:#0a0a12;color:#e8ecf4;border:1px solid #262640;border-radius:8px;padding:8px;font-family:inherit;font-size:.82rem;resize:vertical;"></textarea>
<button id="ai-send" style="background:#00ffcc;border:none;color:#0a0a12;border-radius:8px;padding:0 16px;font-weight:700;cursor:pointer;">&#10148;</button>
</div>
<div id="ai-status" style="font-size:.72rem;color:#8a93a8;text-align:center;"></div>
</div>
</div>
<script>
(function(){
var fab=document.getElementById('ai-fab-btn'),panel=document.getElementById('ai-panel'),
close=document.getElementById('ai-close'),msgs=document.getElementById('ai-msgs'),
input=document.getElementById('ai-input'),send=document.getElementById('ai-send'),
status=document.getElementById('ai-status'),grab=document.getElementById('ai-grab');
var hist=[];
fab.addEventListener('click',function(){panel.style.display=panel.style.display==='flex'?'none':'flex';});
close.addEventListener('click',function(){panel.style.display='none';});
function addMsg(role,text){
var d=document.createElement('div');
d.style.cssText=role==='user'?'align-self:flex-start;background:#1a1a2b;border:1px solid #262640;border-radius:10px;padding:8px 12px;max-width:90%;white-space:pre-wrap;':'align-self:flex-end;background:rgba(0,255,204,.12);border:1px solid #00ffcc;border-radius:10px;padding:8px 12px;max-width:90%;white-space:pre-wrap;';
d.textContent=text;msgs.appendChild(d);msgs.scrollTop=msgs.scrollHeight;
}
async function doSend(){
var text=input.value.trim();if(!text||send.disabled)return;
input.value='';addMsg('user',text);hist.push({role:'user',content:text});
send.disabled=true;status.textContent='...در حال ارسال به مدل';
try{
var r=await fetch('/api/chat',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({messages:hist})});
var d=await r.json();if(!r.ok)throw new Error(d.error||'خطا');
addMsg('bot',d.reply);hist.push({role:'assistant',content:d.reply});status.textContent='مدل: '+(d.model||'');
}catch(e){addMsg('bot','\\u26A0\\uFE0F '+(e.message||'خطا'));status.textContent='خطا در اتصال';}
finally{send.disabled=false;}
}
send.addEventListener('click',doSend);
input.addEventListener('keydown',function(e){if(e.key==='Enter'&&!e.shiftKey){e.preventDefault();doSend();}});
document.addEventListener('click',function(e){
var pr=e.target&&e.target.closest?e.target.closest('[data-prompt]'):null;
if(pr&&typeof PluginSystem!=='undefined'){
try{
var p=PluginSystem.all().find(function(x){return x.id===pr.dataset.prompt;});
if(p){input.value=PluginSystem.buildPrompt(p);panel.style.display='flex';status.textContent='\\u2705 پرامپت "'+p.name+'" درج شد — ارسال را بزنید';}
}catch(err){}
}
},true);
grab.addEventListener('click',function(){
var ids=['ms-output','gen-output','gen-meta','cmp-output','ag-output','ms-pipeline-panel','nar-dna','gen-tagline'];
var parts=[];
ids.forEach(function(id){var el=document.getElementById(id);if(el){var t=(el.innerText||'').trim();if(t)parts.push('['+id+']\\n'+t);}});
if(parts.length){input.value=parts.join('\\n\\n---\\n\\n').slice(0,6000);panel.style.display='flex';status.textContent='\\u2705 خروجی صفحه درج شد';}
else{status.textContent='خروجی متنی در صفحه پیدا نشد';}
});
})();
</script>
"""


class Handler(BaseHTTPRequestHandler):
    server_version = "Workbench/1.0"

    def _cors_headers(self):
        # CORS محدود: فقط مبدأهای loopback
        origin = self.headers.get("Origin", "")
        try:
            host = urllib.parse.urlparse(origin).hostname or ""
        except ValueError:
            host = ""
        if host in ("localhost", "127.0.0.1", "::1"):
            self.send_header("Access-Control-Allow-Origin", origin)
            self.send_header("Vary", "Origin")

    def _send(self, code, body, content_type="application/json"):
        if isinstance(body, (dict, list)):
            body = json.dumps(body, ensure_ascii=False).encode("utf-8")
        elif isinstance(body, str):
            body = body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self._cors_headers()
        self.end_headers()
        self.wfile.write(body)

    def _read_json(self):
        try:
            length = int(self.headers.get("Content-Length", 0))
        except ValueError:
            return {}
        if length <= 0:
            return {}
        if length > MAX_JSON_BYTES:
            return {"__too_large__": True}
        try:
            return json.loads(self.rfile.read(length))
        except (json.JSONDecodeError, ValueError):
            return {}

    def _serve_html(self, filename):
        try:
            html = (ROOT / filename).read_bytes()
        except FileNotFoundError:
            self._send(404, {"error": f"not found: {filename}"})
            return
        self._send(200, html, "text/html; charset=utf-8")

    def _serve_doctrine(self):
        try:
            html = (ROOT / "doctrine.html").read_bytes()
        except FileNotFoundError:
            self._send(404, {"error": "not found: doctrine.html"})
            return
        # فقط آخرین </body> (ته سند) — جایگزینی همه موارد، رشته
        # قالب گزارش‌ساز داخل <script> را خراب و اسکریپت را ناقص می‌کند
        idx = html.rfind(b"</body>")
        if idx != -1:
            html = html[:idx] + BRIDGE_HTML.encode("utf-8") + html[idx:]
        self._send(200, html, "text/html; charset=utf-8")

    def do_GET(self):
        path = urllib.parse.urlparse(self.path).path
        if path == "/" or path == "/index.html":
            self._serve_html("index.html")
        elif path == "/doctrine":
            self._serve_doctrine()
        elif path == "/health" or path == "/api/v1/health":
            self._send(200, {"ok": True, "model": DEFAULT_MODEL,
                             "api": API_VERSION, "offline": True})
        else:
            self._send(404, {"error": "not found"})

    def do_OPTIONS(self):
        # پیش‌پرواز CORS فقط برای مبدأهای loopback
        self.send_response(204)
        self._cors_headers()
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Content-Length", "0")
        self.end_headers()

    def do_POST(self):
        path = urllib.parse.urlparse(self.path).path
        if path == "/api/chat":
            self._chat()
        elif path == "/api/v1/dossier":
            self._dossier()
        else:
            self._send(404, {"error": "not found"})

    def _chat(self):
        data = self._read_json()
        if not isinstance(data, dict):
            self._send(400, {"error": "JSON object required"})
            return
        if data.get("__too_large__"):
            self._send(413, {"error": "request too large"})
            return
        messages = data.get("messages") or []
        model = data.get("model") or DEFAULT_MODEL
        if not isinstance(messages, list) or not messages:
            self._send(400, {"error": "messages required"})
            return
        if not isinstance(model, str) or not model:
            self._send(400, {"error": "invalid model"})
            return
        try:
            completion = CLIENT.chat.completions.create(
                model=model,
                messages=messages,
            )
            content = completion.choices[0].message.content or ""
            self._send(200, {"reply": content, "model": model})
        except Exception as exc:  # noqa: BLE001
            self._send(500, {"error": str(exc)})

    def _dossier(self):
        """ساخت پرونده آفلاین — POST /api/v1/dossier.

        ورودی: {request: str, doc_id?: str, sim_inputs?: {k: float}}
        خروجی: پرونده JSON مطابق dossier.schema.v1.json
        """
        data = self._read_json()
        if not isinstance(data, dict):
            self._send(400, {"error": "JSON object required"})
            return
        if data.get("__too_large__"):
            self._send(413, {"error": "request too large"})
            return
        request = data.get("request", "")
        doc_id = data.get("doc_id")
        sim_inputs = data.get("sim_inputs") or {}
        if not isinstance(request, str) or not request.strip():
            self._send(400, {"error": "request required"})
            return
        if len(request) > MAX_TEXT_CHARS:
            self._send(400, {"error": f"request too long (max {MAX_TEXT_CHARS} chars)"})
            return
        if doc_id is not None and not isinstance(doc_id, str):
            self._send(400, {"error": "invalid doc_id"})
            return
        if not isinstance(sim_inputs, dict):
            self._send(400, {"error": "invalid sim_inputs"})
            return
        try:
            dossier = build_dossier(request, doc_id=doc_id or None,
                                    sim_inputs=sim_inputs)
        except ValueError as exc:
            self._send(400, {"error": str(exc)})
            return
        except Exception as exc:  # noqa: BLE001
            self._send(500, {"error": str(exc)})
            return
        self._send(200, dossier)

    def log_message(self, *args):
        pass


def main():
    port = int(os.environ.get("PORT", 8000))
    server = ThreadingHTTPServer(("0.0.0.0", port), Handler)
    print(f"App running at http://0.0.0.0:{port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
