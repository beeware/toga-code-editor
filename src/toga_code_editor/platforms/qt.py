from bisect import bisect_left, bisect_right

from PySide6.QtCore import QRect, Qt
from PySide6.QtGui import (
    QBrush,
    QFont,
    QPainter,
    QPalette,
    QSyntaxHighlighter,
    QTextCharFormat,
)
from PySide6.QtWidgets import QPlainTextEdit, QWidget
from toga_qt.colors import native_color
from toga_qt.widgets.multilinetextinput import MultilineTextInput

from ..highlighting import to_utf16_spans

GUTTER_PADDING = 6


class TogaLineNumberArea(QWidget):
    def __init__(self, editor):
        super().__init__(editor)
        self.editor = editor

    def paintEvent(self, event):
        self.editor.draw_line_numbers(event)


class TogaCodeTextEdit(QPlainTextEdit):
    # Owns the gutter geometry: setViewportMargins and the block geometry queries
    # are protected in C++, which PySide exposes only inside a subclass.

    def __init__(self):
        super().__init__()
        self.gutter_width = 0
        self.gutter = TogaLineNumberArea(self)

    def set_gutter_width(self, width):
        self.gutter_width = width
        self.setViewportMargins(width, 0, 0, 0)
        self.place_gutter()

    def place_gutter(self):
        rect = self.contentsRect()
        self.gutter.setGeometry(
            QRect(rect.left(), rect.top(), self.gutter_width, rect.height())
        )

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.place_gutter()

    def draw_line_numbers(self, event):
        painter = QPainter(self.gutter)
        # Paint the strip, so the gutter looks the same whatever sits behind the
        # editor.
        painter.fillRect(event.rect(), self.palette().color(QPalette.ColorRole.Window))
        painter.setFont(self.font())
        painter.setPen(self.palette().color(QPalette.ColorRole.PlaceholderText))
        height = self.fontMetrics().height()
        label_width = self.gutter_width - GUTTER_PADDING
        # A block is a logical line; its rectangle spans every wrapped visual line,
        # so continuation lines get no number.
        block = self.firstVisibleBlock()
        geometry = self.blockBoundingGeometry(block).translated(self.contentOffset())
        top = round(geometry.top())
        bottom = top + round(self.blockBoundingRect(block).height())
        while block.isValid() and top <= event.rect().bottom():
            if block.isVisible() and bottom >= event.rect().top():
                painter.drawText(
                    0,
                    top,
                    label_width,
                    height,
                    Qt.AlignmentFlag.AlignRight,
                    str(block.blockNumber() + 1),
                )
            block = block.next()
            top = bottom
            bottom = top + round(self.blockBoundingRect(block).height())
        painter.end()


class TogaSpanHighlighter(QSyntaxHighlighter):
    # Formats set here live in the text layout, not the document, so they never
    # enter the undo stack and never travel with copied text.

    def __init__(self, document):
        super().__init__(document)
        self.formats = {}
        self.spans = []
        self.starts = []

    def set_spans(self, spans):
        self.spans = spans
        self.starts = [span.start for span in spans]
        self.rehighlight()

    def highlightBlock(self, text):
        # Document positions are UTF-16 code units and the text argument's Python
        # length is in code points, so work from the block instead of the text.
        block = self.currentBlock()
        start = block.position()
        end = start + block.length()
        # Spans are sorted and disjoint, so the ones that can reach this block
        # are the last one starting before it through the last one starting
        # inside it.
        first = max(bisect_right(self.starts, start) - 1, 0)
        last = bisect_left(self.starts, end)
        for span in self.spans[first:last]:
            fmt = self.formats.get(span.kind)
            low = max(span.start, start)
            high = min(span.end, end)
            if fmt is not None and high > low:
                self.setFormat(low - start, high - low, fmt)


class CodeEditor(MultilineTextInput):
    def create(self):
        # Mirrors toga_qt's MultilineTextInput.create() with QPlainTextEdit, the Qt
        # widget built for code, in place of QTextEdit. It holds only plain text, so
        # Toga's setAcceptRichText(False) has no counterpart here.
        self.native = TogaCodeTextEdit()
        self.native.textChanged.connect(self.qt_on_change)
        self.native.blockCountChanged.connect(self.qt_on_block_count_changed)
        self.native.updateRequest.connect(self.qt_on_update_request)

        self.highlighter = TogaSpanHighlighter(self.native.document())
        self.applying_highlights = False

        self.gutter_visible = True
        self.update_gutter_width()

    def qt_on_change(self):
        # QSyntaxHighlighter.rehighlight() emits textChanged even though the text is
        # untouched. Counting that as an edit would schedule another re-highlight,
        # forever, and call the user's handler with nothing changed.
        if self.applying_highlights:
            return
        # The re-highlight is scheduled before the user's handler runs, as on the
        # other backends.
        self.interface._schedule_rehighlight()
        self.interface.on_change()

    def set_font(self, font):
        super().set_font(font)
        self.update_gutter_width()

    # CodeEditor backend contract

    def set_theme(self, theme):
        # Formats set only weight and italic, so the widget font shows through. The
        # interface always follows set_theme with set_highlights, which repaints.
        formats = {}
        for kind, style in theme.items():
            fmt = QTextCharFormat()
            fmt.setForeground(QBrush(native_color(style.color)))
            if style.bold:
                fmt.setFontWeight(QFont.Weight.Bold)
            if style.italic:
                fmt.setFontItalic(True)
            formats[kind] = fmt
        self.highlighter.formats = formats

    def set_highlights(self, spans):
        utf16_spans = to_utf16_spans(self.get_value(), spans)
        self.applying_highlights = True
        try:
            self.highlighter.set_spans(utf16_spans)
        finally:
            self.applying_highlights = False

    def set_show_line_numbers(self, value):
        self.gutter_visible = value
        self.native.gutter.setVisible(value)
        self.update_gutter_width()

    # Gutter

    def update_gutter_width(self):
        if self.gutter_visible:
            digits = len(str(self.native.blockCount()))
            width = (
                self.native.fontMetrics().horizontalAdvance("0") * digits
                + 2 * GUTTER_PADDING
            )
        else:
            width = 0
        if width != self.native.gutter_width:
            self.native.set_gutter_width(width)

    def qt_on_block_count_changed(self, count):
        self.update_gutter_width()

    def qt_on_update_request(self, rect, dy):
        gutter = self.native.gutter
        if dy:
            gutter.scroll(0, dy)
        else:
            gutter.update(0, rect.y(), gutter.width(), rect.height())
