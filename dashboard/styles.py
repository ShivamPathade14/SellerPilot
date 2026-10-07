"""Design system tokens and global CSS styles for SellerPilot AI.

Architecture:
- Centralized palette and typography tokens.
- Custom CSS injection replacing default Streamlit styles with a dark, high-contrast,
  Linear/Vercel/Stripe-inspired AI SaaS aesthetic.
- Zero business logic; presentation-only CSS definitions.
"""

# -----------------------------------------------------------------------------
# Design System Tokens
# -----------------------------------------------------------------------------

THEME = {
    # Surfaces
    "bg_main": "#0B0D12",
    "bg_secondary": "#11141B",
    "bg_card": "#151922",
    "bg_card_hover": "#1A1F2A",
    "bg_card_subtle": "#121620",

    # Text
    "text_primary": "#F5F7FA",
    "text_secondary": "#9AA3B2",
    "text_muted": "#667085",
    "text_dark": "#11141B",

    # Accent
    "accent": "#7C5CFC",
    "accent_hover": "#8B70FF",
    "accent_subtle": "rgba(124, 92, 252, 0.12)",
    "accent_border": "rgba(124, 92, 252, 0.35)",

    # Semantic Status
    "success": "#22C55E",
    "success_subtle": "rgba(34, 197, 94, 0.12)",
    "success_border": "rgba(34, 197, 94, 0.3)",

    "warning": "#F59E0B",
    "warning_subtle": "rgba(245, 158, 11, 0.12)",
    "warning_border": "rgba(245, 158, 11, 0.3)",

    "danger": "#EF4444",
    "danger_subtle": "rgba(239, 68, 68, 0.12)",
    "danger_border": "rgba(239, 68, 68, 0.3)",

    # Borders & Dividers
    "border_subtle": "rgba(255, 255, 255, 0.08)",
    "border_hover": "rgba(255, 255, 255, 0.16)",
    "border_active": "rgba(124, 92, 252, 0.6)",

    # Spacing & Radii
    "radius_sm": "6px",
    "radius_md": "8px",
    "radius_lg": "12px",
    "radius_pill": "9999px",
}

# -----------------------------------------------------------------------------
# Global Streamlit Override CSS
# -----------------------------------------------------------------------------

GLOBAL_CSS = """
<style>
/* Import Inter Font */
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

/* Reset and apply base font */
html, body, [class*="css"], .stApp, .stMarkdown, p, div, span, label, input, button, select, textarea {
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif !important;
}

/* Base background */
.stApp {
    background-color: #0B0D12 !important;
    color: #F5F7FA !important;
}

/* Remove default Streamlit top header decoration */
header[data-testid="stHeader"] {
    background: transparent !important;
    border: none !important;
    height: 2.5rem !important;
}
header[data-testid="stHeader"]::before {
    display: none !important;
}
header[data-testid="stHeader"] .stToolbar {
    right: 1.5rem !important;
    top: 0.5rem !important;
}

/* Main Container spacing */
.main .block-container {
    padding-top: 1rem !important;
    padding-bottom: 3rem !important;
    padding-left: 2rem !important;
    padding-right: 2rem !important;
    max-width: 1440px !important;
}

/* Clean Sidebar */
section[data-testid="stSidebar"] {
    background-color: #11141B !important;
    border-right: 1px solid rgba(255, 255, 255, 0.08) !important;
    box-shadow: none !important;
}
section[data-testid="stSidebar"] .block-container {
    padding-top: 1.25rem !important;
    padding-left: 1.25rem !important;
    padding-right: 1.25rem !important;
    padding-bottom: 1.5rem !important;
}

/* Sidebar Navigation Radio Override */
section[data-testid="stSidebar"] [data-testid="stRadio"] > div {
    gap: 4px !important;
}
section[data-testid="stSidebar"] [data-testid="stRadio"] label {
    background-color: transparent !important;
    border-radius: 8px !important;
    padding: 8px 12px !important;
    margin-bottom: 2px !important;
    cursor: pointer !important;
    transition: all 0.15s ease-in-out !important;
    color: #9AA3B2 !important;
    font-size: 0.88rem !important;
    font-weight: 500 !important;
    border-left: 3px solid transparent !important;
    display: flex !important;
    align-items: center !important;
}
section[data-testid="stSidebar"] [data-testid="stRadio"] label:hover {
    background-color: #151922 !important;
    color: #F5F7FA !important;
}
section[data-testid="stSidebar"] [data-testid="stRadio"] label[data-checked="true"],
section[data-testid="stSidebar"] [data-testid="stRadio"] label:has(input:checked) {
    background-color: rgba(124, 92, 252, 0.12) !important;
    border-left: 3px solid #7C5CFC !important;
    color: #F5F7FA !important;
    font-weight: 600 !important;
}
section[data-testid="stSidebar"] [data-testid="stRadio"] input[type="radio"] {
    display: none !important;
}
section[data-testid="stSidebar"] [data-testid="stRadio"] div[data-testid="stMarkdownContainer"] {
    margin-left: 0 !important;
}

/* Dividers */
hr {
    border: none !important;
    border-top: 1px solid rgba(255, 255, 255, 0.08) !important;
    margin: 1.25rem 0 !important;
}

/* Standard Streamlit Metrics */
[data-testid="stMetric"] {
    background-color: #151922 !important;
    border: 1px solid rgba(255, 255, 255, 0.08) !important;
    border-radius: 10px !important;
    padding: 16px !important;
    box-shadow: none !important;
}
[data-testid="stMetricLabel"] {
    color: #667085 !important;
    font-size: 0.75rem !important;
    font-weight: 600 !important;
    text-transform: uppercase !important;
    letter-spacing: 0.05em !important;
}
[data-testid="stMetricValue"] {
    color: #F5F7FA !important;
    font-size: 1.75rem !important;
    font-weight: 700 !important;
    line-height: 1.2 !important;
}
[data-testid="stMetricDelta"] {
    font-size: 0.8rem !important;
    color: #9AA3B2 !important;
}

/* Buttons */
.stButton button {
    background-color: #151922 !important;
    color: #F5F7FA !important;
    border: 1px solid rgba(255, 255, 255, 0.12) !important;
    border-radius: 8px !important;
    font-size: 0.88rem !important;
    font-weight: 500 !important;
    padding: 6px 14px !important;
    transition: all 0.15s ease-in-out !important;
    box-shadow: none !important;
}
.stButton button:hover {
    background-color: #1A1F2A !important;
    border-color: rgba(255, 255, 255, 0.22) !important;
    color: #FFFFFF !important;
}
.stButton button:active {
    transform: translateY(1px) !important;
}

/* Primary Button */
.stButton button[kind="primary"],
.stButton button[data-testid="baseButton-primary"] {
    background-color: #7C5CFC !important;
    color: #FFFFFF !important;
    border: 1px solid #7C5CFC !important;
    font-weight: 600 !important;
    box-shadow: 0 1px 3px rgba(0, 0, 0, 0.2) !important;
}
.stButton button[kind="primary"]:hover,
.stButton button[data-testid="baseButton-primary"]:hover {
    background-color: #8B70FF !important;
    border-color: #8B70FF !important;
    box-shadow: 0 0 16px rgba(124, 92, 252, 0.35) !important;
}

/* Form Inputs, Selectboxes, Textareas */
.stTextInput input,
.stNumberInput input,
.stTextArea textarea {
    background-color: #151922 !important;
    border: 1px solid rgba(255, 255, 255, 0.1) !important;
    border-radius: 8px !important;
    color: #F5F7FA !important;
    font-size: 0.88rem !important;
    padding: 8px 12px !important;
}
.stTextInput input:focus,
.stNumberInput input:focus,
.stTextArea textarea:focus {
    border-color: #7C5CFC !important;
    box-shadow: 0 0 0 1px #7C5CFC !important;
    outline: none !important;
}

/* Selectbox Dropdowns */
[data-baseweb="select"] {
    border-radius: 8px !important;
}
[data-baseweb="select"] > div {
    background-color: #151922 !important;
    border: 1px solid rgba(255, 255, 255, 0.1) !important;
    border-radius: 8px !important;
    color: #F5F7FA !important;
}
[data-baseweb="popover"], [data-baseweb="menu"] {
    background-color: #151922 !important;
    border: 1px solid rgba(255, 255, 255, 0.12) !important;
    border-radius: 8px !important;
}
[data-baseweb="menu"] li {
    color: #F5F7FA !important;
    font-size: 0.88rem !important;
}
[data-baseweb="menu"] li:hover {
    background-color: #1A1F2A !important;
    color: #8B70FF !important;
}

/* Chat Input */
[data-testid="stChatInput"] {
    background-color: transparent !important;
}
[data-testid="stChatInput"] textarea {
    background-color: #151922 !important;
    border: 1px solid rgba(255, 255, 255, 0.12) !important;
    border-radius: 10px !important;
    color: #F5F7FA !important;
    font-size: 0.9rem !important;
}
[data-testid="stChatInput"] textarea:focus {
    border-color: #7C5CFC !important;
    box-shadow: 0 0 0 1px #7C5CFC !important;
}

/* Chat Messages */
[data-testid="stChatMessage"] {
    background-color: #151922 !important;
    border: 1px solid rgba(255, 255, 255, 0.08) !important;
    border-radius: 10px !important;
    padding: 14px 16px !important;
    margin-bottom: 10px !important;
}
[data-testid="stChatMessage"]:has([data-testid="chatAvatarIcon-user"]) {
    background-color: #12151D !important;
    border-color: rgba(255, 255, 255, 0.06) !important;
}
[data-testid="stChatMessage"]:has([data-testid="chatAvatarIcon-assistant"]) {
    background-color: #161A24 !important;
    border-left: 3px solid #7C5CFC !important;
}

/* Expanders */
.stExpander {
    background-color: #151922 !important;
    border: 1px solid rgba(255, 255, 255, 0.08) !important;
    border-radius: 8px !important;
    margin-bottom: 8px !important;
}
.stExpander summary {
    font-weight: 500 !important;
    font-size: 0.88rem !important;
    color: #9AA3B2 !important;
}
.stExpander summary:hover {
    color: #F5F7FA !important;
}

/* Dataframe & Tables */
[data-testid="stDataFrame"] {
    border: 1px solid rgba(255, 255, 255, 0.08) !important;
    border-radius: 10px !important;
    overflow: hidden !important;
}

/* Alerts / Callouts */
.stAlert {
    border-radius: 8px !important;
    background-color: #151922 !important;
    border: 1px solid rgba(255, 255, 255, 0.08) !important;
    color: #F5F7FA !important;
}
div[data-testid="stNotification"] {
    background-color: #151922 !important;
    border: 1px solid rgba(255, 255, 255, 0.08) !important;
}

/* Scrollbars */
::-webkit-scrollbar {
    width: 6px;
    height: 6px;
}
::-webkit-scrollbar-track {
    background: #0B0D12;
}
::-webkit-scrollbar-thumb {
    background: rgba(255, 255, 255, 0.12);
    border-radius: 3px;
}
::-webkit-scrollbar-thumb:hover {
    background: rgba(255, 255, 255, 0.22);
}

/* ========================================================================= */
/* Custom Design System Utility Classes (Pure CSS Components)               */
/* ========================================================================= */

.sp-top-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding-bottom: 1.25rem;
    margin-bottom: 1.5rem;
    border-bottom: 1px solid rgba(255, 255, 255, 0.08);
}
.sp-top-header-left {
    display: flex;
    flex-direction: column;
    gap: 4px;
}
.sp-page-title {
    font-size: 1.5rem;
    font-weight: 700;
    color: #F5F7FA;
    letter-spacing: -0.02em;
    margin: 0;
    line-height: 1.2;
}
.sp-page-subtitle {
    font-size: 0.88rem;
    color: #9AA3B2;
    margin: 0;
}
.sp-top-header-right {
    display: flex;
    align-items: center;
    gap: 16px;
}
.sp-status-chip {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 4px 10px;
    background-color: rgba(34, 197, 94, 0.1);
    border: 1px solid rgba(34, 197, 94, 0.25);
    border-radius: 9999px;
    font-size: 0.75rem;
    font-weight: 500;
    color: #22C55E;
}
.sp-status-dot {
    width: 6px;
    height: 6px;
    border-radius: 50%;
    background-color: #22C55E;
    box-shadow: 0 0 6px rgba(34, 197, 94, 0.6);
}
.sp-account-badge {
    text-align: right;
    display: flex;
    flex-direction: column;
}
.sp-account-name {
    font-size: 0.85rem;
    font-weight: 600;
    color: #F5F7FA;
    line-height: 1.2;
}
.sp-account-role {
    font-size: 0.72rem;
    color: #667085;
}

/* Custom Card Container */
.sp-card {
    background-color: #151922;
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 10px;
    padding: 1.25rem;
    transition: border-color 0.15s ease, background-color 0.15s ease;
    margin-bottom: 1rem;
}
.sp-card:hover {
    border-color: rgba(255, 255, 255, 0.14);
}
.sp-card-interactive:hover {
    background-color: #1A1F2A;
    border-color: rgba(124, 92, 252, 0.3);
}

/* KPI Cards */
.sp-kpi-card {
    background-color: #151922;
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 10px;
    padding: 1.15rem;
    display: flex;
    flex-direction: column;
    justify-content: space-between;
    min-height: 110px;
    transition: all 0.15s ease-in-out;
}
.sp-kpi-card:hover {
    border-color: rgba(255, 255, 255, 0.15);
    background-color: #171C26;
}
.sp-kpi-top {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 0.5rem;
}
.sp-kpi-title {
    font-size: 0.72rem;
    font-weight: 600;
    color: #667085;
    text-transform: uppercase;
    letter-spacing: 0.06em;
}
.sp-kpi-arrow {
    color: #667085;
    font-size: 0.85rem;
    transition: color 0.15s;
}
.sp-kpi-card:hover .sp-kpi-arrow {
    color: #7C5CFC;
}
.sp-kpi-value {
    font-size: 1.85rem;
    font-weight: 700;
    color: #F5F7FA;
    letter-spacing: -0.02em;
    line-height: 1;
    margin-bottom: 0.35rem;
}
.sp-kpi-subtitle {
    font-size: 0.78rem;
    color: #9AA3B2;
}

/* Status Pills */
.sp-pill {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 3px 8px;
    border-radius: 9999px;
    font-size: 0.75rem;
    font-weight: 500;
    line-height: 1;
}
.sp-pill-dot {
    width: 6px;
    height: 6px;
    border-radius: 50%;
}
.sp-pill-success {
    background-color: rgba(34, 197, 94, 0.12);
    color: #22C55E;
    border: 1px solid rgba(34, 197, 94, 0.25);
}
.sp-pill-success .sp-pill-dot {
    background-color: #22C55E;
}
.sp-pill-warning {
    background-color: rgba(245, 158, 11, 0.12);
    color: #F59E0B;
    border: 1px solid rgba(245, 158, 11, 0.25);
}
.sp-pill-warning .sp-pill-dot {
    background-color: #F59E0B;
}
.sp-pill-danger {
    background-color: rgba(239, 68, 68, 0.12);
    color: #EF4444;
    border: 1px solid rgba(239, 68, 68, 0.25);
}
.sp-pill-danger .sp-pill-dot {
    background-color: #EF4444;
}
.sp-pill-accent {
    background-color: rgba(124, 92, 252, 0.12);
    color: #7C5CFC;
    border: 1px solid rgba(124, 92, 252, 0.25);
}
.sp-pill-accent .sp-pill-dot {
    background-color: #7C5CFC;
}
.sp-pill-neutral {
    background-color: rgba(255, 255, 255, 0.05);
    color: #9AA3B2;
    border: 1px solid rgba(255, 255, 255, 0.1);
}

/* Clean Distribution Bar */
.sp-dist-bar {
    width: 100%;
    height: 8px;
    background-color: rgba(255, 255, 255, 0.05);
    border-radius: 9999px;
    display: flex;
    overflow: hidden;
    margin: 12px 0 16px 0;
}
.sp-dist-healthy {
    background-color: #22C55E;
    height: 100%;
}
.sp-dist-low {
    background-color: #F59E0B;
    height: 100%;
}
.sp-dist-out {
    background-color: #EF4444;
    height: 100%;
}

/* Sidebar Brand Block */
.sp-sidebar-brand {
    padding-bottom: 1.25rem;
    margin-bottom: 1.25rem;
    border-bottom: 1px solid rgba(255, 255, 255, 0.08);
}
.sp-brand-row {
    display: flex;
    align-items: center;
    gap: 10px;
}
.sp-logo-mark {
    width: 32px;
    height: 32px;
    background: linear-gradient(135deg, #7C5CFC 0%, #5B3AE0 100%);
    border-radius: 8px;
    display: flex;
    align-items: center;
    justify-content: center;
    color: #FFFFFF;
    font-weight: 800;
    font-size: 14px;
    letter-spacing: -0.5px;
    box-shadow: 0 0 12px rgba(124, 92, 252, 0.4);
}
.sp-brand-text {
    display: flex;
    flex-direction: column;
}
.sp-brand-title {
    font-size: 0.95rem;
    font-weight: 700;
    color: #F5F7FA;
    letter-spacing: 0.05em;
    line-height: 1.1;
}
.sp-brand-tagline {
    font-size: 0.72rem;
    color: #667085;
    font-weight: 500;
}
.sp-nav-header {
    font-size: 0.68rem;
    font-weight: 600;
    color: #667085;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    margin-bottom: 8px;
    margin-top: 12px;
}

/* Sidebar Status Block */
.sp-sidebar-status {
    padding-top: 1.25rem;
    margin-top: 1.25rem;
    border-top: 1px solid rgba(255, 255, 255, 0.08);
}
.sp-status-item {
    display: flex;
    align-items: center;
    justify-content: space-between;
    font-size: 0.76rem;
    color: #9AA3B2;
    margin-top: 6px;
}

/* Alert / Attention Required Cards */
.sp-alert-card {
    background-color: #151922;
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-left: 3px solid #F59E0B;
    border-radius: 8px;
    padding: 12px 14px;
    margin-bottom: 10px;
    display: flex;
    justify-content: space-between;
    align-items: center;
}
.sp-alert-card.danger {
    border-left-color: #EF4444;
}
.sp-alert-info {
    display: flex;
    flex-direction: column;
    gap: 2px;
}
.sp-alert-title {
    font-size: 0.86rem;
    font-weight: 600;
    color: #F5F7FA;
}
.sp-alert-sub {
    font-size: 0.76rem;
    color: #9AA3B2;
}
.sp-alert-link {
    font-size: 0.78rem;
    color: #7C5CFC;
    font-weight: 500;
    text-decoration: none;
    cursor: pointer;
}

/* Instagram Post Preview */
.sp-ig-card {
    background-color: #11141B;
    border: 1px solid rgba(255, 255, 255, 0.1);
    border-radius: 12px;
    overflow: hidden;
    max-width: 440px;
    margin: 0 auto;
}
.sp-ig-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 12px 14px;
    border-bottom: 1px solid rgba(255, 255, 255, 0.06);
}
.sp-ig-user {
    display: flex;
    align-items: center;
    gap: 10px;
}
.sp-ig-avatar {
    width: 30px;
    height: 30px;
    border-radius: 50%;
    background: linear-gradient(135deg, #7C5CFC, #E1306C);
    display: flex;
    align-items: center;
    justify-content: center;
    color: #FFFFFF;
    font-size: 11px;
    font-weight: 700;
}
.sp-ig-username {
    font-size: 0.82rem;
    font-weight: 600;
    color: #F5F7FA;
}
.sp-ig-media {
    width: 100%;
    min-height: 220px;
    background: radial-gradient(circle at center, #1E2330 0%, #11141B 100%);
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    padding: 24px;
    text-align: center;
    border-bottom: 1px solid rgba(255, 255, 255, 0.06);
}
.sp-ig-media-title {
    font-size: 1.05rem;
    font-weight: 600;
    color: #F5F7FA;
    margin-top: 8px;
}
.sp-ig-body {
    padding: 14px;
}
.sp-ig-caption {
    font-size: 0.85rem;
    line-height: 1.45;
    color: #D1D5DB;
    margin-bottom: 12px;
}
.sp-ig-tags {
    display: flex;
    flex-wrap: wrap;
    gap: 4px;
    margin-bottom: 12px;
}
.sp-ig-tag {
    font-size: 0.74rem;
    color: #7C5CFC;
    background-color: rgba(124, 92, 252, 0.1);
    padding: 2px 6px;
    border-radius: 4px;
}

/* Chat Console */
.sp-conv-list-item {
    background-color: #151922;
    border: 1px solid rgba(255, 255, 255, 0.06);
    border-radius: 8px;
    padding: 12px;
    margin-bottom: 8px;
    cursor: pointer;
    transition: all 0.15s ease;
}
.sp-conv-list-item:hover {
    background-color: #1A1F2A;
    border-color: rgba(255, 255, 255, 0.12);
}
.sp-conv-list-item.active {
    background-color: rgba(124, 92, 252, 0.1);
    border: 1px solid rgba(124, 92, 252, 0.35);
}
.sp-conv-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 4px;
}
.sp-conv-name {
    font-size: 0.88rem;
    font-weight: 600;
    color: #F5F7FA;
}
.sp-conv-time {
    font-size: 0.72rem;
    color: #667085;
}
.sp-conv-preview {
    font-size: 0.78rem;
    color: #9AA3B2;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
}

/* AI Metadata Card */
.sp-ai-metadata {
    background-color: #11141B;
    border: 1px solid rgba(124, 92, 252, 0.25);
    border-radius: 8px;
    padding: 12px 14px;
    margin-top: 10px;
}
.sp-ai-meta-title {
    font-size: 0.72rem;
    font-weight: 700;
    color: #7C5CFC;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    margin-bottom: 8px;
}
.sp-ai-meta-grid {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 12px;
}
.sp-meta-field {
    display: flex;
    flex-direction: column;
}
.sp-meta-label {
    font-size: 0.68rem;
    color: #667085;
    text-transform: uppercase;
}
.sp-meta-val {
    font-size: 0.82rem;
    font-weight: 600;
    color: #F5F7FA;
}

/* Live Demo Step Box */
.sp-demo-step {
    background-color: #151922;
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 8px;
    padding: 14px;
    margin-bottom: 10px;
    transition: all 0.2s ease;
}
.sp-demo-step.active {
    border-color: #7C5CFC;
    background-color: rgba(124, 92, 252, 0.08);
    box-shadow: 0 0 12px rgba(124, 92, 252, 0.15);
}
.sp-demo-step.completed {
    border-color: rgba(34, 197, 94, 0.4);
    background-color: rgba(34, 197, 94, 0.04);
}
.sp-demo-step-header {
    display: flex;
    align-items: center;
    gap: 10px;
    font-size: 0.88rem;
    font-weight: 600;
    color: #F5F7FA;
}
.sp-demo-step-badge {
    width: 20px;
    height: 20px;
    border-radius: 50%;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 11px;
    font-weight: 700;
}
.sp-demo-step-content {
    margin-top: 8px;
    font-size: 0.82rem;
    color: #9AA3B2;
    padding-left: 30px;
}
</style>
"""
