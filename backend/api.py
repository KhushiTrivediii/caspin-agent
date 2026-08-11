import aiosqlite
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import PlainTextResponse, HTMLResponse

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
    PurchaseOrder,
    ManualQuoteInput,
    VendorQuote,
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
    save_purchase_order,
    get_purchase_order,
    add_vendor_quote_to_db,
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


# ---------------------------------------------------------
# New Enterprise PO, Quote Ingestion & Export Endpoints
# ---------------------------------------------------------

@router.post("/procurement/{id}/quotes", response_model=ProcurementTicket)
async def ingest_custom_quote(id: str, quote_in: ManualQuoteInput):
    """
    Ingest a custom vendor quote, add it to the ticket, and re-run recommendation.
    """
    ticket = await get_procurement(id)
    if not ticket:
        raise HTTPException(status_code=404, detail="Procurement ticket not found.")

    import uuid
    from datetime import datetime
    from backend.po_generator import po_engine

    # Convert ManualQuoteInput to VendorQuote
    new_quote = VendorQuote(
        id=f"QUOTE-{uuid.uuid4().hex[:8].upper()}",
        vendor_name=quote_in.vendor_name,
        price=quote_in.price,
        delivery_days=quote_in.delivery_days,
        warranty_years=quote_in.warranty_years,
        vendor_rating=quote_in.vendor_rating or 4.5,
        reliability_score=quote_in.reliability_score or 90.0,
        specs_matched=ticket.specifications,
        is_recommended=False,
        savings_amount=0.0,
        savings_percentage=0.0,
    )

    await add_vendor_quote_to_db(id, new_quote)

    # Reload the ticket with all quotes
    updated_ticket = await get_procurement(id)
    
    # Calculate recommended quote
    from backend.models import QuotationInput
    scoring_quotes = [
        QuotationInput(
            vendor_name=q.vendor_name,
            price=q.price,
            delivery_days=q.delivery_days,
            warranty_years=q.warranty_years,
            vendor_rating=q.rating,
            reliability_score=q.reliability_score,
            specs_matched=q.specs_matched,
        )
        for q in updated_ticket.quotes
    ]

    if scoring_quotes:
        rec = vendor_intelligence.recommend_supplier(
            product=updated_ticket.product,
            quantity=updated_ticket.quantity,
            budget=updated_ticket.budget,
            quotes=scoring_quotes,
        )

        # Update the recommended vendor on the ticket in database
        async with aiosqlite.connect("./procurements.db") as db:
            await db.execute(
                """
                UPDATE procurements
                SET recommended_vendor = ?,
                    recommended_price = ?,
                    recommended_delivery_days = ?,
                    summary = ?
                WHERE id = ?
                """,
                (
                    rec.recommended_vendor,
                    rec.recommended_price,
                    rec.recommended_delivery_days or 7,
                    rec.reasons[1] if len(rec.reasons) > 1 else (rec.reasons[0] if rec.reasons else "Recommendation updated"),
                    id,
                ),
            )
            # Mark recommended quote in DB
            await db.execute(
                "UPDATE vendor_quotes SET is_recommended = 1 WHERE procurement_id = ? AND vendor_name = ?",
                (id, rec.recommended_vendor),
            )
            await db.commit()

    # Return refreshed ticket
    return await get_procurement(id)


@router.get("/procurement/{id}/po", response_model=PurchaseOrder)
async def get_po_endpoint(id: str):
    """Retrieve the generated Purchase Order for an approved procurement ticket."""
    po = await get_purchase_order(id)
    if not po:
        raise HTTPException(
            status_code=404,
            detail="Purchase Order not found. Ensure the ticket has been approved by the manager to issue a PO."
        )
    return po


@router.get("/procurement/{id}/po/html", response_class=HTMLResponse)
async def get_po_html_endpoint(id: str):
    """Generate and view the formatted, printable corporate Purchase Order document."""
    po = await get_purchase_order(id)
    ticket = await get_procurement(id)
    if not po or not ticket:
        raise HTTPException(
            status_code=404,
            detail="PO or ticket not found. Ensure the ticket is approved."
        )
    from backend.po_generator import po_engine
    return po_engine.generate_po_html(po, ticket)


@router.get("/export/procurements/csv", response_class=PlainTextResponse)
async def export_csv_endpoint():
    """Export all procurement records as a CSV download."""
    tickets = await list_procurements(limit=200)
    from backend.po_generator import po_engine
    csv_data = po_engine.export_procurements_csv(tickets)
    return csv_data


@router.get("/export/procurements/json", response_model=List[ProcurementTicket])
async def export_json_endpoint():
    """Export all procurement records as structured JSON."""
    tickets = await list_procurements(limit=200)
    return tickets

