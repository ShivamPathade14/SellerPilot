# SellerPilot AI 🚀

SellerPilot AI is a multi-agent AI assistant designed for small, Instagram/WhatsApp-first Direct-to-Consumer (D2C) brands. Tailored for a synthetic handmade jewellery brand, SellerPilot coordinates specialized agents to handle conversational commerce, live inventory synchronization, and brand-voice content generation.

---

## 🏛️ System Architecture

SellerPilot AI employs a decoupled, multi-agent architecture coordinated via **LangGraph**:

1. **Conversational Commerce Agent (`/agents/commerce`)**:
   - Classifies customer intent (stock query, price query, shipping, other).
   - Inquires live catalog and stock via injected `InventoryService` protocols.
   - Responds in a warm, helpful seller voice.
   - Enforces human escalation for ambiguous queries, refund/custom requests, bargaining, or low model confidence.
2. **Inventory Sync Agent (`/agents/inventory`)**:
   - Manages live stock levels, reservations, and tracks low-stock/oversold alerts.
3. **Content Generation Agent (`/agents/content`)**:
   - Drafts on-brand Instagram captions and hashtags from product details and photos using brand voice guidelines.
4. **LangGraph Orchestrator (`/orchestrator`)**:
   - Central state graph that routes incoming events (`new_dm`, `new_product_photo`, `low_stock`) with explicit, loggable nodes and human escalation fallback.
5. **FastAPI Gateway (`/api`)**:
   - Provides `/webhook/message` for incoming Instagram and WhatsApp DMs, conversation query endpoints, and mounts inventory/content routes.
6. **Streamlit Dashboard (`/dashboard`)**:
   - Operational dashboard for sellers to monitor live chats, review inventory alerts, adjust stock, and trigger content drafts.

---

## 🔒 The Frozen Contract (`core/schemas.py`)
All communication across agents, services, and storage is validated through Pydantic v2 schemas defined in `core/schemas.py`. This contract is **frozen** to allow Person A and Person B to develop in parallel without breaking changes.

All inter-agent dependencies are injected via `typing.Protocol` interfaces defined in `core/interfaces.py`, ensuring zero concrete coupling across team ownership boundaries.

---

## 🛠️ Quickstart & Setup

### 1. Prerequisites
- Python 3.10+ (tested on Python 3.11)
- Git

### 2. Environment Setup
```bash
# Clone the repository
git clone https://github.com/ShivamPathade14/SellerPilot.git
cd SellerPilot

# Create and activate virtual environment
python -m venv venv
# On Windows:
.\venv\Scripts\activate
# On Linux/macOS:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Copy environment variables
cp .env.example .env
```

### 3. Running the FastAPI Application
```bash
# Run FastAPI with live reload
uvicorn api.main:app --reload --port 8000
```
Interactive API documentation is accessible at `http://localhost:8000/docs`.

### 4. Running the DM Simulator
Simulate customer interactions across Instagram and WhatsApp channels:
```bash
python scripts/simulate_dm.py
```

### 5. Running the Test Suite
```bash
# Run Part A tests
pytest tests/a_* -v

# Run all tests
pytest -v
```

---

## 🎓 Key Architectural Decisions (Viva Defense)

1. **Protocol-Driven Dependency Inversion (`typing.Protocol`)**:
   - `CommerceService` and `Orchestrator` do not import concrete inventory or content implementations. They depend entirely on abstract protocols.
   - Allows Part A and Part B to be developed, mocked, and tested in total isolation.
2. **Deterministic Mock Service Fallback (`USE_MOCKS=true`)**:
   - `core/mocks.py` provides realistic synthetic data (~15 jewelry products) and functional mock services. Development, continuous integration, and test suites run reliably without external API costs or internet connectivity.
3. **Structured Outputs with Claude LLM**:
   - `core/llm.py` enforces schema guarantees using structured output / tool calling with Pydantic response models, preventing hallucinated response schemas.
4. **Stateful Graph Execution via LangGraph**:
   - LangGraph provides cyclic and stateful graph coordination, holding conversation context, catalog metadata, and routing decisions in a unified `SellerPilotState`.
5. **Guarded Route Ingestion**:
   - `api/main.py` conditionally mounts Part B routers (`routes_inventory.py`, `routes_content.py`), ensuring the API remains functional even if Part B routes have not yet been implemented.