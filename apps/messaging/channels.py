"""Channel adapters (CONTRACTS §5): deliver one outbound message, return the provider's ID."""

from functools import cache
from typing import Protocol

from django.conf import settings
from twilio.rest import Client

from apps.candidates.models import Conversation
from screening.schemas import OutboundMessage


class ChannelAdapter(Protocol):
    def send(self, conversation: Conversation, message: OutboundMessage) -> str | None: ...


class WebChannel:
    """The chat page polls the database, so there is nothing to push."""

    def send(self, conversation: Conversation, message: OutboundMessage) -> str | None:
        return None


class WhatsAppChannel:
    """Twilio WhatsApp. Inside the 24 h customer-service window free text needs no template."""

    def send(self, conversation: Conversation, message: OutboundMessage) -> str | None:
        phone = conversation.candidate.phone
        if not phone:
            raise ValueError("WhatsApp conversation without a phone number")
        sender = settings.TWILIO_WHATSAPP_FROM
        sent = twilio_client().messages.create(
            from_=sender if sender.startswith("whatsapp:") else f"whatsapp:{sender}",
            to=f"whatsapp:{phone}",
            body=message.text,
        )
        return sent.sid


@cache
def twilio_client() -> Client:
    return Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)


def channel_for(conversation: Conversation) -> ChannelAdapter:
    if conversation.channel == Conversation.Channel.WHATSAPP:
        return WhatsAppChannel()
    return WebChannel()
