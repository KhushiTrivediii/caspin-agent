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
                updated_at TEXT NOT NULL
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
                recommended_delivery_days, summary, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
            "recent_activities": recent_logs,
        }
