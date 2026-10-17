# Rakshak AI — Setup & Run Guide

## What You Need
- Python 3.9+
- A free Twilio account (twilio.com)
- ffmpeg installed on your system
- ngrok (for local testing)

---

## Step 1 — Install ffmpeg

### Windows
Download from https://ffmpeg.org/download.html and add to PATH.

### Mac
```bash
brew install ffmpeg
```

### Linux / Ubuntu
```bash
sudo apt install ffmpeg -y
```

---

## Step 2 — Install Python Dependencies

```bash
cd rakshak_ai
pip install -r requirements.txt
```

---

## Step 3 — Fill in Your Credentials

Open `main.py` and fill in these 3 lines at the top:

```python
TWILIO_ACCOUNT_SID = "ACxxxxxxxxxxxxxxxxxx"   # From Twilio Console
TWILIO_AUTH_TOKEN  = "your_auth_token_here"   # From Twilio Console
BASE_URL           = "https://xxxx.ngrok.io"  # Your ngrok URL (see Step 5)
```

---

## Step 4 — Run the Server

```bash
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

You should see:
```
INFO:     Uvicorn running on http://0.0.0.0:8000
```

---

## Step 5 — Expose with ngrok

In a NEW terminal:
```bash
ngrok http 8000
```

Copy the HTTPS URL it gives you, e.g.:
```
https://abc123def456.ngrok.io
```

Paste this into `main.py` as your `BASE_URL` and restart the server.

---

## Step 6 — Configure Twilio

1. Go to twilio.com → Phone Numbers → your number → Configure
2. Under **Voice & Fax → A Call Comes In**, set:
   - Webhook: `https://your-ngrok-url.ngrok.io/incoming-call`
   - Method: `HTTP POST`
3. Save

---

## Step 7 — Test It!

Call your Twilio number. The AI will:
1. Greet you in Hindi
2. Ask your name (you speak it)
3. Ask you to describe the fraud (you speak for up to 45 seconds)
4. Ask a specific follow-up question based on fraud type detected
5. Give you options (1/2/3)
6. Generate a PDF report automatically

---

## View Generated Reports

Open in browser:
```
http://localhost:8000/reports
```

Download a report:
```
http://localhost:8000/download/Rakshak_Report_Rahul_20240425_143022.pdf
```

---

## Health Check

```
http://localhost:8000/health
```

---

## Common Issues

| Problem | Fix |
|---|---|
| "ffmpeg not found" | Install ffmpeg and restart terminal |
| Audio not transcribing | Check internet connection (Google STT needs internet) |
| Twilio can't reach your server | Make sure ngrok is running and URL is correct in main.py |
| Name comes out garbled | Speak slowly and clearly after the beep |
| PDF not generating | Check the `reports/` folder exists (auto-created on start) |

---

## Folder Structure

```
rakshak_ai/
├── main.py           ← Main application
├── requirements.txt  ← Python packages
├── README.md         ← This file
├── reports/          ← PDF + JSON reports saved here (auto-created)
└── temp/             ← Temporary audio files (auto-created)
```

---

## For the Pitch Demo

1. Start server + ngrok BEFORE the presentation
2. Have your Twilio number ready on your phone
3. Call the number live on stage
4. After the call ends, open the reports URL on your laptop
5. Show the PDF — this is your WOW moment!

**Tip:** Do a full rehearsal call at least twice before the demo.
