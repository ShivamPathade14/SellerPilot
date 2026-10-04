"""Inventory Agent Implementation for SellerPilot AI.

Architectural Viva Notes:
1. Purely Deterministic Operation: The Inventory Agent relies strictly on SQLiteInventoryService
   as the single source of truth for stock quantities, reservation logic, and alert status,
   completely eliminating LLM hallucination in inventory bookkeeping.
2. Multi-Agent Orchestration Interoperability:
   - Implements structured event handling for 'low_stock' events dispatched by the LangGraph Orchestrator.
   - Accurately computes critical escalation triggers when products are posted on Instagram but out of stock.
3. Separation of Concerns:
   - Does not duplicate database queries or maintain redundant in-memory stock state.
   - Delegates all persistence and atomic transactions directly to SQLiteInventoryService.
"""

import logging
from typing import Any
from agents.inventory.service import SQLiteInventoryService
from core.interfaces import InventoryService
from core.schemas import AgentAction, Event, Intent, InventoryAlert, StockStatus

logger = logging.getLogger(__name__)


class InventoryAgent:
    """Agent responsible for autonomous inventory monitoring, alert generation, and reservations."""

    def __init__(self, service: InventoryService | None = None):
        self.service: InventoryService = service or SQLiteInventoryService()

    def check_stock(self, product_id: str) -> StockStatus | None:
        """Query real-time stock status for a given product."""
        return self.service.get_stock(product_id)

    def search_products(self, query: str):
        """Search products using deterministic catalog relevance scoring."""
        return self.service.find_products(query)

    def reserve_stock(self, product_id: str, quantity: int) -> bool:
        """Request atomic reservation of stock for an order."""
        return self.service.reserve(product_id, quantity)

    def get_unresolved_alerts(self) -> list[InventoryAlert]:
        """Fetch all active, unresolved inventory alerts."""
        return self.service.get_alerts()

    def check_low_stock(self, product_id: str) -> bool:
        """Check if a specific product is currently at or below low-stock threshold."""
        stock = self.service.get_stock(product_id)
        return stock is not None and stock.low_stock

    def check_out_of_stock(self, product_id: str) -> bool:
        """Check if a product is completely depleted (quantity == 0)."""
        stock = self.service.get_stock(product_id)
        return stock is not None and stock.quantity == 0

    def check_posted_but_unavailable(self, product_id: str) -> bool:
        """Check if a product is featured on Instagram but currently unavailable to purchase."""
        stock = self.service.get_stock(product_id)
        return stock is not None and stock.quantity == 0 and stock.posted_on_instagram

    def handle_event(self, event: Event) -> AgentAction:
        """Process orchestrator coordination events for inventory management.

        Follows the Event contract defined in core.schemas.
        """
        payload = event.payload or {}
        product_id = payload.get("product_id")

        if event.type == "low_stock":
            if not product_id:
                return AgentAction(
                    agent="inventory",
                    intent=Intent.stock_query,
                    product_id=None,
                    response_text="Low stock event received without product_id.",
                    escalate=True,
                    escalation_reason="Low stock event missing product_id in payload.",
                    confidence=1.0,
                )

            stock = self.service.get_stock(product_id)
            alerts = self.service.get_alerts()
            product_alerts = [a for a in alerts if a.product_id == product_id]

            # Critical escalation condition: depleted stock while posted on Instagram
            is_critical = stock is not None and (
                stock.quantity <= 0 or (stock.low_stock and stock.posted_on_instagram)
            )

            if stock is None:
                reason = f"Product '{product_id}' not found in inventory."
                response_text = f"Inventory check error: {reason}"
                escalate = True
            elif stock.quantity <= 0 and stock.posted_on_instagram:
                reason = f"CRITICAL: Product '{product_id}' is completely out of stock but active on Instagram reels/posts."
                response_text = f"Urgent alert: {reason} Studio replenishment or social post pause required."
                escalate = True
            elif stock.low_stock:
                reason = f"LOW STOCK: Product '{product_id}' has only {stock.quantity} units remaining in studio."
                response_text = f"Inventory alert: {reason} Active alert count: {len(product_alerts)}."
                escalate = stock.posted_on_instagram  # escalate if actively featured on IG
            else:
                reason = None
                response_text = f"Product '{product_id}' stock check: {stock.quantity} units available. Stock healthy."
                escalate = False

            return AgentAction(
                agent="inventory",
                intent=Intent.stock_query,
                product_id=product_id,
                response_text=response_text,
                escalate=escalate,
                escalation_reason=reason,
                confidence=1.0,
            )

        # For other events (e.g. new_product_photo), do not make inventory assumptions
        return AgentAction(
            agent="inventory",
            intent=Intent.other,
            product_id=product_id,
            response_text=f"Inventory Agent observed event '{event.type}'. No inventory actions required.",
            escalate=False,
            confidence=1.0,
        )
