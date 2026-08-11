"""
Data models for Caspian AI Procurement Agent & Enterprise Vendor Intelligence Engine.
"""

from datetime import datetime
from enum import Enum
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class ChannelType(str, Enum):
    TELEGRAM = "telegram"
    EMAIL = "email"
    SLACK = "slack"
    WHATSAPP = "whatsapp"
    WEB = "web"


class ProcurementStatus(str, Enum):
    OPEN = "Open"
    VENDOR_SEARCH = "Vendor Search"
    NEGOTIATION = "Negotiation"
    APPROVAL_PENDING = "Approval Pending"
    APPROVED = "Approved"
    REJECTED = "Rejected"
    COMPLETED = "Completed"


class ApprovalTier(str, Enum):
    TIER_1_LEAD = "Tier 1 (Team Lead)"
    TIER_2_MANAGER = "Tier 2 (Department Manager)"
    TIER_3_EXECUTIVE = "Tier 3 (VP / CFO)"


class RiskLevel(str, Enum):
    LOW = "Low"
    MEDIUM = "Medium"
    HIGH = "High"


class NegotiationStatus(str, Enum):
    SENT = "Sent"
    REPLIED = "Replied"
    IMPROVED_OFFER = "Improved Offer"
    CONCLUDED = "Concluded"


# ---------------------------------------------------------------------------
# Core Procurement Models
# ---------------------------------------------------------------------------

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
    details: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)


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


class ProcurementRequirement(BaseModel):
    product: Optional[str] = None
    quantity: Optional[int] = None
    budget: Optional[float] = None
    currency: str = "INR"
    delivery_days: Optional[int] = None
    specifications: List[str] = Field(default_factory=list)


class ExtractionResult(BaseModel):
    requirement: ProcurementRequirement
    missing_fields: List[str] = Field(default_factory=list)
    is_complete: bool = False
    follow_up_question: Optional[str] = None


class VendorQuote(BaseModel):
    id: str
    vendor_name: str
    price: float
    currency: str = "INR"
    delivery_days: int
    warranty_years: int
    rating: float = 4.5
    reliability_score: float = 90.0
    specs_matched: List[str] = Field(default_factory=list)
    is_recommended: bool = False
    savings_amount: float = 0.0
    savings_percentage: float = 0.0
    quote_notes: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)


class ProcurementTicket(BaseModel):
    id: str
    channel: ChannelType = ChannelType.TELEGRAM
    requester_id: Optional[str] = None
    requester_name: Optional[str] = None
    requester_email: Optional[str] = None
    title: str
    product: str
    quantity: int
    budget: float
    currency: str = "INR"
    delivery_days: int
    specifications: List[str] = Field(default_factory=list)
    status: ProcurementStatus = ProcurementStatus.OPEN
    current_stage: str = "Requirement Gathering"
    approval_tier: str = ApprovalTier.TIER_2_MANAGER.value
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    recommended_vendor: Optional[str] = None
    recommended_price: Optional[float] = None
    recommended_delivery_days: Optional[int] = None
    quotes: List[VendorQuote] = Field(default_factory=list)
    approval: Optional[ApprovalDecision] = None
    conversation_history: List[Dict[str, Any]] = Field(default_factory=list)
    summary: Optional[str] = None
    po_number: Optional[str] = None


class ProcurementCreateRequest(BaseModel):
    product: str
    quantity: int
    budget: float
    delivery_days: int
    specifications: List[str] = Field(default_factory=list)
    channel: Optional[ChannelType] = ChannelType.WEB
    requester_id: Optional[str] = "web_user"
    requester_name: Optional[str] = "Procurement Specialist"


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


class ApprovalActionRequest(BaseModel):
    approver: str = "Manager"
    notes: Optional[str] = None
    channel: Optional[ChannelType] = ChannelType.WEB


# ---------------------------------------------------------------------------
# Purchase Order (PO) & ERP Models
# ---------------------------------------------------------------------------

class PurchaseOrderItem(BaseModel):
    item_description: str
    quantity: int
    unit_price: float
    total_price: float


class PurchaseOrder(BaseModel):
    po_number: str
    procurement_id: str
    vendor_name: str
    vendor_email: str
    items: List[PurchaseOrderItem]
    subtotal: float
    tax_rate: float = 0.18  # 18% Standard GST / Tax
    tax_amount: float
    total_amount: float
    delivery_timeline_days: int
    payment_terms: str = "Net 30 Days after fulfillment & QA inspection"
    shipping_address: str = "Enterprise Logistics Center, Tech Park, Bangalore 560100"
    status: str = "Issued & Authorized"
    approved_by: str
    created_at: datetime = Field(default_factory=datetime.utcnow)


class ManualQuoteInput(BaseModel):
    vendor_name: str
    price: float
    delivery_days: int
    warranty_years: int
    vendor_rating: Optional[float] = 4.5
    reliability_score: Optional[float] = 90.0
    notes: Optional[str] = None


# ---------------------------------------------------------------------------
# Vendor Intelligence Engine Models
# ---------------------------------------------------------------------------

class VendorProfile(BaseModel):
    id: str
    name: str
    contact_email: str
    phone: Optional[str] = None
    rating: float
    reliability_score: float
    past_performance: str
    on_time_rate: Optional[float] = 95.0
    product_categories: List[str]
    certifications: List[str] = Field(default_factory=list)
    market_tier: Optional[str] = "Enterprise Tier-1"
    average_delivery_days: int = 7
    created_at: datetime = Field(default_factory=datetime.utcnow)


class QuotationInput(BaseModel):
    vendor_name: str
    price: float
    delivery_days: int
    warranty_years: int
    vendor_rating: float = 4.5
    reliability_score: float = 90.0
    specs_matched: List[str] = Field(default_factory=list)
    notes: Optional[str] = None


class VendorScoreResult(BaseModel):
    vendor: str
    score: int
    rank: int = 1
    price_score: float
    delivery_score: float
    reliability_score: float
    warranty_score: float
    quoted_price: float
    delivery_days: int
    warranty_years: int
    is_recommended: bool = False


class RiskAlert(BaseModel):
    vendor_name: str
    risk_factor: str
    risk_level: RiskLevel
    reason: str


class QuotationAnalysisResult(BaseModel):
    product: str
    quantity: int
    budget: float
    market_average_price: float
    quotes_analyzed: int
    comparison_table: List[Dict[str, Any]]
    scoring_results: List[VendorScoreResult]
    risk_alerts: List[RiskAlert]
    recommended_vendor: Optional[str] = None
    savings_amount: Optional[float] = 0.0
    savings_percentage: Optional[float] = 0.0


class NegotiationThread(BaseModel):
    id: str
    procurement_id: Optional[str] = None
    vendor_name: str
    vendor_email: Optional[str] = None
    initial_price: float
    current_price: float
    target_price: float
    status: NegotiationStatus = NegotiationStatus.SENT
    counter_offer_text: str
    vendor_reply_text: Optional[str] = None
    savings_achieved: float = 0.0
    sent_at: datetime = Field(default_factory=datetime.utcnow)
    replied_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class SupplierRecommendation(BaseModel):
    product: Optional[str] = None
    quantity: Optional[int] = None
    recommended_vendor: str
    recommended_price: float
    recommended_delivery_days: Optional[int] = None
    recommended_warranty_years: Optional[int] = None
    composite_score: Optional[int] = None
    reasons: List[str] = Field(default_factory=list)
    risk_summary: Optional[str] = None
    score_breakdown: Optional[Dict[str, Any]] = Field(default_factory=dict)
    savings_amount: float
    savings_percentage: float
    score: Optional[int] = None
    risk_level: Optional[RiskLevel] = None


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
    quotes: List[QuotationInput]
    target_delivery_days: Optional[int] = 10


class NegotiationRequest(BaseModel):
    procurement_id: Optional[str] = None
    vendor_name: str
    vendor_email: Optional[str] = None
    initial_price: float
    competing_lower_price: float
    target_discount_percentage: float = 5.0
    product_name: str = "Enterprise Equipment"
    quantity: int = 100


class RecommendationRequest(BaseModel):
    product: str
    quantity: int
    budget: float
    target_delivery_days: Optional[int] = 10
    quotes: List[QuotationInput]
