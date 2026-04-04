import argparse
import logging
import os
import platform
import readline
import socket
import sys
import textwrap

from googler_ng.core.connection import https_proxy_from_environment
from googler_ng.ui.colors import COLORMAP, Colors
from googler_ng.ui.repl import GooglerCmd
from googler_ng.utils.helpers import check_stdout_encoding, open_url, text_browsers

def system_is_windows():
    return sys.platform in {'win32', 'cygwin'}

def python_version():
    return '%d.%d.%d' % sys.version_info[:3]

logger = logging.getLogger(__name__)
_VERSION_ = '0.1.0'

def set_win_console_mode():
    if platform.release() == '10':
        STD_OUTPUT_HANDLE = -11
        STD_ERROR_HANDLE = -12
        ENABLE_VIRTUAL_TERMINAL_PROCESSING = 0x0004
        try:
            from ctypes import windll, wintypes, byref
            kernel32 = windll.kernel32
            for nhandle in (STD_OUTPUT_HANDLE, STD_ERROR_HANDLE):
                handle = kernel32.GetStdHandle(nhandle)
                old_mode = wintypes.DWORD()
                if not kernel32.GetConsoleMode(handle, byref(old_mode)):
                    raise RuntimeError('GetConsoleMode failed')
                new_mode = old_mode.value | ENABLE_VIRTUAL_TERMINAL_PROCESSING
                if not kernel32.SetConsoleMode(handle, new_mode):
                    raise RuntimeError('SetConsoleMode failed')
        except Exception:
            pass

class GooglerArgumentParser(argparse.ArgumentParser):
    """Custom argument parser for googler."""

    @staticmethod
    def print_omniprompt_help(file=None):
        file = sys.stderr if file is None else file
        file.write(textwrap.dedent("""
        omniprompt keys:
          n, p                  fetch the next or previous set of search results
          index                 open the result corresponding to index in browser
          f                     jump to the first page
          o [index|range|a ...] open space-separated result indices, numeric ranges
                                (sitelinks unsupported in ranges), or all, in browser
                                open the current search in browser, if no arguments
          O [index|range|a ...] like key 'o', but try to open in a GUI browser
          g keywords            new Google search for 'keywords' with original options
                                should be used to search omniprompt keys and indices
          c index               copy url to clipboard
          u                     toggle url expansion
          q, ^D, double Enter   exit googler
          ?                     show omniprompt help
          *                     other inputs issue a new search with original options
        """))

    @staticmethod
    def print_general_info(file=None):
        file = sys.stderr if file is None else file
        file.write(textwrap.dedent("""
        Version %s
        Copyright © 2008 Henri Hakkinen
        Copyright © 2015-2021 Arun Prakash Jana <engineerarun@gmail.com>
        Zhiming Wang <zmwangx@gmail.com>
        License: GPLv3
        Webpage: https://github.com/grassdionera/googler
        """ % _VERSION_))

    def print_help(self, file=None):
        super().print_help(file)
        self.print_omniprompt_help(file)
        self.print_general_info(file)

    def error(self, message):
        sys.stderr.write('%s: error: %s\n\n' % (self.prog, message))
        self.print_help(sys.stderr)
        self.exit(2)

    @staticmethod
    def positive_int(arg):
        try:
            n = int(arg)
            assert n > 0
            return n
        except (ValueError, AssertionError):
            raise argparse.ArgumentTypeError('%s is not a positive integer' % arg)

    @staticmethod
    def nonnegative_int(arg):
        try:
            n = int(arg)
            assert n >= 0
            return n
        except (ValueError, AssertionError):
            raise argparse.ArgumentTypeError('%s is not a non-negative integer' % arg)

    @staticmethod
    def is_duration(arg):
        try:
            import re
            if arg[0] not in ('h', 'd', 'w', 'm', 'y') or int(arg[1:]) < 0:
                raise ValueError
        except (TypeError, IndexError, ValueError):
            raise argparse.ArgumentTypeError('%s is not a valid duration' % arg)
        return arg

    @staticmethod
    def is_date(arg):
        import re
        if re.match(r'^(\d+/){0,2}\d+$', arg):
            return arg
        else:
            raise argparse.ArgumentTypeError('%s is not a valid date/month/year; '
                                             'use the American date format with slashes')

    @staticmethod
    def is_colorstr(arg):
        try:
            assert len(arg) == 6
            for c in arg:
                assert c in COLORMAP
        except AssertionError:
            raise argparse.ArgumentTypeError('%s is not a valid color string' % arg)
        return arg


def parse_args(args=None, namespace=None):
    colorstr_env = os.getenv('GOOGLER_COLORS')

    argparser = GooglerArgumentParser(description='Google from the command-line.')
    addarg = argparser.add_argument
    addarg('-s', '--start', type=argparser.nonnegative_int, default=0,
           metavar='N', help='start at the Nth result')
    addarg('-n', '--count', dest='num', type=argparser.positive_int,
           default=10, metavar='N', help='show N results (default 10)')
    addarg('-N', '--news', action='store_true',
           help='show results from news section')
    addarg('-V', '--videos', action='store_true',
           help='show results from videos section')
    addarg('-c', '--tld', metavar='TLD',
           help="""country-specific search with top-level domain .TLD, e.g., 'in'
           for India""")
    addarg('-l', '--lang', metavar='LANG', help='display in language LANG')
    addarg('-g', '--geoloc', metavar='CC',
           help="""country-specific geolocation search with country code CC, e.g.
           'in' for India. Country codes are the same as top-level domains""")
    addarg('-x', '--exact', action='store_true',
           help='disable automatic spelling correction')
    addarg('--colorize', nargs='?', choices=['auto', 'always', 'never'],
           const='always', default='auto',
           help="""whether to colorize output; defaults to 'auto', which enables
           color when stdout is a tty device; using --colorize without an argument
           is equivalent to --colorize=always""")
    addarg('-C', '--nocolor', action='store_true',
           help='equivalent to --colorize=never')
    addarg('--colors', dest='colorstr', type=argparser.is_colorstr,
           default=colorstr_env if colorstr_env else 'GKlgxy', metavar='COLORS',
           help='set output colors (see man page for details)')
    addarg('-j', '--first', '--lucky', dest='lucky', action='store_true',
           help='open the first result in web browser and exit')
    addarg('-t', '--time', dest='duration', type=argparser.is_duration,
           metavar='dN', help='time limit search '
           '[h5 (5 hrs), d5 (5 days), w5 (5 weeks), m5 (5 months), y5 (5 years)]')
    addarg('--from', type=argparser.is_date,
           help="""starting date/month/year of date range; must use American date
           format with slashes, e.g., 2/24/2020, 2/2020, 2020; can be used in
           conjunction with --to, and overrides -t, --time""")
    addarg('--to', type=argparser.is_date,
           help='ending date/month/year of date range; see --from')
    addarg('-w', '--site', dest='sites', action='append', metavar='SITE',
           help='search a site using Google')
    addarg('-e', '--exclude', dest='exclude', action='append', metavar='SITE',
           help='exclude site from results')
    addarg('--unfilter', action='store_true', help='do not omit similar results')
    addarg('-p', '--proxy', default=https_proxy_from_environment(),
           help="""tunnel traffic through an HTTP proxy;
           PROXY is of the form [http://][user:password@]proxyhost[:port]""")
    addarg('--noua', action='store_true', help=argparse.SUPPRESS)
    addarg('--notweak', action='store_true',
           help='disable TCP optimizations and forced TLS 1.2')
    addarg('--json', action='store_true',
           help='output in JSON format; implies --noprompt')
    addarg('--url-handler', metavar='UTIL',
           help='custom script or cli utility to open results')
    addarg('--show-browser-logs', action='store_true',
           help='do not suppress browser output (stdout and stderr)')
    addarg('--np', '--noprompt', dest='noninteractive', action='store_true',
           help='search and exit, do not prompt')
    addarg('-4', '--ipv4', action='store_const', dest='address_family',
           const=socket.AF_INET, default=0,
           help="""only connect over IPv4
           (by default, IPv4 is preferred but IPv6 is used as a fallback)""")
    addarg('-6', '--ipv6', action='store_const', dest='address_family',
           const=socket.AF_INET6, default=0,
           help='only connect over IPv6')
    addarg('keywords', nargs='*', metavar='KEYWORD', help='search keywords')
    addarg('-v', '--version', action='version', version=_VERSION_)
    addarg('-d', '--debug', action='store_true', help='enable debugging')
    addarg('-D', '--debugger', action='store_true', help=argparse.SUPPRESS)
    addarg('--parse', dest='html_file', help=argparse.SUPPRESS)
    addarg('--complete', help=argparse.SUPPRESS)

    parsed = argparser.parse_args(args, namespace)
    if parsed.nocolor:
        parsed.colorize = 'never'

    return parsed


def main():
    try:
        opts = parse_args()

        if opts.debug:
            logging.basicConfig(level=logging.DEBUG, format='[DEBUG] %(message)s')
            logger.debug('googler version %s', _VERSION_)
            logger.debug('Python version %s', python_version())
            logger.debug('Platform: %s', platform.platform())

        if opts.debugger:
            # We used to set a global debugger variable, but that's handled locally now or not used.
            pass

        if hasattr(opts, 'upgrade') and opts.upgrade:
            self_upgrade(include_git=opts.include_git)
            sys.exit(0)

        check_stdout_encoding()

        if opts.keywords:
            try:
                readline.add_history(' '.join(opts.keywords))
            except Exception:
                pass

        if opts.colorize == 'always':
            colorize = True
        elif opts.colorize == 'auto':
            colorize = sys.stdout.isatty()
        else:
            colorize = False

        if colorize:
            colors = Colors(*[COLORMAP[c] for c in opts.colorstr], reset=COLORMAP['x'])
        else:
            colors = None
            
        # Instead of monkeypatching Result.colors, we pass it to the Repl which has a printer
        GooglerCmd.colors = colors
        GooglerCmd.urlexpand = True if os.getenv('DISABLE_URL_EXPANSION') is None else False

        if sys.platform == 'win32' and sys.stdout.isatty() and colorize:
            set_win_console_mode()

        if opts.url_handler is not None:
            open_url.url_handler = opts.url_handler
        else:
            open_url.override_text_browser = False
            if opts.show_browser_logs or (os.getenv('BROWSER') in text_browsers):
                open_url.suppress_browser_output = False
            else:
                open_url.suppress_browser_output = True

        if opts.noua:
            logger.warning('--noua option has been deprecated and has no effect (see #284)')

        repl = GooglerCmd(opts)

        if opts.json or opts.lucky or opts.noninteractive or opts.html_file:
            repl.fetch()
            if opts.lucky:
                if repl.results:
                    open_url(repl.results[0].url)
                else:
                    print('No results.', file=sys.stderr)
            else:
                repl.showing_results_for_alert(interactive=False)
                repl.display_results(json_output=opts.json)
            sys.exit(0)

        repl.cmdloop()
    except Exception as e:
        if logger.isEnabledFor(logging.DEBUG):
            raise
        else:
            logger.error(e)
            sys.exit(1)

if __name__ == '__main__':
    main()
