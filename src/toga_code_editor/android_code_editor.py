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


class TogaGutterLayoutListener(dynamic_proxy(View.OnLayoutChangeListener)):
    def __init__(self, impl):
        super().__init__()
        self.impl = weakref.proxy(impl)

    def onLayoutChange(
        self, view, left, top, right, bottom, o_left, o_top, o_right, o_bottom
    ):
        # A new width re-wraps the text, which changes which visual lines start a
        # logical line. Defer the rebuild until this layout pass has finished.
        with suppress_reference_error():
            if (right - left, bottom - top) != (o_right - o_left, o_bottom - o_top):
                self.impl.native.post(self.impl.gutter_updater)


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
        self.native.addOnLayoutChangeListener(TogaGutterLayoutListener(self))
        self.gutter_updater = TogaGutterUpdater(self)
        self.gutter_numbers = None
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
        gutter_numbers = "\n".join(numbers)
        if gutter_numbers != self.gutter_numbers:
            self.gutter_numbers = gutter_numbers
            self.gutter.setText(gutter_numbers)
