import json, urllib.request
BASE="https://karmaai.online"
def get(path):
    req=urllib.request.Request(BASE+path,headers={"User-Agent":"narjis-final-readiness/1.0","Accept":"application/json"})
    with urllib.request.urlopen(req,timeout=30) as r:
        return json.loads(r.read().decode())
deep=get("/health?deep=1")
print("FINAL_CAPABILITY_READINESS")
print(json.dumps({
  "status":deep.get("status"),
  "db":deep.get("db"),
  "external":deep.get("external"),
  "capabilities":deep.get("capabilities"),
  "degraded":deep.get("degraded"),
},ensure_ascii=False))
