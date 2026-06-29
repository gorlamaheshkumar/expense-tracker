"""Accounts: cards/UPI/bank with bank-colored stripe + SMS sender mapping."""

from kivy.uix.screenmanager import Screen
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.scrollview import ScrollView
from kivy.metrics import dp

from .. import theme
from ..widgets.cards import (RoundedCard, TouchCard, Chip, IconCircle,
                             body_label)


TYPE_LABEL = {"bank": "Bank account", "card": "Credit card", "upi": "UPI"}


def back_header(title, on_back):
    """A top bar with a '<' back button and a title (for off-bar screens)."""
    header = BoxLayout(orientation="horizontal", size_hint_y=None,
                       height=dp(40), spacing=dp(8))
    back = TouchCard(bg=(0, 0, 0, 0), size_hint=(None, 1), width=dp(36),
                     padding=0)
    back.add_widget(body_label("[b]<[/b]", size=22))
    back.bind(on_release=lambda *_: on_back())
    header.add_widget(back)
    header.add_widget(body_label("[b]%s[/b]" % title, size=22))
    return header


class AccountsScreen(Screen):
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
        c.add_widget(back_header(
            "Accounts", lambda: self.app.go(self.app._accounts_return)))

        for a in self.db.accounts():
            bank = a["bank"] or "OTHER"
            color = theme.bank_color(bank)
            card = RoundedCard(bg=theme.SURFACE, radius=theme.RADIUS,
                               stripe=color, orientation="vertical",
                               size_hint_y=None, padding=[dp(18), dp(14)],
                               spacing=dp(8))
            card.bind(minimum_height=card.setter("height"))

            top = BoxLayout(orientation="horizontal", size_hint_y=None,
                            height=dp(44), spacing=dp(10))
            top.add_widget(IconCircle(bank[0], color, size=42))
            mid = BoxLayout(orientation="vertical")
            mid.add_widget(body_label("[b]%s[/b]" % a["name"], size=16))
            tail = ("•••• " + a["last4"]) if a["last4"] else ""
            mid.add_widget(body_label(
                "%s  %s" % (TYPE_LABEL.get(a["type"], a["type"]), tail),
                color=theme.TEXT_MUTED, size=12))
            top.add_widget(mid)

            bal = a["balance"] or 0
            bal_color = theme.EXPENSE if bal < 0 else theme.TEXT
            top.add_widget(body_label(
                "[b]%s[/b]" % theme.money(bal), color=bal_color, size=16,
                halign="right", size_hint_x=None, width=dp(100)))
            card.add_widget(top)

            # SMS senders mapped to this account
            senders = (a["sms_senders"] or "").split(",")
            chips = BoxLayout(orientation="horizontal", size_hint_y=None,
                              height=dp(34), spacing=dp(8))
            chips.add_widget(body_label("Reads SMS from:", color=theme.TEXT_MUTED,
                                        size=11, size_hint_x=None, width=dp(96)))
            for s in senders[:3]:
                if s.strip():
                    chips.add_widget(Chip(s.strip()))
            chips.add_widget(BoxLayout())
            card.add_widget(chips)
            c.add_widget(card)
