"""Where the candidate is, for time zones and vocabulary."""

from typing import Literal

from screening.config import ScreeningConfig
from screening.schemas import ConversationState

DEFAULT_COUNTRY: Literal["ES", "MX"] = "ES"


def candidate_country(state: ConversationState) -> Literal["ES", "MX"]:
    """The confirmed city's country, else the phone-prefix or chat-picker hint."""
    location = state.profile.location.value
    if location is not None:
        return location.country
    return state.country_hint or DEFAULT_COUNTRY


def candidate_timezone(state: ConversationState, config: ScreeningConfig) -> str:
    return config.timezone_for(candidate_country(state))
