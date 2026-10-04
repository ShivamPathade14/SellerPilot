"""FastAPI routes for simulated chat webhooks and conversation histories.

Architectural Viva Notes:
1. Webhook Idempotency: Validates message_id against MessageORM before triggering
   the LangGraph Orchestrator to prevent duplicate processing on retries.
2. Decoupled Ingestion: Isolates the webhook endpoint from specific messaging protocols
   (Instagram Graph API, WhatsApp Business API), enabling seamless transition from
   simulation to production.
3. Persistent Conversation State: Automatically records incoming customer messages and
   resulting AgentAction responses in SQLite via SQLAlchemy.
"""

from datetime import datetime
import logging
from typing import Any, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session
from core.schemas import AgentAction, Event, IncomingMessage
from db.base import get_db
from db.conversation_models import ConversationORM, MessageORM

logger = logging.getLogger(__name__)

router = APIRouter(prefix="", tags=["chat"])


@router.post("/webhook/message")
def handle_incoming_message(
    msg: IncomingMessage,
    request: Request,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Ingest simulated incoming customer message from Instagram or WhatsApp."""
    # 1. Idempotency Check: Prevent duplicate processing if message_id exists
    existing_message = db.query(MessageORM).filter(MessageORM.message_id == msg.message_id).first()
    if existing_message:
        logger.info("Message %s already processed; returning cached conversation context.", msg.message_id)
        return {
            "status": "already_processed",
            "conversation_id": existing_message.conversation_id,
            "message_id": msg.message_id,
            "notice": "Duplicate message ignored for idempotency.",
        }

    # 2. Resolve or Create Conversation Thread
    conversation = (
        db.query(ConversationORM)
        .filter(
            ConversationORM.customer_id == msg.customer_id,
            ConversationORM.channel == msg.channel,
        )
        .first()
    )

    if not conversation:
        conversation = ConversationORM(
            customer_id=msg.customer_id,
            channel=msg.channel,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        db.add(conversation)
        db.flush()  # Allocate conversation.id

    # 3. Store Incoming Customer Message
    customer_msg_record = MessageORM(
        conversation_id=conversation.id,
        message_id=msg.message_id,
        sender="customer",
        text=msg.text,
        timestamp=msg.timestamp,
        escalated=False,
        confidence=1.0,
    )
    db.add(customer_msg_record)

    # 4. Dispatch Event to LangGraph Orchestrator
    orchestrator = getattr(request.app.state, "orchestrator", None)
    if not orchestrator:
        raise HTTPException(status_code=500, detail="Orchestrator not initialized on app state.")

    event = Event(type="new_dm", payload={"message": msg.model_dump()})
    result = orchestrator.process_event(event)

    if not isinstance(result, AgentAction):
        raise HTTPException(status_code=500, detail="Orchestrator did not return an AgentAction.")

    # 5. Store Outgoing Agent Response
    agent_msg_record = MessageORM(
        conversation_id=conversation.id,
        message_id=f"reply-{msg.message_id}",
        sender="agent",
        text=result.response_text,
        intent=result.intent.value,
        product_id=result.product_id,
        escalated=result.escalate,
        escalation_reason=result.escalation_reason,
        confidence=result.confidence,
        timestamp=datetime.utcnow(),
    )
    db.add(agent_msg_record)

    conversation.updated_at = datetime.utcnow()
    db.commit()

    return {
        "status": "success",
        "conversation_id": conversation.id,
        "action": result.model_dump(),
    }


@router.get("/conversations")
def list_conversations(
    customer_id: Optional[str] = Query(None, description="Filter by customer ID"),
    channel: Optional[str] = Query(None, description="Filter by channel ('instagram' or 'whatsapp')"),
    limit: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
) -> list[dict[str, Any]]:
    """List customer conversations with message counts and latest activity."""
    query = db.query(ConversationORM)
    if customer_id:
        query = query.filter(ConversationORM.customer_id == customer_id)
    if channel:
        query = query.filter(ConversationORM.channel == channel)

    conversations = query.order_by(ConversationORM.updated_at.desc()).limit(limit).all()

    results = []
    for conv in conversations:
        last_msg = (
            db.query(MessageORM)
            .filter(MessageORM.conversation_id == conv.id)
            .order_by(MessageORM.timestamp.desc())
            .first()
        )
        msg_count = db.query(MessageORM).filter(MessageORM.conversation_id == conv.id).count()

        results.append({
            "id": conv.id,
            "customer_id": conv.customer_id,
            "channel": conv.channel,
            "message_count": msg_count,
            "last_message": last_msg.text if last_msg else None,
            "last_message_sender": last_msg.sender if last_msg else None,
            "last_updated": conv.updated_at.isoformat(),
            "created_at": conv.created_at.isoformat(),
        })

    return results


@router.get("/conversations/{conversation_id}")
def get_conversation_history(
    conversation_id: int,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Retrieve full message history for a specific conversation."""
    conv = db.query(ConversationORM).filter(ConversationORM.id == conversation_id).first()
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found.")

    messages = (
        db.query(MessageORM)
        .filter(MessageORM.conversation_id == conversation_id)
        .order_by(MessageORM.timestamp.asc())
        .all()
    )

    return {
        "id": conv.id,
        "customer_id": conv.customer_id,
        "channel": conv.channel,
        "created_at": conv.created_at.isoformat(),
        "updated_at": conv.updated_at.isoformat(),
        "messages": [
            {
                "id": m.id,
                "message_id": m.message_id,
                "sender": m.sender,
                "text": m.text,
                "intent": m.intent,
                "product_id": m.product_id,
                "escalated": m.escalated,
                "escalation_reason": m.escalation_reason,
                "confidence": m.confidence,
                "timestamp": m.timestamp.isoformat(),
            }
            for m in messages
        ],
    }
