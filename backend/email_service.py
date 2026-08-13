import os
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import aiosmtplib
from jinja2 import Template

logger = logging.getLogger("email_service")

# Sample simple HTML templates using Jinja2 syntax
APPROVAL_REQUEST_TEMPLATE = """
<html>
<body>
  <h2>Procurement Approval Request: {{ ticket_id }}</h2>
  <p>Hello Approver,</p>
  <p>A new procurement request has been submitted and requires your authorization.</p>
  <ul>
    <li><strong>Product:</strong> {{ product }}</li>
    <li><strong>Quantity:</strong> {{ quantity }}</li>
    <li><strong>Estimated Budget:</strong> Rs. {{ "%.2f" | format(budget) }}</li>
    <li><strong>Suggested Vendor:</strong> {{ recommended_vendor }} (Rs. {{ "%.2f" | format(recommended_price) }})</li>
    <li><strong>Department:</strong> {{ department }}</li>
  </ul>
  <p>Please review and act on this request in the dashboard.</p>
</body>
</html>
"""

PO_ISSUED_TEMPLATE = """
<html>
<body>
  <h2>Purchase Order Issued: {{ po_number }}</h2>
  <p>Dear Supplier,</p>
  <p>Please find attached Purchase Order {{ po_number }} for {{ quantity }}x {{ product }}.</p>
  <p><strong>Total Authorized Amount:</strong> Rs. {{ "%.2f" | format(total_amount) }} (including 18% GST)</p>
  <p>Please reply to confirm receipt and coordinate delivery.</p>
  <p>Regards,<br>Procurement Team</p>
</body>
</html>
"""

SLA_ALERT_TEMPLATE = """
<html>
<body>
  <h2>⚠️ SLA Breach Alert: {{ ticket_id }}</h2>
  <p>Attention Team,</p>
  <p>The procurement request {{ ticket_id }} for <strong>{{ product }}</strong> has spent over 24 hours in the <strong>{{ stage }}</strong> stage without approval/rejection decision.</p>
  <p>Please expedite this decision immediately to prevent fulfillment delays.</p>
</body>
</html>
"""

class EmailService:
    """
    Asynchronous SMTP service using aiosmtplib to transmit transactional procurement notifications.
    """
    def __init__(self):
        self.smtp_host = os.getenv("SMTP_HOST", "localhost").strip()
        self.smtp_port = int(os.getenv("SMTP_PORT", "1025"))
        self.smtp_username = os.getenv("SMTP_USERNAME", "").strip()
        self.smtp_password = os.getenv("SMTP_PASSWORD", "").strip()
        self.smtp_use_tls = os.getenv("SMTP_USE_TLS", "False").lower() in ("true", "1", "yes")
        self.sender_address = os.getenv("SENDER_ADDRESS", "no-reply@enterprise.internal").strip()

    async def send_html_email(self, recipient_email: str, subject: str, html_content: str):
        """Send an HTML email asynchronously. Fall back to logging if connection fails."""
        # Clean up recipient
        if not recipient_email or "@" not in recipient_email:
            logger.warning(f"Invalid email recipient: {recipient_email}. Skipping.")
            return

        message = MIMEMultipart("alternative")
        message["From"] = self.sender_address
        message["To"] = recipient_email
        message["Subject"] = subject
        message.attach(MIMEText(html_content, "html"))

        logger.info(f"[Email Engine] Sending email to {recipient_email} | Subject: {subject}")

        # In typical developer flow or sandbox, we log SMTP messages unless config exists
        # We will attempt SMTP send, and if it fails or uses default dummy host, we log it.
        if self.smtp_host in ("localhost", ""):
            logger.info(f"[Email Engine Sandbox] Simulated Email Sent to {recipient_email}:\nSubject: {subject}\nBody: {html_content[:300]}...")
            return

        try:
            await aiosmtplib.send(
                message,
                hostname=self.smtp_host,
                port=self.smtp_port,
                username=self.smtp_username or None,
                password=self.smtp_password or None,
                use_tls=self.smtp_use_tls,
            )
            logger.info(f"[Email Engine] Email successfully delivered to {recipient_email}")
        except Exception as e:
            logger.error(f"[Email Engine] Failed to transmit email via SMTP: {e}. (Logged to console)")
            logger.info(f"[Email Engine Fallback] Simulated Content:\nSubject: {subject}\nBody: {html_content[:300]}...")

    async def send_approval_request(self, recipient_email: str, ticket_id: str, product: str, quantity: int, budget: float, recommended_vendor: str, recommended_price: float, department: str):
        """Send manager approval alert."""
        template = Template(APPROVAL_REQUEST_TEMPLATE)
        html = template.render(
            ticket_id=ticket_id,
            product=product,
            quantity=quantity,
            budget=budget,
            recommended_vendor=recommended_vendor,
            recommended_price=recommended_price,
            department=department
        )
        await self.send_html_email(
            recipient_email=recipient_email,
            subject=f"ACTION REQUIRED: Approve Procurement {ticket_id}",
            html_content=html
        )

    async def send_po_notification(self, recipient_email: str, po_number: str, product: str, quantity: int, total_amount: float):
        """Send vendor PO copy."""
        template = Template(PO_ISSUED_TEMPLATE)
        html = template.render(
            po_number=po_number,
            product=product,
            quantity=quantity,
            total_amount=total_amount
        )
        await self.send_html_email(
            recipient_email=recipient_email,
            subject=f"Purchase Order {po_number} - Caspin Enterprise",
            html_content=html
        )

    async def send_sla_breach_alert(self, recipient_email: str, ticket_id: str, product: str, stage: str):
        """Send SLA breach alert."""
        template = Template(SLA_ALERT_TEMPLATE)
        html = template.render(
            ticket_id=ticket_id,
            product=product,
            stage=stage
        )
        await self.send_html_email(
            recipient_email=recipient_email,
            subject=f"⚠️ SLA BREACH: Procurement {ticket_id} Stalled",
            html_content=html
        )

# Global singleton email service
email_service = EmailService()
