import os
import urllib.parse
from googler_ng.utils.text import TrackedTextwrap

class ResultPrinter:
    def __init__(self, colors=None, urlexpand=True):
        self.colors = colors
        self.urlexpand = urlexpand

    def print_result(self, result):
        """Print the result entry."""
        self._print_title_and_url(result.index, result.title, result.url)
        self._print_metadata_and_abstract(result.abstract, metadata=result.metadata, matches=result.matches)

        for sitelink in result.sitelinks:
            self._print_title_and_url(sitelink.index, sitelink.title, sitelink.url, indent=4)
            self._print_metadata_and_abstract(sitelink.abstract, indent=4)

    def _print_title_and_url(self, index, title, url, indent=0):
        if not self.urlexpand:
            url = '[' + urllib.parse.urlparse(url).netloc + ']'

        if self.colors:
            # Adjust index to print result index clearly
            print(" %s%s%-3s%s" % (' ' * indent, self.colors.index, index + '.', self.colors.reset), end='')
            if not self.urlexpand:
                print(' ' + self.colors.title + title + self.colors.reset + ' ' + self.colors.url + url + self.colors.reset)
            else:
                print(' ' + self.colors.title + title + self.colors.reset)
                print(' ' * (indent + 5) + self.colors.url + url + self.colors.reset)
        else:
            if self.urlexpand:
                print(' %s%-3s %s' % (' ' * indent, index + '.', title))
                print(' %s%s' % (' ' * (indent + 4), url))
            else:
                print(' %s%-3s %s %s' % (' ' * indent, index + '.', title, url))

    def _print_metadata_and_abstract(self, abstract, metadata=None, matches=None, indent=0):
        try:
            columns, _ = os.get_terminal_size()
        except OSError:
            columns = 0

        if metadata:
            if self.colors:
                print(' ' * (indent + 5) + self.colors.metadata + metadata + self.colors.reset)
            else:
                print(' ' * (indent + 5) + metadata)

        if abstract:
            fillwidth = (columns - (indent + 6)) if columns > indent + 6 else len(abstract)
            wrapped_abstract = TrackedTextwrap(abstract, fillwidth)
            if self.colors:
                # Highlight matches.
                for match in matches or []:
                    offset = match['offset']
                    span = len(match['phrase'])
                    wrapped_abstract.insert_zero_width_sequence('\x1b[1m', offset)
                    wrapped_abstract.insert_zero_width_sequence('\x1b[0m', offset + span)

            if self.colors:
                print(self.colors.abstract, end='')
            for line in wrapped_abstract.lines:
                print('%s%s' % (' ' * (indent + 5), line))
            if self.colors:
                print(self.colors.reset, end='')

        print('')
