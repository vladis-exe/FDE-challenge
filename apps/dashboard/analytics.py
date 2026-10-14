"""Screening analytics for the dashboard: funnel, outcomes, timing, reminders and LLM cost.

Aggregated in Python from a handful of queries: at ~1,000 conversations a week this is a few
thousand rows, and plain Python is easier to read and verify than database-specific SQL.
"""

import statistics
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from django.db.models import F, Max, Min

from apps.candidates.models import Conversation
from apps.dashboard.presenters import STAGE_LABELS, field_title, vacancies, vacancy_title
from apps.messaging.models import Event, Message
from screening.llm.pricing import call_cost

FINISHED = {
    Conversation.Status.QUALIFIED,
    Conversation.Status.NEEDS_REVIEW,
    Conversation.Status.DISQUALIFIED,
}
REASON_LABELS = {
    "no_license": "No driver's license",
    "out_of_area": "City not served",
    "recruiter decision": "Recruiter decision",
}


def reason_label(reason: str) -> str:
    """Outcome strings are generated per field (CONTRACTS §7): no_<name> for a boolean knockout."""
    if reason in REASON_LABELS:
        return REASON_LABELS[reason]
    if reason.startswith("no_"):
        return f"No {field_title(reason.removeprefix('no_')).lower()}"
    return reason


@dataclass
class Bar:
    label: str
    count: int
    share: float  # 0-1, of the bar chart's base


@dataclass
class LLMUsage:
    purpose: str
    calls: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    cost: float = 0.0
    latency_ms: list[int] = field(default_factory=list)

    @property
    def median_latency_ms(self) -> int:
        return int(statistics.median(self.latency_ms)) if self.latency_ms else 0


@dataclass
class Report:
    started: int
    finished: int
    qualified: int
    median_time_to_complete: timedelta | None
    reminded: int
    replied_after_reminder: int
    funnel: list[Bar]
    outcomes: list[Bar]
    disqualify_reasons: list[Bar]
    abandoned_at: list[Bar]
    jobs: list[Bar]
    llm: list[LLMUsage]
    llm_cost_total: float

    @property
    def median_time_label(self) -> str:
        if self.median_time_to_complete is None:
            return "—"
        minutes, seconds = divmod(round(self.median_time_to_complete.total_seconds()), 60)
        hours, minutes = divmod(minutes, 60)
        return f"{hours}h {minutes}m" if hours else f"{minutes}m {seconds:02d}s"

    @property
    def cost_per_conversation(self) -> float | None:
        return self.llm_cost_total / self.started if self.started else None


def bars(counts: Counter, base: int, labels: dict | None = None) -> list[Bar]:
    return [
        Bar((labels or {}).get(key, key), count, count / base if base else 0)
        for key, count in counts.most_common()
    ]


def build(since: datetime | None = None, vacancy_id: str = "") -> Report:
    conversations = Conversation.objects.all()
    if since:
        conversations = conversations.filter(started_at__gte=since)
    if vacancy_id:
        conversations = conversations.filter(vacancy_id=vacancy_id)
    rows = list(
        conversations.values(
            "id",
            "vacancy_id",
            "status",
            "stage",
            "started_at",
            "completed_at",
            "final_record",
            # Decoded JSON (F), not text (KT): SQLite's KT gives "null" for a JSON null.
            consent_at=F("state__consent_at"),
            current_field=F("state__current_field"),
            fields=F("state__profile__fields"),
        )
    )
    ids = [row["id"] for row in rows]
    started = len(rows)

    # Funnel: phases for every job; with one job selected, each required field in between.
    read_back = set(
        Event.objects.filter(conversation_id__in=ids, type="stage_entered", data__stage="confirm")
        .values_list("conversation_id", flat=True)
        .distinct()
    )
    steps: list[tuple[str, int]] = [
        ("Started", started),
        ("Consented", sum(1 for row in rows if row["consent_at"])),
    ]
    vacancy = vacancies().get(vacancy_id)
    for spec in vacancy.asked if vacancy else []:
        if spec.requirement == "required":
            answered = sum(1 for row in rows if _answered(row, spec.name))
            steps.append((f"Answered: {field_title(spec.name).lower()}", answered))
    steps += [
        ("Reached the read-back", len(read_back)),
        ("Finished", sum(1 for row in rows if row["status"] in FINISHED)),
    ]
    funnel = [Bar(label, count, count / started if started else 0) for label, count in steps]

    statuses = Counter(row["status"] for row in rows)
    status_labels = dict(Conversation.Status.choices)
    finished_rows = [row for row in rows if row["status"] in FINISHED]
    durations = [
        row["completed_at"] - row["started_at"] for row in finished_rows if row["completed_at"]
    ]
    reasons = Counter(
        row["final_record"]["disqualify_reason"] or "recruiter decision"
        for row in rows
        if row["status"] == Conversation.Status.DISQUALIFIED and row["final_record"]
    )
    abandoned = Counter(
        field_title(row["current_field"])
        if row["stage"] == "collecting" and row["current_field"]
        else STAGE_LABELS.get(row["stage"], row["stage"])
        for row in rows
        if row["status"] == Conversation.Status.ABANDONED
    )
    jobs = Counter(vacancy_title(row["vacancy_id"]) for row in rows)
    # Re-engagement: an inbound message after the first reminder.
    first_reminder = dict(
        Event.objects.filter(conversation_id__in=ids, type="reminder_sent")
        .values("conversation_id")
        .annotate(at=Min("created_at"))
        .values_list("conversation_id", "at")
    )
    last_inbound = dict(
        Message.objects.filter(conversation_id__in=first_reminder, direction=Message.Direction.IN)
        .values("conversation_id")
        .annotate(at=Max("created_at"))
        .values_list("conversation_id", "at")
    )
    replied = sum(
        1 for cid, at in first_reminder.items() if cid in last_inbound and last_inbound[cid] > at
    )

    usage: dict[str, LLMUsage] = {}
    for data in Event.objects.filter(conversation_id__in=ids, type="llm_call").values_list(
        "data", flat=True
    ):
        line = usage.setdefault(data.get("purpose", "?"), LLMUsage(data.get("purpose", "?")))
        line.calls += 1
        line.input_tokens += data.get("input_tokens", 0)
        line.output_tokens += data.get("output_tokens", 0)
        line.cost += call_cost(data)
        line.latency_ms.append(data.get("latency_ms", 0))

    return Report(
        started=started,
        finished=len(finished_rows),
        qualified=statuses[Conversation.Status.QUALIFIED],
        median_time_to_complete=statistics.median(durations) if durations else None,
        reminded=len(first_reminder),
        replied_after_reminder=replied,
        funnel=funnel,
        outcomes=bars(statuses, started, status_labels),
        disqualify_reasons=bars(
            Counter({reason_label(r): n for r, n in reasons.items()}), sum(reasons.values())
        ),
        abandoned_at=bars(abandoned, sum(abandoned.values())),
        jobs=bars(jobs, started),
        llm=sorted(usage.values(), key=lambda line: line.cost, reverse=True),
        llm_cost_total=sum(line.cost for line in usage.values()),
    )


def _answered(row: dict, field: str) -> bool:
    """The candidate gave this field an answer the engine kept, accepted or flagged."""
    value = (row["fields"] or {}).get(field) or {}
    return value.get("status") in ("accepted", "flagged")
