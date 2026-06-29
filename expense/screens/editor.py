"""Transaction editor - the linchpin, modeled on Cashew's add/edit page.

Three modes via load(mode, draft=, tx=):
  create -> blank manual entry
  edit   -> pre-filled existing transaction (+ Delete)
  draft  -> pre-filled from an SMS draft; Save creates tx + approves draft
A pinned NumberPad drives the amount; category grid + account picker below.
"""

import time

from kivy.uix.screenmanager import Screen
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.gridlayout import GridLayout
from kivy.uix.anchorlayout import AnchorLayout
from kivy.uix.textinput import TextInput
from kivy.uix.popup import Popup
from kivy.metrics import dp

from .. import theme
from ..widgets.cards import (RoundedCard, TouchCard, Chip, IconCircle,
                             SelectableTile, body_label, pill_button)
from ..widgets.keypad import NumberPad
from .common import absolute_date, glyph_for

TITLES = {"create": "New transaction", "edit": "Edit transaction",
          "draft": "Review SMS"}


def _fmt_amount(v):
    if not v:
        return ""
    f = float(v)
    if f == int(f):
        return str(int(f))
    return ("%.2f" % f).rstrip("0").rstrip(".")


class EditorScreen(Screen):
    def __init__(self, app, **kwargs):
        super().__init__(**kwargs)
        self.app = app
        self.db = app.db
        self.mode = "create"
        self.draft = None
        self.tx_id = None

    # ---- state loading ----
    def load(self, mode, draft=None, tx=None):
        self.mode = mode
        self.draft = draft
        self.tx_id = None
        self.ref = ""
        if mode == "edit" and tx is not None:
            self.tx_id = tx["id"]
            self._amount_str = _fmt_amount(tx["amount"])
            self.direction = tx["direction"]
            self._title = tx["merchant"] or ""
            self.category = tx["category"] or "Uncategorized"
            self.account_id = tx["account_id"]
            self.ts = tx["ts"]
            self._note = tx["note"] or ""
            self.ref = tx["ref"] or ""
        elif mode == "draft" and draft is not None:
            self._amount_str = _fmt_amount(draft["amount"])
            self.direction = draft["direction"]
            self._title = draft["merchant"] or ""
            self.category = draft["category"] or "Uncategorized"
            self.account_id = draft["account_id"]
            self.ts = draft["ts"] or int(time.time())
            self._note = ""
            self.ref = draft["ref"] or ""
        else:  # create
            accts = self.db.accounts()
            self._amount_str = ""
            self.direction = "debit"
            self._title = ""
            self.category = "Uncategorized"
            self.account_id = accts[0]["id"] if accts else None
            self.ts = int(time.time())
            self._note = ""
        self._build()

    # ---- tree ----
    def _build(self):
        self.clear_widgets()
        root = BoxLayout(orientation="vertical")

        # Top bar: back / title / delete
        topbar = BoxLayout(orientation="horizontal", size_hint_y=None,
                           height=dp(52), padding=[dp(10), dp(8)],
                           spacing=dp(8))
        back = TouchCard(bg=(0, 0, 0, 0), size_hint=(None, 1), width=dp(36),
                         padding=0)
        back.add_widget(body_label("[b]<[/b]", size=22))
        back.bind(on_release=lambda *_: self.app.go(self.app._editor_return))
        topbar.add_widget(back)
        topbar.add_widget(body_label("[b]%s[/b]" % TITLES.get(self.mode,
                                     "Transaction"), size=18))
        if self.mode == "edit":
            delete = TouchCard(bg=theme.hex_rgba("#CA5A5A", 0.14),
                               radius=dp(12), size_hint=(None, 1), width=dp(72),
                               padding=dp(4))
            delete.add_widget(body_label("[b]Delete[/b]", color=theme.EXPENSE,
                                         size=12, halign="center"))
            delete.bind(on_release=lambda *_: self._confirm_delete())
            topbar.add_widget(delete)
        else:
            topbar.add_widget(BoxLayout(size_hint_x=None, width=dp(72)))
        root.add_widget(topbar)

        # Amount block: direction toggle + big readout
        amt_card = RoundedCard(bg=theme.SURFACE, radius=theme.RADIUS,
                               orientation="vertical", size_hint_y=None,
                               height=dp(126), padding=dp(14), spacing=dp(8))
        dirow = BoxLayout(orientation="horizontal", size_hint_y=None,
                          height=dp(34), spacing=dp(8))
        self.exp_chip = Chip("Expense", selected=(self.direction == "debit"))
        self.inc_chip = Chip("Income", selected=(self.direction == "credit"))
        self.exp_chip.bind(on_release=lambda *_: self._set_direction("debit"))
        self.inc_chip.bind(on_release=lambda *_: self._set_direction("credit"))
        dirow.add_widget(self.exp_chip)
        dirow.add_widget(self.inc_chip)
        dirow.add_widget(BoxLayout())
        amt_card.add_widget(dirow)
        color = theme.EXPENSE if self.direction == "debit" else theme.INCOME
        self.readout = body_label(
            "[b]%s%s[/b]" % (theme.CURRENCY, self._amount_str or "0"),
            color=color, size=40, halign="center")
        amt_card.add_widget(self.readout)
        root.add_widget(amt_card)

        # Scrollable form
        scroll = ScrollView()
        self.form = BoxLayout(orientation="vertical", size_hint_y=None,
                              padding=[dp(16), dp(8)], spacing=dp(10))
        self.form.bind(minimum_height=self.form.setter("height"))
        scroll.add_widget(self.form)
        root.add_widget(scroll)
        self._populate_form()

        # Pinned number pad
        self.pad = NumberPad(on_change=self._on_amount_change)
        self.pad.set_value(self._amount_str)
        pad_wrap = BoxLayout(orientation="vertical", size_hint_y=None,
                             height=dp(232), padding=[dp(12), 0])
        pad_wrap.add_widget(self.pad)
        root.add_widget(pad_wrap)

        # Save bar
        save_wrap = BoxLayout(orientation="vertical", size_hint_y=None,
                              height=dp(60), padding=[dp(16), dp(8)])
        save_wrap.add_widget(pill_button("Save transaction", theme.PRIMARY,
                                          theme.ON_PRIMARY, self._save))
        root.add_widget(save_wrap)

        self.add_widget(root)

    # ---- form sections ----
    def _section(self, text):
        return body_label(text, color=theme.TEXT_MUTED, size=11,
                          size_hint_y=None, height=dp(18))

    def _field(self, hint, text):
        card = RoundedCard(bg=theme.SURFACE_ALT, radius=dp(12),
                           size_hint_y=None, height=dp(46),
                           padding=[dp(12), dp(4)])
        ti = TextInput(text=text or "", hint_text=hint, multiline=False,
                       background_normal="", background_active="",
                       background_color=(0, 0, 0, 0),
                       foreground_color=theme.TEXT, cursor_color=theme.PRIMARY,
                       font_size=dp(15), padding=[0, dp(9)])
        card.add_widget(ti)
        return card, ti

    def _populate_form(self):
        f = self.form
        f.clear_widgets()

        if self.mode == "draft" and self.draft:
            raw = RoundedCard(bg=theme.SURFACE_ALT, radius=dp(10),
                              orientation="vertical", size_hint_y=None,
                              padding=dp(10))
            lbl = body_label('"%s"' % self.draft["raw"],
                             color=theme.TEXT_MUTED, size=12, size_hint_y=None)
            lbl.bind(texture_size=lambda i, v: setattr(i, "height", v[1]))
            raw.add_widget(lbl)
            raw.bind(minimum_height=raw.setter("height"))
            f.add_widget(raw)
            if self.draft["dup_of"]:
                warn = RoundedCard(bg=theme.DUP_BG, radius=dp(10),
                                   orientation="horizontal", size_hint_y=None,
                                   height=dp(40), padding=[dp(10), dp(6)],
                                   spacing=dp(8))
                warn.add_widget(body_label("[b]![/b]", color=theme.WARNING,
                                           size=16, size_hint_x=None,
                                           width=dp(16)))
                warn.add_widget(body_label(
                    "Looks like a duplicate of an existing transaction",
                    color=theme.hex_rgba("#8A6516"), size=12))
                f.add_widget(warn)

        f.add_widget(self._section("TITLE"))
        card, self.title_ti = self._field("e.g. Swiggy, Salary", self._title)
        f.add_widget(card)

        f.add_widget(self._section("CATEGORY"))
        f.add_widget(self._category_grid())

        f.add_widget(self._section("ACCOUNT"))
        self._account_rows(f)

        f.add_widget(self._section("DATE"))
        f.add_widget(self._date_control())

        f.add_widget(self._section("NOTE"))
        card2, self.note_ti = self._field("Add a note (optional)", self._note)
        f.add_widget(card2)

    def _category_grid(self):
        grid = GridLayout(cols=4, size_hint_y=None, spacing=dp(10))
        grid.bind(minimum_height=grid.setter("height"))
        self._cat_tiles = {}
        for cat in self.db.categories():
            tile = SelectableTile(selected=(cat == self.category),
                                  orientation="vertical", size_hint_y=None,
                                  height=dp(92), padding=[dp(2), dp(8)],
                                  spacing=dp(2))
            wrap = AnchorLayout(size_hint_y=None, height=dp(46))
            wrap.add_widget(IconCircle(glyph_for(cat),
                                       theme.category_color(cat), size=40))
            tile.add_widget(wrap)
            tile.add_widget(body_label(cat, size=10, halign="center",
                                       size_hint_y=None, height=dp(24)))
            tile.bind(on_release=lambda *_a, c=cat: self._select_category(c))
            self._cat_tiles[cat] = tile
            grid.add_widget(tile)
        return grid

    def _account_rows(self, f):
        self._acct_tiles = {}
        entries = [(None, "No account", None)]
        for a in self.db.accounts():
            entries.append((a["id"], a["name"], a["bank"]))
        for (aid, name, bank) in entries:
            stripe = theme.bank_color(bank) if bank else None
            tile = SelectableTile(selected=(aid == self.account_id),
                                  orientation="horizontal", size_hint_y=None,
                                  height=dp(50), padding=[dp(12), dp(6)],
                                  spacing=dp(10), stripe=stripe)
            glyph = bank[0] if bank else "-"
            color = theme.bank_color(bank) if bank else theme.TEXT_MUTED
            tile.add_widget(IconCircle(glyph, color, size=34))
            tile.add_widget(body_label("[b]%s[/b]" % name, size=14))
            tile.bind(on_release=lambda *_a, i=aid: self._select_account(i))
            self._acct_tiles[aid] = tile
            f.add_widget(tile)

    def _date_control(self):
        row = BoxLayout(orientation="horizontal", size_hint_y=None,
                        height=dp(50), spacing=dp(8))
        row.add_widget(self._step_btn("-", lambda: self._step_date(-1)))
        mid = RoundedCard(bg=theme.SURFACE_ALT, radius=dp(12),
                          padding=dp(6))
        self.date_lbl = body_label(absolute_date(self.ts), size=14,
                                   halign="center")
        mid.add_widget(self.date_lbl)
        row.add_widget(mid)
        row.add_widget(self._step_btn("+", lambda: self._step_date(1)))
        return row

    def _step_btn(self, glyph, cb):
        btn = TouchCard(bg=theme.SURFACE_ALT, radius=dp(16), size_hint=(None, 1),
                        width=dp(46), padding=0)
        btn.add_widget(body_label("[b]%s[/b]" % glyph, size=18,
                                  halign="center"))
        btn.bind(on_release=lambda *_: cb())
        return btn

    # ---- interactions ----
    def _on_amount_change(self, raw):
        self._amount_str = raw
        self._update_readout()

    def _update_readout(self):
        color = theme.EXPENSE if self.direction == "debit" else theme.INCOME
        self.readout.text = "[b]%s%s[/b]" % (theme.CURRENCY,
                                             self._amount_str or "0")
        self.readout.color = color

    def _set_direction(self, d):
        self.direction = d
        self.exp_chip.set_selected(d == "debit")
        self.inc_chip.set_selected(d == "credit")
        self._update_readout()

    def _select_category(self, cat):
        self.category = cat
        for k, tile in self._cat_tiles.items():
            tile.set_selected(k == cat)

    def _select_account(self, aid):
        self.account_id = aid
        for k, tile in self._acct_tiles.items():
            tile.set_selected(k == aid)

    def _step_date(self, days):
        # Clamp to now: no future-dated transactions (they'd desync the chart,
        # date grouping, and 'X min ago' display).
        self.ts = min(int(self.ts) + days * 86400, int(time.time()))
        self.date_lbl.text = absolute_date(self.ts)

    # ---- save / delete ----
    def _save(self):
        try:
            amt = float(self._amount_str or 0)
        except ValueError:
            amt = 0
        if amt <= 0:
            self.app.toast("Enter an amount first")
            return
        title = self.title_ti.text.strip()
        note = self.note_ti.text.strip()
        if self.mode == "create":
            self.db.add_transaction(amt, self.direction, title, self.category,
                                    self.account_id, self.ts, ref="",
                                    source="manual", note=note)
        elif self.mode == "edit":
            self.db.update_transaction(self.tx_id, amt, self.direction, title,
                                       self.category, self.account_id, self.ts,
                                       note=note)
        elif self.mode == "draft":
            self.db.add_transaction(amt, self.direction, title, self.category,
                                    self.account_id, self.ts,
                                    ref=self.ref or "", source="sms",
                                    sms_id=self.draft["sms_id"], note=note)
            self.db.mark_draft_approved(self.draft["id"])
        self.app.toast("Saved %s" % theme.money(amt, self.direction))
        self.app.refresh_badge()
        self.app.go(self.app._editor_return)

    def _confirm_delete(self):
        content = BoxLayout(orientation="vertical", spacing=dp(14),
                            padding=dp(16))
        content.add_widget(body_label("Delete this transaction?", size=15,
                                      halign="center"))
        btns = BoxLayout(orientation="horizontal", spacing=dp(10),
                         size_hint_y=None, height=dp(44))
        popup = Popup(title="", separator_height=0, size_hint=(0.82, None),
                      height=dp(170), auto_dismiss=True)
        btns.add_widget(pill_button("Cancel", theme.SURFACE_ALT,
                                    theme.TEXT_MUTED, popup.dismiss))

        def do_del():
            popup.dismiss()
            self.db.delete_transaction(self.tx_id)
            self.app.toast("Transaction deleted")
            self.app.refresh_badge()
            self.app.go(self.app._editor_return)

        btns.add_widget(pill_button("Delete", theme.EXPENSE, theme.ON_PRIMARY,
                                    do_del))
        content.add_widget(btns)
        popup.content = content
        popup.open()
