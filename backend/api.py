import logging
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import HTMLResponse, PlainTextResponse

from backend.models import (
    IncidentTicket,
    MessageLog,
    SimulationRequest,
    BriefingPayload,
    SettingsUpdate,
    IncidentCategory,
    TicketStatus,
    ChannelType,
)
from backend.database import (
    list_tickets,
    get_ticket,
    create_ticket,
    get_graph_data,
    get_kpi_stats,
    get_settings,
    update_setting,
    get_channel_messages,
    get_audit_logs,
    log_audit_action,
)
from backend.workflow_manager import workflow_manager
from backend.caspian_service import caspian_service

router = APIRouter()
logger = logging.getLogger("api")


@router.get("/tickets", response_model=List[IncidentTicket])
async def get_all_tickets(
    category: Optional[str] = Query(None, description="Filter by category"),
    status: Optional[str] = Query(None, description="Filter by status"),
):
    """Retrieve list of all active incident tickets."""
    return await list_tickets(category=category, status=status)


@router.get("/ticket/{ticket_id}", response_model=IncidentTicket)
async def get_ticket_by_id(ticket_id: str):
    """Retrieve ticket details with description and current assignee."""
    ticket = await get_ticket(ticket_id)
    if not ticket:
        raise HTTPException(status_code=404, detail="Incident ticket not found.")
    return ticket


@router.get("/ticket/{ticket_id}/audit")
async def get_ticket_audit_trail(ticket_id: str):
    """Get audit trail logs for an incident ticket."""
    return await get_audit_logs(ticket_id)


@router.get("/graph")
async def get_memory_graph():
    """Retrieve nodes and edges for Neo4j memory visualization."""
    return await get_graph_data()


@router.get("/stats")
async def get_dashboard_kpis():
    """Retrieve KPI metrics for operations overview."""
    return await get_kpi_stats()


@router.get("/logs", response_model=List[MessageLog])
async def get_all_message_logs(ticket_id: Optional[str] = None):
    """Retrieve all inbound/outbound communication logs."""
    return await get_channel_messages(ticket_id=ticket_id)


@router.get("/settings")
async def get_system_settings():
    """Retrieve current system settings."""
    return await get_settings()


@router.post("/settings")
async def update_system_settings(payload: SettingsUpdate):
    """Toggle Founder Disappears Mode or other configuration flags."""
    await update_setting("founder_disappears_mode", "1" if payload.founder_disappears_mode else "0")
    logger.info(f"Updated setting: founder_disappears_mode = {payload.founder_disappears_mode}")
    
    # Send confirmation message to founder on Telegram
    mode_text = "ENABLED 🟢 (Autonomous Workflows Active)" if payload.founder_disappears_mode else "DISABLED 🔴 (Approval Alerts Enabled)"
    briefing_text = (
        f"⚙️ *BLACKBOX System Update:*\n"
        f"Founder Disappears Mode is now *{mode_text}*."
    )
    await caspian_service.send_message(
        channel=ChannelType.TELEGRAM,
        recipient_id="founder_tg",
        conversation_id="system_notifications",
        text=briefing_text,
    )
    return {"status": "success", "settings": await get_settings()}


@router.post("/simulate")
async def trigger_simulation_endpoint(payload: SimulationRequest):
    """
    Main Hackathon Judge Simulation runner.
    Triggers simulated inbound channel messages for the 5 demo cases.
    """
    sim_type = payload.type.lower()
    logger.info(f"Simulating event: {sim_type}")
    
    if sim_type == "support":
        # Demo 1: Customer email arrives
        result = await workflow_manager.handle_inbound_message(
            channel=ChannelType.EMAIL,
            sender_id="client_alex",
            sender_name="Alex Mercer",
            sender_email="alex@mercer.com",
            text="Hi support, I still haven't received my refund for the order cancellation. Can you check this?",
        )
        return {"status": "success", "result": result}
    elif sim_type == "lead":
        # Demo lead email reply or follow-up
        result = await workflow_manager.handle_inbound_message(
            channel=ChannelType.EMAIL,
            sender_id="lead_tesla",
            sender_name="Tesla Corporate Procurement",
            sender_email="procurement@tesla.com",
            text="Interested in your enterprise task automation solution. Let's set up a time.",
        )
        return {"status": "success", "result": result}
        
    elif sim_type == "blocker":
        # Demo 2: Slack blocker detected
        result = await workflow_manager.handle_inbound_message(
            channel=ChannelType.SLACK,
            sender_id="dev_bob",
            sender_name="Bob (Backend)",
            text="🚨 BLOCKER: Payments System Gateway is down! Out of memory error. Database connection pool exhausted.",
        )
        return {"status": "success", "result": result}
        
    elif sim_type == "bug":
        # Demo 3: Discord community bug report
        result = await workflow_manager.handle_inbound_message(
            channel=ChannelType.DISCORD,
            sender_id="sarah_discord",
            sender_name="Sarah Chen",
            text="Hey team, there is a bug on the checkout page. The system throws a 404 error when selecting domestic cards.",
        )
        return {"status": "success", "result": result}
        
    elif sim_type == "delay":
        # Demo 4: Vendor WhatsApp delay message
        result = await workflow_manager.handle_inbound_message(
            channel=ChannelType.WHATSAPP,
            sender_id="vendor_dhl",
            sender_name="DHL Express Logistics",
            text="Update: Shipment VND-9988 for Payments System Gateway hardware is delayed outside Bangalore due to heavy rains.",
        )
        return {"status": "success", "result": result}
        
    elif sim_type == "briefing":
        # Demo 5: Founder Daily Briefing
        stats = await get_kpi_stats()
        briefing_text = (
            f"📊 *BLACKBOX Founder Daily Briefing*\n"
            f"Good morning! Startup operations summary:\n\n"
            f"💼 *Revenue Opportunities:* {stats['opportunities']} Active Leads\n"
            f"⚠️ *Customer Risks:* {stats['risks']} Escalated Tickets\n"
            f"📋 *Open Issues:* {stats['issues']} Active Work Tasks\n"
            f"📦 *Vendor Delays:* {stats['delays']} Delayed Shipments\n"
            f"📅 *Meetings Today:* {stats['meetings']} Confirmed Appointments\n\n"
            f"BLACKBOX is running fully autonomously. No actions required."
        )
        msg = await caspian_service.send_message(
            channel=ChannelType.TELEGRAM,
            recipient_id="founder_tg",
            conversation_id="daily_briefing",
            text=briefing_text,
        )
        return {"status": "success", "message_id": msg.id}

    elif sim_type == "escalate":
        # Escalation trigger for unresolved bugs
        tickets = await list_tickets(status=TicketStatus.OPEN.value)
        unresolved_bug = next((t for t in tickets if t.category == IncidentCategory.COMMUNITY_INTELLIGENCE), None)
        if unresolved_bug:
            escalation_text = (
                f"⚠️ *SLA ESCALATION* [{unresolved_bug.id}]\n\n"
                f"The Discord community bug report '{unresolved_bug.description}' has been unresolved for 2 hours.\n"
                f"Would you like to assign this to Alice (DevOps) or Bob (Backend)?"
            )
            buttons_list = [
                {"text": "Assign Alice", "value": f"ASSIGN dev_alice {unresolved_bug.id}"},
                {"text": "Assign Bob", "value": f"ASSIGN dev_bob {unresolved_bug.id}"},
            ]
            msg = await caspian_service.send_message(
                channel=ChannelType.TELEGRAM,
                recipient_id="founder_tg",
                conversation_id=f"esc_{unresolved_bug.id}",
                text=escalation_text,
                ticket_id=unresolved_bug.id,
                buttons_list=buttons_list,
            )
            await log_audit_action(unresolved_bug.id, "SLA_ESCALATED", "BLACKBOX", "SLA breached. Escalated incident to Founder.")
            await update_ticket_status(unresolved_bug.id, TicketStatus.ESCALATED)
            return {"status": "success", "message_id": msg.id}
        else:
            raise HTTPException(status_code=400, detail="No active community bug tickets found to escalate.")
            
    else:
        raise HTTPException(status_code=400, detail=f"Unknown simulation type '{sim_type}'.")


@router.post("/channels/{channel}/inbound")
async def unified_channel_inbound_endpoint(channel: str, payload: Dict[str, Any]):
    """
    Unified inbound gateway. Routes live webhook triggers to the workflow manager.
    """
    try:
        from backend.models import ChannelType
        sender_id = payload.get("sender_id", "unknown_user")
        sender_name = payload.get("sender_name", "Unknown User")
        sender_email = payload.get("sender_email")
        text = payload.get("text", "")
        conversation_id = payload.get("conversation_id")
        
        result = await workflow_manager.handle_inbound_message(
            channel=ChannelType(channel),
            sender_id=sender_id,
            sender_name=sender_name,
            sender_email=sender_email,
            conversation_id=conversation_id,
            text=text,
        )
        return result
    except Exception as e:
        logger.exception(f"Error in unified channel inbound: {e}")
        raise HTTPException(status_code=500, detail=str(e))
