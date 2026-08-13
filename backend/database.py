import os
import json
import logging
import sqlite3
import aiosqlite
from datetime import datetime
from typing import List, Dict, Any, Optional
from backend.models import (
    IncidentTicket,
    TicketStatus,
    IncidentCategory,
    MemoryNode,
    MemoryEdge,
    MessageLog,
)

logger = logging.getLogger("database")
DB_PATH = "./blackbox.db"


async def init_db():
    """Initialize database tables with schema definitions and seed data."""
    async with aiosqlite.connect(DB_PATH) as db:
        # Create incidents table
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS tickets (
                id TEXT PRIMARY KEY,
                category TEXT NOT NULL,
                title TEXT NOT NULL,
                description TEXT NOT NULL,
                status TEXT NOT NULL,
                reporter_name TEXT NOT NULL,
                reporter_contact TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                assigned_to TEXT,
                summary TEXT
            )
            """
        )

        # Create nodes table
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS nodes (
                id TEXT PRIMARY KEY,
                label TEXT NOT NULL,
                properties TEXT NOT NULL
            )
            """
        )

        # Create edges table
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS edges (
                source TEXT NOT NULL,
                target TEXT NOT NULL,
                type TEXT NOT NULL,
                PRIMARY KEY (source, target, type)
            )
            """
        )

        # Create messages table
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS messages (
                id TEXT PRIMARY KEY,
                channel TEXT NOT NULL,
                direction TEXT NOT NULL,
                sender TEXT NOT NULL,
                recipient TEXT NOT NULL,
                text TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                ticket_id TEXT
            )
            """
        )

        # Create audit logs table
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS audit_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ticket_id TEXT NOT NULL,
                action TEXT NOT NULL,
                actor TEXT NOT NULL,
                details TEXT NOT NULL,
                timestamp TEXT NOT NULL
            )
            """
        )

        # Create settings table
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
            """
        )

        await db.commit()

        # Seed settings if empty
        cursor = await db.execute("SELECT COUNT(*) FROM settings")
        if (await cursor.fetchone())[0] == 0:
            await db.execute("INSERT INTO settings (key, value) VALUES ('founder_disappears_mode', '0')")
            await db.commit()

        # Seed initial memory graph if empty
        cursor = await db.execute("SELECT COUNT(*) FROM nodes")
        if (await cursor.fetchone())[0] == 0:
            logger.info("Seeding BLACKBOX AI Memory Graph database...")
            
            # Team members
            await db.execute("INSERT INTO nodes (id, label, properties) VALUES (?, ?, ?)", 
                ("dev_alice", "TeamMember", json.dumps({"name": "Alice (DevOps Lead)", "channel": "telegram", "contact": "alice_devops"})))
            await db.execute("INSERT INTO nodes (id, label, properties) VALUES (?, ?, ?)", 
                ("dev_bob", "TeamMember", json.dumps({"name": "Bob (Backend Engineer)", "channel": "slack", "contact": "bob_slack"})))
            await db.execute("INSERT INTO nodes (id, label, properties) VALUES (?, ?, ?)", 
                ("ops_clara", "TeamMember", json.dumps({"name": "Clara (Operations)", "channel": "slack", "contact": "clara_ops"})))
            
            # Vendors
            await db.execute("INSERT INTO nodes (id, label, properties) VALUES (?, ?, ?)", 
                ("vendor_dhl", "Vendor", json.dumps({"name": "DHL Express Logistics", "channel": "whatsapp", "contact": "+919876543210", "email": "support@dhl.com"})))
            await db.execute("INSERT INTO nodes (id, label, properties) VALUES (?, ?, ?)", 
                ("vendor_aws", "Vendor", json.dumps({"name": "Amazon Web Services", "channel": "email", "contact": "billing@aws.amazon.com"})))

            # Customers
            await db.execute("INSERT INTO nodes (id, label, properties) VALUES (?, ?, ?)", 
                ("client_alex", "Customer", json.dumps({"name": "Alex Mercer", "channel": "email", "contact": "alex@mercer.com"})))
            await db.execute("INSERT INTO nodes (id, label, properties) VALUES (?, ?, ?)", 
                ("client_sarah", "Customer", json.dumps({"name": "Sarah Chen", "channel": "discord", "contact": "sarah_discord"})))

            # Projects
            await db.execute("INSERT INTO nodes (id, label, properties) VALUES (?, ?, ?)", 
                ("project_payments", "Project", json.dumps({"name": "Payments System Gateway", "status": "In Development"})))
            
            # Leads
            await db.execute("INSERT INTO nodes (id, label, properties) VALUES (?, ?, ?)", 
                ("lead_tesla", "Lead", json.dumps({"name": "Tesla Corporate Procurement", "email": "procurement@tesla.com", "last_contact": "2026-08-01T12:00:00", "status": "Warm"})))
            await db.execute("INSERT INTO nodes (id, label, properties) VALUES (?, ?, ?)", 
                ("lead_spacex", "Lead", json.dumps({"name": "SpaceX Ground Infrastructure", "email": "contractors@spacex.com", "last_contact": "2026-08-05T09:00:00", "status": "Inactive"})))

            # Edges
            edges = [
                ("dev_bob", "project_payments", "PARTICIPATES_IN"),
                ("dev_alice", "project_payments", "PARTICIPATES_IN"),
                ("vendor_aws", "project_payments", "INFRASTRUCTURE_PROVIDER"),
                ("client_alex", "project_payments", "BETA_TESTER"),
                ("client_sarah", "project_payments", "INTEGRATOR"),
            ]
            for src, tgt, rel in edges:
                await db.execute("INSERT INTO edges (source, target, type) VALUES (?, ?, ?)", (src, tgt, rel))
            
            await db.commit()
            logger.info("BLACKBOX AI memory graph database seeded successfully.")


async def get_settings() -> Dict[str, Any]:
    """Retrieve system settings."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT * FROM settings")
        rows = await cursor.fetchall()
        return {r["key"]: r["value"] for r in rows}


async def update_setting(key: str, value: str):
    """Update a system setting."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
            (key, value),
        )
        await db.commit()


async def create_ticket(ticket: IncidentTicket) -> IncidentTicket:
    """Save a new ticket to the database."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """
            INSERT INTO tickets (
                id, category, title, description, status,
                reporter_name, reporter_contact, created_at, updated_at,
                assigned_to, summary
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                ticket.id,
                ticket.category.value,
                ticket.title,
                ticket.description,
                ticket.status.value,
                ticket.reporter_name,
                ticket.reporter_contact,
                ticket.created_at.isoformat(),
                ticket.updated_at.isoformat(),
                ticket.assigned_to,
                ticket.summary,
            ),
        )
        await db.commit()
    return ticket


async def get_ticket(ticket_id: str) -> Optional[IncidentTicket]:
    """Retrieve ticket details from database."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT * FROM tickets WHERE id = ?", (ticket_id,))
        row = await cursor.fetchone()
        if not row:
            return None
        return IncidentTicket(
            id=row["id"],
            category=IncidentCategory(row["category"]),
            title=row["title"],
            description=row["description"],
            status=TicketStatus(row["status"]),
            reporter_name=row["reporter_name"],
            reporter_contact=row["reporter_contact"],
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
            assigned_to=row["assigned_to"],
            summary=row["summary"],
        )


async def list_tickets(category: Optional[str] = None, status: Optional[str] = None) -> List[IncidentTicket]:
    """Retrieve lists of tickets, optionally filtered."""
    query = "SELECT * FROM tickets WHERE 1=1"
    params = []
    if category:
        query += " AND category = ?"
        params.append(category)
    if status:
        query += " AND status = ?"
        params.append(status)
    query += " ORDER BY created_at DESC"

    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(query, tuple(params))
        rows = await cursor.fetchall()
        tickets = []
        for r in rows:
            tickets.append(
                IncidentTicket(
                    id=r["id"],
                    category=IncidentCategory(r["category"]),
                    title=r["title"],
                    description=r["description"],
                    status=TicketStatus(r["status"]),
                    reporter_name=r["reporter_name"],
                    reporter_contact=r["reporter_contact"],
                    created_at=datetime.fromisoformat(r["created_at"]),
                    updated_at=datetime.fromisoformat(r["updated_at"]),
                    assigned_to=r["assigned_to"],
                    summary=r["summary"],
                )
            )
        return tickets


async def update_ticket_status(
    ticket_id: str,
    status: TicketStatus,
    assigned_to: Optional[str] = None,
    summary: Optional[str] = None,
):
    """Update status, assignee, and description summary of a ticket."""
    async with aiosqlite.connect(DB_PATH) as db:
        query = "UPDATE tickets SET status = ?, updated_at = ?"
        params = [status.value, datetime.utcnow().isoformat()]
        if assigned_to is not None:
            query += ", assigned_to = ?"
            params.append(assigned_to)
        if summary is not None:
            query += ", summary = ?"
            params.append(summary)
        query += " WHERE id = ?"
        params.append(ticket_id)
        
        await db.execute(query, tuple(params))
        await db.commit()


async def save_channel_message(msg: MessageLog):
    """Save an inbound or outbound multi-channel message to database."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """
            INSERT INTO messages (
                id, channel, direction, sender, recipient, text, timestamp, ticket_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                msg.id,
                msg.channel,
                msg.direction,
                msg.sender,
                msg.recipient,
                msg.text,
                msg.timestamp.isoformat(),
                msg.ticket_id,
            ),
        )
        await db.commit()


async def get_channel_messages(ticket_id: Optional[str] = None) -> List[MessageLog]:
    """Retrieve message logs, optionally for a specific ticket."""
    query = "SELECT * FROM messages"
    params = []
    if ticket_id:
        query += " WHERE ticket_id = ?"
        params.append(ticket_id)
    query += " ORDER BY timestamp ASC"

    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(query, tuple(params))
        rows = await cursor.fetchall()
        msgs = []
        for r in rows:
            msgs.append(
                MessageLog(
                    id=r["id"],
                    channel=r["channel"],
                    direction=r["direction"],
                    sender=r["sender"],
                    recipient=r["recipient"],
                    text=r["text"],
                    timestamp=datetime.fromisoformat(r["timestamp"]),
                    ticket_id=r["ticket_id"],
                )
            )
        return msgs


async def log_audit_action(ticket_id: str, action: str, actor: str, details: str):
    """Append a row to the audit logs table."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """
            INSERT INTO audit_logs (ticket_id, action, actor, details, timestamp)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                ticket_id,
                action,
                actor,
                details,
                datetime.utcnow().isoformat(),
            ),
        )
        await db.commit()


async def get_audit_logs(ticket_id: str) -> List[Dict[str, Any]]:
    """Retrieve audit history logs for a ticket."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM audit_logs WHERE ticket_id = ? ORDER BY timestamp DESC",
            (ticket_id,),
        )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]


async def get_graph_data() -> Dict[str, Any]:
    """Retrieve all nodes and edges in the memory graph."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        
        # Load nodes
        n_cursor = await db.execute("SELECT * FROM nodes")
        n_rows = await n_cursor.fetchall()
        nodes = []
        for r in n_rows:
            nodes.append({
                "id": r["id"],
                "label": r["label"],
                "properties": json.loads(r["properties"])
            })

        # Load edges
        e_cursor = await db.execute("SELECT * FROM edges")
        e_rows = await e_cursor.fetchall()
        edges = [dict(r) for r in e_rows]

        return {"nodes": nodes, "edges": edges}


async def add_graph_node(node_id: str, label: str, properties: Dict[str, Any]):
    """Insert or update a node in the memory graph."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT OR REPLACE INTO nodes (id, label, properties) VALUES (?, ?, ?)",
            (node_id, label, json.dumps(properties)),
        )
        await db.commit()


async def add_graph_edge(source: str, target: str, edge_type: str):
    """Insert an edge link into the memory graph."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT OR REPLACE INTO edges (source, target, type) VALUES (?, ?, ?)",
            (source, target, edge_type),
        )
        await db.commit()


async def get_kpi_stats() -> Dict[str, Any]:
    """Get active stats counting opportunities, risks, delays, etc."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        
        # Count open issues (Support, Blocker, Bugs)
        cur_open = await db.execute("SELECT COUNT(*) as count FROM tickets WHERE status != 'Resolved'")
        open_issues = (await cur_open.fetchone())["count"]

        # Count active opportunities (Leads with Warm status)
        cur_opps = await db.execute(
            "SELECT COUNT(*) as count FROM nodes WHERE label = 'Lead' AND properties LIKE '%Warm%'"
        )
        opportunities = (await cur_opps.fetchone())["count"]

        # Risks count: tickets that are Escalated
        cur_esc = await db.execute("SELECT COUNT(*) as count FROM tickets WHERE status = 'Escalated'")
        risks = (await cur_esc.fetchone())["count"]

        # Vendor delays: simulated/recorded delays
        cur_delays = await db.execute(
            "SELECT COUNT(*) as count FROM tickets WHERE category = 'Vendor Intelligence' AND status = 'Open'"
        )
        vendor_delays = (await cur_delays.fetchone())["count"]

        # Meetings today
        meetings = 3

        return {
            "opportunities": opportunities,
            "risks": risks,
            "issues": open_issues,
            "delays": vendor_delays,
            "meetings": meetings,
        }
