"""Product archetypes -- the source data for the curated catalog.

Owner: Member 2 (Data Engineering).

An archetype describes a *kind* of product. The generator expands each one into
many concrete SKUs across brands and marketplaces. Keeping the knowledge here
(rather than in 3,000 hand-written rows) means the catalog stays consistent
with the controlled vocabulary and can be regenerated in seconds.

Every `category`, `subcategory` and feature string here must exist in
app/core/constants.py. scripts/validate_vocab.py enforces it.

Brands are DELIBERATELY FICTIONAL. This is simulated catalog data with
simulated pricing; attaching invented prices to real companies would
misrepresent them. Every row is flagged is_simulated=True and badged in the UI.
"""

from __future__ import annotations

# --------------------------------------------------------------------------
# Brands: (name, tier, quality_bias)
#   tier         -> price multiplier band
#   quality_bias -> nudges rating; premium brands rate slightly higher
# --------------------------------------------------------------------------
BRANDS: dict[str, list[tuple[str, str, float]]] = {
    "outdoor": [
        ("Trekmate", "budget", -0.15),
        ("Voyagr", "budget", -0.10),
        ("BaseCamp Basics", "budget", -0.20),
        ("Rukmini Outdoors", "budget", -0.05),
        ("Trailhawk", "mid", 0.05),
        ("Altura Gear", "mid", 0.10),
        ("Nordkapp", "mid", 0.08),
        ("Summit & Co", "mid", 0.02),
        ("Kailash Pro", "premium", 0.22),
        ("Vertex Alpine", "premium", 0.25),
        ("Arcturus Outdoor", "premium", 0.18),
    ],
    "electronics": [
        ("Voltiq", "budget", -0.18),
        ("Nexbit", "budget", -0.12),
        ("Corely", "budget", -0.08),
        ("Zentra", "mid", 0.06),
        ("Aurex", "mid", 0.12),
        ("Kinetiq", "mid", 0.04),
        ("Obsidian Labs", "premium", 0.24),
        ("Halcyon Tech", "premium", 0.20),
    ],
    "home": [
        ("Grihaa", "budget", -0.14),
        ("DailyNest", "budget", -0.10),
        ("Casaline", "budget", -0.06),
        ("Urbanroot", "mid", 0.08),
        ("Terra Living", "mid", 0.05),
        ("Mellowhome", "mid", 0.10),
        ("Aureva Home", "premium", 0.20),
        ("Studio Neelam", "premium", 0.16),
    ],
}

TIER_MULTIPLIER: dict[str, tuple[float, float]] = {
    "budget": (0.55, 0.80),
    "mid": (0.80, 1.15),
    "premium": (1.15, 1.75),
}

# --------------------------------------------------------------------------
# Marketplaces. Each has its own pricing and delivery personality, which is
# what makes cross-source comparison produce a real winner rather than a tie.
# --------------------------------------------------------------------------
MARKETPLACES: dict[str, dict] = {
    "MARKET_A": {  # fast, slightly pricier, deep catalog
        "price_factor": (0.99, 1.08),
        "delivery": (1, 4),
        "discount_bonus": 0,
        "listing_weight": 0.45,
    },
    "MARKET_B": {  # aggressive discounting, average delivery
        "price_factor": (0.90, 1.00),
        "delivery": (3, 7),
        "discount_bonus": 6,
        "listing_weight": 0.35,
    },
    "MARKET_C": {  # cheapest, slowest, thinner catalog
        "price_factor": (0.86, 0.98),
        "delivery": (5, 11),
        "discount_bonus": 3,
        "listing_weight": 0.20,
    },
}


def _a(
    key: str,
    category: str,
    subcategory: str,
    domain: str,
    price: tuple[int, int],
    titles: list[str],
    required_features: list[str],
    optional_features: list[str],
    tags: list[str],
    models: int = 14,
    specs: dict | None = None,
) -> dict:
    return {
        "key": key,
        "category": category,
        "subcategory": subcategory,
        "domain": domain,
        "price_range": price,
        "titles": titles,
        "required_features": required_features,
        "optional_features": optional_features,
        "tags": tags,
        "models": models,
        "specs": specs or {},
    }


# --------------------------------------------------------------------------
# OUTDOOR / TREKKING -- the primary demo domain, deliberately the deepest.
# Every winter_trek requirement must resolve to >= 6 in-stock candidates.
# --------------------------------------------------------------------------
OUTDOOR: list[dict] = [
    _a("thermals", "clothing", "thermals", "outdoor", (699, 3499),
       ["Thermal Base Layer Set", "Merino Blend Thermal Top", "Winter Thermal Innerwear",
        "Heat-Retain Base Layer", "Cold Weather Thermal Set"],
       ["thermal"], ["quick_dry", "lightweight", "moisture_wicking", "breathable", "machine_washable"],
       ["winter", "trekking", "cold_weather", "layering", "beginner"], 18,
       {"material": ["Merino blend", "Polyester fleece", "Cotton blend"], "temp_rating_c": [-10, -5, 0, 5]}),

    _a("trekking_jacket", "outerwear", "jacket", "outdoor", (1499, 12999),
       ["Insulated Trekking Jacket", "Windproof Mountain Jacket", "3-Layer Shell Jacket",
        "Padded Winter Jacket", "Softshell Trek Jacket"],
       ["insulated"], ["waterproof", "windproof", "breathable", "lightweight", "seam_sealed", "adjustable"],
       ["winter", "trekking", "cold_weather", "snow", "beginner"], 22,
       {"fill": ["Synthetic 200g", "Down 600FP", "Fleece-lined"], "temp_rating_c": [-15, -10, -5, 0]}),

    _a("fleece", "clothing", "fleece", "outdoor", (899, 4499),
       ["Polar Fleece Jacket", "Mid-Layer Fleece Pullover", "Full-Zip Fleece"],
       ["insulated"], ["lightweight", "breathable", "quick_dry", "machine_washable"],
       ["winter", "trekking", "layering", "cold_weather"], 12),

    _a("trekking_pants", "clothing", "pants", "outdoor", (899, 5499),
       ["Convertible Trekking Pants", "Insulated Trek Trousers", "Quick-Dry Hiking Pants",
        "Water-Resistant Trek Pants"],
       [], ["quick_dry", "water_resistant", "lightweight", "breathable", "durable", "adjustable"],
       ["trekking", "hiking", "outdoor", "beginner"], 16),

    _a("gloves", "accessories", "gloves", "outdoor", (399, 3299),
       ["Insulated Trekking Gloves", "Waterproof Snow Gloves", "Thermal Liner Gloves",
        "Touchscreen Winter Gloves"],
       ["insulated"], ["waterproof", "windproof", "thermal", "high_grip", "adjustable"],
       ["winter", "trekking", "snow", "cold_weather"], 14),

    _a("socks", "clothing", "socks", "outdoor", (299, 1799),
       ["Merino Wool Trekking Socks", "Thermal Woolen Socks (3 Pair)", "Cushioned Hiking Socks"],
       ["thermal"], ["moisture_wicking", "quick_dry", "anti_bacterial", "durable"],
       ["winter", "trekking", "cold_weather", "essentials"], 12),

    _a("beanie", "accessories", "headwear", "outdoor", (299, 1899),
       ["Fleece-Lined Beanie", "Woolen Trekking Cap", "Windproof Ear-Flap Cap", "Balaclava Head Cover"],
       ["thermal"], ["windproof", "lightweight", "breathable"],
       ["winter", "trekking", "cold_weather"], 10),

    _a("neck_gaiter", "accessories", "neckwear", "outdoor", (249, 1299),
       ["Thermal Neck Gaiter", "Multi-Use Buff Scarf", "Fleece Neck Warmer"],
       [], ["thermal", "windproof", "quick_dry", "breathable", "uv_protection"],
       ["winter", "trekking", "cold_weather"], 8),

    _a("trekking_shoes", "footwear", "trekking_shoes", "outdoor", (1299, 11999),
       ["Waterproof Trekking Shoes", "High-Ankle Hiking Boots", "All-Terrain Trek Shoes",
        "Snow Trekking Boots"],
       ["anti_slip"], ["waterproof", "shock_absorbing", "durable", "breathable", "lightweight", "high_grip"],
       ["trekking", "hiking", "winter", "beginner", "essentials"], 20,
       {"ankle": ["High", "Mid", "Low"], "sole": ["Vibram-style rubber", "EVA + rubber", "TPR"]}),

    _a("gaiters", "accessories", "gaiters", "outdoor", (499, 2799),
       ["Snow Gaiters", "Waterproof Leg Gaiters", "Anti-Debris Trek Gaiters"],
       ["waterproof"], ["durable", "adjustable", "lightweight"],
       ["winter", "snow", "trekking"], 8),

    _a("backpack", "equipment", "backpack", "outdoor", (999, 9999),
       ["45L Trekking Rucksack", "60L Expedition Backpack", "35L Hiking Backpack",
        "Rain-Cover Trekking Pack"],
       [], ["water_resistant", "durable", "adjustable", "ergonomic", "lightweight"],
       ["trekking", "hiking", "travel", "essentials"], 18,
       {"capacity_l": [30, 35, 45, 55, 60, 70]}),

    _a("daypack", "equipment", "daypack", "outdoor", (599, 3499),
       ["20L Summit Daypack", "Foldable Daypack", "Hydration-Ready Daypack"],
       [], ["lightweight", "foldable", "water_resistant", "compact"],
       ["trekking", "hiking", "daytrip"], 10),

    _a("trekking_poles", "equipment", "trekking_poles", "outdoor", (699, 5999),
       ["Aluminium Trekking Poles (Pair)", "Carbon Fibre Trekking Pole", "Anti-Shock Trek Poles",
        "Foldable Hiking Poles"],
       ["adjustable"], ["shock_absorbing", "lightweight", "foldable", "anti_slip", "durable"],
       ["trekking", "hiking", "beginner", "knee_support"], 14,
       {"material": ["Aluminium 7075", "Carbon fibre", "Aluminium 6061"], "weight_g": [220, 260, 300, 380]}),

    _a("headlamp", "navigation", "headlamp", "outdoor", (399, 4499),
       ["Rechargeable LED Headlamp", "Waterproof Head Torch", "Motion-Sensor Headlamp",
        "High-Lumen Trekking Headlamp"],
       [], ["rechargeable", "waterproof", "lightweight", "adjustable", "durable"],
       ["trekking", "camping", "night", "safety", "essentials"], 14,
       {"lumens": [150, 250, 350, 500, 800], "runtime_h": [8, 12, 20, 40]}),

    _a("water_bottle", "hydration", "bottle", "outdoor", (299, 3499),
       ["Insulated Steel Water Bottle", "Vacuum Flask 1L", "BPA-Free Trek Bottle",
        "Double-Wall Thermos Bottle"],
       ["leak_proof"], ["insulating", "durable", "lightweight", "portable"],
       ["trekking", "hydration", "essentials", "daily"], 14,
       {"capacity_ml": [500, 750, 900, 1000, 1500]}),

    _a("hydration_bladder", "hydration", "bladder", "outdoor", (699, 3299),
       ["2L Hydration Bladder", "3L Hydration Reservoir", "Insulated Hydration Pack"],
       ["leak_proof"], ["lightweight", "durable", "portable"],
       ["trekking", "hydration", "hiking"], 8),

    _a("sleeping_bag", "camping", "sleeping_bag", "outdoor", (1299, 11999),
       ["-10C Mummy Sleeping Bag", "Lightweight Down Sleeping Bag", "3-Season Sleeping Bag",
        "Compact Trek Sleeping Bag"],
       ["insulated"], ["lightweight", "compact", "water_resistant", "machine_washable", "durable"],
       ["camping", "winter", "trekking", "overnight"], 16,
       {"temp_rating_c": [-15, -10, -5, 0, 5], "fill": ["Down 600FP", "Hollow fibre", "Synthetic"]}),

    _a("sleeping_mat", "camping", "sleeping_mat", "outdoor", (599, 4999),
       ["Inflatable Sleeping Pad", "Foam Camping Mat", "Self-Inflating Trek Mattress"],
       [], ["insulating", "lightweight", "compact", "foldable", "durable"],
       ["camping", "overnight", "trekking"], 10),

    _a("tent", "camping", "tent", "outdoor", (2499, 18999),
       ["2-Person Dome Tent", "4-Person Camping Tent", "Ultralight Backpacking Tent",
        "All-Weather Trekking Tent"],
       ["waterproof"], ["windproof", "lightweight", "compact", "durable", "seam_sealed"],
       ["camping", "overnight", "trekking"], 12,
       {"capacity_persons": [1, 2, 3, 4], "season": ["3-season", "4-season"]}),

    _a("first_aid_kit", "safety", "first_aid", "outdoor", (299, 2999),
       ["Trekking First-Aid Kit", "Compact Emergency Medical Kit", "Adventure First-Aid Pouch"],
       ["portable"], ["compact", "lightweight", "water_resistant"],
       ["safety", "trekking", "camping", "essentials", "emergency"], 10),

    _a("emergency_blanket", "safety", "emergency", "outdoor", (149, 999),
       ["Emergency Thermal Blanket", "Mylar Survival Blanket (Pack of 4)", "Bivy Emergency Sack"],
       [], ["thermal", "lightweight", "compact", "waterproof", "reflective"],
       ["safety", "emergency", "winter", "trekking"], 8),

    _a("rain_poncho", "outerwear", "rainwear", "outdoor", (299, 2499),
       ["Trekking Rain Poncho", "Waterproof Rain Jacket", "Packable Rain Cover"],
       ["waterproof"], ["lightweight", "compact", "foldable", "windproof", "seam_sealed"],
       ["monsoon", "trekking", "rain"], 10),

    _a("sunglasses", "accessories", "eyewear", "outdoor", (399, 5999),
       ["UV400 Trekking Sunglasses", "Polarised Mountain Glasses", "Snow Glare Sunglasses"],
       ["uv_protection"], ["lightweight", "durable", "shock_absorbing"],
       ["trekking", "snow", "sun_protection", "high_altitude"], 10),

    _a("sunscreen", "personal_care", "skincare", "outdoor", (249, 1499),
       ["SPF 50 Sunscreen Lotion", "High-Altitude Sun Protection Cream", "Matte SPF 50+ Gel"],
       ["uv_protection"], ["water_resistant", "portable"],
       ["trekking", "sun_protection", "high_altitude", "skincare"], 8),

    _a("power_bank_outdoor", "electronics", "power_bank", "outdoor", (799, 5999),
       ["20000mAh Rugged Power Bank", "Solar Trekking Power Bank", "10000mAh Compact Power Bank"],
       ["rechargeable"], ["portable", "durable", "compact", "water_resistant"],
       ["trekking", "camping", "electronics", "travel"], 12,
       {"capacity_mah": [10000, 15000, 20000, 26800]}),

    _a("dry_bag", "storage", "dry_bag", "outdoor", (299, 2499),
       ["Waterproof Dry Bag 20L", "Roll-Top Dry Sack Set", "Backpack Rain Cover"],
       ["waterproof"], ["lightweight", "durable", "compact", "foldable"],
       ["trekking", "monsoon", "camping", "storage"], 10),

    _a("multi_tool", "equipment", "multi_tool", "outdoor", (399, 4999),
       ["12-in-1 Trekking Multi-Tool", "Stainless Multi-Tool Pliers", "Compact Camping Knife Tool"],
       ["portable"], ["durable", "compact", "lightweight", "ergonomic"],
       ["trekking", "camping", "utility"], 10),

    _a("thermos", "hydration", "flask", "outdoor", (599, 3999),
       ["1L Vacuum Thermos Flask", "Insulated Coffee Flask", "Stainless Thermos Bottle"],
       ["insulating"], ["leak_proof", "durable", "portable"],
       ["winter", "trekking", "camping", "hydration"], 10),

    _a("camp_stove", "camping", "stove", "outdoor", (699, 5999),
       ["Portable Camping Gas Stove", "Ultralight Backpacking Stove", "Windproof Camp Burner"],
       ["portable"], ["compact", "lightweight", "windproof", "foldable", "durable"],
       ["camping", "overnight", "cooking"], 8),

    _a("trekking_towel", "personal_care", "towel", "outdoor", (249, 1499),
       ["Microfibre Quick-Dry Towel", "Compact Travel Towel Set"],
       ["quick_dry"], ["lightweight", "compact", "anti_bacterial", "machine_washable"],
       ["trekking", "camping", "travel"], 6),
]

# --------------------------------------------------------------------------
# ELECTRONICS -- powers Mode A ("laptop for programming under Rs 80,000")
# --------------------------------------------------------------------------
ELECTRONICS: list[dict] = [
    _a("laptop", "electronics", "laptop", "electronics", (28999, 159999),
       ["14\" Programming Laptop", "15.6\" Thin & Light Laptop", "16\" Creator Laptop",
        "13\" Ultraportable Notebook"],
       [], ["lightweight", "durable", "energy_efficient", "warranty_included", "portable"],
       ["programming", "work", "student", "productivity"], 26,
       {"ram_gb": [8, 16, 24, 32], "storage_gb": [256, 512, 1024], "cpu": ["i5-class", "i7-class", "Ryzen 5-class", "Ryzen 7-class"]}),

    _a("laptop_bag", "accessories", "laptop_bag", "electronics", (599, 4999),
       ["15.6\" Padded Laptop Backpack", "Slim Laptop Sleeve", "Water-Resistant Laptop Bag"],
       [], ["water_resistant", "durable", "shock_absorbing", "ergonomic", "lightweight"],
       ["work", "student", "travel", "electronics"], 12),

    _a("mouse", "electronics", "mouse", "electronics", (299, 7999),
       ["Wireless Ergonomic Mouse", "Silent Bluetooth Mouse", "Programmable Productivity Mouse"],
       [], ["ergonomic", "rechargeable", "lightweight", "portable"],
       ["work", "programming", "student", "accessories"], 14),

    _a("keyboard", "electronics", "keyboard", "electronics", (699, 14999),
       ["Mechanical TKL Keyboard", "Wireless Low-Profile Keyboard", "Backlit Membrane Keyboard"],
       [], ["ergonomic", "durable", "rechargeable", "portable"],
       ["work", "programming", "student"], 14),

    _a("monitor", "electronics", "monitor", "electronics", (7999, 54999),
       ["24\" IPS Full-HD Monitor", "27\" QHD Monitor", "27\" 4K Productivity Monitor"],
       [], ["adjustable", "energy_efficient", "warranty_included", "ergonomic"],
       ["work", "programming", "productivity"], 14),

    _a("headphones", "electronics", "headphones", "electronics", (799, 34999),
       ["ANC Over-Ear Headphones", "Studio Wired Headphones", "Wireless Bluetooth Headphones"],
       ["rechargeable"], ["lightweight", "ergonomic", "durable", "portable"],
       ["work", "travel", "music", "focus"], 16),

    _a("earbuds", "electronics", "earbuds", "electronics", (599, 24999),
       ["True Wireless Earbuds", "ANC Earbuds with Case", "Sports Wireless Earbuds"],
       ["rechargeable"], ["water_resistant", "lightweight", "compact", "portable"],
       ["travel", "fitness", "music", "daily"], 14),

    _a("power_bank", "electronics", "power_bank", "electronics", (699, 6999),
       ["20000mAh Fast-Charge Power Bank", "10000mAh Slim Power Bank", "45W PD Power Bank"],
       ["rechargeable"], ["portable", "compact", "energy_efficient", "durable"],
       ["travel", "daily", "electronics"], 12),

    _a("charger", "electronics", "charger", "electronics", (399, 5999),
       ["65W GaN Fast Charger", "Multi-Port USB-C Charger", "30W Compact Wall Charger"],
       [], ["compact", "energy_efficient", "portable", "warranty_included"],
       ["travel", "daily", "electronics"], 10),

    _a("smartwatch", "electronics", "smartwatch", "electronics", (1499, 44999),
       ["GPS Fitness Smartwatch", "AMOLED Smartwatch", "Rugged Outdoor Smartwatch"],
       ["rechargeable"], ["water_resistant", "lightweight", "durable", "portable"],
       ["fitness", "trekking", "daily", "health"], 14),

    _a("router", "electronics", "router", "electronics", (999, 14999),
       ["AX1800 Wi-Fi 6 Router", "Dual-Band Wi-Fi Router", "Mesh Wi-Fi System (2-Pack)"],
       [], ["energy_efficient", "durable", "warranty_included"],
       ["home_setup", "work", "internet"], 10),

    _a("external_ssd", "electronics", "storage", "electronics", (2499, 24999),
       ["1TB Portable SSD", "512GB USB-C SSD", "2TB Rugged External SSD"],
       ["portable"], ["shock_absorbing", "compact", "durable", "lightweight"],
       ["work", "programming", "backup"], 10),

    _a("webcam", "electronics", "webcam", "electronics", (999, 12999),
       ["1080p Full-HD Webcam", "4K Streaming Webcam", "Auto-Focus Conference Webcam"],
       [], ["portable", "adjustable", "compact"],
       ["work", "remote_work", "student"], 8),

    _a("speaker", "electronics", "speaker", "electronics", (799, 19999),
       ["Portable Bluetooth Speaker", "Waterproof Outdoor Speaker", "Desktop Stereo Speakers"],
       ["rechargeable"], ["portable", "water_resistant", "compact", "durable"],
       ["home_setup", "travel", "music"], 10),

    _a("desk_lamp", "electronics", "lighting", "home", (399, 5999),
       ["LED Study Desk Lamp", "Adjustable Reading Lamp", "Eye-Care Table Lamp"],
       [], ["adjustable", "energy_efficient", "rechargeable", "ergonomic"],
       ["home_setup", "student", "work", "study"], 10),

    _a("extension_board", "electronics", "power_strip", "home", (299, 2999),
       ["6-Socket Surge Extension Board", "USB Extension Power Strip", "Wall-Mount Power Board"],
       [], ["durable", "energy_efficient", "compact", "warranty_included"],
       ["home_setup", "hostel", "apartment"], 8),
]

# --------------------------------------------------------------------------
# HOME / APARTMENT SETUP -- second demo scenario
# --------------------------------------------------------------------------
HOME: list[dict] = [
    _a("mattress", "bedding", "mattress", "home", (2999, 34999),
       ["6\" Orthopedic Foam Mattress", "Dual-Comfort Single Mattress", "Memory Foam Queen Mattress"],
       [], ["durable", "ergonomic", "machine_washable", "warranty_included"],
       ["apartment", "home_setup", "bedroom", "hostel"], 14,
       {"size": ["Single", "Double", "Queen", "King"], "thickness_in": [4, 5, 6, 8]}),

    _a("bedsheet", "bedding", "bedsheet", "home", (399, 4999),
       ["Cotton Double Bedsheet Set", "Microfibre Bedsheet with Pillow Covers", "Percale Cotton Sheet Set"],
       ["machine_washable"], ["breathable", "durable", "quick_dry"],
       ["apartment", "home_setup", "bedroom", "hostel"], 12),

    _a("pillow", "bedding", "pillow", "home", (299, 3999),
       ["Memory Foam Pillow", "Microfibre Pillow (Pack of 2)", "Cervical Support Pillow"],
       [], ["machine_washable", "ergonomic", "breathable", "anti_bacterial"],
       ["apartment", "home_setup", "bedroom", "hostel"], 10),

    _a("blanket", "bedding", "blanket", "home", (599, 6999),
       ["Winter Fleece Blanket", "Lightweight Summer Comforter", "Reversible Woolen Blanket"],
       [], ["machine_washable", "thermal", "lightweight", "breathable"],
       ["apartment", "home_setup", "winter", "bedroom"], 10),

    _a("curtains", "furniture", "curtains", "home", (499, 5999),
       ["Blackout Door Curtains (Set of 2)", "Sheer Window Curtains", "Thermal Insulated Curtains"],
       ["machine_washable"], ["uv_protection", "durable", "insulating"],
       ["apartment", "home_setup", "living_room"], 10),

    _a("study_table", "furniture", "table", "home", (1999, 19999),
       ["Foldable Study Table", "Engineered Wood Work Desk", "Compact Writing Desk with Shelf"],
       [], ["foldable", "durable", "ergonomic", "compact"],
       ["apartment", "home_setup", "student", "work", "hostel"], 12),

    _a("chair", "furniture", "chair", "home", (1499, 24999),
       ["Ergonomic Mesh Office Chair", "Foldable Study Chair", "High-Back Executive Chair"],
       ["ergonomic"], ["adjustable", "durable", "foldable", "warranty_included"],
       ["apartment", "home_setup", "work", "student"], 14),

    _a("bookshelf", "furniture", "shelving", "home", (999, 12999),
       ["4-Tier Bookshelf", "Wall-Mount Floating Shelves", "Foldable Storage Bookrack"],
       [], ["durable", "foldable", "compact"],
       ["apartment", "home_setup", "storage", "student"], 10),

    _a("storage_rack", "storage", "rack", "home", (599, 7999),
       ["5-Layer Storage Rack", "Foldable Cloth Wardrobe", "Stackable Utility Shelf"],
       [], ["foldable", "durable", "compact", "portable"],
       ["apartment", "home_setup", "storage", "hostel"], 10),

    _a("cookware_set", "kitchen", "cookware", "home", (999, 14999),
       ["Non-Stick Cookware Set (5-Piece)", "Stainless Steel Cookware Combo", "Induction-Base Kadai Set"],
       ["durable"], ["energy_efficient", "machine_washable", "ergonomic"],
       ["apartment", "home_setup", "kitchen", "cooking"], 12),

    _a("pressure_cooker", "kitchen", "cooker", "home", (899, 6999),
       ["3L Stainless Pressure Cooker", "5L Induction Pressure Cooker", "2L Compact Cooker"],
       ["durable"], ["energy_efficient", "warranty_included", "ergonomic"],
       ["apartment", "home_setup", "kitchen", "cooking"], 10),

    _a("induction_cooktop", "kitchen", "cooktop", "home", (1299, 8999),
       ["2000W Induction Cooktop", "Touch-Panel Induction Stove", "Portable Induction Hob"],
       ["energy_efficient"], ["compact", "portable", "durable", "warranty_included"],
       ["apartment", "home_setup", "kitchen", "hostel"], 10),

    _a("dinner_set", "kitchen", "tableware", "home", (599, 7999),
       ["18-Piece Melamine Dinner Set", "Stainless Steel Dinner Set", "Ceramic Dinnerware Set"],
       ["machine_washable"], ["durable", "lightweight"],
       ["apartment", "home_setup", "kitchen"], 10),

    _a("water_purifier", "kitchen", "purifier", "home", (3999, 24999),
       ["RO + UV Water Purifier", "Gravity Water Filter 20L", "UV Countertop Purifier"],
       [], ["energy_efficient", "durable", "warranty_included", "compact"],
       ["apartment", "home_setup", "kitchen", "health"], 10),

    _a("iron", "personal_care", "iron", "home", (499, 5999),
       ["1200W Dry Iron", "Steam Iron with Anti-Drip", "Travel Folding Iron"],
       [], ["energy_efficient", "compact", "durable", "warranty_included", "portable"],
       ["apartment", "home_setup", "hostel", "daily"], 8),

    _a("bucket_mug", "storage", "bathroom", "home", (199, 1499),
       ["Bucket & Mug Set", "20L Plastic Bucket", "Bathroom Storage Combo"],
       ["durable"], ["lightweight", "portable"],
       ["apartment", "home_setup", "bathroom", "hostel"], 8),

    _a("cleaning_kit", "personal_care", "cleaning", "home", (299, 2999),
       ["Home Cleaning Starter Kit", "Microfibre Mop with Bucket", "Broom + Wiper Combo"],
       [], ["durable", "lightweight", "ergonomic", "machine_washable"],
       ["apartment", "home_setup", "cleaning", "hostel"], 8),

    _a("dustbin", "storage", "waste", "home", (249, 2499),
       ["Pedal Dustbin 10L", "Dual-Compartment Segregation Bin", "Slim Kitchen Dustbin"],
       ["durable"], ["compact", "leak_proof", "lightweight"],
       ["apartment", "home_setup", "kitchen"], 6),

    _a("laundry_basket", "storage", "laundry", "home", (299, 2999),
       ["Foldable Laundry Basket", "Collapsible Laundry Hamper", "3-Section Laundry Sorter"],
       ["foldable"], ["lightweight", "durable", "portable", "machine_washable"],
       ["apartment", "home_setup", "hostel", "storage"], 8),

    _a("door_mat", "furniture", "mat", "home", (149, 1999),
       ["Anti-Slip Door Mat", "Coir Entrance Mat", "Microfibre Absorbent Mat"],
       ["anti_slip"], ["machine_washable", "durable", "quick_dry"],
       ["apartment", "home_setup", "entrance"], 6),

    _a("hangers", "storage", "hangers", "home", (199, 1499),
       ["Wooden Clothes Hangers (Pack of 12)", "Non-Slip Velvet Hangers (Pack of 20)"],
       ["anti_slip"], ["durable", "lightweight", "compact"],
       ["apartment", "home_setup", "wardrobe", "hostel"], 6),

    _a("mirror", "furniture", "mirror", "home", (499, 6999),
       ["Full-Length Wall Mirror", "LED Vanity Mirror", "Frameless Bathroom Mirror"],
       [], ["durable", "shock_absorbing", "lightweight"],
       ["apartment", "home_setup", "bedroom"], 8),

    _a("luggage", "storage", "luggage", "home", (1499, 17999),
       ["Hard-Shell Cabin Trolley", "Expandable Check-In Trolley", "Duffel Travel Bag 60L"],
       ["durable"], ["lightweight", "water_resistant", "portable", "adjustable"],
       ["travel", "trekking", "apartment", "moving"], 12),

    _a("umbrella", "accessories", "umbrella", "home", (299, 2499),
       ["Windproof Compact Umbrella", "Automatic Folding Umbrella", "UV-Coated Sun Umbrella"],
       ["waterproof"], ["windproof", "compact", "foldable", "uv_protection", "portable"],
       ["monsoon", "travel", "daily"], 8),
]

ALL_ARCHETYPES: list[dict] = OUTDOOR + ELECTRONICS + HOME

# Which brand pool an archetype draws from.
DOMAIN_BRAND_POOL: dict[str, str] = {
    "outdoor": "outdoor",
    "electronics": "electronics",
    "home": "home",
}
