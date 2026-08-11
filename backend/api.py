from typing import List, Optional, Dict, Any
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import PlainTextResponse

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
    VendorProfile,
    VendorSearchRequest,
    QuoteAnalyzeRequest,
    QuotationAnalysisResult,
    VendorScoreRequest,
    VendorScoreResult,
    NegotiationRequest,
    NegotiationThread,
    RecommendationRequest,
    SupplierRecommendation,
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
    list_vendors,
    list_negotiations,
)
from backend.ai_engine import ai_engine
from backend.workflow_manager import workflow_manager
from backend.caspian_service import caspian_service
from backend.vendor_intelligence import vendor_intelligence

router = APIRouter()


# ---------------------------------------------------------
# Core Procurement Endpoints
# ---------------------------------------------------------

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


# ---------------------------------------------------------
# Vendor Intelligence Engine APIs (Required 8 & 9)
# ---------------------------------------------------------

@router.get("/vendors", response_model=List[VendorProfile])
async def get_vendor_directory(
    category: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
):
    """List all registered vendors from the enterprise supplier directory."""
    return await list_vendors(category=category, search=search)


@router.post("/vendors/search", response_model=List[VendorProfile])
async def search_vendors_endpoint(payload: VendorSearchRequest):
    """
    1. Vendor Discovery Agent API:
    Search vendor database & external catalogs matching product specifications and budget.
    """
    vendors = await vendor_intelligence.discover_vendors(
        product=payload.product,
        quantity=payload.quantity,
        budget=payload.budget,
        category=payload.category,
    )
    return vendors


@router.post("/quotes/analyze", response_model=QuotationAnalysisResult)
async def analyze_quotes_endpoint(payload: QuoteAnalyzeRequest):
    """
    2. Quotation Analysis Agent API:
    Accept multiple quotations, normalize metrics, generate comparison table,
    and evaluate price deviations.
    """
    result = vendor_intelligence.analyze_quotations(
        product=payload.product,
        quantity=payload.quantity,
        budget=payload.budget,
        quotes=payload.quotes,
    )
    return result


@router.post("/vendors/score", response_model=List[VendorScoreResult])
async def score_vendors_endpoint(payload: VendorScoreRequest):
    """
    3. Vendor Scoring Engine API:
    Calculate composite score using:
    40% Price, 25% Delivery, 20% Reliability, 15% Warranty.
    """
    scores = vendor_intelligence.score_vendors(
        budget=payload.budget,
        quotes=payload.quotes,
        target_delivery_days=payload.target_delivery_days or 10,
    )
    return scores


@router.post("/vendors/negotiate", response_model=NegotiationThread)
async def negotiate_vendor_endpoint(payload: NegotiationRequest):
    """
    4. Negotiation Agent API:
    Generate counter-offer negotiation email automatically, track status
    (Sent -> Replied -> Improved Offer), and calculate savings achieved.
    """
    thread = await vendor_intelligence.create_and_send_negotiation(
        vendor_name=payload.vendor_name,
        initial_price=payload.initial_price,
        competing_lower_price=payload.competing_lower_price,
        target_discount_pct=payload.target_discount_percentage,
        product_name=payload.product_name or "Laptop",
        quantity=payload.quantity or 100,
        vendor_email=payload.vendor_email,
        procurement_id=payload.procurement_id or "PROC-2026-001",
    )
    return thread


@router.post("/vendors/recommend", response_model=SupplierRecommendation)
async def recommend_vendor_endpoint(payload: RecommendationRequest):
    """
    6. Recommendation Engine API:
    Synthesize scores, risk flags, and delivery capabilities to output
    the optimal supplier recommendation with justifications.
    """
    try:
        rec = vendor_intelligence.recommend_supplier(
            product=payload.product,
            quantity=payload.quantity,
            budget=payload.budget,
            quotes=payload.quotes,
        )
        return rec
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/negotiations", response_model=List[NegotiationThread])
async def get_negotiations_endpoint(procurement_id: Optional[str] = None):
    """List ongoing and completed negotiation threads."""
    return await list_negotiations(procurement_id=procurement_id)


# ---------------------------------------------------------
# Executive Reporting Engine Endpoints (Feature 7)
# ---------------------------------------------------------

@router.get("/reports/comparison", response_class=PlainTextResponse)
async def get_comparison_report(
    product: str = "Laptop",
    quantity: int = 100,
    budget: float = 4500000.0,
):
    """Generate and download Vendor Comparison Markdown Report."""
    from backend.models import QuotationInput
    sample_quotes = [
        QuotationInput(vendor_name="Dell Partner (Enterprise Solutions)", price=4150000.0, delivery_days=7, warranty_years=3, vendor_rating=4.8, reliability_score=96.0),
        QuotationInput(vendor_name="HP Commercial Direct", price=4320000.0, delivery_days=9, warranty_years=3, vendor_rating=4.6, reliability_score=92.0),
        QuotationInput(vendor_name="Lenovo Premier Solutions", price=4400000.0, delivery_days=8, warranty_years=3, vendor_rating=4.5, reliability_score=90.0),
    ]
    report = vendor_intelligence.generate_vendor_comparison_report(
        product=product,
        quantity=quantity,
        budget=budget,
        quotes=sample_quotes,
    )
    return report


@router.get("/reports/negotiation", response_class=PlainTextResponse)
async def get_negotiation_report():
    """Generate and download Negotiation Activity Markdown Report."""
    threads = await list_negotiations()
    report = vendor_intelligence.generate_negotiation_report(threads=threads)
    return report


# ---------------------------------------------------------
# Multi-Channel Simulator & Dashboard Stats
# ---------------------------------------------------------

@router.post("/api/channels/simulate-message")
async def simulate_channel_message(payload: SimulateMessageRequest):
    """
    Interactive Multi-Channel Simulator endpoint for Telegram & Email.
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
