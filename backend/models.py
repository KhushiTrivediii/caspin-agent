from datetime import datetime
from enum import Enum
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class ChannelType(str, Enum):
    TELEGRAM = "telegram"
    EMAIL = "email"
    SLACK = "slack"
    WHATSAPP = "whatsapp"
    DISCORD = "discord"
    WEB = "web"


class TicketStatus(str, Enum):
    OPEN = "Open"
    ESCALATED = "Escalated"
    RESOLVED = "Resolved"


class IncidentCategory(str, Enum):
    CUSTOMER_SUPPORT = "Customer Support"
    LEAD_FOLLOWUP = "Lead Follow-up"
    VENDOR_INTELLIGENCE = "Vendor Intelligence"
    TEAM_OPERATIONS = "Team Operations"
    COMMUNITY_INTELLIGENCE = "Community Intelligence"


class IncidentTicket(BaseModel):
    id: str
    category: IncidentCategory
    title: str
    description: str
    status: TicketStatus = TicketStatus.OPEN
    reporter_name: str
    reporter_contact: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    assigned_to: Optional[str] = None
    summary: Optional[str] = None


class MemoryNode(BaseModel):
    id: str
    label: str  # Customer, Vendor, Developer, Project, Task, Lead
    properties: Dict[str, Any] = Field(default_factory=dict)


class MemoryEdge(BaseModel):
    source: str
    target: str
    type: str  # e.g., ASSIGNED_TO, DEPENDS_ON, REPORTED_BY, PARTNERED_WITH


class MessageLog(BaseModel):
    id: str
    channel: str
    direction: str  # inbound, outbound
    sender: str
    recipient: str
    text: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    ticket_id: Optional[str] = None


class SimulationRequest(BaseModel):
    type: str  # 'support', 'blocker', 'bug', 'delay', 'briefing'


class BriefingPayload(BaseModel):
    opportunities: int
    risks: int
    issues: int
    delays: int
    meetings: int


class SettingsUpdate(BaseModel):
    founder_disappears_mode: bool
