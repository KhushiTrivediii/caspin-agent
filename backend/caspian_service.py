import os
import logging
import asyncio
import uuid
from typing import Optional, Dict, Any, List
from datetime import datetime

import caspian_sdk
from caspian_sdk import CommClient
from caspian_sdk.blocks import buttons, text as block_text, card, divider

from backend.models import (
    ChannelType,
    MessageLog,
    IncidentTicket,
    TicketStatus,
)
from backend.database import (
    save_channel_message,
    update_ticket_status,
    log_audit_action,
)

logger = logging.getLogger("caspian_service")


class CaspianService:
    """
    BLACKBOX AI Caspian SDK Communication Interface.
    Orchestrates unified multi-channel identity, routes notifications,
    and simulates responses in sandbox/offline mode.
    """

    def __init__(self):
        self.api_key = os.getenv("CASPIAN_API_KEY", "").strip()
        self.base_url = os.getenv("CASPIAN_BASE_URL", "https://api.trycaspianai.com")
        self.client: Optional[CommClient] = None
        self.is_live = bool(self.api_key)

        if self.is_live:
            try:
                self.client = CommClient(api_key=self.api_key, base_url=self.base_url)
                self._setup_caspian_handlers()
                logger.info("Caspian SDK CommClient initialized in LIVE mode for BLACKBOX AI.")
            except Exception as e:
                logger.warning(f"Failed to initialize live Caspian CommClient: {e}. Falling back to Sandbox mode.")
                self.is_live = False
        else:
            logger.info("Caspian SDK initialized in SANDBOX / SIMULATOR mode (zero-friction hackathon offline demo).")

    def _setup_caspian_handlers(self):
        """Register listeners with Caspian SDK in live mode."""
        if not self.client:
            return

        @self.client.on_message
        def handle_caspian_message(message: caspian_sdk.Message):
            asyncio.create_task(self.handle_raw_caspian_message(message))

        @self.client.on_interaction
        def handle_caspian_interaction(interaction: Any):
            logger.info(f"Received Caspian interaction: {interaction}")
            asyncio.create_task(self.handle_raw_caspian_interaction(interaction))

    async def handle_raw_caspian_message(self, message: caspian_sdk.Message):
        """Process inbound live message from Caspian SDK."""
        channel_name = message.channel.lower() if message.channel else "telegram"
        sender_id = message.sender.get("id", "unknown") if isinstance(message.sender, dict) else str(message.sender)
        sender_name = message.sender.get("name", "User") if isinstance(message.sender, dict) else "User"
        sender_email = message.sender.get("email") if isinstance(message.sender, dict) else None

        from backend.workflow_manager import workflow_manager
        await workflow_manager.handle_inbound_message(
            channel=ChannelType(channel_name) if channel_name in [c.value for c in ChannelType] else ChannelType.TELEGRAM,
            sender_id=sender_id,
            sender_name=sender_name,
            sender_email=sender_email,
            conversation_id=message.conversation_id or f"{channel_name}_{sender_id}",
            text=message.text or "",
        )

    async def handle_raw_caspian_interaction(self, interaction: Any):
        """Process live interaction triggers from interactive blocks (buttons, etc.)."""
        # Parse interaction details and route to approval/resolution
        logger.info(f"Interaction details: {interaction}")
        # Extract callback payload or button values
        sender_id = interaction.user.get("id", "unknown") if hasattr(interaction, "user") else "unknown"
        sender_name = interaction.user.get("name", "User") if hasattr(interaction, "user") else "User"
        callback_value = interaction.value if hasattr(interaction, "value") else ""
        conversation_id = interaction.conversation_id if hasattr(interaction, "conversation_id") else ""

        from backend.workflow_manager import workflow_manager
        await workflow_manager.handle_inbound_message(
            channel=ChannelType.TELEGRAM, # Fallback
            sender_id=sender_id,
            sender_name=sender_name,
            conversation_id=conversation_id,
            text=callback_value,
        )

    async def send_message(
        self,
        channel: ChannelType,
        recipient_id: str,
        conversation_id: str,
        text: str,
        html: Optional[str] = None,
        subject: Optional[str] = None,
        ticket_id: Optional[str] = None,
        buttons_list: Optional[List[Dict[str, str]]] = None,
    ) -> MessageLog:
        """
        Send outbound message via Caspian SDK (or sandbox router) and persist to database.
        """
        msg_id = f"MSG-{uuid.uuid4().hex[:10]}"
        msg = MessageLog(
            id=msg_id,
            channel=channel.value,
            direction="outbound",
            sender="blackbox_ai",
            recipient=recipient_id,
            text=text,
            timestamp=datetime.utcnow(),
            ticket_id=ticket_id,
        )

        # Save to database
        await save_channel_message(msg)

        # If live Caspian SDK client is active, send via CommClient
        if self.is_live and self.client:
            try:
                blocks_payload = None
                if buttons_list:
                    btn_elements = [{"text": b["text"], "value": b.get("value", b["text"])} for b in buttons_list]
                    blocks_payload = [buttons(btn_elements)]

                self.client.send_message(
                    recipient=recipient_id,
                    text=text,
                    html=html,
                    blocks=blocks_payload,
                    channel=channel.value,
                )
                logger.info(f"Live Caspian message dispatched to {recipient_id} on {channel.value}")
            except Exception as e:
                logger.warning(f"Error sending live Caspian message: {e}")

        # Real-time dashboard broadcast
        from backend.realtime import realtime_manager
        await realtime_manager.emit_ticket_update(ticket_id or "SYSTEM", "outbound", {
            "channel": channel.value,
            "recipient": recipient_id,
            "text": text,
            "timestamp": msg.timestamp.isoformat(),
        })

        # Trigger Sandbox/Simulation Loop if in Offline mode
        if not self.is_live:
            # We delay the simulation trigger slightly to let dashboard render naturally
            asyncio.create_task(self._run_sandbox_simulation(channel, recipient_id, conversation_id, text, ticket_id))

        return msg

    async def _run_sandbox_simulation(
        self,
        channel: ChannelType,
        recipient_id: str,
        conversation_id: str,
        text: str,
        ticket_id: Optional[str],
    ):
        """Simulate autonomous response behaviors from team, vendors, and clients in Sandbox mode."""
        await asyncio.sleep(2.0)
        from backend.workflow_manager import workflow_manager

        # Check if the dispatched message was a request for a team member (technician task)
        # e.g., "Hi Bob, DevOps blocker reported on Payments System Gateway..."
        if "bob_slack" in recipient_id and "blocker" in text.lower():
            # Bob accepts the task
            await workflow_manager.handle_inbound_message(
                channel=ChannelType.SLACK,
                sender_id="dev_bob",
                sender_name="Bob (Backend)",
                conversation_id=conversation_id,
                text="ACCEPT",
            )
            # Bob resolves it after another 4 seconds
            await asyncio.sleep(4.0)
            await workflow_manager.handle_inbound_message(
                channel=ChannelType.SLACK,
                sender_id="dev_bob",
                sender_name="Bob (Backend)",
                conversation_id=conversation_id,
                text="RESOLVED - Added memory indexing, connection leaks plugged and database restarted.",
            )

        # Check if the dispatched message was a request for Alice
        elif "alice_devops" in recipient_id and "biometric" in text.lower():
            # Alice accepts
            await workflow_manager.handle_inbound_message(
                channel=ChannelType.TELEGRAM,
                sender_id="dev_alice",
                sender_name="Alice (DevOps Lead)",
                conversation_id=conversation_id,
                text="ACCEPT",
            )
            # Alice resolves
            await asyncio.sleep(4.0)
            await workflow_manager.handle_inbound_message(
                channel=ChannelType.TELEGRAM,
                sender_id="dev_alice",
                sender_name="Alice (DevOps Lead)",
                conversation_id=conversation_id,
                text="RESOLVED - Replaced biometric gateway power adapter, lock functioning normally.",
            )

        # Check if follow-up sent to Lead (e.g. SpaceX or Tesla)
        elif "spacex" in recipient_id or "tesla" in recipient_id:
            # Lead responds warm
            await workflow_manager.handle_inbound_message(
                channel=ChannelType.EMAIL,
                sender_id=recipient_id,
                sender_name="Tesla Procurement Desk",
                conversation_id=conversation_id,
                text="Hello BLACKBOX. Apologies for the radio silence, we were reviewing the specs. Let's schedule an intro meeting for tomorrow Friday 11:00 AM.",
            )

        # Check if vendor shipping delay alert sent
        elif "whatsapp" in channel.value and "delay" in text.lower() and "dhl" in recipient_id:
            # DHL responds
            await workflow_manager.handle_inbound_message(
                channel=ChannelType.WHATSAPP,
                sender_id="vendor_dhl",
                sender_name="DHL Delivery Desk",
                conversation_id=conversation_id,
                text="Apologies for the shipping delay. Our truck was caught in severe weather outside Bangalore. The new shipment arrival ETA is tomorrow at 10:00 AM.",
            )


# Global singleton instance
caspian_service = CaspianService()
