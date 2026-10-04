"""Content service export and alias for SellerPilot AI."""

from agents.content.agent import ContentAgent

# Lifespan dependency injection alias for api/main.py
ContentServiceImplementation = ContentAgent

__all__ = ["ContentAgent", "ContentServiceImplementation"]
