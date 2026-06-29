"""Shared screen helpers: time formatting and category glyphs.

Glyphs are single letters (not emoji) because Kivy's bundled Roboto font does
not render color emoji — letters always show correctly on every platform.
"""

import time

# One-letter stand-in icons per category (rendered inside a colored circle).
CATEGORY_GLYPH = {
    "Food": "F",
    "Shopping": "S",
    "Transport": "T",
    "Groceries": "G",
    "Bills": "B",
    "Entertainment": "E",
    "Health": "H",
    "Income": "+",
    "Transfer": "~",
    "Uncategorized": "?",
}


def glyph_for(category):
    return CATEGORY_GLYPH.get(category, "?")


def _month_start():
    """Unix-seconds timestamp for midnight on the 1st of the current month."""
    t = time.localtime()
    return int(time.mktime((t.tm_year, t.tm_mon, 1, 0, 0, 0, 0, 0, -1)))


def absolute_date(ts):
    """Absolute date label like '28 Jun 2026' for the transaction editor."""
    return time.strftime("%d %b %Y", time.localtime(int(ts)))


def rel_time(ts):
    """Human relative time like '2 min ago', '3 hr ago', 'Yesterday'."""
    now = int(time.time())
    delta = max(0, now - int(ts))
    if delta < 60:
        return "just now"
    if delta < 3600:
        return "%d min ago" % (delta // 60)
    if delta < 86400:
        return "%d hr ago" % (delta // 3600)
    if delta < 2 * 86400:
        return "Yesterday"
    return "%d days ago" % (delta // 86400)
