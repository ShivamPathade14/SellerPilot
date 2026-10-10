"""Product Reference Resolution for SellerPilot AI.

Architectural Viva Notes:
1. Multi-tier Deterministic Resolution:
   - Direct active context pronoun resolution ("this", "it", "this one", "place this")
   - Exact catalog match
   - Weighted multi-token keyword overlap
   - Fuzzy typo tolerance via difflib ratio
   - Category / material alias resolution
2. Ambiguity & Disambiguation:
   - If multiple candidates have competing confidence without a clear winner,
     flags is_ambiguous=True and provides candidates so the agent can ask for clarification.
3. Zero-Hallucination:
   - Always grounded in InventoryService catalog entities. Never invents products.
"""

from dataclasses import dataclass
import difflib
import logging
import re
from typing import Optional
from core.interfaces import InventoryService
from core.schemas import ConversationContext, Product

logger = logging.getLogger(__name__)

DEICTIC_PRONOUNS = {
    "this", "that", "it", "this one", "that one", "these", "those",
    "place this", "buy this", "order this", "take this", "take it",
    "place it", "order it", "the piece", "the item", "same one",
}

STOP_WORDS = {
    "is", "this", "still", "available", "in", "stock", "do", "you", "have", "the",
    "a", "an", "i", "want", "to", "buy", "order", "can", "how", "much", "what",
    "price", "of", "cost", "for", "please", "hello", "hi", "hey", "size", "sizes",
    "are", "there", "any", "left", "pieces", "units", "get", "two", "one", "three",
    "yes", "no", "place", "take", "give", "me", "send", "about", "sell", "with",
    "show", "tell", "looking", "would", "like", "item", "piece", "come", "comes",
}


@dataclass
class ProductResolution:
    product: Optional[Product]
    candidates: list[Product]
    is_ambiguous: bool
    resolved_from_context: bool
    extracted_query: str


class ProductResolver:
    """Resolves natural language customer queries and pronouns to catalog products."""

    def __init__(self, inventory_service: InventoryService):
        self.inventory = inventory_service

    def resolve(
        self,
        text: str,
        context: Optional[ConversationContext] = None,
    ) -> ProductResolution:
        """Resolve a product reference from customer text and conversation context."""
        text_clean = text.strip()
        text_lower = text_clean.lower()

        # 1. Check for Contextual Pronouns / Anaphora / Variant Resolution
        is_pronoun_reference = self._is_pronoun_reference(text_lower)
        variant_patterns = [
            r"what about (silver|gold|rose gold|white gold)",
            r"(available|comes?)\s+in\s+(silver|gold|rose gold|white gold)",
            r"do you have (it|this)?\s*in\s+(silver|gold|rose gold|white gold)",
            r"do you have (silver|gold|rose gold|white gold)\??$",
            r"^(what about|how about)\s+\w+\??$",
            r"^(in\s+)?(silver|gold|rose gold|white gold)\??$",
        ]
        is_variant_query = any(re.search(pat, text_lower) for pat in variant_patterns)

        if (is_pronoun_reference or is_variant_query) and context and context.active_product_id:
            active_prod = self._get_product_by_id(context.active_product_id)
            if active_prod:
                return ProductResolution(
                    product=active_prod,
                    candidates=[active_prod],
                    is_ambiguous=False,
                    resolved_from_context=True,
                    extracted_query=active_prod.name,
                )

        # 2. Extract keywords from text
        query = self._extract_search_query(text_clean)

        # 3. If query is empty or trivial, check if we have context fallback
        if not query:
            if context and context.active_product_id:
                active_prod = self._get_product_by_id(context.active_product_id)
                if active_prod:
                    return ProductResolution(
                        product=active_prod,
                        candidates=[active_prod],
                        is_ambiguous=False,
                        resolved_from_context=True,
                        extracted_query=active_prod.name,
                    )
            return ProductResolution(
                product=None,
                candidates=[],
                is_ambiguous=False,
                resolved_from_context=False,
                extracted_query="",
            )

        # 4. Search via InventoryService
        raw_matches = self.inventory.find_products(query)

        # 5. Fuzzy match against all catalog products for minor spelling mistakes
        all_products = self.inventory.find_products("")
        fuzzy_matches = self._fuzzy_search(query, all_products)

        # Combine results preserving ranking
        combined: list[Product] = []
        seen_ids = set()
        for p in raw_matches + fuzzy_matches:
            if p.id not in seen_ids:
                seen_ids.add(p.id)
                combined.append(p)

        # Verify that at least one query token of length > 2 appears in the product entity
        query_tokens = [w for w in query.lower().split() if len(w) > 2]
        verified_matches = []
        for p in combined:
            p_text = f"{p.name.lower()} {p.category.lower()} {p.material.lower()} {p.description.lower()}"
            if any(w in p_text for w in query_tokens):
                verified_matches.append(p)

        combined = verified_matches

        if not combined:
            # If no product found but text mentions a category word matching active product (e.g. "bangle", "ring")
            if context and context.active_product_id:
                active_prod = self._get_product_by_id(context.active_product_id)
                if active_prod and (active_prod.category.lower() in text_lower or active_prod.name.lower() in text_lower):
                    return ProductResolution(
                        product=active_prod,
                        candidates=[active_prod],
                        is_ambiguous=False,
                        resolved_from_context=True,
                        extracted_query=query,
                    )

            return ProductResolution(
                product=None,
                candidates=[],
                is_ambiguous=False,
                resolved_from_context=False,
                extracted_query=query,
            )

        # 6. Check for Plausible Multiple Matches (Ambiguity Detection)
        # If user gave a broad category query like "earrings" or "rings" with multiple distinct products
        if len(combined) > 1 and self._is_broad_query(query, text_lower):
            # Check if one of them is already the active product
            if context and context.active_product_id and any(p.id == context.active_product_id for p in combined):
                active_p = next(p for p in combined if p.id == context.active_product_id)
                return ProductResolution(
                    product=active_p,
                    candidates=combined,
                    is_ambiguous=False,
                    resolved_from_context=True,
                    extracted_query=query,
                )

            return ProductResolution(
                product=None,
                candidates=combined[:4],
                is_ambiguous=True,
                resolved_from_context=False,
                extracted_query=query,
            )

        # Top product match
        top_product = combined[0]
        return ProductResolution(
            product=top_product,
            candidates=combined,
            is_ambiguous=False,
            resolved_from_context=False,
            extracted_query=query,
        )

    def _get_product_by_id(self, product_id: str) -> Optional[Product]:
        matches = self.inventory.find_products(product_id)
        for m in matches:
            if m.id == product_id:
                return m
        return None

    def _is_pronoun_reference(self, text_lower: str) -> bool:
        """Detect whether text primarily references a previously discussed item."""
        if any(re.search(rf"\b{re.escape(p)}\b", text_lower) for p in DEICTIC_PRONOUNS):
            return True
        tokens = set(text_lower.split())
        return bool(tokens.intersection({"this", "it", "that", "these"}))

    def _extract_search_query(self, text: str) -> str:
        """Extract candidate search query words from text."""
        cleaned = re.sub(r"[^\w\s]", " ", text)
        words = [w for w in cleaned.split() if w.lower() not in STOP_WORDS and len(w) > 2]
        return " ".join(words)

    def _fuzzy_search(self, query: str, catalog: list[Product]) -> list[Product]:
        """Fuzzy match against product names and categories for typo resilience."""
        query_lower = query.lower()
        scored: list[tuple[float, Product]] = []

        for p in catalog:
            # Check full name similarity
            name_ratio = difflib.SequenceMatcher(None, query_lower, p.name.lower()).ratio()
            # Check token similarity
            token_ratios = [
                difflib.SequenceMatcher(None, query_token, name_token).ratio()
                for query_token in query_lower.split()
                for name_token in p.name.lower().split()
            ]
            max_token_ratio = max(token_ratios) if token_ratios else 0.0

            score = max(name_ratio, max_token_ratio)
            if score >= 0.75:
                scored.append((score, p))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [p for _, p in scored]

    def _is_broad_query(self, query: str, text_lower: str) -> bool:
        """Detect if the query is a broad category term (e.g., 'rings', 'bangles', 'earrings')."""
        broad_terms = {"rings", "ring", "necklaces", "necklace", "earrings", "earring", "bracelets", "bracelet", "bangles", "bangle"}
        q_tokens = set(query.lower().split())
        return bool(q_tokens.intersection(broad_terms)) and len(q_tokens) <= 2
