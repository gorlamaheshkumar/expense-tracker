"""A custom on-screen numeric keypad for the transaction editor.

Pure Kivy (no KivyMD): each key is a TouchCard so backgrounds self-sync.
Owns the raw amount string; the editor owns display + float conversion.
"""

from kivy.uix.boxlayout import BoxLayout
from kivy.metrics import dp

from .. import theme
from .cards import TouchCard, body_label


class NumberPad(BoxLayout):
    def __init__(self, on_change=None, **kwargs):
        super().__init__(orientation="vertical", **kwargs)
        self.size_hint_y = None
        self.height = dp(232)
        self.spacing = dp(8)
        self._on_change = on_change
        self._raw = ""
        rows = [["7", "8", "9"], ["4", "5", "6"],
                ["1", "2", "3"], [".", "0", "<"]]
        for r in rows:
            row = BoxLayout(orientation="horizontal", spacing=dp(8),
                            size_hint_y=None, height=dp(54))
            for token in r:
                row.add_widget(self._key(token))
            self.add_widget(row)

    def _key(self, token):
        fg = theme.TEXT_MUTED if token == "<" else theme.TEXT
        btn = TouchCard(bg=theme.SURFACE_ALT, radius=dp(14),
                        orientation="horizontal", size_hint=(1, 1))
        btn.add_widget(body_label("[b]%s[/b]" % token, color=fg, size=20,
                                  halign="center"))
        btn.bind(on_release=lambda *_a, t=token: self._press(t))
        return btn

    def _press(self, token):
        if token == "<":
            self._raw = self._raw[:-1]
        elif token == ".":
            if "." not in self._raw:
                if self._raw == "":
                    self._raw = "0"
                self._raw += "."
        else:  # a digit
            if "." in self._raw:
                _, _, dec = self._raw.partition(".")
                if len(dec) >= 2:
                    return
            else:
                if len(self._raw) >= 9:
                    return
            if self._raw == "0":      # no leading zeros (unless "0.")
                self._raw = ""
            self._raw += token
        if self._on_change:
            self._on_change(self._raw)

    def set_value(self, s):
        """Load an existing amount into the pad WITHOUT firing on_change."""
        if s is None or s == "":
            self._raw = ""
            return
        try:
            f = float(s)
        except (ValueError, TypeError):
            self._raw = ""
            return
        if f == int(f):
            self._raw = str(int(f))
        else:
            self._raw = ("%.2f" % f).rstrip("0").rstrip(".")

    @property
    def raw(self):
        return self._raw
