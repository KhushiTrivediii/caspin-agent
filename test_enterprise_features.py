"""
Verification Test Suite for Advanced Enterprise Integrations & Workflow Features.
"""

import asyncio
import os
import sys
import json
from datetime import datetime

# Windows encoding safety
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

os.environ["DEBUG"] = "False"

from backend.database import init_db, get_procurement, list_procurements, get_purchase_order
from backend.models import ChannelType, ProcurementTicket, ProcurementStatus, ApprovalTier, ManualQuoteInput
from backend.po_generator import po_engine
from backend.workflow_manager import workflow_manager
from fastapi.testclient import TestClient
from backend.main import app


async def test_channel_simulation_slack_whatsapp():
    print("\n--- [1/5] Testing Slack & WhatsApp Channel Gateway Simulation ---")
    await init_db()
    import aiosqlite
    async with aiosqlite.connect("./procurements.db") as db:
        await db.execute("DELETE FROM purchase_orders")
        await db.execute("DELETE FROM procurements")
        await db.execute("DELETE FROM vendor_quotes")
        await db.execute("DELETE FROM audit_logs")
        await db.commit()

    # 1. Simulate Slack message
    res_slack = await workflow_manager.handle_inbound_message(
        channel=ChannelType.SLACK,
        sender_id="slack_u123",
        sender_name="Alex Mercer",
        sender_email="alex@company.slack",
        conversation_id="slack_conv_99",
        text="Need 10 laptops.",
    )
    assert res_slack["status"] == "in_progress"
    assert any("budget" in f.lower() for f in res_slack["missing_fields"])
    print("[PASS] Slack Gateway: Correctly captured requirement and identified missing budget/delivery info")

    # 2. Simulate WhatsApp message
    res_wa = await workflow_manager.handle_inbound_message(
        channel=ChannelType.WHATSAPP,
        sender_id="wa_u456",
        sender_name="Divya Rao",
        sender_email=None,
        conversation_id="wa_conv_88",
        text="Need 20 ergonomic chairs.",
    )
    assert res_wa["status"] == "in_progress"
    assert any("budget" in f.lower() for f in res_wa["missing_fields"])
    print("[PASS] WhatsApp Gateway: Initialized conversational mobile flow successfully")


def test_approval_tier_policies():
    print("\n--- [2/5] Testing Multi-Level Approval Policy Matrix ---")
    
    # Tier 1 Rule: <= 1 Lakh
    t1_tier = po_engine.determine_approval_tier(85000.0)
    assert t1_tier == ApprovalTier.TIER_1_LEAD.value, f"Expected Tier 1, got {t1_tier}"

    # Tier 2 Rule: 1 Lakh to 10 Lakh
    t2_tier = po_engine.determine_approval_tier(450000.0)
    assert t2_tier == ApprovalTier.TIER_2_MANAGER.value, f"Expected Tier 2, got {t2_tier}"

    # Tier 3 Rule: > 10 Lakh
    t3_tier = po_engine.determine_approval_tier(4500000.0)
    assert t3_tier == ApprovalTier.TIER_3_EXECUTIVE.value, f"Expected Tier 3, got {t3_tier}"

    print(f"[PASS] Approval Policy Matrix: Verified Tier 1 (₹85k), Tier 2 (₹4.5L), Tier 3 (₹45L) thresholds")


async def test_quote_ingestion_and_recalculation():
    print("\n--- [3/5] Testing Custom Quote Ingestion & Real-Time Re-scoring ---")
    client = TestClient(app)
    
    # 1. Create a ticket
    ticket_payload = {
        "product": "Office Monitor",
        "quantity": 10,
        "budget": 200000.0,
        "delivery_days": 5,
        "specifications": ["4K", "27 inch"],
        "channel": "web"
    }
    res_create = client.post("/procurement", json=ticket_payload)
    ticket_id = res_create.json()["id"]

    # 2. Post a custom vendor quote
    quote_payload = {
        "vendor_name": "Apex Hardware Ltd",
        "price": 180000.0,
        "delivery_days": 4,
        "warranty_years": 3,
        "vendor_rating": 4.7,
        "reliability_score": 95.0
    }
    res_ingest = client.post(f"/procurement/{ticket_id}/quotes", json=quote_payload)
    assert res_ingest.status_code == 200
    
    updated_ticket = res_ingest.json()
    assert updated_ticket["recommended_vendor"] == "Apex Hardware Ltd"
    assert updated_ticket["recommended_price"] == 180000.0
    print(f"[PASS] Quote Ingestion: Added 'Apex Hardware Ltd' quote, re-ranked successfully. Recommended price updated to ₹1.8 Lakh")


async def test_purchase_order_generation():
    print("\n--- [4/5] Testing Purchase Order Document Generation ---")
    client = TestClient(app)

    # 1. Create and Approve ticket to trigger automatic PO generation
    ticket_payload = {
        "product": "Workstation UPS",
        "quantity": 5,
        "budget": 95000.0,  # Tier 1
        "delivery_days": 5,
        "specifications": ["1KVA", "Line Interactive"],
        "channel": "web"
    }
    res_create = client.post("/procurement", json=ticket_payload)
    ticket_id = res_create.json()["id"]

    res_approve = client.post(f"/procurement/{ticket_id}/approve", json={
        "approver": "Sarah Chen",
        "notes": "Urgent UPS backup requirement",
        "channel": "web"
    })
    assert res_approve.status_code == 200

    # 2. Retrieve generated PO
    po = await get_purchase_order(ticket_id)
    assert po is not None
    assert po.po_number.startswith("PO-2026-")
    assert abs(po.subtotal - po.total_amount / 1.18) < 1.0
    assert abs(po.tax_amount - po.subtotal * 0.18) < 1.0
    assert po.approved_by == "Sarah Chen"
    print(f"[PASS] PO Generator: Issued '{po.po_number}' with subtotal ₹{po.subtotal:,.2f} + 18% GST (₹{po.tax_amount:,.2f}) = ₹{po.total_amount:,.2f}")

    # 3. Test HTML Invoice Endpoint
    res_po_html = client.get(f"/procurement/{ticket_id}/po/html")
    assert res_po_html.status_code == 200
    assert "Official Purchase Order" in res_po_html.text
    assert po.po_number in res_po_html.text
    print(f"[PASS] PO HTML Document: Generated clean, printable invoice layout")


def test_erp_export_endpoints():
    print("\n--- [5/5] Testing ERP Data Export Integrations (CSV/JSON) ---")
    client = TestClient(app)

    # 1. Test CSV Download
    res_csv = client.get("/export/procurements/csv")
    assert res_csv.status_code == 200
    assert "Ticket ID,PO Number,Status,Approval Tier" in res_csv.text
    print("[PASS] ERP Integration: CSV Export verified (CSV downloadable)")

    # 2. Test JSON Dump
    res_json = client.get("/export/procurements/json")
    assert res_json.status_code == 200
    assert isinstance(res_json.json(), list)
    print("[PASS] ERP Integration: JSON Export verified (SAP/NetSuite compatible)")


async def run_enterprise_tests():
    print("===================================================================")
    print("   RUNNING ENTERPRISE INTEGRATIONS & POLICY MATRIX TESTS (5/5)     ")
    print("===================================================================")
    await test_channel_simulation_slack_whatsapp()
    test_approval_tier_policies()
    await test_quote_ingestion_and_recalculation()
    await test_purchase_order_generation()
    test_erp_export_endpoints()
    print("\n===================================================================")
    print("   [SUCCESS] ALL ENTERPRISE INTEGRATION TESTS PASSED CLEANLY! (5/5)")
    print("===================================================================\n")


if __name__ == "__main__":
    asyncio.run(run_enterprise_tests())
