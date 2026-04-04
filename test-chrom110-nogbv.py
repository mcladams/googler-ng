# Location: /home/mike/src/googler-ng/test.py
from curl_cffi import requests

session = requests.Session()
session.cookies.set("CONSENT", "YES+cb.20260101-01-p0.en+FX+123", domain=".google.com")
session.cookies.set("SOCS", "CAISHAgBEhJnd3NfMjAyNjAxMDEtMF9SQzEaAmVuIAE", domain=".google.com")

print("Testing supported fingerprints...")
try:
    print("Warmup with chrome110...")
    session.get("https://www.google.com/", timeout=45, impersonate="chrome110", allow_redirects=True)
    
    print("Searching with chrome110 + NO gbv=1...")
    resp = session.get(
        "https://www.google.com/search?q=python+programmer", 
        timeout=45, 
        impersonate="chrome110", 
        allow_redirects=True
    )
    html = resp.text
    
    print(f"HTML Length: {len(html)}")
    # modern desktop class checks
    print(f"Contains MjjYud)? {'MjjYud' in html}")
    print(f"Contains yuRUbf)? {'yuRUbf' in html}")

except Exception as e:
    print(f"Error: {e}")
    print("\nIf 'chrome110' failed, give up?")
    
