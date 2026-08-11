"""
Enterprise Purchase Order (PO) Generator & ERP Data Export Engine.
Generates official corporate PO records, printable HTML purchase orders, and ERP CSV/JSON exports.
"""

import csv
import io
from datetime import datetime
from typing import List, Dict, Any, Optional
from backend.models import PurchaseOrder, PurchaseOrderItem, ProcurementTicket, ApprovalTier


class POGeneratorEngine:
    """Engine for generating and formatting corporate Purchase Orders & ERP exports."""

    def __init__(self):
        self._po_counter = 1

    def determine_approval_tier(self, budget: float) -> str:
        """
        Determines the required approval tier based on enterprise threshold rules:
        - <= 1 Lakh (100,000 INR): Tier 1 (Team Lead)
        - 1 Lakh to 10 Lakh (100,000 - 1,000,000 INR): Tier 2 (Department Manager)
        - > 10 Lakh (1,000,000+ INR): Tier 3 (VP Operations / CFO Escalation)
        """
        if budget <= 100000.0:
            return ApprovalTier.TIER_1_LEAD.value
        elif budget <= 1000000.0:
            return ApprovalTier.TIER_2_MANAGER.value
        else:
            return ApprovalTier.TIER_3_EXECUTIVE.value

    def generate_purchase_order(
        self,
        ticket: ProcurementTicket,
        approver_name: str = "Authorized Manager",
        vendor_email: Optional[str] = None,
    ) -> PurchaseOrder:
        """Creates a formal Purchase Order from an approved procurement ticket."""
        po_num = f"PO-2026-{self._po_counter:03d}"
        self._po_counter += 1

        unit_price = (ticket.recommended_price or ticket.budget) / max(ticket.quantity, 1)
        subtotal = ticket.recommended_price or ticket.budget
        tax_rate = 0.18  # 18% Standard GST / Corporate Tax
        tax_amount = subtotal * tax_rate
        total_amount = subtotal + tax_amount

        items = [
            PurchaseOrderItem(
                item_description=f"{ticket.product} ({', '.join(ticket.specifications) if ticket.specifications else 'Standard Specifications'})",
                quantity=ticket.quantity,
                unit_price=round(unit_price, 2),
                total_price=round(subtotal, 2),
            )
        ]

        email = vendor_email or f"enterprise.orders@{ticket.recommended_vendor.lower().replace(' ', '')[:12]}.com" if ticket.recommended_vendor else "procurement@enterprise.com"

        return PurchaseOrder(
            po_number=po_num,
            procurement_id=ticket.id,
            vendor_name=ticket.recommended_vendor or "Selected Supplier",
            vendor_email=email,
            items=items,
            subtotal=round(subtotal, 2),
            tax_rate=tax_rate,
            tax_amount=round(tax_amount, 2),
            total_amount=round(total_amount, 2),
            delivery_timeline_days=ticket.delivery_days,
            payment_terms="Net 30 Days from receipt of goods & invoice verification",
            shipping_address="Enterprise Technology Center, 4th Floor, Tech Boulevard, Bangalore 560100",
            status="Issued & Authorized",
            approved_by=approver_name,
            created_at=datetime.utcnow(),
        )

    def generate_po_html(self, po: PurchaseOrder, ticket: ProcurementTicket) -> str:
        """Generates a professional, printable HTML Purchase Order invoice document."""
        item_rows = "".join([
            f"""
            <tr>
                <td style="padding: 12px 14px; border-bottom: 1px solid #e2e8f0;">{item.item_description}</td>
                <td style="padding: 12px 14px; border-bottom: 1px solid #e2e8f0; text-align: center;">{item.quantity}</td>
                <td style="padding: 12px 14px; border-bottom: 1px solid #e2e8f0; text-align: right; font-family: monospace;">₹{item.unit_price:,.2f}</td>
                <td style="padding: 12px 14px; border-bottom: 1px solid #e2e8f0; text-align: right; font-family: monospace; font-weight: 700;">₹{item.total_price:,.2f}</td>
            </tr>
            """
            for item in po.items
        ])

        return f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <title>Official Purchase Order - {po.po_number}</title>
            <style>
                body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; color: #0f172a; line-height: 1.5; padding: 30px; background: #ffffff; }}
                .po-card {{ max-width: 800px; margin: 0 auto; border: 1px solid #cbd5e1; border-radius: 8px; padding: 36px; }}
                .header-flex {{ display: flex; justify-content: space-between; border-bottom: 2px solid #0f172a; padding-bottom: 18px; margin-bottom: 24px; }}
                .meta-grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 24px; margin-bottom: 24px; }}
                .table-po {{ width: 100%; border-collapse: collapse; margin-bottom: 24px; }}
                .table-po th {{ background: #0f172a; color: #ffffff; padding: 10px 14px; text-align: left; font-size: 13px; }}
                .summary-box {{ margin-left: auto; width: 320px; }}
                .summary-line {{ display: flex; justify-content: space-between; padding: 6px 0; font-size: 13px; }}
                .total-line {{ display: flex; justify-content: space-between; padding: 10px 0; border-top: 2px solid #0f172a; font-size: 16px; font-weight: 800; color: #0f172a; }}
                .stamp-box {{ display: inline-block; border: 2px solid #059669; color: #059669; padding: 6px 16px; font-weight: 800; text-transform: uppercase; font-size: 12px; border-radius: 4px; }}
                @media print {{ body {{ padding: 0; }} .po-card {{ border: none; padding: 0; }} }}
            </style>
        </head>
        <body>
            <div class="po-card">
                <div class="header-flex">
                    <div>
                        <h1 style="margin: 0; font-size: 24px; font-weight: 800; color: #0f172a;">PURCHASE ORDER</h1>
                        <div style="font-size: 13px; color: #64748b; margin-top: 4px;">Enterprise AI Procurement System</div>
                    </div>
                    <div style="text-align: right;">
                        <div style="font-family: monospace; font-size: 16px; font-weight: 800; color: #2563eb;">{po.po_number}</div>
                        <div style="font-size: 12px; color: #64748b;">Ref: {po.procurement_id}</div>
                        <div style="font-size: 12px; color: #64748b;">Date: {po.created_at.strftime('%d %b %Y')}</div>
                    </div>
                </div>

                <div class="meta-grid">
                    <div>
                        <div style="font-size: 11px; font-weight: 700; color: #64748b; text-transform: uppercase; margin-bottom: 4px;">Vendor / Supplier</div>
                        <div style="font-size: 14px; font-weight: 700; color: #0f172a;">{po.vendor_name}</div>
                        <div style="font-size: 13px; color: #475569;">Email: {po.vendor_email}</div>
                        <div style="font-size: 13px; color: #475569;">Payment Terms: {po.payment_terms}</div>
                    </div>
                    <div>
                        <div style="font-size: 11px; font-weight: 700; color: #64748b; text-transform: uppercase; margin-bottom: 4px;">Ship To & Deliver To</div>
                        <div style="font-size: 13px; color: #0f172a; line-height: 1.4;">{po.shipping_address}</div>
                        <div style="font-size: 13px; color: #475569; margin-top: 4px;">Target Lead Time: <b>{po.delivery_timeline_days} Calendar Days</b></div>
                    </div>
                </div>

                <table class="table-po">
                    <thead>
                        <tr>
                            <th>Item Description</th>
                            <th style="text-align: center;">Qty</th>
                            <th style="text-align: right;">Unit Price</th>
                            <th style="text-align: right;">Total Amount</th>
                        </tr>
                    </thead>
                    <tbody>
                        {item_rows}
                    </tbody>
                </table>

                <div class="summary-box">
                    <div class="summary-line">
                        <span>Subtotal:</span>
                        <span style="font-family: monospace;">₹{po.subtotal:,.2f}</span>
                    </div>
                    <div class="summary-line">
                        <span>GST / Tax (18%):</span>
                        <span style="font-family: monospace;">₹{po.tax_amount:,.2f}</span>
                    </div>
                    <div class="total-line">
                        <span>Total Payable:</span>
                        <span style="font-family: monospace; color: #059669;">₹{po.total_amount:,.2f}</span>
                    </div>
                </div>

                <div style="margin-top: 36px; padding-top: 18px; border-top: 1px solid #e2e8f0; display: flex; justify-content: space-between; align-items: center;">
                    <div>
                        <div class="stamp-box">✓ AUTHORIZED & ISSUED</div>
                        <div style="font-size: 12px; color: #64748b; margin-top: 6px;">Approved By: <b>{po.approved_by}</b> ({ticket.approval_tier})</div>
                    </div>
                    <div style="text-align: right; font-size: 11px; color: #94a3b8;">
                        Generated automatically via Caspian AI Procurement Engine<br>
                        Digital Verification Hash: {po.po_number}-AUTH
                    </div>
                </div>
            </div>
        </body>
        </html>
        """

    def export_procurements_csv(self, tickets: List[ProcurementTicket]) -> str:
        """Exports procurement records as a CSV string compatible with ERP accounting imports."""
        output = io.StringIO()
        writer = csv.writer(output)

        # CSV Header
        writer.writerow([
            "Ticket ID",
            "PO Number",
            "Status",
            "Approval Tier",
            "Product",
            "Quantity",
            "Budget (INR)",
            "Quoted / Approved Price (INR)",
            "Recommended Vendor",
            "Delivery Days",
            "Channel",
            "Requester",
            "Created Date",
        ])

        for t in tickets:
            writer.writerow([
                t.id,
                t.po_number or "N/A",
                t.status.value if hasattr(t.status, "value") else str(t.status),
                t.approval_tier,
                t.product,
                t.quantity,
                f"{t.budget:.2f}",
                f"{(t.recommended_price or t.budget):.2f}",
                t.recommended_vendor or "Pending",
                t.delivery_days,
                t.channel.value if hasattr(t.channel, "value") else str(t.channel),
                t.requester_name,
                t.created_at.strftime("%Y-%m-%d %H:%M:%S") if hasattr(t.created_at, "strftime") else str(t.created_at),
            ])

        return output.getvalue()


# Singleton Instance
po_engine = POGeneratorEngine()
