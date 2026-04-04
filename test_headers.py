from curl_cffi import requests

def test(consent=False, headers=False):
    session = requests.Session(impersonate="chrome120")
    if consent:
        session.cookies.set("CONSENT", "YES+cb.20260101-01-p0.en+FX+123", domain=".google.com")
    
    # Warmup
    session.get("https://www.google.com/", allow_redirects=True)
        
    req_headers = {}
    if headers:
        req_headers = {
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "same-origin",
            "Sec-Fetch-User": "?1",
            "Upgrade-Insecure-Requests": "1"
        }
    
    resp = session.get("https://www.google.com/search?q=python+programmer", headers=req_headers if headers else None, allow_redirects=True)
    html = resp.text
    print(f"Consent: {consent}, Headers: {headers}")
    print(f"Status Code: {resp.status_code}")
    print(f"yuRUbf: {'yuRUbf' in html}, MjjYud: {'MjjYud' in html}, js reload?: {'/httpservice/retry/enablejs' in html}")
    print(html[:150].replace('\n', ' '))
    print("-" * 40)

test(consent=False, headers=False)
test(consent=True, headers=False)
test(consent=False, headers=True)
test(consent=True, headers=True)
