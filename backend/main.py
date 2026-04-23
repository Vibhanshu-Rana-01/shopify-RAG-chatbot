"""
main.py
───────
FastAPI server for the Mobile Covers RAG Chatbot.

Endpoints:
  GET  /          → Health check
  POST /chat      → Send a message, receive an AI response
  POST /sync      → Re-sync products from Shopify (manual trigger)
  GET  /status    → Returns sync status and product count

Auto-sync:
  Products are re-synced from Shopify every SYNC_INTERVAL_HOURS hours
  using APScheduler — so your chatbot always reflects the latest catalog.
"""

import os
import sys
import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone

# Force UTF-8 output on Windows (fixes charmap emoji errors)
if sys.stdout.encoding != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from typing import Optional
from dotenv import load_dotenv
from apscheduler.schedulers.background import BackgroundScheduler

load_dotenv()

# ─────────────────────────────────────────────
# Config
# ─────────────────────────────────────────────
ALLOWED_ORIGINS      = os.getenv("ALLOWED_ORIGINS", "*").split(",")
SYNC_INTERVAL_HOURS  = int(os.getenv("SYNC_INTERVAL_HOURS", "6"))
SHOPIFY_STORE_URL    = os.getenv("SHOPIFY_STORE_URL", "")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger(__name__)

# ─────────────────────────────────────────────
# Sync state (simple in-memory tracker)
# ─────────────────────────────────────────────
sync_state = {
    "last_sync":       None,
    "products_count":  0,
    "faq_count":       0,
    "status":          "not_synced",
}


def run_sync():
    """Wrapper called by scheduler and /sync endpoint."""
    from ingest import run_full_sync
    log.info("[SYNC] Starting product sync from Shopify...")
    try:
        result = run_full_sync()
        sync_state.update({
            "last_sync":      datetime.now(timezone.utc).isoformat(),
            "products_count": result["products"],
            "faq_count":      result["faq"],
            "status":         "ok",
        })
        log.info(f"[OK] Sync complete - {result['products']} products, {result['faq']} FAQ items")
    except Exception as exc:
        sync_state["status"] = f"error: {exc}"
        log.error(f"[ERROR] Sync failed: {exc}")


# ─────────────────────────────────────────────
# Lifespan: initial sync + scheduler setup
# ─────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    log.info("[START] Mobile Covers Chatbot API starting...")
    run_sync()

    scheduler = BackgroundScheduler()
    scheduler.add_job(
        run_sync,
        trigger="interval",
        hours=SYNC_INTERVAL_HOURS,
        id="product_sync",
        replace_existing=True,
    )
    scheduler.start()
    log.info(f"[SCHEDULER] Auto-sync every {SYNC_INTERVAL_HOURS} hour(s)")

    yield

    scheduler.shutdown()
    log.info("[STOP] Scheduler stopped")


# ─────────────────────────────────────────────
# App
# ─────────────────────────────────────────────
app = FastAPI(
    title="Mobile Covers Chatbot API",
    description="RAG-powered shopping assistant for a Shopify mobile covers store.",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)


# ─────────────────────────────────────────────
# Request / Response Models
# ─────────────────────────────────────────────
class Message(BaseModel):
    role:    str = Field(..., pattern="^(user|assistant)$")
    content: str = Field(..., min_length=1, max_length=4000)


class ChatRequest(BaseModel):
    message: str             = Field(..., min_length=1, max_length=1000)
    history: list[Message]   = Field(default=[])


class ChatResponse(BaseModel):
    response:    str
    status:      str = "success"
    retrieved:   Optional[int] = None  # how many docs were retrieved


# ─────────────────────────────────────────────
# Endpoints
# ─────────────────────────────────────────────

@app.get("/", tags=["Health"])
def health_check():
    return {
        "status":  "ok",
        "service": "Mobile Covers Chatbot API",
        "store":   SHOPIFY_STORE_URL,
    }


@app.get("/status", tags=["Health"])
def get_status():
    """Returns the current sync state and product counts."""
    return {
        "sync": sync_state,
        "auto_sync_interval_hours": SYNC_INTERVAL_HOURS,
    }


@app.post("/chat", response_model=ChatResponse, tags=["Chat"])
async def chat(request: ChatRequest):
    """
    Send a user message and receive an AI-generated response.
    Pass previous messages in `history` to maintain context.
    """
    if sync_state["status"] == "not_synced":
        # Knowledge base not ready yet
        return ChatResponse(
            response=(
                "I'm still warming up! 🔄 The product catalog is being loaded. "
                "Please try again in a moment."
            ),
            status="warming_up",
        )

    try:
        from rag import generate_response
        history = [msg.model_dump() for msg in request.history]
        response_text = generate_response(request.message, history)
        return ChatResponse(response=response_text)

    except RuntimeError as exc:
        log.error(f"Chat error: {exc}", exc_info=True)
        msg = str(exc)
        if "503" in msg or "UNAVAILABLE" in msg or "high demand" in msg:
            return ChatResponse(
                response="The AI service is temporarily busy. Please try again in a few seconds! 🙏",
                status="unavailable",
            )
        raise HTTPException(status_code=500, detail="Something went wrong. Please try again.")
    except Exception as exc:
        log.error(f"Chat error: {exc}", exc_info=True)
        raise HTTPException(status_code=500, detail="Something went wrong. Please try again.")


@app.post("/sync", tags=["Admin"])
async def trigger_sync():
    """
    Manually trigger a fresh product sync from Shopify.
    Useful when you've updated products and want instant refresh.
    """
    try:
        run_sync()
        return {
            "status":   "success",
            "message":  "Products re-synced from Shopify",
            "products": sync_state["products_count"],
            "faq":      sync_state["faq_count"],
            "synced_at": sync_state["last_sync"],
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


# ─────────────────────────────────────────────
# Global error handler
# ─────────────────────────────────────────────
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    log.error(f"Unhandled error: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error. Please try again."},
    )
