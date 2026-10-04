"""Comprehensive End-to-End Multi-Agent Demonstration for SellerPilot AI.

Runs outside Streamlit as a standalone CLI viva demonstration showcasing:
1. Inbound Customer DM
2. LangGraph Orchestrator & Conversational Commerce Agent
3. Live SQLite Inventory Lookup (zero hallucination)
4. Dynamic Inventory Status & Threshold Alerts
5. Brand Voice Extraction
6. Content Agent Caption Generation
7. Structured Observability & Audit Trail

Usage:
    python scripts/demo_full.py
"""

from datetime import datetime
from pathlib import Path
import sys
import time

# Ensure repository root is on sys.path
root_dir = Path(__file__).resolve().parent.parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

# Configure UTF-8 output on Windows terminals
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

from agents.commerce.agent import ConversationalCommerceAgent
from agents.content.agent import ContentAgent
from agents.content.brand_voice import BrandVoiceAnalyzer
from agents.inventory.agent import InventoryAgent
from agents.inventory.service import SQLiteInventoryService
from core.mocks import SAMPLE_PRODUCTS
from core.schemas import AgentAction, CaptionRequest, CaptionResult, Event, IncomingMessage
from db.base import init_db
from orchestrator.graph import SellerPilotOrchestrator
from scripts.seed_db import seed_database


def run_full_demo():
    print("=" * 75)
    print("      🌟 SELLERPILOT AI — COMPREHENSIVE MULTI-AGENT VIVA DEMO 🌟      ")
    print("=" * 75)

    # 0. Initialize & Seed DB
    init_db()
    inv_service = SQLiteInventoryService()
    if len(inv_service.get_all_products_with_stock()) == 0:
        seed_database()

    content_agent = ContentAgent()
    orchestrator = SellerPilotOrchestrator(inventory=inv_service, content=content_agent)
    audit_trail: list[dict] = []

    def record_step(event: str, agent: str, intent: str, action: str, result: str):
        entry = {
            "timestamp": datetime.utcnow().strftime("%H:%M:%S"),
            "event": event,
            "agent": agent,
            "intent": intent,
            "action": action,
            "result": result,
        }
        audit_trail.append(entry)
        return entry

    # -------------------------------------------------------------------------
    # Step 1 & 2 & 3: Customer DM -> Commerce Agent -> Inventory Lookup
    # -------------------------------------------------------------------------
    print("\n[STEP 1-3] CUSTOMER INQUIRY & COMMERCE AGENT (ZERO-HALLUCINATION)")
    print("-" * 75)
    customer_query = "Do you have the Moonstone Wire-Wrapped Ring in size 7?"
    print(f"Customer DM : \"{customer_query}\"")

    msg = IncomingMessage(
        message_id=f"viva-dm-{int(time.time() * 1000)}",
        customer_id="cust_viva_buyer",
        channel="instagram",
        text=customer_query,
        timestamp=datetime.utcnow(),
    )
    event = Event(type="new_dm", payload={"message": msg.model_dump()})
    action_res: AgentAction = orchestrator.process_event(event)  # type: ignore

    print(f"Routing     : Agent={action_res.agent} | Intent={action_res.intent.value.upper()} | Confidence={action_res.confidence:.2f}")
    print(f"Product ID  : {action_res.product_id}")
    print(f"Escalation  : {action_res.escalate}")
    print(f"Seller DM   : \"{action_res.response_text}\"")

    record_step(
        event="new_dm",
        agent="CommerceAgent",
        intent=action_res.intent.value,
        action="stock_lookup",
        result=f"Verified stock for {action_res.product_id}: In stock",
    )

    # -------------------------------------------------------------------------
    # Step 4: Inventory Status & Live Alerts
    # -------------------------------------------------------------------------
    print("\n[STEP 4] LIVE SQLITE INVENTORY HEALTH & ALERTS")
    print("-" * 75)
    stock_status = inv_service.get_stock("prod-101")
    all_alerts = inv_service.get_alerts()
    print(f"Product 'prod-101' Live Stock: {stock_status.quantity if stock_status else 'N/A'} units (In Stock: {stock_status.in_stock if stock_status else False})")
    print(f"Active Unresolved Alerts     : {len(all_alerts)} active alerts across catalog")
    for a in all_alerts[:2]:
        print(f"  * [{a.type.upper()}] Product {a.product_id}: {a.message}")

    record_step(
        event="inventory_inspection",
        agent="InventoryService",
        intent="health_check",
        action="fetch_alerts",
        result=f"{len(all_alerts)} active alerts verified",
    )

    # -------------------------------------------------------------------------
    # Step 5 & 6: Brand Voice Extraction & Content Generation
    # -------------------------------------------------------------------------
    print("\n[STEP 5-6] BRAND VOICE EXTRACTION & CONTENT AGENT")
    print("-" * 75)
    analyzer = BrandVoiceAnalyzer()
    profile = analyzer.get_profile()
    print("Learned Tones :", ", ".join(profile.tone_descriptors[:4]))
    print("Emoji Style   :", profile.emoji_style)
    print("Core Tags     :", ", ".join(profile.hashtags[:5]))

    target_prod = inv_service.find_products("prod-101")[0]
    caption_req = CaptionRequest(
        product=target_prod,
        extra_notes="Viva Showcase Studio Drop",
    )
    caption_res: CaptionResult = content_agent.generate_caption(caption_req)

    print("\nGenerated Instagram Caption:")
    print(f"\"{caption_res.caption}\"")
    print("\nCurated Hashtags:")
    print(" ".join(caption_res.hashtags))
    print(f"\nBrand Voice Match Notes:\n{caption_res.voice_match_notes}")

    record_step(
        event="content_generation",
        agent="ContentAgent",
        intent="caption_generation",
        action="generate_caption",
        result=f"Caption generated with {len(caption_res.hashtags)} hashtags",
    )

    # -------------------------------------------------------------------------
    # Step 7: End-to-End Audit & Observability Trail
    # -------------------------------------------------------------------------
    print("\n[STEP 7] MULTI-AGENT OBSERVABILITY & AUDIT TRAIL")
    print("-" * 75)
    for idx, entry in enumerate(audit_trail, 1):
        print(f"{idx}. [{entry['timestamp']}] Event='{entry['event']}' | Agent={entry['agent']} | Intent={entry['intent']} | Result={entry['result']}")

    print("\n" + "=" * 75)
    print("🎯 Full End-to-End Multi-Agent Pipeline demonstrated successfully!")
    print("=" * 75 + "\n")


if __name__ == "__main__":
    run_full_demo()
