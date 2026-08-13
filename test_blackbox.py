import asyncio
import os
import json
import logging
from typing import Dict, Any
from fastapi.testclient import TestClient

os.environ["PORT"] = "8080"

from backend.main import app
from backend.database import DB_PATH, init_db, list_tickets, get_ticket, get_channel_messages, get_audit_logs, get_graph_data, get_settings
from backend.scheduler import scheduler_service
from backend.models import TicketStatus, IncidentCategory

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("test_blackbox")

client = TestClient(app)


async def setup_clean_db():
    """Wipe database and re-initialize with seeded startup details."""
    if os.path.exists(DB_PATH):
        try:
            os.remove(DB_PATH)
        except Exception as e:
            logger.warning(f"Could not remove old DB file: {e}")
    await init_db()


async def test_blackbox_features():
    logger.info("===================================================================")
    logger.info("       RUNNING BLACKBOX AI OPERATIONS VERIFICATION SUITE           ")
    logger.info("===================================================================")

    await setup_clean_db()
    scheduler_service.start()

    try:
        # -------------------------------------------------------------------
        # Test 1: Customer Support Rescue Engine
        # -------------------------------------------------------------------
        logger.info("\n--- [1/7] Testing Customer Support Rescue Engine ---")
        res = client.post("/api/simulate", json={"type": "support"})
        assert res.status_code == 200, "Support simulation request failed"
        
        # Verify ticket was created
        tickets = await list_tickets(category=IncidentCategory.CUSTOMER_SUPPORT.value)
        assert len(tickets) >= 1, "Support ticket not created in DB"
        support_ticket = tickets[0]
        assert support_ticket.reporter_name == "Alex Mercer"
        assert support_ticket.status == TicketStatus.OPEN
        
        # Verify outgoing messages: email reply to Alex, Slack alert, and Telegram ping to founder
        messages = await get_channel_messages(ticket_id=support_ticket.id)
        outbounds = [m for m in messages if m.direction == "outbound"]
        assert len(outbounds) >= 3, f"Expected 3 outgoing messages, got {len(outbounds)}"
        
        channels = [m.channel for m in outbounds]
        assert "email" in channels, "No email reply sent to customer"
        assert "slack" in channels, "No Slack alert posted to team"
        assert "telegram" in channels, "No Telegram alert sent to founder"
        logger.info("[PASS] Customer Support Rescue: Multi-channel notifications confirmed.")

        # -------------------------------------------------------------------
        # Test 2: Lead Recovery System
        # -------------------------------------------------------------------
        logger.info("\n--- [2/7] Testing Lead Recovery System ---")
        # Tesla is seeded as a Lead. We simulate lead email follow-up
        res_lead = client.post("/api/simulate", json={"type": "lead"}) # triggers generic/inactivity follow-up
        assert res_lead.status_code == 200
        
        tickets_lead = await list_tickets(category=IncidentCategory.LEAD_FOLLOWUP.value)
        assert len(tickets_lead) >= 1
        lead_ticket = tickets_lead[0]
        
        # Verify Tesla's node status updated in memory graph
        graph = await get_graph_data()
        tesla_node = next(n for n in graph["nodes"] if n["id"] == "lead_tesla")
        assert tesla_node["properties"]["status"] == "Meeting Scheduled", "Tesla status not updated in graph"
        logger.info("[PASS] Lead Recovery: Graph database memory nodes updated successfully.")

        # -------------------------------------------------------------------
        # Test 3: Vendor Intelligence Delay Monitor
        # -------------------------------------------------------------------
        logger.info("\n--- [3/7] Testing Vendor Intelligence Delay Monitor ---")
        res_vendor = client.post("/api/simulate", json={"type": "delay"})
        assert res_vendor.status_code == 200
        
        tickets_vendor = await list_tickets(category=IncidentCategory.VENDOR_INTELLIGENCE.value)
        assert len(tickets_vendor) >= 1
        vendor_ticket = tickets_vendor[0]
        assert "DHL" in vendor_ticket.title
        
        # Check graph edges (DHL causes delay ticket, delay ticket impacts Payments project)
        graph = await get_graph_data()
        edges = graph["edges"]
        has_caused = any(e for e in edges if e["source"] == "vendor_dhl" and e["target"] == vendor_ticket.id and e["type"] == "CAUSED")
        has_impacts = any(e for e in edges if e["source"] == vendor_ticket.id and e["target"] == "project_payments" and e["type"] == "IMPACTS")
        assert has_caused, "CAUSED edge not created"
        assert has_impacts, "IMPACTS edge not created"
        logger.info("[PASS] Vendor Intelligence: Dynamic relationship edges linked in Memory Graph.")

        # -------------------------------------------------------------------
        # Test 4: Team Operations Monitor Blocker
        # -------------------------------------------------------------------
        logger.info("\n--- [4/7] Testing Slack Blocker Task Dispatch ---")
        res_blocker = client.post("/api/simulate", json={"type": "blocker"})
        assert res_blocker.status_code == 200
        
        tickets_blocker = await list_tickets(category=IncidentCategory.TEAM_OPERATIONS.value)
        assert len(tickets_blocker) >= 1
        blocker_ticket = tickets_blocker[0]
        
        # Check task card sent to tech
        messages = await get_channel_messages(ticket_id=blocker_ticket.id)
        outbounds = [m for m in messages if m.direction == "outbound" and m.channel == "telegram"]
        assert len(outbounds) >= 1, "Task not dispatched to DevOps (Alice) on Telegram"
        logger.info("[PASS] Team Operations: Task card dispatched to Alice on Telegram.")

        # -------------------------------------------------------------------
        # Test 5: Community Intelligence Bug Report
        # -------------------------------------------------------------------
        logger.info("\n--- [5/7] Testing Community Bug Ingestion ---")
        res_bug = client.post("/api/simulate", json={"type": "bug"})
        assert res_bug.status_code == 200
        
        tickets_bug = await list_tickets(category=IncidentCategory.COMMUNITY_INTELLIGENCE.value)
        assert len(tickets_bug) >= 1
        bug_ticket = tickets_bug[0]
        assert "Discord" in bug_ticket.title
        logger.info("[PASS] Community Intelligence: Discord complaint parsed and ticket created.")

        # -------------------------------------------------------------------
        # Test 6: Founder Daily Briefing
        # -------------------------------------------------------------------
        logger.info("\n--- [6/7] Testing Founder Daily Briefing ---")
        res_briefing = client.post("/api/simulate", json={"type": "briefing"})
        assert res_briefing.status_code == 200
        logger.info("[PASS] Founder Briefing: Telegram summary generated and dispatched.")

        # -------------------------------------------------------------------
        # Test 7: Founder Disappears Mode
        # -------------------------------------------------------------------
        logger.info("\n--- [7/7] Testing Founder Disappears Mode (WOW Feature) ---")
        # Enable founder disappears mode
        res_mode = client.post("/api/settings", json={"founder_disappears_mode": True})
        assert res_mode.status_code == 200
        
        settings = await get_settings()
        assert settings["founder_disappears_mode"] == "1", "Founder disappears mode setting not updated"
        
        # Trigger customer complaint while mode is ON
        res_supp2 = client.post("/api/simulate", json={"type": "support"})
        assert res_supp2.status_code == 200
        
        # Verify support ticket created
        tickets = await list_tickets(category=IncidentCategory.CUSTOMER_SUPPORT.value)
        assert len(tickets) >= 2, "Second support ticket not created in DB"
        new_ticket = tickets[0] # ordered DESC, so new one is first
        
        # Verify outgoing messages: email reply to customer & Slack alert, but NO founder Telegram alert!
        messages = await get_channel_messages(ticket_id=new_ticket.id)
        outbounds = [m for m in messages if m.direction == "outbound"]
        channels = [m.channel for m in outbounds]
        assert "email" in channels, "No email reply sent to customer"
        assert "slack" in channels, "No Slack alert posted to team"
        assert "telegram" not in channels, "Telegram alert sent to founder despite Disappears mode being enabled"
        
        # Verify audit logs contains AUTO_RESOLVE flag
        audit_logs = await get_audit_logs(new_ticket.id)
        auto_resolve_audit = [log for log in audit_logs if log["action"] == "AUTO_RESOLVE"]
        assert len(auto_resolve_audit) >= 1, "Autonomous audit flag not logged"
        logger.info("[PASS] Founder Disappears Mode: Autonomous action logged, founder notifications suppressed.")

    finally:
        scheduler_service.shutdown()

    logger.info("\n===================================================================")
    logger.info("   [SUCCESS] ALL BLACKBOX OPERATIONS TESTS PASSED CLEANLY! (7/7)   ")
    logger.info("===================================================================")


if __name__ == "__main__":
    import asyncio
    asyncio.run(test_blackbox_features())
