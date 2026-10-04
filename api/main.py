"""FastAPI Gateway Application for SellerPilot AI.

Architectural Viva Notes:
1. Guarded Modular Routing: Includes routes_chat.py (Part A) and safely mounts Part B routers
   (routes_inventory.py, routes_content.py) with try/except guards so the backend remains
   fully functional during parallel development.
2. Inversion of Control & Mock Injection: Checks settings.USE_MOCKS on application startup to wire
   either MockInventoryService / MockContentService or live Part B services into the LangGraph
   Orchestrator.
3. Streamlit & Cross-Origin Support: Pre-configures CORS middleware to allow communication
   from the Streamlit dashboard on port 8501.
"""

from contextlib import asynccontextmanager
import logging
from typing import AsyncGenerator
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from api.routes_chat import router as chat_router
from core.config import settings
from core.mocks import MockContentService, MockInventoryService
from db.base import init_db
from orchestrator.graph import SellerPilotOrchestrator

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("sellerpilot.api")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan context manager for startup and shutdown procedures."""
    logger.info("Starting SellerPilot AI Gateway...")

    # 1. Initialize SQLite Database Schema
    init_db()
    logger.info("Database schema initialized at: %s", settings.DATABASE_URL)

    # 2. Wire Dependencies according to USE_MOCKS
    if settings.USE_MOCKS:
        logger.info("USE_MOCKS=True: Wiring MockInventoryService and MockContentService.")
        inventory_svc = MockInventoryService()
        content_svc = MockContentService()
    else:
        logger.info("USE_MOCKS=False: Attempting to wire production services...")
        try:
            from agents.inventory.service import InventoryServiceImplementation  # type: ignore
            inventory_svc = InventoryServiceImplementation()
        except ImportError:
            logger.warning("Production InventoryService not found; falling back to MockInventoryService.")
            inventory_svc = MockInventoryService()

        try:
            from agents.content.service import ContentServiceImplementation  # type: ignore
            content_svc = ContentServiceImplementation()
        except ImportError:
            logger.warning("Production ContentService not found; falling back to MockContentService.")
            content_svc = MockContentService()

    # 3. Assemble and Compile LangGraph Orchestrator
    orchestrator = SellerPilotOrchestrator(inventory=inventory_svc, content=content_svc)
    app.state.orchestrator = orchestrator
    app.state.inventory_service = inventory_svc
    app.state.content_service = content_svc
    logger.info("LangGraph Orchestrator successfully initialized and attached to app.state.")

    yield

    logger.info("Shutting down SellerPilot AI Gateway.")


# Create FastAPI application instance
app = FastAPI(
    title="SellerPilot AI Gateway",
    description="Multi-agent assistant API for Instagram/WhatsApp-first D2C brands.",
    version="1.0.0",
    lifespan=lifespan,
)

# Enable CORS for Streamlit dashboard and local clients
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# -------------------------------------------------------------
# Router Ingestion (Part A + Guarded Part B)
# -------------------------------------------------------------

# Part A Chat & Webhook Router
app.include_router(chat_router)

# Guarded: Part B Inventory Router
try:
    from api.routes_inventory import router as inventory_router  # type: ignore
    app.include_router(inventory_router)
    logger.info("Guarded Mount: Successfully mounted Part B routes_inventory.")
except ImportError:
    logger.info("Guarded Mount: Part B routes_inventory not yet available; skipping mount.")

# Guarded: Part B Content Router
try:
    from api.routes_content import router as content_router  # type: ignore
    app.include_router(content_router)
    logger.info("Guarded Mount: Successfully mounted Part B routes_content.")
except ImportError:
    logger.info("Guarded Mount: Part B routes_content not yet available; skipping mount.")


@app.get("/health", tags=["system"])
def health_check() -> dict[str, str | bool]:
    """System health check and mock mode status."""
    return {
        "status": "healthy",
        "app": "SellerPilot AI",
        "mocks_enabled": settings.USE_MOCKS,
        "database": settings.DATABASE_URL,
    }
