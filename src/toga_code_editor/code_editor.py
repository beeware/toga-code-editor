from __future__ import annotations

import asyncio
from functools import cached_property
from typing import Any

import toga
from toga.fonts import MONOSPACE
from toga.platform import get_factory
from toga.widgets.base import StyleT
from toga.widgets.multilinetextinput import OnChangeHandler

from .highlighting import (
    DEFAULT_THEME,
    Highlighter,
    NullHighlighter,
    PygmentsHighlighter,
    Theme,
)

REHIGHLIGHT_DELAY = 0.15
"""Seconds to wait after the last native edit before re-highlighting."""


class CodeEditor(toga.MultilineTextInput):
    def __init__(
        self,
        id: str | None = None,
        style: StyleT | None = None,
        value: str | None = None,
        readonly: bool = False,
        placeholder: str | None = None,
        on_change: OnChangeHandler | None = None,
        language: str | None = None,
        show_line_numbers: bool = True,
        theme: Theme | None = None,
        **kwargs,
    ):
        """Create a new code editor.

        :param id: The ID for the widget.
        :param style: A style object. If no style is provided, a default style will
            be applied to the widget.
        :param value: The initial content to display in the widget.
        :param readonly: Can the value of the widget be modified by the user?
        :param placeholder: The content to display as a placeholder when there is no
            user content to display.
        :param on_change: A handler that will be invoked when the value of the widget
            changes.
        :param language: A Pygments lexer alias such as ``"python"``, or ``None`` for
            no highlighting.
        :param show_line_numbers: Whether to show the line-number gutter.
        :param theme: A mapping from :class:`TokenKind` to :class:`Style`, or ``None``
            for the default theme.
        :param kwargs: Initial style properties. Unless a font family is given here or
            on ``style``, the editor uses a monospace font.
        """
        if "font_family" not in kwargs and (
            style is None or "font_family" not in style
        ):
            kwargs["font_family"] = MONOSPACE

        # State the inherited value setter needs before super().__init__() runs.
        self._highlighter: Highlighter = NullHighlighter()
        self._language: str | None = None
        self._theme: Theme = DEFAULT_THEME
        self._show_line_numbers = True
        self._pending_rehighlight = None

        super().__init__(
            id=id,
            style=style,
            value=value,
            readonly=readonly,
            placeholder=placeholder,
            on_change=on_change,
            **kwargs,
        )

        self.theme = theme
        self.language = language
        self.show_line_numbers = show_line_numbers

    @cached_property
    def factory(self):
        return get_factory("togax_code_editor")

    def _create(self) -> Any:
        return self.factory.CodeEditor(interface=self)

    @toga.MultilineTextInput.value.setter
    def value(self, value: object) -> None:
        toga.MultilineTextInput.value.fset(self, value)
        self._rehighlight()

    @property
    def language(self) -> str | None:
        """The Pygments lexer alias used for highlighting, or ``None`` for none.

        Setting an alias Pygments does not know raises :exc:`ValueError` and leaves
        the previous language in place.
        """
        return self._language

    @language.setter
    def language(self, value: str | None) -> None:
        highlighter = NullHighlighter() if value is None else PygmentsHighlighter(value)
        self._language = value
        self._highlighter = highlighter
        self._rehighlight()

    @property
    def theme(self) -> Theme:
        """The mapping from token kind to style; ``None`` restores the default."""
        return self._theme

    @theme.setter
    def theme(self, value: Theme | None) -> None:
        self._theme = DEFAULT_THEME if value is None else value
        self._impl.set_theme(self._theme)
        self._rehighlight()

    @property
    def show_line_numbers(self) -> bool:
        """Whether the line-number gutter is shown."""
        return self._show_line_numbers

    @show_line_numbers.setter
    def show_line_numbers(self, value: object) -> None:
        self._show_line_numbers = bool(value)
        self._impl.set_show_line_numbers(self._show_line_numbers)

    def _rehighlight(self) -> None:
        self._cancel_pending_rehighlight()
        self._impl.set_highlights(self._highlighter.highlight(self.value))

    def _schedule_rehighlight(self) -> None:
        """Called by the backend when the user edits the text.

        Re-lexing on every keystroke would be wasteful, so wait for a short pause.
        This is a task rather than a bare ``call_later`` because Toga's Android event
        loop only arms its next wakeup for work scheduled through ``call_soon``; a
        timer added from a native callback would otherwise never fire.
        """
        self._cancel_pending_rehighlight()
        self._pending_rehighlight = toga.App.app.loop.create_task(
            self._rehighlight_after_delay()
        )

    async def _rehighlight_after_delay(self) -> None:
        await asyncio.sleep(REHIGHLIGHT_DELAY)
        self._pending_rehighlight = None
        self._rehighlight()

    def _cancel_pending_rehighlight(self) -> None:
        if self._pending_rehighlight is not None:
            self._pending_rehighlight.cancel()
            self._pending_rehighlight = None
