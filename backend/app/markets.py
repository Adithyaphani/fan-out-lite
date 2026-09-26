"""Market presets. Cues are short prompt fragments about setting and props,
never about people — reviewed once as a team to stay respectful.
"""
from __future__ import annotations

import math

from .bible import Market
from .config import settings

# Catalog: two famous cities per country. The original four ids (IN, BR, KR, NG)
# are preserved for backward compatibility with the fallback run and prerender.
# Cues describe setting, props, light and music only — never people.
MARKETS: dict[str, Market] = {
    # India
    "IN": Market(
        id="IN", city="Delhi", country="India", language="Hindi", script="Devanagari",
        cultural_cues=["warm evening light", "busy street cafe", "kulhad cups nearby"],
        music_style="modern filmi-pop, tabla and synth",
    ),
    "IN-MUM": Market(
        id="IN-MUM", city="Mumbai", country="India", language="Hindi", script="Devanagari",
        cultural_cues=["seaside promenade", "monsoon-slick streets", "art-deco facades"],
        music_style="Bollywood pop, dhol and strings",
    ),
    # Brazil
    "BR": Market(
        id="BR", city="Sao Paulo", country="Brazil", language="Portuguese", script="Latin",
        cultural_cues=["urban rooftop", "tropical plants", "bright afternoon"],
        music_style="bossa nova groove, nylon guitar",
    ),
    "BR-RIO": Market(
        id="BR-RIO", city="Rio de Janeiro", country="Brazil", language="Portuguese", script="Latin",
        cultural_cues=["beachfront boardwalk", "mosaic pavement", "golden coastal light"],
        music_style="samba-funk, bright percussion",
    ),
    # South Korea
    "KR": Market(
        id="KR", city="Seoul", country="South Korea", language="Korean", script="Hangul",
        cultural_cues=["minimal cafe interior", "neon evening", "convenience-store aesthetic"],
        music_style="K-pop synth pop, punchy drums",
    ),
    "KR-BUS": Market(
        id="KR-BUS", city="Busan", country="South Korea", language="Korean", script="Hangul",
        cultural_cues=["harbour skyline", "hillside pastel houses", "coastal breeze"],
        music_style="city-pop synths, mellow groove",
    ),
    # Nigeria
    "NG": Market(
        id="NG", city="Lagos", country="Nigeria", language="English", script="Latin",
        cultural_cues=["vibrant market colours", "sunny street", "modern office break"],
        music_style="Afrobeats, percussion-forward",
    ),
    "NG-ABV": Market(
        id="NG-ABV", city="Abuja", country="Nigeria", language="English", script="Latin",
        cultural_cues=["wide modern boulevards", "granite hills backdrop", "clear daylight"],
        music_style="Afro-soul, smooth horns",
    ),
    # Japan
    "JP-TYO": Market(
        id="JP-TYO", city="Tokyo", country="Japan", language="Japanese", script="Japanese",
        cultural_cues=["neon crossing at dusk", "compact modern interior", "rain reflections"],
        music_style="future-funk, crisp synths",
    ),
    "JP-OSA": Market(
        id="JP-OSA", city="Osaka", country="Japan", language="Japanese", script="Japanese",
        cultural_cues=["street-food alley signage", "canal-side lights", "lively evening"],
        music_style="J-pop groove, upbeat brass",
    ),
    # United States
    "US-NYC": Market(
        id="US-NYC", city="New York", country="United States", language="English", script="Latin",
        cultural_cues=["brownstone stoop", "yellow-cab street", "crisp morning light"],
        music_style="boom-bap hip-hop, warm bass",
    ),
    "US-LAX": Market(
        id="US-LAX", city="Los Angeles", country="United States", language="English", script="Latin",
        cultural_cues=["palm-lined boulevard", "sun-bleached pastels", "golden-hour haze"],
        music_style="West-coast lo-fi, laid-back beat",
    ),
    # France
    "FR-PAR": Market(
        id="FR-PAR", city="Paris", country="France", language="French", script="Latin",
        cultural_cues=["sidewalk cafe terrace", "Haussmann facades", "soft overcast light"],
        music_style="French house, filtered disco",
    ),
    "FR-LYO": Market(
        id="FR-LYO", city="Lyon", country="France", language="French", script="Latin",
        cultural_cues=["riverside quay", "pastel old-town walls", "warm afternoon"],
        music_style="nu-jazz, mellow keys",
    ),
    # Mexico
    "MX-MEX": Market(
        id="MX-MEX", city="Mexico City", country="Mexico", language="Spanish", script="Latin",
        cultural_cues=["colourful tiled courtyard", "leafy plaza", "bright high-altitude light"],
        music_style="cumbia-electronica, warm percussion",
    ),
    "MX-GDL": Market(
        id="MX-GDL", city="Guadalajara", country="Mexico", language="Spanish", script="Latin",
        cultural_cues=["colonial arcades", "agave-field outskirts", "sunny plaza"],
        music_style="mariachi-pop fusion, bright brass",
    ),
    # United Kingdom
    "GB-LON": Market(
        id="GB-LON", city="London", country="United Kingdom", language="English", script="Latin",
        cultural_cues=["rainy brick terraces", "double-decker street", "soft grey light"],
        music_style="UK garage, crisp two-step",
    ),
    "GB-MAN": Market(
        id="GB-MAN", city="Manchester", country="United Kingdom", language="English", script="Latin",
        cultural_cues=["industrial canal-side", "red-brick warehouses", "moody overcast"],
        music_style="indie-electronic, driving bass",
    ),
    # Germany
    "DE-BER": Market(
        id="DE-BER", city="Berlin", country="Germany", language="German", script="Latin",
        cultural_cues=["concrete minimalism", "graffiti courtyard", "cool diffuse light"],
        music_style="minimal techno, deep pulse",
    ),
    "DE-MUC": Market(
        id="DE-MUC", city="Munich", country="Germany", language="German", script="Latin",
        cultural_cues=["clean modern plaza", "alpine backdrop", "bright crisp air"],
        music_style="melodic house, warm synths",
    ),
    # Italy
    "IT-ROM": Market(
        id="IT-ROM", city="Rome", country="Italy", language="Italian", script="Latin",
        cultural_cues=["ancient stone piazza", "espresso-bar counter", "golden afternoon"],
        music_style="cinematic italo-disco, lush strings",
    ),
    "IT-MIL": Market(
        id="IT-MIL", city="Milan", country="Italy", language="Italian", script="Latin",
        cultural_cues=["fashion-district arcade", "sleek glass facades", "elegant light"],
        music_style="polished nu-disco, chic groove",
    ),
    # Spain
    "ES-MAD": Market(
        id="ES-MAD", city="Madrid", country="Spain", language="Spanish", script="Latin",
        cultural_cues=["tiled plaza", "tapas-bar terrace", "warm golden dusk"],
        music_style="flamenco-pop fusion, hand-claps",
    ),
    "ES-BCN": Market(
        id="ES-BCN", city="Barcelona", country="Spain", language="Spanish", script="Latin",
        cultural_cues=["modernista mosaics", "seaside boulevard", "bright mediterranean light"],
        music_style="balearic house, sunny groove",
    ),
    # United Arab Emirates
    "AE-DXB": Market(
        id="AE-DXB", city="Dubai", country="United Arab Emirates", language="Arabic", script="Arabic",
        cultural_cues=["glass-tower skyline", "desert-edge highway", "warm amber dusk"],
        music_style="Khaleeji pop, lush electronic",
    ),
    "AE-AUH": Market(
        id="AE-AUH", city="Abu Dhabi", country="United Arab Emirates", language="Arabic", script="Arabic",
        cultural_cues=["waterfront corniche", "modern white architecture", "bright coastal sun"],
        music_style="orchestral Arabic pop, sweeping strings",
    ),
    # Australia
    "AU-SYD": Market(
        id="AU-SYD", city="Sydney", country="Australia", language="English", script="Latin",
        cultural_cues=["harbour-side promenade", "coastal cliffs", "clear bright daylight"],
        music_style="sunny surf-pop, bright guitars",
    ),
    "AU-MEL": Market(
        id="AU-MEL", city="Melbourne", country="Australia", language="English", script="Latin",
        cultural_cues=["laneway cafe culture", "street-art walls", "soft overcast"],
        music_style="indie-pop, jangly rhythm",
    ),
    # China
    "CN-SHA": Market(
        id="CN-SHA", city="Shanghai", country="China", language="Chinese", script="Chinese",
        cultural_cues=["neon riverfront skyline", "sleek modern interior", "electric evening"],
        music_style="mandopop-electronic, glossy synths",
    ),
    "CN-CAN": Market(
        id="CN-CAN", city="Guangzhou", country="China", language="Chinese", script="Chinese",
        cultural_cues=["subtropical tower blocks", "tea-house courtyard", "humid soft light"],
        music_style="cantopop groove, smooth keys",
    ),
    # Indonesia
    "ID-JKT": Market(
        id="ID-JKT", city="Jakarta", country="Indonesia", language="Indonesian", script="Latin",
        cultural_cues=["bustling street stalls", "tropical greenery", "warm humid haze"],
        music_style="dangdut-pop fusion, lively percussion",
    ),
    "ID-BDG": Market(
        id="ID-BDG", city="Bandung", country="Indonesia", language="Indonesian", script="Latin",
        cultural_cues=["highland cafe terrace", "volcano backdrop", "cool bright morning"],
        music_style="tropical indie-pop, mellow groove",
    ),
    # South Africa
    "ZA-JNB": Market(
        id="ZA-JNB", city="Johannesburg", country="South Africa", language="English", script="Latin",
        cultural_cues=["urban rooftop", "colourful township murals", "high-veld sunlight"],
        music_style="amapiano, log-drum groove",
    ),
    "ZA-CPT": Market(
        id="ZA-CPT", city="Cape Town", country="South Africa", language="English", script="Latin",
        cultural_cues=["table-mountain backdrop", "pastel bo-kaap streets", "clear coastal light"],
        music_style="afro-house, breezy melody",
    ),
    # Turkey
    "TR-IST": Market(
        id="TR-IST", city="Istanbul", country="Turkey", language="Turkish", script="Latin",
        cultural_cues=["bosphorus waterfront", "spice-market arches", "warm golden light"],
        music_style="anatolian-electronic, hypnotic groove",
    ),
    "TR-ANK": Market(
        id="TR-ANK", city="Ankara", country="Turkey", language="Turkish", script="Latin",
        cultural_cues=["modern civic plazas", "hillside cityscape", "crisp clear light"],
        music_style="turkish pop, bright synths",
    ),
}

# Preselected in the UI and used when a run supplies no valid markets.
DEFAULT_MARKET_IDS: list[str] = ["IN", "BR", "KR", "NG"]

# Narrative arc used to label an arbitrary number of scenes. The middle beats
# cycle so any scene count still opens on "establishing" and closes on "cta";
# at n=6 this reproduces the classic establishing/product/hero/lifestyle/macro/cta.
_MIDDLE_BEATS = ["product", "hero", "lifestyle", "macro", "detail"]

_ROLE_DESCRIPTIONS = {
    "establishing": "wide establishing shot that sets the scene and mood",
    "product": "clean product reveal, centred, shallow depth of field",
    "hero": "the hero moment: a satisfying use of the product",
    "lifestyle": "a person enjoying the product in an everyday setting",
    "macro": "extreme close-up macro on texture, condensation or detail",
    "detail": "a design or ingredient detail that sells the product",
    "cta": "final logo / product beauty shot for the call to action",
}


def plan_shot_count(duration_s: float) -> int:
    """How many storyboard scenes for an ad of this length.

    Omni rejects any single clip shorter than VIDEO_MIN_S or longer than
    VIDEO_MAX_S, so when the timeline is split evenly across n scenes, n must
    satisfy VIDEO_MIN_S <= duration/n <= VIDEO_MAX_S:

      - n_min = ceil(duration / VIDEO_MAX_S)  -- enough scenes that none exceeds the cap
      - n_max = floor(duration / VIDEO_MIN_S) -- not so many that any scene is under the floor

    A short ad (e.g. 6s) may only support 1-2 scenes at the 3s floor — forcing
    a fixed minimum of 3 here is what used to make every scene under 9s total
    request an invalid (<3s) clip and fail outright. We pick the largest n in
    [n_min, n_max] up to a readable cap of 6, so longer ads still get a full
    storyboard while short ones degrade gracefully to fewer, longer scenes.
    """
    lo = max(0.1, float(settings.VIDEO_MIN_S))
    hi = max(lo, float(settings.VIDEO_MAX_S))
    n_min = max(1, math.ceil(duration_s / hi))
    n_max = max(1, math.floor(duration_s / lo))
    if n_max < n_min:
        n_max = n_min  # duration shorter than one min-length clip; fall back to n_min
    preferred = min(6, n_max)
    return max(n_min, min(n_max, preferred))


def build_shots(n: int) -> list[dict[str, str]]:
    """Build an n-scene skeleton with a coherent narrative arc."""
    if n <= 1:
        # A very short ad is one continuous hero shot, not a multi-beat arc.
        return [{"id": "s1", "role": "hero", "description": _ROLE_DESCRIPTIONS["hero"]}]
    shots: list[dict[str, str]] = []
    for i in range(n):
        if i == 0:
            role = "establishing"
        elif i == n - 1:
            role = "cta"
        else:
            role = _MIDDLE_BEATS[(i - 1) % len(_MIDDLE_BEATS)]
        shots.append({"id": f"s{i + 1}", "role": role, "description": _ROLE_DESCRIPTIONS[role]})
    return shots


def market_ids() -> list[str]:
    return list(MARKETS.keys())
