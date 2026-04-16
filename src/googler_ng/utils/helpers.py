import codecs
import functools
import locale
import logging
import os
import platform
import subprocess
import sys
import textwrap
import urllib.parse
import webbrowser

logger = logging.getLogger(__name__)

text_browsers = ['elinks', 'links', 'lynx', 'w3m', 'www-browser']

def open_url(url):
    """Open an URL in the user's default web browser.

    The string attribute ``open_url.url_handler`` can be used to open URLs
    in a custom CLI script or utility. A subprocess is spawned with url as
    the parameter in this case instead of the usual webbrowser.open() call.

    Whether the browser's output (both stdout and stderr) are suppressed
    depends on the boolean attribute ``open_url.suppress_browser_output``.
    If the attribute is not set upon a call, set it to a default value,
    which means False if BROWSER is set to a known text-based browser --
    elinks, links, lynx, w3m or 'www-browser'; or True otherwise.

    The string attribute ``open_url.override_text_browser`` can be used to
    ignore env var BROWSER as well as some known text-based browsers and
    attempt to open url in a GUI browser available.
    Note: If a GUI browser is indeed found, this option ignores the program
          option `show-browser-logs`
    """
    logger.debug('Opening %s', url)

    # Custom URL handler gets max priority
    if hasattr(open_url, 'url_handler'):
        subprocess.run([open_url.url_handler, url])
        return

    browser = webbrowser.get()
    if open_url.override_text_browser:
        browser_output = open_url.suppress_browser_output
        for name in [b for b in webbrowser._tryorder if b not in text_browsers]:
            browser = webbrowser.get(name)
            logger.debug(browser)

            # Found a GUI browser, suppress browser output
            open_url.suppress_browser_output = True
            break

    if open_url.suppress_browser_output:
        _stderr = os.dup(2)
        os.close(2)
        _stdout = os.dup(1)
        # Patch for GUI browsers on WSL
        if "microsoft" not in platform.uname()[3].lower():
            os.close(1)
        fd = os.open(os.devnull, os.O_RDWR)
        os.dup2(fd, 2)
        os.dup2(fd, 1)
    try:
        browser.open(url, new=2)
    finally:
        if open_url.suppress_browser_output:
            os.close(fd)
            os.dup2(_stderr, 2)
            os.dup2(_stdout, 1)

    if open_url.override_text_browser:
        open_url.suppress_browser_output = browser_output


def printerr(msg):
    """Print message, verbatim, to stderr.

    ``msg`` could be any stringifiable value.
    """
    print(msg, file=sys.stderr)


def unwrap(text):
    """Unwrap text."""
    lines = text.split('\n')
    result = ''
    for i in range(len(lines) - 1):
        result += lines[i]
        if not lines[i]:
            # Paragraph break
            result += '\n\n'
        elif lines[i + 1]:
            # Next line is not paragraph break, add space
            result += ' '
    # Handle last line
    result += lines[-1] if lines[-1] else '\n'
    return result


def check_stdout_encoding():
    """Make sure stdout encoding is utf-8.

    If not, print error message and instructions, then exit with
    status 1.

    This function is a no-op on win32 because encoding on win32 is
    messy, and let's just hope for the best. /s
    """
    if sys.platform == 'win32':
        return

    # Use codecs.lookup to resolve text encoding alias
    encoding = codecs.lookup(sys.stdout.encoding).name
    if encoding != 'utf-8':
        locale_lang, locale_encoding = locale.getlocale()
        if locale_lang is None:
            locale_lang = '<unknown>'
        if locale_encoding is None:
            locale_encoding = '<unknown>'
        ioencoding = os.getenv('PYTHONIOENCODING', 'not set')
        sys.stderr.write(unwrap(textwrap.dedent("""\
        stdout encoding '{encoding}' detected. googler requires utf-8 to
        work properly. The wrong encoding may be due to a non-UTF-8
        locale or an improper PYTHONIOENCODING. (For the record, your
        locale language is {locale_lang} and locale encoding is
        {locale_encoding}; your PYTHONIOENCODING is {ioencoding}.)

        Please set a UTF-8 locale (e.g., en_US.UTF-8) or set
        PYTHONIOENCODING to utf-8.
        """.format(
            encoding=encoding,
            locale_lang=locale_lang,
            locale_encoding=locale_encoding,
            ioencoding=ioencoding,
        ))))
        sys.exit(1)


def time_it(description=None):
    def decorator(func):
        @functools.wraps(func)
        def wrapped(*args, **kwargs):
            # Only profile in debug mode.
            if not logger.isEnabledFor(logging.DEBUG):
                return func(*args, **kwargs)

            import time
            mark = time.perf_counter()
            ret = func(*args, **kwargs)
            duration = time.perf_counter() - mark
            logger.debug('%s completed in \x1b[33m%.3fs\x1b[0m', description or func.__name__, duration)
            return ret

        return wrapped

    return decorator


def unwrap_link(link):
    qs = urllib.parse.urlparse(link).query
    try:
        url = urllib.parse.parse_qs(qs)['q'][0]
    except KeyError:
        return link
    else:
        if "://" in url:
            return url
        else:
            # Google's internal services link, e.g.,
            # /search?q=google&..., which cannot be unwrapped into
            # an actual URL.
            raise ValueError(link)
