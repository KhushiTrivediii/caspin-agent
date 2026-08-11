import os
import sys
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from dotenv import load_dotenv

load_dotenv()

from backend.database import init_db, list_procurements, create_procurement
from backend.models import (
    ProcurementTicket,
    ProcurementStatus,
    ChannelType,
)
from backend.ai_engine import ai_engine
from backend.api import router as api_router
from backend.caspian_service import caspian_service

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("main")


async def seed_initial_demo_data():
    """Seed initial sample procurements so dashboard is populated on first launch."""
    existing = await list_procurements(limit=5)
    if existing:
        return

    logger.info("Seeding initial enterprise demo procurement tickets...")

    # Seed Sample 1: Laptops (Approval Pending)
    ticket_id_1 = "PROC-2026-001"
    req_1 = type("Req", (), {
        "product": "Laptop",
        "quantity": 100,
        "budget": 4500000.0,
        "currency": "INR",
        "delivery_days": 10,
        "specifications": ["Intel Core i5 13th Gen", "16GB DDR5 RAM", "512GB NVMe SSD", "14-inch FHD IPS", "3-Year Onsite Warranty"],
        "requester_name": "Sarah Chen",
        "requester_email": "sarah.chen@enterprise.internal",
        "channel": ChannelType.TELEGRAM,
    })()
    quotes_1 = ai_engine.generate_vendor_quotes(req_1, ticket_id_1)
    rec_1 = quotes_1[0]

    t1 = ProcurementTicket(
        id=ticket_id_1,
        title="100x Laptop Engineering Refresh",
        product="Laptop",
        quantity=100,
        budget=4500000.0,
        currency="INR",
        delivery_days=10,
        specifications=req_1.specifications,
        status=ProcurementStatus.APPROVAL_PENDING,
        current_stage="Approval Pending",
        requester_name="Sarah Chen (Engineering Lead)",
        requester_email="sarah.chen@enterprise.internal",
        channel=ChannelType.TELEGRAM,
        recommended_vendor=rec_1.vendor_name,
        recommended_price=rec_1.price,
        recommended_delivery_days=rec_1.delivery_days,
        quotes=quotes_1,
        summary="Requirement gathered via Telegram. Recommended Dell Partner offering ₹41.50 Lakh with 7-day express delivery (₹3.5 Lakh savings).",
    )
    await create_procurement(t1)

    # Seed Sample 2: Office Ergonomic Chairs (Approved)
    ticket_id_2 = "PROC-2026-002"
    req_2 = type("Req", (), {
        "product": "Office Chair",
        "quantity": 50,
        "budget": 750000.0,
        "currency": "INR",
        "delivery_days": 14,
        "specifications": ["Ergonomic Lumbar Support", "3D Adjustable Armrests", "High Breathability Mesh", "BIFMA Certified"],
        "requester_name": "David Miller",
        "requester_email": "david.miller@enterprise.internal",
        "channel": ChannelType.EMAIL,
    })()
    quotes_2 = ai_engine.generate_vendor_quotes(req_2, ticket_id_2)
    rec_2 = quotes_2[0]

    t2 = ProcurementTicket(
        id=ticket_id_2,
        title="50x Ergonomic Workstation Chairs",
        product="Office Chair",
        quantity=50,
        budget=750000.0,
        currency="INR",
        delivery_days=14,
        specifications=req_2.specifications,
        status=ProcurementStatus.APPROVED,
        current_stage="Completed",
        requester_name="David Miller (Facilities Manager)",
        requester_email="david.miller@enterprise.internal",
        channel=ChannelType.EMAIL,
        recommended_vendor=rec_2.vendor_name,
        recommended_price=rec_2.price,
        recommended_delivery_days=rec_2.delivery_days,
        quotes=quotes_2,
        summary="Procured via Email workflow. Approved by VP of Operations.",
    )
    await create_procurement(t2)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Initializing SQLite database schema...")
    await init_db()
    await seed_initial_demo_data()
    logger.info("AI Procurement Agent backend ready.")
    yield
    # Shutdown


app = FastAPI(
    title="AI Procurement Agent API",
    description="Enterprise AI Procurement Agent powered by Caspian SDK",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount REST API router
app.include_router(api_router)

# Mount Webhook receiver for live Caspian SDK
@app.post("/webhook/caspian")
async def caspian_webhook(request: Request):
    """Webhook listener for live incoming messages from Caspian SDK."""
    try:
        body = await request.body()
        headers = dict(request.headers)
        if caspian_service.is_live and caspian_service.client:
            res = caspian_service.client.handle_webhook(body, headers=headers)
            return JSONResponse(status_code=res.status_code, content=res.json())
        return {"status": "ok", "mode": "sandbox"}
    except Exception as e:
        logger.error(f"Error handling Caspian webhook: {e}")
        return JSONResponse(status_code=500, content={"error": str(e)})


# Mount static frontend assets
static_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "static")
if os.path.exists(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

    @app.get("/")
    async def serve_index():
        return FileResponse(os.path.join(static_dir, "index.html"))


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    host = os.getenv("HOST", "0.0.0.0")
    uvicorn.run("backend.main:app", host=host, port=port, reload=True)
