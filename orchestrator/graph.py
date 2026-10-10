"""LangGraph Multi-Agent Orchestrator for SellerPilot AI.

Architectural Viva Notes:
1. Event-Driven Graph Execution: Coordinates incoming events across specialized agents:
   - "new_dm" -> routes to commerce_node (CommerceService)
   - "new_product_photo" -> routes to content_node (ContentService)
   - "low_stock" -> routes to inventory_alert_node
2. Explicit, Loggable Transitions: Every routing decision and node execution records
   structured traces into state["log_trail"], providing complete observability and auditability.
3. Conditional Escalation Branching: If the commerce agent flags an inquiry (escalate=True),
   the graph conditionally diverges to the escalation_node before termination.
4. Dependency Injection & Isolation: Services (InventoryService, ContentService, CommerceService)
   are injected at graph build time, ensuring strict protocol adherence.
"""

from datetime import datetime
import logging
from typing import Any
from agents.commerce.agent import ConversationalCommerceAgent
from core.interfaces import (
    CommerceService,
    ContentService,
    InventoryService,
    Orchestrator,
)
from core.mocks import DEFAULT_BRAND_VOICE, SAMPLE_PRODUCTS
from core.schemas import (
    AgentAction,
    CaptionRequest,
    CaptionResult,
    Event,
    IncomingMessage,
    Intent,
    Product,
    StockStatus,
)
from core.state import SellerPilotState

logger = logging.getLogger(__name__)

# Check if langgraph is available
try:
    from langgraph.graph import END, StateGraph
    HAS_LANGGRAPH = True
except ImportError:
    HAS_LANGGRAPH = False
    END = "__END__"


from agents.commerce.order_service import OrderService


class SellerPilotOrchestrator(Orchestrator):
    """Central LangGraph Orchestrator coordinating multi-agent workflows."""

    def __init__(
        self,
        inventory: InventoryService | None = None,
        content: ContentService | None = None,
        commerce: CommerceService | None = None,
        order_service: OrderService | None = None,
    ):
        self.inventory: InventoryService | None = inventory
        self.content: ContentService | None = content
        self.commerce: CommerceService = commerce or ConversationalCommerceAgent()
        self.order_service: OrderService = order_service or OrderService()
        self.compiled_graph: Any = None

        if self.inventory and self.content:
            self.build_graph(self.inventory, self.content)

    def build_graph(self, inventory: InventoryService, content: ContentService) -> Any:
        """Assemble the workflow graph with injected service dependencies."""
        self.inventory = inventory
        self.content = content

        if HAS_LANGGRAPH:
            workflow = StateGraph(SellerPilotState)

            # Register explicit nodes
            workflow.add_node("router", self._router_node)
            workflow.add_node("commerce", self._commerce_node)
            workflow.add_node("content", self._content_node)
            workflow.add_node("inventory_alert", self._inventory_alert_node)
            workflow.add_node("escalation", self._escalation_node)

            # Set entry point
            workflow.set_entry_point("router")

            # Conditional routing from router
            workflow.add_conditional_edges(
                "router",
                self._route_event_condition,
                {
                    "commerce": "commerce",
                    "content": "content",
                    "inventory_alert": "inventory_alert",
                    "end": END,
                },
            )

            # Conditional routing from commerce agent
            workflow.add_conditional_edges(
                "commerce",
                self._route_commerce_condition,
                {
                    "escalation": "escalation",
                    "end": END,
                },
            )

            # Terminal nodes connect to END
            workflow.add_edge("content", END)
            workflow.add_edge("inventory_alert", END)
            workflow.add_edge("escalation", END)

            self.compiled_graph = workflow.compile()
            return self.compiled_graph
        else:
            self.compiled_graph = "internal_dag"
            return self.compiled_graph

    def process_event(self, event: Event) -> AgentAction | CaptionResult:
        """Route and execute an incoming system event through the workflow graph."""
        if not self.inventory or not self.content:
            raise RuntimeError("Orchestrator must have inventory and content services injected via build_graph().")

        payload = event.payload if event else {}
        customer_id = payload.get("customer_id")
        channel = payload.get("channel", "instagram")
        if "message" in payload and isinstance(payload["message"], dict):
            customer_id = payload["message"].get("customer_id", customer_id)
            channel = payload["message"].get("channel", channel)

        # Initialize fresh state with default catalog, brand voice, and audit trail
        initial_state: SellerPilotState = {
            "current_event": event,
            "event_type": event.type,
            "customer_id": customer_id,
            "channel": channel,
            "conversation_id": payload.get("conversation_id"),
            "catalog": SAMPLE_PRODUCTS,
            "brand_voice": DEFAULT_BRAND_VOICE,
            "conversation_history": list(payload.get("history", [])),
            "log_trail": [f"[{datetime.utcnow().isoformat()}] [ORCHESTRATOR_START] Dispatched event type='{event.type}'"],
            "escalated": False,
        }

        if HAS_LANGGRAPH and self.compiled_graph and self.compiled_graph != "internal_dag":
            final_state = self.compiled_graph.invoke(initial_state)
        else:
            # Deterministic, explicit internal DAG matching LangGraph routing
            final_state = self._execute_internal_dag(initial_state)

        # Return primary result (AgentAction or CaptionResult)
        if final_state.get("action") is not None:
            return final_state["action"]
        elif final_state.get("caption_result") is not None:
            return final_state["caption_result"]

        # Default fallback action
        return AgentAction(
            agent="commerce",
            intent=Intent.other,
            response_text="Event processed with no action generated.",
            escalate=False,
            confidence=1.0,
        )

    # ---------------------------------------------------------
    # Explicit, Loggable Graph Nodes
    # ---------------------------------------------------------

    def _router_node(self, state: SellerPilotState) -> dict[str, Any]:
        """Node 1: Inspect event type and validate required payloads."""
        event = state.get("current_event")
        event_type = event.type if event else "unknown"
        log_entry = f"[{datetime.utcnow().isoformat()}] [ROUTER_NODE] Routing event type='{event_type}'"
        logger.info(log_entry)
        logs = list(state.get("log_trail", []))
        logs.append(log_entry)
        return {"event_type": event_type, "log_trail": logs}

    def _commerce_node(self, state: SellerPilotState) -> dict[str, Any]:
        """Node 2: Execute Conversational Commerce Agent with injected inventory service."""
        event = state["current_event"]
        payload = event.payload if event else {}

        # Reconstruct or parse IncomingMessage
        if "message" in payload and isinstance(payload["message"], dict):
            msg = IncomingMessage(**payload["message"])
        elif "text" in payload:
            msg = IncomingMessage(
                message_id=payload.get("message_id", f"msg-{int(datetime.utcnow().timestamp())}"),
                customer_id=payload.get("customer_id", "guest-user"),
                channel=payload.get("channel", "instagram"),
                text=payload["text"],
                timestamp=payload.get("timestamp", datetime.utcnow()),
            )
        else:
            msg = IncomingMessage(
                message_id="msg-default",
                customer_id="guest-user",
                channel="instagram",
                text=str(payload),
                timestamp=datetime.utcnow(),
            )

        # Retrieve or initialize context
        ctx = None
        if hasattr(self.commerce, "context_manager"):
            ctx = self.commerce.context_manager.get_or_create(
                customer_id=msg.customer_id,
                channel=msg.channel,
                conversation_id=payload.get("conversation_id"),
            )

        # Execute commerce agent with dependency injection and context
        if hasattr(self.commerce, "handle_message"):
            try:
                action: AgentAction = self.commerce.handle_message(  # type: ignore
                    msg,
                    self.inventory,
                    context=ctx,
                    order_service=self.order_service,
                )
            except TypeError:
                action: AgentAction = self.commerce.handle_message(msg, self.inventory)  # type: ignore
        else:
            action: AgentAction = self.commerce.handle_message(msg, self.inventory)  # type: ignore

        log_entry = (
            f"[{datetime.utcnow().isoformat()}] [COMMERCE_NODE] Handled DM: "
            f"customer='{msg.customer_id}', channel='{msg.channel}', intent='{action.intent}', "
            f"escalate={action.escalate}, confidence={action.confidence}"
        )
        logger.info(log_entry)

        history = list(state.get("conversation_history", []))
        history.append({
            "message_id": msg.message_id,
            "text": msg.text,
            "response": action.response_text,
            "intent": action.intent.value,
            "escalated": action.escalate,
        })

        logs = list(state.get("log_trail", []))
        logs.append(log_entry)

        return {
            "incoming_message": msg,
            "action": action,
            "intent": action.intent,
            "escalated": action.escalate,
            "escalation_reason": action.escalation_reason,
            "active_product_id": action.product_id,
            "active_product_name": action.active_product_name,
            "conversation_stage": str(action.conversation_stage) if action.conversation_stage else None,
            "pending_action": action.pending_action,
            "requested_quantity": action.requested_quantity,
            "order_id": action.order_id,
            "conversation_history": history,
            "log_trail": logs,
        }

    def _content_node(self, state: SellerPilotState) -> dict[str, Any]:
        """Node 3: Execute Content Agent with injected content service."""
        event = state["current_event"]
        payload = event.payload if event else {}

        # Resolve target product
        product = None
        if "product" in payload and isinstance(payload["product"], dict):
            product = Product(**payload["product"])
        elif "product_id" in payload:
            matches = self.inventory.find_products(payload["product_id"])  # type: ignore
            product = matches[0] if matches else None

        if not product:
            # Fallback to first catalog product
            product = SAMPLE_PRODUCTS[0]

        req = CaptionRequest(
            product=product,
            image_path=payload.get("image_path", product.image_path),
            extra_notes=payload.get("extra_notes"),
        )

        caption_result: CaptionResult = self.content.generate_caption(req)  # type: ignore

        log_entry = (
            f"[{datetime.utcnow().isoformat()}] [CONTENT_NODE] Generated caption for "
            f"product='{product.name}' (id='{product.id}'), hashtags={len(caption_result.hashtags)}"
        )
        logger.info(log_entry)

        logs = list(state.get("log_trail", []))
        logs.append(log_entry)

        return {
            "caption_request_product": product,
            "caption_result": caption_result,
            "log_trail": logs,
        }

    def _inventory_alert_node(self, state: SellerPilotState) -> dict[str, Any]:
        """Node 4: Handle low stock / inventory alert events."""
        event = state["current_event"]
        payload = event.payload if event else {}
        product_id = payload.get("product_id", "prod-101")

        # Inquire live stock via injected inventory interface
        stock: StockStatus | None = self.inventory.get_stock(product_id)  # type: ignore
        alerts = self.inventory.get_alerts()  # type: ignore

        is_critical = stock is not None and (stock.quantity <= 0 or (stock.low_stock and stock.posted_on_instagram))
        reason = (
            f"CRITICAL: Product {product_id} has {stock.quantity if stock else 0} units left "
            f"and is posted on Instagram!" if is_critical else f"Low stock alert for {product_id}"
        )

        action = AgentAction(
            agent="inventory",
            intent=Intent.stock_query,
            product_id=product_id,
            response_text=f"Inventory notification: Product {product_id} stock check completed. Active alerts: {len(alerts)}.",
            escalate=is_critical,
            escalation_reason=reason if is_critical else None,
            confidence=1.0,
        )

        log_entry = (
            f"[{datetime.utcnow().isoformat()}] [INVENTORY_ALERT_NODE] Processed alert for "
            f"product_id='{product_id}', critical={is_critical}, total_alerts={len(alerts)}"
        )
        logger.info(log_entry)

        logs = list(state.get("log_trail", []))
        logs.append(log_entry)

        return {
            "stock_status": stock,
            "inventory_alerts": alerts,
            "action": action,
            "escalated": is_critical,
            "escalation_reason": reason if is_critical else None,
            "log_trail": logs,
        }

    def _escalation_node(self, state: SellerPilotState) -> dict[str, Any]:
        """Node 5: Explicit human escalation handler recording supervisor ticket."""
        reason = state.get("escalation_reason", "Customer inquiry requires human assistance.")
        log_entry = f"[{datetime.utcnow().isoformat()}] [ESCALATION_NODE] Routed to human supervisor: {reason}"
        logger.warning(log_entry)

        logs = list(state.get("log_trail", []))
        logs.append(log_entry)

        return {
            "escalated": True,
            "log_trail": logs,
        }

    # ---------------------------------------------------------
    # Conditional Branching Logic
    # ---------------------------------------------------------

    def _route_event_condition(self, state: SellerPilotState) -> str:
        """Route to appropriate agent node based on event type."""
        event_type = state.get("event_type")
        if event_type == "new_dm":
            return "commerce"
        elif event_type == "new_product_photo":
            return "content"
        elif event_type == "low_stock":
            return "inventory_alert"
        return "end"

    def _route_commerce_condition(self, state: SellerPilotState) -> str:
        """Route to escalation node if commerce agent flagged human review."""
        if state.get("escalated", False):
            return "escalation"
        return "end"

    # ---------------------------------------------------------
    # Internal DAG Execution (Deterministic & Self-Contained)
    # ---------------------------------------------------------

    def _execute_internal_dag(self, state: SellerPilotState) -> SellerPilotState:
        """Executes the exact same multi-agent DAG without external graph dependencies."""
        current_state = dict(state)

        # 1. Router Node
        router_update = self._router_node(current_state)  # type: ignore
        current_state.update(router_update)

        # Route condition
        route = self._route_event_condition(current_state)  # type: ignore

        if route == "commerce":
            # 2. Commerce Node
            commerce_update = self._commerce_node(current_state)  # type: ignore
            current_state.update(commerce_update)

            # Check escalation condition
            if self._route_commerce_condition(current_state) == "escalation":  # type: ignore
                # 5. Escalation Node
                esc_update = self._escalation_node(current_state)  # type: ignore
                current_state.update(esc_update)

        elif route == "content":
            # 3. Content Node
            content_update = self._content_node(current_state)  # type: ignore
            current_state.update(content_update)

        elif route == "inventory_alert":
            # 4. Inventory Alert Node
            inv_update = self._inventory_alert_node(current_state)  # type: ignore
            current_state.update(inv_update)

        return current_state  # type: ignore
