"""Tests for Part B Content Agent and Brand Voice Engine.

Validates:
1. Brand voice extraction from past captions
2. Tone detection heuristics
3. Emoji style detection
4. Hashtag extraction
5. BrandVoiceProfile schema compatibility
6. Caption generation with mock LLM
7. CaptionResult schema validation
8. Product facts appear in caption
9. Unsupported product facts are not invented
10. No image path still works
11. Optional image path is accepted
12. Deterministic mock mode works without API key
13. ContentService protocol conformance
14. Different products produce different captions
15. Existing brand voice is reflected in generated captions
"""

import pytest
from agents.content.agent import ContentAgent
from agents.content.brand_voice import BrandVoiceAnalyzer
from core.interfaces import ContentService
from core.mocks import SAMPLE_PRODUCTS
from core.schemas import BrandVoiceProfile, CaptionRequest, CaptionResult, Product


@pytest.fixture
def analyzer():
    return BrandVoiceAnalyzer()


@pytest.fixture
def agent(analyzer):
    return ContentAgent(analyzer=analyzer)


@pytest.fixture
def sample_product():
    return Product(
        id="prod-101",
        name="Moonstone Wire-Wrapped Ring",
        price=1450.0,
        category="Rings",
        material="Sterling Silver & Rainbow Moonstone",
        description="Natural iridescent moonstone set in hand-twisted sterling silver wire.",
        sizes=["6", "7", "8"],
        colors=["Rainbow Iridescent"],
        image_path="assets/products/moonstone_ring.jpg",
    )


# 1. Brand voice extraction
def test_brand_voice_extraction(analyzer):
    profile = analyzer.analyze()
    assert isinstance(profile, BrandVoiceProfile)
    assert len(profile.tone_descriptors) > 0
    assert len(profile.hashtags) > 0
    assert len(profile.sample_captions) > 0


# 2. Tone detection
def test_tone_detection(analyzer):
    captions = analyzer.load_captions()
    tones = analyzer.extract_tone_descriptors(captions)
    assert isinstance(tones, list)
    assert len(tones) >= 3
    # Check for expected aesthetic tones
    tones_str = " ".join(tones).lower()
    assert "handcrafted" in tones_str or "artisanal" in tones_str
    assert "luxury" in tones_str or "poetic" in tones_str or "mindful" in tones_str


# 3. Emoji style detection
def test_emoji_style_detection(analyzer):
    captions = analyzer.load_captions()
    emoji_style = analyzer.extract_emoji_style(captions)
    assert isinstance(emoji_style, str)
    assert "✨" in emoji_style or "🌿" in emoji_style or "Occasional" in emoji_style


# 4. Hashtag extraction
def test_hashtag_extraction(analyzer):
    captions = analyzer.load_captions()
    hashtags = analyzer.extract_hashtags(captions)
    assert isinstance(hashtags, list)
    assert len(hashtags) >= 5
    assert "#AuraJewels" in hashtags


# 5. BrandVoiceProfile schema compatibility
def test_brand_voice_profile_schema(analyzer):
    profile = analyzer.get_profile()
    dumped = profile.model_dump()
    reconstructed = BrandVoiceProfile.model_validate(dumped)
    assert reconstructed.tone_descriptors == profile.tone_descriptors
    assert reconstructed.emoji_style == profile.emoji_style
    assert reconstructed.hashtags == profile.hashtags


# 6. Caption generation with mock LLM
def test_caption_generation_mock_mode(agent, sample_product):
    req = CaptionRequest(product=sample_product)
    result = agent.generate_caption(req)
    assert isinstance(result, CaptionResult)
    assert len(result.caption) > 20
    assert len(result.hashtags) >= 5


# 7. CaptionResult schema validation
def test_caption_result_schema_validation(agent, sample_product):
    req = CaptionRequest(product=sample_product)
    result = agent.generate_caption(req)
    dumped = result.model_dump()
    validated = CaptionResult.model_validate(dumped)
    assert validated.caption == result.caption
    assert validated.voice_match_notes == result.voice_match_notes


# 8. Product facts appear in caption
def test_product_facts_appear_in_caption(agent, sample_product):
    req = CaptionRequest(product=sample_product)
    result = agent.generate_caption(req)
    assert sample_product.name in result.caption
    assert "Sterling Silver" in result.caption or "Moonstone" in result.caption


# 9. Unsupported product facts are not invented
def test_unsupported_facts_not_invented(agent, sample_product):
    req = CaptionRequest(product=sample_product)
    result = agent.generate_caption(req)
    # Shouldn't invent fake materials or random discount promises
    caption_lower = result.caption.lower()
    assert "diamond" not in caption_lower
    assert "50% off" not in caption_lower
    assert "free international shipping" not in caption_lower


# 10. No image path still works
def test_no_image_path_still_works(agent, sample_product):
    req = CaptionRequest(product=sample_product, image_path=None)
    result = agent.generate_caption(req)
    assert isinstance(result, CaptionResult)
    assert sample_product.name in result.caption


# 11. Optional image path is accepted
def test_optional_image_path_accepted(agent, sample_product):
    req = CaptionRequest(
        product=sample_product,
        image_path="assets/products/moonstone_ring.jpg",
        extra_notes="Special full moon drop",
    )
    result = agent.generate_caption(req)
    assert isinstance(result, CaptionResult)
    assert "Special full moon drop" in result.caption or sample_product.name in result.caption


# 12. Deterministic mock mode works without API key
def test_deterministic_mode_without_api_key(sample_product):
    from core.llm import ClaudeClient
    offline_client = ClaudeClient(api_key="")
    offline_agent = ContentAgent(llm_client=offline_client)
    req = CaptionRequest(product=sample_product)
    result = offline_agent.generate_caption(req)
    assert isinstance(result, CaptionResult)
    assert sample_product.name in result.caption


# 13. ContentService protocol conformance
def test_content_service_protocol_conformance(agent):
    assert isinstance(agent, ContentService)


# 14. Different products produce different captions
def test_different_products_produce_different_captions(agent):
    p1 = SAMPLE_PRODUCTS[0]  # Ring
    p2 = SAMPLE_PRODUCTS[1]  # Necklace
    p3 = SAMPLE_PRODUCTS[3]  # Bangle

    r1 = agent.generate_caption(CaptionRequest(product=p1))
    r2 = agent.generate_caption(CaptionRequest(product=p2))
    r3 = agent.generate_caption(CaptionRequest(product=p3))

    assert r1.caption != r2.caption
    assert r2.caption != r3.caption
    assert p1.name in r1.caption
    assert p2.name in r2.caption
    assert p3.name in r3.caption


# 15. Existing brand voice is reflected in generated captions
def test_brand_voice_reflected_in_caption(agent, sample_product):
    req = CaptionRequest(product=sample_product)
    result = agent.generate_caption(req)
    # Check for signature emojis and hashtags
    assert any(emoji in result.caption for emoji in ["✨", "🌿", "🌙", "🤍", "💫"])
    assert "#AuraJewels" in result.hashtags
    assert "brand voice" in result.voice_match_notes.lower()
