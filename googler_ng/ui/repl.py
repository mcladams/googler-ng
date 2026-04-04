import atexit
import functools
import logging
import os
import re
import readline
import shutil
import sys
from subprocess import Popen, PIPE, DEVNULL

from googler_ng.core.url import GoogleUrl
from googler_ng.core.connection import GoogleConnection, GoogleConnectionError
from googler_ng.parser.google import GoogleParser
from googler_ng.ui.printer import ResultPrinter
from googler_ng.utils.helpers import printerr, open_url

try:
    from googler_ng.utils.upgrade import RAW_DOWNLOAD_REPO_BASE, _EPOCH_
except ImportError:
    # If phase not completed etc.
    RAW_DOWNLOAD_REPO_BASE = 'https://raw.githubusercontent.com/grassdionera/googler'
    _EPOCH_ = '20220718'

logger = logging.getLogger(__name__)

class GooglerCmdException(Exception):
    pass

class NoKeywordsException(GooglerCmdException):
    pass

def require_keywords(method):
    @functools.wraps(method)
    def enforced_method(self, *args, **kwargs):
        if not self.keywords:
            raise NoKeywordsException('No keywords.')
        method(self, *args, **kwargs)
    return enforced_method

def no_argument(method):
    @functools.wraps(method)
    def enforced_method(self, arg):
        if arg:
            method_name = arg.__name__
            command_name = method_name[3:] if method_name.startswith('do_') else method_name
            logger.warning("Argument to the '%s' command ignored.", command_name)
        method(self)
    return enforced_method

class GooglerCmd(object):
    colors = None
    urlexpand = True
    re_url_index = re.compile(r"\d+(a-z)?")

    def __init__(self, opts):
        super().__init__()

        self._opts = opts
        self._google_url = GoogleUrl(opts)

        if getattr(opts, 'html_file', None):
            self._preload_from_file = opts.html_file
            self._conn = None
        else:
            self._preload_from_file = None
            proxy = getattr(opts, 'proxy', None)
            notweak = getattr(opts, 'notweak', False)
            address_family = getattr(opts, 'address_family', 0)
            self._conn = GoogleConnection(self._google_url.hostname,
                                        address_family=address_family,
                                        proxy=proxy,
                                        notweak=notweak)
            atexit.register(self._conn.close)

        self.results = []
        self._autocorrected = None
        self._showing_results_for = None
        self._results_filtered = False
        self._urltable = {}
        self.promptcolor = True if os.getenv('DISABLE_PROMPT_COLOR') is None else False
        self.no_results_instructions_shown = False
        
        self.printer = ResultPrinter(colors=self.colors, urlexpand=self.urlexpand)

    @property
    def options(self):
        return self._opts

    @property
    def keywords(self):
        return self._google_url.keywords

    @require_keywords
    def fetch(self):
        if self._preload_from_file:
            with open(self._preload_from_file, encoding='utf-8') as fp:
                page = fp.read()
        else:
            page = self._conn.fetch_page(self._google_url.relative())
            if logger.isEnabledFor(logging.DEBUG):
                import tempfile
                fd, tmpfile = tempfile.mkstemp(prefix='googler-response-', suffix='.html')
                os.close(fd)
                with open(tmpfile, 'w', encoding='utf-8') as fp:
                    fp.write(page)
                logger.debug("Response body written to '%s'.", tmpfile)

        parser = GoogleParser(page, news=self._google_url.news, videos=self._google_url.videos)

        self.results = parser.results
        self._autocorrected = parser.autocorrected
        self._showing_results_for = parser.showing_results_for
        self._results_filtered = parser.filtered
        self._urltable = {}
        for r in self.results:
            self._urltable.update(r.urltable())

    def warn_no_results(self):
        printerr('No results.')
        if self.no_results_instructions_shown:
            return

        try:
            import json
            import urllib.error
            import urllib.request
            info_json_url = '%s/master/info.json' % RAW_DOWNLOAD_REPO_BASE
            logger.debug('Fetching %s for project status...', info_json_url)
            try:
                with urllib.request.urlopen(info_json_url, timeout=5) as response:
                    try:
                        info = json.load(response)
                    except Exception:
                        logger.error('Failed to decode project status from %s', info_json_url)
                        raise RuntimeError
            except urllib.error.HTTPError as e:
                logger.error('Failed to fetch project status from %s: HTTP %d', info_json_url, e.code)
                raise RuntimeError
            epoch = info.get('epoch')
            if epoch > _EPOCH_:
                printerr('Your version of googler is broken due to Google-side changes.')
                tracking_issue = info.get('tracking_issue')
                fixed_on_master = info.get('fixed_on_master')
                fixed_in_release = info.get('fixed_in_release')
                if fixed_in_release:
                    printerr('A new version, %s, has been released to address the changes.' % fixed_in_release)
                    printerr('Please upgrade to the latest version.')
                elif fixed_on_master:
                    printerr('The fix has been pushed to master, pending a release.')
                    printerr('Please download the master version https://git.io/googler or wait for a release.')
                else:
                    printerr('The issue is tracked at https://github.com/grassdionera/googler/issues/%s.' % tracking_issue)
                return
        except RuntimeError:
            pass

        printerr('If you believe this is a bug, please review '
                 'https://git.io/googler-no-results before submitting a bug report.')
        self.no_results_instructions_shown = True

    @require_keywords
    def display_results(self, prelude='\n', json_output=False):
        if json_output:
            import json
            results_object = [r.jsonizable_object() for r in self.results]
            print(json.dumps(results_object, indent=2, sort_keys=True, ensure_ascii=False))
        else:
            if not self.results:
                self.warn_no_results()
            else:
                sys.stderr.write(prelude)
                self.printer.colors = self.colors
                self.printer.urlexpand = self.urlexpand
                for r in self.results:
                    self.printer.print_result(r)

    @require_keywords
    def showing_results_for_alert(self, interactive=True):
        colors = self.colors
        if self._showing_results_for:
            if colors:
                actual_query = '\x1b[4m' + self._showing_results_for + '\x1b[24m'
            else:
                actual_query = self._showing_results_for
            if self._autocorrected:
                if interactive:
                    info = 'Showing results for %s; enter "x" for an exact search.' % actual_query
                else:
                    info = 'Showing results for %s; use -x, --exact for an exact search.' % actual_query
            else:
                info = 'No results found; showing results for %s.' % actual_query
            if interactive:
                printerr('')
            if colors:
                printerr(colors.prompt + info + colors.reset)
            else:
                printerr('** ' + info)

    @require_keywords
    def fetch_and_display(self, prelude='\n', json_output=False, interactive=True):
        self.fetch()
        self.showing_results_for_alert()
        self.display_results(prelude=prelude, json_output=json_output)
        if self._results_filtered:
            colors = self.colors
            info = 'Enter "unfilter" to show similar results Google omitted.'
            if colors:
                printerr(colors.prompt + info + colors.reset)
            else:
                printerr('** ' + info)
            printerr('')

    def read_next_command(self):
        colors = self.colors
        message = 'googler (? for help)'
        prompt = (colors.prompt + message + colors.reset + ' ') if (colors and self.promptcolor) else (message + ': ')
        enter_count = 0
        while True:
            try:
                cmd = input(prompt)
            except EOFError:
                sys.exit(0)

            if not cmd:
                enter_count += 1
                if enter_count == 2:
                    sys.exit(0)
            else:
                enter_count = 0

            cmd = ' '.join(cmd.split())
            if cmd:
                self.cmd = cmd
                break

    @staticmethod
    def help():
        from googler_ng.ui.cli import GooglerArgumentParser
        GooglerArgumentParser.print_omniprompt_help(sys.stderr)
        printerr('')

    @require_keywords
    @no_argument
    def do_first(self):
        try:
            self._google_url.first_page()
        except ValueError as e:
            print(e, file=sys.stderr)
            return
        self.fetch_and_display()

    def do_google(self, arg):
        self._opts.keywords = arg
        self._google_url = GoogleUrl(self._opts)
        self.fetch_and_display()

    @require_keywords
    @no_argument
    def do_next(self):
        if not self.results and self._google_url._num > 5:
            printerr('No results.')
        else:
            self._google_url.next_page()
            self.fetch_and_display()

    @require_keywords
    def do_open(self, *args):
        if not args:
            open_url(self._google_url.full())
            return

        for nav in args:
            if nav == 'a':
                for key, value in sorted(self._urltable.items()):
                    open_url(self._urltable[key])
            elif nav in self._urltable:
                open_url(self._urltable[nav])
            elif '-' in nav:
                try:
                    vals = [int(x) for x in nav.split('-')]
                    if (len(vals) != 2):
                        printerr('Invalid range %s.' % nav)
                        continue

                    if vals[0] > vals[1]:
                        vals[0], vals[1] = vals[1], vals[0]

                    for _id in range(vals[0], vals[1] + 1):
                        if str(_id) in self._urltable:
                            open_url(self._urltable[str(_id)])
                        else:
                            printerr('Invalid index %s.' % _id)
                except ValueError:
                    printerr('Invalid range %s.' % nav)
            else:
                printerr('Invalid index %s.' % nav)

    @require_keywords
    @no_argument
    def do_previous(self):
        try:
            self._google_url.prev_page()
        except ValueError as e:
            print(e, file=sys.stderr)
            return

        self.fetch_and_display()

    @require_keywords
    @no_argument
    def do_exact(self):
        self._google_url.update(start=0, exact=True)
        self.fetch_and_display()

    @require_keywords
    @no_argument
    def do_unfilter(self):
        self._google_url.update(start=0)
        self._google_url.set_queries(filter=0)
        self.fetch_and_display()

    def copy_url(self, idx):
        try:
            try:
                content = self._urltable[idx].encode('utf-8')
            except KeyError:
                printerr('Invalid index.')
                return

            copier_params = []
            if sys.platform.startswith(('linux', 'freebsd', 'openbsd')):
                if shutil.which('xsel') is not None:
                    copier_params = ['xsel', '-b', '-i']
                elif shutil.which('xclip') is not None:
                    copier_params = ['xclip', '-selection', 'clipboard']
                elif shutil.which('wl-copy') is not None:
                    copier_params = ['wl-copy']
                elif shutil.which('termux-clipboard-set') is not None:
                    copier_params = ['termux-clipboard-set']
            elif sys.platform == 'darwin':
                copier_params = ['pbcopy']
            elif sys.platform == 'win32':
                copier_params = ['clip']

            if copier_params:
                Popen(copier_params, stdin=PIPE, stdout=DEVNULL, stderr=DEVNULL).communicate(content)
                return

            if os.getenv('TMUX_PANE'):
                copier_params = ['tmux', 'set-buffer']
                Popen(copier_params + [content], stdin=DEVNULL, stdout=DEVNULL, stderr=DEVNULL).communicate()
                return

            if os.getenv('STY'):
                import tempfile
                copier_params = ['screen', '-X', 'readbuf', '-e', 'utf8']
                tmpfd, tmppath = tempfile.mkstemp()
                try:
                    with os.fdopen(tmpfd, 'wb') as fp:
                        fp.write(content)
                    copier_params.append(tmppath)
                    Popen(copier_params, stdin=DEVNULL, stdout=DEVNULL, stderr=DEVNULL).communicate()
                finally:
                    os.unlink(tmppath)
                return

            printerr('failed to locate suitable clipboard utility')
        except Exception:
            raise NoKeywordsException

    def cmdloop(self):
        if self.keywords:
            self.fetch_and_display()
        else:
            printerr('Please initiate a query.')

        while True:
            self.read_next_command()
            try:
                cmd = self.cmd
                if cmd == 'f':
                    self.do_first('')
                elif cmd.startswith('g '):
                    self.do_google(cmd[2:])
                elif cmd == 'n':
                    self.do_next('')
                elif cmd == 'o':
                    self.do_open()
                elif cmd.startswith('o '):
                    self.do_open(*cmd[2:].split())
                elif cmd.startswith('O '):
                    open_url.override_text_browser = True
                    self.do_open(*cmd[2:].split())
                    open_url.override_text_browser = False
                elif cmd == 'p':
                    self.do_previous('')
                elif cmd == 'q':
                    break
                elif cmd == 'x':
                    self.do_exact('')
                elif cmd == 'unfilter':
                    self.do_unfilter('')
                elif cmd == '?':
                    self.help()
                elif cmd in self._urltable:
                    open_url(self._urltable[cmd])
                elif self.keywords and cmd.isdigit() and int(cmd) < 100:
                    printerr('Index out of bound. To search for the number, use g.')
                elif cmd == 'u':
                    self.urlexpand = not self.urlexpand
                    self.display_results()
                elif cmd.startswith('c ') and self.re_url_index.match(cmd[2:]):
                    self.copy_url(cmd[2:])
                else:
                    self.do_google(cmd)
            except NoKeywordsException:
                printerr('Initiate a query first.')
