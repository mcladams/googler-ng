import re
from curl_cffi import requests

session = requests.Session(impersonate="chrome120")
session.cookies.set("CONSENT", "YES+cb.20230101-01-p0.en+FX+123", domain=".google.com")

print("1. Fetch search...")
resp = session.get("https://www.google.com/search?q=python+programmer", allow_redirects=True)
html = resp.text

if "enablejs" in html:
    print("Found enablejs!")
    match = re.search(r'url=([^"]+)"', html)
    if match:
        url = "https://www.google.com" + match.group(1).replace("&amp;", "&")
        print("2. Fetching enablejs...", url)
        resp2 = session.get(url, allow_redirects=True)
        # print(resp2.text[:200])

print("3. Fetch search again...")
resp3 = session.get("https://www.google.com/search?q=python+programmer", allow_redirects=True)
html3 = resp3.text
print(f"yuRUbf: {'yuRUbf' in html3}, MjjYud: {'MjjYud' in html3}")
print("-" * 40)

