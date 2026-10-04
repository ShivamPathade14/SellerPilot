"""Service Interfaces (typing.Protocol).

These interfaces define the structural contracts between Part A and Part B.
Implementations MUST NEVER be directly imported across ownership boundaries;
all dependencies must be injected at runtime using these protocols.
"""

from typing import Any, Protocol, runtime_checkable
from core.schemas import (
    AgentAction,
    CaptionRequest,
    CaptionResult,
    Event,
    IncomingMessage,
    InventoryAlert,
    Product,
    StockStatus,
)


@runtime_checkable
class InventoryService(Protocol):
    """Protocol for inventory operations owned by Part B."""

    def get_stock(self, product_id: str) -> StockStatus | None:
        """Fetch real-time stock status for a given product ID."""
        ...

    def find_products(self, query: str) -> list[Product]:
        """Search products in the catalog by name, category, or description keywords."""
        ...

    def reserve(self, product_id: str, qty: int) -> bool:
        """Attempt to reserve a quantity of a product. Returns True if successful."""
        ...

    def get_alerts(self) -> list[InventoryAlert]:
        """Fetch all active inventory alerts (low stock, oversold, etc.)."""
        ...


@runtime_checkable
class ContentService(Protocol):
    """Protocol for content generation owned by Part B."""

    def generate_caption(self, req: CaptionRequest) -> CaptionResult:
        """Generate an on-brand social media caption with hashtags and tone notes."""
        ...


@runtime_checkable
class CommerceService(Protocol):
    """Protocol for conversational commerce handling owned by Part A."""

    def handle_message(self, msg: IncomingMessage, inventory: InventoryService) -> AgentAction:
        """Process an inbound customer DM and return a structured AgentAction."""
        ...


@runtime_checkable
class Orchestrator(Protocol):
    """Protocol for the central multi-agent workflow orchestrator owned by Part A."""

    def build_graph(self, inventory: InventoryService, content: ContentService) -> Any:
        """Assemble and compile the LangGraph workflow with injected service dependencies."""
        ...

    def process_event(self, event: Event) -> AgentAction | CaptionResult:
        """Route and execute an incoming system event through the workflow graph."""
        ...
