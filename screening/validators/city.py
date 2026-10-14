"""Map what the candidate wrote to a configured city.

Exact matching runs first, on every run of 1-5 words in the text, against city
names, aliases and neighborhoods (so "vivo en Gràcia" finds Barcelona). A longer
match beats a shorter one inside it ("San Pedro Garza García" is Monterrey, while
a bare "San Pedro" belongs to two cities and is ambiguous). Only if
nothing matches exactly do we try fuzzy matching, for typos like "Barcelna".
A strong single fuzzy hit counts as a match; anything weaker becomes a short list
of options for the candidate to choose from, because guessing a city wrong could
wrongly disqualify someone.
"""

from dataclasses import dataclass, field
from typing import Literal

from rapidfuzz import fuzz

from screening.config import ScreeningConfig
from screening.schemas import Location
from screening.validators.text import normalize

MAX_WORDS = 5
FUZZY_MATCH = 90  # at or above: treat as the city
FUZZY_SUGGEST = 80  # at or above: offer it as an option
FUZZY_MIN_LENGTH = 4  # short aliases like "df" or "mad" only match exactly
MAX_OPTIONS = 3


@dataclass(frozen=True)
class CityMatch:
    kind: Literal["matched", "ambiguous", "not_served"]
    location: Location | None = None  # when matched
    options: list[Location] = field(default_factory=list)  # when ambiguous
    city_text: str | None = None  # when not_served: what the candidate wrote


def match_city(text: str, config: ScreeningConfig) -> CityMatch:
    index, regions, locations = _index(config)
    words = normalize(text).split()
    grams = [
        " ".join(words[start : start + size])
        for size in range(1, MAX_WORDS + 1)
        for start in range(len(words) - size + 1)
    ]

    matched = [gram for gram in grams if gram in index or gram in regions]
    longest = [gram for gram in matched if not any(_inside(gram, other) for other in matched)]
    city_grams = [gram for gram in longest if gram in index]
    # Names that agree ("San Pedro, Monterrey", "Gràcia, Barcelona") mean the city they
    # share; names that disagree ("entre Madrid y Barcelona") leave every option open.
    shared = (
        [key for key in index[city_grams[0]] if all(key in index[g] for g in city_grams)]
        if city_grams
        else []
    )
    exact = shared or list(dict.fromkeys(key for gram in city_grams for key in index[gram]))
    if not exact:
        # Only a region ("Nuevo León"): offer its cities, never call it out of the area.
        in_region = list(dict.fromkeys(key for gram in longest for key in regions.get(gram, [])))
        if in_region:
            return CityMatch(
                "ambiguous", options=[locations[key] for key in in_region[:MAX_OPTIONS]]
            )
    if len(exact) == 1:
        return CityMatch("matched", location=locations[exact[0]])
    if exact:
        return CityMatch("ambiguous", options=[locations[key] for key in exact[:MAX_OPTIONS]])

    scores: dict[str, float] = {}
    for gram in grams:
        if len(gram) < FUZZY_MIN_LENGTH:
            continue
        for term, keys in index.items():
            if len(term) >= FUZZY_MIN_LENGTH:
                for key in keys:
                    scores[key] = max(fuzz.ratio(gram, term), scores.get(key, 0))
    ranked = sorted(scores, key=scores.__getitem__, reverse=True)
    strong = [key for key in ranked if scores[key] >= FUZZY_MATCH]
    if len(strong) == 1:
        return CityMatch("matched", location=locations[strong[0]])
    suggestions = [key for key in ranked if scores[key] >= FUZZY_SUGGEST]
    if suggestions:
        return CityMatch("ambiguous", options=[locations[key] for key in suggestions[:MAX_OPTIONS]])
    return CityMatch("not_served", city_text=text.strip())


def _inside(gram: str, other: str) -> bool:
    """True when `gram` is a shorter run of words within `other`."""
    return gram != other and f" {gram} " in f" {other} "


def _index(
    config: ScreeningConfig,
) -> tuple[dict[str, list[str]], dict[str, list[str]], dict[str, Location]]:
    """Normalized name, alias and neighborhood -> city keys; region -> city keys;
    city key -> Location.

    A term may belong to several cities (two metros can share a neighborhood name).

    Rebuilt per call: it is about 150 entries, and keeping it pure avoids a cache
    that would go stale if config changed.
    """
    index: dict[str, list[str]] = {}
    regions: dict[str, list[str]] = {}
    locations: dict[str, Location] = {}
    for country, area in config.service_areas.items():
        for city in area.cities:
            locations[city.key] = Location(country=country, city=city.key)
            for term in [city.key, city.name, *city.aliases, *city.neighborhoods]:
                keys = index.setdefault(normalize(term), [])
                if city.key not in keys:
                    keys.append(city.key)
            for region in city.regions:
                regions.setdefault(normalize(region), []).append(city.key)
    return index, regions, locations
