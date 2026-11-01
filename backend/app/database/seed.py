"""Realistic mock data for Al Rajhi Takaful (Saudi Arabia, SAR, individual plans). Dates are relative to *today*
so the demo always has active plans in all five portfolios, one expiring soon (renewal journey) and claims in flight."""
from __future__ import annotations

import json
import sqlite3
from datetime import date, datetime, timedelta


def _d(days: int) -> str:
    return (date.today() + timedelta(days=days)).isoformat()


def _ts(days: int, hour: int = 10) -> str:
    dt = datetime.combine(date.today() + timedelta(days=days), datetime.min.time()).replace(hour=hour)
    return dt.isoformat(timespec="seconds")


# Seed rows for the Customer 360 workbook (Customers sheet) — keys follow excel_store.CUSTOMER_COLS.
CUSTOMERS = [
    {"customer_id": "CUST-1001", "name": "Faisal Abdullah Al-Otaibi", "phone": "+966 55 123 4567",
     "email": "faisal.alotaibi@example.sa", "address": "Building 8228, Prince Sultan Rd, Al Muhammadiyah District, Riyadh 12363",
     "city": "Riyadh", "date_of_birth": "1987-03-14", "nationality": "Saudi", "segment": "Premier",
     "kyc_status": "Verified", "customer_since": "2019-06-12", "id_type": "National ID", "id_reference": "1XXXXXX482",
     "kyc_source": "Branch KYC (Absher)", "onboarded_via": "Branch", "registered_at": "2019-06-12T10:00:00"},
    {"customer_id": "CUST-1002", "name": "Sara Khalid Al-Harbi", "phone": "+966 50 987 6543",
     "email": "sara.alharbi@example.sa", "address": "Building 2451, Tahlia St, Al Andalus District, Jeddah 23326",
     "city": "Jeddah", "date_of_birth": "1993-09-21", "nationality": "Saudi", "segment": "Retail",
     "kyc_status": "Verified", "customer_since": "2021-02-20", "id_type": "National ID", "id_reference": "1XXXXXX915",
     "kyc_source": "Nafath + Yakeen", "onboarded_via": "Mobile app", "registered_at": "2021-02-20T10:00:00"},
    {"customer_id": "CUST-1003", "name": "Imran Ahmed Siddiqui", "phone": "+966 56 222 3344",
     "email": "imran.siddiqui@example.com", "address": "Building 6610, King Saud St, Al Faisaliyah District, Dammam 32272",
     "city": "Dammam", "date_of_birth": "1984-01-08", "nationality": "Pakistani", "segment": "Retail",
     "kyc_status": "Pending - Iqama expired", "customer_since": "2017-09-05", "id_type": "Iqama", "id_reference": "2XXXXXX377",
     "kyc_source": "Branch KYC", "onboarded_via": "Branch", "registered_at": "2017-09-05T10:00:00"},
]


def _policies():
    return [
        # Faisal — all five portfolios; second car expiring in ~18 days (renewal journey)
        ("POL-MTR-240118", "CUST-1001", "Motor - Car", "Motor Comprehensive Plus",
         "Toyota Land Cruiser GXR 2023 · 4521 RTA", 285000, 9850, _d(-220), _d(145), "Active", 20,
         {"line": "motor", "add_ons": ["Agency repair", "Replacement car", "GCC cover"], "deductible": 500}),
        ("POL-MTR-230907", "CUST-1001", "Motor - Car", "Motor Comprehensive",
         "Hyundai Elantra 2021 · 7790 KBD", 48000, 2950, _d(-347), _d(18), "Expiring", 25,
         {"line": "motor", "add_ons": ["Roadside assistance"], "deductible": 500}),
        ("POL-HLT-220415", "CUST-1001", "Health", "Health Gold",
         "Individual · age 39 · Riyadh", 1000000, 5980, _d(-160), _d(205), "Active", 0,
         {"line": "health", "network": "Class B", "co_pay": "10%"}),
        ("POL-SAV-220901", "CUST-1001", "Retirement & Savings", "Retirement Plan",
         "SAR 1,500/month · 25 years · age 35 at entry", 450000, 18000, _d(-1150), _d(7980), "Active", 0,
         {"line": "savings", "fund": "Target-date 2047", "fund_value": 71250}),
        ("POL-LIF-210320", "CUST-1001", "Life", "Life Protect Plus",
         "Faisal Al-Otaibi · age 34 at entry · 20-year term", 1500000, 3950, _d(-1300), _d(5995), "Active", 0,
         {"line": "life", "beneficiaries": ["Maha Al-Otaibi (spouse)"]}),
        # Sara — motor + health
        ("POL-MTR-250312", "CUST-1002", "Motor - Car", "Motor Comprehensive Plus",
         "Kia Sorento 2024 · 3310 HSD", 152000, 6400, _d(-95), _d(270), "Active", 0,
         {"line": "motor", "add_ons": ["Agency repair", "Replacement car"]}),
        ("POL-HLT-250101", "CUST-1002", "Health", "Health Essential",
         "Individual · age 33 · Jeddah", 1000000, 3600, _d(-60), _d(305), "Active", 0, {"line": "health", "network": "Class C"}),
        # Imran — motor + general (home) lapsed
        ("POL-MTR-210744", "CUST-1003", "Motor - Car", "Motor Comprehensive",
         "Toyota Hilux 2020 · 1182 JKD", 78000, 3900, _d(-300), _d(65), "Active", 30, {"line": "motor"}),
        ("POL-GEN-200518", "CUST-1003", "General - Home", "Home Plus",
         "Apartment · Al Faisaliyah, Dammam · building SAR 650,000 + contents SAR 120,000", 770000, 1450,
         _d(-420), _d(-55), "Lapsed", 0, {"line": "general"}),
    ]


def _claims():
    return [
        ("CLM-2603-4471", "CUST-1001", "POL-MTR-240118", _d(-210), "Accident - Own Damage",
         "Rear bumper and tail-lamp damaged in a low-speed collision at a signal on King Fahd Rd (Najm report issued).",
         "King Fahd Rd, Riyadh", 9800, "Closed", "Repaired at the Toyota agency. SAR 9,300 paid.",
         _ts(-209), _ts(-196),
         [("Reported", "Claim registered via AI Copilot with Najm report", -209),
          ("Under Review", "Najm report and Istimara verified", -208),
          ("Assessment", "Damage assessed at the Toyota agency, Riyadh", -206),
          ("Approved", "Approved for SAR 9,300 after SAR 500 deductible", -202),
          ("Closed", "Vehicle delivered, settled directly with the agency", -196)]),
        ("CLM-2610-8812", "CUST-1001", "POL-HLT-220415", _d(-6), "Health - Hospitalisation",
         "Planned day-case knee arthroscopy at a network hospital in Riyadh.",
         "Network hospital, Riyadh", 18500, "Under Review", "Pre-approval granted; awaiting final invoice.",
         _ts(-6), _ts(-4),
         [("Reported", "Pre-approval request received from hospital", -6),
          ("Under Review", "Pre-approval granted; awaiting final invoice", -4)]),
        ("CLM-2609-3390", "CUST-1002", "POL-MTR-250312", _d(-30), "Windshield",
         "Windshield cracked by a stone on the Jeddah–Makkah highway.",
         "Jeddah–Makkah Expressway", 2600, "Approved", "Glass replacement approved, no NCD impact.",
         _ts(-30), _ts(-25),
         [("Reported", "Claim registered", -30), ("Under Review", "Photos verified", -29),
          ("Assessment", "Video self-inspection", -28), ("Approved", "Glass replacement approved", -25)]),
        ("CLM-2608-1027", "CUST-1003", "POL-MTR-210744", _d(-70), "Accident - Third Party",
         "Minor collision with a parked car while reversing in a mall car park.",
         "Al Rashid Mall, Dammam", 4200, "Assessment", "Third-party claim under Najm liability review.",
         _ts(-70), _ts(-60),
         [("Reported", "Najm report uploaded", -70), ("Under Review", "Documents verified", -66),
          ("Assessment", "Third-party liability under review", -60)]),
    ]


def _quotes():
    return [
        ("QT-2609-5521", "CUST-1001", "Health Premier", 24100, "health_premier", 38,
         {"product": "Health", "note": "Upgrade quote shared during annual review"}, _ts(-40)),
        ("QT-2610-1180", "CUST-1001", "Motor Comprehensive Plus", 9900, "comprehensive_plus", 52,
         {"product": "Motor", "note": "Quote for a planned second SUV (Lexus LX)"}, _ts(-12)),
        ("QT-2610-2290", "CUST-1002", "Home Plus", 1150, "home_plus", 28, {"product": "General - Home"}, _ts(-9)),
    ]


def seed(conn: sqlite3.Connection) -> None:
    for p in _policies():
        conn.execute("INSERT INTO policies VALUES (?,?,?,?,?,?,?,?,?,?,?,?)", (*p[:-1], json.dumps(p[-1])))
    for c in _claims():
        *fields, events = c
        conn.execute("INSERT INTO claims VALUES (?,?,?,?,?,?,?,?,?,?,?,?)", fields)
        for status, note, day in events:
            conn.execute("INSERT INTO claim_events (claim_id, status, note, created_at) VALUES (?,?,?,?)",
                         (c[0], status, note, _ts(day, 11)))
    for q in _quotes():
        conn.execute("INSERT INTO quotes VALUES (?,?,?,?,?,?,?,?)", (*q[:6], json.dumps(q[6]), q[7]))
