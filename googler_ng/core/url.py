import base64
import urllib.parse
import uuid

class GoogleUrl(object):
    """
    This class constructs the Google Search/News URL.

    This class is modelled on urllib.parse.ParseResult for familiarity,
    which means it supports reading of all six attributes -- scheme,
    netloc, path, params, query, fragment -- of
    urllib.parse.ParseResult, as well as the geturl() method.

    However, the attributes (properties) and methods listed below should
    be the preferred methods of access to this class.

    Parameters
    ----------
    opts : dict or argparse.Namespace, optional
        See the ``opts`` parameter of `update`.

    Other Parameters
    ----------------
    See "Other Parameters" of `update`.

    Attributes
    ----------
    hostname : str
        Read-write property.
    keywords : str or list of strs
        Read-write property.
    news : bool
        Read-only property.
    videos : bool
        Read-only property.
    url : str
        Read-only property.

    Methods
    -------
    full()
    relative()
    update(opts=None, **kwargs)
    set_queries(**kwargs)
    unset_queries(*args)
    next_page()
    prev_page()
    first_page()

    """

    def __init__(self, opts=None, **kwargs):
        self.scheme = 'https'
        # self.netloc is a calculated property
        self.path = '/search'
        self.params = ''
        # self.query is a calculated property
        self.fragment = ''

        self._tld = None
        self._num = 10
        self._start = 0
        self._keywords = []
        self._sites = None
        self._exclude = None

        self._query_dict = {
            'ie': 'UTF-8',
            'oe': 'UTF-8',
            #'gbv': '1',  # control the presence of javascript on the page, 1=no js, 2=js
            'sei': base64.encodebytes(uuid.uuid4().bytes).decode("ascii").rstrip('=\n').replace('/', '_'),
        }

        # In preloaded HTML parsing mode, set keywords to something so
        # that we are not tripped up by require_keywords.
        if getattr(opts, 'html_file', None) and not getattr(opts, 'keywords', None):
            opts.keywords = ['<debug>']

        self.update(opts, **kwargs)

    def __str__(self):
        return self.url

    @property
    def url(self):
        """The full Google URL you want."""
        return self.full()

    @property
    def hostname(self):
        """The hostname."""
        return self.netloc

    @hostname.setter
    def hostname(self, hostname):
        self.netloc = hostname

    @property
    def keywords(self):
        """The keywords, either a str or a list of strs."""
        return self._keywords

    @keywords.setter
    def keywords(self, keywords):
        self._keywords = keywords

    @property
    def news(self):
        """Whether the URL is for Google News."""
        return 'tbm' in self._query_dict and self._query_dict['tbm'] == 'nws'

    @property
    def videos(self):
        """Whether the URL is for Google Videos."""
        return 'tbm' in self._query_dict and self._query_dict['tbm'] == 'vid'

    def full(self):
        """Return the full URL.

        Returns
        -------
        str

        """
        url = (self.scheme + ':') if self.scheme else ''
        url += '//' + self.netloc + self.relative()
        return url

    def relative(self):
        """Return the relative URL (without scheme and authority).

        Authority (see RFC 3986 section 3.2), or netloc in the
        terminology of urllib.parse, basically means the hostname
        here. The relative URL is good for making HTTP(S) requests to a
        known host.

        Returns
        -------
        str

        """
        rel = self.path
        if self.params:
            rel += ';' + self.params
        if self.query:
            rel += '?' + self.query
        if self.fragment:
            rel += '#' + self.fragment
        return rel

    def update(self, opts=None, **kwargs):
        """Update the URL with the given options.

        Parameters
        ----------
        opts : dict or argparse.Namespace, optional
            Carries options that affect the Google Search/News URL. The
            list of currently recognized option keys with expected value
            types:

                duration: str (GooglerArgumentParser.is_duration)
                exact: bool
                keywords: str or list of strs
                lang: str
                news: bool
                videos: bool
                num: int
                site: str
                start: int
                tld: str
                unfilter: bool

        Other Parameters
        ----------------
        kwargs
            The `kwargs` dict extends `opts`, that is, options can be
            specified either way, in `opts` or as individual keyword
            arguments.

        """

        if opts is None:
            opts = {}
        if hasattr(opts, '__dict__'):
            opts = opts.__dict__
        opts.update(kwargs)

        qd = self._query_dict
        if opts.get('duration'):
            qd['tbs'] = 'qdr:%s' % opts['duration']
        if 'exact' in opts:
            if opts['exact']:
                qd['nfpr'] = 1
            else:
                qd.pop('nfpr', None)
        if opts.get('from') or opts.get('to'):
            cd_min = opts.get('from') or ''
            cd_max = opts.get('to') or ''
            qd['tbs'] = 'cdr:1,cd_min:%s,cd_max:%s' % (cd_min, cd_max)
        if 'keywords' in opts:
            self._keywords = opts['keywords']
        if 'lang' in opts and opts['lang']:
            qd['hl'] = opts['lang']
        if 'geoloc' in opts and opts['geoloc']:
            qd['gl'] = opts['geoloc']
        if 'news' in opts and opts['news']:
            qd['tbm'] = 'nws'
        elif 'videos' in opts and opts['videos']:
            qd['tbm'] = 'vid'
        else:
            qd.pop('tbm', None)
        if 'num' in opts:
            self._num = opts['num']
        if 'sites' in opts:
            self._sites = opts['sites']
        if 'exclude' in opts:
            self._exclude = opts['exclude']
        if 'start' in opts:
            self._start = opts['start']
        if 'tld' in opts:
            self._tld = opts['tld']
        if 'unfilter' in opts and opts['unfilter']:
            qd['filter'] = 0

    def set_queries(self, **kwargs):
        """Forcefully set queries outside the normal `update` mechanism.

        Other Parameters
        ----------------
        kwargs
            Arbitrary key value pairs to be set in the query string. All
            keys and values should be stringifiable.

            Note that certain keys, e.g., ``q``, have their values
            constructed on the fly, so setting those has no actual
            effect.

        """
        for k, v in kwargs.items():
            self._query_dict[k] = v

    def unset_queries(self, *args):
        """Forcefully unset queries outside the normal `update` mechanism.

        Other Parameters
        ----------------
        args
            Arbitrary keys to be unset. No exception is raised if a key
            does not exist in the first place.

            Note that certain keys, e.g., ``q``, are always included in
            the resulting URL, so unsetting those has no actual effect.

        """
        for k in args:
            self._query_dict.pop(k, None)

    def next_page(self):
        """Navigate to the next page."""
        self._start += self._num

    def prev_page(self):
        """Navigate to the previous page.

        Raises
        ------
        ValueError
            If already at the first page (``start=0`` in the current
            query string).

        """
        if self._start == 0:
            raise ValueError('Already at the first page.')
        self._start = (self._start - self._num) if self._start > self._num else 0

    def first_page(self):
        """Navigate to the first page.

        Raises
        ------
        ValueError
            If already at the first page (``start=0`` in the current
            query string).

        """
        if self._start == 0:
            raise ValueError('Already at the first page.')
        self._start = 0

    # Data source: https://web.archive.org/web/20170615200243/https://en.wikipedia.org/wiki/List_of_Google_domains
    # Scraper script: https://gist.github.com/zmwangx/b976e83c14552fe18b71
    TLD_TO_DOMAIN_MAP = {
        'ac': 'google.ac',      'ad': 'google.ad',      'ae': 'google.ae',
        'af': 'google.com.af',  'ag': 'google.com.ag',  'ai': 'google.com.ai',
        'al': 'google.al',      'am': 'google.am',      'ao': 'google.co.ao',
        'ar': 'google.com.ar',  'as': 'google.as',      'at': 'google.at',
        'au': 'google.com.au',  'az': 'google.az',      'ba': 'google.ba',
        'bd': 'google.com.bd',  'be': 'google.be',      'bf': 'google.bf',
        'bg': 'google.bg',      'bh': 'google.com.bh',  'bi': 'google.bi',
        'bj': 'google.bj',      'bn': 'google.com.bn',  'bo': 'google.com.bo',
        'br': 'google.com.br',  'bs': 'google.bs',      'bt': 'google.bt',
        'bw': 'google.co.bw',   'by': 'google.by',      'bz': 'google.com.bz',
        'ca': 'google.ca',      'cat': 'google.cat',    'cc': 'google.cc',
        'cd': 'google.cd',      'cf': 'google.cf',      'cg': 'google.cg',
        'ch': 'google.ch',      'ci': 'google.ci',      'ck': 'google.co.ck',
        'cl': 'google.cl',      'cm': 'google.cm',      'cn': 'google.cn',
        'co': 'google.com.co',  'cr': 'google.co.cr',   'cu': 'google.com.cu',
        'cv': 'google.cv',      'cy': 'google.com.cy',  'cz': 'google.cz',
        'de': 'google.de',      'dj': 'google.dj',      'dk': 'google.dk',
        'dm': 'google.dm',      'do': 'google.com.do',  'dz': 'google.dz',
        'ec': 'google.com.ec',  'ee': 'google.ee',      'eg': 'google.com.eg',
        'es': 'google.es',      'et': 'google.com.et',  'fi': 'google.fi',
        'fj': 'google.com.fj',  'fm': 'google.fm',      'fr': 'google.fr',
        'ga': 'google.ga',      'ge': 'google.ge',      'gf': 'google.gf',
        'gg': 'google.gg',      'gh': 'google.com.gh',  'gi': 'google.com.gi',
        'gl': 'google.gl',      'gm': 'google.gm',      'gp': 'google.gp',
        'gr': 'google.gr',      'gt': 'google.com.gt',  'gy': 'google.gy',
        'hk': 'google.com.hk',  'hn': 'google.hn',      'hr': 'google.hr',
        'ht': 'google.ht',      'hu': 'google.hu',      'id': 'google.co.id',
        'ie': 'google.ie',      'il': 'google.co.il',   'im': 'google.im',
        'in': 'google.co.in',   'io': 'google.io',      'iq': 'google.iq',
        'is': 'google.is',      'it': 'google.it',      'je': 'google.je',
        'jm': 'google.com.jm',  'jo': 'google.jo',      'jp': 'google.co.jp',
        'ke': 'google.co.ke',   'kg': 'google.kg',      'kh': 'google.com.kh',
        'ki': 'google.ki',      'kr': 'google.co.kr',   'kw': 'google.com.kw',
        'kz': 'google.kz',      'la': 'google.la',      'lb': 'google.com.lb',
        'lc': 'google.com.lc',  'li': 'google.li',      'lk': 'google.lk',
        'ls': 'google.co.ls',   'lt': 'google.lt',      'lu': 'google.lu',
        'lv': 'google.lv',      'ly': 'google.com.ly',  'ma': 'google.co.ma',
        'md': 'google.md',      'me': 'google.me',      'mg': 'google.mg',
        'mk': 'google.mk',      'ml': 'google.ml',      'mm': 'google.com.mm',
        'mn': 'google.mn',      'ms': 'google.ms',      'mt': 'google.com.mt',
        'mu': 'google.mu',      'mv': 'google.mv',      'mw': 'google.mw',
        'mx': 'google.com.mx',  'my': 'google.com.my',  'mz': 'google.co.mz',
        'na': 'google.com.na',  'ne': 'google.ne',      'nf': 'google.com.nf',
        'ng': 'google.com.ng',  'ni': 'google.com.ni',  'nl': 'google.nl',
        'no': 'google.no',      'np': 'google.com.np',  'nr': 'google.nr',
        'nu': 'google.nu',      'nz': 'google.co.nz',   'om': 'google.com.om',
        'pa': 'google.com.pa',  'pe': 'google.com.pe',  'pg': 'google.com.pg',
        'ph': 'google.com.ph',  'pk': 'google.com.pk',  'pl': 'google.pl',
        'pn': 'google.co.pn',   'pr': 'google.com.pr',  'ps': 'google.ps',
        'pt': 'google.pt',      'py': 'google.com.py',  'qa': 'google.com.qa',
        'ro': 'google.ro',      'rs': 'google.rs',      'ru': 'google.ru',
        'rw': 'google.rw',      'sa': 'google.com.sa',  'sb': 'google.com.sb',
        'sc': 'google.sc',      'se': 'google.se',      'sg': 'google.com.sg',
        'sh': 'google.sh',      'si': 'google.si',      'sk': 'google.sk',
        'sl': 'google.com.sl',  'sm': 'google.sm',      'sn': 'google.sn',
        'so': 'google.so',      'sr': 'google.sr',      'st': 'google.st',
        'sv': 'google.com.sv',  'td': 'google.td',      'tg': 'google.tg',
        'th': 'google.co.th',   'tj': 'google.com.tj',  'tk': 'google.tk',
        'tl': 'google.tl',      'tm': 'google.tm',      'tn': 'google.tn',
        'to': 'google.to',      'tr': 'google.com.tr',  'tt': 'google.tt',
        'tw': 'google.com.tw',  'tz': 'google.co.tz',   'ua': 'google.com.ua',
        'ug': 'google.co.ug',   'uk': 'google.co.uk',   'uy': 'google.com.uy',
        'uz': 'google.co.uz',   'vc': 'google.com.vc',  've': 'google.co.ve',
        'vg': 'google.vg',      'vi': 'google.co.vi',   'vn': 'google.com.vn',
        'vu': 'google.vu',      'ws': 'google.ws',      'za': 'google.co.za',
        'zm': 'google.co.zm',   'zw': 'google.co.zw',
    }

    @property
    def netloc(self):
        """The hostname."""
        try:
            return 'www.' + self.TLD_TO_DOMAIN_MAP[self._tld]
        except KeyError:
            return 'www.google.com'

    @property
    def query(self):
        """The query string."""
        qd = {}
        qd.update(self._query_dict)
        if self._num != 10:  # Skip sending the default
            qd['num'] = self._num
        if self._start:  # Skip sending the default
            qd['start'] = self._start

        # Construct the q query
        q = ''
        keywords = self._keywords
        sites = self._sites
        exclude = self._exclude
        if keywords:
            if isinstance(keywords, list):
                q += '+'.join(urllib.parse.quote_plus(kw) for kw in keywords)
            else:
                q += urllib.parse.quote_plus(keywords)
        if sites:
            q += '+OR'.join('+site:' + urllib.parse.quote_plus(site) for site in sites)
        if exclude:
            q += ''.join('+-site:' + urllib.parse.quote_plus(e) for e in exclude)
        qd['q'] = q
        return '&'.join('%s=%s' % (k, qd[k]) for k in sorted(qd.keys()))
