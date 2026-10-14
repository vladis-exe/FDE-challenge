"""Recruiter actions and the queue query. Overrides never call the engine (CONTRACTS §5)."""

from django.contrib.auth.models import AbstractBaseUser
from django.db import transaction
from django.db.models import Case, F, IntegerField, Q, QuerySet, Value, When
from django.utils import timezone

from apps.candidates.models import Conversation, ReviewAction
from apps.messaging.models import Event
from screening.record import final_record
from screening.schemas import ConversationState
from screening.schemas import Status as EngineStatus

Status = Conversation.Status

OVERRIDE_STATUS = {
    ReviewAction.Action.APPROVE: Status.QUALIFIED,
    ReviewAction.Action.REJECT: Status.DISQUALIFIED,
    ReviewAction.Action.NEEDS_REVIEW: Status.NEEDS_REVIEW,
}

# Queue order: what a recruiter should act on first.
STATUS_PRIORITY = [
    Status.QUALIFIED,
    Status.NEEDS_REVIEW,
    Status.IN_PROGRESS,
    Status.DISQUALIFIED,
    Status.ABANDONED,
    Status.OPTED_OUT,
]


def record_review(
    conversation: Conversation, user: AbstractBaseUser, action: str, note: str = ""
) -> ReviewAction:
    """Log a recruiter action; approve/reject/needs_review also override the status.

    The override is written into `state` as well as the mirrored column: the worker copies
    `state.status` onto the column on every turn, so changing only the column would be undone
    by the candidate's next message. From then on the engine treats the screening as finished.
    """
    with transaction.atomic():
        conversation = Conversation.objects.select_for_update().get(pk=conversation.pk)
        review = ReviewAction.objects.create(
            conversation=conversation, user=user, action=action, note=note
        )
        new_status = OVERRIDE_STATUS.get(action)
        if new_status is not None and new_status != conversation.status:
            previous = conversation.status
            state = ConversationState.model_validate(conversation.state)
            state.status = EngineStatus(new_status)
            conversation.state = state.model_dump(mode="json")
            conversation.status = new_status
            conversation.final_record = final_record(state)
            conversation.completed_at = conversation.completed_at or timezone.now()
            conversation.next_tick_at = None
            conversation.save()
            Event.objects.create(
                conversation=conversation,
                type="recruiter_override",
                data={"from": previous, "to": new_status, "by": user.get_username(), "note": note},
                created_at=timezone.now(),
            )
    return review


def queue(
    *,
    q: str = "",
    status: str = "",
    country: str = "",
    city: str = "",
    availability: str = "",
    schedule: str = "",
) -> QuerySet[Conversation]:
    conversations = Conversation.objects.select_related("candidate")
    if q:
        digits = "".join(ch for ch in q if ch.isdigit())
        match = Q(candidate__name__icontains=q)
        if digits:
            match |= Q(candidate__phone__contains=digits)
        conversations = conversations.filter(match)
    if status:
        conversations = conversations.filter(status=status)
    if country:
        conversations = conversations.filter(country=country)
    if city:
        conversations = conversations.filter(city=city)
    # The JSON list as text, e.g. '["part_time", "weekends"]'; the option keys don't overlap,
    # and this lookup works the same on SQLite and Postgres.
    if availability:
        conversations = conversations.filter(
            state__profile__availability__value__icontains=f'"{availability}"'
        )
    if schedule:
        conversations = conversations.filter(
            state__profile__schedule__value__icontains=f'"{schedule}"'
        )
    priority = Case(
        *(When(status=s, then=Value(i)) for i, s in enumerate(STATUS_PRIORITY)),
        output_field=IntegerField(),
    )
    return conversations.order_by(priority, F("completed_at").desc(nulls_last=True), "-started_at")
