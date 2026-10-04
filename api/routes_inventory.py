"""FastAPI router for inventory management, stock levels, alerts, and adjustments.

Architectural Viva Notes:
1. Pydantic-Validated Boundaries: All inputs and outputs are strictly typed with Pydantic
   response models, preventing raw ORM exposure and enforcing API contract guarantees.
2. RESTful HTTP Status Codes:
   - 200: Successful read or adjustment
   - 400: Invalid inputs (e.g. quantity <= 0)
   - 404: Nonexistent product ID
   - 409: Conflict on overselling or negative inventory attempts
   - 422: Schema validation failure
3. Route Ordering Guard: GET /inventory/alerts is explicitly registered before
   GET /inventory/{product_id} to avoid parameterized path collision in FastAPI.
"""

import logging
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, ConfigDict, Field
from agents.inventory.service import SQLiteInventoryService
from core.schemas import InventoryAlert, Product, StockStatus

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/inventory", tags=["inventory"])


# -------------------------------------------------------------
# Request & Response Schemas
# -------------------------------------------------------------

class InventoryItemResponse(BaseModel):
    """Product catalog details combined with real-time stock levels for dashboards and clients."""
    model_config = ConfigDict(from_attributes=True)

    product_id: str
    name: str
    price: float
    category: str
    material: str
    description: str
    sizes: list[str] = Field(default_factory=list)
    colors: list[str] = Field(default_factory=list)
    image_path: Optional[str] = None
    quantity: int
    in_stock: bool
    low_stock: bool
    posted_on_instagram: bool
    alert_status: Optional[str] = None


class ProductStockResponse(BaseModel):
    """Detailed response for a single product with full stock status."""
    model_config = ConfigDict(from_attributes=True)

    product: Product
    stock: StockStatus


class ReserveRequest(BaseModel):
    """Payload to request an atomic stock reservation."""
    quantity: int = Field(gt=0, description="Quantity to reserve (must be greater than 0)")


class ReserveResponse(BaseModel):
    """Response indicating the outcome of a reservation request."""
    success: bool
    product_id: str
    requested_quantity: int
    remaining_quantity: int
    alert_generated: Optional[str] = None
    message: str


class StockAdjustRequest(BaseModel):
    """Payload to manually adjust product inventory levels."""
    quantity_delta: int = Field(description="Quantity to adjust by (positive or negative, non-zero)")
    reason: str = Field(default="Manual adjustment", description="Operational rationale for stock change")


class StockAdjustResponse(BaseModel):
    """Outcome of manual inventory adjustment."""
    success: bool
    product_id: str
    previous_quantity: int
    new_quantity: int
    quantity_delta: int
    reason: str
    message: str


# -------------------------------------------------------------
# Dependency Provider
# -------------------------------------------------------------

def get_inventory_service(request: Request) -> SQLiteInventoryService:
    """Retrieve the inventory service instance configured on app state or default to SQLite service."""
    service = getattr(request.app.state, "inventory_service", None)
    if isinstance(service, SQLiteInventoryService):
        return service
    return SQLiteInventoryService()


# -------------------------------------------------------------
# Endpoints
# -------------------------------------------------------------

@router.get("", response_model=list[InventoryItemResponse])
@router.get("/", response_model=list[InventoryItemResponse])
def get_all_inventory(
    service: SQLiteInventoryService = Depends(get_inventory_service),
) -> list[dict]:
    """Return all products with current stock status and inventory details."""
    return service.get_all_products_with_stock()


@router.get("/alerts", response_model=list[InventoryAlert])
def get_inventory_alerts(
    service: SQLiteInventoryService = Depends(get_inventory_service),
) -> list[InventoryAlert]:
    """Return current unresolved inventory alerts (low stock, oversold, posted but out of stock)."""
    return service.get_alerts()


@router.get("/{product_id}", response_model=ProductStockResponse)
def get_product_stock(
    product_id: str,
    service: SQLiteInventoryService = Depends(get_inventory_service),
) -> ProductStockResponse:
    """Return a single product and its real-time StockStatus."""
    matches = service.find_products(product_id)
    product = next((p for p in matches if p.id == product_id), None)

    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Product '{product_id}' not found in catalog.",
        )

    stock = service.get_stock(product_id)
    if not stock:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Inventory record for product '{product_id}' not found.",
        )

    return ProductStockResponse(product=product, stock=stock)


@router.post("/{product_id}/reserve", response_model=ReserveResponse)
def reserve_product_stock(
    product_id: str,
    payload: ReserveRequest,
    service: SQLiteInventoryService = Depends(get_inventory_service),
) -> ReserveResponse:
    """Atomically reserve inventory for an order. Prevents negative stock and overselling."""
    if payload.quantity <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Reservation quantity must be greater than 0.",
        )

    stock = service.get_stock(product_id)
    if not stock:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Product '{product_id}' not found in inventory.",
        )

    success = service.reserve(product_id, payload.quantity)
    if not success:
        # 409 Conflict: Request exceeds available stock
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "success": False,
                "product_id": product_id,
                "requested_quantity": payload.quantity,
                "remaining_quantity": stock.quantity,
                "alert_generated": "oversold",
                "message": f"Reservation failed: requested {payload.quantity} units, but only {stock.quantity} in stock.",
            },
        )

    updated_stock = service.get_stock(product_id)
    remaining_qty = updated_stock.quantity if updated_stock else 0

    alert_type = None
    if updated_stock and updated_stock.quantity == 0 and updated_stock.posted_on_instagram:
        alert_type = "posted_but_out_of_stock"
    elif updated_stock and updated_stock.low_stock:
        alert_type = "low_stock"

    return ReserveResponse(
        success=True,
        product_id=product_id,
        requested_quantity=payload.quantity,
        remaining_quantity=remaining_qty,
        alert_generated=alert_type,
        message=f"Successfully reserved {payload.quantity} unit(s) of '{product_id}'. Remaining stock: {remaining_qty}.",
    )


@router.post("/{product_id}/adjust", response_model=StockAdjustResponse)
def adjust_product_stock(
    product_id: str,
    payload: StockAdjustRequest,
    service: SQLiteInventoryService = Depends(get_inventory_service),
) -> StockAdjustResponse:
    """Manually adjust product inventory levels (e.g. supplier restock, damaged loss)."""
    if payload.quantity_delta == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Adjustment quantity delta cannot be 0.",
        )

    stock = service.get_stock(product_id)
    if not stock:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Product '{product_id}' not found in inventory.",
        )

    success, updated_stock, prev_qty, error_msg = service.adjust_stock(
        product_id=product_id,
        quantity_delta=payload.quantity_delta,
        reason=payload.reason,
    )

    if not success or updated_stock is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "success": False,
                "product_id": product_id,
                "previous_quantity": prev_qty,
                "new_quantity": prev_qty,
                "quantity_delta": payload.quantity_delta,
                "reason": payload.reason,
                "message": error_msg or "Stock adjustment failed.",
            },
        )

    return StockAdjustResponse(
        success=True,
        product_id=product_id,
        previous_quantity=prev_qty,
        new_quantity=updated_stock.quantity,
        quantity_delta=payload.quantity_delta,
        reason=payload.reason,
        message=f"Stock adjusted by {payload.quantity_delta:+d} ({prev_qty} -> {updated_stock.quantity}). Reason: {payload.reason}",
    )
