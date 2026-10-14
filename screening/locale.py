"""Where the candidate is, for time zones and vocabulary."""

from typing import Literal

from screening.config import ScreeningConfig
from screening.schemas import ConversationState

DEFAULT_COUNTRY: Literal["ES", "MX"] = "ES"


def candidate_country(state: ConversationState) -> Literal["ES", "MX"]:
    """The phone-prefix or chat-picker hint, replaced by the city's country once accepted."""
    return state.country_hint or DEFAULT_COUNTRY


def candidate_timezone(state: ConversationState, config: ScreeningConfig) -> str:
    return config.timezone_for(candidate_country(state))
