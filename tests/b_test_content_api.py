"""Integration tests for FastAPI Content Endpoints and Orchestrator Photo Event.

Validates:
1. POST /content/caption
2. Unknown product returns 404
3. Missing / invalid request returns 422 validation error
4. GET /content/brand-voice
5. API returns valid CaptionResult schema
6. API works without real Claude API key (mock mode)
7. Orchestrator routes 'new_product_photo' event to ContentAgent
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from agents.content.agent import ContentAgent
from agents.inventory.service import SQLiteInventoryService
from api.main import app
from core.schemas import CaptionResult, Event
from db.base import Base
import db.conversation_models  # noqa: F401
import db.inventory_models  # noqa: F401
from orchestrator.graph import SellerPilotOrchestrator
from scripts.seed_db import seed_database


@pytest.fixture(scope="module")
def content_test_db():
    """Create an isolated in-memory test database for content API tests."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)

    seed_database(db_session=TestingSessionLocal())

    yield TestingSessionLocal
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def client(content_test_db):
    """TestClient wired with isolated inventory and content dependencies."""
    from api.routes_content import get_content_service, get_inventory_service
    test_inv_service = SQLiteInventoryService(session_factory=content_test_db)
    test_content_service = ContentAgent()

    app.dependency_overrides[get_inventory_service] = lambda: test_inv_service
    app.dependency_overrides[get_content_service] = lambda: test_content_service

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.pop(get_inventory_service, None)
    app.dependency_overrides.pop(get_content_service, None)


# 1. POST /content/caption
def test_post_caption_success(client):
    payload = {
        "product_id": "prod-101",
        "extra_notes": "Handcrafted for Diwali collection",
    }
    response = client.post("/content/caption", json=payload)
    assert response.status_code == 200
    data = response.json()

    assert "caption" in data
    assert "hashtags" in data
    assert "voice_match_notes" in data
    assert "Moonstone Wire-Wrapped Ring" in data["caption"]
    assert "#AuraJewels" in data["hashtags"]


# 2. Unknown product returns 404
def test_post_caption_unknown_product_404(client):
    payload = {
        "product_id": "prod-missing-999",
    }
    response = client.post("/content/caption", json=payload)
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


# 3. Missing/invalid request returns 422 validation error
def test_post_caption_invalid_payload_422(client):
    # Missing required 'product_id'
    response = client.post("/content/caption", json={})
    assert response.status_code == 422


# 4. GET /content/brand-voice
def test_get_brand_voice_endpoint(client):
    response = client.get("/content/brand-voice")
    assert response.status_code == 200
    data = response.json()

    assert "tone_descriptors" in data
    assert isinstance(data["tone_descriptors"], list)
    assert len(data["tone_descriptors"]) > 0

    assert "emoji_style" in data
    assert isinstance(data["emoji_style"], str)

    assert "hashtags" in data
    assert "#AuraJewels" in data["hashtags"]

    assert "sample_captions" in data
    assert len(data["sample_captions"]) > 0


# 5. API returns valid CaptionResult
def test_api_returns_valid_caption_result(client):
    payload = {"product_id": "prod-102"}
    response = client.post("/content/caption", json=payload)
    assert response.status_code == 200
    res_obj = CaptionResult.model_validate(response.json())
    assert isinstance(res_obj, CaptionResult)
    assert len(res_obj.hashtags) >= 5


# 6. API works without real Claude API key
def test_api_works_without_claude_api_key(client):
    payload = {"product_id": "prod-104", "image_path": "assets/bangle.jpg"}
    response = client.post("/content/caption", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "Rose Gold Hammered Bangle" in data["caption"]


# 7. Orchestrator routes 'new_product_photo' event to ContentAgent
def test_orchestrator_routes_new_product_photo_to_content(content_test_db):
    test_inv = SQLiteInventoryService(session_factory=content_test_db)
    test_content = ContentAgent()
    orchestrator = SellerPilotOrchestrator(inventory=test_inv, content=test_content)

    event = Event(
        type="new_product_photo",
        payload={
            "product_id": "prod-101",
            "image_path": "assets/products/moonstone_ring.jpg",
            "extra_notes": "Studio drop showcase",
        },
    )

    result = orchestrator.process_event(event)
    assert isinstance(result, CaptionResult)
    assert "Moonstone Wire-Wrapped Ring" in result.caption
    assert "#AuraJewels" in result.hashtags
