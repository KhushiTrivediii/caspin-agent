import json
import sqlite3
import aiosqlite
from datetime import datetime
from typing import List, Optional, Dict, Any
from pathlib import Path
from backend.models import (
    ProcurementTicket,
    ProcurementStatus,
    VendorQuote,
    AuditLog,
    ChannelMessage,
    ApprovalDecision,
    ChannelType,
    VendorProfile,
    NegotiationThread,
    NegotiationStatus,
    RiskAlert,
    RiskLevel,
    PurchaseOrder,
    PurchaseOrderItem,
)

DB_PATH = Path("./procurements.db")


async def init_db():
    """Initialize database tables with schema definitions."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS procurements (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                product TEXT NOT NULL,
                quantity INTEGER NOT NULL,
                budget REAL NOT NULL,
                currency TEXT DEFAULT 'INR',
                delivery_days INTEGER NOT NULL,
                specifications TEXT,
                status TEXT NOT NULL,
                current_stage TEXT NOT NULL,
                requester_id TEXT,
                requester_name TEXT,
                requester_email TEXT,
                channel TEXT DEFAULT 'telegram',
                recommended_vendor TEXT,
                recommended_price REAL,
                recommended_delivery_days INTEGER,
                approval_status TEXT,
                approval_approver TEXT,
                approval_channel TEXT,
                approval_notes TEXT,
                approval_timestamp TEXT,
                summary TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                approval_tier TEXT DEFAULT 'Tier 2 (Department Manager)',
                po_number TEXT
            )
            """
        )

        # Database Migrations (Run columns additions inside try-except for backward-compatibility)
        try:
            await db.execute("ALTER TABLE procurements ADD COLUMN approval_tier TEXT DEFAULT 'Tier 2 (Department Manager)'")
        except sqlite3.OperationalError:
            pass  # Already exists

        try:
            await db.execute("ALTER TABLE procurements ADD COLUMN po_number TEXT")
        except sqlite3.OperationalError:
            pass  # Already exists

        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS purchase_orders (
                po_number TEXT PRIMARY KEY,
                procurement_id TEXT NOT NULL,
                vendor_name TEXT NOT NULL,
                vendor_email TEXT NOT NULL,
                subtotal REAL NOT NULL,
                tax_rate REAL DEFAULT 0.18,
                tax_amount REAL NOT NULL,
                total_amount REAL NOT NULL,
                delivery_timeline_days INTEGER NOT NULL,
                payment_terms TEXT,
                shipping_address TEXT,
                status TEXT,
                approved_by TEXT,
                items_json TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY (procurement_id) REFERENCES procurements (id)
            )
            """
        )

        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS vendor_quotes (
                id TEXT PRIMARY KEY,
                procurement_id TEXT NOT NULL,
                vendor_name TEXT NOT NULL,
                price REAL NOT NULL,
                currency TEXT DEFAULT 'INR',
                delivery_days INTEGER NOT NULL,
                specs_matched TEXT,
                rating REAL DEFAULT 4.5,
                warranty_years INTEGER DEFAULT 3,
                savings_amount REAL DEFAULT 0.0,
                savings_percentage REAL DEFAULT 0.0,
                is_recommended INTEGER DEFAULT 0,
                quote_notes TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY (procurement_id) REFERENCES procurements (id) ON DELETE CASCADE
            )
            """
        )

        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS audit_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                procurement_id TEXT NOT NULL,
                stage TEXT NOT NULL,
                action TEXT NOT NULL,
                actor TEXT NOT NULL,
                details TEXT,
                timestamp TEXT NOT NULL
            )
            """
        )

        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS channel_messages (
                id TEXT PRIMARY KEY,
                conversation_id TEXT NOT NULL,
                channel TEXT NOT NULL,
                sender_id TEXT NOT NULL,
                sender_name TEXT,
                recipient TEXT,
                subject TEXT,
                text TEXT NOT NULL,
                html TEXT,
                is_agent INTEGER DEFAULT 0,
                procurement_id TEXT,
                timestamp TEXT NOT NULL
            )
            """
        )

        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS conversation_states (
                conversation_id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                channel TEXT NOT NULL,
                state_json TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )

        # Vendors Registry Table
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS vendors (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL UNIQUE,
                contact_email TEXT NOT NULL,
                phone TEXT,
                rating REAL DEFAULT 4.5,
                reliability_score REAL DEFAULT 90.0,
                past_performance TEXT,
                on_time_rate REAL DEFAULT 95.0,
                product_categories TEXT,
                certifications TEXT,
                market_tier TEXT DEFAULT 'Enterprise Tier-1',
                created_at TEXT NOT NULL
            )
            """
        )

        # Negotiation Threads Table
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS negotiations (
                id TEXT PRIMARY KEY,
                procurement_id TEXT,
                vendor_name TEXT NOT NULL,
                vendor_email TEXT NOT NULL,
                status TEXT NOT NULL,
                initial_price REAL NOT NULL,
                target_price REAL NOT NULL,
                current_price REAL NOT NULL,
                counter_offer_text TEXT,
                vendor_reply_text TEXT,
                savings_achieved REAL DEFAULT 0.0,
                sent_at TEXT NOT NULL,
                replied_at TEXT
            )
            """
        )

        # Vendor Risk Logs Table
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS vendor_risk_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                vendor_name TEXT NOT NULL,
                risk_level TEXT NOT NULL,
                risk_factor TEXT NOT NULL,
                reason TEXT NOT NULL,
                mitigation_advice TEXT,
                created_at TEXT NOT NULL
            )
            """
        )

        await db.commit()
    
    await seed_vendor_database()


async def seed_vendor_database():
    """Seed initial enterprise supplier catalog."""
    initial_vendors = [
        VendorProfile(
            id="VEND-DELL-01",
            name="Dell Partner (Enterprise Solutions)",
            contact_email="sales@dell-enterprise-partners.com",
            phone="+91-80-4567-8901",
            rating=4.8,
            reliability_score=96.0,
            past_performance="Excellent (99.2% on-time fulfillment, 0% dispute rate)",
            on_time_rate=99.2,
            product_categories=["Laptop", "Desktop Computer", "Server", "Monitor", "Peripherals"],
            certifications=["Dell Titanium Certified Partner", "ISO 9001:2015", "ISO 27001"],
            market_tier="Enterprise Tier-1 Platinum",
        ),
        VendorProfile(
            id="VEND-HP-02",
            name="HP Commercial Direct",
            contact_email="commercial-bids@hp-direct.internal",
            phone="+91-80-5566-7788",
            rating=4.6,
            reliability_score=92.0,
            past_performance="Very Good (96.5% on-time fulfillment, 0.5% warranty claim rate)",
            on_time_rate=96.5,
            product_categories=["Laptop", "Desktop Computer", "Printer", "Workstation"],
            certifications=["HP Gold Partner", "ISO 9001:2015"],
            market_tier="Enterprise Tier-1 Gold",
        ),
        VendorProfile(
            id="VEND-LENOVO-03",
            name="Lenovo Premier Solutions",
            contact_email="enterprise@lenovo-premier.com",
            phone="+91-11-2345-6789",
            rating=4.5,
            reliability_score=90.0,
            past_performance="Reliable (95.0% on-time fulfillment, 1.2% dispute rate)",
            on_time_rate=95.0,
            product_categories=["Laptop", "ThinkPad", "Server", "Monitor"],
            certifications=["Lenovo Premier Direct Partner", "ISO 9001"],
            market_tier="Enterprise Tier-1",
        ),
        VendorProfile(
            id="VEND-APEX-04",
            name="Apex Hardware Solutions",
            contact_email="bids@apexhardware.net",
            phone="+91-22-3344-5566",
            rating=4.2,
            reliability_score=85.0,
            past_performance="Good (91.0% on-time delivery rate)",
            on_time_rate=91.0,
            product_categories=["Office Chair", "Standing Desk", "Furniture", "Peripherals"],
            certifications=["BIFMA Level 3 Certified", "GreenGuard Gold"],
            market_tier="Tier-2 Commercial",
        ),
        VendorProfile(
            id="VEND-TECHNOVA-05",
            name="TechNova Global Ltd",
            contact_email="procurement@technovaglobal.com",
            phone="+91-40-6677-8899",
            rating=3.6,
            reliability_score=72.0,
            past_performance="Moderate (82.0% on-time rate, multiple delayed shipments)",
            on_time_rate=82.0,
            product_categories=["Laptop", "Server", "Cloud License", "Network Switch"],
            certifications=[],  # Missing OEM certifications for risk testing
            market_tier="Tier-3 Distributor",
        ),
    ]

    async with aiosqlite.connect(DB_PATH) as db:
        for v in initial_vendors:
            await db.execute(
                """
                INSERT INTO vendors (
                    id, name, contact_email, phone, rating, reliability_score,
                    past_performance, on_time_rate, product_categories, certifications,
                    market_tier, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(name) DO UPDATE SET
                    rating=excluded.rating,
                    reliability_score=excluded.reliability_score,
                    product_categories=excluded.product_categories,
                    certifications=excluded.certifications
                """,
                (
                    v.id,
                    v.name,
                    v.contact_email,
                    v.phone,
                    v.rating,
                    v.reliability_score,
                    v.past_performance,
                    v.on_time_rate,
                    json.dumps(v.product_categories),
                    json.dumps(v.certifications),
                    v.market_tier,
                    v.created_at.isoformat(),
                ),
            )
        await db.commit()


async def list_vendors(category: Optional[str] = None, search: Optional[str] = None) -> List[VendorProfile]:
    """Retrieve vendors from registry with category & text filtering."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        query = "SELECT * FROM vendors WHERE 1=1"
        params = []

        if search:
            query += " AND (name LIKE ? OR product_categories LIKE ?)"
            params.extend([f"%{search}%", f"%{search}%"])

        query += " ORDER BY rating DESC"
        cursor = await db.execute(query, tuple(params))
        rows = await cursor.fetchall()
        vendors = []
        for r in rows:
            cats = json.loads(r["product_categories"] or "[]")
            if category and not any(category.lower() in c.lower() for c in cats):
                continue
            vendors.append(
                VendorProfile(
                    id=r["id"],
                    name=r["name"],
                    contact_email=r["contact_email"],
                    phone=r["phone"],
                    rating=r["rating"],
                    reliability_score=r["reliability_score"],
                    past_performance=r["past_performance"],
                    on_time_rate=r["on_time_rate"],
                    product_categories=cats,
                    certifications=json.loads(r["certifications"] or "[]"),
                    market_tier=r["market_tier"],
                    created_at=datetime.fromisoformat(r["created_at"]),
                )
            )
        return vendors


async def save_negotiation_thread(neg: NegotiationThread) -> NegotiationThread:
    """Save or update negotiation thread record."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """
            INSERT INTO negotiations (
                id, procurement_id, vendor_name, vendor_email, status,
                initial_price, target_price, current_price, counter_offer_text,
                vendor_reply_text, savings_achieved, sent_at, replied_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                status=excluded.status,
                current_price=excluded.current_price,
                vendor_reply_text=excluded.vendor_reply_text,
                savings_achieved=excluded.savings_achieved,
                replied_at=excluded.replied_at
            """,
            (
                neg.id,
                neg.procurement_id,
                neg.vendor_name,
                neg.vendor_email,
                neg.status.value if isinstance(neg.status, NegotiationStatus) else neg.status,
                neg.initial_price,
                neg.target_price,
                neg.current_price,
                neg.counter_offer_text,
                neg.vendor_reply_text,
                neg.savings_achieved,
                neg.sent_at.isoformat(),
                neg.replied_at.isoformat() if neg.replied_at else None,
            ),
        )
        await db.commit()
    return neg


async def list_negotiations(procurement_id: Optional[str] = None) -> List[NegotiationThread]:
    """Retrieve negotiation threads."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        if procurement_id:
            cursor = await db.execute(
                "SELECT * FROM negotiations WHERE procurement_id = ? ORDER BY sent_at DESC",
                (procurement_id,),
            )
        else:
            cursor = await db.execute("SELECT * FROM negotiations ORDER BY sent_at DESC LIMIT 50")
        rows = await cursor.fetchall()
        threads = []
        for r in rows:
            threads.append(
                NegotiationThread(
                    id=r["id"],
                    procurement_id=r["procurement_id"],
                    vendor_name=r["vendor_name"],
                    vendor_email=r["vendor_email"],
                    status=NegotiationStatus(r["status"]),
                    initial_price=r["initial_price"],
                    target_price=r["target_price"],
                    current_price=r["current_price"],
                    counter_offer_text=r["counter_offer_text"],
                    vendor_reply_text=r["vendor_reply_text"],
                    savings_achieved=r["savings_achieved"],
                    sent_at=datetime.fromisoformat(r["sent_at"]),
                    replied_at=datetime.fromisoformat(r["replied_at"]) if r["replied_at"] else None,
                )
            )
        return threads


async def log_vendor_risk(alert: RiskAlert):
    """Log detected vendor risk alert into database."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """
            INSERT INTO vendor_risk_logs (vendor_name, risk_level, risk_factor, reason, mitigation_advice, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                alert.vendor_name,
                alert.risk_level.value if isinstance(alert.risk_level, RiskLevel) else alert.risk_level,
                alert.risk_factor,
                alert.reason,
                alert.mitigation_advice,
                datetime.utcnow().isoformat(),
            ),
        )
        await db.commit()


async def get_next_procurement_id() -> str:
    """Generate sequential unique procurement ID like PROC-2026-001."""
    year = datetime.now().year
    prefix = f"PROC-{year}-"
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT id FROM procurements WHERE id LIKE ? ORDER BY id DESC LIMIT 1",
            (f"{prefix}%",),
        )
        row = await cursor.fetchone()
        if not row:
            return f"{prefix}001"
        try:
            last_seq = int(row[0].split("-")[-1])
            new_seq = last_seq + 1
            return f"{prefix}{new_seq:03d}"
        except Exception:
            return f"{prefix}001"


async def create_procurement(ticket: ProcurementTicket) -> ProcurementTicket:
    """Insert new procurement ticket and its quotes into database."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """
            INSERT INTO procurements (
                id, title, product, quantity, budget, currency, delivery_days,
                specifications, status, current_stage, requester_id, requester_name,
                requester_email, channel, recommended_vendor, recommended_price,
                recommended_delivery_days, summary, created_at, updated_at,
                approval_tier, po_number
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                ticket.id,
                ticket.title,
                ticket.product,
                ticket.quantity,
                ticket.budget,
                ticket.currency,
                ticket.delivery_days,
                json.dumps(ticket.specifications),
                ticket.status.value if isinstance(ticket.status, ProcurementStatus) else ticket.status,
                ticket.current_stage,
                ticket.requester_id,
                ticket.requester_name,
                ticket.requester_email,
                ticket.channel.value if isinstance(ticket.channel, ChannelType) else ticket.channel,
                ticket.recommended_vendor,
                ticket.recommended_price,
                ticket.recommended_delivery_days,
                ticket.summary,
                ticket.created_at.isoformat(),
                ticket.updated_at.isoformat(),
                ticket.approval_tier,
                ticket.po_number,
            ),
        )

        for quote in ticket.quotes:
            await db.execute(
                """
                INSERT INTO vendor_quotes (
                    id, procurement_id, vendor_name, price, currency, delivery_days,
                    specs_matched, rating, warranty_years, savings_amount,
                    savings_percentage, is_recommended, quote_notes, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    quote.id,
                    ticket.id,
                    quote.vendor_name,
                    quote.price,
                    quote.currency,
                    quote.delivery_days,
                    json.dumps(quote.specs_matched),
                    quote.rating,
                    quote.warranty_years,
                    quote.savings_amount,
                    quote.savings_percentage,
                    1 if quote.is_recommended else 0,
                    quote.quote_notes,
                    quote.created_at.isoformat(),
                ),
            )

        # Log audit trail
        await db.execute(
            """
            INSERT INTO audit_logs (procurement_id, stage, action, actor, details, timestamp)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                ticket.id,
                "Open",
                "Ticket Created",
                ticket.requester_name or "System Agent",
                json.dumps({"product": ticket.product, "quantity": ticket.quantity, "budget": ticket.budget}),
                datetime.utcnow().isoformat(),
            ),
        )

        await db.commit()
    return ticket


async def get_procurement(procurement_id: str) -> Optional[ProcurementTicket]:
    """Retrieve full procurement record with vendor quotes and approvals."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT * FROM procurements WHERE id = ?", (procurement_id,))
        row = await cursor.fetchone()
        if not row:
            return None

        # Fetch quotes
        quote_cursor = await db.execute(
            "SELECT * FROM vendor_quotes WHERE procurement_id = ? ORDER BY price ASC",
            (procurement_id,),
        )
        quote_rows = await quote_cursor.fetchall()
        quotes = []
        for q in quote_rows:
            quotes.append(
                VendorQuote(
                    id=q["id"],
                    procurement_id=q["procurement_id"],
                    vendor_name=q["vendor_name"],
                    price=q["price"],
                    currency=q["currency"],
                    delivery_days=q["delivery_days"],
                    specs_matched=json.loads(q["specs_matched"] or "[]"),
                    rating=q["rating"],
                    warranty_years=q["warranty_years"],
                    savings_amount=q["savings_amount"],
                    savings_percentage=q["savings_percentage"],
                    is_recommended=bool(q["is_recommended"]),
                    quote_notes=q["quote_notes"],
                    created_at=datetime.fromisoformat(q["created_at"]),
                )
            )

        approval = None
        if row["approval_status"]:
            approval = ApprovalDecision(
                status=row["approval_status"],
                approver=row["approval_approver"] or "Manager",
                channel=row["approval_channel"] or "web",
                notes=row["approval_notes"],
                timestamp=datetime.fromisoformat(row["approval_timestamp"]) if row["approval_timestamp"] else datetime.utcnow(),
            )

        return ProcurementTicket(
            id=row["id"],
            title=row["title"],
            product=row["product"],
            quantity=row["quantity"],
            budget=row["budget"],
            currency=row["currency"],
            delivery_days=row["delivery_days"],
            specifications=json.loads(row["specifications"] or "[]"),
            status=ProcurementStatus(row["status"]),
            current_stage=row["current_stage"],
            requester_id=row["requester_id"],
            requester_name=row["requester_name"],
            requester_email=row["requester_email"],
            channel=ChannelType(row["channel"]),
            recommended_vendor=row["recommended_vendor"],
            recommended_price=row["recommended_price"],
            recommended_delivery_days=row["recommended_delivery_days"],
            quotes=quotes,
            approval=approval,
            summary=row["summary"],
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
            approval_tier=row["approval_tier"] or "Tier 2 (Department Manager)",
            po_number=row["po_number"],
        )


async def list_procurements(
    status: Optional[str] = None,
    channel: Optional[str] = None,
    search: Optional[str] = None,
    limit: int = 50,
) -> List[ProcurementTicket]:
    """List procurement tickets with optional filtering."""
    query = "SELECT id FROM procurements WHERE 1=1"
    params = []

    if status:
        query += " AND status = ?"
        params.append(status)
    if channel:
        query += " AND channel = ?"
        params.append(channel)
    if search:
        query += " AND (product LIKE ? OR id LIKE ? OR requester_name LIKE ?)"
        term = f"%{search}%"
        params.extend([term, term, term])

    query += " ORDER BY created_at DESC LIMIT ?"
    params.append(limit)

    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(query, tuple(params))
        rows = await cursor.fetchall()
        tickets = []
        for row in rows:
            ticket = await get_procurement(row[0])
            if ticket:
                tickets.append(ticket)
        return tickets


async def update_procurement_stage(
    procurement_id: str,
    status: ProcurementStatus,
    current_stage: str,
    actor: str = "System",
    details: Optional[Dict[str, Any]] = None,
):
    """Update status, stage and log audit entry."""
    now = datetime.utcnow().isoformat()
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """
            UPDATE procurements
            SET status = ?, current_stage = ?, updated_at = ?
            WHERE id = ?
            """,
            (status.value if isinstance(status, ProcurementStatus) else status, current_stage, now, procurement_id),
        )
        await db.execute(
            """
            INSERT INTO audit_logs (procurement_id, stage, action, actor, details, timestamp)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                procurement_id,
                current_stage,
                f"Stage changed to {status.value if isinstance(status, ProcurementStatus) else status}",
                actor,
                json.dumps(details or {}),
                now,
            ),
        )
        await db.commit()


async def record_approval_decision(
    procurement_id: str,
    status: str,  # "APPROVED" or "REJECTED"
    approver: str,
    channel: str,
    notes: Optional[str] = None,
):
    """Record manager approval or rejection."""
    now = datetime.utcnow().isoformat()
    procurement_status = ProcurementStatus.APPROVED if status == "APPROVED" else ProcurementStatus.REJECTED
    current_stage = "Completed" if status == "APPROVED" else "Rejected / Closed"

    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """
            UPDATE procurements
            SET status = ?,
                current_stage = ?,
                approval_status = ?,
                approval_approver = ?,
                approval_channel = ?,
                approval_notes = ?,
                approval_timestamp = ?,
                updated_at = ?
            WHERE id = ?
            """,
            (
                procurement_status.value,
                current_stage,
                status,
                approver,
                channel,
                notes,
                now,
                now,
                procurement_id,
            ),
        )

        await db.execute(
            """
            INSERT INTO audit_logs (procurement_id, stage, action, actor, details, timestamp)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                procurement_id,
                current_stage,
                f"Decision: {status}",
                approver,
                json.dumps({"channel": channel, "notes": notes}),
                now,
            ),
        )
        await db.commit()

    if status == "APPROVED":
        ticket = await get_procurement(procurement_id)
        if ticket:
            from backend.po_generator import po_engine
            po = po_engine.generate_purchase_order(ticket, approver)
            await save_purchase_order(po)


async def save_channel_message(msg: ChannelMessage):
    """Store channel message in database."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """
            INSERT INTO channel_messages (
                id, conversation_id, channel, sender_id, sender_name,
                recipient, subject, text, html, is_agent, procurement_id, timestamp
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                msg.id,
                msg.conversation_id,
                msg.channel,
                msg.sender_id,
                msg.sender_name,
                msg.recipient,
                msg.subject,
                msg.text,
                msg.html,
                1 if msg.is_agent else 0,
                msg.procurement_id,
                msg.timestamp.isoformat(),
            ),
        )
        await db.commit()


async def get_channel_messages(conversation_id: Optional[str] = None, procurement_id: Optional[str] = None) -> List[ChannelMessage]:
    """Retrieve message history for a conversation or procurement."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        if conversation_id:
            cursor = await db.execute(
                "SELECT * FROM channel_messages WHERE conversation_id = ? ORDER BY timestamp ASC",
                (conversation_id,),
            )
        elif procurement_id:
            cursor = await db.execute(
                "SELECT * FROM channel_messages WHERE procurement_id = ? ORDER BY timestamp ASC",
                (procurement_id,),
            )
        else:
            cursor = await db.execute(
                "SELECT * FROM channel_messages ORDER BY timestamp DESC LIMIT 100"
            )
        rows = await cursor.fetchall()
        msgs = []
        for r in rows:
            msgs.append(
                ChannelMessage(
                    id=r["id"],
                    conversation_id=r["conversation_id"],
                    channel=r["channel"],
                    sender_id=r["sender_id"],
                    sender_name=r["sender_name"],
                    recipient=r["recipient"],
                    subject=r["subject"],
                    text=r["text"],
                    html=r["html"],
                    is_agent=bool(r["is_agent"]),
                    procurement_id=r["procurement_id"],
                    timestamp=datetime.fromisoformat(r["timestamp"]),
                )
            )
        return msgs


async def get_audit_logs(procurement_id: str) -> List[AuditLog]:
    """Retrieve audit history for a procurement ticket."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM audit_logs WHERE procurement_id = ? ORDER BY timestamp ASC",
            (procurement_id,),
        )
        rows = await cursor.fetchall()
        logs = []
        for r in rows:
            logs.append(
                AuditLog(
                    id=r["id"],
                    procurement_id=r["procurement_id"],
                    stage=r["stage"],
                    action=r["action"],
                    actor=r["actor"],
                    details=json.loads(r["details"] or "{}"),
                    timestamp=datetime.fromisoformat(r["timestamp"]),
                )
            )
        return logs


async def get_conversation_state(conversation_id: str) -> Optional[Dict[str, Any]]:
    """Get multi-turn state for ongoing conversation."""
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT state_json FROM conversation_states WHERE conversation_id = ?",
            (conversation_id,),
        )
        row = await cursor.fetchone()
        if row:
            return json.loads(row[0])
        return None


async def save_conversation_state(conversation_id: str, user_id: str, channel: str, state: Dict[str, Any]):
    """Persist conversation state."""
    now = datetime.utcnow().isoformat()
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """
            INSERT INTO conversation_states (conversation_id, user_id, channel, state_json, updated_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(conversation_id) DO UPDATE SET
                state_json=excluded.state_json,
                updated_at=excluded.updated_at
            """,
            (conversation_id, user_id, channel, json.dumps(state), now),
        )
        await db.commit()


async def clear_conversation_state(conversation_id: str):
    """Clear conversation state after completion."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM conversation_states WHERE conversation_id = ?", (conversation_id,))
        await db.commit()


async def get_dashboard_stats() -> Dict[str, Any]:
    """Calculate KPI statistics for procurement dashboard."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        # Total counts
        cursor = await db.execute(
            """
            SELECT 
                COUNT(*) as total_requests,
                SUM(CASE WHEN status = 'Open' THEN 1 ELSE 0 END) as open_count,
                SUM(CASE WHEN status IN ('Vendor Search', 'Negotiation') THEN 1 ELSE 0 END) as in_progress_count,
                SUM(CASE WHEN status = 'Approval Pending' THEN 1 ELSE 0 END) as pending_approvals,
                SUM(CASE WHEN status = 'Approved' THEN 1 ELSE 0 END) as approved_count,
                SUM(CASE WHEN status = 'Completed' THEN 1 ELSE 0 END) as completed_count,
                SUM(CASE WHEN status = 'Rejected' THEN 1 ELSE 0 END) as rejected_count,
                SUM(budget) as total_budget_requested,
                SUM(CASE WHEN status IN ('Approved', 'Completed') THEN recommended_price ELSE 0 END) as total_spend_committed
            FROM procurements
            """
        )
        row = await cursor.fetchone()
        
        # Calculate total savings
        quote_cursor = await db.execute(
            """
            SELECT SUM(q.savings_amount) as total_savings
            FROM vendor_quotes q
            JOIN procurements p ON q.procurement_id = p.id
            WHERE q.is_recommended = 1 AND p.status IN ('Approved', 'Completed')
            """
        )
        quote_row = await quote_cursor.fetchone()

        # Count registered vendors & active negotiations
        vend_cursor = await db.execute("SELECT COUNT(*) FROM vendors")
        vend_count = (await vend_cursor.fetchone())[0]

        neg_cursor = await db.execute("SELECT COUNT(*) FROM negotiations")
        neg_count = (await neg_cursor.fetchone())[0]

        # Recent activities
        recent_cursor = await db.execute(
            "SELECT * FROM audit_logs ORDER BY timestamp DESC LIMIT 6"
        )
        recent_rows = await recent_cursor.fetchall()
        recent_logs = [
            {
                "id": r["id"],
                "procurement_id": r["procurement_id"],
                "stage": r["stage"],
                "action": r["action"],
                "actor": r["actor"],
                "timestamp": r["timestamp"],
            }
            for r in recent_rows
        ]

        return {
            "total_requests": row["total_requests"] or 0,
            "open_count": row["open_count"] or 0,
            "in_progress_count": row["in_progress_count"] or 0,
            "pending_approvals": row["pending_approvals"] or 0,
            "approved_count": row["approved_count"] or 0,
            "completed_count": row["completed_count"] or 0,
            "rejected_count": row["rejected_count"] or 0,
            "total_budget_requested": row["total_budget_requested"] or 0.0,
            "total_spend_committed": row["total_spend_committed"] or 0.0,
            "total_savings": (quote_row["total_savings"] or 0.0) if quote_row else 0.0,
            "total_vendors": vend_count,
            "total_negotiations": neg_count,
            "recent_activities": recent_logs,
        }


async def save_purchase_order(po: PurchaseOrder) -> PurchaseOrder:
    """Save a generated Purchase Order into the database and update procurement ticket linking."""
    async with aiosqlite.connect(DB_PATH) as db:
        # Save PO
        items_data = json.dumps([item.dict() for item in po.items])
        await db.execute(
            """
            INSERT INTO purchase_orders (
                po_number, procurement_id, vendor_name, vendor_email, subtotal,
                tax_rate, tax_amount, total_amount, delivery_timeline_days,
                payment_terms, shipping_address, status, approved_by, items_json, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(po_number) DO UPDATE SET
                status=excluded.status,
                approved_by=excluded.approved_by,
                total_amount=excluded.total_amount
            """,
            (
                po.po_number,
                po.procurement_id,
                po.vendor_name,
                po.vendor_email,
                po.subtotal,
                po.tax_rate,
                po.tax_amount,
                po.total_amount,
                po.delivery_timeline_days,
                po.payment_terms,
                po.shipping_address,
                po.status,
                po.approved_by,
                items_data,
                po.created_at.isoformat() if hasattr(po.created_at, "isoformat") else str(po.created_at),
            ),
        )

        # Update link on procurement ticket
        await db.execute(
            "UPDATE procurements SET po_number = ? WHERE id = ?",
            (po.po_number, po.procurement_id),
        )
        await db.commit()
    return po


async def get_purchase_order(procurement_id: str) -> Optional[PurchaseOrder]:
    """Retrieve Purchase Order for a specific procurement ticket."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT * FROM purchase_orders WHERE procurement_id = ?", (procurement_id,))
        row = await cursor.fetchone()
        if not row:
            return None

        items_list = json.loads(row["items_json"] or "[]")
        items = [
            PurchaseOrderItem(
                item_description=item["item_description"],
                quantity=item["quantity"],
                unit_price=item["unit_price"],
                total_price=item["total_price"],
            )
            for item in items_list
        ]

        return PurchaseOrder(
            po_number=row["po_number"],
            procurement_id=row["procurement_id"],
            vendor_name=row["vendor_name"],
            vendor_email=row["vendor_email"],
            items=items,
            subtotal=row["subtotal"],
            tax_rate=row["tax_rate"],
            tax_amount=row["tax_amount"],
            total_amount=row["total_amount"],
            delivery_timeline_days=row["delivery_timeline_days"],
            payment_terms=row["payment_terms"],
            shipping_address=row["shipping_address"],
            status=row["status"],
            approved_by=row["approved_by"],
            created_at=datetime.fromisoformat(row["created_at"]),
        )


async def add_vendor_quote_to_db(procurement_id: str, quote: VendorQuote):
    """Add a vendor quote to an existing procurement ticket in the database."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """
            INSERT INTO vendor_quotes (
                id, procurement_id, vendor_name, price, currency, delivery_days,
                specs_matched, rating, warranty_years, savings_amount,
                savings_percentage, is_recommended, quote_notes, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                quote.id,
                procurement_id,
                quote.vendor_name,
                quote.price,
                quote.currency,
                quote.delivery_days,
                json.dumps(quote.specs_matched),
                quote.rating,
                quote.warranty_years,
                quote.savings_amount,
                quote.savings_percentage,
                1 if quote.is_recommended else 0,
                quote.quote_notes,
                quote.created_at.isoformat(),
            ),
        )

        # Clear recommendations first to let new recommendation engine pick the best
        await db.execute(
            "UPDATE vendor_quotes SET is_recommended = 0 WHERE procurement_id = ?",
            (procurement_id,),
        )
        await db.commit()

