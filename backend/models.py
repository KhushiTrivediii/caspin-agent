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


class RiskLevel(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class NegotiationStatus(str, Enum):
    SENT = "Sent"
    REPLIED = "Replied"
    IMPROVED_OFFER = "Improved Offer"
    DECLINED = "Declined"


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


class VendorProfile(BaseModel):
    id: str
    name: str
    contact_email: str
    phone: Optional[str] = None
    rating: float = Field(default=4.5, ge=1.0, le=5.0)
    reliability_score: float = Field(default=90.0, ge=0.0, le=100.0)
    past_performance: str = "Excellent (98% on-time fulfillment, 0% dispute rate)"
    on_time_rate: float = 98.0
    product_categories: List[str] = Field(default_factory=list)
    certifications: List[str] = Field(default_factory=list)
    market_tier: str = "Enterprise Tier-1"
    created_at: datetime = Field(default_factory=datetime.utcnow)


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


class QuotationInput(BaseModel):
    vendor_name: str
    price: float
    delivery_days: int
    warranty_years: int = 1
    vendor_rating: Optional[float] = 4.5
    reliability_score: Optional[float] = 90.0
    contact_email: Optional[str] = None
    specs_matched: List[str] = Field(default_factory=list)
    notes: Optional[str] = None


class VendorScoreResult(BaseModel):
    vendor: str
    score: int
    price_score: float
    delivery_score: float
    reliability_score: float
    warranty_score: float
    quoted_price: float
    delivery_days: int
    warranty_years: int
    rank: int = 1
    is_recommended: bool = False


class RiskAlert(BaseModel):
    vendor_name: str
    risk_level: RiskLevel
    risk_factor: str
    reason: str
    mitigation_advice: Optional[str] = None


class QuotationAnalysisResult(BaseModel):
    product: str
    quantity: int
    budget: float
    market_average_price: float
    quotes_analyzed: int
    comparison_table: List[Dict[str, Any]]
    scoring_results: List[VendorScoreResult]
    risk_alerts: List[RiskAlert]


class NegotiationThread(BaseModel):
    id: str
    procurement_id: Optional[str] = None
    vendor_name: str
    vendor_email: str
    status: NegotiationStatus = NegotiationStatus.SENT
    initial_price: float
    target_price: float
    current_price: float
    counter_offer_text: str
    vendor_reply_text: Optional[str] = None
    savings_achieved: float = 0.0
    sent_at: datetime = Field(default_factory=datetime.utcnow)
    replied_at: Optional[datetime] = None


class SupplierRecommendation(BaseModel):
    recommended_vendor: str
    recommended_price: float
    recommended_delivery_days: int
    recommended_warranty_years: int
    composite_score: int
    reasons: List[str]
    risk_summary: str
    score_breakdown: Dict[str, Any]
    savings_amount: float
    savings_percentage: float


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


# API Payload Models
class VendorSearchRequest(BaseModel):
    product: str
    quantity: int = 1
    budget: Optional[float] = None
    currency: str = "INR"
    category: Optional[str] = None


class QuoteAnalyzeRequest(BaseModel):
    product: str
    quantity: int
    budget: float
    quotes: List[QuotationInput]


class VendorScoreRequest(BaseModel):
    budget: float
    target_delivery_days: Optional[int] = 10
    quotes: List[QuotationInput]


class NegotiationRequest(BaseModel):
    procurement_id: Optional[str] = "PROC-2026-001"
    vendor_name: str
    vendor_email: Optional[str] = None
    initial_price: float
    competing_lower_price: Optional[float] = None
    target_discount_percentage: float = 6.0
    product_name: Optional[str] = "Laptop"
    quantity: Optional[int] = 100


class RecommendationRequest(BaseModel):
    product: str
    quantity: int
    budget: float
    target_delivery_days: Optional[int] = 10
    quotes: List[QuotationInput]


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
