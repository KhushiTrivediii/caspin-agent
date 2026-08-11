"""
Automated Verification Suite for Enterprise Vendor Intelligence Engine.
Tests:
1. Vendor Discovery Agent (POST /vendors/search)
2. Quotation Analysis Agent (POST /quotes/analyze)
3. 4-Factor Weighted Scoring Engine (POST /vendors/score: 40% Price, 25% Delivery, 20% Reliability, 15% Warranty)
4. Autonomous Negotiation Agent (POST /vendors/negotiate)
5. Multi-Factor Risk Detection Engine
6. Supplier Recommendation Engine (POST /vendors/recommend)
7. Executive Reporting Engine
"""

import asyncio
import os
import sys
from datetime import datetime

# Windows encoding safety
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

os.environ["DEBUG"] = "False"

from backend.database import init_db
from backend.models import QuotationInput
from backend.vendor_intelligence import vendor_intelligence
from fastapi.testclient import TestClient
from backend.main import app


async def test_vendor_discovery():
    print("\n--- [1/6] Testing Vendor Discovery Agent ---")
    await init_db()
    
    vendors = await vendor_intelligence.discover_vendors(
        product="Laptop",
        quantity=100,
        budget=4500000.0,
    )
    assert len(vendors) >= 3, f"Expected at least 3 matching vendors, got {len(vendors)}"
    
    dell_vendor = next((v for v in vendors if "Dell" in v.name), None)
    assert dell_vendor is not None, "Dell Partner must be discovered for Laptops"
    assert "Laptop" in dell_vendor.product_categories
    assert dell_vendor.rating >= 4.5
    print(f"[PASS] Vendor Discovery: Discovered {len(vendors)} suppliers (Top: '{dell_vendor.name}', Rating: {dell_vendor.rating})")


def test_quotation_analysis_and_scoring():
    print("\n--- [2/6] Testing Quotation Analysis & 4-Factor Weighted Scoring Engine ---")
    
    # 40% Price, 25% Delivery, 20% Reliability, 15% Warranty
    quotes = [
        QuotationInput(
            vendor_name="Dell Partner",
            price=4150000.0,
            delivery_days=7,
            warranty_years=3,
            vendor_rating=4.8,
            reliability_score=96.0,
        ),
        QuotationInput(
            vendor_name="HP Commercial Direct",
            price=4320000.0,
            delivery_days=9,
            warranty_years=3,
            vendor_rating=4.6,
            reliability_score=92.0,
        ),
        QuotationInput(
            vendor_name="Lenovo Premier",
            price=4400000.0,
            delivery_days=8,
            warranty_years=3,
            vendor_rating=4.5,
            reliability_score=90.0,
        ),
    ]

    scores = vendor_intelligence.score_vendors(budget=4500000.0, quotes=quotes)
    assert len(scores) == 3
    assert scores[0].vendor == "Dell Partner", f"Expected Dell Partner as #1, got {scores[0].vendor}"
    assert scores[0].score >= 88, f"Expected high composite score for Dell Partner, got {scores[0].score}"
    assert scores[0].is_recommended == True
    
    print(f"[PASS] Scoring Engine: Ranked #1 '{scores[0].vendor}' (Score: {scores[0].score}/100), #2 '{scores[1].vendor}' (Score: {scores[1].score}/100)")


async def test_negotiation_agent():
    print("\n--- [3/6] Testing Autonomous Negotiation Agent ---")
    await init_db()

    thread = await vendor_intelligence.create_and_send_negotiation(
        vendor_name="Dell Partner (Enterprise Solutions)",
        initial_price=4400000.0,
        competing_lower_price=4200000.0,
        target_discount_pct=5.5,
        product_name="Laptop",
        quantity=100,
    )

    assert thread.status.value in ["Improved Offer", "Sent"]
    assert thread.savings_achieved > 0, "Negotiation must achieve cost savings"
    assert "4,400,000" in thread.counter_offer_text or "44.00" in thread.counter_offer_text
    print(f"[PASS] Negotiation Agent: Counter email generated -> Achieved Rs. {thread.savings_achieved:,.2f} savings (Status: {thread.status.value})")


def test_vendor_risk_detection():
    print("\n--- [4/6] Testing Multi-Factor Vendor Risk Detection ---")
    
    # Anomaly quote: 38% below market average + low rating + slow delivery
    outlier_quote = QuotationInput(
        vendor_name="TechNova Global (Risk Outlier)",
        price=2800000.0,  # 38% below 4.5M market average!
        delivery_days=16,
        warranty_years=1,
        vendor_rating=3.6,
        reliability_score=72.0,
    )
    
    regular_quote = QuotationInput(
        vendor_name="Dell Partner",
        price=4150000.0,
        delivery_days=7,
        warranty_years=3,
        vendor_rating=4.8,
        reliability_score=96.0,
    )

    alerts = vendor_intelligence.detect_risks(
        budget=4500000.0,
        market_average_price=4150000.0,
        quotes=[outlier_quote, regular_quote],
    )

    assert len(alerts) >= 2, f"Expected risk flags for price anomaly and low rating, got {len(alerts)}"
    price_anomaly = next((a for a in alerts if "Price Anomaly" in a.risk_factor), None)
    assert price_anomaly is not None, "Price anomaly risk must be detected"
    print(f"[PASS] Risk Detection: Correctly flagged '{price_anomaly.risk_factor}' -> {price_anomaly.reason[:70]}...")


def test_supplier_recommendation():
    print("\n--- [5/6] Testing Supplier Recommendation Engine ---")
    
    quotes = [
        QuotationInput(vendor_name="Dell Partner", price=4150000.0, delivery_days=7, warranty_years=3, vendor_rating=4.8, reliability_score=96.0),
        QuotationInput(vendor_name="HP Commercial", price=4320000.0, delivery_days=9, warranty_years=3, vendor_rating=4.6, reliability_score=92.0),
    ]

    rec = vendor_intelligence.recommend_supplier(
        product="Laptop",
        quantity=100,
        budget=4500000.0,
        quotes=quotes,
    )

    assert rec.recommended_vendor == "Dell Partner"
    assert len(rec.reasons) >= 3
    assert rec.savings_amount == 350000.0
    print(f"[PASS] Recommendation: Selected '{rec.recommended_vendor}' with {len(rec.reasons)} key decision rationales")


def test_api_endpoints():
    print("\n--- [6/6] Testing Vendor Intelligence REST APIs ---")
    client = TestClient(app)

    # 1. POST /vendors/search
    res_search = client.post("/vendors/search", json={"product": "Laptop", "quantity": 100, "budget": 4500000.0})
    assert res_search.status_code == 200
    assert len(res_search.json()) >= 1
    print(f"[PASS] POST /vendors/search: Found {len(res_search.json())} suppliers")

    # 2. POST /quotes/analyze
    res_analyze = client.post("/quotes/analyze", json={
        "product": "Laptop",
        "quantity": 100,
        "budget": 4500000.0,
        "quotes": [
            {"vendor_name": "Dell Partner", "price": 4150000.0, "delivery_days": 7, "warranty_years": 3, "vendor_rating": 4.8, "reliability_score": 96.0},
            {"vendor_name": "HP Direct", "price": 4320000.0, "delivery_days": 9, "warranty_years": 3, "vendor_rating": 4.6, "reliability_score": 92.0},
        ]
    })
    assert res_analyze.status_code == 200
    analysis = res_analyze.json()
    assert len(analysis["scoring_results"]) == 2
    print("[PASS] POST /quotes/analyze: Comparison table & 4-factor scoring verified")

    # 3. POST /vendors/score
    res_score = client.post("/vendors/score", json={
        "budget": 4500000.0,
        "quotes": [
            {"vendor_name": "Dell Partner", "price": 4150000.0, "delivery_days": 7, "warranty_years": 3, "vendor_rating": 4.8, "reliability_score": 96.0},
            {"vendor_name": "HP Direct", "price": 4320000.0, "delivery_days": 9, "warranty_years": 3, "vendor_rating": 4.6, "reliability_score": 92.0},
        ]
    })
    assert res_score.status_code == 200
    scores = res_score.json()
    assert scores[0]["vendor"] == "Dell Partner"
    print(f"[PASS] POST /vendors/score: Top Score = {scores[0]['score']}")

    # 4. POST /vendors/negotiate
    res_neg = client.post("/vendors/negotiate", json={
        "vendor_name": "Dell Partner",
        "initial_price": 4400000.0,
        "competing_lower_price": 4200000.0,
        "target_discount_percentage": 5.0,
        "product_name": "Laptop",
        "quantity": 100
    })
    assert res_neg.status_code == 200
    neg_data = res_neg.json()
    assert "Improved Offer" in neg_data["status"] or "Sent" in neg_data["status"]
    print(f"[PASS] POST /vendors/negotiate: Concession recorded (Savings: Rs. {neg_data['savings_achieved']:,.2f})")

    # 5. POST /vendors/recommend
    res_rec = client.post("/vendors/recommend", json={
        "product": "Laptop",
        "quantity": 100,
        "budget": 4500000.0,
        "quotes": [
            {"vendor_name": "Dell Partner", "price": 4150000.0, "delivery_days": 7, "warranty_years": 3, "vendor_rating": 4.8, "reliability_score": 96.0},
            {"vendor_name": "HP Direct", "price": 4320000.0, "delivery_days": 9, "warranty_years": 3, "vendor_rating": 4.6, "reliability_score": 92.0},
        ]
    })
    assert res_rec.status_code == 200
    assert res_rec.json()["recommended_vendor"] == "Dell Partner"
    print("[PASS] POST /vendors/recommend: Supplier recommendation verified")

    # 6. GET /reports/comparison
    res_rep = client.get("/reports/comparison")
    assert res_rep.status_code == 200
    assert "Vendor Intelligence Comparison Report" in res_rep.text
    print("[PASS] GET /reports/comparison: Report generation verified")


async def run_all_tests():
    print("===================================================================")
    print("   RUNNING VENDOR INTELLIGENCE ENGINE VERIFICATION SUITE (6/6)     ")
    print("===================================================================")
    await test_vendor_discovery()
    test_quotation_analysis_and_scoring()
    await test_negotiation_agent()
    test_vendor_risk_detection()
    test_supplier_recommendation()
    test_api_endpoints()
    print("\n===================================================================")
    print("   [SUCCESS] ALL VENDOR INTELLIGENCE TESTS PASSED CLEANLY! (6/6)   ")
    print("===================================================================\n")


if __name__ == "__main__":
    asyncio.run(run_all_tests())
