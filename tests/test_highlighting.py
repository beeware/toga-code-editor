import pytest

from toga_code_editor.highlighting import (
    NullHighlighter,
    PygmentsHighlighter,
    Span,
    TokenKind,
    language_for_filename,
    to_utf16_spans,
    utf16_line_starts,
)


def test_python_snippet():
    """A Python snippet lexes into merged, offset-correct spans; names are dropped."""
    spans = PygmentsHighlighter("python").highlight(
        "def f(x):\n    return x + 1  # hi\n"
    )
    assert spans == [
        Span(0, 3, TokenKind.KEYWORD),
        Span(4, 5, TokenKind.DEFINITION),
        Span(5, 6, TokenKind.PUNCTUATION),
        Span(7, 9, TokenKind.PUNCTUATION),  # ")" and ":" merged into one span
        Span(14, 20, TokenKind.KEYWORD),
        Span(23, 24, TokenKind.OPERATOR),
        Span(25, 26, TokenKind.NUMBER),
        Span(28, 32, TokenKind.COMMENT),
    ]


def test_unknown_language():
    with pytest.raises(ValueError, match="nope"):
        PygmentsHighlighter("nope")


def test_null_highlighter():
    assert NullHighlighter().highlight("def f(): pass") == []


def test_utf16_offsets():
    """An astral character shifts every later UTF-16 offset by one."""
    text = "x = '\U0001f600'  # c\n"
    spans = [Span(4, 7, TokenKind.STRING), Span(9, 12, TokenKind.COMMENT)]
    assert to_utf16_spans(text, spans) == [
        Span(4, 8, TokenKind.STRING),
        Span(10, 13, TokenKind.COMMENT),
    ]
    assert utf16_line_starts("") == [0]
    assert utf16_line_starts("a\n") == [0, 2]
    assert utf16_line_starts("\U0001f600\r\nb") == [0, 4]


@pytest.mark.parametrize(
    "name, expected",
    [("foo.py", "python"), ("Makefile", "make"), ("notes.xyz", None)],
)
def test_language_for_filename(name, expected):
    assert language_for_filename(name) == expected
