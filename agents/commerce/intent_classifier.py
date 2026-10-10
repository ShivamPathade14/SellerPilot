"""Intent Classification for SellerPilot AI.

Architectural Viva Notes:
1. Resilient Dual Execution:
   - Live Tier: Claude 3.7 structured output via tool use when ANTHROPIC_API_KEY is present.
   - Deterministic Tier: High-coverage heuristic rule engine for mock mode, offline, and CI/CD.
2. Contextual Understanding:
   - Incorporates active product, recent dialogue history, and pending actions to accurately
     classify short contextual phrases ("yes", "place this", "how much?", "can I get two?").
3. Safety Guardrails:
   - Automatic escalation tagging for complaints, refunds, bargaining, bespoke customizations, and bulk orders.
"""

import logging
import re
from typing import Optional
from pydantic import BaseModel, ConfigDict
from core.config import settings
from core.llm import ClaudeClient, claude_client as default_claude_client
from core.schemas import ConversationContext, ConversationStage, Intent

logger = logging.getLogger(__name__)

COMPLAINT_KEYWORDS = [
    "angry", "broken", "damaged", "cheat", "scam", "terrible", "worst",
    "unacceptable", "defective", "horrible", "upset", "disappointed",
    "bad quality", "ruined",
]

REFUND_KEYWORDS = [
    "refund", "return", "money back", "cancel order", "cancellation", "exchange",
]

CUSTOM_KEYWORDS = [
    "custom", "customized", "customize", "customisation", "customization",
    "engrave", "engraving", "bespoke", "modify", "made to order",
]

BULK_KEYWORDS = [
    "bulk", "wholesale", "50 pieces", "100 pieces", "20 pieces", "large order",
    "wedding favors", "corporate gift", "reseller",
]

BARGAIN_KEYWORDS = [
    "bargain", "discount", "cheaper", "lower price", "best price",
    "reduce price", "any discount", "coupon code", "deal", "negotiate",
]

SHIPPING_KEYWORDS = [
    "ship", "shipping", "deliver", "delivery", "dispatch", "courier",
    "tracking", "how long", "pin code", "pincode", "timeline",
]


class IntentClassificationResult(BaseModel):
    """Structured output for intent classification."""
    model_config = ConfigDict(from_attributes=True)

    intent: Intent
    confidence: float = 1.0
    product_reference: Optional[str] = None
    quantity: Optional[int] = None
    variant: Optional[str] = None
    clarification_required: bool = False
    escalate: bool = False
    escalation_reason: Optional[str] = None


class IntentClassifier:
    """Classifies user intent considering multi-turn conversation context."""

    def __init__(self, llm_client: ClaudeClient | None = None):
        self.llm = llm_client or default_claude_client

    def classify(
        self,
        text: str,
        context: Optional[ConversationContext] = None,
    ) -> IntentClassificationResult:
        """Classify customer message text into structured IntentClassificationResult."""
        text_clean = text.strip()
        text_lower = text_clean.lower()

        # Step 1: Detect explicit safety escalations (Complaints, Refunds, Bulk, Custom, Bargaining)
        if any(kw in text_lower for kw in COMPLAINT_KEYWORDS):
            return IntentClassificationResult(
                intent=Intent.complaint,
                confidence=0.98,
                escalate=True,
                escalation_reason="Customer complaint or dissatisfaction detected.",
            )

        cleaned_for_refund = re.sub(r"\breturn\s+gifts?\b", "", text_lower)
        if any(kw in cleaned_for_refund for kw in REFUND_KEYWORDS):
            return IntentClassificationResult(
                intent=Intent.return_refund,
                confidence=0.98,
                escalate=True,
                escalation_reason="Refund or return inquiry requiring human policy authorization.",
            )

        if any(kw in text_lower for kw in BULK_KEYWORDS):
            return IntentClassificationResult(
                intent=Intent.other,
                confidence=0.95,
                escalate=True,
                escalation_reason="Bulk or wholesale order inquiry requiring founder review.",
            )

        if any(kw in text_lower for kw in CUSTOM_KEYWORDS):
            return IntentClassificationResult(
                intent=Intent.other,
                confidence=0.92,
                escalate=True,
                escalation_reason="Bespoke customization request requiring artisan consultation.",
            )

        if any(kw in text_lower for kw in BARGAIN_KEYWORDS):
            return IntentClassificationResult(
                intent=Intent.bargaining,
                confidence=0.90,
                escalate=True,
                escalation_reason="Price bargaining or unapproved discount negotiation.",
            )

        # Step 2: Try Live Claude LLM Structured Classification if available
        if self.llm.api_key and not settings.USE_MOCKS:
            try:
                return self._classify_with_llm(text, context)
            except Exception as e:
                logger.warning("LLM classification failed (%s); falling back to deterministic rules.", e)

        # Step 3: High-Coverage Deterministic Fallback Rules
        return self._classify_deterministic(text_clean, text_lower, context)

    def _classify_deterministic(
        self,
        text: str,
        text_lower: str,
        context: Optional[ConversationContext],
    ) -> IntentClassificationResult:
        """Rule-based contextual classification engine."""

        # 1. Order Status Tracking
        if any(kw in text_lower for kw in ["where is my order", "track my order", "order status", "status of my order", "where's my order"]):
            return IntentClassificationResult(
                intent=Intent.order_status,
                confidence=0.95,
            )

        # 2. Shipping Inquiries
        if any(kw in text_lower for kw in SHIPPING_KEYWORDS):
            return IntentClassificationResult(
                intent=Intent.shipping_query,
                confidence=0.95,
            )

        # 3. Quantity Changes ("can I get two?", "add one more", "make it one instead", "two pieces")
        qty_extracted = self._extract_quantity(text_lower)
        if qty_extracted is not None:
            # If the user asks for a quantity change or asks if they can get N
            if any(p in text_lower for p in ["can i get", "add", "make it", "pieces", "units", "two", "three", "four", "one instead"]):
                return IntentClassificationResult(
                    intent=Intent.quantity_change,
                    quantity=qty_extracted,
                    confidence=0.95,
                )

        # 4. Final Order Confirmation ("confirm", "yes confirm", "proceed", "place order")
        confirmation_phrases = ["confirm", "yes confirm", "confirm order", "proceed with order", "place order now"]
        if any(re.search(rf"\b{re.escape(p)}\b", text_lower) for p in confirmation_phrases):
            if context and (context.conversation_stage == ConversationStage.awaiting_order_confirmation or context.pending_action == "awaiting_order_confirmation"):
                return IntentClassificationResult(
                    intent=Intent.purchase_confirmation,
                    confidence=0.98,
                )

        # 5. Purchase Intent ("yes place this", "place this", "yes", "i'll take it", "take this", "i want to buy")
        purchase_intent_phrases = [
            "yes place this", "place this", "i'll take it", "take it", "take this",
            "buy this", "order this", "book it", "i want to buy", "okay, i'll take it",
            "yes, i'll take it", "yes i want to order", "yes please place", "place it",
        ]
        if any(re.search(rf"\b{re.escape(p)}\b", text_lower) for p in purchase_intent_phrases):
            return IntentClassificationResult(
                intent=Intent.purchase_intent,
                confidence=0.96,
            )

        # If customer simply says "yes" or "sure" or "yes please"
        is_simple_affirmation = bool(re.match(r"^(yes|yeah|yep|sure|okay|ok|yes please)\b", text_lower))
        if is_simple_affirmation:
            # Check context: if we are awaiting purchase details / confirmation
            if context:
                if context.conversation_stage == ConversationStage.awaiting_order_confirmation:
                    return IntentClassificationResult(
                        intent=Intent.purchase_confirmation,
                        confidence=0.95,
                    )
                if context.conversation_stage == ConversationStage.availability_verified or context.pending_action == "awaiting_purchase_intent":
                    return IntentClassificationResult(
                        intent=Intent.purchase_intent,
                        confidence=0.95,
                    )

        # 6. Variant Queries ("what about silver?", "in gold?", "size 8?", "what colors?", "other sizes?")
        variant_triggers = ["what about silver", "in silver", "in gold", "silver variant", "what about gold", "what about size", "any other color", "other sizes"]
        if any(kw in text_lower for kw in variant_triggers):
            extracted_variant = "silver" if "silver" in text_lower else ("gold" if "gold" in text_lower else None)
            return IntentClassificationResult(
                intent=Intent.variant_query,
                variant=extracted_variant,
                confidence=0.92,
            )

        # 7. Price Query ("how much?", "price", "cost", "how much is it?")
        price_triggers = ["how much", "price", "cost", "rate", "how much is this", "how much is it"]
        if any(kw in text_lower for kw in price_triggers) and not any(kw in text_lower for kw in ["stock", "available"]):
            return IntentClassificationResult(
                intent=Intent.price_query,
                confidence=0.95,
            )

        # 8. Stock / Availability Query ("is this in stock", "available", "is it available?")
        stock_triggers = ["available", "in stock", "stock", "left", "pieces left", "is it available", "is this available"]
        if any(kw in text_lower for kw in stock_triggers):
            return IntentClassificationResult(
                intent=Intent.stock_query,
                confidence=0.95,
            )

        # 9. Greeting ("hello", "hi", "hey", "good morning")
        if re.match(r"^(hello|hi|hey|good\s+morning|good\s+evening|namaste)\b", text_lower):
            return IntentClassificationResult(
                intent=Intent.greeting,
                confidence=0.95,
            )

        # Default fallback
        return IntentClassificationResult(
            intent=Intent.other,
            confidence=0.80,
        )

    def _extract_quantity(self, text_lower: str) -> Optional[int]:
        """Extract explicit quantity integer from text."""
        # Word numbers
        word_to_num = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6}
        for word, num in word_to_num.items():
            if re.search(rf"\b{word}\b", text_lower):
                return num

        # Digits (e.g. '2 pieces', 'qty 2', 'get 2')
        match = re.search(r"\b(\d+)\s*(?:pieces?|units?|items?|more|instead)?\b", text_lower)
        if match:
            try:
                val = int(match.group(1))
                if 1 <= val <= 100:
                    return val
            except ValueError:
                pass
        return None

    def _classify_with_llm(
        self,
        text: str,
        context: Optional[ConversationContext],
    ) -> IntentClassificationResult:
        """Execute structured LLM classification using Claude."""
        active_prod_info = (
            f"Active product: {context.active_product_name} (ID: {context.active_product_id})"
            if context and context.active_product_id else "Active product: None"
        )
        stage_info = f"Current conversation stage: {context.conversation_stage.value if context else 'discovery'}"
        pending_info = f"Pending action: {context.pending_action if context else 'None'}"

        prompt = f"""You are the NLU intent classifier for SellerPilot AI, a D2C handmade jewelry brand.
Classify the customer message into the appropriate structured Intent.

Context:
{active_prod_info}
{stage_info}
{pending_info}

Customer message:
"{text}"

Possible intents:
greeting, product_search, stock_query, price_query, variant_query, shipping_query,
purchase_intent, purchase_confirmation, quantity_change, order_status, bargaining,
return_refund, complaint, other.
"""
        return self.llm.generate_structured_output(
            prompt=prompt,
            response_model=IntentClassificationResult,
            system_prompt="Classify conversational commerce inquiries with high precision.",
        )
