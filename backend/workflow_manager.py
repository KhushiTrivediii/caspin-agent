import re
import uuid
import logging
from datetime import datetime
from typing import Dict, Any, Optional, Tuple

from backend.models import (
    ChannelType,
    MessageLog,
    IncidentTicket,
    TicketStatus,
    IncidentCategory,
)
from backend.database import (
    create_ticket,
    get_ticket,
    update_ticket_status,
    log_audit_action,
    save_channel_message,
    get_settings,
    get_channel_messages,
    add_graph_node,
    add_graph_edge,
)
from backend.caspian_service import caspian_service

logger = logging.getLogger("workflow_manager")


class WorkflowManager:
    """
    BLACKBOX AI Autonomous Cognitive Coordinator.
    Performs classification, Memory Graph lookups, action routing,
    and coordinates cross-channel communications.
    """

    async def handle_inbound_message(
        self,
        channel: ChannelType,
        sender_id: str,
        sender_name: str,
        sender_email: Optional[str] = None,
        conversation_id: Optional[str] = None,
        text: str = "",
    ) -> Dict[str, Any]:
        """
        Normalized entry point for all channels.
        Processes incoming texts, updates state/memory, and takes outbound actions.
        """
        raw_text = text.strip()
        conv_id = conversation_id or f"{channel.value}_{sender_id}"
        
        # 1. Save incoming message
        inbound_msg = MessageLog(
            id=f"MSG-{uuid.uuid4().hex[:10]}",
            channel=channel.value,
            direction="inbound",
            sender=sender_name or sender_id,
            recipient="blackbox_ai",
            text=raw_text,
            timestamp=datetime.utcnow(),
        )
        await save_channel_message(inbound_msg)

        # 2. Check if this is an operational command from a team member or founder
        action_result = await self._process_command(channel, sender_id, sender_name, conv_id, raw_text)
        if action_result:
            return action_result

        # 3. Route through Agent Engine Cognitive Reasoning Loop
        from backend.agent_engine import agent_engine
        return await agent_engine.process_reasoning_cycle(channel, sender_id, sender_name, raw_text)

    def _classify_message(self, text: str) -> Tuple[IncidentCategory, str]:
        """Classify incoming natural language into categories."""
        text_lower = text.lower()
        if any(k in text_lower for k in ["refund", "money", "charged", "billing", "invoice"]):
            return IncidentCategory.CUSTOMER_SUPPORT, "High"
        if any(k in text_lower for k in ["blocker", "blocked", "down", "broken", "biometric", "offline", "server Gateway"]):
            return IncidentCategory.TEAM_OPERATIONS, "Critical"
        if any(k in text_lower for k in ["bug", "error", "404", "500", "crashed", "fails"]):
            return IncidentCategory.COMMUNITY_INTELLIGENCE, "Medium"
        if any(k in text_lower for k in ["delay", "delayed", "shipment", "freight", "customs", "delivery"]):
            return IncidentCategory.VENDOR_INTELLIGENCE, "High"
        return IncidentCategory.LEAD_FOLLOWUP, "Low"

    async def _process_command(
        self,
        channel: ChannelType,
        sender_id: str,
        sender_name: str,
        conversation_id: str,
        text: str,
    ) -> Optional[Dict[str, Any]]:
        """Detect and execute developer or manager actions (Accept/Resolve/Assign)."""
        text_upper = text.upper()
        
        # Scenario A: Technician accepts a task
        if "ACCEPT" in text_upper:
            # Find the latest open ticket assigned to this contact
            assigned_ticket = await self._find_active_ticket_by_contact(sender_id)
            if assigned_ticket:
                await update_ticket_status(assigned_ticket.id, TicketStatus.OPEN, assigned_to=sender_name)
                await log_audit_action(assigned_ticket.id, "ACCEPT_TASK", sender_name, "Technician accepted task and started work.")
                
                # Notify original reporter
                reporter_channel = ChannelType(assigned_ticket.reporter_contact.split("_")[0]) if "_" in assigned_ticket.reporter_contact else ChannelType.EMAIL
                reporter_id = assigned_ticket.reporter_contact.split("_")[1] if "_" in assigned_ticket.reporter_contact else assigned_ticket.reporter_contact
                
                update_text = f"⚙️ *Update [INC-2026]:* Engineer {sender_name} has accepted task and is working on a fix."
                await caspian_service.send_message(
                    channel=reporter_channel,
                    recipient_id=reporter_id,
                    conversation_id=f"rep_{assigned_ticket.id}",
                    text=update_text,
                    ticket_id=assigned_ticket.id,
                )
                return {"status": "accepted", "ticket_id": assigned_ticket.id}

        # Scenario B: Technician resolves a task
        if "RESOLVED" in text_upper:
            assigned_ticket = await self._find_active_ticket_by_contact(sender_id)
            if assigned_ticket:
                res_details = text.split("RESOLVED")[-1].replace("-", "").strip() or "Issue resolved by technician."
                await update_ticket_status(assigned_ticket.id, TicketStatus.RESOLVED, summary=res_details)
                await log_audit_action(assigned_ticket.id, "RESOLVE_TASK", sender_name, f"Task completed: {res_details}")

                # Notify original reporter
                reporter_channel = ChannelType(assigned_ticket.reporter_contact.split("_")[0]) if "_" in assigned_ticket.reporter_contact else ChannelType.EMAIL
                reporter_id = assigned_ticket.reporter_contact.split("_")[1] if "_" in assigned_ticket.reporter_contact else assigned_ticket.reporter_contact

                resolution_text = f"✅ *Resolved [INC-2026]:* Your issue has been resolved by {sender_name}. Summary: {res_details}"
                await caspian_service.send_message(
                    channel=reporter_channel,
                    recipient_id=reporter_id,
                    conversation_id=f"rep_{assigned_ticket.id}",
                    text=resolution_text,
                    ticket_id=assigned_ticket.id,
                )
                return {"status": "resolved", "ticket_id": assigned_ticket.id}

        # Scenario C: Manager Assign Action (e.g. from Telegram button)
        # e.g., "ASSIGN dev_alice INC-2026-X"
        assign_match = re.match(r'^ASSIGN\s+(\w+)\s+(INC-2026-\w+)$', text, re.IGNORECASE)
        if assign_match:
            tech_id = assign_match.group(1)
            target_ticket_id = assign_match.group(2)
            ticket = await get_ticket(target_ticket_id)
            if ticket:
                # Map tech_id to name and channel
                tech_name = "Alice (DevOps)" if "alice" in tech_id else "Bob (Backend)"
                tech_contact = "alice_devops" if "alice" in tech_id else "bob_slack"
                tech_channel = ChannelType.TELEGRAM if "alice" in tech_id else ChannelType.SLACK

                await update_ticket_status(target_ticket_id, TicketStatus.OPEN, assigned_to=tech_name)
                await log_audit_action(target_ticket_id, "MANAGER_ASSIGN", "Manager", f"Assigned ticket to {tech_name}")

                # Ping the tech directly
                task_dispatch_text = (
                    f"🚨 *URGENT TASK DISPATCH* [{target_ticket_id}]\n\n"
                    f"Hi {tech_name}, you have been assigned an escalated incident by the Founder:\n"
                    f"• Description: {ticket.description}\n\n"
                    f"Please reply with 'ACCEPT' to start or 'RESOLVED [details]' when done."
                )
                await caspian_service.send_message(
                    channel=tech_channel,
                    recipient_id=tech_contact,
                    conversation_id=f"tech_{target_ticket_id}",
                    text=task_dispatch_text,
                    ticket_id=target_ticket_id,
                    buttons_list=[{"text": "Accept Task", "value": "ACCEPT"}]
                )
                
                # Reply to manager
                await caspian_service.send_message(
                    channel=channel,
                    recipient_id=sender_id,
                    conversation_id=conversation_id,
                    text=f"✅ Assigned {target_ticket_id} to {tech_name} successfully.",
                )
                return {"status": "assigned", "ticket_id": target_ticket_id}

        return None

    async def _find_active_ticket_by_contact(self, contact_id: str) -> Optional[IncidentTicket]:
        """Find latest open ticket associated with a technician contact."""
        from backend.database import list_tickets
        tickets = await list_tickets(status=TicketStatus.OPEN.value)
        # Look for tickets assigned to this name
        # Bob is assigned Bob, contact is bob_slack. Alice is assigned Alice, contact is alice_devops.
        tech_name = "Bob" if "bob" in contact_id.lower() else ("Alice" if "alice" in contact_id.lower() else "Clara")
        for t in tickets:
            if t.assigned_to and tech_name in t.assigned_to:
                return t
        
        # Fallback: check unassigned tickets matching category
        for t in tickets:
            if not t.assigned_to:
                if tech_name == "Bob" and t.category in (IncidentCategory.TEAM_OPERATIONS, IncidentCategory.COMMUNITY_INTELLIGENCE):
                    return t
                if tech_name == "Alice" and t.category == IncidentCategory.TEAM_OPERATIONS:
                    return t
        return None

    # -------------------------------------------------------------
    # 5. Incident Handlers
    # -------------------------------------------------------------

    async def _handle_customer_support(
        self,
        ticket_id: str,
        sender_name: str,
        sender_id: str,
        channel: ChannelType,
        conv_id: str,
        text: str,
    ) -> Dict[str, Any]:
        """Feature 1: Customer Rescue Engine - Processes complaints, updates memory, escalates."""
        ticket = IncidentTicket(
            id=ticket_id,
            category=IncidentCategory.CUSTOMER_SUPPORT,
            title="Pending Customer Refund Complaint",
            description=f"Customer {sender_name} complained about missing refund: '{text}'",
            reporter_name=sender_name,
            reporter_contact=f"{channel.value}_{sender_id}",
            summary="Checking transaction state...",
        )
        await create_ticket(ticket)
        await log_audit_action(ticket_id, "TICKET_LOGGED", "BLACKBOX", "Customer Support refund complaint ticket logged.")

        # Simulate database lookup for client history
        refund_eta = "24 Hours"
        reply_to_customer = f"Hello {sender_name},\n\nWe have verified our payments queue. Your refund is scheduled and currently pending processing. It is expected to clear in approximately {refund_eta}.\n\nThank you for your patience."
        
        # Outbound 1: Reply to Customer on their channel (e.g. Email)
        await caspian_service.send_message(
            channel=channel,
            recipient_id=sender_id,
            conversation_id=conv_id,
            text=reply_to_customer,
            ticket_id=ticket_id,
        )

        # Outbound 2: Post to Slack (#finance-ops / Clara)
        finance_alert = (
            f"🚨 *REFUND DISPUTE DETECTED* [{ticket_id}]\n\n"
            f"• Customer: {sender_name}\n"
            f"• Complaint: '{text}'\n"
            f"• Action taken: Auto-notified customer of tomorrow's refund queue.\n"
            f"• Recommended: Finance Lead verify transaction status."
        )
        await caspian_service.send_message(
            channel=ChannelType.SLACK,
            recipient_id="clara_ops",
            conversation_id=f"fin_{ticket_id}",
            text=finance_alert,
            ticket_id=ticket_id,
        )

        # Outbound 3: Founder Notification on Telegram
        settings = await get_settings()
        is_founder_away = settings.get("founder_disappears_mode") == "1"

        if is_founder_away:
            # Fully autonomous resolution, log audit
            await log_audit_action(ticket_id, "AUTO_RESOLVE", "BLACKBOX", "Founder Disappears mode active. Refund resolution handled fully autonomously.")
        else:
            founder_telegram_alert = (
                f"🚨 *Customer Risk Alert* [{ticket_id}]\n\n"
                f"Client {sender_name} complained about pending refund. Support email replied. Ops notified on Slack.\n"
                f"Priority: Medium."
            )
            await caspian_service.send_message(
                channel=ChannelType.TELEGRAM,
                recipient_id="founder_tg",
                conversation_id=f"fnd_{ticket_id}",
                text=founder_telegram_alert,
                ticket_id=ticket_id,
            )

        return {"status": "processed", "ticket_id": ticket_id, "action": "customer_support_rescue"}

    async def _handle_team_operations(
        self,
        ticket_id: str,
        sender_name: str,
        sender_id: str,
        channel: ChannelType,
        conv_id: str,
        text: str,
    ) -> Dict[str, Any]:
        """Feature 4: Team Operations Monitor - Dispatches tasks, notifies blockers."""
        ticket = IncidentTicket(
            id=ticket_id,
            category=IncidentCategory.TEAM_OPERATIONS,
            title="Biometric Door Scanner Blockage",
            description=f"DevOps/Facilities issue reported: '{text}'",
            reporter_name=sender_name,
            reporter_contact=f"{channel.value}_{sender_id}",
        )
        await create_ticket(ticket)
        await log_audit_action(ticket_id, "TICKET_LOGGED", "BLACKBOX", "Team Operations blocker ticket logged.")

        # Determine technician: Alice (DevOps Lead) preferred channel: Telegram
        assigned_tech = "Alice (DevOps Lead)"
        tech_contact = "alice_devops"
        tech_channel = ChannelType.TELEGRAM

        # Dispatch Task to Technician
        task_dispatch = (
            f"🚨 *URGENT INCIDENT DISPATCH* [{ticket_id}]\n\n"
            f"Hi Alice, the biometric scanner is offline. Employees are locked out.\n"
            f"Please reply with 'ACCEPT' to start, or 'RESOLVED [details]'."
        )
        await caspian_service.send_message(
            channel=tech_channel,
            recipient_id=tech_contact,
            conversation_id=f"tech_{ticket_id}",
            text=task_dispatch,
            ticket_id=ticket_id,
            buttons_list=[{"text": "Accept Task", "value": "ACCEPT"}]
        )

        # Notify reporter
        reporter_notify = f"⚠️ *Blocker Logged [INC-2026]:* We have dispatched this issue to DevOps Lead {assigned_tech} on Telegram. We will notify you once they accept/resolve the task."
        await caspian_service.send_message(
            channel=channel,
            recipient_id=sender_id,
            conversation_id=conv_id,
            text=reporter_notify,
            ticket_id=ticket_id,
        )

        return {"status": "processed", "ticket_id": ticket_id, "action": "team_operations_dispatch"}

    async def _handle_community_bug(
        self,
        ticket_id: str,
        sender_name: str,
        sender_id: str,
        channel: ChannelType,
        conv_id: str,
        text: str,
    ) -> Dict[str, Any]:
        """Feature 5: Community Intelligence - Ingests community reports, alerts dev."""
        ticket = IncidentTicket(
            id=ticket_id,
            category=IncidentCategory.COMMUNITY_INTELLIGENCE,
            title="Discord Community crash report",
            description=f"Discord community member reported: '{text}'",
            reporter_name=sender_name,
            reporter_contact=f"{channel.value}_{sender_id}",
        )
        await create_ticket(ticket)
        await log_audit_action(ticket_id, "TICKET_LOGGED", "BLACKBOX", "Discord community bug report ticket logged.")

        # Update Memory Graph with new bug linked to project_payments
        await add_graph_node(ticket_id, "Task", {"name": "Fix Payments Bug", "status": "Reported"})
        await add_graph_edge(ticket_id, "project_payments", "BLOCKS")

        # Alert developer Bob on Slack
        dev_alert = (
            f"🐛 *NEW BUG REPORTED IN COMMUNITY* [{ticket_id}]\n\n"
            f"• Source: Discord Community (Reported by {sender_name})\n"
            f"• Issue: '{text}'\n"
            f"• Linked Project: Payments System Gateway\n"
            f"• Action: Bug registered. Bob (Backend) please review."
        )
        await caspian_service.send_message(
            channel=ChannelType.SLACK,
            recipient_id="bob_slack",
            conversation_id=f"dev_{ticket_id}",
            text=dev_alert,
            ticket_id=ticket_id,
            buttons_list=[{"text": "Accept & Resolve", "value": "ACCEPT"}]
        )

        # Reply to Discord member
        discord_reply = f"Thank you for reporting this issue! I've logged it as ticket {ticket_id} and notified our core backend developer Bob on Slack. We'll update you here once resolved."
        await caspian_service.send_message(
            channel=channel,
            recipient_id=sender_id,
            conversation_id=conv_id,
            text=discord_reply,
            ticket_id=ticket_id,
        )

        return {"status": "processed", "ticket_id": ticket_id, "action": "community_bug_logged"}

    async def _handle_vendor_delay(
        self,
        ticket_id: str,
        sender_name: str,
        sender_id: str,
        channel: ChannelType,
        conv_id: str,
        text: str,
    ) -> Dict[str, Any]:
        """Feature 3: Vendor Intelligence - Monitors vendor delays, alerts operations."""
        ticket = IncidentTicket(
            id=ticket_id,
            category=IncidentCategory.VENDOR_INTELLIGENCE,
            title="DHL Shipment Delayed",
            description=f"Logistics delay reported: '{text}'",
            reporter_name=sender_name,
            reporter_contact=f"{channel.value}_{sender_id}",
        )
        await create_ticket(ticket)
        await log_audit_action(ticket_id, "TICKET_LOGGED", "BLACKBOX", "Vendor shipping delay ticket logged.")

        # Update Memory Graph: vendor_dhl is delayed, which impacts project_payments
        await add_graph_node(ticket_id, "Task", {"name": "Resolve DHL Delay", "status": "Delayed"})
        await add_graph_edge("vendor_dhl", ticket_id, "CAUSED")
        await add_graph_edge(ticket_id, "project_payments", "IMPACTS")

        # Alert operations lead Clara on Slack
        ops_alert = (
            f"📦 *VENDOR SHIPMENT DELAY ALERT* [{ticket_id}]\n\n"
            f"• Vendor: DHL Express Logistics\n"
            f"• Notice: '{text}'\n"
            f"• Impact: Project Payments System Gateway hardware delivery delayed.\n"
            f"• Action: Ops team Clara please coordinate with supplier."
        )
        await caspian_service.send_message(
            channel=ChannelType.SLACK,
            recipient_id="clara_ops",
            conversation_id=f"ops_{ticket_id}",
            text=ops_alert,
            ticket_id=ticket_id,
        )

        return {"status": "processed", "ticket_id": ticket_id, "action": "vendor_delay_logged"}

    async def _handle_lead_inactivity(
        self,
        ticket_id: str,
        sender_name: str,
        sender_id: str,
        channel: ChannelType,
        conv_id: str,
        text: str,
    ) -> Dict[str, Any]:
        """Feature 2: Lead Recovery System - Detects inactivity or coordinates meetings."""
        ticket = IncidentTicket(
            id=ticket_id,
            category=IncidentCategory.LEAD_FOLLOWUP,
            title="Tesla Account Engagement Follow-up",
            description=f"Lead interaction: '{text}'",
            reporter_name=sender_name,
            reporter_contact=f"{channel.value}_{sender_id}",
        )
        await create_ticket(ticket)
        await log_audit_action(ticket_id, "TICKET_LOGGED", "BLACKBOX", "Lead interaction ticket logged.")

        # Update memory graph
        await add_graph_node("lead_tesla", "Lead", {"name": "Tesla Corporate Procurement", "status": "Meeting Scheduled"})

        # Notify team on Slack
        sales_notification = (
            f"💼 *LEAD RESPONSE CAPTURED* [{ticket_id}]\n\n"
            f"• Lead: Tesla Corporate Procurement\n"
            f"• Reply: '{text}'\n"
            f"• Action: BLACKBOX logged interest and scheduled a meeting. CRM updated."
        )
        await caspian_service.send_message(
            channel=ChannelType.SLACK,
            recipient_id="clara_ops",
            conversation_id=f"sales_{ticket_id}",
            text=sales_notification,
            ticket_id=ticket_id,
        )

        # Confirm to client
        client_confirm = "Thank you! I have registered our meeting request for tomorrow Friday 11:00 AM. A calendar invitation has been dispatched to your email address."
        await caspian_service.send_message(
            channel=channel,
            recipient_id=sender_id,
            conversation_id=conv_id,
            text=client_confirm,
            ticket_id=ticket_id,
        )

        return {"status": "processed", "ticket_id": ticket_id, "action": "lead_recovered"}


# Global singleton instance
workflow_manager = WorkflowManager()
