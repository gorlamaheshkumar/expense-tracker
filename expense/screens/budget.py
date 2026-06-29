"""Budget overview: monthly limits vs spend, per-category progress bars."""

from kivy.uix.screenmanager import Screen
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.widget import Widget
from kivy.graphics import Color, RoundedRectangle
from kivy.metrics import dp

from .. import theme
from ..widgets.cards import RoundedCard, body_label
from .common import _month_start


class ProgressTrack(Widget):
    """A rounded progress bar; fill turns red when fraction > 1."""

    def __init__(self, fraction, color, **kwargs):
        super().__init__(**kwargs)
        self.size_hint_y = None
        self.height = dp(10)
        self.fraction = max(0.0, fraction)
        self.color = color
        with self.canvas:
            Color(*theme.SURFACE_ALT)
            self._track = RoundedRectangle(radius=[dp(5)])
            over = self.fraction > 1.0
            fill = theme.EXPENSE if over else self.color
            Color(*fill)
            self._fill = RoundedRectangle(radius=[dp(5)])
        self.bind(pos=self._sync, size=self._sync)

    def _sync(self, *_):
        self._track.pos = self.pos
        self._track.size = self.size
        self._fill.pos = self.pos
        self._fill.size = (self.width * min(self.fraction, 1.0), self.height)


class BudgetScreen(Screen):
    def __init__(self, app, **kwargs):
        super().__init__(**kwargs)
        self.app = app
        self.db = app.db
        root = BoxLayout(orientation="vertical")
        self.scroll = ScrollView()
        self.container = BoxLayout(orientation="vertical", size_hint_y=None,
                                   padding=[dp(16), dp(16), dp(16), dp(24)],
                                   spacing=dp(14))
        self.container.bind(minimum_height=self.container.setter("height"))
        self.scroll.add_widget(self.container)
        root.add_widget(self.scroll)
        self.add_widget(root)

    def on_pre_enter(self, *_):
        self.refresh()

    def refresh(self):
        c = self.container
        c.clear_widgets()
        c.add_widget(body_label("Budgets", size=22, bold=True,
                                size_hint_y=None, height=dp(36)))

        since = _month_start()
        spent_map = self.db.spent_by_category(since)
        budgets = self.db.budgets()
        total_limit = sum(b["limit_amount"] for b in budgets) or 1
        total_spent = sum(spent_map.get(b["category"], 0) for b in budgets)

        # Summary card
        summary = RoundedCard(bg=theme.PRIMARY, radius=theme.RADIUS,
                              orientation="vertical", size_hint_y=None,
                              height=dp(110), padding=dp(18), spacing=dp(6))
        summary.add_widget(body_label("This month", color=(1, 1, 1, 0.85),
                                      size=13, size_hint_y=None, height=dp(18)))
        summary.add_widget(body_label(
            "[b]%s[/b] of %s" % (theme.money(total_spent),
                                 theme.money(total_limit)),
            color=(1, 1, 1, 1), size=24, size_hint_y=None, height=dp(34)))
        frac = total_spent / total_limit
        track = ProgressTrack(frac, theme.hex_rgba("#FFFFFF"))
        summary.add_widget(track)
        c.add_widget(summary)

        # Per-category
        for b in budgets:
            cat = b["category"]
            spent = spent_map.get(cat, 0)
            limit = b["limit_amount"] or 1
            frac = spent / limit
            over = frac > 1.0
            color = theme.category_color(cat)

            row = RoundedCard(bg=theme.SURFACE, radius=theme.RADIUS_SM,
                              orientation="vertical", size_hint_y=None,
                              height=dp(74), padding=[dp(14), dp(10)],
                              spacing=dp(8))
            top = BoxLayout(orientation="horizontal", size_hint_y=None,
                            height=dp(20))
            top.add_widget(body_label("[b]%s[/b]" % cat, size=14))
            amt_color = theme.EXPENSE if over else theme.TEXT_MUTED
            top.add_widget(body_label(
                "%s / %s" % (theme.money(spent), theme.money(limit)),
                color=amt_color, size=12, halign="right"))
            row.add_widget(top)
            row.add_widget(ProgressTrack(frac, color))
            c.add_widget(row)
