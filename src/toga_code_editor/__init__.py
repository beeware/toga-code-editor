from importlib.metadata import version

from .highlighting import DEFAULT_THEME, Span, Style, TokenKind, language_for_filename

__version__ = version("toga-code-editor")

__all__ = [
    "DEFAULT_THEME",
    "Span",
    "Style",
    "TokenKind",
    "__version__",
    "language_for_filename",
]
