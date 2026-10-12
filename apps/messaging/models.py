from django.db import models

from apps.candidates.models import Conversation


class Message(models.Model):
    """Every inbound and outbound message. Inbound rows double as the worker's queue."""

    class Direction(models.TextChoices):
        IN = "in"
        OUT = "out"

    class Kind(models.TextChoices):
        INBOUND = "inbound"
        # Outbound kinds match screening.schemas.OutboundMessage.kind.
        REPLY = "reply"
        REMINDER = "reminder"
        CLOSE = "close"

    class Media(models.TextChoices):
        NONE = "none"
        AUDIO = "audio"
        IMAGE = "image"
        STICKER = "sticker"
        OTHER = "other"

    conversation = models.ForeignKey(
        Conversation, on_delete=models.CASCADE, related_name="messages"
    )
    direction = models.CharField(max_length=3, choices=Direction.choices)
    kind = models.CharField(max_length=16, choices=Kind.choices)
    text = models.TextField(blank=True)
    media = models.CharField(max_length=16, choices=Media.choices, default=Media.NONE)
    # Twilio MessageSid: inbound for webhook idempotency, outbound once sent.
    provider_sid = models.CharField(max_length=64, unique=True, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(null=True, blank=True)
    suppressed = models.BooleanField(default=False)
    send_error = models.TextField(blank=True)

    class Meta:
        # Primary key, not created_at, defines arrival order: it is strictly monotonic.
        ordering = ["id"]
        indexes = [
            models.Index(
                fields=["conversation", "direction", "processed_at"], name="msg_queue_idx"
            ),
        ]

    def __str__(self) -> str:
        return f"{self.direction}/{self.kind}: {self.text[:40]}"


class Event(models.Model):
    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE, related_name="events")
    type = models.CharField(max_length=32, db_index=True)
    data = models.JSONField(default=dict, blank=True)
    # Set from the engine event's `at` (not auto_now_add), so evals and time-scaled runs keep
    # the engine's clock.
    created_at = models.DateTimeField()

    class Meta:
        ordering = ["created_at", "id"]

    def __str__(self) -> str:
        return f"{self.type} @ {self.created_at:%Y-%m-%d %H:%M:%S}"
