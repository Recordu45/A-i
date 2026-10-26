"""
Separate Telephony Integration Module for Outbound AI Voice Calling.
Supports:
1. 'simulator' (Free local/browser sandbox testing - NEVER claims real PSTN call is placed)
2. 'twilio' (Real PSTN outbound calls via Twilio Voice API + Hindi <Gather>/<Say> TwiML)
3. 'exotel' (Real Indian cloud telephony via Exotel Call API with TRAI DLT / 140-prefix compliance)
"""
import uuid
from typing import Dict, Any
import httpx
from backend.config import settings
from backend.security import verify_compliance_before_call


class TelephonyIntegrationService:
    def __init__(self):
        self.provider = settings.TELEPHONY_PROVIDER.lower().strip()

    def get_provider_status(self) -> Dict[str, Any]:
        """Returns transparent status of whether real telephony credentials are configured."""
        twilio_ready = bool(
            settings.TWILIO_ACCOUNT_SID
            and not settings.TWILIO_ACCOUNT_SID.startswith("ACxxxx")
            and settings.TWILIO_AUTH_TOKEN
            and settings.TWILIO_CALLER_ID
        )
        exotel_ready = bool(
            settings.EXOTEL_SID
            and settings.EXOTEL_API_KEY
            and settings.EXOTEL_API_TOKEN
            and settings.EXOTEL_CALLER_ID
        )
        return {
            "configured_provider": self.provider,
            "real_pstn_calls_enabled": (
                (self.provider == "twilio" and twilio_ready)
                or (self.provider == "exotel" and exotel_ready)
            ),
            "twilio_configured": twilio_ready,
            "exotel_configured": exotel_ready,
            "speech_provider": settings.SPEECH_PROVIDER,
            "notice": (
                "Real outbound phone calls require paid telephony credentials (Twilio or Exotel) "
                "and telecom KYC. In 'simulator' mode, calls run safely in the interactive Hindi voice sandbox."
            )
        }

    def initiate_outbound_call(
        self,
        customer: Dict[str, Any],
        initiated_by: str,
        initiation_mode: str = "MANUAL_EMPLOYEE",
        current_hour_ist: int = 11
    ) -> Dict[str, Any]:
        """
        Validates RBI compliance guardrails first, then dispatches either a safe simulation
        session or a real outbound API request to Twilio/Exotel.
        """
        is_compliant, compliance_msg = verify_compliance_before_call(customer, current_hour_ist)
        if not is_compliant:
            return {
                "success": False,
                "mode": self.provider,
                "real_pstn_call": False,
                "status": "BLOCKED_COMPLIANCE_GUARDRAIL",
                "message": compliance_msg,
                "call_sid": None
            }

        if self.provider == "twilio":
            return self._place_twilio_call(customer, initiated_by, initiation_mode)
        elif self.provider == "exotel":
            return self._place_exotel_call(customer, initiated_by, initiation_mode)
        else:
            sim_sid = f"SIM-{uuid.uuid4().hex[:10].upper()}"
            return {
                "success": True,
                "mode": "simulator",
                "real_pstn_call": False,
                "status": "SIMULATOR_SESSION_READY",
                "message": (
                    "Safe Hindi AI Voice Simulator started. (No real PSTN call placed — configure "
                    "TELEPHONY_PROVIDER='twilio' or 'exotel' in .env with paid credentials for live phone calls.)"
                ),
                "call_sid": sim_sid,
                "initiated_by": initiated_by,
                "initiation_mode": initiation_mode
            }

    def _place_twilio_call(
        self,
        customer: Dict[str, Any],
        initiated_by: str,
        initiation_mode: str
    ) -> Dict[str, Any]:
        if not settings.TWILIO_ACCOUNT_SID or settings.TWILIO_ACCOUNT_SID.startswith("ACxxxx"):
            return {
                "success": False,
                "mode": "twilio",
                "real_pstn_call": False,
                "status": "MISSING_CREDENTIALS",
                "message": "Twilio credentials not set in .env. Cannot place real PSTN phone call without paid Twilio SID/AuthToken.",
                "call_sid": None
            }
        try:
            from twilio.rest import Client
            client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
            webhook_url = f"{settings.PUBLIC_WEBHOOK_BASE_URL}/api/telephony/twilio/twiml?customer_id={customer['id']}"
            call = client.calls.create(
                to=customer["phone_number"],
                from_=settings.TWILIO_CALLER_ID,
                url=webhook_url,
                status_callback=f"{settings.PUBLIC_WEBHOOK_BASE_URL}/api/telephony/twilio/status",
                record=settings.REQUIRE_RECORDING_CONSENT
            )
            return {
                "success": True,
                "mode": "twilio",
                "real_pstn_call": True,
                "status": "QUEUED_PSTN",
                "message": f"Twilio outbound call queued to {customer['phone_number']}.",
                "call_sid": call.sid,
                "initiated_by": initiated_by,
                "initiation_mode": initiation_mode
            }
        except Exception as exc:
            return {
                "success": False,
                "mode": "twilio",
                "real_pstn_call": False,
                "status": "TELEPHONY_ERROR",
                "message": f"Twilio API error: {str(exc)}",
                "call_sid": None
            }

    def _place_exotel_call(
        self,
        customer: Dict[str, Any],
        initiated_by: str,
        initiation_mode: str
    ) -> Dict[str, Any]:
        if not settings.EXOTEL_SID or settings.EXOTEL_SID == "your_exotel_sid":
            return {
                "success": False,
                "mode": "exotel",
                "real_pstn_call": False,
                "status": "MISSING_CREDENTIALS",
                "message": "Exotel credentials not set in .env. Cannot place real Indian PSTN call without paid Exotel account.",
                "call_sid": None
            }
        url = f"https://{settings.EXOTEL_API_KEY}:{settings.EXOTEL_API_TOKEN}@{settings.EXOTEL_SUBDOMAIN}/v1/Accounts/{settings.EXOTEL_SID}/Calls/connect.json"
        payload = {
            "From": customer["phone_number"],
            "CallerId": settings.EXOTEL_CALLER_ID,
            "Url": f"http://my.exotel.com/{settings.EXOTEL_SID}/exoml/start_voice/{customer['id']}",
            "CustomField": f"customer_id={customer['id']}|by={initiated_by}"
        }
        try:
            with httpx.Client(timeout=15.0) as client:
                resp = client.post(url, data=payload)
                resp.raise_for_status()
                data = resp.json()
                sid = data.get("Call", {}).get("Sid", f"EXO-{uuid.uuid4().hex[:8]}")
                return {
                    "success": True,
                    "mode": "exotel",
                    "real_pstn_call": True,
                    "status": "QUEUED_PSTN",
                    "message": f"Exotel outbound call queued to {customer['phone_number']}.",
                    "call_sid": sid,
                    "initiated_by": initiated_by,
                    "initiation_mode": initiation_mode
                }
        except Exception as exc:
            return {
                "success": False,
                "mode": "exotel",
                "real_pstn_call": False,
                "status": "TELEPHONY_ERROR",
                "message": f"Exotel API error: {str(exc)}",
                "call_sid": None
            }

    @staticmethod
    def generate_hindi_twiml_greeting(customer: Dict[str, Any]) -> str:
        """Generates Twilio-compatible TwiML XML with Hindi (hi-IN) neural voice and speech gathering."""
        name = customer["full_name"]
        lender = settings.LENDER_NAME
        cid = customer["id"]
        return f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Gather input="speech" language="hi-IN" speechTimeout="auto" action="/api/telephony/twilio/gather?customer_id={cid}&amp;stage=verify" method="POST">
        <Say language="hi-IN" voice="Polly.Aditi">
            नमस्ते! क्या मेरी बात {name} जी से हो रही है? मैं {lender} की ओर से अधिकृत एआई कॉलिंग सहायक बोल रहा हूँ। यह कॉल गुणवत्ता और सुरक्षा के लिए रिकॉर्ड की जा सकती है। कृपया हां बोलकर अपनी पहचान की पुष्टि करें।
        </Say>
    </Gather>
    <Say language="hi-IN" voice="Polly.Aditi">आपकी ओर से कोई उत्तर प्राप्त नहीं हुआ। हम बाद में पुनः संपर्क करेंगे। नमस्ते।</Say>
</Response>"""

    @staticmethod
    def generate_hindi_twiml_reply(ai_reply_hindi: str, customer_id: int, end_call: bool = True) -> str:
        """Generates TwiML for speaking the AI response in Hindi."""
        if end_call:
            return f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say language="hi-IN" voice="Polly.Aditi">{ai_reply_hindi}</Say>
    <Hangup/>
</Response>"""
        return f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Gather input="speech" language="hi-IN" speechTimeout="auto" action="/api/telephony/twilio/gather?customer_id={customer_id}&amp;stage=ptp" method="POST">
        <Say language="hi-IN" voice="Polly.Aditi">{ai_reply_hindi}</Say>
    </Gather>
</Response>"""
