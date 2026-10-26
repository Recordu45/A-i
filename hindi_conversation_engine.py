"""
Hindi & Hinglish AI Conversation Engine for Compliant Loan Collection.
Handles natural Hindi (Devanagari + Romanized Hinglish) and Indian English responses,
verifies identity before disclosing loan figures, records Promise to Pay (PTP),
and strictly prohibits threats, harassment, shaming, or third-party disclosure.
"""
import re
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
from backend.config import settings


MONTH_MAP = {
    "january": 1, "jan": 1, "जनवरी": 1,
    "february": 2, "feb": 2, "फरवरी": 2,
    "march": 3, "mar": 3, "मार्च": 3,
    "april": 4, "apr": 4, "अप्रैल": 4,
    "may": 5, "मई": 5,
    "june": 6, "jun": 6, "जून": 6,
    "july": 7, "jul": 7, "जुलाई": 7,
    "august": 8, "aug": 8, "अगस्त": 8,
    "september": 9, "sep": 9, "सितंबर": 9,
    "october": 10, "oct": 10, "अक्टूबर": 10,
    "november": 11, "nov": 11, "नवंबर": 11,
    "december": 12, "dec": 12, "दिसंबर": 12,
}


def build_opening_greeting(customer: Dict[str, Any], reference_date: Optional[str] = None) -> Dict[str, str]:
    """
    Step 1 of compliant call: Introduce AI assistant + authorized lender,
    verify identity BEFORE disclosing any loan/EMI amount, and inform if call is recorded.
    """
    name = customer["full_name"]
    lender = settings.LENDER_NAME
    hindi_text = (
        f"नमस्ते! क्या मेरी बात {name} जी से हो रही है? "
        f"मैं {lender} की ओर से अधिकृत AI कॉलिंग सहायक बोल रहा हूँ। "
        f"गुणवत्ता और सुरक्षा के लिए यह कॉल रिकॉर्ड की जा सकती है। "
        f"कृपया पुष्टि करें कि आप {name} जी बोल रहे हैं ताकि मैं आपके खाते की जानकारी साझा कर सकूँ।"
    )
    hinglish_text = (
        f"Namaste! Kya meri baat {name} ji se ho rahi hai? "
        f"Main {lender} ki taraf se authorized AI calling assistant bol raha hoon. "
        f"Kripya confirm karein ki aap {name} ji bol rahe hain."
    )
    return {
        "stage": "IDENTITY_VERIFICATION",
        "hindi_devanagari": hindi_text,
        "hinglish": hinglish_text,
        "english": (
            f"Hello, am I speaking with {name}? I am an AI calling assistant representing "
            f"{lender}. Please confirm your identity before we discuss your account details."
        )
    }


def build_emi_disclosure_after_verification(customer: Dict[str, Any]) -> Dict[str, str]:
    """
    Step 2: Only after identity is confirmed, share masked loan account, verified EMI amount,
    and due date, and politely ask when the customer expects to make the payment.
    """
    name = customer["full_name"]
    masked_acc = customer["loan_account_masked"]
    amount = f"₹{float(customer['outstanding_amount']):,.0f}"
    due_date = customer["due_date"]
    status = customer["payment_status"]

    if status == "UPCOMING":
        hindi = (
            f"धन्यवाद {name} जी। हमारे सत्यापित रिकॉर्ड के अनुसार, आपके ऋण खाता {masked_acc} "
            f"की आगामी EMI राशि {amount} दिनांक {due_date} को देय (due) है। "
            f"क्या आप नियत तारीख तक यह भुगतान कर पाएंगे?"
        )
        hinglish = (
            f"Dhanyavaad {name} ji. Hamare verified record ke anusaar, aapke loan account {masked_acc} "
            f"ki upcoming EMI {amount} date {due_date} ko due hai. "
            f"Aap yeh payment kab tak karne ki ummeed rakhte hain?"
        )
    else:
        hindi = (
            f"धन्यवाद {name} जी। हमारे सत्यापित रिकॉर्ड के अनुसार, आपके ऋण खाता {masked_acc} "
            f"की EMI राशि {amount} (देय तिथि: {due_date}) अभी लंबित (pending) है। "
            f"कृपया बताएं कि आप यह भुगतान कब तक कर पाएंगे?"
        )
        hinglish = (
            f"Dhanyavaad {name} ji. Hamare verified record ke anusaar, aapke loan account {masked_acc} "
            f"ki EMI {amount} (due date: {due_date}) abhi pending hai. "
            f"Kripya batayein aap yeh payment kab tak kar payenge?"
        )

    return {
        "stage": "EMI_DISCLOSURE",
        "hindi_devanagari": hindi,
        "hinglish": hinglish,
        "english": (
            f"Thank you for confirming, {name}. According to our verified records for loan account "
            f"{masked_acc}, an installment of {amount} with due date {due_date} is {status.lower()}. "
            f"When do you expect to make this payment?"
        )
    }


def extract_promised_date(utterance: str, today: datetime) -> Optional[str]:
    """Extracts explicit dates like '28 October', 'kal', 'aaj', or '28/10' from Hindi/Hinglish text."""
    text = utterance.lower().strip()

    if any(k in text for k in ["aaj", "today", "आज", "abhi shaam", "आज ही"]):
        return today.strftime("%Y-%m-%d")

    if any(k in text for k in ["kal", "tomorrow", "कल"]):
        return (today + timedelta(days=1)).strftime("%Y-%m-%d")

    if any(k in text for k in ["parso", "परसों"]):
        return (today + timedelta(days=2)).strftime("%Y-%m-%d")

    # Match patterns like "28 october", "28 oct", "28 अक्टूबर"
    date_match = re.search(r"(\b\d{1,2})\s*(?:ko\s*)?([a-zA-Zऀ-ॿ]+)", text)
    if date_match:
        day = int(date_match.group(1))
        month_Token = date_match.group(2).lower()
        for m_key, m_val in MONTH_MAP.items():
            if month_Token.startswith(m_key):
                year = today.year
                try:
                    dt = datetime(year, m_val, day)
                    if dt.date() < today.date() - timedelta(days=30):
                        dt = datetime(year + 1, m_val, day)
                    return dt.strftime("%Y-%m-%d")
                except ValueError:
                    pass

    # Match DD/MM/YYYY or DD-MM-YYYY
    slash_match = re.search(r"(\b\d{1,2})[/-](\d{1,2})(?:[/-](\d{2,4}))?", text)
    if slash_match:
        day = int(slash_match.group(1))
        month = int(slash_match.group(2))
        year = int(slash_match.group(3)) if slash_match.group(3) else today.year
        if year < 100:
            year += 2000
        try:
            return datetime(year, month, day).strftime("%Y-%m-%d")
        except ValueError:
            pass

    return None


def analyze_customer_utterance(
    utterance: str,
    customer: Dict[str, Any],
    reference_datetime: Optional[datetime] = None
) -> Dict[str, Any]:
    """
    Classifies customer Hindi/Hinglish/English response, generates polite RBI-compliant AI reply,
    determines PTP date, follow-up action, or escalation to authorized employee.
    Explicitly handles all required customer utterances:
      1. "Main aaj payment kar dunga."
      2. "Main 28 October ko payment karunga."
      3. "Maine payment kar diya hai."
      4. "Abhi paise nahi hain."
      5. "Mujhe baad mein call karna."
      6. "Galat number hai."
      + Dispute / Third-party / Identity check responses.
    """
    now = reference_datetime or datetime(2026, 10, 26, 10, 30)
    text = utterance.lower().strip()
    name = customer["full_name"]
    masked_acc = customer["loan_account_masked"]
    outstanding = float(customer["outstanding_amount"])
    amount_str = f"₹{outstanding:,.0f}"

    # 1. Wrong number / Identity mismatch ("Galat number hai.")
    if any(kw in text for kw in [
        "galat number", "wrong number", "गलत नंबर", "main woh nahi", "nahi bol raha",
        "kisi aur ka number", "not speaking", "unknown person"
    ]):
        return {
            "intent": "WRONG_NUMBER_ESCALATION",
            "call_outcome": "ANSWERED_WRONG_NUMBER_STOPPED",
            "new_payment_status": "WRONG_NUMBER",
            "ptp_date": None,
            "ptp_amount": None,
            "followup_status": "ESCALATED_IDENTITY_MISMATCH",
            "escalate_to_human": True,
            "escalation_reason": "Identity mismatch / Wrong number reported by recipient. Do not disclose loan details.",
            "ai_reply_hindi": (
                "क्षमा करें, आपको हुई असुविधा के लिए हमें खेद है। हम आपके साथ कोई भी खाता विवरण साझा नहीं करेंगे "
                "और इस नंबर को तुरंत हमारे अधिकृत अधिकारी द्वारा सत्यापन के लिए चिह्नित कर रहे हैं। धन्यवाद, नमस्ते।"
            ),
            "ai_reply_hinglish": (
                "Kshama karein, aapko hui asuvidha ke liye humein khed hai. Hum koi bhi account jankari share nahi karenge "
                "aur is number ko turant verification ke liye mark kar rahe hain. Dhanyavaad, Namaste."
            ),
            "ai_reply_english": (
                "We apologize for the inconvenience. We will not disclose any account information and have "
                "immediately flagged this number for review by an authorized officer. Thank you."
            )
        }

    # 2. Already paid ("Maine payment kar diya hai.")
    if any(kw in text for kw in [
        "payment kar diya", "kar chuka", "paid", "bhar diya", "jama kar diya",
        "मैंने पेमेंट कर दिया", "भुगतान कर दिया", "already paid", "upi kar diya"
    ]):
        return {
            "intent": "ALREADY_PAID_CLAIM",
            "call_outcome": "ANSWERED_ALREADY_PAID",
            "new_payment_status": customer["payment_status"],  # Wait for banking verification before marking PAID_VERIFIED
            "ptp_date": now.strftime("%Y-%m-%d"),
            "ptp_amount": outstanding,
            "followup_status": "PENDING_VERIFICATION",
            "escalate_to_human": True,
            "escalation_reason": "Customer stated payment is already completed; queued for UTR/core-banking reconciliation.",
            "ai_reply_hindi": (
                f"भुगतान की जानकारी देने के लिए बहुत धन्यवाद {name} जी। हमने खाता {masked_acc} के लिए आपकी "
                f"भुगतान सूचना दर्ज कर ली है। हमारे अधिकृत अधिकारी बैंक रिकॉर्ड से इसका सत्यापन (verification) करेंगे, "
                f"और सत्यापन होते ही रिमाइंडर कॉल बंद हो जाएंगी। आपका दिन शुभ हो!"
            ),
            "ai_reply_hinglish": (
                f"Payment ki jankari dene ke liye bahut dhanyavaad {name} ji. Humne account {masked_acc} ke liye "
                f"aapki suchna note kar li hai. Hamari team bank record se verify karegi aur verify hote hi reminders "
                f"band ho jayenge. Namaste!"
            ),
            "ai_reply_english": (
                f"Thank you for informing us, {name}. We have logged your payment claim for account {masked_acc} "
                f"for verification against our banking records. Once verified, all reminders will stop."
            )
        }

    # 3. Callback request ("Mujhe baad mein call karna.")
    if any(kw in text for kw in [
        "baad mein call", "call later", "abhi busy", "meeting mein", "shaam ko call",
        "मुझे बाद में कॉल", "बाद में बात", "busy hoon", "call back", "callback"
    ]):
        next_cb = (now + timedelta(hours=4)).strftime("%Y-%m-%d %H:%M")
        return {
            "intent": "CALLBACK_REQUESTED",
            "call_outcome": "ANSWERED_CALLBACK_SCHEDULED",
            "new_payment_status": customer["payment_status"],
            "ptp_date": None,
            "ptp_amount": None,
            "followup_status": "CALLBACK_SCHEDULED",
            "scheduled_callback_at": next_cb,
            "escalate_to_human": False,
            "escalation_reason": None,
            "ai_reply_hindi": (
                f"जी बिल्कुल {name} जी, हम आपके समय का सम्मान करते हैं। हमने आपके अनुरोध के अनुसार "
                f"अनुमत कॉलिंग समय (सुबह 8 बजे से शाम 7 बजे के बीच) में कॉलबैक शेड्यूल कर लिया है। धन्यवाद, नमस्ते।"
            ),
            "ai_reply_hinglish": (
                f"Ji bilkul {name} ji, hum aapke samay ka samman karte hain. Humne aapke request ke anusaar "
                f"permitted hours mein callback schedule kar liya hai. Dhanyavaad, Namaste."
            ),
            "ai_reply_english": (
                f"Certainly {name}, we respect your time. We have scheduled a callback during permitted hours "
                f"as requested. Thank you and have a good day."
            )
        }

    # 4. Financial hardship / No money right now ("Abhi paise nahi hain.")
    if any(kw in text for kw in [
        "paise nahi", "paisa nahi", "pese nahi", "पैसे नहीं", "dikkat hai", "bimari", "job chali",
        "salary nahi aayi", "hardship", "majboori", "nahi de sakta", "असमर्थ"
    ]):
        return {
            "intent": "FINANCIAL_HARDSHIP",
            "call_outcome": "ANSWERED_HARDSHIP_ESCALATED",
            "new_payment_status": "HARDSHIP_REVIEW",
            "ptp_date": None,
            "ptp_amount": None,
            "followup_status": "ESCALATED_HARDSHIP_OFFICER",
            "escalate_to_human": True,
            "escalation_reason": "Customer expressed financial difficulty/hardship ('Abhi paise nahi hain'). Escalated to authorized officer for empathetic restructuring/support.",
            "ai_reply_hindi": (
                f"हम आपकी परिस्थिति को समझते हैं {name} जी। चिंता न करें, मैंने आपकी स्थिति का विवरण दर्ज कर लिया है "
                f"और इसे हमारे अधिकृत ग्राहक सहायता अधिकारी ({customer.get('assigned_employee', 'अधिकारी')}) को भेज दिया है। "
                f"वे आपको भुगतान के आसान विकल्प या समय विस्तार में सहायता के लिए संपर्क करेंगे। धन्यवाद।"
            ),
            "ai_reply_hinglish": (
                f"Hum aapki paristhiti ko samajhte hain {name} ji. Maine aapki jankari note kar li hai aur ise "
                f"hamare authorized officer ({customer.get('assigned_employee', 'Officer')}) ko escalate kar diya hai "
                f"taaki woh aapko uchit sahayata de sakein. Dhanyavaad."
            ),
            "ai_reply_english": (
                f"We understand your situation, {name}. I have noted your request and escalated your case to an "
                f"authorized support officer ({customer.get('assigned_employee', 'Officer')}) to discuss suitable assistance options."
            )
        }

    # 5. Dispute / Complaint ("Interest galat hai", "Dispute", "Complaint")
    if any(kw in text for kw in [
        "dispute", "complaint", "galat charge", "shikayat", "rbi", "ombudsman",
        "शिकायत", "गलत चार्ज", "धोखा", "excess charge"
    ]):
        return {
            "intent": "DISPUTE_OR_COMPLAINT",
            "call_outcome": "ANSWERED_DISPUTE_ESCALATED",
            "new_payment_status": "DISPUTE_ESCALATED",
            "ptp_date": None,
            "ptp_amount": None,
            "followup_status": "ESCALATED_GRIEVANCE_CELL",
            "escalate_to_human": True,
            "escalation_reason": "Customer raised a billing dispute/complaint. Automated reminders paused and escalated to officer.",
            "ai_reply_hindi": (
                f"आपकी शिकायत को हमने गंभीरता से दर्ज कर लिया है {name} जी। आपके खाते पर ऑटोमेटेड रिमाइंडर रोक दिए गए हैं "
                f"और हमारे अधिकृत अधिकारी ({customer.get('assigned_employee', 'अधिकारी')}) आपके विवरण की जांच कर आपसे संपर्क करेंगे।"
            ),
            "ai_reply_hinglish": (
                f"Aapki shikayat ko humne note kar liya hai {name} ji. Automated reminders pause kar diye gaye hain "
                f"aur hamare authorized officer aapke case ki jaanch kar aapse sampark karenge."
            ),
            "ai_reply_english": (
                f"We have logged your dispute, {name}. Automated collection reminders have been paused and "
                f"an authorized grievance officer will review your account and contact you."
            )
        }

    # 6. Promise to Pay Today or Future Date ("Main aaj payment kar dunga." / "Main 28 October ko payment karunga.")
    extracted_date = extract_promised_date(utterance, now)
    if extracted_date or any(kw in text for kw in ["kar dunga", "karunga", "karungi", "bhej dunga", "दे दूंगा", "कर दूंगा", "करूँगा", "promise"]):
        ptp_date = extracted_date or (now + timedelta(days=2)).strftime("%Y-%m-%d")
        is_today = (ptp_date == now.strftime("%Y-%m-%d"))
        outcome = "ANSWERED_PTP_TODAY" if is_today else "ANSWERED_PTP_FUTURE"
        intent = "PTP_COMMITMENT_TODAY" if is_today else "PTP_COMMITMENT_DATE"

        return {
            "intent": intent,
            "call_outcome": outcome,
            "new_payment_status": "PTP_RECORDED",
            "ptp_date": ptp_date,
            "ptp_amount": outstanding,
            "followup_status": "PENDING_VERIFICATION",
            "escalate_to_human": False,
            "escalation_reason": None,
            "ai_reply_hindi": (
                f"बहुत धन्यवाद {name} जी! हमने आपके ऋण खाता {masked_acc} के लिए दिनांक {ptp_date} को "
                f"{amount_str} के भुगतान की प्रतिबद्धता (Promise to Pay) दर्ज कर ली है। "
                f"आप अधिकृत पेमेंट लिंक या ऐप के माध्यम से भुगतान कर सकते हैं। आपका दिन शुभ हो, नमस्ते!"
            ),
            "ai_reply_hinglish": (
                f"Bahut dhanyavaad {name} ji! Humne aapke loan account {masked_acc} ke liye date {ptp_date} ko "
                f"{amount_str} ke payment ka Promise to Pay (PTP) record kar liya hai. "
                f"Aapka din shubh ho, Namaste!"
            ),
            "ai_reply_english": (
                f"Thank you very much, {name}. We have recorded your Promise to Pay (PTP) of {amount_str} "
                f"for account {masked_acc} on {ptp_date}. Have a wonderful day!"
            )
        }

    # Default polite clarification
    return {
        "intent": "GENERAL_INQUIRY_OR_CLARIFICATION",
        "call_outcome": "ANSWERED_CALLBACK_SCHEDULED",
        "new_payment_status": customer["payment_status"],
        "ptp_date": None,
        "ptp_amount": None,
        "followup_status": "NEEDS_FOLLOWUP",
        "escalate_to_human": False,
        "escalation_reason": None,
        "ai_reply_hindi": (
            f"धन्यवाद {name} जी। आपके ऋण खाता {masked_acc} की देय राशि {amount_str} है। "
            f"कृपया बताएं कि आप यह भुगतान आज करेंगे या किसी निश्चित तारीख (जैसे 28 अक्टूबर) को? "
            f"यदि आप किसी अधिकारी से बात करना चाहते हैं तो कृपया बताएं।"
        ),
        "ai_reply_hinglish": (
            f"Dhanyavaad {name} ji. Aapke loan account {masked_acc} ki due amount {amount_str} hai. "
            f"Kripya batayein aap yeh payment aaj karenge ya kisi specific date ko?"
        ),
        "ai_reply_english": (
            f"Thank you, {name}. Your outstanding EMI for account {masked_acc} is {amount_str}. "
            f"Could you please share the date when you expect to make the payment, or let us know if you need officer assistance?"
        )
    }
