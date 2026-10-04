"""Mock Services with Realistic Handmade Jewellery Data.

Architectural Viva Notes:
1. Protocol Conformance: MockInventoryService and MockContentService implement
   InventoryService and ContentService protocols without coupling to Part B database models.
2. Parallel Development: Allows Part A agents, APIs, and workflows to be executed and tested
   completely independently before Part B builds SQLite models and routes.
"""

from datetime import datetime
from core.interfaces import ContentService, InventoryService
from core.schemas import (
    BrandVoiceProfile,
    CaptionRequest,
    CaptionResult,
    InventoryAlert,
    Product,
    StockStatus,
)

# Realistic catalog of 15 handmade jewellery pieces
SAMPLE_PRODUCTS: list[Product] = [
    Product(
        id="prod-101",
        name="Moonstone Wire-Wrapped Ring",
        price=1450.0,
        category="Rings",
        material="Sterling Silver & Rainbow Moonstone",
        description="Delicate sterling silver wire lovingly wrapped around an ethereal rainbow moonstone cabochon.",
        sizes=["6", "7", "8"],
        colors=["Silver Blue"],
        image_path="/images/moonstone_ring.jpg",
    ),
    Product(
        id="prod-102",
        name="Raw Emerald Pendant Necklace",
        price=2200.0,
        category="Necklaces",
        material="18k Gold Plated Brass & Raw Colombian Emerald",
        description="Organic uncut raw emerald electroplated in warm 18k gold on an adjustable chain.",
        sizes=["18 inch", "20 inch"],
        colors=["Gold Emerald"],
        image_path="/images/raw_emerald_necklace.jpg",
    ),
    Product(
        id="prod-103",
        name="Dainty Freshwater Pearl Choker",
        price=1850.0,
        category="Necklaces",
        material="Freshwater Pearls & 14k Gold Filled Clasp",
        description="Luminous natural baroque pearls hand-strung with high-tensile silk thread.",
        sizes=["14-16 inch adjustable"],
        colors=["Iridescent White"],
        image_path="/images/pearl_choker.jpg",
    ),
    Product(
        id="prod-104",
        name="Rose Gold Hammered Bangle",
        price=1600.0,
        category="Bracelets",
        material="Rose Gold Vermeil",
        description="Chic stacking bangle featuring subtle light-catching hand-hammered texture.",
        sizes=["Small", "Medium", "Large"],
        colors=["Rose Gold"],
        image_path="/images/rose_gold_bangle.jpg",
    ),
    Product(
        id="prod-105",
        name="Sunburst Labradorite Drops",
        price=1350.0,
        category="Earrings",
        material="Sterling Silver & Blue Flash Labradorite",
        description="Radiant teardrop labradorite earrings with dazzling peacock-blue flash.",
        sizes=["Standard"],
        colors=["Grey Blue Flash"],
        image_path="/images/labradorite_drops.jpg",
    ),
    Product(
        id="prod-106",
        name="Amethyst Cluster Studs",
        price=950.0,
        category="Earrings",
        material="925 Sterling Silver & Raw Uruguayan Amethyst",
        description="Dainty everyday raw crystal studs offering soothing amethyst energy.",
        sizes=["Standard"],
        colors=["Deep Violet"],
        image_path="/images/amethyst_studs.jpg",
    ),
    Product(
        id="prod-107",
        name="Turquoise Bohemian Cuff",
        price=2400.0,
        category="Bracelets",
        material="Oxidized Silver & Arizona Turquoise",
        description="Bold bohemian statement cuff featuring intricate tribal filigree.",
        sizes=["Adjustable"],
        colors=["Antique Silver & Turquoise"],
        image_path="/images/turquoise_cuff.jpg",
    ),
    Product(
        id="prod-108",
        name="Herringbone Chain Layering Necklace",
        price=1250.0,
        category="Necklaces",
        material="18k Gold PVD Coated Stainless Steel",
        description="Silky smooth waterproof liquid gold herringbone chain for everyday elegance.",
        sizes=["16 inch", "18 inch"],
        colors=["Classic Gold"],
        image_path="/images/herringbone_chain.jpg",
    ),
    Product(
        id="prod-109",
        name="Opal Solitaire Stacking Ring",
        price=1750.0,
        category="Rings",
        material="Solid 925 Silver & Australian Crystal Opal",
        description="Earthy iridescent crystal opal in a bezel setting made to stack seamlessly.",
        sizes=["5", "6", "7", "8"],
        colors=["Fire Opal Multicolor"],
        image_path="/images/opal_ring.jpg",
    ),
    Product(
        id="prod-110",
        name="Garnet Teardrop Dangle Earrings",
        price=1100.0,
        category="Earrings",
        material="Brass with 1 micron Gold & Bohemian Red Garnet",
        description="Deep crimson faceted garnets swaying on delicate ear wires.",
        sizes=["Standard"],
        colors=["Crimson Red"],
        image_path="/images/garnet_earrings.jpg",
    ),
    Product(
        id="prod-111",
        name="Lapis Lazuli Signet Ring",
        price=1950.0,
        category="Rings",
        material="925 Sterling Silver & Afghan Lapis Lazuli",
        description="Solid unisex silver signet ring set with royal blue golden-speckled lapis lazuli.",
        sizes=["7", "8", "9", "10"],
        colors=["Cobalt Gold Flecked"],
        image_path="/images/lapis_signet.jpg",
    ),
    Product(
        id="prod-112",
        name="Citrine Sunshine Charm Bracelet",
        price=1500.0,
        category="Bracelets",
        material="14k Gold Filled Chain & Brazilian Golden Citrine",
        description="Dainty links adorned with faceted golden citrine briolettes.",
        sizes=["6.5-7.5 inch"],
        colors=["Golden Honey"],
        image_path="/images/citrine_bracelet.jpg",
    ),
    Product(
        id="prod-113",
        name="Moss Agate Botanical Ring",
        price=1650.0,
        category="Rings",
        material="Sterling Silver & Forest Moss Agate",
        description="Kite-cut natural moss agate reflecting verdant evergreen landscapes.",
        sizes=["6", "7", "8"],
        colors=["Emerald Moss"],
        image_path="/images/moss_agate_ring.jpg",
    ),
    Product(
        id="prod-114",
        name="Black Onyx Geometric Threader Earrings",
        price=1200.0,
        category="Earrings",
        material="Sterling Silver & Black Onyx",
        description="Modern minimalist threaders with faceted natural black onyx cubes.",
        sizes=["Long Threader"],
        colors=["Jet Black"],
        image_path="/images/onyx_threaders.jpg",
    ),
    Product(
        id="prod-115",
        name="Carnelian Statement Collar Necklace",
        price=2800.0,
        category="Necklaces",
        material="18k Gold Plated Brass & Madagascar Carnelian",
        description="Rich fiery carnelian stones handcrafted into a stunning collarpiece.",
        sizes=["16 inch"],
        colors=["Burnt Amber"],
        image_path="/images/carnelian_collar.jpg",
    ),
]

# Initial inventory levels matching product list
INITIAL_STOCK: dict[str, StockStatus] = {
    "prod-101": StockStatus(product_id="prod-101", quantity=8, in_stock=True, low_stock=False, posted_on_instagram=True),
    "prod-102": StockStatus(product_id="prod-102", quantity=3, in_stock=True, low_stock=True, posted_on_instagram=True),
    "prod-103": StockStatus(product_id="prod-103", quantity=0, in_stock=False, low_stock=True, posted_on_instagram=True),  # Out of stock & posted on IG!
    "prod-104": StockStatus(product_id="prod-104", quantity=12, in_stock=True, low_stock=False, posted_on_instagram=False),
    "prod-105": StockStatus(product_id="prod-105", quantity=5, in_stock=True, low_stock=False, posted_on_instagram=True),
    "prod-106": StockStatus(product_id="prod-106", quantity=15, in_stock=True, low_stock=False, posted_on_instagram=False),
    "prod-107": StockStatus(product_id="prod-107", quantity=2, in_stock=True, low_stock=True, posted_on_instagram=True),
    "prod-108": StockStatus(product_id="prod-108", quantity=20, in_stock=True, low_stock=False, posted_on_instagram=True),
    "prod-109": StockStatus(product_id="prod-109", quantity=4, in_stock=True, low_stock=True, posted_on_instagram=True),
    "prod-110": StockStatus(product_id="prod-110", quantity=9, in_stock=True, low_stock=False, posted_on_instagram=False),
    "prod-111": StockStatus(product_id="prod-111", quantity=6, in_stock=True, low_stock=False, posted_on_instagram=True),
    "prod-112": StockStatus(product_id="prod-112", quantity=0, in_stock=False, low_stock=True, posted_on_instagram=False),
    "prod-113": StockStatus(product_id="prod-113", quantity=7, in_stock=True, low_stock=False, posted_on_instagram=True),
    "prod-114": StockStatus(product_id="prod-114", quantity=11, in_stock=True, low_stock=False, posted_on_instagram=False),
    "prod-115": StockStatus(product_id="prod-115", quantity=1, in_stock=True, low_stock=True, posted_on_instagram=True),
}

DEFAULT_BRAND_VOICE = BrandVoiceProfile(
    tone_descriptors=["warm", "artisan", "earthy", "approachable", "mindful"],
    emoji_style="organic & starry (✨, 🌿, 🌙, 🌸, 💫)",
    sample_captions=[
        "Spun by hand, loved forever. Each gemstone carries its own ancient vibration. ✨🌙",
        "A little golden light for your Monday stack. Hand-hammered with patience and sterling silver. 🌿",
        "Nature's raw geometry. Our raw emerald pendant is back in studio, made in mindful small batches. 💚",
    ],
    hashtags=["#HandmadeJewelry", "#ArtisanJewelry", "#BohoLuxury", "#CrystalEnergy", "#EthicalJewelry", "#AuraJewels"],
)


class MockInventoryService:
    """In-memory Mock Inventory Service conforming strictly to InventoryService protocol."""

    def __init__(self, products: list[Product] | None = None, stock: dict[str, StockStatus] | None = None):
        self._products: dict[str, Product] = {p.id: p for p in (products or SAMPLE_PRODUCTS)}
        self._stock: dict[str, StockStatus] = dict(stock or INITIAL_STOCK)
        self._alerts: list[InventoryAlert] = [
            InventoryAlert(
                product_id="prod-103",
                type="posted_but_out_of_stock",
                message="Dainty Freshwater Pearl Choker is featured in active Instagram reels but is out of stock (qty: 0).",
                created_at=datetime.utcnow(),
            ),
            InventoryAlert(
                product_id="prod-115",
                type="low_stock",
                message="Carnelian Statement Collar Necklace has only 1 piece remaining in studio.",
                created_at=datetime.utcnow(),
            ),
        ]

    def get_stock(self, product_id: str) -> StockStatus | None:
        return self._stock.get(product_id)

    def find_products(self, query: str) -> list[Product]:
        query_lower = query.lower().strip()
        if not query_lower:
            return list(self._products.values())

        keywords = query_lower.split()
        results: list[Product] = []

        for p in self._products.values():
            searchable_text = f"{p.name} {p.category} {p.material} {p.description} {' '.join(p.colors)} {' '.join(p.sizes)}".lower()
            if any(kw in searchable_text for kw in keywords):
                results.append(p)
        return results

    def reserve(self, product_id: str, qty: int) -> bool:
        status = self._stock.get(product_id)
        if not status or not status.in_stock or status.quantity < qty:
            return False

        new_qty = status.quantity - qty
        self._stock[product_id] = StockStatus(
            product_id=product_id,
            quantity=new_qty,
            in_stock=new_qty > 0,
            low_stock=new_qty <= 3,
            posted_on_instagram=status.posted_on_instagram,
        )

        if new_qty <= 0 and status.posted_on_instagram:
            self._alerts.append(
                InventoryAlert(
                    product_id=product_id,
                    type="posted_but_out_of_stock",
                    message=f"Product {product_id} just ran out of stock but is active on Instagram.",
                    created_at=datetime.utcnow(),
                )
            )
        elif new_qty <= 3:
            self._alerts.append(
                InventoryAlert(
                    product_id=product_id,
                    type="low_stock",
                    message=f"Product {product_id} is down to {new_qty} units.",
                    created_at=datetime.utcnow(),
                )
            )
        return True

    def get_alerts(self) -> list[InventoryAlert]:
        return list(self._alerts)


class MockContentService:
    """In-memory Mock Content Service conforming strictly to ContentService protocol."""

    def __init__(self, brand_voice: BrandVoiceProfile | None = None):
        self.brand_voice = brand_voice or DEFAULT_BRAND_VOICE

    def generate_caption(self, req: CaptionRequest) -> CaptionResult:
        p = req.product
        extra = f" {req.extra_notes}" if req.extra_notes else ""
        caption = (
            f"Hand-forged with devotion: our {p.name}. ✨ Crafted in {p.material} "
            f"to carry gentle, grounding energy into your day.{extra} "
            f"DM us to claim your one-of-a-kind piece before studio reserves close! 🌿🌙"
        )
        hashtags = [
            f"#{p.category.replace(' ', '')}",
            "#HandmadeJewelry",
            "#AuraJewels",
            "#ArtisanMade",
            "#ConsciousLuxury",
        ]
        return CaptionResult(
            caption=caption,
            hashtags=hashtags,
            voice_match_notes="Aligned with warm, earthy artisan voice and intentional gemstone story.",
        )
