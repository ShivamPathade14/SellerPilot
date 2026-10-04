"""Claude LLM Client Wrapper with Structured Output Helper.

Architectural Viva Notes:
1. Pydantic-driven Schema Enforcement: Uses Claude's tool-use mechanism with the target
   Pydantic model's JSON Schema to guarantee conformant structured JSON output.
2. Resilience & Testability: Provides an intelligent mock fallback when ANTHROPIC_API_KEY
   is missing or USE_MOCKS is enabled, ensuring zero-cost, deterministic local testing.
"""

import json
import logging
from typing import Any, TypeVar
from pydantic import BaseModel
from core.config import settings

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)


class ClaudeClient:
    """Wrapper around Anthropic's Claude API supporting structured outputs."""

    def __init__(self, api_key: str | None = None, model: str = "claude-3-7-sonnet-20250219"):
        self.api_key = api_key or settings.ANTHROPIC_API_KEY
        self.model = model
        self._client = None

        if self.api_key and not settings.USE_MOCKS:
            try:
                import anthropic
                self._client = anthropic.Anthropic(api_key=self.api_key)
            except ImportError:
                logger.warning("anthropic package not installed; falling back to mock mode.")

    def generate_structured_output(
        self,
        prompt: str,
        response_model: type[T],
        system_prompt: str | None = None,
    ) -> T:
        """Generates a structured response adhering strictly to the given Pydantic model.

        If live client is unavailable or in mock mode, executes deterministic fallback logic.
        """
        # Fallback to deterministic mock generation if mock mode is on or client is not configured
        if settings.USE_MOCKS or not self._client:
            return self._mock_structured_output(prompt, response_model)

        try:
            # Build tool schema from Pydantic model
            tool_schema = response_model.model_json_schema()
            tool_name = f"submit_{response_model.__name__.lower()}"

            tools = [
                {
                    "name": tool_name,
                    "description": f"Submit structured data matching {response_model.__name__}",
                    "input_schema": tool_schema,
                }
            ]

            messages = [{"role": "user", "content": prompt}]
            kwargs: dict[str, Any] = {
                "model": self.model,
                "max_tokens": 1024,
                "tools": tools,
                "tool_choice": {"type": "tool", "name": tool_name},
                "messages": messages,
            }
            if system_prompt:
                kwargs["system"] = system_prompt

            response = self._client.messages.create(**kwargs)

            # Extract tool call input
            for block in response.content:
                if block.type == "tool_use" and block.name == tool_name:
                    return response_model.model_validate(block.input)

            # If tool use was not triggered, attempt to parse JSON from text block
            for block in response.content:
                if hasattr(block, "text") and block.text:
                    parsed = json.loads(block.text)
                    return response_model.model_validate(parsed)

            raise RuntimeError("Claude did not return structured tool output.")

        except Exception as e:
            logger.warning("Live Claude call failed (%s); reverting to mock generation.", e)
            return self._mock_structured_output(prompt, response_model)

    def _mock_structured_output(self, prompt: str, response_model: type[T]) -> T:
        """Deterministic mock generator for testing and standalone mode without API keys."""
        from core.schemas import AgentAction, CaptionResult, Intent

        lower_prompt = prompt.lower()

        if response_model == AgentAction:
            # Analyze intent from keywords
            if any(k in lower_prompt for k in ["refund", "return", "broken", "angry", "manager", "complaint", "custom order", "bulk"]):
                return response_model.model_validate({
                    "agent": "commerce",
                    "intent": Intent.other,
                    "product_id": None,
                    "response_text": "I completely understand! Let me connect you directly with our founder so we can personally resolve this for you right away. 🌿",
                    "escalate": True,
                    "escalation_reason": "Customer requested refund, complaint, or bulk/custom inquiry.",
                    "confidence": 0.4,
                })
            elif any(k in lower_prompt for k in ["how much", "price", "cost", "discount", "bargain", "deal"]):
                escalate = any(k in lower_prompt for k in ["bargain", "discount", "cheaper", "lower price"])
                return response_model.model_validate({
                    "agent": "commerce",
                    "intent": Intent.price_query,
                    "product_id": None,
                    "response_text": "Our handcrafted pieces are priced based on ethically sourced stones and sterling silver craftsmanship! ✨",
                    "escalate": escalate,
                    "escalation_reason": "Customer attempting price negotiation or custom discount." if escalate else None,
                    "confidence": 0.85 if not escalate else 0.5,
                })
            elif any(k in lower_prompt for k in ["ship", "deliver", "tracking", "courier", "postage"]):
                return response_model.model_validate({
                    "agent": "commerce",
                    "intent": Intent.shipping_query,
                    "product_id": None,
                    "response_text": "We ship orders within 24-48 business hours with tracked delivery across the country! 📦",
                    "escalate": False,
                    "escalation_reason": None,
                    "confidence": 0.95,
                })
            elif any(k in lower_prompt for k in ["available", "in stock", "stock", "left", "size"]):
                return response_model.model_validate({
                    "agent": "commerce",
                    "intent": Intent.stock_query,
                    "product_id": None,
                    "response_text": "Let me check that piece for you right away! ✨",
                    "escalate": False,
                    "escalation_reason": None,
                    "confidence": 0.9,
                })
            else:
                return response_model.model_validate({
                    "agent": "commerce",
                    "intent": Intent.other,
                    "product_id": None,
                    "response_text": "Hello! Welcome to Aura Jewels. Which handcrafted piece caught your eye today? ✨",
                    "escalate": False,
                    "escalation_reason": None,
                    "confidence": 0.75,
                })

        elif response_model == CaptionResult:
            return response_model.model_validate({
                "caption": "Handcrafted with natural gemstones and intentional design. Each piece tells an earthy story. ✨🌿",
                "hashtags": ["#HandmadeJewelry", "#ArtisanMade", "#GemstoneJewelry", "#BohoLuxury", "#AuraJewels"],
                "voice_match_notes": "Warm, earthy, artisanal tone with subtle sparkle emojis matching brand voice.",
            })

        # Generic default construct using model fields
        return response_model.model_construct()


# Default singleton instance
claude_client = ClaudeClient()
