import uuid

from django.conf import settings
from django.db import models


class Candidate(models.Model):
    # Null for web-chat candidates; unique so a second WhatsApp application resumes, not restarts.
    phone = models.CharField(max_length=20, unique=True, null=True, blank=True)
    name = models.CharField(max_length=200, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return self.name or self.masked_phone or f"Candidate {self.pk}"

    @property
    def masked_phone(self) -> str:
        """Phone with the middle digits hidden, for logs and lists."""
        if not self.phone:
            return ""
        return f"{self.phone[:4]}…{self.phone[-3:]}"


class Conversation(models.Model):
    """One screening. `state` is the engine's ConversationState; the other columns mirror it."""

    # Values match screening.schemas.Channel / Status / Stage.
    class Channel(models.TextChoices):
        WEB = "web", "Web chat"
        WHATSAPP = "whatsapp", "WhatsApp"

    class Status(models.TextChoices):
        IN_PROGRESS = "in_progress"
        QUALIFIED = "qualified"
        NEEDS_REVIEW = "needs_review"
        DISQUALIFIED = "disqualified"
        ABANDONED = "abandoned"
        OPTED_OUT = "opted_out"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    candidate = models.ForeignKey(Candidate, on_delete=models.CASCADE, related_name="conversations")
    channel = models.CharField(max_length=16, choices=Channel.choices)
    # Matches a key of ScreeningConfig.vacancies (CONTRACTS §7).
    vacancy_id = models.CharField(max_length=64, db_index=True)

    status = models.CharField(
        max_length=16, choices=Status.choices, default=Status.IN_PROGRESS, db_index=True
    )
    stage = models.CharField(max_length=16, blank=True)
    language = models.CharField(max_length=2, blank=True)
    country = models.CharField(max_length=2, blank=True)
    city = models.CharField(max_length=64, blank=True)
    # Ranking only, inside a status: the dashboard queue sorts by it, it never decides anything.
    preference_score = models.FloatField(default=0.0, db_index=True)

    state = models.JSONField(default=dict)

    final_record = models.JSONField(null=True, blank=True)
    summary = models.TextField(blank=True)

    started_at = models.DateTimeField(auto_now_add=True)
    last_inbound_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    next_tick_at = models.DateTimeField(null=True, blank=True, db_index=True)

    class Meta:
        ordering = ["-started_at"]

    def __str__(self) -> str:
        return f"{self.candidate} ({self.channel}, {self.status})"


class ReviewAction(models.Model):
    class Action(models.TextChoices):
        APPROVE = "approve"
        REJECT = "reject"
        NEEDS_REVIEW = "needs_review"
        NOTE = "note"

    conversation = models.ForeignKey(
        Conversation, on_delete=models.CASCADE, related_name="review_actions"
    )
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    action = models.CharField(max_length=16, choices=Action.choices)
    note = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.action} by {self.user} on {self.conversation_id}"
