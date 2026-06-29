"""Settings: preferences, editable SMS parsing-rule toggles, data, about."""

import os
import json

from kivy.uix.screenmanager import Screen
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.popup import Popup
from kivy.metrics import dp

from .. import theme
from ..widgets.cards import (RoundedCard, IconCircle, SettingRow, body_label)
from .common import glyph_for
from .accounts import back_header


class SettingsScreen(Screen):
    def __init__(self, app, **kwargs):
        super().__init__(**kwargs)
        self.app = app
        self.db = app.db
        root = BoxLayout(orientation="vertical")
        self.scroll = ScrollView()
        self.container = BoxLayout(orientation="vertical", size_hint_y=None,
                                   padding=[dp(16), dp(16), dp(16), dp(24)],
                                   spacing=dp(8))
        self.container.bind(minimum_height=self.container.setter("height"))
        self.scroll.add_widget(self.container)
        root.add_widget(self.scroll)
        self.add_widget(root)

    def on_pre_enter(self, *_):
        self.refresh()

    def _section(self, text):
        return body_label(text, color=theme.TEXT_MUTED, size=11, bold=True,
                          size_hint_y=None, height=dp(30))

    def refresh(self):
        app = self.app
        db = self.db
        c = self.container
        c.clear_widgets()
        c.add_widget(back_header("Settings", lambda: app.go("home")))

        # Preferences
        c.add_widget(self._section("PREFERENCES"))
        c.add_widget(SettingRow(
            "S", "Auto-scan SMS on launch",
            subtitle="Detect new transactions automatically",
            trailing="toggle",
            toggle_value=db.get_pref_bool("pref_autoscan", True),
            on_toggle=self._set_autoscan))
        c.add_widget(SettingRow(
            "M", "Manage accounts", subtitle="%d accounts" % len(db.accounts()),
            trailing="chevron", on_tap=lambda: app.go("accounts")))
        c.add_widget(SettingRow(
            "C", "Categories", subtitle="%d categories" % len(db.categories()),
            trailing="chevron", on_tap=self._show_categories))
        c.add_widget(SettingRow(
            "R", "Currency", value="INR " + theme.CURRENCY, trailing="value"))

        # Parsing rules
        c.add_widget(self._section("SMS PARSING RULES"))
        rules = db.rules_with_ids()
        if not rules:
            c.add_widget(body_label("No parsing rules configured.",
                                    color=theme.TEXT_MUTED, size=13,
                                    size_hint_y=None, height=dp(36)))
        for r in rules:
            bank = r["bank"] or "OTHER"
            c.add_widget(SettingRow(
                bank[0], r["name"],
                subtitle="Matches sender: %s" % r["sender_match"],
                trailing="toggle", toggle_value=bool(r["enabled"]),
                icon_color=theme.bank_color(bank),
                on_toggle=lambda val, rid=r["id"]: self._set_rule(rid, val)))

        # Data
        c.add_widget(self._section("DATA"))
        c.add_widget(SettingRow(
            "E", "Export data",
            subtitle="Save accounts + transactions to JSON",
            trailing="chevron", on_tap=self._export))
        c.add_widget(SettingRow(
            "Z", "Rescan SMS now", subtitle="Check for new bank messages",
            trailing="chevron", on_tap=lambda: app.scan_sms()))

        # About
        c.add_widget(self._section("ABOUT"))
        c.add_widget(SettingRow(
            "A", "Expense Tracker",
            subtitle="v1.0  -  Pure Kivy  -  On-device only",
            trailing="none"))

    # ---- handlers ----
    def _set_autoscan(self, val):
        self.db.set_pref_bool("pref_autoscan", val)
        self.app.toast("Auto-scan %s" % ("on" if val else "off"))

    def _set_rule(self, rule_id, val):
        self.db.set_rule_enabled(rule_id, val)
        self.app.toast("Parsing rule %s" % ("enabled" if val else "disabled"))

    def _show_categories(self):
        content = BoxLayout(orientation="vertical", spacing=dp(2),
                            padding=dp(12), size_hint_y=None)
        content.bind(minimum_height=content.setter("height"))
        for cat in self.db.categories():
            row = BoxLayout(orientation="horizontal", size_hint_y=None,
                            height=dp(40), spacing=dp(10))
            row.add_widget(IconCircle(glyph_for(cat),
                                      theme.category_color(cat), size=30))
            row.add_widget(body_label(cat, size=14))
            content.add_widget(row)
        scroll = ScrollView()
        scroll.add_widget(content)
        popup = Popup(title="Categories", size_hint=(0.8, 0.7),
                      title_size=dp(16))
        popup.content = scroll
        popup.open()

    def _export(self):
        accounts = [{k: a[k] for k in a.keys()} for a in self.db.accounts()]
        txns = [{k: t[k] for k in t.keys()}
                for t in self.db.all_transactions(limit=None)]
        data = {"accounts": accounts, "transactions": txns}
        path = os.path.join(self.app.user_data_dir, "expense_export.json")
        try:
            with open(path, "w", encoding="utf-8") as fh:
                json.dump(data, fh, indent=2, default=str)
            self.app.toast("Exported to expense_export.json")
        except Exception:
            self.app.toast("Export failed")
