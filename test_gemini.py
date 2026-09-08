import json
import sys
import urllib.request
import urllib.error

sys.stdout.reconfigure(encoding="utf-8")

body = json.dumps({
    "model": "gemini-3.6-flash",
    "messages": [{"role": "user", "content": "اكتب جملة تسويقية واحدة قصيرة عن اسم شركة: النرجس للذكاء الاصطناعي"}],
    "max_tokens": 60,
}).encode()
req = urllib.request.Request(
    "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions",
    data=body,
    headers={
        "Authorization": "Bearer REDACTED-GCP-KEY",
        "Content-Type": "application/json",
    },
)
try:
    r = urllib.request.urlopen(req, timeout=20)
    print("GEMINI OK -", r.status)
    data = json.loads(r.read().decode())
    print("Reply:", data["choices"][0]["message"]["content"])
except urllib.error.HTTPError as e:
    print("FAIL:", e.code, e.read().decode()[:300])