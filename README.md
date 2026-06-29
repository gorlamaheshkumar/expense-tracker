# Expense Tracker

A Cashew-inspired, Material-You-style budget app for **India (UPI / INR)** with
one headline feature: **it reads your bank/UPI/card SMS and turns them into
transactions automatically.**

Built in **pure Python + Kivy** — no Node.js, no KivyMD (its only PyPI artifact
is a source tarball blocked by many corporate proxies), no CDNs. The friendly
rounded "Cashew" look is hand-built with canvas widgets.

All data stays **on-device** in SQLite. Nothing is uploaded anywhere.

---

## How the SMS auto-tracking works

```
   Bank SMS                Parser                 Review inbox            Ledger
 ───────────         ─────────────────         ───────────────       ────────────
 "Sent Rs.1,249  ->  amount  = 1249      ->    draft card with   ->  transaction
  From HDFC ...       merchant= SWIGGY          chips + raw SMS        (source=sms)
  To SWIGGY"          bank    = HDFC            + Approve/Reject
                      account = •••• 1234
                      category= Food
```

1. **Scan** — `expense/sms/provider.py` reads messages. On a phone it queries
   `content://sms/inbox` via pyjnius; on a laptop it serves realistic samples
   from `data/sample_sms.json`, so the whole pipeline runs without a phone.
2. **Parse** — `expense/sms/parser.py` extracts amount, direction (debit/credit),
   merchant, masked account, and reference from the SMS body using per-bank
   rules (HDFC / ICICI / SBI / Axis / Kotak). OTPs and promos are ignored.
3. **Categorize & match** — `expense/categorize.py` maps the merchant to a
   category; the masked account tail is matched to one of your accounts.
4. **Dedup** — a draft that matches an existing transaction (same amount +
   account within 24h, or same reference) is flagged as a likely duplicate.
5. **Review** — every detection lands in the **SMS Inbox** as a draft. You tap
   **Add transaction** (the "moment" it becomes real) or **Reject**.

---

## Run it on your laptop (Windows/Mac/Linux)

No phone needed — the mock SMS provider drives everything.

```bash
pip install --user -r requirements.txt
python main.py
```

You'll get a phone-sized window. On launch it auto-scans the sample SMS, so the
Inbox already has detections and the Home badge shows the count.

### Quick engine sanity check (no GUI)

```bash
python - <<'PY'
from expense.sms.parser import parse_sms
p = parse_sms("Sent Rs.1,249.00 From HDFC Bank A/C *1234 To SWIGGY On 28-06 Ref 418876534521", "VM-HDFCBK")
print(p.bank, p.amount, p.merchant, p.direction)   # HDFC 1249.0 SWIGGY debit
PY
```

---

## Build the Android APK (real SMS reading)

SMS access only works on a real Android device with the `READ_SMS` /
`RECEIVE_SMS` permissions, which `main.py` requests at runtime.

Buildozer runs on **Linux** (use WSL2 on Windows):

```bash
pip install buildozer
buildozer -v android debug          # produces bin/expensetracker-0.1.0-debug.apk
buildozer android deploy run        # install + launch on a connected phone
```

Permissions and requirements (`pyjnius`, `android`) are pre-configured in
[`buildozer.spec`](buildozer.spec). On first launch, grant the SMS permission,
then tap **Scan SMS now** in the Inbox.

> Google Play restricts SMS-reading apps. This is intended as a personal /
> sideloaded app; distributing on Play would require their SMS permission
> declaration process.

---

## Project layout

```
ExpenseTracker/
├── main.py                  # entry point; requests Android SMS permissions
├── buildozer.spec           # Android packaging (permissions, requirements)
├── requirements.txt
├── data/
│   └── sample_sms.json      # realistic Indian bank SMS for desktop dev
└── expense/
    ├── theme.py             # Cashew palette + sizing tokens
    ├── db.py                # SQLite schema, seeding, SMS->draft ingest pipeline
    ├── categorize.py        # merchant -> category
    ├── app.py               # ScreenManager, bottom nav, toast, scan wiring
    ├── sms/
    │   ├── parser.py        # SMS text -> ParsedSms (the core regex engine)
    │   └── provider.py      # MockSmsProvider (desktop) / AndroidSmsProvider
    ├── widgets/
    │   ├── cards.py         # RoundedCard, Chip, IconCircle, Toggle, SettingRow…
    │   ├── charts.py        # BarChart (canvas spending chart)
    │   └── keypad.py        # NumberPad (editor amount entry)
    └── screens/
        ├── home.py          # net worth + spending chart + wallets + ledger
        ├── transactions.py  # full date-grouped ledger + filter chips
        ├── editor.py        # create / edit / SMS-draft transaction editor
        ├── inbox.py         # SMS review queue -> opens the editor pre-filled
        ├── budget.py        # monthly limits + category progress bars
        ├── accounts.py      # accounts with bank stripes + SMS sender mapping
        └── settings.py      # prefs + editable per-bank parsing rules
```

## Status & next steps

Working today: the SMS parsing engine, mock + Android providers, on-device
storage with balance-correct edits/deletes, duplicate detection, categorization,
and a full Cashew-style UI:

* **Home** — net-worth card, 6-month spending bar chart, horizontal wallet strip
  with per-account *this-month* transaction counts, "new from SMS" banner,
  top categories, and the unified ledger.
* **Transactions** — date-grouped ledger (Today / Yesterday / date) with
  All / Income / Expense / per-account filter chips.
* **Editor** — one screen, three modes (create / edit / SMS-draft review) with a
  custom number pad, expense/income toggle, category grid, account picker,
  date stepper, and delete.
* **Inbox** — auto-detected SMS drafts that open the editor pre-filled.
* **Settings** — auto-scan toggle, editable per-bank parsing-rule switches,
  manage accounts, categories, currency, and JSON export.

Planned: a foreground `BroadcastReceiver` for real-time SMS detection (vs. the
on-demand scan), an onboarding/permission screen, and a category/budget editor.
```
