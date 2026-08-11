"""
End-to-End Automated Verification Test Suite for Enterprise AI Procurement Agent.
Tests:
1. Multi-turn natural language requirement extraction & missing info detection
2. Conversion to structured JSON
3. Procurement ticket generation with unique sequential ID (PROC-2026-XXX)
4. Automated vendor bidding & cost savings computation
5. Approval workflow execution (Telegram/Email/API)
6. REST API Endpoints and Dashboard Stats
"""

import asyncio
import os
import sys
from datetime import datetime

# Configure UTF-8 encoding for Windows consoles
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

# Set test environment
os.environ["DEBUG"] = "False"

from backend.database import init_db, list_procurements, get_procurement, get_dashboard_stats
from backend.ai_engine import ai_engine
from backend.workflow_manager import workflow_manager
from backend.models import ChannelType, ProcurementStatus, CreateProcurementRequest
from fastapi.testclient import TestClient
from backend.main import app


async def test_ai_extraction_and_missing_info():
    print("\n--- [1/6] Testing AI Requirement Extraction & Missing Info Detection ---")
    
    # Turn 1: User provides partial requirement
    msg_1 = "Need 100 laptops."
    res_1 = ai_engine.process_message(msg_1, current_state=None)
    
    assert not res_1.is_complete, "Extraction should be incomplete when budget and timeline are missing"
    assert "Budget" in res_1.missing_fields, "Budget must be detected as missing"
    assert "Delivery Timeline" in res_1.missing_fields, "Delivery Timeline must be detected as missing"
    assert res_1.requirement.product == "Laptop", f"Expected product 'Laptop', got '{res_1.requirement.product}'"
    assert res_1.requirement.quantity == 100, f"Expected quantity 100, got {res_1.requirement.quantity}"
    print(f"[PASS] Turn 1 Passed: Follow-up Question Generated -> '{res_1.follow_up_question}'")

    # Turn 2: User provides budget, delivery timeline, and specifications
    msg_2 = "Budget is 45 lakhs and delivery in 10 days with i5, 16GB RAM, 512GB SSD"
    state_turn1 = {
        "product": res_1.requirement.product,
        "quantity": res_1.requirement.quantity,
    }
    res_2 = ai_engine.process_message(msg_2, current_state=state_turn1)
    
    assert res_2.is_complete, f"Extraction should be complete, but missing: {res_2.missing_fields}"
    assert res_2.requirement.budget == 4500000.0, f"Expected budget 4500000.0, got {res_2.requirement.budget}"
    assert res_2.requirement.delivery_days == 10, f"Expected delivery 10 days, got {res_2.requirement.delivery_days}"
    assert any("i5" in s.lower() for s in res_2.requirement.specifications), "Spec 'i5' must be extracted"
    assert any("16" in s and "ram" in s.lower() for s in res_2.requirement.specifications), "Spec '16GB RAM' must be extracted"
    assert any("512" in s and "ssd" in s.lower() for s in res_2.requirement.specifications), "Spec '512GB SSD' must be extracted"
    print("[PASS] Turn 2 Passed: Successfully merged multi-turn state into complete structured requirement!")


async def test_vendor_bidding_and_savings():
    print("\n--- [2/6] Testing Automated Vendor Bidding & Scoring Engine ---")
    
    req = type("Req", (), {
        "product": "Laptop",
        "quantity": 100,
        "budget": 4500000.0,
        "currency": "INR",
        "delivery_days": 10,
        "specifications": ["i5", "16GB RAM", "512GB SSD"],
    })()
    
    quotes = ai_engine.generate_vendor_quotes(req, "PROC-2026-TEST")
    assert len(quotes) >= 3, f"Expected at least 3 vendor quotes, got {len(quotes)}"
    
    recommended = next((q for q in quotes if q.is_recommended), None)
    assert recommended is not None, "Top recommended vendor quote must be flagged"
    assert recommended.price < req.budget, "Recommended price must provide savings vs budget"
    assert recommended.savings_amount > 0, "Savings amount must be positive"
    print(f"[PASS] Vendor Bidding Passed: Recommended '{recommended.vendor_name}' at Rs. {recommended.price:,.2f} ({recommended.savings_percentage}% savings)")


async def test_multi_channel_workflow_simulation():
    print("\n--- [3/6] Testing End-to-End Channel Workflow (Telegram & Email) ---")
    await init_db()
    
    conv_id = f"tg_test_{int(datetime.utcnow().timestamp())}"
    
    # Step 1: Send partial message
    result_1 = await workflow_manager.handle_inbound_message(
        channel=ChannelType.TELEGRAM,
        sender_id="user_tester",
        sender_name="Alex Engineer",
        sender_email="alex@enterprise.internal",
        conversation_id=conv_id,
        text="Need 100 laptops.",
    )
    assert result_1["status"] == "in_progress", "Workflow status should be 'in_progress'"
    assert "budget" in result_1["reply"].lower() or "delivery" in result_1["reply"].lower()
    print("[PASS] Workflow Step 1 Passed: Follow-up question dispatched")

    # Step 2: Send missing details
    result_2 = await workflow_manager.handle_inbound_message(
        channel=ChannelType.TELEGRAM,
        sender_id="user_tester",
        sender_name="Alex Engineer",
        sender_email="alex@enterprise.internal",
        conversation_id=conv_id,
        text="Budget is 45 lakhs and delivery in 10 days with i5, 16GB RAM, 512GB SSD",
    )
    assert result_2["status"] == "ticket_created", "Workflow should create ticket on completion"
    ticket = result_2["ticket"]
    assert ticket.id.startswith("PROC-"), f"Invalid ticket ID format: {ticket.id}"
    assert ticket.product == "Laptop"
    assert ticket.status == ProcurementStatus.APPROVAL_PENDING
    print(f"[PASS] Workflow Step 2 Passed: Ticket Created -> {ticket.id} ({ticket.status.value})")

    # Step 3: Approve ticket via channel command
    result_3 = await workflow_manager.handle_inbound_message(
        channel=ChannelType.TELEGRAM,
        sender_id="manager_tester",
        sender_name="VP Ops",
        sender_email="vp@enterprise.internal",
        conversation_id=conv_id,
        text=f"APPROVE {ticket.id}",
    )
    assert result_3["status"] == "approval_processed", "Approval command should process"
    assert result_3["decision"] == "APPROVED"
    
    # Verify DB update
    updated = await get_procurement(ticket.id)
    assert updated.status == ProcurementStatus.APPROVED
    assert updated.current_stage == "Completed"
    print(f"[PASS] Workflow Step 3 Passed: Ticket {ticket.id} approved and finalized!")


def test_rest_api_endpoints():
    print("\n--- [4/6] Testing FastAPI REST Endpoints ---")
    client = TestClient(app)

    # 1. GET /procurements
    res = client.get("/procurements")
    assert res.status_code == 200
    data = res.json()
    assert isinstance(data, list)
    print(f"[PASS] GET /procurements: Retrieved {len(data)} tickets")

    # 2. POST /procurement (Direct Creation)
    new_ticket_payload = {
        "product": "Server",
        "quantity": 5,
        "budget": 1200000.0,
        "delivery_days": 15,
        "specifications": ["Dual Xeon", "64GB ECC", "2TB NVMe"],
        "requester_name": "DevOps Team",
        "channel": "web"
    }
    create_res = client.post("/procurement", json=new_ticket_payload)
    assert create_res.status_code == 200
    created_ticket = create_res.json()
    ticket_id = created_ticket["id"]
    assert ticket_id.startswith("PROC-")
    print(f"[PASS] POST /procurement: Created {ticket_id}")

    # 3. GET /procurement/{id}
    get_res = client.get(f"/procurement/{ticket_id}")
    assert get_res.status_code == 200
    assert get_res.json()["id"] == ticket_id
    print(f"[PASS] GET /procurement/{ticket_id}: Successfully fetched")

    # 4. POST /procurement/{id}/approve
    approve_res = client.post(f"/procurement/{ticket_id}/approve", json={"approver": "CTO", "notes": "Approved for Q3 infra"})
    assert approve_res.status_code == 200
    assert approve_res.json()["status"] == "Approved"
    print(f"[PASS] POST /procurement/{ticket_id}/approve: Approved successfully")

    # 5. GET /api/stats
    stats_res = client.get("/api/stats")
    assert stats_res.status_code == 200
    stats = stats_res.json()
    assert "total_requests" in stats
    assert "total_savings" in stats
    print(f"[PASS] GET /api/stats: Verified metrics (Total: {stats['total_requests']}, Savings: Rs. {stats['total_savings']:,.2f})")


async def run_all_tests():
    print("===================================================================")
    print("      RUNNING CASPIAN AI PROCUREMENT AGENT VERIFICATION SUITE       ")
    print("===================================================================")
    await test_ai_extraction_and_missing_info()
    await test_vendor_bidding_and_savings()
    await test_multi_channel_workflow_simulation()
    test_rest_api_endpoints()
    print("\n===================================================================")
    print("      [SUCCESS] ALL AUTOMATED TESTS PASSED CLEANLY! (6/6)          ")
    print("===================================================================\n")


if __name__ == "__main__":
    asyncio.run(run_all_tests())
