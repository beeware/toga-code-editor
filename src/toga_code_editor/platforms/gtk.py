from toga.handlers import WeakrefCallable
from toga_gtk.colors import native_color
from toga_gtk.libs import Gdk, Gtk, Pango, PangoCairo
from toga_gtk.widgets.multilinetextinput import MultilineTextInput

GUTTER_PADDING = 6


class CodeEditor(MultilineTextInput):
    def create(self):
        self.setting_value = False

        # Toga builds the scrolled window, the text view, the content buffer, and the
        # placeholder buffer, and connects the content buffer's "changed" signal to
        # gtk_on_changed through a weak reference to the bound method, so the
        # override below is what gets connected.
        super().create()

        # Highlights are text tags on the content buffer, one per token kind.
        self.tags = {}

        # The gutter is the text view's left border window. GTK paints the view and
        # the border window's themed background in its own draw handler; connecting
        # after it paints the numbers on top.
        self.gutter_visible = True
        self.gutter_width = 0
        self.native_textview.connect_after("draw", WeakrefCallable(self.gtk_on_draw))
        self.update_gutter_width()

    # Inherited MultilineTextInput methods that must keep the gutter in sync

    def set_value(self, value):
        # Toga's set_value ends by spinning the GTK main loop until no events are
        # pending. The buffer's "changed" signal fires inside set_text, before that
        # spin. During startup, before Toga's asyncio loop has run its first
        # iteration, a task created there is never dispatched by those nested
        # iterations and keeps them pending forever, so the editor hung on its first
        # non-empty value. Skip the debounce for programmatic changes; the interface
        # re-highlights synchronously right after set_value, so nothing is lost.
        previous = self.setting_value
        self.setting_value = True
        try:
            super().set_value(value)
        finally:
            self.setting_value = previous

    def gtk_on_changed(self, *args):
        # The re-highlight is scheduled before the user's handler runs, as on the
        # other backends.
        if not self.setting_value:
            self.interface._schedule_rehighlight()
        super().gtk_on_changed(*args)
        self.native_textview.queue_draw()

    # CodeEditor backend contract

    def set_theme(self, theme):
        # Removing a tag from the table also strips it from the text. The interface
        # always follows set_theme with set_highlights, which paints again.
        table = self.buffer.get_tag_table()
        for tag in self.tags.values():
            table.remove(tag)
        self.tags = {}
        for kind, style in theme.items():
            # Only the properties the style needs, so the view's CSS font and color
            # show through everywhere else.
            properties = {"foreground_rgba": Gdk.RGBA(*native_color(style.color))}
            if style.bold:
                properties["weight"] = Pango.Weight.BOLD
            if style.italic:
                properties["style"] = Pango.Style.ITALIC
            self.tags[kind] = self.buffer.create_tag(None, **properties)

    def set_highlights(self, spans):
        start, end = self.buffer.get_bounds()
        self.buffer.remove_all_tags(start, end)
        for span in spans:
            tag = self.tags.get(span.kind)
            if tag is not None:
                # Buffer offsets are characters, so the spans apply unchanged. An
                # offset past the end, from spans that describe the previous text,
                # gives the end iterator rather than an error.
                self.buffer.apply_tag(
                    tag,
                    self.buffer.get_iter_at_offset(span.start),
                    self.buffer.get_iter_at_offset(span.end),
                )

    def set_show_line_numbers(self, value):
        self.gutter_visible = value
        self.update_gutter_width()

    # Gutter

    def update_gutter_width(self):
        if self.gutter_visible:
            view = self.native_textview
            digits = len(str(view.get_buffer().get_line_count()))
            layout = view.create_pango_layout("0" * digits)
            width = layout.get_pixel_size()[0] + 2 * GUTTER_PADDING
        else:
            width = 0
        if width != self.gutter_width:
            self.gutter_width = width
            # A width of zero removes the window.
            self.native_textview.set_border_window_size(Gtk.TextWindowType.LEFT, width)

    def gtk_on_draw(self, view, cr):
        window = view.get_window(Gtk.TextWindowType.LEFT)
        if window is None or not Gtk.cairo_should_draw_window(cr, window):
            return False
        # A font change reaches the view through CSS on a later frame, so measure
        # here rather than tracking when the font settles.
        self.update_gutter_width()
        cr.save()
        Gtk.cairo_transform_to_window(cr, view, window)
        cr.rectangle(0, 0, window.get_width(), window.get_height())
        cr.clip()
        self.draw_line_numbers(view, cr, window.get_width())
        cr.restore()
        return False

    def draw_line_numbers(self, view, cr, width):
        # Number the lines of whatever buffer the view displays. With the
        # placeholder shown, that is its single line, which reads as line 1 of an
        # empty document.
        buffer = view.get_buffer()
        # Ask for the insensitive color through a saved context: querying a
        # state the view is not in is unsupported on the live one.
        context = view.get_style_context()
        context.save()
        context.set_state(Gtk.StateFlags.INSENSITIVE)
        color = context.get_color(context.get_state())
        context.restore()
        Gdk.cairo_set_source_rgba(cr, color)
        visible = view.get_visible_rect()
        bottom = visible.y + visible.height
        first, _ = view.get_line_at_y(visible.y)
        line = first.get_line()
        # Walk line indices rather than calling forward_line(), which reports
        # failure when it lands on the end iterator and would skip the empty line
        # after a trailing newline.
        count = buffer.get_line_count()
        while line < count:
            y, _ = view.get_line_yrange(buffer.get_iter_at_line(line))
            if y > bottom:
                break
            _, window_y = view.buffer_to_window_coords(Gtk.TextWindowType.LEFT, 0, y)
            layout = view.create_pango_layout(str(line + 1))
            label_width, _ = layout.get_pixel_size()
            # Align to the window as it is now; a queued resize may still be pending.
            cr.move_to(width - GUTTER_PADDING - label_width, window_y)
            PangoCairo.show_layout(cr, layout)
            line += 1
