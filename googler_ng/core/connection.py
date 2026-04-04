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
        
        # We seed the session with a 'CONSENT=YES' cookie to skip the privacy wall
        self._session.cookies.set("CONSENT", "YES+cb.20260101-01-p0.en+FX+123", domain=".google.com")
        self._session.cookies.set("SOCS", "CAISHAgBEhJnd3NfMjAyNjAxMDEtMF9SQzEaAmVuIAE", domain=".google.com")
        self._warmup_done = False

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
        self._session.cookies.set("CONSENT", "YES+cb.20260101-01-p0.en+FX+123", domain=".google.com")
        if self._proxy:
            self._session.proxies = {
                "http": self._proxy,
                "https": self._proxy
            }
        self.cookie = ''
        self._warmup_done = False

    def _warmup(self):
        """
        Warm up the connection to Google by making a request to the root path.
        This is done to avoid the "enablejs" trap.
        """
        if not self._warmup_done:
            logger.debug('Performing warmup request to https://%s/', self._host)
            try:
                # Do a warmup request on the root path
                self._session.get(
                    f"https://{self._host}/", 
                    timeout=self._timeout,
                    impersonate="chrome110",
                    allow_redirects=True
                )
                self._warmup_done = True
            except Exception as e:
                logger.debug('Warmup failed: %s', e)

    def renew_connection(self, timeout=45):
        self.new_connection(timeout=timeout)

    @time_it()
    def fetch_page(self, url):
        """
        Fetch a URL using impersonation
        """
        self._warmup()
        full_url = f"https://{self._host}{url}"
        logger.debug('Fetching URL %s with Chrome Impersonation', full_url)
        
        try:
            # we need gbv=1 so need to impersonate a device requesting a basic page try a mobile device
            resp = self._session.get(
                full_url, 
                timeout=self._timeout,
                impersonate="chrome110",
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