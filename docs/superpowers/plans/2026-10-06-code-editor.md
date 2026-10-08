# CodeEditor Widget Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build `toga-code-editor`, a standalone Toga widget package providing `CodeEditor`, a multi-line text input with line numbers and Pygments-driven syntax highlighting, on Cocoa, iOS, and Android.

**Architecture:** The interface layer (`code_editor.py`) tokenizes text through Pygments into a flat list of `Span` objects and hands them to a backend through three methods: `set_theme`, `set_highlights`, `set_show_line_numbers`. Each backend module subclasses that Toga backend's `MultilineTextInput` implementation, paints spans onto the native attributed text, and draws a line-number gutter. Backends are discovered through `toga_code_editor.backend.<backend>` entry points, the mechanism Toga provides for third-party widgets.

**Tech Stack:** Python 3.11+, toga-core 0.5.7+, Pygments, toga-dummy for tests, pytest with pytest-asyncio, ruff, tox with tox-uv, Briefcase for the example app.

**Spec:** `docs/superpowers/specs/2026-10-06-code-editor-design.md`

## Global Constraints

- Distribution name `toga-code-editor`, import package `toga_code_editor`, entry-point interface group `toga_code_editor`, widget class `CodeEditor`.
- Runtime dependencies: `toga-core >= 0.5.7` and `pygments`. No Toga backend is a dependency of the package.
- `requires-python = ">= 3.11"`, matching toga-core 0.5.7. License BSD-3-Clause.
- Backends in this cut: Cocoa, iOS, Android, plus Dummy for tests. No other backend gets an entry point.
- The interface, highlighting, and dummy modules must reach 100% coverage. The three platform modules are excluded from coverage because they cannot import on CI.
- Never add `# pragma: no cover` or `# noqa`. Fix the underlying issue.
- `filterwarnings = ["error"]` in pytest: any warning fails the test.
- `REHIGHLIGHT_DELAY` is a module constant of `0.15` seconds in `code_editor.py`.
- Span offsets in the interface are Python `str` indices. Real backends convert to UTF-16 with `to_utf16_spans`. The dummy backend does not convert.
- Markdown files use one line per paragraph. Never hard-wrap prose at 80 columns.
- Keep tests minimal. Test public behavior with the fewest tests that reach coverage. Do not add CI matrices, probe harnesses, or checklists beyond what this plan lists.

## Review Focus

Inputs the spec implies but no automated test exercises. The first two get a single assertion each in Task 2; the rest are checked by hand in the example app, per the project's minimal-testing preference.

1. **Empty document, or text ending in a newline.** The gutter must still number the final empty line. Backends take the `extraLineFragmentRect` path; `utf16_line_starts("")` must return `[0]` and `utf16_line_starts("a\n")` must return `[0, 2]`.
2. **CRLF line endings.** Line numbering counts `\n` only, so CRLF files number one line per `\r\n` and highlight offsets stay aligned.
3. **Typing right after a colored token.** Native typing attributes inherit the color until the debounce fires. Cosmetic, expected; check it settles within a blink.
4. **A file of a few thousand lines.** Whole-buffer re-lexing on every debounce; typing should stay responsive on a laptop. Slower on phones is a documented limitation.
5. **Partial theme.** A theme missing a kind leaves that kind unstyled, never crashes. Check in the example app by switching to a theme with one entry if desired.

---

## File Structure

```text
toga-code-editor/
  pyproject.toml                       # package metadata, entry points, tool config
  tox.ini                              # pre-commit, test, coverage environments
  .pre-commit-config.yaml
  .gitignore
  LICENSE
  README.md
  CHANGELOG.md                         # towncrier target
  changes/                             # towncrier fragments
  .github/workflows/ci.yml
  src/toga_code_editor/
    __init__.py                        # public exports and __version__
    highlighting.py                    # TokenKind, Span, Style, Theme, DEFAULT_THEME, highlighters, offset helpers
    code_editor.py                     # CodeEditor interface widget
    dummy_code_editor.py               # toga_dummy implementation
    cocoa_code_editor.py               # macOS implementation
    iOS_code_editor.py                 # iOS implementation
    android_code_editor.py             # Android implementation
  tests/
    conftest.py
    test_highlighting.py
    test_code_editor.py
  examples/editor/                     # Briefcase app for verifying real backends
    pyproject.toml
    LICENSE
    src/editor/__init__.py
    src/editor/__main__.py
    src/editor/app.py
    src/editor/resources/samples/hello.py
    src/editor/resources/samples/config.json
    src/editor/resources/samples/page.html
```

Each module has one responsibility. `highlighting.py` is pure logic with no Toga widget imports. `code_editor.py` owns widget state and the debounce. Each backend file owns one platform and nothing else.

---

### Task 1: Project scaffold

**Files:**
- Create: `pyproject.toml`, `tox.ini`, `.pre-commit-config.yaml`, `.gitignore`, `LICENSE`, `README.md`
- Create: `src/toga_code_editor/__init__.py`
- Create: `tests/conftest.py`, `tests/test_package.py`

**Interfaces:**
- Consumes: nothing.
- Produces: an installable package named `toga-code-editor` exposing `toga_code_editor.__version__`, with all four backend entry points declared (the modules they point at arrive in later tasks; entry points load lazily so that is safe), a `tests/conftest.py` providing an async `app` fixture, and the command `.venv/bin/pytest` running green.

- [ ] **Step 1: Write `pyproject.toml`**

```toml
[build-system]
requires = ["setuptools >= 77"]
build-backend = "setuptools.build_meta"

[project]
name = "toga-code-editor"
version = "0.1.0.dev0"
description = "A Toga widget for editing code, with line numbers and syntax highlighting."
readme = "README.md"
requires-python = ">= 3.11"
license = "BSD-3-Clause"
license-files = ["LICENSE"]
authors = [{name = "Kattni", email = "hello@kattni.com"}]
keywords = ["gui", "widget", "toga", "code", "editor", "syntax-highlighting"]
classifiers = [
    "Development Status :: 3 - Alpha",
    "Intended Audience :: Developers",
    "Programming Language :: Python :: 3",
    "Programming Language :: Python :: 3 :: Only",
    "Topic :: Software Development :: User Interfaces",
    "Topic :: Software Development :: Widget Sets",
]
dependencies = [
    "toga-core >= 0.5.7",
    "pygments >= 2.19",
]

[project.entry-points."toga_code_editor.backend.toga_dummy"]
CodeEditor = "toga_code_editor.dummy_code_editor:CodeEditor"

[project.entry-points."toga_code_editor.backend.toga_cocoa"]
CodeEditor = "toga_code_editor.cocoa_code_editor:CodeEditor"

[project.entry-points."toga_code_editor.backend.toga_iOS"]
CodeEditor = "toga_code_editor.iOS_code_editor:CodeEditor"

[project.entry-points."toga_code_editor.backend.toga_android"]
CodeEditor = "toga_code_editor.android_code_editor:CodeEditor"

[dependency-groups]
test = [
    "coverage[toml]",
    "pytest",
    "pytest-asyncio",
    "toga-dummy >= 0.5.7",
]
dev = [
    {include-group = "test"},
    "briefcase",
    "pre-commit",
    "tox",
    "tox-uv",
    "towncrier",
]

[tool.setuptools.packages.find]
where = ["src"]

[tool.ruff.lint]
extend-select = ["E", "W", "F", "UP", "B", "ASYNC", "C4", "I"]

[tool.ruff.lint.isort]
combine-as-imports = true
known-first-party = ["toga_code_editor"]

[tool.codespell]
skip = ".git,.venv,.tox,*.lock"

[tool.coverage.run]
parallel = true
branch = true
relative_files = true
source_pkgs = ["toga_code_editor"]
omit = [
    "*/toga_code_editor/cocoa_code_editor.py",
    "*/toga_code_editor/iOS_code_editor.py",
    "*/toga_code_editor/android_code_editor.py",
]

[tool.coverage.paths]
source = ["src/toga_code_editor", "**/toga_code_editor"]

[tool.coverage.report]
fail_under = 100
show_missing = true

[tool.pytest.ini_options]
asyncio_mode = "auto"
asyncio_default_fixture_loop_scope = "function"
filterwarnings = ["error"]
testpaths = ["tests"]

[tool.towncrier]
directory = "changes"
package = "toga_code_editor"
package_dir = "src"
filename = "CHANGELOG.md"
start_string = "<!-- towncrier release notes start -->\n"
title_format = "## {version} ({project_date})"
underlines = ["", "", ""]

[[tool.towncrier.type]]
directory = "feature"
name = "Features"
showcontent = true

[[tool.towncrier.type]]
directory = "bugfix"
name = "Bugfixes"
showcontent = true

[[tool.towncrier.type]]
directory = "doc"
name = "Documentation"
showcontent = true

[[tool.towncrier.type]]
directory = "misc"
name = "Misc"
showcontent = false
```

- [ ] **Step 2: Write `tox.ini`**

```ini
[tox]
envlist = pre-commit,py{311,312,313,314,315}-cov,coverage
labels =
    test = py-cov,coverage
skip_missing_interpreters = True

[testenv:pre-commit]
skip_install = True
deps = pre-commit
commands = pre-commit run --all-files --show-diff-on-failure --color=always

# The leading comma generates the "py" environment.
[testenv:py{,311,312,313,314,315}{,-cov}]
depends = pre-commit
package = editable
setenv =
    TOGA_BACKEND = toga_dummy
dependency_groups = test
commands =
    !cov: python -X warn_default_encoding -m pytest {posargs:-vv --color yes}
    cov: python -X warn_default_encoding -m coverage run -m pytest {posargs:-vv --color yes}

[testenv:coverage]
depends = py{,311,312,313,314,315}-cov
skip_install = True
dependency_groups = test
commands =
    python -m coverage combine
    python -m coverage report
```

- [ ] **Step 3: Write `.pre-commit-config.yaml`, `.gitignore`, `LICENSE`, and a README stub**

`.pre-commit-config.yaml`:

```yaml
repos:
  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v6.0.0
    hooks:
      - id: check-toml
      - id: check-yaml
      - id: end-of-file-fixer
      - id: trailing-whitespace
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.16.8
    hooks:
      - id: ruff-check
        args: [--fix]
      - id: ruff-format
  - repo: https://github.com/codespell-project/codespell
    rev: v2.4.1
    hooks:
      - id: codespell
```

`.gitignore`:

```text
.venv/
__pycache__/
*.py[cod]
*.egg-info/
build/
dist/
.coverage
.coverage.*
htmlcov/
.pytest_cache/
.ruff_cache/
.tox/
examples/editor/build/
examples/editor/logs/
.DS_Store
```

`LICENSE`:

```text
BSD 3-Clause License

Copyright (c) 2026, Kattni
All rights reserved.

Redistribution and use in source and binary forms, with or without
modification, are permitted provided that the following conditions are met:

1. Redistributions of source code must retain the above copyright notice, this
   list of conditions and the following disclaimer.

2. Redistributions in binary form must reproduce the above copyright notice,
   this list of conditions and the following disclaimer in the documentation
   and/or other materials provided with the distribution.

3. Neither the name of the copyright holder nor the names of its
   contributors may be used to endorse or promote products derived from
   this software without specific prior written permission.

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE
FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY,
OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
```

`README.md` (the full README is Task 7):

```markdown
# toga-code-editor

A [Toga](https://toga.beeware.org) widget for editing code, with line numbers and syntax highlighting. Supports macOS, iOS, and Android.
```

- [ ] **Step 4: Write the package `__init__.py` and the test fixtures**

`src/toga_code_editor/__init__.py`:

```python
from importlib.metadata import version

__version__ = version("toga-code-editor")

__all__ = ["__version__"]
```

`tests/conftest.py`:

```python
import os

import pytest
import toga
from toga_dummy.utils import EventLog


def pytest_configure(config):
    # Run against the dummy backend even when a real backend is installed in the venv
    # (for example after running the example app with Briefcase).
    os.environ.setdefault("TOGA_BACKEND", "toga_dummy")


@pytest.fixture(autouse=True)
def reset_event_log():
    EventLog.reset()


@pytest.fixture
async def app(tmp_path, monkeypatch):
    # Keep any paths the dummy backend generates inside the test's temp directory.
    monkeypatch.setenv("TOGA_DUMMY_HOME", str(tmp_path / "toga-dummy"))
    # The fixture is async so the app's event loop is the running pytest-asyncio loop.
    return toga.App(formal_name="Test App", app_id="org.beeware.toga_code_editor.test")
```

`tests/test_package.py`:

```python
import toga_code_editor


def test_version():
    assert toga_code_editor.__version__ == "0.1.0.dev0"
```

- [ ] **Step 5: Create the environment and run the test**

Run:

```bash
cd /Users/kattni/BeeWare/toga-code-editor && uv venv && uv pip install -e . --group dev && .venv/bin/pytest -v
```

Expected: `1 passed`.

- [ ] **Step 6: Pin pre-commit hook versions and run them**

Run:

```bash
cd /Users/kattni/BeeWare/toga-code-editor && .venv/bin/pre-commit autoupdate && .venv/bin/pre-commit run --all-files
```

Expected: every hook reports `Passed` (or `Skipped` for hooks with no matching files). If `ruff-format` rewrites a file, run it again until clean.

- [ ] **Step 7: Commit**

```bash
git add pyproject.toml tox.ini .pre-commit-config.yaml .gitignore LICENSE README.md src tests
git commit -m "Scaffold the toga-code-editor package"
```

---

### Task 2: Highlighting pipeline

**Files:**
- Create: `src/toga_code_editor/highlighting.py`
- Modify: `src/toga_code_editor/__init__.py`
- Test: `tests/test_highlighting.py`

**Interfaces:**
- Consumes: nothing from earlier tasks.
- Produces, all in `toga_code_editor.highlighting`:
  - `class TokenKind(StrEnum)` with members `TEXT, KEYWORD, BUILTIN, DEFINITION, DECORATOR, STRING, NUMBER, COMMENT, OPERATOR, PUNCTUATION, TAG, ATTRIBUTE, VARIABLE`.
  - `Span(start: int, end: int, kind: TokenKind)`, frozen dataclass.
  - `Style(color: Color | str, bold: bool = False, italic: bool = False)`, frozen dataclass; `color` is normalized to a `toga.colors.Color` on construction.
  - `Theme = Mapping[TokenKind, Style]` and `DEFAULT_THEME: Theme`.
  - `class Highlighter(Protocol)` with `highlight(self, text: str) -> list[Span]`.
  - `NullHighlighter()` returning `[]`; `PygmentsHighlighter(language: str)` raising `ValueError` for an unknown alias.
  - `language_for_filename(path) -> str | None`.
  - `to_utf16_spans(text: str, spans: list[Span]) -> list[Span]`.
  - `utf16_line_starts(text: str) -> list[int]`, the UTF-16 offset of the first character of each logical line, always starting with `0`.

- [ ] **Step 1: Write the failing tests**

`tests/test_highlighting.py`:

```python
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
    """A Python snippet lexes into merged, offset-correct spans; plain names are dropped."""
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
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `.venv/bin/pytest tests/test_highlighting.py -v`

Expected: FAIL at collection with `ModuleNotFoundError: No module named 'toga_code_editor.highlighting'`.

- [ ] **Step 3: Write `highlighting.py`**

```python
from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from enum import StrEnum
from os import PathLike
from typing import Protocol

from pygments.lexers import find_lexer_class_for_filename, get_lexer_by_name
from pygments.token import (
    Comment,
    Keyword,
    Name,
    Number,
    Operator,
    Punctuation,
    String,
)
from pygments.util import ClassNotFound
from toga.colors import Color


class TokenKind(StrEnum):
    """The flat vocabulary of token kinds a theme can style."""

    TEXT = "text"
    KEYWORD = "keyword"
    BUILTIN = "builtin"
    DEFINITION = "definition"
    DECORATOR = "decorator"
    STRING = "string"
    NUMBER = "number"
    COMMENT = "comment"
    OPERATOR = "operator"
    PUNCTUATION = "punctuation"
    TAG = "tag"
    ATTRIBUTE = "attribute"
    VARIABLE = "variable"


@dataclass(frozen=True)
class Span:
    """A run of text with one token kind.

    Offsets are Python string indices: ``start`` inclusive, ``end`` exclusive.
    """

    start: int
    end: int
    kind: TokenKind


@dataclass(frozen=True)
class Style:
    """How a token kind is drawn. ``color`` accepts anything Toga's color properties accept."""

    color: Color | str
    bold: bool = False
    italic: bool = False

    def __post_init__(self):
        object.__setattr__(self, "color", Color.parse(self.color))


Theme = Mapping[TokenKind, Style]
"""A mapping from token kind to style. Kinds absent from the theme are left unstyled."""

DEFAULT_THEME: Theme = {
    TokenKind.KEYWORD: Style("#a626a4"),
    TokenKind.BUILTIN: Style("#0184bc"),
    TokenKind.DEFINITION: Style("#4078f2", bold=True),
    TokenKind.DECORATOR: Style("#986801"),
    TokenKind.STRING: Style("#50a14f"),
    TokenKind.NUMBER: Style("#986801"),
    TokenKind.COMMENT: Style("#8a8a8a", italic=True),
    TokenKind.TAG: Style("#e45649"),
    TokenKind.ATTRIBUTE: Style("#986801"),
    TokenKind.VARIABLE: Style("#e45649"),
}

# Ordered most-specific first. The first row whose Pygments type contains the token
# wins, so Operator.Word must precede Operator, and the Name.* rows precede nothing
# more general because bare Name falls through to TEXT.
_TOKEN_TABLE = [
    (Comment, TokenKind.COMMENT),
    (String, TokenKind.STRING),
    (Number, TokenKind.NUMBER),
    (Keyword, TokenKind.KEYWORD),
    (Operator.Word, TokenKind.KEYWORD),
    (Operator, TokenKind.OPERATOR),
    (Punctuation, TokenKind.PUNCTUATION),
    (Name.Builtin, TokenKind.BUILTIN),
    (Name.Function, TokenKind.DEFINITION),
    (Name.Class, TokenKind.DEFINITION),
    (Name.Decorator, TokenKind.DECORATOR),
    (Name.Tag, TokenKind.TAG),
    (Name.Attribute, TokenKind.ATTRIBUTE),
    (Name.Variable, TokenKind.VARIABLE),
]


def token_kind(token_type) -> TokenKind:
    """Map a Pygments token type onto the flat vocabulary."""
    for pygments_type, kind in _TOKEN_TABLE:
        if token_type in pygments_type:
            return kind
    return TokenKind.TEXT


def merge_spans(spans: Iterable[Span]) -> list[Span]:
    """Drop TEXT spans and merge adjacent spans of the same kind."""
    merged: list[Span] = []
    for span in spans:
        if span.kind is TokenKind.TEXT:
            continue
        if merged and merged[-1].kind is span.kind and merged[-1].end == span.start:
            merged[-1] = Span(merged[-1].start, span.end, span.kind)
        else:
            merged.append(span)
    return merged


class Highlighter(Protocol):
    def highlight(self, text: str) -> list[Span]: ...


class NullHighlighter:
    """The highlighter used when no language is set."""

    def highlight(self, text: str) -> list[Span]:
        return []


class PygmentsHighlighter:
    """Tokenize text with a Pygments lexer.

    :param language: A Pygments lexer alias, such as ``"python"``.
    :raises ValueError: If Pygments has no lexer for the alias.
    """

    def __init__(self, language: str):
        try:
            # Pygments trims and appends newlines by default, which shifts every
            # offset. Turn all of that off.
            self.lexer = get_lexer_by_name(
                language, stripnl=False, stripall=False, ensurenl=False
            )
        except ClassNotFound:
            raise ValueError(f"Unknown language {language!r}") from None

    def highlight(self, text: str) -> list[Span]:
        return merge_spans(
            Span(index, index + len(value), token_kind(token_type))
            for index, token_type, value in self.lexer.get_tokens_unprocessed(text)
        )


def language_for_filename(path: str | PathLike) -> str | None:
    """Return the Pygments lexer alias for a filename, or ``None`` if there is none.

    The whole filename is matched, so names such as ``Makefile`` resolve.
    """
    lexer_class = find_lexer_class_for_filename(str(path))
    return None if lexer_class is None else lexer_class.aliases[0]


def to_utf16_spans(text: str, spans: list[Span]) -> list[Span]:
    """Convert span offsets from code points to UTF-16 code units.

    Native text views on macOS, iOS, and Android index by UTF-16 code unit, so every
    character outside the Basic Multilingual Plane shifts later offsets by one. Spans
    must be in document order, which is how the highlighters produce them.
    """
    converted = []
    scanned = 0  # code-point index already accounted for
    extra = 0  # extra UTF-16 units contributed by astral characters before `scanned`

    def utf16(index: int) -> int:
        nonlocal scanned, extra
        extra += sum(1 for ch in text[scanned:index] if ord(ch) > 0xFFFF)
        scanned = index
        return index + extra

    for span in spans:
        start = utf16(span.start)
        end = utf16(span.end)
        converted.append(Span(start, end, span.kind))
    return converted


def utf16_line_starts(text: str) -> list[int]:
    """Return the UTF-16 offset of the first character of each logical line."""
    starts = [0]
    offset = 0
    for ch in text:
        offset += 2 if ord(ch) > 0xFFFF else 1
        if ch == "\n":
            starts.append(offset)
    return starts
```

- [ ] **Step 4: Export the public names**

Replace `src/toga_code_editor/__init__.py` with:

```python
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
```

- [ ] **Step 5: Run the tests and coverage**

Run: `.venv/bin/coverage run -m pytest -v && .venv/bin/coverage combine && .venv/bin/coverage report`

Expected: all 8 items pass (the five highlighting tests, one of them parametrized three ways, plus the version test), and the report shows `highlighting.py` at 100% with the total at or above `fail_under`. If `report` fails on `__init__.py` or `conftest`, the missing lines point at code with no test; add the smallest assertion that reaches them rather than a new test.

- [ ] **Step 6: Commit**

```bash
git add src/toga_code_editor/highlighting.py src/toga_code_editor/__init__.py tests/test_highlighting.py
git commit -m "Add the highlighting pipeline"
```

---

### Task 3: The `CodeEditor` interface and the dummy backend

**Files:**
- Create: `src/toga_code_editor/code_editor.py`
- Create: `src/toga_code_editor/dummy_code_editor.py`
- Modify: `src/toga_code_editor/__init__.py`
- Test: `tests/test_code_editor.py`

**Interfaces:**
- Consumes: everything listed under Task 2's "Produces".
- Produces:
  - `toga_code_editor.CodeEditor(id=None, style=None, value=None, readonly=False, placeholder=None, on_change=None, language=None, show_line_numbers=True, theme=None, **kwargs)`, a subclass of `toga.MultilineTextInput` with properties `language: str | None`, `show_line_numbers: bool`, `theme: Theme`, and an internal hook `_schedule_rehighlight() -> None` that backends call from their native change callback before `on_change()`.
  - `toga_code_editor.code_editor.REHIGHLIGHT_DELAY = 0.15`.
  - The backend contract every implementation in Tasks 4 to 6 must satisfy, on top of its backend's `MultilineTextInput`: `set_theme(theme: Theme)`, `set_highlights(spans: list[Span])`, `set_show_line_numbers(value: bool)`.

- [ ] **Step 1: Write the failing tests**

`tests/test_code_editor.py`:

```python
import asyncio

import pytest
from toga.fonts import MONOSPACE, SERIF
from toga.style import Pack
from toga_dummy.utils import assert_action_performed, attribute_value

from toga_code_editor import DEFAULT_THEME, CodeEditor, Span, Style, TokenKind
from toga_code_editor.code_editor import REHIGHLIGHT_DELAY

X_EQUALS_ONE = [Span(2, 3, TokenKind.OPERATOR), Span(4, 5, TokenKind.NUMBER)]


def test_defaults(app):
    editor = CodeEditor()

    assert_action_performed(editor, "create CodeEditor")
    assert editor.language is None
    assert editor.theme is DEFAULT_THEME
    assert editor.show_line_numbers
    assert editor.style.font_family == [MONOSPACE]
    assert attribute_value(editor, "highlights") == []
    assert attribute_value(editor, "theme") is DEFAULT_THEME
    assert attribute_value(editor, "show_line_numbers") is True


@pytest.mark.parametrize(
    "kwargs, expected",
    [
        ({"font_family": SERIF}, [SERIF]),
        ({"style": Pack(font_family=SERIF)}, [SERIF]),
        ({"style": Pack(flex=1)}, [MONOSPACE]),
    ],
)
def test_font_family(app, kwargs, expected):
    """Monospace is the default unless the caller chose a font family."""
    assert CodeEditor(**kwargs).style.font_family == expected


def test_language(app):
    editor = CodeEditor(value="x = 1")

    editor.language = "python"
    assert editor.language == "python"
    assert attribute_value(editor, "highlights") == X_EQUALS_ONE

    with pytest.raises(ValueError, match="nope"):
        editor.language = "nope"
    assert editor.language == "python"

    editor.language = None
    assert attribute_value(editor, "highlights") == []


def test_theme_and_line_numbers(app):
    editor = CodeEditor(value="x = 1", language="python")

    theme = {TokenKind.NUMBER: Style("red")}
    editor.theme = theme
    assert editor.theme is theme
    assert attribute_value(editor, "theme") is theme

    editor.theme = None
    assert editor.theme is DEFAULT_THEME

    editor.show_line_numbers = False
    assert not editor.show_line_numbers
    assert attribute_value(editor, "show_line_numbers") is False


def test_value_rehighlights(app):
    editor = CodeEditor(language="python")
    editor.value = "x = 1"
    assert attribute_value(editor, "highlights") == X_EQUALS_ONE


async def test_native_change_debounces(app):
    changes = []
    editor = CodeEditor(
        language="python",
        on_change=lambda widget, **kwargs: changes.append(widget.value),
    )

    # Simulate typing: the native value changes without going through the interface,
    # then the backend's change callback fires, twice in quick succession.
    editor._impl._set_value("value", "x = 1")
    editor._impl.simulate_change()
    editor._impl.simulate_change()

    assert changes == ["x = 1", "x = 1"]
    assert attribute_value(editor, "highlights") == []

    await asyncio.sleep(REHIGHLIGHT_DELAY * 2)
    assert attribute_value(editor, "highlights") == X_EQUALS_ONE
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `.venv/bin/pytest tests/test_code_editor.py -v`

Expected: FAIL at collection with `ImportError: cannot import name 'CodeEditor' from 'toga_code_editor'`.

- [ ] **Step 3: Write the dummy backend**

`src/toga_code_editor/dummy_code_editor.py`:

```python
from toga_dummy.widgets.multilinetextinput import MultilineTextInput


class CodeEditor(MultilineTextInput):
    def create(self):
        self._action("create CodeEditor")

    def set_theme(self, theme):
        self._set_value("theme", theme)

    def set_highlights(self, spans):
        self._set_value("highlights", spans)

    def set_show_line_numbers(self, value):
        self._set_value("show_line_numbers", value)

    def simulate_change(self):
        # Mirror the real backends: the re-highlight is scheduled before the
        # user's handler runs.
        self.interface._schedule_rehighlight()
        self.interface.on_change()
```

- [ ] **Step 4: Write the interface**

`src/toga_code_editor/code_editor.py`:

```python
from __future__ import annotations

from functools import cached_property
from typing import Any

import toga
from toga.fonts import MONOSPACE, SYSTEM
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
            style is None or style.font_family == [SYSTEM]
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
        return get_factory("toga_code_editor")

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
        """The mapping from token kind to style. Assigning ``None`` restores the default."""
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
        """
        self._cancel_pending_rehighlight()
        self._pending_rehighlight = toga.App.app.loop.call_later(
            REHIGHLIGHT_DELAY, self._rehighlight
        )

    def _cancel_pending_rehighlight(self) -> None:
        if self._pending_rehighlight is not None:
            self._pending_rehighlight.cancel()
            self._pending_rehighlight = None
```

- [ ] **Step 5: Export `CodeEditor`**

Replace `src/toga_code_editor/__init__.py` with:

```python
from importlib.metadata import version

from .code_editor import CodeEditor
from .highlighting import DEFAULT_THEME, Span, Style, TokenKind, language_for_filename

__version__ = version("toga-code-editor")

__all__ = [
    "DEFAULT_THEME",
    "CodeEditor",
    "Span",
    "Style",
    "TokenKind",
    "__version__",
    "language_for_filename",
]
```

- [ ] **Step 6: Run the full suite with coverage**

Run: `.venv/bin/coverage run -m pytest -v && .venv/bin/coverage combine && .venv/bin/coverage report`

Expected: all tests pass and the report ends without a `fail_under` error. The entry point is read from the installed metadata, so if `test_defaults` fails with `NotImplementedError: The 'toga_dummy' backend for the toga_code_editor interface doesn't implement CodeEditor`, re-run `uv pip install -e . --group dev` to refresh the metadata and run again.

- [ ] **Step 7: Run pre-commit and commit**

```bash
.venv/bin/pre-commit run --all-files
git add src/toga_code_editor tests/test_code_editor.py
git commit -m "Add the CodeEditor interface and dummy backend"
```

---

### Task 4: Cocoa backend and the example app

The example app is the only way to verify a real backend, so it is built in this task alongside the Cocoa module. There are no automated tests for platform modules; the deliverable is the example app running on macOS with highlighting and a gutter.

**Files:**
- Create: `src/toga_code_editor/cocoa_code_editor.py`
- Create: `examples/editor/pyproject.toml`, `examples/editor/LICENSE`
- Create: `examples/editor/src/editor/__init__.py`, `__main__.py`, `app.py`
- Create: `examples/editor/src/editor/resources/samples/hello.py`, `config.json`, `page.html`

**Interfaces:**
- Consumes: the backend contract from Task 3 (`set_theme`, `set_highlights`, `set_show_line_numbers`, and calling `interface._schedule_rehighlight()` before `interface.on_change()`); `to_utf16_spans` and `utf16_line_starts` from Task 2.
- Produces: `toga_code_editor.cocoa_code_editor.CodeEditor`, and a Briefcase app at `examples/editor` that Tasks 5 and 6 reuse unchanged.

Toga internals this module subclasses, from toga-cocoa 0.5.7: `toga_cocoa.widgets.multilinetextinput.MultilineTextInput` (attributes `native`, the `NSScrollView`, and `native_text`, the `NSTextView`) and `TogaTextView`, which carries `interface` and `impl` properties and implements `textDidChange_`.

- [ ] **Step 1: Write `cocoa_code_editor.py`**

```python
from bisect import bisect_right

from rubicon.objc import (
    SEL,
    NSPoint,
    NSRange,
    NSRect,
    ObjCClass,
    objc_method,
    objc_property,
)
from toga_cocoa.colors import native_color
from toga_cocoa.libs import (
    NSAttributedString,
    NSBezelBorder,
    NSColor,
    NSFontAttributeName,
    NSFontManager,
    NSForegroundColorAttributeName,
    NSMutableDictionary,
    NSNotificationCenter,
    NSScrollView,
    NSViewBoundsDidChangeNotification,
    NSViewHeightSizable,
    NSViewWidthSizable,
)
from toga_cocoa.widgets.multilinetextinput import MultilineTextInput, TogaTextView

from .highlighting import to_utf16_spans, utf16_line_starts

NSRulerView = ObjCClass("NSRulerView")

# NSRulerOrientation
NSVerticalRuler = 1
# NSFontTraitMask
NSItalicFontMask = 1 << 0
NSBoldFontMask = 1 << 1

GUTTER_PADDING = 6


class TogaCodeTextView(TogaTextView):
    @objc_method
    def textDidChange_(self, notification) -> None:
        self.interface._schedule_rehighlight()
        self.interface.on_change()
        self.impl.text_changed()


class TogaLineNumberView(NSRulerView):
    impl = objc_property(object, weak=True)

    @objc_method
    def boundsDidChange_(self, notification) -> None:
        # The text scrolled; the visible line numbers changed with it.
        self.setNeedsDisplay(True)

    @objc_method
    def drawHashMarksAndLabelsInRect_(self, rect: NSRect) -> None:
        self.impl.draw_line_numbers()


class CodeEditor(MultilineTextInput):
    def create(self):
        # Mirrors toga_cocoa's MultilineTextInput.create(), swapping in
        # TogaCodeTextView, turning off prose features, and adding a ruler.
        self.native = NSScrollView.alloc().init()
        self.native.hasVerticalScroller = True
        self.native.hasHorizontalScroller = False
        self.native.autohidesScrollers = False
        self.native.borderType = NSBezelBorder

        self.native_text = TogaCodeTextView.alloc().init()
        self.native_text.interface = self.interface
        self.native_text.impl = self
        self.native_text.delegate = self.native_text

        self.native_text.editable = True
        self.native_text.selectable = True
        self.native_text.allowsUndo = True
        self.native_text.verticallyResizable = True
        self.native_text.horizontallyResizable = False
        self.native_text.usesAdaptiveColorMappingForDarkAppearance = True
        self.native_text.setAutomaticQuoteSubstitutionEnabled(False)
        self.native_text.setAutomaticDashSubstitutionEnabled(False)
        # Code is not prose.
        self.native_text.setContinuousSpellCheckingEnabled(False)
        self.native_text.setGrammarCheckingEnabled(False)
        self.native_text.setAutomaticSpellingCorrectionEnabled(False)
        self.native_text.setAutomaticTextReplacementEnabled(False)
        self.native_text.setAutomaticTextCompletionEnabled(False)

        self.native_text.autoresizingMask = NSViewWidthSizable | NSViewHeightSizable
        self.native.documentView = self.native_text

        # Reading layoutManager opts the view into TextKit 1, which is what the
        # gutter's line-fragment queries need. Do it once, up front.
        self.layout_manager = self.native_text.layoutManager

        self.ruler = TogaLineNumberView.alloc().initWithScrollView(
            self.native, orientation=NSVerticalRuler
        )
        self.ruler.impl = self
        self.ruler.clientView = self.native_text
        self.ruler.reservedThicknessForMarkers = 0
        self.ruler.reservedThicknessForAccessoryView = 0
        self.native.hasVerticalRuler = True
        self.native.verticalRulerView = self.ruler
        self.native.rulersVisible = True

        # Redraw the gutter whenever the clip view scrolls.
        self.native.contentView.postsBoundsChangedNotifications = True
        NSNotificationCenter.defaultCenter.addObserver(
            self.ruler,
            selector=SEL("boundsDidChange:"),
            name=NSViewBoundsDidChangeNotification,
            object=self.native.contentView,
        )

        self.theme = {}
        self.attributes = {}
        self.spans = []
        self.line_starts = [0]

        self.add_constraints()

    # Inherited MultilineTextInput methods that must keep the gutter and colors in sync

    def set_value(self, value):
        super().set_value(value)
        self.text_changed()

    def set_font(self, font):
        super().set_font(font)
        self.rebuild_attributes()
        self.apply_highlights()
        self.text_changed()

    def set_color(self, value):
        super().set_color(value)
        self.apply_highlights()

    # CodeEditor backend contract

    def set_theme(self, theme):
        self.theme = theme
        self.rebuild_attributes()

    def set_highlights(self, spans):
        self.spans = spans
        self.apply_highlights()

    def set_show_line_numbers(self, value):
        self.native.rulersVisible = value

    # Highlighting

    def rebuild_attributes(self):
        base_font = self.native_text.font
        manager = NSFontManager.sharedFontManager
        self.attributes = {}
        for kind, style in self.theme.items():
            attributes = NSMutableDictionary.alloc().init()
            attributes[NSForegroundColorAttributeName] = native_color(style.color)
            traits = 0
            if style.bold:
                traits |= NSBoldFontMask
            if style.italic:
                traits |= NSItalicFontMask
            if traits:
                attributes[NSFontAttributeName] = manager.convertFont(
                    base_font, toHaveTrait=traits
                )
            self.attributes[kind] = attributes

    def apply_highlights(self):
        storage = self.native_text.textStorage
        full_range = NSRange(0, storage.length)
        storage.beginEditing()
        # Reset to the base font and color, then paint each span.
        storage.addAttribute(
            NSFontAttributeName, value=self.native_text.font, range=full_range
        )
        storage.addAttribute(
            NSForegroundColorAttributeName,
            value=self.native_text.textColor,
            range=full_range,
        )
        for span in to_utf16_spans(self.get_value(), self.spans):
            attributes = self.attributes.get(span.kind)
            if attributes is not None:
                storage.addAttributes(
                    attributes, range=NSRange(span.start, span.end - span.start)
                )
        storage.endEditing()

    # Gutter

    def text_changed(self):
        self.line_starts = utf16_line_starts(self.get_value())
        digits = len(str(len(self.line_starts)))
        label = self.gutter_label("0" * digits)
        thickness = label.size().width + 2 * GUTTER_PADDING
        if self.ruler.ruleThickness != thickness:
            self.ruler.ruleThickness = thickness
        self.ruler.setNeedsDisplay(True)

    def gutter_label(self, text):
        attributes = NSMutableDictionary.alloc().init()
        attributes[NSFontAttributeName] = self.native_text.font
        attributes[NSForegroundColorAttributeName] = NSColor.secondaryLabelColor
        return NSAttributedString.alloc().initWithString(text, attributes=attributes)

    def draw_line_numbers(self):
        layout = self.layout_manager
        container = self.native_text.textContainer
        visible = self.native_text.visibleRect
        inset = self.native_text.textContainerInset
        text_length = self.native_text.textStorage.length

        glyph_range = layout.glyphRangeForBoundingRect(
            visible, inTextContainer=container
        )
        char_range = layout.characterRangeForGlyphRange(
            glyph_range, actualGlyphRange=None
        )
        first_line = max(bisect_right(self.line_starts, char_range.location) - 1, 0)
        last_char = char_range.location + char_range.length
        thickness = self.ruler.ruleThickness

        for number, start in enumerate(
            self.line_starts[first_line:], start=first_line + 1
        ):
            if start > last_char:
                break
            if start == text_length:
                # The empty line after a trailing newline, or an empty document.
                fragment = layout.extraLineFragmentRect
            else:
                glyph = layout.glyphIndexForCharacterAtIndex(start)
                fragment = layout.lineFragmentRectForGlyphAtIndex(
                    glyph, effectiveRange=None
                )
            label = self.gutter_label(str(number))
            x = thickness - GUTTER_PADDING - label.size().width
            y = fragment.origin.y - visible.origin.y + inset.height
            label.drawAtPoint(NSPoint(x, y))
```

- [ ] **Step 2: Write the example app's Briefcase config**

`examples/editor/pyproject.toml`:

```toml
[build-system]
requires = ["briefcase"]

[project]
name = "editor"
version = "0.0.1"

[tool.briefcase]
project_name = "Editor"
bundle = "org.beeware.toga_code_editor.examples"
version = "0.0.1"
url = "https://beeware.org"
license = "BSD-3-Clause"
license-files = ["LICENSE"]
author = "Kattni"
author_email = "hello@kattni.com"
description = "A code editor demonstrating the toga-code-editor widget."
requires = [
    "../..",
]

[tool.briefcase.app.editor]
formal_name = "Editor"
sources = ["src/editor"]

[tool.briefcase.app.editor.macOS]
requires = [
    "toga-cocoa ~= 0.5.7",
    "std-nslog >= 1.0.0",
]

[tool.briefcase.app.editor.iOS]
requires = [
    "toga-iOS ~= 0.5.7",
    "std-nslog >= 1.0.0",
]

[tool.briefcase.app.editor.android]
requires = [
    "toga-android ~= 0.5.7",
]
base_theme = "Theme.MaterialComponents.Light.DarkActionBar"
build_gradle_dependencies = [
    "com.google.android.material:material:1.12.0",
]
```

Copy the license: `cp LICENSE examples/editor/LICENSE`.

- [ ] **Step 3: Write the example app**

`examples/editor/src/editor/__init__.py` is empty.

`examples/editor/src/editor/__main__.py`:

```python
from editor.app import main

if __name__ == "__main__":
    main().main_loop()
```

`examples/editor/src/editor/app.py`:

```python
from pathlib import Path

import toga
from toga.constants import COLUMN, ROW

from toga_code_editor import CodeEditor, language_for_filename

SAMPLES = Path(__file__).parent / "resources" / "samples"
NO_LANGUAGE = "none"
LANGUAGES = ["python", "json", "html", NO_LANGUAGE]


class Editor(toga.App):
    def startup(self):
        self.editor = CodeEditor(flex=1, on_change=self.on_edit)
        self.sample = toga.Selection(
            items=sorted(path.name for path in SAMPLES.iterdir()),
            on_change=self.load_sample,
        )
        self.language = toga.Selection(items=LANGUAGES, on_change=self.set_language)
        self.line_numbers = toga.Switch(
            "Line numbers", value=True, on_change=self.toggle_line_numbers
        )
        self.status = toga.Label("", flex=1)

        toolbar = toga.Box(
            children=[self.sample, self.language, self.line_numbers, self.status],
            direction=ROW,
            align_items="center",
            margin=5,
            gap=5,
        )
        self.main_window = toga.MainWindow()
        self.main_window.content = toga.Box(
            children=[toolbar, self.editor], direction=COLUMN
        )
        self.load_sample(self.sample)
        self.main_window.show()

    def load_sample(self, widget, **kwargs):
        path = SAMPLES / self.sample.value
        self.editor.value = path.read_text(encoding="utf-8")
        self.language.value = language_for_filename(path) or NO_LANGUAGE
        self.status.text = ""

    def set_language(self, widget, **kwargs):
        value = self.language.value
        self.editor.language = None if value == NO_LANGUAGE else value

    def toggle_line_numbers(self, widget, **kwargs):
        self.editor.show_line_numbers = self.line_numbers.value

    def on_edit(self, widget, **kwargs):
        self.status.text = "Modified"


def main():
    return Editor("Editor", "org.beeware.toga_code_editor.examples.editor")
```

- [ ] **Step 4: Write the sample files**

`examples/editor/src/editor/resources/samples/hello.py`:

```python
"""A small sample for the editor."""

import math


@staticmethod
def area(radius: float) -> float:
    # Circles are round 😀 (an emoji keeps UTF-16 offsets honest)
    return math.pi * radius**2


class Greeter:
    def __init__(self, name="world"):
        self.name = name

    def greet(self):
        print(f"Hello, {self.name}!")


if __name__ == "__main__":
    Greeter().greet()
```

`examples/editor/src/editor/resources/samples/config.json`:

```json
{
  "name": "editor",
  "version": 1,
  "features": ["line numbers", "highlighting"],
  "debug": false
}
```

`examples/editor/src/editor/resources/samples/page.html`:

```html
<!DOCTYPE html>
<html lang="en">
  <head>
    <title>Sample</title>
  </head>
  <body>
    <!-- a comment -->
    <h1 class="title">Hello</h1>
    <p>Some <em>text</em>.</p>
  </body>
</html>
```

- [ ] **Step 5: Run the example app on macOS**

Run:

```bash
cd /Users/kattni/BeeWare/toga-code-editor/examples/editor && ../../.venv/bin/briefcase dev
```

Briefcase installs `../..` as a regular package into the venv, so after any later change to the widget source re-run with `briefcase dev -r`. Do not touch the keyboard or mouse until the window appears.

Check by hand, then quit the app:

1. `hello.py` loads with keywords, strings, the comment, and the decorator in color, and a numbered gutter on the left.
2. Typing a new `# comment` line turns it gray within a blink, and the gutter grows by one line.
3. Scrolling keeps the numbers aligned with their lines.
4. The line-numbers switch hides and shows the gutter.
5. Switching the language selection to `none` removes the colors; switching back restores them.
6. The emoji line in `hello.py` colors correctly and the lines after it are still colored correctly.

If any check fails, fix the module and re-run `briefcase dev -r` before moving on.

- [ ] **Step 6: Run pre-commit and commit**

```bash
cd /Users/kattni/BeeWare/toga-code-editor && .venv/bin/pre-commit run --all-files
git add src/toga_code_editor/cocoa_code_editor.py examples/editor
git commit -m "Add the Cocoa backend and the example editor app"
```

---

### Task 5: iOS backend

**Files:**
- Create: `src/toga_code_editor/iOS_code_editor.py`

**Interfaces:**
- Consumes: the backend contract from Task 3; `to_utf16_spans` and `utf16_line_starts` from Task 2; the example app from Task 4.
- Produces: `toga_code_editor.iOS_code_editor.CodeEditor`.

Toga internals this module subclasses, from toga-iOS 0.5.7: `toga_iOS.widgets.multilinetextinput.MultilineTextInput` (attributes `native`, the `UITextView`, and `placeholder_label`, a `UILabel` constrained inside it by `constrain_placeholder_label()`) and `TogaMultilineTextView`, which carries `interface` and `impl` properties and implements `textViewDidChange_`.

There is no ruler on iOS. The gutter is reserved with `textContainerInset.left` and drawn in `drawRect:`. A `UITextView` is a scroll view, so `drawRect:` runs in content coordinates and the numbers scroll with the text; `contentMode` is set to redraw so each scroll repaints.

- [ ] **Step 1: Write `iOS_code_editor.py`**

```python
from bisect import bisect_right

from rubicon.objc import CGPoint, CGRect, NSRange, objc_method, send_super
from rubicon.objc.types import UIEdgeInsets
from toga_iOS.colors import native_color
from toga_iOS.libs import (
    NSAttributedString,
    NSFontAttributeName,
    NSForegroundColorAttributeName,
    NSLayoutAttributeBottom,
    NSLayoutAttributeLeading,
    NSLayoutAttributeTop,
    NSLayoutAttributeTrailing,
    NSLayoutConstraint,
    NSLayoutRelationEqual,
    NSMutableDictionary,
    UIColor,
    UIFont,
    UIFontDescriptorTraitBold,
    UIFontDescriptorTraitItalic,
    UILabel,
)
from toga_iOS.widgets.multilinetextinput import (
    MultilineTextInput,
    TogaMultilineTextView,
)

from .highlighting import to_utf16_spans, utf16_line_starts

UIColor.declare_class_property("labelColor")
UIColor.declare_class_property("secondaryLabelColor")

# UIViewContentMode
UIViewContentModeRedraw = 3
# UITextAutocapitalizationType / UITextAutocorrectionType / UITextSpellCheckingType /
# UITextSmartQuotesType / UITextSmartDashesType / UITextSmartInsertDeleteType
UITextAutocapitalizationTypeNone = 0
UITextAutocorrectionTypeNo = 1
UITextSpellCheckingTypeNo = 1
UITextSmartQuotesTypeNo = 1
UITextSmartDashesTypeNo = 1
UITextSmartInsertDeleteTypeNo = 1

GUTTER_PADDING = 6
PLACEHOLDER_LEADING = 4.0


class TogaCodeTextView(TogaMultilineTextView):
    @objc_method
    def textViewDidChange_(self, text_view):
        self.interface._schedule_rehighlight()
        self.interface.on_change()
        self.impl.text_changed()

    @objc_method
    def drawRect_(self, rect: CGRect) -> None:
        send_super(__class__, self, "drawRect:", rect, argtypes=[CGRect])
        self.impl.draw_line_numbers()


class CodeEditor(MultilineTextInput):
    def create(self):
        # Mirrors toga_iOS's MultilineTextInput.create(), swapping in
        # TogaCodeTextView and turning off prose features.
        self.native = TogaCodeTextView.alloc().init()
        self.native.interface = self.interface
        self.native.impl = self
        self.native.delegate = self.native
        self.native.contentMode = UIViewContentModeRedraw
        self.native.autocapitalizationType = UITextAutocapitalizationTypeNone
        self.native.autocorrectionType = UITextAutocorrectionTypeNo
        self.native.spellCheckingType = UITextSpellCheckingTypeNo
        self.native.smartQuotesType = UITextSmartQuotesTypeNo
        self.native.smartDashesType = UITextSmartDashesTypeNo
        self.native.smartInsertDeleteType = UITextSmartInsertDeleteTypeNo

        # Reading layoutManager opts the view into TextKit 1, which is what the
        # gutter's line-fragment queries need. Do it once, up front.
        self.layout_manager = self.native.layoutManager

        # Placeholder isn't natively supported, so we create our own
        self.placeholder_label = UILabel.alloc().init()
        self.placeholder_label.translatesAutoresizingMaskIntoConstraints = False
        self.placeholder_label.font = self.native.font
        self.placeholder_label.alpha = 0.5
        self.native.addSubview(self.placeholder_label)
        self.constrain_placeholder_label()
        self.native.placeholder_label = self.placeholder_label

        self.theme = {}
        self.attributes = {}
        self.spans = []
        self.line_starts = [0]
        self.show_line_numbers = True
        self.gutter_width = 0
        self.default_inset = self.native.textContainerInset

        self.add_constraints()
        self.text_changed()

    def constrain_placeholder_label(self):
        # Same constraints as toga_iOS, but keeping a reference to the leading one
        # so the gutter can push the placeholder right.
        self.placeholder_leading = NSLayoutConstraint.constraintWithItem(
            self.placeholder_label,
            attribute__1=NSLayoutAttributeLeading,
            relatedBy=NSLayoutRelationEqual,
            toItem=self.native,
            attribute__2=NSLayoutAttributeLeading,
            multiplier=1.0,
            constant=PLACEHOLDER_LEADING,
        )
        trailing_constraint = NSLayoutConstraint.constraintWithItem(
            self.placeholder_label,
            attribute__1=NSLayoutAttributeTrailing,
            relatedBy=NSLayoutRelationEqual,
            toItem=self.native,
            attribute__2=NSLayoutAttributeTrailing,
            multiplier=1.0,
            constant=0,
        )
        top_constraint = NSLayoutConstraint.constraintWithItem(
            self.placeholder_label,
            attribute__1=NSLayoutAttributeTop,
            relatedBy=NSLayoutRelationEqual,
            toItem=self.native,
            attribute__2=NSLayoutAttributeTop,
            multiplier=1.0,
            constant=8.0,
        )
        bottom_constraint = NSLayoutConstraint.constraintWithItem(
            self.placeholder_label,
            attribute__1=NSLayoutAttributeBottom,
            relatedBy=NSLayoutRelationEqual,
            toItem=self.native,
            attribute__2=NSLayoutAttributeBottom,
            multiplier=1.0,
            constant=0,
        )
        self.native.addConstraints(
            [
                self.placeholder_leading,
                trailing_constraint,
                top_constraint,
                bottom_constraint,
            ]
        )

    # Inherited MultilineTextInput methods that must keep the gutter and colors in sync

    def set_value(self, value):
        super().set_value(value)
        self.text_changed()

    def set_font(self, font):
        super().set_font(font)
        self.rebuild_attributes()
        self.apply_highlights()
        self.text_changed()

    def set_color(self, value):
        super().set_color(value)
        self.apply_highlights()

    # CodeEditor backend contract

    def set_theme(self, theme):
        self.theme = theme
        self.rebuild_attributes()

    def set_highlights(self, spans):
        self.spans = spans
        self.apply_highlights()

    def set_show_line_numbers(self, value):
        self.show_line_numbers = value
        self.text_changed()

    # Highlighting

    def rebuild_attributes(self):
        base_font = self.native.font
        self.attributes = {}
        for kind, style in self.theme.items():
            attributes = NSMutableDictionary.alloc().init()
            attributes[NSForegroundColorAttributeName] = native_color(style.color)
            traits = 0
            if style.bold:
                traits |= UIFontDescriptorTraitBold
            if style.italic:
                traits |= UIFontDescriptorTraitItalic
            if traits:
                # If there is no font with the requested traits, this returns None.
                font = UIFont.fontWithDescriptor(
                    base_font.fontDescriptor.fontDescriptorWithSymbolicTraits(traits),
                    size=base_font.pointSize,
                )
                if font is not None:
                    attributes[NSFontAttributeName] = font
            self.attributes[kind] = attributes

    def apply_highlights(self):
        storage = self.native.textStorage
        full_range = NSRange(0, storage.length)
        base_color = self.native.textColor or UIColor.labelColor
        storage.beginEditing()
        # Reset to the base font and color, then paint each span.
        storage.addAttribute(
            NSFontAttributeName, value=self.native.font, range=full_range
        )
        storage.addAttribute(
            NSForegroundColorAttributeName, value=base_color, range=full_range
        )
        for span in to_utf16_spans(self.get_value(), self.spans):
            attributes = self.attributes.get(span.kind)
            if attributes is not None:
                storage.addAttributes(
                    attributes, range=NSRange(span.start, span.end - span.start)
                )
        storage.endEditing()

    # Gutter

    def text_changed(self):
        self.line_starts = utf16_line_starts(self.get_value())
        if self.show_line_numbers:
            digits = len(str(len(self.line_starts)))
            width = self.gutter_label("0" * digits).size().width + 2 * GUTTER_PADDING
        else:
            width = 0
        if width != self.gutter_width:
            self.gutter_width = width
            inset = self.default_inset
            self.native.textContainerInset = UIEdgeInsets(
                inset.top, inset.left + width, inset.bottom, inset.right
            )
            self.placeholder_leading.constant = PLACEHOLDER_LEADING + width
        self.native.setNeedsDisplay()

    def gutter_label(self, text):
        attributes = NSMutableDictionary.alloc().init()
        attributes[NSFontAttributeName] = self.native.font
        attributes[NSForegroundColorAttributeName] = UIColor.secondaryLabelColor
        return NSAttributedString.alloc().initWithString(text, attributes=attributes)

    def draw_line_numbers(self):
        if not self.show_line_numbers:
            return
        layout = self.layout_manager
        container = self.native.textContainer
        inset = self.native.textContainerInset
        text_length = self.native.textStorage.length

        # bounds.origin is the scroll offset; the container is inset within it.
        bounds = self.native.bounds
        visible = CGRect(
            CGPoint(bounds.origin.x - inset.left, bounds.origin.y - inset.top),
            bounds.size,
        )
        glyph_range = layout.glyphRangeForBoundingRect(
            visible, inTextContainer=container
        )
        char_range = layout.characterRangeForGlyphRange(
            glyph_range, actualGlyphRange=None
        )
        first_line = max(bisect_right(self.line_starts, char_range.location) - 1, 0)
        last_char = char_range.location + char_range.length

        for number, start in enumerate(
            self.line_starts[first_line:], start=first_line + 1
        ):
            if start > last_char:
                break
            if start == text_length:
                # The empty line after a trailing newline, or an empty document.
                fragment = layout.extraLineFragmentRect
            else:
                glyph = layout.glyphIndexForCharacterAtIndex(start)
                fragment = layout.lineFragmentRectForGlyphAtIndex(
                    glyph, effectiveRange=None
                )
            label = self.gutter_label(str(number))
            x = self.gutter_width - GUTTER_PADDING - label.size().width
            y = fragment.origin.y + inset.top
            label.drawAtPoint(CGPoint(x, y))
```

- [ ] **Step 2: Run the example app in the iOS simulator**

Run:

```bash
cd /Users/kattni/BeeWare/toga-code-editor/examples/editor && ../../.venv/bin/briefcase run iOS
```

The first run creates the Xcode project and asks which simulator to use; pick any current iPhone. After later widget changes, re-run with `briefcase run iOS -r` so the package is reinstalled.

Check by hand, then stop the app:

1. `hello.py` loads with colors and a numbered gutter that does not overlap the text.
2. Tapping into the text and typing a `# comment` colors it within a blink, with no autocorrect or smart-quote substitution (type `'` and `"` and confirm they stay straight).
3. Scrolling keeps numbers aligned with their lines, including after the emoji line.
4. The line-numbers switch removes the gutter and the text shifts left; turning it back on restores it.
5. Clearing all text still shows `1` in the gutter.

- [ ] **Step 3: Run pre-commit and commit**

```bash
cd /Users/kattni/BeeWare/toga-code-editor && .venv/bin/pre-commit run --all-files
git add src/toga_code_editor/iOS_code_editor.py
git commit -m "Add the iOS backend"
```

---

### Task 6: Android backend

**Files:**
- Create: `src/toga_code_editor/android_code_editor.py`

**Interfaces:**
- Consumes: the backend contract from Task 3; `to_utf16_spans` from Task 2; the example app from Task 4.
- Produces: `toga_code_editor.android_code_editor.CodeEditor`.

Toga internals this module subclasses, from toga-android 0.5.7: `toga_android.widgets.multilinetextinput.MultilineTextInput`, whose `TextInput` base creates `self.native` as an `EditText`, routes the `TextWatcher` through `_on_change()`, and inherits from `ContainedWidget`, which wraps `self.native` in a `RelativeLayout` stored as `self.native_toplevel` after `create()` returns.

Chaquopy can implement Java interfaces from Python through `dynamic_proxy` but cannot subclass Java classes, so there is no `onDraw` to override. The gutter is a sibling `TextView` inside the `RelativeLayout`, showing one number per visual line that starts a logical line and a blank for each wrapped continuation. It shares the editor's typeface, size, padding, and line spacing so rows align, and a scroll listener mirrors the editor's vertical offset onto it.

- [ ] **Step 1: Write `android_code_editor.py`**

```python
import weakref

from android.graphics import Typeface
from android.text import InputType, Spanned
from android.text.style import ForegroundColorSpan, StyleSpan
from android.util import TypedValue
from android.view import Gravity, View
from android.widget import RelativeLayout, TextView
from java import dynamic_proxy
from java.lang import Runnable
from toga_android.colors import native_color
from toga_android.widgets.base import suppress_reference_error
from toga_android.widgets.multilinetextinput import MultilineTextInput

from .highlighting import to_utf16_spans

GUTTER_PADDING = 6  # CSS pixels; scaled to physical pixels at creation


class TogaGutterScrollListener(dynamic_proxy(View.OnScrollChangeListener)):
    def __init__(self, impl):
        super().__init__()
        self.impl = weakref.proxy(impl)

    def onScrollChange(self, view, new_x, new_y, old_x, old_y):
        with suppress_reference_error():
            self.impl.gutter.setScrollY(new_y)


class TogaGutterUpdater(dynamic_proxy(Runnable)):
    def __init__(self, impl):
        super().__init__()
        self.impl = weakref.proxy(impl)

    def run(self):
        with suppress_reference_error():
            self.impl.update_gutter()


class CodeEditor(MultilineTextInput):
    def __init__(self, interface):
        super().__init__(interface)
        # ContainedWidget wraps self.native in a RelativeLayout *after* create()
        # returns, so the gutter can only be added here.
        padding = self.scale_in(GUTTER_PADDING)
        self.gutter = TextView(self._native_activity)
        self.gutter.setId(View.generateViewId())
        self.gutter.setGravity(Gravity.END | Gravity.TOP)
        self.gutter.setTextColor(self.native.getCurrentHintTextColor())
        self.gutter.setPadding(
            padding,
            self.native.getPaddingTop(),
            padding,
            self.native.getPaddingBottom(),
        )
        self.sync_gutter_font()

        gutter_params = RelativeLayout.LayoutParams(
            RelativeLayout.LayoutParams.WRAP_CONTENT,
            RelativeLayout.LayoutParams.MATCH_PARENT,
        )
        gutter_params.addRule(RelativeLayout.ALIGN_PARENT_START)
        self.native_toplevel.addView(self.gutter, gutter_params)

        text_params = RelativeLayout.LayoutParams(
            RelativeLayout.LayoutParams.MATCH_PARENT,
            RelativeLayout.LayoutParams.MATCH_PARENT,
        )
        text_params.addRule(RelativeLayout.END_OF, self.gutter.getId())
        self.native.setLayoutParams(text_params)

        self.native.setOnScrollChangeListener(TogaGutterScrollListener(self))
        self.gutter_updater = TogaGutterUpdater(self)
        self.update_gutter()

    def create(self):
        super().create()
        self.disable_suggestions()
        self.theme = {}
        self.spans = []
        self.active_spans = []

    def disable_suggestions(self):
        # NO_SUGGESTIONS turns off autocorrect on most keyboards. Some third-party
        # keyboards ignore it; that is a known rough edge.
        self.native.setInputType(
            self.native.getInputType() | InputType.TYPE_TEXT_FLAG_NO_SUGGESTIONS
        )

    # Inherited TextInput methods that must keep the gutter and flags in sync

    def set_readonly(self, readonly):
        # The parent toggles NO_SUGGESTIONS with readonly; keep it on regardless.
        super().set_readonly(readonly)
        self.disable_suggestions()

    def set_font(self, font):
        super().set_font(font)
        self.sync_gutter_font()
        self.native.post(self.gutter_updater)

    def _on_change(self):
        self.interface._schedule_rehighlight()
        self.interface.on_change()
        # The text layout is rebuilt after this callback returns; update the
        # gutter once that has happened.
        self.native.post(self.gutter_updater)

    # CodeEditor backend contract

    def set_theme(self, theme):
        self.theme = theme

    def set_highlights(self, spans):
        self.spans = spans
        editable = self.native.getText()
        for span in self.active_spans:
            editable.removeSpan(span)
        self.active_spans = []

        for span in to_utf16_spans(str(editable), spans):
            style = self.theme.get(span.kind)
            if style is None:
                continue
            native_spans = [ForegroundColorSpan(native_color(style.color))]
            if style.bold or style.italic:
                typeface_style = (Typeface.BOLD if style.bold else Typeface.NORMAL) | (
                    Typeface.ITALIC if style.italic else Typeface.NORMAL
                )
                native_spans.append(StyleSpan(typeface_style))
            for native_span in native_spans:
                editable.setSpan(
                    native_span, span.start, span.end, Spanned.SPAN_EXCLUSIVE_EXCLUSIVE
                )
                self.active_spans.append(native_span)

    def set_show_line_numbers(self, value):
        # A GONE anchor collapses to zero width, so the editor fills the row.
        self.gutter.setVisibility(View.VISIBLE if value else View.GONE)

    # Gutter

    def sync_gutter_font(self):
        self.gutter.setTypeface(self.native.getTypeface())
        self.gutter.setTextSize(TypedValue.COMPLEX_UNIT_PX, self.native.getTextSize())
        self.gutter.setLineSpacing(
            self.native.getLineSpacingExtra(), self.native.getLineSpacingMultiplier()
        )
        self.gutter.setIncludeFontPadding(self.native.getIncludeFontPadding())

    def update_gutter(self):
        layout = self.native.getLayout()
        if layout is None:
            # No layout pass has happened yet; the next change will post again.
            return
        text = self.native.getText()
        numbers = []
        line = 0
        for i in range(layout.getLineCount()):
            start = layout.getLineStart(i)
            if start == 0 or text.charAt(start - 1) == "\n":
                line += 1
                numbers.append(str(line))
            else:
                numbers.append("")  # a wrapped continuation line
        self.gutter.setText("\n".join(numbers))
```

- [ ] **Step 2: Run the example app on an Android emulator**

Run:

```bash
cd /Users/kattni/BeeWare/toga-code-editor/examples/editor && ../../.venv/bin/briefcase run android
```

The first run downloads the Android SDK components Briefcase needs and asks which device to use; create or pick an emulator. After later widget changes, re-run with `briefcase run android -r`.

Check by hand, then stop the app:

1. `hello.py` loads with colors and a numbered gutter whose rows line up with the text rows.
2. Typing a `# comment` colors it within a blink; typing `'` keeps a straight quote and no suggestion bar replaces words.
3. A long line that wraps shows its number once, with blank gutter rows beside the continuation.
4. Scrolling the editor scrolls the gutter with it.
5. The line-numbers switch removes the gutter and the editor fills the width; turning it back on restores it.

- [ ] **Step 3: Run pre-commit and commit**

```bash
cd /Users/kattni/BeeWare/toga-code-editor && .venv/bin/pre-commit run --all-files
git add src/toga_code_editor/android_code_editor.py
git commit -m "Add the Android backend"
```

---

### Task 7: README, changelog, and CI

**Files:**
- Modify: `README.md`
- Create: `CHANGELOG.md`, `changes/+initial.feature.md`, `.github/workflows/ci.yml`

**Interfaces:**
- Consumes: the public API from Tasks 2 and 3 and the example app from Task 4.
- Produces: user-facing documentation, a towncrier-ready changelog, and a CI workflow that runs pre-commit and the test suite with coverage.

- [ ] **Step 1: Write the README**

Replace `README.md` with:

````markdown
# toga-code-editor

A [Toga](https://toga.beeware.org) widget for editing code, with line numbers and syntax highlighting. `CodeEditor` is a `toga.MultilineTextInput` that colors its text with [Pygments](https://pygments.org) and shows a line-number gutter. It supports macOS, iOS, and Android.

## Installation

```console
pip install toga-code-editor
```

The package depends on `toga-core` and `pygments`. Your app installs the Toga backend for its platform as usual; `toga-code-editor` contributes its implementation for that backend through entry points, the same way Toga's own widgets are found.

## Usage

```python
import toga
from toga_code_editor import CodeEditor, language_for_filename

editor = CodeEditor(
    value=source,
    language="python",      # any Pygments lexer alias; None turns highlighting off
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

Unless you give the widget a font family, it uses a monospace font. Autocorrect, smart quotes, smart dashes, auto-capitalization, and spell checking are always off.

### Themes

A theme is a plain mapping. Kinds you leave out are drawn in the widget's normal text color.

```python
from toga_code_editor import DEFAULT_THEME, Style, TokenKind

theme = {
    **DEFAULT_THEME,
    TokenKind.COMMENT: Style("#6a737d", italic=True),
    TokenKind.KEYWORD: Style("rebeccapurple", bold=True),
}
editor.theme = theme
```

`Style.color` accepts anything Toga's color properties accept. The token kinds are `KEYWORD`, `BUILTIN`, `DEFINITION`, `DECORATOR`, `STRING`, `NUMBER`, `COMMENT`, `OPERATOR`, `PUNCTUATION`, `TAG`, `ATTRIBUTE`, and `VARIABLE`.

## Platform notes

- **macOS** uses an `NSRulerView` for the gutter and the system's adaptive color mapping, so theme colors follow dark mode.
- **iOS** and **Android** draw the gutter themselves. Theme colors do not change with the system appearance; the default theme is chosen to be legible on both light and dark backgrounds.
- Highlighting re-lexes the whole buffer after a short pause in typing. Files of a few thousand lines are fine on a desktop; very large files are slower on phones.
- Some third-party Android keyboards ignore the flag that disables suggestions.

## Developing

```console
uv venv
uv pip install -e . --group dev
.venv/bin/tox -m test
```

The test suite runs against Toga's dummy backend. Real backends are checked with the example app in `examples/editor`:

```console
cd examples/editor
briefcase dev            # macOS
briefcase run iOS
briefcase run android
```

Add `-r` after changing the widget source so Briefcase reinstalls it.

Every user-visible change needs a fragment in `changes/`, named `<issue>.<kind>.md` where kind is `feature`, `bugfix`, `doc`, or `misc`. Release notes are assembled with `towncrier build`.
````

- [ ] **Step 2: Write the changelog, its first fragment, and the CI workflow**

`CHANGELOG.md`:

```markdown
# Changelog

<!-- towncrier release notes start -->
```

`changes/+initial.feature.md`:

```markdown
Added the `CodeEditor` widget, with line numbers and Pygments syntax highlighting, for the Cocoa, iOS, and Android backends.
```

`.github/workflows/ci.yml`:

```yaml
name: CI

on:
  pull_request:
  push:
    branches: [main]

jobs:
  test:
    name: Lint and test
    runs-on: ubuntu-latest
    steps:
      - name: Checkout
        uses: actions/checkout@v6
        with:
          persist-credentials: false

      - name: Set up Python
        uses: actions/setup-python@v7
        with:
          python-version: "3.13"

      - name: Install tox
        run: python -m pip install tox tox-uv

      - name: Lint
        run: tox -e pre-commit

      - name: Test with coverage
        run: tox -e py-cov,coverage
```

- [ ] **Step 3: Check the changelog assembles and the full tox run passes**

Run:

```bash
cd /Users/kattni/BeeWare/toga-code-editor && .venv/bin/towncrier build --draft --version 0.1.0 && .venv/bin/tox -e pre-commit,py-cov,coverage
```

Expected: the draft shows the feature entry under "Features", and tox finishes with every environment `OK`, including the coverage report with no `fail_under` error.

- [ ] **Step 4: Commit**

```bash
git add README.md CHANGELOG.md changes .github
git commit -m "Add the README, changelog, and CI workflow"
```

---

## Done

When all seven tasks are committed, the package installs with `pip install -e .`, the test suite passes at full coverage on the dummy backend, and the example app runs with highlighting and line numbers on macOS, in the iOS simulator, and on an Android emulator. Publishing to PyPI and announcing the package are outside this plan.
