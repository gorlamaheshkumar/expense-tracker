"""On-device SQLite storage + the SMS->draft ingestion pipeline.

Everything stays local (Cashew-style privacy). The DB file lives in the app's
user-data dir on Android, or alongside the project during desktop development.

Key flow:
    raw SMS  -> parse_sms()  -> draft row (status='pending')
    user taps Approve        -> transaction row (source='sms')
Duplicate guard prevents the same SMS (by sms_id) or a near-identical existing
transaction from creating a second entry.
"""

import os
import sqlite3
import time
import datetime

from .sms.parser import parse_sms, Rule, DEFAULT_RULES
from .categorize import categorize

DUP_WINDOW_SECONDS = 24 * 60 * 60  # treat same amount/acct within a day as dup


def _month_start():
    """Midnight on the 1st of the current month, unix seconds.

    Duplicated (2 lines) from screens.common on purpose so db.py keeps zero
    dependency on the UI layer.
    """
    t = time.localtime()
    return int(time.mktime((t.tm_year, t.tm_mon, 1, 0, 0, 0, 0, 0, -1)))


SCHEMA = """
CREATE TABLE IF NOT EXISTS accounts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    bank TEXT,
    type TEXT,                 -- 'bank' | 'card' | 'upi'
    last4 TEXT,
    color TEXT,
    balance REAL DEFAULT 0,
    sms_senders TEXT           -- comma separated sender ids
);

CREATE TABLE IF NOT EXISTS transactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    amount REAL NOT NULL,
    direction TEXT NOT NULL,   -- 'debit' | 'credit'
    merchant TEXT,
    category TEXT,
    account_id INTEGER,
    ts INTEGER NOT NULL,
    ref TEXT,
    source TEXT DEFAULT 'manual',  -- 'manual' | 'sms'
    sms_id TEXT,
    note TEXT,
    FOREIGN KEY (account_id) REFERENCES accounts(id)
);

CREATE TABLE IF NOT EXISTS drafts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sms_id TEXT UNIQUE,
    raw TEXT,
    sender TEXT,
    bank TEXT,
    amount REAL,
    direction TEXT,
    merchant TEXT,
    category TEXT,
    account_id INTEGER,
    ts INTEGER,
    ref TEXT,
    confidence REAL,
    status TEXT DEFAULT 'pending',  -- 'pending' | 'approved' | 'rejected'
    dup_of INTEGER                  -- transaction id this looks like a dup of
);

CREATE TABLE IF NOT EXISTS rules (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT,
    bank TEXT,
    sender_match TEXT,
    enabled INTEGER DEFAULT 1,
    keywords TEXT
);

CREATE TABLE IF NOT EXISTS budgets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    category TEXT UNIQUE,
    limit_amount REAL,
    period TEXT DEFAULT 'monthly'
);

CREATE TABLE IF NOT EXISTS meta (
    key TEXT PRIMARY KEY,
    value TEXT
);
"""


class Database:
    def __init__(self, path):
        self.path = path
        folder = os.path.dirname(os.path.abspath(path))
        if folder and not os.path.exists(folder):
            os.makedirs(folder, exist_ok=True)
        self.conn = sqlite3.connect(path)
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(SCHEMA)
        self.conn.commit()

    # ---- meta helpers ----
    def get_meta(self, key, default=None):
        row = self.conn.execute(
            "SELECT value FROM meta WHERE key=?", (key,)).fetchone()
        return row["value"] if row else default

    def set_meta(self, key, value):
        self.conn.execute(
            "INSERT INTO meta(key, value) VALUES(?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (key, str(value)))
        self.conn.commit()

    # ---- rules ----
    def load_rules(self):
        rows = self.conn.execute("SELECT * FROM rules").fetchall()
        if not rows:
            return list(DEFAULT_RULES)
        rules = []
        for r in rows:
            kw = tuple((r["keywords"] or "").split(",")) if r["keywords"] else ()
            rules.append(Rule(r["name"], r["bank"], r["sender_match"],
                              bool(r["enabled"]), kw))
        return rules

    def set_rule_enabled(self, rule_id, enabled):
        self.conn.execute("UPDATE rules SET enabled=? WHERE id=?",
                          (1 if enabled else 0, rule_id))
        self.conn.commit()

    # ---- accounts ----
    def accounts(self):
        return self.conn.execute(
            "SELECT * FROM accounts ORDER BY id").fetchall()

    def account_by_match(self, bank, last4):
        """Find the account an SMS belongs to by bank + masked tail."""
        if last4:
            row = self.conn.execute(
                "SELECT * FROM accounts WHERE last4=? ORDER BY "
                "(bank=?) DESC LIMIT 1", (last4, bank)).fetchone()
            if row:
                return row
        if bank:
            row = self.conn.execute(
                "SELECT * FROM accounts WHERE bank=? LIMIT 1", (bank,)).fetchone()
            if row:
                return row
        return None

    # ---- transactions ----
    def add_transaction(self, amount, direction, merchant, category,
                        account_id, ts, ref="", source="manual", sms_id=None,
                        note=""):
        cur = self.conn.execute(
            "INSERT INTO transactions(amount, direction, merchant, category, "
            "account_id, ts, ref, source, sms_id, note) "
            "VALUES(?,?,?,?,?,?,?,?,?,?)",
            (amount, direction, merchant, category, account_id, ts, ref,
             source, sms_id, note))
        self._apply_balance(account_id, amount, direction)
        self.conn.commit()
        return cur.lastrowid

    def _apply_balance(self, account_id, amount, direction):
        if account_id is None:
            return
        delta = amount if direction == "credit" else -amount
        self.conn.execute(
            "UPDATE accounts SET balance = balance + ? WHERE id=?",
            (delta, account_id))

    def recent_transactions(self, limit=20):
        return self.conn.execute(
            "SELECT t.*, a.name AS account_name, a.bank AS account_bank "
            "FROM transactions t LEFT JOIN accounts a ON a.id=t.account_id "
            "ORDER BY t.ts DESC LIMIT ?", (limit,)).fetchall()

    def find_duplicate(self, amount, direction, account_id, ts, ref=""):
        """Return a matching existing transaction id, or None."""
        if ref:
            row = self.conn.execute(
                "SELECT id FROM transactions WHERE ref=? LIMIT 1",
                (ref,)).fetchone()
            if row:
                return row["id"]
        row = self.conn.execute(
            "SELECT id FROM transactions WHERE direction=? "
            "AND ABS(amount-?) < 0.01 AND ABS(ts-?) < ? "
            "AND (account_id IS ? OR account_id=?) LIMIT 1",
            (direction, amount, ts, DUP_WINDOW_SECONDS, account_id,
             account_id)).fetchone()
        return row["id"] if row else None

    # ---- drafts ----
    def pending_drafts(self):
        return self.conn.execute(
            "SELECT d.*, a.name AS account_name FROM drafts d "
            "LEFT JOIN accounts a ON a.id=d.account_id "
            "WHERE d.status='pending' ORDER BY d.ts DESC").fetchall()

    def pending_count(self):
        row = self.conn.execute(
            "SELECT COUNT(*) AS c FROM drafts WHERE status='pending'").fetchone()
        return row["c"]

    def draft(self, draft_id):
        return self.conn.execute(
            "SELECT * FROM drafts WHERE id=?", (draft_id,)).fetchone()

    def approve_draft(self, draft_id, overrides=None):
        """One-shot draft -> transaction helper (non-UI / programmatic path).

        The interactive flow instead opens the editor and uses
        add_transaction + mark_draft_approved, so a user can edit fields first.
        Kept for headless/scripted approval; not called by the UI.
        """
        d = self.draft(draft_id)
        if not d or d["status"] != "pending":
            return None
        o = overrides or {}
        tx_id = self.add_transaction(
            amount=o.get("amount", d["amount"]),
            direction=o.get("direction", d["direction"]),
            merchant=o.get("merchant", d["merchant"]),
            category=o.get("category", d["category"]),
            account_id=o.get("account_id", d["account_id"]),
            ts=d["ts"] or int(time.time()),
            ref=d["ref"] or "",
            source="sms",
            sms_id=d["sms_id"],
        )
        self.conn.execute(
            "UPDATE drafts SET status='approved' WHERE id=?", (draft_id,))
        self.conn.commit()
        return tx_id

    def reject_draft(self, draft_id):
        self.conn.execute(
            "UPDATE drafts SET status='rejected' WHERE id=?", (draft_id,))
        self.conn.commit()

    # ---- the ingest pipeline ----
    def ingest_messages(self, messages):
        """Parse SMS dicts into pending drafts.

        Skips messages already seen (by sms_id), OTP/promo, and flags likely
        duplicates of existing transactions. Returns number of new drafts.
        """
        rules = self.load_rules()
        new_drafts = 0
        for msg in messages:
            sms_id = msg.get("id")
            # already turned into a draft (any status)?
            if sms_id and self.conn.execute(
                    "SELECT 1 FROM drafts WHERE sms_id=?", (sms_id,)).fetchone():
                continue

            parsed = parse_sms(msg.get("body", ""), msg.get("sender", ""), rules)
            if not parsed:
                continue

            account = self.account_by_match(parsed.bank, parsed.account_last4)
            account_id = account["id"] if account else None
            category = categorize(parsed.merchant, parsed.direction)
            ts = msg.get("ts", int(time.time()))

            dup_of = self.find_duplicate(
                parsed.amount, parsed.direction, account_id, ts, parsed.ref)

            self.conn.execute(
                "INSERT OR IGNORE INTO drafts(sms_id, raw, sender, bank, amount, "
                "direction, merchant, category, account_id, ts, ref, "
                "confidence, status, dup_of) "
                "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (sms_id, parsed.raw, parsed.sender, parsed.bank, parsed.amount,
                 parsed.direction, parsed.merchant, category, account_id, ts,
                 parsed.ref, parsed.confidence, "pending", dup_of))
            new_drafts += 1
        self.conn.commit()
        return new_drafts

    # ---- budgets & summaries ----
    def budgets(self):
        return self.conn.execute(
            "SELECT * FROM budgets ORDER BY category").fetchall()

    def spent_by_category(self, since_ts=0):
        rows = self.conn.execute(
            "SELECT category, SUM(amount) AS total FROM transactions "
            "WHERE direction='debit' AND ts>=? GROUP BY category",
            (since_ts,)).fetchall()
        return {r["category"]: r["total"] for r in rows}

    def totals(self, since_ts=0):
        row = self.conn.execute(
            "SELECT "
            "COALESCE(SUM(CASE WHEN direction='debit' THEN amount END),0) AS spent, "
            "COALESCE(SUM(CASE WHEN direction='credit' THEN amount END),0) AS income "
            "FROM transactions WHERE ts>=?", (since_ts,)).fetchone()
        return {"spent": row["spent"], "income": row["income"]}

    def total_balance(self):
        row = self.conn.execute(
            "SELECT COALESCE(SUM(balance),0) AS b FROM accounts").fetchone()
        return row["b"]

    def net_worth(self):
        """Assets (>=0 balances) + liabilities (<0 balances, e.g. credit cards).

        Returns {"assets", "liabilities", "net"}; net == total_balance().
        """
        row = self.conn.execute(
            "SELECT "
            "COALESCE(SUM(CASE WHEN balance>=0 THEN balance END),0) AS assets, "
            "COALESCE(SUM(CASE WHEN balance<0 THEN balance END),0) AS liabilities "
            "FROM accounts").fetchone()
        assets = row["assets"]
        liabilities = row["liabilities"]
        return {"assets": assets, "liabilities": liabilities,
                "net": assets + liabilities}

    def accounts_with_month_counts(self, since_ts=None):
        """Accounts plus this-month transaction count (0 for accounts with none)."""
        if since_ts is None:
            since_ts = _month_start()
        return self.conn.execute(
            "SELECT a.*, "
            "COALESCE(SUM(CASE WHEN t.ts>=? THEN 1 ELSE 0 END),0) AS month_count "
            "FROM accounts a LEFT JOIN transactions t ON t.account_id=a.id "
            "GROUP BY a.id ORDER BY a.id", (since_ts,)).fetchall()

    def monthly_spend_series(self, n_months=6):
        """Last n months of debit totals as [(label, value)], oldest -> newest."""
        rows = self.conn.execute(
            "SELECT strftime('%Y-%m', ts, 'unixepoch', 'localtime') AS ym, "
            "SUM(amount) AS total FROM transactions WHERE direction='debit' "
            "GROUP BY ym").fetchall()
        totals = {r["ym"]: r["total"] for r in rows}
        first = datetime.date.today().replace(day=1)
        y, m = first.year, first.month
        months = []
        for _ in range(n_months):
            months.append((y, m))
            m -= 1
            if m == 0:
                m = 12
                y -= 1
        series = []
        for (yy, mm) in reversed(months):
            key = "%04d-%02d" % (yy, mm)
            label = datetime.date(yy, mm, 1).strftime("%b")
            series.append((label, totals.get(key, 0.0) or 0.0))
        return series

    def all_transactions(self, account_id=None, direction=None, limit=200):
        """Unified ledger across all accounts, newest first, optionally filtered."""
        clauses = []
        params = []
        if account_id is not None:
            clauses.append("t.account_id=?")
            params.append(account_id)
        if direction in ("debit", "credit"):
            clauses.append("t.direction=?")
            params.append(direction)
        where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
        sql = ("SELECT t.*, a.name AS account_name, a.bank AS account_bank "
               "FROM transactions t LEFT JOIN accounts a ON a.id=t.account_id "
               + where + " ORDER BY t.ts DESC")
        if limit is not None:
            sql += " LIMIT ?"
            params.append(limit)
        return self.conn.execute(sql, params).fetchall()

    def transaction(self, tx_id):
        """Single transaction Row (with account_name/account_bank) or None."""
        return self.conn.execute(
            "SELECT t.*, a.name AS account_name, a.bank AS account_bank "
            "FROM transactions t LEFT JOIN accounts a ON a.id=t.account_id "
            "WHERE t.id=? LIMIT 1", (tx_id,)).fetchone()

    def _reverse_balance(self, account_id, amount, direction):
        """Undo a previously-applied balance delta (does not commit)."""
        if account_id is None:
            return
        delta = -amount if direction == "credit" else amount
        self.conn.execute(
            "UPDATE accounts SET balance = balance + ? WHERE id=?",
            (delta, account_id))

    def update_transaction(self, tx_id, amount, direction, merchant, category,
                           account_id, ts, ref=None, note=None):
        """Edit a transaction, correctly reversing then re-applying balances.

        ref/note keep their existing value when the argument is None.
        """
        old = self.conn.execute(
            "SELECT amount, direction, account_id, ref, note "
            "FROM transactions WHERE id=?", (tx_id,)).fetchone()
        if not old:
            return None
        self._reverse_balance(old["account_id"], old["amount"], old["direction"])
        new_ref = old["ref"] if ref is None else ref
        new_note = old["note"] if note is None else note
        self.conn.execute(
            "UPDATE transactions SET amount=?, direction=?, merchant=?, "
            "category=?, account_id=?, ts=?, ref=?, note=? WHERE id=?",
            (amount, direction, merchant, category, account_id, ts, new_ref,
             new_note, tx_id))
        self._apply_balance(account_id, amount, direction)
        self.conn.commit()
        return tx_id

    def delete_transaction(self, tx_id):
        """Delete a transaction and reverse its balance impact."""
        old = self.conn.execute(
            "SELECT amount, direction, account_id FROM transactions WHERE id=?",
            (tx_id,)).fetchone()
        if not old:
            return False
        self._reverse_balance(old["account_id"], old["amount"], old["direction"])
        self.conn.execute("DELETE FROM transactions WHERE id=?", (tx_id,))
        self.conn.commit()
        return True

    def categories(self):
        """Canonical category list (color-backed) + any extras seen in data."""
        from . import theme
        cats = list(theme.CATEGORY_COLORS.keys())
        rows = self.conn.execute(
            "SELECT DISTINCT category FROM transactions "
            "WHERE category IS NOT NULL AND category<>''").fetchall()
        for r in rows:
            if r["category"] not in cats:
                cats.append(r["category"])
        return cats

    def mark_draft_approved(self, draft_id):
        """Mark a draft approved without building a transaction (editor owns that)."""
        self.conn.execute(
            "UPDATE drafts SET status='approved' WHERE id=?", (draft_id,))
        self.conn.commit()

    def rules_with_ids(self):
        """Parsing rules including row id (Settings needs it for toggling)."""
        return self.conn.execute(
            "SELECT id, name, bank, sender_match, enabled, keywords "
            "FROM rules ORDER BY id").fetchall()

    def get_pref_bool(self, key, default=False):
        v = self.get_meta(key)
        return default if v is None else v == "1"

    def set_pref_bool(self, key, value):
        self.set_meta(key, "1" if value else "0")

    def close(self):
        self.conn.close()


def seed_defaults(db):
    """Populate first-run accounts, rules, budgets, and a seed transaction.

    The seed NAMMA METRO transaction intentionally matches sample SMS s5 so the
    duplicate detector lights up on first scan (mirrors the prototype demo).
    """
    if db.get_meta("seeded") == "1":
        return

    # Accounts
    accounts = [
        ("HDFC Savings", "HDFC", "bank", "1234", "#004C8F", 84200,
         "HDFCBK,HDFC"),
        ("ICICI Savings", "ICICI", "bank", "0567", "#AE2A26", 53210,
         "ICICIB,ICICI"),
        ("SBI Salary", "SBI", "bank", "1234", "#22409A", 71230, "SBIINB,SBI"),
        ("Axis Credit Card", "AXIS", "card", "9012", "#97144D", -8750,
         "AXISBK,AXIS"),
    ]
    for name, bank, typ, last4, color, bal, senders in accounts:
        db.conn.execute(
            "INSERT INTO accounts(name, bank, type, last4, color, balance, "
            "sms_senders) VALUES(?,?,?,?,?,?,?)",
            (name, bank, typ, last4, color, bal, senders))

    # Rules
    for r in DEFAULT_RULES:
        db.conn.execute(
            "INSERT INTO rules(name, bank, sender_match, enabled, keywords) "
            "VALUES(?,?,?,?,?)",
            (r.name, r.bank, r.sender_match, 1, ",".join(r.keywords)))

    # Budgets (monthly limits in INR)
    budgets = [("Food", 6000), ("Shopping", 5000), ("Groceries", 8000),
               ("Transport", 3000), ("Bills", 4000), ("Entertainment", 2000)]
    for cat, lim in budgets:
        db.conn.execute(
            "INSERT INTO budgets(category, limit_amount, period) "
            "VALUES(?,?, 'monthly')", (cat, lim))

    db.conn.commit()

    # Seed transaction that collides with sample SMS s5 (Namma Metro ₹85)
    hdfc = db.conn.execute(
        "SELECT id FROM accounts WHERE bank='HDFC' LIMIT 1").fetchone()
    if hdfc:
        db.add_transaction(
            amount=85, direction="debit", merchant="NAMMA METRO",
            category="Transport", account_id=hdfc["id"],
            ts=int(time.time()) - 220 * 60, ref="418999001122",
            source="manual")
    # A couple of historical manual transactions for a non-empty dashboard
    icici = db.conn.execute(
        "SELECT id FROM accounts WHERE bank='ICICI' LIMIT 1").fetchone()
    if icici:
        db.add_transaction(
            amount=320, direction="debit", merchant="BLINKIT",
            category="Groceries", account_id=icici["id"],
            ts=int(time.time()) - 2 * 86400, source="manual")

    db.set_meta("seeded", "1")
