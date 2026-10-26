"""
FastAPI Backend for the AI Loan Collection Calling Agent.
Provides REST endpoints for:
- Dashboard KPIs & Prioritization Engine
- Customer Database CRUD, Search, Filtering, and CSV Import/Export with Loan Account Masking
- Manual & Scheduled Outbound Calling with RBI Compliance Guardrails
- Interactive Hindi AI Conversation & Promise-to-Pay (PTP) Recording
- Twilio / Exotel Webhooks (TwiML)
- Audit Log & Filtered CSV Report Exports
"""
import csv
import io
import json
import sqlite3
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any

from fastapi import FastAPI, UploadFile, File, Query, HTTPException, Response, Depends, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, StreamingResponse
from pydantic import BaseModel, Field

from backend.config import settings
from backend.security import (
    mask_loan_account,
    mask_phone_number,
    encrypt_sensitive_field,
    verify_compliance_before_call,
    require_role,
)
from backend.hindi_conversation_engine import (
    build_opening_greeting,
    build_emi_disclosure_after_verification,
    analyze_customer_utterance,
)
from backend.telephony_service import TelephonyIntegrationService

BASE_PATH = Path(__file__).resolve().parent.parent
DB_PATH = BASE_PATH / "loan_collection.db"
SCHEMA_PATH = BASE_PATH / "database" / "schema.sql"
SAMPLE_CSV_PATH = BASE_PATH / "database" / "sample_customers.csv"

app = FastAPI(
    title=settings.APP_NAME,
    version="1.0.0",
    description="Hindi-first RBI-compliant AI Loan Collection Calling Agent & Dashboard API"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

telephony_service = TelephonyIntegrationService()


def get_db() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def compute_priority_score(payment_status: str, days_past_due: int, outstanding_amount: float) -> int:
    """Configurable prioritization engine (0-100) for collection workflow."""
    if payment_status in ("PAID_VERIFIED", "OPTED_OUT", "WRONG_NUMBER"):
        return 0
    if payment_status in ("DISPUTE_ESCALATED", "HARDSHIP_REVIEW"):
        return 25
    score = 40
    if payment_status == "OVERDUE":
        score += 30
    elif payment_status == "PTP_RECORDED":
        score += 15
    score += min(20, max(0, int(days_past_due) * 2))
    if float(outstanding_amount) >= 7000:
        score += 10
    return min(100, score)


def log_audit_event(
    conn: sqlite3.Connection,
    actor_username: str,
    actor_role: str,
    action_type: str,
    target_entity: str,
    target_reference: str,
    details: str
) -> None:
    conn.execute(
        """INSERT INTO audit_logs
           (actor_username, actor_role, action_type, target_entity, target_reference, details)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (actor_username, actor_role, action_type, target_entity, target_reference, details)
    )


def init_database() -> None:
    conn = get_db()
    with open(SCHEMA_PATH, "r", encoding="utf-8") as f:
        conn.executescript(f.read())

    cur = conn.execute("SELECT COUNT(*) as cnt FROM customers")
    if cur.fetchone()["cnt"] == 0 and SAMPLE_CSV_PATH.exists():
        with open(SAMPLE_CSV_PATH, "r", encoding="utf-8") as csvfile:
            reader = csv.DictReader(csvfile)
            for row in reader:
                masked = mask_loan_account(row["loan_account_masked"])
                encrypted = encrypt_sensitive_field(row["loan_account_masked"])
                dpd = int(row.get("days_past_due", 0))
                out_amt = float(row.get("outstanding_amount", 0))
                status_val = row.get("payment_status", "UPCOMING")
                prio = compute_priority_score(status_val, dpd, out_amt)
                conn.execute(
                    """INSERT INTO customers (
                        customer_code, full_name, phone_number, loan_account_masked,
                        loan_account_encrypted, branch, assigned_employee, preferred_language,
                        emi_amount, outstanding_amount, due_date, days_past_due,
                        payment_status, priority_score, consent_authorized, opted_out, notes
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        row["customer_code"],
                        row["full_name"],
                        row["phone_number"],
                        masked,
                        encrypted,
                        row["branch"],
                        row["assigned_employee"],
                        row.get("preferred_language", "hi-IN"),
                        float(row["emi_amount"]),
                        out_amt,
                        row["due_date"],
                        dpd,
                        status_val,
                        prio,
                        row.get("consent_authorized", "true").lower() == "true",
                        row.get("opted_out", "false").lower() == "true",
                        row.get("notes", "")
                    )
                )

        # Seed initial call and PTP record for CUST-1004 (Meena Kumari)
        c4 = conn.execute("SELECT id FROM customers WHERE customer_code = 'CUST-1004'").fetchone()
        if c4:
            conn.execute(
                """INSERT INTO call_logs (
                    call_reference, customer_id, initiated_by, initiation_mode,
                    telephony_provider, call_duration_seconds, identity_verified,
                    recording_consent_given, detected_intent, customer_utterance,
                    ai_response, call_outcome
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    "CALL-SEED-1001", c4["id"], "Priya Singh", "MANUAL_EMPLOYEE",
                    "simulator", 48, 1, 1, "PTP_COMMITMENT_DATE",
                    "Main 28 October ko payment karunga.",
                    "Bahut dhanyavaad Meena Kumari ji! Humne 28 October ka PTP note kar liya hai.",
                    "ANSWERED_PTP_FUTURE"
                )
            )
            call_id = conn.execute("SELECT last_insert_rowid() as lid").fetchone()["lid"]
            conn.execute(
                """INSERT INTO ptp_commitments (
                    ptp_reference, customer_id, call_log_id, customer_response,
                    promised_date, promised_amount, followup_status, call_outcome, recorded_by
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    "PTP-SEED-2001", c4["id"], call_id,
                    "Main 28 October ko payment karunga.",
                    "2026-10-28", 5100.00, "PENDING_VERIFICATION",
                    "ANSWERED_PTP_FUTURE", "AI Voice Assistant (Priya Singh)"
                )
            )

        log_audit_event(
            conn, "SYSTEM_INIT", "admin", "SEED_DATABASE",
            "customers", "BATCH-INIT", "Initialized SQLite database with 8 fictional loan accounts and masked account numbers."
        )
        conn.commit()
    conn.close()


init_database()


class CallSimulationRequest(BaseModel):
    customer_id: int
    customer_utterance: str = Field(..., description="Hindi, Hinglish, or English customer response")
    initiation_mode: str = Field(default="MANUAL_EMPLOYEE")
    identity_verified: bool = Field(default=True)
    recording_consent_given: bool = Field(default=True)
    simulated_hour_ist: int = Field(default=11, ge=0, le=23)


class VerifyPaymentRequest(BaseModel):
    utr_reference: str = Field(..., min_length=4)




@app.get("/", response_class=HTMLResponse)
def serve_dashboard():
    """Serves the mobile-friendly AI Loan Collection Dashboard directly at the root URL."""
    frontend_file = BASE_PATH / "frontend" / "index.html"
    if frontend_file.exists():
        return HTMLResponse(content=frontend_file.read_text(encoding="utf-8"), status_code=200)
    root_file = BASE_PATH / "index.html"
    if root_file.exists():
        return HTMLResponse(content=root_file.read_text(encoding="utf-8"), status_code=200)
    return HTMLResponse(content="<h1>AI Loan Collection Agent API Running</h1>", status_code=200)


@app.get("/api/health")
def health_check():
    return {
        "status": "ok",
        "app_name": settings.APP_NAME,
        "telephony": telephony_service.get_provider_status(),
        "rbi_window_ist": f"{settings.PERMITTED_CALL_START_HOUR:02d}:00 - {settings.PERMITTED_CALL_END_HOUR:02d}:00"
    }


@app.get("/api/dashboard/summary")
def get_dashboard_summary():
    conn = get_db()
    customers = [dict(r) for r in conn.execute("SELECT * FROM customers").fetchall()]
    calls = [dict(r) for r in conn.execute("SELECT * FROM call_logs").fetchall()]
    ptps = [dict(r) for r in conn.execute("SELECT * FROM ptp_commitments").fetchall()]
    conn.close()

    total_customers = len(customers)
    calls_attempted = len(calls)
    calls_answered = sum(1 for c in calls if c["call_outcome"].startswith("ANSWERED_"))
    promised_to_pay = sum(1 for c in customers if c["payment_status"] == "PTP_RECORDED") or len(ptps)
    payments_verified = sum(1 for c in customers if c["payment_status"] == "PAID_VERIFIED")
    requiring_followup = sum(
        1 for c in customers
        if c["payment_status"] in ("OVERDUE", "HARDSHIP_REVIEW", "DISPUTE_ESCALATED")
    )
    failed_or_callback = sum(
        1 for c in calls
        if c["call_outcome"] in ("NO_ANSWER", "BLOCKED_COMPLIANCE_GUARDRAIL", "ANSWERED_CALLBACK_SCHEDULED")
    )

    return {
        "total_assigned_customers": total_customers,
        "calls_attempted": calls_attempted,
        "calls_answered": calls_answered,
        "customers_promised_to_pay": promised_to_pay,
        "payments_verified": payments_verified,
        "customers_requiring_followup": requiring_followup,
        "failed_calls_and_callbacks": failed_or_callback,
        "answer_rate_pct": round((calls_answered / calls_attempted * 100), 1) if calls_attempted else 0.0,
        "telephony_status": telephony_service.get_provider_status()
    }


@app.get("/api/customers")
def list_customers(
    search: Optional[str] = Query(default=None),
    status: Optional[str] = Query(default=None),
    branch: Optional[str] = Query(default=None),
    employee: Optional[str] = Query(default=None),
    user: Dict[str, str] = Depends(require_role(("admin", "supervisor", "collection_agent", "auditor")))
):
    conn = get_db()
    query = "SELECT * FROM customers WHERE 1=1"
    params: List[Any] = []

    if search:
        query += " AND (LOWER(full_name) LIKE ? OR LOWER(customer_code) LIKE ? OR LOWER(loan_account_masked) LIKE ? OR phone_number LIKE ?)"
        s = f"%{search.lower().strip()}%"
        params.extend([s, s, s, s])
    if status and status != "ALL":
        query += " AND payment_status = ?"
        params.append(status)
    if branch and branch != "ALL":
        query += " AND branch = ?"
        params.append(branch)
    if employee and employee != "ALL":
        query += " AND assigned_employee = ?"
        params.append(employee)

    query += " ORDER BY priority_score DESC, days_past_due DESC"
    rows = [dict(r) for r in conn.execute(query, params).fetchall()]
    conn.close()

    for r in rows:
        # Never expose loan_account_encrypted to API clients
        r.pop("loan_account_encrypted", None)
        r["phone_number"] = mask_phone_number(r["phone_number"], user["role"])

    return {"count": len(rows), "customers": rows}


@app.post("/api/customers/import-csv")
async def import_customers_csv(
    file: UploadFile = File(...),
    user: Dict[str, str] = Depends(require_role(("admin", "supervisor")))
):
    content = (await file.read()).decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(content))
    conn = get_db()
    imported = 0
    for row in reader:
        code = row.get("customer_code") or f"CUST-{uuid.uuid4().hex[:6].upper()}"
        raw_acc = row.get("loan_account_masked") or row.get("loan_account") or "LN0000"
        masked = mask_loan_account(raw_acc)
        encrypted = encrypt_sensitive_field(raw_acc)
        dpd = int(row.get("days_past_due", 0))
        out_amt = float(row.get("outstanding_amount", 0))
        status_val = row.get("payment_status", "UPCOMING")
        prio = compute_priority_score(status_val, dpd, out_amt)

        conn.execute(
            """INSERT OR REPLACE INTO customers (
                customer_code, full_name, phone_number, loan_account_masked,
                loan_account_encrypted, branch, assigned_employee, preferred_language,
                emi_amount, outstanding_amount, due_date, days_past_due,
                payment_status, priority_score, consent_authorized, opted_out, notes
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                code,
                row["full_name"],
                row["phone_number"],
                masked,
                encrypted,
                row.get("branch", "Main Branch"),
                row.get("assigned_employee", user["username"]),
                row.get("preferred_language", "hi-IN"),
                float(row.get("emi_amount", out_amt)),
                out_amt,
                row.get("due_date", "2026-10-30"),
                dpd,
                status_val,
                prio,
                True,
                False,
                row.get("notes", "Imported via CSV")
            )
        )
        imported += 1

    log_audit_event(
        conn, user["username"], user["role"], "CSV_CUSTOMER_IMPORT",
        "customers", file.filename or "upload.csv", f"Imported {imported} customer records with automatic loan account masking."
    )
    conn.commit()
    conn.close()
    return {"status": "success", "imported_count": imported}


@app.post("/api/calls/simulate-or-initiate")
def simulate_or_initiate_call(
    req: CallSimulationRequest,
    user: Dict[str, str] = Depends(require_role(("admin", "supervisor", "collection_agent")))
):
    conn = get_db()
    row = conn.execute("SELECT * FROM customers WHERE id = ?", (req.customer_id,)).fetchone()
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="Customer not found")

    customer = dict(row)

    # 1. Check RBI & Telecom Compliance Guardrails
    telephony_res = telephony_service.initiate_outbound_call(
        customer=customer,
        initiated_by=user["username"],
        initiation_mode=req.initiation_mode,
        current_hour_ist=req.simulated_hour_ist
    )

    call_ref = f"CALL-{uuid.uuid4().hex[:8].upper()}"

    if not telephony_res["success"]:
        conn.execute(
            """INSERT INTO call_logs (
                call_reference, customer_id, initiated_by, initiation_mode,
                telephony_provider, identity_verified, recording_consent_given,
                detected_intent, customer_utterance, ai_response, call_outcome
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                call_ref, customer["id"], user["username"], req.initiation_mode,
                telephony_res["mode"], 0, 0, "BLOCKED_BY_GUARDRAIL",
                req.customer_utterance, telephony_res["message"], "BLOCKED_COMPLIANCE_GUARDRAIL"
            )
        )
        log_audit_event(
            conn, user["username"], user["role"], "CALL_BLOCKED_GUARDRAIL",
            "customers", customer["customer_code"], telephony_res["message"]
        )
        conn.commit()
        conn.close()
        return {
            "call_reference": call_ref,
            "allowed": False,
            "guardrail_message": telephony_res["message"],
            "telephony": telephony_res
        }

    # 2. Build Greeting, EMI Disclosure, and AI Response to Customer Utterance
    greeting = build_opening_greeting(customer)
    disclosure = build_emi_disclosure_after_verification(customer)
    nlu = analyze_customer_utterance(req.customer_utterance, customer)

    transcript = [
        {"speaker": "AI Assistant", "text_hi": greeting["hindi_devanagari"], "text_rom": greeting["hinglish"]},
        {"speaker": "Customer", "text_hi": "हाँ, मैं बोल रहा हूँ।", "text_rom": "Haan, main bol raha hoon."},
        {"speaker": "AI Assistant", "text_hi": disclosure["hindi_devanagari"], "text_rom": disclosure["hinglish"]},
        {"speaker": "Customer", "text_hi": req.customer_utterance, "text_rom": req.customer_utterance},
        {"speaker": "AI Assistant", "text_hi": nlu["ai_reply_hindi"], "text_rom": nlu["ai_reply_hinglish"]},
    ]

    conn.execute(
        """INSERT INTO call_logs (
            call_reference, customer_id, initiated_by, initiation_mode,
            telephony_provider, provider_call_sid, call_duration_seconds,
            identity_verified, recording_consent_given, detected_intent,
            customer_utterance, ai_response, call_outcome, escalated_to_employee, transcript_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            call_ref,
            customer["id"],
            user["username"],
            req.initiation_mode,
            telephony_res["mode"],
            telephony_res.get("call_sid"),
            45,
            int(req.identity_verified),
            int(req.recording_consent_given),
            nlu["intent"],
            req.customer_utterance,
            nlu["ai_reply_hindi"],
            nlu["call_outcome"],
            customer["assigned_employee"] if nlu["escalate_to_human"] else None,
            json.dumps(transcript, ensure_ascii=False)
        )
    )
    call_log_id = conn.execute("SELECT last_insert_rowid() as lid").fetchone()["lid"]

    # 3. Record PTP Commitment if customer promised a payment or reported payment
    ptp_record = None
    if nlu["ptp_date"]:
        ptp_ref = f"PTP-{uuid.uuid4().hex[:8].upper()}"
        conn.execute(
            """INSERT INTO ptp_commitments (
                ptp_reference, customer_id, call_log_id, customer_response,
                promised_date, promised_amount, followup_status, call_outcome, recorded_by
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                ptp_ref,
                customer["id"],
                call_log_id,
                req.customer_utterance,
                nlu["ptp_date"],
                nlu["ptp_amount"] or customer["outstanding_amount"],
                nlu["followup_status"],
                nlu["call_outcome"],
                f"AI Assistant ({user['username']})"
            )
        )
        ptp_record = {
            "ptp_reference": ptp_ref,
            "customer_code": customer["customer_code"],
            "promised_date": nlu["ptp_date"],
            "promised_amount": nlu["ptp_amount"] or customer["outstanding_amount"],
            "followup_status": nlu["followup_status"],
            "call_outcome": nlu["call_outcome"]
        }

    # 4. Update customer status and call counters
    new_status = nlu["new_payment_status"]
    new_prio = compute_priority_score(new_status, customer["days_past_due"], customer["outstanding_amount"])
    conn.execute(
        """UPDATE customers
           SET payment_status = ?,
               priority_score = ?,
               calls_today = calls_today + 1,
               calls_this_week = calls_this_week + 1,
               last_called_at = CURRENT_TIMESTAMP,
               updated_at = CURRENT_TIMESTAMP
           WHERE id = ?""",
        (new_status, new_prio, customer["id"])
    )

    log_audit_event(
        conn,
        user["username"],
        user["role"],
        f"AI_CALL_{nlu['call_outcome']}",
        "customers",
        customer["customer_code"],
        f"Intent={nlu['intent']} | Status->{new_status} | PTP={nlu['ptp_date']}"
    )
    conn.commit()
    conn.close()

    return {
        "call_reference": call_ref,
        "allowed": True,
        "telephony": telephony_res,
        "conversation": {
            "greeting": greeting,
            "emi_disclosure": disclosure,
            "nlu_analysis": nlu,
            "transcript": transcript
        },
        "ptp_recorded": ptp_record
    }


@app.post("/api/customers/{customer_id}/verify-payment")
def verify_customer_payment(
    customer_id: int,
    req: VerifyPaymentRequest,
    user: Dict[str, str] = Depends(require_role(("admin", "supervisor")))
):
    """
    Marks a customer's payment as PAID_VERIFIED after checking reliable banking records (UTR),
    sets outstanding_amount to 0, and automatically stops all collection reminders.
    """
    conn = get_db()
    row = conn.execute("SELECT * FROM customers WHERE id = ?", (customer_id,)).fetchone()
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="Customer not found")

    customer = dict(row)
    conn.execute(
        """UPDATE customers
           SET payment_status = 'PAID_VERIFIED',
               outstanding_amount = 0.0,
               priority_score = 0,
               notes = ?,
               updated_at = CURRENT_TIMESTAMP
           WHERE id = ?""",
        (f"Verified paid via UTR {req.utr_reference}. Collection reminders stopped.", customer_id)
    )
    conn.execute(
        """UPDATE ptp_commitments
           SET followup_status = 'KEPT_PAID'
           WHERE customer_id = ? AND followup_status = 'PENDING_VERIFICATION'""",
        (customer_id,)
    )
    log_audit_event(
        conn, user["username"], user["role"], "VERIFY_PAYMENT_STOP_REMINDERS",
        "customers", customer["customer_code"],
        f"Verified UTR {req.utr_reference}. Status set to PAID_VERIFIED and reminders stopped."
    )
    conn.commit()
    conn.close()
    return {
        "status": "PAID_VERIFIED",
        "customer_code": customer["customer_code"],
        "utr_reference": req.utr_reference,
        "collection_reminders_stopped": True
    }


@app.get("/api/ptp")
def list_ptp_commitments():
    conn = get_db()
    rows = [
        dict(r) for r in conn.execute(
            """SELECT p.*, c.customer_code, c.full_name, c.loan_account_masked, c.branch, c.assigned_employee
               FROM ptp_commitments p
               JOIN customers c ON p.customer_id = c.id
               ORDER BY p.recorded_at DESC"""
        ).fetchall()
    ]
    conn.close()
    return {"count": len(rows), "ptp_commitments": rows}


@app.get("/api/audit-logs")
def list_audit_logs():
    conn = get_db()
    rows = [dict(r) for r in conn.execute("SELECT * FROM audit_logs ORDER BY id DESC LIMIT 200").fetchall()]
    conn.close()
    return {"count": len(rows), "audit_logs": rows}


@app.get("/api/reports/export-csv")
def export_report_csv(
    branch: Optional[str] = Query(default=None),
    employee: Optional[str] = Query(default=None),
    outcome: Optional[str] = Query(default=None),
    user: Dict[str, str] = Depends(require_role(("admin", "supervisor", "auditor")))
):
    conn = get_db()
    query = """
        SELECT c.customer_code, c.full_name, c.loan_account_masked, c.branch,
               c.assigned_employee, c.emi_amount, c.outstanding_amount,
               c.due_date, c.days_past_due, c.payment_status,
               COALESCE(l.call_outcome, 'NOT_CALLED') as last_call_outcome,
               COALESCE(l.call_started_at, '') as last_call_time
        FROM customers c
        LEFT JOIN (
            SELECT customer_id, call_outcome, call_started_at
            FROM call_logs
            WHERE id IN (SELECT MAX(id) FROM call_logs GROUP BY customer_id)
        ) l ON c.id = l.customer_id
        WHERE 1=1
    """
    params: List[Any] = []
    if branch and branch != "ALL":
        query += " AND c.branch = ?"
        params.append(branch)
    if employee and employee != "ALL":
        query += " AND c.assigned_employee = ?"
        params.append(employee)
    if outcome and outcome != "ALL":
        query += " AND COALESCE(l.call_outcome, 'NOT_CALLED') = ?"
        params.append(outcome)

    rows = [dict(r) for r in conn.execute(query, params).fetchall()]
    log_audit_event(
        conn, user["username"], user["role"], "EXPORT_CSV_REPORT",
        "reports", "CSV_EXPORT", f"Exported {len(rows)} rows (branch={branch}, employee={employee}, outcome={outcome})"
    )
    conn.commit()
    conn.close()

    output = io.StringIO()
    fieldnames = [
        "customer_code", "full_name", "loan_account_masked", "branch",
        "assigned_employee", "emi_amount", "outstanding_amount", "due_date",
        "days_past_due", "payment_status", "last_call_outcome", "last_call_time"
    ]
    writer = csv.DictWriter(output, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(rows)

    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=authorized_collection_report.csv"}
    )


@app.post("/api/telephony/twilio/twiml")
def twilio_twiml_webhook(customer_id: int = Query(...)):
    conn = get_db()
    row = conn.execute("SELECT * FROM customers WHERE id = ?", (customer_id,)).fetchone()
    conn.close()
    if not row:
        raise HTTPException(status_code=404, detail="Customer not found")
    xml = telephony_service.generate_hindi_twiml_greeting(dict(row))
    return Response(content=xml, media_type="application/xml")


@app.post("/api/telephony/twilio/gather")
def twilio_gather_webhook(
    customer_id: int = Query(...),
    stage: str = Query(default="verify"),
    SpeechResult: str = Form(default="हाँ")
):
    conn = get_db()
    row = conn.execute("SELECT * FROM customers WHERE id = ?", (customer_id,)).fetchone()
    conn.close()
    if not row:
        raise HTTPException(status_code=404, detail="Customer not found")
    customer = dict(row)

    if stage == "verify":
        disclosure = build_emi_disclosure_after_verification(customer)
        xml = telephony_service.generate_hindi_twiml_reply(
            disclosure["hindi_devanagari"], customer_id=customer_id, end_call=False
        )
        return Response(content=xml, media_type="application/xml")

    nlu = analyze_customer_utterance(SpeechResult, customer)
    xml = telephony_service.generate_hindi_twiml_reply(
        nlu["ai_reply_hindi"], customer_id=customer_id, end_call=True
    )
    return Response(content=xml, media_type="application/xml")
