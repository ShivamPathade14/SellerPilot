"""Integration tests for FastAPI chat webhook and conversation endpoints."""

from datetime import datetime
import pytest
from fastapi.testclient import TestClient
from api.main import app
from db.base import Base, engine


@pytest.fixture(scope="module")
def client():
    # Ensure fresh DB tables for tests
    Base.metadata.create_all(bind=engine)
    with TestClient(app) as test_client:
        yield test_client
    # Clean up test conversation rows while preserving table schema
    from db.conversation_models import ConversationORM, MessageORM
    from db.base import SessionLocal
    with SessionLocal() as db:
        db.query(MessageORM).delete()
        db.query(ConversationORM).delete()
        db.commit()


def test_health_check_endpoint(client):
    """Verify system health endpoint and mock flag."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["mocks_enabled"] is True


def test_webhook_message_in_stock(client):
    """Verify POST /webhook/message handles in-stock inquiry and persists conversation."""
    payload = {
        "message_id": "test-msg-101",
        "customer_id": "cust-test-1",
        "channel": "instagram",
        "text": "Do you have the Moonstone Wire-Wrapped Ring in size 7?",
        "timestamp": datetime.utcnow().isoformat(),
    }
    response = client.post("/webhook/message", json=payload)
    assert response.status_code == 200
    data = response.json()

    assert data["status"] == "success"
    assert "conversation_id" in data
    action = data["action"]
    assert action["agent"] == "commerce"
    assert action["intent"] == "stock_query"
    assert action["product_id"] == "prod-101"
    assert action["escalate"] is False
    assert "1,450" in action["response_text"]


def test_webhook_message_idempotency(client):
    """Verify duplicate message_id is ignored and marked already_processed."""
    payload = {
        "message_id": "test-msg-idempotent-99",
        "customer_id": "cust-test-2",
        "channel": "whatsapp",
        "text": "How much is the Raw Emerald Pendant?",
        "timestamp": datetime.utcnow().isoformat(),
    }
    # First attempt: processed
    res1 = client.post("/webhook/message", json=payload)
    assert res1.status_code == 200
    assert res1.json()["status"] == "success"

    # Second attempt: detected as duplicate
    res2 = client.post("/webhook/message", json=payload)
    assert res2.status_code == 200
    assert res2.json()["status"] == "already_processed"
    assert "Duplicate message ignored" in res2.json()["notice"]


def test_webhook_message_escalation_flow(client):
    """Verify customer complaint triggers escalation flag and reasons."""
    payload = {
        "message_id": "test-msg-complaint-500",
        "customer_id": "cust-angry-client",
        "channel": "instagram",
        "text": "The ring broke after one day! I am furious and want a refund immediately!",
        "timestamp": datetime.utcnow().isoformat(),
    }
    response = client.post("/webhook/message", json=payload)
    assert response.status_code == 200
    data = response.json()

    assert data["status"] == "success"
    action = data["action"]
    assert action["escalate"] is True
    assert action["escalation_reason"] is not None


def test_get_conversations_list(client):
    """Verify GET /conversations lists conversation threads with message counts."""
    response = client.get("/conversations")
    assert response.status_code == 200
    conversations = response.json()
    assert isinstance(conversations, list)
    assert len(conversations) >= 2

    # Check conversation fields
    conv = conversations[0]
    assert "id" in conv
    assert "customer_id" in conv
    assert "channel" in conv
    assert "message_count" in conv
    assert conv["message_count"] >= 2  # Customer message + Agent response


def test_get_conversation_by_id(client):
    """Verify GET /conversations/{id} returns message thread history."""
    # First get list to find an existing ID
    list_res = client.get("/conversations")
    conv_id = list_res.json()[0]["id"]

    # Get specific history
    response = client.get(f"/conversations/{conv_id}")
    assert response.status_code == 200
    data = response.json()

    assert data["id"] == conv_id
    assert "messages" in data
    assert len(data["messages"]) >= 2
    assert data["messages"][0]["sender"] == "customer"
    assert data["messages"][1]["sender"] == "agent"


def test_get_nonexistent_conversation_404(client):
    """Verify 404 is returned for invalid conversation IDs."""
    response = client.get("/conversations/999999")
    assert response.status_code == 404
