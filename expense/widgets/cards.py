"""Hand-built rounded, soft Material-You-ish widgets (no KivyMD needed).

Everything draws its own background with canvas RoundedRectangle so we get
Cashew's soft, friendly cards on pure Kivy.
"""

from kivy.uix.boxlayout import BoxLayout
from kivy.uix.anchorlayout import AnchorLayout
from kivy.uix.label import Label
from kivy.uix.widget import Widget
from kivy.uix.behaviors import ButtonBehavior
from kivy.graphics import Color, RoundedRectangle, Line, Ellipse
from kivy.metrics import dp

from .. import theme


class RoundedCard(BoxLayout):
    """A BoxLayout with a soft rounded background and optional left stripe."""

    def __init__(self, bg=None, radius=None, stripe=None, padding=None,
                 **kwargs):
        super().__init__(**kwargs)
        self._bg = bg or theme.SURFACE
        self._radius = dp(radius if radius is not None else theme.RADIUS)
        self._stripe = stripe
        if padding is not None:
            self.padding = padding
        with self.canvas.before:
            self._bg_color = Color(*self._bg)
            self._rect = RoundedRectangle(radius=[self._radius])
            self._stripe_color = Color(0, 0, 0, 0)
            self._stripe_rect = RoundedRectangle(radius=[self._radius])
        if self._stripe:
            self._stripe_color.rgba = self._stripe
        self.bind(pos=self._sync, size=self._sync)

    def set_bg(self, rgba):
        self._bg = rgba
        self._bg_color.rgba = rgba

    def _sync(self, *_):
        self._rect.pos = self.pos
        self._rect.size = self.size
        if self._stripe:
            self._stripe_rect.pos = self.pos
            self._stripe_rect.size = (dp(6), self.height)


class TouchCard(ButtonBehavior, RoundedCard):
    """A RoundedCard you can tap (fires on_release)."""


class Chip(ButtonBehavior, BoxLayout):
    """Small rounded pill, optionally toggled/selected."""

    def __init__(self, text, color=None, bg=None, selected=False, **kwargs):
        super().__init__(orientation="horizontal", **kwargs)
        self.padding = [dp(12), dp(6), dp(12), dp(6)]
        self.size_hint = (None, None)
        self.height = dp(32)
        self._sel = selected
        self._bg = bg or theme.SURFACE_ALT
        self._fg = color or theme.TEXT
        with self.canvas.before:
            self._c = Color(*(theme.PRIMARY_SOFT if selected else self._bg))
            self._r = RoundedRectangle(radius=[dp(16)])
        self.bind(pos=self._sync, size=self._sync)
        self.label = Label(text=text, color=self._fg, font_size=dp(13),
                           bold=selected, size_hint=(None, 1),
                           halign="center", valign="middle")
        self.label.bind(texture_size=self._fit)
        self.add_widget(self.label)

    def _fit(self, *_):
        self.label.width = self.label.texture_size[0]
        self.width = self.label.width + dp(24)

    def set_selected(self, selected):
        self._sel = selected
        self._c.rgba = theme.PRIMARY_SOFT if selected else self._bg
        self.label.color = theme.PRIMARY if selected else self._fg
        self.label.bold = selected

    def _sync(self, *_):
        self._r.pos = self.pos
        self._r.size = self.size


class IconCircle(BoxLayout):
    """A colored circle holding an emoji/glyph — stands in for category icons."""

    def __init__(self, glyph, color, size=44, **kwargs):
        super().__init__(**kwargs)
        self.size_hint = (None, None)
        self.size = (dp(size), dp(size))
        with self.canvas.before:
            self._c = Color(color[0], color[1], color[2], 0.18)
            self._r = RoundedRectangle(radius=[dp(size / 2)])
        self.bind(pos=self._sync, size=self._sync)
        self.label = Label(text=glyph, font_size=dp(size * 0.45),
                           color=color)
        self.add_widget(self.label)

    def _sync(self, *_):
        self._r.pos = self.pos
        self._r.size = self.size
        self.label.pos = self.pos
        self.label.size = self.size


def body_label(text, color=None, size=14, bold=False, halign="left",
               **kwargs):
    """Convenience left/middle aligned label that wraps to its width."""
    lbl = Label(text=text, color=color or theme.TEXT, font_size=dp(size),
                bold=bold, halign=halign, valign="middle", markup=True,
                **kwargs)
    lbl.bind(size=lambda inst, val: setattr(inst, "text_size", val))
    return lbl


def pill_button(text, bg, fg, on_release, width=None):
    """A full-width (or fixed-width) rounded button. Reused across screens."""
    btn = TouchCard(bg=bg, radius=dp(14), orientation="horizontal",
                    size_hint=(1, None), height=dp(44), padding=dp(6))
    if width:
        btn.size_hint_x = None
        btn.width = width
    btn.add_widget(body_label("[b]%s[/b]" % text, color=fg, size=14,
                              halign="center"))
    btn.bind(on_release=lambda *_: on_release())
    return btn


class SelectableTile(TouchCard):
    """A TouchCard that toggles between a base and a selected background.

    Used by the editor's category grid and account picker rows.
    """

    def __init__(self, selected=False, sel_bg=None, base_bg=None, **kwargs):
        self._base_bg = base_bg or theme.SURFACE
        self._sel_bg = sel_bg or theme.PRIMARY_SOFT
        super().__init__(bg=self._base_bg, **kwargs)
        self.selected = selected
        self.set_bg(self._sel_bg if selected else self._base_bg)

    def set_selected(self, selected):
        self.selected = selected
        self.set_bg(self._sel_bg if selected else self._base_bg)


class Toggle(ButtonBehavior, Widget):
    """A canvas-drawn pill switch (no KivyMD)."""

    def __init__(self, value=False, on_change=None, **kwargs):
        super().__init__(**kwargs)
        self.size_hint = (None, None)
        self.size = (dp(46), dp(28))
        self.value = bool(value)
        self._on_change = on_change
        with self.canvas.before:
            self._track_color = Color(*(theme.PRIMARY if self.value
                                        else theme.SURFACE_ALT))
            self._track = RoundedRectangle(radius=[dp(14)])
            self._knob_color = Color(1, 1, 1, 1)
            self._knob = Ellipse()
        self.bind(pos=self._sync, size=self._sync)
        self.bind(on_release=self._toggle)

    def _toggle(self, *_):
        self.value = not self.value
        self._redraw()
        if self._on_change:
            self._on_change(self.value)

    def set_value(self, v):
        """Set silently (no callback) so refresh() doesn't re-write storage."""
        self.value = bool(v)
        self._redraw()

    def _redraw(self):
        self._track_color.rgba = (theme.PRIMARY if self.value
                                  else theme.SURFACE_ALT)
        self._sync()

    def _sync(self, *_):
        self._track.pos = self.pos
        self._track.size = self.size
        knob = dp(22)
        y = self.y + dp(3)
        x = (self.right - knob - dp(3)) if self.value else (self.x + dp(3))
        self._knob.pos = (x, y)
        self._knob.size = (knob, knob)


class SettingRow(TouchCard):
    """A Cashew-style settings list row with icon, text, and a trailing element.

    trailing in {"chevron", "value", "toggle", "none"}.
    """

    def __init__(self, glyph, title, subtitle=None, trailing="chevron",
                 value=None, toggle_value=False, on_tap=None, on_toggle=None,
                 icon_color=None, **kwargs):
        super().__init__(bg=theme.SURFACE, radius=theme.RADIUS_SM,
                         orientation="horizontal", size_hint_y=None,
                         height=dp(60), padding=[dp(12), dp(8)], spacing=dp(12),
                         **kwargs)
        self.add_widget(IconCircle(glyph, icon_color or theme.PRIMARY, size=40))
        mid = BoxLayout(orientation="vertical")
        mid.add_widget(body_label("[b]%s[/b]" % title, size=15))
        if subtitle:
            mid.add_widget(body_label(subtitle, color=theme.TEXT_MUTED,
                                      size=12))
        self.add_widget(mid)

        if trailing == "chevron":
            self.add_widget(body_label(">", color=theme.TEXT_MUTED, size=20,
                                       halign="right", size_hint_x=None,
                                       width=dp(24)))
        elif trailing == "value":
            self.add_widget(body_label("[b]%s[/b]" % (value or ""),
                                       color=theme.PRIMARY, size=13,
                                       halign="right", size_hint_x=None,
                                       width=dp(90)))
        elif trailing == "toggle":
            anchor = AnchorLayout(size_hint_x=None, width=dp(54))
            self.toggle = Toggle(value=toggle_value, on_change=on_toggle)
            anchor.add_widget(self.toggle)
            self.add_widget(anchor)
        else:  # "none"
            self.add_widget(Widget(size_hint_x=None, width=dp(8)))

        if on_tap and trailing != "toggle":
            self.bind(on_release=lambda *_: on_tap())
