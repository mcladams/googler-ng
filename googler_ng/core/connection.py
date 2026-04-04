import base64
import gzip
import http.client
from http.client import HTTPSConnection
import logging
import os
import socket
import ssl
import sys
import textwrap
import urllib.parse

from googler_ng.utils.helpers import time_it

logger = logging.getLogger(__name__)

USER_AGENT = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_1) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/78.0.3904.108 Safari/537.36'


def https_proxy_from_environment():
    return os.getenv('https_proxy')


def parse_proxy_spec(proxyspec):
    if '://' in proxyspec:
        pos = proxyspec.find('://')
        scheme = proxyspec[:pos]
        proxyspec = proxyspec[pos+3:]
        if scheme.lower() != 'http':
            # Only support HTTP proxies.
            #
            # In particular, we don't support HTTPS proxies since we
            # only speak plain HTTP to the proxy server, so don't give
            # users a false sense of security.
            raise NotImplementedError('Unsupported proxy scheme %s.' % scheme)

    if '@' in proxyspec:
        pos = proxyspec.find('@')
        user_passwd = urllib.parse.unquote(proxyspec[:pos])
        # Remove trailing '/' if any
        host_port = proxyspec[pos+1:].rstrip('/')
    else:
        user_passwd = None
        host_port = proxyspec.rstrip('/')

    if ':' not in host_port:
        # Use port 1080 as default, following curl.
        host_port += ':1080'

    return user_passwd, host_port


class HardenedHTTPSConnection(HTTPSConnection):
    """Overrides HTTPSConnection.connect to specify TLS version

    NOTE: TLS 1.2 is supported from Python 3.4
    """

    def __init__(self, host, address_family=0, **kwargs):
        HTTPSConnection.__init__(self, host, **kwargs)
        self.address_family = address_family

    def connect(self, notweak=False):
        sock = self.create_socket_connection()

        # Optimizations not available on OS X
        if not notweak and sys.platform.startswith('linux'):
            try:
                sock.setsockopt(socket.SOL_TCP, socket.TCP_DEFER_ACCEPT, 1)
                sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_QUICKACK, 1)
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 524288)
            except OSError:
                # Doesn't work on Windows' Linux subsystem (#179)
                logger.debug('setsockopt failed')

        if getattr(self, '_tunnel_host', None):
            self.sock = sock
        elif not notweak:
            # Try to use TLS 1.2
            ssl_context = None
            if hasattr(ssl, 'PROTOCOL_TLS_CLIENT'):
                # Since Python 3.6
                ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
                ssl_context.check_hostname = False
                ssl_context.verify_mode = ssl.CERT_NONE
            elif hasattr(ssl, 'PROTOCOL_TLS'):
                # Since Python 3.5.3
                ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS)
                if hasattr(ssl_context, "minimum_version"):
                    # Python 3.7 with OpenSSL 1.1.0g or later
                    ssl_context.minimum_version = ssl.TLSVersion.TLSv1_2
                else:
                    ssl_context.options |= (ssl.OP_NO_SSLv2 | ssl.OP_NO_SSLv3 |
                                            ssl.OP_NO_TLSv1 | ssl.OP_NO_TLSv1_1)
            elif hasattr(ssl, 'PROTOCOL_TLSv1_2'):
                # Since Python 3.4
                ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLSv1_2)
            if ssl_context:
                self.sock = ssl_context.wrap_socket(sock)
                return

        # Fallback
        HTTPSConnection.connect(self)

    # Adapted from socket.create_connection.
    # https://github.com/python/cpython/blob/bce4ddafdd188cc6deb1584728b67b9e149ca6a4/Lib/socket.py#L771-L813
    def create_socket_connection(self):
        err = None
        results = socket.getaddrinfo(self.host, self.port, self.address_family, socket.SOCK_STREAM)
        # Prefer IPv4 if address family isn't explicitly specified.
        if self.address_family == 0:
            results = sorted(results, key=lambda res: 1 if res[0] == socket.AF_INET else 2)
        for af, socktype, proto, canonname, sa in results:
            sock = None
            try:
                sock = socket.socket(af, socktype, proto)
                if self.timeout is not None:
                    sock.settimeout(self.timeout)
                if self.source_address:
                    sock.bind(self.source_address)
                sock.connect(sa)
                # Break explicitly a reference cycle
                err = None
                self.address_family = af
                logger.debug('Opened socket to %s:%d',
                             sa[0] if af == socket.AF_INET else ('[%s]' % sa[0]),
                             sa[1])
                return sock

            except socket.error as _:
                err = _
                if sock is not None:
                    sock.close()

        if err is not None:
            try:
                raise err
            finally:
                # Break explicitly a reference cycle
                err = None
        else:
            raise socket.error("getaddrinfo returns an empty list")


class GoogleConnectionError(Exception):
    pass


class GoogleConnection(object):
    """
    This class facilitates connecting to and fetching from Google.

    Parameters
    ----------
    See http.client.HTTPSConnection for documentation of the
    parameters.

    Raises
    ------
    GoogleConnectionError

    Attributes
    ----------
    host : str
        The currently connected host. Read-only property. Use
        `new_connection` to change host.

    Methods
    -------
    new_connection(host=None, port=None, timeout=45)
    renew_connection(timeout=45)
    fetch_page(url)
    close()

    """

    def __init__(self, host, port=None, address_family=0, timeout=45, proxy=None, notweak=False):
        self._host = None
        self._port = None
        self._address_family = address_family
        self._proxy = proxy
        self._notweak = notweak
        self._conn = None
        self.new_connection(host, port=port, timeout=timeout)
        self.cookie = ''

    @property
    def host(self):
        """The host currently connected to."""
        return self._host

    @time_it()
    def new_connection(self, host=None, port=None, timeout=45):
        """Close the current connection (if any) and establish a new one.

        Parameters
        ----------
        See http.client.HTTPSConnection for documentation of the
        parameters. Renew the connection (i.e., reuse the current host
        and port) if host is None or empty.

        Raises
        ------
        GoogleConnectionError

        """
        if self._conn:
            self._conn.close()

        if not host:
            host = self._host
            port = self._port
        self._host = host
        self._port = port
        host_display = host + (':%d' % port if port else '')

        proxy = self._proxy

        if proxy:
            proxy_user_passwd, proxy_host_port = parse_proxy_spec(proxy)

            logger.debug('Connecting to proxy server %s', proxy_host_port)
            self._conn = HardenedHTTPSConnection(proxy_host_port,
                                                 address_family=self._address_family, timeout=timeout)

            logger.debug('Tunnelling to host %s' % host_display)
            connect_headers = {}
            if proxy_user_passwd:
                connect_headers['Proxy-Authorization'] = 'Basic %s' % base64.b64encode(
                    proxy_user_passwd.encode('utf-8')
                ).decode('utf-8')
            self._conn.set_tunnel(host, port=port, headers=connect_headers)

            try:
                self._conn.connect(self._notweak)
            except Exception as e:
                msg = 'Failed to connect to proxy server %s: %s.' % (proxy, e)
                raise GoogleConnectionError(msg)
        else:
            logger.debug('Connecting to new host %s', host_display)
            self._conn = HardenedHTTPSConnection(host, port=port,
                                                 address_family=self._address_family, timeout=timeout)
            try:
                self._conn.connect(self._notweak)
            except Exception as e:
                msg = 'Failed to connect to %s: %s.' % (host_display, e)
                raise GoogleConnectionError(msg)

    def renew_connection(self, timeout=45):
        """Renew current connection.

        Equivalent to ``new_connection(timeout=timeout)``.

        """
        self.new_connection(timeout=timeout)

    @time_it()
    def fetch_page(self, url):
        """Fetch a URL.

        Allows one reconnection and multiple redirections before failing
        and raising GoogleConnectionError.

        Parameters
        ----------
        url : str
            The URL to fetch, relative to the host.

        Raises
        ------
        GoogleConnectionError
            When not getting HTTP 200 even after the allowed one
            reconnection and/or one redirection, or when Google is
            blocking query due to unusual activity.

        Returns
        -------
        str
            Response payload, gunzipped (if applicable) and decoded (in UTF-8).

        """
        try:
            self._raw_get(url)
        except (http.client.HTTPException, OSError) as e:
            logger.debug('Got exception: %s.', e)
            logger.debug('Attempting to reconnect...')
            self.renew_connection()
            try:
                self._raw_get(url)
            except http.client.HTTPException as e:
                logger.debug('Got exception: %s.', e)
                raise GoogleConnectionError("Failed to get '%s'." % url)

        resp = self._resp
        redirect_counter = 0
        while resp.status != 200 and redirect_counter < 3:
            if resp.status in {301, 302, 303, 307, 308}:
                redirection_url = resp.getheader('location', '')
                if 'sorry/IndexRedirect?' in redirection_url or 'sorry/index?' in redirection_url:
                    msg = "Connection blocked due to unusual activity.\n"
                    if self._conn.address_family == socket.AF_INET6:
                        msg += textwrap.dedent("""\
                        You are connecting over IPv6 which is likely the problem. Try to make
                        sure the machine has a working IPv4 network interface configured.
                        See also the -4, --ipv4 option of googler.\n""")
                    msg += textwrap.dedent("""\
                    THIS IS NOT A BUG, please do NOT report it as a bug unless you have specific
                    information that may lead to the development of a workaround.
                    You IP address is temporarily or permanently blocked by Google and requires
                    reCAPTCHA-solving to use the service, which googler is not capable of.
                    Possible causes include issuing too many queries in a short time frame, or
                    operating from a shared / low reputation IP with a history of abuse.
                    Please do NOT use googler for automated scraping.""")
                    msg = " ".join(msg.splitlines())
                    raise GoogleConnectionError(msg)
                self._redirect(redirection_url)
                resp = self._resp
                redirect_counter += 1
            else:
                break

        if resp.status != 200:
            raise GoogleConnectionError('Got HTTP %d: %s' % (resp.status, resp.reason))

        payload = resp.read()
        try:
            return gzip.decompress(payload).decode('utf-8')
        except OSError:
            # Not gzipped
            return payload.decode('utf-8')

    def _redirect(self, url):
        """Redirect to and fetch a new URL.

        Like `_raw_get`, the response is stored in ``self._resp``. A new
        connection is made if redirecting to a different host or local proxy is enabled.

        Parameters
        ----------
        url : str
            If absolute and points to a different host, make a new
            connection.

        Raises
        ------
        GoogleConnectionError

        """
        logger.debug('Redirecting to URL %s', url)
        segments = urllib.parse.urlparse(url)

        host = segments.netloc
        if host != self._host or self._proxy is not None:
            self.new_connection(host)

        relurl = urllib.parse.urlunparse(('', '') + segments[2:])
        try:
            self._raw_get(relurl)
        except http.client.HTTPException as e:
            logger.debug('Got exception: %s.', e)
            raise GoogleConnectionError("Failed to get '%s'." % url)

    def _raw_get(self, url):
        """Make a raw HTTP GET request.

        No status check (which implies no redirection). Response can be
        accessed from ``self._resp``.

        Parameters
        ----------
        url : str
            URL relative to the host, used in the GET request.

        Raises
        ------
        http.client.HTTPException

        """
        logger.debug('Fetching URL %s', url)
        self._conn.request('GET', url, None, {
            'Accept': 'text/html',
            'Accept-Encoding': 'gzip',
            'User-Agent': USER_AGENT,
            'Cookie': self.cookie,
            'Connection': 'keep-alive',
            'DNT': '1',
        })
        self._resp = self._conn.getresponse()
        if self.cookie == '':
            complete_cookie = self._resp.getheader('Set-Cookie')
            # Cookie won't be available if already blocked
            if complete_cookie is not None:
                self.cookie = complete_cookie[:complete_cookie.find(';')]
                logger.debug('Cookie: %s' % self.cookie)

    def close(self):
        """Close the connection (if one is active)."""
        if self._conn:
            self._conn.close()
