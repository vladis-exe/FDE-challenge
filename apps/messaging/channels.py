"""Channel adapters (CONTRACTS §5): deliver one outbound message, return the provider's ID."""

from typing import Protocol

from apps.candidates.models import Conversation
from screening.schemas import OutboundMessage


class ChannelAdapter(Protocol):
    def send(self, conversation: Conversation, message: OutboundMessage) -> str | None: ...


class WebChannel:
    """The chat page polls the database, so there is nothing to push."""

    def send(self, conversation: Conversation, message: OutboundMessage) -> str | None:
        return None


class WhatsAppChannel:
    def send(self, conversation: Conversation, message: OutboundMessage) -> str | None:
        raise NotImplementedError("WhatsApp sending lands in A4")


def channel_for(conversation: Conversation) -> ChannelAdapter:
    if conversation.channel == Conversation.Channel.WHATSAPP:
        return WhatsAppChannel()
    return WebChannel()
