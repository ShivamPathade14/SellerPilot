# Contributing & Team Workflow Guidelines

## 1. Team Ownership & Responsibilities
The repository is developed concurrently by two team members with strict ownership boundaries:

### Person A (Part A)
- `/core/`: `schemas.py`, `interfaces.py`, `state.py`, `llm.py`, `config.py`, `mocks.py`
- `/db/base.py`: Shared SQLAlchemy declarative base and session management
- `/db/conversation_models.py`: Conversation and message history models
- `/agents/commerce/`: Conversational Commerce Agent
- `/orchestrator/`: LangGraph orchestration engine
- `/api/main.py`: FastAPI app entrypoint (safely mounting all routes)
- `/api/routes_chat.py`: Inbound webhook & conversation query routes
- `/scripts/simulate_dm.py`: DM simulator CLI script
- `/tests/a_*`: Test suite for Part A components

### Person B (Part B)
- `/db/inventory_models.py`: Inventory & alert storage models
- `/agents/inventory/`: Inventory sync & alert agent
- `/agents/content/`: Content caption generator agent
- `/api/routes_inventory.py`: Inventory REST endpoints
- `/api/routes_content.py`: Content caption generation REST endpoints
- `/dashboard/`: Streamlit dashboard
- `/data/`: Synthetic seed datasets (`products.json`, `past_dms.json`, `past_captions.json`)
- `/scripts/seed_db.py`: Database seeding script
- `/tests/b_*`: Test suite for Part B components

---

## 2. Frozen Contract Rule
`core/schemas.py` defines the **Pydantic v2 Contract** between all agents, APIs, and the database.
- The contract is **frozen** upon the initial contract commit.
- Any change to `core/schemas.py` requires a dedicated PR with advance notice and approval from both team members.

---

## 3. Dependency Injection & Isolation Rule
- Components must **never** import concrete implementations across ownership boundaries.
- All inter-agent communication relies strictly on `typing.Protocol` interfaces in `core/interfaces.py`.
- `core/mocks.py` provides `MockInventoryService` and `MockContentService` so each side runs and tests independently before the other side is implemented.
- Use `USE_MOCKS=true` in `.env` to run with mocks.

---

## 4. Git & Branching Rules
1. **Never commit directly to `main`**: All work happens on feature branches.
   - Part A branches: `feat/a-<feature-name>`
   - Part B branches: `feat/b-<feature-name>`
2. **Commit Conventions**: Use small, semantic commits with clear prefixes:
   - `feat:` for new capabilities
   - `fix:` for bug fixes
   - `test:` for test additions or updates
   - `docs:` for documentation
   - `refactor:` for code restructuring
3. **Pull/Rebase Before Pushing**: Always rebase or pull from `origin/main` before pushing to avoid divergent branches.
4. **Pull Requests (PRs)**:
   - Open a PR per logical chunk summarizing what changed.
   - Do **not** merge your own PR without peer review.
5. **Secrets & Credentials**:
   - Never commit `.env` files, API keys, or database credentials.
   - Only `.env.example` is committed to the repository.
