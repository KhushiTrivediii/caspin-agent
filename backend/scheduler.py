import logging
import asyncio
import datetime
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from backend.database import list_tickets, update_ticket_status, log_audit_action, get_kpi_stats
from backend.models import TicketStatus, IncidentCategory
from backend.caspian_service import caspian_service

logger = logging.getLogger("scheduler")


class SchedulerService:
    """
    BLACKBOX Background Operations Monitor.
    Runs periodic scans for SLA breaches and distributes alerts.
    """

    def __init__(self):
        self.scheduler = AsyncIOScheduler()
        self.started = False

    def start(self):
        if self.started:
            return
        self.scheduler.start()
        self.started = True
        logger.info("BLACKBOX background operations scheduler started.")
        self.register_jobs()

    def shutdown(self):
        if self.started:
            self.scheduler.shutdown()
            self.started = False
            logger.info("BLACKBOX background scheduler shut down.")

    def register_jobs(self):
        # 1. SLA Breach Monitor: runs every 5 seconds to scan for stalled tickets (demo safety)
        self.scheduler.add_job(
            func=self.scan_sla_breaches,
            trigger=IntervalTrigger(seconds=8),
            id="sla_breach_monitor",
            name="SLA Breach Monitor",
            replace_existing=True,
        )

    async def scan_sla_breaches(self):
        """
        Identify open, unassigned tickets that exceed 15 seconds (for demo quick testing)
        and automatically escalate to the founder's Telegram.
        """
        logger.info("[Scheduler] Scanning for operations SLA breaches...")
        now = datetime.datetime.utcnow()
        
        try:
            tickets = await list_tickets(status=TicketStatus.OPEN.value)
            for ticket in tickets:
                # check if unassigned and created more than 15 seconds ago
                time_open = (now - ticket.created_at).total_seconds()
                
                # Check for community bug ticket
                if not ticket.assigned_to and time_open >= 15.0 and ticket.category == IncidentCategory.COMMUNITY_INTELLIGENCE:
                    logger.warning(f"SLA Breach detected on ticket {ticket.id}. Escalating to manager...")
                    
                    escalation_text = (
                        f"⚠️ *SLA ESCALATION ALERT* [{ticket.id}]\n\n"
                        f"The Discord community bug report '{ticket.description}' has been unassigned for over 15 seconds.\n"
                        f"Would you like to assign this task to Bob (Backend) or Alice (DevOps)?"
                    )
                    buttons_list = [
                        {"text": "Assign Bob", "value": f"ASSIGN dev_bob {ticket.id}"},
                        {"text": "Assign Alice", "value": f"ASSIGN dev_alice {ticket.id}"},
                    ]
                    await caspian_service.send_message(
                        channel=caspian_service.ChannelType.TELEGRAM,
                        recipient_id="founder_tg",
                        conversation_id=f"esc_{ticket.id}",
                        text=escalation_text,
                        ticket_id=ticket.id,
                        buttons_list=buttons_list,
                    )
                    
                    # Update status to Escalated
                    await update_ticket_status(ticket.id, TicketStatus.ESCALATED)
                    await log_audit_action(
                        ticket.id, 
                        "SLA_ESCALATED", 
                        "BLACKBOX", 
                        "Ticket unassigned for over 15 seconds. Escalated to founder."
                    )
                    
                    # Realtime notification
                    from backend.realtime import realtime_manager
                    await realtime_manager.emit_ticket_update(ticket.id, "escalated", {
                        "ticket_id": ticket.id,
                        "title": ticket.title,
                        "status": "Escalated",
                    })
        except Exception as e:
            logger.error(f"Error scanning SLA breaches: {e}")

    def get_jobs_status(self):
        """Return status logs of registered scheduler tasks."""
        jobs = []
        for job in self.scheduler.get_jobs():
            jobs.append({
                "id": job.id,
                "name": job.name,
                "next_run_time": job.next_run_time.isoformat() if job.next_run_time else None,
                "pending": job.pending,
            })
        return jobs


# Global singleton instance
scheduler_service = SchedulerService()
