import collections
import logging
import re

from googler_ng.config.selectors import SELECTORS
from googler_ng.parser.models import Result, Sitelink
from googler_ng.utils.helpers import unwrap_link, time_it

logger = logging.getLogger(__name__)

try:
    from googler_ng.dom.engine import parse_html, TextNode
except ImportError:
    pass

class GoogleParser(object):

    def __init__(self, html, *, news=False, videos=False, debugger=False):
        self.news = news
        self.videos = videos
        self.debugger = debugger
        self.autocorrected = False
        self.showing_results_for = None
        self.filtered = False
        self.results = []
        self.parse(html)

    @time_it()
    def parse(self, html):
        tree = parse_html(html)

        if self.debugger:
            logger.debug('Inspect the DOM through the tree variable.')
            try:
                import IPython
                IPython.embed()
            except ImportError:
                import pdb
                pdb.set_trace()

        if self.news:
            config = SELECTORS['news']
        elif self.videos:
            config = SELECTORS['videos']
        else:
            config = SELECTORS['default']

        div_selector = config['div']
        title_selector = config['title']
        h3_selector = config['h3']

        # cw is short for collapse_whitespace.
        cw = lambda s: re.sub(r'[ \t\n\r]+', ' ', s) if s is not None else s

        index = 0
        for div_g in tree.select_all(div_selector):
            if div_g.select('.hp-xpdbox'):
                # Skip smart cards.
                continue
            try:
                abstract_node = None
                metadata_node = None
                if div_g.select('.st'):
                    # Old class structure
                    h3 = div_g.select('div.r h3')
                    if h3:
                        title = h3.text
                        a = h3.parent
                    else:
                        h3 = div_g.select('h3.r')
                        a = h3.select('a')
                        title = a.text
                        mime = div_g.select('.mime')
                        if mime:
                            title = mime.text + ' ' + title
                    abstract_node = div_g.select('.st')
                    metadata_node = div_g.select('.f')
                else:
                    # Current structure as of October 2020.
                    main_node = div_g.select('div')
                    details_node = main_node.select('div[data-content-feature=1]')
                    if 'jtfYYd' not in main_node.classes:
                        main_node = div_g
                        details_node = main_node.select('div.IsZvec')

                    title_node = div_g.select(title_selector)

                    if title_node and 'yuRUbf' not in title_node.classes:
                        logger.debug('unexpected title node class(es): expected %r, got %r',
                                     'yuRUbf', ' '.join(title_node.classes))
                    if details_node and 'IsZvec' not in details_node.classes:
                        logger.debug('unexpected details node class(es): expected %r, got %r',
                                     'IsZvec', ' '.join(details_node.classes))
                    a = title_node.select('a')
                    h3 = a.select(h3_selector)

                    title = h3.text

                    if self.news:
                        newstitle = title.split('.')

                    if details_node:
                        span_nodes = details_node.select_all('span')
                        abstract_node = span_nodes[-1] if span_nodes else None
                        metadata_node = details_node.select('.f, span ~ div')
                url = unwrap_link(a.attr('href'))
                matched_keywords = []
                abstract = ''
                if abstract_node:
                    abstract_nodes = collections.deque([abstract_node])
                    while abstract_nodes:
                        node = abstract_nodes.popleft()
                        if node:
                            if 'f' in node.classes:
                                # .f is handled as metadata instead.
                                continue
                            if node.tag in ['b', 'em']:
                                matched_keywords.append({'phrase': node.text, 'offset': len(abstract)})
                                abstract += node.text
                                continue
                            if not node.children:
                                abstract += node.text
                                continue
                            for child in node.children:
                                abstract_nodes.append(child)


                if self.news:
                    abstract = abstract + " - " + newstitle[-1]

                metadata = None
                try:
                    metadata_fields = metadata_node.select_all('div > div.wFMWsc')
                    if metadata_fields:
                        metadata = ' | '.join(field.text for field in metadata_fields)
                    elif not metadata_node.select('a') and not metadata_node.select('g-expandable-container'):
                        metadata = metadata_node.text
                    if metadata:
                        metadata = (
                            metadata
                            .replace('\u200e', '')
                            .replace(' - ', ', ')
                            .replace(' \u2014 ', ', ')
                            .strip().rstrip(',')
                        )
                except AttributeError:
                    pass

                if self.news:
                    title = metadata
                    metadata = ""

            except (AttributeError, ValueError):
                continue
            sitelinks = []
            for td in div_g.select_all('td'):
                try:
                    a = td.select('a')
                    sl_title = a.text
                    sl_url = unwrap_link(a.attr('href'))
                    sl_abstract = td.select('div.s.st, div.s .st').text
                    sitelink = Sitelink(cw(sl_title), sl_url, cw(sl_abstract))
                    if sitelink not in sitelinks:
                        sitelinks.append(sitelink)
                except (AttributeError, ValueError):
                    continue
            result = Result(index + 1, cw(title), url, abstract,
                            metadata=cw(metadata), sitelinks=sitelinks, matches=matched_keywords)
            if result not in self.results:
                self.results.append(result)
                index += 1

        if not self.results:
            for card in tree.select_all('g-card'):
                a = card.select('a[href]')
                if not a:
                    continue
                url = unwrap_link(a.attr('href'))
                text_nodes = []
                for node in a.descendants():
                    try:
                        if isinstance(node, TextNode) and node.strip():
                            text_nodes.append(node.text)
                    except NameError:
                        if hasattr(node, 'text') and node.text.strip() and not hasattr(node, 'children'):
                            text_nodes.append(node.text)

                if len(text_nodes) != 4:
                    continue
                publisher, title, abstract, publishing_time = text_nodes
                metadata = '%s, %s' % (publisher, publishing_time)
                index += 1
                self.results.append(Result(index + 1, cw(title), url, cw(abstract), metadata=cw(metadata)))

        spell_orig = tree.select("span.spell_orig")
        if spell_orig:
            showing_results_for_link = next(
                filter(lambda el: el.tag == "a", spell_orig.previous_siblings()), None
            )
            if showing_results_for_link:
                self.autocorrected = True
                self.showing_results_for = showing_results_for_link.text

        alt_query_infobox = tree.select('#topstuff')
        if alt_query_infobox:
            bolds = alt_query_infobox.select_all('div b')
            if len(bolds) == 2:
                self.showing_results_for = bolds[1].text

        self.filtered = tree.select('p#ofr') is not None
