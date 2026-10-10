"""LangGraph shared state definitions for SellerPilot AI.

The shared state coordinates data across conversational commerce, inventory alerts,
content generation, and human escalation.
"""

from typing import Annotated, Any, TypedDict
from core.schemas import (
    AgentAction,
    BrandVoiceProfile,
    CaptionResult,
    ConversationContext,
    Event,
    IncomingMessage,
    Intent,
    InventoryAlert,
    Product,
    StockStatus,
)


def append_log(existing: list[str], new_entries: list[str] | str) -> list[str]:
    """Reducer helper to append execution traces to the log trail."""
    if isinstance(new_entries, str):
        return existing + [new_entries]
    return existing + list(new_entries)


class SellerPilotState(TypedDict, total=False):
    """Shared state object passed between nodes in the LangGraph Orchestrator."""

    # Event trigger and routing
    current_event: Event | None
    event_type: str | None

    # Customer and conversation context
    customer_id: str | None
    channel: str | None
    incoming_message: IncomingMessage | None
    conversation_history: list[dict[str, Any]]

    # Commerce Agent state
    intent: Intent | None
    query_text: str | None
    matched_products: list[Product]
    active_product: Product | None
    stock_status: StockStatus | None
    action: AgentAction | None
    escalated: bool
    escalation_reason: str | None

    # Content Agent state
    caption_request_product: Product | None
    caption_result: CaptionResult | None
    brand_voice: BrandVoiceProfile | None

    # Inventory context & alerts
    inventory_alerts: list[InventoryAlert]

    # Shared catalog
    catalog: list[Product]

    # Audit & observability
    log_trail: list[str]

    # Persistent conversation context
    conversation_id: int | str | None
    active_product_id: str | None
    active_product_name: str | None
    conversation_stage: str | None
    pending_action: str | None
    requested_quantity: int | None
    order_id: str | None
    conversation_context: ConversationContext | None

