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
    ChannelMessage,
    ProcurementTicket,
    ProcurementStatus,
)
from backend.database import (
    save_channel_message,
    get_channel_messages,
)

logger = logging.getLogger("caspian_service")
logging.basicConfig(level=logging.INFO)


class CaspianService:
    """
    Unified Multi-Channel Communication Layer using Caspian SDK.
    Bridges Telegram, Email, and Web channels with behavior prompts,
    threading, and interactive approval blocks.
    """

    def __init__(self):
        self.api_key = os.getenv("CASPIAN_API_KEY", "").strip()
        self.base_url = os.getenv("CASPIAN_BASE_URL", "https://api.trycaspianai.com")
        self.client: Optional[CommClient] = None
        self.is_live = bool(self.api_key)
        self._message_handlers = []
        self._interaction_handlers = []

        if self.is_live:
            try:
                self.client = CommClient(api_key=self.api_key, base_url=self.base_url)
                self._setup_caspian_handlers()
                logger.info("Caspian SDK CommClient initialized in LIVE mode.")
            except Exception as e:
                logger.warning(f"Failed to initialize live Caspian CommClient: {e}. Falling back to Sandbox mode.")
                self.is_live = False
        else:
            logger.info("Caspian SDK initialized in SANDBOX / SIMULATOR mode (zero-friction offline testing).")

    def _setup_caspian_handlers(self):
        """Register listeners with Caspian SDK."""
        if not self.client:
            return

        @self.client.on_message
        def handle_caspian_message(message: caspian_sdk.Message):
            # Dispatch to workflow manager
            asyncio.create_task(self.handle_raw_caspian_message(message))

        @self.client.on_interaction
        def handle_caspian_interaction(interaction: Any):
            logger.info(f"Received Caspian interaction: {interaction}")

    async def handle_raw_caspian_message(self, message: caspian_sdk.Message):
        """Translate raw Caspian inbound message into procurement workflow."""
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
            subject=message.subject,
        )

    def get_behavior_prompt(self, channel: ChannelType) -> str:
        """Fetch channel-specific etiquette and formatting prompt."""
        if channel == ChannelType.TELEGRAM:
            return (
                "You are an enterprise AI Procurement Bot on Telegram. "
                "Keep responses concise, friendly, and formatted with emojis and markdown. "
                "Use bullet points for specifications and clear call-to-actions for approvals."
            )
        elif channel == ChannelType.EMAIL:
            return (
                "You are an enterprise AI Procurement Assistant sending formal emails. "
                "Use professional corporate etiquette, structured tables, clear subject lines, "
                "and include comprehensive executive summaries for decision makers."
            )
        elif channel == ChannelType.SLACK:
            return (
                "You are an enterprise AI Procurement Bot in a Slack Workspace. "
                "Use Slack Block Kit formatting style, concise bullet points, bold key figures, "
                "and interactive approval action prompts."
            )
        elif channel == ChannelType.WHATSAPP:
            return (
                "You are an enterprise AI Procurement Assistant on WhatsApp Business. "
                "Keep messages crisp, mobile-friendly, bulleted with key amounts in INR, "
                "and provide fast single-word reply commands (e.g. APPROVE or REJECT)."
            )
        return "You are an AI Procurement Agent. Be professional, clear, and structured."

    async def send_message(
        self,
        channel: ChannelType,
        recipient_id: str,
        conversation_id: str,
        text: str,
        html: Optional[str] = None,
        subject: Optional[str] = None,
        procurement_id: Optional[str] = None,
        buttons_list: Optional[List[Dict[str, str]]] = None,
    ) -> ChannelMessage:
        """
        Send outbound message via Caspian SDK (or sandbox router) and persist to database.
        """
        msg_id = f"MSG-{uuid.uuid4().hex[:10]}"
        msg = ChannelMessage(
            id=msg_id,
            conversation_id=conversation_id,
            channel=channel.value,
            sender_id="procurement_ai_agent",
            sender_name="Procurement AI Agent",
            recipient=recipient_id,
            subject=subject,
            text=text,
            html=html,
            is_agent=True,
            procurement_id=procurement_id,
            timestamp=datetime.utcnow(),
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

        return msg


# Global singleton instance
caspian_service = CaspianService()
