import re
import uuid
import logging
from typing import Optional, Dict, Any, List, Tuple
from datetime import datetime

from backend.models import (
    ProcurementTicket,
    ProcurementStatus,
    ProcurementRequirement,
    VendorQuote,
    ChannelType,
    ChannelMessage,
    ApprovalDecision,
)
from backend.database import (
    get_next_procurement_id,
    create_procurement,
    get_procurement,
    list_procurements,
    update_procurement_stage,
    record_approval_decision,
    get_conversation_state,
    save_conversation_state,
    clear_conversation_state,
    save_channel_message,
)
from backend.ai_engine import ai_engine
from backend.caspian_service import caspian_service

logger = logging.getLogger("workflow_manager")


class WorkflowManager:
    """
    Orchestrates the end-to-end Enterprise AI Procurement Workflow:
    Requirement Ingestion -> Multi-turn Follow-up -> Structuring & Ticket Generation ->
    Vendor Bidding -> Approval Routing -> Multi-Channel Notifications.
    """

    async def handle_inbound_message(
        self,
        channel: ChannelType,
        sender_id: str,
        sender_name: str,
        sender_email: Optional[str],
        conversation_id: str,
        text: str,
        subject: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Process any incoming message from Telegram, Email, or Web Simulator.
        """
        raw_text = text.strip()

        # 1. Save user's incoming message
        inbound_msg = ChannelMessage(
            id=f"MSG-{uuid.uuid4().hex[:10]}",
            conversation_id=conversation_id,
            channel=channel.value,
            sender_id=sender_id,
            sender_name=sender_name,
            recipient="procurement_ai_agent",
            subject=subject,
            text=raw_text,
            is_agent=False,
            timestamp=datetime.utcnow(),
        )
        await save_channel_message(inbound_msg)

        # 2. Check if this message is an approval response (e.g. "Approve", "Reject", "Approve PROC-2026-001")
        approval_decision = self._check_approval_command(raw_text)
        if approval_decision:
            action, target_ticket_id = approval_decision
            return await self._process_channel_approval(
                action=action,
                ticket_id=target_ticket_id,
                channel=channel,
                sender_id=sender_id,
                sender_name=sender_name,
                conversation_id=conversation_id,
            )

        # 3. Retrieve ongoing conversation state for multi-turn dialogue
        existing_state = await get_conversation_state(conversation_id)

        # 4. AI Engine requirement extraction and missing field detection
        extraction = ai_engine.process_message(
            text=raw_text,
            current_state=existing_state,
            channel=channel,
            sender_id=sender_id,
            sender_name=sender_name,
            sender_email=sender_email,
        )

        # If information is missing, ask intelligent follow-up question
        if not extraction.is_complete:
            # Persist intermediate state
            current_dict = {
                "product": extraction.requirement.product,
                "quantity": extraction.requirement.quantity,
                "budget": extraction.requirement.budget,
                "currency": extraction.requirement.currency,
                "delivery_days": extraction.requirement.delivery_days,
                "specifications": extraction.requirement.specifications,
                "requester_id": sender_id,
                "requester_name": sender_name,
                "requester_email": sender_email,
                "channel": channel.value,
            }
            await save_conversation_state(conversation_id, sender_id, channel.value, current_dict)

            # Reply with follow-up question
            follow_up = extraction.follow_up_question or "Could you provide additional details regarding your budget and timeline?"
            await caspian_service.send_message(
                channel=channel,
                recipient_id=sender_id,
                conversation_id=conversation_id,
                text=follow_up,
                subject=f"Re: {subject}" if subject else "Procurement Requirement Follow-up",
            )

            return {
                "status": "in_progress",
                "is_complete": False,
                "missing_fields": extraction.missing_fields,
                "reply": follow_up,
                "current_state": current_dict,
            }

        # 5. Requirements are COMPLETE! Create structured ticket & run vendor search
        await clear_conversation_state(conversation_id)

        req = extraction.requirement
        ticket_id = await get_next_procurement_id()

        # Generate competitive vendor quotes
        quotes = ai_engine.generate_vendor_quotes(req, ticket_id)
        recommended_quote = next((q for q in quotes if q.is_recommended), quotes[0] if quotes else None)

        title = f"{req.quantity}x {req.product} Procurement"
        summary = (
            f"Procurement for {req.quantity} {req.product}(s) with budget of {ai_engine.format_currency_inr(req.budget or 0)}. "
            f"Specifications: {', '.join(req.specifications) if req.specifications else 'Standard'}. "
            f"Best offer from {recommended_quote.vendor_name if recommended_quote else 'Vendor'} "
            f"at {ai_engine.format_currency_inr(recommended_quote.price if recommended_quote else req.budget or 0)} "
            f"with delivery in {recommended_quote.delivery_days if recommended_quote else req.delivery_days} days."
        )

        ticket = ProcurementTicket(
            id=ticket_id,
            title=title,
            product=req.product or "Item",
            quantity=req.quantity or 1,
            budget=req.budget or 0.0,
            currency=req.currency,
            delivery_days=req.delivery_days or 10,
            specifications=req.specifications,
            status=ProcurementStatus.APPROVAL_PENDING,
            current_stage="Approval Pending",
            requester_id=sender_id,
            requester_name=sender_name,
            requester_email=sender_email,
            channel=channel,
            recommended_vendor=recommended_quote.vendor_name if recommended_quote else None,
            recommended_price=recommended_quote.price if recommended_quote else req.budget,
            recommended_delivery_days=recommended_quote.delivery_days if recommended_quote else req.delivery_days,
            quotes=quotes,
            summary=summary,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )

        created_ticket = await create_procurement(ticket)

        # 6. Send Ticket Creation & Structured Confirmation to Employee
        structured_json = {
            "product": ticket.product,
            "quantity": ticket.quantity,
            "budget": ticket.budget,
            "delivery_days": ticket.delivery_days,
            "specifications": ticket.specifications,
        }

        confirmation_text = (
            f"🎉 *Procurement Ticket Created: {ticket.id}*\n\n"
            f"📋 *Structured Requirements:*\n"
            f"• Product: {ticket.product}\n"
            f"• Quantity: {ticket.quantity}\n"
            f"• Budget: {ai_engine.format_currency_inr(ticket.budget)}\n"
            f"• Delivery: {ticket.delivery_days} Days\n"
            f"• Specs: {', '.join(ticket.specifications)}\n\n"
            f"🔍 *Vendor Search Complete:* 3 competitive bids evaluated."
        )

        await caspian_service.send_message(
            channel=channel,
            recipient_id=sender_id,
            conversation_id=conversation_id,
            text=confirmation_text,
            procurement_id=ticket.id,
        )

        # 7. Dispatch Approval Request to Manager / Channel
        approval_prompt = ai_engine.generate_approval_prompt(ticket)
        subject_mail, text_mail, html_mail = ai_engine.generate_email_summary(ticket)

        buttons_action = [
            {"text": "✅ Approve", "value": f"APPROVE {ticket.id}"},
            {"text": "❌ Reject", "value": f"REJECT {ticket.id}"},
        ]

        await caspian_service.send_message(
            channel=channel,
            recipient_id=sender_id,
            conversation_id=conversation_id,
            text=approval_prompt,
            html=html_mail if channel == ChannelType.EMAIL else None,
            subject=subject_mail if channel == ChannelType.EMAIL else None,
            procurement_id=ticket.id,
            buttons_list=buttons_action,
        )

        return {
            "status": "ticket_created",
            "is_complete": True,
            "ticket": created_ticket,
            "structured_requirement": structured_json,
            "approval_prompt": approval_prompt,
            "quotes": quotes,
        }

    def _check_approval_command(self, text: str) -> Optional[Tuple[str, Optional[str]]]:
        """Detect if message is an approval or rejection command."""
        text_clean = text.strip()
        text_lower = text_clean.lower()

        # Check for explicit command with ID: e.g. "APPROVE PROC-2026-001" or "REJECT PROC-2026-001"
        id_match = re.search(r'\b(PROC-[0-9]{4}-[0-9]{3})\b', text_clean, re.IGNORECASE)
        ticket_id = id_match.group(1).upper() if id_match else None

        if re.search(r'\b(approve|approved|accept|yes|confirm|looks good|proceed)\b', text_lower):
            return ("APPROVED", ticket_id)
        elif re.search(r'\b(reject|rejected|decline|no|cancel|deny)\b', text_lower):
            return ("REJECTED", ticket_id)

        return None

    async def _process_channel_approval(
        self,
        action: str,
        ticket_id: Optional[str],
        channel: ChannelType,
        sender_id: str,
        sender_name: str,
        conversation_id: str,
    ) -> Dict[str, Any]:
        """Handle manager approval or rejection command via message."""
        target_ticket = None

        if ticket_id:
            target_ticket = await get_procurement(ticket_id)
        else:
            # Find latest ticket in Approval Pending stage
            pending_tickets = await list_procurements(status=ProcurementStatus.APPROVAL_PENDING.value, limit=5)
            if pending_tickets:
                target_ticket = pending_tickets[0]

        if not target_ticket:
            reply_text = "⚠️ No pending procurement request found to approve/reject."
            await caspian_service.send_message(
                channel=channel,
                recipient_id=sender_id,
                conversation_id=conversation_id,
                text=reply_text,
            )
            return {"status": "error", "message": reply_text}

        # Apply approval decision
        await record_approval_decision(
            procurement_id=target_ticket.id,
            status=action,
            approver=sender_name or "Manager",
            channel=channel.value,
            notes=f"Processed via {channel.value.title()} interaction",
        )

        if action == "APPROVED":
            reply_text = (
                f"✅ *Procurement Approved!* [{target_ticket.id}]\n\n"
                f"Vendor *{target_ticket.recommended_vendor}* has been officially selected.\n"
                f"PO generation and fulfillment tracking initiated.\n"
                f"Estimated delivery: {target_ticket.recommended_delivery_days} days."
            )
        else:
            reply_text = (
                f"❌ *Procurement Rejected* [{target_ticket.id}]\n\n"
                f"The request for {target_ticket.quantity}x {target_ticket.product} has been declined."
            )

        await caspian_service.send_message(
            channel=channel,
            recipient_id=sender_id,
            conversation_id=conversation_id,
            text=reply_text,
            procurement_id=target_ticket.id,
        )

        updated_ticket = await get_procurement(target_ticket.id)
        return {
            "status": "approval_processed",
            "decision": action,
            "ticket": updated_ticket,
            "reply": reply_text,
        }

    async def advance_stage(self, procurement_id: str, new_stage: str, actor: str = "Manager") -> Optional[ProcurementTicket]:
        """Manually or programmatically advance ticket stage."""
        ticket = await get_procurement(procurement_id)
        if not ticket:
            return None

        status_mapping = {
            "Open": ProcurementStatus.OPEN,
            "Vendor Search": ProcurementStatus.VENDOR_SEARCH,
            "Negotiation": ProcurementStatus.NEGOTIATION,
            "Approval Pending": ProcurementStatus.APPROVAL_PENDING,
            "Approved": ProcurementStatus.APPROVED,
            "Rejected": ProcurementStatus.REJECTED,
            "Completed": ProcurementStatus.COMPLETED,
        }

        new_status = status_mapping.get(new_stage, ticket.status)
        await update_procurement_stage(
            procurement_id=procurement_id,
            status=new_status,
            current_stage=new_stage,
            actor=actor,
        )
        return await get_procurement(procurement_id)


# Global singleton instance
workflow_manager = WorkflowManager()
