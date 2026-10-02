"""Approximate major-road alignments around Kondapur, Hyderabad.

Waypoints are hand-placed near real localities so the map looks plausible,
but alignments are simplified and illustrative — not surveyed geometry.
Pole sites placed along them are fictional.
"""

GEOGRAPHY_NOTICE = (
    "Road alignments are simplified approximations of real corridors; "
    "pole sites are fictional and placed for illustration."
)

# (label, lat, lng)
Waypoint = tuple[str, float, float]

ROADS: list[dict] = [
    {
        "name": "Kondapur Main Road",
        "importance": 88,
        "waypoints": [
            ("Kothaguda Junction", 17.4609, 78.3713),
            ("Kondapur Junction", 17.4622, 78.3655),
            ("Kondapur RTO", 17.4635, 78.3585),
            ("Masjid Banda", 17.4648, 78.3500),
        ],
    },
    {
        "name": "Kondapur–Financial District Corridor",
        "importance": 92,
        "waypoints": [
            ("Kondapur Junction", 17.4622, 78.3655),
            ("Botanical Garden", 17.4567, 78.3585),
            ("DLF Cyber City", 17.4460, 78.3560),
            ("Gachibowli Junction", 17.4401, 78.3489),
            ("Wipro Circle", 17.4206, 78.3410),
            ("Financial District", 17.4150, 78.3440),
        ],
    },
    {
        "name": "HITEC City Connectivity Road",
        "importance": 95,
        "waypoints": [
            ("Kothaguda Junction", 17.4609, 78.3713),
            ("Shilparamam", 17.4525, 78.3782),
            ("Cyber Towers", 17.4504, 78.3809),
            ("Mindspace Junction", 17.4410, 78.3790),
        ],
    },
    {
        "name": "Kothaguda Connectivity Road",
        "importance": 74,
        "waypoints": [
            ("Kothaguda Junction", 17.4609, 78.3713),
            ("Kothaguda Lake", 17.4645, 78.3760),
            ("HITEC City MMTS", 17.4660, 78.3830),
        ],
    },
    {
        "name": "Gachibowli Main Corridor",
        "importance": 90,
        "waypoints": [
            ("Gachibowli Junction", 17.4401, 78.3489),
            ("Telecom Nagar", 17.4412, 78.3600),
            ("IKEA Junction", 17.4428, 78.3710),
            ("Mindspace Junction", 17.4410, 78.3790),
        ],
    },
    {
        "name": "Hafeezpet–Miyapur Road",
        "importance": 70,
        "waypoints": [
            ("Kondapur Junction", 17.4622, 78.3655),
            ("Hafeezpet", 17.4810, 78.3610),
            ("Miyapur", 17.4968, 78.3577),
        ],
    },
    {
        "name": "JNTU–HITEC City Road",
        "importance": 84,
        "waypoints": [
            ("JNTU Junction", 17.4933, 78.3915),
            ("KPHB Phase 9", 17.4805, 78.3895),
            ("HITEC City MMTS", 17.4660, 78.3830),
            ("Cyber Towers", 17.4504, 78.3809),
        ],
    },
    {
        "name": "Madhapur–Jubilee Hills Road",
        "importance": 86,
        "waypoints": [
            ("Cyber Towers", 17.4504, 78.3809),
            ("Madhapur", 17.4483, 78.3915),
            ("Jubilee Hills Road No. 36", 17.4352, 78.4020),
            ("Jubilee Hills Check Post", 17.4300, 78.4080),
        ],
    },
    {
        "name": "Mumbai Highway (NH65) — Kukatpally–Chandanagar",
        "importance": 82,
        "waypoints": [
            ("JNTU Junction", 17.4933, 78.3915),
            ("Allwyn X Roads", 17.4950, 78.3720),
            ("Miyapur", 17.4968, 78.3577),
            ("Chandanagar", 17.4930, 78.3290),
        ],
    },
    {
        "name": "Gachibowli–Lingampally Road",
        "importance": 68,
        "waypoints": [
            ("Gachibowli Junction", 17.4401, 78.3489),
            ("IIIT Junction", 17.4455, 78.3440),
            ("University of Hyderabad", 17.4560, 78.3330),
            ("Lingampally", 17.4840, 78.3170),
        ],
    },
    {
        "name": "Raidurg–Khajaguda Road",
        "importance": 76,
        "waypoints": [
            ("Mindspace Junction", 17.4410, 78.3790),
            ("Raidurg Metro", 17.4300, 78.3850),
            ("Khajaguda", 17.4180, 78.3770),
            ("Manikonda", 17.4030, 78.3790),
        ],
    },
    {
        "name": "Nanakramguda Road",
        "importance": 72,
        "waypoints": [
            ("Wipro Circle", 17.4206, 78.3410),
            ("Nanakramguda", 17.4190, 78.3560),
            ("Khajaguda", 17.4180, 78.3770),
        ],
    },
    {
        "name": "Outer Ring Road — Gachibowli Stretch",
        "importance": 80,
        "waypoints": [
            ("Nanakramguda ORR Exit", 17.4150, 78.3330),
            ("Gachibowli ORR Exit", 17.4350, 78.3300),
            ("Nallagandla ORR", 17.4620, 78.3150),
            ("Tellapur ORR", 17.4850, 78.3010),
        ],
    },
    {
        "name": "Nallagandla–Serilingampally Road",
        "importance": 58,
        "waypoints": [
            ("University of Hyderabad", 17.4560, 78.3330),
            ("Nallagandla", 17.4640, 78.3070),
        ],
    },
    {
        "name": "Durgam Cheruvu Cable Bridge Road",
        "importance": 78,
        "waypoints": [
            ("Inorbit Mall", 17.4344, 78.3866),
            ("Cable Bridge", 17.4317, 78.3920),
            ("Jubilee Hills Road No. 45", 17.4300, 78.4020),
        ],
    },
]

# Commercial hubs used by the synthetic model to shape footfall.
# (label, lat, lng, weight, sigma_km)
HUBS: list[tuple[str, float, float, float, float]] = [
    ("Cyber Towers / HITEC City", 17.4504, 78.3809, 1.00, 1.4),
    ("Kondapur Junction", 17.4622, 78.3655, 0.85, 1.1),
    ("Gachibowli Junction", 17.4401, 78.3489, 0.80, 1.2),
    ("Financial District", 17.4180, 78.3430, 0.70, 1.4),
    ("Madhapur", 17.4483, 78.3915, 0.65, 1.1),
    ("Miyapur", 17.4968, 78.3577, 0.45, 1.1),
    ("JNTU / KPHB", 17.4933, 78.3915, 0.50, 1.2),
]
