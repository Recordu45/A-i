import os
from dotenv import load_dotenv

load_dotenv()

class Settings:
    APP_NAME: str = os.getenv("APP_NAME", "AI Loan Collection Agent")
    APP_ENV: str = os.getenv("APP_ENV", "development")
    SECRET_KEY: str = os.getenv("SECRET_KEY", "dev-only-secret-change-in-production")
    ENCRYPTION_KEY: str = os.getenv("ENCRYPTION_KEY", "dev-only-encryption-key-32bytes!")
    LENDER_NAME: str = os.getenv("LENDER_NAME", "Bharat Samriddhi Finance Ltd.")
    HELPLINE_NUMBER: str = os.getenv("HELPLINE_NUMBER", "1800-120-9900")
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./loan_collection.db")

    # RBI Compliance Guardrails
    PERMITTED_CALL_START_HOUR: int = int(os.getenv("PERMITTED_CALL_START_HOUR", "8"))
    PERMITTED_CALL_END_HOUR: int = int(os.getenv("PERMITTED_CALL_END_HOUR", "19"))
    MAX_CALL_ATTEMPTS_PER_DAY: int = int(os.getenv("MAX_CALL_ATTEMPTS_PER_DAY", "2"))
    MAX_CALL_ATTEMPTS_PER_WEEK: int = int(os.getenv("MAX_CALL_ATTEMPTS_PER_WEEK", "5"))
    REQUIRE_RECORDING_CONSENT: bool = os.getenv("REQUIRE_RECORDING_CONSENT", "true").lower() == "true"

    # Telephony & AI Providers
    TELEPHONY_PROVIDER: str = os.getenv("TELEPHONY_PROVIDER", "simulator")
    TWILIO_ACCOUNT_SID: str = os.getenv("TWILIO_ACCOUNT_SID", "")
    TWILIO_AUTH_TOKEN: str = os.getenv("TWILIO_AUTH_TOKEN", "")
    TWILIO_CALLER_ID: str = os.getenv("TWILIO_CALLER_ID", "")
    PUBLIC_WEBHOOK_BASE_URL: str = os.getenv("PUBLIC_WEBHOOK_BASE_URL", "http://localhost:8000")

    EXOTEL_SID: str = os.getenv("EXOTEL_SID", "")
    EXOTEL_API_KEY: str = os.getenv("EXOTEL_API_KEY", "")
    EXOTEL_API_TOKEN: str = os.getenv("EXOTEL_API_TOKEN", "")
    EXOTEL_CALLER_ID: str = os.getenv("EXOTEL_CALLER_ID", "")
    EXOTEL_SUBDOMAIN: str = os.getenv("EXOTEL_SUBDOMAIN", "api.in.exotel.com")

    SPEECH_PROVIDER: str = os.getenv("SPEECH_PROVIDER", "browser_web_speech")
    LLM_PROVIDER: str = os.getenv("LLM_PROVIDER", "rule_and_llm_hybrid")
    LLM_API_KEY: str = os.getenv("LLM_API_KEY", "")
    LLM_MODEL_NAME: str = os.getenv("LLM_MODEL_NAME", "gemini-2.5-flash")

settings = Settings()
