"""Pure-Kivy canvas charts (no external plotting lib)."""

from kivy.uix.widget import Widget
from kivy.uix.label import Label
from kivy.graphics import Color, RoundedRectangle
from kivy.metrics import dp

from .. import theme


class BarChart(Widget):
    """A simple monthly-spend bar chart.

    data: list[(label, value)] (e.g. from db.monthly_spend_series(6)).
    The last bar (current month) is full-alpha; older bars are faded.
    Value labels sit above each bar; month labels below the baseline.
    """

    def __init__(self, data, color=None, height=160, value_fmt=None, **kwargs):
        super().__init__(**kwargs)
        self.size_hint_y = None
        self.height = dp(height)
        self.data = list(data or [])
        self.color = color or theme.PRIMARY
        self.value_fmt = value_fmt or (lambda v: theme.money(v))
        self.max_v = max((v for _, v in self.data), default=0) or 1

        self._bars = []          # (rect, value)
        self._val_labels = []
        self._x_labels = []
        n = len(self.data)
        with self.canvas:
            for i, (_, val) in enumerate(self.data):
                last = (i == n - 1)
                c = self.color if last else (
                    self.color[0], self.color[1], self.color[2], 0.45)
                Color(*c)
                rect = RoundedRectangle(radius=[dp(6)])
                self._bars.append((rect, val))
        for i, (label, val) in enumerate(self.data):
            vlbl = Label(text="" if val == 0 else self.value_fmt(val),
                         font_size=dp(9), color=theme.TEXT_MUTED,
                         size_hint=(None, None), halign="center",
                         valign="middle")
            xlbl = Label(text=label, font_size=dp(11), color=theme.TEXT_MUTED,
                         size_hint=(None, None), halign="center",
                         valign="bottom")
            self.add_widget(vlbl)
            self.add_widget(xlbl)
            self._val_labels.append(vlbl)
            self._x_labels.append(xlbl)
        self.bind(pos=self._sync, size=self._sync)

    def _sync(self, *_):
        n = len(self.data)
        if n == 0:
            return
        top_band = dp(16)
        bottom_band = dp(18)
        baseline = self.y + bottom_band
        plot_h = max(self.height - top_band - bottom_band, dp(1))
        slot = self.width / n
        bar_w = min(slot * 0.5, dp(28))
        for i, (rect, val) in enumerate(self._bars):
            cx = self.x + slot * i + slot / 2
            bh = max(plot_h * (val / self.max_v), dp(2))
            rect.size = (bar_w, bh)
            rect.pos = (cx - bar_w / 2, baseline)

            vlbl = self._val_labels[i]
            vlbl.size = (slot, top_band)
            vlbl.text_size = vlbl.size
            vlbl.pos = (self.x + slot * i, baseline + bh + dp(1))

            xlbl = self._x_labels[i]
            xlbl.size = (slot, bottom_band)
            xlbl.text_size = xlbl.size
            xlbl.pos = (self.x + slot * i, self.y)
