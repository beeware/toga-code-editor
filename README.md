# toga-code-editor

A [Toga](https://toga.beeware.org) widget for editing code, with line numbers and syntax highlighting. `CodeEditor` is a `toga.MultilineTextInput` that colors its text with [Pygments](https://pygments.org) and shows a line-number gutter. It supports macOS, Windows, iOS, Android, and Linux (both GTK and Qt).

## Installation

```console
pip install toga-code-editor
```

## Usage

```python
from toga_code_editor import CodeEditor, language_for_filename

editor = CodeEditor(
    value=source,
    language="python",  # any Pygments lexer alias; None turns highlighting off
    show_line_numbers=True,
    on_change=handle_edit,
    flex=1,
)

# Pick the language from a file name. Unknown files get None, which means no highlighting.
editor.language = language_for_filename(path)
```

`CodeEditor` inherits everything from `toga.MultilineTextInput`, including `value`, `readonly`, `placeholder`, `on_change`, `scroll_to_top`, and `scroll_to_bottom`. It adds three properties:

- `language`: a Pygments lexer alias such as `"python"`, `"rust"`, or `"json"`. Setting an unknown alias raises `ValueError`. `None` disables highlighting. The default is `None`.
- `show_line_numbers`: shows or hides the gutter. Default `True`.
- `theme`: a mapping from `TokenKind` to `Style`. `None` selects the built-in `DEFAULT_THEME`.

Unless you give the widget a font family, it uses a monospace font. Autocorrect, smart quotes, smart dashes, smart insert and delete, auto-capitalization, and spell checking are always off.

### Themes

A theme is a Python mapping between "kinds" of content, and a text style definition. The `DEFAULT_THEME` can be customized:

```python
from toga_code_editor import DEFAULT_THEME, Style, TokenKind

theme = {
    **DEFAULT_THEME,
    TokenKind.COMMENT: Style("#6a737d", italic=True),
    TokenKind.KEYWORD: Style("rebeccapurple", bold=True),
}
editor.theme = theme
```

`Style.color` accepts anything Toga's color properties accept. The token kinds are `KEYWORD`, `BUILTIN`, `DEFINITION`, `DECORATOR`, `STRING`, `NUMBER`, `COMMENT`, `OPERATOR`, `PUNCTUATION`, `TAG`, `ATTRIBUTE`, and `VARIABLE`. Everything else, including plain names, uses a kind of `TEXT`, which is never styled.

## Platform notes

- **macOS** uses an `NSRulerView` for the gutter and the system's adaptive color mapping, so theme colors follow dark mode.
- **Windows** paints the gutter beside a `RichTextBox` and colors text through RichEdit's character formatting, with undo recording suspended while it paints, so Ctrl+Z still undoes typing. Theme colors do not change with the system appearance; WinForms draws the editor light. Tab inserts a tab, and Ctrl+V pastes plain text.
- **Android** 12 and later are supported. The example app is checked on Android 12 and Android 15 emulators.
- **iOS**, **Android**, **GTK**, and **Qt** draw the gutter themselves. Theme colors do not change with the system appearance; the default theme is chosen to be legible on both light and dark backgrounds. On GTK the gutter background follows the theme's styling for text view borders.
- **Linux** needs GTK 3 for the GTK backend; Toga 0.5.7 has no working multiline text input on GTK 4 yet. The Qt backend uses PySide6. Both backends register as the `linux` platform, so an app that installs both must set `TOGA_BACKEND` to `toga_gtk` or `toga_qt`. Both backends were checked on Ubuntu 26.04.
- Highlighting re-lexes the whole buffer after a short pause in typing. Files of a few thousand lines are fine on a desktop; very large files are slower on phones.
- Some third-party Android keyboards ignore the flag that disables suggestions.
- On Android, the widget asks the window to shrink its content when the soft keyboard appears, so the editor scrolls internally and the rest of the layout stays put. It only does this when the app has not chosen a soft-input mode itself. Android deprecated that request in API 30 in favour of handling window insets, so a future release may stop honouring it. With Briefcase's current template, which targets SDK 36 and enables edge-to-edge drawing, the layout still shrinks for the keyboard on Android 12 and Android 15 emulators.

## Developing

```console
uv venv
uv pip install -e . --group dev
.venv/bin/tox -m test
```

On Windows the virtual environment's scripts are in `.venv\Scripts` rather than `.venv/bin`; activate it with `.venv\Scripts\activate` before running `tox` or `briefcase`.

The test suite runs against Toga's dummy backend. Real backends are checked with the example app in `examples/editor`:

```console
cd examples/editor
briefcase dev -a testbed      # macOS, Windows, or Linux (GTK backend)
briefcase dev -a testbed-qt   # Linux (Qt backend)
briefcase run iOS -a testbed  # iOS
```

On macOS, iOS, Windows, and Linux, the example installs the widget straight from this repository; add `-r` after changing the widget source so Briefcase reinstalls it.

On Android the example installs the widget from a wheel in `dist/`, because Gradle rejects a path requirement whose directory contains the Android build tree. Build the wheel from the repository root before each Android run that should pick up widget changes:

```console
uv build --wheel
cd examples/editor
briefcase run android -a testbed -r
```

Every user-visible change needs a fragment in `changes/`, named `<issue>.<kind>.md` where kind is `feature`, `bugfix`, `doc`, or `misc`. Release notes are assembled with `towncrier build`.

## Community

`toga-code-editor` is part of the [BeeWare suite](http://beeware.org). You can talk to the community through:

- [@beeware@fosstodon.org on Mastodon](https://fosstodon.org/@beeware)
- [Discord](https://beeware.org/bee/chat/)

We foster a welcoming and respectful community as described in our [BeeWare Community Code of Conduct](http://beeware.org/community/behavior/).

## Contributing

If you experience problems with the `CodeEditor` widget, [log them on GitHub](https://github.com/beeware/toga-code-editor/issues). If you want to contribute code, please [fork the code](https://github.com/beeware/toga-code-editor) and [submit a pull request](https://github.com/beeware/toga-code-editor/pulls).
