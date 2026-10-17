from fastapi import FastAPI, Request
from fastapi.responses import Response, FileResponse
from fpdf import FPDF
import requests
import os
import speech_recognition as sr
from pydub import AudioSegment
import json
from datetime import datetime
import logging

# ── All credentials come from config.py — edit ONLY that file ──
from config import TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, BASE_URL

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()

REPORTS_DIR = "reports"
TEMP_DIR    = "temp"
os.makedirs(REPORTS_DIR, exist_ok=True)
os.makedirs(TEMP_DIR,    exist_ok=True)

# In-memory session store  (fine for demo; use Redis in production)
sessions: dict = {}


# ══════════════════════════════════════════════
#  HELPER: Download audio from Twilio with auth
# ══════════════════════════════════════════════
def download_audio(url: str, call_sid: str) -> str:
    """Download Twilio recording and return local WAV path."""
    raw_path  = os.path.join(TEMP_DIR, f"{call_sid}_raw.wav")
    conv_path = os.path.join(TEMP_DIR, f"{call_sid}_conv.wav")

    # Twilio requires HTTP Basic Auth to fetch recordings
    response = requests.get(url, auth=(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN), timeout=15)
    response.raise_for_status()

    with open(raw_path, "wb") as f:
        f.write(response.content)

    # Re-encode to standard 16-bit PCM WAV that SpeechRecognition can handle
    audio = AudioSegment.from_file(raw_path)
    audio = audio.set_channels(1).set_frame_rate(16000).set_sample_width(2)
    audio.export(conv_path, format="wav")

    return conv_path


# ══════════════════════════════════════════════
#  HELPER: Speech-to-Text (Hindi)
# ══════════════════════════════════════════════
def transcribe_audio(url: str, call_sid: str) -> str:
    """Convert audio URL → Hindi text. Returns fallback string on failure."""
    try:
        conv_path  = download_audio(url, call_sid)
        recognizer = sr.Recognizer()

        with sr.AudioFile(conv_path) as source:
            # Adjust for ambient noise to improve accuracy
            recognizer.adjust_for_ambient_noise(source, duration=0.5)
            audio_data = recognizer.record(source)

        text = recognizer.recognize_google(audio_data, language="hi-IN")
        logger.info(f"[STT] {call_sid} → {text}")
        return text

    except sr.UnknownValueError:
        logger.warning(f"[STT] Could not understand audio for {call_sid}")
        return "समझ नहीं आया"
    except sr.RequestError as e:
        logger.error(f"[STT] Google API error: {e}")
        return "सर्विस उपलब्ध नहीं"
    except Exception as e:
        logger.error(f"[STT] Unexpected error: {e}")
        return "त्रुटि"


# ══════════════════════════════════════════════
#  HELPER: Detect fraud scenario from transcript
# ══════════════════════════════════════════════
def detect_scenario(text: str) -> str:
    text = text.lower()

    otp_keywords  = ["ओटीपी", "otp", "बैंक", "bank", "खाता", "account",
                     "पासवर्ड", "password", "कॉल", "call", "atm"]
    olx_keywords  = ["olx", "qr", "क्यूआर", "स्कैन", "scan", "ओएलएक्स",
                     "बेचना", "sell", "खरीदना", "buy"]
    job_keywords  = ["job", "नौकरी", "telegram", "टेलीग्राम", "रजिस्ट्रेशन",
                     "registration", "fees", "फीस", "पैसा", "work from home"]
    loan_keywords = ["loan", "लोन", "ऋण", "emi", "insurance", "बीमा"]

    if any(w in text for w in otp_keywords):  return "OTP_FRAUD"
    if any(w in text for w in olx_keywords):  return "OLX_SCAM"
    if any(w in text for w in job_keywords):  return "JOB_SCAM"
    if any(w in text for w in loan_keywords): return "LOAN_FRAUD"
    return "GENERAL_FRAUD"


SCENARIO_LABELS = {
    "OTP_FRAUD":    "OTP / Banking Fraud",
    "OLX_SCAM":     "OLX / QR Code Scam",
    "JOB_SCAM":     "Fake Job / Telegram Scam",
    "LOAN_FRAUD":   "Fake Loan / Insurance Fraud",
    "GENERAL_FRAUD":"General Cyber Fraud",
}

SCENARIO_QUESTIONS = {
    "OTP_FRAUD":  "क्या आपने किसी को अपना बैंक OTP या ATM PIN बताया था? और किस बैंक का नाम लिया गया था?",
    "OLX_SCAM":   "क्या आपने कोई QR कोड स्कैन किया था? और वह कौन सा प्लेटफार्म था — OLX, Facebook?",
    "JOB_SCAM":   "क्या आपसे नौकरी के लिए रजिस्ट्रेशन फीस मांगी गई थी? आपने पैसे कहाँ भेजे?",
    "LOAN_FRAUD": "आपसे कितनी प्रोसेसिंग फीस मांगी गई और किस ऐप या वेबसाइट का उपयोग हुआ?",
    "GENERAL_FRAUD": "यह घटना कब हुई, कहाँ हुई, और आपने कुल कितने पैसे खोए?",
}


# ══════════════════════════════════════════════
#  FONT PATHS  (bundled inside /fonts folder)
# ══════════════════════════════════════════════
BASE_DIR  = os.path.dirname(os.path.abspath(__file__))
FONTS_DIR = os.path.join(BASE_DIR, "fonts")
FONT_HI   = os.path.join(FONTS_DIR, "NotoSansDevanagari-Regular.ttf")
FONT_HI_B = os.path.join(FONTS_DIR, "NotoSansDevanagari-Bold.ttf")
FONT_EN   = os.path.join(FONTS_DIR, "NotoSans-Regular.ttf")


# ══════════════════════════════════════════════
#  HELPER: Generate PDF Report  (Hindi-safe)
# ══════════════════════════════════════════════
def generate_pdf_report(data: dict) -> str:
    pdf = FPDF()
    pdf.add_page()

    # Register Unicode fonts — required for Hindi/Devanagari text
    pdf.add_font("Devanagari", "",  FONT_HI)
    pdf.add_font("Devanagari", "B", FONT_HI_B)
    pdf.add_font("NotoSans",   "",  FONT_EN)

    # ── Header ──
    pdf.set_fill_color(10, 25, 70)
    pdf.rect(0, 0, 210, 32, "F")
    pdf.set_text_color(0, 200, 200)
    pdf.set_font("NotoSans", "", 20)
    pdf.set_y(6)
    pdf.cell(0, 10, "RAKSHAK AI", ln=True, align="C")
    pdf.set_font("NotoSans", "", 11)
    pdf.set_text_color(255, 255, 255)
    pdf.cell(0, 8, "AI-Powered Cybercrime Investigation Report", ln=True, align="C")
    pdf.set_text_color(0, 0, 0)
    pdf.ln(10)

    # ── Case Details Box ──
    pdf.set_fill_color(235, 245, 255)
    pdf.set_draw_color(0, 150, 180)
    pdf.set_line_width(0.4)
    y_box = pdf.get_y()
    pdf.rect(10, y_box, 190, 52, "FD")
    pdf.set_xy(15, y_box + 3)

    def info_row(label_en: str, value: str, hindi: bool = False):
        pdf.set_font("NotoSans", "", 11)
        pdf.set_text_color(10, 25, 70)
        pdf.set_x(15)
        pdf.cell(58, 8, f"{label_en}:", border=0)
        pdf.set_font("Devanagari" if hindi else "NotoSans", "", 11)
        pdf.set_text_color(0, 0, 0)
        pdf.cell(0, 8, value, ln=True)

    info_row("Report Generated", datetime.now().strftime("%d %B %Y, %I:%M %p"))
    info_row("Victim Name",      data.get("name", "N/A"),                         hindi=True)
    info_row("Fraud Category",   SCENARIO_LABELS.get(data.get("scenario",""), "Unknown"))
    info_row("Call Session ID",  data.get("call_sid", "N/A"))
    pdf.ln(6)

    # ── Section helper ──
    def section(title_en: str, body: str, hindi: bool = True):
        pdf.set_fill_color(10, 25, 70)
        pdf.set_text_color(255, 255, 255)
        pdf.set_font("NotoSans", "", 12)
        pdf.cell(0, 9, f"  {title_en}", ln=True, fill=True)
        pdf.set_text_color(30, 30, 30)
        pdf.set_x(12)
        pdf.set_font("Devanagari" if hindi else "NotoSans", "", 11)
        pdf.multi_cell(185, 8, body or "No information provided.")
        pdf.ln(4)

    section("VICTIM'S ACCOUNT OF INCIDENT", data.get("story",   ""))
    section("ADDITIONAL DETAILS / EVIDENCE",  data.get("details", ""))

    # ── Advisory Box ──
    pdf.set_fill_color(255, 243, 205)
    pdf.set_draw_color(255, 165, 0)
    adv_y = pdf.get_y()
    pdf.rect(10, adv_y, 190, 34, "FD")
    pdf.set_xy(15, adv_y + 3)
    pdf.set_font("NotoSans", "", 11)
    pdf.set_text_color(140, 70, 0)
    pdf.cell(0, 7, "IMMEDIATE ACTION RECOMMENDED", ln=True)
    pdf.set_x(15)
    pdf.set_font("NotoSans", "", 10)
    pdf.set_text_color(0, 0, 0)
    pdf.multi_cell(180, 6,
        "1. Call 1930 (National Cybercrime Helpline) immediately.\n"
        "2. Block your bank account — SBI: 1800-11-2211 | HDFC: 1800-202-6161.\n"
        "3. File a complaint at cybercrime.gov.in with this report attached."
    )
    pdf.ln(8)

    # ── Footer ──
    pdf.set_font("NotoSans", "", 9)
    pdf.set_text_color(130, 130, 130)
    pdf.cell(0, 6,
        "This report was automatically generated by Rakshak AI. Confidential — For Official Use Only.",
        align="C")

    # Save
    safe_name = "".join(c for c in data.get("name","Unknown") if c.isalnum() or c in " _-").strip() or "User"
    filename  = f"Rakshak_Report_{safe_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
    path      = os.path.join(REPORTS_DIR, filename)
    pdf.output(path)
    logger.info(f"[PDF] Report saved: {path}")
    return path


# ══════════════════════════════════════════════
#  TWIML HELPERS
# ══════════════════════════════════════════════
def twiml_response(content: str) -> Response:
    return Response(content=content, media_type="application/xml")

def xml(body: str) -> str:
    return f'<?xml version="1.0" encoding="UTF-8"?><Response>{body}</Response>'

def say(text: str) -> str:
    return f'<Say language="hi-IN" voice="Polly.Aditi">{text}</Say>'

def gather_speech(action: str, timeout: int = 5, hints: str = "") -> str:
    hints_attr = f'hints="{hints}"' if hints else ""
    return (f'<Gather action="{BASE_URL}{action}" method="POST" '
            f'input="speech" language="hi-IN" timeout="{timeout}" {hints_attr}/>')

def record(action: str, max_length: int = 45) -> str:
    return (f'<Record action="{BASE_URL}{action}" method="POST" '
            f'maxLength="{max_length}" playBeep="true" trim="trim-silence"/>')


# ══════════════════════════════════════════════
#  ROUTES
# ══════════════════════════════════════════════

@app.post("/incoming-call")
async def incoming_call():
    """Step 0 — Greet caller and ask for their name."""
    body = (
        say("नमस्ते! मैं रक्षक एआई हूँ — आपकी साइबर सुरक्षा सहायक।")
        + say("कृपया बीप के बाद अपना पूरा नाम बोलें।")
        + record("/step1-name", max_length=10)
    )
    return twiml_response(xml(body))


@app.post("/step1-name")
async def step1_name(request: Request):
    """Step 1 — Receive name, confirm it, ask them to describe incident."""
    form     = await request.form()
    call_sid = form.get("CallSid", "unknown")
    audio_url= form.get("RecordingUrl", "")

    name = transcribe_audio(audio_url, call_sid) if audio_url else "अनजान"

    # Store session
    sessions[call_sid] = {
        "call_sid": call_sid,
        "name":     name,
        "scenario": "",
        "story":    "",
        "details":  "",
        "started":  datetime.now().isoformat(),
    }

    body = (
        say(f"धन्यवाद, {name} जी।")
        + say("बीप के बाद कृपया विस्तार से बताएं कि आपके साथ क्या हुआ। "
              "आप हिंदी में बोल सकते हैं। आपके पास 45 सेकंड हैं।")
        + record("/step2-story", max_length=45)
    )
    return twiml_response(xml(body))


@app.post("/step2-story")
async def step2_story(request: Request):
    """Step 2 — Transcribe story, detect fraud type, ask specific follow-up."""
    form     = await request.form()
    call_sid = form.get("CallSid", "unknown")
    audio_url= form.get("RecordingUrl", "")

    if call_sid not in sessions:
        sessions[call_sid] = {"name": "अनजान", "call_sid": call_sid}

    transcript = transcribe_audio(audio_url, call_sid) if audio_url else "कोई जानकारी नहीं"
    scenario   = detect_scenario(transcript)

    sessions[call_sid]["story"]    = transcript
    sessions[call_sid]["scenario"] = scenario

    follow_up = SCENARIO_QUESTIONS.get(scenario, SCENARIO_QUESTIONS["GENERAL_FRAUD"])
    label     = SCENARIO_LABELS.get(scenario, "General Fraud")

    body = (
        say(f"समझ गया। यह मामला {label} जैसा लग रहा है।")
        + say(follow_up)
        + record("/step3-details", max_length=45)
    )
    return twiml_response(xml(body))


@app.post("/step3-details")
async def step3_details(request: Request):
    """Step 3 — Collect extra details, then ask what action they want."""
    form     = await request.form()
    call_sid = form.get("CallSid", "unknown")
    audio_url= form.get("RecordingUrl", "")

    details = transcribe_audio(audio_url, call_sid) if audio_url else "कोई जानकारी नहीं"
    if call_sid in sessions:
        sessions[call_sid]["details"] = details

    body = (
        say("आपकी जानकारी मिल गई है। रक्षक एआई रिपोर्ट तैयार कर रहा है।")
        + say("अब बताएं आप क्या करना चाहते हैं — "
              "पुलिस रिपोर्ट के लिए 1 दबाएं, "
              "बैंक ब्लॉक जानकारी के लिए 2 दबाएं, "
              "या सिर्फ रिपोर्ट सेव करने के लिए 3 दबाएं।")
        + f'<Gather action="{BASE_URL}/final-action" method="POST" numDigits="1" timeout="7"/>'
        + say("कोई जवाब नहीं मिला, रिपोर्ट सेव की जा रही है।")
        + f'<Redirect method="POST">{BASE_URL}/auto-save?CallSid={call_sid}</Redirect>'
    )
    return twiml_response(xml(body))


@app.post("/final-action")
async def final_action(request: Request):
    """Step 4 — Generate PDF + JSON report, give final advice, hang up."""
    form     = await request.form()
    call_sid = form.get("CallSid", "unknown")
    digit    = form.get("Digits", "3")

    data = sessions.get(call_sid, {
        "name": "अनजान", "scenario": "GENERAL_FRAUD",
        "story": "", "details": "", "call_sid": call_sid
    })

    # Generate PDF report
    try:
        pdf_path  = generate_pdf_report(data)
        json_path = os.path.join(REPORTS_DIR, f"Data_{call_sid}.json")
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
        logger.info(f"[SAVE] PDF={pdf_path}, JSON={json_path}")
        report_saved = True
    except Exception as e:
        logger.error(f"[SAVE] Failed: {e}")
        report_saved = False

    advice_map = {
        "1": ("साइबर क्राइम की रिपोर्ट के लिए तुरंत 1930 डायल करें। "
              "यह भारत सरकार की आधिकारिक साइबर हेल्पलाइन है। "
              "आप cybercrime.gov.in पर भी शिकायत दर्ज कर सकते हैं।"),
        "2": ("अपने बैंक का कस्टमर केयर नंबर अभी डायल करें और कहें — "
              "मेरा खाता तुरंत ब्लॉक करें। "
              "SBI: 1800-11-2211, HDFC: 1800-202-6161, Paytm: 0120-4456-456।"),
        "3": ("आपकी रिपोर्ट सुरक्षित रूप से सेव कर ली गई है।"),
    }
    advice = advice_map.get(digit, advice_map["3"])

    saved_msg = "आपकी विस्तृत रिपोर्ट तैयार हो गई है।" if report_saved else ""

    body = (
        say(advice)
        + say(saved_msg)
        + say("रक्षक एआई की सलाह है — कभी भी किसी अजनबी को OTP, PIN, या बैंक जानकारी न दें।")
        + say("रक्षक एआई से जुड़ने के लिए धन्यवाद। सावधान रहें, सुरक्षित रहें।")
        + "<Hangup/>"
    )

    # Clean up session
    sessions.pop(call_sid, None)
    return twiml_response(xml(body))


@app.post("/auto-save")
async def auto_save(request: Request, CallSid: str = "unknown"):
    """Fallback: auto-save if caller doesn't press any digit."""
    data = sessions.get(CallSid, {"name": "अनजान", "call_sid": CallSid})
    try:
        generate_pdf_report(data)
    except Exception as e:
        logger.error(f"[AUTO-SAVE] {e}")

    body = (
        say("आपकी रिपोर्ट स्वचालित रूप से सेव कर ली गई है।")
        + say("धन्यवाद। सुरक्षित रहें।")
        + "<Hangup/>"
    )
    sessions.pop(CallSid, None)
    return twiml_response(xml(body))


# ══════════════════════════════════════════════
#  REPORT DOWNLOAD ENDPOINT (for admin/demo)
# ══════════════════════════════════════════════
@app.get("/reports")
async def list_reports():
    """List all generated reports (for demo viewing)."""
    files = []
    for f in os.listdir(REPORTS_DIR):
        path = os.path.join(REPORTS_DIR, f)
        files.append({
            "filename": f,
            "size_kb":  round(os.path.getsize(path) / 1024, 1),
            "created":  datetime.fromtimestamp(os.path.getctime(path)).strftime("%Y-%m-%d %H:%M:%S"),
            "download": f"{BASE_URL}/download/{f}",
        })
    files.sort(key=lambda x: x["created"], reverse=True)
    return {"total": len(files), "reports": files}


@app.get("/download/{filename}")
async def download_report(filename: str):
    """Download a specific report PDF."""
    path = os.path.join(REPORTS_DIR, filename)
    if not os.path.exists(path):
        return Response(content="File not found", status_code=404)
    return FileResponse(path, media_type="application/pdf", filename=filename)


@app.get("/health")
async def health():
    return {"status": "ok", "service": "Rakshak AI", "sessions_active": len(sessions)}
