"""SellerPilot AI — Streamlit Operations Copilot Dashboard.

Architectural Design Notes:
1. Unified AI SaaS Interface: Premium dark-mode operations platform for D2C sellers.
   - Linear / Vercel / Stripe-inspired visual hierarchy, typography, and card system.
   - High contrast, 8px-24px spacing, subtle borders (8-12% white opacity), violet/indigo accent (#7C5CFC).
2. Pure Presentation Layer: Consumes core services (SQLiteInventoryService, ContentAgent,
   SellerPilotOrchestrator) without altering schemas, business logic, or agent behavior.
3. Safe Observability: Surfaces structured operational metadata (intent, confidence, inventory verification)
   without exposing internal hidden chain-of-thought tokens.
4. Offline & Mock Resilient: Seamlessly executes in offline mock mode or with live Claude API.
"""

from datetime import datetime
import html
from pathlib import Path
import sys
import pandas as pd
import streamlit as st

# Ensure repository root is on sys.path
root_dir = Path(__file__).resolve().parent.parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

from agents.commerce.agent import ConversationalCommerceAgent
from agents.content.agent import ContentAgent
from agents.content.brand_voice import BrandVoiceAnalyzer
from agents.inventory.agent import InventoryAgent
from agents.inventory.service import SQLiteInventoryService
from core.config import settings
from core.mocks import SAMPLE_PRODUCTS
from core.schemas import (
    AgentAction,
    CaptionRequest,
    CaptionResult,
    Event,
    IncomingMessage,
    Intent,
    InventoryAlert,
    Product,
)
from dashboard.components import (
    get_stock_badge,
    render_agent_badge,
    render_alert_badge,
    render_caption_result,
    render_chat_message,
    render_global_styles,
    render_inventory_alert_card,
    render_inventory_distribution,
    render_kpi_card,
    render_page_header,
    render_sidebar_brand,
    render_sidebar_system_status,
    render_status_pill,
    st_html,
)
from dashboard.demo import render_demo_page
from db.base import init_db
from orchestrator.graph import SellerPilotOrchestrator
from scripts.seed_db import seed_database


# -----------------------------------------------------------------------------
# App Configuration & Global Styles
# -----------------------------------------------------------------------------

st.set_page_config(
    page_title="SellerPilot AI — D2C Operations Copilot",
    page_icon="✨",
    layout="wide",
    initial_sidebar_state="expanded",
)

render_global_styles()


# -----------------------------------------------------------------------------
# Service Initializers & Session State
# -----------------------------------------------------------------------------

@st.cache_resource
def init_services():
    """Initialize database and core singleton agent services."""
    init_db()
    inv_service = SQLiteInventoryService()

    # Ensure catalog is seeded
    products = inv_service.get_all_products_with_stock()
    if len(products) == 0:
        seed_database()

    content_agent = ContentAgent()
    orchestrator = SellerPilotOrchestrator(inventory=inv_service, content=content_agent)
    return inv_service, content_agent, orchestrator


inv_service, content_agent, orchestrator = init_services()

# Session State for Activity Log
if "activity_log" not in st.session_state:
    st.session_state.activity_log = [
        {
            "timestamp": "12:41:02",
            "agent": "Commerce",
            "event": "new_dm",
            "action": "lookup_stock",
            "result": "8 units available in SQLite",
            "status": "Completed",
        },
        {
            "timestamp": "12:39:15",
            "agent": "Inventory",
            "event": "low_stock_check",
            "action": "threshold_scan",
            "result": "3 items nearing reorder point",
            "status": "Attention",
        },
        {
            "timestamp": "12:35:48",
            "agent": "Content",
            "event": "caption_gen",
            "action": "brand_voice_match",
            "result": "Restock caption crafted with 8 tags",
            "status": "Completed",
        },
        {
            "timestamp": "12:30:00",
            "agent": "Orchestrator",
            "event": "system_startup",
            "action": "pipeline_init",
            "result": "Multi-agent runtime initialized",
            "status": "Completed",
        },
    ]


def log_activity(entry: dict):
    """Append a structured entry to the session activity log."""
    if "status" not in entry:
        entry["status"] = "Completed"
    st.session_state.activity_log.insert(0, entry)


# Pre-populated realistic seller conversations
if "conversations" not in st.session_state:
    st.session_state.conversations = {
        "Priya": {
            "name": "Priya",
            "channel": "Instagram DM",
            "time_ago": "2 min ago",
            "preview": "Is the moonstone ring available in size 7?",
            "messages": [
                {
                    "sender": "customer",
                    "text": "Is the Moonstone Wire-Wrapped Ring available in size 7?",
                    "action": None,
                },
                {
                    "sender": "assistant",
                    "text": "Yes, it's currently available in size 7. We have 8 units in stock, priced at ₹1,450. Hand-forged in Sterling Silver & Rainbow Moonstone. ✨ Would you like to place an order?",
                    "action": AgentAction(
                        agent="commerce",
                        intent=Intent.stock_query,
                        product_id="prod-101",
                        response_text="Yes, it's currently available in size 7. We have 8 units in stock...",
                        escalate=False,
                        confidence=0.95,
                    ),
                },
            ],
        },
        "Rahul": {
            "name": "Rahul",
            "channel": "Instagram DM",
            "time_ago": "8 min ago",
            "preview": "Can I get a discount?",
            "messages": [
                {
                    "sender": "customer",
                    "text": "Can I get a 30% discount if I buy two pieces right now?",
                    "action": None,
                },
                {
                    "sender": "assistant",
                    "text": "Thank you for reaching out! Because our pieces are artisan-crafted in small limited batches, our listed prices are fixed to guarantee fair artisan wages. I've noted your request for our studio team to review.",
                    "action": AgentAction(
                        agent="commerce",
                        intent=Intent.price_query,
                        product_id=None,
                        response_text="Thank you for reaching out! Because our pieces are artisan-crafted...",
                        escalate=True,
                        escalation_reason="Bargain request exceeds standard policy threshold.",
                        confidence=0.92,
                    ),
                },
            ],
        },
        "Ananya": {
            "name": "Ananya",
            "channel": "WhatsApp",
            "time_ago": "15 min ago",
            "preview": "Do you ship to Mumbai?",
            "messages": [
                {
                    "sender": "customer",
                    "text": "Do you ship to Mumbai and how long does delivery take?",
                    "action": None,
                },
                {
                    "sender": "assistant",
                    "text": "Yes, we ship across India including Mumbai! Express delivery takes 2 to 3 business days with insured, eco-friendly gift packaging.",
                    "action": AgentAction(
                        agent="commerce",
                        intent=Intent.shipping_query,
                        product_id=None,
                        response_text="Yes, we ship across India including Mumbai! Express delivery takes 2 to 3 business days...",
                        escalate=False,
                        confidence=0.98,
                    ),
                },
            ],
        },
    }

if "active_conv_name" not in st.session_state:
    st.session_state.active_conv_name = "Priya"

# Backward compatibility for tests inspecting chat_history
active_thread = st.session_state.conversations[st.session_state.active_conv_name]
st.session_state.chat_history = active_thread["messages"]


# -----------------------------------------------------------------------------
# Sidebar Navigation
# -----------------------------------------------------------------------------

render_sidebar_brand()

page = st.sidebar.radio(
    "WORKSPACE",
    [
        "Overview",
        "Conversations",
        "Inventory",
        "Content Studio",
        "Agent Activity",
        "Live Demo",
    ],
    label_visibility="collapsed",
)

render_sidebar_system_status(
    is_mock=settings.USE_MOCKS,
    db_url=settings.DATABASE_URL,
)


def get_time_greeting() -> str:
    hour = datetime.now().hour
    if hour < 12:
        return "Good morning"
    elif hour < 17:
        return "Good afternoon"
    return "Good evening"


# -----------------------------------------------------------------------------
# PAGE 1: Overview
# -----------------------------------------------------------------------------

if page == "Overview":
    render_page_header(
        "Overview",
        "Monitor your store, customers, inventory and AI operations.",
    )

    # Executive Greeting Header
    greeting = get_time_greeting()
    st_html(f"""
    <div style="margin-bottom: 1.5rem;">
        <h2 style="font-size: 1.25rem; font-weight: 600; color: #F5F7FA; margin: 0 0 4px 0;">{greeting}</h2>
        <div style="font-size: 0.88rem; color: #9AA3B2;">Here's what's happening across Aura Jewels.</div>
    </div>
    """)

    # Fetch inventory metrics
    inventory_items = inv_service.get_all_products_with_stock()
    alerts = inv_service.get_alerts()

    total_products = len(inventory_items)
    in_stock_count = sum(1 for item in inventory_items if item["in_stock"])
    low_stock_count = sum(1 for item in inventory_items if item["low_stock"])
    out_of_stock_count = sum(1 for item in inventory_items if not item["in_stock"])
    in_stock_pct = (in_stock_count / max(1, total_products)) * 100

    # 4 Executive KPI Cards
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        render_kpi_card("Total Products", total_products, subtitle="Catalog size")
    with col2:
        render_kpi_card("In Stock", in_stock_count, subtitle=f"{in_stock_pct:.1f}% of catalog")
    with col3:
        render_kpi_card("Low Stock", low_stock_count, subtitle="Needs attention")
    with col4:
        render_kpi_card("Out of Stock", out_of_stock_count, subtitle="Action required")

    st.write("")

    # Two-Column Section: Inventory Health & Attention Required
    col_health, col_alerts = st.columns([1.1, 0.9])

    with col_health:
        healthy_count = in_stock_count - low_stock_count
        render_inventory_distribution(
            total=total_products,
            healthy=healthy_count,
            low=low_stock_count,
            out_of_stock=out_of_stock_count,
        )

    with col_alerts:
        st_html("""
        <div style="font-size: 0.88rem; font-weight: 600; color: #F5F7FA; margin-bottom: 8px;">
            Attention Required
        </div>
        """)

        # Show priority inventory alerts
        if alerts:
            for alert in alerts[:3]:
                render_inventory_alert_card(alert)
        else:
            # Fallback preview cards if alerts are resolved
            st_html("""
            <div class="sp-alert-card">
                <div class="sp-alert-info">
                    <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 3px;">
                        <span class="sp-pill sp-pill-warning"><span class="sp-pill-dot"></span>Low Stock</span>
                        <span style="font-size: 0.75rem; color: #667085; font-family: monospace;">prod-102</span>
                    </div>
                    <div class="sp-alert-title">Rose Gold Hammered Bangle</div>
                    <div class="sp-alert-sub">3 units remaining in studio</div>
                </div>
                <div><span class="sp-alert-link">Review inventory →</span></div>
            </div>
            <div class="sp-alert-card danger">
                <div class="sp-alert-info">
                    <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 3px;">
                        <span class="sp-pill sp-pill-danger"><span class="sp-pill-dot"></span>Out of Stock</span>
                        <span style="font-size: 0.75rem; color: #667085; font-family: monospace;">prod-103</span>
                    </div>
                    <div class="sp-alert-title">Freshwater Pearl Choker</div>
                    <div class="sp-alert-sub">Posted on Instagram • 0 units left</div>
                </div>
                <div><span class="sp-alert-link">Resolve →</span></div>
            </div>
            """)

    st.write("")

    # Recent Agent Operations Timeline/Table
    st_html("""
    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; margin-top: 8px;">
        <span style="font-size: 0.88rem; font-weight: 600; color: #F5F7FA;">AI Operations</span>
        <span style="font-size: 0.76rem; color: #667085;">Live event stream</span>
    </div>
    """)

    # Activity Table (Built as compact single-line HTML without leading spaces)
    recent_events = st.session_state.activity_log[:5]
    table_rows = []
    for ev in recent_events:
        agent_name = ev.get("agent", "")
        agent_pill = render_agent_badge(agent_name)
        status_val = ev.get("status", "Completed")
        status_pill = render_status_pill("success" if status_val == "Completed" else "warning", status_val)
        time_str = ev.get("timestamp", "")
        event_str = ev.get("event", "")
        result_str = ev.get("result", "")

        table_rows.append(
            f'<tr style="border-bottom: 1px solid rgba(255, 255, 255, 0.05);">'
            f'<td style="padding: 10px 12px; font-size: 0.78rem; font-family: monospace; color: #667085;">{html.escape(time_str)}</td>'
            f'<td style="padding: 10px 12px;">{agent_pill}</td>'
            f'<td style="padding: 10px 12px; font-size: 0.84rem; font-weight: 500; color: #F5F7FA;">{html.escape(event_str)}</td>'
            f'<td style="padding: 10px 12px; font-size: 0.82rem; color: #9AA3B2;">{html.escape(result_str)}</td>'
            f'<td style="padding: 10px 12px; text-align: right;">{status_pill}</td>'
            f'</tr>'
        )

    all_rows_html = "".join(table_rows)
    table_html = (
        '<div class="sp-card" style="padding: 0; overflow: hidden;">'
        '<table style="width: 100%; border-collapse: collapse; text-align: left;">'
        '<thead>'
        '<tr style="background: #11141B; border-bottom: 1px solid rgba(255, 255, 255, 0.08);">'
        '<th style="padding: 10px 12px; font-size: 0.7rem; font-weight: 600; color: #667085; text-transform: uppercase;">TIME</th>'
        '<th style="padding: 10px 12px; font-size: 0.7rem; font-weight: 600; color: #667085; text-transform: uppercase;">AGENT</th>'
        '<th style="padding: 10px 12px; font-size: 0.7rem; font-weight: 600; color: #667085; text-transform: uppercase;">EVENT</th>'
        '<th style="padding: 10px 12px; font-size: 0.7rem; font-weight: 600; color: #667085; text-transform: uppercase;">RESULT</th>'
        '<th style="padding: 10px 12px; font-size: 0.7rem; font-weight: 600; color: #667085; text-transform: uppercase; text-align: right;">STATUS</th>'
        '</tr>'
        '</thead>'
        f'<tbody>{all_rows_html}</tbody>'
        '</table>'
        '</div>'
    )
    st_html(table_html)


# -----------------------------------------------------------------------------
# PAGE 2: Conversations
# -----------------------------------------------------------------------------

elif page == "Conversations":
    render_page_header(
        "Customer Conversations",
        "AI support and sales console with live LangGraph routing.",
    )

    col_conv_list, col_chat_panel = st.columns([1.1, 2.0], gap="medium")

    # LEFT COLUMN: Conversation Inquiries List
    with col_conv_list:
        st_html("""
        <div style="font-size: 0.82rem; font-weight: 600; color: #667085; text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 8px;">
            CUSTOMER CONVERSATIONS
        </div>
        """)

        for c_name, c_data in st.session_state.conversations.items():
            is_active = (c_name == st.session_state.active_conv_name)

            btn_label = f"{'● ' if is_active else ''}{c_name} • {c_data['channel']} ({c_data['time_ago']})"
            if st.button(btn_label, key=f"sel_conv_{c_name}", use_container_width=True):
                st.session_state.active_conv_name = c_name
                st.session_state.chat_history = st.session_state.conversations[c_name]["messages"]
                st.rerun()

            safe_preview = html.escape(c_data["preview"])
            st_html(f"""
            <div style="font-size: 0.76rem; color: #9AA3B2; margin-top: -6px; margin-bottom: 12px; padding-left: 8px;">
                "{safe_preview}"
            </div>
            """)

        st.divider()

        st_html("""
        <div style="font-size: 0.75rem; font-weight: 600; color: #667085; text-transform: uppercase; margin-bottom: 8px;">
            QUICK TEST INQUIRIES
        </div>
        """)

        quick_inquiry = None
        if st.button("💍 In-Stock Moonstone Ring", use_container_width=True):
            quick_inquiry = "Is the Moonstone Wire-Wrapped Ring available in size 7?"
        if st.button("💰 Bargain / 30% Off (Escalate)", use_container_width=True):
            quick_inquiry = "Can I get a 30% discount if I buy two right now?"
        if st.button("🚫 Sold Out Pearl Choker", use_container_width=True):
            quick_inquiry = "Is the Freshwater Pearl Choker in stock to order?"

    # RIGHT COLUMN: Conversation Panel
    with col_chat_panel:
        curr_conv = st.session_state.conversations[st.session_state.active_conv_name]

        # Conversation Header
        st_html(f"""
        <div class="sp-card" style="padding: 12px 16px; margin-bottom: 14px; display: flex; justify-content: space-between; align-items: center;">
            <div style="display: flex; align-items: center; gap: 12px;">
                <div style="width: 32px; height: 32px; border-radius: 50%; background: #1F2432; display: flex; align-items: center; justify-content: center; font-weight: 700; color: #F5F7FA; font-size: 0.85rem;">
                    {curr_conv['name'][0]}
                </div>
                <div>
                    <div style="font-size: 0.95rem; font-weight: 600; color: #F5F7FA;">{html.escape(curr_conv['name'])}</div>
                    <div style="font-size: 0.75rem; color: #667085;">{html.escape(curr_conv['channel'])} • Active</div>
                </div>
            </div>
            <div>
                <span class="sp-pill sp-pill-accent"><span class="sp-pill-dot"></span>AI Copilot Active</span>
            </div>
        </div>
        """)

        # Chat Bubble Stream
        chat_box = st.container()
        with chat_box:
            for m in curr_conv["messages"]:
                render_chat_message(
                    sender=m["sender"],
                    text=m["text"],
                    action=m.get("action"),
                )

        # Composer Box
        with st.form("chat_composer_form", clear_on_submit=True):
            col_inp, col_snd = st.columns([5, 1])
            with col_inp:
                typed_msg = st.text_input(
                    "Message",
                    placeholder="Type a customer message...",
                    label_visibility="collapsed",
                )
            with col_snd:
                send_pressed = st.form_submit_button("Send", use_container_width=True)

        msg_to_send = quick_inquiry or (typed_msg if send_pressed and typed_msg.strip() else None)

        if msg_to_send:
            curr_conv["messages"].append({
                "sender": "customer",
                "text": msg_to_send,
                "action": None,
            })
            curr_conv["preview"] = msg_to_send

            msg_obj = IncomingMessage(
                message_id=f"chat-{int(datetime.utcnow().timestamp() * 1000)}",
                customer_id=f"cust_{curr_conv['name'].lower()}",
                channel="instagram" if "instagram" in curr_conv["channel"].lower() else "whatsapp",
                text=msg_to_send,
                timestamp=datetime.utcnow(),
            )
            event = Event(type="new_dm", payload={"message": msg_obj.model_dump()})
            action_res: AgentAction = orchestrator.process_event(event)  # type: ignore

            curr_conv["messages"].append({
                "sender": "assistant",
                "text": action_res.response_text,
                "action": action_res,
            })

            log_activity({
                "timestamp": datetime.utcnow().strftime("%H:%M:%S"),
                "agent": "Commerce",
                "event": "new_dm",
                "action": "handle_dm",
                "result": f"Intent={action_res.intent.value} | Escalate={action_res.escalate}",
                "status": "Completed" if not action_res.escalate else "Attention",
            })

            st.session_state.chat_history = curr_conv["messages"]
            st.rerun()


# -----------------------------------------------------------------------------
# PAGE 3: Inventory
# -----------------------------------------------------------------------------

elif page == "Inventory":
    items = inv_service.get_all_products_with_stock()
    alerts = inv_service.get_alerts()

    low_count = sum(1 for item in items if item["low_stock"])
    oos_count = sum(1 for item in items if not item["in_stock"])
    total_count = len(items)

    render_page_header(
        "Inventory",
        f"Manage catalog availability and stock levels.  •  {total_count} products  •  {low_count} low stock  •  {oos_count} out of stock",
    )

    # Search & Filter Row
    col_search, col_filter = st.columns([3, 2])
    with col_search:
        search_query = st.text_input(
            "Search",
            placeholder="Search products by name or category...",
            label_visibility="collapsed",
        )
    with col_filter:
        stock_filter = st.selectbox(
            "Filter Status",
            ["All", "In Stock", "Low Stock", "Out of Stock"],
            label_visibility="collapsed",
        )

    # Filter logic
    filtered_items = items
    if search_query:
        q = search_query.lower()
        filtered_items = [
            i for i in filtered_items
            if q in i["name"].lower() or q in i["category"].lower() or q in i["product_id"].lower()
        ]

    if stock_filter == "In Stock":
        filtered_items = [i for i in filtered_items if i["in_stock"] and not i["low_stock"]]
    elif stock_filter == "Low Stock":
        filtered_items = [i for i in filtered_items if i["low_stock"]]
    elif stock_filter == "Out of Stock":
        filtered_items = [i for i in filtered_items if not i["in_stock"]]

    # Build clean styled table
    rows_html = []
    for item in filtered_items:
        q = item["quantity"]
        is_low = item["low_stock"]
        if q <= 0:
            pill = render_status_pill("danger", "Out of Stock")
        elif is_low:
            pill = render_status_pill("warning", f"Low Stock ({q})")
        else:
            pill = render_status_pill("success", f"In Stock ({q})")

        insta_badge = '<span class="sp-pill sp-pill-accent">Instagram</span>' if item["posted_on_instagram"] else '<span style="color: #667085; font-size: 0.75rem;">—</span>'

        rows_html.append(
            f'<tr style="border-bottom: 1px solid rgba(255, 255, 255, 0.05);">'
            f'<td style="padding: 12px 14px;">'
            f'<div style="font-weight: 600; color: #F5F7FA; font-size: 0.88rem;">{html.escape(item["name"])}</div>'
            f'<div style="font-size: 0.72rem; color: #667085; font-family: monospace;">{html.escape(item["product_id"])}</div>'
            f'</td>'
            f'<td style="padding: 12px 14px; font-size: 0.82rem; color: #9AA3B2;">{html.escape(item["category"])}</td>'
            f'<td style="padding: 12px 14px; font-size: 0.84rem; font-weight: 500; color: #F5F7FA;">₹{item["price"]:,.0f}</td>'
            f'<td style="padding: 12px 14px; font-size: 0.88rem; font-weight: 700; color: #F5F7FA;">{item["quantity"]}</td>'
            f'<td style="padding: 12px 14px;">{pill}</td>'
            f'<td style="padding: 12px 14px;">{insta_badge}</td>'
            f'</tr>'
        )

    all_inv_rows = "".join(rows_html)
    if not all_inv_rows:
        all_inv_rows = '<tr><td colspan="6" style="padding: 24px; text-align: center; color: #667085;">No matching products found.</td></tr>'

    inv_table_html = (
        '<div class="sp-card" style="padding: 0; overflow: hidden; margin-bottom: 1.5rem;">'
        '<table style="width: 100%; border-collapse: collapse; text-align: left;">'
        '<thead>'
        '<tr style="background: #11141B; border-bottom: 1px solid rgba(255, 255, 255, 0.08);">'
        '<th style="padding: 10px 14px; font-size: 0.7rem; font-weight: 600; color: #667085; text-transform: uppercase;">PRODUCT</th>'
        '<th style="padding: 10px 14px; font-size: 0.7rem; font-weight: 600; color: #667085; text-transform: uppercase;">CATEGORY</th>'
        '<th style="padding: 10px 14px; font-size: 0.7rem; font-weight: 600; color: #667085; text-transform: uppercase;">PRICE</th>'
        '<th style="padding: 10px 14px; font-size: 0.7rem; font-weight: 600; color: #667085; text-transform: uppercase;">STOCK</th>'
        '<th style="padding: 10px 14px; font-size: 0.7rem; font-weight: 600; color: #667085; text-transform: uppercase;">STATUS</th>'
        '<th style="padding: 10px 14px; font-size: 0.7rem; font-weight: 600; color: #667085; text-transform: uppercase;">CHANNEL</th>'
        '</tr>'
        '</thead>'
        f'<tbody>{all_inv_rows}</tbody>'
        '</table>'
        '</div>'
    )
    st_html(inv_table_html)

    # Operations & Stock Actions Drawer
    st_html("""
    <div style="font-size: 0.88rem; font-weight: 600; color: #F5F7FA; margin-bottom: 12px;">
        Inventory Operations
    </div>
    """)

    col_res, col_adj = st.columns(2, gap="medium")
    product_dict = {item["name"]: item["product_id"] for item in items}

    with col_res:
        with st.container():
            st_html("""
            <div class="sp-card" style="margin-bottom: 0;">
                <div style="font-size: 0.75rem; font-weight: 700; color: #7C5CFC; text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 4px;">
                    RESERVE STOCK
                </div>
                <div style="font-size: 0.78rem; color: #9AA3B2; margin-bottom: 12px;">
                    Atomically hold stock for pending orders. Prevents overselling.
                </div>
            </div>
            """)

            res_name = st.selectbox("Select Product to Reserve", list(product_dict.keys()), key="inv_res_prod")
            res_qty = st.number_input("Units to Reserve", min_value=1, max_value=100, value=1, key="inv_res_qty")

            if st.button("Reserve Units", type="primary", use_container_width=True):
                target_id = product_dict[res_name]
                curr_info = inv_service.get_stock(target_id)
                curr_q = curr_info.quantity if curr_info else 0

                ok = inv_service.reserve(target_id, res_qty)
                if ok:
                    new_info = inv_service.get_stock(target_id)
                    new_q = new_info.quantity if new_info else 0
                    st.success(f"Reserved {res_qty} unit(s) of '{res_name}'! Remaining: {new_q}.")
                    log_activity({
                        "timestamp": datetime.utcnow().strftime("%H:%M:%S"),
                        "agent": "Inventory",
                        "event": "stock_reservation",
                        "action": "reserve_stock",
                        "result": f"Reserved {res_qty} of {target_id} ({curr_q} -> {new_q})",
                        "status": "Completed",
                    })
                    st.rerun()
                else:
                    st.error(f"Reservation blocked! Requested {res_qty}, but only {curr_q} in stock.")

    with col_adj:
        with st.container():
            st_html("""
            <div class="sp-card" style="margin-bottom: 0;">
                <div style="font-size: 0.75rem; font-weight: 700; color: #F59E0B; text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 4px;">
                    ADJUST STOCK
                </div>
                <div style="font-size: 0.78rem; color: #9AA3B2; margin-bottom: 12px;">
                    Studio restock or damage write-off. Strictly positive-bounded.
                </div>
            </div>
            """)

            adj_name = st.selectbox("Select Product to Adjust", list(product_dict.keys()), key="inv_adj_prod")
            adj_delta = st.number_input("Delta (+/-)", value=5, step=1, key="inv_adj_delta")
            adj_reason = st.text_input("Operational Reason", value="Studio artisan restock", key="inv_adj_reason")

            if st.button("Apply Adjustment", use_container_width=True):
                target_id = product_dict[adj_name]
                ok, updated_stock, prev_q, err_msg = inv_service.adjust_stock(
                    product_id=target_id,
                    quantity_delta=adj_delta,
                    reason=adj_reason,
                )
                if ok and updated_stock:
                    st.success(f"Stock adjusted by {adj_delta:+d} ({prev_q} -> {updated_stock.quantity}).")
                    log_activity({
                        "timestamp": datetime.utcnow().strftime("%H:%M:%S"),
                        "agent": "Inventory",
                        "event": "stock_adjustment",
                        "action": "adjust_stock",
                        "result": f"Adjusted {target_id} ({prev_q} -> {updated_stock.quantity})",
                        "status": "Completed",
                    })
                    st.rerun()
                else:
                    st.error(f"Adjustment rejected: {err_msg}")


# -----------------------------------------------------------------------------
# PAGE 4: Content Studio
# -----------------------------------------------------------------------------

elif page == "Content Studio":
    render_page_header(
        "Content Studio",
        "Create on-brand social content in seconds.",
    )

    all_prods = inv_service.find_products("")
    prod_map = {p.name: p for p in all_prods}

    col_form, col_preview = st.columns([1.1, 1.2], gap="large")

    with col_form:
        st_html("""
        <div style="font-size: 0.82rem; font-weight: 600; color: #667085; text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 8px;">
            PRODUCT SELECTION
        </div>
        """)

        chosen_name = st.selectbox("Select Catalog Product", list(prod_map.keys()), label_visibility="collapsed")
        chosen_prod: Product = prod_map[chosen_name]

        stock_obj = inv_service.get_stock(chosen_prod.id)
        current_qty = stock_obj.quantity if stock_obj else 0
        stock_status_pill = render_status_pill("success" if current_qty > 3 else "warning" if current_qty > 0 else "danger", f"{current_qty} in stock")

        st_html(f"""
        <div class="sp-card" style="margin-top: 10px; margin-bottom: 16px;">
            <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 8px;">
                <div>
                    <div style="font-size: 1.05rem; font-weight: 700; color: #F5F7FA;">{html.escape(chosen_prod.name)}</div>
                    <div style="font-size: 0.78rem; color: #7C5CFC; font-weight: 500;">{html.escape(chosen_prod.category)} • ₹{chosen_prod.price:,.0f}</div>
                </div>
                {stock_status_pill}
            </div>
            <div style="font-size: 0.82rem; color: #9AA3B2; margin-bottom: 8px;">
                <strong>Material:</strong> {html.escape(chosen_prod.material)}
            </div>
            <div style="font-size: 0.8rem; color: #667085; line-height: 1.4;">
                {html.escape(chosen_prod.description)}
            </div>
        </div>
        """)

        st_html("""
        <div style="font-size: 0.82rem; font-weight: 600; color: #667085; text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 6px;">
            CAMPAIGN HIGHLIGHTS / NOTES
        </div>
        """)

        campaign_notes = st.text_area(
            "Notes",
            value="Limited artisan batch restock — hand-forged in studio",
            label_visibility="collapsed",
            height=85,
        )

        generate_clicked = st.button("Generate Caption", type="primary", use_container_width=True)

        if "studio_result" not in st.session_state or generate_clicked:
            req = CaptionRequest(
                product=chosen_prod,
                extra_notes=campaign_notes if campaign_notes else None,
            )
            st.session_state.studio_result = content_agent.generate_caption(req)
            st.session_state.studio_prod_name = chosen_prod.name
            st.session_state.studio_prod_price = chosen_prod.price

            if generate_clicked:
                log_activity({
                    "timestamp": datetime.utcnow().strftime("%H:%M:%S"),
                    "agent": "Content",
                    "event": "caption_generated",
                    "action": "generate_caption",
                    "result": f"Generated caption for {chosen_prod.id} with {len(st.session_state.studio_result.hashtags)} hashtags",
                    "status": "Completed",
                })

    # RIGHT COLUMN: Realistic Instagram-Style Preview
    with col_preview:
        st_html("""
        <div style="font-size: 0.82rem; font-weight: 600; color: #667085; text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 8px;">
            PREVIEW
        </div>
        """)

        res: CaptionResult = st.session_state.studio_result
        safe_caption = html.escape(res.caption)
        tags_pills = "".join([f'<span class="sp-ig-tag">#{html.escape(t.lstrip("#"))}</span>' for t in res.hashtags])

        st_html(f"""
        <div class="sp-ig-card">
            <!-- Instagram Header -->
            <div class="sp-ig-header">
                <div class="sp-ig-user">
                    <div class="sp-ig-avatar">AJ</div>
                    <div>
                        <div class="sp-ig-username">aurajewels.studio</div>
                        <div style="font-size: 0.68rem; color: #667085;">Jaipur, Rajasthan</div>
                    </div>
                </div>
                <div style="color: #667085; font-size: 14px;">•••</div>
            </div>

            <!-- Visual Content Card -->
            <div class="sp-ig-media">
                <div style="width: 48px; height: 48px; border-radius: 50%; background: rgba(124, 92, 252, 0.2); display: flex; align-items: center; justify-content: center; color: #7C5CFC; font-size: 20px;">
                    ✨
                </div>
                <div class="sp-ig-media-title">{html.escape(chosen_name)}</div>
                <div style="font-size: 0.82rem; color: #9AA3B2; margin-top: 4px;">Aura Jewels Artisanal Collection • ₹{chosen_prod.price:,.0f}</div>
            </div>

            <!-- Post Content -->
            <div class="sp-ig-body">
                <div style="font-size: 0.72rem; font-weight: 700; color: #667085; text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 6px;">
                    GENERATED CAPTION
                </div>
                <div class="sp-ig-caption">
                    {safe_caption}
                </div>

                <div style="font-size: 0.72rem; font-weight: 700; color: #667085; text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 6px;">
                    HASHTAGS
                </div>
                <div class="sp-ig-tags">
                    {tags_pills}
                </div>

                <div style="margin-top: 12px; padding-top: 10px; border-top: 1px solid rgba(255, 255, 255, 0.06);">
                    <div style="font-size: 0.72rem; font-weight: 700; color: #22C55E; text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 4px;">
                        BRAND VOICE
                    </div>
                    <div style="display: flex; gap: 6px; flex-wrap: wrap;">
                        <span class="sp-pill sp-pill-neutral">Conscious luxury</span>
                        <span class="sp-pill sp-pill-neutral">Warm & grounded</span>
                        <span class="sp-pill sp-pill-neutral">Poetic & ethereal</span>
                    </div>
                </div>
            </div>
        </div>
        """)

        st.write("")
        st.code(res.caption + "\n\n" + " ".join([f"#{t.lstrip('#')}" for t in res.hashtags]), language="text")


# -----------------------------------------------------------------------------
# PAGE 5: Agent Activity
# -----------------------------------------------------------------------------

elif page == "Agent Activity":
    render_page_header(
        "Agent Activity",
        "Monitor how SellerPilot handles operations.",
    )

    col_flt, col_clr = st.columns([4, 1])
    with col_flt:
        agent_choice = st.selectbox(
            "Filter by Agent",
            ["All Agents", "Commerce", "Inventory", "Content", "Orchestrator"],
            label_visibility="collapsed",
        )
    with col_clr:
        if st.button("Clear Log", use_container_width=True):
            st.session_state.activity_log = []
            st.rerun()

    logs = st.session_state.activity_log
    if agent_choice != "All Agents":
        logs = [l for l in logs if agent_choice.lower() in l.get("agent", "").lower()]

    if logs:
        rows_activity = []
        for l in logs:
            a_pill = render_agent_badge(l.get("agent", ""))
            s_val = l.get("status", "Completed")
            s_pill = render_status_pill("success" if s_val == "Completed" else "warning", s_val)

            rows_activity.append(
                f'<tr style="border-bottom: 1px solid rgba(255, 255, 255, 0.05);">'
                f'<td style="padding: 10px 14px; font-size: 0.78rem; font-family: monospace; color: #667085;">{html.escape(l.get("timestamp", ""))}</td>'
                f'<td style="padding: 10px 14px;">{a_pill}</td>'
                f'<td style="padding: 10px 14px; font-size: 0.84rem; font-weight: 500; color: #F5F7FA;">{html.escape(l.get("event", ""))}</td>'
                f'<td style="padding: 10px 14px; font-size: 0.82rem; color: #9AA3B2; font-family: monospace;">{html.escape(str(l.get("action", "")))}</td>'
                f'<td style="padding: 10px 14px; font-size: 0.82rem; color: #D1D5DB;">{html.escape(str(l.get("result", "")))}</td>'
                f'<td style="padding: 10px 14px; text-align: right;">{s_pill}</td>'
                f'</tr>'
            )

        table_act_html = (
            '<div class="sp-card" style="padding: 0; overflow: hidden;">'
            '<table style="width: 100%; border-collapse: collapse; text-align: left;">'
            '<thead>'
            '<tr style="background: #11141B; border-bottom: 1px solid rgba(255, 255, 255, 0.08);">'
            '<th style="padding: 10px 14px; font-size: 0.7rem; font-weight: 600; color: #667085; text-transform: uppercase;">TIME</th>'
            '<th style="padding: 10px 14px; font-size: 0.7rem; font-weight: 600; color: #667085; text-transform: uppercase;">AGENT</th>'
            '<th style="padding: 10px 14px; font-size: 0.7rem; font-weight: 600; color: #667085; text-transform: uppercase;">EVENT</th>'
            '<th style="padding: 10px 14px; font-size: 0.7rem; font-weight: 600; color: #667085; text-transform: uppercase;">ACTION</th>'
            '<th style="padding: 10px 14px; font-size: 0.7rem; font-weight: 600; color: #667085; text-transform: uppercase;">RESULT</th>'
            '<th style="padding: 10px 14px; font-size: 0.7rem; font-weight: 600; color: #667085; text-transform: uppercase; text-align: right;">STATUS</th>'
            '</tr>'
            '</thead>'
            f'<tbody>{"".join(rows_activity)}</tbody>'
            '</table>'
            '</div>'
        )
        st_html(table_act_html)
    else:
        st_html("""
        <div class="sp-card" style="text-align: center; color: #667085; padding: 32px;">
            No operational events recorded for the selected filter.
        </div>
        """)


# -----------------------------------------------------------------------------
# PAGE 6: Live Demo
# -----------------------------------------------------------------------------

elif page == "Live Demo":
    render_demo_page(
        inventory_service=inv_service,
        content_agent=content_agent,
        orchestrator=orchestrator,
        log_callback=log_activity,
    )
