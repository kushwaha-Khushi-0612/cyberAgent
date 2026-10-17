"""
Rakshak AI — Outbound Call Trigger
Run this script and YOUR phone will ring.
No ISD charges. Twilio calls you.

Usage:
    python call_me.py
"""

from twilio.rest import Client

# ── All credentials come from config.py — edit ONLY that file ──
from config import TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_NUMBER, YOUR_NUMBER, BASE_URL

def make_outbound_call():
    client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)

    call = client.calls.create(
        to=YOUR_NUMBER,                              # Twilio calls your phone
        from_=TWILIO_NUMBER,                         # using your Twilio number
        url=f"{BASE_URL}/incoming-call",             # same flow as before
        method="POST",
    )

    print("=" * 50)
    print("  Rakshak AI — Outbound Call Initiated!")
    print("=" * 50)
    print(f"  Calling:   {YOUR_NUMBER}")
    print(f"  From:      {TWILIO_NUMBER}")
    print(f"  Call SID:  {call.sid}")
    print(f"  Status:    {call.status}")
    print("=" * 50)
    print("  Your phone will ring in a few seconds.")
    print("  Pick up and speak in Hindi!")
    print("=" * 50)

if __name__ == "__main__":
    make_outbound_call()
