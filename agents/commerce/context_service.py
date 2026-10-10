"""Conversation Context Service for SellerPilot AI.

Architectural Viva Notes:
1. Conversation Isolation: Contexts are strictly keyed per conversation / (customer_id, channel).
   Ensures zero cross-talk or leaked active products between different customers.
2. Multi-tier Persistence: Supports persistent SQLite storage via ConversationContextORM
   alongside in-memory session caching for fast access and testing without active database sessions.
3. Multi-turn Memory: Tracks active product, stages, pending actions, requested quantities,
   and recent dialogue history.
"""

from datetime import datetime
import logging
from typing import Any, Callable, Optional
from sqlalchemy.orm import Session
from core.schemas import ConversationContext, ConversationStage, Intent
from db.base import SessionLocal
from db.conversation_models import ConversationContextORM, ConversationORM

logger = logging.getLogger(__name__)


class ConversationContextManager:
    """Manages creation, loading, and persistence of conversation contexts."""

    def __init__(self, session_factory: Callable[[], Session] | None = None):
        self.session_factory = session_factory or SessionLocal
        self._memory_cache: dict[tuple[str, str], ConversationContext] = {}

    def get_or_create(
        self,
        customer_id: str,
        channel: str,
        conversation_id: int | None = None,
        db: Session | None = None,
    ) -> ConversationContext:
        """Fetch active conversation context or initialize a fresh one."""
        cache_key = (customer_id, channel)

        # 1. If explicit db session or conversation_id provided, check SQLite
        if db is not None:
            orm_ctx = self._find_orm_context(db, customer_id, channel, conversation_id)
            if orm_ctx:
                ctx = self._orm_to_context(orm_ctx)
                self._memory_cache[cache_key] = ctx
                return ctx

        # 2. Check in-memory session cache
        if cache_key in self._memory_cache:
            ctx = self._memory_cache[cache_key]
            if conversation_id and not ctx.conversation_id:
                ctx.conversation_id = conversation_id
            return ctx

        # 3. Check SQLite using session factory if not already checked
        if self.session_factory:
            try:
                with self.session_factory() as session:
                    orm_ctx = self._find_orm_context(session, customer_id, channel, conversation_id)
                    if orm_ctx:
                        ctx = self._orm_to_context(orm_ctx)
                        self._memory_cache[cache_key] = ctx
                        return ctx
            except Exception as e:
                logger.debug("Database lookup for context returned exception: %s", e)

        # 4. Initialize fresh context
        new_ctx = ConversationContext(
            conversation_id=conversation_id,
            customer_id=customer_id,
            channel=channel,
            active_product_id=None,
            active_product_name=None,
            previous_intent=None,
            conversation_stage=ConversationStage.discovery,
            pending_action=None,
            requested_quantity=1,
            selected_size=None,
            selected_color=None,
            shipping_city=None,
            last_agent_question=None,
            recent_history=[],
            metadata={},
        )
        self._memory_cache[cache_key] = new_ctx
        return new_ctx

    def save(
        self,
        context: ConversationContext,
        db: Session | None = None,
    ) -> None:
        """Persist conversation context to memory and SQLite."""
        cache_key = (context.customer_id, context.channel)
        self._memory_cache[cache_key] = context

        # Persist to SQLite
        if db is not None:
            self._save_to_db(db, context)
            return

        if self.session_factory:
            try:
                with self.session_factory() as session:
                    self._save_to_db(session, context)
                    session.commit()
            except Exception as e:
                logger.debug("Could not commit context to database: %s", e)

    def reset(self, customer_id: str, channel: str) -> None:
        """Clear memory cache for a customer thread."""
        cache_key = (customer_id, channel)
        if cache_key in self._memory_cache:
            del self._memory_cache[cache_key]

    def clear_cache(self) -> None:
        """Clear all entries from in-memory cache."""
        self._memory_cache.clear()

    def _find_orm_context(
        self,
        db: Session,
        customer_id: str,
        channel: str,
        conversation_id: int | None = None,
    ) -> Optional[ConversationContextORM]:
        if conversation_id:
            ctx = (
                db.query(ConversationContextORM)
                .filter(
                    ConversationContextORM.conversation_id == conversation_id,
                    ConversationContextORM.customer_id == customer_id,
                )
                .first()
            )
            if ctx:
                return ctx
        return (
            db.query(ConversationContextORM)
            .filter(
                ConversationContextORM.customer_id == customer_id,
                ConversationContextORM.channel == channel,
            )
            .order_by(ConversationContextORM.updated_at.desc())
            .first()
        )

    def _save_to_db(self, db: Session, context: ConversationContext) -> None:
        # Resolve conversation_id if missing
        conv_id = context.conversation_id
        if not conv_id:
            conv = (
                db.query(ConversationORM)
                .filter(
                    ConversationORM.customer_id == context.customer_id,
                    ConversationORM.channel == context.channel,
                )
                .order_by(ConversationORM.updated_at.desc())
                .first()
            )
            if not conv:
                conv = ConversationORM(
                    customer_id=context.customer_id,
                    channel=context.channel,
                    created_at=datetime.utcnow(),
                    updated_at=datetime.utcnow(),
                )
                db.add(conv)
                db.flush()

            conv_id = conv.id
            context.conversation_id = conv_id


        orm_ctx = db.query(ConversationContextORM).filter(ConversationContextORM.conversation_id == conv_id).first()
        if not orm_ctx:
            orm_ctx = ConversationContextORM(
                conversation_id=int(conv_id),
                customer_id=context.customer_id,
                channel=context.channel,
            )
            db.add(orm_ctx)

        orm_ctx.active_product_id = context.active_product_id
        orm_ctx.active_product_name = context.active_product_name
        orm_ctx.previous_intent = context.previous_intent.value if context.previous_intent else None
        orm_ctx.conversation_stage = (
            context.conversation_stage.value
            if isinstance(context.conversation_stage, ConversationStage)
            else str(context.conversation_stage)
        )
        orm_ctx.pending_action = context.pending_action
        orm_ctx.requested_quantity = context.requested_quantity
        orm_ctx.selected_size = context.selected_size
        orm_ctx.selected_color = context.selected_color
        orm_ctx.shipping_city = context.shipping_city
        orm_ctx.last_agent_question = context.last_agent_question
        orm_ctx.context_metadata = {
            "recent_history": context.recent_history[-10:],
            "extra": context.metadata,
        }
        orm_ctx.updated_at = datetime.utcnow()

    def _orm_to_context(self, orm: ConversationContextORM) -> ConversationContext:
        stage = ConversationStage.discovery
        if orm.conversation_stage:
            try:
                stage = ConversationStage(orm.conversation_stage)
            except ValueError:
                stage = ConversationStage.discovery

        prev_intent = None
        if orm.previous_intent:
            try:
                prev_intent = Intent(orm.previous_intent)
            except ValueError:
                prev_intent = None

        meta = orm.context_metadata or {}
        recent_hist = meta.get("recent_history", [])

        return ConversationContext(
            conversation_id=orm.conversation_id,
            customer_id=orm.customer_id,
            channel=orm.channel,
            active_product_id=orm.active_product_id,
            active_product_name=orm.active_product_name,
            previous_intent=prev_intent,
            conversation_stage=stage,
            pending_action=orm.pending_action,
            requested_quantity=orm.requested_quantity,
            selected_size=orm.selected_size,
            selected_color=orm.selected_color,
            shipping_city=orm.shipping_city,
            last_agent_question=orm.last_agent_question,
            recent_history=recent_hist,
            metadata=meta.get("extra", {}),
        )


# Global default context manager instance
default_context_manager = ConversationContextManager()
