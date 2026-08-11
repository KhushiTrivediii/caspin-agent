import re
import json
import uuid
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
from backend.models import (
    ProcurementRequirement,
    ExtractionResult,
    VendorQuote,
    ProcurementTicket,
    ProcurementStatus,
    ChannelType,
)


class AIEngine:
    """
    Enterprise AI Procurement Engine.
    Handles Natural Language Requirement Extraction, Missing Information Detection,
    Contextual Follow-up Question Generation, Vendor Quotation Matching,
    and Executive Approval Justifications.
    """

    def __init__(self):
        pass

    def parse_budget(self, text: str) -> Optional[float]:
        """Extract monetary budget amount supporting Lakhs, Crores, K, M, and plain numbers."""
        text_lower = text.lower()

        # Check for Lakhs / Lacs (e.g. 45 lakh, 41.5 lakhs, 45L, ₹45 lakh)
        lakh_match = re.search(r'(?:₹|rs\.?|inr)?\s*([0-9]+(?:\.[0-9]+)?)\s*(?:lakhs?|lacs?|lac|l\b)', text_lower)
        if lakh_match:
            try:
                return float(lakh_match.group(1)) * 100000.0
            except ValueError:
                pass

        # Check for Crores (e.g. 1.2 crore, 2 cr)
        cr_match = re.search(r'(?:₹|rs\.?|inr)?\s*([0-9]+(?:\.[0-9]+)?)\s*(?:crores?|cr\b)', text_lower)
        if cr_match:
            try:
                return float(cr_match.group(1)) * 10000000.0
            except ValueError:
                pass

        # Check for Millions (e.g. $1.5M, 2 million)
        mil_match = re.search(r'(?:\$|usd|€|eur)?\s*([0-9]+(?:\.[0-9]+)?)\s*(?:million|m\b)', text_lower)
        if mil_match:
            try:
                return float(mil_match.group(1)) * 1000000.0
            except ValueError:
                pass

        # Check for Thousands (e.g. 50k, 50 thousand)
        k_match = re.search(r'(?:₹|\$|rs\.?)?\s*([0-9]+(?:\.[0-9]+)?)\s*(?:k\b|thousand)', text_lower)
        if k_match:
            try:
                return float(k_match.group(1)) * 1000.0
            except ValueError:
                pass

        # Direct currency pattern e.g. ₹ 4500000 or budget of 4500000 or 4,50,000
        budget_match = re.search(r'(?:budget|cost|price|max|under|approx|around)?\s*(?:₹|\$|rs\.?|inr|usd)?\s*([0-9]{1,3}(?:,[0-9]{2,3})+|[0-9]{4,10})', text_lower)
        if budget_match:
            val_str = budget_match.group(1).replace(',', '')
            try:
                val = float(val_str)
                if val >= 100:  # Sensible minimum budget threshold
                    return val
            except ValueError:
                pass

        return None

    def parse_quantity(self, text: str) -> Optional[int]:
        """Extract item quantity from text."""
        # e.g. "100 laptops", "50 units", "qty 20", "need 10 servers", "quantity: 5"
        patterns = [
            r'(?:qty|quantity|count|need|procure|buy|order)?\s*[:=\-]?\s*([0-9]+)\s*(?:units?|pcs?|pieces?|nos?|items?|laptops?|desktops?|monitors?|chairs?|servers?|licenses?|keyboards?|printers?|macbooks?)',
            r'(?:need|order|buy|get|purchase|procure)\s+([0-9]+)\b',
            r'\b([0-9]+)\s+(?:units|pieces|pcs|laptops|servers|chairs|monitors|devices|systems|nodes)\b',
            r'(?:quantity|qty)\s*[:=\-]?\s*([0-9]+)',
        ]
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                try:
                    qty = int(match.group(1))
                    if 0 < qty < 1000000:
                        return qty
                except ValueError:
                    pass
        return None

    def parse_delivery_timeline(self, text: str) -> Optional[int]:
        """Extract delivery timeline in days."""
        text_lower = text.lower()
        # Days pattern
        days_match = re.search(r'([0-9]+)\s*(?:business\s*days?|working\s*days?|days?|d\b)', text_lower)
        if days_match:
            try:
                return int(days_match.group(1))
            except ValueError:
                pass

        # Weeks pattern
        weeks_match = re.search(r'([0-9]+)\s*(?:weeks?|wks?|w\b)', text_lower)
        if weeks_match:
            try:
                return int(weeks_match.group(1)) * 7
            except ValueError:
                pass

        # Months pattern
        months_match = re.search(r'([0-9]+)\s*(?:months?|mths?|m\b)', text_lower)
        if months_match:
            try:
                return int(months_match.group(1)) * 30
            except ValueError:
                pass

        if "urgent" in text_lower or "asap" in text_lower or "immediate" in text_lower:
            return 3

        return None

    def parse_product_name(self, text: str) -> Optional[str]:
        """Extract primary product or category name."""
        known_products = [
            ("MacBook Pro", r"\b(macbook\s*pro|macbooks?|apple\s*laptop)\b"),
            ("Laptop", r"\b(laptops?|notebooks?|thinkpads?|latitude|dell\s*xps)\b"),
            ("Desktop Computer", r"\b(desktops?|workstations?|all-in-one|pc\s*systems?)\b"),
            ("Server", r"\b(servers?|rack\s*servers?|blade\s*servers?)\b"),
            ("Monitor", r"\b(monitors?|displays?|4k\s*screens?|oled\s*display)\b"),
            ("Office Chair", r"\b(chairs?|office\s*chairs?|ergonomic\s*chairs?|desk\s*chairs?)\b"),
            ("Standing Desk", r"\b(standing\s*desks?|height\s*adjustable\s*desks?|desks?)\b"),
            ("Cloud License", r"\b(licenses?|software\s*licenses?|saas\s*subscriptions?|aws\s*credits?)\b"),
            ("Network Switch", r"\b(switches?|network\s*switches?|routers?|firewalls?)\b"),
            ("Printer", r"\b(printers?|laserjet|photocopiers?)\b"),
            ("Keyboard & Mouse", r"\b(keyboards?|mice|mouse|peripherals)\b"),
        ]

        for canonical_name, pattern in known_products:
            if re.search(pattern, text, re.IGNORECASE):
                return canonical_name

        # Fallback heuristic: look for "need/buy/procure <something>"
        match = re.search(r'(?:need|procure|buy|purchase|order)\s+(?:[0-9]+\s+)?([A-Za-z0-9\s\-]{3,30}?)(?:\.|\,|$|\bwith\b|\bfor\b|\bundert\b|\bbudget\b)', text, re.IGNORECASE)
        if match:
            candidate = match.group(1).strip()
            candidate = re.sub(r'^(a|an|the|some|units\s+of)\s+', '', candidate, flags=re.IGNORECASE).strip()
            if candidate and len(candidate) >= 3 and not candidate.isdigit():
                return candidate.title()

        return None

    def parse_specifications(self, text: str, product_name: Optional[str] = None) -> List[str]:
        """Extract technical specifications from text or prompt."""
        specs = []

        # Common hardware specifications patterns
        patterns = [
            r'\b(i[3579](?:-[0-9]{4,5}[A-Z]*)?|core\s*i[3579]|ryzen\s*[3579]|m[1234](?:\s*(?:pro|max|ultra))?|xeon|epyc)\b',
            r'\b([0-9]{1,3}\s*(?:gb|tb)\s*(?:ram|memory|ddr[45]))\b',
            r'\b([0-9]{1,3}\s*(?:gb|tb)\s*(?:ssd|nvme|hdd|storage))\b',
            r'\b(rtx\s*[0-9]{4}(?:\s*ti)?|geforce|radeon|gpu)\b',
            r'\b([0-9]{2}(?:\.[0-9])?["\']\s*(?:inch|4k|fhd|qhd|oled|ips|120hz|144hz|display))\b',
            r'\b(ergonomic|lumbar\s*support|height\s*adjustable|mesh\s*back|leather)\b',
            r'\b(windows\s*11\s*pro|ubuntu|macos|enterprise\s*edition)\b',
            r'\b(3-year\s*warranty|on-site\s*warranty|accidental\s*damage\s*protection)\b',
        ]

        for p in patterns:
            matches = re.finditer(p, text, re.IGNORECASE)
            for m in matches:
                matched_str = m.group(0).strip()
                if matched_str and matched_str not in specs:
                    specs.append(matched_str)

        # Look for explicit spec lists like "with i5, 16GB RAM, 512GB SSD"
        spec_clause = re.search(r'(?:with|specs?:?|specifications?:?)\s+([^\.\n]+)', text, re.IGNORECASE)
        if spec_clause:
            items = [item.strip() for item in re.split(r'[,;+&]', spec_clause.group(1)) if item.strip()]
            for item in items:
                # filter out budget / delivery mentions
                if not any(k in item.lower() for k in ['budget', 'day', 'week', 'lakh', 'cost', 'price']):
                    if item not in specs and len(item) > 1:
                        specs.append(item)

        # Default specs if product is known but specs empty
        if not specs and product_name:
            if "Laptop" in product_name:
                specs = ["Core i5 / Ryzen 5", "16GB RAM", "512GB SSD", "14-inch FHD Display"]
            elif "Server" in product_name:
                specs = ["Dual Intel Xeon", "64GB ECC RAM", "2x 1TB NVMe SSD", "Redundant PSU"]
            elif "Chair" in product_name:
                specs = ["Ergonomic Lumbar Support", "Adjustable Armrests", "High Density Mesh"]

        return specs

    def process_message(
        self,
        text: str,
        current_state: Optional[Dict[str, Any]] = None,
        channel: ChannelType = ChannelType.TELEGRAM,
        sender_id: Optional[str] = None,
        sender_name: Optional[str] = None,
        sender_email: Optional[str] = None,
    ) -> ExtractionResult:
        """
        Multi-turn requirement processing. Merges incoming message with previous state,
        identifies missing fields, and generates intelligent follow-ups.
        """
        state = current_state.copy() if current_state else {}

        # Extract components from current message
        parsed_product = self.parse_product_name(text)
        parsed_quantity = self.parse_quantity(text)
        parsed_budget = self.parse_budget(text)
        parsed_delivery = self.parse_delivery_timeline(text)
        parsed_specs = self.parse_specifications(text, parsed_product or state.get("product"))

        # Merge with existing state (new non-null values overwrite old)
        if parsed_product:
            state["product"] = parsed_product
        if parsed_quantity:
            state["quantity"] = parsed_quantity
        if parsed_budget:
            state["budget"] = parsed_budget
        if parsed_delivery:
            state["delivery_days"] = parsed_delivery
        if parsed_specs:
            existing_specs = state.get("specifications", [])
            merged_specs = list(dict.fromkeys(existing_specs + parsed_specs))
            state["specifications"] = merged_specs

        # Check required fields
        missing_fields = []
        if not state.get("product"):
            missing_fields.append("Product Name")
        if not state.get("quantity"):
            missing_fields.append("Quantity")
        if not state.get("budget"):
            missing_fields.append("Budget")
        if not state.get("delivery_days"):
            missing_fields.append("Delivery Timeline")

        is_complete = len(missing_fields) == 0

        # Construct follow-up question if incomplete
        follow_up_question = None
        if not is_complete:
            follow_up_question = self._generate_follow_up(missing_fields, state)

        requirement = ProcurementRequirement(
            product=state.get("product"),
            quantity=state.get("quantity"),
            budget=state.get("budget"),
            currency=state.get("currency", "INR"),
            delivery_days=state.get("delivery_days"),
            specifications=state.get("specifications", []),
            requester_id=sender_id,
            requester_name=sender_name,
            requester_email=sender_email,
            channel=channel,
            raw_prompt=text,
        )

        return ExtractionResult(
            is_complete=is_complete,
            requirement=requirement,
            missing_fields=missing_fields,
            follow_up_question=follow_up_question,
            confidence=0.95 if is_complete else 0.75,
        )

    def _generate_follow_up(self, missing_fields: List[str], current_state: Dict[str, Any]) -> str:
        """Formulate natural conversational follow-up questions."""
        has_product = current_state.get("product")
        has_quantity = current_state.get("quantity")

        if len(missing_fields) == 2 and "Budget" in missing_fields and "Delivery Timeline" in missing_fields:
            if has_product and has_quantity:
                return f"Got it! To proceed with procuring {has_quantity} {has_product}s, what is your budget and required delivery timeline?"
            return "What is your budget and required delivery timeline?"

        if len(missing_fields) == 1:
            field = missing_fields[0]
            if field == "Budget":
                return f"What is your total estimated budget for this procurement?"
            elif field == "Delivery Timeline":
                return f"By when do you need these delivered (in days or weeks)?"
            elif field == "Quantity":
                return f"How many units of {has_product or 'the item'} do you require?"
            elif field == "Product Name":
                return f"Could you please specify which product or equipment you want to procure?"

        # Multiple missing
        fields_str = " and ".join([", ".join(missing_fields[:-1]), missing_fields[-1]] if len(missing_fields) > 1 else missing_fields)
        return f"Could you please provide the missing details: {fields_str}?"

    def generate_vendor_quotes(self, ticket: ProcurementRequirement, ticket_id: str) -> List[VendorQuote]:
        """
        Simulate competitive vendor quotes based on product, budget, and quantity.
        Calculates savings and marks the optimal recommendation.
        """
        budget = ticket.budget or 100000.0
        delivery_days = ticket.delivery_days or 10
        product = ticket.product or "Laptop"

        # Define vendor profiles
        vendor_configs = [
            {
                "vendor_name": "Dell Partner (Enterprise Solutions)",
                "price_multiplier": 0.922,  # ~7.8% savings
                "delivery_offset": -3 if delivery_days > 5 else -1,
                "rating": 4.8,
                "warranty_years": 3,
                "notes": "Includes 3-Year ProSupport Onsite Next Business Day & Volume Enterprise Discount.",
            },
            {
                "vendor_name": "HP Commercial Direct",
                "price_multiplier": 0.960,  # 4% savings
                "delivery_offset": -1 if delivery_days > 4 else 0,
                "rating": 4.6,
                "warranty_years": 3,
                "notes": "Standard HP CarePack Onsite 3-Year Support included.",
            },
            {
                "vendor_name": "Lenovo Premier Partner",
                "price_multiplier": 0.978,  # 2.2% savings
                "delivery_offset": -2 if delivery_days > 5 else 0,
                "rating": 4.5,
                "warranty_years": 3,
                "notes": "Includes Lenovo Premier Support and bulk packaging.",
            },
        ]

        quotes = []
        for i, config in enumerate(vendor_configs):
            quoted_price = round(budget * config["price_multiplier"], 2)
            quoted_delivery = max(2, delivery_days + config["delivery_offset"])
            savings_amt = round(budget - quoted_price, 2)
            savings_pct = round((savings_amt / budget) * 100.0, 1)

            is_best = (i == 0)  # Dell Partner is top recommended

            quotes.append(
                VendorQuote(
                    id=f"QUOTE-{uuid.uuid4().hex[:8].upper()}",
                    procurement_id=ticket_id,
                    vendor_name=config["vendor_name"],
                    price=quoted_price,
                    currency=ticket.currency,
                    delivery_days=quoted_delivery,
                    specs_matched=ticket.specifications,
                    rating=config["rating"],
                    warranty_years=config["warranty_years"],
                    savings_amount=savings_amt,
                    savings_percentage=savings_pct,
                    is_recommended=is_best,
                    quote_notes=config["notes"],
                )
            )

        return quotes

    def format_currency_inr(self, amount: float) -> str:
        """Format number into Lakh / Crore or comma-separated Indian currency format."""
        if amount >= 10000000:
            return f"₹{amount / 10000000:.2f} Crore"
        elif amount >= 100000:
            return f"₹{amount / 100000:.2f} Lakh"
        else:
            return f"₹{amount:,.2f}"

    def generate_approval_prompt(self, ticket: ProcurementTicket) -> str:
        """
        Generate manager approval prompt matching the required specification:
        Recommended Vendor: Dell Partner
        Price: ₹41.5 lakh
        Delivery: 7 Days

        Approve or Reject?
        """
        vendor = ticket.recommended_vendor or "Dell Partner"
        price_str = self.format_currency_inr(ticket.recommended_price or ticket.budget)
        delivery = f"{ticket.recommended_delivery_days or ticket.delivery_days} Days"

        prompt = (
            f"🔔 *Procurement Approval Request* [{ticket.id}]\n\n"
            f"📦 *Product:* {ticket.quantity}x {ticket.product}\n"
            f"🏢 *Recommended Vendor:* {vendor}\n"
            f"💰 *Price:* {price_str} (Budget: {self.format_currency_inr(ticket.budget)})\n"
            f"🚚 *Delivery:* {delivery}\n"
            f"📋 *Specs:* {', '.join(ticket.specifications[:4]) if ticket.specifications else 'Standard'}\n\n"
            f"Approve or Reject?"
        )
        return prompt

    def generate_email_summary(self, ticket: ProcurementTicket) -> Tuple[str, str, str]:
        """Generate subject, text, and rich HTML summary for Email."""
        subject = f"[Procurement] {ticket.id} - Recommendation for {ticket.quantity}x {ticket.product}"
        vendor = ticket.recommended_vendor or "Dell Partner"
        price_str = self.format_currency_inr(ticket.recommended_price or ticket.budget)
        budget_str = self.format_currency_inr(ticket.budget)

        text_body = (
            f"Procurement Ticket: {ticket.id}\n"
            f"Product: {ticket.quantity}x {ticket.product}\n"
            f"Status: {ticket.status.value}\n"
            f"Recommended Vendor: {vendor}\n"
            f"Quoted Price: {price_str} (Budget: {budget_str})\n"
            f"Delivery Timeline: {ticket.recommended_delivery_days} Days\n\n"
            f"Please respond with 'APPROVE' or 'REJECT' or review on the management dashboard."
        )

        html_body = f"""
        <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px; border: 1px solid #e2e8f0; border-radius: 8px;">
            <h2 style="color: #1e293b; border-bottom: 2px solid #3b82f6; padding-bottom: 8px;">Procurement Recommendation Report</h2>
            <p><strong>Ticket ID:</strong> <span style="background: #e0f2fe; color: #0369a1; padding: 2px 8px; border-radius: 4px;">{ticket.id}</span></p>
            <p><strong>Item:</strong> {ticket.quantity}x {ticket.product}</p>
            <p><strong>Requester:</strong> {ticket.requester_name or 'Employee'} ({ticket.channel.value.title()})</p>
            
            <div style="background: #f8fafc; border: 1px solid #cbd5e1; border-radius: 6px; padding: 16px; margin: 16px 0;">
                <h3 style="margin-top: 0; color: #0f172a;">Recommended Vendor: {vendor}</h3>
                <table style="width: 100%; border-collapse: collapse;">
                    <tr><td style="padding: 4px 0; color: #64748b;">Quoted Price:</td><td style="padding: 4px 0; font-weight: bold; color: #059669;">{price_str}</td></tr>
                    <tr><td style="padding: 4px 0; color: #64748b;">Total Budget:</td><td style="padding: 4px 0;">{budget_str}</td></tr>
                    <tr><td style="padding: 4px 0; color: #64748b;">Delivery Days:</td><td style="padding: 4px 0;">{ticket.recommended_delivery_days} Days</td></tr>
                </table>
            </div>

            <p style="font-size: 14px; color: #475569;">To authorize this order, reply <strong>APPROVE</strong> or <strong>REJECT</strong> to this email, or review via Telegram bot.</p>
        </div>
        """
        return subject, text_body, html_body


# Global singleton instance
ai_engine = AIEngine()
