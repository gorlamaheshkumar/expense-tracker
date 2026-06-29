"""Home dashboard, Cashew-style.

Net worth -> spending chart -> SMS banner -> wallet strip -> top categories
-> unified 'all transactions' ledger. Rows + wallet cards tap into the editor
/ accounts. Built on the existing widget kit.
"""

from kivy.uix.screenmanager import Screen
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.scrollview import ScrollView
from kivy.metrics import dp

from .. import theme
from ..widgets.cards import (RoundedCard, TouchCard, IconCircle, body_label)
from ..widgets.charts import BarChart
from .common import rel_time, glyph_for, _month_start
from .budget import ProgressTrack


def transaction_row(tx, on_tap=None):
    """A tappable transaction list row (shared by Home and Transactions)."""
    cat = tx["category"] or "Uncategorized"
    color = theme.category_color(cat)
    row = TouchCard(bg=theme.SURFACE, radius=theme.RADIUS_SM,
                    orientation="horizontal", size_hint_y=None,
                    height=dp(66), padding=[dp(10), dp(8)], spacing=dp(10))
    row.add_widget(IconCircle(glyph_for(cat), color, size=42))

    mid = BoxLayout(orientation="vertical", spacing=dp(2))
    merchant = tx["merchant"] or cat
    mid.add_widget(body_label("[b]%s[/b]" % merchant, size=15))
    src = "SMS" if tx["source"] == "sms" else "Manual"
    acct = tx["account_name"] or "No account"
    sub = "%s  -  %s  -  %s" % (acct, rel_time(tx["ts"]), src)
    mid.add_widget(body_label(sub, color=theme.TEXT_MUTED, size=12))
    row.add_widget(mid)

    amt_color = theme.EXPENSE if tx["direction"] == "debit" else theme.INCOME
    row.add_widget(body_label(
        "[b]%s[/b]" % theme.money(tx["amount"], tx["direction"]),
        color=amt_color, size=15, halign="right",
        size_hint_x=None, width=dp(92)))
    if on_tap:
        row.bind(on_release=lambda *_: on_tap())
    return row


def _circle_button(glyph, fg, bg, on_release, size=32):
    """A small tappable circle (radius == half size) e.g. gear / plus."""
    btn = TouchCard(bg=bg, radius=size / 2, size_hint=(None, None),
                    size=(dp(size), dp(size)), padding=0,
                    pos_hint={"center_y": 0.5})
    btn.add_widget(body_label("[b]%s[/b]" % glyph, color=fg, size=size * 0.5,
                              halign="center"))
    btn.bind(on_release=lambda *_: on_release())
    return btn


def wallet_card(app, acct):
    bank = acct["bank"] or "OTHER"
    color = theme.bank_color(bank)
    card = TouchCard(bg=theme.SURFACE, radius=theme.RADIUS_SM, stripe=color,
                     orientation="vertical", size_hint=(None, 1),
                     width=dp(154), padding=[dp(14), dp(12)], spacing=dp(4))
    top = BoxLayout(orientation="horizontal", size_hint_y=None, height=dp(38),
                    spacing=dp(8))
    top.add_widget(IconCircle(bank[0], color, size=34))
    nm = BoxLayout(orientation="vertical")
    nm.add_widget(body_label("[b]%s[/b]" % acct["name"], size=13))
    nm.add_widget(body_label(bank, color=theme.TEXT_MUTED, size=10))
    top.add_widget(nm)
    card.add_widget(top)

    bal = acct["balance"] or 0
    bal_color = theme.EXPENSE if bal < 0 else theme.TEXT
    card.add_widget(body_label("[b]%s[/b]" % theme.money(bal),
                               color=bal_color, size=18, size_hint_y=None,
                               height=dp(26)))
    card.add_widget(body_label("%d txns this month" % acct["month_count"],
                               color=theme.TEXT_MUTED, size=11,
                               size_hint_y=None, height=dp(16)))
    card.bind(on_release=lambda *_: app.go("accounts"))
    return card


def cat_row(cat, spent, max_spent):
    color = theme.category_color(cat)
    row = BoxLayout(orientation="horizontal", size_hint_y=None, height=dp(42),
                    spacing=dp(10))
    row.add_widget(IconCircle(glyph_for(cat), color, size=32))
    mid = BoxLayout(orientation="vertical", spacing=dp(4))
    mid.add_widget(body_label("[b]%s[/b]" % cat, size=13, size_hint_y=None,
                              height=dp(16)))
    frac = (spent / max_spent) if max_spent else 0
    mid.add_widget(ProgressTrack(frac, color))
    row.add_widget(mid)
    row.add_widget(body_label("[b]%s[/b]" % theme.money(spent), size=13,
                              halign="right", size_hint_x=None, width=dp(82)))
    return row


class HomeScreen(Screen):
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
        app = self.app
        c = self.container
        c.clear_widgets()

        # 1. Header: greeting + settings gear
        header = BoxLayout(orientation="horizontal", size_hint_y=None,
                           height=dp(48), spacing=dp(8))
        greet = BoxLayout(orientation="vertical")
        greet.add_widget(body_label("Hello, Mahesh", size=22, bold=True))
        greet.add_widget(body_label("Here's your money today",
                                    color=theme.TEXT_MUTED, size=12))
        header.add_widget(greet)
        header.add_widget(_circle_button("G", theme.PRIMARY, theme.PRIMARY_SOFT,
                                          lambda: app.go("settings"), size=40))
        c.add_widget(header)

        # 2. Net worth card
        nw = self.db.net_worth()
        card = RoundedCard(bg=theme.PRIMARY, radius=theme.RADIUS,
                           orientation="vertical", size_hint_y=None,
                           height=dp(140), padding=dp(18), spacing=dp(4))
        card.add_widget(body_label("Net worth", color=theme.ON_PRIMARY_MUTED,
                                   size=13, size_hint_y=None, height=dp(20)))
        card.add_widget(body_label("[b]%s[/b]" % theme.money(nw["net"]),
                                   color=theme.ON_PRIMARY, size=30,
                                   size_hint_y=None, height=dp(42)))
        card.add_widget(body_label(
            "Assets %s    Owed %s" % (theme.money(nw["assets"]),
                                      theme.money(abs(nw["liabilities"]))),
            color=theme.ON_PRIMARY_MUTED, size=12, size_hint_y=None,
            height=dp(20)))
        c.add_widget(card)

        # 3. Spending chart
        spend = RoundedCard(bg=theme.SURFACE, radius=theme.RADIUS,
                            orientation="vertical", size_hint_y=None,
                            padding=dp(16), spacing=dp(8))
        spend.bind(minimum_height=spend.setter("height"))
        shdr = BoxLayout(orientation="horizontal", size_hint_y=None,
                         height=dp(24))
        shdr.add_widget(body_label("[b]Spending[/b]", size=16))
        shdr.add_widget(body_label("Last 6 months", color=theme.TEXT_MUTED,
                                   size=12, halign="right"))
        spend.add_widget(shdr)
        spend.add_widget(BarChart(self.db.monthly_spend_series(6), height=160))
        c.add_widget(spend)

        # 4. SMS banner (conditional)
        pending = self.db.pending_count()
        if pending:
            banner = TouchCard(bg=theme.BANNER_BG, radius=theme.RADIUS_SM,
                               orientation="horizontal", size_hint_y=None,
                               height=dp(58), padding=[dp(14), dp(8)],
                               spacing=dp(10))
            banner.add_widget(IconCircle("S", theme.INCOME, size=38))
            txt = BoxLayout(orientation="vertical")
            txt.add_widget(body_label("[b]%d new from SMS[/b]" % pending,
                                      color=theme.hex_rgba("#1B5E20"), size=14))
            txt.add_widget(body_label("Tap to review & add",
                                      color=theme.hex_rgba("#3C7A40"),
                                      size=12))
            banner.add_widget(txt)
            banner.add_widget(body_label("[b]>[/b]", color=theme.INCOME,
                                         size=18, halign="right",
                                         size_hint_x=None, width=dp(24)))
            banner.bind(on_release=lambda *_: app.go("inbox"))
            c.add_widget(banner)

        # 5. Accounts strip (horizontal scroll)
        c.add_widget(body_label("[b]Accounts[/b]", size=16, size_hint_y=None,
                                height=dp(26)))
        strip_scroll = ScrollView(size_hint_y=None, height=dp(126),
                                  do_scroll_x=True, do_scroll_y=False,
                                  bar_width=0)
        strip = BoxLayout(orientation="horizontal", size_hint_x=None,
                          spacing=dp(12))
        strip.bind(minimum_width=strip.setter("width"))
        for acct in self.db.accounts_with_month_counts():
            strip.add_widget(wallet_card(app, acct))
        strip_scroll.add_widget(strip)
        c.add_widget(strip_scroll)

        # 6. Top categories this month (only if there's spend)
        spent_map = self.db.spent_by_category(_month_start())
        spent_items = sorted(spent_map.items(), key=lambda kv: kv[1],
                             reverse=True)[:4]
        if spent_items:
            c.add_widget(body_label("[b]Top categories[/b]", size=16,
                                    size_hint_y=None, height=dp(26)))
            cats_card = RoundedCard(bg=theme.SURFACE, radius=theme.RADIUS,
                                    orientation="vertical", size_hint_y=None,
                                    padding=[dp(14), dp(12)], spacing=dp(8))
            cats_card.bind(minimum_height=cats_card.setter("height"))
            max_spent = spent_items[0][1] or 1
            for cat, spent in spent_items:
                cats_card.add_widget(cat_row(cat, spent, max_spent))
            c.add_widget(cats_card)

        # 7. All transactions header + list
        hdr = BoxLayout(orientation="horizontal", size_hint_y=None,
                        height=dp(34), spacing=dp(8))
        hdr.add_widget(body_label("[b]All transactions[/b]", size=16))
        hdr.add_widget(_circle_button("+", theme.ON_PRIMARY, theme.PRIMARY,
                                      lambda: app.open_editor("create"),
                                      size=32))
        seeall = TouchCard(bg=(0, 0, 0, 0), size_hint=(None, None),
                           size=(dp(58), dp(32)), padding=0,
                           pos_hint={"center_y": 0.5})
        seeall.add_widget(body_label("See all", color=theme.PRIMARY, size=12,
                                     halign="right"))
        seeall.bind(on_release=lambda *_: app.go("transactions"))
        hdr.add_widget(seeall)
        c.add_widget(hdr)

        txns = self.db.recent_transactions(12)
        if not txns:
            c.add_widget(body_label("No transactions yet. Scan your SMS or "
                                    "tap +", color=theme.TEXT_MUTED, size=13,
                                    size_hint_y=None, height=dp(40)))
        for tx in txns:
            c.add_widget(transaction_row(
                tx, on_tap=lambda t=tx: app.open_editor("edit", tx=t)))
