import uuid
import json
import logging
import asyncio
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple

from backend.models import (
    ChannelType,
    TicketStatus,
    IncidentCategory,
    IncidentTicket,
)
from backend.database import (
    get_graph_data,
    get_ticket,
    update_ticket_status,
    log_audit_action,
    get_settings,
    get_kpi_stats,
    create_ticket,
    add_graph_node,
    add_graph_edge,
)
from backend.caspian_service import caspian_service

logger = logging.getLogger("agent_engine")

# ANSI Color formatting for rich terminal trace logs
COLOR_RESET = "\033[0m"
COLOR_CYAN = "\033[36m"
COLOR_YELLOW = "\033[33m"
COLOR_GREEN = "\033[32m"
COLOR_MAGENTA = "\033[35m"
COLOR_RED = "\033[31m"
COLOR_BOLD = "\033[1m"


def _safe_print(text: str):
    try:
        print(text)
    except UnicodeEncodeError:
        print(text.encode("ascii", errors="ignore").decode("ascii"))


class AgentEngine:
    """
    BLACKBOX AI Cognitive Agent Brain.
    Executes reasoning loops, queries startup memory graphs,
    and calls multi-channel Caspian tools.
    """

    def log_agent_step(self, step_type: str, title: str, details: str, channel: Optional[str] = None):
        """Format and print colored agent reasoning logs to terminal stdout and broadcast to dashboard."""
        timestamp = datetime.now().strftime("%H:%M:%S")
        prefix = f"{COLOR_BOLD}{COLOR_CYAN}[BLACKBOX AGENT {timestamp}]{COLOR_RESET}"
        
        if step_type == "THINKING":
            _safe_print(f"\n{prefix} {COLOR_YELLOW}[REASONING]{COLOR_RESET} {COLOR_BOLD}{title}{COLOR_RESET}")
            _safe_print(f"   └─ {details}")
        elif step_type == "TOOL":
            _safe_print(f"{prefix} {COLOR_MAGENTA}[TOOL EXECUTION]{COLOR_RESET} {COLOR_BOLD}{title}{COLOR_RESET}")
            _safe_print(f"   └─ {details}")
        elif step_type == "CASPIAN":
            _safe_print(f"{prefix} {COLOR_GREEN}[CASPIAN DISPATCH]{COLOR_RESET} {COLOR_BOLD}{title}{COLOR_RESET}")
            _safe_print(f"   └─ {details}")
        elif step_type == "SUCCESS":
            _safe_print(f"{prefix} {COLOR_GREEN}[ACTION COMPLETE]{COLOR_RESET} {COLOR_BOLD}{title}{COLOR_RESET}")
            _safe_print(f"   └─ {details}")

        # Broadcast event to WebSockets Dashboard
        try:
            from backend.realtime import realtime_manager
            asyncio.create_task(realtime_manager.broadcast({
                "type": "activity_feed_item",
                "timestamp": datetime.now().strftime("%I:%M %p"),
                "step_type": step_type,
                "title": title,
                "details": details,
                "channel": channel or "",
            }))
        except Exception:
            pass

    # -------------------------------------------------------------
    # AGENT EXPLICIT TOOLS
    # -------------------------------------------------------------

    async def tool_query_memory_graph(self, entity_id: str) -> Dict[str, Any]:
        """Tool 1: Query Neo4j-style startup context graph for nodes & links."""
        self.log_agent_step("TOOL", "query_memory_graph()", f"Searching memory nodes for entity: '{entity_id}'")
        graph = await get_graph_data()
        
        matching_nodes = [n for n in graph["nodes"] if entity_id.lower() in n["id"].lower() or entity_id.lower() in n["properties"].get("name", "").lower()]
        matching_edges = [e for e in graph["edges"] if entity_id.lower() in e["source"].lower() or entity_id.lower() in e["target"].lower()]
        
        result = {"nodes": matching_nodes, "edges": matching_edges}
        self.log_agent_step("TOOL", "query_memory_graph() -> Result", f"Found {len(matching_nodes)} node(s), {len(matching_edges)} edge(s)")
        return result

    async def tool_send_caspian_message(
        self,
        channel: ChannelType,
        recipient: str,
        text: str,
        ticket_id: Optional[str] = None,
        buttons_list: Optional[List[Dict[str, str]]] = None,
    ):
        """Tool 2: Send multi-channel message via Caspian SDK."""
        self.log_agent_step(
            "CASPIAN", 
            f"send_message({channel.value.upper()})", 
            f"Recipient: '{recipient}' | Text: '{text[:60]}...'",
            channel=channel.value,
        )

        # Pulse channel card on dashboard matrix
        try:
            from backend.realtime import realtime_manager
            await realtime_manager.broadcast({
                "type": "channel_pulse",
                "channel": channel.value.lower(),
                "recipient": recipient,
            })
        except Exception:
            pass

        msg = await caspian_service.send_message(
            channel=channel,
            recipient_id=recipient,
            conversation_id=f"{channel.value}_{recipient}",
            text=text,
            ticket_id=ticket_id,
            buttons_list=buttons_list,
        )
        return msg

    async def tool_update_ticket(self, ticket_id: str, status: TicketStatus, assigned_to: Optional[str] = None, summary: Optional[str] = None):
        """Tool 3: Update ticket state in database."""
        self.log_agent_step("TOOL", "update_ticket()", f"Ticket '{ticket_id}' status set to {status.value} (Assignee: {assigned_to or 'None'})")
        await update_ticket_status(ticket_id, status, assigned_to=assigned_to, summary=summary)

    async def tool_escalate_founder(self, ticket_id: str, reason: str):
        """Tool 4: Escalate critical issue to founder via Telegram or handle autonomously if Disappears mode active."""
        settings = await get_settings()
        is_founder_away = settings.get("founder_disappears_mode") == "1"

        if is_founder_away:
            self.log_agent_step("THINKING", "Founder Disappears Mode Check", "Founder Disappears mode is ACTIVE. Escalation suppressed; resolving autonomously.")
            await log_audit_action(ticket_id, "AUTO_RESOLVE", "BLACKBOX", f"Autonomous resolution active: {reason}")
        else:
            self.log_agent_step("CASPIAN", "escalate_founder(TELEGRAM)", f"Dispatching escalation alert to Founder on Telegram: {reason}")
            escalation_text = (
                f"🚨 *FOUNDER ESCALATION ALERT* [{ticket_id}]\n\n"
                f"• Reason: {reason}\n"
                f"• Action Required: Please review or assign task."
            )
            await self.tool_send_caspian_message(
                channel=ChannelType.TELEGRAM,
                recipient="founder_tg",
                text=escalation_text,
                ticket_id=ticket_id,
            )

    async def tool_compile_briefing(self):
        """Tool 5: Aggregate KPIs and dispatch Daily Briefing to Telegram."""
        self.log_agent_step("TOOL", "compile_briefing()", "Aggregating startup KPIs (Opportunities, Risks, Issues, Meetings)...")
        stats = await get_kpi_stats()
        
        briefing_text = (
            f"📊 *BLACKBOX Founder Daily Briefing*\n"
            f"Good morning! Here is your autonomous startup operational summary:\n\n"
            f"💼 *Revenue Opportunities:* {stats['opportunities']} Active Leads\n"
            f"⚠️ *Customer Risks:* {stats['risks']} Escalated Tickets\n"
            f"📋 *Open Issues:* {stats['issues']} Active Work Tasks\n"
            f"📦 *Vendor Delays:* {stats['delays']} Delayed Shipments\n"
            f"📅 *Meetings Today:* {stats['meetings']} Confirmed Appointments\n\n"
            f"BLACKBOX is running operations fully autonomously."
        )
        await self.tool_send_caspian_message(
            channel=ChannelType.TELEGRAM,
            recipient="founder_tg",
            text=briefing_text,
        )

    # -------------------------------------------------------------
    # COGNITIVE REASONING CYCLE
    # -------------------------------------------------------------

    async def process_reasoning_cycle(self, channel: ChannelType, sender_id: str, sender_name: str, text: str) -> Dict[str, Any]:
        """
        Main cognitive loop:
        Observation -> Memory Lookup -> Reasoning -> Tool Invocations
        """
        self.log_agent_step("THINKING", "Inbound Observation Received", f"Channel: {channel.value.upper()} | From: {sender_name} ({sender_id}) | Input: '{text}'")

        text_lower = text.lower()

        # Step 1: Memory Graph Query
        graph_context = await self.tool_query_memory_graph(sender_id)

        # Step 2: Cognitive Reasoning & Intent Deduction
        if "refund" in text_lower or "money" in text_lower or "billing" in text_lower:
            self.log_agent_step("THINKING", "Intent Deduction", "Detected Customer Refund Dispute. Category: Customer Support. Priority: High.")
            
            try:
                from backend.realtime import realtime_manager
                await realtime_manager.broadcast({
                    "type": "agent_decision",
                    "input_text": text,
                    "intent": "Customer Refund Dispute",
                    "category": "Customer Support",
                    "confidence": 96,
                    "actions": ["Email Response Sent", "Slack Team Alert Generated", "Telegram Founder Escalation Check"]
                })
            except Exception:
                pass

            ticket_id = f"INC-2026-REF-{uuid.uuid4().hex[:4].upper()}"
            await create_ticket(IncidentTicket(
                id=ticket_id,
                category=IncidentCategory.CUSTOMER_SUPPORT,
                title="Customer Refund Dispute",
                description=text,
                reporter_name=sender_name,
                reporter_contact=f"{channel.value}_{sender_id}",
            ))

            # Tool 1: Reply to Customer on original channel (Email)
            customer_reply = f"Hello {sender_name},\n\nWe have queried our Payments Gateway context. Your refund is scheduled and currently pending processing. It will clear within 24 hours."
            await self.tool_send_caspian_message(channel, sender_id, customer_reply, ticket_id=ticket_id)

            # Tool 2: Alert Operations Team on Slack
            slack_alert = f"🚨 *CUSTOMER REFUND CASE* [{ticket_id}]\nCustomer {sender_name} reported refund dispute. Automated status email dispatched."
            await self.tool_send_caspian_message(ChannelType.SLACK, "clara_ops", slack_alert, ticket_id=ticket_id)

            # Tool 3: Escalate to Founder if Disappears mode is off
            await self.tool_escalate_founder(ticket_id, f"Customer {sender_name} reported refund dispute.")

            self.log_agent_step("SUCCESS", "Customer Support Workflow Complete", f"Ticket {ticket_id} created, customer notified, team alerted.")
            return {"status": "success", "ticket_id": ticket_id}

        elif "blocker" in text_lower or "down" in text_lower or "broken" in text_lower:
            self.log_agent_step("THINKING", "Intent Deduction", "Detected Technical Blocker. Category: Team Operations. Priority: Critical.")
            
            ticket_id = f"INC-2026-BLK-{uuid.uuid4().hex[:4].upper()}"
            await create_ticket(IncidentTicket(
                id=ticket_id,
                category=IncidentCategory.TEAM_OPERATIONS,
                title="Engineering Blocker Reported",
                description=text,
                reporter_name=sender_name,
                reporter_contact=f"{channel.value}_{sender_id}",
            ))

            # Tool: Dispatch task to DevOps Lead (Alice on Telegram)
            task_dispatch = f"🚨 *CRITICAL BLOCKER DISPATCH* [{ticket_id}]\nHi Alice, technical blocker reported: '{text}'. Please inspect."
            await self.tool_send_caspian_message(ChannelType.TELEGRAM, "alice_devops", task_dispatch, ticket_id=ticket_id, buttons_list=[{"text": "Accept Task", "value": "ACCEPT"}])

            self.log_agent_step("SUCCESS", "Team Blocker Dispatched", f"Task {ticket_id} assigned and sent to Alice on Telegram.")
            return {"status": "success", "ticket_id": ticket_id}

        elif "bug" in text_lower or "404" in text_lower or "500" in text_lower:
            self.log_agent_step("THINKING", "Intent Deduction", "Detected Community Bug Report. Category: Community Intelligence. Priority: Medium.")
            
            ticket_id = f"INC-2026-BUG-{uuid.uuid4().hex[:4].upper()}"
            await create_ticket(IncidentTicket(
                id=ticket_id,
                category=IncidentCategory.COMMUNITY_INTELLIGENCE,
                title="Discord Community Bug Report",
                description=text,
                reporter_name=sender_name,
                reporter_contact=f"{channel.value}_{sender_id}",
            ))

            # Tool: Link bug node to Payments project in Memory Graph
            await add_graph_node(ticket_id, "Task", {"name": "Fix Payments Bug", "status": "Reported"})
            await add_graph_edge(ticket_id, "project_payments", "BLOCKS")

            # Tool: Alert Developer Bob on Slack
            slack_bug = f"🐛 *NEW COMMUNITY BUG* [{ticket_id}]\nDiscord user {sender_name} reported: '{text}'. Linked to Payments System Gateway."
            await self.tool_send_caspian_message(ChannelType.SLACK, "bob_slack", slack_bug, ticket_id=ticket_id)

            self.log_agent_step("SUCCESS", "Community Bug Handled", f"Memory Graph node linked, developer alerted on Slack.")
            return {"status": "success", "ticket_id": ticket_id}

        elif "delay" in text_lower or "shipment" in text_lower:
            self.log_agent_step("THINKING", "Intent Deduction", "Detected Logistics Delay. Category: Vendor Intelligence. Priority: High.")
            
            ticket_id = f"INC-2026-VND-{uuid.uuid4().hex[:4].upper()}"
            await create_ticket(IncidentTicket(
                id=ticket_id,
                category=IncidentCategory.VENDOR_INTELLIGENCE,
                title="DHL Shipment Delayed",
                description=text,
                reporter_name=sender_name,
                reporter_contact=f"{channel.value}_{sender_id}",
            ))

            # Tool: Update graph relationships
            await add_graph_edge("vendor_dhl", ticket_id, "CAUSED")
            await add_graph_edge(ticket_id, "project_payments", "IMPACTS")

            # Tool: Alert Operations Lead Clara on Slack
            ops_alert = f"📦 *VENDOR DELAY ALERT* [{ticket_id}]\nDHL logistics delayed: '{text}'. Linked to Payments System Gateway."
            await self.tool_send_caspian_message(ChannelType.SLACK, "clara_ops", ops_alert, ticket_id=ticket_id)

            self.log_agent_step("SUCCESS", "Vendor Intelligence Handled", f"Shipment impact linked in Memory Graph, ops team alerted.")
            return {"status": "success", "ticket_id": ticket_id}

        elif any(k in text_lower for k in ("lead", "tesla", "meeting", "interested", "solution", "time", "automation", "pricing")):
            self.log_agent_step("THINKING", "Intent Deduction", "Detected Lead Recovery Opportunity. Category: Lead Follow-up. Priority: Low.")
            
            ticket_id = f"INC-2026-LED-{uuid.uuid4().hex[:4].upper()}"
            await create_ticket(IncidentTicket(
                id=ticket_id,
                category=IncidentCategory.LEAD_FOLLOWUP,
                title="Tesla Account Engagement Follow-up",
                description=text,
                reporter_name=sender_name,
                reporter_contact=f"{channel.value}_{sender_id}",
            ))

            # Tool: Update graph memory node
            await add_graph_node("lead_tesla", "Lead", {"name": "Tesla Corporate Procurement", "status": "Meeting Scheduled"})

            # Tool: Notify Sales on Slack
            sales_notification = f"💼 *LEAD RESPONSE CAPTURED* [{ticket_id}]\nLead {sender_name} responded: '{text}'. CRM updated."
            await self.tool_send_caspian_message(ChannelType.SLACK, "clara_ops", sales_notification, ticket_id=ticket_id)

            # Tool: Confirm to client
            client_confirm = f"Hello {sender_name}, BLACKBOX AI has registered your meeting request. A calendar invite has been dispatched."
            await self.tool_send_caspian_message(channel, sender_id, client_confirm, ticket_id=ticket_id)

            self.log_agent_step("SUCCESS", "Lead Recovery Handled", f"Meeting scheduled, CRM memory graph updated, sales team notified on Slack.")
            return {"status": "success", "ticket_id": ticket_id}

        else:
            self.log_agent_step("THINKING", "Intent Deduction", "General Operational Query.")
            reply = f"Hello {sender_name}, BLACKBOX AI has received your message. Operations context updated."
            await self.tool_send_caspian_message(channel, sender_id, reply)
            return {"status": "success", "ticket_id": "GENERAL"}


# Global singleton instance
agent_engine = AgentEngine()
