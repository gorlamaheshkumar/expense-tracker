# Building the APK in the cloud (GitHub Actions)

Buildozer can't run on Windows, and your corporate network blocks the CDNs a
local build needs. So we build on GitHub's Linux runners instead: you push the
code, GitHub compiles the APK, you download it. The workflow lives at
[.github/workflows/build-apk.yml](.github/workflows/build-apk.yml).

---

## 1. Put this project on GitHub

Open a terminal **in this folder** (`C:\Users\2399586\VScode\ExpenseTracker`):

```bash
git init
git add .
git commit -m "Expense Tracker - Kivy SMS budget app"
git branch -M main
```

Now create an **empty** repo on GitHub (do NOT add a README/.gitignore there):

1. Go to https://github.com/new
2. Name it e.g. `expense-tracker`, choose **Public** (Public = unlimited free
   Actions minutes; Private works too, 2000 min/month — a build uses ~20-40).
3. Click **Create repository** — leave it empty.

Then connect and push (replace `<you>` with your GitHub username):

```bash
git remote add origin https://github.com/<you>/expense-tracker.git
git push -u origin main
```

## 2. Let GitHub build it

The push to `main` triggers the build automatically. Watch it:

- Open your repo → **Actions** tab → the **Build Android APK** run.
- First run takes **~20-40 min** (it downloads the Android SDK/NDK on GitHub's
  servers and compiles Python-for-Android). Later runs are faster (cached).
- You can also start it manually anytime: **Actions → Build Android APK →
  Run workflow**.

## 3. Download the APK

When the run shows a green check:

1. Open the finished run.
2. Scroll to **Artifacts** at the bottom → download **expensetracker-debug-apk**.
3. It's a `.zip` — unzip it to get `expensetracker-0.1.0-debug.apk`.

## 4. Install on your phone (sideload)

This is a **debug, unsigned** APK, so Android needs permission to install it:

1. Copy the `.apk` to your phone (USB, Google Drive, email to yourself, etc.).
2. On the phone, tap the file. Android will ask to allow installing from this
   source — enable **"Allow from this source" / "Install unknown apps"** for the
   app you're installing from (Files / Chrome / Drive).
3. Install, then open **Expense Tracker**.
4. On first launch it asks for **SMS permission** — tap **Allow** (this is what
   lets it auto-detect bank transactions).
5. Go to the **Inbox** tab and tap **Scan SMS now** to read your real messages.

---

## Notes & caveats

- **Real SMS only works on the phone.** On desktop it uses the bundled sample
  messages; on the phone the app reads your actual inbox via the granted
  READ_SMS permission.
- **Google Play restricts SMS-reading apps.** This is fine for personal /
  sideloaded use; publishing to Play would require Google's SMS-permission
  declaration review. Keep it sideloaded.
- **Debug build** = not optimized and signed with a throwaway debug key. That's
  expected for personal use. (A signed release APK is a later step if you ever
  want one.)
- **Faster builds:** in `buildozer.spec`, `android.archs = arm64-v8a` (drop
  `armeabi-v7a`) cuts build time roughly in half and still covers virtually all
  phones from the last ~8 years.
- **If a build fails:** open the failed Actions run, read the red step's log. The
  most common causes are a typo in `buildozer.spec` or a transient SDK download
  hiccup — re-running the job usually clears the latter.
