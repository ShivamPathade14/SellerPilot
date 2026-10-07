"""Reusable Streamlit presentation components for SellerPilot AI Dashboard.

Architectural Design Notes:
1. Pure Presentation Layer: Components receive structured domain models (Product, StockStatus,
   CaptionResult, InventoryAlert, AgentAction) and render clean UI without containing business logic.
2. Safe Observability: Exposes structured agent metadata (event, intent, confidence, escalation)
   without leaking raw internal chain-of-thought tokens.
3. Accessible Visual Indicators: Intuitive color-coded status badges for stock health and alerts.
4. Minimalist SaaS Aesthetic: Linear / Vercel / Stripe-inspired card systems, subtle borders,
   clean typography, and no childish emojis or gaudy decorations.
"""

from typing import Any
import html
import streamlit as st
from core.schemas import AgentAction, CaptionResult, InventoryAlert, Product, StockStatus
from dashboard.styles import GLOBAL_CSS, THEME


def st_html(raw_html: str, sidebar: bool = False) -> None:
    """Render HTML safely without allowing leading whitespace to trigger Markdown code-block parsing."""
    cleaned = "\n".join(line.strip() for line in raw_html.splitlines() if line.strip())
    if sidebar:
        st.sidebar.markdown(cleaned, unsafe_allow_html=True)
    else:
        st.markdown(cleaned, unsafe_allow_html=True)


def render_global_styles() -> None:
    """Inject global design system CSS overrides into the Streamlit app."""
    st.markdown(GLOBAL_CSS, unsafe_allow_html=True)


def render_page_header(title: str, subtitle: str) -> None:
    """Render a consistent top header across all dashboard pages."""
    safe_title = html.escape(title)
    safe_sub = html.escape(subtitle)
    header_html = f"""
    <div class="sp-top-header">
        <div class="sp-top-header-left">
            <h1 class="sp-page-title">{safe_title}</h1>
            <p class="sp-page-subtitle">{safe_sub}</p>
        </div>
        <div class="sp-top-header-right">
            <div class="sp-status-chip">
                <span class="sp-status-dot"></span>
                <span>All systems operational</span>
            </div>
            <div class="sp-account-badge">
                <span class="sp-account-name">Aura Jewels</span>
                <span class="sp-account-role">Seller account</span>
            </div>
        </div>
    </div>
    """
    st_html(header_html)


def render_sidebar_brand() -> None:
    """Render the top brand block in the sidebar."""
    sidebar_html = """
    <div class="sp-sidebar-brand">
        <div class="sp-brand-row">
            <div class="sp-logo-mark">SP</div>
            <div class="sp-brand-text">
                <div class="sp-brand-title">SELLERPILOT</div>
                <div class="sp-brand-tagline">AI Operations Copilot</div>
            </div>
        </div>
    </div>
    <div class="sp-nav-header">WORKSPACE</div>
    """
    st_html(sidebar_html, sidebar=True)


def render_sidebar_system_status(is_mock: bool = True, db_url: str = "sqlite:///./sellerpilot.db") -> None:
    """Render the system status block at the bottom of the sidebar."""
    mode_text = "Mock Mode" if is_mock else "Claude 3.5 Sonnet"
    db_summary = "Connected (SQLite)" if "sqlite" in db_url.lower() else "Connected"

    status_html = f"""
    <div class="sp-sidebar-status">
        <div class="sp-nav-header" style="margin-top: 0; margin-bottom: 6px;">SYSTEM STATUS</div>
        <div class="sp-status-item">
            <span style="display: inline-flex; align-items: center; gap: 6px;">
                <span class="sp-status-dot"></span> All systems operational
            </span>
        </div>
        <div class="sp-status-item">
            <span>Model Provider</span>
            <span style="color: #F5F7FA; font-weight: 500;">{mode_text}</span>
        </div>
        <div class="sp-status-item">
            <span>Database</span>
            <span style="color: #22C55E; font-weight: 500;">{db_summary}</span>
        </div>
    </div>
    """
    st_html(status_html, sidebar=True)


def render_kpi_card(
    title: str,
    value: Any,
    subtitle: str | None = None,
    icon: str = "",
) -> None:
    """Render a clean SaaS metric KPI card."""
    safe_title = html.escape(str(title).upper())
    safe_val = html.escape(str(value))
    sub_text = html.escape(subtitle) if subtitle else ""

    card_html = f"""
    <div class="sp-kpi-card">
        <div class="sp-kpi-top">
            <span class="sp-kpi-title">{safe_title}</span>
            <span class="sp-kpi-arrow">→</span>
        </div>
        <div>
            <div class="sp-kpi-value">{safe_val}</div>
            <div class="sp-kpi-subtitle">{sub_text}</div>
        </div>
    </div>
    """
    st_html(card_html)


def get_stock_badge(quantity: int, low_stock: bool) -> str:
    """Return standard status label for stock levels (backward-compatible)."""
    if quantity <= 0:
        return "Out of Stock"
    elif low_stock:
        return f"Low Stock ({quantity} left)"
    else:
        return f"In Stock ({quantity})"


def render_status_pill(status_type: str, label: str) -> str:
    """Generate HTML for a modern status pill."""
    type_class = {
        "success": "sp-pill-success",
        "warning": "sp-pill-warning",
        "danger": "sp-pill-danger",
        "accent": "sp-pill-accent",
        "neutral": "sp-pill-neutral",
    }.get(status_type, "sp-pill-neutral")

    return f"""<span class="sp-pill {type_class}"><span class="sp-pill-dot"></span>{html.escape(label)}</span>"""


def render_agent_badge(agent_name: str) -> str:
    """Return HTML for an agent badge."""
    name_clean = agent_name.lower()
    if "commerce" in name_clean:
        pill_class = "sp-pill-accent"
        display = "Commerce"
    elif "inventory" in name_clean:
        pill_class = "sp-pill-warning"
        display = "Inventory"
    elif "content" in name_clean:
        pill_class = "sp-pill-success"
        display = "Content"
    else:
        pill_class = "sp-pill-neutral"
        display = agent_name.capitalize()

    return f"""<span class="sp-pill {pill_class}"><span class="sp-pill-dot"></span>{html.escape(display)}</span>"""


def render_alert_badge(alert_type: str) -> str:
    """Format alert type into readable status label."""
    if alert_type == "posted_but_out_of_stock":
        return "Critical: Out of Stock on Instagram"
    elif alert_type == "oversold":
        return "Oversell Prevented"
    elif alert_type == "low_stock":
        return "Low Stock Warning"
    return alert_type.replace("_", " ").title()


def render_inventory_distribution(
    total: int,
    healthy: int,
    low: int,
    out_of_stock: int,
) -> None:
    """Render a clean ratio distribution bar and numerical breakdown."""
    tot = max(1, total)
    healthy_pct = (healthy / tot) * 100
    low_pct = (low / tot) * 100
    out_pct = (out_of_stock / tot) * 100

    html_bar = f"""
    <div class="sp-card" style="margin-bottom: 0;">
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
            <span style="font-size: 0.88rem; font-weight: 600; color: #F5F7FA;">Inventory Health</span>
            <span style="font-size: 0.78rem; color: #9AA3B2;">{total} total items</span>
        </div>
        <div class="sp-dist-bar">
            <div class="sp-dist-healthy" style="width: {healthy_pct:.1f}%;" title="Healthy: {healthy}"></div>
            <div class="sp-dist-low" style="width: {low_pct:.1f}%;" title="Low Stock: {low}"></div>
            <div class="sp-dist-out" style="width: {out_pct:.1f}%;" title="Out of Stock: {out_of_stock}"></div>
        </div>
        <div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px; margin-top: 14px;">
            <div style="background: rgba(34, 197, 94, 0.06); border: 1px solid rgba(34, 197, 94, 0.2); border-radius: 8px; padding: 10px;">
                <div style="font-size: 0.72rem; color: #22C55E; font-weight: 600; text-transform: uppercase;">Healthy</div>
                <div style="font-size: 1.25rem; font-weight: 700; color: #F5F7FA; margin-top: 2px;">{healthy}</div>
                <div style="font-size: 0.72rem; color: #9AA3B2;">{healthy_pct:.1f}% catalog</div>
            </div>
            <div style="background: rgba(245, 158, 11, 0.06); border: 1px solid rgba(245, 158, 11, 0.2); border-radius: 8px; padding: 10px;">
                <div style="font-size: 0.72rem; color: #F59E0B; font-weight: 600; text-transform: uppercase;">Low Stock</div>
                <div style="font-size: 1.25rem; font-weight: 700; color: #F5F7FA; margin-top: 2px;">{low}</div>
                <div style="font-size: 0.72rem; color: #9AA3B2;">{low_pct:.1f}% catalog</div>
            </div>
            <div style="background: rgba(239, 68, 68, 0.06); border: 1px solid rgba(239, 68, 68, 0.2); border-radius: 8px; padding: 10px;">
                <div style="font-size: 0.72rem; color: #EF4444; font-weight: 600; text-transform: uppercase;">Out of Stock</div>
                <div style="font-size: 1.25rem; font-weight: 700; color: #F5F7FA; margin-top: 2px;">{out_of_stock}</div>
                <div style="font-size: 0.72rem; color: #9AA3B2;">{out_pct:.1f}% catalog</div>
            </div>
        </div>
    </div>
    """
    st_html(html_bar)


def render_chat_message(sender: str, text: str, action: AgentAction | None = None) -> None:
    """Render a conversation message bubble with safe structured agent audit metadata."""
    safe_text = html.escape(text)

    if sender == "customer":
        bubble_html = f"""
        <div style="display: flex; flex-direction: column; align-items: flex-start; margin-bottom: 12px; max-width: 80%;">
            <div style="font-size: 0.7rem; color: #667085; margin-bottom: 4px; font-weight: 500;">CUSTOMER</div>
            <div style="background-color: #151922; border: 1px solid rgba(255, 255, 255, 0.08); border-radius: 10px 10px 10px 2px; padding: 12px 16px; color: #F5F7FA; font-size: 0.88rem; line-height: 1.45;">
                {safe_text}
            </div>
        </div>
        """
        st_html(bubble_html)
    else:
        # Assistant / SellerPilot message
        meta_html = ""
        if action:
            intent_val = getattr(action.intent, "value", str(action.intent))
            intent_clean = intent_val.replace("_", " ").title()
            conf_pct = f"{action.confidence * 100:.0f}%" if action.confidence is not None else "High"
            stock_verified = "Verified (SQLite)" if action.product_id else "Catalog Verified"

            meta_html = f"""
            <div class="sp-ai-metadata">
                <div class="sp-ai-meta-title">AI ACTION • {html.escape(action.agent.upper())} AGENT</div>
                <div class="sp-ai-meta-grid">
                    <div class="sp-meta-field">
                        <span class="sp-meta-label">Detected Intent</span>
                        <span class="sp-meta-val">{html.escape(intent_clean)}</span>
                    </div>
                    <div class="sp-meta-field">
                        <span class="sp-meta-label">Inventory Status</span>
                        <span class="sp-meta-val" style="color: #22C55E;">{stock_verified}</span>
                    </div>
                    <div class="sp-meta-field">
                        <span class="sp-meta-label">Confidence</span>
                        <span class="sp-meta-val">{conf_pct}</span>
                    </div>
                </div>
            </div>
            """

        bubble_html = f"""
        <div style="display: flex; flex-direction: column; align-items: flex-end; margin-bottom: 16px; width: 100%;">
            <div style="max-width: 85%; width: 100%;">
                <div style="display: flex; justify-content: flex-end; align-items: center; gap: 6px; margin-bottom: 4px;">
                    <span style="width: 6px; height: 6px; border-radius: 50%; background-color: #7C5CFC;"></span>
                    <span style="font-size: 0.7rem; color: #7C5CFC; font-weight: 600;">SELLERPILOT</span>
                </div>
                <div style="background-color: #171B26; border: 1px solid rgba(124, 92, 252, 0.25); border-left: 3px solid #7C5CFC; border-radius: 10px 10px 2px 10px; padding: 14px 16px; color: #F5F7FA; font-size: 0.88rem; line-height: 1.5;">
                    {safe_text}
                </div>
                {meta_html}
            </div>
        </div>
        """
        st_html(bubble_html)


def render_caption_result(result: CaptionResult) -> None:
    """Render generated Instagram caption, curated hashtags, and brand voice notes."""
    safe_caption = html.escape(result.caption)
    tags_html = "".join([f'<span class="sp-ig-tag">{html.escape(t)}</span>' for t in result.hashtags])
    safe_notes = html.escape(result.voice_match_notes)

    card_html = f"""
    <div class="sp-card" style="margin-top: 1rem;">
        <div style="font-size: 0.72rem; font-weight: 600; color: #7C5CFC; text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 8px;">
            GENERATED INSTAGRAM CAPTION
        </div>
        <div style="font-size: 0.9rem; line-height: 1.55; color: #F5F7FA; background: #11141B; padding: 14px; border-radius: 8px; border: 1px solid rgba(255, 255, 255, 0.06); margin-bottom: 14px;">
            {safe_caption}
        </div>

        <div style="font-size: 0.72rem; font-weight: 600; color: #667085; text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 8px;">
            CURATED HASHTAGS
        </div>
        <div style="display: flex; flex-wrap: wrap; gap: 6px; margin-bottom: 14px;">
            {tags_html}
        </div>

        <div style="font-size: 0.72rem; font-weight: 600; color: #22C55E; text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 6px;">
            BRAND VOICE MATCH
        </div>
        <div style="font-size: 0.82rem; color: #9AA3B2; line-height: 1.45;">
            {safe_notes}
        </div>
    </div>
    """
    st_html(card_html)


def render_inventory_alert_card(alert: InventoryAlert) -> None:
    """Render an individual unresolved inventory alert in modern SaaS style."""
    badge = render_alert_badge(alert.type)
    is_danger = "Critical" in badge or alert.type == "posted_but_out_of_stock"
    danger_class = "danger" if is_danger else ""
    pill_type = "danger" if is_danger else "warning"

    safe_prod = html.escape(alert.product_id)
    safe_msg = html.escape(alert.message)

    alert_html = f"""
    <div class="sp-alert-card {danger_class}">
        <div class="sp-alert-info">
            <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 3px;">
                {render_status_pill(pill_type, badge)}
                <span style="font-size: 0.75rem; color: #667085; font-family: monospace;">{safe_prod}</span>
            </div>
            <div class="sp-alert-sub">{safe_msg}</div>
        </div>
        <div>
            <span class="sp-alert-link">Resolve →</span>
        </div>
    </div>
    """
    st_html(alert_html)


def render_agent_activity_row(entry: dict[str, Any]) -> None:
    """Format and render a single activity audit log entry."""
    cols = st.columns([1.5, 2, 2.5, 3, 1.5])
    cols[0].markdown(f"<span style='color: #667085; font-size: 0.8rem; font-family: monospace;'>{html.escape(entry.get('timestamp', ''))}</span>", unsafe_allow_html=True)
    cols[1].markdown(render_agent_badge(entry.get("agent", "")), unsafe_allow_html=True)
    cols[2].markdown(f"<span style='font-weight: 500; font-size: 0.85rem; color: #F5F7FA;'>{html.escape(entry.get('event', ''))}</span>", unsafe_allow_html=True)
    cols[3].markdown(f"<span style='color: #9AA3B2; font-size: 0.82rem;'>{html.escape(str(entry.get('result', '')))}</span>", unsafe_allow_html=True)
    cols[4].markdown(render_status_pill("success", "Completed"), unsafe_allow_html=True)


def render_pipeline_diagram(active_step: int | None = None) -> None:
    """Render a modern linear pipeline diagram for the live multi-agent demo."""
    steps = [
        ("CUSTOMER", "Buyer Inquiry"),
        ("COMMERCE AGENT", "Intent & Inventory"),
        ("INVENTORY SERVICE", "Live SQLite State"),
        ("INVENTORY AGENT", "Threshold Alert"),
        ("CONTENT AGENT", "Brand Voice Caption"),
        ("SELLERPILOT", "Autonomous Output"),
    ]

    nodes_html = []
    for idx, (title, sub) in enumerate(steps, 1):
        is_active = (active_step == idx)
        is_done = (active_step is not None and active_step > idx)

        if is_active:
            border_color = "#7C5CFC"
            bg_color = "rgba(124, 92, 252, 0.15)"
            text_color = "#FFFFFF"
            dot_color = "#7C5CFC"
            badge_icon = str(idx)
        elif is_done:
            border_color = "rgba(34, 197, 94, 0.4)"
            bg_color = "rgba(34, 197, 94, 0.08)"
            text_color = "#F5F7FA"
            dot_color = "#22C55E"
            badge_icon = "✓"
        else:
            border_color = "rgba(255, 255, 255, 0.08)"
            bg_color = "#11141B"
            text_color = "#9AA3B2"
            dot_color = "#667085"
            badge_icon = str(idx)

        node = (
            f'<div style="flex: 1; background: {bg_color}; border: 1px solid {border_color}; border-radius: 8px; padding: 10px 8px; text-align: center; min-width: 110px;">'
            f'<div style="display: inline-flex; width: 18px; height: 18px; border-radius: 50%; background: {dot_color}; color: #0B0D12; font-size: 10px; font-weight: 700; align-items: center; justify-content: center; margin-bottom: 4px;">'
            f'{badge_icon}'
            f'</div>'
            f'<div style="font-size: 0.72rem; font-weight: 700; color: {text_color}; letter-spacing: 0.04em;">{title}</div>'
            f'<div style="font-size: 0.65rem; color: #667085; margin-top: 2px;">{sub}</div>'
            f'</div>'
        )
        nodes_html.append(node)

    arrows_joined = '<div style="color: #667085; font-size: 12px; margin: 0 4px;">→</div>'.join(nodes_html)

    diagram_html = (
        '<div class="sp-card" style="margin-bottom: 1.5rem; padding: 14px 16px;">'
        '<div style="font-size: 0.72rem; font-weight: 600; color: #667085; text-transform: uppercase; letter-spacing: 0.06em; margin-bottom: 10px;">'
        'MULTI-AGENT COORDINATION PIPELINE'
        '</div>'
        f'<div style="display: flex; align-items: center; justify-content: space-between; overflow-x: auto; gap: 4px;">{arrows_joined}</div>'
        '</div>'
    )
    st_html(diagram_html)
