"""FastAPI router for AI Content Generation and Brand Voice Engine.

Architectural Viva Notes:
1. Grounded Content Generation: Accepts product_id, resolves verified catalog product facts
   from SQLiteInventoryService, and generates Instagram captions strictly bounded to product truth.
2. Inversion of Control & Dependency Injection: Retrieves ContentService and InventoryService
   from FastAPI app.state, with clean standalone fallbacks.
3. Brand Voice Observability: Exposes GET /content/brand-voice for live dashboard monitoring
   and viva demonstration of the learned persona profile.
"""

import logging
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from agents.content.agent import ContentAgent
from agents.content.brand_voice import BrandVoiceAnalyzer
from agents.inventory.service import SQLiteInventoryService
from core.interfaces import ContentService, InventoryService
from core.schemas import BrandVoiceProfile, CaptionRequest, CaptionResult, Product

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/content", tags=["content"])


# -------------------------------------------------------------
# Request & Response Schemas
# -------------------------------------------------------------

class GenerateCaptionPayload(BaseModel):
    """Payload to request an AI-generated on-brand caption for a catalog product."""
    product_id: str = Field(description="Unique product identifier from catalog (e.g. 'prod-101')")
    image_path: Optional[str] = Field(default=None, description="Optional path to local product image")
    extra_notes: Optional[str] = Field(default=None, description="Optional campaign context, drop notes, or seasonal hints")


# -------------------------------------------------------------
# Dependency Providers
# -------------------------------------------------------------

def get_content_service(request: Request) -> ContentService:
    """Retrieve ContentService instance configured on app.state or fallback to ContentAgent."""
    service = getattr(request.app.state, "content_service", None)
    if service is not None and isinstance(service, ContentService):
        return service
    return ContentAgent()


def get_inventory_service(request: Request) -> SQLiteInventoryService:
    """Retrieve InventoryService instance configured on app.state or fallback to SQLiteInventoryService."""
    service = getattr(request.app.state, "inventory_service", None)
    if service is not None and isinstance(service, SQLiteInventoryService):
        return service
    return SQLiteInventoryService()


# -------------------------------------------------------------
# Endpoints
# -------------------------------------------------------------

@router.post("/caption", response_model=CaptionResult)
def create_product_caption(
    payload: GenerateCaptionPayload,
    content_service: ContentService = Depends(get_content_service),
    inventory_service: SQLiteInventoryService = Depends(get_inventory_service),
) -> CaptionResult:
    """Generate an on-brand, fact-grounded Instagram caption and hashtags for a product."""
    product_id = payload.product_id.strip()

    # 1. Resolve product facts from catalog
    matches = inventory_service.find_products(product_id)
    product = next((p for p in matches if p.id == product_id), None)

    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Product with ID '{product_id}' was not found in catalog.",
        )

    # 2. Construct CaptionRequest
    caption_req = CaptionRequest(
        product=product,
        image_path=payload.image_path,
        extra_notes=payload.extra_notes,
    )

    # 3. Generate caption via ContentService
    result = content_service.generate_caption(caption_req)
    return result


@router.get("/brand-voice", response_model=BrandVoiceProfile)
def get_brand_voice_profile(
    content_service: ContentService = Depends(get_content_service),
) -> BrandVoiceProfile:
    """Return the learned BrandVoiceProfile for Aura Jewels."""
    if isinstance(content_service, ContentAgent):
        return content_service.profile

    analyzer = BrandVoiceAnalyzer()
    return analyzer.get_profile()
