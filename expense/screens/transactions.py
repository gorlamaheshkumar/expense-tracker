"""Transactions: the full ledger across all banks, date-grouped + filterable."""

import time

from kivy.uix.screenmanager import Screen
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.scrollview import ScrollView
from kivy.metrics import dp

from .. import theme
from ..widgets.cards import Chip, body_label, pill_button
from .home import transaction_row


def _day_bounds():
    t = time.localtime()
    today0 = int(time.mktime((t.tm_year, t.tm_mon, t.tm_mday,
                              0, 0, 0, 0, 0, -1)))
    return today0, today0 - 86400


def group_by_date(rows):
    """Bucket ts-DESC rows into [(header, [rows])], newest group first."""
    today0, yest0 = _day_bounds()
    groups = {}
    order = []
    for r in rows:
        ts = r["ts"]
        if ts >= today0:
            key = "Today"
        elif ts >= yest0:
            key = "Yesterday"
        else:
            key = time.strftime("%d %b %Y", time.localtime(ts))
        if key not in groups:
            groups[key] = []
            order.append(key)
        groups[key].append(r)
    return [(k, groups[k]) for k in order]


def DateHeader(text):
    return body_label("[b]%s[/b]" % text, color=theme.TEXT_MUTED, size=12,
                      size_hint_y=None, height=dp(24))


class TransactionsScreen(Screen):
    def __init__(self, app, **kwargs):
        super().__init__(**kwargs)
        self.app = app
        self.db = app.db
        self._active = "all"     # "all" | "income" | "expense" | ("acct", id)
        root = BoxLayout(orientation="vertical")
        self.scroll = ScrollView()
        self.container = BoxLayout(orientation="vertical", size_hint_y=None,
                                   padding=[dp(16), dp(16), dp(16), dp(24)],
                                   spacing=dp(12))
        self.container.bind(minimum_height=self.container.setter("height"))
        self.scroll.add_widget(self.container)
        root.add_widget(self.scroll)
        self.add_widget(root)

    def on_pre_enter(self, *_):
        self.refresh()

    def _set_filter(self, key):
        self._active = key
        self.refresh()

    def _query(self):
        a = self._active
        if a == "income":
            return self.db.all_transactions(direction="credit")
        if a == "expense":
            return self.db.all_transactions(direction="debit")
        if isinstance(a, tuple) and a[0] == "acct":
            return self.db.all_transactions(account_id=a[1])
        return self.db.all_transactions()

    def refresh(self):
        app = self.app
        c = self.container
        c.clear_widgets()

        # Title + Add
        top = BoxLayout(orientation="horizontal", size_hint_y=None,
                        height=dp(38), spacing=dp(8))
        top.add_widget(body_label("Transactions", size=22, bold=True))
        top.add_widget(pill_button("+ Add", theme.PRIMARY, theme.ON_PRIMARY,
                                   lambda: app.open_editor("create"),
                                   width=dp(96)))
        c.add_widget(top)

        # Filter chips (horizontal scroll)
        chip_scroll = ScrollView(size_hint_y=None, height=dp(40),
                                 do_scroll_x=True, do_scroll_y=False,
                                 bar_width=0)
        chips = BoxLayout(orientation="horizontal", size_hint_x=None,
                          spacing=dp(8), padding=[0, dp(4)])
        chips.bind(minimum_width=chips.setter("width"))

        defs = [("All", "all"), ("Income", "income"), ("Expense", "expense")]
        for acct in self.db.accounts():
            defs.append((acct["name"], ("acct", acct["id"])))
        for label, key in defs:
            selected = (self._active == key)
            chip = Chip(label, selected=selected)
            chip.bind(on_release=lambda *_a, k=key: self._set_filter(k))
            chips.add_widget(chip)
        chip_scroll.add_widget(chips)
        c.add_widget(chip_scroll)

        # Grouped rows
        rows = self._query()
        if not rows:
            c.add_widget(body_label("No transactions match this filter.",
                                    color=theme.TEXT_MUTED, size=13,
                                    size_hint_y=None, height=dp(40)))
            return
        for header, group in group_by_date(rows):
            c.add_widget(DateHeader(header))
            for tx in group:
                c.add_widget(transaction_row(
                    tx, on_tap=lambda t=tx: app.open_editor("edit", tx=t)))
