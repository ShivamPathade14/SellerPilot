"""Demonstration script for Aura Jewels Brand Voice and Content Agent.

Loads the empirical Aura Jewels brand voice profile, selects sample catalog products,
generates fact-grounded Instagram captions, and showcases viva demonstration metrics.

Usage:
    python scripts/demo_content.py
"""

from pathlib import Path
import sys

# Ensure repository root is on sys.path
root_dir = Path(__file__).resolve().parent.parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

# Configure UTF-8 output on Windows terminals
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

from agents.content.agent import ContentAgent
from agents.content.brand_voice import BrandVoiceAnalyzer
from core.mocks import SAMPLE_PRODUCTS
from core.schemas import CaptionRequest


def run_demo():
    print("=" * 75)
    print("      ✨ AURA JEWELS — BRAND VOICE & CONTENT AGENT DEMO ✨      ")
    print("=" * 75)

    # 1. Analyze and Load Brand Voice
    analyzer = BrandVoiceAnalyzer()
    profile = analyzer.analyze()

    print("\n[1] LEARNED BRAND VOICE PROFILE")
    print("-" * 50)
    print("Tone Descriptors :", ", ".join(profile.tone_descriptors))
    print("Emoji Style      :", profile.emoji_style)
    print("Core Hashtags    :", ", ".join(profile.hashtags[:6]))
    print("Sample Captions  :")
    for idx, s in enumerate(profile.sample_captions, 1):
        print(f"  {idx}. \"{s[:90]}...\"")

    # 2. Initialize Content Agent
    agent = ContentAgent(brand_voice_profile=profile, analyzer=analyzer)

    # 3. Generate captions for different product types
    demo_products = [
        SAMPLE_PRODUCTS[0],  # Moonstone Wire-Wrapped Ring
        SAMPLE_PRODUCTS[1],  # Raw Emerald Pendant Necklace
        SAMPLE_PRODUCTS[2],  # Dainty Freshwater Pearl Choker
    ]

    print("\n[2] GENERATED PRODUCT CAPTIONS")
    print("=" * 75)

    for p in demo_products:
        req = CaptionRequest(product=p, extra_notes="Drop 04 Studio Exclusive")
        result = agent.generate_caption(req)

        print(f"\nProduct          : {p.name} ({p.category})")
        print(f"Material         : {p.material}")
        print(f"Price            : ₹{p.price:,.0f}")
        print("-" * 50)
        print("Generated Caption:\n" + result.caption)
        print("\nHashtags         :", " ".join(result.hashtags))
        print("Voice Match      :", result.voice_match_notes)
        print("-" * 75)

    print("\n🎯 Content Agent demonstration completed successfully!")


if __name__ == "__main__":
    run_demo()
