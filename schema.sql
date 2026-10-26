-- ============================================================================
-- AI LOAN COLLECTION AGENT - DATABASE SCHEMA (SQLite & PostgreSQL Compatible)
-- Built with RBI Fair Practices Code, DPDP Act 2023, & Audit Trail Compliance
-- ============================================================================

CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username VARCHAR(64) UNIQUE NOT NULL,
    full_name VARCHAR(120) NOT NULL,
    role VARCHAR(32) NOT NULL CHECK (role IN ('admin', 'supervisor', 'collection_agent', 'auditor')),
    branch VARCHAR(64) NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    is_active BOOLEAN DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS customers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    customer_code VARCHAR(32) UNIQUE NOT NULL,
    full_name VARCHAR(120) NOT NULL,
    phone_number VARCHAR(20) NOT NULL,
    loan_account_masked VARCHAR(32) NOT NULL,
    loan_account_encrypted TEXT NOT NULL,
    branch VARCHAR(64) NOT NULL,
    assigned_employee VARCHAR(64) NOT NULL,
    preferred_language VARCHAR(16) DEFAULT 'hi-IN',
    emi_amount NUMERIC(12, 2) NOT NULL,
    outstanding_amount NUMERIC(12, 2) NOT NULL,
    due_date DATE NOT NULL,
    days_past_due INTEGER DEFAULT 0,
    payment_status VARCHAR(32) NOT NULL CHECK (payment_status IN ('UPCOMING', 'OVERDUE', 'PTP_RECORDED', 'PAID_VERIFIED', 'DISPUTE_ESCALATED', 'HARDSHIP_REVIEW', 'WRONG_NUMBER', 'OPTED_OUT')),
    priority_score INTEGER DEFAULT 50,
    consent_authorized BOOLEAN DEFAULT 1,
    opted_out BOOLEAN DEFAULT 0,
    calls_today INTEGER DEFAULT 0,
    calls_this_week INTEGER DEFAULT 0,
    last_called_at TIMESTAMP NULL,
    next_followup_at TIMESTAMP NULL,
    notes TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS call_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    call_reference VARCHAR(40) UNIQUE NOT NULL,
    customer_id INTEGER NOT NULL REFERENCES customers(id),
    initiated_by VARCHAR(64) NOT NULL,
    initiation_mode VARCHAR(24) NOT NULL CHECK (initiation_mode IN ('MANUAL_EMPLOYEE', 'SCHEDULED_CAMPAIGN', 'CALLBACK_REQUEST')),
    telephony_provider VARCHAR(32) NOT NULL,
    provider_call_sid VARCHAR(80) NULL,
    call_started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    call_duration_seconds INTEGER DEFAULT 0,
    identity_verified BOOLEAN DEFAULT 0,
    recording_consent_given BOOLEAN DEFAULT 0,
    detected_intent VARCHAR(48) NOT NULL,
    customer_utterance TEXT DEFAULT '',
    ai_response TEXT DEFAULT '',
    call_outcome VARCHAR(40) NOT NULL CHECK (call_outcome IN (
        'ANSWERED_PTP_TODAY',
        'ANSWERED_PTP_FUTURE',
        'ANSWERED_ALREADY_PAID',
        'ANSWERED_HARDSHIP_ESCALATED',
        'ANSWERED_CALLBACK_SCHEDULED',
        'ANSWERED_WRONG_NUMBER_STOPPED',
        'ANSWERED_DISPUTE_ESCALATED',
        'NO_ANSWER',
        'BLOCKED_COMPLIANCE_GUARDRAIL'
    )),
    escalated_to_employee VARCHAR(64) NULL,
    transcript_json TEXT DEFAULT '[]'
);

CREATE TABLE IF NOT EXISTS ptp_commitments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ptp_reference VARCHAR(40) UNIQUE NOT NULL,
    customer_id INTEGER NOT NULL REFERENCES customers(id),
    call_log_id INTEGER NOT NULL REFERENCES call_logs(id),
    recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    customer_response TEXT NOT NULL,
    promised_date DATE NOT NULL,
    promised_amount NUMERIC(12, 2) NOT NULL,
    followup_status VARCHAR(32) NOT NULL CHECK (followup_status IN ('PENDING_VERIFICATION', 'KEPT_PAID', 'BROKEN_FOLLOWUP', 'CANCELLED')),
    call_outcome VARCHAR(40) NOT NULL,
    recorded_by VARCHAR(64) NOT NULL
);

CREATE TABLE IF NOT EXISTS audit_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    actor_username VARCHAR(64) NOT NULL,
    actor_role VARCHAR(32) NOT NULL,
    action_type VARCHAR(64) NOT NULL,
    target_entity VARCHAR(64) NOT NULL,
    target_reference VARCHAR(64) NOT NULL,
    details TEXT NOT NULL,
    ip_address VARCHAR(45) DEFAULT '127.0.0.1'
);

CREATE INDEX IF NOT EXISTS idx_customers_status ON customers(payment_status);
CREATE INDEX IF NOT EXISTS idx_customers_due_date ON customers(due_date);
CREATE INDEX IF NOT EXISTS idx_customers_branch ON customers(branch);
CREATE INDEX IF NOT EXISTS idx_ptp_promised_date ON ptp_commitments(promised_date);
CREATE INDEX IF NOT EXISTS idx_audit_timestamp ON audit_logs(timestamp);
