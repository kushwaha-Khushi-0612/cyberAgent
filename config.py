# ╔══════════════════════════════════════════════════════╗
# ║         RAKSHAK AI — CONFIGURATION FILE             ║
# ║   Fill in your details HERE only. Don't touch       ║
# ║   main.py or call_me.py for credentials.            ║
# ╚══════════════════════════════════════════════════════╝

# ── Twilio Credentials (from https://console.twilio.com) ──
TWILIO_ACCOUNT_SID = __import__("os").getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN  = __import__("os").getenv("TWILIO_AUTH_TOKEN")

# ── Phone Numbers ──
TWILIO_NUMBER      = "+15186349138"               # Your Twilio number (with +1)
YOUR_NUMBER        = "+918896538118"              # YOUR mobile number (with +91)

# ── Server URL ──
BASE_URL           = "https://sound-licensing-paper-seminars.trycloudflare.com"
