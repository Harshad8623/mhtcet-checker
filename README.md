# 📢 MHT-CET PCM Score Card Checker

Automatically logs into `portal-2026.maharashtracet.org` every **15 minutes**, navigates to the Score Card section, and **calls your phone** the moment your PCM result is available.

---

## 🚀 Setup (One Time)

### Step 1 — Get a Free Twilio Account
1. Sign up at [twilio.com](https://www.twilio.com)
2. From the Console, note:
   - **Account SID**
   - **Auth Token**
3. Go to **Phone Numbers → Get a Trial Number** (e.g. `+12015551234`)

> ⚠️ On a free Twilio trial, you can only call **verified numbers**.  
> Go to **Verified Caller IDs** and add your personal number.

---

### Step 2 — Upload this project to GitHub
1. Create a new repo at [github.com](https://github.com) (e.g. `mhtcet-checker`)
2. Upload these files keeping the folder structure:
```
mhtcet-checker/
├── checker.py
├── requirements.txt
├── .github/
│   └── workflows/
│       └── check.yml
└── README.md
```

---

### Step 3 — Add GitHub Secrets
Go to your repo → **Settings → Secrets and variables → Actions → New repository secret**

| Secret Name | What to enter |
|---|---|
| `MHTCET_EMAIL` | Your registered email on MHT-CET portal |
| `MHTCET_PASSWORD` | Your MHT-CET portal password |
| `TWILIO_ACCOUNT_SID` | From Twilio dashboard |
| `TWILIO_AUTH_TOKEN` | From Twilio dashboard |
| `TWILIO_FROM_NUMBER` | Your Twilio number e.g. `+12015551234` |
| `YOUR_PHONE_NUMBER` | Your phone e.g. `+919876543210` (with +91) |

---

### Step 4 — Enable GitHub Actions
1. Go to the **Actions** tab in your repo
2. Click **"Enable workflows"** if prompted
3. Done! ✅ It now runs every 15 minutes automatically.

---

### Step 5 — Test Manually
Actions tab → **MHT-CET PCM Score Card Checker** → **Run workflow** → **Run workflow**

Check the logs — you should see:
```
✅ Logged in! Dashboard loaded.
✅ Found Score Card link
⏳ PCM result not yet available. Will check again in 15 minutes.
```

---

## 🔁 How It Works

```
Every 15 minutes (GitHub Actions free runner)
         │
         ▼
  Opens portal-2026.maharashtracet.org
  (auto-redirects to login page)
         │
         ▼
  Enters your Email + Password → Sign In
         │
         ▼
  Dashboard loads → clicks "Get Score Card →"
         │
         ├── PCM result NOT available → exit, retry in 15 min ⏳
         │
         └── PCM result IS available
                  │
                  ▼
           📞 Twilio calls your phone!
    "Your MHT CET PCM Score Card is now available..."
```

---

## 🛑 Stop It After Results
Once you see your result, go to:  
**Actions tab → MHT-CET PCM Score Card Checker → ⋯ → Disable workflow**

---

## 🐛 Debugging
If something goes wrong, the workflow uploads **debug screenshots** (PNG files) as artifacts.  
Go to: **Actions → latest run → Artifacts → debug-screenshots** to see exactly what the browser saw.
