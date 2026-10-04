"""Reusable Streamlit presentation components for SellerPilot AI Dashboard.

Architectural Viva Notes:
1. Pure Presentation Layer: Components receive structured domain models (Product, StockStatus,
   CaptionResult, InventoryAlert, AgentAction) and render clean UI without containing business logic.
2. Safe Observability: Exposes structured agent metadata (event, intent, confidence, escalation)
   without leaking raw internal chain-of-thought tokens.
3. Accessible Visual Indicators: Intuitive color-coded status badges for stock health and alerts.
"""

from typing import Any
import streamlit as st
from core.schemas import AgentAction, CaptionResult, InventoryAlert, Product, StockStatus


def render_kpi_card(title: str, value: Any, subtitle: str | None = None, icon: str = "📊"):
    """Render a clean metric KPI card."""
    with st.container():
        st.metric(label=f"{icon} {title}", value=value, delta=subtitle)


def get_stock_badge(quantity: int, low_stock: bool) -> str:
    """Return standard markdown status indicator for stock levels."""
    if quantity <= 0:
        return "🔴 Out of Stock"
    elif low_stock:
        return f"🟡 Low Stock ({quantity} left)"
    else:
        return f"🟢 In Stock ({quantity})"


def render_alert_badge(alert_type: str) -> str:
    """Format alert type into readable status label."""
    if alert_type == "posted_but_out_of_stock":
        return "🚨 Critical: Out of Stock on Instagram"
    elif alert_type == "oversold":
        return "⚠️ Oversell Prevented"
    elif alert_type == "low_stock":
        return "🟡 Low Stock Warning"
    return f"ℹ️ {alert_type}"


def render_chat_message(sender: str, text: str, action: AgentAction | None = None):
    """Render a conversation message bubble with optional structured agent audit metadata."""
    if sender == "customer":
        with st.chat_message("user", avatar="👤"):
            st.markdown(text)
    else:
        with st.chat_message("assistant", avatar="✨"):
            st.markdown(text)
            if action:
                with st.expander("🧠 Agent Reasoning & Activity", expanded=False):
                    c1, c2 = st.columns(2)
                    with c1:
                        st.caption(f"**Agent:** `{action.agent}`")
                        st.caption(f"**Intent:** `{action.intent.value}`")
                        st.caption(f"**Confidence:** `{action.confidence:.2f}`")
                    with c2:
                        st.caption(f"**Product ID:** `{action.product_id or 'None'}`")
                        st.caption(f"**Escalation:** `{'🚨 Yes' if action.escalate else '✅ No'}`")
                        if action.escalate and action.escalation_reason:
                            st.warning(f"**Reason:** {action.escalation_reason}")


def render_caption_result(result: CaptionResult):
    """Render generated Instagram caption, hashtags, and brand voice notes."""
    st.markdown("### ✍️ Generated Caption")
    st.info(result.caption)

    st.markdown("### 🏷️ Curated Hashtags")
    tags_display = " ".join([f"`{t}`" for t in result.hashtags])
    st.markdown(tags_display)

    st.markdown("### 🎨 Brand Voice Match")
    st.success(result.voice_match_notes)


def render_inventory_alert_card(alert: InventoryAlert):
    """Render an individual unresolved inventory alert."""
    badge = render_alert_badge(alert.type)
    if "Critical" in badge or alert.type == "posted_but_out_of_stock":
        st.error(f"**{badge}** (Product: `{alert.product_id}`)\n\n{alert.message}")
    elif "Warning" in badge or alert.type == "low_stock":
        st.warning(f"**{badge}** (Product: `{alert.product_id}`)\n\n{alert.message}")
    else:
        st.info(f"**{badge}** (Product: `{alert.product_id}`)\n\n{alert.message}")


def render_agent_activity_row(entry: dict[str, Any]):
    """Format and render a single activity audit log entry."""
    cols = st.columns([2, 2, 2, 3, 3])
    cols[0].write(f"`{entry.get('timestamp', '')}`")
    cols[1].write(f"**{entry.get('event', '')}**")
    cols[2].write(f"`{entry.get('agent', '')}`")
    cols[3].write(f"Intent: *{entry.get('intent', 'N/A')}*")
    cols[4].write(f"{entry.get('action', '')}: {entry.get('result', '')}")
