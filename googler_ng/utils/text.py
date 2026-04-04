import textwrap
import unicodedata
from typing import List, Tuple

def monkeypatch_textwrap_for_cjk():
    try:
        if textwrap.wrap.patched:
            return
    except AttributeError:
        pass
    psl_textwrap_wrap = textwrap.wrap

    def textwrap_wrap(text, width=70, **kwargs):
        if width <= 2:
            width = 2
        # We first add a U+0000 after each East Asian Fullwidth or East
        # Asian Wide character, then fill to width - 1 (so that if a NUL
        # character ends up on a new line, we still have one last column
        # to spare for the preceding wide character). Finally we strip
        # all the NUL characters.
        #
        # East Asian Width: https://www.unicode.org/reports/tr11/
        return [
            line.replace('\0', '')
            for line in psl_textwrap_wrap(
                ''.join(
                    ch + '\0' if unicodedata.east_asian_width(ch) in ('F', 'W') else ch
                    for ch in unicodedata.normalize('NFC', text)
                ),
                width=width - 1,
                **kwargs
            )
        ]

    def textwrap_fill(text, width=70, **kwargs):
        return '\n'.join(textwrap_wrap(text, width=width, **kwargs))

    textwrap.wrap = textwrap_wrap
    textwrap.fill = textwrap_fill
    textwrap.wrap.patched = True
    textwrap.fill.patched = True


monkeypatch_textwrap_for_cjk()


CoordinateType = Tuple[int, int]


class TrackedTextwrap:
    """
    Implements a text wrapper that tracks the position of each source
    character, and can correctly insert zero-width sequences at given
    offsets of the source text.

    Wrapping result should be the same as that from PSL textwrap.wrap
    with default settings except expand_tabs=False.
    """

    def __init__(self, text: str, width: int):
        self._original = text

        # Do the job of replace_whitespace first so that we can easily
        # match text to wrapped lines later. Note that this operation
        # does not change text length or offsets.
        whitespace = "\t\n\v\f\r "
        whitespace_trans = str.maketrans(whitespace, " " * len(whitespace))
        text = text.translate(whitespace_trans)

        self._lines = textwrap.wrap(
            text, width, expand_tabs=False, replace_whitespace=False
        )

        # self._coords track the (row, column) coordinate of each source
        # character in the result text. It is indexed by offset in
        # source text.
        self._coords = []  # type: List[CoordinateType]
        offset = 0
        try:
            if not self._lines:
                # Source text only has whitespaces. We add an empty line
                # in order to produce meaningful coordinates.
                self._lines = [""]
            for row, line in enumerate(self._lines):
                assert text[offset : offset + len(line)] == line
                col = 0
                for _ in line:
                    self._coords.append((row, col))
                    offset += 1
                    col += 1
                # All subsequent dropped whitespaces map to the last, imaginary column
                # (the EOL character if you wish) of the current line.
                while offset < len(text) and text[offset] == " ":
                    self._coords.append((row, col))
                    offset += 1
            # One past the final character (think of it as EOF) should
            # be treated as a valid offset.
            self._coords.append((row, col))
        except AssertionError:
            raise RuntimeError(
                "TrackedTextwrap: the impossible happened at offset {} of text {!r}".format(
                    offset, self._original
                )
            )

    # seq should be a zero-width sequence, e.g., an ANSI escape sequence.
    # May raise IndexError if offset is out of bounds.
    def insert_zero_width_sequence(self, seq: str, offset: int) -> None:
        row, col = self._coords[offset]
        line = self._lines[row]
        self._lines[row] = line[:col] + seq + line[col:]

        # Shift coordinates of all characters after the given character
        # on the same line.
        shift = len(seq)
        offset += 1
        while offset < len(self._coords) and self._coords[offset][0] == row:
            _, col = self._coords[offset]
            self._coords[offset] = (row, col + shift)
            offset += 1

    @property
    def original(self) -> str:
        return self._original

    @property
    def lines(self) -> List[str]:
        return self._lines

    @property
    def wrapped(self) -> str:
        return "\n".join(self._lines)

    # May raise IndexError if offset is out of bounds.
    def get_coordinate(self, offset: int) -> CoordinateType:
        return self._coords[offset]
