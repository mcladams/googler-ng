import logging
import textwrap
from curl_cffi import requests
from googler_ng.utils.helpers import time_it

logger = logging.getLogger(__name__)

# We no longer need HardenedHTTPSConnection or manual SSLContext management.
# curl_cffi handles the "impersonation" at the TLS/socket level.

class GoogleConnectionError(Exception):
    pass

class GoogleConnection(object):
    """
    Handles connecting to and fetching from Google using curl_cffi 
    to bypass TLS fingerprinting/WAF blocks.
    """

    def __init__(self, host, port=None, address_family=0, timeout=45, proxy=None, notweak=False):
        self._host = host
        self._port = port
        self._proxy = proxy
        self._timeout = timeout
        # self.cookie = ''
        self._session = requests.Session()
        
        # We seed the session with a 'CONSENT=YES' cookie to skip the 2026 privacy wall
        self._session.cookies.set("CONSENT", "YES+cb.20260101-01-p0.en+FX+123", domain=".google.com")

        # Mapping proxy for curl_cffi if provided
        if self._proxy:
            self._session.proxies = {
                "http": self._proxy,
                "https": self._proxy
            }

    @time_it()
    def new_connection(self, host=None, port=None, timeout=45):
        """Reset the session and cookies."""
        if host:
            self._host = host
        if port:
            self._port = port
        self._timeout = timeout
        self._session = requests.Session()
        self.cookie = ''

    def renew_connection(self, timeout=45):
        self.new_connection(timeout=timeout)

    @time_it()
    def fetch_page(self, url):
        """
        Fetch a URL using Chrome 120 impersonation.
        """
        full_url = f"https://{self._host}{url}"
        logger.debug('Fetching URL %s with Chrome Impersonation', full_url)
        
        try:
            # impersonate="chrome120" handles the TLS fingerprint and default headers
            resp = self._session.get(
                full_url, 
                timeout=self._timeout,
                impersonate="chrome120",
                allow_redirects=True
            )
        except Exception as e:
            raise GoogleConnectionError(f"Failed to connect to {self._host}: {e}")

        if resp.status_code == 429 or "sorry/index" in resp.url:
            msg = "Connection blocked due to unusual activity (CAPTCHA).\n"
            msg += "Your IP is likely flagged for automated scraping."
            raise GoogleConnectionError(msg)

        if resp.status_code != 200:
            raise GoogleConnectionError(f"Got HTTP {resp.status_code}: {resp.reason}")

        # Basic check for the enablejs trap even with impersonation
        if "enablejs" in resp.text and "retry" in resp.text:
             logger.debug("Detected enablejs trap despite impersonation.")
             # If we still hit this, we'll need to re-examine headers or gbv=1

        return resp.text

    def close(self):
        """Close the session."""
        self._session.close()