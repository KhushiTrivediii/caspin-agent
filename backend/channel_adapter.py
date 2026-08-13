import logging
import uuid
from typing import Dict, Any, Optional
from pydantic import BaseModel
from backend.models import ChannelType
from backend.workflow_manager import workflow_manager

logger = logging.getLogger("channel_adapter")

class NormalizedMessage(BaseModel):
    """
    Standard schema for any incoming message, independent of the channel source.
    """
    channel: ChannelType
    sender_id: str
    sender_name: str
    sender_email: Optional[str] = None
    conversation_id: str
    text: str
    subject: Optional[str] = None

class UnifiedChannelAdapter:
    """
    Unified Multi-Channel Adapter. Enforces a SINGLE handler interface to process
    inbound messages from Telegram, Email, Slack, WhatsApp, and Web Simulator.
    """

    async def handle_channel_message(self, channel: ChannelType, raw_payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        The SINGLE entrypoint and handler for all incoming communication channels.
        Normalizes channel-specific payloads into a NormalizedMessage and dispatches
        to the workflow manager.
        """
        logger.info(f"[Unified Handler] Processing message from channel: {channel.value}")
        
        # Normalize based on source channel format
        normalized = self._normalize(channel, raw_payload)
        
        logger.info(
            f"[Unified Handler] Normalized: sender_id={normalized.sender_id}, "
            f"conv_id={normalized.conversation_id}, text='{normalized.text[:30]}'"
        )

        # Dispatch standard message to the core workflow manager
        result = await workflow_manager.handle_inbound_message(
            channel=normalized.channel,
            sender_id=normalized.sender_id,
            sender_name=normalized.sender_name,
            sender_email=normalized.sender_email,
            conversation_id=normalized.conversation_id,
            text=normalized.text,
            subject=normalized.subject
        )
        return result

    def _normalize(self, channel: ChannelType, raw: Dict[str, Any]) -> NormalizedMessage:
        """
        Map diverse incoming schemas to the single standard NormalizedMessage.
        """
        if channel == ChannelType.TELEGRAM:
            # Telegram format: { "update_id": 123, "message": { "chat": { "id": 999 }, "from": { "id": 11, "first_name": "John" }, "text": "Hello" } }
            message = raw.get("message", {})
            chat = message.get("chat", {})
            sender = message.get("from", {})
            sender_id = str(sender.get("id", "telegram_user"))
            sender_name = sender.get("first_name", "Telegram User")
            chat_id = str(chat.get("id", sender_id))
            text = message.get("text", "")
            return NormalizedMessage(
                channel=channel,
                sender_id=sender_id,
                sender_name=sender_name,
                conversation_id=f"telegram_{chat_id}",
                text=text
            )

        elif channel == ChannelType.EMAIL:
            # Email webhook format: { "from_email": "user@domain.com", "from_name": "Jane", "subject": "Procure Laptop", "body_plain": "..." }
            sender_email = raw.get("from_email", "user@enterprise.internal")
            sender_name = raw.get("from_name", "Email Requester")
            sender_id = sender_email.replace("@", "_").replace(".", "_")
            subject = raw.get("subject", "Procurement Inquiry")
            text = raw.get("body_plain", "")
            # Thread emails by email address or subject
            conversation_id = f"email_{sender_id}"
            return NormalizedMessage(
                channel=channel,
                sender_id=sender_id,
                sender_name=sender_name,
                sender_email=sender_email,
                conversation_id=conversation_id,
                text=text,
                subject=subject
            )

        elif channel == ChannelType.SLACK:
            # Slack event format: { "event": { "user": "U12345", "text": "Approve", "channel": "C999" } }
            event = raw.get("event", {})
            sender_id = event.get("user", "slack_user")
            sender_name = raw.get("user_name", "Slack User")
            channel_id = event.get("channel", "C_general")
            text = event.get("text", "")
            return NormalizedMessage(
                channel=channel,
                sender_id=sender_id,
                sender_name=sender_name,
                conversation_id=f"slack_{channel_id}",
                text=text
            )

        elif channel == ChannelType.WHATSAPP:
            # WhatsApp format: { "message": { "from": "1234567890", "text": { "body": "Approve" } } }
            message = raw.get("message", {})
            sender_id = message.get("from", "whatsapp_user")
            sender_name = raw.get("profile_name", "WhatsApp User")
            text = message.get("text", {}).get("body", "")
            return NormalizedMessage(
                channel=channel,
                sender_id=sender_id,
                sender_name=sender_name,
                conversation_id=f"whatsapp_{sender_id}",
                text=text
            )

        else:
            # Fallback/Web format
            sender_id = raw.get("sender_id", "web_user")
            sender_name = raw.get("sender_name", "Web User")
            sender_email = raw.get("sender_email")
            conversation_id = raw.get("conversation_id") or f"web_{sender_id}"
            text = raw.get("text", "")
            subject = raw.get("subject")
            return NormalizedMessage(
                channel=channel,
                sender_id=sender_id,
                sender_name=sender_name,
                sender_email=sender_email,
                conversation_id=conversation_id,
                text=text,
                subject=subject
            )

# Global singleton adapter
channel_adapter = UnifiedChannelAdapter()
