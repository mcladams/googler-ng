# Location: /home/mike/src/googler-ng/test.py
from curl_cffi import requests

session = requests.Session()
session.cookies.set("CONSENT", "YES+cb.20260101-01-p0.en+FX+123", domain=".google.com")

print("Testing supported fingerprints...")
try:
    print("Warmup with safari_ios...")
    session.get("https://www.google.com/", timeout=45, impersonate="safari_ios", allow_redirects=True)
    
    print("Searching with safari_ios + gbv=1...")
    resp = session.get(
        "https://www.google.com/search?q=python+programmer&gbv=1", 
        timeout=45, 
        impersonate="safari_ios", 
        allow_redirects=True
    )
    html = resp.text
    
    print(f"HTML Length: {len(html)}")
    # Mobile/Basic class checks
    print(f"Contains ZINbbc xpd (Mobile Result Container)? {'ZINbbc xpd' in html}")
    print(f"Contains kCrYT (Mobile Link Wrapper)? {'kCrYT' in html}")
    print(f"Contains BNeawe (Mobile Title Text)? {'BNeawe' in html}")

except Exception as e:
    print(f"Error: {e}")
    print("\nIf 'safari_ios' failed, try 'chrome110' or 'safari15_5'.")
    
