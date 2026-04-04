from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional

@dataclass
class Sitelink:
    """Container for a sitelink."""
    title: str
    url: str
    abstract: str
    index: str = ''

@dataclass
class Result:
    """Container for one search result."""
    index: str
    title: str
    url: str
    abstract: str
    metadata: Optional[str] = None
    sitelinks: List[Sitelink] = field(default_factory=list)
    matches: List[Dict[str, Any]] = field(default_factory=list)

    def __post_init__(self):
        self.index = str(self.index)
        self._urltable = {self.index: self.url}
        subindex = 'a'
        for sitelink in self.sitelinks:
            fullindex = self.index + subindex
            sitelink.index = fullindex
            self._urltable[fullindex] = sitelink.url
            subindex = chr(ord(subindex) + 1)

    def jsonizable_object(self):
        """Return a JSON-serializable dict representing the result entry."""
        obj = {
            'title': self.title,
            'url': self.url,
            'abstract': self.abstract
        }
        if self.metadata:
            obj['metadata'] = self.metadata
        if self.sitelinks:
            obj['sitelinks'] = [sitelink.__dict__ for sitelink in self.sitelinks]
        if self.matches:
            obj['matches'] = self.matches
        return obj

    def urltable(self):
        """Return a index-to-URL table for the current result."""
        return self._urltable
