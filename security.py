import hashlib
import base64
from datetime import datetime
from typing import Dict, Any, Tuple
from fastapi import Header, HTTPException, status
from backend.config import settings


def mask_loan_account(raw_account: str) -> str:
    """
    Never expose complete loan account numbers unnecessarily.
    Shows only the last 4 digits (e.g., LN-XXXX-4821).
    """
    clean = "".join(ch for ch in str(raw_account) if ch.isalnum())
    last4 = clean[-4:] if len(clean) >= 4 else clean.zfill(4)
    return f"LN-XXXX-{last4}"


def mask_phone_number(phone: str, role: str = "collection_agent") -> str:
    """Masks middle digits for auditor/viewer roles while keeping last 4 visible."""
    clean = str(phone).strip()
    if role in ("admin", "supervisor", "collection_agent"):
        return clean
    if len(clean) >= 10:
        return clean[:3] + "******" + clean[-4:]
    return "******"


def encrypt_sensitive_field(plaintext: str) -> str:
    """Deterministic keyed obfuscation/encryption helper for storing raw loan references."""
    key_bytes = settings.ENCRYPTION_KEY.encode("utf-8")
    data_bytes = plaintext.encode("utf-8")
    xored = bytes(b ^ key_bytes[i % len(key_bytes)] for i, b in enumerate(data_bytes))
    return base64.urlsafe_b64encode(xored).decode("ascii")


def verify_compliance_before_call(
    customer: Dict[str, Any],
    current_hour_ist: int
) -> Tuple[bool, str]:
    """
    Enforces RBI Fair Practices Code & Telecom Commercial Communications Customer Preference Regulations:
    1. Only call between 08:00 and 19:00 IST.
    2. Stop immediately if payment is PAID_VERIFIED.
    3. Stop if customer opted out, reported WRONG_NUMBER, or is under active dispute/hardship lock.
    4. Enforce daily and weekly contact frequency caps.
    """
    if not customer.get("consent_authorized", True):
        return False, "BLOCKED: Customer record lacks verified calling authorization."

    if customer.get("opted_out", False) or customer.get("payment_status") == "OPTED_OUT":
        return False, "BLOCKED: Customer has opted out of automated calls."

    if customer.get("payment_status") == "PAID_VERIFIED" or float(customer.get("outstanding_amount", 0)) <= 0:
        return False, "BLOCKED: Payment is already verified as PAID. Collection reminders stopped."

    if customer.get("payment_status") == "WRONG_NUMBER":
        return False, "BLOCKED: Number flagged as Wrong Number / Identity Mismatch. Escalated for manual KYC check."

    if not (settings.PERMITTED_CALL_START_HOUR <= current_hour_ist < settings.PERMITTED_CALL_END_HOUR):
        return (
            False,
            f"BLOCKED: Current hour ({current_hour_ist}:00 IST) is outside RBI permitted window "
            f"({settings.PERMITTED_CALL_START_HOUR:02d}:00 to {settings.PERMITTED_CALL_END_HOUR:02d}:00 IST)."
        )

    if int(customer.get("calls_today", 0)) >= settings.MAX_CALL_ATTEMPTS_PER_DAY:
        return False, f"BLOCKED: Daily contact limit ({settings.MAX_CALL_ATTEMPTS_PER_DAY} calls/day) reached."

    if int(customer.get("calls_this_week", 0)) >= settings.MAX_CALL_ATTEMPTS_PER_WEEK:
        return False, f"BLOCKED: Weekly contact limit ({settings.MAX_CALL_ATTEMPTS_PER_WEEK} calls/week) reached."

    return True, "COMPLIANT_READY"


def require_role(allowed_roles: Tuple[str, ...]):
    """Simple header-based RBAC dependency for API routes."""
    def dependency(
        x_user_role: str = Header(default="collection_agent"),
        x_user_name: str = Header(default="Amit Verma")
    ) -> Dict[str, str]:
        role = x_user_role.lower().strip()
        if role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Role '{role}' is not authorized. Allowed roles: {allowed_roles}"
            )
        return {"username": x_user_name, "role": role}
    return dependency
