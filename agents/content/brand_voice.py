"""Deterministic Brand Voice Analyzer for SellerPilot AI.

Architectural Viva Notes:
1. Deterministic Heuristic Profiling: Analyzes past brand captions (data/past_captions.json)
   without LLM latency or cost, extracting tone descriptors, emoji patterns, and hashtag taxonomies.
2. Grounded Persona Modeling: Derives an empirical BrandVoiceProfile that reflects the authentic
   Aura Jewels artisanal and ethereal aesthetic.
3. Caching & Idempotency: Caches the computed profile to ensure zero overhead on repeated requests.
"""

from collections import Counter
import json
import logging
from pathlib import Path
import re
from typing import Any
from core.schemas import BrandVoiceProfile

logger = logging.getLogger(__name__)

# Common project-level paths
DEFAULT_CAPTIONS_FILE = Path(__file__).resolve().parent.parent.parent / "data" / "past_captions.json"

# Semantic tone keyword clusters for deterministic matching
TONE_CLUSTERS: dict[str, list[str]] = {
    "handcrafted & artisanal": [
        "handcrafted", "artisan", "hand-forged", "hand-hammered", "hand-strung",
        "studio", "batch", "batches", "crafted", "small batch",
    ],
    "poetic & ethereal": [
        "ethereal", "glow", "luminous", "poetry", "whispers", "mesmerize",
        "celestial", "aurora", "galaxies", "magic", "radiant",
    ],
    "conscious luxury": [
        "luxury", "heirloom", "elegance", "timeless", "signature",
        "conscious", "ethical", "sterling", "gold", "vermeil",
    ],
    "earthy & mindful": [
        "mindful", "ancient", "untamed", "earthy", "organic", "forest",
        "nature", "earthborn", "gemstone", "verdant", "grounded",
    ],
    "warm & grounded": [
        "warm", "warmth", "skin", "quiet", "soul", "heart", "everyday",
        "foundation", "inner courage", "comfort",
    ],
}


class BrandVoiceAnalyzer:
    """Extracts a structured BrandVoiceProfile from past brand captions using deterministic heuristics."""

    def __init__(self, captions_path: Path | str | None = None, captions_data: list[dict[str, Any]] | None = None):
        self.captions_path = Path(captions_path) if captions_path else DEFAULT_CAPTIONS_FILE
        self._captions_data: list[dict[str, Any]] | None = captions_data
        self._cached_profile: BrandVoiceProfile | None = None

    def load_captions(self) -> list[dict[str, Any]]:
        """Load raw caption dictionaries from file or provided data."""
        if self._captions_data is not None:
            return self._captions_data

        if not self.captions_path.exists():
            logger.warning("Captions file not found at %s; returning empty dataset.", self.captions_path)
            return []

        try:
            with open(self.captions_path, "r", encoding="utf-8") as f:
                self._captions_data = json.load(f)
                return self._captions_data or []
        except Exception as e:
            logger.error("Failed to load past captions from %s: %s", self.captions_path, e)
            return []

    def extract_tone_descriptors(self, captions: list[dict[str, Any]]) -> list[str]:
        """Detect dominant tone descriptors based on semantic cluster frequency."""
        combined_text = " ".join(c.get("caption", "").lower() for c in captions)
        cluster_scores: dict[str, int] = {}

        for tone, keywords in TONE_CLUSTERS.items():
            score = sum(combined_text.count(kw) for kw in keywords)
            if score > 0:
                cluster_scores[tone] = score

        # Sort clusters by score descending
        sorted_tones = sorted(cluster_scores.items(), key=lambda x: x[1], reverse=True)
        return [tone for tone, _ in sorted_tones] or ["handcrafted & artisanal", "poetic & ethereal", "conscious luxury"]

    def extract_emoji_style(self, captions: list[dict[str, Any]]) -> str:
        """Classify emoji usage frequency and identify characteristic brand emojis."""
        # Regex matching emoji ranges
        emoji_pattern = re.compile(
            r"[\U0001F300-\U0001F9FF]|[\U0001FA00-\U0001FAFF]|[\u2600-\u26FF]|[\u2700-\u27BF]"
        )

        all_emojis: list[str] = []
        counts_per_caption: list[int] = []

        for c in captions:
            text = c.get("caption", "")
            found = emoji_pattern.findall(text)
            all_emojis.extend(found)
            counts_per_caption.append(len(found))

        avg_emojis = (sum(counts_per_caption) / len(counts_per_caption)) if counts_per_caption else 0.0
        most_common = [emoji for emoji, _ in Counter(all_emojis).most_common(5)]
        common_emojis_str = ", ".join(most_common) if most_common else "✨, 🌿, 🌙, 🤍, 💫"

        if avg_emojis < 1.0:
            frequency_desc = "Minimal"
        elif avg_emojis <= 3.0:
            frequency_desc = "Occasional and tasteful"
        else:
            frequency_desc = "Frequent"

        return f"{frequency_desc} (average {avg_emojis:.1f} per caption; preferred: {common_emojis_str})"

    def extract_hashtags(self, captions: list[dict[str, Any]]) -> list[str]:
        """Aggregate, rank, and return signature recurring hashtags."""
        tag_counter: Counter[str] = Counter()

        for c in captions:
            tags = c.get("hashtags", [])
            for tag in tags:
                clean_tag = tag.strip()
                if clean_tag:
                    if not clean_tag.startswith("#"):
                        clean_tag = f"#{clean_tag}"
                    tag_counter[clean_tag] += 1

        # Return top recurring hashtags ordered by occurrence count
        top_tags = [tag for tag, _ in tag_counter.most_common(12)]
        return top_tags or ["#AuraJewels", "#HandmadeJewelry", "#BohoLuxury", "#ArtisanJewelry"]

    def extract_sample_captions(self, captions: list[dict[str, Any]], limit: int = 3) -> list[str]:
        """Select diverse, high-quality sample captions to represent the brand voice."""
        samples: list[str] = []
        seen_products = set()

        for c in captions:
            prod_id = c.get("product_id")
            caption_text = c.get("caption", "").strip()
            if caption_text and prod_id not in seen_products:
                samples.append(caption_text)
                seen_products.add(prod_id)
                if len(samples) >= limit:
                    break

        return samples

    def analyze(self, force_refresh: bool = False) -> BrandVoiceProfile:
        """Execute deterministic brand voice analysis and return a validated BrandVoiceProfile."""
        if self._cached_profile and not force_refresh:
            return self._cached_profile

        captions = self.load_captions()

        tones = self.extract_tone_descriptors(captions)
        emoji_style = self.extract_emoji_style(captions)
        hashtags = self.extract_hashtags(captions)
        samples = self.extract_sample_captions(captions, limit=3)

        profile = BrandVoiceProfile(
            tone_descriptors=tones,
            emoji_style=emoji_style,
            sample_captions=samples,
            hashtags=hashtags,
        )

        self._cached_profile = profile
        return profile

    def get_profile(self) -> BrandVoiceProfile:
        """Retrieve current brand voice profile, analyzing on first invocation."""
        if not self._cached_profile:
            return self.analyze()
        return self._cached_profile
