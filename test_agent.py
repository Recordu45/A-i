from fastapi.testclient import TestClient
from backend.main import app

client = TestClient(app)


def test_health_and_summary():
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"

    s = client.get("/api/dashboard/summary")
    assert s.status_code == 200
    data = s.json()
    assert data["total_assigned_customers"] >= 8
    assert "payments_verified" in data


def test_customer_masking_and_search():
    r = client.get("/api/customers?search=Rajesh")
    assert r.status_code == 200
    customers = r.json()["customers"]
    assert len(customers) == 1
    assert customers[0]["loan_account_masked"] == "LN-XXXX-4821"
    assert "loan_account_encrypted" not in customers[0]


def test_six_hindi_utterances_and_ptp_recording():
    # 1. "Main aaj payment kar dunga." on CUST-1001
    res1 = client.post("/api/calls/simulate-or-initiate", json={
        "customer_id": 1,
        "customer_utterance": "Main aaj payment kar dunga.",
        "simulated_hour_ist": 11
    })
    assert res1.status_code == 200
    d1 = res1.json()
    assert d1["allowed"] is True
    assert d1["conversation"]["nlu_analysis"]["call_outcome"] == "ANSWERED_PTP_TODAY"
    assert d1["ptp_recorded"] is not None

    # 2. "Main 28 October ko payment karunga." on CUST-1002
    res2 = client.post("/api/calls/simulate-or-initiate", json={
        "customer_id": 2,
        "customer_utterance": "Main 28 October ko payment karunga.",
        "simulated_hour_ist": 11
    })
    d2 = res2.json()
    assert d2["conversation"]["nlu_analysis"]["ptp_date"] == "2026-10-28"

    # 3. "Galat number hai." on CUST-1003
    res3 = client.post("/api/calls/simulate-or-initiate", json={
        "customer_id": 3,
        "customer_utterance": "Galat number hai.",
        "simulated_hour_ist": 12
    })
    d3 = res3.json()
    assert d3["conversation"]["nlu_analysis"]["call_outcome"] == "ANSWERED_WRONG_NUMBER_STOPPED"
    assert d3["conversation"]["nlu_analysis"]["escalate_to_human"] is True


def test_rbi_calling_hours_guardrail():
    # Calling at 21:00 IST (outside 08:00-19:00 window) must be blocked
    res = client.post("/api/calls/simulate-or-initiate", json={
        "customer_id": 7,
        "customer_utterance": "Main aaj payment kar dunga.",
        "simulated_hour_ist": 21
    })
    assert res.status_code == 200
    data = res.json()
    assert data["allowed"] is False
    assert "outside RBI permitted window" in data["guardrail_message"]


def test_paid_verified_stops_calls():
    # CUST-1005 (id=5) is already PAID_VERIFIED
    res = client.post("/api/calls/simulate-or-initiate", json={
        "customer_id": 5,
        "customer_utterance": "Hello",
        "simulated_hour_ist": 11
    })
    assert res.status_code == 200
    assert res.json()["allowed"] is False
    assert "already verified as PAID" in res.json()["guardrail_message"]
