"""End-to-end checks of the Al Rajhi Takaful (Saudi Arabia) demo journeys — offline agent, no API key needed.

Run:  cd backend && python -m pytest -q
"""
import json
import os
import shutil
from datetime import date

os.environ["GEMINI_API_KEY"] = ""
os.environ["VERTEX_PROJECT"] = ""
os.environ["LLM_PROVIDER"] = "gemini_api"
os.environ["TTS_PROVIDER"] = "off"
os.environ["SYSTEM_STEPS_FAST"] = "1"
os.environ["DATA_DIR"] = os.path.abspath("./data-test")
os.environ["INSURER_NAME"] = "Al Rajhi Takaful"
os.environ["INSURER_SHORT"] = "Al Rajhi Takaful"
shutil.rmtree(os.environ["DATA_DIR"], ignore_errors=True)

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from openpyxl import load_workbook  # noqa: E402

from app.main import app  # noqa: E402

XLSX = os.path.join(os.environ["DATA_DIR"], "art_customer_360.xlsx")
PORTFOLIOS = ("health", "motor", "life", "retirement & savings", "general")


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


class Chat:
    def __init__(self, c):
        self.c, self.sid = c, None

    def __call__(self, msg):
        r = self.c.post("/api/chat", json={"message": msg, "session_id": self.sid})
        assert r.status_code == 200, r.text
        d = r.json()
        self.sid = d["session_id"]
        return d


def tools(r):
    return [t["name"] for t in r["tools_used"]]


def card(r, kind):
    return next(c["data"] for c in reversed(r["cards"]) if c["type"] == kind)


def sheet(name):
    ws = load_workbook(XLSX)[name]
    head = [c.value for c in ws[1]]
    return [dict(zip(head, [c.value for c in row])) for row in ws.iter_rows(min_row=2)]


def words(r):
    return len(r["reply"].split())


# ---------------------------------------------------------------- brand, greeting, scope
def test_arabic_greeting_and_portfolio_first(client):
    say = Chat(client)
    r = say("hi")
    assert r["reply"].startswith("Ahlan wa sahlan!") and "Al Rajhi Takaful" in r["reply"]
    for p in PORTFOLIOS:
        assert p in r["reply"].lower()
    r = say("I need insurance for my company fleet")
    assert "individual plans only" in r["reply"]
    assert client.get("/api/health").json()["insurer"] == "Al Rajhi Takaful"
    assert set(client.get("/api/products").json()["lines"]) == {"health", "motor", "life", "savings", "general"}


def test_replies_stay_short(client):
    say = Chat(client)
    for m in ["motor", "Abdullah Al-Qahtani", "1012345678", "7788 BDR"]:
        r = say(m)
        assert words(r) <= 30, r["reply"]


# ---------------------------------------------------------------- new customer: product → name → ID → plate
def test_new_customer_motor_journey(client):
    say = Chat(client)
    r = say("I want motor insurance")
    assert "full name" in r["reply"] and not r["tools_used"]
    r = say("Abdullah Al-Qahtani")
    assert "National ID or Iqama" in r["reply"] and "Nafath" in r["reply"]
    r = say("1012345678")
    assert "plate" in r["reply"] and not r["tools_used"]
    r = say("7788 BDR")
    k = card(r, "kyc")["draft"]
    assert tools(r) == ["fetch_kyc_from_government"] and "Is that you?" in r["reply"]
    assert k["name"] == "Abdullah Mohammed Al-Qahtani" and k["vehicle"]["make_model"] == "Toyota Camry GLE"
    assert k["name_match"] is True and k["vehicle"]["vehicle_type"] == "car"
    assert "1012345678" not in json.dumps(r)
    r = say("yes")
    reg = card(r, "registered")
    assert reg["registered"] and reg["excel"]["synced"] and "Shukran" in r["reply"]
    assert "Comprehensive" in r["reply"]  # straight to the plan question — no vehicle / city questions
    r = say("go with your suggestion")
    q = card(r, "quote")
    assert q["line"] == "motor" and q["location"] == "Riyadh" and q["vehicle_label"] == "Private Car"
    assert "contribution" not in r["reply"].lower() or "premium" not in r["reply"].lower()
    say("yes")
    r = say("mada")
    done = card(r, "purchase")
    assert done["status"] == "issued" and r["reply"].startswith("Mabrook!")
    row = next(x for x in sheet("Customers") if x["customer_id"] == reg["customer"]["customer_id"])
    assert row["nationality"] == "Saudi" and row["id_reference"] == "1XXXXXX678"
    # the same ID again is recognised as already registered
    say2 = Chat(client)
    say2("motor insurance please")
    say2("Abdullah")
    say2("1012345678")
    r = say2("7788 BDR")
    assert r["identity"]["customer_id"] == reg["customer"]["customer_id"] and "already with us" in r["reply"]


def test_new_customer_health_is_individual(client):
    say = Chat(client)
    r = say("I want health insurance for my family")
    assert "individuals" in r["reply"]
    say("Reem Al Harbi")
    r = say("1098765432")
    assert card(r, "kyc")["draft"]["name"] == "Reem Al Harbi"  # synthetic Yakeen record takes the given name
    r = say("yes that's me")
    assert "chronic" in r["reply"]
    r = say("no")
    q = card(r, "quote")
    assert q["line"] == "health" and set(q["params"]) == {"age", "city", "pre_existing", "copay", "maternity"} and q["premium"]["gst"] > 0
    assert q["subject"].startswith("Individual")


def test_iqama_validation_and_stream_masking(client):
    say = Chat(client)
    say("life insurance")
    say("Anil")
    r = say("my Iqama is 3123456789")  # not a Saudi ID pattern → asks again
    assert not r["tools_used"]
    r = client.post("/api/chat/stream", json={"message": "Iqama 2234567890"})
    events = [json.loads(x[5:]) for x in r.text.split("\n\n") if x.startswith("data:")]
    labels = [e["label"] for e in events if e["type"] == "tool_progress"]
    assert any("Nafath" in x for x in labels) and any("Yakeen" in x for x in labels)
    call = next(e for e in events if e["type"] == "tool_call")
    assert "2234567890" not in json.dumps(call)


# ---------------------------------------------------------------- existing customers
def test_existing_customer_by_mobile_and_claim(client):
    say = Chat(client)
    r = say("What policies do I have?")
    assert not r["tools_used"] and "registered mobile" in r["reply"]
    r = say("my number is 0551234567")
    assert tools(r)[:2] == ["identify_customer", "get_policy_details"] and r["reply"].startswith("Ahlan, Faisal!")
    say("I had an accident")
    say("yesterday")
    say("King Fahd Rd, Riyadh")
    r = say("Another car hit my rear bumper at a signal, Najm report done")
    assert "Which car" in r["reply"] and "Land Cruiser" in r["reply"] and "Elantra" in r["reply"]
    r = say("the Land Cruiser")
    c = card(r, "claim")
    assert c["policy_id"] == "POL-MTR-240118" and c["status"] == "Reported"


def test_existing_customer_motor_uses_elm_vehicle(client):
    say = Chat(client)
    say("I need car insurance")
    r = say("0509876543")
    assert "Ahlan, Sara" in r["reply"] and "plate" in r["reply"]
    r = say("4521 RTA")
    assert tools(r) == ["lookup_vehicle"] and "Land Cruiser" in r["reply"]
    r = say("Comprehensive Plus")
    q = card(r, "quote")
    assert q["vehicle_type"] == "suv" and q["location"] == "Jeddah"


def test_unknown_mobile(client):
    say = Chat(client)
    r = say("I'm an existing customer, my mobile is 0599999999")
    assert tools(r) == ["identify_customer"] and "National ID / Iqama" in r["reply"]


def test_excel_edits_are_picked_up(client):
    wb = load_workbook(XLSX)
    ws = wb["Customers"]
    head = [c.value for c in ws[1]]
    for row in ws.iter_rows(min_row=2):
        if row[0].value == "CUST-1002":
            row[head.index("email")].value = "sara.updated@example.sa"
    wb.save(XLSX)
    os.utime(XLSX, None)
    assert client.get("/api/customers/CUST-1002/360").json()["customer"]["email"] == "sara.updated@example.sa"


# ---------------------------------------------------------------- purchases across portfolios
def test_retirement_plan_full_journey(client):
    say = Chat(client)
    say("I want a retirement savings plan")
    say("my name is Anil Mathew")
    say("2234567890")
    r = say("yes")
    assert "retire" in r["reply"]
    assert "SAR 1,000" in say("60")["reply"]
    assert "quarterly" in say("2000 a month")["reply"]
    assert "Balanced" in say("quarterly")["reply"]
    assert "Takaful protection" in say("balanced")["reply"]
    assert "US citizen" in say("Mary Mathew, wife")["reply"]
    assert "salary" in say("no")["reply"]
    r = say("salary")
    q = card(r, "quote")
    p = q["params"]
    assert q["line"] == "savings" and q["coverage"] == "retirement_plan" and q["premium"]["gst"] == 0
    assert p["retirement_age"] == 60 and p["monthly_contribution"] == 2000 and p["frequency"] == "quarterly"
    assert p["fund"] == "balanced" and p["beneficiary"] == "Mary Mathew, wife"
    assert p["declarations"] == {"us_person": False, "pep": False, "source_of_funds": "salary"}
    pj = q["projection"]
    assert pj["low"] < pj["mid"] < pj["high"] and pj["monthly_income"]["mid"] > 0 and "not guaranteed" in r["reply"]
    assert q["premium"]["instalment"] == 6000  # quarterly
    assert {a["key"] for a in q["adjustables"]} >= {"monthly_contribution", "retirement_age", "fund"}
    say("go ahead")
    r = say("STC pay")
    done = card(r, "purchase")
    assert done["policy_id"].startswith("POL-SAV-") and done["payment"]["method"] == "STC Pay"
    assert "Retire at 60" in done["insured_asset"] and "Mary Mathew" in done["insured_asset"]
    doc = client.get(done["document_url"]).text
    assert "VAT-exempt" in doc and "Takaful" in doc


def test_reprice_slider_streams_engine_steps(client):
    say = Chat(client)
    say("health insurance")
    say("0551234567")
    q = card(say("no"), "quote")
    assert any(a["key"] == "copay" for a in q["adjustables"])
    r = client.post(f"/api/quotes/{q['quote_id']}/reprice/stream", json={"changes": {"copay": 0}, "session_id": say.sid})
    events = [json.loads(x[5:]) for x in r.text.split("\n\n") if x.startswith("data:")]
    labels = " ".join(e["label"] for e in events if e["type"] == "tool_progress")
    for system in ("ESKA", "Neutrinos", "iFoundry", "Payment Engine"):
        assert system in labels
    final = next(e for e in events if e["type"] == "final")
    nq = final["cards"][0]["data"]
    assert final["replaces_quote"] == q["quote_id"] and nq["params"]["copay"] == 0
    assert nq["premium"]["total_premium"] > q["premium"]["total_premium"]  # no co-pay costs more
    r = say("buy it")  # checkout uses the re-priced quote
    assert card(r, "purchase")["quote_id"] == nq["quote_id"]


def test_arabic_conversation(client):
    say = Chat(client)
    r = say("السلام عليكم")
    assert "أمان" in r["reply"] and "أهلاً وسهلاً" in r["reply"]
    assert "اسمك" in say("أبغى تأمين صحي")["reply"]
    say("سارة")
    r = say("0509876543")
    assert "مزمن" in r["reply"]
    r = say("لا")
    assert card(r, "quote")["line"] == "health" and "ريال" in r["reply"]


def test_life_purchase_existing_customer(client):
    say = Chat(client)
    say("Life insurance please")
    r = say("0551234567")
    assert "smoke" in r["reply"]  # age comes from the ID record — not asked
    r = say("no I don't smoke")
    assert "SAR 1,500,000" in r["reply"] and "20 years" in r["reply"]
    r = say("yes")
    q = card(r, "quote")
    assert q["line"] == "life" and q["premium"]["gst"] == 0 and q["sum_insured"] == 1_500_000
    say("go ahead")
    done = card(say("credit card"), "purchase")
    assert done["policy_id"].startswith("POL-LIF-")
    assert date.fromisoformat(done["end_date"]).year == date.today().year + 20


def test_general_home_purchase_with_flood_loading(client):
    say = Chat(client)
    say("insure my villa")
    say("0509876543")  # Sara lives in Jeddah (flood-prone)
    say("1.5 million")
    r = say("contents 200k")
    q = card(r, "quote")
    assert q["line"] == "general" and q["params"]["building_value"] == 1_500_000 and q["zone"] == "Flood-prone"
    say("buy")
    done = card(say("SADAD"), "purchase")
    assert done["policy_id"].startswith("POL-GEN-") and done["payment"]["method"] == "SADAD"


def test_motor_agency_rule(client):
    q = client.post("/api/quotes", json={"customer_id": "CUST-1002", "vehicle_type": "suv", "vehicle_age": 8,
                                         "coverage": "comprehensive_plus", "location": "Abha"}).json()
    rev = client.post("/api/purchase", json={"customer_id": "CUST-1002", "quote_id": q["quote_id"]}).json()
    assert not rev["underwriting"]["accepted"] and "5 years" in rev["underwriting"]["issues"][0]
    assert client.post("/api/quotes", json={"customer_id": "CUST-1002", "vehicle_type": "commercial", "vehicle_age": 1,
                                            "coverage": "tpl", "location": "Riyadh"}).status_code in (400, 422)


def test_expired_iqama_customer_is_refused(client):
    say = Chat(client)
    say("health insurance")
    say("0562223344")
    say("no")
    r = say("yes")
    assert "Iqama" in r["reply"] and "Absher" in r["reply"] and "Which plan" not in r["reply"]


def test_senior_health_referral_and_savings_aml(client):
    q = client.post("/api/quotes/health", json={"customer_id": "CUST-1001", "params": {
        "age": 68, "city": "Riyadh", "pre_existing": True}}).json()
    rev = client.post("/api/purchase", json={"customer_id": "CUST-1001", "quote_id": q["quote_id"]}).json()
    assert not rev["underwriting"]["accepted"] and "65" in rev["underwriting"]["issues"][0]
    q = client.post("/api/quotes/savings", json={"customer_id": "CUST-1001", "plan": "savings_plan", "params": {
        "age": 40, "monthly_contribution": 20000}}).json()
    rev = client.post("/api/purchase", json={"customer_id": "CUST-1001", "quote_id": q["quote_id"]}).json()
    assert not rev["underwriting"]["accepted"] and "source-of-funds" in rev["underwriting"]["issues"][0]


def test_tts_endpoint_falls_back_cleanly(client):
    r = client.post("/api/tts", json={"text": "Ahlan wa sahlan"})
    assert r.status_code == 503  # disabled in tests → the browser voice takes over


def test_id_guardrail_blocks_invented_ids(client):
    from app.services.session_store import session_store
    from app.tools.insurance_tools import fetch_kyc_from_government

    session_store.get("guard-1").extra["said"] = ["I want a retirement plan", "Abdullah Sheikh Zafar"]
    out = json.loads(fetch_kyc_from_government.invoke(
        {"name": "fetch_kyc_from_government", "type": "tool_call", "id": "t1",
         "args": {"id_type": "NATIONAL_ID", "id_number": "1012345678", "consent": True}},
        config={"configurable": {"thread_id": "guard-1"}}).content)
    assert not out["ok"] and "NOT_PROVIDED" in out["error"]
    session_store.get("guard-1").extra["said"].append("my ID is 1012345678")
    out = json.loads(fetch_kyc_from_government.invoke(
        {"name": "fetch_kyc_from_government", "type": "tool_call", "id": "t2",
         "args": {"id_type": "NATIONAL_ID", "id_number": "1012345678", "consent": True}},
        config={"configurable": {"thread_id": "guard-1"}}).content)
    assert out["ok"]
