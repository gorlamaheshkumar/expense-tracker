"""SMS review inbox - the heart of the app.

Each pending draft shows: the bank, the raw SMS, the parsed fields as chips,
a duplicate warning when relevant, and Add / Reject actions. Approving turns
the draft into a real transaction (the 'moment').
"""

from kivy.uix.screenmanager import Screen
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.scrollview import ScrollView
from kivy.metrics import dp

from .. import theme
from ..widgets.cards import (RoundedCard, TouchCard, Chip, IconCircle,
                             body_label, pill_button)
from .common import rel_time, glyph_for


class InboxScreen(Screen):
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

        # Header
        header = BoxLayout(orientation="vertical", size_hint_y=None,
                           height=dp(50), spacing=dp(2))
        header.add_widget(body_label("SMS Inbox", size=22, bold=True))
        header.add_widget(body_label(
            "Auto-detected transactions waiting for your OK",
            color=theme.TEXT_MUTED, size=13))
        c.add_widget(header)

        # Scan button
        c.add_widget(pill_button(
            "Scan SMS now", theme.PRIMARY, (1, 1, 1, 1),
            self.app.scan_sms))

        drafts = self.db.pending_drafts()
        if not drafts:
            empty = RoundedCard(bg=theme.SURFACE, radius=theme.RADIUS,
                                orientation="vertical", size_hint_y=None,
                                height=dp(120), padding=dp(20), spacing=dp(6))
            empty.add_widget(body_label("[b]All caught up![/b]", size=16,
                                        halign="center"))
            empty.add_widget(body_label(
                "No pending SMS transactions. Tap 'Scan SMS now' to check "
                "again.", color=theme.TEXT_MUTED, size=13, halign="center"))
            c.add_widget(empty)
            return

        for d in drafts:
            c.add_widget(self._draft_card(d))

    def _draft_card(self, d):
        cat = d["category"] or "Uncategorized"
        cat_color = theme.category_color(cat)
        is_dup = d["dup_of"] is not None

        card = RoundedCard(
            bg=theme.SURFACE, radius=theme.RADIUS,
            stripe=theme.bank_color(d["bank"]),
            orientation="vertical", size_hint_y=None,
            padding=[dp(16), dp(14)], spacing=dp(10))
        card.bind(minimum_height=card.setter("height"))

        # Header: bank + time
        head = BoxLayout(orientation="horizontal", size_hint_y=None,
                         height=dp(40), spacing=dp(10))
        head.add_widget(IconCircle(glyph_for(cat), cat_color, size=40))
        htext = BoxLayout(orientation="vertical")
        htext.add_widget(body_label("[b]%s[/b]" % (d["merchant"] or cat),
                                    size=16))
        htext.add_widget(body_label(
            "%s  ·  %s  ·  %s" % (d["bank"], d["sender"], rel_time(d["ts"])),
            color=theme.TEXT_MUTED, size=11))
        head.add_widget(htext)
        amt_color = theme.EXPENSE if d["direction"] == "debit" else theme.INCOME
        head.add_widget(body_label(
            "[b]%s[/b]" % theme.money(d["amount"], d["direction"]),
            color=amt_color, size=18, halign="right",
            size_hint_x=None, width=dp(96)))
        card.add_widget(head)

        # Raw SMS preview
        raw = RoundedCard(bg=theme.SURFACE_ALT, radius=dp(10),
                          orientation="vertical", size_hint_y=None,
                          padding=dp(10))
        sms_lbl = body_label('"%s"' % d["raw"], color=theme.TEXT_MUTED,
                             size=12, size_hint_y=None)
        sms_lbl.bind(texture_size=lambda i, v: setattr(i, "height", v[1]))
        raw.add_widget(sms_lbl)
        raw.bind(minimum_height=raw.setter("height"))
        card.add_widget(raw)

        # Parsed chips
        chips = BoxLayout(orientation="horizontal", size_hint_y=None,
                          height=dp(34), spacing=dp(8))
        chips.add_widget(Chip(cat, color=cat_color))
        if d["account_name"]:
            chips.add_widget(Chip(d["account_name"]))
        if d["ref"]:
            chips.add_widget(Chip("Ref " + str(d["ref"])[:8]))
        chips.add_widget(BoxLayout())  # spacer pushes chips left
        card.add_widget(chips)

        # Duplicate warning
        if is_dup:
            warn = RoundedCard(bg=theme.hex_rgba("#FCEFD6"), radius=dp(10),
                               orientation="horizontal", size_hint_y=None,
                               height=dp(40), padding=[dp(10), dp(6)],
                               spacing=dp(8))
            warn.add_widget(body_label(
                "[b]![/b]", color=theme.WARNING, size=16,
                size_hint_x=None, width=dp(16)))
            warn.add_widget(body_label(
                "Looks like a duplicate of an existing transaction",
                color=theme.hex_rgba("#8A6516"), size=12))
            card.add_widget(warn)

        # Actions
        actions = BoxLayout(orientation="horizontal", size_hint_y=None,
                            height=dp(44), spacing=dp(10))
        actions.add_widget(pill_button(
            "Reject", theme.SURFACE_ALT, theme.TEXT_MUTED,
            lambda did=d["id"]: self._reject(did)))
        add_label = "Add anyway" if is_dup else "Add transaction"
        actions.add_widget(pill_button(
            add_label, theme.INCOME if not is_dup else theme.WARNING,
            (1, 1, 1, 1), lambda did=d["id"]: self._approve(did)))
        card.add_widget(actions)
        return card

    def _approve(self, draft_id):
        # Route into the editor pre-filled from the draft, so the user can
        # tweak fields before saving (Cashew-style), instead of a bare approve.
        d = self.db.draft(draft_id)
        if d:
            self.app.open_editor("draft", draft=d)

    def _reject(self, draft_id):
        self.db.reject_draft(draft_id)
        self.app.toast("Dismissed")
        self.app.refresh_badge()
        self.refresh()
