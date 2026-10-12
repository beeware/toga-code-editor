from bisect import bisect_right
from ctypes import (
    HRESULT,
    POINTER,
    WINFUNCTYPE,
    Structure,
    addressof,
    byref,
    c_long,
    c_ubyte,
    c_ulong,
    c_void_p,
    cast,
)
from ctypes.wintypes import DWORD, POINT, WORD

import System.Windows.Forms as WinForms
from System import Int32
from System.Drawing import Font, FontStyle, Point, Rectangle, Size, SystemColors
from System.Windows.Forms import TextFormatFlags, TextRenderer
from toga.handlers import WeakrefCallable
from toga_winforms.colors import native_color
from toga_winforms.libs.user32 import SendMessageW
from toga_winforms.widgets.multilinetextinput import MultilineTextInput

from ..highlighting import to_utf16_spans, utf16_line_starts

GUTTER_PADDING = 6  # CSS pixels; scaled to physical pixels where it is used

# Edit-control messages from winuser.h and richedit.h; toga_winforms binds none.
WM_USER = 0x0400
EM_POSFROMCHAR = 0x00D6
EM_CHARFROMPOS = 0x00D7
EM_GETEVENTMASK = WM_USER + 59
EM_GETOLEINTERFACE = WM_USER + 60
EM_SETEVENTMASK = WM_USER + 69
EM_GETSCROLLPOS = WM_USER + 221
EM_SETSCROLLPOS = WM_USER + 222
ENM_CHANGE = 0x00000001
ENM_SELCHANGE = 0x00000002

# Text Object Model, from tom.h: the ITextDocument.Undo arguments, and the vtable
# slots of the methods used here. IUnknown fills slots 0 to 2 and IDispatch 3 to 6.
TOM_SUSPEND = -9999995  # tomSuspend
TOM_RESUME = -9999994  # tomResume
IUNKNOWN_QUERY_INTERFACE = 0
IUNKNOWN_RELEASE = 2
ITEXTDOCUMENT_FREEZE = 18
ITEXTDOCUMENT_UNFREEZE = 19
ITEXTDOCUMENT_UNDO = 22

UNBOUNDED = Size(Int32.MaxValue, Int32.MaxValue)
GUTTER_TEXT_FLAGS = (
    TextFormatFlags.Right | TextFormatFlags.NoPadding | TextFormatFlags.SingleLine
)


class GUID(Structure):
    _fields_ = [
        ("Data1", DWORD),
        ("Data2", WORD),
        ("Data3", WORD),
        ("Data4", c_ubyte * 8),
    ]


IID_ITEXTDOCUMENT = GUID(
    0x8CC497C0,
    0xA1DF,
    0x11CE,
    (c_ubyte * 8)(0x80, 0x98, 0x00, 0xAA, 0x00, 0x47, 0xBE, 0x5D),
)

# COM method prototypes; the first argument is always the interface pointer. The
# document methods declare a plain integer result rather than HRESULT, so ctypes
# never raises from them, and their results are discarded by design: the paint's
# restore chain must run to its end whatever they report, and none of them fails
# on a live control.
QUERY_INTERFACE = WINFUNCTYPE(HRESULT, c_void_p, POINTER(GUID), POINTER(c_void_p))
RELEASE = WINFUNCTYPE(c_ulong, c_void_p)
COUNT_METHOD = WINFUNCTYPE(c_long, c_void_p, POINTER(c_long))  # Freeze, Unfreeze
UNDO_METHOD = WINFUNCTYPE(c_long, c_void_p, c_long, POINTER(c_long))


def com_method(interface, slot, prototype):
    """Bind the method at a vtable slot of a COM interface pointer."""
    vtable = cast(interface, POINTER(c_void_p))[0]
    return prototype(cast(vtable, POINTER(c_void_p))[slot])


class TextDocument:
    """The Text Object Model document behind a RichEdit control.

    WinForms exposes neither Freeze nor undo suspension, so both are called through
    the interface's vtable. The document reference is never released: Toga gives a
    widget implementation no teardown hook, and the object dies with the control.
    """

    def __init__(self, hwnd):
        ole = c_void_p()
        SendMessageW(hwnd, EM_GETOLEINTERFACE, 0, byref(ole))
        if ole.value is None:
            raise RuntimeError("The RichEdit control did not supply its OLE interface")
        self.pointer = c_void_p()
        com_method(ole, IUNKNOWN_QUERY_INTERFACE, QUERY_INTERFACE)(
            ole, byref(IID_ITEXTDOCUMENT), byref(self.pointer)
        )
        com_method(ole, IUNKNOWN_RELEASE, RELEASE)(ole)
        self._freeze = com_method(self.pointer, ITEXTDOCUMENT_FREEZE, COUNT_METHOD)
        self._unfreeze = com_method(self.pointer, ITEXTDOCUMENT_UNFREEZE, COUNT_METHOD)
        self._undo = com_method(self.pointer, ITEXTDOCUMENT_UNDO, UNDO_METHOD)

    def freeze(self):
        self._freeze(self.pointer, byref(c_long()))

    def unfreeze(self):
        self._unfreeze(self.pointer, byref(c_long()))

    def suspend_undo(self):
        self._undo(self.pointer, TOM_SUSPEND, byref(c_long()))

    def resume_undo(self):
        self._undo(self.pointer, TOM_RESUME, byref(c_long()))


class CodeEditor(MultilineTextInput):
    def create(self):
        # The inherited create() builds the RichTextBox and hooks its events.
        super().create()
        # Settings that would recreate a live window handle come first; the handle
        # does not exist yet.
        self.native.BorderStyle = getattr(WinForms.BorderStyle, "None")
        self.native.DetectUrls = False  # an auto-linked URL recolors itself
        self.native.AcceptsTab = True  # Tab inserts a tab, as on macOS
        self.native.RichTextShortcutsEnabled = False  # Ctrl+E and friends realign
        self.native.Dock = WinForms.DockStyle.Fill
        # VScroll covers the scroll bar and the wheel; the caret moving the view,
        # as with Page Down, reports a selection change instead.
        self.native.VScroll += WeakrefCallable(self.winforms_gutter_stale)
        self.native.SelectionChanged += WeakrefCallable(self.winforms_gutter_stale)
        self.native.Resize += WeakrefCallable(self.winforms_gutter_stale)
        self.native.KeyDown += WeakrefCallable(self.winforms_key_down)
        self.native.HandleCreated += WeakrefCallable(self.winforms_handle_created)

        self.gutter = WinForms.Panel()
        self.gutter.DoubleBuffered = True
        self.gutter.TabStop = False
        self.gutter.Dock = WinForms.DockStyle.Left
        self.gutter.Paint += WeakrefCallable(self.winforms_gutter_paint)

        # One sunken border around both, with the text box's own border removed.
        # Docking lays out later controls first, so the gutter takes its width and
        # the text box fills what is left.
        self.frame = WinForms.Panel()
        self.frame.BorderStyle = WinForms.BorderStyle.Fixed3D
        self.frame.Controls.Add(self.native)
        self.frame.Controls.Add(self.gutter)

        # RichTextBox.Font applies to every character, so the base font is tracked
        # here; scale_font keeps it current.
        self.base_font = self.native.Font
        self.theme = {}
        self.attributes = {}
        self.spans = []
        self.line_starts = [0]
        self.line_height = 0
        self.document = None
        # Size the gutter for the empty text now, rather than leaving the Panel's
        # default width in place until the style applies a font.
        self.text_changed()

    @property
    def hwnd(self):
        return int(self.native.Handle.ToString())

    # Toga positions, parents, hides, and colors self.native; the frame stands in.

    @property
    def container(self):
        return self._container

    @container.setter
    def container(self, container):
        if self._container:
            self._container.native_content.Controls.Remove(self.frame)
        self._container = container
        if container:
            container.native_content.Controls.Add(self.frame)
            self.frame.BringToFront()
        self.refresh()
        self.set_background_color(self.interface.style.background_color)

    def set_bounds(self, x, y, width, height):
        self.frame.Size = Size(*map(self.scale_in, (width, height)))
        self.frame.Location = Point(*map(self.scale_in, (x, y)))

    def set_hidden(self, hidden):
        self.frame.Visible = not hidden

    def set_background_color(self, color):
        super().set_background_color(color)
        self.gutter.BackColor = self.native.BackColor

    def get_tab_index(self):
        return self.frame.TabIndex

    def set_tab_index(self, tab_index):
        # The frame is what sits among the window's other widgets; inside it the
        # text box is the only tab stop.
        self.frame.TabIndex = tab_index
        self.native.TabIndex = tab_index

    # Native events

    def winforms_text_changed(self, sender, event):
        # Replaces Toga's handler, which reads Text twice; each read streams the
        # whole buffer out of the control. Formatting also raises this event, and
        # the comparison filters it out.
        if self._placeholder_visible:
            return
        text = self.native.Text
        if text == self._text_history:
            return
        self._text_history = text
        self.interface._schedule_rehighlight()
        self.interface.on_change()
        self.text_changed(text)

    def winforms_key_down(self, sender, event):
        # RichTextBox pastes rich text, whose paragraph formatting the re-highlight
        # never resets. Paste plain text for Ctrl+V and Shift+Insert instead. A
        # read-only control is left to RichEdit, which ignores the paste.
        if self.native.ReadOnly:
            return
        keys = WinForms.Keys
        if (event.Control and not event.Alt and event.KeyCode == keys.V) or (
            event.Shift and not event.Control and event.KeyCode == keys.Insert
        ):
            self.native.Paste(
                WinForms.DataFormats.GetFormat(WinForms.DataFormats.UnicodeText)
            )
            event.Handled = True
            event.SuppressKeyPress = True

    def winforms_gutter_stale(self, sender, event):
        # The text scrolled or re-wrapped; the line tops moved with it.
        self.gutter.Invalidate()

    def winforms_handle_created(self, sender, event):
        # A recreated handle is a new RichEdit object with a new document.
        self.document = None

    # Inherited methods that must keep the gutter and colors in sync

    def set_value(self, value):
        super().set_value(value)
        self.text_changed()

    def scale_font(self):
        # Toga routes set_font and DPI changes through here. Assigning Font resets
        # every character's formatting, so paint again afterwards.
        super().scale_font()
        self.base_font = self.native.Font
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
        # Docking hands a hidden gutter's width to the text box.
        self.gutter.Visible = value

    # Highlighting

    def rebuild_attributes(self):
        base_font = self.base_font
        family = base_font.FontFamily
        self.attributes = {}
        for kind, style in self.theme.items():
            font_style = base_font.Style
            if style.bold:
                font_style |= FontStyle.Bold
            if style.italic:
                font_style |= FontStyle.Italic
            font = None
            # A family without a face for the style would make Font() throw.
            if font_style != base_font.Style and family.IsStyleAvailable(font_style):
                font = Font(base_font, font_style)
            self.attributes[kind] = (native_color(style.color), font)

    def apply_highlights(self):
        # The placeholder is the text box's own gray text; leave it alone.
        if self._placeholder_visible:
            return
        length = self.native.TextLength
        if length == 0:
            return
        # Reading Handle can create the handle, which drops any cached document, so
        # it comes before the document is acquired.
        hwnd = self.hwnd
        if self.document is None:
            self.document = TextDocument(hwnd)
        # Between a native edit and the debounced re-highlight the spans describe the
        # previous text, so clamp them to the current length.
        spans = [
            (span.start, min(span.end, length), self.attributes.get(span.kind))
            for span in to_utf16_spans(self.get_value(), self.spans)
            if span.start < length
        ]
        native = self.native
        selection = (native.SelectionStart, native.SelectionLength)
        scroll = POINT()
        SendMessageW(hwnd, EM_GETSCROLLPOS, 0, byref(scroll))
        mask = SendMessageW(hwnd, EM_GETEVENTMASK, 0, 0)
        try:
            # Formatting raises TextChanged, whose handler streams the buffer out to
            # compare it, and every Select raises SelectionChanged. Silence both for
            # the duration.
            SendMessageW(hwnd, EM_SETEVENTMASK, 0, mask & ~(ENM_CHANGE | ENM_SELCHANGE))
            self.document.freeze()
            # Formatting would otherwise land on the undo stack ahead of the typing.
            self.document.suspend_undo()
            # Reset to the base font and color, then paint each span.
            native.Select(0, length)
            native.SelectionFont = self.base_font
            native.SelectionColor = self._color
            for start, end, attributes in spans:
                if attributes is None or end <= start:
                    continue
                color, font = attributes
                native.Select(start, end - start)
                native.SelectionColor = color
                if font is not None:
                    native.SelectionFont = font
        finally:
            # The notifications come back before the selection is restored, so
            # WinForms sees that change. WinForms' Select sends EM_SCROLLCARET after
            # EM_SETSEL, and the freeze defers every one of those scrolls until the
            # view thaws, so the selection goes back before the thaw and the scroll
            # position is put back after it; the scroll restore is load-bearing.
            self.document.resume_undo()
            SendMessageW(hwnd, EM_SETEVENTMASK, 0, mask)
            try:
                native.Select(*selection)
            finally:
                self.document.unfreeze()
                SendMessageW(hwnd, EM_SETSCROLLPOS, 0, byref(scroll))
                # A bold or italic span can re-wrap a line.
                self.gutter.Invalidate()

    # Gutter

    def text_changed(self, text=None):
        # The change handler passes the text it has already read; every other
        # caller pays one read of the buffer.
        if text is None:
            text = self.get_value()
        self.line_starts = utf16_line_starts(text)
        digits = len(str(len(self.line_starts)))
        size = TextRenderer.MeasureText(
            "0" * digits, self.base_font, UNBOUNDED, GUTTER_TEXT_FLAGS
        )
        self.line_height = size.Height
        width = size.Width + 2 * self.scale_in(GUTTER_PADDING)
        if self.gutter.Width != width:
            self.gutter.Width = width
        self.gutter.Invalidate()

    def winforms_gutter_paint(self, sender, event):
        hwnd = self.hwnd
        height = self.native.ClientSize.Height
        line_height = self.line_height
        right = self.gutter.Width - self.scale_in(GUTTER_PADDING)
        point = POINT(0, 0)
        # The first visible character and the logical line it belongs to. That
        # line's number may sit above the view, where it is clipped.
        first_char = SendMessageW(hwnd, EM_CHARFROMPOS, 0, byref(point))
        first_line = max(bisect_right(self.line_starts, first_char) - 1, 0)
        for number, start in enumerate(
            self.line_starts[first_line:], start=first_line + 1
        ):
            # Client coordinates of the line's first character. The index equal to
            # the text length addresses the final paragraph mark RichEdit always
            # keeps, which places the empty line after a trailing newline.
            SendMessageW(hwnd, EM_POSFROMCHAR, addressof(point), start)
            if point.y >= height:
                break
            TextRenderer.DrawText(
                event.Graphics,
                str(number),
                self.base_font,
                Rectangle(0, point.y, right, line_height),
                SystemColors.GrayText,
                GUTTER_TEXT_FLAGS,
            )
