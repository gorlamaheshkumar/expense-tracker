"""Cashew-inspired Material You palette and shared UI tokens.

Colors are normalized RGBA tuples (0..1) ready for Kivy canvas instructions.
Kept dependency-free so the parser/db modules can import sizing constants too.
"""


def hex_rgba(value, alpha=1.0):
    """Convert '#RRGGBB' (or 'RRGGBB') to a Kivy (r, g, b, a) tuple."""
    value = value.lstrip("#")
    r = int(value[0:2], 16) / 255.0
    g = int(value[2:4], 16) / 255.0
    b = int(value[4:6], 16) / 255.0
    return (r, g, b, alpha)


# --- Core palette (soft, playful Material You like Cashew) ---
BG = hex_rgba("#F6F5FB")          # near-white app background
SURFACE = hex_rgba("#FFFFFF")     # cards
SURFACE_ALT = hex_rgba("#EEEDF6")  # subtle raised chips
TEXT = hex_rgba("#1C1B22")        # near-black text
TEXT_MUTED = hex_rgba("#7A7886")  # secondary text
PRIMARY = hex_rgba("#7C6FF0")     # playful purple accent (seed color)
PRIMARY_SOFT = hex_rgba("#7C6FF0", 0.14)

# Cashew's expense/income colors
EXPENSE = hex_rgba("#CA5A5A")
INCOME = hex_rgba("#59A849")
WARNING = hex_rgba("#E0A042")

# Semantic helpers (named so screens don't re-inline literals)
DUP_BG = hex_rgba("#FCEFD6")        # duplicate-warning card
BANNER_BG = hex_rgba("#E7FBEA")     # "new from SMS" banner
ON_PRIMARY = (1, 1, 1, 1)           # text on purple cards
ON_PRIMARY_MUTED = (1, 1, 1, 0.8)   # sub-labels on purple cards

# Bank brand accents (used for account side-stripes)
BANK_COLORS = {
    "HDFC": hex_rgba("#004C8F"),
    "ICICI": hex_rgba("#AE2A26"),
    "SBI": hex_rgba("#22409A"),
    "AXIS": hex_rgba("#97144D"),
    "KOTAK": hex_rgba("#ED1C24"),
    "OTHER": hex_rgba("#7C6FF0"),
}

# Category accent colors
CATEGORY_COLORS = {
    "Food": hex_rgba("#E0734A"),
    "Shopping": hex_rgba("#C85AC8"),
    "Transport": hex_rgba("#4AA3E0"),
    "Groceries": hex_rgba("#5BA85B"),
    "Bills": hex_rgba("#E0A042"),
    "Entertainment": hex_rgba("#E05A7D"),
    "Health": hex_rgba("#4AC0B0"),
    "Income": hex_rgba("#59A849"),
    "Transfer": hex_rgba("#8A8696"),
    "Uncategorized": hex_rgba("#9A96A6"),
}

# --- Sizing tokens ---
RADIUS = 22          # default card corner radius
RADIUS_SM = 14
PAD = 16
GAP = 12

CURRENCY = "₹"   # INR rupee sign


def category_color(name):
    return CATEGORY_COLORS.get(name, CATEGORY_COLORS["Uncategorized"])


def bank_color(bank):
    return BANK_COLORS.get((bank or "OTHER").upper(), BANK_COLORS["OTHER"])


def money(amount, direction=None):
    """Format a rupee amount with thousands separators (Indian-friendly).

    With a direction, prefixes - / + (debit/credit). Without one, a negative
    amount (e.g. a credit-card balance or negative net worth) still shows '-'.
    """
    if direction == "debit":
        sign = "-"
    elif direction == "credit":
        sign = "+"
    else:
        sign = "-" if amount < 0 else ""
    return "{}{}{:,.0f}".format(sign, CURRENCY, abs(amount))
