# AI Loan Collection Agent (Hindi + English)

Complete, RBI-compliant **AI Loan Collection Calling Agent** built with **Python FastAPI**, **SQLite / PostgreSQL**, **Hindi/Hinglish Natural Language Conversation Engine**, **Twilio / Exotel Telephony Integration**, and a **Mobile-Friendly Responsive Dashboard**.

---

## 1. System Architecture

```
+-----------------------------------------------------------------------------------+
|                   MOBILE & DESKTOP RESPONSIVE WEB DASHBOARD                       |
|  - KPI Overview (Assigned, Attempted, Answered, PTP, Verified Paid, Escalations)  |
|  - Customer DB (CSV Import, Masked Loan Account LN-XXXX-1234, Search & Filters)   |
|  - Interactive Hindi AI Voice Simulator (Web Speech API hi-IN TTS + Mic STT)      |
|  - PTP Register, Campaign Scheduler, Filtered CSV Export & Immutable Audit Log    |
+-----------------------------------------+-----------------------------------------+
                                          | REST API / JSON (RBAC Headers & JWT)
                                          v
+-----------------------------------------------------------------------------------+
|                        PYTHON FASTAPI BACKEND (`backend/main.py`)                 |
|                                                                                   |
|  +---------------------------+   +---------------------------------------------+  |
|  | RBI Compliance Guardrails |   | Hindi & English Conversation Engine         |  |
|  | (`backend/security.py`)   |   | (`backend/hindi_conversation_engine.py`)    |  |
|  | - Hours: 08:00-19:00 IST  |   | - Step 1: Lender Intro + Recording Notice   |  |
|  | - Max 2/day, 5/week caps  |   | - Step 2: Identity Verification Gate        |  |
|  | - Auto-stop if PAID       |   | - Step 3: Masked Loan & Verified EMI Info   |  |
|  | - Mask Loan Account Nos.  |   | - Step 4: Intent & PTP Date Extraction      |  |
|  | - Encrypt Raw References  |   | - Escalates Hardship, Disputes, Wrong No.   |  |
|  +---------------------------+   +---------------------------------------------+  |
+-------------------+-------------------------------------------+-------------------+
                    |                                           |
                    v                                           v
+---------------------------------------+   +---------------------------------------+
|   DATABASE LAYER (`database/`)        |   | TELEPHONY MODULE (`telephony_service`)|
| - Local Dev: SQLite (`loan_...db`)    |   | - Safe Browser/Local Simulator (Free) |
| - Production: PostgreSQL              |   | - Twilio Voice API (`<Say hi-IN>`)    |
| - Tables: `users`, `customers`,       |   | - Exotel Cloud Telephony (India DLT)  |
|   `call_logs`, `ptp_commitments`,     |   | - Sarvam AI / Google Cloud / WebSpeech|
|   `audit_logs`                        |   |   Hindi STT & Neural TTS              |
+---------------------------------------+   +---------------------------------------+
```

---

## 2. Project Folder Structure

```text
ai-loan-collection-agent/
├── .env.example                       # Environment template (no real secrets)
├── requirements.txt                   # Python dependencies
├── README.md                          # Architecture, Cost Matrix, Android GitHub & Telephony Guide
├── backend/
│   ├── config.py                      # Environment & RBI compliance settings
│   ├── security.py                    # Loan masking, encryption, RBAC, calling-hour guardrails
│   ├── hindi_conversation_engine.py   # Hindi/Hinglish NLU, 6 core intents, polite dialogue builder
│   ├── telephony_service.py           # Separate telephony module (Simulator, Twilio, Exotel)
│   └── main.py                        # FastAPI server & REST endpoints
├── database/
│   ├── schema.sql                     # SQLite & PostgreSQL compatible schema
│   └── sample_customers.csv           # Fictional Indian customer dataset
├── frontend/
│   └── index.html                     # Complete standalone mobile-friendly dashboard & Hindi voice app
└── tests/
    └── test_agent.py                  # Automated pytest suite verifying guardrails & Hindi NLU
```

---

## 3. Cost Breakdown: Free vs. Paid Requirements

> **Important Transparency Rule**: Real PSTN phone calls to mobile numbers **cannot** be placed for free without a licensed telephony provider. This system includes a **100% free Hindi Voice Simulator** for browser/mobile testing and a modular telephony connector for live calls when credentials are provided.

| Component | Free / Open-Source Option (Included) | Paid Production Option (When Needed) |
| :--- | :--- | :--- |
| **Dashboard, CRM, PTP & Audit Log** | **100% Free** (HTML/Tailwind/JS + FastAPI + SQLite) | Free on Render/Railway free tier or ₹400/mo VPS |
| **Database** | **100% Free** (SQLite local, Neon/Supabase Postgres free tier) | Managed PostgreSQL (~$15/mo for high volume) |
| **Hindi Voice TTS & STT (In-App Testing)** | **100% Free** via Browser Web Speech API (`hi-IN` & `en-IN`) | Sarvam AI Bulbul / Google Cloud Chirp (`hi-IN`) for PSTN lines |
| **AI Conversation Engine** | **100% Free** deterministic Hindi/Hinglish NLU + Gemini Free Tier API | Paid LLM tokens if exceeding free rate limits |
| **Outbound PSTN Phone Calls** | **Not Possible for Free** (Use built-in Hindi Voice Simulator safely) | **Paid Required**: Exotel (India) or Twilio (~₹0.75–₹1.50/min + TRAI DLT KYC) |
| **SMS / WhatsApp Payment Links** | Simulated in Dashboard Audit Log | Paid DLT-registered SMS / WhatsApp Business API |

---

## 4. Android Mobile Phone Deployment & GitHub Guide (No PC Required!)

You can manage the code repository, deploy the backend, and use the dashboard entirely from an **Android phone**:

### Step A: Manage Repository on GitHub from Android
1. Open **Chrome** on your Android phone or install the official **GitHub Mobile App** from the Google Play Store.
2. Sign in to [github.com](https://github.com) and tap **+** -> **New repository** -> name it `ai-loan-collection-agent` (set to **Private** for security).
3. Tap **Add file** -> **Upload files** in mobile Chrome, select the extracted files from `ai-loan-collection-agent.zip` on your phone, and tap **Commit changes**.
4. **Never upload a `.env` file containing real API keys.** Instead, configure secrets inside your hosting provider's Environment Variables dashboard.

### Step B: Deploy Backend & Database from Android Browser
1. Log in to **[Render.com](https://render.com)** or **[Railway.app](https://railway.app)** from mobile Chrome using your GitHub account.
2. Tap **New +** -> **Web Service** -> connect your `ai-loan-collection-agent` GitHub repository.
3. Set Build Command: `pip install -r requirements.txt`
4. Set Start Command: `uvicorn backend.main:app --host 0.0.0.0 --port $PORT`
5. Under **Environment Variables**, paste the keys from `.env.example` (keep `TELEPHONY_PROVIDER=simulator` until you are ready for live calls).
6. Tap **Deploy**. Within 2 minutes you get an HTTPS URL you can open on any Android phone and tap **"Add to Home Screen"** like a native mobile app.

---

## 5. How to Configure Telephony Provider & Test Calls Safely

1. **Phase 1 — Safe Sandbox Testing (Default)**:
   - Keep `TELEPHONY_PROVIDER="simulator"` in `.env`.
   - Test all 6 Hindi customer responses (`"Main aaj payment kar dunga"`, `"Main 28 October ko payment karunga"`, `"Maine payment kar diya hai"`, `"Abhi paise nahi hain"`, `"Mujhe baad mein call karna"`, `"Galat number hai"`), verify PTP creation, and test RBI time-window blocking (before 8 AM / after 7 PM IST) without dialing any real phone number.
2. **Phase 2 — Internal Whitelist Testing with Twilio or Exotel**:
   - Create an **Exotel** (recommended for India TRAI 140-series telemarketing/transactional compliance) or **Twilio** account.
   - Verify **only your own personal mobile number** in the provider's Verified Caller IDs / Sandbox list.
   - Set `TELEPHONY_PROVIDER="twilio"` (or `"exotel"`) and populate `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_CALLER_ID`, and `PUBLIC_WEBHOOK_BASE_URL` in `.env`.
   - Initiate a manual test call to your own verified number from the dashboard and verify that the Hindi greeting asks for identity confirmation before mentioning any EMI amount.
