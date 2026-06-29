"""ExpenseApp: wires DB + SMS provider + screens + bottom nav together."""

import os

from kivy.app import App
from kivy.core.window import Window
from kivy.clock import Clock
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.screenmanager import ScreenManager, NoTransition
from kivy.uix.behaviors import ButtonBehavior
from kivy.graphics import Color, RoundedRectangle, Ellipse, Rectangle
from kivy.core.text import Label as CoreLabel
from kivy.metrics import dp
from kivy.animation import Animation

from . import theme
from .db import Database, seed_defaults
from .sms import get_provider
from .screens.home import HomeScreen
from .screens.transactions import TransactionsScreen
from .screens.inbox import InboxScreen
from .screens.budget import BudgetScreen
from .screens.accounts import AccountsScreen
from .screens.settings import SettingsScreen
from .screens.editor import EditorScreen


# Desktop dev window roughly phone-shaped. Ignored on Android (fullscreen).
if os.name == "nt" or os.environ.get("ET_DESKTOP"):
    Window.size = (390, 800)


# Bottom-nav tabs (4). Accounts/Settings/Editor are reached off-bar but still
# light their parent tab so the nav never looks "unselected".
TABS = [("home", "Home", "H"), ("transactions", "Txns", "T"),
        ("inbox", "Inbox", "S"), ("budget", "Budget", "B")]

PARENT_TAB = {"accounts": "home", "settings": "home", "editor": "home"}


class NavTab(ButtonBehavior, BoxLayout):
    def __init__(self, key, label, glyph, on_tap, **kwargs):
        super().__init__(orientation="vertical", **kwargs)
        self.key = key
        self.padding = [0, dp(8), 0, dp(6)]
        self.spacing = dp(2)
        self.glyph_lbl = Label(text=glyph, font_size=dp(18),
                               color=theme.TEXT_MUTED, bold=True)
        self.text_lbl = Label(text=label, font_size=dp(11),
                              color=theme.TEXT_MUTED)
        self.add_widget(self.glyph_lbl)
        self.add_widget(self.text_lbl)
        self.bind(on_release=lambda *_: on_tap(key))
        # Badge drawn entirely in canvas.after (circle + count texture) so it
        # floats over the glyph instead of being placed by the BoxLayout.
        self._badge_size = dp(17)
        with self.canvas.after:
            self._badge_color = Color(0, 0, 0, 0)
            self._badge = Ellipse(size=(self._badge_size, self._badge_size))
            self._badge_tex_color = Color(1, 1, 1, 0)
            self._badge_tex = Rectangle()
        self.bind(pos=self._sync_badge, size=self._sync_badge)

    def set_active(self, active):
        color = theme.PRIMARY if active else theme.TEXT_MUTED
        self.glyph_lbl.color = color
        self.text_lbl.color = color
        self.text_lbl.bold = active

    def set_badge(self, count):
        if count > 0:
            self._badge_color.rgba = theme.EXPENSE
            text = str(count) if count < 10 else "9+"
            cl = CoreLabel(text=text, font_size=dp(11), bold=True)
            cl.refresh()
            self._badge_tex.texture = cl.texture
            self._badge_tex.size = cl.texture.size
            self._badge_tex_color.rgba = (1, 1, 1, 1)
        else:
            self._badge_color.rgba = (0, 0, 0, 0)
            self._badge_tex_color.rgba = (1, 1, 1, 0)
            self._badge_tex.texture = None
        self._sync_badge()

    def _sync_badge(self, *_):
        bx = self.center_x + dp(8)
        by = self.top - dp(24)
        self._badge.pos = (bx, by)
        if self._badge_tex.texture:
            tw, th = self._badge_tex.size
            self._badge_tex.pos = (bx + (self._badge_size - tw) / 2,
                                   by + (self._badge_size - th) / 2)


class ExpenseApp(App):
    title = "Expense Tracker"

    def build(self):
        Window.clearcolor = theme.BG
        db_path = os.path.join(self.user_data_dir, "expense.db")
        self.db = Database(db_path)
        seed_defaults(self.db)
        self.provider = get_provider()

        self.root_layout = FloatLayout()
        col = BoxLayout(orientation="vertical")

        self.sm = ScreenManager(transition=NoTransition())
        self._editor_return = "home"
        self._accounts_return = "home"   # Accounts is reachable from Home or Settings
        self.screens = {
            "home": HomeScreen(self, name="home"),
            "transactions": TransactionsScreen(self, name="transactions"),
            "inbox": InboxScreen(self, name="inbox"),
            "budget": BudgetScreen(self, name="budget"),
            "accounts": AccountsScreen(self, name="accounts"),
            "settings": SettingsScreen(self, name="settings"),
            "editor": EditorScreen(self, name="editor"),
        }
        for s in self.screens.values():
            self.sm.add_widget(s)
        col.add_widget(self.sm)

        # Bottom nav
        nav = BoxLayout(orientation="horizontal", size_hint_y=None,
                        height=dp(62))
        with nav.canvas.before:
            Color(*theme.SURFACE)
            self._nav_bg = RoundedRectangle()
        nav.bind(pos=self._sync_nav, size=self._sync_nav)
        self.tabs = {}
        for key, label, glyph in TABS:
            tab = NavTab(key, label, glyph, self.go)
            self.tabs[key] = tab
            nav.add_widget(tab)
        col.add_widget(nav)

        self.root_layout.add_widget(col)
        self.go("home")
        return self.root_layout

    def on_start(self):
        # Initial SMS scan once the event loop is running. Doing this here (not
        # via a build-time Clock callback, which doesn't reliably fire) keeps
        # the inbox drafts + badge populated on launch.
        if self.db.get_pref_bool("pref_autoscan", True):
            self.scan_sms(quiet=True)

    def _sync_nav(self, inst, *_):
        self._nav_bg.pos = inst.pos
        self._nav_bg.size = inst.size

    # ---- navigation ----
    def go(self, key):
        # Remember where Accounts was opened from so its back button can return
        # there (Home wallet card or Settings -> Manage accounts).
        if key == "accounts" and self.sm.current not in ("accounts", "editor"):
            self._accounts_return = self.sm.current
        self.sm.current = key
        active = PARENT_TAB.get(key, key)   # sub-screens light their parent tab
        for k, tab in self.tabs.items():
            tab.set_active(k == active)
        self.refresh_badge()

    def open_editor(self, mode, draft=None, tx=None):
        """Open the transaction editor; remembers the origin screen for back."""
        ed = self.screens["editor"]
        self._editor_return = self.sm.current
        ed.load(mode, draft=draft, tx=tx)   # build form BEFORE switching
        self.go("editor")

    def refresh_badge(self):
        self.tabs["inbox"].set_badge(self.db.pending_count())

    # ---- SMS pipeline ----
    def scan_sms(self, quiet=False):
        messages = self.provider.read_recent(50)
        new = self.db.ingest_messages(messages)
        self.refresh_badge()
        # refresh the visible screen
        cur = self.screens.get(self.sm.current)
        if cur and hasattr(cur, "refresh"):
            cur.refresh()
        if not quiet:
            if new:
                self.toast("Found %d new transaction%s from SMS"
                           % (new, "" if new == 1 else "s"))
            else:
                self.toast("No new SMS transactions")

    # ---- toast ----
    def toast(self, text):
        from .widgets.cards import RoundedCard
        toast = RoundedCard(bg=theme.TEXT, radius=dp(20),
                            size_hint=(None, None), height=dp(44),
                            padding=[dp(18), dp(8)],
                            pos_hint={"center_x": 0.5, "y": 0.12})
        lbl = Label(text=text, color=(1, 1, 1, 1), font_size=dp(13),
                    size_hint=(None, 1))
        lbl.bind(texture_size=lambda i, v: setattr(toast, "width",
                                                   v[0] + dp(36)))
        lbl.bind(texture_size=lambda i, v: setattr(lbl, "width", v[0]))
        toast.add_widget(lbl)
        toast.opacity = 0
        self.root_layout.add_widget(toast)
        Animation(opacity=1, d=0.18).start(toast)

        def _remove(*_):
            anim = Animation(opacity=0, d=0.3)
            anim.bind(on_complete=lambda *a: self.root_layout.remove_widget(
                toast))
            anim.start(toast)
        Clock.schedule_once(_remove, 1.8)


def main():
    ExpenseApp().run()
