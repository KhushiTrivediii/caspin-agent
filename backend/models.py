from enum import Enum
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime


class ProcurementStatus(str, Enum):
    OPEN = "Open"
    VENDOR_SEARCH = "Vendor Search"
    NEGOTIATION = "Negotiation"
    APPROVAL_PENDING = "Approval Pending"
    APPROVED = "Approved"
    REJECTED = "Rejected"
    COMPLETED = "Completed"
    CANCELLED = "Cancelled"


class ChannelType(str, Enum):
    TELEGRAM = "telegram"
    EMAIL = "email"
    WEB = "web"
    SLACK = "slack"


class ProcurementRequirement(BaseModel):
    product: Optional[str] = Field(None, description="Name or category of the product to procure")
    quantity: Optional[int] = Field(None, description="Required quantity")
    budget: Optional[float] = Field(None, description="Total budget in currency amount")
    currency: str = Field("INR", description="Currency (e.g., INR, USD, EUR)")
    delivery_days: Optional[int] = Field(None, description="Required delivery timeline in days")
    specifications: List[str] = Field(default_factory=list, description="List of technical or functional specifications")
    requester_id: Optional[str] = None
    requester_name: Optional[str] = None
    requester_email: Optional[str] = None
    channel: ChannelType = ChannelType.TELEGRAM
    raw_prompt: Optional[str] = None


class ExtractionResult(BaseModel):
    is_complete: bool
    requirement: ProcurementRequirement
    missing_fields: List[str] = Field(default_factory=list)
    follow_up_question: Optional[str] = None
    confidence: float = 1.0


class VendorQuote(BaseModel):
    id: str
    procurement_id: str
    vendor_name: str
    price: float
    currency: str = "INR"
    delivery_days: int
    specs_matched: List[str] = Field(default_factory=list)
    rating: float = 4.5
    warranty_years: int = 3
    savings_amount: float = 0.0
    savings_percentage: float = 0.0
    is_recommended: bool = False
    quote_notes: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)


class ApprovalDecision(BaseModel):
    status: str  # "APPROVED" or "REJECTED"
    approver: str
    channel: str
    notes: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class AuditLog(BaseModel):
    id: Optional[int] = None
    procurement_id: str
    stage: str
    action: str
    actor: str
    details: Dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class ProcurementTicket(BaseModel):
    id: str
    title: str
    product: str
    quantity: int
    budget: float
    currency: str = "INR"
    delivery_days: int
    specifications: List[str] = Field(default_factory=list)
    status: ProcurementStatus = ProcurementStatus.OPEN
    current_stage: str = "Requirement Gathering"
    requester_id: Optional[str] = None
    requester_name: Optional[str] = None
    requester_email: Optional[str] = None
    channel: ChannelType = ChannelType.TELEGRAM
    recommended_vendor: Optional[str] = None
    recommended_price: Optional[float] = None
    recommended_delivery_days: Optional[int] = None
    quotes: List[VendorQuote] = Field(default_factory=list)
    approval: Optional[ApprovalDecision] = None
    summary: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class ChannelMessage(BaseModel):
    id: str
    conversation_id: str
    channel: str
    sender_id: str
    sender_name: Optional[str] = None
    recipient: Optional[str] = None
    subject: Optional[str] = None
    text: str
    html: Optional[str] = None
    is_agent: bool = False
    procurement_id: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class CreateProcurementRequest(BaseModel):
    product: str
    quantity: int
    budget: float
    currency: str = "INR"
    delivery_days: int
    specifications: List[str] = Field(default_factory=list)
    requester_name: Optional[str] = "Employee"
    requester_email: Optional[str] = "employee@enterprise.internal"
    channel: ChannelType = ChannelType.WEB


class ApprovalActionRequest(BaseModel):
    approver: Optional[str] = "Manager"
    channel: Optional[str] = "telegram"
    notes: Optional[str] = None


class SimulateMessageRequest(BaseModel):
    channel: ChannelType = ChannelType.TELEGRAM
    sender_id: str = "user_101"
    sender_name: str = "Employee User"
    sender_email: Optional[str] = "user@enterprise.internal"
    conversation_id: Optional[str] = None
    subject: Optional[str] = None
    text: str


class AdvanceStageRequest(BaseModel):
    stage: str
