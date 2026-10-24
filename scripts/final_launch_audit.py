from __future__ import annotations
import json
import urllib.error
import urllib.parse
import urllib.request

BASE="https://karmaai.online"
TIMEOUT=30
UA="Al-Narjis-Final-Launch-Audit/2026-10-25"

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None

def request(path, *, method="GET", data=None, follow=True):
    url=urllib.parse.urljoin(BASE,path)
    body=None if data is None else json.dumps(data,ensure_ascii=False).encode()
    headers={"User-Agent":UA,"Accept":"application/json,text/html,*/*"}
    if body is not None: headers["Content-Type"]="application/json"
    opener=urllib.request.build_opener() if follow else urllib.request.build_opener(NoRedirect())
    req=urllib.request.Request(url,data=body,headers=headers,method=method)
    try:
        with opener.open(req,timeout=TIMEOUT) as r:
            return r.status,r.geturl(),r.read().decode("utf-8","replace")
    except urllib.error.HTTPError as e:
        return e.code,e.geturl(),e.read().decode("utf-8","replace")

def jget(path):
    st,_,body=request(path)
    if st!=200: raise AssertionError(f"{path} HTTP {st}: {body[:300]}")
    return json.loads(body)

def must(ok,msg):
    if not ok: raise AssertionError(msg)

health=jget("/health")
must(health.get("status")=="healthy",f"liveness={health}")
deep=jget("/health?deep=1")
must((deep.get("db") or {}).get("ok") is True,f"db={deep.get('db')}")
external=deep.get("external") or {}
capabilities=deep.get("capabilities") or {}

agents=jget("/api/agents").get("agents") or []
must(len(agents)==35,f"expected 35 public agents, got {len(agents)}")
for a in agents:
    for forbidden in ("default_model","is_system","employee_no","questions"):
        must(forbidden not in a,f"public agent leaked {forbidden}: {a.get('slug')}")

pages={}
for path in ("/ar/home","/en/home","/portal","/login","/ar/contact","/ar/pricing","/ar/privacy","/ar/terms","/ar/data-deletion","/ar/about"):
    st,_,body=request(path)
    must(st==200,f"{path} HTTP {st}")
    pages[path]=body

public_blob="\n".join(pages[p] for p in ("/ar/home","/ar/contact","/ar/pricing"))
for marker in ("wa.me/","t.me/","m.me/","mailto:","tel:","0540799266"):
    must(marker not in public_blob,f"public contact leak: {marker}")
must('id="siteAssistant"' in pages["/ar/home"],"site assistant missing")

for path in ("/docs","/redoc","/openapi.json"):
    st,_,_=request(path)
    must(st==404,f"{path} expected 404, got {st}")

st,_,_=request("/api/owner/overview",follow=False)
must(st==401,f"owner API exposed: {st}")
st,_,_=request("/owner",follow=False)
must(st in (301,302,303,307),f"owner page exposed: {st}")

session=jget("/api/portal/session?probe=1")
must(session=={"authenticated":False},f"portal anon session={session}")

caps=jget("/api/payments/capabilities")
must(caps.get("card") is False,f"Moyasar card should remain pending/on-hold: {caps}")

channels={}
for name,path in (("telegram","/webhooks/telegram/health"),("whatsapp","/webhooks/whatsapp/health")):
    d=jget(path)
    blob=json.dumps(d).lower()
    must("eaa" not in blob and "sk_live_" not in blob and "pk_live_" not in blob,f"{name} leaked credential-like value")
    channels[name]={k:d.get(k) for k in ("configured","connected","status")}

store_routes={}
for name in ("salla","zid"):
    st,_,body=request(f"/webhooks/stores/{name}/callback",follow=False)
    # disabled => 404; enabled => callback validates missing code/state and returns 400.
    must(st in (400,404),f"{name} callback unexpected HTTP {st}: {body[:200]}")
    store_routes[name]={"http":st,"enabled":st!=404}

# CEO path: harmless, no PII and no purchase.
st,_,body=request("/api/ceo/consult",method="POST",data={"problem":"متجر إلكتروني يحتاج تحسين المبيعات وخدمة العملاء","lang":"ar"})
must(st==200,f"CEO consult HTTP {st}: {body[:400]}")
ceo=json.loads(body)
must(bool(ceo.get("agents")),f"CEO returned no agents: {ceo}")
must(len(ceo.get("agents") or [])>=1,"CEO agent team empty")

# Public assistant: proves the actual visitor answer path, not merely UI rendering.
st,_,body=request("/api/consult",method="POST",data={"messages":[{"role":"user","content":"ما هي خدمة النرجس وكيف أبدأ الاشتراك؟"}]})
must(st==200,f"assistant HTTP {st}: {body[:400]}")
assistant=json.loads(body)
reply=str(assistant.get("reply") or "").strip()
must(len(reply)>=20,f"assistant empty/short: {assistant}")
for leak in ("0540799266","wa.me/","t.me/","m.me/","mailto:"):
    must(leak not in reply,f"assistant leaked direct contact: {leak}")
handoff=("لا أستطيع الإجابة" in reply or "خدمة العملاء" in reply or "can't answer" in reply.lower())
must(not handoff,f"assistant failed ordinary sales question / handed off: {reply[:500]}")

print("FINAL_HTTP_AUDIT_PASS")
print(json.dumps({
  "main_surface":"ok",
  "agents":len(agents),
  "db":deep.get("db"),
  "externals":external,
  "capabilities":capabilities,
  "channels":channels,
  "moyasar_card":caps.get("card"),
  "stores":store_routes,
  "ceo_agents":[a.get("slug") for a in (ceo.get("agents") or [])],
  "assistant_reply_preview":reply[:180],
},ensure_ascii=False))
