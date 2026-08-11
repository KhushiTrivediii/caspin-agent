from typing import List, Optional, Dict, Any
from fastapi import APIRouter, HTTPException, Query
from backend.models import (
    ProcurementTicket,
    CreateProcurementRequest,
    ApprovalActionRequest,
    SimulateMessageRequest,
    AdvanceStageRequest,
    ChannelMessage,
    AuditLog,
    ProcurementRequirement,
    ProcurementStatus,
    ChannelType,
)
from backend.database import (
    list_procurements,
    get_procurement,
    get_next_procurement_id,
    create_procurement,
    record_approval_decision,
    get_audit_logs,
    get_channel_messages,
    get_dashboard_stats,
)
from backend.ai_engine import ai_engine
from backend.workflow_manager import workflow_manager
from backend.caspian_service import caspian_service

router = APIRouter()


@router.get("/procurements", response_model=List[ProcurementTicket])
async def get_all_procurements(
    status: Optional[str] = Query(None, description="Filter by status (e.g. Open, Approval Pending, Approved, Completed)"),
    channel: Optional[str] = Query(None, description="Filter by channel (telegram, email, web)"),
    search: Optional[str] = Query(None, description="Search term for product, ID, requester"),
    limit: int = Query(50, ge=1, le=100),
):
    """Retrieve list of all procurement tickets with optional filters."""
    return await list_procurements(status=status, channel=channel, search=search, limit=limit)


@router.get("/procurement/{procurement_id}", response_model=ProcurementTicket)
async def get_procurement_by_id(procurement_id: str):
    """Get single procurement ticket with quotes, approval details, and specifications."""
    ticket = await get_procurement(procurement_id)
    if not ticket:
        raise HTTPException(status_code=404, detail=f"Procurement ticket '{procurement_id}' not found.")
    return ticket


@router.post("/procurement", response_model=ProcurementTicket)
async def create_new_procurement(payload: CreateProcurementRequest):
    """Directly create a new structured procurement ticket and run automated vendor evaluation."""
    ticket_id = await get_next_procurement_id()
    req = ProcurementRequirement(
        product=payload.product,
        quantity=payload.quantity,
        budget=payload.budget,
        currency=payload.currency,
        delivery_days=payload.delivery_days,
        specifications=payload.specifications,
        requester_name=payload.requester_name,
        requester_email=payload.requester_email,
        channel=payload.channel,
    )

    quotes = ai_engine.generate_vendor_quotes(req, ticket_id)
    recommended_quote = next((q for q in quotes if q.is_recommended), quotes[0] if quotes else None)

    ticket = ProcurementTicket(
        id=ticket_id,
        title=f"{req.quantity}x {req.product} Procurement",
        product=req.product,
        quantity=req.quantity,
        budget=req.budget,
        currency=req.currency,
        delivery_days=req.delivery_days,
        specifications=req.specifications,
        status=ProcurementStatus.APPROVAL_PENDING,
        current_stage="Approval Pending",
        requester_name=payload.requester_name,
        requester_email=payload.requester_email,
        channel=payload.channel,
        recommended_vendor=recommended_quote.vendor_name if recommended_quote else None,
        recommended_price=recommended_quote.price if recommended_quote else req.budget,
        recommended_delivery_days=recommended_quote.delivery_days if recommended_quote else req.delivery_days,
        quotes=quotes,
        summary=f"Created via Direct API. Best bid from {recommended_quote.vendor_name if recommended_quote else 'Vendor'} at {ai_engine.format_currency_inr(recommended_quote.price if recommended_quote else req.budget)}.",
    )

    created = await create_procurement(ticket)
    return created


@router.post("/procurement/{procurement_id}/approve", response_model=ProcurementTicket)
async def approve_procurement(procurement_id: str, payload: Optional[ApprovalActionRequest] = None):
    """Approve a pending procurement recommendation."""
    ticket = await get_procurement(procurement_id)
    if not ticket:
        raise HTTPException(status_code=404, detail=f"Procurement ticket '{procurement_id}' not found.")

    approver = payload.approver if payload else "Executive Approver"
    channel = payload.channel if payload else "web"
    notes = payload.notes if payload else "Approved via Dashboard"

    await record_approval_decision(
        procurement_id=procurement_id,
        status="APPROVED",
        approver=approver,
        channel=channel,
        notes=notes,
    )

    # Disclose update notification
    await caspian_service.send_message(
        channel=ticket.channel,
        recipient_id=ticket.requester_id or "user",
        conversation_id=f"{ticket.channel.value}_{ticket.requester_id or 'default'}",
        text=f"✅ *Procurement Approved!* [{ticket.id}] for {ticket.quantity}x {ticket.product}. Selected Vendor: {ticket.recommended_vendor}.",
        procurement_id=ticket.id,
    )

    return await get_procurement(procurement_id)


@router.post("/procurement/{procurement_id}/reject", response_model=ProcurementTicket)
async def reject_procurement(procurement_id: str, payload: Optional[ApprovalActionRequest] = None):
    """Reject a procurement recommendation."""
    ticket = await get_procurement(procurement_id)
    if not ticket:
        raise HTTPException(status_code=404, detail=f"Procurement ticket '{procurement_id}' not found.")

    approver = payload.approver if payload else "Executive Approver"
    channel = payload.channel if payload else "web"
    notes = payload.notes if payload else "Declined via Dashboard"

    await record_approval_decision(
        procurement_id=procurement_id,
        status="REJECTED",
        approver=approver,
        channel=channel,
        notes=notes,
    )

    await caspian_service.send_message(
        channel=ticket.channel,
        recipient_id=ticket.requester_id or "user",
        conversation_id=f"{ticket.channel.value}_{ticket.requester_id or 'default'}",
        text=f"❌ *Procurement Declined* [{ticket.id}] for {ticket.quantity}x {ticket.product}.",
        procurement_id=ticket.id,
    )

    return await get_procurement(procurement_id)


@router.post("/procurement/{procurement_id}/advance-stage", response_model=ProcurementTicket)
async def advance_stage(procurement_id: str, payload: AdvanceStageRequest):
    """Advance procurement ticket to specified workflow stage."""
    updated = await workflow_manager.advance_stage(procurement_id, payload.stage)
    if not updated:
        raise HTTPException(status_code=404, detail=f"Procurement ticket '{procurement_id}' not found.")
    return updated


@router.post("/api/channels/simulate-message")
async def simulate_channel_message(payload: SimulateMessageRequest):
    """
    Interactive Multi-Channel Simulator endpoint for Telegram & Email.
    Allows testing conversational requirement collection, follow-ups,
    ticket creation, and approval flows in real time.
    """
    conversation_id = payload.conversation_id or f"{payload.channel.value}_{payload.sender_id}"
    result = await workflow_manager.handle_inbound_message(
        channel=payload.channel,
        sender_id=payload.sender_id,
        sender_name=payload.sender_name,
        sender_email=payload.sender_email,
        conversation_id=conversation_id,
        text=payload.text,
        subject=payload.subject,
    )
    return result


@router.get("/api/channels/messages", response_model=List[ChannelMessage])
async def get_messages(
    conversation_id: Optional[str] = None,
    procurement_id: Optional[str] = None,
):
    """Retrieve message history for active simulation or specific ticket."""
    return await get_channel_messages(conversation_id=conversation_id, procurement_id=procurement_id)


@router.get("/api/stats")
async def get_stats():
    """Get KPI summary statistics for the executive dashboard."""
    return await get_dashboard_stats()


@router.get("/api/audit-logs/{procurement_id}", response_model=List[AuditLog])
async def get_ticket_audit_logs(procurement_id: str):
    """Get audit trail logs for a procurement ticket."""
    return await get_audit_logs(procurement_id)
