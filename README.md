# ⚡ ProcureAI - Enterprise AI Procurement & Vendor Intelligence Engine

An enterprise-grade autonomous AI Procurement Agent & **Vendor Intelligence Engine** powered by **Caspian SDK**, orchestrating multi-channel procurement across **Telegram**, **Corporate Email**, and a real-time **Web Management Dashboard**.

---

## 🌟 Core System Capabilities

### 1. Multi-Turn AI Requirement Collection Agent
- Ingests natural language requests from Telegram, Email, or the Web Sandbox.
- Extracts **Product Name, Quantity, Budget, Delivery Timeline, and Technical Specifications**.
- Detects missing mandatory information and formulates intelligent conversational follow-up questions.
- Converts conversational dialogue into standardized JSON payloads and creates sequential IDs: `PROC-2026-001`.

```json
{
  "product": "Laptop",
  "quantity": 100,
  "budget": 4500000,
  "delivery_days": 10,
  "specifications": [
    "i5 13th Gen",
    "16GB DDR5 RAM",
    "512GB NVMe SSD"
  ]
}
```

---

### 2. Enterprise-Grade Vendor Intelligence Engine

#### 🔍 1. Vendor Discovery Agent
- Searches internal supplier database and external provider catalogs matching specifications and volume.
- Tracks: `Vendor Name`, `Contact Email`, `Rating`, `Past Performance`, `Product Categories`, `Certifications`.

#### 📊 2. Quotation Analysis Agent
- Normalizes multi-vendor quotes (Price, Delivery Speed, Warranty, Vendor Rating, Reliability Index).
- Calculates market average price and price deviation percentages.
- Generates comprehensive comparison matrices.

#### 🧮 3. 4-Factor Weighted Vendor Scoring Engine
Calculates composite scores ($0 - 100$) using the precise weighting formula:
$$\text{Final Score} = (0.40 \times \text{Price Score}) + (0.25 \times \text{Delivery Score}) + (0.20 \times \text{Reliability Score}) + (0.15 \times \text{Warranty Score})$$

```json
[
  {
    "vendor": "Dell Partner (Enterprise Solutions)",
    "score": 99,
    "rank": 1,
    "is_recommended": true
  },
  {
    "vendor": "HP Commercial Direct",
    "score": 78,
    "rank": 2,
    "is_recommended": false
  }
]
```

#### 🤝 4. Autonomous Negotiation Agent
- Generates professional counter-offer emails automatically with competitive leverage.
- Tracks lifecycle: `Sent` $\longrightarrow$ `Replied` $\longrightarrow$ `Improved Offer`.
- Quantifies enterprise savings achieved through negotiation rounds.

#### ⚠️ 5. Multi-Factor Vendor Risk Detection
Flags:
- **Price Anomalies / Dumping:** Alerts when bids are $\ge 25\%$ lower than market average (*e.g., "Risk Level: Medium - Price is 35% lower than market average"*).
- **Missing Certifications:** Identifies uncertified suppliers or missing OEM Tier-1 credentials.
- **Historical Performance Gaps:** Detects low vendor ratings ($< 3.8$) and fulfillment delays.
- **Lead-Time Risks:** Flags delivery timelines exceeding project deadlines.

#### 🏆 6. Supplier Recommendation Engine
- Synthesizes composite scores, warranty coverage, and compliance risk flags to recommend the optimal supplier.

#### 📑 7. Executive Reporting Engine
- Generates 3 markdown/HTML downloadable reports:
  1. **Vendor Comparison Report**
  2. **Negotiation Intelligence Report**
  3. **Final Recommendation Report**

---

## 📡 REST API Reference

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/vendors/search` | Discover matching vendors from supplier catalog |
| `POST` | `/quotes/analyze` | Multi-quote comparative analysis and normalization |
| `POST` | `/vendors/score` | Compute 4-factor scores ($40\%/25\%/20\%/15\%$) |
| `POST` | `/vendors/negotiate` | Launch AI counter-offer email & track concession |
| `POST` | `/vendors/recommend` | Generate optimal supplier recommendation |
| `GET` | `/vendors` | List supplier directory with certifications & ratings |
| `GET` | `/negotiations` | Retrieve all active and completed negotiation rounds |
| `GET` | `/reports/comparison` | Generate Vendor Comparison Markdown Report |
| `GET` | `/reports/negotiation` | Generate Negotiation Intelligence Report |
| `GET` | `/procurements` | List all procurement tickets (filter by status/channel) |
| `GET` | `/procurement/{id}` | Get ticket details, vendor bids, and audit trail |
| `POST` | `/procurement/{id}/approve` | Manager approval authorization |
| `POST` | `/procurement/{id}/reject` | Decline procurement request |
| `POST` | `/api/channels/simulate-message` | Inbound simulator for Telegram & Email |
| `GET` | `/api/stats` | Executive KPI analytics & cost savings |

---

## 🚀 Quick Start

### 1. Installation

```bash
git clone https://github.com/KhushiTrivediii/caspin-agent.git
cd caspin-agent
pip install -r requirements.txt
```

### 2. Start the Server

```bash
python -m backend.main
```

Open dashboard at:
👉 **[http://localhost:8000](http://localhost:8000)**

---

## 🧪 Automated Testing

Run the full verification test suites:

```bash
# Test Core Procurement Agent (6/6)
python test_procurement_agent.py

# Test Vendor Intelligence Engine (6/6)
python test_vendor_intelligence.py
```

---

## 📄 License
MIT License
