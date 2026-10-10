"""Conversational Commerce Agent for SellerPilot AI.

Architectural Viva Notes:
1. Context-Aware Multi-Turn Intelligence:
   Tracks conversation_id, active_product, conversation_stage, pending_action,
   and requested_quantity across conversational turns. Resolves pronouns and deictic
   references ("this", "it", "place this") without losing context.
2. Protocol Dependency Inversion:
   Adheres strictly to the CommerceService protocol. Receives InventoryService and
   optional OrderService / ConversationContext as injected dependencies.
3. Zero Hallucination Guarantee:
   Product prices, materials, and live inventory counts are strictly retrieved via
   InventoryService.find_products() and InventoryService.get_stock().
4. Strict Multi-tier Escalation Guard:
   Preserves all human escalation rules for complaints, refunds, bargaining,
   wholesale/bulk inquiries, and bespoke customization.
5. Structured Order Workflow:
   Supports explicit multi-stage purchase flow:
   availability check -> details/summary -> explicit confirmation -> atomic reservation.
"""

from datetime import datetime
import logging
import re
from typing import Any, Optional
from agents.commerce.context_service import ConversationContextManager, default_context_manager
from agents.commerce.intent_classifier import IntentClassificationResult, IntentClassifier
from agents.commerce.order_service import OrderService
from agents.commerce.product_resolver import ProductResolution, ProductResolver
from core.config import settings
from core.interfaces import CommerceService, InventoryService
from core.schemas import (
    AgentAction,
    ConversationContext,
    ConversationStage,
    IncomingMessage,
    Intent,
    Product,
    StockStatus,
)

logger = logging.getLogger(__name__)


class ConversationalCommerceAgent(CommerceService):
    """Conversational Commerce Agent answering customer DMs across Instagram and WhatsApp."""

    def __init__(
        self,
        confidence_threshold: float | None = None,
        context_manager: ConversationContextManager | None = None,
        classifier: IntentClassifier | None = None,
    ):
        self.confidence_threshold = (
            confidence_threshold if confidence_threshold is not None
            else settings.ESCALATION_CONFIDENCE_THRESHOLD
        )
        self.context_manager = context_manager or default_context_manager
        self.classifier = classifier or IntentClassifier()

    def handle_message(
        self,
        msg: IncomingMessage,
        inventory: InventoryService,
        context: Optional[ConversationContext] = None,
        order_service: Optional[OrderService] = None,
    ) -> AgentAction:
        """Process inbound customer DM and return structured AgentAction.

        Architectural Flow:
        1. Context Resolution: Retrieve or initialize customer-isolated context.
        2. Intent Classification: Categorize intent with contextual awareness.
        3. Product Resolution: Resolve exact names, typos, or pronouns ('this', 'it').
        4. State Machine Execution: Progress through conversational stages.
        5. Grounded Persistence: Create order and reserve stock only on explicit confirmation.
        6. Context Synchronization: Persist updated stage, active product, and history.
        """
        text = msg.text.strip()
        text_lower = text.lower()

        # 1. Retrieve or isolate context
        ctx = context or self.context_manager.get_or_create(
            customer_id=msg.customer_id,
            channel=msg.channel,
        )
        orders = order_service or OrderService()
        resolver = ProductResolver(inventory)

        # 1b. Check for duplicate order confirmation message idempotency
        if msg.message_id:
            existing_order = orders.get_order_by_confirmation_message(msg.message_id)
            if existing_order:
                return AgentAction(
                    agent="commerce",
                    intent=Intent.purchase_confirmation,
                    product_id=existing_order.product_id,
                    response_text=(
                        f"Your order #{existing_order.order_id} for {existing_order.product_name} is already confirmed and reserved! 🌸 "
                        f"We'll dispatch it within 24-48 business hours with tracked delivery."
                    ),
                    confidence=1.0,
                    conversation_stage=ConversationStage.order_created,
                    active_product_name=existing_order.product_name,
                    order_id=existing_order.order_id,
                )


        # 2. Intent Classification
        classification: IntentClassificationResult = self.classifier.classify(text, ctx)

        # 3. Handle Escalations Immediately (Preserve Safety Guardrails)
        if classification.escalate:
            ctx.conversation_stage = ConversationStage.escalated
            ctx.previous_intent = classification.intent
            self.context_manager.save(ctx)

            if classification.intent == Intent.complaint:
                return AgentAction(
                    agent="commerce",
                    intent=Intent.other if classification.intent == Intent.other else classification.intent,
                    product_id=ctx.active_product_id,
                    response_text=(
                        "I am so truly sorry to hear about this! 🤍 We hold our craftsmanship to the highest "
                        "standard and want to make this right immediately. I'm connecting you directly with "
                        "our founder right now to resolve this for you."
                    ),
                    escalate=True,
                    escalation_reason=classification.escalation_reason,
                    confidence=classification.confidence,
                    conversation_stage=ConversationStage.escalated,
                )

            if "bulk" in (classification.escalation_reason or "").lower() or any(k in text_lower for k in ["bulk", "wholesale"]):
                return AgentAction(
                    agent="commerce",
                    intent=Intent.other,
                    product_id=ctx.active_product_id,
                    response_text=(
                        "Congratulations on your celebration or special event! 🌸 For large or wholesale orders, "
                        "we offer dedicated artisan batch timelines and custom pricing. I'm handing this over to our "
                        "founder to tailor a proposal for you!"
                    ),
                    escalate=True,
                    escalation_reason="Bulk or wholesale order inquiry requiring founder review.",
                    confidence=classification.confidence,
                    conversation_stage=ConversationStage.escalated,
                )

            if "bespoke" in (classification.escalation_reason or "").lower() or any(k in text_lower for k in ["custom", "engrave", "bespoke"]):
                return AgentAction(
                    agent="commerce",
                    intent=Intent.other,
                    product_id=ctx.active_product_id,
                    response_text=(
                        "We love creating bespoke pieces! ✨ Because each custom commission involves personal gemstone "
                        "selection and wire sizing, I'm bringing our artisan directly into this chat to help you design it."
                    ),
                    escalate=True,
                    escalation_reason="Bespoke customization request requiring artisan consultation.",
                    confidence=classification.confidence,
                    conversation_stage=ConversationStage.escalated,
                )

            if classification.intent == Intent.return_refund or "refund" in (classification.escalation_reason or "").lower():
                return AgentAction(
                    agent="commerce",
                    intent=Intent.other if classification.intent == Intent.other else classification.intent,
                    product_id=ctx.active_product_id,
                    response_text=(
                        "We want you to love your jewelry completely. 🌿 Let me connect you directly with our "
                        "orders team so they can process your return or refund request according to our studio policy."
                    ),
                    escalate=True,
                    escalation_reason="Refund or return inquiry requiring human policy authorization.",
                    confidence=classification.confidence,
                    conversation_stage=ConversationStage.escalated,
                )

            if classification.intent == Intent.bargaining:
                return AgentAction(
                    agent="commerce",
                    intent=Intent.price_query,
                    product_id=ctx.active_product_id,
                    response_text=(
                        "Our jewelry is mindfully priced to honor ethical gemstones and fair artisan wages. ✨ "
                        "I'm looping in our founder to see if any seasonal welcome offer can be shared with you!"
                    ),
                    escalate=True,
                    escalation_reason="Price bargaining or unapproved discount negotiation.",
                    confidence=classification.confidence,
                    conversation_stage=ConversationStage.escalated,
                )

        # 4. Resolve Product Reference
        resolution: ProductResolution = resolver.resolve(text, ctx)
        matched_product: Optional[Product] = resolution.product

        # If a new product is successfully identified, update active product
        if matched_product:
            ctx.active_product_id = matched_product.id
            ctx.active_product_name = matched_product.name

        # 5. Route by Intent & Conversational Stage

        # A0. Pending Size Selection Resolution
        if ctx.pending_action == "select_size":
            active_prod = matched_product or (resolver._get_product_by_id(ctx.active_product_id) if ctx.active_product_id else None)
            if active_prod:
                size_choice = self._extract_requested_size(text)
                if not size_choice and active_prod.sizes:
                    for sz in active_prod.sizes:
                        if sz.lower() in text_lower:
                            size_choice = sz
                            break
                if size_choice:
                    ctx.selected_size = size_choice
                    ctx.conversation_stage = ConversationStage.awaiting_order_confirmation
                    ctx.pending_action = "awaiting_order_confirmation"
                    self.context_manager.save(ctx)

                    qty = ctx.requested_quantity or 1
                    total_amt = active_prod.price * qty
                    shipping_label = "Complimentary shipping ✨" if total_amt >= 1500 else "Standard tracked shipping included"
                    return AgentAction(
                        agent="commerce",
                        intent=Intent.purchase_intent,
                        product_id=active_prod.id,
                        response_text=(
                            f"Wonderful, size {size_choice} noted! ✨\n\n"
                            f"Order Summary:\n"
                            f"• {qty}x {active_prod.name} (Size {size_choice})\n"
                            f"• Total: ₹{total_amt:,.0f} ({shipping_label})\n\n"
                            f"Please reply 'confirm' to place your order!"
                        ),
                        confidence=0.96,
                        conversation_stage=ConversationStage.awaiting_order_confirmation,
                        active_product_name=active_prod.name,
                        pending_action="awaiting_order_confirmation",
                        requested_quantity=qty,
                    )

        # A. Shipping Queries
        if classification.intent == Intent.shipping_query:
            ctx.previous_intent = Intent.shipping_query
            self.context_manager.save(ctx)
            return AgentAction(
                agent="commerce",
                intent=Intent.shipping_query,
                product_id=ctx.active_product_id,
                response_text=(
                    "We dispatch all studio orders within 24-48 business hours with tracked delivery across the country! 📦 "
                    "Standard delivery usually takes 3 to 5 business days. We also offer complimentary shipping on all "
                    "orders above ₹1,500. ✨"
                ),
                escalate=False,
                confidence=0.95,
                conversation_stage=ctx.conversation_stage,
                active_product_name=ctx.active_product_name,
            )

        # B. Order Status Queries
        if classification.intent == Intent.order_status:
            customer_orders = orders.get_orders_for_customer(msg.customer_id)
            if customer_orders:
                latest_order = customer_orders[0]
                resp = (
                    f"Your order #{latest_order.order_id} for {latest_order.product_name} is {latest_order.status}! 📦 "
                    f"Handcrafted and packaged with care. We dispatch all pieces within 24-48 business hours with tracked delivery. ✨"
                )
            else:
                resp = (
                    "I couldn't locate an active order for this chat account. 🤍 "
                    "Could you please share your Order ID (e.g., ORD-...) so I can check its delivery status for you?"
                )
            ctx.previous_intent = Intent.order_status
            self.context_manager.save(ctx)
            return AgentAction(
                agent="commerce",
                intent=Intent.order_status,
                product_id=ctx.active_product_id,
                response_text=resp,
                escalate=False,
                confidence=0.95,
                conversation_stage=ctx.conversation_stage,
            )

        # C. Quantity Change Inquiries
        if classification.intent == Intent.quantity_change:
            target_qty = classification.quantity or 1
            if not matched_product and ctx.active_product_id:
                matched_product = resolver._get_product_by_id(ctx.active_product_id)

            if not matched_product:
                resp = "Which piece would you like to update the quantity for? ✨"
                return AgentAction(
                    agent="commerce",
                    intent=Intent.quantity_change,
                    product_id=None,
                    response_text=resp,
                    confidence=0.85,
                )

            stock = inventory.get_stock(matched_product.id)
            if stock and stock.quantity >= target_qty:
                ctx.requested_quantity = target_qty
                ctx.conversation_stage = ConversationStage.availability_verified
                ctx.pending_action = "awaiting_purchase_intent"
                ctx.previous_intent = Intent.quantity_change
                self.context_manager.save(ctx)

                total_amount = matched_product.price * target_qty
                return AgentAction(
                    agent="commerce",
                    intent=Intent.quantity_change,
                    product_id=matched_product.id,
                    response_text=(
                        f"Yes! We have {stock.quantity} available in our studio. For {target_qty} pieces of the "
                        f"{matched_product.name}, the total is ₹{total_amount:,.0f}. ✨ "
                        f"Would you like to place an order for {target_qty}?"
                    ),
                    confidence=0.95,
                    conversation_stage=ctx.conversation_stage,
                    active_product_name=matched_product.name,
                    requested_quantity=target_qty,
                )
            else:
                available_qty = stock.quantity if stock else 0
                return AgentAction(
                    agent="commerce",
                    intent=Intent.quantity_change,
                    product_id=matched_product.id,
                    response_text=(
                        f"We currently have {available_qty} pieces remaining in our studio for the {matched_product.name}. "
                        f"Would you like to reserve the remaining available stock?"
                    ),
                    confidence=0.90,
                    conversation_stage=ctx.conversation_stage,
                    active_product_name=matched_product.name,
                )

        # D. Variant Query ("what about silver?", "in gold?")
        if classification.intent == Intent.variant_query:
            if not matched_product and ctx.active_product_id:
                matched_product = resolver._get_product_by_id(ctx.active_product_id)

            if matched_product:
                queried_variant = (classification.variant or "").lower()
                material_lower = matched_product.material.lower()
                colors_lower = [c.lower() for c in matched_product.colors]

                has_variant = queried_variant in material_lower or any(queried_variant in c for c in colors_lower)
                if has_variant:
                    resp = (
                        f"Yes! The {matched_product.name} is crafted in {matched_product.material}. ✨ "
                        f"Would you like to secure one?"
                    )
                else:
                    resp = (
                        f"Our {matched_product.name} is currently crafted in {matched_product.material} "
                        f"and is not available in {queried_variant or 'that variant'}. 🌙 "
                        f"Would you like us to show you other pieces in our studio?"
                    )
                ctx.previous_intent = Intent.variant_query
                self.context_manager.save(ctx)
                return AgentAction(
                    agent="commerce",
                    intent=Intent.variant_query,
                    product_id=matched_product.id,
                    response_text=resp,
                    confidence=0.95,
                    conversation_stage=ctx.conversation_stage,
                    active_product_name=matched_product.name,
                )

        # E. Purchase Confirmation ("confirm", "yes confirm", "proceed")
        if classification.intent == Intent.purchase_confirmation:
            if not matched_product and ctx.active_product_id:
                matched_product = resolver._get_product_by_id(ctx.active_product_id)

            if matched_product and (ctx.conversation_stage == ConversationStage.awaiting_order_confirmation or ctx.pending_action == "awaiting_order_confirmation"):
                qty = ctx.requested_quantity or 1
                success, order, notice = orders.create_order(
                    customer_id=msg.customer_id,
                    channel=msg.channel,
                    product_id=matched_product.id,
                    product_name=matched_product.name,
                    quantity=qty,
                    unit_price=matched_product.price,
                    inventory_service=inventory,
                    size=ctx.selected_size,
                    color=ctx.selected_color,
                    confirmation_message_id=msg.message_id,
                    conversation_id=ctx.conversation_id,
                )

                if success and order:
                    ctx.conversation_stage = ConversationStage.order_created
                    ctx.pending_action = None
                    self.context_manager.save(ctx)

                    if notice and "already" in notice.lower():
                        resp = f"Your order #{order.order_id} for {matched_product.name} is already confirmed and reserved! 🌸"
                    else:
                        resp = (
                            f"Your order #{order.order_id} is confirmed! 🎉 {qty}x {matched_product.name} has been reserved for you. "
                            f"We'll dispatch it within 24-48 business hours with tracked delivery. "
                            f"Thank you for supporting handcrafted jewellery! ✨"
                        )
                    return AgentAction(
                        agent="commerce",
                        intent=Intent.purchase_confirmation,
                        product_id=matched_product.id,
                        response_text=resp,
                        confidence=0.98,
                        conversation_stage=ConversationStage.order_created,
                        active_product_name=matched_product.name,
                        order_id=order.order_id,
                    )
                else:
                    return AgentAction(
                        agent="commerce",
                        intent=Intent.purchase_confirmation,
                        product_id=matched_product.id,
                        response_text=f"We could not finalize your order: {notice or 'Stock could not be reserved.'} 🤍",
                        confidence=0.90,
                        conversation_stage=ctx.conversation_stage,
                        active_product_name=matched_product.name,
                    )

        # F. Purchase Intent ("yes place this", "place this", "buy this", "i'll take it", "yes")
        if classification.intent == Intent.purchase_intent:
            if not matched_product and ctx.active_product_id:
                matched_product = resolver._get_product_by_id(ctx.active_product_id)

            if not matched_product:
                return AgentAction(
                    agent="commerce",
                    intent=Intent.purchase_intent,
                    product_id=None,
                    response_text="I'd love to help you place an order! ✨ Could you share which piece from our collection you'd like to order?",
                    confidence=0.85,
                    conversation_stage=ConversationStage.discovery,
                )

            # Check stock
            stock = inventory.get_stock(matched_product.id)
            qty = ctx.requested_quantity or 1
            if not stock or stock.quantity < qty:
                return AgentAction(
                    agent="commerce",
                    intent=Intent.purchase_intent,
                    product_id=matched_product.id,
                    response_text=(
                        f"I'm so sorry, but our {matched_product.name} is currently sold out! 🤍 "
                        f"Shall I notify you as soon as our next studio batch is crafted?"
                    ),
                    confidence=0.95,
                    conversation_stage=ctx.conversation_stage,
                    active_product_name=matched_product.name,
                )

            # Check if variant selection is needed
            requested_size = self._extract_requested_size(text)
            if requested_size and matched_product.sizes and requested_size in matched_product.sizes:
                ctx.selected_size = requested_size

            # If product has multiple sizes and no size selected yet
            if matched_product.sizes and len(matched_product.sizes) > 1 and not ctx.selected_size:
                ctx.conversation_stage = ConversationStage.awaiting_purchase_details
                ctx.pending_action = "select_size"
                self.context_manager.save(ctx)

                available_sizes = ", ".join(matched_product.sizes)
                return AgentAction(
                    agent="commerce",
                    intent=Intent.purchase_intent,
                    product_id=matched_product.id,
                    response_text=(
                        f"Wonderful choice! ✨ To prepare your order for the {matched_product.name} "
                        f"(priced at ₹{matched_product.price:,.0f}), which size would you prefer: {available_sizes}?"
                    ),
                    confidence=0.95,
                    conversation_stage=ConversationStage.awaiting_purchase_details,
                    active_product_name=matched_product.name,
                    pending_action="select_size",
                )

            # Summarize and await final confirmation
            ctx.conversation_stage = ConversationStage.awaiting_order_confirmation
            ctx.pending_action = "awaiting_order_confirmation"
            self.context_manager.save(ctx)

            size_label = f" (Size {ctx.selected_size})" if ctx.selected_size else ""
            total_amt = matched_product.price * qty
            shipping_label = "Complimentary shipping ✨" if total_amt >= 1500 else "Standard tracked shipping included"

            return AgentAction(
                agent="commerce",
                intent=Intent.purchase_intent,
                product_id=matched_product.id,
                response_text=(
                    f"I would be delighted to arrange that for you! ✨\n\n"
                    f"Order Summary:\n"
                    f"• {qty}x {matched_product.name}{size_label}\n"
                    f"• Total: ₹{total_amt:,.0f} ({shipping_label})\n\n"
                    f"Please reply 'confirm' to place your order!"
                ),
                confidence=0.96,
                conversation_stage=ConversationStage.awaiting_order_confirmation,
                active_product_name=matched_product.name,
                pending_action="awaiting_order_confirmation",
                requested_quantity=qty,
            )

        # G. Ambiguous Product Reference
        if resolution.is_ambiguous:
            candidate_names = [p.name for p in resolution.candidates]
            cand_str = ", ".join(candidate_names)
            return AgentAction(
                agent="commerce",
                intent=Intent.product_search,
                product_id=None,
                response_text=f"We have a few pieces in that collection: {cand_str}. Which one would you like to know more about? ✨",
                confidence=0.80,
                conversation_stage=ConversationStage.discovery,
            )

        # H. Price Query ("how much?")
        if classification.intent == Intent.price_query:
            if not matched_product and ctx.active_product_id:
                matched_product = resolver._get_product_by_id(ctx.active_product_id)

            if matched_product:
                stock = inventory.get_stock(matched_product.id)
                stock_note = ""
                if stock and not stock.in_stock:
                    stock_note = " (Note: currently awaiting our next studio batch)"
                elif stock and stock.low_stock:
                    stock_note = f" (Only {stock.quantity} left in studio!)"

                ctx.conversation_stage = ConversationStage.product_selected
                ctx.pending_action = "awaiting_purchase_intent"
                ctx.previous_intent = Intent.price_query
                self.context_manager.save(ctx)

                return AgentAction(
                    agent="commerce",
                    intent=Intent.price_query,
                    product_id=matched_product.id,
                    response_text=(
                        f"Our {matched_product.name} is ₹{matched_product.price:,.0f}{stock_note}. ✨ "
                        f"Handcrafted in {matched_product.material}. Would you like to secure one?"
                    ),
                    confidence=0.95,
                    conversation_stage=ConversationStage.product_selected,
                    active_product_name=matched_product.name,
                )

        # I. Stock / Availability Query
        is_avail_text = any(kw in text_lower for kw in ["available", "in stock", "stock", "left", "size", "pieces left", "buy", "order"])
        if classification.intent == Intent.stock_query or is_avail_text:
            if not matched_product and ctx.active_product_id and resolution.resolved_from_context:
                matched_product = resolver._get_product_by_id(ctx.active_product_id)

            if not matched_product:
                # Ambiguous "is this available" with no product named
                return AgentAction(
                    agent="commerce",
                    intent=Intent.stock_query,
                    product_id=None,
                    response_text=(
                        "Hello! ✨ We'd love to check availability for you. Could you share the name of the piece "
                        "or send a photo/screenshot of what you're eyeing?"
                    ),
                    escalate=True,
                    escalation_reason="Ambiguous inquiry: Customer asked about availability without naming a specific product.",
                    confidence=0.60,
                    conversation_stage=ConversationStage.discovery,
                )

            # Strict live inventory check via injected protocol
            stock = inventory.get_stock(matched_product.id)

            # Size Specific Inquiry Check
            requested_size = self._extract_requested_size(text)
            if requested_size and matched_product.sizes:
                if requested_size not in matched_product.sizes:
                    available_sizes_str = ", ".join(matched_product.sizes)
                    return AgentAction(
                        agent="commerce",
                        intent=Intent.stock_query,
                        product_id=matched_product.id,
                        response_text=(
                            f"Our {matched_product.name} is currently crafted in sizes: {available_sizes_str}. "
                            f"We don't have size {requested_size} in standard stock right now. 🌙 "
                            f"Would you like us to see if our artisan can custom-size this for you?"
                        ),
                        escalate=False,
                        confidence=0.92,
                        conversation_stage=ConversationStage.product_selected,
                        active_product_name=matched_product.name,
                    )
                else:
                    ctx.selected_size = requested_size

            if stock is None or not stock.in_stock or stock.quantity == 0:
                ctx.conversation_stage = ConversationStage.product_selected
                self.context_manager.save(ctx)
                return AgentAction(
                    agent="commerce",
                    intent=Intent.stock_query,
                    product_id=matched_product.id,
                    response_text=(
                        f"Our {matched_product.name} is currently sold out! 🤍 Since every piece is handmade in "
                        f"small batches, shall I notify you as soon as our next studio batch is ready?"
                    ),
                    escalate=False,
                    confidence=0.95,
                    conversation_stage=ConversationStage.product_selected,
                    active_product_name=matched_product.name,
                )

            if stock.low_stock:
                ctx.conversation_stage = ConversationStage.availability_verified
                ctx.pending_action = "awaiting_purchase_intent"
                self.context_manager.save(ctx)
                return AgentAction(
                    agent="commerce",
                    intent=Intent.stock_query,
                    product_id=matched_product.id,
                    response_text=(
                        f"Yes, our {matched_product.name} is in stock! ✨ We only have {stock.quantity} pieces remaining "
                        f"in our studio, priced at ₹{matched_product.price:,.0f}. Would you like to reserve yours now?"
                    ),
                    escalate=False,
                    confidence=0.95,
                    conversation_stage=ConversationStage.availability_verified,
                    active_product_name=matched_product.name,
                )

            ctx.conversation_stage = ConversationStage.availability_verified
            ctx.pending_action = "awaiting_purchase_intent"
            self.context_manager.save(ctx)
            return AgentAction(
                agent="commerce",
                intent=Intent.stock_query,
                product_id=matched_product.id,
                response_text=(
                    f"Yes! The {matched_product.name} is available in stock ({stock.quantity} available), "
                    f"priced at ₹{matched_product.price:,.0f}. Hand-forged in {matched_product.material}. ✨ "
                    f"Would you like to place an order?"
                ),
                escalate=False,
                confidence=0.95,
                conversation_stage=ConversationStage.availability_verified,
                active_product_name=matched_product.name,
            )

        # J. Greeting
        if classification.intent == Intent.greeting:
            if ctx.active_product_name:
                resp = (
                    f"Hello again! ✨ We were just looking at the {ctx.active_product_name}. "
                    f"Would you like to know more about it or place an order?"
                )
            else:
                resp = (
                    "Hello! Welcome to Aura Jewels. 🌿 Every piece in our studio is handmade with natural gemstones. "
                    "How can I help you find the perfect piece today? ✨"
                )
            return AgentAction(
                agent="commerce",
                intent=Intent.greeting,
                product_id=ctx.active_product_id,
                response_text=resp,
                confidence=0.95,
                conversation_stage=ctx.conversation_stage,
                active_product_name=ctx.active_product_name,
            )

        # K. Fallback / Unrecognized in active context
        if ctx.active_product_name:
            return AgentAction(
                agent="commerce",
                intent=Intent.other,
                product_id=ctx.active_product_id,
                response_text=(
                    f"I'm here to help with the {ctx.active_product_name}! ✨ "
                    f"Would you like to check its availability, sizing, or proceed with an order?"
                ),
                escalate=False,
                confidence=0.85,
                conversation_stage=ctx.conversation_stage,
                active_product_name=ctx.active_product_name,
            )

        return AgentAction(
            agent="commerce",
            intent=Intent.other,
            product_id=None,
            response_text=(
                "Hello! Welcome to Aura Jewels. 🌿 Every piece in our studio is handmade with natural gemstones. "
                "How can I help you find the perfect piece today? ✨"
            ),
            escalate=False,
            confidence=0.80,
            conversation_stage=ConversationStage.discovery,
        )

    def _extract_requested_size(self, text: str) -> str | None:
        """Extract requested size numbers or strings (e.g. 'size 7', 'size 10', 'medium')."""
        match = re.search(r"\bsize\s*([a-zA-Z0-9]+)\b", text, re.IGNORECASE)
        if match:
            val = match.group(1)
            return val.upper() if val.isalpha() and len(val) <= 2 else val.capitalize()
        # Direct word sizes: Small, Medium, Large
        for s in ["small", "medium", "large"]:
            if re.search(rf"\b{s}\b", text, re.IGNORECASE):
                return s.capitalize()
        return None
